import { useEffect, useState, type ReactNode } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { useAuth } from "../lib/auth";
import type { RangeKey } from "../lib/api";
import { TimeRangeSelector } from "./TimeRangeSelector";

const DOCKER_NAV = [
  { to: "/docker/containers", label: "Containers" },
  { to: "/docker/images", label: "Images" },
  { to: "/docker/networks", label: "Networks" },
];

const NAV: { to: string; label: string; icon: ReactNode; end?: boolean }[] = [
  {
    to: "/",
    label: "Dashboard",
    end: true,
    icon: (
      <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="3" width="7" height="9" rx="1.5" />
        <rect x="14" y="3" width="7" height="5" rx="1.5" />
        <rect x="14" y="12" width="7" height="9" rx="1.5" />
        <rect x="3" y="16" width="7" height="5" rx="1.5" />
      </svg>
    ),
  },
  {
    to: "/cpu",
    label: "CPU",
    icon: (
      <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <rect x="5" y="5" width="14" height="14" rx="2" />
        <rect x="9.5" y="9.5" width="5" height="5" rx="1" />
        <path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3" />
      </svg>
    ),
  },
  {
    to: "/memory",
    label: "Memory",
    icon: (
      <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M6 19v-3M10 19v-3M14 19v-3M18 19v-3" />
        <rect x="3" y="5" width="18" height="11" rx="2" />
        <path d="M7 9h.01M11 9h.01M15 9h.01" />
      </svg>
    ),
  },
  {
    to: "/disk",
    label: "Disk",
    icon: (
      <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <ellipse cx="12" cy="5" rx="9" ry="3" />
        <path d="M3 5v14a9 3 0 0 0 18 0V5" />
        <path d="M3 12a9 3 0 0 0 18 0" />
      </svg>
    ),
  },
  {
    to: "/network",
    label: "Network",
    icon: (
      <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="9" />
        <path d="M3 12h18" />
        <path d="M12 3a15 15 0 0 1 0 18a15 15 0 0 1 0-18" />
      </svg>
    ),
  },
  {
    to: "/docker",
    label: "Docker",
    icon: (
      <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="13" width="5" height="5" rx="1" />
        <rect x="9.5" y="13" width="5" height="5" rx="1" />
        <rect x="16" y="13" width="5" height="5" rx="1" />
        <rect x="9.5" y="7" width="5" height="5" rx="1" />
        <rect x="16" y="7" width="5" height="5" rx="1" />
        <rect x="16" y="1" width="5" height="5" rx="1" />
      </svg>
    ),
  },
  {
    to: "/security",
    label: "Security",
    icon: (
      <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 3 20 6v5c0 5-3.4 8.5-8 10-4.6-1.5-8-5-8-10V6l8-3Z" />
        <path d="m9 12 2 2 4-4" />
      </svg>
    ),
  },
];

