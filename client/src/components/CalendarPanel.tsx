import { useEffect, useMemo, useState, type FormEvent } from "react";
import {
  Ban,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Plus,
  SunMedium,
  Trash2,
  X,
} from "lucide-react";

import {
  createCalendarException,
  createOvertimeEntry,
  deleteCalendarException,
  deleteOvertimeEntry,
  listCalendarExceptions,
  listOvertimeEntries,
} from "../api/client";
import type {
  CalendarExceptionKind,
  OvertimeEntry,
  WorkCalendarException,
} from "../types/calendar";
import type { Collaborator } from "../types/report";

const WEEKDAYS = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"];

const KIND_META: Record<
  CalendarExceptionKind,
  { label: string; Icon: typeof SunMedium; className: string }
> = {
  holiday: { label: "Feriado", Icon: SunMedium, className: "kind-holiday" },
  schedule_override: { label: "Meio período", Icon: Clock3, className: "kind-schedule_override" },
  exclude_window: { label: "Excluir janela", Icon: Ban, className: "kind-exclude_window" },
};

interface CalendarPanelProps {
  token: string;
  collaborators: Collaborator[];
  month: string;
  onMonthChange: (month: string) => void;
  onError: (message: string) => void;
}

function toggleId(list: number[], id: number): number[] {
  return list.includes(id) ? list.filter((item) => item !== id) : [...list, id];
}

function parseMonth(month: string): { year: number; monthIndex: number } {
  const [year, mon] = month.split("-").map(Number);
  return { year: year || new Date().getFullYear(), monthIndex: (mon || 1) - 1 };
}

