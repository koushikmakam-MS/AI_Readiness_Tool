# Contributing to AI Readiness Tool

Thank you for your interest in contributing! This guide will help you get started.

## Getting Started

### Prerequisites

- Python 3.10+
- Git

### Setup

```bash
# Clone the repo
git clone https://github.com/koushikmakam-MS/AI_Readiness_Tool.git
cd AI_Readiness_Tool

# Create a virtual environment
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # macOS / Linux

# Install in development mode
pip install -e ".[dev]"

# (Optional) Install PDF support
pip install -e ".[pdf]"
```

### Running Tests

```bash
# Run the full test suite
pytest

# Run with coverage
pytest --cov=ai_readiness --cov-report=term-missing

# Run a specific test file
pytest tests/test_checkers/test_documentation.py
```

## How to Contribute

### Reporting Bugs

Open an issue with:
- Steps to reproduce
- Expected vs actual behaviour
- Python version and OS

### Suggesting Features

Open an issue describing:
- The problem you're solving
- Your proposed solution
- Any alternatives you considered

### Submitting Changes

1. Fork the repo and create a feature branch from `master`
2. Make your changes
3. Add or update tests as needed
4. Run the full test suite: `pytest`
5. Commit with a clear message (see below)
6. Open a pull request

### Commit Messages

Use conventional commit style:

```
feat: add new checker for monorepo detection
fix: handle empty README gracefully in doc checker
docs: update persona cast table in README
test: add coverage for context-aware skip logic
```

## Project Structure

| Directory | Purpose |
|-----------|---------|
| `ai_readiness/checkers/` | Pluggable static analysis checkers |
| `ai_readiness/core/` | Engine, reporter, models, config |
| `ai_readiness/llm/` | LLM client and analyzer |
| `ai_readiness/personas/` | Persona-based doc readiness suite |
| `tests/` | Test suite (mirrors source layout) |
| `config/` | Default YAML configurations |

## Code Style

- Follow existing patterns in the codebase
- Add type hints to function signatures
- Keep functions focused and under 50 lines where practical
- Comment *why*, not *what*

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you agree to uphold it.

---

## Adding a New Persona

The tool ships 10 built-in personas. You can add more by following these steps:

### 1. Create the prompt file

Copy the template and fill in the placeholders:

```bash
cp ai_readiness/personas/prompts/_TEMPLATE.md ai_readiness/personas/prompts/your_persona.md
```

Edit `your_persona.md` — give the persona a name, role, and perspective. The three scoring dimensions (`context_sufficiency`, `ambiguity_risk`, `token_efficiency`) are fixed; only the perspective changes.

### 2. Register in `registry.py`

Add a tuple to the `_BUILTIN` list in `ai_readiness/personas/registry.py`:

```python
(
    "your_id",                    # unique snake_case ID
    "Character Name",             # display name
    "Role Description",           # short role (shown in report tables)
    "your_persona.md",            # prompt file name
    "interest keywords...",       # comma-separated topics the persona cares about
    "A simulated task sentence.", # end-to-end task for validation
    1.0,                          # weight (1.0 = default)
),
```

### 3. Update counts

- Update the persona count in `README.md` (search for "10 personas")
- Add a row to the persona cast table in `README.md`

### 4. Test

```bash
# Run existing tests
pytest

# Test your persona on a repo
ai-readiness personas . --personas your_id --format markdown
```
