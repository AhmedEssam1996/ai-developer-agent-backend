"use client";

import { usePathname } from "next/navigation";
import { Command, LogOut, Menu, RefreshCw } from "lucide-react";
import { NAV_ITEMS } from "@/lib/nav";
import { useShell } from "@/stores/shell";
import { useAuth } from "@/stores/auth";

export function Topbar({ onMenu }: { onMenu: () => void }) {
  const pathname = usePathname();
  const setPaletteOpen = useShell((s) => s.setPaletteOpen);
  const loadIntegrations = useShell((s) => s.loadIntegrations);
  const isMock = useShell((s) => s.isMock);
  const logout = useAuth((s) => s.logout);

  const current = NAV_ITEMS.find((i) => pathname.startsWith(i.href));

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-white/[0.06] bg-base-900/70 px-4 backdrop-blur-xl">
      <button onClick={onMenu} className="btn-ghost !px-2 lg:hidden" aria-label="Open navigation">
        <Menu className="h-4 w-4" />
      </button>

      <h1 className="text-sm font-semibold tracking-tight text-ink-100">
        {current?.label ?? "MyWork AI"}
      </h1>

      {isMock && (
        <span className="chip border-violet/30 bg-violet/10 text-violet">Development data</span>
      )}

      <div className="ml-auto flex items-center gap-2">
        <button
          onClick={() => setPaletteOpen(true)}
          className="hidden items-center gap-2 rounded-lg border border-white/[0.07] bg-white/[0.02] px-2.5 py-1.5 text-xs text-ink-400 transition hover:text-ink-200 sm:flex"
        >
          <Command className="h-3.5 w-3.5" />
          <span>Commands</span>
          <kbd className="rounded border border-white/10 bg-white/[0.04] px-1.5 font-mono text-[10px]">
            K
          </kbd>
        </button>
        <button
          onClick={() => void loadIntegrations()}
          className="btn-ghost !px-2"
          aria-label="Refresh connections"
        >
          <RefreshCw className="h-4 w-4" />
        </button>
        <button onClick={logout} className="btn-ghost !px-2" aria-label="Sign out">
          <LogOut className="h-4 w-4" />
        </button>
      </div>
    </header>
  );
}