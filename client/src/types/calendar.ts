import type { Collaborator } from "../types/report";

export type CalendarExceptionKind = "holiday" | "schedule_override" | "exclude_window";

export interface WorkCalendarException {
  id: number;
  date: string;
  kind: CalendarExceptionKind;
  start_time: string | null;
  end_time: string | null;
  scope: "all" | "collaborators";
  collaborator_ids: number[];
  collaborator_names: string[];
  note: string;
  active: boolean;
}

export interface OvertimeEntry {
  id: number;
  collaborator: number;
  collaborator_name: string;
  date: string;
  start_time: string;
  end_time: string;
  note: string;
  active: boolean;
}

export interface CalendarExceptionPayload {
  date: string;
  kind: CalendarExceptionKind;
  start_time?: string | null;
  end_time?: string | null;
  scope?: "all" | "collaborators";
  collaborator_ids?: number[];
  note?: string;
  active?: boolean;
}

export interface OvertimePayload {
  collaborator: number;
  date: string;
  start_time: string;
  end_time: string;
  note?: string;
  active?: boolean;
}

export type { Collaborator };
