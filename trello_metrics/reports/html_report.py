from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from typing import Any


def write_html_report(metrics: dict[str, Any], output_path: str | Path) -> Path:
    """Gera relatorio HTML interativo (self-contained) a partir do JSON de metricas."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    static = files("trello_metrics.reports.static")
    css = static.joinpath("report.css").read_text(encoding="utf-8")
    js = static.joinpath("report.js").read_text(encoding="utf-8")
    defs = files("trello_metrics.reports").joinpath("metric_definitions.json").read_text(encoding="utf-8")
    metrics_json = json.dumps(metrics, ensure_ascii=False)
    export_meta = metrics.get("export_meta") or {}
    page_title = (export_meta.get("title") or "").split("|")[0].strip()
    if not page_title:
        page_title = f"Relatorio de Engenharia — {(metrics.get('period') or {}).get('month', 'Periodo')}"

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{page_title}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
  <style>{css}</style>
</head>
<body>
  <div class="layout">
    <aside class="sidebar">
      <div class="sidebar-brand">
        <span class="brand-mark">INTGEST</span>
        <h1>Relatorio de Engenharia</h1>
        <p>Metricas do fluxo de trabalho</p>
      </div>
      <nav>
        <a href="#overview">Visao geral</a>
        <a href="#ai-analysis">Analise IA</a>
        <a href="#metric-guide">Guia de metricas</a>
        <a href="#flow">Fluxo</a>
        <a href="#risk">Risco</a>
        <a href="#priority">Prioridade</a>
        <a href="#dora">DORA</a>
        <a href="#discipline">Disciplina</a>
        <a href="#analysis-workflow">Analises</a>
        <a href="#fibonacci">Pontos Fibonacci</a>
        <a href="#collaborators">Colaboradores</a>
        <a href="#developers">Desenvolvedores</a>
        <a href="#reviewers">Revisores</a>
        <a href="#testers">Testers</a>
        <a href="#requesters">Solicitantes</a>
        <a href="#projects">Projetos</a>
        <a href="#sla">SLA</a>
        <a href="#bottlenecks">Gargalos</a>
        <a href="#trends">Tendencias</a>
        <a href="#quality">Qualidade</a>
        <a href="#dossier">Dossie de cards</a>
      </nav>
    </aside>
    <main class="main">
      <header class="hero">
        <div class="hero-top">
          <div>
            <h2 id="hero-title">Relatorio</h2>
            <div id="hero-board" class="hero-board"></div>
            <div class="hero-meta" id="hero-meta"></div>
          </div>
          <span class="seal-badge" id="seal-badge">Selo</span>
        </div>
      </header>
      <div class="content">
        <section class="section" id="overview">
          <div class="section-header">
            <h3>Visao geral</h3>
            <p>Indicadores principais do periodo</p>
          </div>
          <div class="kpi-grid" id="kpi-grid"></div>
          <div class="charts-grid" id="overview-charts"></div>
        </section>
        <section class="section ai-analysis-section" id="ai-analysis">
          <div class="section-header">
            <h3>Analise com IA</h3>
            <p>Interpretacao executiva gerada a partir das metricas do periodo</p>
          </div>
          <div id="ai-analysis-meta" class="ai-analysis-meta"></div>
          <div id="ai-analysis-content" class="ai-analysis-content"></div>
        </section>
        <section class="section" id="metric-guide">
          <div class="section-header">
            <h3>Guia de metricas</h3>
            <p>Calculo e exemplos para gestao</p>
          </div>
          <div id="metric-guide-content"></div>
        </section>
        <section class="section" id="flow">
          <div class="section-header">
            <h3>Fluxo</h3>
            <p>Lead time, cycle time, WIP, CFD e aging</p>
          </div>
          <div id="flow-content"></div>
        </section>
        <section class="section" id="risk">
          <div class="section-header">
            <h3>Risco</h3>
            <p>Cards que merecem atencao agora</p>
          </div>
          <div id="risk-content"></div>
        </section>
        <section class="section" id="priority">
          <div class="section-header">
            <h3>Prioridade</h3>
            <p>Urgencia, envelhecimento e furos de fila</p>
          </div>
          <div id="priority-content"></div>
        </section>
        <section class="section" id="dora">
          <div class="section-header">
            <h3>DORA adaptado</h3>
            <p>Deploys, falhas de mudanca e restauracao</p>
          </div>
          <div id="dora-content"></div>
        </section>
        <section class="section" id="discipline">
          <div class="section-header">
            <h3>Disciplina de processo</h3>
            <p>Conformidade do fluxo e preenchimento dos dados</p>
          </div>
          <div id="discipline-content"></div>
        </section>
        <section class="section" id="analysis-workflow">
          <div class="section-header">
            <h3>Cards de analise</h3>
            <p>Fluxo analise, planejamento e qualidade do registro</p>
          </div>
          <div id="analysis-workflow-content"></div>
        </section>
        <section class="section" id="fibonacci">
          <div class="section-header">
            <h3>Pontos Fibonacci</h3>
            <p>Creditados exclusivamente ao desenvolvedor do card entregue</p>
          </div>
          <div id="fibonacci-content"></div>
        </section>
        <section class="section" id="collaborators">
          <div class="section-header"><h3>Colaboradores</h3><p>Visao individual consolidada por nome</p></div>
          <div id="collaborators-content"></div>
        </section>
        <section class="section collaborator-detail-section" id="collaborator-detail" hidden>
          <div id="collaborator-detail-content"></div>
        </section>
        <section class="section" id="developers">
          <div class="section-header"><h3>Desenvolvedores</h3><p>Entregas, pontos e qualidade</p></div>
          <div id="developers-content"></div>
        </section>
        <section class="section" id="reviewers">
          <div class="section-header"><h3>Revisores</h3><p>Revisao em par e formal</p></div>
          <div id="reviewers-content"></div>
        </section>
        <section class="section" id="testers">
          <div class="section-header"><h3>Testers / Suporte</h3><p>Garantia de qualidade e retestes</p></div>
          <div id="testers-content"></div>
        </section>
        <section class="section" id="requesters">
          <div class="section-header"><h3>Solicitantes</h3><p>Demanda e planejamento</p></div>
          <div id="requesters-content"></div>
        </section>
        <section class="section" id="projects">
          <div class="section-header"><h3>Projetos / Sistemas</h3><p>Distribuicao por sistema</p></div>
          <div id="projects-content"></div>
        </section>
        <section class="section" id="sla">
          <div class="section-header"><h3>SLA</h3><p>Prazos por etapa, risco e estouro</p></div>
          <div id="sla-content"></div>
        </section>
        <section class="section" id="bottlenecks">
          <div class="section-header"><h3>Gargalos</h3><p>Tempo medio por etapa do fluxo</p></div>
          <div id="bottlenecks-content"></div>
        </section>
        <section class="section" id="trends">
          <div class="section-header"><h3>Tendencias</h3><p>Historico dos ultimos meses</p></div>
          <div id="trends-content"></div>
        </section>
        <section class="section" id="quality">
          <div class="section-header"><h3>Qualidade</h3><p>Dupla revisao e retornos</p></div>
          <div id="quality-content"></div>
        </section>
        <section class="section" id="dossier">
          <div class="section-header"><h3>Dossie de cards</h3><p>Detalhamento por pessoa</p></div>
          <div id="dossier-content"></div>
        </section>
        <footer class="report-footer">
          <p id="footer-meta"></p>
          <p class="footer-note">Tempo de fluxo em horas corridas. SLA usa horas uteis ou dias corridos conforme regra. Pontos Fibonacci: somente desenvolvedor (D-).</p>
        </footer>
      </div>
    </main>
  </div>
  <script>const METRIC_DEFS = {defs};</script>
  <script>const METRICS = {metrics_json};</script>
  <script>{js}</script>
</body>
</html>
"""

    output.write_text(html, encoding="utf-8")
    return output


def write_html_from_json_file(metrics_json_path: str | Path, output_path: str | Path) -> Path:
    path = Path(metrics_json_path)
    metrics = json.loads(path.read_text(encoding="utf-8"))
    return write_html_report(metrics, output_path)
