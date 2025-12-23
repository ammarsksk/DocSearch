import asyncio
from typing import List, Tuple

from sentence_transformers import CrossEncoder

from ..core.config import get_settings

settings = get_settings()

_model: CrossEncoder | None = None


def _get_model() -> CrossEncoder:
    global _model
    if _model is None:
        _model = CrossEncoder(settings.reranker_model_name)
    return _model


async def rerank(
    *,
    query: str,
    candidates: List[Tuple[str, str]],
) -> List[Tuple[str, float]]:
    """
    Rerank candidate texts with a cross-encoder.

    candidates: list of (candidate_id, candidate_text)
    returns: list of (candidate_id, score) sorted desc
    """
    if not candidates:
        return []

    model = _get_model()
    pairs = [(query, text) for _, text in candidates]

    scores = await asyncio.to_thread(model.predict, pairs)
    scored = [(candidate_id, float(score)) for (candidate_id, _), score in zip(candidates, scores)]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored

