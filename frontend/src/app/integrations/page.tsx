"use client";

import { useEffect, useState } from "react";
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
  StatusDot,
} from "@/components/ui";
import { useAsync } from "@/lib/hooks";
import { api } from "@/lib/api";
import { type IntegrationOverview } from "@/types";

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

function IntegrationCard({ integration, onConnect, onDisconnect, connecting }: { integration: IntegrationOverview; onConnect: () => void; onDisconnect: () => void; connecting: boolean }) {
  return (
    <Card>
      <CardBody>
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <StatusDot state={integration.connected ? "connected" : "disconnected"} />
              <p className="text-sm font-semibold text-ink-100">{integration.display_name}</p>
            </div>
            <p className="mt-1 text-xs text-ink-500">{integration.description}</p>
            {integration.account_label && (
              <p className="mt-1 text-[10px] text-ink-600">Account: {integration.account_label}</p>
            )}
            {integration.is_mock && (
              <Badge tone="violet" className="mt-1">Development data</Badge>
            )}
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {integration.connected ? (
              <button onClick={onDisconnect} disabled={connecting} className="btn-danger !py-1 !px-2 !text-xs">
                Disconnect
              </button>
            ) : (
              <button onClick={onConnect} disabled={connecting} className="btn-primary !py-1 !px-2 !text-xs">
                {connecting ? "Connecting…" : "Connect"}
              </button>
            )}
          </div>
        </div>
      </CardBody>
    </Card>
  );
}

export default function IntegrationsPage() {
  const me = useAuth((s) => s.me);
  const ready = useAuth((s) => s.ready);
  const router = useRouter();
  const [connecting, setConnecting] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);

  useEffect(() => {
    if (ready && !me) router.push("/auth");
  }, [ready, me, router]);

  const { data, error, retry } = useAsync(() => api.integrations());
  const { data: syncStates, error: syncError, retry: syncRetry } = useAsync(() => api.syncStates());
  const reloadAll = () => {
    retry();
    syncRetry();
  };

  if (!ready) return <LoadingPage />;
  if (!me) return null;

  async function handleConnect(provider: string) {
    setConnecting(provider);
    try {
      const result = await api.connect(provider);
      if (result.authorize_url.startsWith("mock://")) {
        reloadAll();
        return;
      }
      window.location.href = result.authorize_url;
    } finally {
      setConnecting(null);
    }
  }

  async function handleDisconnect(provider: string) {
    setConnecting(provider);
    try {
      await api.disconnect(provider);
    } finally {
      reloadAll();
      setConnecting(null);
    }
  }

  async function handleSync() {
    setSyncing(true);
    try {
      await api.sync(true);
    } finally {
      reloadAll();
      setSyncing(false);
    }
  }

  return (
    <AppShell>
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-ink-100">Integrations</h2>
          <button onClick={handleSync} disabled={syncing} className="btn-ghost !py-1 !px-2 !text-xs">
            {syncing ? "Syncing…" : "Sync all"}
          </button>
        </div>

        {(error || syncError) && (
          <ErrorBanner message={error ?? syncError ?? ""} onRetry={() => { retry(); syncRetry(); }} />
        )}

        {!error && (!data || data.length === 0) && (
          <EmptyState icon={<span className="text-ink-500">🔌</span>} title="No integrations" description="Connect your tools to get started." />
        )}

        {!error && data && data.length > 0 && (
          <div className="grid gap-4">
            {data.map((integration: IntegrationOverview) => (
              <IntegrationCard
                key={integration.provider}
                integration={integration}
                onConnect={() => handleConnect(integration.provider)}
                onDisconnect={() => handleDisconnect(integration.provider)}
                connecting={connecting === integration.provider}
              />
            ))}
          </div>
        )}

        {syncStates && syncStates.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Sync history</CardTitle>
            </CardHeader>
            <CardBody className="space-y-2">
              {syncStates.map((s) => (
                <div key={`${s.provider}-${s.resource}`} className="flex items-center justify-between rounded-lg bg-white/[0.02] px-3 py-2">
                  <span className="text-xs text-ink-300">{s.provider} · {s.resource}</span>
                  <span className="text-[10px] text-ink-500">
                    {s.last_error ? `Error: ${s.last_error}` : s.last_synced_at ? `Synced ${new Date(s.last_synced_at).toLocaleString()}` : "Never synced"}
                  </span>
                </div>
              ))}
            </CardBody>
          </Card>
        )}
      </div>
    </AppShell>
  );
}
