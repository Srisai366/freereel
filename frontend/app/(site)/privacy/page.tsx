import type { Metadata } from "next";

import ProsePage from "@/components/ProsePage";

export const metadata: Metadata = { title: "Privacy policy" };

export default function PrivacyPage() {
  return (
    <ProsePage title="Privacy policy">
      <p>FreeReel has no user accounts, and we collect as little information as we can.</p>
      <h2>What we record</h2>
      <ul>
        <li>A random ID stored in your browser, so we can count visits and plays without knowing who you are.</li>
        <li>The pages you open and the films you play, with roughly how long you watched.</li>
        <li>Your device type (phone, tablet or desktop), worked out once and then discarded with the rest of the browser details.</li>
      </ul>
      <h2>What we don&apos;t record</h2>
      <ul>
        <li>Your name, email address or IP address.</li>
        <li>Your full browser identification string.</li>
      </ul>
      <p>
        You can clear the random ID at any time by clearing this site&apos;s data in your browser. If we add
        third-party advertising, this page will be updated to describe the cookies those services use
        before they are switched on.
      </p>
    </ProsePage>
  );
}
