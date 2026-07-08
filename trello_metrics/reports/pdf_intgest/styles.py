"""Montagem do bloco <style> do relatório PDF IntGest."""
from __future__ import annotations

from pathlib import Path

ASSETS = Path(__file__).parent / "assets"


def _font_css() -> str:
    return (
        "@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700&display=swap');"
    )


def _page_css(size: str = "A4") -> str:
    return (
        "*{-webkit-print-color-adjust:exact;print-color-adjust:exact;}"
        "html,body{margin:0;padding:0;}"
        "body{font-family:'Montserrat',system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;"
        "color:#1A1A1A;background:#FFFFFF;}"
        "a{color:#3982DB;text-decoration:none;}"
        f"@page{{size:{size};}}"
    )


def build_style_block(size: str = "A4") -> str:
    report_css = (ASSETS / "report.css").read_text(encoding="utf-8")
    extra = (
        ".rt-logo-text{font-size:28px;font-weight:700;color:#133968;letter-spacing:2px;line-height:52px;}"
        ".rt-chart{width:100%;max-height:320px;object-fit:contain;margin:10px 0 14px;border-radius:8px;}"
        ".rt-muted{font-size:10px;color:#666;line-height:1.45;margin:6px 0 10px;}"
        ".rt-h3{font-size:14px;font-weight:700;color:#275362;margin:14px 0 8px;letter-spacing:-.2px;}"
        ".rt-h4{font-size:12px;font-weight:700;color:#428BA5;margin:12px 0 6px;}"
    )
    return _font_css() + _page_css(size) + report_css + extra
