/* global Chart, METRICS, METRIC_DEFS */

const COLORS = {
  blue: "#2563eb",
  teal: "#0891b2",
  slate: "#64748b",
  green: "#16a34a",
  red: "#dc2626",
  orange: "#ea580c",
  purple: "#7c3aed",
  indigo: "#4f46e5",
};

const chartInstances = [];

const REPORT_LAYOUTS = {
  general: {
    sections: [
      "overview", "ai-analysis", "flow", "risk", "priority", "dora", "discipline", "analysis-workflow", "antifraud", "fibonacci",
      "collaborators", "developers", "reviewers", "formal_reviewers", "testers", "requesters", "projects",
      "sla", "bottlenecks", "trends", "quality", "dossier",
    ],
  },
  individual: {
    sections: ["overview", "ai-analysis", "dossier"],
  },
  developers: {
    sections: ["overview", "ai-analysis", "flow", "fibonacci", "developers", "sla", "quality", "dossier"],
  },
  requesters: {
    sections: ["overview", "ai-analysis", "requesters", "projects", "dossier"],
  },
  testers: {
    sections: ["overview", "ai-analysis", "testers", "quality", "dossier"],
  },
  management: {
    sections: [
      "overview", "ai-analysis", "metric-guide", "flow", "risk", "priority", "dora", "discipline",
      "analysis-workflow", "antifraud", "projects", "sla", "bottlenecks", "trends", "quality",
    ],
  },
  specific_metrics: {
    sections: null,
  },
};

function configureReportLayout() {
  const meta = METRICS.export_meta || {};
  const reportType = meta.report_type || "general";
  const layout = REPORT_LAYOUTS[reportType] || REPORT_LAYOUTS.general;
  const allowed = layout.sections;

  if (meta.title) {
    const heading = meta.title.split("|")[0].trim();
    const sidebarTitle = document.querySelector(".sidebar-brand h1");
    if (sidebarTitle) sidebarTitle.textContent = heading;
  }

  if (!allowed) return;

  document.querySelectorAll(".sidebar nav a").forEach((link) => {
    const sectionId = link.getAttribute("href").slice(1);
    const show = allowed.includes(sectionId);
    link.style.display = show ? "" : "none";
    const section = document.getElementById(sectionId);
    if (section) section.style.display = show ? "" : "none";
  });

  if (reportType !== "management") {
    const guideLink = document.querySelector('.sidebar nav a[href="#metric-guide"]');
    const guideSection = document.getElementById("metric-guide");
    if (guideLink) guideLink.style.display = "none";
    if (guideSection) guideSection.style.display = "none";
  }
}

function metricLabel(key) {
  return (METRIC_DEFS?.labels?.[key]) || String(key || "").replace(/_/g, " ");
}

function metricDescription(key) {
  return METRIC_DEFS?.descriptions?.[key] || "";
}

function tableIntro(tableId) {
  const info = METRIC_DEFS?.tables?.[tableId];
  if (!info) return "";
  const legend = (info.columns || [])
    .map((key) => {
      const desc = metricDescription(key);
      if (!desc) return "";
      return `<li><strong>${escapeHtml(metricLabel(key))}</strong>: ${escapeHtml(desc)}</li>`;
    })
    .filter(Boolean)
    .join("");
  return `
    ${info.description ? `<p class="table-description">${escapeHtml(info.description)}</p>` : ""}
    ${legend ? `<details class="metric-legend"><summary>Como ler esta tabela</summary><ul>${legend}</ul></details>` : ""}`;
}

function renderSectionGuide(sectionId) {
  const guide = METRIC_DEFS?.guides?.[sectionId];
  if (!guide) return "";
  const metrics = (guide.metrics || [])
    .map((item) => {
      const label = metricLabel(item.key);
      const formula = item.formula || metricDescription(item.key);
      const example = item.example ? `<div class="guide-example"><strong>Exemplo:</strong> ${escapeHtml(item.example)}</div>` : "";
      return `
        <li class="guide-metric">
          <strong>${escapeHtml(label)}</strong>
          <div class="guide-formula">${escapeHtml(formula)}</div>
          ${example}
        </li>`;
    })
    .join("");
  return `
    <div class="metric-guide-block">
      <h4>${escapeHtml(guide.title || sectionId)}</h4>
      ${guide.description ? `<p class="table-description">${escapeHtml(guide.description)}</p>` : ""}
      ${metrics ? `<ol class="metric-guide-list">${metrics}</ol>` : ""}
    </div>`;
}

