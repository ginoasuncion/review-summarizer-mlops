from fastapi import FastAPI

from review_summarizer_mlops.api.endpoints import router

app = FastAPI(title="Review Summarizer API")

app.include_router(router)
