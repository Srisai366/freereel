import type { Metadata } from "next";

import ProsePage from "@/components/ProsePage";

export const metadata: Metadata = { title: "About & content rights" };

export default function AboutPage() {
  return (
    <ProsePage title="About FreeReel">
      <p>
        FreeReel streams films for free, with no account or sign-up. Every film on the site is in the
        public domain, released under a Creative Commons licence, or streamed with the rights holder&apos;s
        permission.
      </p>
      <h2>How we choose films</h2>
      <p>
        Each title page lists the rights basis for that film. Public-domain status depends on the
        country, so we check each title before publishing it.
      </p>
      <h2>Advertising</h2>
      <p>
        Ads keep the site free. We never use pop-ups, forced downloads or misleading redirects.
        Sponsored content is always labelled.
      </p>
    </ProsePage>
  );
}
