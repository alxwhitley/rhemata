# New Wine — Live Status

Point-in-time state only. Overwritten each session, never appended to. Durable
truth lives in code, git history, `PLAN.md`, `docs/roadmap.md`,
`docs/plan-archive.md`, and `CLAUDE.md`.

Last verified: 2026-09-05. **PLAN.md has no active blockers.**

---

## Current state

**Seven commits shipped and are DEPLOYED and verified in production.**
`origin/main` is at `f1a0cd7` (`d9c3b1c`..`f1a0cd7`), pushed on Alex's explicit
approval at the end of a remote, phone-driven session. No migration and no
admin database write were part of it. Verification was functional, not build
status — details under each item below.

**Starlette advisories triaged and the one real finding mitigated** (`d9c3b1c`,
`docs/audits/2026-09/starlette_advisory_triage_2026-09-05.md`). The 2026-08-24
scan's "7 advisories" are 5 distinct CVEs; 4 are inert here. The fifth is real:
starlette 0.52.1 does not apply `max_fields`/`max_part_size` to urlencoded
bodies, **and FastAPI parses the body before it solves dependencies**, so
`/ingest`'s admin gate does not stand in front of it — 200k fields urlencoded
cost 686ms of event-loop-blocking work on a single-worker API, against 11ms for
the same fields as multipart. Alex classified it **Scheduled** and chose a
narrow middleware refusing urlencoded over the coupled fastapi+starlette bump,
which stays Scheduled. **Confirmed live**: production returns `415` in 0.12s
while multipart still reaches the admin gate with `401`.

**Two UI fixes, deployed and verified by bytes.** `c58f252` renders the
word-study article on the standalone `/study` word search — it had been fetched
into state since `40cdb4c` and never passed to `WordStudyPanel`. `2137233`
closes the roadmap's footer half: feedback and Sources are now one group, with
a measured optical correction (a plain stack put 27px between the thumb icon
and the Sources label against a 24px break, inverting the rhythm, because two
44px touch targets stack 26px of unpainted padding). Both are pinned by new
stubbed Playwright specs and mutation-proven. Verified in production per
`frontend/CLAUDE.md`'s stale-CSS landmine: the served chunk is byte-identical
to a clean local build apart from 22 bytes of font content-hashes, `-mt-3` is
present, the stray `.invisible` rule is absent, and the word-study empty state
ships in the served JS.

**The backend regression suite was run for the first time in this repo's
history** — there is no CI of any kind. 90/90 credential-free files pass. Two
stale references repaired (`b782375`): a test pointing at a script archived in
August, crashing before three of its own checks ran, and a hardcoded corpus
count of 144 the corpus had outgrown to 172.

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
Mutation-proving that guard stripped it from `verify_pastors_rls_live.py` *in
place*, and the checker then subprocess-ran the script bare, so `main()`
executed against production unattended — the thing the hard rule forbids. Net
effect verified zero: cleanup is in a `finally`, both target tables are empty,
`user_roles` shows no residue, and only that one script was mutated. The
durable lesson is now a CLAUDE.md landmine.

**Post-deploy smoke passed on the real answer path.** Guest job
`06de7723-46e3-4d1e-a050-4739f275dcd4`: `outcome=answered`, 3,058 characters,
15 citations, 3 verified references, 42.1s end to end, picked up by worker
`1d79a205082d-1-slot2` — which is the direct evidence that `answer-worker`
rebuilt and came back. It also confirmed three things on deployed code: B8's
prose-quotation guard held (zero attributed quotations of five or more words),
`quote_ids` is `[]` so the rail is still correctly off, and `analytics_outcome`
is NULL, the expected guest path rather than a degraded marker.
`answer_jobs` went 75 → 76.

