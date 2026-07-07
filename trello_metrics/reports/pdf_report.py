from __future__ import annotations

from pathlib import Path
from typing import Any

from trello_metrics.reports.charts import render_charts
from trello_metrics.reports.metric_definitions import (
    add_management_guide,
    add_section_guide,
    add_table_intro,
    metric_label,
)
from trello_metrics.reports.report_layouts import allows_section
from trello_metrics.utils.dates import human_hours


def write_pdf_report(metrics: dict[str, Any], output_path: str | Path) -> Path:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            Image,
            PageBreak,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError as exc:
        raise RuntimeError(
            "ReportLab nao esta instalado. Rode: python -m pip install -r requirements.txt"
        ) from exc

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    charts = render_charts(metrics)

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="Small",
            parent=styles["BodyText"],
            fontSize=8,
            leading=10,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Muted",
            parent=styles["BodyText"],
            fontSize=8,
            textColor=colors.HexColor("#555555"),
        )
    )

    doc = SimpleDocTemplate(
        str(output),
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.4 * cm,
        bottomMargin=1.4 * cm,
        title="Relatorio de metricas Trello",
    )

    story: list[Any] = []
    board = metrics["board"]
    overview = metrics["overview"]
    period = metrics.get("period")
    team = metrics.get("team_summary")

    export_meta = metrics.get("export_meta") or {}
    report_type = export_meta.get("report_type")
    include = lambda section: allows_section(report_type, section)

    title = (export_meta.get("title") or "").split("|")[0].strip()
    if not title:
        title = "Relatorio mensal INTGEST" if period else "Relatorio de metricas Trello"
    story.append(Paragraph(_escape(title), styles["Title"]))
    story.append(Paragraph(_escape(board.get("name", "")), styles["Heading2"]))
    story.append(Paragraph(f"Gerado em: {board.get('generated_at')}", styles["Muted"]))
    if period:
        story.append(
            Paragraph(
                f"Periodo: {period.get('month')} ({period.get('timezone')})",
                styles["Muted"],
            )
        )
    if board.get("url"):
        story.append(Paragraph(_escape(board["url"]), styles["Muted"]))
    story.append(Spacer(1, 0.4 * cm))

    if team and include("team_summary"):
        _add_team_summary(story, team, metrics.get("bottlenecks", {}), styles)
        if "executive" in charts:
            story.append(Spacer(1, 0.2 * cm))
            story.append(Image(str(charts["executive"]), width=16 * cm, height=7 * cm))
        if "quality" in charts:
            story.append(Spacer(1, 0.2 * cm))
            story.append(Image(str(charts["quality"]), width=16 * cm, height=7 * cm))

    if include("role_summary") and metrics.get("role_summary"):
        _add_role_summary_section(story, metrics["role_summary"], styles)

    if include("individual_summary") and metrics.get("individual_summary"):
        _add_individual_summary_section(story, metrics, styles)

    summary_rows = [
        ["Indicador", "Valor"],
        ["Listas no quadro", overview["total_lists"]],
        ["Cards no export/API", overview["total_cards_raw"]],
        ["Cards metricados", overview["total_cards_metricados"]],
        ["Templates ignorados", overview["total_templates_ignorados"]],
        ["Placeholders/controle ignorados", overview.get("total_placeholders_ignorados", 0)],
        ["Movimentos no historico", overview["total_movements"]],
    ]
    data_quality = metrics.get("data_quality", {})
    if data_quality:
        summary_rows.append(
            [
                "Cards com campos obrigatorios",
                f"{data_quality.get('cards_with_required_fields_pct', 0)}%",
            ]
        )
    story.append(_table(summary_rows, [9 * cm, 4 * cm], styles))

    if metrics.get("ai_analysis") and include("ai"):
        _add_ai_analysis_section(story, metrics, styles)

    if report_type == "management" and include("metric_guide"):
        add_management_guide(story, styles)

    if any(
        include(key) and metrics.get(key if key != "discipline" else "process_discipline")
        for key in ("flow", "risk_board", "priority", "dora", "discipline")
    ) and any(
        metrics.get(key)
        for key in (
            "flow",
            "priority",
            "dora",
            "process_discipline",
            "risk_board",
        )
    ):
        story.append(PageBreak())
        _add_operational_metrics_section(story, metrics, charts, styles)

    fibonacci = metrics.get("fibonacci_points") or {}
    if include("fibonacci") and fibonacci.get("by_developer"):
        story.append(PageBreak())
        _add_fibonacci_section(story, fibonacci, charts, styles)

    if include("collaborators") and metrics.get("collaborators"):
        _add_collaborators_section(story, metrics["collaborators"], charts, styles)

    if include("developers") and metrics.get("developers"):
        story.append(PageBreak())
        story.append(Paragraph("Desenvolvedores", styles["Heading1"]))
        add_table_intro(story, "developers", styles)
        _add_metric_table(
            story,
            [
                "Nome",
                "Cards",
                "Normais",
                "Analise",
                "Pts normais",
                "Pts analise",
                "Tempo dev",
                "Aceitacao",
                "Retrabalho",
                "Pegos no teste",
                "Ret. par",
            ],
            [
                [
                    row["name"],
                    row["cards_delivered"],
                    row.get("cards_delivered_normal", 0),
                    row.get("cards_delivered_analysis", 0),
                    row["fibonacci_normal"],
                    row["fibonacci_analysis"],
                    row["avg_dev_human"],
                    f"{row['acceptance_rate_pct']}%",
                    f"{row.get('rework_rate_pct', 0)}%",
                    row.get("tester_quality_returns", 0),
                    row["peer_review_returns"],
                ]
                for row in metrics["developers"]
            ],
            styles,
        )
        if "dev_points" in charts:
            story.append(Spacer(1, 0.2 * cm))
            story.append(Image(str(charts["dev_points"]), width=16 * cm, height=8 * cm))
        if "dev_flow" in charts:
            story.append(Spacer(1, 0.2 * cm))
            story.append(Image(str(charts["dev_flow"]), width=16 * cm, height=8 * cm))
        if "dev_quality" in charts:
            story.append(Spacer(1, 0.2 * cm))
            story.append(Image(str(charts["dev_quality"]), width=16 * cm, height=8 * cm))
        _add_developer_profiles_section(story, metrics.get("developer_profiles") or [], styles)

    if include("reviewers") and metrics.get("reviewers"):
        story.append(PageBreak())
        story.append(Paragraph("Revisores em par", styles["Heading1"]))
        add_table_intro(story, "reviewers", styles)
        _add_metric_table(
            story,
            ["Nome", "Revisoes", "Aprovadas", "Devolvidas", "Escapes teste", "Taxa aprovacao"],
            [
                [
                    row["name"],
                    row["reviews_done"],
                    row["approved"],
                    row["sent_back"],
                    row.get("escaped_to_test", 0),
                    f"{row['approval_rate_pct']}%",
                ]
                for row in metrics["reviewers"]
            ],
            styles,
        )

    if include("testers") and metrics.get("testers"):
        story.append(PageBreak())
        story.append(Paragraph("Testers / Suporte", styles["Heading1"]))
        add_table_intro(story, "testers", styles)
        _add_metric_table(
            story,
            [
                "Nome",
                "Testes",
                "1a passagem",
                "Problemas evitados",
                "Sem motivo",
                "Retestes",
            ],
            [
                [
                    row["name"],
                    row["cards_tested"],
                    row["approved_first_pass"],
                    row.get("prevented_problems", row.get("returned_dev_for_quality", 0)),
                    row.get("returns_missing_reason", 0),
                    row["retest_cycles_total"],
                ]
                for row in metrics["testers"]
            ],
            styles,
        )
        if "testers" in charts:
            story.append(Spacer(1, 0.2 * cm))
            story.append(Image(str(charts["testers"]), width=16 * cm, height=8 * cm))

    if include("requesters") and metrics.get("requesters"):
        story.append(PageBreak())
        story.append(Paragraph("Solicitantes", styles["Heading1"]))
        add_table_intro(story, "requesters", styles)
        _add_metric_table(
            story,
            ["Nome", "Criados", "Entregues", "Em producao", "Planejamento ok", "Aprovacao media"],
            [
                [
                    row["name"],
                    row["cards_created"],
                    row["cards_delivered"],
                    row["in_production"],
                    f"{row['planning_ok_rate_pct']}%",
                    row.get("avg_approval_human", "-"),
                ]
                for row in metrics["requesters"]
            ],
            styles,
        )

    if include("projects") and metrics.get("projects"):
        story.append(PageBreak())
        story.append(Paragraph("Projetos / Sistemas", styles["Heading1"]))
        add_table_intro(story, "projects", styles)
        _add_metric_table(
            story,
            ["Sistema", "Cards", "Pts normais", "Pts analise", "Top dev"],
            [
                [
                    row["name"],
                    row["cards_delivered"],
                    row["fibonacci_normal"],
                    row["fibonacci_analysis"],
                    row.get("top_developer") or "-",
                ]
                for row in metrics["projects"]
            ],
            styles,
        )
        if "projects" in charts:
            story.append(Spacer(1, 0.2 * cm))
            story.append(Image(str(charts["projects"]), width=16 * cm, height=8 * cm))

    sla = metrics.get("sla", {})
    if include("sla") and sla:
        story.append(PageBreak())
        _add_sla_section(story, sla, charts, styles)

    bottlenecks = metrics.get("bottlenecks", {})
    if include("bottlenecks") and bottlenecks.get("by_stage"):
        story.append(PageBreak())
        story.append(Paragraph("Gargalos", styles["Heading1"]))
        add_table_intro(story, "bottlenecks", styles)
        top = bottlenecks.get("top_bottleneck")
        if top:
            story.append(
                Paragraph(
                    f"Maior gargalo: {_escape(top.get('title'))} "
                    f"({top.get('avg_human', '-')})",
                    styles["BodyText"],
                )
            )
        _add_metric_table(
            story,
            ["Etapa", "Media", "Mediana", "P95", "Amostras"],
            [
                [
                    row["title"],
                    row["avg_human"],
                    human_hours(row["median_hours"]),
                    human_hours(row["p95_hours"]),
                    row["samples"],
                ]
                for row in bottlenecks["by_stage"]
            ],
            styles,
        )
        if "bottlenecks" in charts:
            story.append(Spacer(1, 0.2 * cm))
            story.append(Image(str(charts["bottlenecks"]), width=16 * cm, height=8 * cm))

        if bottlenecks.get("by_sistema"):
            story.append(Spacer(1, 0.3 * cm))
            story.append(Paragraph("Gargalo por sistema/projeto", styles["Heading2"]))
            _add_metric_table(
                story,
                ["Sistema", "Media de espera", "Amostras"],
                [
                    [row["sistema"], row["avg_human"], row["samples"]]
                    for row in bottlenecks["by_sistema"]
                ],
                styles,
            )

        management_view = bottlenecks.get("management_only_view") or {}
        if any(management_view.values()):
            story.append(Spacer(1, 0.3 * cm))
            story.append(Paragraph("Controle de gestao (por projeto)", styles["Heading2"]))
            story.append(
                Paragraph(
                    "Visao apenas gerencial: mostra em qual lista especifica por "
                    "projeto/canal os cards estao. Nao impacta as metricas de gargalo, "
                    "que ja usam o estagio fundido (Aguardando teste / Aguardando producao).",
                    styles["Muted"],
                )
            )
            for group_title, rows in (
                ("Aguardando teste", management_view.get("waiting_test", [])),
                ("Aguardando producao", management_view.get("waiting_production", [])),
            ):
                if not rows:
                    continue
                story.append(Spacer(1, 0.15 * cm))
                _add_metric_table(
                    story,
                    [group_title, "Cards agora"],
                    [[row["list"], row["count"]] for row in rows],
                    styles,
                )

    quality_gates = metrics.get("quality_gates", {})
    if include("quality_gates") and quality_gates:
        story.append(PageBreak())
        story.append(Paragraph("Conformidade de dupla revisao", styles["Heading1"]))
        story.append(
            Paragraph(
                "Regra: cards nivel 8/13 exigem revisao em par + revisao formal "
                "(dupla revisao) antes da entrega. Nivel 5 e recomendado, mas nao "
                "obrigatorio.",
                styles["BodyText"],
            )
        )
        story.append(Spacer(1, 0.2 * cm))
        story.append(
            _table(
                [
                    ["Indicador", "Valor"],
                    ["Cards nivel 8/13 (obrigatorio)", quality_gates.get("mandatory_total", 0)],
                    [
                        "Violacoes (sem dupla revisao)",
                        quality_gates.get("mandatory_violations_count", 0),
                    ],
                    [
                        "Conformidade obrigatoria",
                        f"{quality_gates.get('mandatory_compliance_pct', 0)}%",
                    ],
                    ["Cards nivel 5 (recomendado)", quality_gates.get("recommended_total", 0)],
                    [
                        "Fizeram dupla revisao (informativo)",
                        f"{quality_gates.get('recommended_done_pct', 0)}%",
                    ],
                ],
                [9 * cm, 4 * cm],
                styles,
            )
        )
        violations = quality_gates.get("mandatory_violations") or []
        if violations:
            story.append(Spacer(1, 0.3 * cm))
            story.append(Paragraph("Cards nivel 8/13 sem dupla revisao", styles["Heading2"]))
            _add_metric_table(
                story,
                ["Card", "Desenvolvedor", "Sistema", "Nivel", "Passou par?", "Passou formal?"],
                [
                    [
                        row["card_name"],
                        row["desenvolvedor"],
                        row["sistema"],
                        row["fibonacci_level"],
                        "Sim" if row["passed_peer_review"] else "Nao",
                        "Sim" if row["passed_formal_review"] else "Nao",
                    ]
                    for row in violations
                ],
                styles,
            )

    trends = metrics.get("trends_6m")
    if include("trends") and trends:
        story.append(PageBreak())
        story.append(Paragraph("Tendencia 6 meses", styles["Heading1"]))
        if "trends_team" in charts:
            story.append(Image(str(charts["trends_team"]), width=16 * cm, height=8 * cm))
        if "trends_quality" in charts:
            story.append(Spacer(1, 0.2 * cm))
            story.append(Image(str(charts["trends_quality"]), width=16 * cm, height=8 * cm))
        if "trends_devs" in charts:
            story.append(Spacer(1, 0.2 * cm))
            story.append(Image(str(charts["trends_devs"]), width=16 * cm, height=8 * cm))

    movements = metrics.get("movements", {})
    if include("movements") and movements:
        story.append(PageBreak())
        story.append(Paragraph("Detalhes operacionais", styles["Heading1"]))
        _add_counter_section(story, "Cards por etapa atual", overview["cards_by_current_group"], styles)
        _add_counter_section(story, "Entradas por etapa", movements.get("target_groups", []), styles)

        story.append(Paragraph("Tempo por coluna", styles["Heading2"]))
        time_rows = [["Coluna", "Total", "Media", "Entradas"]]
        for row in movements.get("time_by_list", [])[:20]:
            time_rows.append(
                [
                    Paragraph(_escape(row["list"]), styles["Small"]),
                    human_hours(row["total_hours"]),
                    row["avg_human"],
                    row["spans"],
                ]
            )
        story.append(_table(time_rows, [8 * cm, 3 * cm, 3 * cm, 2 * cm], styles))

    card_dossier = metrics.get("card_dossier")
    if include("dossier") and card_dossier:
        _add_card_dossier_appendix(story, card_dossier, styles)

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return output