function renderManagementGuide() {
  const reportType = METRICS.export_meta?.report_type;
  const container = document.getElementById("metric-guide-content");
  if (!container || reportType !== "management") {
    if (container) container.closest(".section")?.remove();
    return;
  }

  const intro = METRIC_DEFS?.guides?.management_intro;
  const sections = [
    "team_summary", "flow", "dora", "direct_production", "sla", "process_discipline",
    "analysis_workflow", "priority", "risk", "bottlenecks", "quality_gates",
  ];
  container.innerHTML = `
    <div class="metric-guide-intro">
      <h4>${escapeHtml(intro?.title || "Guia de metricas")}</h4>
      ${intro?.description ? `<p class="table-description">${escapeHtml(intro.description)}</p>` : ""}
    </div>
    ${sections.map((id) => renderSectionGuide(id)).join("")}`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function attrEscape(value) {
  return escapeHtml(value);
}

const TASK_LEVELS = [1, 2, 3, 5, 8, 13];
const ANALYSIS_LEVELS = [1, 2, 3];

function pct(value) {
  const num = Number(value);
  return Number.isFinite(num) ? `${num}%` : "-";
}

function sealClass(seal) {
  const normalized = String(seal || "").toLowerCase();
  if (normalized.includes("ouro")) return "ouro";
  if (normalized.includes("prata")) return "prata";
  if (normalized.includes("atenc")) return "atencao";
  return "";
}

function ratePill(value, invert) {
  const num = Number(value);
  if (!Number.isFinite(num)) return '<span class="pill neutral">-</span>';
  const good = invert ? num <= 20 : num >= 80;
  const mid = invert ? num <= 50 : num >= 50;
  const cls = good ? "ok" : mid ? "warn" : "bad";
  return `<span class="pill ${cls}">${pct(num)}</span>`;
}

function kpi(label, value, sub, accent) {
  return `
    <div class="kpi-card accent-${accent}">
      <div class="label">${escapeHtml(label)}</div>
      <div class="value">${escapeHtml(value)}</div>
      ${sub ? `<div class="sub">${escapeHtml(sub)}</div>` : ""}
    </div>`;
}

function table(headers, rows) {
  if (!rows.length) {
    return '<div class="empty-state">Sem dados para este periodo.</div>';
  }
  const head = headers.map((h) => `<th>${escapeHtml(h)}</th>`).join("");
  const body = rows
    .map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join("")}</tr>`)
    .join("");
  return `
    <div class="data-table-wrap">
      <table class="data-table">
        <thead><tr>${head}</tr></thead>
        <tbody>${body}</tbody>
      </table>
    </div>`;
}

function chartCard(id, title) {
  return `
    <div class="chart-card">
      <h4>${escapeHtml(title)}</h4>
      <canvas id="${id}"></canvas>
    </div>`;
}

function makeChart(id, config) {
  const canvas = document.getElementById(id);
  if (!canvas) return;
  const instance = new Chart(canvas, config);
  chartInstances.push(instance);
}

function defaultOptions(title) {
  return {
    responsive: true,
    maintainAspectRatio: true,
    plugins: {
      legend: { position: "bottom", labels: { boxWidth: 12, padding: 14 } },
      title: { display: false, text: title },
    },
  };
}

function processTable(processes) {
  const rows = processes || [];
  return table(
    ["Processo", "Tempo total", "Media", "Visitas", "Cards"],
    rows.map((p) => [
      escapeHtml(p.title || p.group || "-"),
      escapeHtml(formatDurationFull(p.total_hours, p.total_human || `${p.total_hours ?? 0}h`)),
      escapeHtml(formatDurationFull(p.avg_hours, p.avg_human || "-")),
      p.visits ?? 0,
      p.cards ?? 0,
    ]),
  );
}

function roleMetricValue(role, key, fallback = 0) {
  return role && role[key] != null ? role[key] : fallback;
}

const ROLE_DETAIL_METRICS = {
  solicitante: [
    ["Cards ativos", "cards_active"],
    ["Cards criados", "cards_created"],
    ["Cards entregues", "requester_delivered"],
    ["Em producao", "in_production"],
    ["Planejamento ok", "planning_ok_rate_pct", "pct"],
    ["Tempo total", "time_human"],
    ["Tempo medio", "avg_time_human"],
    ["Visitas em processos", "visits"],
  ],
  desenvolvedor: [
    ["Cards ativos", "cards_active"],
    ["Cards entregues", "cards_delivered"],
    ["Pontos normais", "fibonacci_normal"],
    ["Pontos analise", "fibonacci_analysis"],
    ["Pontos totais", "fibonacci_total"],
    ["Retornos DEV penalizados", "return_dev_count"],
    ["Problemas pegos no teste", "tester_quality_returns"],
    ["Cards com retrabalho", "cards_with_rework"],
    ["Taxa de retrabalho", "rework_rate_pct", "pct"],
    ["Taxa de qualidade", "quality_rate_pct", "pct"],
    ["Aceitacao sem retorno", "acceptance_rate_pct", "pct"],
    ["Sugestoes aceitas (par)", "suggestions_accepted"],
    ["Dupla revisao obrigatoria", "double_review_mandatory_total"],
    ["Violacoes dupla revisao", "double_review_mandatory_violations"],
    ["Tempo total", "time_human"],
    ["Tempo medio", "avg_time_human"],
    ["Visitas em processos", "visits"],
  ],
  revisor_par: [
    ["Cards ativos", "cards_active"],
    ["Cards entregues", "cards_delivered"],
    ["Revisoes feitas", "reviews_done"],
    ["Aprovadas", "approved"],
    ["Sugestoes aceitas", "suggestions_accepted"],
    ["Taxa de sugestoes", "suggestion_rate_pct", "pct"],
    ["Escapes (revisao/teste)", "escaped_to_test"],
    ["Taxa de aprovacao", "approval_rate_pct", "pct"],
    ["Tempo total", "time_human"],
    ["Tempo medio", "avg_time_human"],
    ["Visitas em processos", "visits"],
  ],
  revisor: [
    ["Cards ativos", "cards_active"],
    ["Cards entregues", "cards_delivered"],
    ["Revisoes formais", "formal_reviews_done"],
    ["Revisoes concluidas", "formal_review_passed"],
    ["Retornos atribuidos a revisao", "review_return_events"],
    ["Escapes no teste", "escaped_to_test"],
    ["Taxa de aprovacao", "approval_rate_pct", "pct"],
    ["Tempo total", "time_human"],
    ["Tempo medio", "avg_time_human"],
    ["Visitas em processos", "visits"],
  ],
  tester: [
    ["Cards ativos", "cards_active"],
    ["Cards entregues", "cards_delivered"],
    ["Cards testados", "cards_tested"],
    ["Aprovados 1a passagem", "approved_first_pass"],
    ["Problemas evitados", "prevented_problems"],
    ["Retornos indevidos", "undue_test_returns"],
    ["Taxa indevidos (%)", "undue_return_rate_pct", "pct"],
    ["Sem motivo", "returns_missing_reason"],
    ["Retestes", "retest_cycles_total"],
    ["Tempo total", "time_human"],
    ["Tempo medio", "avg_time_human"],
    ["Visitas em processos", "visits"],
  ],
};

function metricDisplay(value, kind) {
  if (kind === "pct") return pct(value);
  return escapeHtml(value ?? "-");
}

function renderRoleMetricTable(role) {
  const metrics = ROLE_DETAIL_METRICS[role.role_key] || [];
  return table(
    ["Metrica", "Valor"],
    metrics.map(([label, key, kind]) => {
      let value = roleMetricValue(role, key, "-");
      if (key === "time_human") {
        value = formatDurationFull(role.time_hours, role.time_human || "-");
      }
      if (key === "avg_time_human") {
        value = formatDurationFull(role.avg_time_hours, role.avg_time_human || "-");
      }
      return [
        escapeHtml(label),
        metricDisplay(value, kind),
      ];
    }),
  );
}

function renderHero() {
  const board = METRICS.board || {};
  const period = METRICS.period || {};
  const team = METRICS.team_summary || {};
  const month = period.month || "Periodo completo";
  const generated = (board.generated_at || "").slice(0, 10);

  const meta = METRICS.export_meta || {};
  const customTitle = (meta.title || "").split("|")[0].trim();
  document.getElementById("hero-title").textContent = customTitle || `Relatorio ${month}`;
  document.getElementById("hero-board").textContent = board.name || "Quadro Trello";
  document.getElementById("hero-meta").textContent =
    `Gerado em ${generated || "-"} · ${team.cards_delivered ?? 0} cards entregues · pontos so para desenvolvedor`;

  const seal = team.quality_seal || "Sem dados";
  const badge = document.getElementById("seal-badge");
  badge.textContent = `Selo ${seal}`;
  badge.className = `seal-badge ${sealClass(seal)}`;

  const footer = document.getElementById("footer-meta");
  if (footer) {
    footer.textContent = `${board.name || "Quadro Trello"} · ${month} · export processado em ${generated || "-"}`;
  }
}

function renderOverview() {
  const reportType = METRICS.export_meta?.report_type || "general";
  if (reportType === "individual" && METRICS.individual_summary) {
    renderIndividualOverview();
    return;
  }
  if (METRICS.role_summary) {
    renderRoleOverview();
    return;
  }

  const team = METRICS.team_summary || {};
  const fib = METRICS.fibonacci_points?.team || team;
  const overview = METRICS.overview || {};
  const grid = document.getElementById("kpi-grid");

  grid.innerHTML = [
    kpi("Cards entregues", team.cards_delivered ?? 0, "No periodo", "primary"),
    kpi("Pontos Fibonacci", fib.points_total ?? team.fibonacci_total ?? 0,
      `${fib.points_normal ?? team.fibonacci_normal ?? 0} normais + ${fib.points_analysis ?? team.fibonacci_analysis ?? 0} analise`, "purple"),
    kpi("Taxa de qualidade", pct(team.quality_rate_pct),
      `${team.cards_with_rework_count ?? 0} com retrabalho`, "success"),
    kpi("Retrabalho", pct(team.rework_rate_pct),
      `${team.total_return_dev_events ?? 0} retornos DEV penalizados`, "warning"),
    kpi("Problemas evitados", team.total_prevented_problems ?? team.total_tester_quality_returns ?? 0,
      `${team.test_returns_missing_reason_count ?? 0} sem motivo`, "success"),
    kpi("Devs ativos", team.active_developers ?? 0,
      `${overview.total_cards_metricados ?? 0} cards metricados · ${overview.total_placeholders_ignorados ?? 0} controle`, "primary"),
  ].join("");

  const charts = document.getElementById("overview-charts");
  charts.innerHTML = [
    chartCard("chart-executive", "Resumo executivo"),
    chartCard("chart-quality", "Qualidade vs retrabalho"),
  ].join("");

  makeChart("chart-executive", {
    type: "bar",
    data: {
      labels: ["Pontos normais", "Pontos analise", "Cards"],
      datasets: [{
        data: [
          fib.points_normal ?? team.fibonacci_normal ?? 0,
          fib.points_analysis ?? team.fibonacci_analysis ?? 0,
          team.cards_delivered ?? 0,
        ],
        backgroundColor: [COLORS.blue, COLORS.teal, COLORS.slate],
        borderRadius: 8,
      }],
    },
    options: {
      ...defaultOptions(),
      scales: { y: { beginAtZero: true, grid: { color: "#f1f5f9" } }, x: { grid: { display: false } } },
    },
  });

  makeChart("chart-quality", {
    type: "doughnut",
    data: {
      labels: ["Qualidade", "Retrabalho"],
      datasets: [{
        data: [team.quality_rate_pct ?? 0, team.rework_rate_pct ?? 0],
        backgroundColor: [COLORS.green, COLORS.red],
        borderWidth: 0,
      }],
    },
    options: {
      ...defaultOptions(),
      cutout: "62%",
    },
  });
}

function statValue(stat, key, fallback = "-") {
  if (!stat) return fallback;
  const value = stat[key];
  return value == null ? fallback : value;
}

function statDuration(stat, key, humanKey) {
  if (!stat) return "-";
  const hours = stat[key];
  const human = stat[humanKey];
  if (hours == null) return "-";
  return formatDurationFull(hours, human || "-");
}

function riskPill(level) {
  if (level === "critico") return '<span class="pill bad">Critico</span>';
  if (level === "alto") return '<span class="pill warn">Alto</span>';
  if (level === "medio") return '<span class="pill neutral">Medio</span>';
  return '<span class="pill ok">Baixo</span>';
}

function agingStatusPill(status) {
  if (status === "above_p85") return '<span class="pill bad">Acima P85</span>';
  if (status === "above_p50") return '<span class="pill warn">Acima P50</span>';
  return '<span class="pill ok">Ok</span>';
}

function renderIndividualOverview() {
  const summary = METRICS.individual_summary || {};
  const grid = document.getElementById("kpi-grid");
  grid.innerHTML = [
    kpi("Colaborador", summary.name ?? METRICS.individual_target ?? "-", (summary.roles || []).join(", "), "primary"),
    kpi("Cards entregues", summary.cards_delivered ?? 0, `${summary.cards_active ?? 0} ativos`, "success"),
    kpi("Pontos Fibonacci", summary.fibonacci_total ?? 0,
      `${summary.fibonacci_normal ?? 0} normais + ${summary.fibonacci_analysis ?? 0} analise`, "purple"),
    kpi("Tempo de atuacao", summary.time_human ?? "-", "No periodo", "warning"),
  ].join("");
  document.getElementById("overview-charts").innerHTML = "";
}

function renderRoleOverview() {
  const summary = METRICS.role_summary || {};
  const grid = document.getElementById("kpi-grid");
  const cards = [];
  if (summary.scope === "developers") {
    cards.push(
      kpi("Desenvolvedores", summary.people_count ?? 0, "No periodo", "primary"),
      kpi("Cards entregues", summary.cards_delivered ?? 0, "Pelo time dev", "success"),
      kpi("Pontos totais", (summary.fibonacci_normal ?? 0) + (summary.fibonacci_analysis ?? 0),
        `${summary.fibonacci_normal ?? 0} normais + ${summary.fibonacci_analysis ?? 0} analise`, "purple"),
      kpi("Qualidade", pct(summary.quality_rate_pct), pct(summary.rework_rate_pct) + " retrabalho", "warning"),
    );
  } else if (summary.scope === "requesters") {
    cards.push(
      kpi("Solicitantes", summary.people_count ?? 0, "No periodo", "primary"),
      kpi("Cards criados", summary.cards_created ?? 0, `${summary.cards_delivered ?? 0} entregues`, "success"),
      kpi("Em producao", summary.in_production ?? 0, "Agora", "warning"),
      kpi("Planejamento ok", pct(summary.avg_planning_ok_pct), "Media do time", "purple"),
    );
  } else if (summary.scope === "testers") {
    cards.push(
      kpi("Testers", summary.people_count ?? 0, "No periodo", "primary"),
      kpi("Cards testados", summary.cards_tested ?? 0, `${summary.approved_first_pass ?? 0} na 1a passagem`, "success"),
      kpi("Problemas evitados", summary.prevented_problems ?? 0, "Retornos ao DEV", "warning"),
      kpi("Retestes", summary.retest_cycles_total ?? 0, "Total no periodo", "purple"),
    );
  } else {
    cards.push(
      kpi("Metricas selecionadas", (summary.selected_metrics || []).length, "Secoes incluidas", "primary"),
    );
  }
  grid.innerHTML = cards.join("");
  document.getElementById("overview-charts").innerHTML = "";
}

function renderFlow() {
  const flow = METRICS.flow || {};
  const team = flow.team || {};
  const efficiency = team.flow_efficiency || {};
  const stages = flow.stage_time || [];
  const aging = flow.aging_wip || [];
  const wip = flow.wip_by_stage || [];
  const cfd = flow.cfd || [];
  const container = document.getElementById("flow-content");
  if (!container) return;

  if (!Object.keys(flow).length) {
    container.innerHTML = '<div class="empty-state">Sem metricas de fluxo para este periodo.</div>';
    return;
  }

  container.innerHTML = `
    ${tableIntro("flow_team")}
    ${renderSectionGuide("flow")}
    <div class="kpi-grid">
      ${kpi("Lead time P85", statDuration(team.lead_time, "p85_hours", "p85_human"), `${statValue(team.lead_time, "samples", 0)} entrega(s)`, "primary")}
      ${kpi("Cycle time P85", statDuration(team.cycle_time, "p85_hours", "p85_human"), "1a entrada em desenvolvimento ate entrega", "primary")}
      ${kpi("Eficiencia de fluxo", pct(efficiency.efficiency_pct), `${formatDurationFull(efficiency.work_hours, efficiency.work_human || "-")} trabalho`, "success")}
      ${kpi("WIP atual", team.wip_total ?? 0, `Little: ${team.little_law_predicted_lead_time_days ?? "-"} dia(s)`, "warning")}
      ${kpi("Planej. -> aprovacao", statDuration(team.planning_to_approval_time, "p85_hours", "p85_human"), "P85 da primeira movimentacao", "purple")}
    </div>
    <div class="charts-grid">
      ${chartCard("chart-cfd", "CFD diario")}
      ${chartCard("chart-stage-time", "Tempo por etapa")}
    </div>
    <div class="two-col">
      <div class="panel">${table(
        ["Etapa", "WIP"],
        wip.map((row) => [escapeHtml(row.title), row.count ?? 0]),
      )}</div>
      <div class="panel">${table(
        ["Etapa", "Mediana", "P85", "P95", "Amostras"],
        stages.map((row) => [
          escapeHtml(row.title),
          statDuration(row, "median_hours", "median_human"),
          statDuration(row, "p85_hours", "p85_human"),
          statDuration(row, "p95_hours", "p95_human"),
          row.samples ?? 0,
        ]),
      )}</div>
    </div>
    <div class="panel">${table(
      ["Card", "Etapa atual", "Idade", "P50", "P85", "Status", "Prioridade"],
      aging.map((row) => [
        row.url ? `<a href="${attrEscape(row.url)}" target="_blank" rel="noreferrer">${escapeHtml(row.card_name)}</a>` : escapeHtml(row.card_name),
        escapeHtml(row.title || row.list_name || "-"),
        escapeHtml(formatDurationFull(row.age_hours, row.age_human || "-")),
        escapeHtml(formatDurationFull(row.p50_hours, row.p50_human || "-")),
        escapeHtml(formatDurationFull(row.p85_hours, row.p85_human || "-")),
        agingStatusPill(row.status),
        escapeHtml(row.prioridade || "-"),
      ]),
    )}</div>
    ${(() => {
      const baseline = flow.aging_baseline || [];
      const rework = team.rework_ratio || {};
      const blocked = team.blocked_time || {};
      const net = flow.net_flow || {};
      const ftr = METRICS.first_time_right || {};
      const peer = ftr.peer_review || {};
      const testing = ftr.testing || {};
      const member = METRICS.member_assignment || {};
      const moves = METRICS.board_moves || {};
      return `
        <div class="panel">${table(
          ["Etapa", "P50", "P85", "P95", "Amostras"],
          baseline.map((row) => [
            escapeHtml(row.title || "-"),
            escapeHtml(row.p50_human || "-"),
            escapeHtml(row.p85_human || "-"),
            escapeHtml(row.p95_human || "-"),
            row.samples ?? 0,
          ]),
        )}</div>
        <div class="kpi-grid">
          ${kpi("Rework ratio", pct(rework.team_rework_ratio_pct), "Horas em retorno_dev / fluxo", "warning")}
          ${kpi("Blocked P85", statDuration(blocked, "p85_hours", "p85_human"), "Pausa + retorno suporte", "warning")}
          ${kpi("Net flow 4sem", net.avg_net_last_4_weeks ?? "-", net.alert_wip_rising ? "WIP subindo" : "Estavel", net.alert_wip_rising ? "danger" : "success")}
          ${kpi("FTR teste", pct(testing.pct), `Peer ${pct(peer.pct)}`, "success")}
          ${kpi("Inconsist. membros", pct(member.inconsistent_pct), "Campo vs idMembers", "warning")}
          ${kpi("Board in/out", `${moves.cards_in ?? 0}/${moves.cards_out ?? 0}`, "Movimentacao entre boards", "purple")}
        </div>`;
    })()}`;

  if (cfd.length) {
    const stageNames = [...new Set(cfd.flatMap((row) => Object.keys(row).filter((key) => key !== "date")))];
    const palette = [COLORS.blue, COLORS.teal, COLORS.orange, COLORS.purple, COLORS.green, COLORS.indigo, COLORS.slate, COLORS.red];
    makeChart("chart-cfd", {
      type: "line",
      data: {
        labels: cfd.map((row) => row.date),
        datasets: stageNames.map((stage, index) => ({
          label: stage,
          data: cfd.map((row) => row[stage] || 0),
          borderColor: palette[index % palette.length],
          backgroundColor: `${palette[index % palette.length]}33`,
          fill: true,
          tension: 0.25,
        })),
      },
      options: {
        ...defaultOptions(),
        scales: { y: { beginAtZero: true, stacked: true }, x: { grid: { display: false } } },
      },
    });
  }

  const stageRows = stages.slice().sort((a, b) => (b.p85_hours || 0) - (a.p85_hours || 0)).slice(0, 10);
  makeChart("chart-stage-time", {
    type: "bar",
    data: {
      labels: stageRows.map((row) => row.title),
      datasets: [
        { label: "Mediana", data: stageRows.map((row) => row.median_hours || 0), backgroundColor: COLORS.blue, borderRadius: 4 },
        { label: "P85", data: stageRows.map((row) => row.p85_hours || 0), backgroundColor: COLORS.orange, borderRadius: 4 },
      ],
    },
    options: { indexAxis: "y", ...defaultOptions(), scales: { x: { beginAtZero: true } } },
  });
}

function renderRiskBoard() {
  const risk = METRICS.risk_board || {};
  const attention = risk.cards_that_need_attention || [];
  const rows = risk.cards || [];
  const container = document.getElementById("risk-content");
  if (!container) return;

  container.innerHTML = `
    <div class="kpi-grid">
      ${kpi("Alto/critico", risk.high_or_critical_count ?? 0, "Cards abertos com risco", "warning")}
      ${kpi("Cards avaliados", rows.length, "WIP aberto", "primary")}
    </div>
    <div class="panel">${table(
      ["Card", "Risco", "Score", "Etapa", "Idade", "Prioridade", "Motivos"],
      (attention.length ? attention : rows).map((row) => [
        row.url ? `<a href="${attrEscape(row.url)}" target="_blank" rel="noreferrer">${escapeHtml(row.card_name)}</a>` : escapeHtml(row.card_name),
        riskPill(row.level),
        row.score ?? 0,
        escapeHtml(row.current_stage || "-"),
        escapeHtml(formatDurationFull(row.age_hours, row.age_human || "-")),
        escapeHtml(row.prioridade || "-"),
        escapeHtml((row.reasons || []).join(", ") || "-"),
      ]),
    )}</div>`;
}

function renderPriority() {
  const priority = METRICS.priority || {};
  const leadRows = priority.lead_time_by_priority || [];
  const jumps = priority.queue_jumps || [];
  const urgentAging = priority.urgent_aging || [];
  const container = document.getElementById("priority-content");
  if (!container) return;

  container.innerHTML = `
    <div class="kpi-grid">
      ${kpi("Urgente/Critica", pct(priority.urgent_critical_pct), priority.priority_inflation_alert ? "Alerta de inflacao" : "Distribuicao saudavel", priority.priority_inflation_alert ? "warning" : "success")}
      ${kpi("Furos de fila", priority.queue_jumps_count ?? 0, "Menor prioridade antes de maior", "warning")}
      ${kpi("Urgentes envelhecendo", priority.urgent_aging_count ?? 0, "Acima de P50/P85", "danger")}
    </div>
    <div class="two-col">
      <div class="panel">${table(
        ["Prioridade", "Mediana LT", "P85", "P95", "Amostras"],
        leadRows.map((row) => [
          escapeHtml(row.priority),
          statDuration(row, "median_hours", "median_human"),
          statDuration(row, "p85_hours", "p85_human"),
          statDuration(row, "p95_hours", "p95_human"),
          row.samples ?? 0,
        ]),
      )}</div>
      <div class="panel">${table(
        ["Prioridade", "Cards"],
        (priority.distribution || []).map((row) => [escapeHtml(row.priority), row.count ?? 0]),
      )}</div>
    </div>
    <div class="panel">${table(
      ["Entregue antes", "Prioridade", "Maior prioridade aguardou", "Prioridade"],
      jumps.map((item) => [
        escapeHtml(item.delivered_first?.card_name || "-"),
        escapeHtml(item.delivered_first?.priority || "-"),
        escapeHtml(item.higher_priority_waited?.card_name || "-"),
        escapeHtml(item.higher_priority_waited?.priority || "-"),
      ]),
    )}</div>
    <div class="panel">${table(
      ["Urgente envelhecendo", "Etapa", "Idade", "Status"],
      urgentAging.map((row) => [
        row.url ? `<a href="${attrEscape(row.url)}" target="_blank" rel="noreferrer">${escapeHtml(row.card_name)}</a>` : escapeHtml(row.card_name),
        escapeHtml(row.title || "-"),
        escapeHtml(formatDurationFull(row.age_hours, row.age_human || "-")),
        agingStatusPill(row.status),
      ]),
    )}</div>`;
}

function renderDora() {
  const dora = METRICS.dora || {};
  const frequency = dora.deployment_frequency || {};
  const byPath = frequency.by_path || {};
  const container = document.getElementById("dora-content");
  if (!container) return;

  container.innerHTML = `
    ${tableIntro("dora")}
    ${renderSectionGuide("dora")}
    ${dora.note ? `<p class="table-description">${escapeHtml(dora.note)}</p>` : ""}
    <div class="kpi-grid">
      ${kpi("Deploys", frequency.total ?? 0, "Em producao + direto", "primary")}
      ${kpi("Fluxo normal", byPath.standard_production ?? 0, "Em producao", "success")}
      ${kpi("Direto prod.", byPath.direct_production ?? 0, "Sem homolog/teste", "warning")}
      ${kpi("LT deploy P85", statDuration(dora.lead_time_deploy, "p85_hours", "p85_human"), "Aguardando producao ate deploy", "purple")}
    </div>
    <div class="kpi-grid">
      ${kpi("LT deploy mediana", statDuration(dora.lead_time_deploy, "median_hours", "median_human"), "Lead time de mudanca", "primary")}
      ${kpi("LT deploy P95", statDuration(dora.lead_time_deploy, "p95_hours", "p95_human"), "Cauda longa", "danger")}
    </div>
    <div class="two-col">
      <div class="panel">${table(
        ["Semana", "Deploys"],
        Object.entries(frequency.by_week || {}).map(([week, count]) => [escapeHtml(week), count]),
      )}</div>
      <div class="panel">${table(
        ["Sistema", "Deploys"],
        (frequency.by_system || []).map((row) => [escapeHtml(row.sistema || "-"), row.count ?? 0]),
      )}</div>
    </div>`;
}

function renderProcessDiscipline() {
  const discipline = METRICS.process_discipline || {};
  const conformity = discipline.flow_conformity || {};
  const assignment = discipline.developer_assignment_latency || {};
  const container = document.getElementById("discipline-content");
  if (!container) return;

  container.innerHTML = `
    ${tableIntro("process_discipline")}
    ${renderSectionGuide("process_discipline")}
    <div class="kpi-grid">
      ${kpi("Conformidade", pct(conformity.compliance_pct), `${conformity.compliant_count ?? 0} de ${conformity.cards_evaluated ?? 0}`, "success")}
      ${kpi("Cards sem nivel", (discipline.cards_without_level || []).length, "Impedem velocity", "warning")}
      ${kpi("Latencia dev P85", statDuration(assignment, "p85_hours", "p85_human"), `${assignment.developer_assignment_events ?? 0} atribuicao(oes)`, "purple")}
    </div>
    <div class="panel">${table(
      ["Etapa", "Campos completos", "Cards", "Pendencias"],
      (discipline.required_fields_by_stage || []).map((row) => [
        escapeHtml(row.title),
        ratePill(row.completion_pct, false),
        row.cards_evaluated ?? 0,
        (row.missing || []).length,
      ]),
    )}</div>
    <div class="two-col">
      <div class="panel">${table(
        ["Etapa pulada", "Opcional", "Cards"],
        (discipline.skipped_stages || []).map((row) => [
          escapeHtml(row.title),
          row.optional ? '<span class="pill neutral">Opcional</span>' : '<span class="pill warn">Core</span>',
          row.count ?? 0,
        ]),
      )}</div>
      <div class="panel">${table(
        ["Card sem nivel", "Dev", "Sistema"],
        (discipline.cards_without_level || []).map((row) => [
          escapeHtml(row.card_name),
          escapeHtml(row.desenvolvedor || "-"),
          escapeHtml(row.sistema || "-"),
        ]),
      )}</div>
    </div>
    <div class="panel">${table(
      ["Violacao", "Problemas"],
      (conformity.violations || []).map((row) => [
        escapeHtml(row.card_name),
        escapeHtml((row.issues || []).join(", ") || "-"),
      ]),
    )}</div>
    ${(discipline.post_terminal_returns?.count || 0) > 0 ? `<div class="panel"><h4>Retornos apos producao/analise finalizada</h4><p class="table-description">${escapeHtml(discipline.post_terminal_returns.note || "")}</p>${table(
      ["Card", "ID", "Terminal", "Problema"],
      (discipline.post_terminal_returns.cards || []).map((row) => [
        escapeHtml(row.card_name || "-"),
        `<code class="ai-code">${escapeHtml(row.card_id || "-")}</code>`,
        escapeHtml(row.terminal_group || "-"),
        "Retorno apos entrega — abrir novo card",
      ]),
    )}</div>` : ""}`;
}

function renderAnalysisWorkflow() {
  const block = METRICS.analysis_workflow || {};
  const container = document.getElementById("analysis-workflow-content");
  if (!container) return;

  container.innerHTML = `
    ${tableIntro("analysis_workflow")}
    ${renderSectionGuide("analysis_workflow")}
    ${block.note ? `<p class="table-description">${escapeHtml(block.note)}</p>` : ""}
    <div class="kpi-grid">
      ${kpi("Entregues", block.analysis_delivered ?? 0, "Analises finalizadas", "success")}
      ${kpi("Ativos", block.cards_active_in_period ?? 0, "Com atividade no periodo", "primary")}
      ${kpi("Em planejamento", block.analysis_in_planning_wip ?? 0, "WIP solicitante", "warning")}
      ${kpi("Descricao ok", pct(block.descricao_completa_pct), `${block.descricao_completa_count ?? 0} cards`, "purple")}
    </div>
    <div class="kpi-grid">
      ${kpi("Retorno DEV", block.returned_to_dev_count ?? 0, "Qualidade do registro", "danger")}
      ${kpi("Pos-terminal", block.post_terminal_return_count ?? 0, "Violacao de processo", "danger")}
      ${kpi("Espera planej. P85", statDuration(block.planning_wait, "p85_hours", "p85_human"), "Analises para planejamento", "warning")}
    </div>
    <div class="two-col">
      <div class="panel">${table(
        ["Desenvolvedor", "Cards"],
        (block.by_developer || []).map((row) => [escapeHtml(row.name || "-"), row.count ?? 0]),
      )}</div>
      <div class="panel">${table(
        ["Solicitante", "Cards"],
        (block.by_solicitante || []).map((row) => [escapeHtml(row.name || "-"), row.count ?? 0]),
      )}</div>
    </div>
    <div class="panel">${table(
      ["Card", "ID", "Dev", "Solicitante", "Flags"],
      (block.highlight_cards || []).map((row) => [
        escapeHtml(row.card_name || "-"),
        `<code class="ai-code">${escapeHtml(row.card_id || "-")}</code>`,
        escapeHtml(row.desenvolvedor || "-"),
        escapeHtml(row.solicitante || "-"),
        escapeHtml((row.flags || []).join(", ") || "-"),
      ]),
    )}</div>`;
}

function formatPoints(value) {
  if (value == null || value === "" || value === 0) return "—";
  return value;
}

function renderFibonacci() {
  const block = METRICS.fibonacci_points || {};
  const team = block.team || {};
  const rows = block.by_developer || [];
  const container = document.getElementById("fibonacci-content");
  if (!container) return;

  if (!rows.length) {
    container.innerHTML = '<div class="empty-state">Sem pontos Fibonacci no periodo.</div>';
    return;
  }

  container.innerHTML = `
    <p class="points-policy">${escapeHtml(block.policy || "Pontos creditados ao desenvolvedor.")}</p>
    <div class="points-breakdown">
      <div class="points-breakdown-item">
        <div class="label">Cards normais</div>
        <div class="value">${team.cards_normal ?? 0}</div>
        <div class="sub">${team.points_normal ?? 0} pontos</div>
      </div>
      <div class="points-breakdown-item">
        <div class="label">Cards analise</div>
        <div class="value">${team.cards_analysis ?? 0}</div>
        <div class="sub">${team.points_analysis ?? 0} pontos</div>
      </div>
      <div class="points-breakdown-item">
        <div class="label">Total equipe</div>
        <div class="value">${team.points_total ?? 0}</div>
        <div class="sub">${team.cards_total ?? 0} cards entregues</div>
      </div>
    </div>
    <div class="charts-grid">${chartCard("chart-fibonacci", "Distribuicao por desenvolvedor")}</div>
    <div class="panel">${table(
      ["Desenvolvedor", "Cards normais", "Pts normais", "Cards analise", "Pts analise", "Total pts"],
      [
        ...rows.map((d) => [
          escapeHtml(d.developer),
          d.cards_normal,
          d.points_normal,
          d.cards_analysis,
          d.points_analysis,
          d.points_total,
        ]),
        [
          "<strong>Total equipe</strong>",
          team.cards_normal ?? 0,
          team.points_normal ?? 0,
          team.cards_analysis ?? 0,
          team.points_analysis ?? 0,
          `<strong>${team.points_total ?? 0}</strong>`,
        ],
      ],
    )}</div>`;

  const top = rows.slice(0, 12);
  makeChart("chart-fibonacci", {
    type: "bar",
    data: {
      labels: top.map((d) => d.developer.replace(/^D-/, "")),
      datasets: [
        { label: "Normais", data: top.map((d) => d.points_normal), backgroundColor: COLORS.blue, borderRadius: 3 },
        { label: "Analise", data: top.map((d) => d.points_analysis), backgroundColor: COLORS.teal, borderRadius: 3 },
      ],
    },
    options: {
      ...defaultOptions(),
      scales: { x: { stacked: true, grid: { display: false } }, y: { stacked: true, beginAtZero: true } },
    },
  });
}

function renderCollaborators() {
  const rows = METRICS.collaborators || [];
  const container = document.getElementById("collaborators-content");

  if (!rows.length) {
    container.innerHTML = '<div class="empty-state">Sem dados de colaboradores para este periodo.</div>';
    return;
  }

  container.innerHTML = `
    ${tableIntro("collaborators")}
    <p class="section-note">Pontos Fibonacci aparecem apenas para quem atuou como desenvolvedor (D-). Revisores, testers e solicitantes nao acumulam pontos.</p>
    <div class="charts-grid">
      ${chartCard("chart-collab-points", "Pontos por desenvolvedor")}
      ${chartCard("chart-collab-time", "Tempo de atuacao por colaborador")}
    </div>
    <div class="panel">${table(
      ["Nome", "Papeis", "Ativos", "Entregues", "Pts (dev)", "Tempo", "Detalhes"],
      rows.map((c) => [
        `<strong>${escapeHtml(c.name)}</strong>`,
        escapeHtml((c.roles || []).join(", ") || "-"),
        c.summary?.cards_active ?? 0,
        c.summary?.cards_delivered ?? 0,
        c.summary?.has_developer_points ? (c.summary?.fibonacci_total ?? 0) : "—",
        escapeHtml(formatDurationFull(c.summary?.time_hours, c.summary?.time_human || "-")),
        `<button type="button" class="btn-expand collab-open" data-collab-id="${attrEscape(c.id)}">Abrir</button>`,
      ]),
    )}</div>`;

  const top = rows.filter((c) => c.summary?.has_developer_points).slice(0, 10);
  if (top.length) {
    makeChart("chart-collab-points", {
    type: "bar",
    data: {
      labels: top.map((c) => c.name),
      datasets: [
        { label: "Normais", data: top.map((c) => c.summary?.fibonacci_normal ?? 0), backgroundColor: COLORS.blue, borderRadius: 4 },
        { label: "Analise", data: top.map((c) => c.summary?.fibonacci_analysis ?? 0), backgroundColor: COLORS.teal, borderRadius: 4 },
      ],
    },
    options: {
      ...defaultOptions(),
      scales: { x: { stacked: true, grid: { display: false } }, y: { stacked: true, beginAtZero: true } },
    },
  });
  }

  makeChart("chart-collab-time", {
    type: "bar",
    data: {
      labels: top.map((c) => c.name),
      datasets: [{
        label: "Horas",
        data: top.map((c) => c.summary?.time_hours ?? 0),
        backgroundColor: COLORS.orange,
        borderRadius: 4,
      }],
    },
    options: {
      indexAxis: "y",
      ...defaultOptions(),
      scales: { x: { beginAtZero: true } },
    },
  });
}

function findCollaborator(id) {
  return (METRICS.collaborators || []).find((collab) => collab.id === id);
}

function roleMetricCards(role) {
  const cards = [
    kpi("Cards ativos", roleMetricValue(role, "cards_active"), "No periodo", "primary"),
    kpi("Cards entregues", roleMetricValue(role, "cards_delivered"), "Entregas do periodo", "success"),
  ];

  if (role.role_key === "desenvolvedor") {
    cards.push(kpi("Pts normais", roleMetricValue(role, "fibonacci_normal"), "Cards problema", "purple"));
    cards.push(kpi("Pts analise", roleMetricValue(role, "fibonacci_analysis"), "Cards analise", "purple"));
    cards.push(kpi("Pts totais", roleMetricValue(role, "fibonacci_total"), "Soma", "purple"));
  }

  cards.push(kpi("Tempo", formatDurationFull(role.time_hours, role.time_human || "-"), "Processos do papel", "warning"));

  if (role.role_key === "desenvolvedor") {
    cards.push(kpi("Qualidade", pct(role.quality_rate_pct), `${role.cards_with_rework ?? 0} com retrabalho`, "success"));
  }
  if (role.role_key === "tester") {
    cards.push(kpi("Problemas evitados", role.prevented_problems ?? role.returned_dev_for_quality ?? 0, `${role.returns_missing_reason ?? 0} sem motivo`, "success"));
    cards.push(kpi("Retornos indevidos", role.undue_test_returns ?? 0, pct(role.undue_return_rate_pct), "danger"));
  }
  if (role.role_key === "solicitante") {
    cards.push(kpi("Planejamento ok", pct(role.planning_ok_rate_pct), `${role.requester_delivered ?? 0} entregues`, "success"));
  }
  if (role.role_key === "revisor_par" || role.role_key === "revisor") {
    cards.push(kpi("Aprovacao", pct(role.approval_rate_pct), "Revisoes do periodo", "success"));
  }

  return cards.join("");
}

function renderRoleDetails(roles) {
  if (!roles || !roles.length) return "";
  return roles.map((role) => `
    <div class="collab-role-block">
      <h4>${escapeHtml(role.role_label)}</h4>
      <div class="kpi-grid">${roleMetricCards(role)}</div>
      <div class="collab-detail-grid">
        <div class="panel">${renderRoleMetricTable(role)}</div>
        <div class="panel">${processTable(role.process_times || [])}</div>
      </div>
    </div>`).join("");
}

function renderCollaboratorDetail(collab) {
  const section = document.getElementById("collaborator-detail");
  const container = document.getElementById("collaborator-detail-content");
  if (!collab) {
    section.hidden = true;
    container.innerHTML = "";
    return;
  }

  const summary = collab.summary || {};
  section.hidden = false;
  container.innerHTML = `
    <div class="collab-detail-header">
      <div>
        <div class="dossier-section-title">Relatorio individual</div>
        <h3>${escapeHtml(collab.name)}</h3>
        <p>${escapeHtml((collab.roles || []).join(", ") || "-")}</p>
      </div>
      <div class="dossier-actions">
        <button type="button" class="btn-expand btn-muted collab-back">Voltar</button>
        <button type="button" class="btn-expand collab-print" data-collab-id="${attrEscape(collab.id)}">Exportar PDF</button>
      </div>
    </div>
    <div class="kpi-grid">
      ${kpi("Cards ativos", summary.cards_active ?? 0, "Com participacao no periodo", "primary")}
      ${kpi("Cards entregues", summary.cards_delivered ?? 0, "Cards unicos", "success")}
      ${summary.has_developer_points
        ? kpi("Pts totais", summary.fibonacci_total ?? 0, `${summary.fibonacci_normal ?? 0} normais + ${summary.fibonacci_analysis ?? 0} analise`, "purple")
        : kpi("Pts Fibonacci", "—", "Sem papel de desenvolvedor", "purple")}
      ${kpi("Tempo de atuacao", formatDurationFull(summary.time_hours, summary.time_human || "-"), "Soma dos processos atribuidos", "warning")}
    </div>
    <div class="collab-detail-grid">
      <div class="panel">${processTable(collab.process_times || [])}</div>
      <div class="panel collab-aliases">
        <h4>Identificadores</h4>
        <div>${(collab.aliases || []).map((alias) => `<span class="pill neutral">${escapeHtml(alias)}</span>`).join("")}</div>
      </div>
    </div>
    ${renderRoleDetails(collab.role_metrics || [])}
    <div class="dossier-section-title">Cards</div>
    <div class="dossier-cards">
      ${(collab.cards || []).map((card) => renderCardBlock(card, { collaborator: true })).join("") || '<div class="empty-state">Nenhum card para este colaborador.</div>'}
    </div>`;
}

function openCollaboratorDetail(id, pushHash = true) {
  const collab = findCollaborator(id);
  renderCollaboratorDetail(collab);
  if (collab && pushHash) {
    history.pushState(null, "", `#colaborador/${encodeURIComponent(id)}`);
  }
  if (collab) {
    document.getElementById("collaborator-detail").scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

function expandCollaboratorCards() {
  document
    .querySelectorAll("#collaborator-detail .card-item")
    .forEach((item) => {
      item.open = true;
    });
}

function setupCollaboratorActions() {
  document.addEventListener("click", (event) => {
    const openBtn = event.target.closest(".collab-open");
    if (openBtn) {
      openCollaboratorDetail(openBtn.dataset.collabId);
      return;
    }

    if (event.target.closest(".collab-back")) {
      renderCollaboratorDetail(null);
      history.pushState(null, "", "#collaborators");
      document.getElementById("collaborators").scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }

    const printBtn = event.target.closest(".collab-print");
    if (printBtn) {
      const collab = findCollaborator(printBtn.dataset.collabId);
      renderCollaboratorDetail(collab);
      expandCollaboratorCards();
      document.body.classList.add("print-collaborator");
      window.print();
      window.setTimeout(() => document.body.classList.remove("print-collaborator"), 300);
    }
  });

  window.addEventListener("popstate", () => {
    const match = location.hash.match(/^#colaborador\/(.+)$/);
    if (match) {
      renderCollaboratorDetail(findCollaborator(decodeURIComponent(match[1])));
    } else {
      renderCollaboratorDetail(null);
    }
  });
}

function renderInitialCollaboratorRoute() {
  const match = location.hash.match(/^#colaborador\/(.+)$/);
  if (match) {
    renderCollaboratorDetail(findCollaborator(decodeURIComponent(match[1])));
  }
}

function renderDevelopers() {
  const profiles = (METRICS.developer_profiles || []).filter((d) => d.cards_delivered > 0);
  const devs = profiles.length ? profiles : (METRICS.developers || []).filter((d) => d.cards_delivered > 0);
  const container = document.getElementById("developers-content");

  container.innerHTML = `
    ${tableIntro("developers")}
    <p class="section-note">Tempos corridos (24h) a partir da saida de PLANEJAMENTO. Tempo em planejamento fica visivel no dossie, mas nao entra em atuacao/espera do dev.</p>
    <div class="charts-grid">
      ${chartCard("chart-dev-points", "Pontos por desenvolvedor")}
      ${chartCard("chart-dev-flow", "Atuacao vs espera no pipeline")}
    </div>
    <div class="panel">${table(
      [
        "Desenvolvedor",
        "Entregues",
        "Pts",
        "Atuacao dev",
        "Espera pipeline",
        "% espera",
        "Retrabalho",
        "Qualidade",
      ],
      devs.map((d) => [
        escapeHtml(d.name),
        d.cards_delivered,
        d.fibonacci_total,
        escapeHtml(d.dev_work_hours_human || d.avg_dev_work_human || "-"),
        escapeHtml(d.pipeline_wait_hours_human || d.avg_pipeline_wait_human || "-"),
        `${d.pipeline_wait_ratio_pct ?? 0}%`,
        ratePill(d.rework_rate_pct, true),
        ratePill(d.quality_rate_pct, false),
      ]),
    )}</div>
    <div id="developer-profiles"></div>`;

  const top = devs.slice(0, 10);
  makeChart("chart-dev-points", {
    type: "bar",
    data: {
      labels: top.map((d) => d.name.replace(/^D-/, "")),
      datasets: [
        { label: "Normais", data: top.map((d) => d.fibonacci_normal), backgroundColor: COLORS.blue, borderRadius: 4 },
        { label: "Analise", data: top.map((d) => d.fibonacci_analysis), backgroundColor: COLORS.teal, borderRadius: 4 },
      ],
    },
    options: {
      ...defaultOptions(),
      scales: { x: { stacked: true, grid: { display: false } }, y: { stacked: true, beginAtZero: true } },
    },
  });

  makeChart("chart-dev-flow", {
    type: "bar",
    data: {
      labels: top.map((d) => d.name.replace(/^D-/, "")),
      datasets: [
        { label: "Atuacao (dev)", data: top.map((d) => d.dev_work_hours_total ?? d.avg_dev_work_hours ?? 0), backgroundColor: COLORS.green, borderRadius: 4 },
        { label: "Espera pipeline", data: top.map((d) => d.pipeline_wait_hours_total ?? d.avg_pipeline_wait_hours ?? 0), backgroundColor: COLORS.orange, borderRadius: 4 },
      ],
    },
    options: {
      ...defaultOptions(),
      scales: { x: { stacked: true, grid: { display: false } }, y: { stacked: true, beginAtZero: true } },
    },
  });

  const profilesRoot = document.getElementById("developer-profiles");
  if (!profiles.length) return;

  profilesRoot.innerHTML = profiles
    .map((dev) => {
      const cards = dev.cards || [];
      const cardRows = cards.map((card) => [
        escapeHtml(card.card_name),
        escapeHtml(card.sistema),
        card.kind === "analysis" ? `A${card.fibonacci_level ?? "-"}` : `N${card.fibonacci_level ?? "-"}`,
        escapeHtml(card.dev_work_human || "-"),
        escapeHtml(card.pipeline_wait_human || "-"),
        `${card.pipeline_wait_ratio_pct ?? 0}%`,
        escapeHtml(card.cycle_time_human || "-"),
        card.tester_quality_returns > 0
          ? '<span class="pill warn">Pego no teste</span>'
          : (card.return_dev_count > 0
            ? '<span class="pill warn">Retorno dev</span>'
            : '<span class="pill ok">Ok</span>'),
      ]);
      return `
        <div class="dev-profile panel" id="dev-${escapeHtml(dev.name).replace(/[^a-zA-Z0-9_-]/g, "_")}">
          <div class="dev-profile-header">
            <div>
              <h4>${escapeHtml(dev.name)}</h4>
              <p class="dossier-subtitle">
                ${dev.cards_delivered} entrega(s) · ${dev.fibonacci_total} pts ·
                atuacao ${escapeHtml(dev.dev_work_hours_human)} · espera ${escapeHtml(dev.pipeline_wait_hours_human)}
              </p>
            </div>
            <a class="btn-expand" href="#dossier">Ver dossie</a>
          </div>
          ${table(
            ["Card", "Sistema", "Nivel", "Atuacao dev", "Espera", "% espera", "Ciclo", "Status"],
            cardRows,
          )}
        </div>`;
    })
    .join("");
}

function renderReviewers() {
  const rows = METRICS.reviewers || [];
  const el = document.getElementById("reviewers-content");
  if (!el) return;
  el.innerHTML = `
    ${tableIntro("reviewers")}
    <div class="panel">${table(
      ["Nome", "Revisoes", "Sugestoes aceitas", "% sugestoes", "Sem escape", "Escapes", "Taxa", "Tempo medio"],
      rows.map((r) => [
        escapeHtml(r.name),
        r.reviews_done,
        r.suggestions_accepted ?? r.sent_back ?? 0,
        ratePill(r.suggestion_rate_pct ?? 0, false),
        r.approved,
        r.escaped_to_test ?? 0,
        ratePill(r.approval_rate_pct, false),
        escapeHtml(r.avg_review_human || "-"),
      ]),
    )}</div>`;
}

function renderFormalReviewers() {
  const rows = METRICS.formal_reviewers || [];
  const el = document.getElementById("formal-reviewers-content");
  if (!el) return;
  el.innerHTML = `
    ${tableIntro("formal_reviewers")}
    <div class="panel">${table(
      ["Nome", "Revisoes", "Aprovadas", "Retornos", "Escapes teste", "Taxa", "Tempo medio"],
      rows.map((r) => [
        escapeHtml(r.name),
        r.formal_reviews_done,
        r.formal_review_passed,
        r.review_return_events ?? 0,
        r.escaped_to_test ?? 0,
        ratePill(r.approval_rate_pct, false),
        escapeHtml(r.avg_review_human || "-"),
      ]),
    )}</div>`;
}

function renderTesters() {
  const rows = METRICS.testers || [];
  const container = document.getElementById("testers-content");

  container.innerHTML = `
    ${tableIntro("testers")}
    <div class="charts-grid">${chartCard("chart-testers", "Performance de testes")}</div>
    <div class="panel">${table(
      ["Nome", "Testados", "1a passagem", "Problemas evitados", "Indevidos", "Sem motivo", "Retestes"],
      rows.map((t) => [
        escapeHtml(t.name),
        t.cards_tested ?? t.tests_started ?? 0,
        t.approved_first_pass ?? 0,
        t.prevented_problems ?? t.returned_dev_for_quality ?? t.returned_dev ?? 0,
        t.undue_test_returns ?? 0,
        t.returns_missing_reason ?? 0,
        t.retest_cycles_total ?? 0,
      ]),
    )}</div>`;

  if (rows.length) {
    makeChart("chart-testers", {
      type: "bar",
      data: {
        labels: rows.map((t) => t.name.replace(/^T-/, "")),
        datasets: [
          { label: "1a passagem", data: rows.map((t) => t.approved_first_pass ?? 0), backgroundColor: COLORS.green, borderRadius: 4 },
          { label: "Problemas evitados", data: rows.map((t) => t.prevented_problems ?? t.returned_dev_for_quality ?? 0), backgroundColor: COLORS.orange, borderRadius: 4 },
          { label: "Retornos indevidos", data: rows.map((t) => t.undue_test_returns ?? 0), backgroundColor: COLORS.red, borderRadius: 4 },
        ],
      },
      options: {
        ...defaultOptions(),
        scales: { x: { stacked: true, grid: { display: false } }, y: { stacked: true, beginAtZero: true } },
      },
    });
  }
}

function renderRequesters() {
  const rows = METRICS.requesters || [];
  document.getElementById("requesters-content").innerHTML = `
    ${tableIntro("requesters")}
    <div class="panel">${table(
      ["Nome", "Criados", "Entregues", "Em producao", "Planejamento ok", "Aprovacao media"],
      rows.map((r) => [
        escapeHtml(r.name),
        r.cards_created,
        r.cards_delivered,
        r.in_production,
        ratePill(r.planning_ok_rate_pct, false),
        escapeHtml(r.avg_approval_human || "-"),
      ]),
    )}</div>`;
}

function renderProjects() {
  const rows = METRICS.projects || [];
  const container = document.getElementById("projects-content");

  container.innerHTML = `
    ${tableIntro("projects")}
    <div class="charts-grid">${chartCard("chart-projects", "Pontos por projeto")}</div>
    <div class="panel">${table(
      ["Sistema", "Cards", "Pts normais", "Pts analise", "Top dev"],
      rows.map((p) => [
        escapeHtml(p.name),
        p.cards_delivered,
        p.fibonacci_normal,
        p.fibonacci_analysis,
        escapeHtml(p.top_developer || "-"),
      ]),
    )}</div>`;

  if (rows.length) {
    makeChart("chart-projects", {
      type: "bar",
      data: {
        labels: rows.map((p) => p.name),
        datasets: [
          { label: "Normais", data: rows.map((p) => p.fibonacci_normal), backgroundColor: COLORS.purple, borderRadius: 4 },
          { label: "Analise", data: rows.map((p) => p.fibonacci_analysis), backgroundColor: COLORS.indigo, borderRadius: 4 },
        ],
      },
      options: {
        ...defaultOptions(),
        scales: { x: { stacked: true, grid: { display: false } }, y: { stacked: true, beginAtZero: true } },
      },
    });
  }
}

function slaStatusPill(status) {
  if (status === "estourado") return '<span class="pill bad">Estourado</span>';
  if (status === "em_risco") return '<span class="pill warn">Em risco</span>';
  return '<span class="pill ok">No prazo</span>';
}

function renderSla() {
  const sla = METRICS.sla || {};
  const team = sla.team || {};
  const stages = sla.by_stage || [];
  const developers = sla.by_developer || [];
  const cards = sla.cards || [];
  const alerts = sla.current_alerts || [];
  const container = document.getElementById("sla-content");
  if (!container) return;

  if (!Object.keys(sla).length) {
    container.innerHTML = '<div class="empty-state">Sem regras de SLA configuradas.</div>';
    return;
  }

  container.innerHTML = `
    ${tableIntro("sla_team")}
    ${renderSectionGuide("sla")}
    <div class="kpi-grid">
      ${kpi("Cumprimento SLA", pct(team.compliance_pct), `${team.stage_checks ?? 0} etapa(s) avaliadas`, "success")}
      ${kpi("Estouradas", team.breached_count ?? 0, `${team.cards_evaluated ?? 0} card(s) avaliados`, "warning")}
      ${kpi("Em risco agora", team.current_at_risk_count ?? 0, "Etapa atual acima de 80%", "warning")}
      ${kpi("Estouradas agora", team.current_breached_count ?? 0, "Etapa atual fora do prazo", "warning")}
    </div>
    <p class="section-note">${escapeHtml(sla.policy?.note || "SLA conforme regras do workflow.")}</p>
    ${alerts.length ? `<div class="panel">${table(
      ["Card", "Etapa atual", "Uso", "SLA", "Status"],
      alerts.map((item) => [
        item.url ? `<a href="${attrEscape(item.url)}" target="_blank" rel="noreferrer">${escapeHtml(item.card_name)}</a>` : escapeHtml(item.card_name),
        escapeHtml(item.title || item.current_list || "-"),
        `${escapeHtml(item.elapsed_human || "-")} (${item.usage_pct ?? 0}%)`,
        escapeHtml(item.limit_human || "-"),
        slaStatusPill(item.status),
      ]),
    )}</div>` : ""}
    <div class="charts-grid">${chartCard("chart-sla-stage", "Cumprimento por etapa")}</div>
    ${tableIntro("sla_by_stage")}
    <div class="panel">${table(
      ["Etapa", "SLA", "Avaliadas", "Estouradas", "Cumprimento", "Media usada"],
      stages.map((stage) => [
        escapeHtml(stage.title),
        escapeHtml(stage.sla_human || "-"),
        stage.checks ?? 0,
        stage.breached_count ?? 0,
        ratePill(stage.compliance_pct, false),
        escapeHtml(stage.avg_elapsed_human || "-"),
      ]),
    )}</div>
    ${tableIntro("sla_developers")}
    <div class="panel">${table(
      ["Desenvolvedor", "Cards", "Etapas", "Estouradas", "Cards com estouro", "Cumprimento"],
      developers.map((dev) => [
        escapeHtml(dev.name),
        dev.cards_evaluated ?? 0,
        dev.stage_checks ?? 0,
        dev.breached_count ?? 0,
        dev.breached_cards ?? 0,
        ratePill(dev.compliance_pct, false),
      ]),
    )}</div>
    <div class="panel">${table(
      ["Card", "Dev", "Nível", "Pior etapa", "Uso máx.", "Etapas", "Estouradas", "Cumprimento"],
      cards.map((card) => [
        escapeHtml(card.card_name),
        escapeHtml(card.desenvolvedor || "-"),
        card.fibonacci_level ?? "-",
        escapeHtml(card.worst_stage || "-"),
        `${card.worst_usage_pct ?? 0}%`,
        card.stage_checks ?? 0,
        card.breached_count ?? 0,
        ratePill(card.compliance_pct, false),
      ]),
    )}</div>`;

  const chartRows = stages.slice(0, 10);
  makeChart("chart-sla-stage", {
    type: "bar",
    data: {
      labels: chartRows.map((stage) => stage.title),
      datasets: [{
        label: "% no prazo",
        data: chartRows.map((stage) => stage.compliance_pct ?? 0),
        backgroundColor: COLORS.green,
        borderRadius: 6,
      }],
    },
    options: {
      indexAxis: "y",
      ...defaultOptions(),
      scales: { x: { beginAtZero: true, max: 100 } },
    },
  });
}

function renderBottlenecks() {
  const stages = (METRICS.bottlenecks || {}).by_stage || [];
  const active = stages.filter((s) => (s.avg_hours ?? 0) > 0);
  const rows = active.length ? active : stages.slice(0, 8);
  const container = document.getElementById("bottlenecks-content");
  const top = (METRICS.bottlenecks || {}).top_bottleneck;

  container.innerHTML = `
    ${tableIntro("bottlenecks")}
    ${renderSectionGuide("bottlenecks")}
    ${top ? `<p style="margin:0 0 1rem;color:var(--muted);font-size:0.9rem">
      Maior gargalo: <strong>${escapeHtml(top.title)}</strong> (${escapeHtml(top.avg_human || "-")} em media)
    </p>` : ""}
    <div class="charts-grid">${chartCard("chart-bottlenecks", "Tempo medio por etapa")}</div>
    <div class="panel">${table(
      ["Etapa", "Media", "Mediana", "P95", "Amostras"],
      rows.map((s) => [
        escapeHtml(s.title),
        escapeHtml(s.avg_human || `${s.avg_hours}h`),
        escapeHtml(s.median_hours != null ? `${s.median_hours}h` : "-"),
        escapeHtml(s.p95_hours != null ? `${s.p95_hours}h` : "-"),
        s.samples ?? 0,
      ]),
    )}</div>`;

  makeChart("chart-bottlenecks", {
    type: "bar",
    data: {
      labels: rows.map((s) => s.title),
      datasets: [{
        label: "Horas medias",
        data: rows.map((s) => s.avg_hours ?? 0),
        backgroundColor: COLORS.orange,
        borderRadius: 6,
      }],
    },
    options: {
      indexAxis: "y",
      ...defaultOptions(),
      scales: { x: { beginAtZero: true } },
    },
  });
}

function renderTrends() {
  const trends = METRICS.trends_6m || {};
  const teamRows = trends.team || [];
  const container = document.getElementById("trends-content");

  if (!teamRows.length) {
    container.innerHTML = '<div class="empty-state">Historico insuficiente para tendencias.</div>';
    return;
  }

  container.innerHTML = `
    <div class="charts-grid">
      ${chartCard("chart-trends-team", "Pontos ao longo do tempo")}
      ${chartCard("chart-trends-quality", "Qualidade e retrabalho")}
      ${chartCard("chart-trends-devs", "Pontos por desenvolvedor")}
    </div>`;

  const months = teamRows.map((r) => r.month);
  makeChart("chart-trends-team", {
    type: "line",
    data: {
      labels: months,
      datasets: [
        { label: "Normais", data: teamRows.map((r) => r.fibonacci_normal), borderColor: COLORS.blue, tension: 0.3 },
        { label: "Analise", data: teamRows.map((r) => r.fibonacci_analysis), borderColor: COLORS.teal, tension: 0.3 },
      ],
    },
    options: defaultOptions(),
  });

  makeChart("chart-trends-quality", {
    type: "line",
    data: {
      labels: months,
      datasets: [
        { label: "Qualidade (%)", data: teamRows.map((r) => r.quality_rate_pct ?? 0), borderColor: COLORS.green, tension: 0.3 },
        { label: "Retrabalho (%)", data: teamRows.map((r) => r.rework_rate_pct ?? 0), borderColor: COLORS.red, tension: 0.3 },
      ],
    },
    options: {
      ...defaultOptions(),
      scales: { y: { min: 0, max: 100 } },
    },
  });

  const devTrends = trends.developers || {};
  const devDatasets = Object.entries(devTrends)
    .slice(0, 6)
    .map(([name, series], index) => {
      const palette = [COLORS.blue, COLORS.teal, COLORS.purple, COLORS.orange, COLORS.green, COLORS.indigo];
      const normal = series.fibonacci_normal || [];
      const analysis = series.fibonacci_analysis || [];
      const total = normal.map((v, i) => v + (analysis[i] || 0));
      return {
        label: name.replace(/^[DRPST]-/, ""),
        data: total,
        borderColor: palette[index % palette.length],
        tension: 0.3,
      };
    })
    .filter((ds) => ds.data.some((v) => v > 0));

  if (devDatasets.length) {
    makeChart("chart-trends-devs", {
      type: "line",
      data: { labels: trends.months || months, datasets: devDatasets },
      options: defaultOptions(),
    });
  }
}

function renderAntifraud() {
  const block = METRICS.antifraud || {};
  const container = document.getElementById("antifraud-content");
  if (!container) return;
  const summary = block.summary || {};
  const alerts = (block.alerts || []).filter((item) => item.score === "high" || item.score === "medium");
  if (!block.summary && !(block.alerts || []).length) {
    container.innerHTML = '<div class="empty-state">Sem dados de antifraude neste relatorio.</div>';
    return;
  }
  container.innerHTML = `
    ${tableIntro("antifraud")}
    ${renderSectionGuide("antifraud")}
    <div class="kpi-grid">
      ${kpi("Copias no periodo", summary.copies_in_period ?? 0, null, "primary")}
      ${kpi("Whitelist template", summary.whitelisted_copies_count ?? block.whitelisted_copies_count ?? 0, null, "teal")}
      ${kpi("Alertas high", summary.high_count ?? 0, null, "danger")}
      ${kpi("Alertas medium", summary.medium_count ?? 0, null, "warning")}
    </div>
    ${alerts.length ? `
      <div class="panel" style="padding:1rem;margin-top:1rem;overflow:auto">
        <table>
          <thead>
            <tr>
              <th>Score</th><th>Card novo</th><th>ID</th><th>Fonte</th>
              <th>Status fonte</th><th>Terminal?</th><th>Destino</th><th>Autor</th>
            </tr>
          </thead>
          <tbody>
            ${alerts.slice(0, 40).map((item) => {
              const lineage = item.source_lineage || {};
              return `<tr>
                <td>${escapeHtml(item.score || "")}</td>
                <td>${escapeHtml(item.card_name || "")}</td>
                <td><code>${escapeHtml(item.card_id || "")}</code></td>
                <td>${escapeHtml(item.source_card_name || "")}</td>
                <td>${escapeHtml(lineage.status || "")}</td>
                <td>${lineage.passed_terminal ? "Sim" : "Nao"}</td>
                <td>${escapeHtml(item.dest_list || "")}</td>
                <td>${escapeHtml(item.actor_name || "")}</td>
              </tr>`;
            }).join("")}
          </tbody>
        </table>
      </div>
      <div class="panel" style="padding:1rem;margin-top:1rem">
        ${alerts.slice(0, 12).map((item) => {
          const lineage = item.source_lineage || {};
          const groups = (lineage.groups_visited || []).join(", ") || "-";
          const lastList = lineage.last_list_at_dispose || lineage.last_list_at_delete || lineage.last_list_at_copy || "-";
          const secs = lineage.seconds_copy_to_dispose ?? lineage.seconds_copy_to_delete;
          const visits = lineage.visits || [];
          const visitsTable = visits.length ? `
            <div style="overflow:auto;margin-top:0.5rem">
              <table>
                <thead><tr><th>Quando</th><th>Evento</th><th>Lista</th><th>Grupo</th><th>Quem</th><th>Apos copia?</th></tr></thead>
                <tbody>
                  ${visits.map((visit) => `<tr>
                    <td>${escapeHtml(visit.at || "-")}</td>
                    <td>${escapeHtml(visit.event_type || "-")}</td>
                    <td>${escapeHtml(visit.list_name || "-")}</td>
                    <td>${escapeHtml(visit.group || "-")}</td>
                    <td>${escapeHtml(visit.actor_name || "-")}</td>
                    <td>${visit.after_copy ? "Sim" : "Nao"}</td>
                  </tr>`).join("")}
                </tbody>
              </table>
            </div>` : '<div class="empty-state" style="margin-top:0.5rem">Sem movimentacoes residuais alem da exclusao/arquivamento/copia.</div>';
          return `<details style="margin-bottom:0.85rem" ${item.score === "high" ? "open" : ""}>
            <summary><strong>${escapeHtml(item.score || "")}</strong> · ${escapeHtml(item.card_name || "")}
            · <code>${escapeHtml(item.card_id || "")}</code></summary>
            <div style="margin-top:0.5rem">
              ${escapeHtml(item.reason || "")}<br/>
              <span style="opacity:0.8">Status: ${escapeHtml(lineage.status || "")} · ultima coluna: ${escapeHtml(lastList)} · copia→descarte: ${escapeHtml(String(secs ?? "-"))}s · grupos: ${escapeHtml(groups)}</span>
              ${lineage.recovery_note ? `<br/><em>${escapeHtml(lineage.recovery_note)}</em>` : ""}
              ${visitsTable}
            </div>
          </details>`;
        }).join("")}
      </div>` : '<div class="empty-state">Nenhum alerta high/medium no periodo.</div>'}`;
}

function renderQuality() {
  const gates = METRICS.quality_gates || {};
  const team = METRICS.team_summary || {};
  document.getElementById("quality-content").innerHTML = `
    ${tableIntro("quality_gates")}
    ${renderSectionGuide("quality_gates")}
    <div class="kpi-grid">
      ${kpi("Dupla rev. obrigatoria", `${gates.mandatory_compliance_pct ?? 100}%`,
        `${gates.mandatory_violations_count ?? 0} violacoes de ${gates.mandatory_total ?? 0}`, "primary")}
      ${kpi("Dupla rev. recomendada", `${gates.recommended_done_pct ?? 0}%`,
        `${gates.recommended_done_count ?? 0} de ${gates.recommended_total ?? 0}`, "purple")}
      ${kpi("Retorno DEV penalizado", pct(team.return_dev_rate_pct),
        `${team.total_return_dev_events ?? 0} evento(s) penalizado(s)`, "warning")}
      ${kpi("Problemas evitados", team.total_prevented_problems ?? team.total_tester_quality_returns ?? 0,
        `${team.test_returns_missing_reason_count ?? 0} sem motivo`, "success")}
    </div>
    ${(gates.mandatory_violations || []).length ? `
      <div class="panel" style="padding:1rem;margin-top:1rem">
        <strong>Violacoes de dupla revisao:</strong>
        <ul style="margin:0.5rem 0 0;padding-left:1.25rem">
          ${gates.mandatory_violations.map((v) => `<li>${escapeHtml(v)}</li>`).join("")}
        </ul>
      </div>` : ""}`;
}

const DESCRICAO_LABELS = {
  cliente: "Cliente",
  solicitacao: "Solicitacao",
  solucao_dev: "Solucao do desenvolvedor",
  obs_revisor_par: "Observacoes do revisor em par",
  obs_revisor: "Observacoes do revisor",
  obs_tester: "Observacoes do tester",
  observacoes_gerais: "Observacoes gerais",
  solicitacao_analise: "Solicitacao da analise",
  analise_realizada: "Analise realizada",
  recomendacao: "Recomendacao",
  analise_origem: "Analise que originou",
};

const DESCRICAO_ORDER = [
  "cliente",
  "solicitacao",
  "solicitacao_analise",
  "solucao_dev",
  "obs_revisor_par",
  "obs_revisor",
  "obs_tester",
  "analise_realizada",
  "recomendacao",
  "analise_origem",
  "observacoes_gerais",
];

function renderDescricao(descricao) {
  if (!descricao || !Object.keys(descricao).length) {
    return "";
  }
  const blocks = DESCRICAO_ORDER.filter((key) => descricao[key])
    .concat(Object.keys(descricao).filter((key) => !DESCRICAO_ORDER.includes(key)))
    .map((key) => `
      <div class="obs-block">
        <div class="obs-label">${escapeHtml(DESCRICAO_LABELS[key] || key)}</div>
        <div class="obs-text">${escapeHtml(descricao[key])}</div>
      </div>`)
    .join("");
  return `<div class="obs-section"><div class="obs-section-title">Descricao do card</div>${blocks}</div>`;
}

function dossierGroupHeader(name, groupId, subtitle) {
  return `
    <div class="dossier-group-header">
      <div>
        <h4>${escapeHtml(name)}</h4>
        ${subtitle ? `<p class="dossier-subtitle">${escapeHtml(subtitle)}</p>` : ""}
      </div>
      <div class="dossier-actions">
        <button type="button" class="btn-expand" data-group="${groupId}" data-action="expand">Expandir todos</button>
        <button type="button" class="btn-expand btn-muted" data-group="${groupId}" data-action="collapse">Recolher todos</button>
      </div>
    </div>`;
}

function formatShortDate(iso) {
  if (!iso) return "-";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "-";
  return date.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatDurationFull(hours, fallback = "-") {
  const value = Number(hours);
  if (!Number.isFinite(value)) return fallback;

  let totalSeconds = Math.max(0, Math.round(value * 3600));
  const days = Math.floor(totalSeconds / 86400);
  totalSeconds -= days * 86400;
  const hoursPart = Math.floor(totalSeconds / 3600);
  totalSeconds -= hoursPart * 3600;
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds - minutes * 60;
  return `${days}d ${String(hoursPart).padStart(2, "0")}h ${String(minutes).padStart(2, "0")}m ${String(seconds).padStart(2, "0")}s`;
}

function aggregateStagesByList(stages) {
  const grouped = new Map();
  (stages || []).forEach((stage, index) => {
    const key = stage.list_name || stage.title || stage.group || `stage-${index}`;
    if (!grouped.has(key)) {
      grouped.set(key, {
        group: stage.group,
        title: stage.title,
        list_name: stage.list_name,
        hours: 0,
        start_at: stage.start_at,
        end_at: stage.end_at,
        visits: 0,
        first_index: index,
      });
    }
    const row = grouped.get(key);
    row.hours += Number(stage.hours || 0);
    row.visits += 1;
    if (!row.start_at || (stage.start_at && new Date(stage.start_at) < new Date(row.start_at))) {
      row.start_at = stage.start_at;
    }
    if (!row.end_at || (stage.end_at && new Date(stage.end_at) > new Date(row.end_at))) {
      row.end_at = stage.end_at;
    }
  });
  return [...grouped.values()].sort((a, b) => a.first_index - b.first_index);
}

function collaboratorStages(card) {
  const stages = (card.collaborator_involvements || [])
    .flatMap((item) => item.stages || []);
  return aggregateStagesByList(stages);
}

function renderStageTimeline(etapas, options = {}) {
  if (!etapas || !etapas.length) {
    return "";
  }
  const totalHours = etapas.reduce((sum, step) => sum + (step.hours || 0), 0);
  const aggregated = options.aggregated === true;
  const title = options.title || "Etapas do fluxo";
  const maxHours = Math.max(...etapas.map((step) => Number(step.hours || 0)));
  const rows = etapas
    .map((step, index) => {
      const isLongest = maxHours > 0 && Number(step.hours || 0) === maxHours;
      const classes = [
        step.excluded_from_flow_metrics ? "stage-pre-flow" : "",
        isLongest ? "stage-longest" : "",
      ].filter(Boolean).join(" ");
      return `
      <tr class="${classes}">
        <td>${index + 1}</td>
        <td><strong>${escapeHtml(step.title)}</strong>${isLongest ? ' <span class="pill warn">maior tempo</span>' : ""}${step.excluded_from_flow_metrics ? ' <span class="pill neutral">fora das metricas</span>' : ""}</td>
        <td>${escapeHtml(step.list_name)}</td>
        <td>${escapeHtml(formatDurationFull(step.hours, step.hours_human || "-"))}</td>
        ${aggregated ? `<td>${step.visits ?? 1}</td>` : ""}
        <td>${formatShortDate(step.start_at)}</td>
        <td>${formatShortDate(step.end_at)}</td>
      </tr>`;
    })
    .join("");
  return `
    <div class="obs-section stage-section">
      <div class="obs-section-title">${escapeHtml(title)} (${escapeHtml(String(etapas.length))} coluna(s) · ${escapeHtml(formatDurationFull(totalHours))} total)</div>
      <div class="stage-table-wrap">
        <table class="stage-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Etapa</th>
              <th>Lista</th>
              <th>Tempo</th>
              ${aggregated ? "<th>Mov.</th>" : ""}
              <th>Inicio</th>
              <th>Fim</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    </div>`;
}

function renderCollaboratorInvolvements(card) {
  const involvements = card.collaborator_involvements || [];
  if (!involvements.length) return "";
  const rows = involvements.map((item) => {
    const stages = aggregateStagesByList(item.stages || [])
      .map((stage) => {
        const visits = (stage.visits ?? 1) > 1 ? ` (${stage.visits} mov.)` : "";
        return `<span class="pill neutral">${escapeHtml(stage.list_name || stage.title)}: ${escapeHtml(formatDurationFull(stage.hours, stage.hours_human || "-"))}${escapeHtml(visits)}</span>`;
      })
      .join("");
    return `
      <div class="collab-involvement-row">
        <div>
          <strong>${escapeHtml(item.role_label)}</strong>
          <span>${escapeHtml(item.alias || "")}</span>
        </div>
        <div class="collab-involvement-time">${escapeHtml(formatDurationFull(item.time_hours, item.time_human || "-"))}</div>
        <div class="collab-stage-pills">${stages || '<span class="pill neutral">Sem tempo registrado</span>'}</div>
      </div>`;
  }).join("");
  return `
    <div class="obs-section collab-involvement">
      <div class="obs-section-title">Atuacao do colaborador (${escapeHtml(formatDurationFull(card.collaborator_time_hours, card.collaborator_time_human || "-"))})</div>
      ${rows}
    </div>`;
}

function renderCardBlock(card, options = {}) {
  const filterable = options.filterable === true;
  const collaboratorView = options.collaborator === true;
  const kindLabel = card.kind === "analysis" ? "Analise" : "Tarefa";
  const dataAttrs = filterable
    ? ` data-kind="${attrEscape(card.kind)}" data-level="${card.fibonacci_level ?? ""}" data-sistema="${attrEscape(card.sistema)}"`
    : "";
  const retornos = (card.retornos || [])
    .map((r) => {
      const tipo = r.tipo === "dev" ? "DEV" : "SUP";
      const sub = r.subtipo ? ` (${r.subtipo})` : "";
      const undue = r.is_undue_test_return || r.kind === "undue";
      const solucaoLabel = undue ? "Solução de retorno indevido" : "Solucao";
      return `
        <div class="retorno-item${undue ? " undue" : ""}">
          <strong>Retorno ${r.numero} (${tipo})${escapeHtml(sub)}${undue ? " · Indevido" : ""}</strong>
          <div>${escapeHtml(r.motivo || "Sem motivo registrado")}</div>
          <div class="attr">${solucaoLabel}: ${escapeHtml(r.solucao || "-")} · Atribuido: ${escapeHtml(r.atribuido_a || "-")}</div>
        </div>`;
    })
    .join("");

  const undueSolutions = (card.undue_return_solutions || [])
    .map((item) => `
        <div class="retorno-item undue">
          <strong>Solução de retorno indevido${item.numero != null ? ` #${item.numero}` : ""}</strong>
          <div>${escapeHtml(item.motivo || "Sem motivo registrado")}</div>
          <div class="attr">${escapeHtml(item.solucao || "-")}</div>
        </div>`)
    .join("");

  const pausas = (card.pausas || [])
    .map((p) => `<div class="retorno-item">Pausa ${p.numero}: ${escapeHtml(p.motivo || "-")}</div>`)
    .join("");

  const flags = [];
  if (card.tester_returned_dev) flags.push('<span class="pill warn">Pego no teste</span>');
  if (card.double_review_violation) flags.push('<span class="pill bad">Sem dupla revisao</span>');
  const timelineStages = card.etapas || [];
  const timelineTitle = collaboratorView ? "Etapas do fluxo completo do card" : "Etapas do fluxo";

  return `
    <details class="card-item"${dataAttrs}>
      <summary>
        <span>${escapeHtml(card.card_name)}</span>
        <span class="pill neutral">${escapeHtml(kindLabel)} · ${escapeHtml(card.sistema)} · N${card.fibonacci_level ?? "-"}</span>
        ${flags.join("")}
      </summary>
      <div class="card-body">
        <div class="card-meta">
          <span>Dev: ${escapeHtml(card.desenvolvedor)}</span>
          <span>Tester: ${escapeHtml(card.tester)}</span>
          <span>Revisor: ${escapeHtml(card.revisor)}</span>
          <span>Solicitante: ${escapeHtml(card.solicitante)}</span>
          ${collaboratorView ? `<span>Papeis: ${escapeHtml((card.collaborator_roles || []).join(", ") || "-")}</span>` : ""}
          ${collaboratorView ? `<span>Tempo do colaborador: ${escapeHtml(formatDurationFull(card.collaborator_time_hours, card.collaborator_time_human || "-"))}</span>` : ""}
          <span>Vida util: ${escapeHtml(formatDurationFull(card.lead_time_hours, card.lead_time_human || "-"))}</span>
          <span>Entrega: ${escapeHtml(formatDurationFull(card.cycle_time_hours, card.cycle_time_human || "-"))}</span>
          <span>Ret. teste/revisao: ${card.return_dev_by_teste_count ?? 0}/${card.return_dev_by_revisao_count ?? 0}</span>
          <span>Sem motivo teste: ${card.test_return_missing_reason_count ?? 0}</span>
          <span>Retestes: ${card.retest_cycles ?? 0}</span>
        </div>
        ${collaboratorView ? renderCollaboratorInvolvements(card) : ""}
        ${renderDescricao(card.descricao)}
        ${renderStageTimeline(timelineStages, { title: timelineTitle })}
        ${undueSolutions ? '<div class="obs-section"><div class="obs-section-title">Soluções de retorno indevido</div>' + undueSolutions + "</div>" : ""}
        ${retornos || pausas ? '<div class="obs-section"><div class="obs-section-title">Retornos e pausas</div>' : ""}
        ${retornos}${pausas}
        ${retornos || pausas ? "</div>" : ""}
      </div>
    </details>`;
}

function uniqueLevels(cards) {
  return [...new Set(cards.map((c) => c.fibonacci_level).filter((v) => v != null))].sort((a, b) => a - b);
}

function mergeLevels(found, baseLevels) {
  return [...new Set([...baseLevels, ...found])].sort((a, b) => a - b);
}

function renderLevelFilterRow(groupId, filterKey, label, levels) {
  if (!levels.length) return "";
  const chips = levels
    .map(
      (level) => `
    <label class="filter-chip">
      <input type="checkbox" class="dev-filter-input" data-group="${groupId}" data-filter="${filterKey}" value="${level}">
      <span>N${level}</span>
    </label>`,
    )
    .join("");
  return `
    <div class="filter-row">
      <span class="filter-label">${escapeHtml(label)}</span>
      <div class="filter-chips">${chips}</div>
    </div>`;
}

function renderDevFilters(groupId, normal, analise) {
  const all = [...normal, ...analise];
  const sistemas = [...new Set(all.map((c) => c.sistema).filter(Boolean))].sort();
  const taskLevels = mergeLevels(uniqueLevels(normal), TASK_LEVELS);
  const analysisLevels = mergeLevels(uniqueLevels(analise), ANALYSIS_LEVELS);

  const sistemaRow = sistemas.length
    ? `
    <div class="filter-row">
      <span class="filter-label">Sistema</span>
      <div class="filter-chips">
        ${sistemas
          .map(
            (sistema) => `
          <label class="filter-chip">
            <input type="checkbox" class="dev-filter-input" data-group="${groupId}" data-filter="sistema" value="${attrEscape(sistema)}">
            <span>${escapeHtml(sistema)}</span>
          </label>`,
          )
          .join("")}
      </div>
    </div>`
    : "";

  return `
    <div class="dossier-filters">
      ${renderLevelFilterRow(groupId, "task-level", "Nivel tarefa", taskLevels)}
      ${renderLevelFilterRow(groupId, "analysis-level", "Nivel analise", analysisLevels)}
      ${sistemaRow}
      <div class="filter-row filter-actions">
        <button type="button" class="btn-expand btn-muted dev-filter-clear" data-group="${groupId}">Limpar filtros</button>
        <span class="filter-count" data-count-for="${groupId}"></span>
      </div>
    </div>`;
}

function applyDevGroupFilters(groupEl) {
  const groupId = groupEl.dataset.groupId;
  const taskLevels = new Set();
  const analysisLevels = new Set();
  const sistemas = new Set();

  groupEl.querySelectorAll('.dev-filter-input[data-filter="task-level"]:checked').forEach((input) => {
    taskLevels.add(Number(input.value));
  });
  groupEl.querySelectorAll('.dev-filter-input[data-filter="analysis-level"]:checked').forEach((input) => {
    analysisLevels.add(Number(input.value));
  });
  groupEl.querySelectorAll('.dev-filter-input[data-filter="sistema"]:checked').forEach((input) => {
    sistemas.add(input.value);
  });

  let visible = 0;
  let total = 0;
  groupEl.querySelectorAll(".card-item[data-kind]").forEach((cardEl) => {
    total += 1;
    const kind = cardEl.dataset.kind;
    const level = cardEl.dataset.level ? Number(cardEl.dataset.level) : null;
    const sistema = cardEl.dataset.sistema || "";
    let show = true;

    if (sistemas.size > 0 && !sistemas.has(sistema)) {
      show = false;
    }
    if (show && kind === "problem" && taskLevels.size > 0) {
      show = level !== null && taskLevels.has(level);
    }
    if (show && kind === "analysis" && analysisLevels.size > 0) {
      show = level !== null && analysisLevels.has(level);
    }

    cardEl.style.display = show ? "" : "none";
    if (show) visible += 1;
  });

  groupEl.querySelectorAll(".dossier-subsection").forEach((section) => {
    const hasVisible = [...section.querySelectorAll(".card-item[data-kind]")].some(
      (card) => card.style.display !== "none",
    );
    section.classList.toggle("is-empty", !hasVisible);
  });

  const countEl = groupEl.querySelector(`[data-count-for="${groupId}"]`);
  if (countEl) {
    const hasFilter = taskLevels.size || analysisLevels.size || sistemas.size;
    countEl.textContent = hasFilter ? `${visible} de ${total} card(s) visiveis` : `${total} card(s)`;
  }
}

function setupDossierActions() {
  const container = document.getElementById("dossier-content");

  container.addEventListener("click", (event) => {
    const clearBtn = event.target.closest(".dev-filter-clear");
    if (clearBtn) {
      const groupId = clearBtn.dataset.group;
      const groupEl = container.querySelector(`.dossier-group.dev-dossier[data-group-id="${groupId}"]`);
      if (!groupEl) return;
      groupEl.querySelectorAll(".dev-filter-input").forEach((input) => {
        input.checked = false;
      });
      applyDevGroupFilters(groupEl);
      return;
    }

    const button = event.target.closest(".btn-expand");
    if (!button || button.classList.contains("dev-filter-clear")) return;
    const groupId = button.dataset.group;
    const expand = button.dataset.action === "expand";
    container.querySelectorAll(`.dossier-group[data-group-id="${groupId}"] .card-item`).forEach((item) => {
      if (item.style.display === "none") return;
      item.open = expand;
    });
  });

  container.addEventListener("change", (event) => {
    if (!event.target.classList.contains("dev-filter-input")) return;
    const groupId = event.target.dataset.group;
    const groupEl = container.querySelector(`.dossier-group.dev-dossier[data-group-id="${groupId}"]`);
    if (groupEl) applyDevGroupFilters(groupEl);
  });
}

function renderDossier() {
  const dossier = METRICS.card_dossier || {};
  const container = document.getElementById("dossier-content");
  let html = `<p style="color:var(--muted);font-size:0.875rem;margin:0 0 1rem">${dossier.cards_total ?? 0} cards com atividade no periodo</p>`;

  const byDev = dossier.by_developer || {};
  if (Object.keys(byDev).length) {
    html += '<div class="dossier-section-title">Por desenvolvedor</div>';
  }
  Object.entries(byDev).forEach(([name, groups], index) => {
    const groupId = `dev-${index}`;
    const normal = groups.tarefas_normais || [];
    const analise = groups.cards_analise || [];
    const subtitle = `${normal.length} tarefa(s) · ${analise.length} analise(s)`;
    html += `<div class="dossier-group dev-dossier" data-group-id="${groupId}">`;
    html += dossierGroupHeader(name, groupId, subtitle);
    html += renderDevFilters(groupId, normal, analise);
    if (normal.length) {
      html += '<div class="dossier-subsection"><h5 class="dossier-bucket-title">Tarefas normais</h5><div class="dossier-cards">';
      normal.forEach((c) => { html += renderCardBlock(c, { filterable: true }); });
      html += "</div></div>";
    }
    if (analise.length) {
      html += '<div class="dossier-subsection"><h5 class="dossier-bucket-title">Analises</h5><div class="dossier-cards">';
      analise.forEach((c) => { html += renderCardBlock(c, { filterable: true }); });
      html += "</div></div>";
    }
    if (!normal.length && !analise.length) {
      html += '<div class="empty-state">Nenhum card para este desenvolvedor.</div>';
    }
    html += "</div>";
  });

  const byTester = dossier.by_tester || {};
  if (Object.keys(byTester).length) {
    html += '<div class="dossier-section-title">Por tester</div>';
  }
  Object.entries(byTester).forEach(([name, cards], index) => {
    const groupId = `tester-${index}`;
    html += `<div class="dossier-group" data-group-id="${groupId}">`;
    html += dossierGroupHeader(`Tester: ${name}`, groupId, `${cards.length} card(s)`);
    html += '<div class="dossier-cards">';
    cards.forEach((c) => { html += renderCardBlock(c); });
    html += "</div></div>";
  });

  const bySolicitante = dossier.by_solicitante || {};
  if (Object.keys(bySolicitante).length) {
    html += '<div class="dossier-section-title">Por solicitante</div>';
  }
  Object.entries(bySolicitante).forEach(([name, cards], index) => {
    const groupId = `sol-${index}`;
    html += `<div class="dossier-group" data-group-id="${groupId}">`;
    html += dossierGroupHeader(`Solicitante: ${name}`, groupId, `${cards.length} card(s)`);
    html += '<div class="dossier-cards">';
    cards.forEach((c) => { html += renderCardBlock(c); });
    html += "</div></div>";
  });

  if (!Object.keys(byDev).length && !Object.keys(byTester).length && !Object.keys(bySolicitante).length) {
    html += '<div class="empty-state">Nenhum card no dossie.</div>';
  }

  container.innerHTML = html;
  container.querySelectorAll(".dossier-group.dev-dossier").forEach((groupEl) => {
    applyDevGroupFilters(groupEl);
  });
}

function setupNav() {
  const links = document.querySelectorAll(".sidebar nav a");
  const sections = [...links].map((a) => document.querySelector(a.getAttribute("href")));

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          links.forEach((l) => l.classList.toggle("active", l.getAttribute("href") === `#${entry.target.id}`));
        }
      });
    },
    { rootMargin: "-20% 0px -70% 0px" },
  );
  sections.filter(Boolean).forEach((s) => observer.observe(s));
}

