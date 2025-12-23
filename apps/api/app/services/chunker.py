from dataclasses import dataclass
from hashlib import sha256
from typing import List, Sequence, Tuple


def _find_page_range(
    page_offsets: List[tuple[int, int, int]],
    char_start: int,
    char_end: int,
) -> tuple[int, int]:
    # page_offsets: (page_no, start, end) in the concatenated text space
    page_start = page_offsets[0][0] if page_offsets else 1
    page_end = page_offsets[-1][0] if page_offsets else 1

    for page_no, start, end in page_offsets:
        if end > char_start:
            page_start = page_no
            break

    for page_no, start, end in reversed(page_offsets):
        if start < char_end:
            page_end = page_no
            break

    return page_start, page_end


@dataclass
class ChunkData:
    text: str
    page_start: int
    page_end: int
    char_start: int
    char_end: int
    chunk_hash: str


def _hash_text(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def simple_chunk(
    pages: Sequence[Tuple[int, str]],
    max_chars: int = 2000,
    overlap_chars: int = 200,
) -> List[ChunkData]:
    """
    Chunk a document into overlapping character windows.

    This implementation avoids per-character loops for speed on large documents.
    """
    chunks: List[ChunkData] = []
    if not pages:
        return chunks

    full_text_parts: List[str] = []
    page_offsets: List[tuple[int, int, int]] = []
    cursor = 0

    for page_no, text in pages:
        if not isinstance(text, str):
            text = str(text)
        if full_text_parts:
            full_text_parts.append("\n")
            cursor += 1
        start = cursor
        full_text_parts.append(text)
        cursor += len(text)
        end = cursor
        page_offsets.append((page_no, start, end))

    full_text = "".join(full_text_parts)
    if not full_text:
        return chunks

    start = 0
    step = max(max_chars - overlap_chars, 1)
    while start < len(full_text):
        end = min(start + max_chars, len(full_text))
        text = full_text[start:end]
        if text.strip():
            page_start, page_end = _find_page_range(page_offsets, start, end)
            chunks.append(
                ChunkData(
                    text=text,
                    page_start=page_start,
                    page_end=page_end,
                    char_start=start,
                    char_end=end,
                    chunk_hash=_hash_text(text),
                )
            )
        start += step

    return chunks


def chunk_text_block(
    text: str,
    *,
    page_start: int,
    page_end: int,
    base_char_start: int,
    max_chars: int,
    overlap_chars: int,
) -> List[ChunkData]:
    """
    Chunk a single text block (e.g. a parent chunk) into child chunks.

    Char offsets are returned in the document-global coordinate space using base_char_start.
    """
    chunks: List[ChunkData] = []
    if not text:
        return chunks

    start = 0
    step = max(max_chars - overlap_chars, 1)
    while start < len(text):
        end = min(start + max_chars, len(text))
        part = text[start:end]
        if part.strip():
            chunks.append(
                ChunkData(
                    text=part,
                    page_start=page_start,
                    page_end=page_end,
                    char_start=base_char_start + start,
                    char_end=base_char_start + end,
                    chunk_hash=_hash_text(part),
                )
            )
        start += step

    return chunks