def _add_team_summary(
    story: list[Any],
    team: dict[str, Any],
    bottlenecks: dict[str, Any],
    styles: Any,
) -> None:
    from reportlab.lib.units import cm
    from reportlab.platypus import Spacer

    top = bottlenecks.get("top_bottleneck") or {}
    rows = [
        ["Indicador", "Valor"],
        ["Cards entregues", team.get("cards_delivered", 0)],
        ["Pontos normais", team.get("fibonacci_normal", 0)],
        ["Pontos analise", team.get("fibonacci_analysis", 0)],
        ["Taxa aceitacao", f"{team.get('acceptance_rate_pct', 0)}%"],
        ["Retorno DEV penalizado", f"{team.get('return_dev_rate_pct', 0)}%"],
        ["Problemas evitados pelo teste", team.get("total_prevented_problems", team.get("total_tester_quality_returns", 0))],
        ["Retornos de teste sem motivo", team.get("test_returns_missing_reason_count", 0)],
        ["Maior gargalo", top.get("title", "-")],
        ["Cards que voltaram (retrabalho)", team.get("cards_with_rework_count", 0)],
        ["Taxa de retrabalho", f"{team.get('rework_rate_pct', 0)}%"],
        ["Taxa de qualidade de entrega", f"{team.get('quality_rate_pct', 0)}%"],
        ["Selo de qualidade do mes", team.get("quality_seal", "-")],
    ]
    story.append(_table(rows, [7 * cm, 6 * cm], styles))
    story.append(Spacer(1, 0.3 * cm))


