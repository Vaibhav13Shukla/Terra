"use client";

import { type ReactNode } from "react";
import { motion } from "framer-motion";

export function AuthCard({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: ReactNode;
}) {
  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-canvas px-6">
      <div
        className="pointer-events-none absolute inset-0 opacity-40"
        style={{
          background:
            "radial-gradient(circle at 50% 0%, rgba(34,211,170,0.18), transparent 55%)",
        }}
      />
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
        className="glass-panel relative z-10 w-full max-w-sm p-8"
      >
        <h1 className="text-xl font-medium text-text-primary">{title}</h1>
        <p className="mt-1 text-sm text-text-secondary">{subtitle}</p>
        <div className="mt-6">{children}</div>
      </motion.div>
    </div>
  );
}

export function FormField({
  label,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  return (
    <label className="block text-sm">
      <span className="mb-1.5 block text-text-secondary">{label}</span>
      <input
        {...props}
        className="w-full rounded-[var(--radius-sm)] border border-border bg-inset px-3 py-2.5 text-sm text-text-primary outline-none placeholder:text-text-tertiary focus:border-border-strong"
      />
    </label>
  );
}

export function SubmitButton({
  children,
  loading,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { loading?: boolean }) {
  return (
    <button
      {...props}
      disabled={loading || props.disabled}
      className="w-full rounded-[var(--radius-sm)] border border-text-primary bg-transparent py-2.5 text-sm font-medium text-text-primary transition hover:bg-text-primary hover:text-canvas disabled:opacity-50"
    >
      {loading ? "Working…" : children}
    </button>
  );
}
