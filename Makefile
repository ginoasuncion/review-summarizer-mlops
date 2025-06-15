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

# Run tests
test:
	pytest

# Run pre-commit hooks
lint:
	pre-commit run --all-files

# Freeze requirements (for CI or reproducibility)
freeze:
	uv pip freeze > requirements.txt

