import logging
import tiktoken
from typing import List, Dict, Tuple, Optional, Any
from ..models import PREvent, ContextPack, DocChunk, SourceType
from .templates import (
    SYSTEM_PROMPT,
    TICKET_CONTEXT_LAYER,
    ARCH_CONTEXT_LAYER,
    STANDARDS_LAYER,
    DIFF_LAYER,
    EXAMPLES_LAYER
)

logger = logging.getLogger(__name__)

class PromptAssembler:
    """Assembles context layers, coding standards, diffs, and Jira info into a final structured prompt under token budget."""

    def __init__(self, max_context_tokens: int) -> None:
        """
        Initialize the PromptAssembler.

        Args:
            max_context_tokens: Total token budget allowed for the prompt.
        """
        self.max_context_tokens = max_context_tokens

    def build(self, context_pack: ContextPack, pr_event: PREvent, jira_ticket: Optional[Any] = None) -> str:
        """
        Build the final prompt string from the given context pack and PR event.

        Args:
            context_pack: Selected context pack.
            pr_event: The Pull Request event.
            jira_ticket: Optional JiraTicket model details.

        Returns:
            A formatted prompt string ready for Ollama ingestion.
        """
        layers = self._build_layers(context_pack, pr_event, jira_ticket)
        trimmed_contents = self._trim_to_budget(layers, self.max_context_tokens)
        return "\n\n".join(trimmed_contents)

    def _build_layers(self, context_pack: ContextPack, pr_event: PREvent, jira_ticket: Optional[Any] = None) -> List[Tuple[str, str, int]]:
        """
        Construct the individual text layers (Jira, diff, arch, standards) with priorities.

        Args:
            context_pack: Selected context pack.
            pr_event: The Pull Request event.
            jira_ticket: Optional JiraTicket model details.

        Returns:
            A list of tuples: (layer_name, text_content, priority_level).
        """
        layers = []

        # 1. System Prompt (Priority 10)
        layers.append(("system", SYSTEM_PROMPT, 10))

        # 2. Jira Ticket (Priority 9)
        if jira_ticket:
            ticket_text = TICKET_CONTEXT_LAYER.format(
                ticket_id=jira_ticket.id,
                summary=jira_ticket.summary,
                description=jira_ticket.description or "No description provided."
            )
            layers.append(("ticket", ticket_text, 9))
        elif pr_event.jira_ticket_id:
            ticket_text = TICKET_CONTEXT_LAYER.format(
                ticket_id=pr_event.jira_ticket_id,
                summary="Unknown Summary",
                description="Ticket details not retrieved."
            )
            layers.append(("ticket", ticket_text, 9))

        # 3. Coding Standards (Priority 8)
        standards_text = self._format_chunks_by_type(context_pack.chunks, SourceType.STANDARD)
        if standards_text:
            layers.append(("standards", STANDARDS_LAYER.format(standards_text=standards_text), 8))

        # 4. Architectural docs (Priority 7)
        arch_chunks_text = self._format_chunks_by_type(context_pack.chunks, SourceType.ARCH_DOC)
        if arch_chunks_text:
            layers.append(("arch", ARCH_CONTEXT_LAYER.format(arch_chunks_text=arch_chunks_text), 7))

        # 5. Diffs (Priority 6)
        # Allocate a large portion of the budget to diff, e.g. up to 60% of max_context_tokens
        max_diff_tokens = int(self.max_context_tokens * 0.6)
        diff_text = self._format_diff_section(pr_event, max_diff_tokens)
        if diff_text:
            layers.append(("diff", DIFF_LAYER.format(file_count=len(pr_event.changed_files), diff_text=diff_text), 6))

        # 6. Past Similar PRs/Examples (Priority 5)
        examples_text = self._format_chunks_by_type(context_pack.chunks, SourceType.PR_EXAMPLE)
        if examples_text:
            layers.append(("examples", EXAMPLES_LAYER.format(examples_text=examples_text), 5))

        return layers

    def _trim_to_budget(self, layers: List[Tuple[str, str, int]], max_tokens: int) -> List[str]:
        """
        Drop lower-priority layers if the total prompt token count exceeds the maximum limit.

        Args:
            layers: List of prioritize layers.
            max_tokens: The absolute limit of tokens.

        Returns:
            A list of formatted text strings representing the final included layers.
        """
        # Sort layers by priority descending
        sorted_layers = sorted(layers, key=lambda x: x[2], reverse=True)
        
        included = []
        current_tokens = 0
        
        for name, content, priority in sorted_layers:
            tokens = self._count_tokens(content)
            # The system prompt is always included regardless of the budget
            if name == "system" or current_tokens + tokens <= max_tokens:
                included.append(content)
                current_tokens += tokens
            else:
                logger.info(f"Token budget limit reached. Dropping layer '{name}' (priority {priority}).")
                
        # Re-sort to maintain natural logical presentation order: system, ticket, standards, arch, diff, examples
        # which corresponds exactly to descending order of priorities!
        return included

    def _count_tokens(self, text: str) -> int:
        """
        Count the number of tokens in the given text using tiktoken.

        Args:
            text: Raw input text.

        Returns:
            The integer token count.
        """
        try:
            encoding = tiktoken.get_encoding("cl100k_base")
        except Exception:
            encoding = tiktoken.encoding_for_model("gpt-4")
        return len(encoding.encode(text))

    def _format_diff_section(self, pr_event: PREvent, max_tokens: int) -> str:
        """
        Format the changed files and their patches as a structured diff section.

        Args:
            pr_event: The Pull Request event.
            max_tokens: Maximum tokens allowed for the diff section.

        Returns:
            A formatted text representation of the PR diff.
        """
        sorted_files = sorted(
            pr_event.changed_files,
            key=lambda x: x.additions + x.deletions,
            reverse=True
        )
        
        diff_lines = []
        current_tokens = 0
        
        for f in sorted_files:
            if not f.patch:
                continue
            file_header = f"File: {f.path} (+{f.additions} -{f.deletions})\n"
            file_patch = f.patch
            file_section = f"{file_header}{file_patch}\n\n"
            
            section_tokens = self._count_tokens(file_section)
            if current_tokens + section_tokens <= max_tokens:
                diff_lines.append(file_section)
                current_tokens += section_tokens
            else:
                remaining_budget = max_tokens - current_tokens
                if remaining_budget > 30:
                    truncated_section = f"File: {f.path} (Truncated patch)\n"
                    patch_lines = file_patch.split("\n")
                    temp_patch = []
                    for line in patch_lines:
                        line_text = line + "\n"
                        if self._count_tokens("".join(temp_patch) + line_text) <= remaining_budget - 40:
                            temp_patch.append(line_text)
                        else:
                            temp_patch.append("... [Truncated due to token limit] ...\n")
                            break
                    truncated_section += "".join(temp_patch)
                    diff_lines.append(truncated_section)
                break
                
        return "".join(diff_lines)

    def _format_chunks_by_type(self, chunks: List[DocChunk], source_type: SourceType) -> str:
        """
        Helper method to filter and format scored chunks of a particular source type.

        The chunks have already been scored, compressed, and budget-trimmed by the
        ContextRanker, so we use their full content without arbitrary truncation.

        Args:
            chunks: List of DocChunk instances.
            source_type: The target SourceType to filter by.

        Returns:
            A string containing formatted content of matched chunks.
        """
        matched_chunks = [c for c in chunks if c.source_type == source_type]
        formatted = []
        for c in matched_chunks:
            formatted.append(c.content)
        return "\n---\n".join(formatted) if formatted else ""

