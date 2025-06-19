# Makefile for Review Summarizer MLOps

# Create virtual environment using uv
venv:
	uv venv
	source .uv/bin/activate

# Install dependencies
install:
	uv pip install .

# Format code
format:
	black .
	ruff check .

# Run pre-commit hooks
lint:
	pre-commit run --all-files

# Update lock file
lock:
	uv lock

