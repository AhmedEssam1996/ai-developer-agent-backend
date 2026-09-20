"use client";

import { useEffect } from "react";
import { useAuth } from "@/stores/auth";

export function Providers({ children }: { children: React.ReactNode }) {
  const loadMe = useAuth((s) => s.loadMe);

  useEffect(() => {
    void loadMe();
  }, [loadMe]);

  return <>{children}</>;
}