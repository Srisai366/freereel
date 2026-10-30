"use client";

const PUBLIC_API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const KEY = "fr_session";

type EventType = "visit" | "page_view" | "play" | "progress";

/** Random anonymous id kept in this browser only; it identifies no person. */
export function sessionId(): string {
  try {
    let id = localStorage.getItem(KEY);
    if (!id) {
      id = crypto.randomUUID();
      localStorage.setItem(KEY, id);
    }
    return id;
  } catch {
    return crypto.randomUUID(); // storage blocked (private mode): fall back to a per-load id
  }
}

export function track(type: EventType, data: { movie_id?: number; path?: string; watch_seconds?: number } = {}) {
  // keepalive lets the request finish even if the user navigates away. Failures are ignored on purpose.
  fetch(`${PUBLIC_API}/api/events`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type, session_id: sessionId(), ...data }),
    keepalive: true,
  }).catch(() => {});
}
