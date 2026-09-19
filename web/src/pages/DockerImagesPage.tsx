import { useEffect, useState } from "react";
import { Layout } from "../components/Layout";
import { LoadingBlock, TableCard, Td, Th } from "../components/ui";
import { fmtBytes } from "../lib/format";

export function DockerImagesPage() {
  const [data, setData] = useState<any>(null);
  useEffect(() => { fetch("/api/docker/images", { credentials: "same-origin" }).then((r) => r.json()).then(setData); }, []);
  if (!data) return <Layout title="Docker"><LoadingBlock /></Layout>;
    return <Layout title="Docker" subtitle="images on this host"><div className="grid gap-5"><TableCard title="Images" subtitle={`${data.images?.length ?? 0} images`}><table className="w-full"><thead><tr><Th>Image</Th><Th>Tags</Th><Th className="text-right">Size</Th></tr></thead><tbody>{(data.images ?? []).map((image: any) => <tr key={image.id} className="border-t border-ink-100"><Td mono>{image.id}</Td><Td>{(image.tags ?? []).join(", ") || "untagged"}</Td><Td mono className="text-right">{fmtBytes(image.size)}</Td></tr>)}</tbody></table></TableCard></div></Layout>;
}

export function DockerTabs({ active }: { active: string }) { return <nav className="flex flex-wrap gap-2 text-sm">{[["containers", "Containers"], ["images", "Images"], ["networks", "Networks"]].map(([key, label]) => <a key={key} href={`/docker/${key}`} className={`rounded-lg px-3 py-1.5 ${active === key ? "bg-ink-900 text-white" : "bg-white text-ink-500 hover:bg-ink-100"}`}>{label}</a>)}</nav>; }
