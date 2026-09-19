"use client";

import Link from "next/link";
import dynamic from "next/dynamic";
import { Navbar } from "@/components/Navbar";
import { ScrollReveal } from "@/components/ScrollReveal";
import { entryHref } from "@/lib/auth";

const Globe3D = dynamic(
  () => import("@/components/Globe3D").then((m) => m.Globe3D),
  { ssr: false }
);

const PIPELINE = [
  {
    step: "01",
    title: "Ask",
    body: "Draw an area, ask a plain-English question. “How has vegetation changed here since July?”",
  },
  {
    step: "02",
    title: "Discover",
    body: "Terra searches Sentinel-2 for usable scenes, filters by cloud cover, and caps what it reads for predictable latency.",
  },
  {
    step: "03",
    title: "Compute",
    body: "Deterministic Python computes NDVI from raw reflectance windows. The LLM never touches the math.",
  },
  {
    step: "04",
    title: "Explain",
    body: "You get the number, its evidence trail, and every limitation — never a claim the data can't support.",
  },
];

const PRINCIPLES = [
  {
    title: "Deterministic science",
    body: "Every metric comes from NumPy on real reflectance data. The language model maps your question to an analysis and explains the result in words — it never computes anything.",
  },
  {
    title: "Evidence, not vibes",
    body: "Every result ships with which scenes were used, which were rejected and why, cloud cover, and valid-pixel ratio. Scientific honesty is not a feature flag.",
  },
  {
    title: "AWS-native, built to scale",
    body: "API Gateway, Lambda, DynamoDB, SQS, Cognito, and Bedrock — the same architecture underneath a one-shot hackathon demo and a production deployment.",
  },
];

export default function LandingPage() {
  return (
    <main className="relative min-h-screen overflow-hidden bg-canvas">
      <Navbar />

      {/* Hero */}
      <section className="relative mx-auto flex max-w-[1280px] flex-col items-center px-6 pt-8 pb-32 text-center">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-[680px]">
          <Globe3D />
        </div>
        <div
          className="pointer-events-none absolute inset-x-0 top-0 h-[680px]"
          style={{
            background:
              "radial-gradient(60% 55% at 50% 38%, rgba(7,8,10,0.88) 0%, rgba(7,8,10,0.55) 45%, rgba(7,8,10,0) 75%)",
          }}
        />

        <div className="relative z-10 mt-24 animate-fade-up">
          <span className="mb-6 inline-flex items-center gap-2 rounded-full border border-border px-3 py-1 text-xs text-text-secondary">
            <span className="h-1.5 w-1.5 rounded-full bg-positive" />
            Built for First Commit × AWS — SHIP IT track
          </span>
          <h1 className="mx-auto max-w-3xl text-5xl font-medium tracking-tight text-text-primary sm:text-6xl">
            Earth Observation,
            <br />
            <span className="spectral-text">without the plumbing.</span>
          </h1>
          <p className="mx-auto mt-6 max-w-xl text-base text-text-secondary sm:text-lg">
            Ask a question about any area on Earth. Get a satellite-derived
            answer, backed by the exact evidence that produced it —
            nothing hidden, nothing overstated.
          </p>
          <div className="mt-10 flex items-center justify-center gap-4">
            <Link
              href={entryHref()}
              className="spectral-glow rounded-[var(--radius-sm)] border border-text-primary bg-text-primary px-6 py-3 text-sm font-medium text-canvas transition hover:opacity-90"
            >
              Launch Terra
            </Link>
            <Link
              href="#how-it-works"
              className="rounded-[var(--radius-sm)] border border-border px-6 py-3 text-sm font-medium text-text-secondary transition hover:border-border-strong hover:text-text-primary"
            >
              See how it works
            </Link>
          </div>
        </div>
      </section>

      {/* Principles */}
      <section className="mx-auto max-w-[1280px] px-6 py-24">
        <ScrollReveal>
          <h2 className="mb-14 text-center text-2xl font-medium tracking-tight text-text-primary sm:text-3xl">
            Built on three non-negotiables
          </h2>
        </ScrollReveal>
        <div className="grid gap-5 sm:grid-cols-3">
          {PRINCIPLES.map((p, i) => (
            <ScrollReveal key={p.title} delay={i * 0.1}>
              <div className="glass-panel h-full p-7">
                <h3 className="text-lg font-medium text-text-primary">
                  {p.title}
                </h3>
                <p className="mt-3 text-sm leading-relaxed text-text-secondary">
                  {p.body}
                </p>
              </div>
            </ScrollReveal>
          ))}
        </div>
      </section>

      {/* Pipeline */}
      <section id="how-it-works" className="mx-auto max-w-[1280px] px-6 py-24">
        <ScrollReveal>
          <h2 className="mb-14 text-center text-2xl font-medium tracking-tight text-text-primary sm:text-3xl">
            From question to evidence in one pipeline
          </h2>
        </ScrollReveal>
        <div className="grid gap-px overflow-hidden rounded-[var(--radius-lg)] border border-border bg-border sm:grid-cols-4">
          {PIPELINE.map((p, i) => (
            <ScrollReveal key={p.step} delay={i * 0.08}>
              <div className="h-full bg-surface p-7">
                <span className="text-mono-num text-sm text-accent">
                  {p.step}
                </span>
                <h3 className="mt-3 text-base font-medium text-text-primary">
                  {p.title}
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-text-secondary">
                  {p.body}
                </p>
              </div>
            </ScrollReveal>
          ))}
        </div>
      </section>

      {/* Sample result */}
      <section className="mx-auto max-w-[1280px] px-6 py-24">
        <ScrollReveal>
          <div className="glass-panel mx-auto max-w-2xl p-8">
            <p className="text-xs uppercase tracking-wide text-text-tertiary">
              Sample result &middot; NDVI change
            </p>
            <p className="text-mono-num mt-3 text-5xl font-medium text-negative">
              -18.2%
            </p>
            <p className="mt-2 text-sm text-text-secondary">
              0.5613 &rarr; 0.4591, Aug 2025 vs Jul 2025
            </p>
            <div className="mt-6 grid grid-cols-3 gap-4 border-t border-border pt-6 text-sm">
              <div>
                <p className="text-mono-num text-text-primary">8</p>
                <p className="text-text-tertiary">scenes used</p>
              </div>
              <div>
                <p className="text-mono-num text-text-primary">32</p>
                <p className="text-text-tertiary">rejected</p>
              </div>
              <div>
                <p className="text-mono-num text-text-primary">94%</p>
                <p className="text-text-tertiary">valid pixels</p>
              </div>
            </div>
          </div>
        </ScrollReveal>
      </section>

      {/* Footer CTA */}
      <section className="mx-auto max-w-[1280px] px-6 pb-32 pt-8 text-center">
        <ScrollReveal>
          <h2 className="text-3xl font-medium tracking-tight text-text-primary">
            Ready to ask Earth a question?
          </h2>
          <Link
            href={entryHref()}
            className="spectral-glow mt-8 inline-block rounded-[var(--radius-sm)] border border-text-primary bg-text-primary px-6 py-3 text-sm font-medium text-canvas transition hover:opacity-90"
          >
            Launch Terra
          </Link>
        </ScrollReveal>
      </section>

      <footer className="border-t border-border py-8 text-center text-xs text-text-tertiary">
        Terra &middot; Earth Observation, without the plumbing.
      </footer>
    </main>
  );
}
