import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

export function initials(name: string): string {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((n) => n[0]?.toUpperCase() ?? "")
    .join("");
}

export function greetingFor(date = new Date()): string {
  const h = date.getHours();
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}

export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  const diff = Date.now() - then;
  const mins = Math.round(diff / 60000);
  if (Math.abs(mins) < 1) return "just now";
  if (Math.abs(mins) < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (Math.abs(hours) < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (Math.abs(days) < 30) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}

export function timeOfDay(iso: string | null | undefined): string {
  if (!iso) return "";
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function dayLabel(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  const today = new Date();
  const isToday = d.toDateString() === today.toDateString();
  const tomorrow = new Date(today);
  tomorrow.setDate(today.getDate() + 1);
  const isTomorrow = d.toDateString() === tomorrow.toDateString();
  if (isToday) return "Today";
  if (isTomorrow) return "Tomorrow";
  return d.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" });
}

// Human tool labels for the agent activity feed (never raw tool ids).
export const TOOL_LABELS: Record<string, string> = {
  search_outlook_emails: "Searching Outlook",
  get_email: "Reading email",
  search_calendar: "Checking your calendar",
  get_calendar_event: "Reading calendar event",
  search_teams_messages: "Searching Teams",
  get_teams_conversation: "Reading Teams conversation",
  search_goodday_tasks: "Checking GoodDay",
  get_goodday_task: "Reading GoodDay task",
  create_goodday_task: "Create GoodDay task",
  update_goodday_task: "Update GoodDay task",
  create_calendar_event: "Create calendar event",
  draft_email: "Draft email",
  send_email: "Send email",
  draft_teams_message: "Draft Teams message",
  send_teams_message: "Send Teams message",
};

export function toolLabel(name: string): string {
  return TOOL_LABELS[name] ?? name.replace(/_/g, " ");
}

export function sourceAccent(source: string): string {
  switch (source) {
    case "outlook":
      return "text-accent-soft";
    case "teams":
      return "text-violet";
    case "goodday":
      return "text-teal";
    default:
      return "text-ink-300";
  }
}