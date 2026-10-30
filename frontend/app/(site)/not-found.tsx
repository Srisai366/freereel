import Link from "next/link";

export default function NotFound() {
  return (
    <div className="py-24 text-center">
      <p className="text-sm font-semibold uppercase tracking-widest text-accent">404</p>
      <h1 className="mt-2 text-3xl font-extrabold">We couldn&apos;t find that page</h1>
      <p className="mt-2 text-muted">The movie may have been removed, or the link is wrong.</p>
      <Link href="/" className="mt-6 inline-block rounded-md bg-accent px-5 py-2.5 font-semibold text-accent-ink">
        Back to home
      </Link>
    </div>
  );
}
