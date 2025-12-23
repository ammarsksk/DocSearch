from typing import List
import asyncio

from sentence_transformers import SentenceTransformer

from ..core.config import get_settings

settings = get_settings()

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(settings.embedding_model_name)
    return _model


async def embed_texts(texts: List[str]) -> List[list[float]]:
    """
    Embed a batch of texts using a local SentenceTransformer model.
    """
    if not texts:
        return []

    model = _get_model()
    # Run blocking encode in a thread to avoid blocking the event loop.
    embeddings = await asyncio.to_thread(
        model.encode,
        texts,
        convert_to_numpy=True,
        show_progress_bar=False,
        batch_size=settings.embedding_batch_size,
    )
    # embeddings is a 2D numpy array (len(texts), dim)
    return embeddings.tolist()


async def embed_query(text: str) -> list[float]:
    (vector,) = await embed_texts([text])
    return vector
