import { create } from "zustand";
import { api } from "@/lib/api";
import type { IntegrationOverview } from "@/types";

interface ShellState {
  integrations: IntegrationOverview[];
  loaded: boolean;
  loading: boolean;
  isMock: boolean;
  paletteOpen: boolean;
  loadIntegrations: () => Promise<void>;
  setPaletteOpen: (open: boolean) => void;
}

export const useShell = create<ShellState>((set, get) => ({
  integrations: [],
  loaded: false,
  loading: false,
  isMock: false,
  paletteOpen: false,

  async loadIntegrations() {
    if (get().loading) return;
    set({ loading: true });
    try {
      const list = await api.integrations();
      set({
        integrations: list,
        isMock: list.some((i) => i.is_mock),
        loaded: true,
        loading: false,
      });
    } catch {
      set({ loading: false });
    }
  },

  setPaletteOpen(open) {
    set({ paletteOpen: open });
  },
}));

export function connectionState(
  integrations: IntegrationOverview[],
  provider: string,
): "connected" | "disconnected" | "error" | "working" {
  const match = integrations.find((i) => i.provider === provider);
  if (!match) return "disconnected";
  if (match.last_error) return "error";
  return match.connected ? "connected" : "disconnected";
}