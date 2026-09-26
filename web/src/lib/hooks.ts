import { useCallback, useMemo, useEffect, useRef, useState } from "react";
import { api, Details, DockerInfo, MetricPoint, RangeKey, UnauthorizedError } from "../lib/api";
import { useAuth } from "../lib/auth";

/** Poll the live summary on an interval. */
export function useSummary(intervalMs = 3000) {
  const { clear } = useAuth();
  const [latest, setLatest] = useState<MetricPoint | null>(null);
  const [error, setError] = useState<string | null>(null);

  const tick = useCallback(async () => {
    try {
      const r = await api.summary();
      setLatest(r.latest);
      setError(null);
    } catch (e) {
      if (e instanceof UnauthorizedError) clear();
      else setError(e instanceof Error ? e.message : "Failed to load");
    }
  }, [clear]);

  useEffect(() => {
    tick();
    const id = setInterval(tick, intervalMs);
    return () => clearInterval(id);
  }, [tick, intervalMs]);

  return { latest, error };
}

/** Fetch a downsampled series for a time range. */
export function useSeries(range: RangeKey) {
  const { clear } = useAuth();
  const [points, setPoints] = useState<MetricPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const reqId = useRef(0);

  const reload = useCallback(async () => {
    const id = ++reqId.current;
    setLoading(true);
    try {
      const r = await api.series(range);
      if (id === reqId.current) setPoints(r.points);
    } catch (e) {
      if (e instanceof UnauthorizedError) clear();
    } finally {
      if (id === reqId.current) setLoading(false);
    }
  }, [range, clear]);

  useEffect(() => {
    reload();
    // Refresh the series periodically so charts advance with live data.
    const id = setInterval(reload, 10000);
    return () => clearInterval(id);
  }, [reload]);

  return { points, loading };
}

/** Poll the live system-details endpoint on an interval. */
export function useDetails(intervalMs = 2000) {
  const { clear } = useAuth();
  const [data, setData] = useState<Details | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const r = await api.details();
        if (alive) {
          setData(r);
          setError(null);
        }
      } catch (e) {
        if (e instanceof UnauthorizedError) clear();
        else if (alive) setError(e instanceof Error ? e.message : "Failed to load");
      }
    };
    tick();
    const id = setInterval(tick, intervalMs);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [intervalMs, clear]);

  return { data, error };
}

/** Poll the Docker containers endpoint on an interval. */
export function useDocker(intervalMs = 3000) {
  const { clear } = useAuth();
  const [data, setData] = useState<DockerInfo | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const r = await api.docker();
        if (alive) {
          setData(r);
          setError(null);
        }
      } catch (e) {
        if (e instanceof UnauthorizedError) clear();
        else if (alive) setError(e instanceof Error ? e.message : "Failed to load");
      }
    };
    tick();
    const id = setInterval(tick, intervalMs);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [intervalMs, clear]);

  return { data, error };
}
/** Sort an array of objects by column key and direction. */
export function useSortable<T>(
  items: T[],
  defaultKey: string | null = null,
  defaultDirection: "asc" | "desc" = "asc",
  getters?: Record<string, (item: T) => any>
) {
  const [sortKey, setSortKey] = useState<string | null>(defaultKey);
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">(defaultDirection);

  const toggleSort = (key: string) => {
    if (sortKey === key) {
      setSortDirection((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDirection("asc");
    }
  };

  const sortedItems = useMemo(() => {
    if (!sortKey) return items;
    const getter = getters?.[sortKey] ?? ((item: any) => item[sortKey]);
    return [...items].sort((a, b) => {
      const va = getter(a);
      const vb = getter(b);

      if (va == null && vb == null) return 0;
      if (va == null) return 1;
      if (vb == null) return -1;

      if (typeof va === "string" && typeof vb === "string") {
        const res = va.localeCompare(vb, undefined, { numeric: true, sensitivity: "base" });
        return sortDirection === "asc" ? res : -res;
      }

      if (va < vb) return sortDirection === "asc" ? -1 : 1;
      if (va > vb) return sortDirection === "asc" ? 1 : -1;
      return 0;
    });
  }, [items, sortKey, sortDirection, getters]);

  return { items: sortedItems, sortKey, sortDirection, toggleSort };
}
