# app

Next.js 14 frontend for Unsellable, using `@tidecloak/nextjs` 0.14.40.

## Run

**Simulated TideCloak** (no Docker, no Tide account):

```bash
cd app
npm install
npm run dev:sim   # http://localhost:3000, Log in = persona picker
```

**Real TideCloak:**

1. Run `npm run setup` (see the root README, Setup). It creates the realm, the client `unsellable-web` with redirect URI `http://localhost:3000/*` and web origin `http://localhost:3000`, and the demo users, then writes the client adapter to `app/tidecloak.json`. That file is not committed. Without it every page shows "TideCloak not configured".
2. Start the app:

```bash
cd app
npm run dev   # http://localhost:3000
```

Pages call `useTide()` ([src/lib/tide.ts](src/lib/tide.ts)), which returns the real `useTideCloak()` or the simulation; see [docs/tidecloak-integration-plan.md](../docs/tidecloak-integration-plan.md).

## Pages

| Route | Persona | Plan task |
|---|---|---|
| `/` | anyone | Navigation |
| header | all | B2: log in or out, username, genome roles held |
| `/genome` | `maya` | B3: "Seal genome" encrypts in the browser (tag `genome`) and POSTs ciphertext; "Open" fetches and decrypts |
| `/admin` | `admin.acquirer` | B4: "Export all genomes" tries to decrypt every record and shows Denied. B5: "Grant myself genome read access" calls `addUserRoles`, checks the role did not land, and shows the pending request's approvals from the IGA inbox |
| `/quorum` | `admin.company`, `custodian`, `ethics` | Change-request inbox with approvals and decisions. Simulated mode: approve or reject here. Real mode: links to the Tide console |
| `/database` | anyone | C3: prints `app/data/genomes.json` raw; the `genome` field is ciphertext |
| `/sim-login` | anyone | Simulated mode only: persona picker that stands in for Tide sign-in |

## API (stream C)

- `POST /api/genome`: body `{participantId, genome: "<ciphertext>"}`, stored in `app/data/genomes.json` (override with `GENOME_DB_PATH`).
- `GET /api/genome`: every record.
- `GET /api/genome/:id`: one record.
- `GET /api/export-all`: C4, downloads the whole store as `unsellable-export.json` (ciphertext only).
- `GET /api/adapter`: serves `tidecloak.json` to the browser.
- `/api/sim/*` (simulated mode only, 404 otherwise): `token/{user}` claims, `users/{id}/roles` GET and governed POST (202 change request), `change-requests` inbox, `change-requests/{id}/approve|reject`, `reset`. State in `app/data/sim-iga.json` (override with `SIM_IGA_PATH`).

The synthetic genome (C2) is a constant in `src/lib/syntheticGenome.ts` and only reaches the server encrypted. There is no seed script: real ciphertext can only be made in a signed-in browser, so seed by having `maya` press "Seal genome".
