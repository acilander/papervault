"""
Pfad-Migration nach Archiv-Umzug.

Ausführen NACHDEM:
  1. Der Archiv-Ordner an den neuen Ort verschoben wurde
  2. Die .env Datei mit SOURCE_DIR und TARGET_BASE aktualisiert wurde

Verwendung:
  python migrate_paths.py --old "C:/Archive" --new "D:/Archive" --dry-run
  python migrate_paths.py --old "C:/Archive" --new "D:/Archive"
"""
import sys
import os
import argparse

sys.path.insert(0, 'backend')
from db.connection import get_conn

parser = argparse.ArgumentParser()
parser.add_argument('--old', required=True, help='Alter Basispfad, z.B. C:/Archive')
parser.add_argument('--new', required=True, help='Neuer Basispfad, z.B. D:/Archive')
parser.add_argument('--dry-run', action='store_true', help='Nur anzeigen, nichts ändern')
args = parser.parse_args()

old = args.old.rstrip('/\\')
new = args.new.rstrip('/\\')

with get_conn() as conn:
    rows = conn.execute("SELECT id, file_path FROM documents").fetchall()
    affected = [r for r in rows if r['file_path'] and r['file_path'].startswith(old)]

    print(f"Gefunden: {len(affected)} von {len(rows)} Einträgen betroffen")
    print(f"Ersetze: '{old}' → '{new}'\n")

    for r in affected[:5]:
        new_path = r['file_path'].replace(old, new, 1)
        print(f"  {r['file_path']}")
        print(f"  → {new_path}\n")
    if len(affected) > 5:
        print(f"  ... und {len(affected) - 5} weitere\n")

    if args.dry_run:
        print("DRY-RUN: Keine Änderungen vorgenommen. Ohne --dry-run erneut ausführen.")
        sys.exit(0)

    confirm = input(f"Wirklich {len(affected)} Einträge aktualisieren? (ja/nein): ")
    if confirm.lower() != 'ja':
        print("Abgebrochen.")
        sys.exit(0)

    n = conn.execute(
        "UPDATE documents SET file_path = REPLACE(file_path, ?, ?)",
        (old, new)
    ).rowcount
    print(f"\n✓ {n} Einträge aktualisiert.")
