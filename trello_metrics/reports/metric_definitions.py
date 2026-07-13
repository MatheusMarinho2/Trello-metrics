from __future__ import annotations

import json
from importlib.resources import files
from typing import Any

_CACHE: dict[str, Any] | None = None


def _load() -> dict[str, Any]:
    global _CACHE
    if _CACHE is None:
        path = files("trello_metrics.reports").joinpath("metric_definitions.json")
        _CACHE = json.loads(path.read_text(encoding="utf-8"))
    return _CACHE


def metric_label(key: str) -> str:
    labels = _load().get("labels") or {}
    if key in labels:
        return labels[key]
    return key.replace("_", " ").strip().capitalize()


def metric_description(key: str) -> str:
    return (_load().get("descriptions") or {}).get(key, "")


def metric_formula(key: str) -> str:
    entry = (_load().get("formulas") or {}).get(key) or {}
    return str(entry.get("formula") or "")


def metric_example(key: str) -> str:
    entry = (_load().get("formulas") or {}).get(key) or {}
    return str(entry.get("example") or "")


def metric_help_text(key: str) -> str:
    parts: list[str] = []
    description = metric_description(key)
    formula = metric_formula(key)
    example = metric_example(key)
    if description:
        parts.append(description)
    if formula and formula != description:
        parts.append(f"Formula: {formula}")
    elif formula and not description:
        parts.append(formula)
    if example:
        parts.append(f"Exemplo: {example}")
    return "\n\n".join(parts)


def table_info(table_id: str) -> dict[str, Any]:
    return (_load().get("tables") or {}).get(table_id, {})


def section_guide(section_id: str) -> dict[str, Any]:
    return (_load().get("guides") or {}).get(section_id, {})


def management_guide_sections() -> list[str]:
    return [
        "management_intro",
        "team_summary",
        "flow",
        "priority",
        "dora",
        "sla",
        "process_discipline",
        "bottlenecks",
        "quality_gates",
        "risk",
        "direct_production",
        "analysis_workflow",
        "antifraud",
    ]


def definitions_json() -> str:
    return json.dumps(_load(), ensure_ascii=False)


def add_table_intro(story: list[Any], table_id: str, styles: Any) -> None:
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, Spacer

    info = table_info(table_id)
    description = info.get("description")
    if description:
        story.append(Paragraph(_escape_text(description), styles["Muted"]))
        story.append(Spacer(1, 0.15 * cm))

    columns = info.get("columns") or []
    legend_lines: list[str] = []
    for key in columns:
        desc = metric_description(key)
        if not desc:
            continue
        legend_lines.append(f"• {metric_label(key)}: {desc}")

    if legend_lines:
        story.append(
            Paragraph(
                "<br/>".join(_escape_text(line) for line in legend_lines),
                styles["Small"],
            )
        )
        story.append(Spacer(1, 0.2 * cm))


def add_section_guide(story: list[Any], section_id: str, styles: Any) -> None:
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, Spacer

    guide = section_guide(section_id)
    if not guide:
        return

    title = guide.get("title")
    if title:
        story.append(Paragraph(_escape_text(title), styles["Heading2"]))
    description = guide.get("description")
    if description:
        story.append(Paragraph(_escape_text(description), styles["Muted"]))
        story.append(Spacer(1, 0.12 * cm))

    for item in guide.get("metrics") or []:
        key = item.get("key", "")
        label = metric_label(key) if key else ""
        parts: list[str] = []
        formula = item.get("formula") or metric_formula(key) or metric_description(key)
        example = item.get("example") or metric_example(key)
        if label and formula:
            parts.append(f"<b>{_escape_text(label)}</b> — {_escape_text(formula)}")
        if example:
            parts.append(f"Exemplo: {_escape_text(example)}")
        if parts:
            story.append(Paragraph("<br/>".join(parts), styles["Small"]))
            story.append(Spacer(1, 0.08 * cm))

    story.append(Spacer(1, 0.15 * cm))


def add_management_guide(story: list[Any], styles: Any) -> None:
    from reportlab.lib.units import cm
    from reportlab.platypus import PageBreak, Paragraph, Spacer

    intro = section_guide("management_intro")
    if not intro:
        return

    story.append(PageBreak())
    story.append(Paragraph(intro.get("title") or "Memoria de calculo das metricas", styles["Heading1"]))
    if intro.get("description"):
        story.append(Paragraph(_escape_text(intro["description"]), styles["BodyText"]))
        story.append(Spacer(1, 0.25 * cm))

    for section_id in management_guide_sections():
        if section_id == "management_intro":
            continue
        add_section_guide(story, section_id, styles)


def _escape_text(value: Any) -> str:
    text = str(value or "")
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
