# Where TideCloak fits in Unsellable

The app runs in two modes from the same code:

| Mode | Command | What protects the app |
|---|---|---|
| **TideCloak** | `npm run setup`, then `npm run dev` | Real TideCloak dev server and the Tide Fabric |
| **Simulated** | `npm run dev:sim` | A local stand-in with the same interface: sign-in, roles, quorum approvals and the Fabric's access checks are mocked |

Simulated mode exists because the Tide development network was failing on 22 Oct 2026 (`setUpTideRealm` 500 `Midgard.FinalizeWallet: Not enough orks returned an ok response`, and Tide account creation errors). It needs no Docker and no Tide account, so anyone can run the demo.

How this plan was made: Tide's MCP server (Raziel) was not connected to the coding agent we used. The mapping below comes from the `@tidecloak/nextjs` 0.14.40 type definitions in `app/node_modules` and from calls we made against `tideorg/tidecloak-dev` while setting up the real realm.

## One switch point

Every page calls `useTide()` from [`app/src/lib/tide.ts`](../app/src/lib/tide.ts). It returns `useTideCloak()` from `@tidecloak/nextjs`, or the simulated provider when `NEXT_PUBLIC_TIDE_MODE=simulated`. Both satisfy the same interface ([`app/src/lib/tide-types.ts`](../app/src/lib/tide-types.ts)), so pages do not branch on the mode.

## Mapping

| Concern | Real TideCloak | Simulated stand-in |
|---|---|---|
| Sign-in | `TideCloakContextProvider` + `login()`: Tide enclave sign-in (BYOiD), no password stored by the app or TideCloak | Persona picker at `/sim-login`; one persona per browser tab ([`SimTideCloakProvider.tsx`](../app/src/lib/sim/SimTideCloakProvider.tsx)) |
| Personas and roles | Realm `unsellable` from [`app/init/realm.json`](../app/init/realm.json) and [`tcinit.sh`](../app/init/tcinit.sh): only `maya` holds `_tide_genome.selfencrypt` / `selfdecrypt`; quorum seats hold `tide-realm-admin` | Same personas and roles in [`personas.ts`](../app/src/lib/sim/personas.ts) |
| Role checks in the UI | `hasRealmRole()`, token claims | Same functions over simulated claims from `/api/sim/token/{user}` |
| Sealing a genome | `doEncrypt([{ data, tags: ["genome"] }])`: the Fabric checks `_tide_genome.selfencrypt` | [`fabric.ts`](../app/src/lib/sim/fabric.ts): real AES-GCM in the browser, refuses without the role |
| Opening a genome | `doDecrypt([{ encrypted, tags: ["genome"] }])`: the Fabric checks `_tide_genome.selfdecrypt`; self-decrypt opens only the caller's own data | Same rules: role required, and only the owner can open a record |
| Key custody | Key split across 20 Fabric nodes, 14 needed (`thresholdT`/`thresholdN` in the adapter config); no single party holds it | **Not secure**: key derived in the browser from a constant. Shows the rules, not the custody |
| Granting a role | `AdminAPI.addUserRoles()` → TideCloak parks a `GRANT_ROLES` change request | `POST /api/sim/users/{id}/roles` → change request, HTTP 202 |
| Change-request inbox | `GET /admin/realms/unsellable/iga/change-requests?status=PENDING` (the SDK's `getUserChangeRequests()` calls a removed endpoint and returns 404, so the app reads this one) | `GET /api/sim/change-requests` with the same fields (`actionType`, `entityId`, `authorizationCount`, `threshold`) |
| Approving or rejecting | Quorum admins sign their decision in the Tide console | `/quorum` page; `max(1, floor(N × 0.7))` approvals commit the grant, too many rejections reject it ([`iga.ts`](../app/src/lib/sim/iga.ts)) |
| Server storage | `app/data/genomes.json` holds ciphertext only | Same file and API, with simulated ciphertext (`sim-tide:v1:` prefix) |

## Switching back to real TideCloak

1. `cd app && npm run setup` (creates the realm, users, roles and quorum requests; needs the Tide Fabric to be healthy).
2. `npm run dev` instead of `npm run dev:sim`. Nothing else changes.
3. Ciphertext sealed in simulated mode cannot be opened by real TideCloak; seal the genome again.

## Known gaps of the simulation

- The simulated token is the persona name sent in an `x-sim-user` header; the server trusts it. Real TideCloak verifies tokens signed by a distributed key.
- Quorum decisions in the simulation are a button click, not a signature.
- The threshold formula `max(1, floor(N × 0.7))` comes from our governance design; we have not confirmed it against a live three-admin realm.
