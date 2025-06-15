# Review Summarizer MLOps

An automated system that retrieves and summarizes product reviews or video transcripts using LLMs — built with MLOps best practices.

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
source .uv/bin/activate  # On macOS/Linux
# .uv\Scripts\Activate.ps1  # On Windows
```

### 3. Install dependencies

```bash
uv pip install .
```

### 4. (Optional) Lock your environment for reproducibility

```bash
uv pip freeze > requirements.txt
```

---

## ✅ Developer Setup

### Install and enable pre-commit

```bash
uv pip install pre-commit
pre-commit install
```

### Run linting, formatting, and tests manually

```bash
black .
ruff check .
pytest
```

---

## 🔁 GitHub Actions

CI automatically checks:
- Code formatting (Black)
- Linting (Ruff)
- Tests (Pytest)

---

## 🧠 GitHub Issue Automation

This project uses a GitHub Actions workflow to **automatically create a new branch** whenever a new issue is opened.

- Branches follow this naming convention:  
  ```
  issue-<number>-<slugified-title>
  ```
  Example: an issue titled `Add OpenAI summarizer module` creates a branch like  
  `issue-7-add-openai-summarizer-module`

- ✅ Requires a repository secret named `GH_PAT` with `repo` and `workflow` scopes.

This improves traceability and links development work directly to tracked issues.

