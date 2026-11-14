"""Seed the Firestore 'eras' catalog from contracts/fixtures/eras.json.

Idempotent: uses era ID as document key; updates if schema_version changes.
Run with:
  GOOGLE_APPLICATION_CREDENTIALS=... FIREBASE_PROJECT_ID=... python scripts/seed_eras.py
Or with Emulator:
  FIRESTORE_EMULATOR_HOST=localhost:8081 FIREBASE_PROJECT_ID=lockulture-dev python scripts/seed_eras.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.src.firebase import get_db

ERAS_FILE = ROOT / "contracts/fixtures/eras.json"


def seed_eras(dry_run: bool = False) -> None:
    eras = json.loads(ERAS_FILE.read_text(encoding="utf-8"))
    db = get_db()
    batch = db.batch()
    count = 0

    for era in eras:
        ref = db.collection("eras").document(era["id"])
        doc = {
            "schema_version": 1,
            "id": era["id"],
            "name": era["name"],
            "period": era["period"],
            "sort_order": era["sort_order"],
            "fragment_goal": era["fragment_goal"],
        }
        if dry_run:
            print(f"[dry-run] Would seed era: {era['id']} — {era['name']}")
        else:
            batch.set(ref, doc)
            count += 1

    if not dry_run:
        batch.commit()
        print(f"Seeded {count} eras to Firestore.")
    else:
        print(f"Dry-run complete: {len(eras)} eras would be written.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Seed Firestore eras catalog")
    parser.add_argument("--dry-run", action="store_true", help="Print without writing")
    args = parser.parse_args()
    seed_eras(dry_run=args.dry_run)
