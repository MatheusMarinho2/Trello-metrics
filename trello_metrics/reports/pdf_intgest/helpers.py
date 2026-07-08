"""Utilitários de formatação e componentes HTML do relatório PDF IntGest."""
from __future__ import annotations

import base64
import re
from html import escape as _html_escape
from pathlib import Path

NAVY = "#133968"
TEAL = "#428BA5"

PRIO_COLORS = {
    "Critica": "#8E0000", "Crítica": "#8E0000",
    "Urgente": "#C62828",
    "Alta": "#F57C00",
    "Média": "#2196F3", "Media": "#2196F3",
    "Baixa": "#9E9E9E",
}
RISK_COLORS = {
    "critico": "#C62828", "alto": "#F57C00",
    "medio": "#2196F3", "médio": "#2196F3", "baixo": "#4CAF50",
}
ROLE_COLORS = {
    "Desenvolvedor": "#133968", "Revisor em Par": "#428BA5",
    "Revisor": "#275362", "Solicitante": "#F57C00", "Tester": "#2196F3",
}
SEAL_COLORS = {"Ouro": "#C9A227", "Prata": "#8C9AA3", "Bronze": "#B87333"}

MONTHS_PT = [
    "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]


def prio_color(p: str) -> str:
    return PRIO_COLORS.get(p, "#666")


def risk_color(r: str) -> str:
    return RISK_COLORS.get((r or "").lower(), "#666")


def role_color(r: str) -> str:
    return ROLE_COLORS.get(r, "#666")


def esc(s) -> str:
    if s is None:
        return ""
    return _html_escape(str(s), quote=True)


def dev_name(d) -> str:
    return re.sub(r"^[A-Z]{1,3}-", "", str(d or "")).replace(".", " ")


def month_label(month: str) -> str:
    y, mo = month.split("-")
    return f"{MONTHS_PT[int(mo)]} · {y}"


def md(raw) -> str:
    if not raw:
        return ""
    t = str(raw)
    t = re.sub(r"\\([_*`#\[\]()~>|-])", r"\1", t)
    codes: list[str] = []

    def _grab_block(m):
        codes.append(m.group(1).strip())
        return f"@@CB{len(codes) - 1}@@"

    def _grab_span(m):
        codes.append(m.group(1))
        return f"@@CS{len(codes) - 1}@@"

    t = re.sub(r"```([\s\S]*?)```", _grab_block, t)
    t = re.sub(r"`([^`]+)`", _grab_span, t)
    t = esc(t)
    t = re.sub(
        r"\[([^\]]+)\]\((https?:[^)\s]+)(?:\s+&quot;[^)]*&quot;)?\)",
        r'<span class="rt-lnk">\1</span>', t,
    )
    t = re.sub(r"#{2,6}\s*\*\*(.+?)\*\*", r"\n@@H@@\1@@/H@@\n", t)
    t = re.sub(r"#{2,6}\s*([^\n]+)", r"\n@@H@@\1@@/H@@\n", t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"\s*---+\s*", "\n", t)
    t = re.sub(r"\s+-\s+", "\n• ", t)
    t = re.sub(r"(^|\n)(\d{1,2})\.\s+", r"\1\n\2. ", t)
    t = t.replace("|", " · ")

    def _pre(m):
        return f"@@PRE@@{esc(codes[int(m.group(1))])}@@/PRE@@"

    def _code(m):
        return f'<code class="rt-code">{esc(codes[int(m.group(1))])}</code>'

    t = re.sub(r"@@CB(\d+)@@", _pre, t)
    t = re.sub(r"@@CS(\d+)@@", _code, t)

    parts = [p.strip() for p in re.split(r"\n{1,}", t) if p.strip()]
    html = ""
    for p in parts:
        if p.startswith("@@H@@"):
            inner = p.replace("@@H@@", "", 1).replace("@@/H@@", "", 1)
            html += f'<div class="rt-mh">{inner}</div>'
        elif p.startswith("@@PRE@@"):
            inner = p.replace("@@PRE@@", "", 1).replace("@@/PRE@@", "", 1)
            html += f'<pre class="rt-pre">{inner}</pre>'
        elif p.startswith("•"):
            html += f'<div class="rt-li">{re.sub(r"^•\s*", "", p)}</div>'
        else:
            html += f"<p>{p}</p>"
    return html


def pill(text, color) -> str:
    return (
        f'<span class="rt-pill" style="color:{color};border-color:{color}44;'
        f'background:{color}12;">{esc(text)}</span>'
    )


def badge(text, color) -> str:
    return (
        f'<span class="rt-badge" style="color:{color};background:{color}14;'
        f'border:1px solid {color}44;">{esc(text)}</span>'
    )


def role_chip(r) -> str:
    c = role_color(r)
    return (
        f'<span class="rt-role" style="color:{c};background:{c}14;'
        f'border:1px solid {c}33;">{esc(r)}</span>'
    )


def table(headers, rows, align=None, cls="") -> str:
    align = align or []

    def a(i):
        return align[i] if i < len(align) and align[i] else "left"

    th = "".join(f'<th style="text-align:{a(i)}">{h}</th>' for i, h in enumerate(headers))
    tb = ""
    for r in rows:
        cells = ""
        for i, c in enumerate(r):
            val = "—" if (c is None or c == "") else c
            cells += f'<td style="text-align:{a(i)}">{val}</td>'
        tb += f"<tr>{cells}</tr>"
    klass = f"rt-table {cls}".strip()
    return f'<table class="{klass}"><thead><tr>{th}</tr></thead><tbody>{tb}</tbody></table>'


def metric_card(label, value, sub=None, accent=NAVY) -> str:
    sub_html = f'<div class="rt-msub">{sub}</div>' if sub else ""
    return (
        '<div class="rt-metric">'
        f'<div class="rt-mval" style="color:{accent}">{value}</div>'
        f'<div class="rt-mlabel">{esc(label)}</div>{sub_html}'
        "</div>"
    )


def sec_head(num, title, sub=None) -> str:
    sub_html = f'<p class="rt-secsub">{esc(sub)}</p>' if sub else ""
    return (
        '<div class="rt-sechead">'
        f'<div class="rt-secnum">{num}</div>'
        f'<div class="rt-sectt"><h2 class="rt-h2">{esc(title)}</h2>{sub_html}</div>'
        "</div>"
    )


def note(html_text) -> str:
    return f'<div class="rt-notebox">{html_text}</div>'


def subttl(t) -> str:
    return f'<div class="rt-subttl">{esc(t)}</div>'


def muted(text) -> str:
    return f'<div class="rt-muted">{text}</div>'


def chart_img(path: Path | None) -> str:
    if not path or not path.exists():
        return ""
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f'<img class="rt-chart" src="data:image/png;base64,{b64}" alt=""/>'
