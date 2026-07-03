import type { ReportType } from "../types/report";

export const REPORT_PREVIEW_SECTIONS: Record<
  ReportType,
  Array<
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
  >
> = {
  general: [
    "team_summary",
    "flow",
    "priority",
    "dora",
    "quality_gates",
    "discipline",
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
  management: ["team_summary", "flow", "priority", "dora", "discipline", "projects", "sla_dev", "bottlenecks", "alerts"],
  specific_metrics: ["team_summary", "sla_dev", "sla_cards", "bottlenecks", "flow", "priority", "dora"],
};

export const TAB_DESCRIPTIONS: Record<ReportType, string> = {
  general: "Visao completa do time: entregas, fluxo, qualidade, pessoas e dossie de cards.",
  individual: "Perfil consolidado de um colaborador e cards em que atuou no periodo.",
  developers: "Entregas, pontos Fibonacci, tempo de atuacao e qualidade por desenvolvedor.",
  requesters: "Demanda criada, planejamento e entregas por solicitante.",
  testers: "Testes, primeira passagem, problemas evitados e retestes.",
  management: "Indicadores para gestao: fluxo, SLA, risco, DORA e tendencias.",
  specific_metrics: "Somente as metricas selecionadas abaixo.",
};
