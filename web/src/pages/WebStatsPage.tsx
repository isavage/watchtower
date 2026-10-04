import { useMemo, useState } from "react";
import type { RangeKey, WebstatsSite } from "../lib/api";
import { useSortable, useWebstats } from "../lib/hooks";
import { fmtBytes, fmtClockWithDate, fmtNum } from "../lib/format";
import { Layout } from "../components/Layout";
import { MetricCard } from "../components/MetricCard";
import { MetricChart } from "../components/MetricChart";
import { LoadingBlock, StatTile, TableCard, Td, Th } from "../components/ui";

/** Compact integer formatting for request/visitor counts. */
function fmtCount(n: number | null | undefined): string {
  if (n == null || isNaN(n)) return "—";
  return Math.round(n).toLocaleString();
}

/** Tiny inline badge for a status-class count; muted when zero. */
function ClassBadge({ label, value, tone }: { label: string; value: number; tone: string }) {
  const zero = !value;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-mono tabular-nums ${
        zero ? "bg-ink-50 text-ink-300" : tone
      }`}
      title={`${label}: ${fmtCount(value)}`}
    >
      {label} {fmtCount(value)}
    </span>
  );
}

export function WebStatsPage() {
  const [range, setRange] = useState<RangeKey>("24h");
  const [selected, setSelected] = useState<string | null>(null);

  // One call returns the all-site rollup plus, when a site is selected, its
  // own series and top paths.
  const { data, error, loading } = useWebstats(range, selected ?? undefined);

  const sites = useMemo(() => data?.sites ?? [], [data]);

  const totals = useMemo(() => {
    let requests = 0;
    let bytes = 0;
    let visitors = 0;
    let errors = 0;
    for (const s of sites) {
      requests += s.requests;
      bytes += s.bytes;
      visitors += s.visitors;
      errors += s.s4xx + s.s5xx;
    }
    const errorRate = requests > 0 ? (errors / requests) * 100 : 0;
    return { requests, bytes, visitors, errors, errorRate, sites: sites.length };
  }, [sites]);

  const sortGetters = useMemo(
    () => ({
      site: (x: WebstatsSite) => x.site,
      requests: (x: WebstatsSite) => x.requests,
      visitors: (x: WebstatsSite) => x.visitors,
      bytes: (x: WebstatsSite) => x.bytes,
      errors: (x: WebstatsSite) => x.s4xx + x.s5xx,
      last_seen: (x: WebstatsSite) => x.last_seen,
    }),
    [],
  );

  const { items: sortedSites, sortKey, sortDirection, toggleSort } = useSortable(
    sites,
    "requests",
    "desc",
    sortGetters,
  );

  const ingesterError = data?.status?.last_error ?? null;
  const selectedSite = selected ? sites.find((s) => s.site === selected) ?? null : null;

  return (
    <Layout
      title="Websites"
      subtitle="nginx access-log aggregates, per site"
      range={range}
      onRange={setRange}
    >
      {error && (
        <div className="card mb-5 p-4 text-sm text-rose-600">
          {error} — the Websites ingester may not be reachable.
        </div>
      )}

      {loading && !data ? (
        <LoadingBlock />
      ) : (
        <div className="grid gap-5">
          {/* Rollup tiles */}
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <StatTile label="Requests" value={fmtCount(totals.requests)} sub={`${totals.sites} site${totals.sites === 1 ? "" : "s"}`} />
            <StatTile label="Visitors ≈" value={fmtCount(totals.visitors)} sub="approx., summed per window" />
            <StatTile label="Bytes out" value={fmtBytes(totals.bytes)} sub="response bodies" />
            <StatTile
              label="Error rate"
              value={totals.requests ? `${fmtNum(totals.errorRate, 1)}%` : "—"}
              sub={`${fmtCount(totals.errors)} 4xx + 5xx`}
            />
          </div>

          {/* All-site traffic chart */}
          <MetricCard
            title="Requests over time"
            subtitle="all sites, bucketed"
            value={<span className="text-xl">{fmtCount(totals.requests)}</span>}
          >
            <MetricChart
              data={data?.series ?? []}
              unit="count"
              wide
              series={[
                { key: "requests", name: "Requests", color: "#0ea5e9" },
                { key: "errors", name: "Errors", color: "#ef4444" },
              ]}
            />
          </MetricCard>

          {/* Drill-down for a selected site */}
          {selected && (
            <div className="grid gap-5 lg:grid-cols-2">
              <MetricCard
                title={selected}
                subtitle="requests for this site"
                right={
                  <button
                    type="button"
                    onClick={() => setSelected(null)}
                    className="rounded-lg border border-ink-200 px-3 py-1 text-xs font-medium text-ink-500 transition-colors hover:bg-ink-100 hover:text-ink-900"
                  >
                    ← All sites
                  </button>
                }
              >
                <MetricChart
                  data={data?.site_series ?? []}
                  unit="count"
                  series={[
                    { key: "requests", name: "Requests", color: "#0ea5e9" },
                    { key: "errors", name: "Errors", color: "#ef4444" },
                  ]}
                />
              </MetricCard>

              <TableCard
                title="Top paths"
                subtitle={selectedSite ? `${selected} · most requested in range` : "most requested in range"}
              >
                <table className="w-full">
                  <thead>
                    <tr>
                      <Th>Path</Th>
                      <Th className="text-right">Requests</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {(data?.top_paths ?? []).map((p) => (
                      <tr key={p.path} className="border-t border-ink-100">
                        <Td className="max-w-[16rem] truncate font-mono text-[12px] text-ink-700" >
                          {p.path}
                        </Td>
                        <Td mono className="text-right">{fmtCount(p.count)}</Td>
                      </tr>
                    ))}
                    {(data?.top_paths ?? []).length === 0 && (
                      <tr>
                        <Td className="text-ink-400">No path data for this site in the range.</Td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </TableCard>
            </div>
          )}

          {/* Per-site table */}
          <TableCard
            title="Sites"
            subtitle="click a row to drill into a site"
            right={
              ingesterError ? (
                <span
                  className="rounded-full bg-amber-50 px-2 py-1 text-[11px] text-amber-700"
                  title={ingesterError}
                >
                  ingester: {ingesterError}
                </span>
              ) : undefined
            }
          >
            <table className="w-full">
              <thead>
                <tr>
                  <Th sortKey="site" currentSortKey={sortKey} sortDirection={sortDirection} onSort={toggleSort}>
                    Site
                  </Th>
                  <Th sortKey="requests" currentSortKey={sortKey} sortDirection={sortDirection} onSort={toggleSort} className="text-right">
                    Requests
                  </Th>
                  <Th sortKey="visitors" currentSortKey={sortKey} sortDirection={sortDirection} onSort={toggleSort} className="text-right">
                    Visitors ≈
                  </Th>
                  <Th sortKey="bytes" currentSortKey={sortKey} sortDirection={sortDirection} onSort={toggleSort} className="text-right">
                    Bytes
                  </Th>
                  <Th className="hidden text-right lg:table-cell">Status mix</Th>
                  <Th sortKey="last_seen" currentSortKey={sortKey} sortDirection={sortDirection} onSort={toggleSort} className="text-right hidden sm:table-cell">
                    Last seen
                  </Th>
                </tr>
              </thead>
              <tbody>
                {sortedSites.map((s) => {
                  const active = selected === s.site;
                  return (
                    <tr
                      key={s.site}
                      onClick={() => setSelected(active ? null : s.site)}
                      className={`cursor-pointer border-t border-ink-100 transition-colors hover:bg-ink-50 ${
                        active ? "bg-ink-100/70" : ""
                      }`}
                    >
                      <Td className="font-medium text-ink-900">{s.site}</Td>
                      <Td mono className="text-right">{fmtCount(s.requests)}</Td>
                      <Td mono className="text-right text-ink-500">{fmtCount(s.visitors)}</Td>
                      <Td mono className="text-right">{fmtBytes(s.bytes)}</Td>
                      <Td className="hidden text-right lg:table-cell">
                        <span className="inline-flex flex-wrap justify-end gap-1">
                          <ClassBadge label="2" value={s.s2xx} tone="bg-emerald-50 text-emerald-700" />
                          <ClassBadge label="3" value={s.s3xx} tone="bg-sky-50 text-sky-700" />
                          <ClassBadge label="4" value={s.s4xx} tone="bg-amber-50 text-amber-700" />
                          <ClassBadge label="5" value={s.s5xx} tone="bg-rose-50 text-rose-700" />
                        </span>
                      </Td>
                      <Td mono className="text-right hidden text-ink-500 sm:table-cell">
                        {fmtClockWithDate(s.last_seen)}
                      </Td>
                    </tr>
                  );
                })}
                {sortedSites.length === 0 && (
                  <tr>
                    <Td className="text-ink-400">
                      No site data yet. Enable <span className="font-mono">WT_ALLOW_WEBSTATS=1</span>,
                      mount the nginx log directory into host-proxy, and wait for the ingester to
                      pull a delta.
                    </Td>
                  </tr>
                )}
              </tbody>
            </table>
          </TableCard>
        </div>
      )}
    </Layout>
  );
}
