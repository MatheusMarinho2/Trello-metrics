from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any


COLORS = {
    "blue": "#2563eb",
    "teal": "#0891b2",
    "slate": "#64748b",
    "green": "#16a34a",
    "red": "#dc2626",
    "orange": "#ea580c",
    "purple": "#7c3aed",
    "indigo": "#4f46e5",
}


from trello_metrics.reports.report_layouts import allows_section


def render_charts(metrics: dict[str, Any]) -> dict[str, Path]:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return {}

    charts: dict[str, Path] = {}
    temp_dir = Path(tempfile.mkdtemp(prefix="trello_metrics_"))
    report_type = (metrics.get("export_meta") or {}).get("report_type")
    include = lambda section: allows_section(report_type, section)

    team = metrics.get("team_summary")
    if team and include("team_summary"):
        charts["executive"] = _executive_chart(temp_dir, team, plt)
        charts["quality"] = _quality_chart(temp_dir, team, plt)

    flow = metrics.get("flow") or {}
    if include("flow") and flow.get("cfd"):
        path = _cfd_chart(temp_dir, flow["cfd"], plt)
        if path:
            charts["cfd"] = path
    if include("flow") and flow.get("stage_time"):
        path = _stage_time_chart(temp_dir, flow["stage_time"], plt)
        if path:
            charts["stage_time"] = path

    fibonacci = metrics.get("fibonacci_points") or {}
    if include("fibonacci") and fibonacci.get("by_developer"):
        charts["fibonacci"] = _fibonacci_chart(temp_dir, fibonacci["by_developer"], plt)

    collaborators = metrics.get("collaborators") or []
    if include("collaborators") and collaborators:
        path = _collab_points_chart(temp_dir, collaborators, plt)
        if path:
            charts["collab_points"] = path
        charts["collab_time"] = _collab_time_chart(temp_dir, collaborators, plt)

    profiles = metrics.get("developer_profiles") or []
    developers = profiles or metrics.get("developers") or []
    if include("developers") and developers:
        charts["dev_points"] = _dev_points_chart(temp_dir, developers, plt)
        charts["dev_quality"] = _dev_quality_chart(temp_dir, developers, plt)
        charts["dev_flow"] = _dev_flow_chart(temp_dir, developers, plt)

    bottlenecks = metrics.get("bottlenecks", {})
    if include("bottlenecks") and bottlenecks.get("by_stage"):
        charts["bottlenecks"] = _bottleneck_chart(temp_dir, bottlenecks["by_stage"], plt)

    trends = metrics.get("trends_6m", {})
    if include("trends") and trends.get("team"):
        charts["trends_team"] = _trends_team_chart(temp_dir, trends["team"], plt)
        charts["trends_quality"] = _trends_quality_chart(temp_dir, trends["team"], plt)
    if trends.get("developers"):
        charts["trends_devs"] = _trends_devs_chart(
            temp_dir, trends.get("months", []), trends["developers"], plt
        )

    projects = metrics.get("projects", [])
    if include("projects") and projects:
        charts["projects"] = _projects_chart(temp_dir, projects, plt)

    testers = metrics.get("testers") or []
    if include("testers") and testers:
        path = _testers_chart(temp_dir, testers, plt)
        if path:
            charts["testers"] = path

    sla = metrics.get("sla") or {}
    if include("sla") and sla.get("by_stage"):
        path = _sla_stage_chart(temp_dir, sla["by_stage"], plt)
        if path:
            charts["sla_stage"] = path

    return charts


def _save(fig: Any, path: Path) -> Path:
    fig.tight_layout()
    fig.savefig(path, dpi=130, bbox_inches="tight")
    __import__("matplotlib.pyplot", fromlist=["close"]).close(fig)
    return path


def _short_name(value: str, limit: int = 18) -> str:
    text = str(value or "")
    return text.replace("D-", "").replace("T-", "")[:limit]


def _executive_chart(temp_dir: Path, team: dict[str, Any], plt: Any) -> Path:
    labels = ["Pontos normais", "Pontos analise", "Cards entregues"]
    values = [
        team.get("fibonacci_normal", 0),
        team.get("fibonacci_analysis", 0),
        team.get("cards_delivered", 0),
    ]
    fig, ax = plt.subplots(figsize=(7, 3.8))
    ax.bar(labels, values, color=[COLORS["blue"], COLORS["teal"], COLORS["slate"]])
    ax.set_title("Resumo executivo do mes")
    ax.grid(axis="y", alpha=0.2)
    return _save(fig, temp_dir / "executive.png")


