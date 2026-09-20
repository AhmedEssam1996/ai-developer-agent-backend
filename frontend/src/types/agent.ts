// Agent, action, activity and streaming event types.

export interface AgentAction {
  id: string;
  tool_name: string;
  kind: "read" | "write";
  risk: string;
  status: string;
  arguments: Record<string, unknown>;
  preview?: string | null;
  result?: Record<string, unknown> | null;
  error?: string | null;
  created_at: string;
}

export interface AgentRun {
  id: string;
  status: string;
  intent?: string | null;
  prompt: string;
  model?: string | null;
  provider?: string | null;
  latency_ms?: number | null;
  total_tokens: number;
  tool_call_count: number;
  error?: string | null;
  created_at: string;
}

export interface AgentRunDetail {
  run: AgentRun;
  actions: AgentAction[];
}

export interface ApprovalDecision {
  decision: "approve" | "reject";
  edited_arguments?: Record<string, unknown>;
  note?: string;
}

export interface ActivityEvent {
  id: string;
  kind: string;
  title: string;
  detail: string;
  source?: string | null;
  level: string;
  run_id?: string | null;
  created_at: string;
}

export interface UsageStats {
  total_runs: number;
  total_tokens: number;
  avg_latency_ms: number;
  total_tool_calls: number;
}

// --- Agent streaming event protocol (mirrors backend SSE) -------------------

export type AgentStreamEvent =
  | { event: "run_started"; data: { run_id: string } }
  | { event: "status"; data: { label: string; phase?: string } }
  | { event: "intent"; data: { intent: string } }
  | { event: "token"; data: { text: string } }
  | { event: "tool_started"; data: { name: string; kind: string; label: string } }
  | { event: "tool_finished"; data: { name: string; kind: string; ok: boolean; summary: string } }
  | {
      event: "approval_required";
      data: {
        action_id: string;
        tool_name: string;
        preview: string;
        arguments: Record<string, unknown>;
        flagged?: boolean;
      };
    }
  | { event: "warning"; data: { message: string } }
  | { event: "error"; data: { code: string; message: string; retryable?: boolean } }
  | {
      event: "run_finished";
      data: {
        run_id: string;
        status: string;
        latency_ms: number;
        tool_calls: number;
        total_tokens: number;
        model?: string | null;
      };
    };