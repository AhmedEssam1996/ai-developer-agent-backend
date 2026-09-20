import { create } from "zustand";
import type { AgentStreamEvent } from "@/types";

export interface TranscriptStep {
  id: string;
  phase: "status" | "tool" | "approval" | "warning" | "error";
  label: string;
  detail?: string;
  state: "running" | "done" | "error";
  tool?: string;
  actionId?: string;
  preview?: string;
  args?: Record<string, unknown>;
}

interface AgentState {
  running: boolean;
  runId: string | null;
  answer: string;
  steps: TranscriptStep[];
  error: string | null;
  model: string | null;
  tokens: number;
  latencyMs: number | null;
  start: () => void;
  apply: (event: AgentStreamEvent) => void;
  reset: () => void;
  abort: () => void;
}

let counter = 0;
const nextId = () => `step-${++counter}`;
const settle = (steps: TranscriptStep[]): TranscriptStep[] =>
  steps.map((st) => (st.state === "running" ? { ...st, state: "done" } : st));

type Setter = (partial: Partial<AgentState> | ((s: AgentState) => Partial<AgentState>)) => void;

function reducer(set: Setter, event: AgentStreamEvent): void {
  switch (event.event) {
    case "run_started":
      set({ runId: event.data.run_id });
      break;
    case "status":
      set((s) => ({
        steps: [
          ...settle(s.steps),
          { id: nextId(), phase: "status", label: event.data.label, state: "running" },
        ],
      }));
      break;
    case "tool_started":
      set((s) => ({
        steps: [
          ...settle(s.steps),
          {
            id: nextId(),
            phase: "tool",
            label: event.data.label,
            detail: "in progress",
            state: "running",
            tool: event.data.name,
          },
        ],
      }));
      break;
    case "tool_finished":
      set((s) => {
        const idx = [...s.steps]
          .reverse()
          .findIndex((st) => st.tool === event.data.name && st.state === "running");
        if (idx === -1) return s;
        const realIdx = s.steps.length - 1 - idx;
        const steps = [...s.steps];
        steps[realIdx] = {
          ...steps[realIdx],
          state: event.data.ok ? "done" : "error",
          detail: event.data.summary || (event.data.ok ? "done" : "failed"),
        };
        return { steps };
      });
      break;
    case "approval_required":
      set((s) => ({
        steps: [
          ...settle(s.steps),
          {
            id: nextId(),
            phase: "approval",
            label: "Approval required",
            state: "running",
            tool: event.data.tool_name,
            actionId: event.data.action_id,
            preview: event.data.preview,
            args: event.data.arguments,
          },
        ],
      }));
      break;
    case "warning":
      set((s) => ({
        steps: [...s.steps, { id: nextId(), phase: "warning", label: event.data.message, state: "done" }],
      }));
      break;
    case "token":
      set((s) => ({ answer: s.answer + event.data.text }));
      break;
    case "error":
      set((s) => ({
        running: false,
        error: event.data.message,
        steps: [...settle(s.steps), { id: nextId(), phase: "error", label: event.data.message, state: "error" }],
      }));
      break;
    case "run_finished":
      set((s) => ({
        running: false,
        model: event.data.model ?? s.model,
        tokens: event.data.total_tokens,
        latencyMs: event.data.latency_ms,
        steps: settle(s.steps),
      }));
      break;
  }
}

export const useAgent = create<AgentState>((set, get) => ({
  running: false,
  runId: null,
  answer: "",
  steps: [],
  error: null,
  model: null,
  tokens: 0,
  latencyMs: null,

  start() {
    set({ running: true, runId: null, answer: "", steps: [], error: null, model: null, tokens: 0, latencyMs: null });
  },

  abort() {
    set({ running: false });
  },

  reset() {
    get().abort();
    set({ steps: [], answer: "", error: null, runId: null });
  },

  apply(event) {
    reducer(set, event);
  },
}));