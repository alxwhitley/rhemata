# New Wine — Live Status

Point-in-time state only. Overwritten each session, never appended to. Durable
truth lives in code, git history, `PLAN.md`, `docs/roadmap.md`,
`docs/plan-archive.md`, and `CLAUDE.md`.

Last verified: 2026-09-05. **PLAN.md has no active blockers.**

---

## Current state

**Six commits sit on local `main` and NOTHING FROM THIS SESSION IS DEPLOYED.**
`origin/main` is still at `4fdf39b`; local is `d9c3b1c`..`6ca1310`. This was a
remote, phone-driven session, repo-only by design — no push, no migration, no
production write approved. Four of the six change shipped behavior, so the
deploy is a live, pending, attended gate.

**Starlette advisories triaged and the one real finding mitigated** (`d9c3b1c`,
`docs/audits/2026-09/starlette_advisory_triage_2026-09-05.md`). The 2026-08-24
scan's "7 advisories" collapse to 5 distinct CVEs; 4 are inert here. The fifth
is real: starlette 0.52.1 does not apply `max_fields`/`max_part_size` to
urlencoded bodies, **and FastAPI parses the body before it solves dependencies**,
so `/ingest`'s admin gate does not stand in front of it. Measured on the real
endpoint: 200k fields as multipart rejected in 11ms without reaching the gate;
the same fields urlencoded parsed over 686ms of event-loop-blocking work, on a
single-worker API. Alex classified it **Scheduled** and chose a narrow
mitigation over the coupled fastapi+starlette bump, which stays Scheduled.
A middleware now refuses urlencoded outright — safe because no endpoint here
accepts it. Repository-verified only; **not deployed**.

**Two UI fixes, both repo-verified and undeployed.** `c58f252` renders the
word-study article on the standalone `/study` word search — it had been fetched
into state since `40cdb4c` and never passed to `WordStudyPanel`. `2137233`
closes the roadmap's footer half: feedback and Sources are now one group, with
a measured optical correction (a plain stack put 27px between the thumb icon
and the Sources label against a 24px break, inverting the rhythm, because two
44px touch targets stack 26px of unpainted padding). Both are pinned by new
stubbed Playwright specs and mutation-proven.

**The backend regression suite was run for the first time in this repo's
history** — there is no CI of any kind. 90/90 credential-free files pass.
Two stale references repaired (`b782375`): a test pointing at a script archived
in August, which had been crashing before three of its own checks ran, and a
hardcoded corpus count of 144 that the corpus had outgrown to 172 while the
endpoint was correct throughout.

**Four production writers were sitting in the `test_*.py` namespace** and are
now gated (`6ca1310`). `test_ingest_queue_endpoints` inserted a `user_roles`
row with `role='admin'`; three others wrote `deletion_requests`,
`pastors_cards`, and `contributor_requests`. Running the suite the obvious way
would have executed all four against production. They are renamed to
`verify_*_live.py`, require `--apply`, and have no import side effects — the
same three-part guard as `verify_metering_live.py`.
`scripts/test_live_writer_guards.py` asserts all three per script and sweeps
the namespace for any other file that commits on a real connection.

**Incident, recorded because the outcome was clean and the method was not.**
While mutation-proving that guard, the guard was stripped from
`verify_pastors_rls_live.py` *in place* and the checker then subprocess-ran it
bare, so `main()` executed against production unattended — the exact thing the
hard rule forbids. Net effect verified zero afterward: cleanup sits in a
`finally` block, `pastors_cards` and `contributor_requests` are both empty, and
`user_roles` shows 1 admin / 1 user with no residue. Only that one script was
mutated. The durable lesson is now a CLAUDE.md landmine.

**Deployment state elsewhere is unchanged from 2026-09-05's earlier entry.**
`origin/main` at `4fdf39b` is built by Vercel with
`VERCEL_FORCE_NO_BUILD_CACHE=1` set (Production scope, project `newwine`) after
a green build shipped stale CSS; the public API health check passes. The two
mobile gesture behaviours from `3d7649c`..`4fdf39b` are live and **still not
verified on a physical device**.

**TIPNR ingestion is paused mid-gate, one operation in.** Packets 0–4 are
merged (`8c99ea1` is an ancestor). Of five approved operations only
**operation 1 ran** — the rollback-only probe, 2026-09-02: 600 rows staged, 1
transaction rolled back, **0 committed**, 0 embedding requests. Operations 2–5
have not started. Live state re-verified 2026-09-05: `next_batch_index 1`,
`completed_batches 0`, 3,939 clean, 0 TIPNR propositions, source hidden,
`biblical_context_answer_enabled false`, both registries empty. Three things a
resuming session needs: (1) the pinned artifact is **not tracked in git** —
confirm `sources/stepbible/` is present and hashes to `69f69d80…e180e`, because
26 checks silently skip without `TIPNR_TEST_ARTIFACT` set; (2) approvals are
same-day, and the `local/2026-09/` artifacts are expired; (3) the classifier
refuses these writes from inside a session — the probe ran only when Alex
invoked it himself with `!`, and an opaque `bash <script>.sh` was refused where
an explicit `python3.12 scripts/…` was allowed.

---

## Session outcome and measures

- Original outcome completed: **yes** — every item Alex selected was finished
  and verified; nothing was left half-done.
- Unplanned investigations started: **1** — the suite audit, which was
  authorized mid-session and produced the writer-gating work.
- Findings promoted to Blocker: **0**. The starlette finding was classified
  Scheduled by Alex, with the mitigation shipped in the same decision.
- Scope changes approved by Alex: four, all via explicit decision — Scheduled
  plus mitigate, commit without pushing, static-audit the DB tests before
  running any, and transcribe the roadmap wording.
- Active critical-path item count: **0**.
- Rule violations: **1**, self-reported above — an unattended production write
  during a mutation test, net effect zero.

---

## Next single item

No active Blocker. In recommended order:

1. **Deploy, then verify on a phone.** Six commits are unpushed and four change
   shipped behavior. Pushing publishes the backend mitigation and both UI fixes
   at once. After Vercel, check the footer group and the `/study` word search on
   a real device, along with the two still-unverified gesture behaviours.

2. **The orphaned test fixture.** Document `c19ad18c-ea97-4841-8fa0-e60afc273521`
   no longer exists — no row, zero chunks — and
   `test_propositions_reference_grounding.py` and
   `test_reference_grounding_unit_proof.py` both hardcode it. Consistent with
   the 2026-09-04 re-ingest replacing 79 sermon documents with new ids. Needs a
   runtime-resolved document, which is a small design call.

3. **Three papercuts**, cheapest first: 64 untracked `docs/audits/` directories
   awaiting a commit-or-gitignore decision; two tests that need
   `PYTHONPATH=backend` when the other 86 self-resolve; and a hydration
   mismatch on `/study`'s root `<html>` theme class.

Also known, not scheduled: **10 of the 30 read-only DB tests make real paid
model calls** and were only run safely because the API keys were neutralized
first. Resume TIPNR at operation 2 only on fresh same-day authorization. The
next authorized Scheduled corpus item remains the representative Ravenhill
source-quality comparison in `docs/roadmap.md`.
