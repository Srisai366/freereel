import Link from "next/link";

const NAV = [
  { href: "/", label: "Home" },
  { href: "/language/ta", label: "Tamil" },
  { href: "/language/te", label: "Telugu" },
  { href: "/language/hi", label: "Hindi" },
  { href: "/language/ml", label: "Malayalam" },
  { href: "/language/en", label: "English" },
  { href: "/genres", label: "Genres" },
  { href: "/latest", label: "Latest" },
];

export default function Header() {
  return (
    <header className="sticky top-0 z-40 border-b border-line bg-ink/90 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-3">
        <Link href="/" className="flex shrink-0 items-center gap-2" aria-label="FreeReel home">
          <span className="grid h-8 w-8 place-items-center rounded-md bg-accent text-sm font-black text-accent-ink">
            FR
          </span>
          <span className="hidden text-lg font-extrabold tracking-tight sm:inline">
            Free<span className="text-accent">Reel</span>
          </span>
        </Link>

        {/* GET form: search works without JavaScript and the results URL is shareable. */}
        <form action="/search" method="get" role="search" className="ml-auto flex w-full max-w-sm">
          <label htmlFor="site-search" className="sr-only">
            Search movies
          </label>
          <input
            id="site-search"
            name="q"
            type="search"
            placeholder="Search movies, directors, cast…"
            maxLength={100}
            className="w-full rounded-l-md border border-line bg-panel px-3 py-2 text-sm placeholder:text-muted focus:border-accent focus:outline-none"
          />
          <button type="submit" className="rounded-r-md bg-accent px-3 text-sm font-semibold text-accent-ink">
            Search
          </button>
        </form>
      </div>

      <nav aria-label="Main" className="shelf mx-auto flex max-w-7xl gap-1 overflow-x-auto px-4 pb-2">
        {NAV.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className="shrink-0 rounded-full px-3 py-1.5 text-sm text-muted hover:bg-panel hover:text-white"
          >
            {item.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}
