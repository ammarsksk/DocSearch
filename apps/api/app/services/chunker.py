from dataclasses import dataclass
from hashlib import sha256
from typing import List, Sequence, Tuple


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
    Simple character-based chunker with overlap.
    """
    chunks: List[ChunkData] = []
    current_page_start = pages[0][0] if pages else 1
    buffer = ""
    buffer_start_offset = 0

    for page_number, text in pages:
        for ch in text:
            if not buffer:
                buffer_start_offset = 0
                current_page_start = page_number

            buffer += ch

            if len(buffer) >= max_chars:
                char_end = buffer_start_offset + len(buffer)
                chunk_hash = _hash_text(buffer)
                chunks.append(
                    ChunkData(
                        text=buffer,
                        page_start=current_page_start,
                        page_end=page_number,
                        char_start=buffer_start_offset,
                        char_end=char_end,
                        chunk_hash=chunk_hash,
                    )
                )
                # Keep overlap at end of buffer
                buffer = buffer[-overlap_chars:]
                buffer_start_offset = char_end - len(buffer)

        # end of page, continue with buffer

    if buffer:
        char_end = buffer_start_offset + len(buffer)
        chunk_hash = _hash_text(buffer)
        chunks.append(
            ChunkData(
                text=buffer,
                page_start=current_page_start,
                page_end=pages[-1][0] if pages else current_page_start,
                char_start=buffer_start_offset,
                char_end=char_end,
                chunk_hash=chunk_hash,
            )
        )

    return chunks

