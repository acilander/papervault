import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

import config
import db
import storage
from db.sender_repo import get_all, count

print(f"DB_PATH: {config.DB_PATH}")
print(f"Datei existiert: {Path(config.DB_PATH).exists()}")
print(f"Dateigröße: {Path(config.DB_PATH).stat().st_size if Path(config.DB_PATH).exists() else 0} Bytes")

# Ensure table exists
db.init_db()

print(f"Sender-Einträge in DB: {count()}")
for name, entry in get_all().items():
    print(f"  - {name}: {entry['categories']}")

# Simulate a single record_sender call
print("\nSimuliere storage.record_sender('Kommunikation', 'Telekom')...")
changed = storage.record_sender("Kommunikation", "Telekom")
print(f"changed: {changed}")
print(f"Sender-Einträge in DB nach record_sender: {count()}")
for name, entry in get_all().items():
    print(f"  - {name}: {entry['categories']}")

# Clean up the test sender
from db.sender_repo import delete
delete("Telekom")
print(f"\nSender-Einträge in DB nach Bereinigung: {count()}")
