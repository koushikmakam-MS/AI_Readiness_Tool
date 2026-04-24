# 🤖 AI Readiness Tool

Assess how **AI coding agent friendly** your repository is. Get a score (0-100) with actionable recommendations — works with any language, any codebase, any AI agent.

## Features

- **Language-agnostic** — detects your stack and adapts checks automatically
- **Agent-agnostic** — checks readiness for Copilot, Cursor, Aider, Claude, and more
- **Plugin architecture** — add custom dimensions via YAML config
- **Hybrid analysis** — fast static checks + optional LLM-powered deep analysis (OpenAI)
- **3 output formats** — Terminal (rich), JSON (CI), Markdown (PR comments)
- **Local & remote** — scan local paths or clone from GitHub URLs

## Quick Start

```bash
# Install
pip install -e .

# Scan current directory
ai-readiness check .

# Scan a GitHub repo
ai-readiness check https://github.com/microsoft/vscode

# Scan with shorthand
ai-readiness check microsoft/vscode

# Clone to specific directory
ai-readiness check owner/repo --clone-dir ./repos
```

## Output Formats

```bash
# Terminal (default) — colored output with score bars
ai-readiness check .

# JSON — machine-readable for CI pipelines
ai-readiness check . --format json

# Markdown — shareable, suitable for PR comments
ai-readiness check . --format markdown
```

## Assessment Dimensions

| Dimension | Weight | What it checks |
|-----------|--------|----------------|
| 📄 Documentation | 20% | README, CONTRIBUTING, architecture docs, changelog |
| 🚀 Setup & Onboarding | 15% | Makefile, Dockerfile, scripts, env templates |
| 🤖 AI Agent Configuration | 15% | copilot-instructions, cursorrules, AGENTS.md, CLAUDE.md |
| ✅ Testing & Verification | 20% | Test files, CI/CD pipelines, coverage config |
| 🏗️ Code Quality & Structure | 15% | Linters, formatters, type checking, file sizes |
| 📦 Dependency Management | 8% | Lock files, manifests, version pinning |
| 🛡️ Change Safety | 7% | PR templates, pre-commit hooks, security policy |

## Scoring

- Each dimension scores **0-10** based on checks passed
- **Overall score** = weighted average (0-100)
- Ratings: 🔴 Poor (0-39) · 🟡 Fair (40-59) · 🟢 Good (60-79) · 🌟 Excellent (80-100)

## LLM Analysis

By default, the tool runs LLM-powered deep analysis on top of static checks using OpenAI GPT-4o.

```bash
# Initialize config with API key
ai-readiness init-config --api-key sk-...

# Run with LLM (default)
ai-readiness check .

# Run without LLM (offline/static only)
ai-readiness check . --no-llm
```

Config is stored at `~/.ai-readiness/config.yaml`.

## CI Integration

Add to your GitHub Actions workflow:

```yaml
- name: AI Readiness Check
  run: |
    pip install ai-readiness
    ai-readiness check . --format json > report.json
```

Or use the included workflow at `.github/workflows/ai-readiness.yml` which auto-comments on PRs.

## Custom Checkers

Dimensions are config-driven. Create a custom checker:

```python
from ai_readiness.checkers.base import BaseChecker
from ai_readiness.core.models import CheckResult, CheckStatus

class MyCustomChecker(BaseChecker):
    dimension_id = "my_check"
    dimension_name = "My Custom Dimension"
    default_weight = 10.0

    def run_checks(self) -> list[CheckResult]:
        # Your checks here
        return [
            CheckResult(
                name="My check",
                status=CheckStatus.PASS,
                message="Everything looks good!",
            )
        ]
```

Register it in your config YAML:

```yaml
dimensions:
  my_check:
    enabled: true
    weight: 10
    checker: my_module.MyCustomChecker
```

## Commands

```bash
ai-readiness check <path-or-url>    # Run assessment
ai-readiness init-config             # Create user config
ai-readiness list-checkers           # Show configured dimensions
```

## License

MIT
