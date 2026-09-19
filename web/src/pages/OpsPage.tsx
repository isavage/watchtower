import { useEffect, useState } from "react";

type Ops = any;
function Card({title, children}:{title:string;children:React.ReactNode}) { return <section className="card min-w-0 p-4 sm:p-5"><h2 className="mb-3 text-sm font-semibold text-ink-900">{title}</h2>{children}</section> }
function List({items, empty="None reported"}:{items:string[];empty?:string}) { return items.length ? <ul className="space-y-1 text-xs text-ink-600">{items.map((x,i)=><li key={i} className="rounded-lg bg-ink-50 px-2 py-1 font-mono break-all">{x}</li>)}</ul> : <p className="text-xs text-ink-400">{empty}</p> }
export function OpsPage(){
 const [data,setData]=useState<Ops|null>(null); const [error,setError]=useState("");
 useEffect(()=>{fetch("/api/ops",{credentials:"same-origin"}).then(r=>r.ok?r.json():Promise.reject()).then(setData).catch(()=>setError("Could not collect read-only host data."));},[]);
 if(error)return <div className="card p-5 text-sm text-rose-600">{error}</div>;
 if(!data)return <div className="card p-8 text-sm text-ink-500">Collecting VPS overview…</div>;
 const sec=data.security; const h=data.health;
 return <div className="grid gap-5 lg:grid-cols-2">
  <Card title="Security & firewall"><div className="mb-3 flex flex-wrap gap-2"><span className="rounded-full bg-emerald-50 px-2 py-1 text-xs text-emerald-700">Read-only</span><span className="rounded-full bg-ink-100 px-2 py-1 text-xs text-ink-600">UFW {sec.ufw.available?"available":"not detected"}</span></div><List items={sec.ufw.status}/><h3 className="mt-4 mb-2 text-xs font-medium text-ink-500">iptables rules</h3><List items={sec.iptables.rules}/></Card>
  <Card title="SSH login audit"><h3 className="mb-2 text-xs font-medium text-ink-500">Failed logins ({data.ssh.failed.length})</h3><List items={data.ssh.failed.map((x:any)=>`${x.user} · ${x.source} · ${x.when}`)} empty="No failed logins returned"/><h3 className="mt-4 mb-2 text-xs font-medium text-ink-500">Recent logins</h3><List items={data.ssh.recent.slice(0,8).map((x:any)=>`${x.user} · ${x.source} · ${x.when}`)}/></Card>
  <Card title="Listening ports"><List items={data.listeners.map((x:any)=>`${x.address} · pid ${x.pid??"—"}`)} empty="No listeners returned"/></Card>
  <Card title="Services & containers"><h3 className="mb-2 text-xs font-medium text-ink-500">Docker containers</h3><List items={data.services.docker.map((x:any)=>`${x.name} · ${x.status}${x.ports?` · ${x.ports}`:""}`)}/><h3 className="mt-4 mb-2 text-xs font-medium text-ink-500">Failed systemd units</h3><List items={data.services.failed_systemd}/></Card>
  <Card title="Host health"><div className="grid grid-cols-2 gap-3 text-sm"><div><span className="text-xs text-ink-400">Memory</span><p className="font-mono font-semibold">{h.memory_pct}%</p></div><div><span className="text-xs text-ink-400">Root disk</span><p className="font-mono font-semibold">{h.disk_pct}%</p></div><div><span className="text-xs text-ink-400">Load 1m</span><p className="font-mono font-semibold">{h.load?.[0]?.toFixed?.(2)??"—"}</p></div><div><span className="text-xs text-ink-400">Free disk</span><p className="font-mono font-semibold">{(data.storage.root.free/1024/1024/1024).toFixed(1)} GB</p></div></div></Card>
  <Card title="Collection scope"><p className="text-sm text-ink-600">{data.metadata.hostname}</p><p className="mt-1 text-xs text-ink-400">All data on this page is observational. No firewall, SSH, service, package, or process changes are performed.</p></Card>
 </div>
}
