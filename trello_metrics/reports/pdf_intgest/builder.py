"""Monta HTML estilo IntGest a partir do JSON de metricas (mesmos dados do PDF ReportLab)."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None  # type: ignore

from trello_metrics.reports.charts import render_charts
from trello_metrics.reports.metric_definitions import (
    management_guide_sections,
    metric_description,
    metric_label,
    section_guide,
    table_info,
)
from trello_metrics.reports.report_layouts import allows_section
from trello_metrics.utils.dates import human_hours

from . import helpers as H
from .card_rendering import render_card_block
from .helpers import (
    badge,
    chart_img,
    esc,
    metric_card,
    muted,
    note,
    pill,
    prio_color,
    risk_color,
    role_chip,
    sec_head,
    subttl,
    table,
)
from .pdf import render_pdf
from .styles import build_style_block

SEAL_COLORS = H.SEAL_COLORS


def build_pdf_report(metrics: dict[str, Any], output_path: str | Path, *, size: str = "A4") -> Path:
    builder = PdfReportBuilder(metrics, size=size)
    html = builder.build_html()
    return render_pdf(html, output_path, size=size)


class PdfReportBuilder:
    def __init__(self, metrics: dict[str, Any], *, size: str = "A4") -> None:
        self.metrics = metrics
        self.size = size
        self.charts = render_charts(metrics)
        self.export_meta = metrics.get("export_meta") or {}
        self.report_type = self.export_meta.get("report_type")
        self._sec = 0

    def include(self, section: str) -> bool:
        return allows_section(self.report_type, section)

    def _head(self, title: str, sub: str | None = None, *, break_page: bool = True) -> str:
        self._sec += 1
        brk = " rt-break" if break_page else ""
        return f'<section class="rt-sec{brk}">{sec_head(f"{self._sec:02d}", title, sub)}'

    def build_html(self) -> str:
        parts = [
            self._cover(),
            self._team_summary(),
            self._role_summary(),
            self._individual_summary(),
            self._overview(),
            self._ai_analysis(),
            self._management_guide(),
            self._operational_metrics(),
            self._fibonacci(),
            self._collaborators(),
            self._developers(),
            self._reviewers(),
            self._testers(),
            self._requesters(),
            self._projects(),
            self._sla(),
            self._bottlenecks(),
            self._quality_gates(),
            self._trends(),
            self._movements(),
            self._dossier(),
        ]
        body = "\n".join(p for p in parts if p)
        style = build_style_block(self.size)
        title = self._doc_title()
        return (
            '<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8">'
            f"<title>{esc(title)}</title>"
            f"<style>{style}</style></head>"
            f'<body><div class="rt-doc">{body}</div></body></html>'
        )

    def _doc_title(self) -> str:
        t = (self.export_meta.get("title") or "").split("|")[0].strip()
        if t:
            return t
        period = self.metrics.get("period") or {}
        return f"Relatorio de metricas Trello — {period.get('month', '')}"

    def _gen_date(self) -> str:
        iso = (self.metrics.get("board") or {}).get("generated_at", "")
        try:
            dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
            if ZoneInfo is not None:
                dt = dt.astimezone(ZoneInfo("America/Sao_Paulo"))
            return f"{dt.day} de {H.MONTHS_PT[dt.month].lower()} de {dt.year} as {dt:%H:%M}"
        except Exception:
            return esc(iso)

    def _table_intro(self, table_id: str) -> str:
        info = table_info(table_id)
        html = ""
        if info.get("description"):
            html += muted(esc(info["description"]))
        lines = []
        for key in info.get("columns") or []:
            desc = metric_description(key)
            if desc:
                lines.append(f"• <strong>{esc(metric_label(key))}</strong>: {esc(desc)}")
        if lines:
            html += note("<br/>".join(lines))
        return html

    def _section_guide(self, section_id: str) -> str:
        guide = section_guide(section_id)
        if not guide:
            return ""
        html = ""
        if guide.get("title"):
            html += f'<div class="rt-h3">{esc(guide["title"])}</div>'
        if guide.get("description"):
            html += muted(esc(guide["description"]))
        items = []
        for item in guide.get("metrics") or []:
            key = item.get("key", "")
            label = metric_label(key) if key else ""
            formula = item.get("formula") or metric_description(key)
            example = item.get("example")
            part = f"<strong>{esc(label)}</strong> — {esc(formula)}" if label and formula else ""
            if example:
                part += f"<br/>Exemplo: {esc(example)}"
            if part:
                items.append(part)
        if items:
            html += note("<br/>".join(items))
        return html

    def _cover(self) -> str:
        m = self.metrics
        board = m.get("board") or {}
        period = m.get("period") or {}
        overview = m.get("overview") or {}
        team = m.get("team_summary") or {}
        seal = (team.get("quality_seal") or "").strip()
        seal_c = SEAL_COLORS.get(seal, H.NAVY)
        title = self._doc_title()
        period_label = H.month_label(period["month"]) if period.get("month") else ""
        seal_block = ""
        if team and self.include("team_summary"):
            seal_block = (
                f'<div class="rt-seal" style="border-color:{seal_c};color:{seal_c};">'
                f'<div class="rt-seal-k">Selo de qualidade do mes</div>'
                f'<div class="rt-seal-v">{esc(seal or "—")}</div>'
                f'<div class="rt-seal-s">Qualidade {team.get("quality_rate_pct", 0)}% · '
                f'Aceitacao {team.get("acceptance_rate_pct", 0)}%</div></div>'
            )
        foot = [
            ("Periodo", f"{esc(period.get('month', '-'))} · {esc(period.get('timezone', '-'))}"),
            ("Gerado em", self._gen_date()),
            ("Escopo", f"{esc(overview.get('total_cards_metricados', 0))} cards · {esc(overview.get('total_movements', 0))} movimentos"),
        ]
        foot_html = "".join(
            f'<div><span class="rt-cf-k">{k}</span><span class="rt-cf-v">{v}</span></div>'
            for k, v in foot
        )
        return f"""<section class="rt-cover">
  <div class="rt-cover-top"><div class="rt-logo-text">INTGEST</div>
  <div class="rt-cover-kicker">Inteligencia e Gestao Tecnologica</div></div>
  <div class="rt-cover-mid"><div class="rt-cover-eyebrow">Relatorio de Engenharia</div>
  <h1 class="rt-cover-title">{esc(title)}</h1>
  <div class="rt-cover-board">{esc(board.get("name", ""))}</div>
  <div class="rt-cover-period">{period_label}</div>{seal_block}</div>
  <div class="rt-cover-foot">{foot_html}</div></section>"""

    def _team_summary(self) -> str:
        team = self.metrics.get("team_summary")
        if not team or not self.include("team_summary"):
            return ""
        bn = (self.metrics.get("bottlenecks") or {}).get("top_bottleneck") or {}
        kpis = [
            metric_card("Cards entregues", team.get("cards_delivered", 0), None, H.NAVY),
            metric_card("Pontos normais", team.get("fibonacci_normal", 0), None, H.TEAL),
            metric_card("Pontos analise", team.get("fibonacci_analysis", 0), None, H.TEAL),
            metric_card("Taxa aceitacao", f"{team.get('acceptance_rate_pct', 0)}%", None, "#388E3C"),
            metric_card("Retorno DEV penalizado", f"{team.get('return_dev_rate_pct', 0)}%", None, "#C62828" if team.get("return_dev_rate_pct", 0) > 0 else "#388E3C"),
            metric_card("Problemas evitados", team.get("total_prevented_problems", team.get("total_tester_quality_returns", 0)), "pelo teste", H.NAVY),
            metric_card("Retrabalho", f"{team.get('rework_rate_pct', 0)}%", f"{team.get('cards_with_rework_count', 0)} cards", "#F57C00" if team.get("rework_rate_pct", 0) > 0 else "#388E3C"),
            metric_card("Qualidade", f"{team.get('quality_rate_pct', 0)}%", esc(team.get("quality_seal", "-")), "#388E3C"),
        ]
        rows = [
            ["Indicador", "Valor"],
            ["Cards entregues", team.get("cards_delivered", 0)],
            ["Pontos normais", team.get("fibonacci_normal", 0)],
            ["Pontos analise", team.get("fibonacci_analysis", 0)],
            ["Taxa aceitacao", f"{team.get('acceptance_rate_pct', 0)}%"],
            ["Retorno DEV penalizado", f"{team.get('return_dev_rate_pct', 0)}%"],
            ["Problemas evitados pelo teste", team.get("total_prevented_problems", team.get("total_tester_quality_returns", 0))],
            ["Retornos de teste sem motivo", team.get("test_returns_missing_reason_count", 0)],
            ["Maior gargalo", bn.get("title", "-")],
            ["Cards que voltaram (retrabalho)", team.get("cards_with_rework_count", 0)],
            ["Taxa de retrabalho", f"{team.get('rework_rate_pct', 0)}%"],
            ["Taxa de qualidade de entrega", f"{team.get('quality_rate_pct', 0)}%"],
            ["Selo de qualidade do mes", team.get("quality_seal", "-")],
        ]
        charts = chart_img(self.charts.get("executive")) + chart_img(self.charts.get("quality"))
        callout = ""
        if bn:
            callout = (
                f'<div class="rt-callouts"><div class="rt-callout" style="border-left-color:#C62828;">'
                f'<div class="rt-co-k">Maior gargalo</div><div class="rt-co-v">{esc(bn.get("title", "-"))}</div>'
                f'<div class="rt-co-s">Media {esc(bn.get("avg_human", "-"))}</div></div></div>'
            )
        return (
            f'{self._head("Sumario executivo", "Indicadores consolidados do time no periodo", break_page=False)}'
            f'<div class="rt-kpis">{"".join(kpis)}</div>{callout}{charts}'
            f'{table(["Indicador", "Valor"], rows[1:], align=["left", "right"])}</section>'
        )

    def _role_summary(self) -> str:
        summary = self.metrics.get("role_summary")
        if not summary or not self.include("role_summary"):
            return ""
        titles = {
            "developers": "Resumo de desenvolvedores",
            "requesters": "Resumo de solicitantes",
            "testers": "Resumo de testers",
            "specific_metrics": "Metricas selecionadas",
        }
        title = titles.get(summary.get("scope", ""), "Resumo do relatorio")
        rows = []
        for key, value in summary.items():
            if key == "scope":
                continue
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value)
            rows.append([metric_label(key), value])
        return (
            f'{self._head(title, break_page=False)}'
            f'{table(["Indicador", "Valor"], rows, align=["left", "right"])}</section>'
        )

    def _individual_summary(self) -> str:
        if not self.include("individual_summary"):
            return ""
        summary = self.metrics.get("individual_summary") or {}
        target = self.metrics.get("individual_target") or summary.get("name", "")
        if not summary:
            return ""
        rows = [
            ["Cards ativos", summary.get("cards_active", 0)],
            ["Cards criados", summary.get("cards_created", 0)],
            ["Cards entregues", summary.get("cards_delivered", 0)],
            ["Pontos normais", summary.get("fibonacci_normal", 0)],
            ["Pontos analise", summary.get("fibonacci_analysis", 0)],
            ["Tempo de atuacao", summary.get("time_human", "-")],
        ]
        html = (
            f'{self._head(f"Colaborador: {target}", esc(", ".join(summary.get("roles") or []) or "-"), break_page=False)}'
            f'{table(["Indicador", "Valor"], rows, align=["left", "right"])}'
        )
        role_metrics = self.metrics.get("role_metrics") or []
        if role_metrics:
            html += subttl("Metricas por papel") + self._table_intro("collaborators")
            html += table(
                ["Papel", "Ativos", "Entregues", "Pontos", "Tempo", "Media"],
                [[r.get("role_label", "-"), r.get("cards_active", 0), r.get("cards_delivered", 0),
                  r.get("fibonacci_total", 0), r.get("time_human", "-"), r.get("avg_time_human", "-")]
                 for r in role_metrics],
                align=["left", "right", "right", "right", "right", "right"],
            )
        collabs = self.metrics.get("collaborators") or []
        if len(collabs) == 1 and collabs[0].get("process_times"):
            pt = collabs[0]["process_times"]
            html += subttl("Tempo por processo") + table(
                ["Processo", "Total", "Media", "Visitas", "Cards"],
                [[r.get("title", "-"), r.get("total_human", "-"), r.get("avg_human", "-"),
                  r.get("visits", 0), r.get("cards", 0)] for r in pt],
                align=["left", "right", "right", "right", "right"],
            )
        return html + "</section>"

    def _overview(self) -> str:
        ov = self.metrics.get("overview") or {}
        dq = self.metrics.get("data_quality") or {}
        rows = [
            ["Listas no quadro", ov.get("total_lists", 0)],
            ["Cards no export/API", ov.get("total_cards_raw", 0)],
            ["Cards metricados", ov.get("total_cards_metricados", 0)],
            ["Templates ignorados", ov.get("total_templates_ignorados", 0)],
            ["Placeholders/controle ignorados", ov.get("total_placeholders_ignorados", 0)],
            ["Movimentos no historico", ov.get("total_movements", 0)],
        ]
        if dq:
            rows.append(["Cards com campos obrigatorios", f"{dq.get('cards_with_required_fields_pct', 0)}%"])
        board = self.metrics.get("board") or {}
        meta = muted(
            f"Gerado em: {esc(board.get('generated_at', '-'))}"
            + (f"<br/>URL: {esc(board.get('url', ''))}" if board.get("url") else "")
        )
        return (
            f'{self._head("Visao geral do quadro", "Composicao do backlog e movimentacao", break_page=False)}'
            f"{meta}{table(['Indicador', 'Valor'], rows, align=['left', 'right'])}</section>"
        )

    def _ai_analysis(self) -> str:
        if not self.metrics.get("ai_analysis") or not self.include("ai"):
            return ""
        ai = self.metrics.get("ai") or {}
        body = muted(esc(f"{ai.get('provider', 'IA')} | {ai.get('model', '-')}"))
        for raw_line in str(self.metrics.get("ai_analysis", "")).splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("#"):
                body += f'<div class="rt-h3">{esc(line.lstrip("# "))}</div>'
            elif line.startswith(("-", "*")):
                body += f'<div class="rt-li">{esc(line.lstrip("-* "))}</div>'
            else:
                body += f"<p>{esc(line)}</p>"
        return f'{self._head("Analise gerada por IA", break_page=True)}{body}</section>'

    def _management_guide(self) -> str:
        if self.report_type != "management" or not self.include("metric_guide"):
            return ""
        intro = section_guide("management_intro")
        if not intro:
            return ""
        html = f'{self._head("Guia de metricas para gestao", break_page=True)}'
        if intro.get("description"):
            html += note(f"<strong>Introducao.</strong> {esc(intro['description'])}")
        for sid in management_guide_sections():
            if sid != "management_intro":
                html += self._section_guide(sid)
        return html + "</section>"

    def _operational_metrics(self) -> str:
        keys = ("flow", "risk_board", "priority", "dora", "process_discipline")
        if not any(self.include(k if k != "process_discipline" else "discipline") and self.metrics.get(
            "process_discipline" if k == "process_discipline" else k
        ) for k in keys):
            return ""
        html = f'{self._head("Fluxo, prioridade, DORA e risco", break_page=True)}'
        html += self._section_guide("flow")
        flow = self.metrics.get("flow") or {}
        if flow and self.include("flow"):
            html += chart_img(self.charts.get("cfd")) + chart_img(self.charts.get("stage_time"))
            team = flow.get("team") or {}
            eff = team.get("flow_efficiency") or {}
            little = team.get("little_law") or {}
            html += subttl("Fluxo do time") + table(
                ["Indicador", "Valor"],
                [
                    ["Lead time med/P85/P95", _stats_triplet(team.get("lead_time"))],
                    ["Cycle time med/P85/P95", _stats_triplet(team.get("cycle_time"))],
                    ["Planejamento ate aprovacao", _stats_triplet(team.get("planning_to_approval_time"))],
                    ["Eficiencia de fluxo", f"{eff.get('efficiency_pct', 0)}%"],
                    ["Tempo em fila", eff.get("wait_human", "-")],
                    ["Tempo em trabalho", eff.get("work_human", "-")],
                    ["WIP atual", team.get("wip_total", 0)],
                    ["Lei de Little", f"{little.get('predicted_lead_time_days', '-')} dias previstos"],
                ],
                align=["left", "right"],
            )
            wip = flow.get("wip_by_stage") or []
            if wip:
                html += subttl("WIP atual por etapa") + table(
                    ["Etapa", "Cards"], [[r.get("title", "-"), r.get("count", 0)] for r in wip[:10]],
                    align=["left", "right"],
                )
            stages = flow.get("stage_time") or []
            if stages:
                html += subttl("Tempo por etapa do fluxo") + table(
                    ["Etapa", "Mediana", "P85", "P95", "Amostras"],
                    [[r.get("title", "-"), r.get("median_human", "-"), r.get("p85_human", "-"),
                      r.get("p95_human", "-"), r.get("samples", 0)] for r in stages[:12]],
                    align=["left", "right", "right", "right", "right"],
                )
            aging = flow.get("aging_wip") or []
            if aging:
                html += subttl("Aging WIP vs P50/P85 historico") + table(
                    ["Card", "Etapa", "Idade", "P50", "P85", "Status"],
                    [[r.get("card_name", "-"), r.get("title") or r.get("list_name", "-"),
                      r.get("age_human", "-"), r.get("p50_human", "-"), r.get("p85_human", "-"),
                      _aging_status_label(r.get("status"))] for r in aging[:15]],
                    align=["left", "left", "right", "right", "right", "center"],
                )
            cfd = _cfd_rows(flow.get("cfd") or [])
            if cfd:
                html += subttl("CFD - ultimos snapshots") + table(
                    ["Data", "Total", "Distribuicao por etapa"], cfd,
                    align=["left", "right", "left"],
                )
        risk = self.metrics.get("risk_board") or {}
        if risk and self.include("risk_board"):
            attention = risk.get("cards_that_need_attention") or []
            html += subttl("Cards que merecem atencao agora")
            html += muted(f"Cards em risco alto/critico: {risk.get('high_or_critical_count', 0)}")
            if attention:
                rows = []
                for c in attention[:10]:
                    reasons = "".join(f"<span>{esc(r)}</span>" for r in c.get("reasons") or [])
                    name = f'<div class="rt-cardname">{esc(c.get("card_name"))}</div>'
                    rows.append([
                        name, esc(c.get("current_stage", "-")), c.get("age_human", "-"),
                        pill(c.get("prioridade", "-"), prio_color(c.get("prioridade", "-"))),
                        badge((c.get("level") or "").upper(), risk_color(c.get("level"))),
                        f'<div class="rt-reasons">{reasons}</div>',
                    ])
                html += table(
                    ["Card", "Etapa", "Idade", "Prioridade", "Risco", "Motivos"], rows,
                    align=["left", "left", "right", "center", "center", "left"],
                )
            else:
                html += muted("Nenhum card alto/critico no momento.")
        priority = self.metrics.get("priority") or {}
        if priority and self.include("priority"):
            html += subttl("Prioridade") + table(
                ["Indicador", "Valor"],
                [
                    ["Urgente/Critica no periodo", f"{priority.get('urgent_critical_pct', 0)}%"],
                    ["Alerta de inflacao", "Sim" if priority.get("priority_inflation_alert") else "Nao"],
                    ["Furos de fila", priority.get("queue_jumps_count", 0)],
                    ["Urgentes envelhecendo", priority.get("urgent_aging_count", 0)],
                ],
                align=["left", "right"],
            )
            lbp = priority.get("lead_time_by_priority") or []
            if lbp:
                html += subttl("Lead time por prioridade") + table(
                    ["Prioridade", "Mediana", "P85", "P95", "Amostras"],
                    [[r.get("priority", "-"), r.get("median_human", "-"), r.get("p85_human", "-"),
                      r.get("p95_human", "-"), r.get("samples", 0)] for r in lbp],
                    align=["left", "right", "right", "right", "right"],
                )
            dist = priority.get("distribution") or []
            if dist:
                html += subttl("Distribuicao de prioridades") + table(
                    ["Prioridade", "Cards"],
                    [[pill(r.get("priority", "-"), prio_color(r.get("priority", "-"))), r.get("count", 0)] for r in dist],
                    align=["left", "right"],
                )
            qj = priority.get("queue_jumps") or []
            if qj:
                html += subttl("Furos de fila") + table(
                    ["Entregue antes", "Prioridade", "Maior prioridade aguardou", "Prioridade"],
                    [[(i.get("delivered_first") or {}).get("card_name", "-"),
                      (i.get("delivered_first") or {}).get("priority", "-"),
                      (i.get("higher_priority_waited") or {}).get("card_name", "-"),
                      (i.get("higher_priority_waited") or {}).get("priority", "-")] for i in qj[:12]],
                    align=["left", "center", "left", "center"],
                )
            ua = priority.get("urgent_aging") or []
            if ua:
                html += subttl("Urgentes/Criticas envelhecendo") + table(
                    ["Card", "Etapa", "Idade", "Status"],
                    [[r.get("card_name", "-"), r.get("title", "-"), r.get("age_human", "-"),
                      _aging_status_label(r.get("status"))] for r in ua[:12]],
                    align=["left", "left", "right", "center"],
                )
        dora = self.metrics.get("dora") or {}
        if dora and self.include("dora"):
            deploy = dora.get("deployment_frequency") or {}
            failure = dora.get("change_failure_rate") or {}
            html += subttl("DORA adaptado") + table(
                ["Indicador", "Valor"],
                [
                    ["Frequencia de deploy", deploy.get("total", 0)],
                    ["Lead time de deploy med/P85/P95", _stats_triplet(dora.get("lead_time_deploy"))],
                    ["Change failure rate", f"{failure.get('rate_pct', 0)}%"],
                    ["Deploys com falha", failure.get("failed_deployments", 0)],
                    ["Time to restore med/P85/P95", _stats_triplet(dora.get("time_to_restore"))],
                ],
                align=["left", "right"],
            )
            by_week = deploy.get("by_week") or {}
            if by_week:
                html += subttl("Deploys por semana") + table(
                    ["Semana", "Deploys"], [[w, c] for w, c in sorted(by_week.items())],
                    align=["left", "right"],
                )
            by_sys = deploy.get("by_system") or []
            if by_sys:
                html += subttl("Deploys por sistema") + table(
                    ["Sistema", "Deploys"], [[esc(r.get("sistema", "-")), r.get("count", 0)] for r in by_sys[:12]],
                    align=["left", "right"],
                )
            fails = failure.get("failures") or []
            if fails:
                html += subttl("Change failures detectados") + table(
                    ["Deploy", "Sistema", "Correcao subsequente", "Criada em"],
                    [[r.get("deployment_card_name", "-"), r.get("sistema", "-"),
                      r.get("correction_card_name", "-"), r.get("correction_created_at", "-")] for r in fails[:12]],
                    align=["left", "left", "left", "left"],
                )
        discipline = self.metrics.get("process_discipline") or {}
        if discipline and self.include("discipline"):
            fc = discipline.get("flow_conformity") or {}
            dal = discipline.get("developer_assignment_latency") or {}
            wl = discipline.get("cards_without_level") or []
            html += subttl("Disciplina de processo")
            html += self._section_guide("process_discipline") + self._table_intro("process_discipline")
            html += table(
                ["Indicador", "Valor"],
                [
                    ["Conformidade do fluxo", f"{fc.get('compliance_pct', 0)}%"],
                    ["Cards avaliados", fc.get("cards_evaluated", 0)],
                    ["Violacoes", len(fc.get("violations") or [])],
                    ["Cards sem nivel", len(wl)],
                    ["Latencia para atribuir dev", _stats_triplet(dal)],
                    ["Eventos de campo historicos", dal.get("history_events", 0)],
                ],
                align=["left", "right"],
            )
            rf = discipline.get("required_fields_by_stage") or []
            if rf:
                html += subttl("Campos obrigatorios por etapa") + table(
                    ["Etapa", "Completude", "Cards", "Pendencias"],
                    [[r.get("title", "-"), f"{r.get('completion_pct', 0)}%", r.get("cards_evaluated", 0),
                      len(r.get("missing") or [])] for r in rf],
                    align=["left", "right", "right", "right"],
                )
            skipped = discipline.get("skipped_stages") or []
            if skipped:
                html += subttl("Etapas puladas") + table(
                    ["Etapa", "Tipo", "Cards"],
                    [[r.get("title", "-"), "Opcional" if r.get("optional") else "Core", r.get("count", 0)]
                     for r in skipped[:12]],
                    align=["left", "center", "right"],
                )
            if wl:
                html += subttl("Cards sem nivel") + table(
                    ["Card", "Dev", "Sistema"],
                    [[r.get("card_name", "-"), r.get("desenvolvedor", "-"), r.get("sistema", "-")]
                     for r in wl[:12]],
                    align=["left", "left", "left"],
                )
            ac = dal.get("cards") or []
            if ac:
                html += subttl("Latencia ate atribuir desenvolvedor") + table(
                    ["Card", "Dev", "Criado em", "Atribuido em", "Horas"],
                    [[r.get("card_name", "-"), r.get("developer", "-"), r.get("created_at", "-"),
                      r.get("assigned_at", "-"), r.get("latency_hours", 0)] for r in ac[:12]],
                    align=["left", "left", "left", "left", "right"],
                )
            viol = fc.get("violations") or []
            if viol:
                html += subttl("Violacoes do fluxo canonico") + table(
                    ["Card", "Problemas"],
                    [[r.get("card_name", "-"), "; ".join(r.get("issues") or [])] for r in viol[:12]],
                    align=["left", "left"],
                )
        return html + "</section>"

    def _fibonacci(self) -> str:
        fb = self.metrics.get("fibonacci_points") or {}
        if not self.include("fibonacci") or not fb.get("by_developer"):
            return ""
        team = fb.get("team") or {}
        html = (
            f'{self._head("Pontos Fibonacci", "Pontuacao creditada ao desenvolvedor")}'
            + (muted(esc(fb.get("policy", ""))) if fb.get("policy") else "")
            + table(
                ["Indicador", "Valor"],
                [
                    ["Cards normais", team.get("cards_normal", 0)],
                    ["Pontos normais", team.get("points_normal", 0)],
                    ["Cards analise", team.get("cards_analysis", 0)],
                    ["Pontos analise", team.get("points_analysis", 0)],
                    ["Total equipe", team.get("points_total", 0)],
                ],
                align=["left", "right"],
            )
            + chart_img(self.charts.get("fibonacci"))
            + table(
                ["Desenvolvedor", "Cards normais", "Pts normais", "Cards analise", "Pts analise", "Total"],
                [[r.get("developer", "-"), r.get("cards_normal", 0), r.get("points_normal", 0),
                  r.get("cards_analysis", 0), r.get("points_analysis", 0), r.get("points_total", 0)]
                 for r in fb.get("by_developer") or []],
                align=["left", "right", "right", "right", "right", "right"],
            )
        )
        return html + "</section>"

    def _collaborators(self) -> str:
        collabs = self.metrics.get("collaborators") or []
        if not self.include("collaborators") or not collabs:
            return ""
        html = (
            f'{self._head("Colaboradores", "Visao consolidada por pessoa")}'
            + muted("Visao individual consolidada por nome base, juntando todos os papeis.")
            + self._table_intro("collaborators")
            + chart_img(self.charts.get("collab_points"))
            + chart_img(self.charts.get("collab_time"))
            + table(
                ["Nome", "Papeis", "Ativos", "Entregues", "Pontos", "Tempo"],
                [[c["name"], ", ".join(c.get("roles") or []) or "-",
                  c.get("summary", {}).get("cards_active", 0),
                  c.get("summary", {}).get("cards_delivered", 0),
                  c.get("summary", {}).get("fibonacci_total", 0),
                  c.get("summary", {}).get("time_human", "-")] for c in collabs],
                align=["left", "left", "right", "right", "right", "right"],
            )
        )
        for c in collabs:
            s = c.get("summary") or {}
            roles = "".join(role_chip(r) for r in c.get("roles") or [])
            pk = [
                (s.get("cards_active", 0), "Ativos"), (s.get("cards_delivered", 0), "Entregues"),
                (s.get("cards_created", 0), "Criados"),
                (s.get("fibonacci_total", 0), "Pontos"), (s.get("time_human", "-"), "Tempo"),
            ]
            kpis = "".join(
                f'<div class="rt-pk"><span class="rt-pk-v">{v}</span><span class="rt-pk-k">{k}</span></div>'
                for v, k in pk
            )
            prof = (
                f'<div class="rt-profile rt-profile-page"><div class="rt-prof-head">'
                f'<div class="rt-prof-name">{esc(c.get("name"))}</div>'
                f'<div class="rt-rolewrap">{roles}</div></div>'
                f'<div class="rt-profkpis">{kpis}</div>'
            )
            pt = c.get("process_times") or []
            if pt:
                prof += subttl("Tempo por processo") + table(
                    ["Processo", "Total", "Media", "Visitas", "Cards"],
                    [[r.get("title", "-"), r.get("total_human", "-"), r.get("avg_human", "-"),
                      r.get("visits", 0), r.get("cards", 0)] for r in pt],
                    align=["left", "right", "right", "right", "right"],
                )
            rm = c.get("role_metrics") or []
            if rm:
                prof += subttl("Papeis no periodo") + table(
                    ["Papel", "Ativos", "Entregues", "Pontos", "Tempo", "Media"],
                    [[r.get("role_label", "-"), r.get("cards_active", 0), r.get("cards_delivered", 0),
                      r.get("fibonacci_total", 0), r.get("time_human", "-"), r.get("avg_time_human", "-")]
                     for r in rm],
                    align=["left", "right", "right", "right", "right", "right"],
                )
            cards = c.get("cards") or []
            if cards:
                prof += subttl("Cards com atuacao") + "".join(render_card_block(card) for card in cards)
            html += prof + "</div>"
        return html + "</section>"

    def _role_table_section(self, section: str, title: str, table_id: str, headers: list, rows: list, chart_keys: list[str]) -> str:
        data = self.metrics.get(section)
        if not self.include(section) or not data:
            return ""
        charts_html = "".join(chart_img(self.charts.get(k)) for k in chart_keys)
        return (
            f'{self._head(title)}{self._table_intro(table_id)}'
            f'{charts_html}{table(headers, rows, align=["left"] + ["right"] * (len(headers) - 1))}</section>'
        )

    def _developers(self) -> str:
        devs = self.metrics.get("developers")
        if not self.include("developers") or not devs:
            return ""
        html = (
            f'{self._head("Desenvolvedores")}{self._table_intro("developers")}'
            f'{chart_img(self.charts.get("dev_points"))}{chart_img(self.charts.get("dev_flow"))}'
            f'{chart_img(self.charts.get("dev_quality"))}'
            f'{table(["Nome", "Cards", "Normais", "Analise", "Pts normais", "Pts analise", "Tempo dev", "Aceitacao", "Retrabalho", "Pegos no teste", "Ret. par"], [[r["name"], r["cards_delivered"], r.get("cards_delivered_normal", 0), r.get("cards_delivered_analysis", 0), r["fibonacci_normal"], r["fibonacci_analysis"], r["avg_dev_human"], f"{r['acceptance_rate_pct']}%", f"{r.get('rework_rate_pct', 0)}%", r.get("tester_quality_returns", 0), r["peer_review_returns"]] for r in devs], align=["left", "right", "right", "right", "right", "right", "right", "right", "right", "right", "right"])}'
        )
        profiles = self.metrics.get("developer_profiles") or []
        if profiles:
            html += subttl("Perfis detalhados por desenvolvedor")
            for dev in profiles:
                cards = dev.get("cards") or []
                if not cards:
                    continue
                html += (
                    f'<div class="rt-devgroup-head"><div class="rt-devgroup-name">{esc(dev.get("name", "-"))}</div>'
                    f'<div class="rt-devgroup-sub">{dev.get("cards_delivered", 0)} entrega(s) · '
                    f'{dev.get("fibonacci_total", 0)} pts</div></div>'
                    + table(
                        ["Card", "Sistema", "Nivel", "Atuacao", "Espera", "% espera", "Ciclo"],
                        [[c.get("card_name", "-"), c.get("sistema", "-"), c.get("fibonacci_level", "-"),
                          c.get("dev_work_human", "-"), c.get("pipeline_wait_human", "-"),
                          f"{c.get('pipeline_wait_ratio_pct', 0)}%", c.get("cycle_time_human", "-")]
                         for c in cards],
                        align=["left", "left", "right", "right", "right", "right", "right"],
                    )
                )
        return html + "</section>"

    def _reviewers(self) -> str:
        rows = self.metrics.get("reviewers")
        if not self.include("reviewers") or not rows:
            return ""
        return (
            f'{self._head("Revisores em par")}{self._table_intro("reviewers")}'
            f'{table(["Nome", "Revisoes", "Aprovadas", "Devolvidas", "Escapes teste", "Taxa aprovacao"], [[r["name"], r["reviews_done"], r["approved"], r["sent_back"], r.get("escaped_to_test", 0), f"{r['approval_rate_pct']}%"] for r in rows], align=["left", "right", "right", "right", "right", "right"])}'
            "</section>"
        )

    def _testers(self) -> str:
        rows = self.metrics.get("testers")
        if not self.include("testers") or not rows:
            return ""
        return (
            f'{self._head("Testers / Suporte")}{self._table_intro("testers")}'
            f'{chart_img(self.charts.get("testers"))}'
            f'{table(["Nome", "Testes", "1a passagem", "Problemas evitados", "Sem motivo", "Retestes"], [[r["name"], r["cards_tested"], r["approved_first_pass"], r.get("prevented_problems", r.get("returned_dev_for_quality", 0)), r.get("returns_missing_reason", 0), r["retest_cycles_total"]] for r in rows], align=["left", "right", "right", "right", "right", "right"])}'
            "</section>"
        )

    def _requesters(self) -> str:
        rows = self.metrics.get("requesters")
        if not self.include("requesters") or not rows:
            return ""
        return (
            f'{self._head("Solicitantes")}{self._table_intro("requesters")}'
            f'{table(["Nome", "Criados", "Entregues", "Em producao", "Planejamento ok", "Aprovacao media"], [[r["name"], r["cards_created"], r["cards_delivered"], r["in_production"], f"{r['planning_ok_rate_pct']}%", r.get("avg_approval_human", "-")] for r in rows], align=["left", "right", "right", "right", "right", "right"])}'
            "</section>"
        )

    def _projects(self) -> str:
        rows = self.metrics.get("projects")
        if not self.include("projects") or not rows:
            return ""
        return (
            f'{self._head("Projetos / Sistemas")}{self._table_intro("projects")}'
            f'{chart_img(self.charts.get("projects"))}'
            f'{table(["Sistema", "Cards", "Pts normais", "Pts analise", "Top dev"], [[r["name"], r["cards_delivered"], r["fibonacci_normal"], r["fibonacci_analysis"], r.get("top_developer") or "-"] for r in rows], align=["left", "right", "right", "right", "left"])}'
            "</section>"
        )

    def _sla(self) -> str:
        sla = self.metrics.get("sla") or {}
        if not self.include("sla") or not sla:
            return ""
        team = sla.get("team") or {}
        policy = sla.get("policy") or {}
        html = (
            f'{self._head("SLA")}{self._section_guide("sla")}{self._table_intro("sla_team")}'
            + (muted(esc(policy.get("note", ""))) if policy.get("note") else "")
            + table(
                ["Indicador", "Valor"],
                [
                    ["Cards avaliados", team.get("cards_evaluated", 0)],
                    ["Etapas avaliadas", team.get("stage_checks", 0)],
                    ["Etapas estouradas", team.get("breached_count", 0)],
                    ["Cumprimento SLA", f"{team.get('compliance_pct', 0)}%"],
                    ["Em risco agora", team.get("current_at_risk_count", 0)],
                    ["Estouradas agora", team.get("current_breached_count", 0)],
                ],
                align=["left", "right"],
            )
            + chart_img(self.charts.get("sla_stage"))
        )
        by_stage = sla.get("by_stage") or []
        if by_stage:
            html += subttl("SLA por etapa") + self._table_intro("sla_by_stage") + table(
                ["Etapa", "SLA", "Avaliadas", "Estouradas", "Cumprimento", "Media usada"],
                [[r.get("title", "-"), r.get("sla_human", "-"), r.get("checks", 0), r.get("breached_count", 0),
                  f"{r.get('compliance_pct', 0)}%", r.get("avg_elapsed_human", "-")] for r in by_stage],
                align=["left", "right", "right", "right", "right", "right"],
            )
        by_dev = sla.get("by_developer") or []
        if by_dev:
            html += subttl("SLA por desenvolvedor") + self._table_intro("sla_developers") + table(
                ["Desenvolvedor", "Cards", "Etapas", "Estouradas", "Cards c/ estouro", "Cumprimento"],
                [[r.get("name", "-"), r.get("cards_evaluated", 0), r.get("stage_checks", 0),
                  r.get("breached_count", 0), r.get("breached_cards", 0), f"{r.get('compliance_pct', 0)}%"]
                 for r in by_dev],
                align=["left", "right", "right", "right", "right", "right"],
            )
        cards = sla.get("cards") or []
        if cards:
            html += subttl("SLA por card") + table(
                ["Card", "Dev", "Nivel", "Pior etapa", "Uso max.", "Etapas", "Estouradas", "Cumprimento"],
                [[r.get("card_name", "-"), r.get("desenvolvedor", "-"), r.get("fibonacci_level", "-"),
                  r.get("worst_stage", "-"), f"{r.get('worst_usage_pct', 0)}%", r.get("stage_checks", 0),
                  r.get("breached_count", 0), f"{r.get('compliance_pct', 0)}%"] for r in cards],
                align=["left", "left", "right", "left", "right", "right", "right", "right"],
            )
        alerts = sla.get("current_alerts") or []
        if alerts:
            html += subttl("Cards com alerta de SLA na etapa atual") + table(
                ["Card", "Etapa", "Uso", "SLA", "Status"],
                [[r.get("card_name", "-"), r.get("title", r.get("current_list", "-")),
                  f"{r.get('elapsed_human', '-')} ({r.get('usage_pct', 0)}%)",
                  r.get("limit_human", "-"), r.get("status", "-")] for r in alerts],
                align=["left", "left", "right", "right", "center"],
            )
        return html + "</section>"

    def _bottlenecks(self) -> str:
        bn = self.metrics.get("bottlenecks") or {}
        if not self.include("bottlenecks") or not bn.get("by_stage"):
            return ""
        top = bn.get("top_bottleneck") or {}
        html = (
            f'{self._head("Gargalos")}{self._table_intro("bottlenecks")}'
            + (note(f"<strong>Maior gargalo:</strong> {esc(top.get('title', '-'))} ({esc(top.get('avg_human', '-'))})") if top else "")
            + chart_img(self.charts.get("bottlenecks"))
            + table(
                ["Etapa", "Media", "Mediana", "P95", "Amostras"],
                [[r["title"], r["avg_human"], human_hours(r["median_hours"]), human_hours(r["p95_hours"]), r["samples"]]
                 for r in bn["by_stage"]],
                align=["left", "right", "right", "right", "right"],
            )
        )
        if bn.get("by_sistema"):
            html += subttl("Gargalo por sistema/projeto") + table(
                ["Sistema", "Media de espera", "Amostras"],
                [[r["sistema"], r["avg_human"], r["samples"]] for r in bn["by_sistema"]],
                align=["left", "right", "right"],
            )
        mv = bn.get("management_only_view") or {}
        if any(mv.values()):
            html += subttl("Controle de gestao (por projeto)")
            html += muted(
                "Visao gerencial: lista especifica por projeto/canal. "
                "Nao impacta metricas de gargalo (estagio fundido)."
            )
            for group_title, rows in (("Aguardando teste", mv.get("waiting_test", [])), ("Aguardando producao", mv.get("waiting_production", []))):
                if rows:
                    html += table([group_title, "Cards agora"], [[r["list"], r["count"]] for r in rows], align=["left", "right"])
        return html + "</section>"

    def _quality_gates(self) -> str:
        qg = self.metrics.get("quality_gates") or {}
        if not self.include("quality_gates") or not qg:
            return ""
        html = (
            f'{self._head("Conformidade de dupla revisao")}'
            + note(
                "<strong>Regra.</strong> Cards nivel 8/13 exigem revisao em par + revisao formal. "
                "Nivel 5 e recomendado, mas nao obrigatorio."
            )
            + table(
                ["Indicador", "Valor"],
                [
                    ["Cards nivel 8/13 (obrigatorio)", qg.get("mandatory_total", 0)],
                    ["Violacoes (sem dupla revisao)", qg.get("mandatory_violations_count", 0)],
                    ["Conformidade obrigatoria", f"{qg.get('mandatory_compliance_pct', 0)}%"],
                    ["Cards nivel 5 (recomendado)", qg.get("recommended_total", 0)],
                    ["Fizeram dupla revisao (informativo)", f"{qg.get('recommended_done_pct', 0)}%"],
                ],
                align=["left", "right"],
            )
        )
        viol = qg.get("mandatory_violations") or []
        if viol:
            html += subttl("Cards nivel 8/13 sem dupla revisao") + table(
                ["Card", "Desenvolvedor", "Sistema", "Nivel", "Passou par?", "Passou formal?"],
                [[r["card_name"], r["desenvolvedor"], r["sistema"], r["fibonacci_level"],
                  "Sim" if r["passed_peer_review"] else "Nao",
                  "Sim" if r["passed_formal_review"] else "Nao"] for r in viol],
                align=["left", "left", "left", "right", "center", "center"],
            )
        return html + "</section>"

    def _trends(self) -> str:
        trends = self.metrics.get("trends_6m")
        if not self.include("trends") or not trends:
            return ""
        return (
            f'{self._head("Tendencia 6 meses")}'
            f'{chart_img(self.charts.get("trends_team"))}'
            f'{chart_img(self.charts.get("trends_quality"))}'
            f'{chart_img(self.charts.get("trends_devs"))}'
            "</section>"
        )

    def _movements(self) -> str:
        movements = self.metrics.get("movements") or {}
        if not self.include("movements") or not movements:
            return ""
        ov = self.metrics.get("overview") or {}
        html = f'{self._head("Detalhes operacionais")}'
        for title, rows in (
            ("Cards por etapa atual", ov.get("cards_by_current_group") or []),
            ("Entradas por etapa", movements.get("target_groups") or []),
        ):
            if rows:
                html += subttl(title) + table(
                    ["Nome", "Total"], [[r["name"], r["count"]] for r in rows], align=["left", "right"]
                )
        time_rows = movements.get("time_by_list") or []
        if time_rows:
            html += subttl("Tempo por coluna") + table(
                ["Coluna", "Total", "Media", "Entradas"],
                [[r["list"], human_hours(r["total_hours"]), r["avg_human"], r["spans"]] for r in time_rows[:20]],
                align=["left", "right", "right", "right"],
            )
        return html + "</section>"

    def _dossier(self) -> str:
        dossier = self.metrics.get("card_dossier")
        if not self.include("dossier") or not dossier:
            return ""
        html = (
            f'{self._head("Detalhamento de cards", "Apendice descritivo com historico de cada card")}'
            + muted(
                "Agrupado por desenvolvedor, solicitante e tester. "
                "Casamento retorno/movimento e heuristica cronologica."
            )
        )
        by_dev = dossier.get("by_developer") or {}
        if by_dev:
            html += subttl("Por desenvolvedor")
            for name, buckets in by_dev.items():
                html += (
                    f'<div class="rt-devgroup-head"><div class="rt-devgroup-name">{esc(H.dev_name(name))}</div></div>'
                )
                if buckets.get("tarefas_normais"):
                    html += '<div class="rt-dossier-subhead">Tarefas normais</div>'
                    html += "".join(render_card_block(c) for c in buckets["tarefas_normais"])
                if buckets.get("cards_analise"):
                    html += '<div class="rt-dossier-subhead">Cards de analise</div>'
                    html += "".join(render_card_block(c) for c in buckets["cards_analise"])
        by_sol = dossier.get("by_solicitante") or {}
        if by_sol:
            html += subttl("Por solicitante")
            for name, cards in by_sol.items():
                html += f'<div class="rt-devgroup-head"><div class="rt-devgroup-name">{esc(name)}</div></div>'
                html += "".join(render_card_block(c) for c in cards)
        by_tester = dossier.get("by_tester") or {}
        if by_tester:
            html += subttl("Por tester")
            for name, cards in by_tester.items():
                html += f'<div class="rt-devgroup-head"><div class="rt-devgroup-name">{esc(name)}</div></div>'
                html += "".join(render_card_block(c) for c in cards)
        return html + "</section>"


def _stats_triplet(stats: dict[str, Any] | None) -> str:
    if not stats or not stats.get("samples"):
        return "-"
    return f"{stats.get('median_human', '-')} / {stats.get('p85_human', '-')} / {stats.get('p95_human', '-')}"


def _aging_status_label(status: object) -> str:
    if status == "above_p85":
        return badge("Acima P85", "#C62828")
    if status == "above_p50":
        return badge("Acima P50", "#F57C00")
    return badge("Ok", "#388E3C")


def _cfd_rows(rows: list[dict[str, Any]]) -> list[list[Any]]:
    formatted: list[list[Any]] = []
    for row in rows[-10:]:
        date = row.get("date", "-")
        stage_counts = [
            (stage, count) for stage, count in row.items()
            if stage != "date" and isinstance(count, (int, float)) and count
        ]
        total = sum(count for _, count in stage_counts)
        distribution = "; ".join(
            f"{stage}: {count}" for stage, count in sorted(stage_counts, key=lambda i: i[1], reverse=True)
        )
        formatted.append([date, total, distribution or "-"])
    return formatted
