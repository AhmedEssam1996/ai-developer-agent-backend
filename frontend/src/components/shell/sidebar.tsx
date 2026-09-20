"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import { Command, Hexagon } from "lucide-react";
import { NAV_ITEMS } from "@/lib/nav";
import { cn } from "@/lib/utils";
import { useShell, connectionState } from "@/stores/shell";
import { useAuth } from "@/stores/auth";
import { StatusDot } from "@/components/ui";

const PROVIDERS = [
  { key: "outlook", label: "Outlook" },
  { key: "teams", label: "Teams" },
  { key: "goodday", label: "GoodDay" },
];

export function Sidebar() {
  const pathname = usePathname();
  const integrations = useShell((s) => s.integrations);
  const isMock = useShell((s) => s.isMock);
  const setPaletteOpen = useShell((s) => s.setPaletteOpen);
  const me = useAuth((s) => s.me);

  return (
    <aside className="hidden w-[248px] shrink-0 flex-col border-r border-white/[0.06] bg-base-900/60 backdrop-blur-xl lg:flex">
      <div className="flex items-center gap-2.5 px-5 py-5">
        <div className="relative grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-accent to-violet shadow-glow">
          <Hexagon className="h-4 w-4 text-white" strokeWidth={2.5} />
        </div>
        <div className="leading-tight">
          <p className="text-sm font-semibold tracking-tight text-ink-50">MyWork AI</p>
          <p className="text-[10px] uppercase tracking-[0.14em] text-ink-500">Work OS</p>
        </div>
      </div>

      <button
        onClick={() => setPaletteOpen(true)}
        className="mx-4 mb-4 flex items-center justify-between rounded-xl border border-white/[0.07] bg-white/[0.02] px-3 py-2 text-xs text-ink-400 transition hover:border-white/[0.12] hover:text-ink-200"
      >
        <span className="flex items-center gap-2">
          <Command className="h-3.5 w-3.5" />
          Search & commands
        </span>
        <kbd className="rounded border border-white/10 bg-white/[0.04] px-1.5 py-0.5 font-mono text-[10px]">
          ⌘K
        </kbd>
      </button>

      <nav className="flex-1 space-y-0.5 overflow-y-auto px-2.5">
        {NAV_ITEMS.map((item) => {
          const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "group relative flex items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] font-medium transition-colors",
                active ? "text-ink-50" : "text-ink-400 hover:text-ink-100",
              )}
            >
              {active && (
                <motion.span
                  layoutId="nav-active"
                  className="absolute inset-0 rounded-lg border border-white/[0.08] bg-white/[0.05]"
                  transition={{ type: "spring", stiffness: 400, damping: 32 }}
                />
              )}
              <Icon className="relative z-10 h-4 w-4" strokeWidth={active ? 2.2 : 1.8} />
              <span className="relative z-10">{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-white/[0.06] p-4">
        <p className="section-title mb-2.5">Connections</p>
        <div className="space-y-1.5">
          {PROVIDERS.map((p) => {
            const state = connectionState(integrations, p.key);
            return (
              <div key={p.key} className="flex items-center justify-between text-xs">
                <span className="flex items-center gap-2 text-ink-300">
                  <StatusDot state={state} />
                  {p.label}
                </span>
                <span className={cn("text-[10px]", state === "connected" ? "text-ink-500" : "text-ink-600")}>
                  {state === "connected" ? "connected" : state === "error" ? "error" : "off"}
                </span>
              </div>
            );
          })}
        </div>

        {isMock && (
          <div className="mt-3 rounded-lg border border-violet/25 bg-violet/[0.08] px-2.5 py-2 text-[10px] leading-tight text-violet">
            Development data — integrations run in mock mode.
          </div>
        )}

        <div className="mt-4 flex items-center gap-2.5 border-t border-white/[0.06] pt-3">
          <div className="grid h-7 w-7 place-items-center rounded-full bg-white/[0.06] text-[11px] font-semibold text-ink-200">
            {(me?.user.display_name ?? me?.user.email ?? "?").slice(0, 1).toUpperCase()}
          </div>
          <div className="min-w-0 leading-tight">
            <p className="truncate text-xs font-medium text-ink-200">
              {me?.user.display_name ?? "Signed in"}
            </p>
            <p className="truncate text-[10px] text-ink-500">{me?.organization.name ?? ""}</p>
          </div>
        </div>
      </div>
    </aside>
  );
}