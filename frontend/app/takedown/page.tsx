import type { Metadata } from "next";

import ProsePage from "@/components/ProsePage";

export const metadata: Metadata = { title: "Copyright & takedown requests" };

export default function TakedownPage() {
  return (
    <ProsePage title="Copyright & takedown requests">
      <p>
        We only publish films we believe we have the right to stream. If you hold the rights to a film
        on this site and didn&apos;t authorise it, tell us and we will remove it promptly while we look into it.
      </p>
      <h2>Please include</h2>
      <ul>
        <li>A link to the film page on FreeReel.</li>
        <li>Proof that you own the rights or represent the owner.</li>
        <li>Your contact details.</li>
      </ul>
      <p>Send requests to the site operator&apos;s contact address (to be published before launch).</p>
    </ProsePage>
  );
}
