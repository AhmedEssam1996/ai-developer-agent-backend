// Types for normalized work data.

export type Priority = "low" | "normal" | "high" | "urgent";

export interface User {
  id: string;
  email: string;
  full_name: string;
  display_name: string;
  timezone: string;
  is_active: boolean;
  created_at: string;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
}

export interface MeResponse {
  user: User;
  organization: Organization;
  role: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface EmailItem {
  id: string;
  source: string;
  subject: string;
  body_preview: string;
  sender_email: string;
  sender_name: string;
  to_recipients: string[];
  received_at: string | null;
  is_read: boolean;
  has_attachments: boolean;
  priority: Priority;
  needs_reply: boolean;
  is_important: boolean;
  external_id?: string;
  project_id?: string | null;
  web_link?: string | null;
}

export interface CalendarEvent {
  id: string;
  source: string;
  subject: string;
  body_preview: string;
  starts_at: string;
  ends_at: string;
  is_all_day: boolean;
  location: string;
  organizer_email: string;
  attendees: { email?: string; name?: string }[];
  is_online_meeting: boolean;
  join_url?: string | null;
  response_status: string;
}

export interface MessageItem {
  id: string;
  source: string;
  conversation_id: string;
  conversation_name: string;
  sender_email: string;
  sender_name: string;
  body: string;
  direction: string;
  sent_at: string | null;
  is_mention: boolean;
}

export interface TaskItem {
  id: string;
  source: string;
  external_id: string;
  title: string;
  description: string;
  status: string;
  priority: Priority;
  due_at: string | null;
  assignee_name?: string | null;
  project_id?: string | null;
  progress: number;
  is_overdue: boolean;
  web_link?: string | null;
}

export interface Commitment {
  id: string;
  direction: "i_owe" | "owed_to_me";
  status: string;
  text: string;
  counterparty_email?: string | null;
  counterparty_name?: string | null;
  due_at: string | null;
  confidence: number;
  source: string;
  acknowledged: boolean;
}

export interface TimelineItem {
  id: string;
  source: string;
  type: string;
  timestamp: string | null;
  title: string;
  summary: string;
  people: string[];
  project?: string | null;
  priority: Priority;
  metadata: Record<string, unknown>;
}

export interface AttentionCounts {
  requiring_action: number;
  overdue_tasks: number;
  important_emails: number;
  upcoming_meetings: number;
}

export interface Dashboard {
  greeting: string;
  generated_at: string;
  counts: AttentionCounts;
  urgent: TimelineItem[];
  upcoming_events: CalendarEvent[];
  waiting_for: Commitment[];
  you_owe: Commitment[];
  important_emails: EmailItem[];
  overdue_tasks: TaskItem[];
  today_tasks: TaskItem[];
  integrations_warning: string[];
  is_development_data: boolean;
}

export interface IntegrationOverview {
  provider: string;
  display_name: string;
  description: string;
  connected: boolean;
  status: string;
  configured: boolean;
  account_label?: string | null;
  last_synced_at?: string | null;
  last_error?: string | null;
  is_mock: boolean;
  connect_url?: string | null;
}

export interface SyncState {
  provider: string;
  resource: string;
  status: string;
  last_synced_at: string | null;
  last_error: string | null;
  items_synced: number;
  consecutive_failures: number;
}

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}