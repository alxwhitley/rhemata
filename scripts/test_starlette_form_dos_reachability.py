#!/usr/bin/env python3.12
"""Reachability proof for GHSA-82w8-qh3p-5jfq (CVE-2026-54283) against this
application's actual form-parsing endpoint.

Full triage: docs/audits/2026-09/starlette_advisory_triage_2026-09-05.md

The advisory: `request.form()` enforces `max_fields` / `max_part_size` for
`multipart/form-data` and silently ignores them for
`application/x-www-form-urlencoded`. Starlette < 1.3.1.

What this script establishes, which reading the advisory alone does not:

  1. `backend/app/routers/ingest.py:71-76` is the only endpoint in this app
     that declares form parameters, so it is the only one where FastAPI calls
     `request.form()`. Every other route parses JSON.
  2. That endpoint is `Depends(require_admin_role)`-gated and the gate does
     NOT protect it, because FastAPI parses the body at
     `fastapi/routing.py:366` and does not solve dependencies until line 416.
  3. The parser dispatches on the request's own Content-Type, so declaring
     `UploadFile` does not keep an attacker on the multipart path.

Credential-free by construction: no network, no database, no environment
variables, no Authorization header. It reconstructs the real endpoint's
signature rather than importing the app, so it needs no backend config.

Reports state instead of asserting the defect is present, so it stays useful
across a starlette bump: run it after any fastapi/starlette version change and
it will say whether the urlencoded path became bounded.

Usage:  python3.12 scripts/test_starlette_form_dos_reachability.py
Exit 0 = ran and reported. Exit 1 = the harness itself is broken.
"""

import sys
import time

try:
    import starlette
    from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
    from fastapi.testclient import TestClient
except ImportError as exc:  # pragma: no cover - environment problem, not a finding
    print(f"cannot run: {exc}", file=sys.stderr)
    sys.exit(1)

FIELD_COUNT = 200_000
BIG_FIELD_BYTES = 50 * 1024 * 1024

auth_calls: list[int] = []


def require_admin_role() -> str:
    """Stand-in for the real dependency. Records whether it was ever reached."""
    auth_calls.append(1)
    raise HTTPException(status_code=401, detail="not admin")


app = FastAPI()


@app.post("/ingest")
async def ingest(
    file: UploadFile = File(...),
    source_type: str = Form("sermon"),
    user_id: str = Depends(require_admin_role),
):
    # Mirrors backend/app/routers/ingest.py:71-76. Body is irrelevant; the
    # defect is in what happens before this function is ever entered.
    return {"ok": True}


client = TestClient(app, raise_server_exceptions=False)


def probe(label: str, body: bytes, content_type: str) -> tuple[float, bool, int]:
    auth_calls.clear()
    started = time.perf_counter()
    response = client.post("/ingest", content=body, headers={"Content-Type": content_type})
    elapsed = time.perf_counter() - started
    reached_auth = bool(auth_calls)
    print(
        f"  {label:<44} status={response.status_code}  {elapsed:7.3f}s  "
        f"auth_dependency_ran={str(reached_auth):<5}  bytes={len(body):,}"
    )
    return elapsed, reached_auth, response.status_code


def main() -> int:
    print(f"starlette {starlette.__version__} | anonymous requests only, no Authorization header\n")

    probe("tiny urlencoded (control)", b"source_type=sermon", "application/x-www-form-urlencoded")

    multipart = b"".join(
        b'--b\r\nContent-Disposition: form-data; name="f%d"\r\n\r\nv\r\n' % i
        for i in range(FIELD_COUNT)
    ) + b"--b--\r\n"
    mp_elapsed, mp_auth, mp_status = probe(
        f"multipart, {FIELD_COUNT // 1000}k fields", multipart, "multipart/form-data; boundary=b"
    )

    urlencoded = b"&".join(b"f%d=v" % i for i in range(FIELD_COUNT))
    ue_elapsed, ue_auth, ue_status = probe(
        f"urlencoded, {FIELD_COUNT // 1000}k fields",
        urlencoded,
        "application/x-www-form-urlencoded",
    )

    probe(
        f"urlencoded, one {BIG_FIELD_BYTES // (1024 * 1024)}MB field",
        b"f=" + b"A" * BIG_FIELD_BYTES,
        "application/x-www-form-urlencoded",
    )

    multipart_bounded = mp_status == 400 and not mp_auth
    urlencoded_bounded = ue_status == 400 and not ue_auth

    print()
    if not multipart_bounded:
        print("INCONCLUSIVE: the multipart control did not reject before auth.")
        print("The harness no longer reflects the parser's documented behaviour.")
        return 0

    if urlencoded_bounded:
        print("FIXED: the urlencoded path now rejects before auth, same as multipart.")
        print("GHSA-82w8-qh3p-5jfq no longer reaches this application.")
        return 0

    ratio = ue_elapsed / mp_elapsed if mp_elapsed else float("inf")
    print("REACHABLE: GHSA-82w8-qh3p-5jfq applies to this application.")
    print(
        f"  Multipart rejected in {mp_elapsed:.3f}s without reaching the admin gate; "
        f"the same {FIELD_COUNT:,} fields sent as urlencoded were parsed in full "
        f"({ue_elapsed:.3f}s, {ratio:.0f}x) before the gate rejected the caller."
    )
    print("  That parse is synchronous, and backend/railway.toml runs one uvicorn worker.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
