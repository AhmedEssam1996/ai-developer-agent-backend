"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/stores/auth";
import { AppShell } from "@/components/shell/app-shell";
import { Card, CardBody, CardHeader, CardTitle, Skeleton, EmptyState } from "@/components/ui";
import { useAsync } from "@/lib/hooks";
import { api } from "@/lib/api";
import { timeOfDay, dayLabel } from "@/lib/utils";
import type { CalendarEvent } from "@/types";

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

export default function CalendarPage() {
  const me = useAuth((s) => s.me);
  const ready = useAuth((s) => s.ready);
  const router = useRouter();

  useEffect(() => {
    if (ready && !me) router.push("/auth");
  }, [ready, me, router]);

  const { data, loading, error, retry } = useAsync(() => api.calendar(30));

  if (!ready) return <LoadingPage />;
  if (!me) return null;

  if (loading) return <LoadingPage />;

  return (
    <AppShell>
      <div className="space-y-4">
        <h2 className="text-lg font-semibold text-ink-100">Calendar</h2>

        {error && (
          <Card>
            <CardBody>
              <p className="text-sm text-signal-warn">{error}</p>
              <button onClick={retry} className="btn-ghost mt-3 text-xs">Retry</button>
            </CardBody>
          </Card>
        )}

        {!error && (!data || data.length === 0) && (
          <Card>
            <CardBody>
              <EmptyState icon={<span className="text-ink-500">📅</span>} title="No events" description="Your calendar is clear." />
            </CardBody>
          </Card>
        )}

        {!error && data && data.length > 0 && (
          <div className="space-y-2">
            {data.map((event: CalendarEvent) => (
              <Card key={event.id}>
                <CardBody className="flex items-center justify-between gap-4 py-4">
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-ink-100">{event.subject}</p>
                    <p className="mt-0.5 text-xs text-ink-500">
                      {dayLabel(event.starts_at)} · {timeOfDay(event.starts_at)} — {timeOfDay(event.ends_at)}
                      {event.location ? ` · ${event.location}` : ""}
                    </p>
                    <p className="mt-0.5 line-clamp-1 text-xs text-ink-400">{event.body_preview}</p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    {event.is_online_meeting && event.join_url && (
                      <a href={event.join_url} className="btn-primary !py-1 !px-2 !text-xs">Join</a>
                    )}
                    {event.attendees.length > 0 && (
                      <span className="chip border-white/[0.06] bg-white/[0.03] text-ink-400">{event.attendees.length} attending</span>
                    )}
                  </div>
                </CardBody>
              </Card>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
