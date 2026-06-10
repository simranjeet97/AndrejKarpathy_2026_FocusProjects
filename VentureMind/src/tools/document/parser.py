import os
import re
import tempfile
from typing import Any
import fitz  # PyMuPDF
import httpx
import pdfplumber
from bs4 import BeautifulSoup
from ..search.web_search import validate_url

class DocumentParser:
    """Utility class to parse and extract text and tables from PDFs, HTML, and web documents."""

    def __init__(self, max_pages: int):
        self.max_pages = max_pages

    def parse_pdf(self, filepath: str) -> dict[str, Any]:
        """Extract page text, page count, and metadata from a PDF file using PyMuPDF."""
        doc = fitz.open(filepath)
        page_count = len(doc)
        metadata = dict(doc.metadata)

        pages = []
        for page_num in range(min(page_count, self.max_pages)):
            page = doc.load_page(page_num)
            pages.append(page.get_text())

        doc.close()
        return {
            "pages": pages,
            "metadata": metadata,
            "page_count": page_count
        }

    async def parse_pdf_from_url(self, url: str) -> dict[str, Any]:
        """Download a PDF from a URL and parse it, ensuring clean-up of temporary files."""
        validate_url(url)
        headers = {"User-Agent": "Mozilla/5.0"}
        
        # Create a temporary file to write binary contents
        temp_file_fd, temp_file_path = tempfile.mkstemp(suffix=".pdf")
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=headers, follow_redirects=True)
                response.raise_for_status()
                with os.fdopen(temp_file_fd, "wb") as f:
                    f.write(response.content)

            return self.parse_pdf(temp_file_path)
        finally:
            try:
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
            except Exception:
                pass

    def extract_tables_from_pdf(self, filepath: str) -> list[list[list[Any]]]:
        """Extract all tabular data from the PDF file using pdfplumber."""
        tables = []
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages[:self.max_pages]:
                page_tables = page.extract_tables()
                for table in page_tables:
                    tables.append(table)
        return tables

    def parse_html_to_text(self, html: str) -> str:
        """Parse raw HTML and clean out tags, scripts, navigation elements, and footers."""
        soup = BeautifulSoup(html, "html.parser")
        
        # Decompose non-content tags
        for element in soup(["script", "style", "meta", "noscript", "header", "footer", "nav", "aside", "form"]):
            element.decompose()

        # Extract text content from structural blocks
        paragraphs = [p.get_text(strip=True) for p in soup.find_all("p")]
        text = "\n\n".join([p for p in paragraphs if p])
        if not text:
            text = soup.get_text(separator="\n", strip=True)

        # Clean multiple redundant newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def chunk_text(self, text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
        """Chunk plain text using a sliding window on sentence boundaries."""
        if not text.strip():
            return []

        # Split text on sentences using lookbehind regex
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        chunks = []
        current_chunk = []
        current_length = 0

        for sentence in sentences:
            sentence_len = len(sentence)
            if sentence_len > chunk_size:
                # If a single sentence exceeds the chunk limit, split it by characters
                if current_chunk:
                    chunks.append(" ".join(current_chunk))
                    current_chunk = []
                    current_length = 0
                
                start = 0
                while start < sentence_len:
                    end = min(start + chunk_size, sentence_len)
                    chunks.append(sentence[start:end])
                    start += chunk_size - overlap
                continue

            # Check if sentence fits in the current chunk
            if current_length + sentence_len + (1 if current_chunk else 0) <= chunk_size:
                current_chunk.append(sentence)
                current_length += sentence_len + (1 if current_chunk else 0)
            else:
                chunks.append(" ".join(current_chunk))
                # Add sentences to maintain overlap
                overlap_chunk = []
                overlap_len = 0
                for sent in reversed(current_chunk):
                    if overlap_len + len(sent) + (1 if overlap_chunk else 0) <= overlap:
                        overlap_chunk.insert(0, sent)
                        overlap_len += len(sent) + (1 if overlap_chunk else 0)
                    else:
                        break
                current_chunk = overlap_chunk + [sentence]
                current_length = sum(len(s) for s in current_chunk) + len(current_chunk) - 1

        if current_chunk:
            chunks.append(" ".join(current_chunk))

        # Guarantee non-empty input returns at least one chunk
        if not chunks and text.strip():
            chunks = [text.strip()[:chunk_size]]

        return chunks
