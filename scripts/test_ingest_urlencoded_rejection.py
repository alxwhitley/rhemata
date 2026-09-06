#!/usr/bin/env python3.12
"""The urlencoded refusal that closes GHSA-82w8-qh3p-5jfq on this deployment.

Drives the REAL app (app.main), not a reconstruction, so it proves the shipped
middleware order actually puts the refusal in front of the form parser.

Companion to scripts/test_starlette_form_dos_reachability.py, which establishes
that the defect reaches this application at all.
Triage: docs/audits/2026-09/starlette_advisory_triage_2026-09-05.md

Credential-free: no network, no database. Exit 0 = all checks pass.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from fastapi.testclient import TestClient  # noqa: E402
from starlette.requests import Request  # noqa: E402

from app.main import app  # noqa: E402

failures = []
form_calls = []


def check(label, condition):
    print("  %s: %s" % ("OK" if condition else "FAIL", label))
    if not condition:
        failures.append(label)


# Tripwire: if the refusal ever stops running before body parsing, this fires.
_real_form = Request.form


def _tripwire(self, *a, **kw):
    form_calls.append(1)
    return _real_form(self, *a, **kw)


Request.form = _tripwire

client = TestClient(app, raise_server_exceptions=False)

print("\nurlencoded refusal on the real app (GHSA-82w8-qh3p-5jfq)")

# 1. The attack shape: 200k fields, anonymous.
body = b"&".join(b"f%d=v" % i for i in range(200_000))
form_calls.clear()
started = time.perf_counter()
r = client.post("/ingest", content=body,
                headers={"Content-Type": "application/x-www-form-urlencoded"})
elapsed = time.perf_counter() - started
check("urlencoded body is refused with 415", r.status_code == 415)
check("the form parser is never reached", not form_calls)
check("refusal is not proportional to body size (<0.25s)", elapsed < 0.25)
print("     (%d fields, %.3fs, status %d)" % (200_000, elapsed, r.status_code))

# 2. The 50MB single-field shape.
form_calls.clear()
r = client.post("/ingest", content=b"f=" + b"A" * (50 * 1024 * 1024),
                headers={"Content-Type": "application/x-www-form-urlencoded"})
check("oversized single urlencoded field is refused", r.status_code == 415)
check("the form parser is never reached for it either", not form_calls)

# 3. Charset parameter must not smuggle it past the check.
r = client.post("/ingest", content=b"a=1",
                headers={"Content-Type": "application/x-www-form-urlencoded; charset=utf-8"})
check("content-type parameters do not bypass the refusal", r.status_code == 415)
r = client.post("/ingest", content=b"a=1",
                headers={"Content-Type": "APPLICATION/X-WWW-FORM-URLENCODED"})
check("the check is case-insensitive", r.status_code == 415)

# 4. The real upload path is untouched: multipart still reaches the admin gate.
form_calls.clear()
multipart = (b'--b\r\nContent-Disposition: form-data; name="source_type"\r\n\r\nsermon\r\n'
             b'--b\r\nContent-Disposition: form-data; name="file"; filename="a.pdf"\r\n'
             b'Content-Type: application/pdf\r\n\r\n%PDF-1.4\r\n--b--\r\n')
r = client.post("/ingest", content=multipart,
                headers={"Content-Type": "multipart/form-data; boundary=b"})
check("multipart still reaches the admin gate (401/403)", r.status_code in (401, 403))
check("multipart still parses its form", bool(form_calls))

# 5. Ordinary JSON traffic is unaffected.
r = client.get("/")
check("the API root still serves", r.status_code == 200)

print("\n%s" % ("All checks passed." if not failures
                else "FAILED: %s" % ", ".join(failures)))
sys.exit(1 if failures else 0)