def _add_ai_analysis_section(
    story: list[Any],
    metrics: dict[str, Any],
    styles: Any,
) -> None:
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, Spacer

    ai = metrics.get("ai") or {}
    provider = ai.get("provider") or "IA"
    model = ai.get("model") or "-"
    story.append(Spacer(1, 0.35 * cm))
    story.append(Paragraph("Analise gerada por IA", styles["Heading1"]))
    story.append(Paragraph(_escape(f"{provider} | {model}"), styles["Muted"]))
    story.append(Spacer(1, 0.15 * cm))
    for raw_line in str(metrics.get("ai_analysis", "")).splitlines():
        line = raw_line.strip()
        if not line:
            story.append(Spacer(1, 0.08 * cm))
            continue
        if line.startswith("#"):
            story.append(Paragraph(_escape(line.lstrip("# ")), styles["Heading2"]))
        elif line.startswith(("-", "*")):
            story.append(Paragraph(f"&raquo; {_escape(line.lstrip('-* '))}", styles["BodyText"]))
        else:
            story.append(Paragraph(_escape(line), styles["BodyText"]))


def _add_operational_metrics_section(
    story: list[Any],
    metrics: dict[str, Any],
    charts: dict[str, Any],
    styles: Any,
) -> None:
    from reportlab.lib.units import cm
    from reportlab.platypus import Image, Paragraph, Spacer

    story.append(Paragraph("Fluxo, prioridade, DORA e risco", styles["Heading1"]))
    add_section_guide(story, "flow", styles)

    flow = metrics.get("flow") or {}
    if flow:
        if "cfd" in charts:
            story.append(Image(str(charts["cfd"]), width=16 * cm, height=8 * cm))
            story.append(Spacer(1, 0.15 * cm))
        if "stage_time" in charts:
            story.append(Image(str(charts["stage_time"]), width=16 * cm, height=8 * cm))
            story.append(Spacer(1, 0.15 * cm))
        team = flow.get("team") or {}
        efficiency = team.get("flow_efficiency") or {}
        little = team.get("little_law") or {}
        story.append(Paragraph("Fluxo do time", styles["Heading2"]))
        story.append(
            _table(
                [
                    ["Indicador", "Valor"],
                    ["Lead time med/P85/P95", _stats_triplet(team.get("lead_time"))],
                    ["Cycle time med/P85/P95", _stats_triplet(team.get("cycle_time"))],
                    [
                        "Planejamento ate aprovacao",
                        _stats_triplet(team.get("planning_to_approval_time")),
                    ],
                    ["Eficiencia de fluxo", f"{efficiency.get('efficiency_pct', 0)}%"],
                    ["Tempo em fila", efficiency.get("wait_human", "-")],
                    ["Tempo em trabalho", efficiency.get("work_human", "-")],
                    ["WIP atual", team.get("wip_total", 0)],
                    [
                        "Lei de Little",
                        f"{little.get('predicted_lead_time_days', '-')} dias previstos",
                    ],
                ],
                [8 * cm, 7 * cm],
                styles,
            )
        )
        wip_rows = flow.get("wip_by_stage") or []
        if wip_rows:
            story.append(Spacer(1, 0.15 * cm))
            story.append(Paragraph("WIP atual por etapa", styles["Heading3"]))
            _add_metric_table(
                story,
                ["WIP por etapa", "Cards"],
                [[row.get("title", "-"), row.get("count", 0)] for row in wip_rows[:10]],
                styles,
            )
        stage_rows = flow.get("stage_time") or []
        if stage_rows:
            story.append(Spacer(1, 0.15 * cm))
            story.append(Paragraph("Tempo por etapa do fluxo", styles["Heading3"]))
            _add_metric_table(
                story,
                ["Etapa", "Mediana", "P85", "P95", "Amostras"],
                [
                    [
                        row.get("title", "-"),
                        row.get("median_human", "-"),
                        row.get("p85_human", "-"),
                        row.get("p95_human", "-"),
                        row.get("samples", 0),
                    ]
                    for row in stage_rows[:12]
                ],
                styles,
            )
        aging_rows = flow.get("aging_wip") or []
        if aging_rows:
            story.append(Spacer(1, 0.15 * cm))
            story.append(Paragraph("Aging WIP vs P50/P85 historico", styles["Heading3"]))
            _add_metric_table(
                story,
                ["Card", "Etapa", "Idade", "P50", "P85", "Status"],
                [
                    [
                        row.get("card_name", "-"),
                        row.get("title") or row.get("list_name", "-"),
                        row.get("age_human", "-"),
                        row.get("p50_human", "-"),
                        row.get("p85_human", "-"),
                        _aging_status_label(row.get("status")),
                    ]
                    for row in aging_rows[:15]
                ],
                styles,
            )
        cfd_rows = _cfd_rows_for_pdf(flow.get("cfd") or [])
        if cfd_rows:
            story.append(Spacer(1, 0.15 * cm))
            story.append(Paragraph("CFD - ultimos snapshots", styles["Heading3"]))
            _add_metric_table(
                story,
                ["Data", "Total", "Distribuicao por etapa"],
                cfd_rows,
                styles,
            )

    risk = metrics.get("risk_board") or {}
    attention = risk.get("cards_that_need_attention") or []
    if risk:
        story.append(Spacer(1, 0.25 * cm))
        story.append(Paragraph("Cards que merecem atencao agora", styles["Heading2"]))
        story.append(
            Paragraph(
                f"Cards em risco alto/critico: {risk.get('high_or_critical_count', 0)}",
                styles["BodyText"],
            )
        )
        if attention:
            _add_metric_table(
                story,
                ["Card", "Etapa", "Idade", "Prioridade", "Risco", "Motivos"],
                [
                    [
                        row.get("card_name", "-"),
                        row.get("current_stage", "-"),
                        row.get("age_human", "-"),
                        row.get("prioridade", "-"),
                        row.get("level", "-"),
                        "; ".join(row.get("reasons") or []),
                    ]
                    for row in attention[:10]
                ],
                styles,
            )
        else:
            story.append(Paragraph("Nenhum card alto/critico no momento.", styles["Muted"]))

    priority = metrics.get("priority") or {}
    if priority:
        story.append(Spacer(1, 0.25 * cm))
        story.append(Paragraph("Prioridade", styles["Heading2"]))
        story.append(
            _table(
                [
                    ["Indicador", "Valor"],
                    ["Urgente/Critica no periodo", f"{priority.get('urgent_critical_pct', 0)}%"],
                    [
                        "Alerta de inflacao",
                        "Sim" if priority.get("priority_inflation_alert") else "Nao",
                    ],
                    ["Furos de fila", priority.get("queue_jumps_count", 0)],
                    ["Urgentes envelhecendo", priority.get("urgent_aging_count", 0)],
                ],
                [8 * cm, 7 * cm],
                styles,
            )
        )
        lead_by_priority = priority.get("lead_time_by_priority") or []
        if lead_by_priority:
            story.append(Spacer(1, 0.15 * cm))
            story.append(Paragraph("Lead time por prioridade", styles["Heading3"]))
            _add_metric_table(
                story,
                ["Prioridade", "Mediana", "P85", "P95", "Amostras"],
                [
                    [
                        row.get("priority", "-"),
                        row.get("median_human", "-"),
                        row.get("p85_human", "-"),
                        row.get("p95_human", "-"),
                        row.get("samples", 0),
                    ]
                    for row in lead_by_priority
                ],
                styles,
            )
        distribution = priority.get("distribution") or []
        if distribution:
            story.append(Spacer(1, 0.15 * cm))
            story.append(Paragraph("Distribuicao de prioridades", styles["Heading3"]))
            _add_metric_table(
                story,
                ["Prioridade", "Cards"],
                [[row.get("priority", "-"), row.get("count", 0)] for row in distribution],
                styles,
            )
        queue_jumps = priority.get("queue_jumps") or []
        if queue_jumps:
            story.append(Spacer(1, 0.15 * cm))
            story.append(Paragraph("Furos de fila", styles["Heading3"]))
            _add_metric_table(
                story,
                ["Entregue antes", "Prioridade", "Maior prioridade aguardou", "Prioridade"],
                [
                    [
                        (item.get("delivered_first") or {}).get("card_name", "-"),
                        (item.get("delivered_first") or {}).get("priority", "-"),
                        (item.get("higher_priority_waited") or {}).get("card_name", "-"),
                        (item.get("higher_priority_waited") or {}).get("priority", "-"),
                    ]
                    for item in queue_jumps[:12]
                ],
                styles,
            )
        urgent_aging = priority.get("urgent_aging") or []
        if urgent_aging:
            story.append(Spacer(1, 0.15 * cm))
            story.append(Paragraph("Urgentes/Criticas envelhecendo", styles["Heading3"]))
            _add_metric_table(
                story,
                ["Card", "Etapa", "Idade", "Status"],
                [
                    [
                        row.get("card_name", "-"),
                        row.get("title", "-"),
                        row.get("age_human", "-"),
                        _aging_status_label(row.get("status")),
                    ]
                    for row in urgent_aging[:12]
                ],
                styles,
            )

    dora = metrics.get("dora") or {}
    if dora:
        deploy = dora.get("deployment_frequency") or {}
        failure = dora.get("change_failure_rate") or {}
        story.append(Spacer(1, 0.25 * cm))
        story.append(Paragraph("DORA adaptado", styles["Heading2"]))
        story.append(
            _table(
                [
                    ["Indicador", "Valor"],
                    ["Frequencia de deploy", deploy.get("total", 0)],
                    ["Lead time de deploy med/P85/P95", _stats_triplet(dora.get("lead_time_deploy"))],
                    ["Change failure rate", f"{failure.get('rate_pct', 0)}%"],
                    ["Deploys com falha", failure.get("failed_deployments", 0)],
                    ["Time to restore med/P85/P95", _stats_triplet(dora.get("time_to_restore"))],
                ],
                [8 * cm, 7 * cm],
                styles,
            )
        )
        by_week = deploy.get("by_week") or {}
        if by_week:
            story.append(Spacer(1, 0.15 * cm))
            story.append(Paragraph("Deploys por semana", styles["Heading3"]))
            _add_metric_table(
                story,
                ["Semana", "Deploys"],
                [[week, count] for week, count in sorted(by_week.items())],
                styles,
            )
        by_system = deploy.get("by_system") or []
        if by_system:
            story.append(Spacer(1, 0.15 * cm))
            story.append(Paragraph("Deploys por sistema", styles["Heading3"]))
            _add_metric_table(
                story,
                ["Sistema", "Deploys"],
                [[row.get("sistema", "-"), row.get("count", 0)] for row in by_system[:12]],
                styles,
            )
        failures = failure.get("failures") or []
        if failures:
            story.append(Spacer(1, 0.15 * cm))
            story.append(Paragraph("Change failures detectados", styles["Heading3"]))
            _add_metric_table(
                story,
                ["Deploy", "Sistema", "Correcao subsequente", "Criada em"],
                [
                    [
                        row.get("deployment_card_name", "-"),
                        row.get("sistema", "-"),
                        row.get("correction_card_name", "-"),
                        row.get("correction_created_at", "-"),
                    ]
                    for row in failures[:12]
                ],
                styles,
            )

    discipline = metrics.get("process_discipline") or {}
    if discipline:
        conformity = discipline.get("flow_conformity") or {}
        assignment = discipline.get("developer_assignment_latency") or {}
        without_level = discipline.get("cards_without_level") or []
        story.append(Spacer(1, 0.25 * cm))
        story.append(Paragraph("Disciplina de processo", styles["Heading2"]))
        add_section_guide(story, "process_discipline", styles)
        add_table_intro(story, "process_discipline", styles)
        story.append(
            _table(
                [
                    ["Indicador", "Valor"],
                    ["Conformidade do fluxo", f"{conformity.get('compliance_pct', 0)}%"],
                    ["Cards avaliados", conformity.get("cards_evaluated", 0)],
                    ["Violacoes", len(conformity.get("violations") or [])],
                    ["Cards sem nivel", len(without_level)],
                    ["Latencia para atribuir dev", _stats_triplet(assignment)],
                    ["Eventos de campo historicos", assignment.get("history_events", 0)],
                ],
                [8 * cm, 7 * cm],
                styles,
            )
        )
        required_rows = discipline.get("required_fields_by_stage") or []
        if required_rows:
            story.append(Spacer(1, 0.15 * cm))
            story.append(Paragraph("Campos obrigatorios por etapa", styles["Heading3"]))
            _add_metric_table(
                story,
                ["Etapa", "Completude", "Cards", "Pendencias"],
                [
                    [
                        row.get("title", "-"),
                        f"{row.get('completion_pct', 0)}%",
                        row.get("cards_evaluated", 0),
                        len(row.get("missing") or []),
                    ]
                    for row in required_rows
                ],
                styles,
            )
        skipped = discipline.get("skipped_stages") or []
        if skipped:
            story.append(Spacer(1, 0.15 * cm))
            story.append(Paragraph("Etapas puladas", styles["Heading3"]))
            _add_metric_table(
                story,
                ["Etapa", "Tipo", "Cards"],
                [
                    [
                        row.get("title", "-"),
                        "Opcional" if row.get("optional") else "Core",
                        row.get("count", 0),
                    ]
                    for row in skipped[:12]
                ],
                styles,
            )
        if without_level:
            story.append(Spacer(1, 0.15 * cm))
            story.append(Paragraph("Cards sem nivel", styles["Heading3"]))
            _add_metric_table(
                story,
                ["Card", "Dev", "Sistema"],
                [
                    [
                        row.get("card_name", "-"),
                        row.get("desenvolvedor", "-"),
                        row.get("sistema", "-"),
                    ]
                    for row in without_level[:12]
                ],
                styles,
            )
        assignment_cards = assignment.get("cards") or []
        if assignment_cards:
            story.append(Spacer(1, 0.15 * cm))
            story.append(Paragraph("Latencia ate atribuir desenvolvedor", styles["Heading3"]))
            _add_metric_table(
                story,
                ["Card", "Dev", "Criado em", "Atribuido em", "Horas"],
                [
                    [
                        row.get("card_name", "-"),
                        row.get("developer", "-"),
                        row.get("created_at", "-"),
                        row.get("assigned_at", "-"),
                        row.get("latency_hours", 0),
                    ]
                    for row in assignment_cards[:12]
                ],
                styles,
            )
        violations = conformity.get("violations") or []
        if violations:
            story.append(Spacer(1, 0.15 * cm))
            story.append(Paragraph("Violacoes do fluxo canonico", styles["Heading3"]))
            _add_metric_table(
                story,
                ["Card", "Problemas"],
                [
                    [
                        row.get("card_name", "-"),
                        "; ".join(row.get("issues") or []),
                    ]
                    for row in violations[:12]
                ],
                styles,
            )


