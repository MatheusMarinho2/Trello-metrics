import { useEffect, useMemo, useState } from "react";
import { CalendarDays, Clock3, Trash2 } from "lucide-react";

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

const KIND_LABELS: Record<CalendarExceptionKind, string> = {
  holiday: "Feriado / dia inteiro",
  schedule_override: "Meio período",
  exclude_window: "Excluir janela",
};

interface CalendarPanelProps {
  token: string;
  collaborators: Collaborator[];
  month: string;
  onError: (message: string) => void;
}

function toggleId(list: number[], id: number): number[] {
  return list.includes(id) ? list.filter((item) => item !== id) : [...list, id];
}

export function CalendarPanel({ token, collaborators, month, onError }: CalendarPanelProps) {
  const [exceptions, setExceptions] = useState<WorkCalendarException[]>([]);
  const [overtime, setOvertime] = useState<OvertimeEntry[]>([]);
  const [busy, setBusy] = useState(false);

  const [exDate, setExDate] = useState(`${month}-01`);
  const [exKind, setExKind] = useState<CalendarExceptionKind>("holiday");
  const [exStart, setExStart] = useState("08:00");
  const [exEnd, setExEnd] = useState("12:00");
  const [exScope, setExScope] = useState<"all" | "collaborators">("all");
  const [exPeople, setExPeople] = useState<number[]>([]);
  const [exNote, setExNote] = useState("");

  const [otDate, setOtDate] = useState(`${month}-01`);
  const [otCollaborator, setOtCollaborator] = useState<number | "">("");
  const [otStart, setOtStart] = useState("08:00");
  const [otEnd, setOtEnd] = useState("12:00");
  const [otNote, setOtNote] = useState("");

  const activeCollaborators = useMemo(
    () => collaborators.filter((item) => item.active),
    [collaborators],
  );

  useEffect(() => {
    setExDate(`${month}-01`);
    setOtDate(`${month}-01`);
  }, [month]);

  async function reload() {
    const [ex, ot] = await Promise.all([
      listCalendarExceptions(token, month),
      listOvertimeEntries(token, month),
    ]);
    setExceptions(ex);
    setOvertime(ot);
  }

  useEffect(() => {
    void reload().catch((err) => onError(err instanceof Error ? err.message : String(err)));
  }, [token, month]);

  async function handleCreateException(event: React.FormEvent) {
    event.preventDefault();
    if (exScope === "collaborators" && exPeople.length === 0) {
      onError("Selecione ao menos um colaborador.");
      return;
    }
    setBusy(true);
    try {
      await createCalendarException(token, {
        date: exDate,
        kind: exKind,
        start_time: exKind === "holiday" ? null : exStart,
        end_time: exKind === "holiday" ? null : exEnd,
        scope: exScope,
        collaborator_ids: exScope === "collaborators" ? exPeople : [],
        note: exNote,
        active: true,
      });
      setExNote("");
      setExPeople([]);
      await reload();
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleCreateOvertime(event: React.FormEvent) {
    event.preventDefault();
    if (!otCollaborator) {
      onError("Selecione o colaborador da hora extra.");
      return;
    }
    setBusy(true);
    try {
      await createOvertimeEntry(token, {
        collaborator: otCollaborator,
        date: otDate,
        start_time: otStart,
        end_time: otEnd,
        note: otNote,
        active: true,
      });
      setOtNote("");
      await reload();
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="calendar-panel report-form">
      <header className="panel-title">
        <CalendarDays size={20} />
        <div>
          <h1>Calendário operacional</h1>
          <p className="tab-description">
            Feriados, meios períodos, exclusões (ex.: queda de energia) e hora extra por
            colaborador. Aplicado automaticamente ao gerar o relatório do mês.
          </p>
        </div>
      </header>

      <div className="calendar-sections">
        <section className="calendar-section">
          <div className="calendar-section-head">
            <h2>Exceções do expediente</h2>
            <span>{exceptions.length} neste mês</span>
          </div>

          <form className="calendar-form" onSubmit={(event) => void handleCreateException(event)}>
            <div className="calendar-form-row">
              <label>
                Data
                <input type="date" value={exDate} onChange={(e) => setExDate(e.target.value)} required />
              </label>
              <label>
                Tipo
                <select
                  value={exKind}
                  onChange={(e) => setExKind(e.target.value as CalendarExceptionKind)}
                >
                  {Object.entries(KIND_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              {exKind !== "holiday" ? (
                <>
                  <label>
                    Início
                    <input type="time" value={exStart} onChange={(e) => setExStart(e.target.value)} />
                  </label>
                  <label>
                    Fim
                    <input type="time" value={exEnd} onChange={(e) => setExEnd(e.target.value)} />
                  </label>
                </>
              ) : null}
              <label>
                Escopo
                <select
                  value={exScope}
                  onChange={(e) => setExScope(e.target.value as "all" | "collaborators")}
                >
                  <option value="all">Todos</option>
                  <option value="collaborators">Colaboradores</option>
                </select>
              </label>
              <label className="calendar-form-grow">
                Motivo
                <input
                  value={exNote}
                  onChange={(e) => setExNote(e.target.value)}
                  placeholder="Ex.: queda de energia"
                />
              </label>
              <button className="primary-button" type="submit" disabled={busy}>
                Salvar exceção
              </button>
            </div>

            {exScope === "collaborators" ? (
              <div className="calendar-people">
                <span className="calendar-people-label">Pessoas</span>
                <div className="calendar-people-grid">
                  {activeCollaborators.map((item) => {
                    const selected = exPeople.includes(item.id);
                    return (
                      <button
                        key={item.id}
                        type="button"
                        className={`check-row calendar-person${selected ? " active" : ""}`}
                        onClick={() => setExPeople((prev) => toggleId(prev, item.id))}
                      >
                        {item.name}
                      </button>
                    );
                  })}
                </div>
              </div>
            ) : null}
          </form>

          <div className="calendar-list-wrap">
            {exceptions.length === 0 ? (
              <p className="calendar-empty">Nenhuma exceção neste mês.</p>
            ) : (
              <ul className="calendar-list">
                {exceptions.map((item) => (
                  <li key={item.id}>
                    <div>
                      <strong>
                        {item.date} — {KIND_LABELS[item.kind]}
                      </strong>
                      <span>
                        {item.start_time && item.end_time
                          ? `${item.start_time.slice(0, 5)}–${item.end_time.slice(0, 5)}`
                          : "dia inteiro"}
                        {item.note ? ` · ${item.note}` : ""}
                        {item.scope === "collaborators"
                          ? ` · ${item.collaborator_names.join(", ") || "sem pessoas"}`
                          : " · todos"}
                      </span>
                    </div>
                    <button
                      type="button"
                      className="ghost-btn danger"
                      aria-label="Remover exceção"
                      onClick={() =>
                        void deleteCalendarException(token, item.id)
                          .then(reload)
                          .catch((err) => onError(err instanceof Error ? err.message : String(err)))
                      }
                    >
                      <Trash2 size={14} />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>

        <section className="calendar-section">
          <div className="calendar-section-head">
            <h2>
              <Clock3 size={16} /> Hora extra
            </h2>
            <span>{overtime.length} neste mês</span>
          </div>

          <form className="calendar-form" onSubmit={(event) => void handleCreateOvertime(event)}>
            <div className="calendar-form-row">
              <label>
                Colaborador
                <select
                  value={otCollaborator}
                  onChange={(e) => setOtCollaborator(e.target.value ? Number(e.target.value) : "")}
                  required
                >
                  <option value="">Selecione</option>
                  {activeCollaborators.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Data
                <input type="date" value={otDate} onChange={(e) => setOtDate(e.target.value)} required />
              </label>
              <label>
                Início
                <input type="time" value={otStart} onChange={(e) => setOtStart(e.target.value)} required />
              </label>
              <label>
                Fim
                <input type="time" value={otEnd} onChange={(e) => setOtEnd(e.target.value)} required />
              </label>
              <label className="calendar-form-grow">
                Motivo
                <input
                  value={otNote}
                  onChange={(e) => setOtNote(e.target.value)}
                  placeholder="Ex.: plantão sábado"
                />
              </label>
              <button className="primary-button" type="submit" disabled={busy}>
                Salvar hora extra
              </button>
            </div>
          </form>

          <div className="calendar-list-wrap">
            {overtime.length === 0 ? (
              <p className="calendar-empty">Nenhuma hora extra neste mês.</p>
            ) : (
              <ul className="calendar-list">
                {overtime.map((item) => (
                  <li key={item.id}>
                    <div>
                      <strong>
                        {item.date} — {item.collaborator_name}
                      </strong>
                      <span>
                        {item.start_time.slice(0, 5)}–{item.end_time.slice(0, 5)}
                        {item.note ? ` · ${item.note}` : ""}
                      </span>
                    </div>
                    <button
                      type="button"
                      className="ghost-btn danger"
                      aria-label="Remover hora extra"
                      onClick={() =>
                        void deleteOvertimeEntry(token, item.id)
                          .then(reload)
                          .catch((err) => onError(err instanceof Error ? err.message : String(err)))
                      }
                    >
                      <Trash2 size={14} />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
