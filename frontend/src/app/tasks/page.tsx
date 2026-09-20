"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/stores/auth";
import { AppShell } from "@/components/shell/app-shell";
import { Card, CardBody, CardHeader, CardTitle, Skeleton, EmptyState, ErrorBanner } from "@/components/ui";
import { useAsync } from "@/lib/hooks";
import { useDebounced } from "@/lib/hooks";
import { api } from "@/lib/api";
import { relativeTime, dayLabel } from "@/lib/utils";
import type { TaskItem } from "@/types";

function LoadingPage() {
  return (
    <AppShell>
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        {Array.from({ length: 3 }).map((_, i) => (
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

export default function TasksPage() {
  const me = useAuth((s) => s.me);
  const ready = useAuth((s) => s.ready);
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const debouncedSearch = useDebounced(search, 300);

  useEffect(() => {
    if (ready && !me) router.push("/auth");
  }, [ready, me, router]);

  const query: { page?: number; page_size?: number; status?: string; search?: string } = { page_size: 50 };
  if (statusFilter !== "all") query.status = statusFilter;
  if (debouncedSearch) query.search = debouncedSearch;

  const { data, loading, error, retry } = useAsync(() => api.tasks(query), [debouncedSearch, statusFilter]);

  if (!ready) return <LoadingPage />;
  if (!me) return null;

  return (
    <AppShell>
      <div className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-lg font-semibold text-ink-100">Tasks</h2>
          <div className="flex items-center gap-2">
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="input max-w-[140px] !py-1.5 !text-xs"
            >
              <option value="all">All status</option>
              <option value="todo">To do</option>
              <option value="in_progress">In progress</option>
              <option value="done">Done</option>
            </select>
            <input
              placeholder="Search…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="input max-w-xs !py-1.5 !text-xs"
            />
          </div>
        </div>

        {error && (
          <ErrorBanner message={error} onRetry={retry} />
        )}

        {!error && (!data || data.items.length === 0) && (
          <Card>
            <CardBody>
              <EmptyState icon={<span className="text-ink-500">📋</span>} title="No tasks" description={search ? "No tasks match your search." : "Create a task to get started."} />
            </CardBody>
          </Card>
        )}

        {!error && data && data.items.length > 0 && (
          <div className="grid gap-3">
            {data.items.map((task: TaskItem) => (
              <Card key={task.id}>
                <CardBody className="flex items-center justify-between gap-4 py-3.5">
                  <div className="min-w-0 flex-1">
                    <p className={`text-sm font-medium ${task.is_overdue ? "text-signal-urgent" : "text-ink-100"}`}>{task.title}</p>
                    {task.description && (
                      <p className="mt-0.5 line-clamp-1 text-xs text-ink-500">{task.description}</p>
                    )}
                    <p className="mt-1 flex items-center gap-3 text-[10px] text-ink-600">
                      <span>{task.source}</span>
                      {task.assignee_name && <span>· {task.assignee_name}</span>}
                      {task.due_at && <span>· due {dayLabel(task.due_at)}</span>}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <span className={`chip ${task.status === "done" ? "border-signal-ok/30 bg-signal-ok/10 text-signal-ok" : task.is_overdue ? "border-signal-urgent/30 bg-signal-urgent/10 text-signal-urgent" : "border-white/[0.08] bg-white/[0.03] text-ink-300"}`}>
                      {task.status}
                    </span>
                    <div className="w-16">
                      <div className="h-1.5 rounded-full bg-white/[0.06]">
                        <div
                          className="h-1.5 rounded-full bg-accent"
                          style={{ width: `${task.progress}%` }}
                        />
                      </div>
                    </div>
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
