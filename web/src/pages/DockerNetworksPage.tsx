import { useEffect, useState } from "react";
import { Layout } from "../components/Layout";
import { LoadingBlock, TableCard, Td, Th } from "../components/ui";

function Badge({ children, tone }: { children: React.ReactNode; tone: "blue" | "green" | "amber" | "slate" }) { const styles = { blue: "bg-sky-50 text-sky-700 ring-sky-200", green: "bg-emerald-50 text-emerald-700 ring-emerald-200", amber: "bg-amber-50 text-amber-700 ring-amber-200", slate: "bg-ink-100 text-ink-600 ring-ink-200" }; return <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ring-1 ${styles[tone]}`}>{children}</span>; }
function prefixTone(cidr: string) { const prefix = Number(cidr.split("/")[1]); return prefix >= 24 ? "green" : prefix >= 16 ? "blue" : "amber"; }
export function DockerNetworksPage() {
  const [data, setData] = useState<any>(null);
  useEffect(() => { fetch("/api/docker/networks", { credentials: "same-origin" }).then((r) => r.json()).then(setData); }, []);
  if (!data) return <Layout title="Docker"><LoadingBlock /></Layout>;
    return <Layout title="Docker" subtitle="networks and IP ranges on this host"><div className="grid gap-5"><TableCard title="Networks" subtitle={`${data.networks?.length ?? 0} networks`}><div className="mb-3 flex flex-wrap gap-2 px-2 text-xs text-ink-500"><Badge tone="green">/24+ local</Badge><Badge tone="blue">/16–/23 private</Badge><Badge tone="amber">larger range</Badge></div><table className="w-full"><thead><tr><Th>Name</Th><Th>Driver</Th><Th>Scope</Th><Th>IP ranges</Th><Th className="text-right">Containers</Th></tr></thead><tbody>{(data.networks ?? []).map((network: any) => <tr key={network.id} className="border-t border-ink-100"><Td><div className="font-medium text-ink-900">{network.name}</div><div className="font-mono text-[10px] text-ink-400">{network.id}</div></Td><Td>{network.driver}</Td><Td>{network.scope}{network.internal ? " · internal" : ""}</Td><Td mono><div className="flex flex-wrap gap-1">{(network.subnets ?? []).length ? network.subnets.map((subnet: string) => <Badge key={subnet} tone={prefixTone(subnet) as any}>{subnet}</Badge>) : <span className="text-ink-400">—</span>}{network.gateways?.map((gateway: string) => <Badge key={gateway} tone="slate">gw {gateway}</Badge>)}</div></Td><Td mono className="text-right">{network.containers}</Td></tr>)}</tbody></table></TableCard></div></Layout>;
}
