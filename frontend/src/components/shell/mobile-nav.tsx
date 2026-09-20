"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { X } from "lucide-react";
import { NAV_ITEMS } from "@/lib/nav";
import { cn } from "@/lib/utils";

export function MobileNav({ open, onClose }: { open: boolean; onClose: () => void }) {
  const pathname = usePathname();

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-40 lg:hidden"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <div className="absolute inset-0 bg-base-950/70 backdrop-blur-sm" onClick={onClose} />
          <motion.nav
            initial={{ x: -320 }}
            animate={{ x: 0 }}
            exit={{ x: -320 }}
            transition={{ type: "spring", stiffness: 380, damping: 34 }}
            className="relative h-full w-[268px] overflow-y-auto border-r border-white/[0.08] bg-base-900/95 p-4 backdrop-blur-2xl"
          >
            <div className="mb-4 flex items-center justify-between">
              <span className="text-sm font-semibold text-ink-50">MyWork AI</span>
              <button onClick={onClose} className="btn-ghost !px-2" aria-label="Close">
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="space-y-0.5">
              {NAV_ITEMS.map((item) => {
                const active = pathname.startsWith(item.href);
                const Icon = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={onClose}
                    className={cn(
                      "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                      active ? "bg-white/[0.06] text-ink-50" : "text-ink-400",
                    )}
                  >
                    <Icon className="h-4 w-4" />
                    {item.label}
                  </Link>
                );
              })}
            </div>
          </motion.nav>
        </motion.div>
      )}
    </AnimatePresence>
  );
}