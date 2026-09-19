"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useAuthStore } from "@/lib/store";
import { isAuthConfigured } from "@/lib/auth";
import { InspectorPanel } from "@/components/InspectorPanel";

const AOIMap = dynamic(
  () => import("@/components/AOIMap").then((m) => m.AOIMap),
  { ssr: false }
);

export default function WorkspacePage() {
  const router = useRouter();
  const { authenticated, hydrate, email, logout } = useAuthStore();
  // With no Cognito pool configured there is nothing to sign in to, so the
  // workspace runs in open demo mode rather than redirecting to a login
  // screen that can never succeed. (The backend is equally open until
  // AUTH_ENABLED=true — docs/DEPLOYMENT.md §6.)
  const authRequired = isAuthConfigured();

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  useEffect(() => {
    if (!authRequired) return;
    // Auth is optional at the API layer until AUTH_ENABLED=true is set on
    // the deployed backend (see docs/DEPLOYMENT.md §6); this client-side
    // guard reflects the intended product flow once it is.
    const timeout = setTimeout(() => {
      if (!useAuthStore.getState().authenticated) {
        router.replace("/login");
      }
    }, 50);
    return () => clearTimeout(timeout);
  }, [router, authRequired]);

  if (authRequired && !authenticated) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-canvas">
        <p className="text-sm text-text-tertiary">Redirecting to sign in…</p>
      </main>
    );
  }

  return (
    <main className="flex h-screen flex-col bg-canvas">
      <header className="flex items-center justify-between border-b border-border px-6 py-4">
        <Link href="/" className="flex items-center gap-2">
          <span className="inline-block h-2 w-2 rounded-full bg-accent" />
          <span className="text-sm font-medium text-text-primary">Terra</span>
        </Link>
        <div className="flex items-center gap-3 text-sm">
          {authRequired ? (
            <>
              <span className="text-text-tertiary">{email}</span>
              <button
                onClick={() => {
                  logout();
                  router.push("/");
                }}
                className="rounded-[var(--radius-sm)] border border-border px-3 py-1.5 text-xs text-text-secondary transition hover:border-border-strong hover:text-text-primary"
              >
                Sign out
              </button>
            </>
          ) : (
            <span
              title="Sign-in isn't configured on this deployment, so the workspace is open."
              className="rounded-full border border-border-strong px-2.5 py-1 text-xs text-text-secondary"
            >
              Demo mode &middot; no sign-in
            </span>
          )}
        </div>
      </header>
      <div className="relative flex flex-1 gap-4 overflow-hidden p-4">
        <div className="flex-1 overflow-hidden rounded-[var(--radius-lg)] border border-border">
          <AOIMap />
        </div>
        <InspectorPanel />
      </div>
    </main>
  );
}
