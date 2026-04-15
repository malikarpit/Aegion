#!/usr/bin/env python3
"""
Aegion Seed Script Wrapper (W8.3).

Wrapper around app.scripts.seed_data that provides CLI interface
for seeding the database with demo data.

Usage:
  python scripts/seed.py                    # Insert seed data
  python scripts/seed.py --dry-run          # Print data without inserting
  python scripts/seed.py --reset            # Truncate tables first, then seed

Docker usage:
  docker compose exec backend python -m scripts.seed
"""

import argparse
import json
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    parser = argparse.ArgumentParser(description="Aegion Database Seeder")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Generate and print seed data without inserting to DB",
    )
    parser.add_argument(
        "--reset", action="store_true",
        help="Truncate all seeded tables before inserting",
    )
    parser.add_argument(
        "--format", choices=["json", "summary"], default="summary",
        help="Output format for --dry-run (default: summary)",
    )
    args = parser.parse_args()

    try:
        from app.scripts.seed_data import generate_all, insert_to_supabase
    except ImportError:
        print("ERROR: Cannot import seed_data module. Run from project root.")
        sys.exit(1)

    # Generate all seed data
    print("🌱 Generating seed data...")
    data = generate_all()

    # Print summary
    print(f"\n📊 Seed Data Summary:")
    for table_name, rows in data.items():
        count = len(rows) if isinstance(rows, list) else 1
        print(f"   {table_name}: {count} rows")
    total = sum(len(r) if isinstance(r, list) else 1 for r in data.values())
    print(f"   ─────────────────────")
    print(f"   Total: {total} rows")

    if args.dry_run:
        if args.format == "json":
            print("\n📋 Full seed data (JSON):")
            print(json.dumps(data, indent=2, default=str))
        print("\n✅ Dry run complete (no data inserted)")
        return

    if args.reset:
        print("\n⚠️  Resetting (truncating) seeded tables...")
        _reset_tables(data.keys())

    print("\n📤 Inserting seed data...")
    try:
        insert_to_supabase(data)
        print("✅ Seed data inserted successfully!")
    except Exception as exc:
        print(f"❌ Seed insertion failed: {exc}")
        sys.exit(1)


def _reset_tables(table_names):
    """Truncate tables before re-seeding."""
    try:
        from app.db.supabase_client import get_supabase_client
        client = get_supabase_client()
        for table in table_names:
            try:
                client.table(table).delete().neq("id", "impossible-id").execute()
                print(f"   Truncated: {table}")
            except Exception as exc:
                print(f"   Skip (not found): {table} ({exc})")
    except Exception as exc:
        print(f"   ⚠️  Cannot connect to DB for reset: {exc}")


if __name__ == "__main__":
    main()
