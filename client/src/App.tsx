import {
  BarChart3,
  BrainCircuit,
  CalendarDays,
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
  Trash2,
  User,
  UserPlus,
  Users,
  type LucideIcon,
} from "lucide-react";
import { type Dispatch, type FormEvent, type SetStateAction, useEffect, useMemo, useRef, useState } from "react";

import {
  clearStoredToken,
  createCollaborator,
  deleteAllReports,
  deleteReport,
  downloadReport,
  generateReport,
  getReport,
  getMe,
  getReportOptions,
  getStoredToken,
  listCollaborators,
  listReports,
  login,
  syncCollaboratorsFromTrello,
  updateCollaborator,
} from "./api/client";
import { LoadingOverlay } from "./components/LoadingOverlay";
import { HelpTip } from "./components/HelpTip";
import { CalendarPanel } from "./components/CalendarPanel";
import {
  REPORT_PREVIEW_SECTIONS,
  TAB_DESCRIPTIONS,
  allowedSectionsForReport,
} from "./lib/reportLayouts";
import {
  AI_MAX_OUTPUT_TOKENS,
  type AIProvider,
  type Collaborator,
  type GenerateReportPayload,
  type GeneratedReport,
  type ReportOptions,
  type ReportType,
} from "./types/report";
import { AiMarkdown } from "./utils/aiMarkdown";
import {
  MANAGEMENT_GUIDE_SECTIONS,
  metricDescription,
  metricExample,
  metricFormula,
  metricLabel,
  sectionGuide,
  SECTION_TABLE_IDS,
  SLA_ALERTS_TABLE_TITLE,
  tableDescription,
} from "./lib/metricDefinitions";

const tabs: Array<{ value: ReportType; label: string; icon: LucideIcon }> = [
  { value: "general", label: "Geral", icon: BarChart3 },
  { value: "individual", label: "Individual", icon: User },
  { value: "developers", label: "Desenvolvedores", icon: Users },
  { value: "requesters", label: "Solicitantes", icon: ClipboardList },
  { value: "testers", label: "Testers", icon: ShieldCheck },
  { value: "reviewers", label: "Revisao em par", icon: Users },
  { value: "formal_reviewers", label: "Revisores", icon: ClipboardList },
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
    { value: "reviewers", label: "Revisao em par" },
    { value: "formal_reviewers", label: "Revisores" },
    { value: "requesters", label: "Solicitantes" },
    { value: "sla", label: "SLA" },
    { value: "bottlenecks", label: "Gargalos" },
    { value: "card_dossier", label: "Detalhamento" },
  ],
  ai_providers: [
    {
      value: "openai",
      label: "GPT",
      default_model: "gpt-4o-mini",
      models: [
        { value: "gpt-4o-mini", label: "GPT-4o Mini (padrao)" },
        { value: "gpt-4o", label: "GPT-4o" },
        { value: "gpt-4.1-mini", label: "GPT-4.1 Mini" },
      ],
    },
    {
      value: "gemini",
      label: "Gemini",
      default_model: "gemini-2.5-flash",
      models: [
        { value: "gemini-2.5-flash", label: "Gemini 2.5 Flash (padrao)" },
        { value: "gemini-2.5-flash-lite", label: "Gemini 2.5 Flash Lite" },
        { value: "gemini-2.5-pro", label: "Gemini 2.5 Pro" },
        { value: "gemini-3.5-flash", label: "Gemini 3.5 Flash" },
      ],
    },
    {
      value: "claude",
      label: "Claude",
      default_model: "claude-sonnet-4-20250514",
      models: [
        { value: "claude-sonnet-4-20250514", label: "Claude Sonnet 4 (padrao)" },
        { value: "claude-3-5-sonnet-latest", label: "Claude 3.5 Sonnet" },
        { value: "claude-3-5-haiku-latest", label: "Claude 3.5 Haiku" },
      ],
    },
  ],
};

