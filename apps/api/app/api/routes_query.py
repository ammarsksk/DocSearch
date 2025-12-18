from fastapi import APIRouter, HTTPException

from ..schemas.query import QueryRequest, QueryResponse
from ..services.retriever import retrieve_relevant_chunks
from ..services.generator import generate_answer_with_citations

router = APIRouter()


@router.post("", response_model=QueryResponse)
async def query(request: QueryRequest) -> QueryResponse:
    """
    Run a hybrid retrieval over chunks and generate an answer with citations.
    """
    chunks = await retrieve_relevant_chunks(
        question=request.question,
        limit=request.top_k,
        document_ids=request.document_ids or [],
    )

    if not chunks:
        raise HTTPException(status_code=404, detail="No relevant chunks found")

    answer, citations = await generate_answer_with_citations(
        question=request.question,
        chunks=chunks,
    )

    return QueryResponse(answer=answer, citations=citations)

