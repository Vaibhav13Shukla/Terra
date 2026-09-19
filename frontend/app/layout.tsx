import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

const mono = JetBrains_Mono({
  variable: "--font-mono-data",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Terra — Earth Observation, without the plumbing",
  description:
    "Ask a natural-language question about an area on Earth and get an evidence-backed satellite analysis: which scenes were used, why others were rejected, and the honest number behind the answer.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${mono.variable} h-full`}
    >
      <body className="min-h-full bg-canvas text-text-primary antialiased">
        {children}
      </body>
    </html>
  );
}
