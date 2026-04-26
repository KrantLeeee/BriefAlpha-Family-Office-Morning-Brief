import type { Brief, ParseReport, QaResponse, SourceHealth } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${path} failed: ${res.status} ${text}`);
  }
  return (await res.json()) as T;
}

/**
 * Fetches today's brief from the API. The API itself decides whether to
 * serve fixture (demo mode) or live data — the client is intentionally
 * NOT a silent fallback layer. If the request fails, the error
 * propagates so the page can render an explicit error state via
 * <ModeBanner status="error" />.
 */
export async function getBriefToday(): Promise<Brief> {
  return fetchJson<Brief>("/api/brief/today");
}

export async function getSourceHealth(): Promise<SourceHealth> {
  return fetchJson<SourceHealth>("/api/source-health");
}

export async function postQa(body: {
  brief_id: string;
  scope: "judgement" | "evidence" | "global";
  scope_target_id?: string;
  question: string;
}): Promise<QaResponse> {
  return fetchJson<QaResponse>("/api/qa", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function uploadResearch(form: FormData): Promise<{ file_id: string; status: string }> {
  const res = await fetch(`${API_BASE}/api/research/upload`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(`upload failed: ${res.status}`);
  return res.json();
}

export async function getParseReport(fileId: string): Promise<ParseReport> {
  return fetchJson<ParseReport>(`/api/research/${fileId}/parse_report`);
}
