import os
import glob
import re
from datetime import datetime

# Define knowledge directory path (absolute to project root/data/knowledge)
KNOWLEDGE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../../data/knowledge")
)

# Ensure the directory exists
if not os.path.exists(KNOWLEDGE_DIR):
    os.makedirs(KNOWLEDGE_DIR)

async def search_markdown_kb(query: str, max_results: int = 5) -> list[dict]:
    """Search internal Markdown knowledge base for relevant documentation."""
    if not os.path.exists(KNOWLEDGE_DIR):
        os.makedirs(KNOWLEDGE_DIR)

    md_files = glob.glob(os.path.join(KNOWLEDGE_DIR, "**/*.md"), recursive=True)
    results = []

    # Clean query into keywords
    query_words = [w.lower() for w in re.findall(r"\w+", query)]
    if not query_words:
        return []

    for filepath in md_files:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            content_lower = content.lower()
            score = sum(content_lower.count(word) for word in query_words)

            if score > 0:
                stat = os.stat(filepath)
                last_modified = datetime.fromtimestamp(stat.st_mtime).isoformat()

                # Find first keyword match context
                snippet = "No matching snippet found."
                for word in query_words:
                    pos = content_lower.find(word)
                    if pos != -1:
                        start = max(0, pos - 100)
                        end = min(len(content), pos + 200)
                        snippet = content[start:end].replace("\n", " ").strip()
                        if start > 0:
                            snippet = "..." + snippet
                        if end < len(content):
                            snippet = snippet + "..."
                        break

                title = os.path.basename(filepath)
                # Attempt to extract first Markdown header
                header_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
                if header_match:
                    title = header_match.group(1).strip()

                results.append({
                    "score": score,
                    "title": title,
                    "filepath": filepath,
                    "last_edited": last_modified,
                    "snippet": snippet
                })
        except Exception:
            continue

    # Sort by matching score descending
    results = sorted(results, key=lambda x: x["score"], reverse=True)

    # Clean score from final output
    for r in results:
        r.pop("score", None)

    return results[:max_results]

async def get_markdown_file_content(filepath: str) -> str:
    """Retrieve full text content of a specific markdown file."""
    # SECURITY: Prevent path traversal out of the KNOWLEDGE_DIR
    real_path = os.path.realpath(filepath)
    real_kb_dir = os.path.realpath(KNOWLEDGE_DIR)

    if os.path.commonpath([real_kb_dir, real_path]) != real_kb_dir:
        raise ValueError("Access denied: File lies outside the allowed knowledge base directory.")

    if not os.path.exists(real_path):
        raise FileNotFoundError(f"Markdown file not found at: {filepath}")

    with open(real_path, "r", encoding="utf-8") as f:
        content = f.read()

    return content[:3000]

async def list_markdown_kb_files() -> list[dict]:
    """List all files in the markdown knowledge base with metadata."""
    if not os.path.exists(KNOWLEDGE_DIR):
        os.makedirs(KNOWLEDGE_DIR)

    md_files = glob.glob(os.path.join(KNOWLEDGE_DIR, "**/*.md"), recursive=True)
    results = []

    for filepath in md_files:
        try:
            stat = os.stat(filepath)
            last_modified = datetime.fromtimestamp(stat.st_mtime).isoformat()
            title = os.path.basename(filepath)

            with open(filepath, "r", encoding="utf-8") as f:
                preview = f.read(150).replace("\n", " ").strip()
                if len(preview) == 150:
                    preview += "..."

            results.append({
                "title": title,
                "filepath": filepath,
                "last_edited": last_modified,
                "preview": preview
            })
        except Exception:
            continue

    return results
