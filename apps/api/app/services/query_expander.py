import httpx

from ..core.config import get_settings

settings = get_settings()


async def hyde_expand(question: str) -> str:
    """
    HyDE-style query expansion using the local LLM.

    Returns an expanded query text; on failure returns the original question.
    """
    if not settings.hyde_enabled:
        return question

    prompt = (
        "Write a short hypothetical answer that would likely appear in a document. "
        "Do not mention that this is hypothetical. Keep it concise.\n\n"
        f"Question: {question}"
    )

    try:
        async with httpx.AsyncClient(
            base_url=settings.local_llm_base_url,
            timeout=httpx.Timeout(60.0),
        ) as client:
            resp = await client.post(
                "/api/chat",
                json={
                    "model": settings.local_llm_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {"num_predict": 160},
                },
            )
            resp.raise_for_status()
            data = resp.json()
            expanded = data.get("message", {}).get("content", "") or ""
            expanded = expanded.strip()
            if not expanded:
                return question
            return f"{question}\n\n{expanded}"
    except Exception:
        return question

