import os
import asyncio
import fitz
from src.llm.ollama_client import OllamaClient
from src.models import PDFSummary

class PDFTool:
    """Tool for reading, chunking, and summarizing PDF files using Ollama LLM."""

    def __init__(self, ollama_client: OllamaClient, max_pages: int, pdf_dir: str = "data/pdfs"):
        """Initialize PDFTool with Ollama client, page limits, and allowed directory."""
        self.ollama_client = ollama_client
        self.max_pages = max_pages
        self.pdf_dir = os.path.abspath(pdf_dir)

    def _validate_path(self, filepath: str) -> str:
        """Verify the filepath resides within the allowed PDF directory."""
        real_path = os.path.realpath(filepath)
        real_pdf_dir = os.path.realpath(self.pdf_dir)
        if os.path.commonpath([real_pdf_dir, real_path]) != real_pdf_dir:
            raise ValueError("Access denied: File lies outside the allowed PDF directory.")
        return real_path

    async def summarize_pdf(self, filepath: str) -> PDFSummary:
        """Summarize a PDF file. Respects MAX_PDF_PAGES limit."""
        try:
            pages = self._extract_text(filepath)
        except (FileNotFoundError, ValueError) as e:
            return PDFSummary(
                filename=os.path.basename(filepath),
                page_count=0,
                summary=f"Error: {e}",
                key_points=[f"Error: {str(e)}"],
                tokens_used=0
            )

        if not pages:
            return PDFSummary(
                filename=os.path.basename(filepath),
                page_count=0,
                summary="The document is empty.",
                key_points=["No content to summarize."],
                tokens_used=0
            )

        # Chunk pages
        chunks = self._chunk_pages(pages, chunk_size=3)

        # Summarize chunks concurrently
        chunk_summaries = await asyncio.gather(*(self._summarize_chunk(chunk) for chunk in chunks))

        # Combine summaries
        all_summaries = "\n\n".join(chunk_summaries)
        combine_prompt = (
            "Combine these summaries into one coherent summary with key points (as bullet points):\n"
            f"{all_summaries}"
        )
        
        final_summary = await self.ollama_client.generate(combine_prompt)
        final_summary_text = str(final_summary).strip()

        # Parse key points from final summary
        key_points = []
        for line in final_summary_text.split("\n"):
            cleaned = line.strip()
            if cleaned.startswith(("- ", "* ", "• ")):
                key_points.append(cleaned[2:].strip())
            elif cleaned.startswith(tuple(f"{i}." for i in range(1, 20))):
                parts = cleaned.split(".", 1)
                key_points.append(parts[1].strip())

        if not key_points:
            key_points = [s.strip() for s in final_summary_text.split(".") if s.strip()][:5]

        # Estimate tokens used
        words_count = sum(len(p.split()) for p in pages)
        tokens_used = int(words_count * 1.33)

        return PDFSummary(
            filename=os.path.basename(filepath),
            page_count=len(pages),
            summary=final_summary_text,
            key_points=key_points,
            tokens_used=tokens_used
        )

    async def extract_key_metrics(self, filepath: str, metrics: list[str]) -> dict[str, str]:
        """Extract specific metrics or data points from a PDF by name."""
        try:
            pages = self._extract_text(filepath)
        except (FileNotFoundError, ValueError) as e:
            return {m: f"Error: {e}" for m in metrics}

        full_text = "\n\n".join(pages)[:8000]
        prompt = (
            f"From this document, extract these values: {', '.join(metrics)}.\n"
            "Return your answer ONLY as a JSON dictionary where the keys are the metric names and values are the extracted values as strings.\n"
            f"Document content:\n{full_text}"
        )
        
        res = await self.ollama_client.generate(prompt, expect_json=True)
        if isinstance(res, dict):
            return {k: str(v) for k, v in res.items()}
        return {}

    async def answer_question_from_pdf(self, filepath: str, question: str) -> str:
        """Answer a specific question using PDF content as context."""
        try:
            pages = self._extract_text(filepath)
        except (FileNotFoundError, ValueError) as e:
            return f"Error: {e}"

        full_text = "\n\n".join(pages)[:4000]
        prompt = f"Using only this document as context, answer: {question}\n\nDocument:\n{full_text}"
        res = await self.ollama_client.generate(prompt)
        return str(res).strip()

    def _extract_text(self, filepath: str) -> list[str]:
        """Extract plain text from each page of the PDF up to max_pages."""
        validated_path = self._validate_path(filepath)
        if not os.path.exists(validated_path):
            raise FileNotFoundError(f"PDF file not found at {filepath}")

        pages_text = []
        doc = fitz.open(validated_path)
        try:
            num_pages = min(len(doc), self.max_pages)
            for i in range(num_pages):
                page = doc.load_page(i)
                pages_text.append(page.get_text())
        finally:
            doc.close()
        return pages_text

    def _chunk_pages(self, pages: list[str], chunk_size: int = 3) -> list[str]:
        """Group list of pages into text chunks for LLM context compatibility."""
        chunks = []
        for i in range(0, len(pages), chunk_size):
            chunk_text = "\n\n".join(pages[i : i + chunk_size])
            chunks.append(chunk_text)
        return chunks

    async def _summarize_chunk(self, chunk: str) -> str:
        """Use Ollama client to generate a summary for a specific text chunk."""
        prompt = f"Summarize this document section concisely in 3-5 sentences:\n{chunk}"
        res = await self.ollama_client.generate(prompt)
        return str(res).strip()
