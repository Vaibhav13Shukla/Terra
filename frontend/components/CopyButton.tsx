"use client";

import { useState } from "react";

export function CopyButton({
  text,
  label = "Copy",
}: {
  text: string;
  label?: string;
}) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard API unavailable (e.g. an insecure origin) — leave the
      // label as-is rather than claiming a copy that didn't happen.
    }
  }

  return (
    <button
      type="button"
      onClick={copy}
      className="rounded-[var(--radius-sm)] border border-border px-2 py-1 text-[11px] text-text-secondary transition hover:border-border-strong hover:text-text-primary"
    >
      {copied ? "Copied" : label}
    </button>
  );
}
