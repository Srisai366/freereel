export default function ProsePage({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <article className="mx-auto max-w-3xl py-10 leading-relaxed [&_h2]:mt-8 [&_h2]:text-lg [&_h2]:font-bold [&_p]:mt-3 [&_p]:text-muted [&_ul]:mt-3 [&_ul]:list-disc [&_ul]:pl-6 [&_li]:text-muted">
      <h1 className="text-3xl font-extrabold">{title}</h1>
      {children}
    </article>
  );
}
