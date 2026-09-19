"use client";

import Link from "next/link";
import { useEffect } from "react";
import { useAuthStore } from "@/lib/store";

export function Navbar() {
  const { authenticated, email, hydrate, logout } = useAuthStore();

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  return (
    <nav className="relative z-20 mx-auto flex max-w-[1280px] items-center justify-between px-6 py-8">
      <Link href="/" className="flex items-center gap-2">
        <span className="inline-block h-2 w-2 rounded-full bg-accent" />
        <span className="text-base font-medium tracking-tight text-text-primary">
          Terra
        </span>
      </Link>
      <div className="flex items-center gap-3">
        {authenticated ? (
          <>
            <Link
              href="/workspace"
              className="text-sm font-medium text-text-secondary hover:text-text-primary"
            >
              Workspace
            </Link>
            <span className="hidden text-sm text-text-tertiary sm:inline">
              {email}
            </span>
            <button
              onClick={logout}
              className="rounded-[var(--radius-sm)] border border-border px-4 py-2 text-sm text-text-secondary transition hover:border-border-strong hover:text-text-primary"
            >
              Sign out
            </button>
          </>
        ) : (
          <>
            <Link
              href="/login"
              className="text-sm font-medium text-text-secondary hover:text-text-primary"
            >
              Sign in
            </Link>
            <Link
              href="/signup"
              className="rounded-[var(--radius-sm)] border border-text-primary px-4 py-2 text-sm font-medium text-text-primary transition hover:bg-text-primary hover:text-canvas"
            >
              Get started
            </Link>
          </>
        )}
      </div>
    </nav>
  );
}