def _quality_chart(temp_dir: Path, team: dict[str, Any], plt: Any) -> Path:
    labels = ["Qualidade", "Retrabalho", "Aceitacao"]
    values = [
        team.get("quality_rate_pct", 0),
        team.get("rework_rate_pct", 0),
        team.get("acceptance_rate_pct", 0),
    ]
    fig, ax = plt.subplots(figsize=(7, 3.8))
    ax.bar(labels, values, color=[COLORS["green"], COLORS["red"], COLORS["blue"]])
    ax.set_ylim(0, 100)
    ax.set_ylabel("%")
    ax.set_title("Qualidade vs retrabalho")
    ax.grid(axis="y", alpha=0.2)
    return _save(fig, temp_dir / "quality.png")


def _cfd_chart(temp_dir: Path, rows: list[dict[str, Any]], plt: Any) -> Path | None:
    if not rows:
        return None
    stage_names = sorted({key for row in rows for key in row if key != "date"})
    if not stage_names:
        return None
    palette = list(COLORS.values())
    dates = [row.get("date", "") for row in rows]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    bottom = [0.0] * len(rows)
    for index, stage in enumerate(stage_names[:8]):
        values = [float(row.get(stage) or 0) for row in rows]
        ax.bar(
            dates,
            values,
            bottom=bottom,
            label=stage[:24],
            color=palette[index % len(palette)],
        )
        bottom = [base + value for base, value in zip(bottom, values)]
    ax.set_title("CFD diario")
    ax.tick_params(axis="x", rotation=35)
    ax.legend(fontsize=7, loc="upper left")
    ax.grid(axis="y", alpha=0.2)
    return _save(fig, temp_dir / "cfd.png")


def _stage_time_chart(temp_dir: Path, stages: list[dict[str, Any]], plt: Any) -> Path | None:
    rows = [row for row in stages if row.get("median_hours", 0) > 0][:10]
    if not rows:
        rows = stages[:10]
    if not rows:
        return None
    labels = [_short_name(row.get("title", "-"), 24) for row in rows]
    values = [row.get("median_hours", 0) for row in rows]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.barh(labels, values, color=COLORS["indigo"])
    ax.set_xlabel("Horas (mediana)")
    ax.set_title("Tempo por etapa")
    ax.invert_yaxis()
    ax.grid(axis="x", alpha=0.2)
    return _save(fig, temp_dir / "stage_time.png")


def _fibonacci_chart(temp_dir: Path, rows: list[dict[str, Any]], plt: Any) -> Path:
    top = rows[:12]
    names = [_short_name(row.get("developer", "-")) for row in top]
    normal = [row.get("points_normal", 0) for row in top]
    analysis = [row.get("points_analysis", 0) for row in top]
    x = range(len(names))
    width = 0.38
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.bar([i - width / 2 for i in x], normal, width, label="Normais", color=COLORS["blue"])
    ax.bar([i + width / 2 for i in x], analysis, width, label="Analise", color=COLORS["teal"])
    ax.set_xticks(list(x))
    ax.set_xticklabels(names, rotation=25, ha="right")
    ax.set_title("Distribuicao de pontos Fibonacci")
    ax.legend()
    ax.grid(axis="y", alpha=0.2)
    return _save(fig, temp_dir / "fibonacci.png")


def _collab_points_chart(temp_dir: Path, collaborators: list[dict[str, Any]], plt: Any) -> Path | None:
    top = [
        row for row in collaborators
        if (row.get("summary") or {}).get("has_developer_points")
    ][:10]
    if not top:
        return None
    names = [_short_name(row.get("name", "-")) for row in top]
    normal = [(row.get("summary") or {}).get("fibonacci_normal", 0) for row in top]
    analysis = [(row.get("summary") or {}).get("fibonacci_analysis", 0) for row in top]
    x = range(len(names))
    width = 0.38
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.bar([i - width / 2 for i in x], normal, width, label="Normais", color=COLORS["blue"])
    ax.bar([i + width / 2 for i in x], analysis, width, label="Analise", color=COLORS["teal"])
    ax.set_xticks(list(x))
    ax.set_xticklabels(names, rotation=25, ha="right")
    ax.set_title("Pontos por colaborador (papel dev)")
    ax.legend()
    return _save(fig, temp_dir / "collab_points.png")


