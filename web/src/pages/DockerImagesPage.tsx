import { useEffect, useState } from "react";
import { Layout } from "../components/Layout";
import { LoadingBlock, TableCard, Td, Th } from "../components/ui";
import { fmtBytes } from "../lib/format";

function Badge({ children, tone }: { children: React.ReactNode; tone: "blue" | "green" | "amber" | "slate" }) { const styles = { blue: "bg-sky-50 text-sky-700 ring-sky-200", green: "bg-emerald-50 text-emerald-700 ring-emerald-200", amber: "bg-amber-50 text-amber-700 ring-amber-200", slate: "bg-ink-100 text-ink-600 ring-ink-200" }; return <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ring-1 ${styles[tone]}`}>{children}</span>; }

export function DockerImagesPage() {
  const [data, setData] = useState<any>(null);
  useEffect(() => { fetch("/api/docker/images", { credentials: "same-origin" }).then((r) => r.json()).then(setData); }, []);
  if (!data) return <Layout title="Docker"><LoadingBlock /></Layout>;
  const images: any[] = data.images ?? [];
  const inUse = images.filter((i) => (i.used_by ?? []).length > 0).length;
    return <Layout title="Docker" subtitle="images on this host"><div className="grid gap-5"><TableCard title="Images" subtitle={`${images.length} images · ${inUse} in use`}><div className="mb-3 flex flex-wrap gap-2 px-2 text-xs text-ink-500"><Badge tone="green">used by containers</Badge><Badge tone="amber">unused</Badge><span>Containers (running and stopped) are matched by image ID, not tag.</span></div><table className="w-full"><thead><tr><Th>Image</Th><Th>Tags</Th><Th>Used by</Th><Th className="text-right">Size</Th></tr></thead><tbody>{images.map((image: any) => { const users: string[] = image.used_by ?? []; return <tr key={image.id} className="border-t border-ink-100"><Td mono>{image.id}</Td><Td>{(image.tags ?? []).join(", ") || "untagged"}</Td><Td>{users.length ? <div className="flex max-w-[260px] flex-wrap gap-1">{users.map((u) => <Badge key={u} tone="green">{u}</Badge>)}</div> : <Badge tone="amber">unused</Badge>}</Td><Td mono className="text-right">{fmtBytes(image.size)}</Td></tr>; })}</tbody></table></TableCard></div></Layout>;
}

export function DockerTabs({ active }: { active: string }) { return <nav className="flex flex-wrap gap-2 text-sm">{[["containers", "Containers"], ["images", "Images"], ["networks", "Networks"], ["volumes", "Volumes"]].map(([key, label]) => <a key={key} href={`/docker/${key}`} className={`rounded-lg px-3 py-1.5 ${active === key ? "bg-ink-900 text-white" : "bg-white text-ink-500 hover:bg-ink-100"}`}>{label}</a>)}</nav>; }
