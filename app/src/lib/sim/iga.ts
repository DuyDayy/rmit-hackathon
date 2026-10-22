// Simulated TideCloak governance (IGA), server side. Mirrors /admin/realms/{realm}/iga/change-requests:
// once governance is on, a role grant is parked as a PENDING change request and only takes effect
// when enough quorum administrators approve it. State lives in app/data/sim-iga.json.
import { promises as fs } from "fs";
import path from "path";
import { PERSONAS, QUORUM_ROLE, APP_ADMIN_ROLES, findPersona, quorumThreshold } from "./personas";

export type ChangeRequest = {
  id: string;
  actionType: "GRANT_ROLES";
  entityType: "USER";
  entityId: string;
  rows: { USER_ID: string; ROLE_NAME: string }[];
  requestedBy: string;
  status: "PENDING" | "COMMITTED" | "REJECTED";
  threshold: number;
  authorizationCount: number;
  approvals: string[];
  rejections: string[];
  createdAt: string;
  resolvedAt?: string;
};

type Store = {
  realmRoles: Record<string, string[]>;
  clientRoles: Record<string, string[]>;
  changeRequests: ChangeRequest[];
};

const STORE_PATH = path.resolve(process.cwd(), process.env.SIM_IGA_PATH ?? "data/sim-iga.json");

function initialStore(): Store {
  return {
    realmRoles: Object.fromEntries(PERSONAS.map((p) => [p.username, [...p.realmRoles]])),
    clientRoles: Object.fromEntries(PERSONAS.map((p) => [p.username, [...p.clientRoles]])),
    changeRequests: [],
  };
}

async function load(): Promise<Store> {
  try {
    return JSON.parse(await fs.readFile(STORE_PATH, "utf8"));
  } catch {
    return initialStore();
  }
}

async function save(store: Store) {
  await fs.mkdir(path.dirname(STORE_PATH), { recursive: true });
  await fs.writeFile(STORE_PATH, JSON.stringify(store, null, 2));
}

export class SimError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

const quorumSeats = (s: Store) => Object.keys(s.clientRoles).filter((u) => s.clientRoles[u].includes(QUORUM_ROLE));
const isAppAdmin = (s: Store, u: string) =>
  (s.clientRoles[u] ?? []).some((r) => r === QUORUM_ROLE || APP_ADMIN_ROLES.includes(r));

export async function claimsFor(username: string) {
  const s = await load();
  const p = findPersona(username);
  if (!p) throw new SimError(404, `unknown user ${username}`);
  return {
    sub: p.username,
    preferred_username: p.username,
    name: p.displayName,
    realm_access: { roles: s.realmRoles[p.username] ?? [] },
    resource_access: { "realm-management": { roles: s.clientRoles[p.username] ?? [] } },
  };
}

export async function userRealmRoles(actor: string, userId: string) {
  const s = await load();
  if (actor !== userId && !isAppAdmin(s, actor)) throw new SimError(403, "view-users required");
  return (s.realmRoles[userId] ?? []).map((name) => ({ name }));
}

// POST role-mappings: governed, so it parks a change request (HTTP 202) instead of applying.
export async function requestGrant(actor: string, userId: string, roles: { name: string }[]) {
  const s = await load();
  if (!isAppAdmin(s, actor)) throw new SimError(403, "manage-users required");
  if (!findPersona(userId)) throw new SimError(404, `unknown user ${userId}`);
  const missing = roles.map((r) => r.name).filter((n) => !(s.realmRoles[userId] ?? []).includes(n));
  if (missing.length === 0) return null;
  const cr: ChangeRequest = {
    id: crypto.randomUUID(),
    actionType: "GRANT_ROLES",
    entityType: "USER",
    entityId: userId,
    rows: missing.map((ROLE_NAME) => ({ USER_ID: userId, ROLE_NAME })),
    requestedBy: actor,
    status: "PENDING",
    threshold: quorumThreshold(quorumSeats(s).length),
    authorizationCount: 0,
    approvals: [],
    rejections: [],
    createdAt: new Date().toISOString(),
  };
  s.changeRequests.push(cr);
  await save(s);
  return cr;
}

export async function listChangeRequests(actor: string, status?: string) {
  const s = await load();
  if (!isAppAdmin(s, actor)) throw new SimError(403, "admin role required");
  return s.changeRequests.filter((cr) => !status || status === "ALL" || cr.status === status).reverse();
}

// A quorum administrator approves or rejects. The grant commits only at the threshold.
export async function decide(actor: string, id: string, decision: "approve" | "reject") {
  const s = await load();
  const seats = quorumSeats(s);
  if (!seats.includes(actor)) throw new SimError(403, `${actor} holds no quorum seat`);
  const cr = s.changeRequests.find((c) => c.id === id);
  if (!cr) throw new SimError(404, "change request not found");
  if (cr.status !== "PENDING") throw new SimError(409, `change request is ${cr.status}`);
  if (cr.approvals.includes(actor) || cr.rejections.includes(actor)) throw new SimError(409, `${actor} already decided`);

  if (decision === "approve") cr.approvals.push(actor);
  else cr.rejections.push(actor);
  cr.authorizationCount = cr.approvals.length;

  if (cr.approvals.length >= cr.threshold) {
    for (const row of cr.rows) {
      const held = (s.realmRoles[row.USER_ID] ??= []);
      if (!held.includes(row.ROLE_NAME)) held.push(row.ROLE_NAME);
    }
    cr.status = "COMMITTED";
    cr.resolvedAt = new Date().toISOString();
  } else if (cr.rejections.length > seats.length - cr.threshold) {
    // Not enough seats left to reach the threshold.
    cr.status = "REJECTED";
    cr.resolvedAt = new Date().toISOString();
  }
  await save(s);
  return cr;
}

export async function resetStore() {
  await save(initialStore());
}