def _collab_time_chart(temp_dir: Path, collaborators: list[dict[str, Any]], plt: Any) -> Path:
    top = collaborators[:12]
    names = [_short_name(row.get("name", "-")) for row in top]
    values = [(row.get("summary") or {}).get("time_hours", 0) for row in top]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.bar(names, values, color=COLORS["purple"])
    ax.set_title("Tempo de atuacao por colaborador")
    ax.tick_params(axis="x", rotation=25)
    ax.set_ylabel("Horas")
    ax.grid(axis="y", alpha=0.2)
    return _save(fig, temp_dir / "collab_time.png")


def _dev_points_chart(temp_dir: Path, developers: list[dict[str, Any]], plt: Any) -> Path:
    top = developers[:10]
    names = [_short_name(row.get("name", "-")) for row in top]
    normal = [row.get("fibonacci_normal", 0) for row in top]
    analysis = [row.get("fibonacci_analysis", 0) for row in top]
    x = range(len(names))
    width = 0.38
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.bar([i - width / 2 for i in x], normal, width, label="Normais", color=COLORS["blue"])
    ax.bar([i + width / 2 for i in x], analysis, width, label="Analise", color=COLORS["teal"])
    ax.set_xticks(list(x))
    ax.set_xticklabels(names, rotation=25, ha="right")
    ax.set_title("Pontos por desenvolvedor")
    ax.legend()
    return _save(fig, temp_dir / "dev_points.png")


def _dev_quality_chart(temp_dir: Path, developers: list[dict[str, Any]], plt: Any) -> Path:
    top = developers[:10]
    names = [_short_name(row.get("name", "-")) for row in top]
    acceptance = [row.get("acceptance_rate_pct", 0) for row in top]
    returns = [row.get("suggestions_accepted", row.get("peer_review_returns", 0)) for row in top]
    fig, ax1 = plt.subplots(figsize=(9, 4.5))
    ax1.bar(names, acceptance, color=COLORS["green"])
    ax1.set_ylabel("Aceitacao (%)")
    ax1.set_title("Qualidade por desenvolvedor")
    ax1.tick_params(axis="x", rotation=25)
    ax2 = ax1.twinx()
    ax2.plot(names, returns, color=COLORS["teal"], marker="o", label="Sugestoes aceitas")
    ax2.set_ylabel("Sugestoes aceitas (par)")
    return _save(fig, temp_dir / "dev_quality.png")


def _dev_flow_chart(temp_dir: Path, developers: list[dict[str, Any]], plt: Any) -> Path:
    top = developers[:10]
    names = [_short_name(row.get("name", "-")) for row in top]
    work = [
        row.get("dev_work_hours_total")
        or row.get("avg_dev_work_hours")
        or 0
        for row in top
    ]
    wait = [
        row.get("pipeline_wait_hours_total")
        or row.get("avg_pipeline_wait_hours")
        or 0
        for row in top
    ]
    x = range(len(names))
    width = 0.38
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.bar([i - width / 2 for i in x], work, width, label="Atuacao dev", color=COLORS["green"])
    ax.bar([i + width / 2 for i in x], wait, width, label="Espera pipeline", color=COLORS["orange"])
    ax.set_xticks(list(x))
    ax.set_xticklabels(names, rotation=25, ha="right")
    ax.set_title("Atuacao vs espera no pipeline")
    ax.legend()
    return _save(fig, temp_dir / "dev_flow.png")


def _bottleneck_chart(temp_dir: Path, stages: list[dict[str, Any]], plt: Any) -> Path:
    rows = [row for row in stages if row.get("avg_hours", 0) > 0][:10]
    if not rows:
        rows = stages[:10]
    labels = [_short_name(row.get("title", "-"), 24) for row in rows]
    values = [row.get("avg_hours", 0) for row in rows]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.barh(labels, values, color=COLORS["orange"])
    ax.set_xlabel("Horas medias")
    ax.set_title("Gargalos por etapa")
    ax.invert_yaxis()
    return _save(fig, temp_dir / "bottlenecks.png")


def _trends_team_chart(temp_dir: Path, team_rows: list[dict[str, Any]], plt: Any) -> Path:
    months = [row["month"] for row in team_rows]
    normal = [row["fibonacci_normal"] for row in team_rows]
    analysis = [row["fibonacci_analysis"] for row in team_rows]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot(months, normal, marker="o", label="Normais", color=COLORS["blue"])
    ax.plot(months, analysis, marker="o", label="Analise", color=COLORS["teal"])
    ax.set_title("Tendencia de pontos (equipe)")
    ax.tick_params(axis="x", rotation=30)
    ax.legend()
    ax.grid(alpha=0.2)
    return _save(fig, temp_dir / "trends_team.png")


