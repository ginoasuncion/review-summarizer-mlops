# 🚀 Review Summarizer MLOps

An automated system that retrieves and summarizes product reviews or video transcripts using LLMs — built with FastAPI and MLOps best practices.

---

## 🛠 Installation

### 1. Clone the repository

```bash
git clone https://github.com/ginoasuncion/review-summarizer-mlops.git
cd review-summarizer-mlops
```

### 2. Set up virtual environment using [uv](https://github.com/astral-sh/uv)

```bash
uv venv
source .venv/bin/activate  # or .uv/bin/activate if that's your setup
```

### 3. Install dependencies

```bash
uv pip install --system .
```

---

## 🧪 Running Tests

To run all tests:

```bash
pytest
```

You can also check type correctness:

```bash
mypy .
```

---

## ✅ Developer Setup

### Install and enable pre-commit hooks

```bash
uv pip install pre-commit
pre-commit install
```

### Run manually

```bash
black .
ruff check . --fix
pytest
mypy .
```

---

## 🔁 GitHub Actions

CI automatically checks:
- ✅ Formatting via **Black**
- ✅ Linting via **Ruff**
- ✅ Tests via **Pytest**
- ✅ Type checking via **Mypy**

---

## 🧠 GitHub Issue Automation

This project uses a GitHub Actions workflow to **automatically create a new branch** when an issue is opened.

- Branches follow this format:

  ```
  issue-<number>-<slugified-title>
  ```

  Example:  
  `issue-7-add-openai-summarizer-module`

- ✅ Requires a secret named `GH_PAT` with `repo` and `workflow` scopes.

---

## 📂 Project Structure

```
├── main.py               # FastAPI app entry point
├── tests/                # Pytest-based tests
├── pyproject.toml        # Project config and dependencies
├── requirements.txt
└── README.md
```

---

## 📦 Download

[![Download](https://img.shields.io/badge/Download-ZIP-blue?logo=github)](https://github.com/ginoasuncion/review-summarizer-mlops/archive/refs/heads/main.zip)
