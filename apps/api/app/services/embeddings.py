from typing import List


async def embed_texts(texts: List[str]) -> List[list[float]]:
    """
    Phase 1 placeholder embeddings implementation.

    Replace with a real embedding provider (OpenAI, local model, etc.).
    """
    # For now, return a fixed-size zero vector to unblock the pipeline;
    # retrieval quality will not be meaningful until this is implemented.
    dim = 768
    return [[0.0] * dim for _ in texts]


async def embed_query(text: str) -> list[float]:
    (vector,) = await embed_texts([text])
    return vector

