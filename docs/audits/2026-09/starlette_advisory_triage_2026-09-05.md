# Starlette advisory exploitability triage — 2026-09-05

Read-only diagnostic. Closes the first item of `docs/roadmap.md`'s "Dependency
and hardening follow-up (from the 2026-08-24 scan)", which reads: *"Do the
read-only exploitability triage of the 7 advisories first — the same pass done
for the Next.js CVEs turned 3 alarming-looking entries into zero live attack
surface, and may do so here. Triage is cheap; the bump is not."*

It did not do so here. **Four of five are not applicable. One is reachable
unauthenticated on the deployed API and was proved, not inferred.**

No code was changed, no dependency bumped, no database touched, nothing
deployed. No network request was made to any New Wine service; the only
outbound call was to the OSV.dev advisory API.

## Scope correction — five distinct advisories, not seven

The 2026-08-24 scan recorded "7" from `pip-audit`'s raw count. Querying OSV.dev
for `starlette==0.52.1` returns 10 records that collapse to **5 distinct
advisories**; the other 5 are PYSEC aliases of the same GHSA IDs. The count
difference is bookkeeping, not a change in exposure.

| Advisory | CVE | Severity | Fixed in | Verdict |
|---|---|---|---|---|
| GHSA-82w8-qh3p-5jfq | CVE-2026-54283 | HIGH | 1.3.1 | **APPLICABLE — proved reachable pre-auth** |
| GHSA-86qp-5c8j-p5mr | CVE-2026-48710 | MODERATE | 1.0.1 | Not applicable |
| GHSA-jp82-jpqv-5vv3 | CVE-2026-54282 | LOW | 1.3.0 | Not applicable |
| GHSA-wqp7-x3pw-xc5r | CVE-2026-48818 | HIGH | 1.1.0 | Not applicable |
| GHSA-x746-7m8f-x49c | CVE-2026-48817 | MODERATE | 1.1.0 | Not applicable |

## The one that applies

**GHSA-82w8-qh3p-5jfq — `request.form()` limits silently ignored for
`application/x-www-form-urlencoded`.** `max_fields` and `max_part_size` are
enforced for `multipart/form-data` and dropped for urlencoded bodies, so an
unauthenticated request can block the event loop (field count) or force
unbounded memory allocation (field size).

### Confirmed present in the pinned code

`starlette/requests.py:281-283` forwards all three limits to the multipart
parser. Line 291 constructs the urlencoded parser as
`FormParser(self.headers, self.stream())` — no limits passed, and `FormParser`
has no parameter to receive them. Verified by reading the installed
`starlette==0.52.1`, which matches `backend/requirements.txt:3` exactly.

### Confirmed reachable, and reachable *before* authentication

`backend/app/routers/ingest.py:71-76` is the one endpoint in the application
that declares form parameters (`file: UploadFile = File(...)`,
`source_type: str = Form("sermon")`), so it is the one endpoint where FastAPI
calls `request.form()`. Every other route parses JSON.

That endpoint carries `user_id: str = Depends(require_admin_role)`, which
makes it look protected. It is not protected against this, because FastAPI
parses the body before it solves dependencies: `fastapi/routing.py:366`
performs `body = await request.form()`, and `solve_dependencies(...)` — which
runs `require_admin_role` — is not called until line 416.

The parser also does not care that the endpoint declares a file upload. It
dispatches on the request's own `Content-Type` header, so an attacker simply
sends `application/x-www-form-urlencoded` and the urlencoded path runs.

### Proof

`scripts/test_starlette_form_dos_reachability.py` reconstructs the exact
signature of the real endpoint — same `File`/`Form` parameters, same admin
dependency — and drives it with `TestClient`. Credential-free, no network, no
database. Anonymous requests only; no `Authorization` header is ever sent.

