from typing import List, Tuple
import io

from PyPDF2 import PdfReader


def _sanitize_text(text: str) -> str:
    # Remove NULs and other problematic control characters for Postgres.
    return text.replace("\x00", "")


async def parse_document(content: bytes, content_type: str) -> List[Tuple[int, str]]:
    """
    Parse a document into (page_number, text) tuples.

    - For PDFs: use PyPDF2 to extract page text.
    - For everything else: UTF-8 decode with best-effort fallback.
    """
    content_type_lower = (content_type or "").lower()

    # Basic PDF detection by content type or header.
    if "pdf" in content_type_lower or content.startswith(b"%PDF"):
        reader = PdfReader(io.BytesIO(content))
        pages: List[Tuple[int, str]] = []
        for i, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text() or ""
            pages.append((i, _sanitize_text(page_text)))
        return pages

    # Fallback: treat as UTF-8 text.
    text = content.decode("utf-8", errors="ignore")
    return [(1, _sanitize_text(text))]

