from fastapi.testclient import TestClient

from review_summarizer_mlops.main import app

client = TestClient(app)


def test_summarize_endpoint():
    response = client.post("/summarize/", json={"product_name": "Sample Product"})
    assert response.status_code == 200
    assert "summary" in response.json()