function App() {
  const [token, setToken] = useState(getStoredToken());
  const [username, setUsername] = useState("");
  const [loginName, setLoginName] = useState(import.meta.env.DEV ? "gestor" : "");
  const [password, setPassword] = useState(import.meta.env.DEV ? "intgest" : "");
  const [activeTab, setActiveTab] = useState<ReportType>("general");
  const [options, setOptions] = useState<ReportOptions>(fallbackOptions);
  const [reports, setReports] = useState<GeneratedReport[]>([]);
  const [collaborators, setCollaborators] = useState<Collaborator[]>([]);
  const [currentReport, setCurrentReport] = useState<GeneratedReport | null>(null);
  const selectedByTabRef = useRef<Partial<Record<ReportType, string>>>({});
  const [loading, setLoading] = useState(false);
  const [loadingLabel, setLoadingLabel] = useState("Carregando");
  const [exporting, setExporting] = useState<"pdf" | "json" | "html" | null>(null);
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
  const [syncingCollaborators, setSyncingCollaborators] = useState(false);
  const [historyExpanded, setHistoryExpanded] = useState(false);
  const [showCalendar, setShowCalendar] = useState(false);
  const historyMenuRef = useRef<HTMLDivElement>(null);
  const [metricKeys, setMetricKeys] = useState<string[]>(["team_summary", "flow", "sla"]);

  const [aiEnabled, setAiEnabled] = useState(false);
  const [aiProvider, setAiProvider] = useState<AIProvider>("openai");
  const [aiModel, setAiModel] = useState("gpt-4o-mini");
  const [aiKey, setAiKey] = useState("");

  useEffect(() => {
    if (!token) return;
    void bootstrap(token);
  }, [token]);

  useEffect(() => {
    if (!token) return;
    void loadHistoryForTab(activeTab);
    setHistoryExpanded(false);
  }, [activeTab, token]);

  useEffect(() => {
    if (!historyExpanded) return;

    function handlePointerDown(event: MouseEvent) {
      if (!historyMenuRef.current?.contains(event.target as Node)) {
        setHistoryExpanded(false);
      }
    }

    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setHistoryExpanded(false);
      }
    }

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [historyExpanded]);

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
      setAiModel((current) => ensureValidModel(aiProvider, current, loadedOptions));
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
        collaborator_name: collaboratorName || undefined,
        metric_keys: activeTab === "specific_metrics" ? metricKeys : undefined,
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
          max_tokens: AI_MAX_OUTPUT_TOKENS,
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
    if (exporting) return;
    setExporting(format);
    setError("");
    try {
      await downloadReport(token, report.id, format, reportFileBaseName(report));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setExporting(null);
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

  async function handleDeleteReport(report: GeneratedReport, event: React.MouseEvent) {
    event.stopPropagation();
    if (!window.confirm(`Excluir o relatorio "${report.title}"? Esta acao nao pode ser desfeita.`)) return;
    setError("");
    try {
      await deleteReport(token, report.id);
      if (currentReport?.id === report.id) setCurrentReport(null);
      await loadHistoryForTab(activeTab);
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function handleDeleteAllReports() {
    if (reports.length === 0) return;
    if (!window.confirm(`Excluir TODOS os ${reports.length} relatorios da aba "${activeTabLabel}"? Esta acao nao pode ser desfeita.`)) return;
    setError("");
    try {
      await deleteAllReports(token, activeTab);
      setCurrentReport(null);
      await loadHistoryForTab(activeTab);
    } catch (err) {
      setError(errorMessage(err));
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

  async function handleSyncCollaborators() {
    if (!useLiveApi) {
      setError("Ative a API do Trello para sincronizar colaboradores.");
      return;
    }
    setError("");
    setSyncingCollaborators(true);
    setLoadingLabel("Sincronizando colaboradores do Trello");
    setLoading(true);
    try {
      const result = await syncCollaboratorsFromTrello(token, {
        board_id: boardId || undefined,
        api_key: trelloApiKey || undefined,
        token: trelloToken || undefined,
      });
      setCollaborators(
        [...result.collaborators].sort((a, b) => a.name.localeCompare(b.name)),
      );
      if (!collaboratorName && result.collaborators.length > 0) {
        const firstActive = result.collaborators.find((item) => item.active);
        if (firstActive) setCollaboratorName(firstActive.name);
      }
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSyncingCollaborators(false);
      setLoading(false);
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
    const previousTitle = document.title;
    if (currentReport) {
      document.title = reportFileBaseName(currentReport);
    }
    const restore = () => {
      document.title = previousTitle;
      window.removeEventListener("afterprint", restore);
    };
    window.addEventListener("afterprint", restore);
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

  const overlayLabel = useMemo(() => {
    if (exporting === "pdf") return "Gerando PDF";
    if (exporting === "html") return "Gerando HTML";
    if (exporting === "json") return "Gerando JSON";
    return loadingLabel;
  }, [exporting, loadingLabel]);

  if (!token) {
    return (
      <main className="login-shell">
        <LoadingOverlay show={loading || exporting !== null} label={overlayLabel} />
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
      <LoadingOverlay show={loading || exporting !== null} label={overlayLabel} />
      <header className="topbar">
        <div className="brand-row">
          <div className="brand-mark">ig</div>
          <div>
            <strong>INTGEST</strong>
            <span>{activeTabLabel}</span>
          </div>
        </div>
        <div className="topbar-actions">
          <div
            className={`history-menu${reports.length > 0 ? " has-reports" : ""}`}
            ref={historyMenuRef}
          >
            <button
              type="button"
              className={`history-trigger${historyExpanded ? " open" : ""}`}
              onClick={() => setHistoryExpanded((open) => !open)}
              aria-expanded={historyExpanded}
              aria-haspopup="dialog"
              title={`Relatorios salvos da aba ${activeTabLabel}`}
            >
              <ClipboardList size={17} />
              <span className="history-trigger-label">Historico</span>
              <span className="history-count">{reports.length}</span>
              <ChevronDown size={15} className="history-chevron" />
            </button>
            {historyExpanded ? (
              <div className="history-dropdown" role="dialog" aria-label="Historico de relatorios">
                <div className="history-dropdown-header">
                  <div>
                    <strong>Relatorios salvos</strong>
                    <span>{activeTabLabel}</span>
                  </div>
                  {reports.length > 0 ? (
                    <button
                      type="button"
                      className="ghost-btn danger"
                      onClick={() => void handleDeleteAllReports()}
                      title="Excluir todos os relatorios desta aba"
                    >
                      <Trash2 size={14} /> Limpar
                    </button>
                  ) : null}
                </div>
                <div className="history-list">
                  {reports.length > 0 ? (
                    reports.map((report) => (
                      <div
                        key={report.id}
                        className={currentReport?.id === report.id ? "history-item active" : "history-item"}
                        onClick={() => {
                          void handleSelectReport(report);
                          setHistoryExpanded(false);
                        }}
                        role="button"
                        tabIndex={0}
                      >
                        <div className="history-item-info">
                          <strong>{report.title}</strong>
                          <span>{formatDate(report.created_at)}</span>
                        </div>
                        <button
                          type="button"
                          className="history-item-delete"
                          onClick={(event) => void handleDeleteReport(report, event)}
                          title="Excluir este relatorio"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    ))
                  ) : (
                    <p className="history-empty">Nenhum relatorio salvo nesta aba ainda.</p>
                  )}
                </div>
              </div>
            ) : null}
          </div>
          <span className="user-chip">{username}</span>
          <button
            className={`icon-button${showCalendar ? " active" : ""}`}
            type="button"
            onClick={() => setShowCalendar((open) => !open)}
            title="Calendario operacional"
          >
            <CalendarDays size={18} />
          </button>
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

      {showCalendar ? (
        <section className="workspace">
          <CalendarPanel
            token={token}
            collaborators={collaborators}
            month={month}
            onError={setError}
          />
        </section>
      ) : null}

      <section className="workspace" style={showCalendar ? { display: "none" } : undefined}>
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
                <select
                  value={aiModel}
                  disabled={!aiEnabled}
                  onChange={(event) => setAiModel(event.target.value)}
                >
                  {modelsForProvider(aiProvider, options).map((model) => (
                    <option key={model.value} value={model.value}>
                      {model.label}
                    </option>
                  ))}
                </select>
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
            <button
              type="button"
              className="sync-collaborators-button"
              disabled={!useLiveApi || syncingCollaborators}
              onClick={() => void handleSyncCollaborators()}
            >
              <RefreshCw size={16} className={syncingCollaborators ? "spin" : undefined} />
              Sincronizar do Trello
            </button>
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
                  <button type="button" disabled={exporting !== null} onClick={() => void handleDownload(currentReport, "html")}>
                    <Globe size={17} />
                    HTML
                  </button>
                  <button type="button" disabled={exporting !== null} onClick={() => void handleDownload(currentReport, "pdf")}>
                    <Download size={17} />
                    PDF
                  </button>
                  <button type="button" disabled={exporting !== null} onClick={() => void handleDownload(currentReport, "json")}>
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
              <MetricCalculationGuide report={currentReport} />
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
      </section>
    </main>
  );
}

function KpiStrip({ report }: { report: GeneratedReport }) {
  const metrics = report.filtered_metrics ?? {};
  const allowed = allowedSectionsForReport(report.report_type, report.metric_keys);

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

  if (report.report_type === "management") {
    const flow = metrics.flow?.team ?? {};
    const dora = metrics.dora ?? {};
    const frequency = dora.deployment_frequency ?? {};
    const slaTeam = metrics.sla?.team ?? {};
    const discipline = metrics.process_discipline?.flow_conformity ?? {};
    const risk = metrics.risk_board ?? {};
    return (
      <div className="kpi-strip">
        <Kpi label="Entregues" value={team.cards_delivered ?? "-"} term="cards_delivered" />
        <Kpi
          label="SLA time"
          value={slaTeam.compliance_pct != null ? `${slaTeam.compliance_pct}%` : "-"}
          term="compliance_pct"
        />
        <Kpi label="Deploys" value={frequency.total ?? "-"} term="deployments_evaluated" />
        <Kpi
          label="LT deploy P85"
          value={dora.lead_time_deploy?.p85_human ?? "-"}
          term="lead_time_deploy"
        />
        <Kpi
          label="Conformidade"
          value={discipline.compliance_pct != null ? `${discipline.compliance_pct}%` : "-"}
          term="compliance_pct"
        />
        <Kpi label="Risco alto" value={risk.high_or_critical_count ?? "-"} term="high_or_critical_count" />
        <Kpi label="WIP" value={flow.wip_total ?? "-"} term="wip_total" />
      </div>
    );
  }

  const flow = metrics.flow?.team ?? {};
  const items = [];

  if (allowed.has("team_summary")) {
    items.push(
      <Kpi key="delivered" label="Cards entregues" value={team.cards_delivered ?? "-"} term="cards_delivered" />,
      <Kpi key="quality" label="Qualidade" value={team.quality_rate_pct != null ? `${team.quality_rate_pct}%` : "-"} term="quality_rate_pct" />,
    );
  }
  if (allowed.has("flow")) {
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
  const status = report.ai_status || report.filtered_metrics?.ai?.status;

  if (!analysis && status === "disabled") return null;

  return (
    <section className={status === "error" ? "analysis-panel error" : "analysis-panel"}>
      <div className="panel-title compact">
        <BrainCircuit size={18} />
        <div>
          <h2>Analise IA</h2>
          {status && status !== "generated" ? (
            <span className="ai-status-chip">{aiStatusLabel(status)}</span>
          ) : null}
          {report.ai_provider ? (
            <span className="ai-meta">
              {report.ai_provider} · {report.ai_model || "modelo padrao"}
            </span>
          ) : null}
        </div>
      </div>
      {analysis ? <AiMarkdown text={analysis} /> : <p>{report.ai_error || "Analise nao gerada."}</p>}
    </section>
  );
}

function aiStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    skipped: "IA desativada — informe API key",
    error: "Erro na geracao",
    empty: "Resposta vazia",
    disabled: "IA desligada",
  };
  return labels[status] ?? status;
}

function MetricSections({ report }: { report: GeneratedReport }) {
  const metrics = report.filtered_metrics ?? {};
  const allowed = allowedSectionsForReport(report.report_type, report.metric_keys);
  const showCardDossier =
    report.report_type !== "specific_metrics" || (report.metric_keys ?? []).includes("card_dossier");

  if (report.report_type === "management") {
    return <ManagementSections metrics={metrics} allowed={allowed} />;
  }

  if (allowed.has("individual") && metrics.individual_summary) {
    const collaborator = metrics.collaborators?.[0];
    return (
      <div className="metric-sections">
        <ObjectPanel title="Resumo individual" value={metrics.individual_summary} />
        {collaborator ? (
          <PersonRoleSections collaborator={collaborator} dossier={metrics.card_dossier} />
        ) : showCardDossier ? (
          <CardDossier title="Cards do colaborador" metrics={metrics} />
        ) : null}
      </div>
    );
  }

  if (
    (report.report_type === "developers" && metrics.developers) ||
    (report.report_type === "testers" && metrics.testers) ||
    (report.report_type === "requesters" && metrics.requesters)
  ) {
    return (
      <PeopleTabSections
        report={report}
        metrics={metrics}
        allowed={allowed}
        showCardDossier={showCardDossier}
      />
    );
  }

  if (report.report_type === "reviewers" || report.report_type === "formal_reviewers") {
    const isPeer = report.report_type === "reviewers";
    const rows = isPeer ? metrics.reviewers : metrics.formal_reviewers;
    const title = isPeer ? "Revisao em par" : "Revisores";
    return (
      <div className="metric-sections">
        {metrics.role_summary ? (
          <ObjectPanel title="Resumo do relatorio" value={metrics.role_summary} />
        ) : null}
        {Array.isArray(rows) && rows.length > 0 ? <MetricTable title={title} rows={rows} /> : null}
        {allowed.has("quality_gates") && metrics.quality_gates ? (
          <ObjectPanel title="Dupla revisao" value={metrics.quality_gates} />
        ) : null}
        {showCardDossier ? <CardDossier title="Cards" metrics={metrics} /> : null}
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
        {allowed.has("reviewers") && metrics.reviewers ? (
          <MetricTable title="Revisao em par" rows={metrics.reviewers} />
        ) : null}
        {allowed.has("formal_reviewers") && metrics.formal_reviewers ? (
          <MetricTable title="Revisores" rows={metrics.formal_reviewers} />
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
          <MetricTable
            title={SLA_ALERTS_TABLE_TITLE}
            rows={metrics.sla.current_alerts}
            hiddenColumns={["desenvolvedor", "solicitante", "tester", "revisor", "revisor_par"]}
          />
        ) : null}
        {showCardDossier ? <CardDossier title="Cards" metrics={metrics} /> : null}
      </div>
    );
  }

  const sections = [
    ["Desenvolvedores", "developers", metrics.developers],
    ["Revisao em par", "reviewers", metrics.reviewers],
    ["Revisores", "formal_reviewers", metrics.formal_reviewers],
    ["Testers", "testers", metrics.testers],
    ["Solicitantes", "requesters", metrics.requesters],
    ["Projetos", "projects", metrics.projects],
    ["Gargalos", "bottlenecks", metrics.bottlenecks?.by_stage],
    [SLA_ALERTS_TABLE_TITLE, "alerts", metrics.sla?.current_alerts],
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
      {allowed.has("collaborators") && Array.isArray(metrics.collaborators) && metrics.collaborators.length > 0 ? (
        <CollaboratorsSections collaborators={metrics.collaborators} dossier={metrics.card_dossier} />
      ) : null}
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
      {allowed.has("antifraud") && metrics.antifraud ? (
        <AntifraudPanel antifraud={metrics.antifraud} />
      ) : null}
      {showCardDossier && !metrics.collaborators?.length ? (
        <CardDossier title="Cards" metrics={metrics} />
      ) : null}
    </div>
  );
}

function ManagementSections({
  metrics,
  allowed,
}: {
  metrics: Record<string, any>;
  allowed: Set<string>;
}) {
  const trends = metrics.trends_6m;
  const trendRows = (trends?.team ?? []).map((row: Record<string, any>) => ({
    month: row.month,
    cards_delivered: row.cards_delivered,
    quality_rate_pct: row.quality_rate_pct,
    rework_rate_pct: row.rework_rate_pct,
  }));

  return (
    <div className="metric-sections">
      {allowed.has("team_summary") && metrics.team_summary ? (
        <ObjectPanel title="Resumo do time" value={metrics.team_summary} />
      ) : null}
      {allowed.has("flow") && metrics.flow?.team ? (
        <>
          <ObjectPanel title="Fluxo do time" value={metrics.flow.team} />
          {Array.isArray(metrics.flow.aging_baseline) && metrics.flow.aging_baseline.length > 0 ? (
            <MetricTable title="Baseline aging por etapa" rows={metrics.flow.aging_baseline} />
          ) : null}
          {Array.isArray(metrics.flow.net_flow?.series) && metrics.flow.net_flow.series.length > 0 ? (
            <MetricTable title="Net flow semanal" rows={metrics.flow.net_flow.series} />
          ) : null}
        </>
      ) : null}
      {metrics.first_time_right ? (
        <ObjectPanel title="First-Time-Right" value={metrics.first_time_right} />
      ) : null}
      {metrics.member_assignment ? (
        <ObjectPanel title="Atribuicao de membros" value={metrics.member_assignment} />
      ) : null}
      {metrics.due_predictability ? (
        <ObjectPanel title="Previsibilidade (due)" value={metrics.due_predictability} />
      ) : null}
      {metrics.board_moves ? (
        <ObjectPanel title="Movimentacao entre boards" value={metrics.board_moves} />
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
        <>
          <ObjectPanel title="Disciplina de processo" value={metrics.process_discipline} />
          {(metrics.process_discipline.post_terminal_returns?.count ?? 0) > 0 ? (
            <MetricTable
              title="Retornos apos producao/analise finalizada"
              rows={metrics.process_discipline.post_terminal_returns.cards ?? []}
            />
          ) : null}
        </>
      ) : null}
      {allowed.has("analysis_workflow") && metrics.analysis_workflow ? (
        <>
          <ObjectPanel title="Cards de analise" value={metrics.analysis_workflow} />
          {Array.isArray(metrics.analysis_workflow.highlight_cards) &&
          metrics.analysis_workflow.highlight_cards.length > 0 ? (
            <MetricTable title="Analises em destaque" rows={metrics.analysis_workflow.highlight_cards} />
          ) : null}
        </>
      ) : null}
      {allowed.has("antifraud") && metrics.antifraud ? (
        <AntifraudPanel antifraud={metrics.antifraud} />
      ) : null}
      {allowed.has("risk") && metrics.risk_board ? (
        <>
          <ObjectPanel title="Risco" value={metrics.risk_board} />
          {Array.isArray(metrics.risk_board.cards_that_need_attention) &&
          metrics.risk_board.cards_that_need_attention.length > 0 ? (
            <MetricTable title="Cards que precisam de atencao" rows={metrics.risk_board.cards_that_need_attention} />
          ) : null}
        </>
      ) : null}
      {allowed.has("trends") && trendRows.length > 0 ? (
        <MetricTable title="Tendencia 6 meses" rows={trendRows} />
      ) : null}
      {allowed.has("projects") && metrics.projects ? (
        <MetricTable title="Projetos" rows={metrics.projects} />
      ) : null}
      {allowed.has("bottlenecks") && metrics.bottlenecks?.by_stage ? (
        <MetricTable title="Gargalos" rows={metrics.bottlenecks.by_stage} />
      ) : null}
      {allowed.has("sla_dev") && metrics.sla?.by_developer ? (
        <MetricTable title="SLA por desenvolvedor" rows={metrics.sla.by_developer} />
      ) : null}
      {allowed.has("alerts") && metrics.sla?.current_alerts ? (
        <MetricTable
          title={SLA_ALERTS_TABLE_TITLE}
          rows={metrics.sla.current_alerts}
          hiddenColumns={["desenvolvedor", "solicitante", "tester", "revisor", "revisor_par"]}
        />
      ) : null}
      {metrics.bottlenecks?.management_only_view ? (
        <ObjectPanel title="Visao gerencial por lista" value={metrics.bottlenecks.management_only_view} />
      ) : null}
    </div>
  );
}

const ROLE_DESCRIPTIONS: Record<string, string> = {
  solicitante: "Demandas criadas, planejamento, aprovacoes e entregas solicitadas no periodo.",
  desenvolvedor: "Entregas, pontos Fibonacci, retrabalhos, SLA e tempo em desenvolvimento.",
  revisor_par: "Sugestoes aceitas na revisao em par (garantia de qualidade) e escapes posteriores.",
  revisor: "Revisoes formais, retornos ao DEV e escapes detectados no teste.",
  tester: "Testes, primeira passagem, retestes, retornos e problemas evitados.",
};

function PeopleTabSections({
  report,
  metrics,
  allowed,
  showCardDossier,
}: {
  report: GeneratedReport;
  metrics: Record<string, any>;
  allowed: Set<string>;
  showCardDossier: boolean;
}) {
  const config =
    report.report_type === "developers"
      ? { title: "Desenvolvedor", rows: metrics.developers, bucket: "by_developer" as const }
      : report.report_type === "testers"
        ? { title: "Tester", rows: metrics.testers, bucket: "by_tester" as const }
        : { title: "Solicitante", rows: metrics.requesters, bucket: "by_solicitante" as const };

  return (
    <div className="metric-sections">
      {metrics.role_summary ? (
        <ObjectPanel title="Resumo do relatorio" value={metrics.role_summary} />
      ) : null}
      {allowed.has("flow") && metrics.flow?.team ? (
        <ObjectPanel title="Fluxo do time" value={metrics.flow.team} />
      ) : null}
      {allowed.has("quality_gates") && metrics.quality_gates ? (
        <ObjectPanel title="Dupla revisao" value={metrics.quality_gates} />
      ) : null}
      {allowed.has("fibonacci") && metrics.fibonacci_points?.by_developer ? (
        <MetricTable title="Pontos Fibonacci" rows={metrics.fibonacci_points.by_developer} />
      ) : null}
      {allowed.has("sla_dev") && metrics.sla?.by_developer ? (
        <MetricTable title="SLA por desenvolvedor" rows={metrics.sla.by_developer} />
      ) : null}
      {Array.isArray(config.rows)
        ? config.rows.map((person: Record<string, any>) => (
            <section className="person-section" key={person.name ?? person.id}>
              <h3>
                {config.title}: {person.name}
              </h3>
              <ObjectPanel title="Metricas" value={person} />
              <CardDossier
                title="Cards no periodo"
                metrics={metrics}
                cards={dossierCardsForPerson(metrics.card_dossier, config.bucket, person.name, person.aliases)}
              />
            </section>
          ))
        : null}
      {showCardDossier && !config.rows?.length ? <CardDossier title="Cards" metrics={metrics} /> : null}
    </div>
  );
}

function CollaboratorsSections({
  collaborators,
  dossier,
}: {
  collaborators: Array<Record<string, any>>;
  dossier?: Record<string, any>;
}) {
  return (
    <section className="collaborators-sections">
      <h3>Colaboradores</h3>
      <p className="table-description">
        Cada colaborador com subsecoes por papel (solicitante, desenvolvedor, revisor, revisor em par, tester) e
        cards detalhados com movimentacao.
      </p>
      {collaborators.map((collaborator) => (
        <section className="person-section" key={collaborator.id ?? collaborator.name}>
          <h3>Colaborador: {collaborator.name}</h3>
          {collaborator.summary ? <ObjectPanel title="Resumo" value={collaborator.summary} /> : null}
          <PersonRoleSections collaborator={collaborator} dossier={dossier} />
        </section>
      ))}
    </section>
  );
}

function PersonRoleSections({
  collaborator,
  dossier,
}: {
  collaborator: Record<string, any>;
  dossier?: Record<string, any>;
}) {
  const roles = Array.isArray(collaborator.role_metrics) ? collaborator.role_metrics : [];
  if (!roles.length) {
    return <CardDossier title="Cards" metrics={{ collaborators: [collaborator], card_dossier: dossier }} />;
  }

  return (
    <>
      {roles.map((role: Record<string, any>) => {
        const roleKey = String(role.role_key ?? "");
        const roleLabel = role.role_label ?? metricLabel(roleKey);
        const cards = cardsForCollaboratorRole(collaborator, roleKey).map((card) =>
          mergeCardWithDossier(card, dossier),
        );
        return (
          <section className="role-subsection" key={`${collaborator.name}-${roleKey}`}>
            <h4>{roleLabel}</h4>
            {ROLE_DESCRIPTIONS[roleKey] ? <p className="table-description">{ROLE_DESCRIPTIONS[roleKey]}</p> : null}
            <ObjectPanel title="Metricas do papel" value={role} />
            {Array.isArray(role.process_times) && role.process_times.length > 0 ? (
              <MetricTable title="Tempo por etapa" rows={role.process_times} />
            ) : null}
            <CardDossier title={`Cards como ${roleLabel}`} metrics={{ card_dossier: dossier }} cards={cards} />
          </section>
        );
      })}
    </>
  );
}

function MetricCalculationGuide(_props: { report: GeneratedReport }) {
  const intro = sectionGuide("management_intro");
  const sections = MANAGEMENT_GUIDE_SECTIONS.filter((id) => id !== "management_intro");

  return (
    <section className="management-guide">
      <h3>{intro.title || "Memoria de calculo das metricas"}</h3>
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
                  <p>{item.formula || metricFormula(item.key) || metricDescription(item.key)}</p>
                  {(item.example || metricExample(item.key)) ? (
                    <p className="guide-example">Exemplo: {item.example || metricExample(item.key)}</p>
                  ) : null}
                </li>
              ))}
            </ol>
          </details>
        );
      })}
    </section>
  );
}

