"use client";

import { useState } from "react";
import { useTide } from "@/lib/tide";
import { MAYA_ID, SYNTHETIC_GENOME, type Genome } from "@/lib/syntheticGenome";

const TAG = "genome";

export default function GenomePage() {
  const { authenticated, doEncrypt, doDecrypt } = useTide();
  const [status, setStatus] = useState<{ kind: "ok" | "denied"; text: string } | null>(null);
  const [genome, setGenome] = useState<Genome | null>(null);
  const [busy, setBusy] = useState(false);

  if (!authenticated) return <p>Log in as <code>maya</code> to see your genome.</p>;

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setStatus(null);
    try {
      await action();
    } catch (e) {
      setStatus({ kind: "denied", text: `Denied by Tide Fabric: ${e instanceof Error ? e.message : String(e)}` });
    } finally {
      setBusy(false);
    }
  }

  // Encrypt in the browser, then send only the ciphertext to the server.
  const seal = () =>
    run(async () => {
      const [ciphertext] = await doEncrypt([{ data: JSON.stringify(SYNTHETIC_GENOME), tags: [TAG] }]);
      const res = await fetch("/api/genome", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          participantId: MAYA_ID,
          displayName: "Maya (synthetic)",
          consent: { cancerResearch: true, commercialAiTraining: false },
          genome: ciphertext,
        }),
      });
      if (!res.ok) throw new Error(`server ${res.status}`);
      setGenome(null);
      setStatus({ kind: "ok", text: "Sealed. The server stored ciphertext only." });
    });

  // Fetch ciphertext from the server and decrypt it here, in the browser.
  const open = () =>
    run(async () => {
      const res = await fetch(`/api/genome/${MAYA_ID}`);
      if (!res.ok) throw new Error(res.status === 404 ? "nothing sealed yet" : `server ${res.status}`);
      const { genome: ciphertext } = await res.json();
      const [plaintext] = await doDecrypt([{ encrypted: ciphertext, tags: [TAG] }]);
      // The SDK types allow string or bytes.
      setGenome(JSON.parse(typeof plaintext === "string" ? plaintext : new TextDecoder().decode(plaintext)));
      setStatus({ kind: "ok", text: "Opened in your browser." });
    });

  return (
    <>
      <h1>My genome</h1>
      <button onClick={seal} disabled={busy}>Seal genome</button>{" "}
      <button onClick={open} disabled={busy}>Open</button>
      {status && <p className={status.kind}>{status.text}</p>}
      {genome && (
        <table>
          <thead>
            <tr><th>Marker</th><th>Genotype</th></tr>
          </thead>
          <tbody>
            {genome.markers.map((m) => (
              <tr key={m.id}><td>{m.id}</td><td>{m.genotype}</td></tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}
