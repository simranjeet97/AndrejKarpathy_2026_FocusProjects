import asyncio
import logging
from typing import TypedDict, Optional, Any
from ..models import PREvent, ContextPack, ReviewResponse
from ..context.harvester import ContextHarvester
from ..context.ranker import ContextRanker
from ..prompt.assembler import PromptAssembler
from ..llm.ollama_client import OllamaClient
from ..output.dispatcher import ReviewDispatcher
from ..memory.long_term import LongTermMemory
from ..config.settings import Settings

logger = logging.getLogger(__name__)

class AgentState(TypedDict):
    pr_event: PREvent
    raw_bundle: Optional[Any]
    context_pack: Optional[ContextPack]
    review: Optional[ReviewResponse]
    retry_count: int
    error: Optional[str]
    should_retry: bool

class ReviewAgent:
    """LangGraph orchestration agent that runs the code review workflow node by node."""

    def __init__(
        self,
        harvester: ContextHarvester,
        ranker: ContextRanker,
        assembler: PromptAssembler,
        ollama: OllamaClient,
        dispatcher: ReviewDispatcher,
        memory: LongTermMemory,
        settings: Settings
    ) -> None:
        """
        Initialize the ReviewAgent with all required dependencies.
        """
        self.harvester = harvester
        self.ranker = ranker
        self.assembler = assembler
        self.ollama = ollama
        self.dispatcher = dispatcher
        self.memory = memory
        self.settings = settings
        
        # Instantiate short-term memory directly using Dragonfly url config
        from ..memory.short_term import ShortTermMemory
        self.short_term = ShortTermMemory(settings.DRAGONFLY_URL)
        
        # Build and compile the state graph
        self.graph = self.build_graph()

    def build_graph(self) -> Any:
        """
        Construct and compile the LangGraph state machine.

        Returns:
            The compiled LangGraph workflow.
        """
        from langgraph.graph import StateGraph, START, END
        
        workflow = StateGraph(AgentState)
        
        # Add Nodes
        workflow.add_node("harvest", self.harvest_node)
        workflow.add_node("rank", self.rank_node)
        workflow.add_node("generate", self.generate_node)
        workflow.add_node("critique", self.critique_node)
        workflow.add_node("dispatch", self.dispatch_node)
        
        # Add Node Transitions
        workflow.add_edge(START, "harvest")
        workflow.add_edge("harvest", "rank")
        workflow.add_edge("rank", "generate")
        workflow.add_edge("generate", "critique")
        
        # Add Conditional Edge from critique
        workflow.add_conditional_edges(
            "critique",
            self.should_retry_edge,
            {
                "generate": "generate",
                "dispatch": "dispatch"
            }
        )
        
        # Add Edge from dispatch to completion
        workflow.add_edge("dispatch", END)
        
        return workflow.compile()


    async def harvest_node(self, state: AgentState) -> AgentState:
        """
        Node: Collect raw context for the PR using the harvester.
        """
        try:
            bundle = await self.harvester.collect(state["pr_event"])
            state["raw_bundle"] = bundle
            state["error"] = None
        except Exception as e:
            state["error"] = f"Harvesting context failed: {str(e)}"
            logger.error(f"Error in harvest_node: {e}", exc_info=True)
        return state

    async def rank_node(self, state: AgentState) -> AgentState:
        """
        Node: Score, rank, and compress the collected context to fit the token budget.
        """
        if state.get("error"):
            return state

        bundle = state.get("raw_bundle")
        if not bundle:
            state["error"] = "No context bundle found to rank"
            return state

        try:
            # self.ranker.rank_and_compress is a synchronous CPU/memory operation
            context_pack = self.ranker.rank_and_compress(
                bundle,
                state["pr_event"],
                budget=self.settings.MAX_CONTEXT_TOKENS
            )
            state["context_pack"] = context_pack
            state["error"] = None
        except Exception as e:
            state["error"] = f"Ranking context failed: {str(e)}"
            logger.error(f"Error in rank_node: {e}", exc_info=True)
        return state

    async def generate_node(self, state: AgentState) -> AgentState:
        """
        Node: Assemble the prompt and query the LLM for the review response.
        """
        if state.get("error"):
            return state

        context_pack = state.get("context_pack")
        if not context_pack:
            state["error"] = "No context pack found to generate review"
            return state

        try:
            bundle = state.get("raw_bundle")
            jira_ticket = bundle.jira_ticket if bundle else None

            # Build prompt
            prompt = self.assembler.build(context_pack, state["pr_event"], jira_ticket)

            import time
            import json
            start_time = time.time()
            
            # Call Ollama (expecting a valid JSON conforming to ReviewResponse)
            response_json = await asyncio.to_thread(self.ollama.generate, prompt, expect_json=True)
            latency_ms = (time.time() - start_time) * 1000.0

            # Inject metadata fields that the LLM cannot know itself
            if isinstance(response_json, dict):
                response_json.setdefault("model_used", self.settings.OLLAMA_MODEL_CODE)
                response_json.setdefault("latency_ms", round(latency_ms, 2))
                # Estimate token usage (roughly 4 characters per token)
                estimated_tokens = (len(prompt) + len(json.dumps(response_json))) // 4
                response_json.setdefault("tokens_used", estimated_tokens)

            # Map response JSON to model
            review = ReviewResponse.model_validate(response_json)
            state["review"] = review
            state["error"] = None
        except Exception as e:
            state["error"] = f"Review generation failed: {str(e)}"
            logger.error(f"Error in generate_node: {e}", exc_info=True)
        return state

    async def critique_node(self, state: AgentState) -> AgentState:
        """
        Node: Parse and critique the review response, checking JSON validity.
        """
        # If there's an error (like parse error) and we can retry, let's retry
        if state.get("error") and state.get("retry_count", 0) < 2:
            state["should_retry"] = True
            state["retry_count"] = state.get("retry_count", 0) + 1
            # Clear error for the retry attempt
            state["error"] = None
            logger.info(f"Review generation failed with error. Retrying review generation (attempt {state['retry_count']}).")
            return state

        review = state.get("review")
        retry_count = state.get("retry_count", 0)

        if review and review.confidence < 0.6 and retry_count < 2:
            state["should_retry"] = True
            state["retry_count"] = retry_count + 1
            logger.info(f"Review confidence low ({review.confidence}). Retrying review generation (attempt {state['retry_count']}).")
        else:
            state["should_retry"] = False

        return state

    async def dispatch_node(self, state: AgentState) -> AgentState:
        """
        Node: Post the completed review comments to GitHub and save to long-term memory.
        """
        if state.get("error"):
            return state

        review = state.get("review")
        if not review:
            state["error"] = "No review found to dispatch"
            return state

        try:
            pr_event = state["pr_event"]
            # Call dispatcher (ReviewDispatcher) to post to GitHub and log to Excel
            await asyncio.to_thread(
                self.dispatcher.dispatch,
                pr_event,
                review
            )
            
            # Store in SQLite and ChromaDB via LongTermMemory
            # memory.store_review is an async method
            await self.memory.store_review(pr_event, review)
            state["error"] = None
        except Exception as e:
            state["error"] = f"Dispatch failed: {str(e)}"
            logger.error(f"Error in dispatch_node: {e}", exc_info=True)
            
        return state

    def should_retry_edge(self, state: AgentState) -> str:
        """
        Conditional Edge: Decide if we should critique/retry or proceed to dispatch.
        """
        return "generate" if state.get("should_retry") else "dispatch"

    async def run(self, pr_event: PREvent) -> AgentState:
        """
        Execute the completed LangGraph workflow for the given PR event.
        """
        pr_id_str = str(pr_event.pr_id)
        
        # 1. Check short-term memory cache first
        try:
            cached_review = await self.short_term.get_review(pr_id_str)
            if cached_review:
                logger.info(f"Retrieved cached review for PR {pr_event.pr_id} from short-term memory")
                cached_ctx = await self.short_term.get_context(pr_id_str)
                return {
                    "pr_event": pr_event,
                    "raw_bundle": None,
                    "context_pack": cached_ctx,
                    "review": cached_review,
                    "retry_count": 0,
                    "error": None,
                    "should_retry": False
                }
        except Exception as e:
            logger.warning(f"Failed to check short-term memory cache: {e}")

        # 2. Invoke the compiled graph
        initial_state: AgentState = {
            "pr_event": pr_event,
            "raw_bundle": None,
            "context_pack": None,
            "review": None,
            "retry_count": 0,
            "error": None,
            "should_retry": False
        }
        
        try:
            final_state = await self.graph.ainvoke(initial_state)
            
            # Cache the successful review and context pack in short-term memory
            if final_state.get("review") and not final_state.get("error"):
                await self.short_term.cache_review(pr_id_str, final_state["review"])
                if final_state.get("context_pack"):
                    await self.short_term.cache_context(pr_id_str, final_state["context_pack"])
                    
            return final_state
        except Exception as e:
            logger.error(f"Graph invocation failed: {e}", exc_info=True)
            initial_state["error"] = f"Graph execution failed: {str(e)}"
            return initial_state

