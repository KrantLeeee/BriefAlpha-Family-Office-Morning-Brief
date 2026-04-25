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
 * Server component fetcher: tolerates the API being offline so the design
 * stays previewable. Falls back to the bundled fixture so visual review
 * works without `make dev-api` running.
 */
export async function getBriefToday(): Promise<Brief> {
  try {
    return await fetchJson<Brief>("/api/brief/today");
  } catch {
    const fallback = await import("./fixtures").then((m) => m.demoBrief);
    return { ...fallback, stale: true };
  }
}

export async function getSourceHealth(): Promise<SourceHealth> {
  try {
    return await fetchJson<SourceHealth>("/api/source-health");
  } catch {
    const fallback = await import("./fixtures").then((m) => m.demoSourceHealth);
    return fallback;
  }
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
