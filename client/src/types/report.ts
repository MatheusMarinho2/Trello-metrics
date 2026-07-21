export type ReportType =
  | "general"
  | "individual"
  | "developers"
  | "requesters"
  | "testers"
  | "reviewers"
  | "formal_reviewers"
  | "management"
  | "specific_metrics"
  | "by_system";

export type AIProvider = "openai" | "gemini" | "claude";

export interface SelectOption {
  value: string;
  label: string;
  default_model?: string;
}

export interface AIProviderOption {
  value: AIProvider;
  label: string;
  default_model: string;
  models: SelectOption[];
}

export interface ReportOptions {
  report_types: SelectOption[];
  metric_options: SelectOption[];
  ai_providers: AIProviderOption[];
  systems?: SelectOption[];
}

export const AI_MAX_OUTPUT_TOKENS = 131_072;

export interface GenerateReportPayload {
  report_type: ReportType;
  month: string;
  history_months: number;
  timezone: string;
  include_templates: boolean;
  collaborator_name?: string;
  sistema_name?: string;
  metric_keys?: string[];
  trello: {
    board_id?: string;
    api_key?: string;
    token?: string;
    use_live_api: boolean;
    source_json?: unknown;
  };
  ai: {
    enabled: boolean;
    provider: AIProvider;
    api_key?: string;
    model?: string;
    temperature: number;
    max_tokens: number;
  };
}

export interface GeneratedReport {
  id: string;
  title: string;
  report_type: ReportType;
  month: string;
  collaborator_name?: string;
  sistema_name?: string;
  metric_keys?: string[];
  board_id?: string;
  board_name?: string;
  board_url?: string;
  snapshot?: {
    id: string;
    source: string;
    cards_count: number;
    movements_count: number;
    custom_field_changes_count?: number;
    created_at?: string;
  } | null;
  filtered_metrics?: Record<string, any>;
  ai_status?: string;
  ai_provider?: string;
  ai_model?: string;
  ai_analysis?: string;
  ai_error?: string;
  created_at: string;
  summary?: {
    cards_delivered?: number;
    quality_rate_pct?: number;
    cards_metricados?: number;
  };
}

export interface Collaborator {
  id: number;
  name: string;
  aliases: string[];
  active: boolean;
  source: string;
  created_at: string;
  updated_at: string;
}

export interface ProjectSystem {
  id: number;
  name: string;
  active: boolean;
  source: string;
  created_at: string;
  updated_at: string;
}
