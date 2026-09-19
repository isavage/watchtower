import { useEffect, useState } from "react";
import { Layout } from "../components/Layout";
import { LoadingBlock, TableCard, Td, Th } from "../components/ui";

export function DockerNetworksPage() {
  const [data, setData] = useState<any>(null);
  useEffect(() => { fetch("/api/docker/networks", { credentials: "same-origin" }).then((r) => r.json()).then(setData); }, []);
  if (!data) return <Layout title="Docker"><LoadingBlock /></Layout>;
    return <Layout title="Docker" subtitle="networks and IP ranges on this host"><div className="grid gap-5"><TableCard title="Networks" subtitle={`${data.networks?.length ?? 0} networks`}><table className="w-full"><thead><tr><Th>Name</Th><Th>Driver</Th><Th>Scope</Th><Th>IP ranges</Th><Th className="text-right">Containers</Th></tr></thead><tbody>{(data.networks ?? []).map((network: any) => <tr key={network.id} className="border-t border-ink-100"><Td><div className="font-medium text-ink-900">{network.name}</div><div className="font-mono text-[10px] text-ink-400">{network.id}</div></Td><Td>{network.driver}</Td><Td>{network.scope}{network.internal ? " · internal" : ""}</Td><Td mono>{(network.subnets ?? []).join(", ") || "—"}{network.gateways?.length ? ` · gw ${network.gateways.join(", ")}` : ""}</Td><Td mono className="text-right">{network.containers}</Td></tr>)}</tbody></table></TableCard></div></Layout>;
}
