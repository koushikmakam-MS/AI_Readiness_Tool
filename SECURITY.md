# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please report it responsibly.

**Do not open a public issue.** Instead, send an email to the project maintainers with:

- A description of the vulnerability
- Steps to reproduce it
- The potential impact
- Any suggested fixes (optional)

We will acknowledge your report within 48 hours and aim to provide a fix within 7 days for critical issues.

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅ Current |

## Security Considerations

This tool is **read-only** — it never modifies the target repository. However:

- **API keys**: The tool uses OpenAI / Azure OpenAI API keys. Never commit these to source control. Use environment variables.
- **Repository cloning**: When scanning remote repos, the tool performs shallow clones into temporary directories that are cleaned up after the scan.
- **LLM outputs**: Persona scores and suggestions are AI-generated. They should be reviewed by humans before acting on them.
- **Cache data**: Embeddings and scores are cached locally under `~/.ai-readiness/`. This cache may contain derived representations of your documentation.
