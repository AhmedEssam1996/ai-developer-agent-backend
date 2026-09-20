"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/shell/app-shell";
import { useAuth } from "@/stores/auth";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui";
import { Skeleton } from "@/components/ui";

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

function SettingRow({ label, description, children }: { label: string; description?: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-lg bg-white/[0.02] px-4 py-3">
      <div className="min-w-0">
        <p className="text-sm font-medium text-ink-100">{label}</p>
        {description && <p className="mt-0.5 text-xs text-ink-500">{description}</p>}
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  );
}

export default function SettingsPage() {
  const router = useRouter();
  const me = useAuth((s) => s.me);
  const ready = useAuth((s) => s.ready);
  const logout = useAuth((s) => s.logout);

  useEffect(() => {
    if (ready && !me) router.push("/auth");
  }, [ready, me, router]);

  if (!ready) return <LoadingPage />;
  if (!me) return null;

  return (
    <AppShell>
      <div className="space-y-4">
        <h2 className="text-lg font-semibold text-ink-100">Settings</h2>

        <Card>
          <CardHeader>
            <CardTitle>Profile</CardTitle>
          </CardHeader>
          <CardBody className="space-y-3">
            <SettingRow label="Profile" description="Your name and email">
              <span className="chip border-white/[0.08] bg-white/[0.03] text-ink-300">{me.user.email}</span>
            </SettingRow>
            <SettingRow label="Organization" description="Your workspace">
              <span className="chip border-white/[0.08] bg-white/[0.03] text-ink-300">{me.organization.name}</span>
            </SettingRow>
            <SettingRow label="Role" description="Your permission level">
              <span className="chip border-white/[0.08] bg-white/[0.03] text-ink-300">{me.role}</span>
            </SettingRow>
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Preferences</CardTitle>
          </CardHeader>
          <CardBody className="space-y-3">
            <SettingRow label="Notifications" description="Receive agent alerts">
              <span className="chip border-signal-ok/30 bg-signal-ok/10 text-signal-ok">Enabled</span>
            </SettingRow>
            <SettingRow label="Dark mode" description="Theme preference">
              <span className="chip border-white/[0.08] bg-white/[0.03] text-ink-300">Dark</span>
            </SettingRow>
            <SettingRow label="Language" description="Interface language">
              <span className="chip border-white/[0.08] bg-white/[0.03] text-ink-300">English</span>
            </SettingRow>
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Danger zone</CardTitle>
          </CardHeader>
          <CardBody>
            <p className="text-sm text-ink-500">Danger zone</p>
            <div className="mt-3 flex gap-2">
              <button onClick={logout} className="btn-danger">Sign out</button>
            </div>
          </CardBody>
        </Card>
      </div>
    </AppShell>
  );
}