```
tiny urlencoded (control)                  status=401    0.006s  auth_dependency_ran=True   bytes=18
multipart, 200k fields (limits ENFORCED)   status=400    0.012s  auth_dependency_ran=False  bytes=11,488,897
urlencoded, 200k fields (limits IGNORED)   status=401    0.696s  auth_dependency_ran=True   bytes=1,888,889
urlencoded, one 50MB field                 status=401    0.027s  auth_dependency_ran=True   bytes=52,428,802
```

Read the `auth_dependency_ran` column, not the status codes. The multipart
request carrying 200,000 fields is rejected in 12ms and the admin dependency
never runs — the limit fires inside the parser, exactly as designed. The
urlencoded request carrying the same 200,000 fields spends **0.696s of
synchronous, event-loop-blocking work** parsing all of them, and only then
reaches the admin check that rejects it. A 57x parse-time ratio between two
requests an attacker chooses freely between.

The final row is the memory shape: a single 50MB field is buffered in full,
again before the caller is known to be unauthorized.

The script reports state rather than asserting the defect, so it stays useful
after any fastapi/starlette bump. That detection was mutation-checked: with
`FormParser.parse` wrapped to enforce a 1,000-field ceiling — emulating the
patched urlencoded path — the same script flips to `FIXED: the urlencoded path
now rejects before auth`. It is reading the two behaviours apart, not printing
a constant.

### Why this is worse here than the advisory's baseline

`backend/railway.toml` starts the API as
`uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}` with no `--workers`
flag — **one process, one event loop**. There is no second worker to serve
traffic while the first one parses. Blocking that loop stalls every route on
the API for every user, including `/async-chat/submit` and `/async-chat/result`,
which is the core beta answer journey.

No body-size limit is configured anywhere in the application. Whether Railway's
edge proxy imposes one is not determinable from this repository and is not
claimed either way — but per the advisory a sub-10MB body is already sufficient,
and the measurement above blocked for 0.7s on 1.9MB.

`healthcheckPath = "/"` and `restartPolicyType = "on_failure"` mean a
sufficiently sustained stall is also a restart loop, not only a slowdown. Not
tested; recorded as a consequence to check if this is acted on.

### Not claimed

This was not driven against production. No live attack was attempted or should
be. The measurement is local, on one developer machine, against a faithful
reconstruction of the endpoint's signature — it establishes reachability and
the pre-auth ordering, not a production throughput figure.

## The four that do not apply

**GHSA-86qp-5c8j-p5mr — Host header poisons `request.url.path`.** Requires code
that makes security decisions from `request.url` rather than the raw ASGI
scope. There are **zero** `request.url` reads in `backend/app/` (the only `.url`
matches in the whole backend are `body.url`, a Pydantic field on
`ingest_queue.py:127,143`, unrelated). The one custom middleware,
`main.py:41`'s `security_headers`, reads nothing from the request at all, and
Starlette's `CORSMiddleware` keys on the `Origin` header, not `request.url` —
confirmed by reading the installed `starlette/middleware/cors.py`. Nothing in
this application can be misled by a poisoned `request.url.path`, because
nothing reads it.

**GHSA-jp82-jpqv-5vv3 — path poisons `request.url.hostname`.** Same reason, and
weaker still: the advisory notes the poisoned path matches no route, so only
pre-routing middleware or 404/exception handlers are exposed. This app has
neither reading `request.url`.

**GHSA-wqp7-x3pw-xc5r — SSRF / NTLM theft via UNC paths in `StaticFiles`.** Not
applicable twice over. `StaticFiles` appears nowhere in `backend/app/`, and the
advisory states plainly that POSIX systems are unaffected — the service runs on
Railway's Linux containers (`nixPkgs = ["python312"]`).

**GHSA-x746-7m8f-x49c — arbitrary HTTP method dispatched via `getattr` on
`HTTPEndpoint`.** `HTTPEndpoint` appears nowhere in `backend/app/`. It is
Starlette's class-based routing API; this application uses FastAPI's decorator
routing exclusively, so no endpoint resolves a handler by lowercasing the
client-supplied method name.

