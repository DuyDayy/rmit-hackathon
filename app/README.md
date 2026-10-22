# app

Next.js 14 frontend for Unsellable, using `@tidecloak/nextjs` 0.14.40.

## Run

1. Put the client adapter exported from TideCloak (task A6) at `app/tidecloak.json`. It is not committed. Without it every page shows "TideCloak not configured".
2. In the TideCloak client, allow redirect URI `http://localhost:3000/*` and web origin `http://localhost:3000`.
3. Start the app:

```bash
cd app
npm install
npm run dev   # http://localhost:3000
```

## Pages

| Route | Persona | Plan task |
|---|---|---|
| `/` | anyone | Navigation |
| header | all | B2: log in or out, username, genome roles held |
| `/genome` | `maya` | B3: "Seal genome" encrypts in the browser (tag `genome`) and POSTs ciphertext; "Open" fetches and decrypts |
| `/admin` | `admin.acquirer` | B4: "Export all genomes" tries to decrypt every record and shows Denied. B5: "Grant myself genome read access" calls `addUserRoles`, then lists pending change requests |
| `/database` | anyone | C3: prints `app/data/genomes.json` raw; the `genome` field is ciphertext |

## API (stream C)

- `POST /api/genome`: body `{participantId, genome: "<ciphertext>"}`, stored in `app/data/genomes.json` (override with `GENOME_DB_PATH`).
- `GET /api/genome`: every record.
- `GET /api/genome/:id`: one record.
- `GET /api/export-all`: C4, downloads the whole store as `unsellable-export.json` (ciphertext only).
- `GET /api/adapter`: serves `tidecloak.json` to the browser.

The synthetic genome (C2) is a constant in `src/lib/syntheticGenome.ts` and only reaches the server encrypted. There is no seed script: real ciphertext can only be made in a signed-in browser, so seed by having `maya` press "Seal genome".
