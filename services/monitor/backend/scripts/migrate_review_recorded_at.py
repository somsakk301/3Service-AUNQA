"""One-time migration (project owner, 2026-10-04: Authentication): rename `review.reviewedAt` to
`review.recordedAt` in the Monitor-owned `monitoring_results` collection, for the field rename that came with
adding `review.recordedBy`.

* Only renames the field; it does not invent `review.recordedBy` for these records — there is no way to know
  who recorded a review saved before sessions existed, so that field is left absent for them (null to the API).
* Idempotent: `$rename` is a no-op on a document that has no `review.reviewedAt` (already migrated, or never
  had a review), so running this more than once changes nothing further.
* Targets the same database the running backend uses (MORNITOR_RESULTS_DB_URI/NAME, falling back to
  MORNITOR_DB_URI/NAME — see app/settings.py): the one `monitoring_results` actually lives in.

Run from backend/:
    .venv/bin/python scripts/migrate_review_recorded_at.py --dry-run   # report only, write nothing
    .venv/bin/python scripts/migrate_review_recorded_at.py             # apply
"""
import argparse
import sys
from pathlib import Path

from pymongo import MongoClient

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from app.adapters.monitoring_results import MONITORING_RESULTS_COLLECTION  # noqa: E402
from app.settings import Settings  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dry-run", action="store_true", help="report how many documents would change; write nothing")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    s = Settings.from_env()
    db = MongoClient(s.results_db_uri, serverSelectionTimeoutMS=3000)[s.results_db_name]
    collection = db[MONITORING_RESULTS_COLLECTION]

    query = {"review.reviewedAt": {"$exists": True}}
    matches = list(collection.find(query, {"psCode": 1, "curriculumId": 1}))
    print(f"{s.results_db_name}.{MONITORING_RESULTS_COLLECTION}: {len(matches)} document(s) with review.reviewedAt")
    for doc in matches:
        print(f"  curriculumId={doc.get('curriculumId')} psCode={doc.get('psCode')}")

    if args.dry_run:
        print("[dry-run] no write performed")
        return 0
    if not matches:
        print("nothing to migrate")
        return 0

    result = collection.update_many(query, {"$rename": {"review.reviewedAt": "review.recordedAt"}})
    print(f"migrated {result.modified_count} document(s): review.reviewedAt -> review.recordedAt "
          "(review.recordedBy intentionally left absent for this pre-existing data)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
