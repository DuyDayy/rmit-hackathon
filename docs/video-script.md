# Video script: Unsellable (target 2:00)

Four parts, as suggested by the organisers: Possibility, Constraint, Prototype, What changes.
"Step" refers to the README Demo walkthrough. Narration only is counted toward the time budget; screen actions happen while speaking.

| Time | Part | Screen | Narration |
|---|---|---|---|
| 0:00–0:15 | Possibility | Title card "Unsellable", then home page | Genetic data drives medical discovery. But today, whoever owns the company owns the keys to your DNA. Unsellable is a genetic data platform where your genome cannot be sold with the company. |
| 0:15–0:35 | Constraint | Slide: 23andMe and UK Biobank headlines (README "What actually happened") | In 2025, a court approved transferring bankrupt 23andMe's customer genetic data to its buyer, and 1.9 million people asked to be deleted. In 2026, UK Biobank paused research access after data appeared for sale online. When people cannot trust who holds the keys, data is pulled out or locked down. |
| 0:35–0:55 | Prototype, step 1 | Log in as `maya`, open My genome, press Seal, then Open | Maya signs in. Her synthetic genome is encrypted in her browser before it leaves, and only her role and her identity can open it again, on her screen. |
| 0:55–1:05 | Prototype, step 3 | Database view page | This is the raw database file on our server. The genome field is ciphertext. There is no key here to unlock it. |
| 1:05–1:25 | Prototype, step 4 | Log in as `admin.acquirer`, Admin, press Export all genomes | Now Acquirer Corp has bought the company and controls every server and admin account. Export all genomes: denied by the Tide Fabric. Downloading the file only gives them ciphertext. |
| 1:25–1:45 | Prototype, steps 5–6 | Press Grant myself genome read access (Pending, 0 of 2), then on the Quorum page: `admin.company` approves (1 of 2), `custodian` and `ethics` reject (REJECTED) | So the acquirer tries to grant itself access. It stays pending. Even using the company's own quorum seat, it gets one approval of the two it needs, because the other seats belong to an independent custodian and an ethics board. They reject it. |
| 1:45–2:00 | What changes | Closing card | Owning the company no longer means owning the keys. Participants can stay in research, and a sale transfers a service, not people's DNA. |

## Notes for recording

- Recording in simulated mode (`npm run dev:sim`): keep the blue "Simulated TideCloak" banner visible, and say once, around 0:35, "TideCloak is simulated here because Tide's development network was down; the same code runs on real TideCloak." Open one browser tab per persona before recording (Log in → pick persona), so no sign-in happens on camera.
- To record again from a clean state: stop the server, delete `app/data/`, start `npm run dev:sim` again.
- Step 2 (consent toggle) is not in the app yet, so it is not in the script. Add it only if the team builds it.
- With real TideCloak, steps 5–6 decisions are signed in the Tide console instead of the app's Quorum page; change the 1:25 narration to "in the Tide console".
- Read the narration aloud with a timer before recording. If it runs over 2:00, cut the second sentence of the Constraint part first.
