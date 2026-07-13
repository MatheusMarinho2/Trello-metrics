import type { ReportType } from "../types/report";

export type PreviewSection =
  | "collaborators"
  | "developers"
  | "reviewers"
  | "testers"
  | "requesters"
  | "projects"
  | "cards"
  | "sla_dev"
  | "sla_cards"
  | "bottlenecks"
  | "alerts"
  | "team_summary"
  | "flow"
  | "priority"
  | "dora"
  | "quality_gates"
  | "discipline"
  | "individual"
  | "role_metrics"
  | "fibonacci"
  | "trends"
  | "risk"
  | "analysis_workflow"
  | "antifraud";

export const REPORT_PREVIEW_SECTIONS: Record<ReportType, PreviewSection[]> = {
  general: [
    "team_summary",
    "flow",
    "priority",
    "dora",
    "quality_gates",
    "discipline",
    "analysis_workflow",
    "antifraud",
    "fibonacci",
    "collaborators",
    "developers",
    "reviewers",
    "testers",
    "requesters",
    "projects",
    "sla_dev",
    "sla_cards",
    "bottlenecks",
    "alerts",
  ],
  individual: ["individual", "role_metrics", "collaborators"],
  developers: ["role_metrics", "developers", "flow", "fibonacci", "sla_dev", "quality_gates"],
  requesters: ["role_metrics", "requesters", "projects"],
  testers: ["role_metrics", "testers", "quality_gates"],
  management: [
    "team_summary",
    "flow",
    "priority",
    "dora",
    "discipline",
    "quality_gates",
    "analysis_workflow",
    "antifraud",
    "projects",
    "sla_dev",
    "bottlenecks",
    "alerts",
    "trends",
    "risk",
  ],
  specific_metrics: ["team_summary", "sla_dev", "sla_cards", "bottlenecks", "flow", "priority", "dora", "antifraud"],
};

export const METRIC_KEY_SECTIONS: Record<string, PreviewSection[]> = {
  team_summary: ["team_summary"],
  flow: ["flow"],
  developers: ["role_metrics", "developers", "fibonacci", "flow", "quality_gates", "sla_dev"],
  testers: ["role_metrics", "testers", "quality_gates"],
  requesters: ["role_metrics", "requesters", "projects"],
  sla: ["sla_dev", "sla_cards", "alerts"],
  bottlenecks: ["bottlenecks"],
  card_dossier: [],
  priority: ["priority"],
  dora: ["dora"],
  quality_gates: ["quality_gates"],
  discipline: ["discipline"],
  analysis_workflow: ["analysis_workflow"],
  antifraud: ["antifraud"],
};

export function allowedSectionsForReport(
  reportType: ReportType,
  metricKeys?: string[],
): Set<PreviewSection> {
  if (reportType === "specific_metrics" && metricKeys?.length) {
    const allowed = new Set<PreviewSection>();
    for (const key of metricKeys) {
      for (const section of METRIC_KEY_SECTIONS[key] ?? []) {
        allowed.add(section);
      }
    }
    return allowed;
  }
  return new Set(REPORT_PREVIEW_SECTIONS[reportType] ?? REPORT_PREVIEW_SECTIONS.general);
}

export const TAB_DESCRIPTIONS: Record<ReportType, string> = {
  general: "Visao completa do time: entregas, fluxo, qualidade, pessoas e dossie de cards.",
  individual: "Perfil consolidado de um colaborador e cards em que atuou no periodo.",
  developers: "Entregas, pontos Fibonacci, tempo de atuacao e qualidade por desenvolvedor.",
  requesters: "Demanda criada, planejamento e entregas por solicitante.",
  testers: "Testes, primeira passagem, problemas evitados e retestes.",
  management: "Indicadores para gestao: fluxo, SLA, risco, DORA, analises e tendencias.",
  specific_metrics: "Somente as metricas selecionadas abaixo.",
};
