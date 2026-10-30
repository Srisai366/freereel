import Footer from "@/components/Footer";
import Header from "@/components/Header";
import PageTracker from "@/components/PageTracker";

export default function SiteLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-accent focus:px-3 focus:py-2 focus:text-accent-ink"
      >
        Skip to content
      </a>
      <Header />
      <main id="main" className="mx-auto w-full max-w-7xl flex-1 px-4">
        {children}
      </main>
      <Footer />
      <PageTracker />
    </div>
  );
}
