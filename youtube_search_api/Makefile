# YouTube Search API Makefile

.PHONY: help setup install test run build deploy clean

help: ## Show this help message
	@echo "YouTube Search API - Available commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

setup: ## Run the setup script
	./setup.sh

install: ## Install dependencies
	pip install -r requirements.txt

test: ## Run API tests
	python test_api.py

run: ## Run the API locally
	python main.py

build: ## Build Docker image
	docker build -t youtube-search-api .

deploy: ## Deploy to Cloud Run
	./deploy.sh

clean: ## Clean up generated files
	rm -rf __pycache__
	rm -rf *.pyc
	rm -rf venv
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

docker-build: ## Build and tag Docker image
	docker build -t gcr.io/$(shell gcloud config get-value project)/youtube-search-api .

docker-push: ## Push Docker image to registry
	docker push gcr.io/$(shell gcloud config get-value project)/youtube-search-api

docker-deploy: docker-build docker-push ## Build, push and deploy
	gcloud run deploy youtube-search-api \
		--image gcr.io/$(shell gcloud config get-value project)/youtube-search-api \
		--platform managed \
		--region us-central1 \
		--allow-unauthenticated \
		--memory 512Mi \
		--cpu 1 \
		--max-instances 10

logs: ## View Cloud Run logs
	gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=youtube-search-api" --limit=50

status: ## Check Cloud Run service status
	gcloud run services describe youtube-search-api --region=us-central1 --format="value(status.url)" 