def _add_sla_section(
    story: list[Any],
    sla: dict[str, Any],
    charts: dict[str, Any],
    styles: Any,
) -> None:
    from reportlab.lib.units import cm
    from reportlab.platypus import Image, Paragraph, Spacer

    team = sla.get("team") or {}
    policy = sla.get("policy") or {}
    story.append(Paragraph("SLA", styles["Heading1"]))
    add_section_guide(story, "sla", styles)
    add_table_intro(story, "sla_team", styles)
    if policy.get("note"):
        story.append(Paragraph(_escape(policy["note"]), styles["Muted"]))
        story.append(Spacer(1, 0.15 * cm))

    story.append(
        _table(
            [
                ["Indicador", "Valor"],
                ["Cards avaliados", team.get("cards_evaluated", 0)],
                ["Etapas avaliadas", team.get("stage_checks", 0)],
                ["Etapas estouradas", team.get("breached_count", 0)],
                ["Cumprimento SLA", f"{team.get('compliance_pct', 0)}%"],
                ["Em risco agora", team.get("current_at_risk_count", 0)],
                ["Estouradas agora", team.get("current_breached_count", 0)],
            ],
            [8 * cm, 5 * cm],
            styles,
        )
    )

    if "sla_stage" in charts:
        story.append(Spacer(1, 0.25 * cm))
        story.append(Image(str(charts["sla_stage"]), width=16 * cm, height=8 * cm))

    by_stage = sla.get("by_stage") or []
    if by_stage:
        story.append(Spacer(1, 0.25 * cm))
        story.append(Paragraph("SLA por etapa", styles["Heading2"]))
        add_table_intro(story, "sla_by_stage", styles)
        _add_metric_table(
            story,
            ["Etapa", "SLA", "Avaliadas", "Estouradas", "Cumprimento", "Media usada"],
            [
                [
                    row.get("title", "-"),
                    row.get("sla_human", "-"),
                    row.get("checks", 0),
                    row.get("breached_count", 0),
                    f"{row.get('compliance_pct', 0)}%",
                    row.get("avg_elapsed_human", "-"),
                ]
                for row in by_stage
            ],
            styles,
        )

    by_developer = sla.get("by_developer") or []
    if by_developer:
        story.append(Spacer(1, 0.25 * cm))
        story.append(Paragraph("SLA por desenvolvedor", styles["Heading2"]))
        add_table_intro(story, "sla_developers", styles)
        _add_metric_table(
            story,
            ["Desenvolvedor", "Cards", "Etapas", "Estouradas", "Cards c/ estouro", "Cumprimento"],
            [
                [
                    row.get("name", "-"),
                    row.get("cards_evaluated", 0),
                    row.get("stage_checks", 0),
                    row.get("breached_count", 0),
                    row.get("breached_cards", 0),
                    f"{row.get('compliance_pct', 0)}%",
                ]
                for row in by_developer
            ],
            styles,
        )

    cards = sla.get("cards") or []
    if cards:
        story.append(Spacer(1, 0.25 * cm))
        story.append(Paragraph("SLA por card", styles["Heading2"]))
        _add_metric_table(
            story,
            ["Card", "Dev", "Nivel", "Pior etapa", "Uso max.", "Etapas", "Estouradas", "Cumprimento"],
            [
                [
                    row.get("card_name", "-"),
                    row.get("desenvolvedor", "-"),
                    row.get("fibonacci_level", "-"),
                    row.get("worst_stage", "-"),
                    f"{row.get('worst_usage_pct', 0)}%",
                    row.get("stage_checks", 0),
                    row.get("breached_count", 0),
                    f"{row.get('compliance_pct', 0)}%",
                ]
                for row in cards
            ],
            styles,
        )

    alerts = sla.get("current_alerts") or []
    if alerts:
        story.append(Spacer(1, 0.25 * cm))
        story.append(Paragraph("Cards com alerta de SLA na etapa atual", styles["Heading2"]))
        _add_metric_table(
            story,
            ["Card", "Etapa", "Uso", "SLA", "Status"],
            [
                [
                    row.get("card_name", "-"),
                    row.get("title", row.get("current_list", "-")),
                    f"{row.get('elapsed_human', '-')} ({row.get('usage_pct', 0)}%)",
                    row.get("limit_human", "-"),
                    row.get("status", "-"),
                ]
                for row in alerts
            ],
            styles,
        )


