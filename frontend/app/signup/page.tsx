"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { AuthCard, FormField, SubmitButton } from "@/components/AuthCard";
import { signUp } from "@/lib/auth";

export default function SignupPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await signUp(email, password);
      router.push(`/confirm?email=${encodeURIComponent(email)}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign up failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthCard
      title="Create your Terra account"
      subtitle="Password needs 12+ characters, upper, lower, and a number."
    >
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
          minLength={12}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="••••••••••••"
        />
        {error && <p className="text-sm text-negative">{error}</p>}
        <SubmitButton type="submit" loading={loading}>
          Create account
        </SubmitButton>
      </form>
      <p className="mt-6 text-center text-sm text-text-secondary">
        Already have one?{" "}
        <Link href="/login" className="text-accent hover:text-accent-strong">
          Sign in
        </Link>
      </p>
    </AuthCard>
  );
}
