import type { Metadata, Viewport } from "next";

import Footer from "@/components/Footer";
import Header from "@/components/Header";
import PageTracker from "@/components/PageTracker";

import "./globals.css";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";
const SITE_NAME = process.env.NEXT_PUBLIC_SITE_NAME ?? "FreeReel";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: { default: `${SITE_NAME} – Watch free legal movies online`, template: `%s | ${SITE_NAME}` },
  description:
    "Stream public-domain classics and Creative Commons films free in Tamil, Telugu, Hindi, Malayalam and English. No sign-up.",
  openGraph: { type: "website", siteName: SITE_NAME, url: SITE_URL },
  twitter: { card: "summary_large_image" },
};

export const viewport: Viewport = {
  themeColor: "#0b0d12",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="flex min-h-screen flex-col font-sans">
        <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-accent focus:px-3 focus:py-2 focus:text-accent-ink">
          Skip to content
        </a>
        <Header />
        <main id="main" className="mx-auto w-full max-w-7xl flex-1 px-4">
          {children}
        </main>
        <Footer />
        <PageTracker />
      </body>
    </html>
  );
}
