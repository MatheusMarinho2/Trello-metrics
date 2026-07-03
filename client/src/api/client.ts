import type { Collaborator, GenerateReportPayload, GeneratedReport, ReportOptions, ReportType } from "../types/report";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api";
const TOKEN_KEY = "intgest_reports_token";

export function getStoredToken(): string {
  return localStorage.getItem(TOKEN_KEY) ?? "";
}

export function setStoredToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearStoredToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export async function login(username: string, password: string): Promise<string> {
  const response = await fetch(`${API_BASE_URL}/auth/login/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  const data = await parseResponse(response);
  setStoredToken(data.access);
  return data.access;
}

export async function getMe(token: string): Promise<{ user: { username: string } }> {
  return apiFetch("/auth/me/", token);
}

export async function getReportOptions(token: string): Promise<ReportOptions> {
  return apiFetch("/reports/options/", token);
}

export async function listReports(token: string, reportType?: ReportType): Promise<GeneratedReport[]> {
  const query = reportType ? `?report_type=${encodeURIComponent(reportType)}` : "";
  return apiFetch(`/reports/${query}`, token);
}

export async function getReport(token: string, id: string): Promise<GeneratedReport> {
  return apiFetch(`/reports/${id}/`, token);
}

export async function generateReport(
  token: string,
  payload: GenerateReportPayload,
): Promise<GeneratedReport> {
  return apiFetch("/reports/generate/", token, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function downloadReport(
  token: string,
  id: string,
  format: "pdf" | "json" | "html",
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/reports/${id}/export/${format}/`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    await parseResponse(response);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const match = disposition.match(/filename="(.+)"/);
  link.href = url;
  link.download = match?.[1] ?? `intgest-report.${format}`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export async function listCollaborators(token: string): Promise<Collaborator[]> {
  return apiFetch("/collaborators/", token);
}

export async function createCollaborator(token: string, name: string): Promise<Collaborator> {
  return apiFetch("/collaborators/", token, {
    method: "POST",
    body: JSON.stringify({ name, aliases: [], active: true }),
  });
}

export async function updateCollaborator(
  token: string,
  id: number,
  data: Partial<Pick<Collaborator, "name" | "aliases" | "active">>,
): Promise<Collaborator> {
  return apiFetch(`/collaborators/${id}/`, token, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

async function apiFetch<T>(
  path: string,
  token: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(init.headers ?? {}),
    },
  });
  return parseResponse(response);
}

async function parseResponse(response: Response): Promise<any> {
  const contentType = response.headers.get("Content-Type") ?? "";
  const data = contentType.includes("application/json")
    ? await response.json()
    : await response.text();
  if (!response.ok) {
    const message = typeof data === "string" ? data : data.detail ?? JSON.stringify(data);
    throw new Error(message);
  }
  return data;
}
