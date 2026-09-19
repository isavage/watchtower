export interface MetricPoint {
  ts: number;
  cpu_pct: number | null;
  cpu_count: number | null;
  load1: number | null;
  load5: number | null;
  load15: number | null;
  mem_total: number | null;
  mem_used: number | null;
  mem_pct: number | null;
  swap_total: number | null;
  swap_used: number | null;
  disk_total: number | null;
  disk_used: number | null;
  disk_pct: number | null;
  disk_read: number | null;
  disk_write: number | null;
  net_recv: number | null;
  net_sent: number | null;
  uptime: number | null;
  proc_count: number | null;
}

export type RangeKey = "5m" | "15m" | "1h" | "6h" | "24h" | "7d";

export const RANGES: { key: RangeKey; label: string }[] = [
  { key: "5m", label: "5m" },
  { key: "15m", label: "15m" },
  { key: "1h", label: "1h" },
  { key: "6h", label: "6h" },
  { key: "24h", label: "24h" },
  { key: "7d", label: "7d" },
];

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (res.status === 401) {
    throw new UnauthorizedError();
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export class UnauthorizedError extends Error {}

export const api = {
  me: () => request<{ user: string }>("/api/auth/me"),
  login: (username: string, password: string) =>
    request<{ user: string }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  logout: () => request<{ ok: boolean }>("/api/auth/logout", { method: "POST" }),
  summary: () => request<{ latest: MetricPoint | null }>("/api/summary"),
  series: (range: RangeKey) =>
    request<{ range: RangeKey; start: number; end: number; points: MetricPoint[] }>(
      `/api/series?range=${range}`,
    ),
};
