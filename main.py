import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, Query

app = FastAPI()


# Placeholder scraper function
def scrape_reviews(product_url: str) -> dict:
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        response = requests.get(product_url, headers=headers, timeout=10)
    except requests.RequestException:
        return {"error": "Failed to connect to the provided URL."}

    if response.status_code != 200:
        return {"error": f"Failed to fetch page, status code: {response.status_code}"}

    soup = BeautifulSoup(response.text, "html.parser")

    # Placeholder extraction: update this based on target site structure
    reviews = []
    for tag in soup.select(".review-text, .review"):  # Update selector
        reviews.append(tag.get_text(strip=True))

    if not reviews:
        reviews = ["No reviews found (check your selector or page structure)."]

    return {"product_url": product_url, "reviews": reviews}


# FastAPI endpoint
@app.get("/scrape/")
def scrape(
    product_url: str = Query(..., description="Product page URL to scrape reviews from")
):
    return scrape_reviews(product_url)
