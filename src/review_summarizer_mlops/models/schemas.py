from pydantic import BaseModel


class SummarizeRequest(BaseModel):
    product_name: str


class SummarizeResponse(BaseModel):
    summary: str
