const STYLES: Record<string, string> = {
  published: "bg-emerald-950 text-emerald-300 ring-emerald-800",
  succeeded: "bg-emerald-950 text-emerald-300 ring-emerald-800",
  processing: "bg-sky-950 text-sky-300 ring-sky-800",
  running: "bg-sky-950 text-sky-300 ring-sky-800",
  queued: "bg-amber-950 text-amber-300 ring-amber-800",
  draft: "bg-panel-2 text-muted ring-line",
  failed: "bg-red-950 text-red-300 ring-red-800",
};

export default function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium capitalize ring-1 ${STYLES[status] ?? STYLES.draft}`}>
      {status}
    </span>
  );
}
