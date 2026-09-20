import {
  Activity,
  CalendarDays,
  Inbox,
  LayoutDashboard,
  ListChecks,
  MessageSquare,
  Plug,
  Settings,
  Sparkles,
  Sun,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  hint?: string;
}

export const NAV_ITEMS: NavItem[] = [
  { href: "/overview", label: "Overview", icon: LayoutDashboard },
  { href: "/today", label: "Today", icon: Sun },
  { href: "/inbox", label: "Inbox", icon: Inbox },
  { href: "/calendar", label: "Calendar", icon: CalendarDays },
  { href: "/teams", label: "Teams", icon: MessageSquare },
  { href: "/tasks", label: "Tasks", icon: ListChecks },
  { href: "/agent", label: "AI Agent", icon: Sparkles, hint: "K" },
  { href: "/activity", label: "Activity", icon: Activity },
  { href: "/integrations", label: "Integrations", icon: Plug },
  { href: "/settings", label: "Settings", icon: Settings },
];