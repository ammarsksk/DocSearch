from typing import List, Tuple

from ..schemas.query import Citation
from .retriever import RetrievedChunk


async def generate_answer_with_citations(
    question: str,
    chunks: List[RetrievedChunk],
) -> Tuple[str, List[Citation]]:
    """
    Phase 1 placeholder generator.

    In a real implementation, call an LLM with a strict prompt:
    - use only provided chunks
    - attach citation markers per chunk
    - abstain if answer not supported by context
    """
    if not chunks:
        return "I could not find relevant information.", []

    # Naive baseline: concatenate top chunks as the "answer".
    answer_parts: List[str] = []
    citations: List[Citation] = []

    for idx, chunk in enumerate(chunks):
        marker = f"[C{idx + 1}]"
        excerpt = chunk.text[:300]
        answer_parts.append(f"{marker} {excerpt}")
        citations.append(
            Citation(
                document_id=chunk.document_id,
                filename=chunk.filename,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                excerpt=excerpt,
                chunk_id=chunk.chunk_id,
            )
        )

    answer = "\n\n".join(answer_parts)
    return answer, citations