def _add_collaborators_section(
    story: list[Any],
    collaborators: list[dict[str, Any]],
    charts: dict[str, Any],
    styles: Any,
) -> None:
    from reportlab.lib.units import cm
    from reportlab.platypus import Image, PageBreak, Paragraph, Spacer

    story.append(PageBreak())
    story.append(Paragraph("Colaboradores", styles["Heading1"]))
    add_table_intro(story, "collaborators", styles)
    story.append(
        Paragraph(
            "Visao individual consolidada por nome base, juntando solicitante, "
            "desenvolvedor, revisor em par, revisor e tester quando forem a mesma pessoa.",
            styles["Muted"],
        )
    )
    story.append(Spacer(1, 0.2 * cm))
    if "collab_points" in charts:
        story.append(Image(str(charts["collab_points"]), width=16 * cm, height=8 * cm))
        story.append(Spacer(1, 0.15 * cm))
    if "collab_time" in charts:
        story.append(Image(str(charts["collab_time"]), width=16 * cm, height=8 * cm))
        story.append(Spacer(1, 0.15 * cm))
    _add_metric_table(
        story,
        ["Nome", "Papeis", "Ativos", "Entregues", "Pontos", "Tempo"],
        [
            [
                row["name"],
                ", ".join(row.get("roles", [])) or "-",
                row.get("summary", {}).get("cards_active", 0),
                row.get("summary", {}).get("cards_delivered", 0),
                row.get("summary", {}).get("fibonacci_total", 0),
                row.get("summary", {}).get("time_human", "-"),
            ]
            for row in collaborators
        ],
        styles,
    )

    for collaborator in collaborators:
        summary = collaborator.get("summary", {})
        story.append(PageBreak())
        story.append(Paragraph(f"Relatorio individual - {_escape(collaborator.get('name'))}", styles["Heading1"]))
        story.append(
            Paragraph(
                _escape(", ".join(collaborator.get("roles", [])) or "-"),
                styles["Muted"],
            )
        )
        story.append(Spacer(1, 0.15 * cm))
        story.append(
            _table(
                [
                    ["Indicador", "Valor"],
                    ["Cards ativos", summary.get("cards_active", 0)],
                    ["Cards entregues", summary.get("cards_delivered", 0)],
                    ["Cards criados", summary.get("cards_created", 0)],
                    ["Pontos normais", summary.get("fibonacci_normal", 0)],
                    ["Pontos analise", summary.get("fibonacci_analysis", 0)],
                    ["Tempo de atuacao", summary.get("time_human", "-")],
                    ["Identificadores", ", ".join(collaborator.get("aliases", [])) or "-"],
                ],
                [6 * cm, 9 * cm],
                styles,
            )
        )

        process_times = collaborator.get("process_times") or []
        if process_times:
            story.append(Spacer(1, 0.25 * cm))
            story.append(Paragraph("Tempo por processo", styles["Heading2"]))
            story.append(
                _table(
                    [["Processo", "Total", "Media", "Visitas", "Cards"]]
                    + [
                        [
                            Paragraph(_escape(row.get("title", "-")), styles["Small"]),
                            row.get("total_human", "-"),
                            row.get("avg_human", "-"),
                            row.get("visits", 0),
                            row.get("cards", 0),
                        ]
                        for row in process_times
                    ],
                    [5.8 * cm, 2.6 * cm, 2.6 * cm, 2 * cm, 2 * cm],
                    styles,
                )
            )

        role_metrics = collaborator.get("role_metrics") or []
        if role_metrics:
            story.append(Spacer(1, 0.25 * cm))
            story.append(Paragraph("Papeis no periodo", styles["Heading2"]))
            _add_metric_table(
                story,
                ["Papel", "Ativos", "Entregues", "Pontos", "Tempo", "Media"],
                [
                    [
                        role.get("role_label", "-"),
                        role.get("cards_active", 0),
                        role.get("cards_delivered", 0),
                        role.get("fibonacci_total", 0),
                        role.get("time_human", "-"),
                        role.get("avg_time_human", "-"),
                    ]
                    for role in role_metrics
                ],
                styles,
            )

        cards = collaborator.get("cards") or []
        if cards:
            story.append(Spacer(1, 0.25 * cm))
            story.append(Paragraph("Cards", styles["Heading2"]))
            for card in cards:
                _render_card_block(story, card, styles)