function MetricTable({
  title,
  rows,
  hiddenColumns = [],
}: {
  title: string;
  rows: Array<Record<string, any>>;
  hiddenColumns?: string[];
}) {
  const tableId = SECTION_TABLE_IDS[title];
  const description = tableId ? tableDescription(tableId) : "";
  const columns = Object.keys(rows[0] ?? {})
    .filter((key) => isSimple(rows[0][key]) || key === "top_bottleneck")
    .filter((key) => !["id", "card_id", "scope", "sent_back", "avg_review_hours", "peer_review_returns", ...hiddenColumns].includes(key))
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
          .filter(([key, item]) => isSimple(item) && !["id", "card_id", "scope"].includes(key))
          .slice(0, 16)
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

type AntifraudAlert = {
  score?: string;
  card_id?: string;
  card_name?: string;
  source_card_id?: string;
  source_card_name?: string;
  dest_list?: string;
  dest_group?: string;
  actor_name?: string;
  reason?: string;
  flags?: string[];
  copied_at?: string;
  source_lineage?: {
    status?: string;
    passed_terminal?: boolean;
    groups_visited?: string[];
    deleted_at?: string;
    archived_at?: string;
    disposal?: string;
    last_list_at_copy?: string;
    last_group_at_copy?: string;
    last_list_at_delete?: string;
    last_list_at_dispose?: string;
    last_group_at_delete?: string;
    last_group_at_dispose?: string;
    seconds_copy_to_delete?: number | null;
    seconds_copy_to_dispose?: number | null;
    rapid_copy_delete?: boolean;
    rapid_copy_dispose?: boolean;
    disposed_at?: string;
    recovery_note?: string;
    visits?: Array<{
      at?: string;
      event_type?: string;
      list_name?: string;
      group?: string | null;
      actor_name?: string;
      after_copy?: boolean;
    }>;
    visits_count?: number;
  };
};

function AntifraudPanel({ antifraud }: { antifraud: Record<string, any> }) {
  const summary = antifraud.summary ?? antifraud;
  const alerts: AntifraudAlert[] = Array.isArray(antifraud.alerts)
    ? antifraud.alerts.filter(
        (item: AntifraudAlert) => item.score === "high" || item.score === "medium",
      )
    : [];

  return (
    <section className="antifraud-panel">
      <ObjectPanel title="Antifraude" value={summary} />
      {alerts.length === 0 ? (
        <p className="table-description">Nenhum alerta high/medium no periodo.</p>
      ) : (
        <div className="antifraud-alerts">
          <h3>Alertas e movimentacoes da fonte</h3>
          {alerts.map((alert, index) => {
            const lineage = alert.source_lineage || {};
            const visits = Array.isArray(lineage.visits) ? lineage.visits : [];
            return (
              <details
                key={`${alert.card_id || "alert"}-${index}`}
                className={`antifraud-alert score-${alert.score || "low"}`}
                open={alert.score === "high"}
              >
                <summary>
                  <span className={`antifraud-score score-${alert.score || "low"}`}>
                    {(alert.score || "low").toUpperCase()}
                  </span>
                  <span className="antifraud-summary-text">
                    {alert.card_name || "Card sem nome"}
                    {alert.dest_list ? ` → ${alert.dest_list}` : ""}
                  </span>
                </summary>
                <div className="antifraud-alert-body">
                  <p>{alert.reason || "Sem motivo detalhado."}</p>
                  {lineage.recovery_note ? (
                    <p className="table-description">{lineage.recovery_note}</p>
                  ) : null}
                  <div className="antifraud-meta">
                    <span>
                      <strong>Card novo:</strong> {alert.card_name || "-"}{" "}
                      <code>{alert.card_id || "-"}</code>
                    </span>
                    <span>
                      <strong>Fonte:</strong> {alert.source_card_name || "-"}{" "}
                      <code>{alert.source_card_id || "-"}</code>
                    </span>
                    <span>
                      <strong>Status fonte:</strong> {lineage.status || "-"}
                    </span>
                    <span>
                      <strong>Ultima coluna na copia:</strong>{" "}
                      {lineage.last_list_at_copy || lineage.last_list_at_delete || "-"}
                      {lineage.last_group_at_copy || lineage.last_group_at_delete
                        ? ` (${lineage.last_group_at_copy || lineage.last_group_at_delete})`
                        : ""}
                    </span>
                    <span>
                      <strong>Coluna na exclusao/arquivamento:</strong>{" "}
                      {lineage.last_list_at_dispose || lineage.last_list_at_delete || "-"}
                    </span>
                    <span>
                      <strong>Passou terminal:</strong> {lineage.passed_terminal ? "Sim" : "Nao"}
                    </span>
                    <span>
                      <strong>Copia → exclusao/arquivamento:</strong>{" "}
                      {(lineage.seconds_copy_to_dispose ?? lineage.seconds_copy_to_delete) != null
                        ? `${lineage.seconds_copy_to_dispose ?? lineage.seconds_copy_to_delete}s${
                            lineage.rapid_copy_dispose || lineage.rapid_copy_delete ? " (rapido)" : ""
                          }`
                        : "-"}
                    </span>
                    <span>
                      <strong>Autor da copia:</strong> {alert.actor_name || "-"}
                    </span>
                    <span>
                      <strong>Copiado em:</strong> {alert.copied_at || "-"}
                    </span>
                    {(lineage.groups_visited || []).length > 0 ? (
                      <span>
                        <strong>Grupos conhecidos:</strong> {(lineage.groups_visited || []).join(", ")}
                      </span>
                    ) : null}
                    {lineage.disposed_at || lineage.deleted_at || lineage.archived_at ? (
                      <span>
                        <strong>
                          Fonte {lineage.disposal === "archived" ? "arquivada" : "excluida"} em:
                        </strong>{" "}
                        {lineage.disposed_at || lineage.archived_at || lineage.deleted_at}
                      </span>
                    ) : null}
                  </div>
                  {visits.length > 0 ? (
                    <div className="table-scroll">
                      <table>
                        <thead>
                          <tr>
                            <th>Quando</th>
                            <th>Evento</th>
                            <th>Lista</th>
                            <th>Grupo</th>
                            <th>Quem</th>
                            <th>Apos copia?</th>
                          </tr>
                        </thead>
                        <tbody>
                          {visits.map((visit, visitIndex) => (
                            <tr key={`${alert.card_id}-visit-${visitIndex}`}>
                              <td>{visit.at || "-"}</td>
                              <td>{visit.event_type || "-"}</td>
                              <td>{visit.list_name || "-"}</td>
                              <td>{visit.group || "-"}</td>
                              <td>{visit.actor_name || "-"}</td>
                              <td>{visit.after_copy ? "Sim" : "Nao"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className="table-description">
                      Sem movimentacoes recuperaveis da fonte no historico do board.
                    </p>
                  )}
                </div>
              </details>
            );
          })}
        </div>
      )}
    </section>
  );
}

function CardDossier({
  title,
  metrics,
  cards: explicitCards,
}: {
  title: string;
  metrics: Record<string, any>;
  cards?: Array<Record<string, any>>;
}) {
  const cards = (explicitCards ?? collectCards(metrics)).slice(0, 40);
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
  const undueSolutions = Array.isArray(card.undue_return_solutions)
    ? card.undue_return_solutions
    : [];
  const involvements = Array.isArray(card.collaborator_involvements) ? card.collaborator_involvements : [];
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

      {involvements.length ? (
        <div className="mini-table-scroll">
          {involvements.map((involvement: Record<string, any>, involvementIndex: number) => (
            <div key={`${involvement.role_key ?? involvementIndex}`}>
              <strong>{`Movimentacao (${involvement.role_label ?? involvement.role_key ?? "papel"})`}</strong>
              {Array.isArray(involvement.stages) && involvement.stages.length ? (
                <table className="mini-table">
                  <thead>
                    <tr>
                      <th>Etapa</th>
                      <th>Lista</th>
                      <th>Tempo</th>
                    </tr>
                  </thead>
                  <tbody>
                    {involvement.stages.slice(0, 12).map((stage: Record<string, any>, index: number) => (
                      <tr key={`${stage.group ?? stage.title}-${index}`}>
                        <td>{formatCell(stage.title ?? stage.group)}</td>
                        <td>{formatCell(stage.list_name)}</td>
                        <td>{formatCell(stage.hours_human ?? stage.hours)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : null}
            </div>
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

      {undueSolutions.length ? (
        <div className="return-list">
          <strong>Soluções de retorno indevido</strong>
          {undueSolutions.map((item: Record<string, any>, index: number) => (
            <div key={`undue-${item.numero ?? index}-${item.at ?? ""}`}>
              <strong>{`Solução de retorno indevido${item.numero != null ? ` #${item.numero}` : ""}`}</strong>
              <p>{formatCell(item.motivo)}</p>
              <p>{formatCell(item.solucao)}</p>
            </div>
          ))}
        </div>
      ) : null}

      {retornos.length ? (
        <div className="return-list">
          {retornos.map((item: Record<string, any>, index: number) => (
            <div key={`${item.numero ?? index}-${item.at ?? ""}`}>
              <strong>
                {item.is_undue_test_return || item.kind === "undue"
                  ? `Retorno indevido ${formatCell(item.numero ?? index + 1)}`
                  : `Retorno ${formatCell(item.numero ?? index + 1)}`}
              </strong>
              <span>{[item.tipo, item.subtipo, item.atribuido_a].filter(Boolean).join(" / ")}</span>
              <p>{formatCell(item.motivo || item.solucao)}</p>
              {item.is_undue_test_return || item.kind === "undue" ? (
                <p>
                  <strong>Solução de retorno indevido:</strong> {formatCell(item.solucao)}
                </p>
              ) : null}
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

function cardsForCollaboratorRole(collaborator: Record<string, any>, roleKey: string): Array<Record<string, any>> {
  const cards: Array<Record<string, any>> = [];
  for (const card of collaborator.cards ?? []) {
    if (!isRecord(card)) continue;
    const involvements = Array.isArray(card.collaborator_involvements) ? card.collaborator_involvements : [];
    if (involvements.some((item) => isRecord(item) && item.role_key === roleKey)) {
      cards.push(card);
    }
  }
  return cards;
}

function dossierCardsForPerson(
  dossier: unknown,
  bucketName: "by_developer" | "by_solicitante" | "by_tester",
  personName: string,
  aliases?: string[],
): Array<Record<string, any>> {
  if (!isRecord(dossier) || !isRecord(dossier[bucketName])) return [];
  const bucket = dossier[bucketName] as Record<string, unknown>;
  const key = matchDossierBucketKey(bucket, personName, aliases);
  if (!key) return [];
  const entry = bucket[key];
  if (bucketName === "by_developer" && isRecord(entry)) {
    return [...(Array.isArray(entry.tarefas_normais) ? entry.tarefas_normais : []), ...(Array.isArray(entry.cards_analise) ? entry.cards_analise : [])].filter(isRecord);
  }
  return Array.isArray(entry) ? entry.filter(isRecord) : [];
}

function mergeCardWithDossier(card: Record<string, any>, dossier: unknown): Record<string, any> {
  const indexed = indexDossierCards(dossier);
  const cardId = String(card.card_id ?? "");
  const full = cardId ? indexed[cardId] : undefined;
  return full ? { ...full, ...card } : card;
}

function indexDossierCards(dossier: unknown): Record<string, Record<string, any>> {
  const indexed: Record<string, Record<string, any>> = {};
  if (!isRecord(dossier)) return indexed;
  const push = (value: unknown) => {
    if (!isRecord(value)) return;
    const cardId = String(value.card_id ?? "");
    if (cardId) indexed[cardId] = value;
  };
  collectDeveloperCards(dossier.by_developer, push);
  collectNamedCardBucket(dossier.by_solicitante, push);
  collectNamedCardBucket(dossier.by_tester, push);
  if (Array.isArray(dossier.cards)) dossier.cards.forEach(push);
  return indexed;
}

function matchDossierBucketKey(
  bucket: Record<string, unknown>,
  personName: string,
  aliases: string[] = [],
): string | null {
  const candidates = [personName, ...aliases];
  for (const bucketKey of Object.keys(bucket)) {
    if (candidates.some((candidate) => namesMatch(candidate, bucketKey))) {
      return bucketKey;
    }
  }
  return null;
}

function namesMatch(left: string, right: string): boolean {
  return normalizePersonKey(left) === normalizePersonKey(right);
}

function normalizePersonKey(value: string): string {
  return value
    .replace(/^\s*(?:REVISOR\s+EM\s+PAR|REVISOR\/PAR|DESENVOLVEDOR|SOLICITANTE|TESTER|REV|DEV|RP|R|D|T|S)\s*[-:/]\s*/i, "")
    .trim()
    .toLowerCase();
}

function cardIndex(card: Record<string, any>, index: number): string {
  const idShort = card.id_short ?? card.idShort;
  return idShort ? `#${idShort}` : `#${index + 1}`;
}

function cardMeta(card: Record<string, any>): string {
  return [
    card.current_list,
    card.sistema,
    formatCell(card.kind, "kind"),
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
    "gpt-4o-mini"
  );
}

function modelsForProvider(provider: AIProvider, options: ReportOptions) {
  return (
    options.ai_providers.find((item) => item.value === provider)?.models ??
    fallbackOptions.ai_providers.find((item) => item.value === provider)?.models ??
    []
  );
}

function ensureValidModel(provider: AIProvider, model: string, options: ReportOptions): string {
  const models = modelsForProvider(provider, options);
  if (models.some((item) => item.value === model)) {
    return model;
  }
  return defaultModelFor(provider, options);
}

function currentMonth(): string {
  return new Date().toISOString().slice(0, 7);
}

const REPORT_TYPE_SLUGS: Record<string, string> = {
  general: "geral",
  individual: "individual",
  developers: "desenvolvedores",
  requesters: "solicitantes",
  testers: "testers",
  management: "gestao",
  specific_metrics: "metricas",
};

function slugify(value: string): string {
  return value
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^A-Za-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .toLowerCase();
}

function reportFileBaseName(report: GeneratedReport): string {
  const tipo = REPORT_TYPE_SLUGS[report.report_type] ?? report.report_type;
  const parts = ["intgest", tipo];
  if (report.collaborator_name) {
    const colaborador = slugify(report.collaborator_name);
    if (colaborador) parts.push(colaborador);
  }
  if (report.month) parts.push(report.month.replace(/\//g, "-"));
  return parts.join("_");
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
  if (isRecord(value)) return false;
  return value == null || ["string", "number", "boolean"].includes(typeof value);
}

function formatCell(value: unknown, key?: string): string {
  if (value == null || value === "") return "-";
  if (typeof value === "number") {
    if (key?.endsWith("_pct")) return `${value}%`;
    return Number.isInteger(value) ? `${value}` : value.toFixed(1);
  }
  if (typeof value === "boolean") return value ? "Sim" : "Nao";
  if (key === "top_bottleneck" && isRecord(value)) {
    const title = String(value.title ?? value.group ?? "-");
    const hours = value.avg_human ?? value.avg_hours;
    return hours != null && hours !== "" ? `${title} (${hours})` : title;
  }
  if (key === "kind" && typeof value === "string") {
    return ({ problem: "Problema", analysis: "Analise", unknown: "Nao classificado" } as Record<string, string>)[value] ?? value;
  }
  if (key === "group" && typeof value === "string") {
    return metricLabel(value);
  }
  if (key === "status" && typeof value === "string") {
    return ({ ok: "Dentro do prazo", em_risco: "Alerta de SLA", estourado: "Fora do prazo" } as Record<string, string>)[value] ?? value;
  }
  if (key === "sla_basis" && typeof value === "string") {
    return (
      {
        stage_hours: "Etapa (horas corridas)",
        stage_calendar_hours: "Etapa (horas uteis)",
        analysis_level: "Nivel de analise",
        development_level: "Nivel de desenvolvimento",
        return_priority: "Prioridade do retorno",
        excluded: "Sem SLA",
        wip_only: "Somente WIP",
      } as Record<string, string>
    )[value] ?? metricLabel(value);
  }
  if (key === "scope" && typeof value === "string") {
    return ({
      developers: "Desenvolvedores",
      testers: "Testers",
      requesters: "Solicitantes",
      reviewers: "Revisao em par",
      formal_reviewers: "Revisores",
    } as Record<string, string>)[value] ?? metricLabel(value);
  }
  if (isRecord(value)) {
    const title = value.title ?? value.name ?? value.card_name;
    if (title) return String(title);
  }
  return String(value);
}

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : "Erro inesperado.";
}

export default App;
