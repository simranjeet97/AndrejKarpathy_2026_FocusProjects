from typing import List, Dict, Any, Optional
from evalops.models import EvalTask, EvalRun
from evalops.judge import LLMJudge

class PairwiseComparator:
    """
    Compares LLM evaluation runs deterministically or via LLM judge.
    """

    def __init__(self, judge: Optional[LLMJudge] = None):
        self.judge = judge or LLMJudge()

    def compare(self, run_a: EvalRun, run_b: EvalRun) -> Dict[str, Any]:
        """
        Compare two runs deterministically. Run B is the candidate, Run A is the baseline.

        Returns:
            Dict[str, Any]: Comparison results containing winner, score_delta, latency_delta_ms, and token_delta.
        """
        score_delta = run_b.score - run_a.score
        latency_delta_ms = run_b.latency_ms - run_a.latency_ms
        token_delta = run_b.tokens_used - run_a.tokens_used

        if run_a.score > run_b.score:
            winner = "a"
        elif run_b.score > run_a.score:
            winner = "b"
        else:
            # Tie breaker: lower latency wins
            if run_a.latency_ms < run_b.latency_ms:
                winner = "a"
            elif run_b.latency_ms < run_a.latency_ms:
                winner = "b"
            else:
                winner = "tie"

        return {
            "winner": winner,
            "score_delta": score_delta,
            "latency_delta_ms": latency_delta_ms,
            "token_delta": token_delta
        }

    async def llm_compare(self, task: EvalTask, run_a: EvalRun, run_b: EvalRun) -> Dict[str, Any]:
        """
        Compare two outputs using the LLM judge.

        Returns:
            Dict[str, Any]: Similar structure as compare() with winner determined by LLM, plus LLM reason.
        """
        system_prompt = (
            "You are an expert evaluator. Compare the two candidate outputs (A and B) generated for the given task.\n"
            "Pick the winner based on correctness, clarity, and detail.\n"
            "Return ONLY a JSON object: {\"winner\": \"A\"|\"B\"|\"tie\", \"reason\": \"<one sentence>\"}"
        )
        prompt = (
            f"Task Prompt: {task.input_prompt}\n"
            f"Expected Output: {task.expected_output}\n\n"
            f"Candidate A output: {run_a.output}\n\n"
            f"Candidate B output: {run_b.output}\n\n"
            f"Evaluate both and select the winner."
        )

        winner = "tie"
        reason = "Fallback tie due to LLM comparison failure"

        try:
            resp = await self.judge.client.generate(
                model=self.judge.settings.judge_model,
                prompt=prompt,
                system_prompt=system_prompt
            )
            parsed = self.judge._extract_json(resp["text"])
            if parsed and "winner" in parsed:
                winner_val = str(parsed.get("winner", "tie")).lower()
                if winner_val in ["a", "b", "tie"]:
                    winner = winner_val
                reason = str(parsed.get("reason", ""))
        except Exception:
            pass

        score_delta = run_b.score - run_a.score
        latency_delta_ms = run_b.latency_ms - run_a.latency_ms
        token_delta = run_b.tokens_used - run_a.tokens_used

        return {
            "winner": winner,
            "reason": reason,
            "score_delta": score_delta,
            "latency_delta_ms": latency_delta_ms,
            "token_delta": token_delta
        }

    @staticmethod
    def rank_runs(runs: List[EvalRun]) -> List[EvalRun]:
        """
        Rank a list of runs. Sorts primarily by score descending, and secondarily by latency ascending.

        Returns:
            List[EvalRun]: Sorted list of runs.
        """
        # Python sort is stable; sort by latency ascending first, then score descending.
        sorted_runs = sorted(runs, key=lambda r: r.latency_ms)
        sorted_runs = sorted(sorted_runs, key=lambda r: r.score, reverse=True)
        return sorted_runs
