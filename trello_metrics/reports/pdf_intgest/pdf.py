"""Renderização HTML → PDF via Playwright (Chromium)."""
from __future__ import annotations

from pathlib import Path


def render_pdf(
    html: str,
    out_path: str | Path,
    *,
    size: str = "A4",
    margin: str = "0.6in",
) -> Path:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Playwright nao instalado. Rode:\n"
            "    pip install playwright\n"
            "    playwright install chromium"
        ) from exc

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    footer = (
        '<div style="font-size:8px;color:#666;width:100%;padding:0 0.6in;'
        'display:flex;justify-content:space-between;font-family:Montserrat,sans-serif;">'
        '<span>Metricas Trello INTGEST</span>'
        '<span>Pagina <span class="pageNumber"></span></span></div>'
    )

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="networkidle")
        page.emulate_media(media="print")
        try:
            page.evaluate("document.fonts.ready")
        except Exception:
            pass
        page.pdf(
            path=str(out),
            format=size,
            print_background=True,
            display_header_footer=True,
            header_template="<div></div>",
            footer_template=footer,
            prefer_css_page_size=False,
            margin={"top": margin, "bottom": margin, "left": margin, "right": margin},
        )
        browser.close()
    return out
