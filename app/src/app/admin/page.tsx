"use client";

import { useState } from "react";
import { useTideCloak } from "@tidecloak/nextjs";

const TAG = "genome";
const READ_ROLE = "_tide_genome.selfdecrypt";

type Status = { kind: "ok" | "denied" | "pending"; text: string };

// Shape of an entry from /admin/realms/{realm}/iga/change-requests (fields this page reads).
type PendingRequest = {
  id: string;
  actionType: string;
  entityId?: string;
  rows?: unknown;
  authorizationCount?: number;
  threshold?: number;
};

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
      // The source of truth: did the role actually land on our account?
      const held: { name: string }[] = (await AdminAPI.getUserRoles(userId)) ?? [];
      if (held.some((r) => r.name === READ_ROLE)) {
        setGrantStatus({ kind: "ok", text: "Granted immediately: quorum governance is not enforced. Check the quorum setup (task A5)." });
        return;
      }
      // AdminAPI.getUserChangeRequests() calls the legacy tide-admin/change-set endpoints, which
      // return 404 on current TideCloak, so read the IGA change-request inbox directly.
      let approvals = "";
      try {
        const pending: PendingRequest[] =
          (await AdminAPI.fetch(`/admin/realms/${AdminAPI.getRealm()}/iga/change-requests?status=PENDING`)) ?? [];
        const mine = pending.find(
          (cr) => cr.actionType === "GRANT_ROLES" && (cr.entityId === userId || JSON.stringify(cr.rows ?? "").includes(userId)),
        );
        if (mine) approvals = ` ${mine.authorizationCount ?? 0} of ${mine.threshold ?? "?"} approvals.`;
      } catch {
        // Reading the inbox may need more rights than this admin has; the role check above is enough.
      }
      setGrantStatus({
        kind: "pending",
        text: `Pending quorum approval.${approvals} The role is not granted until the custodian and ethics board decide.`,
      });
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
        <p>
          The raw file can still be <a href="/api/export-all">downloaded</a>. It contains ciphertext only.
        </p>
      </section>
      <section>
        <button onClick={grantSelf} disabled={busy}>Grant myself genome read access</button>
        {grantStatus && <p className={grantStatus.kind}>{grantStatus.text}</p>}
      </section>
    </>
  );
}
