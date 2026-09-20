"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/stores/auth";
import { AppShell } from "@/components/shell/app-shell";
import {
  Badge,
  Card,
  CardBody,
  CardHeader,
  CardTitle,
  EmptyState,
  ErrorBanner,
  Skeleton,
} from "@/components/ui";
import { useAsync } from "@/lib/hooks";
import { api } from "@/lib/api";
import { relativeTime, toolLabel } from "@/lib/utils";
import type { ActivityEvent, AgentAction } from "@/types";

function LoadingPage() {
  return (
    <AppShell>
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        {Array.from({ length: 4 }).map((_, i) => (
          <Card key={i}>
            <CardBody>
              <Skeleton className="h-4 w-full" />
              <Skeleton className="mt-2 h-4 w-2/3" />
            </CardBody>
          </Card>
        ))}
      </div>
    </AppShell>
  );
}

export default function ActivityPage() {
  const me = useAuth((s) => s.me);
  const ready = useAuth((s) => s.ready);
  const router = useRouter();

  useEffect(() => {
    if (ready && !me) router.push("/auth");
  }, [ready, me, router]);

  const { data, loading, error, retry } = useAsync(() => api.activity(100));
  const { data: pendingActions, loading: paLoading, error: paError, retry: paRetry } = useAsync(() => api.pendingActions());

  if (!ready) return <LoadingPage />;
  if (!me) return null;

  return (
    <AppShell>
      <div className="space-y-4">
        <h2 className="text-lg font-semibold text-ink-100">Activity</h2>

        {(error || paError) && (
          <ErrorBanner message={error ?? paError ?? ""} onRetry={() => { retry(); paRetry(); }} />
        )}

        {pendingActions && pendingActions.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle />
            </CardHeader>
            <CardBody className="space-y-3">
              {pendingActions.map((action: AgentAction) => (
                <div key={action.id} className="rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2.5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium text-ink-100">{toolLabel(action.tool_name)}</span>
                    <Badge tone="warn">Pending</Badge>
                  </div>
                  <p className="mt-1 text-xs text-ink-500">                    {action.preview || (action.arguments && Object.keys(action.arguments).length
                      ? JSON.stringify(action.arguments).slice(0, 120)
                      : "Awaiting approval")}</p>
                </div>
              ))}
            </CardBody>
          </Card>
        )}

        <Card>
          <CardHeader>
            <CardTitle />
          </CardHeader>
          <CardBody className="space-y-2">
            {!data || data.length === 0 ? (
              <EmptyState icon={<span className="text-ink-500">📡</span>} title="No recent activity" description="Your agent has been quiet." />
            ) : (
              data.map((event: ActivityEvent) => (
                <div key={event.id} className="flex items-start gap-3 rounded-lg bg-white/[0.02] px-3 py-2.5">
                  <Badge
                    tone={
                      event.level === "error" ? "urgent" : event.level === "warn" ? "warn" : "neutral"
                    }
                  >
                    {event.level}
                  </Badge>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-ink-100">{event.title}</p>
                    <p className="text-xs text-ink-500">{event.detail}</p>
                    <p className="mt-0.5 text-[10px] text-ink-600">{relativeTime(event.created_at)}</p>
                  </div>
                </div>
              ))
            )}
          </CardBody>
        </Card>
      </div>
    </AppShell>
  );
}
