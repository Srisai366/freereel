"use client";

import { usePathname } from "next/navigation";
import { useEffect } from "react";

import { track } from "@/services/analytics";

export default function PageTracker() {
  const pathname = usePathname();

  useEffect(() => {
    if (pathname.startsWith("/admin")) return;
    try {
      if (!sessionStorage.getItem("fr_visit")) {
        sessionStorage.setItem("fr_visit", "1");
        track("visit", { path: pathname });
        return;
      }
    } catch {
      // storage unavailable: still count the page view below
    }
    track("page_view", { path: pathname });
  }, [pathname]);

  return null;
}