## What this does and does not settle about the bump

The roadmap's premise for the coupled bump is unchanged and still correct:
every fix version for these advisories is `>=1.0.0`, and pinned
`fastapi==0.128.8` declares `starlette<1.0.0,>=0.40.0`, so neither package
moves alone. Invariant 14's landmine — the `da27fe4` 422-vs-401 admin-auth bug,
which reproduced locally but not in the deployed container — is exactly this
version-interaction territory, and nothing here makes that bump safer.

What this triage changes is only the *urgency input* to that decision. The
Next.js precedent does not repeat: four advisories are genuinely inert, but the
fifth is a real unauthenticated availability defect against the single-process
API, not a theoretical one.

Worth noting for whoever scopes the fix: the fix version for the applicable
advisory is `1.3.1`, the highest of the five. Bumping to satisfy only the
lower-severity entries would leave the one that actually applies unfixed.

An in-place mitigation that avoids the coupled bump entirely was **not**
designed here — designing one is outside a triage's stop condition. It is
recorded as an option because it materially affects the classification: the
exposure is one endpoint, and the endpoint is the admin single-PDF upload that
CLAUDE.md's Landmines entry already records as the confirmed ingestion-chokepoint
bypass with no known caller and no frontend caller, which never appears to have
been used.

## Classification

Not self-promoted. Per `AGENTS.md`, promotion is Alex's decision; the four
required elements are assembled here so the decision can be made without
re-deriving them.

- **Concrete failure:** an unauthenticated request blocks the single-worker API
  event loop, or forces memory allocation proportional to its body.
- **Evidence:** the reachability proof above, plus the pre-auth ordering read
  from the installed FastAPI and Starlette source.
- **Affected beta surface:** the whole public API, including the core answer
  journey — there is no second worker.
- **Smallest closure condition:** closed by the mitigation below, on Alex's
  2026-09-05 decision (Scheduled, mitigate now rather than bump).

## Mitigation shipped, 2026-09-05

Alex classified this **Scheduled** and chose a scoped in-place fix over the
coupled fastapi + starlette bump, which stays Scheduled on its own merits.

`backend/app/main.py` gains one middleware that refuses
`application/x-www-form-urlencoded` with `415` before any body is read. This
works because **no endpoint in this application accepts urlencoded input** —
`/ingest` is the only route declaring form fields and it requires multipart for
its file upload. Multipart is untouched and keeps its own enforced
`max_fields` / `max_part_size`. No version pin moved, so Invariant 14's
landmine is not disturbed.

It is registered before `security_headers` so that middleware still stamps the
refusal. It sits inside `CORSMiddleware`, so the `415` carries no CORS headers
— accepted, because no browser client here sends this content type.

**Proof:** `scripts/test_ingest_urlencoded_rejection.py`, 10 checks against the
REAL `app.main` (not a reconstruction, so it exercises the shipped middleware
order), credential-free. It tripwires `Request.form` to prove the parser is
never reached rather than inferring it from timing.

| | before | after |
|---|---|---|
| 200,000-field urlencoded body | 0.829s, parsed in full, then `401` | 0.006s, `415`, never parsed |
| 50MB single urlencoded field | buffered in full, then `401` | `415`, never parsed |
| multipart upload | reaches the admin gate | unchanged, reaches the admin gate |

Mutation-verified: with the middleware reverted, 7 of the 10 checks fail and
the 200k-field body is parsed again. The three that still pass are the
multipart and API-root checks, which is the point — they confirm the test
covers the untouched paths rather than merely asserting the middleware exists.

**Not claimed:** this is not deployed. It is repository-verified only;
deployment remains a separate attended gate.

The four non-applicable advisories need no work and should be recorded as
triaged so they are not re-raised at the next scan.

## Reproduce

```
python3.12 scripts/test_starlette_form_dos_reachability.py
```
