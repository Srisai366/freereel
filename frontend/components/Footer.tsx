import Link from "next/link";

export default function Footer() {
  return (
    <footer className="mt-16 border-t border-line bg-panel/40">
      <div className="mx-auto grid max-w-7xl gap-6 px-4 py-10 text-sm text-muted sm:grid-cols-3">
        <div>
          <p className="font-bold text-white">
            Free<span className="text-accent">Reel</span>
          </p>
          <p className="mt-2">
            Free, legal streaming of public-domain, Creative Commons and licensed films. No sign-up needed.
          </p>
        </div>
        <nav aria-label="Browse" className="flex flex-col gap-1">
          <Link href="/latest" className="hover:text-white">Latest movies</Link>
          <Link href="/genres" className="hover:text-white">All genres</Link>
          <Link href="/search" className="hover:text-white">Search</Link>
        </nav>
        <nav aria-label="Legal" className="flex flex-col gap-1">
          <Link href="/about" className="hover:text-white">About &amp; content rights</Link>
          <Link href="/privacy" className="hover:text-white">Privacy policy</Link>
          <Link href="/takedown" className="hover:text-white">Copyright / takedown requests</Link>
        </nav>
      </div>
      <p className="pb-6 text-center text-xs text-muted">© {new Date().getFullYear()} FreeReel</p>
    </footer>
  );
}
