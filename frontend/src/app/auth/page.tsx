"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Hexagon, Loader2 } from "lucide-react";
import { useAuth } from "@/stores/auth";

function AuthForm() {
  const router = useRouter();
  const { login, register, loading, error } = useAuth();
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [orgName, setOrgName] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      if (isRegister) {
        await register({ email, password, full_name: fullName || undefined, organization_name: orgName || undefined });
      } else {
        await login({ email, password });
      }
      router.push("/overview");
      router.refresh();
    } catch {
      /* error shown via store */
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3">
      {isRegister && (
        <input
          required
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          placeholder="Full name"
          className="input"
        />
      )}
      {isRegister && (
        <input
          required
          value={orgName}
          onChange={(e) => setOrgName(e.target.value)}
          placeholder="Organization name"
          className="input"
        />
      )}
      <input
        required
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="Email"
        className="input"
      />
      <input
        required
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder="Password"
        className="input"
      />
      {error && (
        <p className="text-sm text-signal-urgent">{error}</p>
      )}
      <button type="submit" disabled={loading} className="btn-primary">
        {loading && <Loader2 className="h-4 w-4 animate-spin" />}
        {loading ? "Please wait" : isRegister ? "Create account" : "Sign in"}
      </button>
      <button type="button" onClick={() => { setIsRegister(!isRegister); }} className="btn-ghost">
        {isRegister ? "Already have an account? Sign in" : "Need an account? Register"}
      </button>
    </form>
  );
}

export default function AuthPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-base-950 px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 grid h-12 w-12 place-items-center rounded-xl bg-gradient-to-br from-accent to-violet shadow-glow">
            <Hexagon className="h-6 w-6 text-white" strokeWidth={2.5} />
          </div>
          <h1 className="text-xl font-semibold tracking-tight text-ink-50">MyWork AI</h1>
          <p className="mt-1 text-sm text-ink-500">Sign in to your workspace</p>
        </div>
        <div className="panel p-6">
          <AuthForm />
        </div>
      </div>
    </div>
  );
}
