import { create } from "zustand";
import { api, tokenStore } from "@/lib/api";
import type { MeResponse } from "@/types";

interface AuthState {
  me: MeResponse | null;
  loading: boolean;
  ready: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  register: (input: {
    email: string;
    password: string;
    full_name?: string;
    organization_name?: string;
  }) => Promise<void>;
  loadMe: () => Promise<void>;
  logout: () => void;
}

export const useAuth = create<AuthState>((set) => ({
  me: null,
  loading: false,
  ready: false,
  error: null,

  async login(email, password) {
    set({ loading: true, error: null });
    try {
      const pair = await api.login({ email, password });
      tokenStore.set(pair);
      const me = await api.me();
      set({ me, loading: false, ready: true });
    } catch (e) {
      set({ loading: false, error: (e as Error).message });
      throw e;
    }
  },

  async register(input) {
    set({ loading: true, error: null });
    try {
      const pair = await api.register(input);
      tokenStore.set(pair);
      const me = await api.me();
      set({ me, loading: false, ready: true });
    } catch (e) {
      set({ loading: false, error: (e as Error).message });
      throw e;
    }
  },

  async loadMe() {
    if (!tokenStore.access) {
      set({ ready: true, me: null });
      return;
    }
    set({ loading: true });
    try {
      const me = await api.me();
      set({ me, loading: false, ready: true });
    } catch {
      tokenStore.clear();
      set({ me: null, loading: false, ready: true });
    }
  },

  logout() {
    tokenStore.clear();
    set({ me: null, ready: true });
  },
}));