def _add_role_summary_section(
    story: list[Any],
    summary: dict[str, Any],
    styles: Any,
) -> None:
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, Spacer

    scope = summary.get("scope", "role")
    titles = {
        "developers": "Resumo de desenvolvedores",
        "requesters": "Resumo de solicitantes",
        "testers": "Resumo de testers",
        "specific_metrics": "Metricas selecionadas",
    }
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(titles.get(scope, "Resumo do relatorio"), styles["Heading2"]))
    rows = [["Indicador", "Valor"]]
    for key, value in summary.items():
        if key == "scope":
            continue
        if isinstance(value, list):
            value = ", ".join(str(item) for item in value)
        rows.append([metric_label(key), value])
    story.append(_table(rows, [8 * cm, 7 * cm], styles))
    story.append(Spacer(1, 0.25 * cm))


def _add_individual_summary_section(
    story: list[Any],
    metrics: dict[str, Any],
    styles: Any,
) -> None:
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, Spacer

    summary = metrics.get("individual_summary") or {}
    target = metrics.get("individual_target") or summary.get("name", "")
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(f"Colaborador: {_escape(target)}", styles["Heading1"]))
    story.append(
        Paragraph(_escape(", ".join(summary.get("roles") or []) or "-"), styles["Muted"])
    )
    story.append(Spacer(1, 0.15 * cm))
    story.append(
        _table(
            [
                ["Indicador", "Valor"],
                ["Cards ativos", summary.get("cards_active", 0)],
                ["Cards criados", summary.get("cards_created", 0)],
                ["Cards entregues", summary.get("cards_delivered", 0)],
                ["Pontos normais", summary.get("fibonacci_normal", 0)],
                ["Pontos analise", summary.get("fibonacci_analysis", 0)],
                ["Tempo de atuacao", summary.get("time_human", "-")],
            ],
            [7 * cm, 6 * cm],
            styles,
        )
    )

    role_metrics = metrics.get("role_metrics") or []
    if role_metrics:
        story.append(Spacer(1, 0.25 * cm))
        story.append(Paragraph("Metricas por papel", styles["Heading2"]))
        add_table_intro(story, "collaborators", styles)
        _add_metric_table(
            story,
            ["Papel", "Ativos", "Entregues", "Pontos", "Tempo", "Media"],
            [
                [
                    role.get("role_label", "-"),
                    role.get("cards_active", 0),
                    role.get("cards_delivered", 0),
                    role.get("fibonacci_total", 0),
                    role.get("time_human", "-"),
                    role.get("avg_time_human", "-"),
                ]
                for role in role_metrics
            ],
            styles,
        )

    collaborators = metrics.get("collaborators") or []
    if len(collaborators) == 1:
        process_times = collaborators[0].get("process_times") or []
        if process_times:
            story.append(Spacer(1, 0.25 * cm))
            story.append(Paragraph("Tempo por processo", styles["Heading2"]))
            story.append(
                _table(
                    [["Processo", "Total", "Media", "Visitas", "Cards"]]
                    + [
                        [
                            Paragraph(_escape(row.get("title", "-")), styles["Small"]),
                            row.get("total_human", "-"),
                            row.get("avg_human", "-"),
                            row.get("visits", 0),
                            row.get("cards", 0),
                        ]
                        for row in process_times
                    ],
                    [5.8 * cm, 2.6 * cm, 2.6 * cm, 2 * cm, 2 * cm],
                    styles,
                )
            )


