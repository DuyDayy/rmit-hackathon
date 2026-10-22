"use client";

import { useState } from "react";
import { useTideCloak } from "@tidecloak/nextjs";

const TAG = "genome";
const READ_ROLE = "_tide_genome.selfdecrypt";

type Status = { kind: "ok" | "denied" | "pending"; text: string };

const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

export default function AdminPage() {
  const { authenticated, doDecrypt, getValueFromToken, AdminAPI } = useTideCloak();
  const [exportStatus, setExportStatus] = useState<Status | null>(null);
  const [grantStatus, setGrantStatus] = useState<Status | null>(null);
  const [busy, setBusy] = useState(false);

  if (!authenticated) return <p>Log in as <code>admin.acquirer</code>.</p>;

  // B4: try to decrypt every stored genome. The Fabric should refuse each one.
  async function exportAll() {
    setBusy(true);
    setExportStatus(null);
    const records: { participantId: string; genome: string }[] = await (await fetch("/api/genome")).json();
    let opened = 0;
    let denied = 0;
    let lastError = "";
    for (const r of records) {
      try {
        await doDecrypt([{ encrypted: r.genome, tags: [TAG] }]);
        opened++;
      } catch (e) {
        denied++;
        lastError = message(e);
      }
    }
    setExportStatus(
      opened === 0
        ? { kind: "denied", text: `Denied by Tide Fabric: 0 of ${records.length} genomes decrypted. ${lastError}` }
        : { kind: "ok", text: `Decrypted ${opened} of ${records.length} (denied ${denied}).` },
    );
    setBusy(false);
  }

  // B5: assign the read role to ourselves. With a quorum configured this becomes a pending change request.
  async function grantSelf() {
    setBusy(true);
    setGrantStatus(null);
    try {
      const userId = getValueFromToken("sub");
      const role = await AdminAPI.getRole(READ_ROLE);
      await AdminAPI.addUserRoles(userId, [role]);
      const pending = [...(await AdminAPI.getUserChangeRequests()), ...(await AdminAPI.getRoleChangeRequests())];
      setGrantStatus(
        pending.length > 0
          ? { kind: "pending", text: `Pending: ${pending.length} change request(s) awaiting quorum approval.` }
          : { kind: "ok", text: "No pending request found. Check the quorum setup (task A5)." },
      );
    } catch (e) {
      setGrantStatus({ kind: "denied", text: `Request failed: ${message(e)}` });
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h1>Admin</h1>
      <section>
        <button onClick={exportAll} disabled={busy}>Export all genomes</button>
        {exportStatus && <p className={exportStatus.kind}>{exportStatus.text}</p>}
      </section>
      <section>
        <button onClick={grantSelf} disabled={busy}>Grant myself genome read access</button>
        {grantStatus && <p className={grantStatus.kind}>{grantStatus.text}</p>}
      </section>
    </>
  );
}
