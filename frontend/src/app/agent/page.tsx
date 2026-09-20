"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/stores/auth";
import { useAgent } from "@/stores/agent";
import { AppShell } from "@/components/shell/app-shell";
import { Card, CardBody, CardHeader, CardTitle, Skeleton, EmptyState, Spinner, ErrorBanner } from "@/components/ui";
import { useAsync } from "@/lib/hooks";
import { api } from "@/lib/api";
import { streamAgentRun } from "@/lib/sse";
import { toolLabel } from "@/lib/utils";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { AgentStreamEvent } from "@/types";

function LoadingPage() {
  return (
    <AppShell>
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        {Array.from({ length: 3 }).map((_, i) => (
          <Card key={i}>
            <CardBody>
              <Skeleton className="h-4 w-full" />
            </CardBody>
          </Card>
        ))}
      </div>
    </AppShell>
  );
}

export default function AgentPage() {
  const me = useAuth((s) => s.me);
  const ready = useAuth((s) => s.ready);
  const router = useRouter();

  const { running, answer, steps, error, tokens, latencyMs, start, apply, abort } = useAgent();
  const [input, setInput] = useState("");
  const [sendError, setSendError] = useState<string | null>(null);
  const abortRef = useRef(false);

  const { data: runs, loading: runsLoading, error: runsError, retry: runsRetry } = useAsync(() => api.runs(25));
  const { data: pendingActions, loading: actionsLoading, error: actionsError, retry: actionsRetry } = useAsync(() => api.pendingActions());

  useEffect(() => {
    if (ready && !me) router.push("/auth");
  }, [ready, me, router]);

  const handleSend = useCallback(async () => {
    if (!input.trim() || running) return;
    setSendError(null);
    abortRef.current = false;
    start();
    await streamAgentRun(input, {
      onEvent: (event: AgentStreamEvent) => apply(event),
      onError: (err) => setSendError(err.message),
      onClose: () => {
        void api.runs(25).then((data) => {
          void data;
        });
      },
      signal: undefined,
    });
    setInput("");
  }, [input, running, start, apply]);

  const handleAbort = useCallback(() => {
    abortRef.current = true;
    abort();
  }, [abort]);

  if (!ready) return <LoadingPage />;
  if (!me) return null;

  return (
    <AppShell>
      <div className="flex flex-col gap-4" style={{ height: "calc(100vh - 8rem)" }}>
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-ink-100">AI Agent</h2>
          {running && (
            <button onClick={handleAbort} className="btn-danger !py-1 !px-2 !text-xs">
              Stop
            </button>
          )}
        </div>

        {sendError && (
          <ErrorBanner message={sendError} onRetry={() => { setSendError(null); }} />
        )}

        <div className="flex flex-1 flex-col gap-4 overflow-hidden">
          <Card className="flex-1 overflow-auto">
            <CardBody className="space-y-3">
              {!steps.length && !answer && !running && (
                <EmptyState
                  icon={<span className="text-ink-500">🤖</span>}
                  title="Ask the agent anything"
                  description="Try: \"What should I focus on today?\" or \"Prepare me for my next meeting.\""
                />
              )}

              {steps.map((step) => (
                <div key={step.id} className={`flex items-start gap-2.5 rounded-lg px-3 py-2 ${step.state === "error" ? "bg-signal-urgent/5" : "bg-white/[0.02]"}`}>
                  <span className={`mt-1 h-2 w-2 shrink-0 rounded-full ${step.state === "running" ? "bg-accent animate-pulse" : step.state === "error" ? "bg-signal-urgent" : "bg-signal-ok"}`} />
                  <div className="min-w-0">
                    <p className="text-sm text-ink-100">{step.label}</p>
                    {step.detail && <p className="text-xs text-ink-500">{step.detail}</p>}
                    {step.phase === "approval" && step.actionId && (
                      <div className="mt-2 rounded-lg border border-white/[0.06] bg-base-950/50 p-3">
                        <p className="text-xs text-ink-400">Action: {step.tool}</p>
                        {step.preview && <p className="mt-1 text-xs text-ink-300">{step.preview}</p>}
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {answer && (
                <ReactMarkdown remarkPlugins={[remarkGfm]} className="prose-agent">
                  {answer}
                </ReactMarkdown>
              )}

              {running && <Spinner />}
            </CardBody>
          </Card>

          <div className="flex gap-2">
            <input
              placeholder="Ask the agent…"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
              disabled={running}
              className="input flex-1"
            />
            <button onClick={handleSend} disabled={running || !input.trim()} className="btn-primary">
              {running ? <Spinner /> : "Send"}
            </button>
          </div>

          <div className="grid gap-3 md:grid-cols-3">
            <Card>
              <CardBody>
                <p className="section-title">Runs</p>
                <p className="mt-1 text-xl font-semibold text-ink-100">{runs?.length ?? 0}</p>
              </CardBody>
            </Card>
            <Card>
              <CardBody>
                <p className="section-title">Tokens</p>
                <p className="mt-1 text-xl font-semibold text-accent">{tokens}</p>
              </CardBody>
            </Card>
            <Card>
              <CardBody>
                <p className="section-title">Latency</p>
                <p className="mt-1 text-xl font-semibold text-teal">{latencyMs ? `${latencyMs}ms` : "—"}</p>
              </CardBody>
            </Card>
          </div>

          {(runsError || actionsError) && (
            <ErrorBanner message={runsError ?? actionsError ?? ""} onRetry={() => { runsRetry(); actionsRetry(); }} />
          )}
        </div>
      </div>
    </AppShell>
  );
}