def _add_fibonacci_section(
    story: list[Any],
    fibonacci: dict[str, Any],
    charts: dict[str, Any],
    styles: Any,
) -> None:
    from reportlab.lib.units import cm
    from reportlab.platypus import Image, Paragraph, Spacer

    team = fibonacci.get("team") or {}
    rows = fibonacci.get("by_developer") or []
    story.append(Paragraph("Pontos Fibonacci", styles["Heading1"]))
    if fibonacci.get("policy"):
        story.append(Paragraph(_escape(fibonacci["policy"]), styles["Muted"]))
    story.append(Spacer(1, 0.15 * cm))
    story.append(
        _table(
            [
                ["Indicador", "Valor"],
                ["Cards normais", team.get("cards_normal", 0)],
                ["Pontos normais", team.get("points_normal", 0)],
                ["Cards analise", team.get("cards_analysis", 0)],
                ["Pontos analise", team.get("points_analysis", 0)],
                ["Total equipe", team.get("points_total", 0)],
            ],
            [8 * cm, 7 * cm],
            styles,
        )
    )
    if "fibonacci" in charts:
        story.append(Spacer(1, 0.2 * cm))
        story.append(Image(str(charts["fibonacci"]), width=16 * cm, height=8 * cm))
    story.append(Spacer(1, 0.2 * cm))
    _add_metric_table(
        story,
        ["Desenvolvedor", "Cards normais", "Pts normais", "Cards analise", "Pts analise", "Total"],
        [
            [
                row.get("developer", "-"),
                row.get("cards_normal", 0),
                row.get("points_normal", 0),
                row.get("cards_analysis", 0),
                row.get("points_analysis", 0),
                row.get("points_total", 0),
            ]
            for row in rows
        ],
        styles,
    )


def _add_developer_profiles_section(
    story: list[Any],
    profiles: list[dict[str, Any]],
    styles: Any,
) -> None:
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, Spacer

    if not profiles:
        return

    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("Perfis detalhados por desenvolvedor", styles["Heading2"]))
    for dev in profiles:
        cards = dev.get("cards") or []
        if not cards:
            continue
        story.append(Spacer(1, 0.2 * cm))
        story.append(Paragraph(_escape(dev.get("name", "-")), styles["Heading3"]))
        story.append(
            Paragraph(
                _escape(
                    f"{dev.get('cards_delivered', 0)} entrega(s) · "
                    f"{dev.get('fibonacci_total', 0)} pts · "
                    f"atuacao {dev.get('dev_work_hours_human', '-')} · "
                    f"espera {dev.get('pipeline_wait_hours_human', '-')}"
                ),
                styles["Muted"],
            )
        )
        _add_metric_table(
            story,
            ["Card", "Sistema", "Nivel", "Atuacao", "Espera", "% espera", "Ciclo"],
            [
                [
                    card.get("card_name", "-"),
                    card.get("sistema", "-"),
                    card.get("fibonacci_level", "-"),
                    card.get("dev_work_human", "-"),
                    card.get("pipeline_wait_human", "-"),
                    f"{card.get('pipeline_wait_ratio_pct', 0)}%",
                    card.get("cycle_time_human", "-"),
                ]
                for card in cards
            ],
            styles,
        )


def _add_metric_table(
    story: list[Any],
    headers: list[str],
    rows: list[list[Any]],
    styles: Any,
) -> None:
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph

    table_rows = [headers]
    for row in rows:
        table_rows.append([Paragraph(_escape(value), styles["Small"]) for value in row])
    widths = [13 * cm / len(headers)] * len(headers)
    story.append(_table(table_rows, widths, styles))


def _add_counter_section(
    story: list[Any],
    title: str,
    rows: list[dict[str, Any]],
    styles: Any,
) -> None:
    from reportlab.platypus import Paragraph, Spacer
    from reportlab.lib.units import cm

    story.append(Spacer(1, 0.25 * cm))
    story.append(Paragraph(_escape(title), styles["Heading2"]))
    if not rows:
        story.append(Paragraph("Sem dados.", styles["BodyText"]))
        return
    table_rows = [["Nome", "Total"]]
    for row in rows:
        table_rows.append([Paragraph(_escape(row["name"]), styles["Small"]), row["count"]])
    story.append(_table(table_rows, [11 * cm, 3 * cm], styles))


def _add_card_dossier_appendix(
    story: list[Any],
    dossier: dict[str, Any],
    styles: Any,
) -> None:
    from reportlab.lib.units import cm
    from reportlab.platypus import PageBreak, Paragraph, Spacer

    story.append(PageBreak())
    story.append(Paragraph("Detalhamento de cards", styles["Heading1"]))
    story.append(
        Paragraph(
            "Apendice descritivo com o historico de cada card com atividade no mes: "
            "motivos de retorno (dev/sup), solucoes registradas, pausas e conformidade "
            "de dupla revisao. Agrupado por desenvolvedor (tarefas normais e cards de "
            "analise separados), por solicitante e por tester. O casamento entre o "
            "texto do retorno e o movimento real e uma heuristica por ordem cronologica.",
            styles["Muted"],
        )
    )

    by_developer = dossier.get("by_developer") or {}
    if by_developer:
        story.append(Spacer(1, 0.3 * cm))
        story.append(Paragraph("Por desenvolvedor", styles["Heading2"]))
        for name, buckets in by_developer.items():
            story.append(Spacer(1, 0.25 * cm))
            story.append(Paragraph(_escape(name), styles["Heading3"]))
            if buckets.get("tarefas_normais"):
                story.append(Paragraph("Tarefas normais", styles["Heading4"]))
                for card in buckets["tarefas_normais"]:
                    _render_card_block(story, card, styles)
            if buckets.get("cards_analise"):
                story.append(Paragraph("Cards de analise", styles["Heading4"]))
                for card in buckets["cards_analise"]:
                    _render_card_block(story, card, styles)

    by_solicitante = dossier.get("by_solicitante") or {}
    if by_solicitante:
        story.append(PageBreak())
        story.append(Paragraph("Por solicitante", styles["Heading2"]))
        for name, cards in by_solicitante.items():
            story.append(Spacer(1, 0.25 * cm))
            story.append(Paragraph(_escape(name), styles["Heading3"]))
            for card in cards:
                _render_card_block(story, card, styles)

    by_tester = dossier.get("by_tester") or {}
    if by_tester:
        story.append(PageBreak())
        story.append(Paragraph("Por tester", styles["Heading2"]))
        for name, cards in by_tester.items():
            story.append(Spacer(1, 0.25 * cm))
            story.append(Paragraph(_escape(name), styles["Heading3"]))
            for card in cards:
                _render_card_block(story, card, styles)


_DESCRICAO_LABELS: dict[str, str] = {
    "cliente": "Cliente",
    "solicitacao": "Solicitacao",
    "solucao_dev": "Solucao do desenvolvedor",
    "obs_revisor_par": "Observacoes do revisor em par",
    "obs_revisor": "Observacoes do revisor",
    "obs_tester": "Observacoes do tester",
    "observacoes_gerais": "Observacoes gerais",
    "solicitacao_analise": "Solicitacao da analise",
    "analise_realizada": "Analise realizada",
    "recomendacao": "Recomendacao",
    "analise_origem": "Analise que originou",
}


