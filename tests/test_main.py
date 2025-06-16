from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_summarize() -> None:
    """Test the /summarize endpoint returns 200 and valid summary"""
    response = client.post("/summarize", json={"product_name": "MacBook"})
    assert response.status_code == 200
    assert "summary" in response.json()
