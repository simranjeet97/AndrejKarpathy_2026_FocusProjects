from typing import Dict
from ..models import ContextPack

SYSTEM_PROMPT = """You are CodeLens AI, an expert software developer and code reviewer.
Your task is to review a Pull Request against the provided codebase diff, Jira ticket, architectural documents, and coding standards.
Provide constructive, clear, and actionable feedback.

You MUST respond with a single, valid JSON object conforming exactly to this schema:
{
  "summary": "High-level summary of the review findings and overall assessment.",
  "issues": [
    {
      "file_path": "path/to/file.py",
      "line_number": 42,
      "severity": "CRITICAL" | "HIGH" | "MEDIUM" | "LOW",
      "category": "SECURITY" | "PERF" | "STYLE" | "LOGIC" | "TEST",
      "message": "Description of the problem found.",
      "suggestion": "Specific, actionable suggestion to fix the issue."
    }
  ],
  "suggestions": [
    "General non-line-specific suggestions or best practices."
  ],
  "approval": "APPROVE" | "REQUEST_CHANGES" | "COMMENT",
  "confidence": 0.95
}

Rules:
1. Output ONLY the raw JSON object. Do not add introductory or concluding text, just the raw JSON.
2. If the code is good and has no issues, set "approval" to "APPROVE" and leave "issues" as an empty list.
3. If there are critical security vulnerabilities or severe logic bugs, set "approval" to "REQUEST_CHANGES".
4. If there are only minor style or documentation issues, set "approval" to "COMMENT".
5. Use the exact enum values for severity, category, and approval.
"""

TICKET_CONTEXT_LAYER = """Jira Ticket: {ticket_id}
Goal: {summary}
Details: {description}
"""

ARCH_CONTEXT_LAYER = """Architecture Context:
{arch_chunks_text}
"""

STANDARDS_LAYER = """Coding Standards to enforce:
{standards_text}
"""

DIFF_LAYER = """Changed Files ({file_count} files):
{diff_text}
"""

EXAMPLES_LAYER = """Similar past PR reviews for reference:
{examples_text}
"""

SELF_CRITIQUE_PROMPT = """The JSON output you previously generated had parsing issues.
Please review your previous response, correct any trailing commas, unescaped quotes, or bad formatting, and output a valid JSON object matching the requested schema.

Previous Output:
{previous_output}

Corrected JSON:
"""

def format_context_pack(context_pack: ContextPack) -> Dict[str, str]:
    """
    Renders context chunks from a ContextPack into categorized text layers.

    Args:
        context_pack: ContextPack containing retrieved documentation chunks.

    Returns:
        A dictionary with keys 'arch_chunks_text', 'standards_text', and 'examples_text'.
    """
    from ..models import SourceType

    arch_texts = []
    standards_texts = []
    examples_texts = []

    for chunk in context_pack.chunks:
        if chunk.source_type == SourceType.ARCH_DOC:
            arch_texts.append(f"- [{chunk.chunk_id}] (Source: {chunk.metadata.get('file_path', 'unknown')}):\n{chunk.content}")
        elif chunk.source_type == SourceType.STANDARD:
            standards_texts.append(f"- [{chunk.chunk_id}] (Source: {chunk.metadata.get('file_path', 'unknown')}):\n{chunk.content}")
        elif chunk.source_type == SourceType.PR_EXAMPLE:
            examples_texts.append(f"- [{chunk.chunk_id}] (Source: {chunk.metadata.get('file_path', 'unknown')}):\n{chunk.content}")

    return {
        "arch_chunks_text": "\n\n".join(arch_texts) if arch_texts else "No architectural context found.",
        "standards_text": "\n\n".join(standards_texts) if standards_texts else "No specific coding standards found.",
        "examples_text": "\n\n".join(examples_texts) if examples_texts else "No similar PR examples found."
    }
