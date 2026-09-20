"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, Search, Sparkles } from "lucide-react";
import { NAV_ITEMS } from "@/lib/nav";
import { cn } from "@/lib/utils";
import { useShell } from "@/stores/shell";

interface Command {
  id: string;
  label: string;
  icon: typeof Search;
  run: () => void;
}

export function CommandPalette() {
  const router = useRouter();
  const open = useShell((s) => s.paletteOpen);
  const setOpen = useShell((s) => s.setPaletteOpen);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen(!useShell.getState().paletteOpen);
      }
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [setOpen]);

  useEffect(() => {
    if (open) {
      setQuery("");
      setActive(0);
    }
  }, [open]);

  const commands = useMemo<Command[]>(() => {
    const quick: Command[] = [
      { id: "ask", label: "Ask the AI agent…", icon: Sparkles, run: () => router.push("/agent") },
      {
        id: "prepare",
        label: "Prepare me for my next meeting",
        icon: Sparkles,
        run: () => router.push("/agent?q=Prepare me for my next meeting"),
      },
      {
        id: "brief",
        label: "Generate my daily brief",
        icon: Sparkles,
        run: () => router.push("/agent?q=What should I focus on today?"),
      },
    ];
    const nav: Command[] = NAV_ITEMS.map((item) => ({
      id: `nav-${item.href}`,
      label: `Go to ${item.label}`,
      icon: item.icon,
      run: () => router.push(item.href),
    }));
    return [...quick, ...nav];
  }, [router]);

  const filtered = useMemo(() => {
    if (!query.trim()) return commands;
    const q = query.toLowerCase();
    return commands.filter((c) => c.label.toLowerCase().includes(q));
  }, [commands, query]);

  function execute(command: Command) {
    command.run();
    setOpen(false);
  }

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-50 flex items-start justify-center px-4 pt-[12vh]"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <div className="absolute inset-0 bg-base-950/70 backdrop-blur-sm" onClick={() => setOpen(false)} />
          <motion.div
            initial={{ opacity: 0, y: -8, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.98 }}
            transition={{ duration: 0.16 }}
            className="relative w-full max-w-xl overflow-hidden rounded-2xl border border-white/[0.08] bg-base-850/95 shadow-glow backdrop-blur-2xl"
          >
            <div className="flex items-center gap-3 border-b border-white/[0.06] px-4 py-3">
              <Search className="h-4 w-4 text-ink-500" />
              <input
                autoFocus
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setActive(0);
                }}
                onKeyDown={(e) => {
                  if (e.key === "ArrowDown") {
                    e.preventDefault();
                    setActive((a) => Math.min(a + 1, filtered.length - 1));
                  } else if (e.key === "ArrowUp") {
                    e.preventDefault();
                    setActive((a) => Math.max(a - 1, 0));
                  } else if (e.key === "Enter" && filtered[active]) {
                    execute(filtered[active]);
                  }
                }}
                placeholder="Search or run a command…"
                className="w-full bg-transparent text-sm text-ink-100 placeholder:text-ink-500 outline-none"
              />
            </div>
            <div className="max-h-[50vh] overflow-y-auto p-2">
              {filtered.length === 0 && (
                <p className="px-3 py-6 text-center text-sm text-ink-500">No commands found.</p>
              )}
              {filtered.map((command, index) => {
                const Icon = command.icon;
                return (
                  <button
                    key={command.id}
                    onMouseEnter={() => setActive(index)}
                    onClick={() => execute(command)}
                    className={cn(
                      "flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm transition-colors",
                      index === active ? "bg-white/[0.06] text-ink-50" : "text-ink-300",
                    )}
                  >
                    <Icon className="h-4 w-4 shrink-0 text-ink-500" />
                    <span className="flex-1 truncate">{command.label}</span>
                    <ArrowRight className="h-3.5 w-3.5 text-ink-600" />
                  </button>
                );
              })}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}