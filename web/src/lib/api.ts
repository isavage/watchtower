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

// ---- /api/details ----

export interface ProcRow {
  pid: number;
  name: string;
  user: string;
  cpu_pct: number;
  mem_rss: number;
  mem_vms: number;
  mem_pct: number;
  status: string;
  threads: number;
  started: number;
  age: number;
}

export interface CoreRow {
  core: number;
  pct: number;
  user?: number;
  system?: number;
  idle?: number;
  iowait?: number;
}

export interface PartitionRow {
  device: string;
  mountpoint: string;
  fstype: string;
  total: number;
  used: number;
  free: number;
  pct: number;
}

export interface DiskDeviceRow {
  name: string;
  read_total: number;
  write_total: number;
  read_count: number;
  write_count: number;
  read_rate?: number;
  write_rate?: number;
  ops?: number;
}

export interface NicRow {
  name: string;
  up: boolean | null;
  speed_mbps: number | null;
  mtu: number | null;
  recv_total: number;
  sent_total: number;
  packets_err: number;
  packets_drop: number;
  recv_rate?: number;
  sent_rate?: number;
}

export interface Details {
  ts: number;
  host: {
    hostname: string;
    os: string;
    arch: string;
    boot_time: number | null;
    uptime: number | null;
  };
  cpu: {
    count_logical: number | null;
    count_physical: number | null;
    per_core: CoreRow[];
    breakdown: Record<string, number>;
    freq: { current: number | null; min: number | null; max: number | null } | null;
  };
  memory: {
    total: number;
    available: number;
    used: number;
    free: number;
    pct: number;
    active: number;
    inactive: number;
    buffers: number;
    cached: number;
    shared: number;
    swap_total: number;
    swap_used: number;
    swap_pct: number;
  };
  processes: {
    count: number;
    total_mem: number;
    top_cpu: ProcRow[];
    top_mem: ProcRow[];
  };
  partitions: PartitionRow[];
  disk_io: { devices: DiskDeviceRow[]; total: { read: number; write: number } | null };
  network: { interfaces: NicRow[] };
  addresses: { iface: string; family: string; address: string }[];
}

// ---- /api/docker ----

export interface DockerContainer {
  id: string;
  name: string;
  image: string;
  ports: { PublicPort?: number; PrivatePort: number; Type: string }[];
  state: string;
  status: string;
  started: number;
  age: number | null;
  cpu_pct: number | null;
  mem_usage: number | null;
  mem_limit: number | null;
  mem_pct: number | null;
  net_rx: number | null;
  net_tx: number | null;
  blkio: number | null;
  pids: number | null;
}

export interface DockerInfo {
  available: boolean;
  count?: number;
  cpu_total?: number;
  memory?: { total: number };
  containers: DockerContainer[];
}

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
  details: (limit = 15) => request<Details>(`/api/details?limit=${limit}`),
  docker: () => request<DockerInfo>("/api/docker"),
};
