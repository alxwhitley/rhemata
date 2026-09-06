#!/usr/bin/env python3.12
"""Guards the guards on this repo's four production-writing verify scripts.

The 2026-09-05 suite audit classified all 34 database-touching
`scripts/test_*.py` files. Four of them commit real writes to production --
including `INSERT INTO user_roles (user_id, role) VALUES (%s, 'admin')` -- while
sitting in a namespace that reads as safe and that a `scripts/test_*.py` glob
collects. They were renamed and gated the same way `scripts/test_metering.py`
was on 2026-08-31, and this file is what keeps that from silently rotting.

Asserts all three parts of the guard, for each script:
  1. the name is out of the `test_*.py` namespace, so no runner collects it;
  2. a bare invocation refuses with exit 2 and opens no socket;
  3. importing the module has no side effects.

Deliberately never exercises the --apply path: that path writes to production.
It asserts only that `_require_apply(["--apply"])` returns 0, which is the
decision point, not the write.

Credential-free: no network, no database. Exit 0 = all checks pass.
"""

import importlib.util
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

GUARDED = [
    "verify_account_delete_request_live.py",
    "verify_ingest_queue_endpoints_live.py",
    "verify_deletion_requests_migration_live.py",
    "verify_pastors_rls_live.py",
]

failures = []


def check(label, condition):
    print("  %s: %s" % ("OK" if condition else "FAIL", label))
    if not condition:
        failures.append(label)


class _SocketOpened(Exception):
    pass


def _boom(*a, **kw):
    """Tripwire body: reaching this means something tried to connect."""
    raise _SocketOpened("a connection was attempted")


print("\nproduction-writer guards")

for name in GUARDED:
    path = ROOT / "scripts" / name
    print("\n%s" % name)
    check("exists at its guarded name", path.exists())
    if not path.exists():
        continue

    # 1. Out of the collected namespace.
    check("not collected by a scripts/test_*.py glob", not name.startswith("test_"))

    # 2. Bare invocation refuses, exit 2.
    p = subprocess.run([sys.executable, str(path)], capture_output=True, text=True,
                       cwd=str(ROOT), timeout=120)
    check("bare invocation exits 2", p.returncode == 2)
    check("bare invocation says it refused", "REFUSED" in p.stdout)
    check("bare invocation reports nothing was written",
          "nothing was written" in p.stdout.lower())

    # 3. Import has no side effects, proven with sockets disabled so a
    #    connection attempt raises rather than silently succeeding.
    real_connect, real_create = socket.socket.connect, socket.create_connection
    socket.socket.connect, socket.create_connection = _boom, _boom
    try:
        spec = importlib.util.spec_from_file_location(path.stem + "_probe", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        imported, why = True, ""
    except _SocketOpened:
        imported, why = False, "opened a socket on import"
    except Exception as exc:
        imported, why = False, "%s: %s" % (type(exc).__name__, exc)
    finally:
        socket.socket.connect, socket.create_connection = real_connect, real_create

    check("imports cleanly with sockets disabled%s" % ("" if imported else " -- " + why),
          imported)

    if imported:
        # The decision point only. Running main() would write to production.
        check("_require_apply([]) refuses with 2", mod._require_apply([]) == 2)
        check("_require_apply(['--apply']) allows with 0", mod._require_apply(["--apply"]) == 0)

# No stragglers: nothing in the test namespace may commit to the database.
print("\nnamespace sweep")
leaked = []
for f in sorted((ROOT / "scripts").glob("test_*.py")):
    if f.name == Path(__file__).name:
        continue  # this file names those strings in order to check for them
    src = f.read_text(errors="ignore")
    if "conn.commit()" in src and "psycopg2" in src:
        leaked.append(f.name)
check("no scripts/test_*.py commits to a real connection -- %s" % (leaked or "none"),
      not leaked)

print("\n%s" % ("All checks passed." if not failures else "FAILED: %d" % len(failures)))
sys.exit(1 if failures else 0)
