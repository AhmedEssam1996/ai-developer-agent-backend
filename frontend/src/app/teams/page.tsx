"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/stores/auth";
import { AppShell } from "@/components/shell/app-shell";
import { Card, CardBody, CardHeader, CardTitle, Skeleton, EmptyState, ErrorBanner } from "@/components/ui";
import { useAsync } from "@/lib/hooks";
import { useDebounced } from "@/lib/hooks";
import { api } from "@/lib/api";
import { relativeTime } from "@/lib/utils";
import type { MessageItem, TaskItem } from "@/types";

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

export default function TeamsPage() {
  const me = useAuth((s) => s.me);
  const ready = useAuth((s) => s.ready);
  const router = useRouter();
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebounced(search, 300);

  useEffect(() => {
    if (ready && !me) router.push("/auth");
  }, [ready, me, router]);

  const { data: messagesData, loading: mLoading, error: mError, retry: mRetry } = useAsync(
    () => api.messages({ page_size: 30, search: debouncedSearch || undefined }),
    [debouncedSearch],
  );
  const { data: tasksData, loading: tLoading, error: tError, retry: tRetry } = useAsync(() => api.tasks({ page_size: 10 }));

  if (!ready) return <LoadingPage />;
  if (!me) return null;

  return (
    <AppShell>
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-ink-100">Teams</h2>
          <input
            placeholder="Search messages…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="input max-w-xs !py-1.5 !text-xs"
          />
        </div>

        {(mError || tError) && (
          <Card>
            <CardBody>
              <ErrorBanner message={mError ?? tError ?? ""} onRetry={() => { mRetry(); tRetry(); }} />
            </CardBody>
          </Card>
        )}

        <Card>
          <CardHeader>
            <CardTitle />
          </CardHeader>
          <CardBody className="space-y-2">
            {mLoading && Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="rounded-lg bg-white/[0.02] px-3 py-2.5">
                <Skeleton className="h-3 w-3/4" />
                <Skeleton className="mt-1 h-3 w-1/2" />
              </div>
            ))}
            {!mLoading && (!messagesData || messagesData.items.length === 0) && (
              <EmptyState icon={<span className="text-ink-500">💬</span>} title="No messages" description="No Teams messages found." />
            )}
            {messagesData?.items.map((msg: MessageItem) => (
              <div key={msg.id} className="flex flex-col gap-0.5 rounded-lg bg-white/[0.02] px-3 py-2.5">
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate text-sm font-medium text-ink-100">{msg.conversation_name}</span>
                  {msg.sent_at && (
                    <span className="shrink-0 text-[10px] text-ink-600">{relativeTime(msg.sent_at)}</span>
                  )}
                </div>
                <p className="truncate text-xs text-ink-500">{msg.sender_name}: {msg.body}</p>
              </div>
            ))}
          </CardBody>
        </Card>

        {tasksData && tasksData.items.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle />
            </CardHeader>
            <CardBody className="space-y-2">
              {tasksData.items.slice(0, 5).map((task: TaskItem) => (
                <div key={task.id} className="flex items-center justify-between gap-3 rounded-lg bg-white/[0.02] px-3 py-2.5">
                  <span className={`truncate text-sm ${task.is_overdue ? "text-signal-urgent" : "text-ink-200"}`}>{task.title}</span>
                  <span className={`shrink-0 text-xs ${task.status === "done" ? "text-signal-ok" : task.is_overdue ? "text-signal-urgent" : "text-ink-400"}`}>{task.status}</span>
                </div>
              ))}
            </CardBody>
          </Card>
        )}
      </div>
    </AppShell>
  );
}
