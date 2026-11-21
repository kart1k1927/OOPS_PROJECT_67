"""Diagnose a local setup when sign in does not work.

    python scripts/check_setup.py

Reports which database you are pointed at, whether the demo accounts exist
there, and whether the demo password verifies against them. Prints no secrets.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEMO_PASSWORD = "campus2026"
EXPECTED = ["admin@bits.ac.in", "priya@bits.ac.in", "ravi@bits.ac.in"]


def main() -> int:
    print("I-ITSM setup check\n" + "=" * 60)

    env = ROOT / ".env"
    if not env.exists():
        print("\n.env            MISSING")
        print("\nYou have two options.")
        print("  1. For rehearsing, you do not need it at all:")
        print("       python scripts/demo_server.py")
        print("  2. To use the shared database, ask Amith for his .env file")
        print("     and put it in the project root.")
        return 1

    from app.core.config import ConfigurationError, get_settings

    try:
        settings = get_settings()
    except ConfigurationError as exc:
        print(f"\n.env            PRESENT but incomplete\n  {exc}")
        return 1

    project = settings.supabase_url.split("//")[-1].split(".")[0]
    print(f"\n.env            present")
    print(f"supabase project  {project}")
    print(f"jwt secret        set, {len(settings.jwt_secret)} characters")

    if project != "uwvvoxsyaeuppumqautr":
        print("\n  WARNING: this is not the team's shared project.")
        print("  The shared one is uwvvoxsyaeuppumqautr. If you are pointed")
        print("  somewhere else, your copy has no seeded accounts, which looks")
        print("  exactly like a wrong password. Use Amith's .env.")

    from app.core.security import verify_password
    from app.database.database import get_client

    try:
        rows = get_client().table("profiles").select(
            "employee_code,full_name,email,role,is_active,password_hash"
        ).order("employee_code").execute().data
    except Exception as exc:
        print(f"\ndatabase         UNREACHABLE\n  {str(exc)[:160]}")
        return 1

    print(f"database         reachable, {len(rows)} accounts\n")

    if not rows:
        print("  No accounts exist in this database. Run:")
        print("    python scripts/seed_demo.py")
        return 1

    print(f"{'EMAIL':26} {'ROLE':11} {'ACTIVE':7} PASSWORD '{DEMO_PASSWORD}'")
    print("-" * 68)
    working = []
    for r in rows:
        email = r.get("email") or "(no email)"
        ok = verify_password(DEMO_PASSWORD, r.get("password_hash"))
        if ok and r.get("is_active"):
            working.append(email)
        print(f"{email[:25]:26} {r['role']:11} {str(r.get('is_active')):7} {'works' if ok else 'does not match'}")

    print()
    missing = [e for e in EXPECTED if e not in [r.get("email") for r in rows]]
    if missing:
        print(f"  Missing demo accounts: {', '.join(missing)}")
        print("  Run: python scripts/seed_demo.py")
        return 1

    if not working:
        print("  No account accepts the demo password. Run:")
        print("    python scripts/seed_demo.py --reset-passwords")
        return 1

    print(f"  {len(working)} accounts accept '{DEMO_PASSWORD}'. Sign in should work.")
    print("\n  If it still fails in the browser:")
    print("    - check for a trailing space when pasting the email")
    print("    - make sure the server you opened is the one you just started")
    print("    - a stale cookie: open a private window")
    return 0


if __name__ == "__main__":
    sys.exit(main())
