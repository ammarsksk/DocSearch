from typing import List, Tuple
import re

import logging
import httpx

from ..core.config import get_settings
from ..schemas.query import Citation

settings = get_settings()
logger = logging.getLogger(__name__)


def _truncate(s: str, limit: int) -> str:
    if s is None:
        return ""
    if len(s) <= limit:
        return s
    return s[:limit] + f"\n\n…(truncated, total_chars={len(s)})"


def _build_context(chunks: List, max_chunks: int, max_chars: int) -> str:
    """Build a bounded context string to avoid huge prompts."""
    parts: List[str] = []
    for idx, chunk in enumerate(chunks[:max_chunks], start=1):
        marker = f"P{idx}"
        text = (getattr(chunk, "text", "") or "")[:max_chars]
        filename = getattr(chunk, "filename", "document")
        page_start = getattr(chunk, "page_start", None)
        page_end = getattr(chunk, "page_end", None)
        parts.append(
            f"[{marker}] (doc={filename}, pages={page_start}-{page_end})\n{text}"
        )
    return "\n\n".join(parts)


def _fallback_answer(chunks: List) -> Tuple[str, List[Citation]]:
    """Simple non-LLM answer: just stitch top chunks."""
    if not chunks:
        return "I could not find relevant information.", []

    answer_parts: List[str] = []
    citations: List[Citation] = []
    for idx, chunk in enumerate(chunks[: settings.max_parent_chunks_for_llm], start=1):
        marker = f"[P{idx}]"
        excerpt = (getattr(chunk, "text", "") or "")[:300]
        answer_parts.append(f"{marker} {excerpt}")
        citations.append(
            Citation(
                document_id=getattr(chunk, "document_id"),
                filename=getattr(chunk, "filename", "document"),
                page_start=getattr(chunk, "page_start", None),
                page_end=getattr(chunk, "page_end", None),
                excerpt=excerpt,
                chunk_id=getattr(chunk, "chunk_id"),
            )
        )
    return "\n\n".join(answer_parts), citations


async def generate_answer_with_citations(
    question: str,
    chunks: List,
) -> Tuple[str, List[Citation]]:
    """
    Use a local LLM (via Ollama-compatible API) to generate a grounded answer with citations.
    Falls back to a simple stitched answer if the LLM is unavailable or times out.
    """
    if not chunks:
        return "I could not find relevant information.", []

    context_text = _build_context(
        chunks,
        max_chunks=settings.max_parent_chunks_for_llm,
        max_chars=settings.max_parent_chunk_chars_for_llm,
    )

    system_prompt = (
        "You are a strict assistant answering questions about the provided document context.\n"
        "You are given context chunks, each tagged with an ID like [P1], [P2], etc.\n"
        "Rules:\n"
        "- The question ALWAYS refers to the provided context; do not ask which document to use.\n"
        "- Answer ONLY using the provided context.\n"
        '- If the answer is not clearly supported, reply exactly: "I do not know."\n'
        "- Every factual sentence must include at least one citation marker like [P1].\n"
        "- Do not invent IDs; only use the ones you see in the context.\n"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                f"Question: {question}\n\n"
                f"Context:\n{context_text}\n\n"
                "Now answer the question. Remember to use citation markers like [P1], [P2] in your answer."
            ),
        },
    ]

    try:
        if settings.debug_prompts:
            payload_preview = {
                "model": settings.local_llm_model,
                "messages": [
                    {"role": m["role"], "content": _truncate(m["content"], settings.debug_max_chars)}
                    for m in messages
                ],
                "stream": False,
            }
            logger.info("Ollama request (truncated): %s", payload_preview)

        async with httpx.AsyncClient(
            base_url=settings.local_llm_base_url,
            timeout=httpx.Timeout(300.0),
        ) as client:
            resp = await client.post(
                "/api/chat",
                json={
                    "model": settings.local_llm_model,
                    "messages": messages,
                    "stream": False,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            # Ollama-style response: {"message": {"role": "assistant", "content": "..."}}
            answer = data.get("message", {}).get("content", "") or ""
    except Exception:
        # On any error (timeout, connection issue, etc.), fall back to stitched chunks.
        return _fallback_answer(chunks)

    # Extract which chunk IDs were cited.
    used_indices: set[int] = set()
    for match in re.finditer(r"\[P(\d+)\]", answer):
        try:
            idx = int(match.group(1))
            if 1 <= idx <= len(chunks):
                used_indices.add(idx)
        except ValueError:
            continue

    citations: List[Citation] = []
    for idx in sorted(used_indices):
        chunk = chunks[idx - 1]
        excerpt = (getattr(chunk, "text", "") or "")[:300]
        citations.append(
            Citation(
                document_id=getattr(chunk, "document_id"),
                filename=getattr(chunk, "filename", "document"),
                page_start=getattr(chunk, "page_start", None),
                page_end=getattr(chunk, "page_end", None),
                excerpt=excerpt,
                chunk_id=getattr(chunk, "chunk_id"),
            )
        )

    # If the model did not include any citations, fall back to top-1 chunk.
    if not citations and chunks:
        chunk = chunks[0]
        citations.append(
            Citation(
                document_id=getattr(chunk, "document_id"),
                filename=getattr(chunk, "filename", "document"),
                page_start=getattr(chunk, "page_start", None),
                page_end=getattr(chunk, "page_end", None),
                excerpt=(getattr(chunk, "text", "") or "")[:300],
                chunk_id=getattr(chunk, "chunk_id"),
            )
        )

    return answer, citations