def _render_descricao(story: list[Any], card: dict[str, Any], styles: Any) -> None:
    from reportlab.platypus import Paragraph

    descricao = card.get("descricao") or {}
    if not descricao:
        return
    for key, label in _DESCRICAO_LABELS.items():
        value = descricao.get(key)
        if not value:
            continue
        text = f"&raquo; <b>{_escape(label)}:</b> {_escape(value)}"
        story.append(Paragraph(text, styles["Muted"]))


def _render_etapas(story: list[Any], card: dict[str, Any], styles: Any) -> None:
    from reportlab.platypus import Paragraph

    etapas = card.get("etapas") or []
    if not etapas:
        return
    story.append(Paragraph("<b>Etapas do fluxo:</b>", styles["Small"]))
    for index, etapa in enumerate(etapas, start=1):
        text = (
            f"&raquo; {index}. {_escape(etapa.get('title', '-'))} "
            f"({_escape(etapa.get('list_name', '-'))}) &mdash; "
            f"{_escape(etapa.get('hours_human', '-'))}"
        )
        story.append(Paragraph(text, styles["Muted"]))


def _render_collaborator_involvement(
    story: list[Any],
    card: dict[str, Any],
    styles: Any,
) -> None:
    from reportlab.platypus import Paragraph

    involvements = card.get("collaborator_involvements") or []
    if not involvements:
        return
    total = card.get("collaborator_time_human", "-")
    story.append(Paragraph(f"<b>Atuacao do colaborador:</b> {_escape(total)}", styles["Small"]))
    for item in involvements:
        stages = item.get("stages") or []
        stage_text = "; ".join(
            f"{_escape(stage.get('title', '-'))}: {_escape(stage.get('hours_human', '-'))}"
            for stage in stages
        )
        if not stage_text:
            stage_text = "Sem tempo registrado"
        text = (
            f"&raquo; {_escape(item.get('role_label', '-'))} "
            f"({_escape(item.get('alias', '-'))}) - "
            f"{_escape(item.get('time_human', '-'))}. {stage_text}"
        )
        story.append(Paragraph(text, styles["Muted"]))


def _render_card_block(story: list[Any], card: dict[str, Any], styles: Any) -> None:
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, Spacer

    header = (
        f"<b>{_escape(card['card_name'])}</b> &mdash; {_escape(card['sistema'])} "
        f"(nivel {card['fibonacci_level'] or '-'}, {_escape(card['kind'])})"
    )
    story.append(Paragraph(header, styles["BodyText"]))

    facts = (
        f"Solicitante: {_escape(card['solicitante'])} | "
        f"Dev: {_escape(card['desenvolvedor'])} | "
        f"Revisor em par: {_escape(card['revisor_par'])} | "
        f"Revisor: {_escape(card['revisor'])} | "
        f"Tester: {_escape(card['tester'])}"
    )
    story.append(Paragraph(facts, styles["Small"]))

    if card.get("collaborator_roles"):
        story.append(
            Paragraph(
                f"Papeis neste card: {_escape(', '.join(card.get('collaborator_roles', [])))}",
                styles["Small"],
            )
        )

    times = (
        f"Vida util: {card['lead_time_human']} | "
        f"Tempo de entrega: {card['cycle_time_human']} | "
        f"Retornos DEV (teste/revisao): {card.get('return_dev_by_teste_count', 0)}/"
        f"{card.get('return_dev_by_revisao_count', 0)} | "
        f"Retestes: {card.get('retest_cycles', 0)} | "
        f"Pausas: {card['pause_count']}"
    )
    story.append(Paragraph(times, styles["Small"]))

    if card.get("double_review_required"):
        status = "com dupla revisao" if card.get("double_review_done") else "SEM dupla revisao (violacao)"
        story.append(Paragraph(f"Dupla revisao obrigatoria (nivel 8/13): {status}.", styles["Small"]))
    elif card.get("double_review_recommended"):
        status = "com dupla revisao" if card.get("double_review_done") else "sem dupla revisao"
        story.append(Paragraph(f"Dupla revisao recomendada (nivel 5): {status}.", styles["Small"]))

    _render_collaborator_involvement(story, card, styles)
    _render_descricao(story, card, styles)
    _render_etapas(story, card, styles)

    for retorno in card.get("retornos", []):
        tipo_label = "Desenvolvimento" if retorno["tipo"] == "dev" else "Suporte/Teste"
        subtipo = f" ({retorno['subtipo']})" if retorno.get("subtipo") else ""
        motivo = retorno.get("motivo") or "motivo nao registrado no card"
        solucao = retorno.get("solucao") or "solucao nao registrada no card"
        atribuido = retorno.get("atribuido_a") or "desconhecido"
        text = (
            f"&raquo; Retorno {retorno['numero']} ({_escape(tipo_label)}{_escape(subtipo)}): "
            f"{_escape(motivo)} &mdash; Solucao: {_escape(solucao)} "
            f"&mdash; Atribuido a: {_escape(atribuido)}"
        )
        story.append(Paragraph(text, styles["Muted"]))

    for pausa in card.get("pausas", []):
        motivo = pausa.get("motivo") or "motivo nao registrado no card"
        text = f"&raquo; Pausa {pausa['numero']}: {_escape(motivo)}"
        story.append(Paragraph(text, styles["Muted"]))

    story.append(Spacer(1, 0.25 * cm))


def _table(rows: list[list[Any]], widths: list[float], styles: Any) -> Any:
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle

    table = Table(rows, colWidths=widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#263238")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#DDDDDD")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F7FA")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _footer(canvas: Any, doc: Any) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColorRGB(0.35, 0.35, 0.35)
    canvas.drawString(doc.leftMargin, 0.8 * 28.3465, "Metricas Trello INTGEST")
    canvas.drawRightString(doc.pagesize[0] - doc.rightMargin, 0.8 * 28.3465, f"Pagina {doc.page}")
    canvas.restoreState()


def _escape(value: object) -> str:
    text = "" if value is None else str(value)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _stats_triplet(stats: dict[str, Any] | None) -> str:
    if not stats or not stats.get("samples"):
        return "-"
    return (
        f"{stats.get('median_human', '-')} / "
        f"{stats.get('p85_human', '-')} / "
        f"{stats.get('p95_human', '-')}"
    )


def _aging_status_label(status: object) -> str:
    if status == "above_p85":
        return "Acima P85"
    if status == "above_p50":
        return "Acima P50"
    return "Ok"


def _cfd_rows_for_pdf(rows: list[dict[str, Any]]) -> list[list[Any]]:
    formatted: list[list[Any]] = []
    for row in rows[-10:]:
        date = row.get("date", "-")
        stage_counts = [
            (stage, count)
            for stage, count in row.items()
            if stage != "date" and isinstance(count, (int, float)) and count
        ]
        total = sum(count for _, count in stage_counts)
        distribution = "; ".join(
            f"{stage}: {count}"
            for stage, count in sorted(stage_counts, key=lambda item: item[1], reverse=True)
        )
        formatted.append([date, total, distribution or "-"])
    return formatted
