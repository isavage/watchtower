import { useEffect, useMemo, useState } from "react";
import { Layout } from "../components/Layout";
import { LoadingBlock, TableCard, Td, Th } from "../components/ui";
import { fmtBytes } from "../lib/format";
import { useSortable } from "../lib/hooks";

function Badge({ children, tone }: { children: React.ReactNode; tone: "blue" | "green" | "amber" | "slate" }) { const styles = { blue: "bg-sky-50 text-sky-700 ring-sky-200", green: "bg-emerald-50 text-emerald-700 ring-emerald-200", amber: "bg-amber-50 text-amber-700 ring-amber-200", slate: "bg-ink-100 text-ink-600 ring-ink-200" }; return <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ring-1 ${styles[tone]}`}>{children}</span>; }
function driverTone(driver: string) { return driver === "local" ? "blue" : driver === "tmpfs" ? "green" : "slate"; }
function fmtCreated(created: string | null): string { if (!created) return "—"; const d = new Date(created); return isNaN(d.getTime()) ? "—" : d.toLocaleString([], { year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }); }

export function DockerVolumesPage() {
  const [data, setData] = useState<any>(null);
  useEffect(() => { fetch("/api/docker/volumes", { credentials: "same-origin" }).then((r) => r.json()).then(setData); }, []);

  const volumes: any[] = data?.volumes ?? [];
  const inUse = volumes.filter((v) => (v.refcount ?? (v.used_by?.length ?? 0)) > 0).length;

  const sortGetters = useMemo(() => ({
    name: (v: any) => v.name,
    driver: (v: any) => v.driver || "",
    used_by: (v: any) => v.refcount ?? (v.used_by?.length ?? 0),
    created: (v: any) => (v.created ? new Date(v.created).getTime() : 0),
    size: (v: any) => v.size ?? -1,
  }), []);

  const { items: sortedVolumes, sortKey, sortDirection, toggleSort } = useSortable(
    volumes,
    "size",
    "desc",
    sortGetters
  );

  if (!data) return <Layout title="Docker"><LoadingBlock /></Layout>;
  if (!data.available) return <Layout title="Docker" subtitle="volumes on this host"><TableCard title="Volumes"><div className="px-2 py-3 text-sm text-ink-500">Docker API unavailable — is the docker-proxy sidecar reachable and <span className="font-mono">VOLUMES</span> enabled?</div></TableCard></Layout>;

  return (
    <Layout title="Docker" subtitle="named volumes on this host">
      <div className="grid gap-5">
        <TableCard title="Volumes" subtitle={`${volumes.length} volumes · ${inUse} in use`}>
          <div className="mb-3 flex flex-wrap gap-2 px-2 text-xs text-ink-500">
            <Badge tone="green">in use</Badge>
            <Badge tone="amber">unused</Badge>
            {data.usage_available === false ? (
              <span>Size needs Docker Engine 23.0+ (API 1.42) — this daemon doesn't report volume usage.</span>
            ) : (
              <span>Sizes come from the daemon (slow path); they may show — on older Docker versions.</span>
            )}
          </div>
          <table className="w-full">
            <thead>
              <tr>
                <Th sortKey="name" currentSortKey={sortKey} sortDirection={sortDirection} onSort={toggleSort}>Name</Th>
                <Th sortKey="driver" currentSortKey={sortKey} sortDirection={sortDirection} onSort={toggleSort}>Driver</Th>
                <Th sortKey="used_by" currentSortKey={sortKey} sortDirection={sortDirection} onSort={toggleSort}>Used by</Th>
                <Th sortKey="created" currentSortKey={sortKey} sortDirection={sortDirection} onSort={toggleSort} className="hidden lg:table-cell">Created</Th>
                <Th sortKey="size" currentSortKey={sortKey} sortDirection={sortDirection} onSort={toggleSort} className="text-right">Size</Th>
              </tr>
            </thead>
            <tbody>
              {sortedVolumes.map((volume: any) => {
                const users: string[] = volume.used_by ?? [];
                const refs = volume.refcount ?? users.length;
                return (
                  <tr key={volume.name} className="border-t border-ink-100">
                    <Td>
                      <div className="font-medium text-ink-900">{volume.name}</div>
                      <div className="truncate font-mono text-[10px] text-ink-400" title={volume.mountpoint}>{volume.mountpoint}</div>
                    </Td>
                    <Td><Badge tone={driverTone(volume.driver) as any}>{volume.driver || "unknown"}</Badge></Td>
                    <Td>
                      {refs > 0 || users.length ? (
                        <div className="flex flex-wrap gap-1">
                          {users.map((u) => <Badge key={u} tone="green">{u}</Badge>)}
                          {!users.length && <Badge tone="green">{refs} refs</Badge>}
                        </div>
                      ) : (
                        <Badge tone="amber">unused</Badge>
                      )}
                    </Td>
                    <Td className="hidden text-ink-500 lg:table-cell">{fmtCreated(volume.created)}</Td>
                    <Td mono className="text-right">{fmtBytes(volume.size)}</Td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </TableCard>
      </div>
    </Layout>
  );
}
