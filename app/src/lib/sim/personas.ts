// Simulated TideCloak realm: the same personas and roles that app/init/realm.json and
// app/init/tcinit.sh provision in the real realm `unsellable`.

export const REALM = "unsellable";

export const GENOME_ROLES = ["_tide_genome.selfencrypt", "_tide_genome.selfdecrypt"];
// Composite default role of the real realm (default-roles-unsellable).
export const DEFAULT_ROLES = ["appUser", "_tide_message.selfencrypt", "_tide_message.selfdecrypt"];

// realm-management client roles.
export const QUORUM_ROLE = "tide-realm-admin";
export const APP_ADMIN_ROLES = ["manage-users", "view-users", "query-users", "view-realm"];

export type Persona = {
  username: string;
  displayName: string;
  story: string;
  realmRoles: string[];
  clientRoles: string[];
};

export const PERSONAS: Persona[] = [
  {
    username: "maya",
    displayName: "Maya",
    story: "Participant. Seals and opens her own genome.",
    realmRoles: [...DEFAULT_ROLES, ...GENOME_ROLES],
    clientRoles: [],
  },
  {
    username: "admin.acquirer",
    displayName: "Acquirer Corp admin",
    story: "New owner's administrator after the sale. Full app admin, no quorum seat.",
    realmRoles: [...DEFAULT_ROLES],
    clientRoles: [...APP_ADMIN_ROLES],
  },
  {
    username: "admin.company",
    displayName: "Company admin",
    story: "Runs the service. Quorum seat 1 of 3.",
    realmRoles: [...DEFAULT_ROLES],
    clientRoles: [QUORUM_ROLE, ...APP_ADMIN_ROLES],
  },
  {
    username: "custodian",
    displayName: "Independent data custodian",
    story: "Quorum seat 2 of 3.",
    realmRoles: [...DEFAULT_ROLES],
    clientRoles: [QUORUM_ROLE],
  },
  {
    username: "ethics",
    displayName: "Independent ethics board",
    story: "Quorum seat 3 of 3.",
    realmRoles: [...DEFAULT_ROLES],
    clientRoles: [QUORUM_ROLE],
  },
  {
    username: "lee",
    displayName: "Dr. Lee, researcher",
    story: "Cancer study. Reads only what the quorum approves (roadmap).",
    realmRoles: [...DEFAULT_ROLES],
    clientRoles: [],
  },
];

export const findPersona = (username: string) => PERSONAS.find((p) => p.username === username);

// Quorum threshold used in the README governance design: max(1, floor(N x 0.7)).
// With three seats (company, custodian, ethics) two approvals are needed.
export const quorumThreshold = (seats: number) => Math.max(1, Math.floor(seats * 0.7));