export function Layout({
  title,
  subtitle,
  range,
  onRange,
  actions,
  children,
}: {
  title: string;
  subtitle?: ReactNode;
  /** When provided, the page shows the shared time-range selector in its header. */
  range?: RangeKey;
  onRange?: (r: RangeKey) => void;
  actions?: ReactNode;
  children: ReactNode;
}) {
  const { user, logout } = useAuth();
  const { pathname } = useLocation();
  const inDocker = pathname.startsWith("/docker/");
  const [dockerOpen, setDockerOpen] = useState(inDocker);
  useEffect(() => { setDockerOpen(inDocker); }, [inDocker]);

  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-60 flex-col border-r border-ink-200/70 bg-white md:flex">
        <div className="flex items-center gap-2.5 px-5 py-[18px]">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-ink-900 text-white">
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 12h4l2 6 4-14 2 8h6" />
            </svg>
          </div>
          <span className="text-[15px] font-semibold tracking-tight text-ink-900">Watchtower</span>
        </div>

        <nav className="mt-1 flex-1 space-y-0.5 px-3">
          {NAV.map((item) => item.to === "/docker" ? (
            <div key={item.to}>
              <button type="button" onClick={() => setDockerOpen((open) => !open)} className={`group flex w-full items-center gap-3 rounded-xl px-3 py-2 text-left text-sm font-medium transition-colors ${dockerOpen ? "bg-ink-900 text-white" : "text-ink-500 hover:bg-ink-100 hover:text-ink-900"}`}>
                {item.icon}<span className="flex-1">{item.label}</span><span className={`text-xs transition-transform ${dockerOpen ? "rotate-90" : ""}`}>›</span>
              </button>
              {dockerOpen && <div className="ml-5 mt-0.5 space-y-0.5 border-l border-ink-200 pl-3">{DOCKER_NAV.map((child) => <NavLink key={child.to} to={child.to} className={({ isActive }) => `block rounded-lg px-3 py-1.5 text-xs font-medium ${isActive ? "bg-ink-100 text-ink-900" : "text-ink-400 hover:bg-ink-50 hover:text-ink-700"}`}>{child.label}</NavLink>)}</div>}
            </div>
          ) : (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `group flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-ink-900 text-white"
                    : "text-ink-500 hover:bg-ink-100 hover:text-ink-900"
                }`
              }
            >
              {item.icon}
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-ink-200/70 px-5 py-4">
          <div className="flex items-center justify-between gap-2">
            <div className="min-w-0">
              <div className="text-xs text-ink-400">Signed in as</div>
              <div className="truncate text-sm font-medium text-ink-800">{user}</div>
            </div>
            <button
              onClick={() => logout()}
              title="Sign out"
              className="rounded-lg p-2 text-ink-400 transition-colors hover:bg-ink-100 hover:text-ink-900"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                <path d="M16 17l5-5-5-5M21 12H9" />
              </svg>
            </button>
          </div>
        </div>
      </aside>

      {/* Mobile top bar (collapsed nav) */}
      <div className="fixed inset-x-0 top-0 z-20 flex items-center gap-2 border-b border-ink-200/70 bg-white/90 px-4 py-3 pb-[calc(0.75rem+env(safe-area-inset-top))] pt-[calc(0.75rem+env(safe-area-inset-top))] backdrop-blur md:hidden">
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-ink-900 text-white">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3 12h4l2 6 4-14 2 8h6" />
          </svg>
        </div>
        <span className="text-sm font-semibold text-ink-900">Watchtower</span>
        <div className="ml-auto flex gap-1 overflow-x-auto">
          {NAV.map((item) => item.to === "/docker" ? (
            <button key={item.to} type="button" onClick={() => setDockerOpen((open) => !open)} className={`shrink-0 rounded-lg px-2.5 py-1 text-xs font-medium ${dockerOpen ? "bg-ink-900 text-white" : "text-ink-500 hover:bg-ink-100"}`}>{item.label} <span className={`inline-block transition-transform ${dockerOpen ? "rotate-90" : ""}`}>›</span></button>
          ) : (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `rounded-lg px-2.5 py-1 text-xs font-medium ${
                  isActive ? "bg-ink-900 text-white" : "text-ink-500 hover:bg-ink-100"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </div>
        {dockerOpen && (
          <div className="fixed inset-x-0 top-[53px] z-20 flex gap-1 overflow-x-auto border-b border-ink-200/70 bg-white/95 px-4 py-2 backdrop-blur md:hidden">
            {DOCKER_NAV.map((item) => <NavLink key={item.to} to={item.to} className={({ isActive }) => `shrink-0 rounded-lg px-2.5 py-1 text-xs font-medium ${isActive ? "bg-ink-900 text-white" : "text-ink-500 hover:bg-ink-100"}`}>{item.label}</NavLink>)}
          </div>
        )}
      </div>

      {/* Main column */}
      <div className="flex min-w-0 flex-1 flex-col md:pl-60">
        <header className="sticky top-[53px] z-10 border-b border-ink-200/70 bg-white/80 backdrop-blur md:top-0">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-5 py-3.5 md:px-8">
            <div className="min-w-0">
              <h1 className="truncate text-[15px] font-semibold tracking-tight text-ink-900">{title}</h1>
              {subtitle && <p className="truncate text-xs text-ink-400">{subtitle}</p>}
            </div>
            <div className="ml-auto flex items-center gap-3">
              {actions}
              {range && onRange && <TimeRangeSelector value={range} onChange={onRange} />}
            </div>
          </div>
        </header>

        <main className="flex-1 px-5 py-6 md:px-8">{children}</main>
      </div>
    </div>
  );
}