function toIsoDate(year: number, monthIndex: number, day: number): string {
  return `${year}-${String(monthIndex + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

function shiftMonth(month: string, delta: number): string {
  const { year, monthIndex } = parseMonth(month);
  const date = new Date(year, monthIndex + delta, 1);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

function formatMonthLabel(month: string): string {
  const { year, monthIndex } = parseMonth(month);
  return new Date(year, monthIndex, 1).toLocaleDateString("pt-BR", {
    month: "long",
    year: "numeric",
  });
}

function formatDayTitle(isoDate: string): string {
  const [year, month, day] = isoDate.split("-").map(Number);
  if (!year || !month || !day) return isoDate;
  return new Date(year, month - 1, day).toLocaleDateString("pt-BR", {
    weekday: "long",
    day: "2-digit",
    month: "long",
  });
}

function timeRange(start?: string | null, end?: string | null): string {
  if (start && end) return `${start.slice(0, 5)} – ${end.slice(0, 5)}`;
  return "Dia inteiro";
}

export function CalendarPanel({
  token,
  collaborators,
  month,
  onMonthChange,
  onError,
}: CalendarPanelProps) {
  const [exceptions, setExceptions] = useState<WorkCalendarException[]>([]);
  const [overtime, setOvertime] = useState<OvertimeEntry[]>([]);
  const [busy, setBusy] = useState(false);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);

  const [exKind, setExKind] = useState<CalendarExceptionKind>("holiday");
  const [exStart, setExStart] = useState("08:00");
  const [exEnd, setExEnd] = useState("12:00");
  const [exScope, setExScope] = useState<"all" | "collaborators">("all");
  const [exPeople, setExPeople] = useState<number[]>([]);
  const [exNote, setExNote] = useState("");

  const [otCollaborator, setOtCollaborator] = useState<number | "">("");
  const [otStart, setOtStart] = useState("08:00");
  const [otEnd, setOtEnd] = useState("12:00");
  const [otNote, setOtNote] = useState("");

  const activeCollaborators = useMemo(
    () => collaborators.filter((item) => item.active),
    [collaborators],
  );

  const { year, monthIndex } = parseMonth(month);
  const daysInMonth = new Date(year, monthIndex + 1, 0).getDate();
  const startWeekday = new Date(year, monthIndex, 1).getDay();
  const todayIso = useMemo(() => {
    const now = new Date();
    return toIsoDate(now.getFullYear(), now.getMonth(), now.getDate());
  }, []);

  const byDate = useMemo(() => {
    const map = new Map<string, { exceptions: WorkCalendarException[]; overtime: OvertimeEntry[] }>();
    for (const item of exceptions) {
      const bucket = map.get(item.date) ?? { exceptions: [], overtime: [] };
      bucket.exceptions.push(item);
      map.set(item.date, bucket);
    }
    for (const item of overtime) {
      const bucket = map.get(item.date) ?? { exceptions: [], overtime: [] };
      bucket.overtime.push(item);
      map.set(item.date, bucket);
    }
    return map;
  }, [exceptions, overtime]);

  const dayExceptions = selectedDate ? byDate.get(selectedDate)?.exceptions ?? [] : [];
  const dayOvertime = selectedDate ? byDate.get(selectedDate)?.overtime ?? [] : [];

  async function reload() {
    const [ex, ot] = await Promise.all([
      listCalendarExceptions(token, month),
      listOvertimeEntries(token, month),
    ]);
    setExceptions(ex);
    setOvertime(ot);
  }

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [ex, ot] = await Promise.all([
          listCalendarExceptions(token, month),
          listOvertimeEntries(token, month),
        ]);
        if (!cancelled) {
          setExceptions(ex);
          setOvertime(ot);
        }
      } catch (error) {
        if (!cancelled) {
          onError(error instanceof Error ? error.message : "Falha ao carregar calendário.");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token, month, onError]);

  function resetDayForms() {
    setExKind("holiday");
    setExStart("08:00");
    setExEnd("12:00");
    setExScope("all");
    setExPeople([]);
    setExNote("");
    setOtCollaborator("");
    setOtStart("08:00");
    setOtEnd("12:00");
    setOtNote("");
  }

  function openDay(isoDate: string) {
    setSelectedDate(isoDate);
    resetDayForms();
  }

  function closeDay() {
    setSelectedDate(null);
    resetDayForms();
  }

  async function handleCreateException(event: FormEvent) {
    event.preventDefault();
    if (!selectedDate) return;
    if (exKind !== "holiday" && (!exStart || !exEnd)) {
      onError("Informe início e fim para meio período ou exclusão de janela.");
      return;
    }
    if (exScope === "collaborators" && exPeople.length === 0) {
      onError("Selecione ao menos um colaborador.");
      return;
    }
    setBusy(true);
    try {
      await createCalendarException(token, {
        date: selectedDate,
        kind: exKind,
        start_time: exKind === "holiday" ? null : exStart,
        end_time: exKind === "holiday" ? null : exEnd,
        scope: exScope,
        collaborator_ids: exScope === "collaborators" ? exPeople : [],
        note: exNote,
        active: true,
      });
      resetDayForms();
      await reload();
    } catch (error) {
      onError(error instanceof Error ? error.message : "Falha ao criar exceção.");
    } finally {
      setBusy(false);
    }
  }

  async function handleCreateOvertime(event: FormEvent) {
    event.preventDefault();
    if (!selectedDate) return;
    if (!otCollaborator) {
      onError("Selecione o colaborador da hora extra.");
      return;
    }
    setBusy(true);
    try {
      await createOvertimeEntry(token, {
        collaborator: Number(otCollaborator),
        date: selectedDate,
        start_time: otStart,
        end_time: otEnd,
        note: otNote,
        active: true,
      });
      resetDayForms();
      await reload();
    } catch (error) {
      onError(error instanceof Error ? error.message : "Falha ao criar hora extra.");
    } finally {
      setBusy(false);
    }
  }

  async function handleDeleteException(id: number) {
    setBusy(true);
    try {
      await deleteCalendarException(token, id);
      await reload();
    } catch (error) {
      onError(error instanceof Error ? error.message : "Falha ao remover exceção.");
    } finally {
      setBusy(false);
    }
  }

  async function handleDeleteOvertime(id: number) {
    setBusy(true);
    try {
      await deleteOvertimeEntry(token, id);
      await reload();
    } catch (error) {
      onError(error instanceof Error ? error.message : "Falha ao remover hora extra.");
    } finally {
      setBusy(false);
    }
  }

  const cells: Array<{ iso: string; day: number } | null> = [];
  for (let i = 0; i < startWeekday; i += 1) cells.push(null);
  for (let day = 1; day <= daysInMonth; day += 1) {
    cells.push({ iso: toIsoDate(year, monthIndex, day), day });
  }

  return (
    <>
      <aside className="report-form calendar-sidebar">
        <div className="panel-title compact">
          <CalendarDays size={20} />
          <div>
            <h2>Calendário</h2>
            <p className="tab-description">Clique em um dia para configurar exceções e hora extra.</p>
          </div>
        </div>

        <div className="calendar-side-block">
          <span className="calendar-side-label">Mês</span>
          <div className="calendar-month-nav">
            <button
              type="button"
              className="icon-button"
              onClick={() => onMonthChange(shiftMonth(month, -1))}
              aria-label="Mês anterior"
            >
              <ChevronLeft size={16} />
            </button>
            <strong>{formatMonthLabel(month)}</strong>
            <button
              type="button"
              className="icon-button"
              onClick={() => onMonthChange(shiftMonth(month, 1))}
              aria-label="Próximo mês"
            >
              <ChevronRight size={16} />
            </button>
          </div>
        </div>

        <div className="calendar-side-block">
          <span className="calendar-side-label">Resumo do mês</span>
          <div className="calendar-side-stats">
            <div>
              <strong>{exceptions.length}</strong>
              <span>Exceções</span>
            </div>
            <div>
              <strong>{overtime.length}</strong>
              <span>Horas extras</span>
            </div>
            <div>
              <strong>{byDate.size}</strong>
              <span>Dias afetados</span>
            </div>
          </div>
        </div>

        <div className="calendar-side-block">
          <span className="calendar-side-label">Legenda</span>
          <ul className="calendar-legend">
            <li><span className="calendar-dot kind-holiday" /> Feriado</li>
            <li><span className="calendar-dot kind-schedule_override" /> Meio período</li>
            <li><span className="calendar-dot kind-exclude_window" /> Excluir janela</li>
            <li><span className="calendar-dot overtime" /> Hora extra</li>
          </ul>
        </div>

        <p className="calendar-side-hint">
          As configurações feitas no popup do dia aparecem imediatamente no calendário.
        </p>
      </aside>

      <section className="report-preview calendar-main">
        <div className="calendar-main-head">
          <div>
            <p className="calendar-kicker">Visão mensal</p>
            <h1>{formatMonthLabel(month)}</h1>
          </div>
          <div className="calendar-month-nav calendar-month-nav-lg">
            <button type="button" className="calendar-nav-btn" onClick={() => onMonthChange(shiftMonth(month, -1))}>
              <ChevronLeft size={16} /> Anterior
            </button>
            <button type="button" className="calendar-nav-btn" onClick={() => onMonthChange(shiftMonth(month, 1))}>
              Próximo <ChevronRight size={16} />
            </button>
          </div>
        </div>

        <div className="month-calendar">
          <div className="month-calendar-weekdays">
            {WEEKDAYS.map((label) => (
              <div key={label}>{label}</div>
            ))}
          </div>
          <div className="month-calendar-grid">
            {cells.map((cell, index) => {
              if (!cell) {
                return <div key={`empty-${index}`} className="month-day empty" />;
              }
              const bucket = byDate.get(cell.iso);
              const exCount = bucket?.exceptions.length ?? 0;
              const otCount = bucket?.overtime.length ?? 0;
              const hasItems = exCount + otCount > 0;
              const isToday = cell.iso === todayIso;
              return (
                <button
                  key={cell.iso}
                  type="button"
                  className={`month-day${hasItems ? " has-items" : ""}${isToday ? " today" : ""}`}
                  onClick={() => openDay(cell.iso)}
                >
                  <span className="month-day-number">{cell.day}</span>
                  <div className="month-day-marks">
                    {(bucket?.exceptions ?? []).slice(0, 3).map((item) => (
                      <span
                        key={`ex-${item.id}`}
                        className={`calendar-dot ${KIND_META[item.kind].className}`}
                        title={KIND_META[item.kind].label}
                      />
                    ))}
                    {(bucket?.overtime ?? []).slice(0, 2).map((item) => (
                      <span
                        key={`ot-${item.id}`}
                        className="calendar-dot overtime"
                        title={`HE · ${item.collaborator_name}`}
                      />
                    ))}
                  </div>
                  {hasItems ? (
                    <span className="month-day-count">
                      {exCount > 0 ? <em>{exCount} ex.</em> : null}
                      {otCount > 0 ? <em className="he">{otCount} HE</em> : null}
                    </span>
                  ) : null}
                </button>
              );
            })}
          </div>
        </div>
      </section>

      {selectedDate ? (
        <div className="calendar-modal-overlay" onClick={closeDay} role="presentation">
          <div
            className="calendar-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="calendar-day-title"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="calendar-modal-head">
              <div>
                <p className="calendar-kicker">Dia selecionado</p>
                <h2 id="calendar-day-title">{formatDayTitle(selectedDate)}</h2>
              </div>
              <button type="button" className="icon-button" onClick={closeDay} aria-label="Fechar">
                <X size={18} />
              </button>
            </div>

            <div className="calendar-modal-body">
              <div className="calendar-modal-col">
                <div className="calendar-modal-section-head">
                  <h3>Exceções do dia</h3>
                  <span>{dayExceptions.length}</span>
                </div>
                <ul className="calendar-day-list">
                  {dayExceptions.length === 0 ? (
                    <li className="calendar-day-empty">Nenhuma exceção neste dia.</li>
                  ) : (
                    dayExceptions.map((item) => {
                      const meta = KIND_META[item.kind];
                      return (
                        <li key={item.id}>
                          <div>
                            <div className="calendar-item-top">
                              <strong>{meta.label}</strong>
                              <span className={`calendar-badge ${meta.className}`}>{timeRange(item.start_time, item.end_time)}</span>
                            </div>
                            <span>
                              {item.scope === "all"
                                ? "Toda a equipe"
                                : item.collaborator_names.join(", ") || "Colaboradores"}
                              {item.note ? ` · ${item.note}` : ""}
                            </span>
                          </div>
                          <button
                            type="button"
                            className="icon-button danger"
                            disabled={busy}
                            onClick={() => void handleDeleteException(item.id)}
                            aria-label="Remover exceção"
                          >
                            <Trash2 size={16} />
                          </button>
                        </li>
                      );
                    })
                  )}
                </ul>

                <form className="calendar-day-form" onSubmit={(event) => void handleCreateException(event)}>
                  <div className="calendar-kind-grid compact">
                    {(Object.keys(KIND_META) as CalendarExceptionKind[]).map((kind) => {
                      const meta = KIND_META[kind];
                      const Icon = meta.Icon;
                      return (
                        <button
                          key={kind}
                          type="button"
                          className={`calendar-kind-card${exKind === kind ? " active" : ""}`}
                          onClick={() => setExKind(kind)}
                        >
                          <Icon size={16} />
                          <strong>{meta.label}</strong>
                        </button>
                      );
                    })}
                  </div>
                  {exKind !== "holiday" ? (
                    <div className="calendar-form-row">
                      <label>
                        Início
                        <input type="time" value={exStart} onChange={(e) => setExStart(e.target.value)} required />
                      </label>
                      <label>
                        Fim
                        <input type="time" value={exEnd} onChange={(e) => setExEnd(e.target.value)} required />
                      </label>
                    </div>
                  ) : null}
                  <div className="calendar-form-row">
                    <label>
                      Escopo
                      <select
                        value={exScope}
                        onChange={(e) => setExScope(e.target.value as "all" | "collaborators")}
                      >
                        <option value="all">Toda a equipe</option>
                        <option value="collaborators">Colaboradores</option>
                      </select>
                    </label>
                    <label className="calendar-form-grow">
                      Nota
                      <input
                        type="text"
                        value={exNote}
                        onChange={(e) => setExNote(e.target.value)}
                        placeholder="Opcional"
                      />
                    </label>
                  </div>
                  {exScope === "collaborators" ? (
                    <div className="calendar-people-grid">
                      {activeCollaborators.map((person) => (
                        <button
                          key={person.id}
                          type="button"
                          className={`calendar-person${exPeople.includes(person.id) ? " active" : ""}`}
                          onClick={() => setExPeople((prev) => toggleId(prev, person.id))}
                        >
                          {person.name}
                        </button>
                      ))}
                    </div>
                  ) : null}
                  <button type="submit" className="primary-button" disabled={busy}>
                    <Plus size={16} /> Adicionar exceção
                  </button>
                </form>
              </div>

              <div className="calendar-modal-col">
                <div className="calendar-modal-section-head">
                  <h3>Hora extra do dia</h3>
                  <span>{dayOvertime.length}</span>
                </div>
                <ul className="calendar-day-list">
                  {dayOvertime.length === 0 ? (
                    <li className="calendar-day-empty">Nenhuma hora extra neste dia.</li>
                  ) : (
                    dayOvertime.map((item) => (
                      <li key={item.id}>
                        <div>
                          <div className="calendar-item-top">
                            <strong>{item.collaborator_name}</strong>
                            <span className="calendar-badge overtime">{timeRange(item.start_time, item.end_time)}</span>
                          </div>
                          <span>{item.note || "Sem nota"}</span>
                        </div>
                        <button
                          type="button"
                          className="icon-button danger"
                          disabled={busy}
                          onClick={() => void handleDeleteOvertime(item.id)}
                          aria-label="Remover hora extra"
                        >
                          <Trash2 size={16} />
                        </button>
                      </li>
                    ))
                  )}
                </ul>

                <form className="calendar-day-form" onSubmit={(event) => void handleCreateOvertime(event)}>
                  <div className="calendar-form-row">
                    <label className="calendar-form-grow">
                      Colaborador
                      <select
                        value={otCollaborator}
                        onChange={(e) => setOtCollaborator(e.target.value ? Number(e.target.value) : "")}
                        required
                      >
                        <option value="">Selecione</option>
                        {activeCollaborators.map((person) => (
                          <option key={person.id} value={person.id}>
                            {person.name}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                  <div className="calendar-form-row">
                    <label>
                      Início
                      <input type="time" value={otStart} onChange={(e) => setOtStart(e.target.value)} required />
                    </label>
                    <label>
                      Fim
                      <input type="time" value={otEnd} onChange={(e) => setOtEnd(e.target.value)} required />
                    </label>
                  </div>
                  <label>
                    Nota
                    <input
                      type="text"
                      value={otNote}
                      onChange={(e) => setOtNote(e.target.value)}
                      placeholder="Opcional"
                    />
                  </label>
                  <button type="submit" className="primary-button" disabled={busy}>
                    <Plus size={16} /> Adicionar hora extra
                  </button>
                </form>
              </div>
            </div>

            <div className="calendar-modal-foot">
              <CalendarDays size={16} />
              <span>Tudo que você configurar aqui aparece no calendário grande.</span>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
