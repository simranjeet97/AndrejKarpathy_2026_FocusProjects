import json
import re
import logging
from typing import List, Dict, Any, Optional

from evalops.config import get_settings
from evalops.models import EvalTask, EvalRun
from evalops.ollama_client import OllamaClient
from evalops.scorer import EvalScorer

logger = logging.getLogger(__name__)

JUDGE_SYSTEM_PROMPT = (
    "You are an evaluator. Score the following model output against the expected output.\n"
    "Return ONLY a JSON object: {\"score\": <float 0-1>, \"reason\": \"<one sentence>\", \"hallucination\": <bool>}"
)

class LLMJudge:
    """
    LLM-as-a-Judge using Ollama. Evaluates semantic correctness and detects hallucinations.
    """

    def __init__(self, settings: Optional[Any] = None):
        self.settings = settings or get_settings()
        self.client = OllamaClient()

    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        """Robustly extracts and parses JSON from text, handling markdown fences and partial strings."""
        text_clean = text.strip()
        
        # Strip markdown fences if present
        if text_clean.startswith("```"):
            # Match block contents
            match = re.search(r'```(?:json)?\s*(.*?)\s*```', text_clean, re.DOTALL | re.IGNORECASE)
            if match:
                text_clean = match.group(1).strip()
        
        # Try direct load
        try:
            return json.loads(text_clean)
        except json.JSONDecodeError:
            pass

        # Try searching for first '{' and last '}'
        try:
            start_idx = text_clean.find('{')
            end_idx = text_clean.rfind('}')
            if start_idx != -1 and end_idx != -1:
                candidate = text_clean[start_idx:end_idx + 1]
                return json.loads(candidate)
        except Exception:
            pass

        return None

    async def score(self, task: EvalTask, run: EvalRun) -> Dict[str, Any]:
        """
        Evaluate output of a run against the task expectation.
        
        Returns:
            Dict[str, Any]: Contains keys 'score', 'reason', 'hallucination'.
        """
        prompt = (
            f"Task: {task.input_prompt}\n"
            f"Expected: {task.expected_output}\n"
            f"Actual output: {run.output}\n"
            f"Score it."
        )

        try:
            resp = await self.client.generate(
                model=self.settings.judge_model,
                prompt=prompt,
                system_prompt=JUDGE_SYSTEM_PROMPT
            )
            parsed = self._extract_json(resp["text"])
            if parsed and "score" in parsed:
                # Ensure correct types
                return {
                    "score": float(parsed.get("score", 0.0)),
                    "reason": str(parsed.get("reason", "")),
                    "hallucination": bool(parsed.get("hallucination", False))
                }
        except Exception as e:
            logger.warning(f"Ollama judge execution failed: {e}")

        # Fallback to deterministic composite score
        fallback_score = EvalScorer.composite_score(run.output, task.expected_output)
        return {
            "score": fallback_score,
            "reason": "Fallback to composite score due to judge error",
            "hallucination": False
        }

    async def score_batch(self, tasks: List[EvalTask], runs: List[EvalRun]) -> List[Dict[str, Any]]:
        """
        Scores a list of tasks and runs.
        """
        results = []
        for task, run in zip(tasks, runs):
            results.append(await self.score(task, run))
        return results


class HallucinationDetector:
    """
    Detects hallucinations by calculating token overlap metrics against reference materials
    or calling LLM judge.
    """

    @staticmethod
    def check(output: str, known_facts: List[str]) -> float:
        """
        Calculates fraction of output tokens that do not appear in the known reference facts.
        0.0 means no hallucination (perfect overlap), 1.0 means full hallucination.
        """
        # Helper to tokenize
        def tokenize(text: str) -> set:
            return set(re.findall(r'\w+', text.lower()))

        tokens_out = tokenize(output)
        if not tokens_out:
            return 0.0

        tokens_facts = set()
        for fact in known_facts:
            tokens_facts.update(tokenize(fact))

        hallucinated_tokens = tokens_out - tokens_facts
        return float(len(hallucinated_tokens)) / len(tokens_out)

    async def check_with_judge(self, task: EvalTask, run: EvalRun) -> bool:
        """
        Delegates the hallucination check to LLMJudge.
        """
        judge = LLMJudge()
        res = await judge.score(task, run)
        return res.get("hallucination", False)
