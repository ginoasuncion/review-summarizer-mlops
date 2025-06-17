from fastapi import FastAPI
from pydantic import BaseModel


class SummaryRequest(BaseModel):
    """Request model containing product name"""

    product_name: str


class SummaryResponse(BaseModel):
    """Response model containing generated summary"""

    summary: str


app = FastAPI()


@app.post("/summarize", response_model=SummaryResponse)
def summarize(request: SummaryRequest) -> SummaryResponse:
    """
    Summarize reviews for a given product.

    Args:
        request (SummaryRequest): Request containing product name

    Returns:
        SummaryResponse: Summary text
    """
    summary = f"The {request.product_name} has excellent reviews overall."
    return SummaryResponse(summary=summary)
