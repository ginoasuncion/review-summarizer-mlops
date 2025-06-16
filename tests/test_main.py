import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_scrape_endpoint():
    test_url = "https://example.com"

    response = client.get("/scrape/", params={"product_url": test_url})

    assert response.status_code == 200

    json_response = response.json()
    assert "product_url" in json_response
    assert json_response["product_url"] == test_url
    assert "reviews" in json_response
    assert isinstance(json_response["reviews"], list)
    # We expect either empty or default placeholder message
    assert len(json_response["reviews"]) > 0