**What is still unverified after the deploy.** `search-analytics-finalizer` and
`search-analytics-retention` rebuilt but were not checked — they have no
request surface; use `scripts/analytics_health_report.py` if certainty is
wanted. Vercel still carries `VERCEL_FORCE_NO_BUILD_CACHE=1` (Production scope,
project `newwine`); removing it silently restores the stale-CSS failure.

**Device verification PASSED (Alex, 2026-09-05, on real hardware).** This
closes the item outstanding since 2026-09-04. Confirmed working: the answer
footer group, the `/study` word search rendering its article, thread overscroll
containment, and Profile swipe-to-dismiss. The `visualViewport` `top`-write
change that was held in reserve for a surviving overscroll bounce is therefore
**not needed and must not be applied** — the bounce is gone.

**TIPNR ingestion is paused mid-gate, one operation in.** Packets 0–4 merged
(`8c99ea1`). Of five approved operations only **operation 1 ran** — the
rollback-only probe, 2026-09-02: 600 rows staged, **0 committed**, 0 embedding
requests. State re-verified 2026-09-05: `next_batch_index 1`,
`completed_batches 0`, 3,939 clean, source hidden, both registries empty. A
resuming session needs three things: the pinned artifact is **not tracked in
git** (confirm `sources/stepbible/` hashes to `69f69d80…e180e`, or 26 checks
silently skip); approvals are same-day and `local/2026-09/`'s are expired; and
the classifier refuses these writes from inside a session — the probe ran only
when Alex invoked it with `!`.

---

## Session outcome and measures

- Original outcome completed: **yes** — every item Alex selected was finished,
  verified, deployed, and smoke-tested.
- Unplanned investigations started: **1** — the suite audit, which was
  authorized mid-session and produced the writer-gating work.
- Findings promoted to Blocker: **0**. The starlette finding was classified
  Scheduled by Alex, with the mitigation shipped in the same decision.
- Scope changes approved by Alex: eight, all via explicit decision — Scheduled
  plus mitigate, commit without pushing, static-audit the DB tests before
  running any, transcribe the roadmap wording, deploy, run the post-deploy
  answer smoke, run the sermon exposure audit, and rule no filter.
- Gates closed: **1** — sermon passage quality, measured then ruled. It had
  blocked all sermon filter/classifier work since 2026-09-04.
- Active critical-path item count: **0**.
- Rule violations: **1**, self-reported above — an unattended production write
  during a mutation test, net effect zero.

---

## Next single item

No active Blocker. In recommended order:

1. **The orphaned test fixture.** Document `c19ad18c-ea97-4841-8fa0-e60afc273521`
   no longer exists — no row, zero chunks — and
   `test_propositions_reference_grounding.py` and
   `test_reference_grounding_unit_proof.py` both hardcode it. Consistent with
   the 2026-09-04 re-ingest replacing 79 sermon documents with new ids. Needs a
   runtime-resolved document, which is a small design call.

2. **Three papercuts**, cheapest first: 64 untracked `docs/audits/` directories
   awaiting a commit-or-gitignore decision; two tests that need
   `PYTHONPATH=backend` when the other 86 self-resolve; and a hydration
   mismatch on `/study`'s root `<html>` theme class.

**Sermon passage quality is CLOSED — no filter** (Alex, 2026-09-05, after the
session close). The Stage 3 gate was measured read-only: kill-grade passages
reached top 8 in 6 of 50 question groups, were cited in 3, and degraded 0 of 3.
Stages 4 and 5 of the design spec are not authorized. Recorded in
`docs/roadmap.md`, CLAUDE.md Settled #31, and the spec itself;
evidence in `docs/audits/2026-09/sermon_exposure_audit_2026-09-05.md`.

Also known, not scheduled: **10 of the 30 read-only DB tests make real paid
model calls** and were only run safely because the API keys were neutralized
first. Resume TIPNR at operation 2 only on fresh same-day authorization. The
next authorized Scheduled corpus item remains the representative Ravenhill
source-quality comparison in `docs/roadmap.md`.
