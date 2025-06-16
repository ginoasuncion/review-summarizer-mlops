from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_valid_product_summary() -> None:
    response = client.post("/summarize", json={"product_name": "iPhone"})
    assert response.status_code == 200
    data = response.json()
    assert "iPhone" in data["summary"]


def test_missing_product_name() -> None:
    response = client.post("/summarize", json={})
    assert response.status_code == 422  # Unprocessable Entity (validation error)


def test_invalid_payload_type() -> None:
    response = client.post("/summarize", json={"product_name": 123})
    assert response.status_code == 422


def test_extra_field_ignored() -> None:
    response = client.post(
        "/summarize", json={"product_name": "MacBook", "extra": "field"}
    )
    assert response.status_code == 200
    assert "MacBook" in response.json()["summary"]


def test_empty_product_name() -> None:
    response = client.post("/summarize", json={"product_name": ""})
    assert response.status_code == 200
    summary = response.json()["summary"]
    assert "has excellent reviews overall" in summary
