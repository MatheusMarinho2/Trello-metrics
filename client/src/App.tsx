import {
  BarChart3,
  BrainCircuit,
  ChevronDown,
  ClipboardList,
  Database,
  Download,
  ExternalLink,
  FileJson,
  FileText,
  Globe,
  LogOut,
  Printer,
  RefreshCw,
  Settings,
  ShieldCheck,
  Sparkles,
  User,
  UserPlus,
  Users,
  type LucideIcon,
} from "lucide-react";
import { type Dispatch, type FormEvent, type SetStateAction, useEffect, useMemo, useRef, useState } from "react";

import {
  clearStoredToken,
  createCollaborator,
  downloadReport,
  generateReport,
  getReport,
  getMe,
  getReportOptions,
  getStoredToken,
  listCollaborators,
  listReports,
  login,
  updateCollaborator,
} from "./api/client";
import { LoadingOverlay } from "./components/LoadingOverlay";
import { HelpTip } from "./components/HelpTip";
import {
  REPORT_PREVIEW_SECTIONS,
  TAB_DESCRIPTIONS,
} from "./lib/reportLayouts";
import type { AIProvider, Collaborator, GenerateReportPayload, GeneratedReport, ReportOptions, ReportType } from "./types/report";
import {
  MANAGEMENT_GUIDE_SECTIONS,
  metricDescription,
  metricLabel,
  sectionGuide,
  SECTION_TABLE_IDS,
  tableDescription,
} from "./lib/metricDefinitions";

const tabs: Array<{ value: ReportType; label: string; icon: LucideIcon }> = [
  { value: "general", label: "Geral", icon: BarChart3 },
  { value: "individual", label: "Individual", icon: User },
  { value: "developers", label: "Desenvolvedores", icon: Users },
  { value: "requesters", label: "Solicitantes", icon: ClipboardList },
  { value: "testers", label: "Testers", icon: ShieldCheck },
  { value: "management", label: "Gestao", icon: Settings },
  { value: "specific_metrics", label: "Metricas", icon: Database },
];

const fallbackOptions: ReportOptions = {
  report_types: tabs.map((tab) => ({ value: tab.value, label: tab.label })),
  metric_options: [
    { value: "team_summary", label: "Resumo do time" },
    { value: "flow", label: "Fluxo" },
    { value: "developers", label: "Desenvolvedores" },
    { value: "testers", label: "Testers" },
    { value: "requesters", label: "Solicitantes" },
    { value: "sla", label: "SLA" },
    { value: "bottlenecks", label: "Gargalos" },
    { value: "card_dossier", label: "Detalhamento" },
  ],
  ai_providers: [
    { value: "openai", label: "GPT", default_model: "gpt-5.4-mini" },
    { value: "gemini", label: "Gemini", default_model: "gemini-3.5-flash" },
    { value: "claude", label: "Claude", default_model: "claude-sonnet-5" },
  ],
};

