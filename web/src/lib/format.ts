// Formatting helpers shared across the dashboard.

export function fmtBytes(bytes: number | null | undefined, digits = 1): string {
  if (bytes == null || isNaN(bytes)) return "—";
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB", "PB"];
  const i = Math.min(Math.floor(Math.log(Math.abs(bytes)) / Math.log(1024)), units.length - 1);
  const v = bytes / Math.pow(1024, i);
  return `${v.toFixed(i === 0 ? 0 : digits)} ${units[i]}`;
}

export function fmtRate(bytesPerSec: number | null | undefined): string {
  if (bytesPerSec == null || isNaN(bytesPerSec)) return "—";
  return `${fmtBytes(bytesPerSec, 1)}/s`;
}

export function fmtPct(pct: number | null | undefined, digits = 0): string {
  if (pct == null || isNaN(pct)) return "—";
  return `${pct.toFixed(digits)}%`;
}

export function fmtNum(n: number | null | undefined, digits = 2): string {
  if (n == null || isNaN(n)) return "—";
  return n.toFixed(digits);
}

export function fmtUptime(seconds: number | null | undefined): string {
  if (seconds == null || isNaN(seconds)) return "—";
  const s = Math.floor(seconds);
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

/** Like fmtUptime but precise enough for short-lived processes/containers. */
export function fmtDuration(seconds: number | null | undefined): string {
  if (seconds == null || isNaN(seconds)) return "—";
  const s = Math.floor(seconds);
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${sec}s`;
  return `${sec}s`;
}

export function fmtClock(tsSeconds: number): string {
  const dt = new Date(tsSeconds * 1000);
  return dt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function fmtClockWithHours(tsSeconds: number): string {
  const dt = new Date(tsSeconds * 1000);
  return dt.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
