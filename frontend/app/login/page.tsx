"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { AuthCard, FormField, SubmitButton } from "@/components/AuthCard";
import { signIn } from "@/lib/auth";
import { useAuthStore } from "@/lib/store";

export default function LoginPage() {
  const router = useRouter();
  const login = useAuthStore((s) => s.login);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await signIn(email, password);
      login(email);
      router.push("/workspace");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign in failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthCard title="Sign in to Terra" subtitle="Continue your analyses.">
      <form onSubmit={handleSubmit} className="space-y-4">
        <FormField
          label="Email"
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@example.com"
        />
        <FormField
          label="Password"
          type="password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="••••••••"
        />
        {error && <p className="text-sm text-negative">{error}</p>}
        <SubmitButton type="submit" loading={loading}>
          Sign in
        </SubmitButton>
      </form>
      <p className="mt-6 text-center text-sm text-text-secondary">
        No account?{" "}
        <Link href="/signup" className="text-accent hover:text-accent-strong">
          Create one
        </Link>
      </p>
    </AuthCard>
  );
}
