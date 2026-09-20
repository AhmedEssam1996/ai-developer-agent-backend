"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/stores/auth";
import { AppShell } from "@/components/shell/app-shell";
import { Card, CardBody, CardHeader, CardTitle, Skeleton, EmptyState } from "@/components/ui";
import { useAsync } from "@/lib/hooks";
import { api } from "@/lib/api";
import { relativeTime, dayLabel } from "@/lib/utils";
import type { TimelineItem, TaskItem, CalendarEvent } from "@/types";

function LoadingPage() {
  return (
    <AppShell>
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        {Array.from({ length: 4 }).map((_, i) => (
          <Card key={i}>
            <CardBody>
              <Skeleton className="h-4 w-full" />
              <Skeleton className="mt-2 h-4 w-3/4" />
            </CardBody>
          </Card>
        ))}
      </div>
    </AppShell>
  );
}

export default function TodayPage() {
  const me = useAuth((s) => s.me);
  const ready = useAuth((s) => s.ready);
  const router = useRouter();

  useEffect(() => {
    if (ready && !me) router.push("/auth");
  }, [ready, me, router]);

  if (!ready) return <LoadingPage />;
  if (!me) return null;

  const { data: timeline, loading: tlLoading, error: tlError, retry: tlRetry } = useAsync(() => api.timeline({ days: 1 }));
  const { data: tasks, loading: tkLoading, error: tkError, retry: tkRetry } = useAsync(() => api.tasks({ page_size: 20 }));
  const { data: calendar, loading: calLoading, error: calError, retry: calRetry } = useAsync(() => api.calendar(7));

  if (tlLoading || tkLoading || calLoading) return <LoadingPage />;

  return (
    <AppShell>
      <div className="space-y-4">
        <h2 className="text-lg font-semibold text-ink-100">Today</h2>

        {(tlError || tkError || calError) && (
          <Card>
            <CardBody>
              <p className="text-sm text-signal-warn">{tlError ?? tkError ?? calError}</p>
              <button onClick={() => { tlRetry(); tkRetry(); calRetry(); }} className="btn-ghost mt-3 text-xs">Retry all</button>
            </CardBody>
          </Card>
        )}

        <div className="grid gap-4 md:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle />
            </CardHeader>
            <CardBody className="space-y-2">
              {!timeline || timeline.items.length === 0 ? (
                <EmptyState icon={<span className="text-ink-500">📋</span>} title="No activity today" description="Nothing scheduled for today." />
              ) : (
                timeline?.items.map((item: TimelineItem) => (
                  <div key={item.id} className="flex items-start gap-3 rounded-lg bg-white/[0.02] px-3 py-2.5">
                    <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-accent" />
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-ink-100">{item.title}</p>
                      <p className="text-xs text-ink-500">{item.summary}</p>
                      {item.timestamp && <p className="mt-0.5 text-[10px] text-ink-600">{relativeTime(item.timestamp)}</p>}
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
            <CardBody className="space-y-2">
              {!tasks || tasks.items.length === 0 ? (
                <EmptyState icon={<span className="text-ink-500">✅</span>} title="No tasks yet" description="Keep going!" />
              ) : (
                tasks?.items.map((task: TaskItem) => (
                  <div key={task.id} className="flex items-center justify-between gap-3 rounded-lg bg-white/[0.02] px-3 py-2.5">
                    <div className="min-w-0">
                      <p className={`truncate text-sm ${task.is_overdue ? "text-signal-urgent" : "text-ink-200"}`}>{task.title}</p>
                      <p className="text-xs text-ink-500">{task.description}</p>
                    </div>
                    <span className={`shrink-0 text-xs ${task.status === "done" ? "text-signal-ok" : task.is_overdue ? "text-signal-urgent" : "text-ink-400"}`}>
                      {task.status}
                    </span>
                  </div>
                ))
              )}
            </CardBody>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <CardTitle />
          </CardHeader>
          <CardBody className="space-y-2">
            {!calendar || calendar.length === 0 ? (
              <EmptyState icon={<span className="text-ink-500">📅</span>} title="No upcoming events" description="Schedule a meeting to see it here." />
            ) : (
              calendar.map((event: CalendarEvent) => (
                <div key={event.id} className="flex items-center justify-between gap-3 rounded-lg bg-white/[0.02] px-3 py-2.5">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-ink-100">{event.subject}</p>
                    <p className="text-xs text-ink-500">{dayLabel(event.starts_at)} {event.starts_at ? new Date(event.starts_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : ""} — {event.location}</p>
                  </div>
                  {event.join_url && (
                    <a href={event.join_url} className="shrink-0 text-xs text-accent-soft underline">Join</a>
                  )}
                </div>
              ))
            )}
          </CardBody>
        </Card>
      </div>
    </AppShell>
  );
}
