"""PDF report rendering. Markdown -> HTML -> PDF via xhtml2pdf.

Optional dependency: install with ``pip install ai-readiness[pdf]``.
"""

from __future__ import annotations

from pathlib import Path

_CSS = """
@page { size: A4; margin: 1.6cm 1.8cm; }
body { font-family: 'Helvetica', 'Arial', sans-serif; font-size: 10pt; color: #222; }
h1 { color: #1f4e79; border-bottom: 2px solid #1f4e79; padding-bottom: 4px; }
h2 { color: #2e75b6; margin-top: 18pt; border-bottom: 1px solid #d0d7de; padding-bottom: 2px; }
h3 { color: #2e75b6; margin-top: 12pt; }
h4 { color: #444; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0; }
th { background-color: #f0f4f8; text-align: left; padding: 4px 6px; border: 1px solid #ccc; font-size: 9pt; }
td { padding: 3px 6px; border: 1px solid #ddd; font-size: 9pt; }
code { background-color: #f4f4f4; padding: 1px 4px; border-radius: 3px; font-family: 'Courier New', monospace; font-size: 9pt; }
pre { background-color: #f4f4f4; padding: 6px; border-radius: 4px; font-size: 8.5pt; }
blockquote { border-left: 3px solid #2e75b6; padding-left: 8px; color: #555; margin: 6pt 0; }
ul, ol { margin: 4pt 0 4pt 18pt; }
li { margin-bottom: 2pt; }
hr { border: none; border-top: 1px solid #ccc; margin: 12pt 0; }
"""


def render_pdf(markdown_text: str, output_path: Path) -> Path:
    """Render Markdown to a PDF file. Returns the output path.

    Raises ``RuntimeError`` if optional PDF dependencies aren't installed.
    """
    try:
        import markdown as md_lib
        from xhtml2pdf import pisa
    except ImportError as exc:
        raise RuntimeError(
            "PDF output requires optional dependencies. "
            "Install with: pip install ai-readiness[pdf]"
        ) from exc

    html_body = md_lib.markdown(
        markdown_text,
        extensions=["tables", "fenced_code", "sane_lists"],
    )
    html = (
        "<html><head><meta charset='utf-8'>"
        f"<style>{_CSS}</style>"
        "</head><body>"
        f"{html_body}"
        "</body></html>"
    )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as fh:
        result = pisa.CreatePDF(src=html, dest=fh, encoding="utf-8")
    if result.err:
        raise RuntimeError(f"PDF rendering failed ({result.err} errors).")
    return output_path
