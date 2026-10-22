# Unsellable

[![Built with TideCloak](https://tide.org/badges/built-with-tidecloak.svg)](https://tide.org/tidecloak?utm_source=github&utm_medium=readme&utm_campaign=unlocked)

## Project overview

**Unsellable is a genetic data platform where your DNA cannot be sold, transferred or exported with the company, because no admin, acquirer or AI ever holds the key.**

Built with [TideCloak](https://tide.org/tidecloak?utm_source=github&utm_medium=readme&utm_campaign=unlocked).

### 1. Vision & originality

Genetic testing and biobanks power medical discovery, but participants must trust one company forever, including whoever buys it next. Unsellable separates custody from ownership: the company runs the service, while authority over each genome stays with participants and independent custodians. Selling the company sells servers and ciphertext, not access.

### 2. Trust constraint insight

In 2025, a court approved transferring bankrupt 23andMe's customer genetic data to its $305M buyer; 1.9 million people requested deletion. In 2026, UK Biobank paused research access after researchers' data appeared for sale online. Whoever controls the company controls the keys, so people withdraw and custodians lock research down. Remove that single point of control and genetic data stays useful without being for sale.

### 3. Value & impact

Participants can contribute DNA knowing an acquisition, rogue admin or breach cannot take it. Companies offer a verifiable guarantee instead of a privacy policy. Example: Maya's genome stays hers even after "Acquirer Corp" seizes every server.

### 4. Why TideCloak matters

Genomes are sealed with TideCloak's Hermetic E2EE: plaintext only appears in an authorised user's browser, never on our server. Read access needs quorum approval, and independent custodians hold the majority, so an acquirer inheriting admin seats cannot grant itself access. With ordinary permissions, that admin could export everything.

### 5. Prototype & storytelling

Watch for: Maya seals and views her genome; the database holds only ciphertext; Acquirer Corp's admin is denied on "Export all"; its self-granted read access stays pending until the custodian and ethics board refuse. The demo simulates TideCloak because Tide's dev network was down.

## Setup

### Run the demo now: simulated TideCloak (no Docker, no Tide account)

```bash
cd app
npm install
npm run dev:sim
```

Open `http://localhost:3000` and click **Log in** to pick a persona. Each browser tab keeps its own persona, so open one tab per persona. Or run `npm run demo -- --fresh` instead of `npm run dev:sim`: it starts the app with empty demo data and opens a Chrome window with five tabs already signed in (`maya`, `admin.acquirer`, `admin.company`, `custodian`, `ethics`). In this mode TideCloak's sign-in, roles, quorum approvals and the Fabric's access checks are simulated behind the same interface the app uses with real TideCloak; a blue banner says so on every page. To start the demo over, stop the server and delete `app/data/`.

We added this mode because the Tide development network was failing on 22 Oct 2026 (realm license setup and Tide account creation returned errors). [docs/tidecloak-integration-plan.md](docs/tidecloak-integration-plan.md) maps each simulated piece to the TideCloak feature it stands in for. The steps below run the same app against real TideCloak.

### Prerequisites

| Tool | Version | Why |
|---|---|---|
| Docker | Recent stable | Runs the TideCloak development server |
| Node.js | 18.17 or newer | Required by Next.js 14 |
| npm | Bundled with Node.js | Installs dependencies |
| `jq` and `curl` | Any | Used by the realm setup script |
| A modern browser | Chrome, Edge or Firefox | Decryption happens in the browser |

### Quick start: one command

```bash
cd app
npm install
npm run setup
```

[`app/init/setup-all.sh`](app/init/setup-all.sh) runs steps 1 and 2 below, then the parts that follow them. It is safe to re-run: each step checks what is already done and skips it. Whenever a person is needed it opens that persona's own Chrome profile, and waits. Profiles keep separate sessions, so nothing has to be closed between personas, and `npm run as -- <persona>` reopens the app as that persona later:

- once per persona, to create that persona's Tide account (enrollment);
- once for `admin.company`, to approve and commit the pending change requests in the Tide console. These give `custodian` and `ethics` their quorum seats and make `admin.acquirer` an app administrator without a quorum seat.

`npm run setup -- --status` shows what is done without changing anything. The steps below describe the same setup by hand.

### 1. Start TideCloak (development mode)

From the repository root:

```bash
docker run -d --name tidecloak -p 8080:8080 \
  -v "$PWD/.tidecloak-data:/opt/keycloak/data/h2" \
  -e KC_BOOTSTRAP_ADMIN_USERNAME=admin \
  -e KC_BOOTSTRAP_ADMIN_PASSWORD=password \
  tideorg/tidecloak-dev:latest
```

Wait until `http://localhost:8080` responds. These bootstrap credentials are for local development only; the setup script below expects `admin` / `password` (override with `KC_USER` and `KC_PASSWORD`).

### 2. Create the `unsellable` realm

```bash
cd app
npm install
npm run init
```

The script ([`app/init/tcinit.sh`](app/init/tcinit.sh), adapted from the official `@tidecloak/create-nextjs` template) does the following:

1. Creates the realm `unsellable` with web client `unsellable-web` (redirect URI `http://localhost:3000/*`, web origin `http://localhost:3000`), activates the development licence and enables Quorum-Enforced Governance.
2. Creates the six demo users listed below. Only `maya` receives the genome roles `_tide_genome.selfencrypt` and `_tide_genome.selfdecrypt`.
3. Prints an **ACTION REQUIRED** link. Open it and enrol a Tide account for `admin.company`, the first quorum administrator. The script waits, then finishes setup and writes the client adapter config to `app/tidecloak.json` (not committed).

If the script stops with HTTP 500 `TIDE-IDPEXT-VENDOR-KEYGEN_FAILED`, the Tide Fabric had a temporary error. Delete the realm in the admin console and run `npm run init` again.

After the script finishes, enrol the other demo users, then nominate `custodian` and `ethics` as quorum administrators in the Tide console at `http://localhost:8080/realms/unsellable/tide-console/`, so there are **three** in total (see [Governance design](#governance-design-who-sits-in-the-quorum)).

We could not verify the Tide console steps on 22 Oct 2026, because Tide account enrollment kept failing on the development network.

### 3. Run the app

```bash
cd app
npm run dev
```

Open `http://localhost:3000`. If the page says "TideCloak not configured", `app/tidecloak.json` is missing.

There is no seed script: real ciphertext can only be produced in a signed-in browser. Sign in as `maya` and press "Seal genome" to create the first record. The server stores it in `app/data/genomes.json`.

### Demo accounts

| Username | Role in the story | Roles it holds | Can do in the demo |
|---|---|---|---|
| `maya` | Participant | `_tide_genome.selfencrypt`, `_tide_genome.selfdecrypt` | Seal and open her own genome |
| `admin.acquirer` | New owner's administrator after the sale | App admin (`manage-users`, `view-users`, `query-users`, `view-realm`); no genome role, no quorum seat | Try "Export all" (denied) and request read access for itself (pending) |
| `admin.company` | Company administrator; after the sale the acquirer controls it too | Quorum seat 1 (`tide-realm-admin`) | Approve or reject on the Quorum page: one of the two approvals needed |
| `custodian` | Independent data custodian | Quorum seat 2 | Approve or reject access changes |
| `ethics` | Independent ethics board | Quorum seat 3 | Approve or reject access changes |
| `lee` | Researcher, cancer study | Default roles only | Not in the demo (roadmap: read only what the quorum approves) |

Signing in:

- **Simulated mode:** click **Log in** and pick the persona. No password.
- **Real TideCloak:** each persona links its own Tide account during enrollment (`npm run setup` opens the link). The app and TideCloak store no password.

All people, genomes and organisations in this repository are synthetic.

### Troubleshooting

- TideCloak setup issues: ask in the `#support` channel of the [Tide Discord](https://discord.gg/XBMd9ny2q5) with your error and what you tried.
- Integration questions: connect [Raziel, Tide's MCP server](https://docs.tide.org/ai-agent-pack), to your coding agent.

---

# Detailed documentation

The sections below go deeper than the 300-word overview, for judges and reviewers who want the full reasoning.

## Contents

- [The problem in one picture](#the-problem-in-one-picture)
- [What actually happened](#what-actually-happened)
- [Problem statement](#problem-statement)
- [What Unsellable makes possible](#what-unsellable-makes-possible)
- [Who uses it](#who-uses-it)
- [How it works](#how-it-works)
- [TideCloak features we rely on](#tidecloak-features-we-rely-on)
- [Governance design: who sits in the quorum](#governance-design-who-sits-in-the-quorum)
- [Threat model](#threat-model)
- [Would it work without TideCloak?](#would-it-work-without-tidecloak)
- [Demo walkthrough](#demo-walkthrough)
- [Data model](#data-model)
- [Prototype status](#prototype-status)
- [Limitations and open questions](#limitations-and-open-questions)
- [Roadmap](#roadmap)
- [How we built it](#how-we-built-it)
- [Team](#team)
- [References](#references)

## The problem in one picture

Think of a safe deposit box at a shop.

- **Today:** the shop owner keeps a master key. If the shop is sold, the master key is sold with it, and the new owner can open any box.
- **With Unsellable:** no complete key exists anywhere. Opening a box for anyone other than its owner needs signatures from two of three independent keyholders: the shop, an outside custodian and an ethics board. If the shop is sold, the new owner inherits one signature, which is not enough.

Genetic data makes this especially serious:

- **It cannot be changed.** A leaked password can be reset; a leaked genome cannot.
- **It is not only yours.** Your DNA reveals information about parents, siblings and children who never took a test.
- **It is valuable.** Large genetic datasets are raw material for drug discovery, so there is always a buyer.

## What actually happened

### 23andMe: legal transfer, not a hack

| When | What happened |
|---|---|
| 2023 | A months-long breach exposed personal and genetic data of 6.9 million customers. |
| March 2025 | 23andMe filed for bankruptcy and put the company, including the genetic data of its 15 million customers, up for sale. |
| By June 2025 | About 1.9 million people, roughly 15% of customers, asked for their genetic data to be deleted. |
| June 2025 | More than two dozen states sued 23andMe to challenge the sale of customers' private data. |
| June 2025 | TTAM Research Institute, a nonprofit led by the former CEO, outbid Regeneron. |
| July 2025 | The bankruptcy court approved the $305M purchase **and the transfer of customers' genetic data** to the buyer, overruling the states' objections. |

Nothing here required an attacker. The data changed hands because the company did. Customers' only real option was to delete their data, which also removed it from research.

### UK Biobank: approved access, then a lockdown

In April 2026, UK Biobank data held by three research institutions was offered for sale on a site owned by Alibaba. The de-identified data covered all 500,000 volunteers. UK Biobank temporarily paused researcher access while it investigated.

### The common pattern

When people cannot trust who controls the keys, the data is either **pulled out** (23andMe deletions) or **locked down** (UK Biobank's pause). Both outcomes slow medical research.

## Problem statement

> Today, whoever owns the company owns the keys. Every privacy promise is only as durable as the company's ownership: if the company is sold, goes bankrupt or is taken over, the promise changes hands with it. How can a company run a genetic data service without the power to unlock people's DNA being part of what it can sell?

## What Unsellable makes possible

| Today | With Unsellable |
|---|---|
| A privacy policy is a promise that the next owner can reinterpret | Custody is enforced by cryptography and governance that the next owner does not control |
| Participants' safest choice is to delete their data | Participants can stay in research because exit is not their only protection |
| Custodians respond to misuse by shutting down access for everyone | Access is granted per decision by independent parties, so trust does not hinge on one operator |
| Acquirers price in the database as an asset | Acquirers buy a service, not unrestricted access to genomes |

## Who uses it

| Persona | Need | What Unsellable gives them |
|---|---|---|
| **Maya, participant** | Contribute to research without her DNA becoming a sellable asset | Her genome is sealed; reading it requires her session or an independent quorum decision |
| **Dr. Lee, researcher** | Access to well-governed data for a cancer study | Access granted by named, independent approvers, which is easier to defend to ethics committees and participants |
| **Genetic testing startup** | Win customers who saw what happened to 23andMe | A guarantee customers can verify rather than a policy they must trust |
| **Independent custodian and ethics board** | Oversight that cannot be bypassed | A required signature on every access change |

## How it works

### Architecture

```mermaid
flowchart LR
    P[Participant browser] -- seal and open genome via TideCloak SDK --> F[Tide Cybersecurity Fabric]
    P -- stores ciphertext only --> S[Unsellable server and database]
    R[Researcher browser] -- open only if access was granted --> F
    A[Company or acquirer admin] -- request access changes --> T[TideCloak IAM]
    Q[Quorum: company, custodian, ethics board] -- approve or reject --> T
    T -- quorum-approved roles --> F
```

Key properties:

- The **server and database only ever store ciphertext**. They have no key to decrypt it.
- **Decryption happens in the browser** of an authorised user. The Fabric re-encrypts the result to that user's session key, so plaintext never exists on a server.
- **Who may read what** is defined by roles that can only change through **quorum approval**.

### Flow 1: Maya seals her genome

```mermaid
sequenceDiagram
    participant M as Maya browser
    participant T as TideCloak
    participant F as Tide Fabric
    participant S as Unsellable server
    M->>T: Sign in
    T-->>M: Session with genome encrypt and decrypt roles
    M->>F: Encrypt genome field
    F-->>M: Ciphertext
    M->>S: Store ciphertext
    Note over S: Database never sees plaintext
```

### Flow 2: Acquirer Corp tries to take the data

```mermaid
sequenceDiagram
    participant X as Acquirer admin browser
    participant T as TideCloak
    participant F as Tide Fabric
    participant Q as Quorum approvers
    X->>F: Decrypt all genomes
    F-->>X: Denied, no approved read access
    X->>T: Grant myself read access
    T-->>X: Change request pending, 0 of 2 approvals
    T->>Q: Ask custodian and ethics board
    Q-->>T: Rejected
    Note over X: Owning the company does not mean owning the keys
```

## TideCloak features we rely on

| TideCloak feature | Where it appears in Unsellable | What it guarantees |
|---|---|---|
| **Hermetic E2EE** | Sealing and opening genome fields | Plaintext exists only in the authorised user's browser; servers, admins, cloud providers and Tide cannot decrypt |
| **Role-gated encrypt and decrypt** | `_tide_genome.selfencrypt` and `_tide_genome.selfdecrypt` | Encrypt and decrypt endpoints check for the matching role before running |
| **Quorum-Enforced Governance** | Any change to who may read genomes | Granting these roles is a governed change that goes through quorum approval instead of applying immediately |
| **Ineffable keys on the Fabric** | All cryptographic operations | Each key is split across 20 nodes and any operation needs 14 of them (`thresholdT` 14 of `thresholdN` 20 in our realm's adapter config), so no single node, admin or server holds a whole key |
| **Tamper-proof authorization** | Every request to the Fabric | Tokens are signed by a distributed key, so a compromised server cannot forge permissions |
| **BYOiD authentication** | Sign-in for every persona | No password hash stored by the app or TideCloak |

## Governance design: who sits in the quorum

TideCloak's quorum threshold for administrative changes is roughly 70% of nominated administrators: `threshold = max(1, floor(N × 0.7))`.

| Number of admins | Threshold | Seat split | Can the company (or acquirer) act alone? |
|---|---|---|---|
| 1 | 1 | Company only | **Yes**, the design fails |
| 2 | 1 | Company and custodian | **Yes**, either admin alone meets the threshold |
| **3** | **2** | **Company, custodian, ethics board** | **No**, at least one independent party must agree |
| 5 | 3 | Company plus four independent parties | No, at least two independent parties must agree |

We use **three** administrators. The company keeps a seat so it can operate the service, but independent parties hold the majority. When the company is sold, the acquirer inherits one seat out of three.

In the prototype, all three quorum accounts are created by our team on one machine to simulate independent organisations. In production, each seat would belong to a separate legal entity, for example a data trust and a university ethics board.

## Threat model

| Actor | Ordinary app | Unsellable | Why |
|---|---|---|---|
| Database thief | Gets genomes | Gets ciphertext | Data is sealed before it reaches the database |
| Our own server, fully compromised | Attacker reads data and keys | Attacker finds no keys and no plaintext | The server holds no decryption authority |
| Rogue company admin | Queries and exports everything | Cannot decrypt; cannot grant itself access alone | Read access needs quorum approval |
| **Acquirer after a sale** | Inherits full access | Inherits one quorum seat out of three | Independent parties hold the majority |
| A single Fabric node or Tide itself | Not applicable | Cannot decrypt | Keys are split; a threshold of independent nodes is required |
| Company plus one colluding custodian | Full access | **Not prevented** | Two of three approvals meet the threshold |
| Approved researcher who copies data | Full copy | **Not prevented** | Decrypted data on an authorised screen cannot be recalled |

Unsellable removes **unilateral** control. It does not remove the possibility of collusion among enough independent parties, or misuse by someone already granted access.

## Would it work without TideCloak?

The challenge asks whether the app would work exactly the same with ordinary login and backend permissions. It would not:

| Scenario | Ordinary login + backend permissions | Unsellable with TideCloak |
|---|---|---|
| Acquirer opens the admin panel and grants itself access | Takes effect immediately | Stays pending until the quorum approves |
| Acquirer bypasses the app and queries the database | Reads plaintext or finds the key next to it | Reads ciphertext; no key exists on the server |
| Acquirer edits the server code to skip permission checks | Permission checks disappear | Authority lives in the Fabric, outside the server |
| A privacy policy is rewritten after the sale | Users must accept or leave | The governance rules require the same independent approvals |

## Demo walkthrough

Video: [`demo.mp4`](./demo.mp4) (one minute, no narration, recorded in simulated mode).

Approximate timestamps: 0:00 Maya seals and opens her genome · 0:10 database view, ciphertext only · 0:20 acquirer export denied, self-grant pending (0 of 2) · 0:30 quorum votes · 0:40 request rejected · 0:50 acquirer still denied.

| Step | Who | Action | Expected result |
|---|---|---|---|
| 1 | Maya | Signs in and opens "My genome" | Her synthetic genome is decrypted in her browser |
| 2 | Maya | Sets consent: cancer research on, commercial AI training off | Not in the prototype yet (planned) |
| 3 | Anyone | Opens the database file | Genome field is ciphertext only |
| 4 | `admin.acquirer` | Clicks "Export all genomes" | **Denied** by the Fabric |
| 5 | `admin.acquirer` | Tries to grant itself read access | **Pending**: 0 of 2 approvals |
| 6 | `admin.company`, `custodian`, `ethics` | Review the request. The acquirer now also controls the company's seat and approves (1 of 2); the custodian and ethics board reject | **Rejected**, so the acquirer still cannot read |

The key interaction for judges is **steps 4 to 6**: full ownership of the company, its servers and its quorum seat still does not translate into the power to read anyone's DNA.

In simulated mode (`npm run dev:sim`) sign-in is a persona picker and step 6 happens on the app's **Quorum** page; with real TideCloak the quorum signs its decisions in the Tide console.

## Data model

All data is synthetic. A participant record as stored on the server:

```json
{
  "participantId": "p-0001",
  "displayName": "Maya (synthetic)",
  "consent": {
    "cancerResearch": true,
    "commercialAiTraining": false
  },
  "genome": "<TideCloak ciphertext>",
  "updatedAt": "2026-10-22T13:00:00+07:00"
}
```

Before sealing, the synthetic genome is a short list of made-up markers, for example:

```json
{
  "markers": [
    { "id": "rs0000001", "genotype": "A/G" },
    { "id": "rs0000002", "genotype": "C/C" },
    { "id": "rs0000003", "genotype": "T/T" }
  ],
  "note": "Synthetic data. No medical meaning."
}
```

Consent flags are stored in plaintext in the prototype so the app can display them. Making them tamper-proof (signed by the participant) is on the roadmap.

## Prototype status

| Capability | Simulated mode (`npm run dev:sim`) | Real TideCloak |
|---|---|---|
| Realm `unsellable` with six personas; genome roles held only by `maya` | Same personas and roles | Setup script creates them; enrolling Tide accounts failed on 22 Oct (Tide dev network errors) |
| Sign-in for the five demo personas (`lee` exists but is not in the demo) | Implemented (persona picker) | Wired through `@tidecloak/nextjs`, not demonstrated |
| Genome sealed in the browser; database stores ciphertext only | Implemented (simulated Fabric: AES-GCM, role-gated, owner-bound) | Wired to `doEncrypt` with tag `genome`, not demonstrated |
| Participant views her own genome | Implemented | Wired to `doDecrypt`, not demonstrated |
| Acquirer "Export all" denied | Implemented | Wired, not demonstrated |
| Acquirer self-grant of read access pending quorum | Implemented (0 of 2 approvals) | Wired to the IGA change-request inbox, not demonstrated |
| Three-seat quorum (company, custodian, ethics board) | Implemented (Quorum page, 2 of 3 to commit) | Setup script requests the seats; not demonstrated |
| Researcher access approved by quorum | Planned | Planned |
| Consent preferences enforced cryptographically | Planned | Planned |
| AI research agent limited to approved scope | Planned | Planned |

## Limitations and open questions

We prefer to state these plainly:

1. **Collusion is not prevented.** The company plus one independent custodian meets the threshold. A larger quorum raises the bar but cannot remove it.
2. **Decrypted data cannot be recalled.** Once an approved researcher opens a record, they can copy it. This is the same weakness behind the UK Biobank incident; Unsellable controls who gets access, not what they do afterwards.
3. **Plaintext lives in the browser.** Any script running on an authorised user's page could read decrypted data. A production version needs a strict content security policy and no third-party trackers.
4. **Off-boarding from Tide.** Tide documents a Ragnarok Protocol that lets a customer reconstruct and export its authority keys when leaving Tide. We have asked Tide who can trigger it and whether it requires quorum approval. If a company owner could trigger it alone, Unsellable's guarantee would weaken to "an acquirer cannot do this silently".
5. **Cross-user reading.** The field roles are named `selfencrypt` and `selfdecrypt`. We are confirming with Tide the recommended way for a quorum-approved researcher to read another user's record (for example a Forseti policy).
6. **Simulated independence.** In the prototype, our team operates all three quorum seats. Real independence requires separate organisations. The prototype also runs on Tide's development network, whose 20 nodes are hosted in a single cloud environment.
7. **Consent flags are informational.** In the prototype they are not yet bound cryptographically to access decisions.
8. **The demo runs on simulated TideCloak.** The Tide development network failed during our build, so the recorded demo uses simulated mode. It enforces the same rules (role-gated, owner-bound encryption; 2-of-3 quorum for role grants), but its key is derived in the browser and its server trusts the persona name, so it shows the rules, not the custody guarantees. Those come only from real TideCloak.

## Roadmap

| Next step | Why it matters |
|---|---|
| Researcher access: Dr. Lee requests a study, the custodian and ethics board approve, and Lee opens only approved records in their browser | Shows the legitimate path that the quorum exists to allow, not only the one it blocks |
| Forseti contract for research access with `ForbidSelfApproval` and `RequireDistinctOrgs` | Guarantees approvals come from different organisations and nobody approves their own request |
| Purpose-bound access (consent purpose must match the study purpose) | Maya's "no commercial AI training" choice becomes enforceable, not just recorded |
| Scoped AI research agent | An agent can analyse approved records but cannot export raw genomes, even under prompt injection |
| Participant council seat in the quorum | Participants gain a direct voice in access decisions |
| Confidential computing for aggregate analysis | Researchers receive results without ever seeing individual genomes |
| Public, verifiable access log | Participants can check every decision made about their data |

## How we built it

- **TideCloak** for identity, field-level encryption and quorum governance.
- **Next.js 14** web app using the `@tidecloak/nextjs` SDK (0.14.40) for sign-in, encryption and admin requests.
- **AI coding agent** for the integration, planned from the `@tidecloak/nextjs` SDK types because Tide's MCP server (Raziel) was not connected ([integration plan](docs/tidecloak-integration-plan.md)).
- **Simulated TideCloak mode** behind the same `useTide()` interface, so the demo runs while the Tide development network is down ([integration plan](docs/tidecloak-integration-plan.md)).
- **Synthetic data only.** No real genetic or personal data is used anywhere in this repository.

## Team

- Nguyễn Nhất Duy
- Nguyễn Thanh Nguyên
- Nguyên Phương Quyên
- Nguyễn Hùng Vương

## References

1. TechCrunch, "23andMe says 15% of customers asked to delete their genetic data since bankruptcy" (June 2025). https://techcrunch.com/?p=3017740
2. BioSpace, "Regeneron Backs Off 23andMe, Losing Bid to Former CEO" (2025). https://www.biospace.com/business/regeneron-backs-off-23andme-losing-bid-to-former-ceo
3. Mealey's, "Bankruptcy Judge Approves $305 Million Purchase Of 23andMe And Data Transfer" (July 2025). https://www.mealeys.com/mealeys/articles/2362409
4. NPR, "23andMe is filing for bankruptcy. Here's what it means for your genetic data" (March 2025). https://www.kpbs.org/news/science-technology/2025/03/24/23andme-is-filing-for-bankruptcy-heres-what-it-means-for-your-genetic-data
5. Times Higher Education, "UK Biobank access suspended after major health data breach" (April 2026). https://www.timeshighereducation.com/node/742589
6. TechRepublic, "Health Records of 500,000 UK Biobank Volunteers Listed Online in China" (April 2026). https://www.techrepublic.com/article/uk-biobank-data-500k-sale-china/
7. TideCloak docs, "Hermetic End-to-End Encryption". https://docs.tide.org/Core-Concepts/hermetic-e2ee
8. TideCloak docs, "Forseti Programmable Policy Engine". https://docs.tide.org/Core-Concepts/forseti-engine
9. Tide, "How Tide Works". https://tide.org/howtideworks
10. Tide, "UNLOCKED: Challenge 2 of the RMIT hackathon". https://tide.org/unlocked
