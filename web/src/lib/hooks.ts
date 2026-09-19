import { useCallback, useEffect, useRef, useState } from "react";
import { api, MetricPoint, RangeKey, UnauthorizedError } from "../lib/api";
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
