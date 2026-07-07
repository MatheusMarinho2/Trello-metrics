import definitions from "../data/metric_definitions.json";

type MetricDefinitions = {
  labels: Record<string, string>;
  descriptions: Record<string, string>;
  tables: Record<string, { description?: string; columns?: string[] }>;
};

const defs = definitions as MetricDefinitions;

export function metricLabel(key: string): string {
  if (defs.labels[key]) return defs.labels[key];
  return key
    .replace(/_pct$/i, " (%)")
    .replace(/_human$/i, "")
    .replace(/_hours$/i, " (horas)")
    .replace(/_count$/i, "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

export function metricDescription(key: string): string {
  return defs.descriptions[key] ?? "";
}

export function tableInfo(tableId: string) {
  return defs.tables[tableId] ?? {};
}

export function tableDescription(tableId: string): string {
  return tableInfo(tableId).description ?? "";
}

export function sectionGuide(sectionId: string) {
  return (defs as MetricDefinitions & { guides?: Record<string, any> }).guides?.[sectionId] ?? {};
}

export const MANAGEMENT_GUIDE_SECTIONS = [
  "management_intro",
  "team_summary",
  "flow",
  "dora",
  "direct_production",
  "sla",
  "process_discipline",
  "analysis_workflow",
  "priority",
  "risk",
  "bottlenecks",
  "quality_gates",
] as const;

export const SLA_ALERTS_TABLE_TITLE = "Cards com alerta de SLA";

export const SECTION_TABLE_IDS: Record<string, string> = {
  Colaboradores: "collaborators",
  Desenvolvedores: "developers",
  Revisores: "reviewers",
  Testers: "testers",
  Solicitantes: "requesters",
  Projetos: "projects",
  Gargalos: "bottlenecks",
  [SLA_ALERTS_TABLE_TITLE]: "sla_alerts",
  "SLA por desenvolvedor": "sla_developers",
  "SLA por card": "sla_cards",
};
