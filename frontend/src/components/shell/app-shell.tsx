"use client";

import { useEffect, useState } from "react";
import { useShell } from "@/stores/shell";
import { useAuth } from "@/stores/auth";
import { Sidebar } from "./sidebar";
import { Topbar } from "./topbar";
import { MobileNav } from "./mobile-nav";
import { CommandPalette } from "./command-palette";

export function AppShell({ children }: { children: React.ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const loadIntegrations = useShell((s) => s.loadIntegrations);
  const me = useAuth((s) => s.me);

  useEffect(() => {
    if (me) void loadIntegrations();
  }, [me, loadIntegrations]);

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar onMenu={() => setMobileOpen(true)} />
        <main className="flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-[1180px] px-4 py-6 sm:px-6 lg:px-8">{children}</div>
        </main>
      </div>
      <MobileNav open={mobileOpen} onClose={() => setMobileOpen(false)} />
      <CommandPalette />
    </div>
  );
}