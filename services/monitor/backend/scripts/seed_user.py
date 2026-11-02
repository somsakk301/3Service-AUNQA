"""Create (or update) one account in the Monitor-owned `users` collection (project owner, 2026-10-04:
Authentication). This is the ONLY way an account is made: there is no register endpoint and no
user-management API in the running application.

* Writes to the same database the running backend uses for `monitoring_results`
  (MORNITOR_RESULTS_DB_URI/NAME, falling back to MORNITOR_DB_URI/NAME — see app/settings.py), so a seeded
  account is found by the same AuthService the API wires up.
* The password is never stored in plaintext: this script hashes it with the same PBKDF2-HMAC + random salt
  as app/services/auth.py (the one function, imported, not reimplemented here).
* Idempotent by default: an existing username is left untouched and reported, not overwritten.
  --update-password changes the password (and name) of an existing account on purpose.
* The password is read from the --password flag, or prompted (hidden input) when omitted, so it does not
  have to sit in shell history.

Run from backend/:
    .venv/bin/python scripts/seed_user.py --username reviewer1 --name "ชื่อผู้ตรวจ"
    .venv/bin/python scripts/seed_user.py --username reviewer1 --name "ชื่อผู้ตรวจ" --update-password
    .venv/bin/python scripts/seed_user.py --username reviewer1 --name "ชื่อผู้ตรวจ" --dry-run
"""
import argparse
import getpass
import sys
from pathlib import Path

from pymongo import MongoClient

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from app.adapters.auth import USERS_COLLECTION  # noqa: E402
from app.services.auth import hash_password  # noqa: E402
from app.settings import Settings  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--username", required=True, help="login name (unique)")
    p.add_argument("--name", required=True, help="display name, saved as review.recordedBy.name")
    p.add_argument("--password", default=None, help="omit to be prompted (hidden input)")
    p.add_argument("--update-password", action="store_true", help="replace the password/name of an existing account")
    p.add_argument("--dry-run", action="store_true", help="check only, write nothing")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    password = args.password or getpass.getpass(f"Password for {args.username}: ")
    if not password:
        print("A password is required.", file=sys.stderr)
        return 1

    s = Settings.from_env()
    db = MongoClient(s.results_db_uri, serverSelectionTimeoutMS=3000)[s.results_db_name]
    collection = db[USERS_COLLECTION]

    existing = collection.find_one({"username": args.username})
    if existing is not None and not args.update_password:
        print(f"'{args.username}' already exists in {s.results_db_name}.{USERS_COLLECTION} — nothing changed "
              "(pass --update-password to replace its password/name).")
        return 0

    doc = {"username": args.username, "name": args.name, "passwordHash": hash_password(password)}
    verb = "updated" if existing is not None else "inserted"
    if args.dry_run:
        action = "update" if existing is not None else "insert"
        print(f"[dry-run] would {action} username={args.username!r} name={args.name!r} "
              f"into {s.results_db_name}.{USERS_COLLECTION}")
        return 0

    collection.update_one({"username": args.username}, {"$set": doc}, upsert=True)
    print(f"{verb} username={args.username!r} into {s.results_db_name}.{USERS_COLLECTION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