def _trends_quality_chart(temp_dir: Path, team_rows: list[dict[str, Any]], plt: Any) -> Path:
    months = [row["month"] for row in team_rows]
    quality = [row.get("quality_rate_pct", 0) for row in team_rows]
    rework = [row.get("rework_rate_pct", 0) for row in team_rows]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot(months, quality, marker="o", label="Qualidade (%)", color=COLORS["green"])
    ax.plot(months, rework, marker="o", label="Retrabalho (%)", color=COLORS["red"])
    ax.set_ylim(0, 100)
    ax.set_title("Tendencia de qualidade e retrabalho")
    ax.tick_params(axis="x", rotation=30)
    ax.legend()
    ax.grid(alpha=0.2)
    return _save(fig, temp_dir / "trends_quality.png")


def _trends_devs_chart(
    temp_dir: Path,
    months: list[str],
    developers: dict[str, dict[str, list[int]]],
    plt: Any,
) -> Path:
    fig, ax = plt.subplots(figsize=(9, 4.5))
    month_count = len(months)
    for name, series in list(developers.items())[:5]:
        normal = _pad_series(series.get("fibonacci_normal", []), month_count)
        analysis = _pad_series(series.get("fibonacci_analysis", []), month_count)
        total = [n + a for n, a in zip(normal, analysis)]
        if not any(total):
            continue
        ax.plot(months, total, marker="o", label=_short_name(name, 16))
    ax.set_title("Tendencia de pontos por desenvolvedor")
    ax.tick_params(axis="x", rotation=30)
    ax.legend(fontsize=7)
    ax.grid(alpha=0.2)
    return _save(fig, temp_dir / "trends_devs.png")


def _pad_series(values: list[int], size: int) -> list[int]:
    if len(values) >= size:
        return values[:size]
    return values + [0] * (size - len(values))


def _projects_chart(temp_dir: Path, projects: list[dict[str, Any]], plt: Any) -> Path:
    top = projects[:10]
    names = [_short_name(row.get("name", "-"), 16) for row in top]
    normal = [row.get("fibonacci_normal", 0) for row in top]
    analysis = [row.get("fibonacci_analysis", 0) for row in top]
    x = range(len(names))
    width = 0.38
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.bar([i - width / 2 for i in x], normal, width, label="Normais", color=COLORS["purple"])
    ax.bar([i + width / 2 for i in x], analysis, width, label="Analise", color=COLORS["indigo"])
    ax.set_xticks(list(x))
    ax.set_xticklabels(names, rotation=25, ha="right")
    ax.set_title("Pontos por projeto/sistema")
    ax.legend()
    return _save(fig, temp_dir / "projects.png")


def _testers_chart(temp_dir: Path, testers: list[dict[str, Any]], plt: Any) -> Path | None:
    if not testers:
        return None
    names = [_short_name(row.get("name", "-")) for row in testers[:10]]
    first_pass = [row.get("approved_first_pass", 0) for row in testers[:10]]
    prevented = [
        row.get("prevented_problems")
        or row.get("returned_dev_for_quality")
        or 0
        for row in testers[:10]
    ]
    x = range(len(names))
    width = 0.38
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.bar([i - width / 2 for i in x], first_pass, width, label="1a passagem", color=COLORS["green"])
    ax.bar([i + width / 2 for i in x], prevented, width, label="Problemas evitados", color=COLORS["orange"])
    ax.set_xticks(list(x))
    ax.set_xticklabels(names, rotation=25, ha="right")
    ax.set_title("Performance de testes")
    ax.legend()
    return _save(fig, temp_dir / "testers.png")


def _sla_stage_chart(temp_dir: Path, stages: list[dict[str, Any]], plt: Any) -> Path | None:
    rows = stages[:12]
    if not rows:
        return None
    labels = [_short_name(row.get("title", "-"), 22) for row in rows]
    values = [row.get("compliance_pct", 0) for row in rows]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.barh(labels, values, color=COLORS["blue"])
    ax.set_xlim(0, 100)
    ax.set_xlabel("Cumprimento (%)")
    ax.set_title("SLA por etapa")
    ax.invert_yaxis()
    ax.grid(axis="x", alpha=0.2)
    return _save(fig, temp_dir / "sla_stage.png")