function App() {
  const [token, setToken] = useState(getStoredToken());
  const [username, setUsername] = useState("");
  const [loginName, setLoginName] = useState("gestor");
  const [password, setPassword] = useState("intgest");
  const [activeTab, setActiveTab] = useState<ReportType>("general");
  const [options, setOptions] = useState<ReportOptions>(fallbackOptions);
  const [reports, setReports] = useState<GeneratedReport[]>([]);
  const [collaborators, setCollaborators] = useState<Collaborator[]>([]);
  const [currentReport, setCurrentReport] = useState<GeneratedReport | null>(null);
  const selectedByTabRef = useRef<Partial<Record<ReportType, string>>>({});
  const [loading, setLoading] = useState(false);
  const [loadingLabel, setLoadingLabel] = useState("Carregando");
  const [error, setError] = useState("");

  const [month, setMonth] = useState(currentMonth());
  const [historyMonths, setHistoryMonths] = useState(6);
  const [boardId, setBoardId] = useState("yo4qzLai");
  const [trelloApiKey, setTrelloApiKey] = useState("");
  const [trelloToken, setTrelloToken] = useState("");
  const [useLiveApi, setUseLiveApi] = useState(true);
  const [sourceJson, setSourceJson] = useState("");
  const [collaboratorName, setCollaboratorName] = useState("");
  const [newCollaboratorName, setNewCollaboratorName] = useState("");
  const [metricKeys, setMetricKeys] = useState<string[]>(["team_summary", "flow", "sla"]);

  const [aiEnabled, setAiEnabled] = useState(false);
  const [aiProvider, setAiProvider] = useState<AIProvider>("openai");
  const [aiModel, setAiModel] = useState("gpt-5.4-mini");
  const [aiKey, setAiKey] = useState("");

  useEffect(() => {
    if (!token) return;
    void bootstrap(token);
  }, [token]);

  useEffect(() => {
    if (!token) return;
    void loadHistoryForTab(activeTab);
  }, [activeTab, token]);

  async function bootstrap(activeToken: string) {
    setLoading(true);
    setLoadingLabel("Sincronizando sessao");
    setError("");
    try {
      const [me, loadedOptions, history, loadedCollaborators] = await Promise.all([
        getMe(activeToken),
        getReportOptions(activeToken),
        listReports(activeToken, activeTab),
        listCollaborators(activeToken),
      ]);
      setUsername(me.user.username);
      setOptions(loadedOptions);
      setCollaborators(loadedCollaborators);
      setReports(history);
      if (history.length > 0) {
        rememberSelection(activeTab, history[0].id);
        const detail = await getReport(activeToken, history[0].id);
        setCurrentReport(detail);
      } else {
        setCurrentReport(null);
      }
    } catch (err) {
      clearStoredToken();
      setToken("");
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  async function loadHistoryForTab(reportType: ReportType) {
    setError("");
    try {
      const history = await listReports(token, reportType);
      setReports(history);
      if (history.length === 0) {
        setCurrentReport(null);
        return;
      }
      const preferredId = selectedByTabRef.current[reportType];
      const targetId =
        preferredId && history.some((report) => report.id === preferredId)
          ? preferredId
          : history[0].id;
      setCurrentReport(await getReport(token, targetId));
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  function rememberSelection(reportType: ReportType, reportId: string) {
    selectedByTabRef.current = { ...selectedByTabRef.current, [reportType]: reportId };
  }

  async function handleLogin(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setLoadingLabel("Autenticando");
    setError("");
    try {
      const access = await login(loginName, password);
      setToken(access);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  function handleLogout() {
    clearStoredToken();
    setToken("");
    setUsername("");
    setCurrentReport(null);
  }

  async function handleGenerate(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setLoadingLabel(aiEnabled ? "Gerando metricas e analise" : "Gerando metricas");
    setError("");
    try {
      const parsedSource = useLiveApi ? undefined : JSON.parse(sourceJson);
      const payload: GenerateReportPayload = {
        report_type: activeTab,
        month,
        history_months: historyMonths,
        timezone: "America/Sao_Paulo",
        include_templates: false,
        collaborator_name: collaboratorName,
        metric_keys: metricKeys,
        trello: {
          board_id: boardId,
          api_key: trelloApiKey,
          token: trelloToken,
          use_live_api: useLiveApi,
          source_json: parsedSource,
        },
        ai: {
          enabled: aiEnabled,
          provider: aiProvider,
          api_key: aiKey,
          model: aiModel,
          temperature: 0.2,
          max_tokens: 1800,
        },
      };
      const report = await generateReport(token, payload);
      rememberSelection(activeTab, report.id);
      setCurrentReport(report);
      setReports(await listReports(token, activeTab));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  async function handleDownload(report: GeneratedReport, format: "pdf" | "json" | "html") {
    setError("");
    try {
      await downloadReport(token, report.id, format);
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function handleSelectReport(report: GeneratedReport) {
    setLoading(true);
    setLoadingLabel("Abrindo relatorio");
    setError("");
    try {
      const detail = await getReport(token, report.id);
      rememberSelection(report.report_type, report.id);
      setCurrentReport(detail);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  async function handleAddCollaborator() {
    const name = newCollaboratorName.trim();
    if (!name) return;
    setError("");
    try {
      const collaborator = await createCollaborator(token, name);
      setCollaborators((items) => [...items, collaborator].sort((a, b) => a.name.localeCompare(b.name)));
      setCollaboratorName(collaborator.name);
      setNewCollaboratorName("");
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function handleToggleCollaborator(collaborator: Collaborator) {
    setError("");
    try {
      const updated = await updateCollaborator(token, collaborator.id, {
        active: !collaborator.active,
      });
      setCollaborators((items) =>
        items.map((item) => (item.id === updated.id ? updated : item)),
      );
      if (!updated.active && collaboratorName === updated.name) {
        setCollaboratorName("");
      }
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  function handlePrint() {
    window.print();
  }

  function updateProvider(provider: AIProvider) {
    setAiProvider(provider);
    setAiModel(defaultModelFor(provider, options));
  }

  const activeCollaborators = useMemo(
    () => collaborators.filter((collaborator) => collaborator.active),
    [collaborators],
  );

  const activeTabLabel = useMemo(
    () => tabs.find((tab) => tab.value === activeTab)?.label ?? "Relatorio",
    [activeTab],
  );

  if (!token) {
    return (
      <main className="login-shell">
        <LoadingOverlay show={loading} label={loadingLabel} />
        <section className="login-card">
          <div className="brand-row">
            <div className="brand-mark">ig</div>
            <div>
              <strong>INTGEST</strong>
              <span>Metricas Trello</span>
            </div>
          </div>
          <form onSubmit={handleLogin} className="login-form">
            <label>
              Usuario
              <input value={loginName} onChange={(event) => setLoginName(event.target.value)} />
            </label>
            <label>
              Senha
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </label>
            {error && <p className="form-error">{error}</p>}
            <button className="primary-button" type="submit">
              <ShieldCheck size={18} />
              Entrar
            </button>
          </form>
        </section>
      </main>
    );
  }

  return (
    <main className="app-shell">
      <LoadingOverlay show={loading} label={loadingLabel} />
      <header className="topbar">
        <div className="brand-row">
          <div className="brand-mark">ig</div>
          <div>
            <strong>INTGEST</strong>
            <span>{activeTabLabel}</span>
          </div>
        </div>
        <div className="topbar-actions">
          <span className="user-chip">{username}</span>
          <button className="icon-button" type="button" onClick={() => void bootstrap(token)} title="Atualizar">
            <RefreshCw size={18} />
          </button>
          <button className="icon-button" type="button" onClick={handleLogout} title="Sair">
            <LogOut size={18} />
          </button>
        </div>
      </header>

      <section className="tabs" aria-label="Tipos de relatorio">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.value}
              className={activeTab === tab.value ? "tab active" : "tab"}
              type="button"
              onClick={() => setActiveTab(tab.value)}
            >
              <Icon size={18} />
              {tab.label}
            </button>
          );
        })}
      </section>

      {error && <div className="app-alert">{error}</div>}

      <section className="workspace">
        <form className="report-form" onSubmit={handleGenerate}>
          <div className="panel-title">
            <FileText size={20} />
            <div>
              <h1>{activeTabLabel}</h1>
              <p className="tab-description">{TAB_DESCRIPTIONS[activeTab]}</p>
            </div>
          </div>

          <div className="form-grid">
            <label>
              Mes
              <input type="month" value={month} onChange={(event) => setMonth(event.target.value)} />
            </label>
            <label>
              Historico
              <input
                type="number"
                min={1}
                max={24}
                value={historyMonths}
                onChange={(event) => setHistoryMonths(Number(event.target.value))}
              />
            </label>
            <label>
              Board Trello
              <input value={boardId} onChange={(event) => setBoardId(event.target.value)} />
            </label>
          </div>

          <fieldset className="segmented-field">
            <legend>Origem</legend>
            <button
              className={useLiveApi ? "segment active" : "segment"}
              type="button"
              onClick={() => setUseLiveApi(true)}
            >
              API Trello
            </button>
            <button
              className={!useLiveApi ? "segment active" : "segment"}
              type="button"
              onClick={() => setUseLiveApi(false)}
            >
              JSON
            </button>
          </fieldset>

          {useLiveApi ? (
            <div className="form-grid">
              <label>
                Trello key
                <input
                  type="password"
                  value={trelloApiKey}
                  onChange={(event) => setTrelloApiKey(event.target.value)}
                  placeholder="opcional via .env"
                />
              </label>
              <label>
                Trello token
                <input
                  type="password"
                  value={trelloToken}
                  onChange={(event) => setTrelloToken(event.target.value)}
                  placeholder="opcional via .env"
                />
              </label>
            </div>
          ) : (
            <label>
              JSON Trello
              <textarea
                value={sourceJson}
                onChange={(event) => setSourceJson(event.target.value)}
                spellCheck={false}
              />
            </label>
          )}

          {activeTab === "individual" && (
            <label>
              Colaborador
              <select
                value={collaboratorName}
                onChange={(event) => setCollaboratorName(event.target.value)}
              >
                <option value="">Selecione um colaborador</option>
                {activeCollaborators.map((collaborator) => (
                  <option key={collaborator.id} value={collaborator.name}>
                    {collaborator.name}
                  </option>
                ))}
              </select>
            </label>
          )}

          {activeTab === "specific_metrics" && (
            <div className="metric-picker">
              {options.metric_options.map((option) => (
                <label key={option.value} className="check-row">
                  <input
                    type="checkbox"
                    checked={metricKeys.includes(option.value)}
                    onChange={() => toggleMetric(option.value, metricKeys, setMetricKeys)}
                  />
                  {option.label}
                </label>
              ))}
            </div>
          )}

          <section className="ai-panel">
            <div className="ai-heading">
              <BrainCircuit size={20} />
              <strong>Analise IA</strong>
              <label className="switch">
                <input
                  type="checkbox"
                  checked={aiEnabled}
                  onChange={(event) => setAiEnabled(event.target.checked)}
                />
                <span />
              </label>
            </div>
            <div className="form-grid">
              <label>
                Provedor
                <select
                  value={aiProvider}
                  disabled={!aiEnabled}
                  onChange={(event) => updateProvider(event.target.value as AIProvider)}
                >
                  {options.ai_providers.map((provider) => (
                    <option key={provider.value} value={provider.value}>
                      {provider.label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Modelo
                <input
                  value={aiModel}
                  disabled={!aiEnabled}
                  onChange={(event) => setAiModel(event.target.value)}
                />
              </label>
              <label>
                API key
                <input
                  type="password"
                  value={aiKey}
                  disabled={!aiEnabled}
                  onChange={(event) => setAiKey(event.target.value)}
                />
              </label>
            </div>
          </section>

          <section className="collaborator-panel">
            <div className="panel-title compact">
              <UserPlus size={18} />
              <h2>Colaboradores</h2>
            </div>
            <div className="inline-add">
              <input
                value={newCollaboratorName}
                onChange={(event) => setNewCollaboratorName(event.target.value)}
                placeholder="Adicionar colaborador"
              />
              <button type="button" onClick={() => void handleAddCollaborator()}>
                Adicionar
              </button>
            </div>
            <div className="collaborator-list">
              {collaborators.map((collaborator) => (
                <button
                  key={collaborator.id}
                  type="button"
                  className={collaborator.active ? "collaborator-item active" : "collaborator-item"}
                  onClick={() => void handleToggleCollaborator(collaborator)}
                >
                  <span>{collaborator.name}</span>
                  <strong>{collaborator.active ? "Ativo" : "Fora"}</strong>
                </button>
              ))}
            </div>
          </section>

          <button className="primary-button wide" type="submit">
            <Sparkles size={18} />
            Gerar relatorio
          </button>
        </form>

        <section className="report-preview">
          {currentReport ? (
            <>
              <div className="preview-header">
                <div>
                  <span className="eyebrow">{currentReport.month}</span>
                  <h2>{currentReport.title}</h2>
                </div>
                <div className="download-actions">
                  <button type="button" onClick={() => void handleDownload(currentReport, "html")}>
                    <Globe size={17} />
                    HTML
                  </button>
                  <button type="button" onClick={() => void handleDownload(currentReport, "pdf")}>
                    <Download size={17} />
                    PDF
                  </button>
                  <button type="button" onClick={() => void handleDownload(currentReport, "json")}>
                    <FileJson size={17} />
                    JSON
                  </button>
                  <button type="button" onClick={handlePrint}>
                    <Printer size={17} />
                    Imprimir
                  </button>
                </div>
              </div>
              <KpiStrip report={currentReport} />
              {currentReport.report_type === "management" && (
                <ManagementMetricGuide report={currentReport} />
              )}
              <SnapshotInfo report={currentReport} />
              <AiAnalysis report={currentReport} />
              <MetricSections report={currentReport} />
            </>
          ) : (
            <div className="empty-state">
              <BarChart3 size={42} />
              <strong>Nenhum relatorio selecionado</strong>
            </div>
          )}
        </section>

        <aside className="history-panel">
          <div className="panel-title compact">
            <ClipboardList size={18} />
            <h2>Historico {activeTabLabel}</h2>
          </div>
          <div className="history-list">
            {reports.map((report) => (
              <button
                key={report.id}
                type="button"
                className={currentReport?.id === report.id ? "history-item active" : "history-item"}
                onClick={() => void handleSelectReport(report)}
              >
                <strong>{report.title}</strong>
                <span>{formatDate(report.created_at)}</span>
              </button>
            ))}
          </div>
        </aside>
      </section>
    </main>
  );
}

function KpiStrip({ report }: { report: GeneratedReport }) {
  const metrics = report.filtered_metrics ?? {};
  const allowed = REPORT_PREVIEW_SECTIONS[report.report_type] ?? REPORT_PREVIEW_SECTIONS.general;

  if (report.report_type === "individual" && metrics.individual_summary) {
    const summary = metrics.individual_summary;
    return (
      <div className="kpi-strip">
        <Kpi label="Entregues" value={summary.cards_delivered ?? "-"} term="cards_delivered" />
        <Kpi label="Pontos" value={summary.fibonacci_total ?? "-"} term="fibonacci_total" />
        <Kpi label="Ativos" value={summary.cards_active ?? "-"} term="cards_active" />
        <Kpi label="Tempo" value={summary.time_human ?? "-"} term="time_human" />
      </div>
    );
  }

  if (metrics.role_summary) {
    const summary = metrics.role_summary;
    if (summary.scope === "developers") {
      return (
        <div className="kpi-strip">
          <Kpi label="Devs" value={summary.people_count ?? "-"} term="people_count" />
          <Kpi label="Entregues" value={summary.cards_delivered ?? "-"} term="cards_delivered" />
          <Kpi label="Qualidade" value={summary.quality_rate_pct != null ? `${summary.quality_rate_pct}%` : "-"} term="quality_rate_pct" />
          <Kpi label="Retrabalho" value={summary.rework_rate_pct != null ? `${summary.rework_rate_pct}%` : "-"} term="rework_rate_pct" />
        </div>
      );
    }
    if (summary.scope === "testers") {
      return (
        <div className="kpi-strip">
          <Kpi label="Testers" value={summary.people_count ?? "-"} term="people_count" />
          <Kpi label="Testados" value={summary.cards_tested ?? "-"} term="cards_tested" />
          <Kpi label="1a passagem" value={summary.approved_first_pass ?? "-"} term="approved_first_pass" />
          <Kpi label="Retestes" value={summary.retest_cycles_total ?? "-"} term="retest_cycles_total" />
        </div>
      );
    }
    if (summary.scope === "requesters") {
      return (
        <div className="kpi-strip">
          <Kpi label="Solicitantes" value={summary.people_count ?? "-"} term="people_count" />
          <Kpi label="Criados" value={summary.cards_created ?? "-"} term="cards_created" />
          <Kpi label="Entregues" value={summary.cards_delivered ?? "-"} term="cards_delivered" />
          <Kpi label="Em producao" value={summary.in_production ?? "-"} term="in_production" />
        </div>
      );
    }
  }

  const team = metrics.team_summary ?? {};
  const overview = metrics.overview ?? {};
  const flow = metrics.flow?.team ?? {};
  const items = [];

  if (allowed.includes("team_summary")) {
    items.push(
      <Kpi key="delivered" label="Cards entregues" value={team.cards_delivered ?? "-"} term="cards_delivered" />,
      <Kpi key="quality" label="Qualidade" value={team.quality_rate_pct != null ? `${team.quality_rate_pct}%` : "-"} term="quality_rate_pct" />,
    );
  }
  if (allowed.includes("flow")) {
    items.push(<Kpi key="wip" label="WIP" value={flow.wip_total ?? "-"} term="wip_total" />);
  }
  items.push(<Kpi key="metricados" label="Metricados" value={overview.total_cards_metricados ?? "-"} term="total_cards_metricados" />);

  return <div className="kpi-strip">{items.slice(0, 4)}</div>;
}

function Kpi({ label, value, term }: { label: string; value: string | number; term?: string }) {
  return (
    <div className="kpi">
      <span>
        {label}
        {term ? <HelpTip term={term} /> : null}
      </span>
      <strong>{value}</strong>
    </div>
  );
}

function SnapshotInfo({ report }: { report: GeneratedReport }) {
  if (!report.snapshot) return null;
  return (
    <div className="snapshot-info">
      <span>Snapshot Trello</span>
      <strong>{report.snapshot.cards_count} cards</strong>
      <strong>{report.snapshot.movements_count} movimentos</strong>
      <strong>{report.snapshot.source}</strong>
    </div>
  );
}

function AiAnalysis({ report }: { report: GeneratedReport }) {
  const analysis = report.ai_analysis || report.filtered_metrics?.ai_analysis;
  if (!analysis && report.ai_status !== "error") return null;

  return (
    <section className={report.ai_status === "error" ? "analysis-panel error" : "analysis-panel"}>
      <div className="panel-title compact">
        <BrainCircuit size={18} />
        <h2>Analise IA</h2>
      </div>
      {analysis ? <pre>{analysis}</pre> : <p>{report.ai_error}</p>}
    </section>
  );
}

function MetricSections({ report }: { report: GeneratedReport }) {
  const metrics = report.filtered_metrics ?? {};
  const allowed = new Set(REPORT_PREVIEW_SECTIONS[report.report_type] ?? REPORT_PREVIEW_SECTIONS.general);

  if (allowed.has("individual") && metrics.individual_summary) {
    return (
      <div className="metric-sections">
        <ObjectPanel title="Resumo individual" value={metrics.individual_summary} />
        {Array.isArray(metrics.role_metrics) && metrics.role_metrics.length > 0 ? (
          <MetricTable title="Papeis no periodo" rows={metrics.role_metrics} />
        ) : null}
        {Array.isArray(metrics.collaborators) && metrics.collaborators.length > 0 ? (
          <MetricTable title="Colaborador" rows={metrics.collaborators} />
        ) : null}
        <CardDossier title="Cards do colaborador" metrics={metrics} />
      </div>
    );
  }

  if (allowed.has("role_metrics") && metrics.role_summary) {
    return (
      <div className="metric-sections">
        <ObjectPanel title="Resumo do relatorio" value={metrics.role_summary} />
        {allowed.has("developers") && metrics.developers ? (
          <MetricTable title="Desenvolvedores" rows={metrics.developers} />
        ) : null}
        {allowed.has("testers") && metrics.testers ? (
          <MetricTable title="Testers" rows={metrics.testers} />
        ) : null}
        {allowed.has("requesters") && metrics.requesters ? (
          <MetricTable title="Solicitantes" rows={metrics.requesters} />
        ) : null}
        {allowed.has("projects") && metrics.projects ? (
          <MetricTable title="Projetos" rows={metrics.projects} />
        ) : null}
        {allowed.has("fibonacci") && metrics.fibonacci_points?.by_developer ? (
          <MetricTable title="Pontos Fibonacci" rows={metrics.fibonacci_points.by_developer} />
        ) : null}
        {allowed.has("flow") && metrics.flow?.team ? (
          <ObjectPanel title="Fluxo do time" value={metrics.flow.team} />
        ) : null}
        {allowed.has("quality_gates") && metrics.quality_gates ? (
          <ObjectPanel title="Dupla revisao" value={metrics.quality_gates} />
        ) : null}
        {allowed.has("sla_dev") && metrics.sla?.by_developer ? (
          <MetricTable title="SLA por desenvolvedor" rows={metrics.sla.by_developer} />
        ) : null}
        {allowed.has("bottlenecks") && metrics.bottlenecks?.by_stage ? (
          <MetricTable title="Gargalos" rows={metrics.bottlenecks.by_stage} />
        ) : null}
        {allowed.has("priority") && metrics.priority?.team ? (
          <ObjectPanel title="Prioridade" value={metrics.priority.team} />
        ) : null}
        {allowed.has("dora") && metrics.dora ? (
          <ObjectPanel title="DORA" value={metrics.dora} />
        ) : null}
        {allowed.has("discipline") && metrics.process_discipline ? (
          <ObjectPanel title="Disciplina de processo" value={metrics.process_discipline} />
        ) : null}
        {allowed.has("alerts") && metrics.sla?.current_alerts ? (
          <MetricTable title="Cards em risco" rows={metrics.sla.current_alerts} />
        ) : null}
        <CardDossier title="Cards" metrics={metrics} />
      </div>
    );
  }

  const sections = [
    ["Colaboradores", "collaborators", metrics.collaborators],
    ["Desenvolvedores", "developers", metrics.developers],
    ["Revisores", "reviewers", metrics.reviewers],
    ["Testers", "testers", metrics.testers],
    ["Solicitantes", "requesters", metrics.requesters],
    ["Projetos", "projects", metrics.projects],
    ["Gargalos", "bottlenecks", metrics.bottlenecks?.by_stage],
    ["Cards em risco", "alerts", metrics.sla?.current_alerts],
    ["SLA por desenvolvedor", "sla_dev", metrics.sla?.by_developer],
    ["SLA por card", "sla_cards", metrics.sla?.cards],
  ] as const;

  return (
    <div className="metric-sections">
      {sections.map(([title, key, rows]) =>
        allowed.has(key) && Array.isArray(rows) && rows.length > 0 ? (
          <MetricTable key={title} title={title} rows={rows} />
        ) : null,
      )}
      {allowed.has("team_summary") && metrics.team_summary ? (
        <ObjectPanel title="Resumo do time" value={metrics.team_summary} />
      ) : null}
      {allowed.has("flow") && metrics.flow?.team ? (
        <ObjectPanel title="Fluxo do time" value={metrics.flow.team} />
      ) : null}
      {allowed.has("priority") && metrics.priority?.team ? (
        <ObjectPanel title="Prioridade" value={metrics.priority.team} />
      ) : null}
      {allowed.has("dora") && metrics.dora ? (
        <ObjectPanel title="DORA" value={metrics.dora} />
      ) : null}
      {allowed.has("quality_gates") && metrics.quality_gates ? (
        <ObjectPanel title="Dupla revisao" value={metrics.quality_gates} />
      ) : null}
      {allowed.has("discipline") && metrics.process_discipline ? (
        <ObjectPanel title="Disciplina de processo" value={metrics.process_discipline} />
      ) : null}
      <CardDossier title="Cards" metrics={metrics} />
    </div>
  );
}

function ManagementMetricGuide({ report }: { report: GeneratedReport }) {
  const intro = sectionGuide("management_intro");
  const sections = MANAGEMENT_GUIDE_SECTIONS.filter((id) => id !== "management_intro");

  return (
    <section className="management-guide">
      <h3>{intro.title || "Guia de metricas para gestao"}</h3>
      {intro.description ? <p className="table-description">{intro.description}</p> : null}
      {sections.map((sectionId) => {
        const guide = sectionGuide(sectionId);
        if (!guide.title && !(guide.metrics || []).length) return null;
        return (
          <details key={sectionId} className="guide-section" open={sectionId === "sla"}>
            <summary>{guide.title || sectionId}</summary>
            {guide.description ? <p className="table-description">{guide.description}</p> : null}
            <ol className="guide-metrics">
              {(guide.metrics || []).map((item: { key: string; formula?: string; example?: string }) => (
                <li key={item.key}>
                  <strong>{metricLabel(item.key)}</strong>
                  <p>{item.formula || metricDescription(item.key)}</p>
                  {item.example ? <p className="guide-example">Exemplo: {item.example}</p> : null}
                </li>
              ))}
            </ol>
          </details>
        );
      })}
    </section>
  );
}

function MetricTable({ title, rows }: { title: string; rows: Array<Record<string, any>> }) {
  const tableId = SECTION_TABLE_IDS[title];
  const description = tableId ? tableDescription(tableId) : "";
  const columns = Object.keys(rows[0] ?? {})
    .filter((key) => isSimple(rows[0][key]))
    .slice(0, 8);

  return (
    <section className="table-block">
      <h3>{title}</h3>
      {description ? <p className="table-description">{description}</p> : null}
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column}>
                  {metricLabel(column)}
                  <HelpTip term={column} />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, 12).map((row, index) => (
              <tr key={`${title}-${index}`}>
                {columns.map((column) => (
                  <td key={column}>{formatCell(row[column], column)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <MetricLegend columns={columns} />
    </section>
  );
}

function MetricLegend({ columns }: { columns: string[] }) {
  const items = columns
    .map((key) => ({ key, label: metricLabel(key), description: metricDescription(key) }))
    .filter((item) => item.description);

  if (!items.length) return null;

  return (
    <details className="metric-legend">
      <summary>Como ler esta tabela</summary>
      <ul>
        {items.map((item) => (
          <li key={item.key}>
            <strong>{item.label}</strong>: {item.description}
          </li>
        ))}
      </ul>
    </details>
  );
}

function ObjectPanel({ title, value }: { title: string; value: Record<string, any> }) {
  return (
    <section className="object-panel">
      <h3>{title}</h3>
      <div className="object-grid">
        {Object.entries(value)
          .filter(([, item]) => isSimple(item))
          .slice(0, 12)
          .map(([key, item]) => (
            <div key={key}>
              <span>
                {metricLabel(key)}
                <HelpTip term={key} />
              </span>
              <strong>{formatCell(item, key)}</strong>
            </div>
          ))}
      </div>
    </section>
  );
}

function CardDossier({ title, metrics }: { title: string; metrics: Record<string, any> }) {
  const cards = collectCards(metrics).slice(0, 40);
  if (!cards.length) return null;

  return (
    <section className="card-dossier">
      <h3>{title}</h3>
      <div className="card-dossier-list">
        {cards.map((card, index) => (
          <details className="card-detail" key={`${card.card_id ?? card.id ?? card.card_name}-${index}`}>
            <summary>
              <span className="card-index">{cardIndex(card, index)}</span>
              <span className="card-title">{formatCell(card.card_name ?? card.name, "card_name")}</span>
              <span className="card-meta">{cardMeta(card)}</span>
              {card.url ? (
                <a
                  className="card-link"
                  href={String(card.url)}
                  target="_blank"
                  rel="noreferrer"
                  title="Abrir no Trello"
                  onClick={(event) => event.stopPropagation()}
                >
                  <ExternalLink size={15} />
                </a>
              ) : null}
              <ChevronDown className="card-chevron" size={16} />
            </summary>
            <CardDetailBody card={card} />
          </details>
        ))}
      </div>
    </section>
  );
}

function CardDetailBody({ card }: { card: Record<string, any> }) {
  const facts = [
    "desenvolvedor",
    "tester",
    "solicitante",
    "sistema",
    "fibonacci_level",
    "lead_time_human",
    "cycle_time_human",
    "collaborator_time_human",
    "current_list",
  ].filter((key) => card[key] !== undefined && card[key] !== null && card[key] !== "");
  const etapas = Array.isArray(card.etapas) ? card.etapas.slice(0, 10) : [];
  const retornos = Array.isArray(card.retornos) ? card.retornos.slice(0, 6) : [];
  const descricao = isRecord(card.descricao)
    ? Object.entries(card.descricao).filter(([, value]) => value)
    : [];

  return (
    <div className="card-detail-body">
      {facts.length ? (
        <div className="card-facts">
          {facts.map((key) => (
            <div key={key}>
              <span>{metricLabel(key)}</span>
              <strong>{formatCell(card[key], key)}</strong>
            </div>
          ))}
        </div>
      ) : null}

      {descricao.length ? (
        <div className="card-notes">
          {descricao.map(([key, value]) => (
            <p key={key}>
              <strong>{metricLabel(key)}</strong>
              {String(value)}
            </p>
          ))}
        </div>
      ) : null}

      {etapas.length ? (
        <div className="mini-table-scroll">
          <table className="mini-table">
            <thead>
              <tr>
                <th>Etapa</th>
                <th>Lista</th>
                <th>Tempo</th>
              </tr>
            </thead>
            <tbody>
              {etapas.map((stage: Record<string, any>, index: number) => (
                <tr key={`${stage.group ?? stage.title}-${index}`}>
                  <td>{formatCell(stage.title ?? stage.group)}</td>
                  <td>{formatCell(stage.list_name)}</td>
                  <td>{formatCell(stage.hours_human ?? stage.hours)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {retornos.length ? (
        <div className="return-list">
          {retornos.map((item: Record<string, any>, index: number) => (
            <div key={`${item.numero ?? index}-${item.at ?? ""}`}>
              <strong>{`Retorno ${formatCell(item.numero ?? index + 1)}`}</strong>
              <span>{[item.tipo, item.subtipo, item.atribuido_a].filter(Boolean).join(" / ")}</span>
              <p>{formatCell(item.motivo || item.solucao)}</p>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function collectCards(metrics: Record<string, any>): Array<Record<string, any>> {
  const cards: Array<Record<string, any>> = [];
  const seen = new Set<string>();

  const push = (value: unknown, context?: Record<string, any>) => {
    if (!isRecord(value)) return;
    const cardId = value.card_id ?? value.id;
    const name = value.card_name ?? value.name;
    if (!cardId && !name) return;
    const key = String(cardId ?? name);
    if (seen.has(key)) return;
    seen.add(key);
    cards.push({ ...context, ...value });
  };

  if (Array.isArray(metrics.collaborators)) {
    metrics.collaborators.forEach((collaborator: Record<string, any>) => {
      if (Array.isArray(collaborator.cards)) {
        collaborator.cards.forEach((card: unknown) => {
          push(card, { collaborator_name: collaborator.name });
        });
      }
    });
  }

  if (Array.isArray(metrics.cards)) {
    metrics.cards.forEach((card: unknown) => push(card));
  }

  const dossier = metrics.card_dossier;
  if (isRecord(dossier)) {
    collectDeveloperCards(dossier.by_developer, push);
    collectNamedCardBucket(dossier.by_solicitante, push);
    collectNamedCardBucket(dossier.by_tester, push);
  }

  return cards;
}

function collectDeveloperCards(
  bucket: unknown,
  push: (value: unknown, context?: Record<string, any>) => void,
) {
  if (!isRecord(bucket)) return;
  Object.entries(bucket).forEach(([owner, groups]) => {
    if (!isRecord(groups)) return;
    ["tarefas_normais", "cards_analise"].forEach((key) => {
      const rows = groups[key];
      if (Array.isArray(rows)) {
        rows.forEach((card) => push(card, { dossier_owner: owner }));
      }
    });
  });
}

function collectNamedCardBucket(
  bucket: unknown,
  push: (value: unknown, context?: Record<string, any>) => void,
) {
  if (!isRecord(bucket)) return;
  Object.entries(bucket).forEach(([owner, rows]) => {
    if (Array.isArray(rows)) {
      rows.forEach((card) => push(card, { dossier_owner: owner }));
    }
  });
}

function cardIndex(card: Record<string, any>, index: number): string {
  const idShort = card.id_short ?? card.idShort;
  return idShort ? `#${idShort}` : `#${index + 1}`;
}

function cardMeta(card: Record<string, any>): string {
  return [
    card.current_list,
    card.sistema,
    card.kind,
    card.collaborator_time_human,
  ]
    .filter(Boolean)
    .join(" / ");
}

function isRecord(value: unknown): value is Record<string, any> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function toggleMetric(
  metric: string,
  selected: string[],
  setSelected: Dispatch<SetStateAction<string[]>>,
) {
  if (selected.includes(metric)) {
    setSelected(selected.filter((item) => item !== metric));
  } else {
    setSelected([...selected, metric]);
  }
}

function defaultModelFor(provider: AIProvider, options: ReportOptions): string {
  return (
    options.ai_providers.find((item) => item.value === provider)?.default_model ??
    fallbackOptions.ai_providers.find((item) => item.value === provider)?.default_model ??
    ""
  );
}

function currentMonth(): string {
  return new Date().toISOString().slice(0, 7);
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function humanize(value: string): string {
  return metricLabel(value);
}

function isSimple(value: unknown): boolean {
  return value == null || ["string", "number", "boolean"].includes(typeof value);
}

function formatCell(value: unknown, key?: string): string {
  if (value == null || value === "") return "-";
  if (typeof value === "number") {
    if (key?.endsWith("_pct")) return `${value}%`;
    return Number.isInteger(value) ? `${value}` : value.toFixed(1);
  }
  if (typeof value === "boolean") return value ? "Sim" : "Nao";
  return String(value);
}

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : "Erro inesperado.";
}

export default App;
