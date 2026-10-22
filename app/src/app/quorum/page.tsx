"use client";

// Quorum inbox: governed change requests and the approvals they still need.
// Simulated mode: quorum seats approve or reject here. Real mode: decisions are signed in the
// Tide console, so this page only lists requests and links there.
import { useCallback, useEffect, useState } from "react";
import { useTide, TIDE_MODE } from "@/lib/tide";

type CR = {
  id: string;
  actionType: string;
  entityId?: string;
  requestedBy?: string;
  rows?: { USER_ID?: string; ROLE_NAME?: string; ROLE_ID?: string }[];
  status: string;
  threshold?: number;
  authorizationCount?: number;
  approvals?: string[];
  rejections?: string[];
};

export default function QuorumPage() {
  const { authenticated, getValueFromToken, AdminAPI } = useTide();
  const [requests, setRequests] = useState<CR[] | null>(null);
  const [message, setMessage] = useState<{ kind: "ok" | "denied"; text: string } | null>(null);
  const me: string | undefined = authenticated ? getValueFromToken("preferred_username") ?? getValueFromToken("sub") : undefined;
  const status = TIDE_MODE === "simulated" ? "ALL" : "PENDING";

  const load = useCallback(async () => {
    try {
      setRequests((await AdminAPI.fetch(`/admin/realms/${AdminAPI.getRealm()}/iga/change-requests?status=${status}`)) ?? []);
    } catch (e) {
      setRequests([]);
      setMessage({ kind: "denied", text: `Cannot read the change-request inbox: ${e instanceof Error ? e.message : String(e)}` });
    }
  }, [AdminAPI, status]);

  useEffect(() => {
    if (authenticated) load();
  }, [authenticated, load]);

  if (!authenticated) return <p>Log in as a quorum administrator: <code>admin.company</code>, <code>custodian</code> or <code>ethics</code>.</p>;

  async function decide(id: string, decision: "approve" | "reject") {
    setMessage(null);
    try {
      const cr: CR = await AdminAPI.fetch(`/admin/realms/${AdminAPI.getRealm()}/iga/change-requests/${id}/${decision}`, { method: "POST" });
      setMessage({ kind: "ok", text: `${me} ${decision === "approve" ? "approved" : "rejected"}. Request is now ${cr.status}.` });
    } catch (e) {
      setMessage({ kind: "denied", text: e instanceof Error ? e.message : String(e) });
    }
    load();
  }

  return (
    <>
      <h1>Quorum change requests</h1>
      <p>
        Access to genomes only changes when enough independent quorum seats approve. Signed in as <code>{me}</code>.
      </p>
      {TIDE_MODE !== "simulated" && (
        <p className="pending">
          Approve or reject in the <a href="http://localhost:8080/realms/unsellable/tide-console/">Tide console</a>; decisions are signed there.
        </p>
      )}
      {message && <p className={message.kind}>{message.text}</p>}
      {requests === null ? (
        <p>Loading…</p>
      ) : requests.length === 0 ? (
        <p>No change requests.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Request</th>
              <th>Status</th>
              <th>Approvals</th>
              <th>Decisions</th>
              {TIDE_MODE === "simulated" && <th />}
            </tr>
          </thead>
          <tbody>
            {requests.map((cr) => (
              <tr key={cr.id}>
                <td>
                  {cr.requestedBy ? <code>{cr.requestedBy}</code> : "?"} asks to grant{" "}
                  <code>{(cr.rows ?? []).map((r) => r.ROLE_NAME ?? r.ROLE_ID).join(", ")}</code> to{" "}
                  <code>{cr.entityId}</code>
                </td>
                <td className={cr.status === "PENDING" ? "pending" : cr.status === "COMMITTED" ? "ok" : "denied"}>{cr.status}</td>
                <td>
                  {cr.authorizationCount ?? 0} of {cr.threshold ?? "?"}
                </td>
                <td>
                  {(cr.approvals ?? []).map((a) => `✓ ${a}`).join(" ")} {(cr.rejections ?? []).map((r) => `✗ ${r}`).join(" ")}
                </td>
                {TIDE_MODE === "simulated" && (
                  <td>
                    {cr.status === "PENDING" && (
                      <>
                        <button onClick={() => decide(cr.id, "approve")}>Approve</button>{" "}
                        <button onClick={() => decide(cr.id, "reject")}>Reject</button>
                      </>
                    )}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}
