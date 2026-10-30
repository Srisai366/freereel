import type { Metadata, Viewport } from "next";

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

// Root layout only owns <html>/<body>; the public site and the admin area each add their own chrome.
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen font-sans">{children}</body>
    </html>
  );
}
