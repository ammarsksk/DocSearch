from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select

from ..core.config import get_settings
from ..db import models
from ..db.session import async_session
from .embeddings import embed_query
from .generator import generate_answer_with_citations
from .opensearch_index import search_keyword
from .query_expander import hyde_expand
from .reranker import rerank
from .vector_search import vector_search_child_chunks

settings = get_settings()
logger = logging.getLogger(__name__)


@dataclass
class RetrievedContextChunk:
    chunk_id: UUID
    document_id: UUID
    filename: str
    page_start: int | None
    page_end: int | None
    text: str


def _slice_window(
    text: str,
    *,
    rel_start: int,
    rel_end: int,
    window_chars: int,
) -> str:
    """
    Extract a window of text around a relevant span so the LLM sees the part
    that triggered retrieval (avoids truncation hiding the answer).
    """
    if not text:
        return ""

    rel_start = max(rel_start, 0)
    rel_end = max(rel_end, rel_start)
    span_center = (rel_start + rel_end) // 2

    half = max(window_chars // 2, 1)
    start = max(span_center - half, 0)
    end = min(start + window_chars, len(text))
    start = max(end - window_chars, 0)
    snippet = text[start:end]
    return snippet.strip()


def _rrf_merge(
    *,
    keyword_ids: List[str],
    vector_ids: List[str],
    k: int = 60,
) -> List[str]:
    scores: Dict[str, float] = {}

    for rank, cid in enumerate(keyword_ids):
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)

    for rank, cid in enumerate(vector_ids):
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)

    return sorted(scores.keys(), key=lambda x: scores[x], reverse=True)


async def answer_question(
    *,
    question: str,
    top_k: int,
    document_ids: Optional[list[UUID]] = None,
) -> Tuple[str, List]:
    """
    Full Phase-2 query pipeline:
    - optional HyDE expansion
    - BM25 retrieval (OpenSearch) + vector retrieval (pgvector)
    - RRF merge
    - cross-encoder rerank
    - expand to parent chunks
    - generate answer with citations
    """
    expanded_query = await hyde_expand(question)
    query_vec = await embed_query(expanded_query)

    doc_ids_str = [str(d) for d in (document_ids or [])]

    keyword_hits = search_keyword(
        query_text=expanded_query,
        size=settings.retrieve_k_keyword,
        document_ids=doc_ids_str or None,
    )
    keyword_ids = [h.get("_source", {}).get("chunk_id") for h in keyword_hits]
    keyword_ids = [cid for cid in keyword_ids if cid]

    vector_ids = await vector_search_child_chunks(
        query_embedding=query_vec,
        limit=settings.retrieve_k_vector,
        document_ids=document_ids or None,
    )

    merged_ids = _rrf_merge(keyword_ids=keyword_ids, vector_ids=vector_ids)
    merged_ids = merged_ids[: max(settings.retrieve_k_merge, top_k)]

    if not merged_ids:
        return "No relevant chunks found.", []

    if settings.debug_prompts:
        logger.info(
            "Retrieval debug: question=%r hyde=%s keyword_hits=%d vector_hits=%d merged=%d",
            question,
            "on" if settings.hyde_enabled else "off",
            len(keyword_ids),
            len(vector_ids),
            len(merged_ids),
        )

    merged_uuid_ids: List[UUID] = []
    merged_id_order: List[str] = []
    for cid in merged_ids:
        try:
            merged_uuid_ids.append(UUID(str(cid)))
            merged_id_order.append(str(cid))
        except Exception:
            continue

    async with async_session() as session:
        stmt = (
            select(models.ChildChunk, models.Document)
            .join(models.Document, models.ChildChunk.document_id == models.Document.id)
            .where(models.ChildChunk.id.in_(merged_uuid_ids))
        )
        rows = (await session.execute(stmt)).all()

        child_by_id: Dict[str, Tuple[models.ChildChunk, models.Document]] = {
            str(child.id): (child, doc) for child, doc in rows
        }
        ordered_children: List[Tuple[str, models.ChildChunk, models.Document]] = []
        for cid in merged_id_order:
            item = child_by_id.get(str(cid))
            if item:
                ordered_children.append((str(cid), item[0], item[1]))

    # Rerank the merged candidates
    rerank_candidates = [(cid, child.text) for cid, child, _ in ordered_children]
    reranked = await rerank(query=question, candidates=rerank_candidates)
    reranked_ids = [cid for cid, _ in reranked[: settings.rerank_top_n]]

    if not reranked_ids:
        return "No relevant chunks found.", []

    if settings.debug_prompts:
        top_debug = reranked[: min(len(reranked), settings.rerank_top_n)]
        logger.info("Rerank top_%d (child_chunk_id, score): %s", len(top_debug), top_debug)

    # Expand to parent chunks but keep the "relevant window" around the top child chunk
    # for that parent (small-to-big retrieval).
    parent_pick: List[tuple[str, models.ChildChunk]] = []
    parent_seen: set[str] = set()
    for cid in reranked_ids:
        child, _doc = child_by_id[cid]
        pid = str(child.parent_id)
        if pid in parent_seen:
            continue
        parent_seen.add(pid)
        parent_pick.append((pid, child))
        if len(parent_pick) >= max(settings.max_parent_chunks_for_llm, top_k):
            break

    parent_ids = [pid for pid, _ in parent_pick]

    parent_uuid_ids: List[UUID] = []
    for pid in parent_ids:
        try:
            parent_uuid_ids.append(UUID(pid))
        except Exception:
            continue

    async with async_session() as session:
        stmt = (
            select(models.ParentChunk, models.Document)
            .join(models.Document, models.ParentChunk.document_id == models.Document.id)
            .where(models.ParentChunk.id.in_(parent_uuid_ids))
        )
        rows = (await session.execute(stmt)).all()
        parent_by_id: Dict[str, Tuple[models.ParentChunk, models.Document]] = {
            str(p.id): (p, d) for p, d in rows
        }

    context_chunks: List[RetrievedContextChunk] = []
    child_by_parent: Dict[str, models.ChildChunk] = {pid: child for pid, child in parent_pick}

    for pid in parent_ids:
        if pid not in parent_by_id:
            continue
        parent, doc = parent_by_id[pid]
        child = child_by_parent.get(pid)
        if child:
            rel_start = (child.char_start or 0) - (parent.char_start or 0)
            rel_end = (child.char_end or 0) - (parent.char_start or 0)
            snippet = _slice_window(
                parent.text,
                rel_start=rel_start,
                rel_end=rel_end,
                window_chars=settings.max_parent_chunk_chars_for_llm,
            )
        else:
            snippet = (parent.text or "")[: settings.max_parent_chunk_chars_for_llm]

        context_chunks.append(
            RetrievedContextChunk(
                chunk_id=parent.id,
                document_id=doc.id,
                filename=doc.filename,
                page_start=parent.page_start,
                page_end=parent.page_end,
                text=snippet,
            )
        )

    if settings.debug_prompts:
        for i, cc in enumerate(context_chunks, start=1):
            logger.info(
                "Context[P%d] chunk_id=%s doc_id=%s pages=%s-%s chars=%d text_preview=%r",
                i,
                cc.chunk_id,
                cc.document_id,
                cc.page_start,
                cc.page_end,
                len(cc.text or ""),
                (cc.text or "")[:500],
            )

    if not context_chunks:
        return "No relevant chunks found.", []

    answer, citations = await generate_answer_with_citations(
        question=question, chunks=context_chunks
    )
    return answer, citations
