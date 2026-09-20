// Typed API client. All calls go to the backend; provider keys never reach the browser.

import type {
  ActivityEvent,
  AgentAction,
  AgentRun,
  AgentRunDetail,
  CalendarEvent,
  Commitment,
  Dashboard,
  EmailItem,
  IntegrationOverview,
  MeResponse,
  MessageItem,
  Paginated,
  SyncState,
  TaskItem,
  TimelineItem,
  TokenPair,
  UsageStats,
} from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

const ACCESS_KEY = "mywork.access_token";
const REFRESH_KEY = "mywork.refresh_token";

export class ApiError extends Error {
  code: string;
  status: number;
  retryable: boolean;

  constructor(message: string, code = "error", status = 500, retryable = false) {
    super(message);
    this.code = code;
    this.status = status;
    this.retryable = retryable;
  }
}

export const tokenStore = {
  get access(): string | null {
    if (typeof window === "undefined") return null;
    return window.localStorage.getItem(ACCESS_KEY);
  },
  get refresh(): string | null {
    if (typeof window === "undefined") return null;
    return window.localStorage.getItem(REFRESH_KEY);
  },
  set(pair: TokenPair) {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(ACCESS_KEY, pair.access_token);
    window.localStorage.setItem(REFRESH_KEY, pair.refresh_token);
  },
  clear() {
    if (typeof window === "undefined") return;
    window.localStorage.removeItem(ACCESS_KEY);
    window.localStorage.removeItem(REFRESH_KEY);
  },
};

interface RequestOptions {
  method?: string;
  body?: unknown;
  auth?: boolean;
  query?: Record<string, string | number | boolean | undefined>;
  signal?: AbortSignal;
}

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const url = new URL(`${API_BASE}${path}`);
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null) url.searchParams.set(key, String(value));
    }
  }
  return url.toString();
}

function defaultMessage(status: number): string {
  if (status === 401) return "Your session expired. Please sign in again.";
  if (status === 403) return "You do not have permission to do that.";
  if (status === 404) return "We couldn't find what you were looking for.";
  if (status === 429) return "Too many requests. Please slow down.";
  if (status >= 500) return "The server had a problem. Please retry.";
  return "Request failed.";
}

async function parseError(res: Response): Promise<ApiError> {
  let payload: { code?: string; message?: string } = {};
  try {
    payload = await res.json();
  } catch {
    /* non-JSON error body */
  }
  const message = payload.message || defaultMessage(res.status);
  return new ApiError(message, payload.code || "error", res.status, res.status >= 500);
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (options.auth !== false && tokenStore.access) {
    headers.Authorization = `Bearer ${tokenStore.access}`;
  }

  const res = await fetch(buildUrl(path, options.query), {
    method: options.method || "GET",
    headers,
    body: options.body ? JSON.stringify(options.body) : undefined,
    signal: options.signal,
  });

  if (res.status === 401 && options.auth !== false) {
    tokenStore.clear();
  }
  if (!res.ok) throw await parseError(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  // Auth
  register(body: { email: string; password: string; full_name?: string; organization_name?: string }) {
    return request<TokenPair>("/api/auth/register", { method: "POST", body, auth: false });
  },
  login(body: { email: string; password: string }) {
    return request<TokenPair>("/api/auth/login", { method: "POST", body, auth: false });
  },
  me() {
    return request<MeResponse>("/api/auth/me");
  },

  // Dashboard / work
  dashboard() {
    return request<Dashboard>("/api/dashboard");
  },
  timeline(params?: { limit?: number; days?: number; sources?: string }) {
    return request<{ items: TimelineItem[] }>("/api/timeline", { query: params });
  },
  emails(params?: { page?: number; page_size?: number; important?: boolean; needs_reply?: boolean; search?: string }) {
    return request<Paginated<EmailItem>>("/api/emails", { query: params });
  },
  email(id: string) {
    return request<EmailItem>(`/api/emails/${id}`);
  },
  calendar(days = 7) {
    return request<CalendarEvent[]>("/api/calendar", { query: { days } });
  },
  messages(params?: { page?: number; page_size?: number; search?: string }) {
    return request<Paginated<MessageItem>>("/api/messages", { query: params });
  },
  tasks(params?: { page?: number; page_size?: number; status?: string; overdue?: boolean; search?: string }) {
    return request<Paginated<TaskItem>>("/api/tasks", { query: params });
  },
  commitments(params?: { direction?: string; status?: string }) {
    return request<Commitment[]>("/api/commitments", { query: params });
  },
  scanCommitments() {
    return request<{ from_emails: number; from_messages: number }>("/api/commitments/scan", { method: "POST" });
  },

  // Integrations
  integrations() {
    return request<IntegrationOverview[]>("/api/integrations");
  },
  syncStates() {
    return request<SyncState[]>("/api/integrations/sync-states");
  },
  connect(provider: string) {
    return request<{ provider: string; authorize_url: string }>(`/api/integrations/${provider}/connect`);
  },
  disconnect(provider: string) {
    return request<{ provider: string; status: string }>(`/api/integrations/${provider}/disconnect`, { method: "POST" });
  },
  sync(full = false) {
    return request<{ provider: string; upserted: number; message: string }[]>("/api/integrations/sync", { method: "POST", query: { full } });
  },

  // Agent
  runs(limit = 25) {
    return request<AgentRun[]>("/api/agent/runs", { query: { limit } });
  },
  run(id: string) {
    return request<AgentRunDetail>(`/api/agent/runs/${id}`);
  },
  usage() {
    return request<UsageStats>("/api/agent/usage");
  },
  pendingActions() {
    return request<AgentAction[]>("/api/agent/actions/pending");
  },
  decideAction(id: string, body: { decision: "approve" | "reject"; edited_arguments?: Record<string, unknown>; note?: string }) {
    return request<AgentAction>(`/api/agent/actions/${id}/decision`, { method: "POST", body });
  },
  activity(limit = 50) {
    return request<ActivityEvent[]>("/api/agent/activity", { query: { limit } });
  },
};

export { API_BASE };
