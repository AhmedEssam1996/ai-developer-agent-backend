"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/stores/auth";
import { AppShell } from "@/components/shell/app-shell";
import { Card, CardBody, CardHeader, CardTitle, Skeleton } from "@/components/ui";
import { useAsync } from "@/lib/hooks";
import { api } from "@/lib/api";
import { greetingFor } from "@/lib/utils";

function LoadingPage() {
  return (
    <AppShell>
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i}>
              <CardBody>
                <Skeleton className="h-4 w-20" />
                <Skeleton className="mt-2 h-8 w-12" />
              </CardBody>
            </Card>
          ))}
        </div>
        <Card>
          <CardBody>
            <Skeleton className="h-4 w-32" />
            <div className="mt-3 space-y-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} />
              ))}
            </div>
          </CardBody>
        </Card>
      </div>
    </AppShell>
  );
}

function DashboardContent() {
  const router = useRouter();
  const { data, loading, error, retry } = useAsync(() => api.dashboard());
  const { data: tasksData, loading: tasksLoading } = useAsync(() => api.tasks({ page_size: 5 }));

  if (loading || tasksLoading) return <LoadingPage />;
  if (error) {
    return (
      <AppShell>
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-ink-100">Welcome back</h2>
          <Card>
            <CardBody>
              <p className="text-sm text-signal-warn">{error}</p>
              <button onClick={retry} className="btn-ghost mt-3 text-xs">Retry</button>
            </CardBody>
          </Card>
        </div>
      </AppShell>
    );
  }
  if (!data) return null;

  const d = data;

  return (
    <AppShell>
      <div className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold text-ink-100">
            {greetingFor()}, {d.greeting.includes(",") ? d.greeting.split(",")[1].trim() : "there"}
          </h2>
          <p className="text-sm text-ink-500">{new Date(d.generated_at).toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" })}</p>
        </div>

        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <Card>
            <CardHeader />
            <CardBody>
              <p className="section-title">Urgent</p>
              <p className="mt-1 text-3xl font-semibold text-signal-urgent">{d.counts.requiring_action}</p>
            </CardBody>
          </Card>
          <Card>
            <CardHeader />
            <CardBody>
              <p className="section-title">Overdue</p>
              <p className="mt-1 text-3xl font-semibold text-signal-warn">{d.counts.overdue_tasks}</p>
            </CardBody>
          </Card>
          <Card>
            <CardHeader />
            <CardBody>
              <p className="section-title">Important emails</p>
              <p className="mt-1 text-3xl font-semibold text-accent">{d.counts.important_emails}</p>
            </CardBody>
          </Card>
          <Card>
            <CardHeader />
            <CardBody>
              <p className="section-title">Meetings today</p>
              <p className="mt-1 text-3xl font-semibold text-teal">{d.counts.upcoming_meetings}</p>
            </CardBody>
          </Card>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle />
            </CardHeader>
            <CardBody className="space-y-3">
              {d.urgent.length === 0 ? (
                <p className="text-sm text-ink-500">Nothing urgent right now.</p>
              ) : (
                d.urgent.map((item) => (
                  <div key={item.id} className="flex items-start gap-3 rounded-lg bg-white/[0.02] px-3 py-2.5">
                    <span className={`mt-1 h-2 w-2 shrink-0 rounded-full ${item.priority === "urgent" ? "bg-signal-urgent" : item.priority === "high" ? "bg-signal-warn" : "bg-accent"}`} />
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-ink-100">{item.title}</p>
                      <p className="text-xs text-ink-500">{item.summary}</p>
                    </div>
                  </div>
                ))
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle />
            </CardHeader>
            <CardBody className="space-y-3">
              {d.today_tasks.length === 0 ? (
                <p className="text-sm text-ink-500">No tasks for today.</p>
              ) : (
                d.today_tasks.map((task) => (
                  <div key={task.id} className="flex items-center justify-between gap-3 rounded-lg bg-white/[0.02] px-3 py-2.5">
                    <span className="truncate text-sm text-ink-200">{task.title}</span>
                    <span className={`text-xs ${task.is_overdue ? "text-signal-urgent" : task.status === "done" ? "text-signal-ok" : "text-ink-400"}`}>
                      {task.status}
                    </span>
                  </div>
                ))
              )}
            </CardBody>
          </Card>
        </div>

        {d.integrations_warning.length > 0 && (
          <Card>
            <CardBody>
              <p className="text-sm text-signal-warn">{d.integrations_warning.join("; ")}</p>
            </CardBody>
          </Card>
        )}
      </div>
    </AppShell>
  );
}

export default function OverviewPage() {
  const me = useAuth((s) => s.me);
  const ready = useAuth((s) => s.ready);
  const router = useRouter();

  useEffect(() => {
    if (ready && !me) router.push("/auth");
  }, [ready, me, router]);

  if (!ready) return <LoadingPage />;
  if (!me) return null;

  return <DashboardContent />;
}
