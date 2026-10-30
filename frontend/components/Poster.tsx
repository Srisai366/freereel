interface PosterProps {
  title: string;
  src: string | null;
  className?: string;
  eager?: boolean;
}

// Deterministic hue per title, so a movie without artwork always gets the same fallback.
function hue(title: string): number {
  let h = 0;
  for (const ch of title) h = (h * 31 + ch.charCodeAt(0)) % 360;
  return h;
}

export default function Poster({ title, src, className = "", eager = false }: PosterProps) {
  if (src) {
    return (
      <img
        src={src}
        alt={`${title} poster`}
        loading={eager ? "eager" : "lazy"}
        decoding="async"
        className={`h-full w-full object-cover ${className}`}
      />
    );
  }
  const h = hue(title);
  return (
    <div
      role="img"
      aria-label={`${title} poster`}
      className={`flex h-full w-full items-end p-3 ${className}`}
      style={{
        background: `linear-gradient(160deg, hsl(${h} 55% 32%), hsl(${(h + 40) % 360} 60% 12%))`,
      }}
    >
      <span className="line-clamp-3 text-base font-bold leading-tight text-white/90 drop-shadow">
        {title}
      </span>
    </div>
  );
}
