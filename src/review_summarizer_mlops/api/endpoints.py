from fastapi import APIRouter, HTTPException
from review_summarizer_mlops.models.schemas import SummarizeRequest, SummarizeResponse
from review_summarizer_mlops.core.data_parser import fetch_product_data
from review_summarizer_mlops.core.summarizer import summarize_feedback

router = APIRouter()


@router.post("/summarize/", response_model=SummarizeResponse)
async def summarize_feedback_route(request: SummarizeRequest):
    try:
        data = fetch_product_data(request.product_name)
        summary = summarize_feedback(data)
        return {"summary": summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
