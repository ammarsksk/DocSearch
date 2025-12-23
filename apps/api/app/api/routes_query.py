from fastapi import APIRouter, HTTPException

from ..schemas.query import QueryRequest, QueryResponse
from ..services.query_pipeline import answer_question

router = APIRouter()


@router.post("", response_model=QueryResponse)
async def query(request: QueryRequest) -> QueryResponse:
    """
    Run a hybrid retrieval over chunks and generate an answer with citations.
    """
    answer, citations = await answer_question(
        question=request.question,
        top_k=request.top_k,
        document_ids=request.document_ids or None,
    )

    if not citations and answer.lower().startswith("no relevant"):
        raise HTTPException(status_code=404, detail="No relevant chunks found")

    return QueryResponse(answer=answer, citations=citations)
