#!/usr/bin/env python3
"""
⚠ THIS SCRIPT WRITES TO THE PRODUCTION DATABASE. It is not a pytest test and
never was. It was called `scripts/verify_account_delete_request_live.py` until 2026-09-05; that name
put a production writer one `pytest scripts/` away from running, and it
advertised itself to other plans as the pattern to copy. The same three-part
guard already applied to scripts/verify_metering_live.py now applies here, and
all three stay — do not undo one because the others cover it:

  1. Renamed out of the `test_*.py` namespace, so no test runner collects it.
  2. `--apply` is required. A bare invocation prints a refusal and exits 2
     WITHOUT connecting to anything.
  3. Importing this module has no side effects: credential reads, connections
     and writes are reached only through `if __name__ == "__main__"`.

Deliberately unchanged: what the script does when it IS run with --apply.
Same checks, same order, same assertions, same output, same cleanup.

Found by the 2026-09-05 suite audit, which classified all 34 database-touching
`scripts/test_*.py` files; these four were the ones that commit real writes.

Usage:
  python3.12 scripts/verify_account_delete_request_live.py --apply

verify_account_delete_request_live.py -- End-to-end verification of the
account deletion-request stub against the LIVE production API:
  POST /account/delete-request
  GET  /account/delete-requests
  POST /account/delete-requests/{id}/resolve

Run AFTER pushing to main and confirming the Railway deploy has finished
(see scripts/verify_metering_live.py for the established pattern this follows).

Requires in backend/app/.env (or environment):
  SUPABASE_DB_URL      -- direct Postgres connection (service role)
  SUPABASE_URL         -- project URL
  SUPABASE_SERVICE_KEY -- service role key (for admin.generate_link)

Usage:
  python3 scripts/verify_account_delete_request_live.py
"""

import os
import sys
from pathlib import Path
from urllib.parse import parse_qs

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / "backend" / "app" / ".env")

# Read lazily: importing this module must not require credentials.
def _sb_url():
    return os.environ["SUPABASE_URL"]


API_BASE = "https://rhemata-production.up.railway.app"
TEST_EMAIL = "creative@clf-church.com"

_pass = 0
_fail = 0


def check(label, passed):
    global _pass, _fail
    tag = "PASS" if passed else "FAIL"
    print("  [%s] %s" % (tag, label))
    if passed:
        _pass += 1
    else:
        _fail += 1


def get_db_conn():
    import psycopg2
    from urllib.parse import urlparse, unquote

    db_url = os.environ["SUPABASE_DB_URL"]
    p = urlparse(db_url)
    return psycopg2.connect(
        host=p.hostname,
        port=p.port or 5432,
        user=unquote(p.username or ""),
        password=unquote(p.password or ""),
        dbname=p.path.lstrip("/"),
    )


def jwt_for_email(db, email):
    """Mint a real access token for `email` via a Supabase magic link --
    same approach as scripts/verify_metering_live.py."""
    link = db.auth.admin.generate_link({"type": "magiclink", "email": email})
    resp = httpx.get(
        f"{_sb_url()}/auth/v1/verify",
        params={
            "token": link.properties.hashed_token,
            "type": "magiclink",
            "redirect_to": "http://localhost:3000",
        },
        follow_redirects=False,
    )
    fragment = resp.headers.get("location", "").split("#", 1)[1]
    token = parse_qs(fragment).get("access_token", [""])[0]
    if not token:
        raise RuntimeError("Failed to obtain JWT for %s" % email)
    return token, link.user.id


def _require_apply(argv=None):
    """Refuse to run without --apply, before anything connects or is read.

    Same dry-run-by-default convention as scripts/verify_metering_live.py,
    scripts/apply_migration_088.py and scripts/sync_master_ingestion_queue.py.
    Returns a process exit code: 0 to proceed, 2 to refuse.
    """
    argv = sys.argv[1:] if argv is None else argv
    if "--apply" not in argv:
        print("REFUSED: %s writes to the PRODUCTION database." % Path(__file__).name)
        print("Nothing was connected to and nothing was written.")
        print("Re-run with --apply if that is genuinely what you intend.")
        return 2
    return 0


def main():
    from supabase import create_client

    print("\nAccount deletion requests -- end-to-end verification")
    print("=" * 50)

    db = create_client(_sb_url(), os.environ["SUPABASE_SERVICE_KEY"])
    conn = get_db_conn()
    cur = conn.cursor()

    # -- Find an admin to test the admin-only endpoints -------------------------
    cur.execute("SELECT user_id FROM user_roles WHERE role = 'admin' LIMIT 1")
    row = cur.fetchone()
    if not row:
        print("ERROR: no admin user found in user_roles -- cannot test admin endpoints")
        sys.exit(1)
    admin_user_id = row[0]
    cur.execute("SELECT email FROM auth.users WHERE id = %s", (admin_user_id,))
    admin_email = cur.fetchone()[0]

    user_jwt, user_id = jwt_for_email(db, TEST_EMAIL)
    admin_jwt, _ = jwt_for_email(db, admin_email)
    print(f"Test user: {TEST_EMAIL} ({user_id})")
    print(f"Admin:     {admin_email} ({admin_user_id})\n")

    cur.execute("DELETE FROM deletion_requests WHERE user_id = %s", (user_id,))
    conn.commit()

    try:
        # -- TEST 1: submit a deletion request -----------------------------------
        res = httpx.post(
            f"{API_BASE}/account/delete-request",
            headers={"Authorization": f"Bearer {user_jwt}"},
        )
        check("POST /account/delete-request returns 200", res.status_code == 200)

        # -- TEST 2: duplicate submission is rejected ----------------------------
        res2 = httpx.post(
            f"{API_BASE}/account/delete-request",
            headers={"Authorization": f"Bearer {user_jwt}"},
        )
        check("duplicate POST /account/delete-request returns 400", res2.status_code == 400)

        # -- TEST 3: admin can list the pending request --------------------------
        res3 = httpx.get(
            f"{API_BASE}/account/delete-requests",
            headers={"Authorization": f"Bearer {admin_jwt}"},
        )
        listed = res3.json() if res3.status_code == 200 else []
        found = next((r for r in listed if r["user_id"] == user_id), None)
        check("GET /account/delete-requests (admin) lists the new request", found is not None)

        # -- TEST 4: non-admin cannot list requests ------------------------------
        res4 = httpx.get(
            f"{API_BASE}/account/delete-requests",
            headers={"Authorization": f"Bearer {user_jwt}"},
        )
        check("GET /account/delete-requests (non-admin) returns 403", res4.status_code == 403)

        # -- TEST 5: admin can resolve it -----------------------------------------
        if found:
            res5 = httpx.post(
                f"{API_BASE}/account/delete-requests/{found['id']}/resolve",
                headers={"Authorization": f"Bearer {admin_jwt}"},
            )
            check("POST /account/delete-requests/{id}/resolve returns 200", res5.status_code == 200)

            cur.execute("SELECT status FROM deletion_requests WHERE id = %s", (found["id"],))
            status = cur.fetchone()[0]
            check("row status is 'resolved' after resolve", status == "resolved")
    finally:
        cur.execute("DELETE FROM deletion_requests WHERE user_id = %s", (user_id,))
        conn.commit()
        cur.close()
        conn.close()

    print()
    print("%d/%d checks passed" % (_pass, _pass + _fail))
    if _fail:
        sys.exit(1)


if __name__ == "__main__":
    _refusal = _require_apply()
    if _refusal:
        sys.exit(_refusal)
    main()
