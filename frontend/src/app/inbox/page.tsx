"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/stores/auth";
import { AppShell } from "@/components/shell/app-shell";
import { Card, CardBody, CardHeader, CardTitle, Skeleton, EmptyState, ErrorBanner } from "@/components/ui";
import { useAsync } from "@/lib/hooks";
import { useDebounced } from "@/lib/hooks";
import { api } from "@/lib/api";
import { relativeTime } from "@/lib/utils";
import type { EmailItem, MessageItem } from "@/types";

function LoadingPage() {
  return (
    <AppShell>
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        {Array.from({ length: 3 }).map((_, i) => (
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

function MailList({ title, items, detail }: { title: string; items: EmailItem[] | MessageItem[] | null; detail: string; loading: boolean; error: string | null; retry: () => void }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle />
      </CardHeader>
      <CardBody>
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-ink-100">{title}</h3>
          <span className="text-xs text-ink-500">{items ? `${items.length} items` : detail}</span>
        </div>
        {error && <ErrorBanner message={error} onRetry={retry} />}
        {(!items || items.length === 0) && !loading && (
          <EmptyState icon={<span className="text-ink-500">📭</span>} title="Nothing here" description={detail} />
        )}
        <div className="space-y-1">
          {loading && Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="rounded-lg bg-white/[0.02] px-3 py-2.5">
              <Skeleton className="h-3 w-3/4" />
              <Skeleton className="mt-1 h-3 w-1/2" />
            </div>
          ))}
          {items?.map((item) => (
            <div key={item.id} className="flex flex-col gap-0.5 rounded-lg bg-white/[0.02] px-3 py-2.5">
              <div className="flex items-center justify-between gap-2">
                <span className="truncate text-sm font-medium text-ink-100">
                  {(item as EmailItem).subject ?? (item as MessageItem).sender_name ?? "Unknown"}
                </span>
                {(item as EmailItem).received_at && (
                  <span className="shrink-0 text-[10px] text-ink-600">{relativeTime((item as EmailItem).received_at!)}</span>
                )}
              </div>
              <p className="truncate text-xs text-ink-500">{detail}</p>
            </div>
          ))}
        </div>
      </CardBody>
    </Card>
  );
}

export default function InboxPage() {
  const me = useAuth((s) => s.me);
  const ready = useAuth((s) => s.ready);
  const router = useRouter();
  const searchParams = useSearchParams();
  const [emailSearch, setEmailSearch] = useState("");
  const msgSearch = searchParams.get("q") ?? "";
  const debouncedEmailSearch = useDebounced(emailSearch, 300);

  useEffect(() => {
    if (ready && !me) router.push("/auth");
  }, [ready, me, router]);

  const { data: emails, loading: eLoading, error: eError, retry: eRetry } = useAsync(
    () => api.emails({ page_size: 20, search: debouncedEmailSearch || undefined }),
    [debouncedEmailSearch],
  );
  const { data: messages, loading: mLoading, error: mError, retry: mRetry } = useAsync(
    () => api.messages({ page_size: 20, search: msgSearch || undefined }),
    [msgSearch],
  );

  if (!ready) return <LoadingPage />;
  if (!me) return null;

  return (
    <AppShell>
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-ink-100">Inbox</h2>
          <input
            placeholder="Search emails…"
            value={emailSearch}
            onChange={(e) => setEmailSearch(e.target.value)}
            className="input max-w-xs !py-1.5 !text-xs"
          />
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <MailList title="Emails" items={emails?.items ?? null} detail="No unread emails" loading={eLoading} error={eError} retry={eRetry} />
          <MailList title="Teams messages" items={messages?.items ?? null} detail="No new messages" loading={mLoading} error={mError} retry={mRetry} />
        </div>
      </div>
    </AppShell>
  );
}
