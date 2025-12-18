from typing import Any, List, Tuple


async def parse_document(content: bytes, content_type: str) -> List[Tuple[int, str]]:
    """
    Phase 1 placeholder parser.

    Returns a list of (page_number, text) tuples.
    In a real implementation, integrate Unstructured or PDF parsing + OCR here.
    """
    text = content.decode(errors="ignore")
    # Treat the whole document as a single "page" for now.
    return [(1, text)]

