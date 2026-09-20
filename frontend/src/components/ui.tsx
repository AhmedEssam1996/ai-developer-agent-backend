// Reusable UI primitives (shadcn-style, original visual identity).

import * as React from "react";
import { cn } from "@/lib/utils";

// --- Card --------------------------------------------------------------------

export function Card({
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("panel", className)} {...props}>
      {children}
    </div>
  );
}

export function CardHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("flex items-center justify-between gap-3 px-5 pt-5", className)} {...props} />;
}

export function CardTitle({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return <h3 className={cn("section-title", className)} {...props} />;
}

export function CardBody({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("px-5 pb-5 pt-3", className)} {...props} />;
}

// --- Badge -------------------------------------------------------------------

const TONES: Record<string, string> = {
  neutral: "border-white/[0.08] bg-white/[0.03] text-ink-300",
  accent: "border-accent/30 bg-accent/10 text-accent-soft",
  violet: "border-violet/30 bg-violet/10 text-violet",
  teal: "border-teal/30 bg-teal/10 text-teal",
  urgent: "border-signal-urgent/30 bg-signal-urgent/10 text-signal-urgent",
  warn: "border-signal-warn/30 bg-signal-warn/10 text-signal-warn",
  ok: "border-signal-ok/30 bg-signal-ok/10 text-signal-ok",
};

export function Badge({
  tone = "neutral",
  className,
  children,
}: {
  tone?: keyof typeof TONES;
  className?: string;
  children: React.ReactNode;
}) {
  return <span className={cn("chip", TONES[tone], className)}>{children}</span>;
}

// --- Skeleton ----------------------------------------------------------------

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton h-4 w-full", className)} />;
}

// --- Spinner -----------------------------------------------------------------

export function Spinner({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-block h-4 w-4 animate-spin rounded-full border-2 border-white/20 border-t-accent",
        className,
      )}
    />
  );
}

// --- Empty state -------------------------------------------------------------

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-white/[0.08] px-6 py-14 text-center">
      {icon && <div className="text-ink-500">{icon}</div>}
      <div>
        <p className="text-sm font-medium text-ink-200">{title}</p>
        {description && <p className="mt-1 text-xs text-ink-500">{description}</p>}
      </div>
      {action}
    </div>
  );
}

// --- Status dot --------------------------------------------------------------

export function StatusDot({ state }: { state: "connected" | "disconnected" | "error" | "working" }) {
  const color =
    state === "connected"
      ? "bg-signal-ok"
      : state === "working"
        ? "bg-accent"
        : state === "error"
          ? "bg-signal-urgent"
          : "bg-ink-600";
  return (
    <span className="relative inline-flex h-2 w-2">
      {(state === "connected" || state === "working") && (
        <span
          className={cn("absolute inline-flex h-full w-full rounded-full animate-pulse-ring", color)}
        />
      )}
      <span className={cn("relative inline-flex h-2 w-2 rounded-full", color)} />
    </span>
  );
}

// --- Error banner ------------------------------------------------------------

export function ErrorBanner({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-xl border border-signal-warn/25 bg-signal-warn/[0.07] px-4 py-3 text-sm text-signal-warn">
      <span>{message}</span>
      {onRetry && (
        <button onClick={onRetry} className="btn-ghost !py-1 !text-xs">
          Retry
        </button>
      )}
    </div>
  );
}