function formatInlineMarkdown(text) {
  return escapeHtml(text)
    .replace(/`([^`]+)`/g, '<code class="ai-code">$1</code>')
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
}

function isUnfairCallout(lines) {
  const joined = lines.join(" ").toLowerCase();
  return (
    joined.includes("indevido") ||
    joined.includes("nao faz sentido") ||
    joined.includes("não faz sentido") ||
    joined.includes("id trello") ||
    joined.includes("revisar se deve abater")
  );
}

function renderMarkdownAnalysis(text) {
  const lines = String(text).split("\n");
  const html = [];
  let index = 0;

  while (index < lines.length) {
    const trimmed = lines[index].trim();
    if (!trimmed) {
      html.push('<div class="ai-spacer"></div>');
      index += 1;
      continue;
    }

    if (trimmed.startsWith(">")) {
      const quoteLines = [];
      while (index < lines.length && lines[index].trim().startsWith(">")) {
        quoteLines.push(lines[index].trim().replace(/^>\s?/, ""));
        index += 1;
      }
      const cls = isUnfairCallout(quoteLines) ? "ai-callout ai-callout-warn" : "ai-callout";
      html.push(
        `<blockquote class="${cls}">${quoteLines
          .map((line) => `<p>${formatInlineMarkdown(line)}</p>`)
          .join("")}</blockquote>`,
      );
      continue;
    }

    if (/^[-*] /.test(trimmed)) {
      const items = [];
      while (index < lines.length && /^[-*] /.test(lines[index].trim())) {
        items.push(lines[index].trim().replace(/^[-*] /, ""));
        index += 1;
      }
      html.push(
        `<ul class="ai-list">${items.map((item) => `<li>${formatInlineMarkdown(item)}</li>`).join("")}</ul>`,
      );
      continue;
    }

    if (/^\d+\.\s/.test(trimmed)) {
      const items = [];
      while (index < lines.length && /^\d+\.\s/.test(lines[index].trim())) {
        items.push(lines[index].trim().replace(/^\d+\.\s/, ""));
        index += 1;
      }
      html.push(
        `<ol class="ai-list ai-list-ordered">${items
          .map((item) => `<li>${formatInlineMarkdown(item)}</li>`)
          .join("")}</ol>`,
      );
      continue;
    }

    if (trimmed.startsWith("#### ")) {
      html.push(`<h6 class="ai-h6">${escapeHtml(trimmed.slice(5))}</h6>`);
    } else if (trimmed.startsWith("### ")) {
      html.push(`<h5>${escapeHtml(trimmed.slice(4))}</h5>`);
    } else if (trimmed.startsWith("## ")) {
      const title = trimmed.slice(3);
      const alertClass = /retorno|indevido|atencao|atenção/i.test(title) ? " ai-h4-alert" : "";
      html.push(`<h4 class="ai-h4${alertClass}">${escapeHtml(title)}</h4>`);
    } else if (trimmed.startsWith("# ")) {
      html.push(`<h3>${escapeHtml(trimmed.slice(2))}</h3>`);
    } else if (/^---+$/.test(trimmed)) {
      html.push('<hr class="ai-divider" />');
    } else {
      html.push(`<p>${formatInlineMarkdown(trimmed)}</p>`);
    }
    index += 1;
  }

  return html.join("");
}

function renderAiAnalysis() {
  const section = document.getElementById("ai-analysis");
  const container = document.getElementById("ai-analysis-content");
  const meta = document.getElementById("ai-analysis-meta");
  const text = METRICS.ai_analysis;
  if (!section || !container) return;

  if (!text || !String(text).trim()) {
    section.style.display = "none";
    const navLink = document.querySelector('.sidebar nav a[href="#ai-analysis"]');
    if (navLink) navLink.style.display = "none";
    return;
  }

  const ai = METRICS.ai || {};
  if (meta) {
    const provider = ai.provider || "IA";
    const model = ai.model || "modelo padrao";
    meta.textContent = `${provider} · ${model}`;
  }

  container.innerHTML = renderMarkdownAnalysis(text);
}

function init() {
  configureReportLayout();
  renderHero();
  renderAiAnalysis();
  renderManagementGuide();
  renderOverview();
  renderFlow();
  renderRiskBoard();
  renderPriority();
  renderDora();
  renderProcessDiscipline();
  renderAnalysisWorkflow();
  renderFibonacci();
  renderCollaborators();
  renderDevelopers();
  renderReviewers();
  renderFormalReviewers();
  renderTesters();
  renderRequesters();
  renderProjects();
  renderSla();
  renderBottlenecks();
  renderTrends();
  renderAntifraud();
  renderQuality();
  renderDossier();
  setupDossierActions();
  setupCollaboratorActions();
  renderInitialCollaboratorRoute();
  setupNav();
}

document.addEventListener("DOMContentLoaded", init);
