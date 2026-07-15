# MIGRATION GUIDE: Upgrade to Custom Multi-Family House (MFH) Architecture

This document serves as an exhaustive, step-by-step instruction manual for developers or local LLM assistants (e.g., Cline, Gemini CLI) to execute the migration of a live PaperVault archive containing 5,000+ documents from the old generic flat categories to the new highly specialized **Multi-Family House (MFH)** architecture.

---

## Objective
Upgrade the SQLite database schema, translate the old categories into the new streamlined ones (UG, EG, OG, DG), and physically relocate all 5,000+ archived PDF files on disk into the newly designed root subdirectories (`1_Privat_und_Alltag` and `2_Mehrfamilienhaus_Verwaltung`) without re-running LLM inferences.

---

## PHASE 1: Safety Backup (Pre-Flight Checks)
Before running any script, execute these safety commands on the production machine:

1.  **Stop all processes:** Ensure that the FastAPI backend, the React frontend, and the Watchdog thread (`archiver.py`) are completely stopped.
2.  **Backup the SQLite Database:** Locate your active `archive.db` (usually at `C:/Archive/archive.db` or configured in `.env`). Create a copy of this file:
    ```bash
    cp C:/Archive/archive.db C:/Archive/archive_backup_before_mfh.db
    ```
3.  **Verify DB connection:** Ensure that the backup database is not corrupted.

---

## PHASE 2: Database Schema Upgrade (Automated)
Start the FastAPI backend once or run `python -c "import sys; sys.path.insert(0, 'backend'); import db; db.init_db()"` to run the database migrations.
*   **What this does:** The migration array in `schema.py` automatically appends the `property_unit` column and its lookup index `idx_documents_property_unit` to the SQLite `documents` table. Existing documents will default to `NULL`.

---

## PHASE 3: Physical Folder and Metadata Migration

Write the following Python script as `migrate_to_mfh.py` in the root folder of the workspace on the production machine:

```python
# migrate_to_mfh.py
"""
PaperVault - Live Archive Migration Script
Upgrades categories, assigns initial property units, moves files physically on disk,
and updates database file paths for 5,000+ records.
"""
import os
import shutil
import sqlite3
import re
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.environ.get("DB_PATH", "C:/Archive/archive.db")
TARGET_BASE = os.environ.get("TARGET_BASE", "C:/Archive")

# 1. Old-to-new category translation map
CATEGORY_TRANSLATION = {
    "Versicherung":           "Privatversicherungen",
    "Fahrzeug & Werkstatt":   "Fahrzeug",
    "Einkauf & Bestellungen": "Einkauf & Konsum",
    "Kassenbon & Quittung":   "Einkauf & Konsum",
    "Geräte & Garantie":      "Einkauf & Konsum",
    "Kommunikation":          "Sonstiges",
    "Behörde & Urkunden":     "Sonstiges",
    "Ausbildung & Verein":    "Kinder_und_Ausbildung",
    "Wohnen & Eigentum":      "EG_Kosten", # Default private housing costs to EG
    "Vermieter":              "Haus_Gemeinkosten" # Default legacy Vermieter to Gesamthaus
}

# 2. Sequential flat folder name mappings starting with numeric prefixes
NEW_FOLDER_MAP = {
    "Arbeit & Rente":         "01_Arbeit_und_Rente",
    "Bank & Finanzen":        "02_Banken_und_Finanzen",
    "Gesundheit":             "03_Gesundheit_und_Vorsorge",
    "EG_Kosten":              "04_EG_Kosten",
    "Fahrzeug":               "05_Fahrzeug",
    "Einkauf & Konsum":       "06_Konsum_und_Einkauf",
    "Haus_Gemeinkosten":      "07_Gesamthaus_Gemeinkosten",
    "OG_Miete":               "08_Vermietung_OG",
    "DG_Miete":               "09_Vermietung_DG",
    "Privatversicherungen":   "10_Versicherungen",
    "UG_Kosten":              "11_UG_Kosten",
    "Sonstiges":              "12_Sonstiges",
    "Kinder_und_Ausbildung":  "13_Kinder_und_Ausbildung",
}

# 3. Dynamic root directory mappings
ROOT_MAP = {
    "Haus_Gemeinkosten":      "2_Mehrfamilienhaus_Verwaltung",
    "OG_Miete":               "2_Mehrfamilienhaus_Verwaltung",
    "DG_Miete":               "2_Mehrfamilienhaus_Verwaltung",
} # All others default to "1_Privat_und_Alltag"

def migrate():
    DB_PATH_NORM = os.path.normpath(DB_PATH)
    TARGET_BASE_NORM = os.path.normpath(TARGET_BASE)

    if not os.path.exists(DB_PATH_NORM):
        print(f"Error: Database file not found at {DB_PATH_NORM}")
        return

    print(f"Starting migration on database: {DB_PATH_NORM}")
    print(f"Archive storage base path: {TARGET_BASE_NORM}")

    conn = sqlite3.connect(DB_PATH_NORM)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Query all active documents
    docs = cursor.execute("SELECT id, file_path, category, sender, date, document_type, filename, keywords, summary, low_value, status, archived_at, confidence FROM documents").fetchall()
    print(f"Retrieved {len(docs)} documents from database.")

    migrated_count = 0
    skipped_count = 0

    for doc in docs:
        old_path = doc["file_path"]
        if not old_path or not os.path.exists(old_path):
            skipped_count += 1
            continue

        # A. Translate Category
        cat = doc["category"] or "Sonstiges"
        new_cat = CATEGORY_TRANSLATION.get(cat, cat)

        # B. Assign Property Unit, Vehicle, and Child (Heuristic based on metadata)
        property_unit = None
        vehicle_id = None
        child_name = None

        sender_lower = (doc["sender"] or "").lower()
        summary_lower = (doc["summary"] or "").lower()
        filename_lower = (doc["filename"] or "").lower()
        keywords_lower = (doc["keywords"] or "").lower()

        # 1. Building-level property units
        if "gemeinkosten" in sender_lower or "gebäudeversicherung" in sender_lower or "schornsteinfeger" in sender_lower or "wartung" in summary_lower:
            new_cat = "Haus_Gemeinkosten"
            property_unit = "Gesamthaus"
        elif "mieter og" in sender_lower or "obergeschoss" in sender_lower or "og rechts" in sender_lower or "og links" in sender_lower or "og" in filename_lower:
            new_cat = "OG_Miete"
            property_unit = "OG"
        elif "mieter dg" in sender_lower or "dachgeschoss" in sender_lower or "dg rechts" in sender_lower or "dg" in filename_lower:
            new_cat = "DG_Miete"
            property_unit = "DG"
        elif new_cat == "EG_Kosten" or "erdgeschoss" in sender_lower or "eg" in filename_lower:
            new_cat = "EG_Kosten"
            property_unit = "EG"
        elif new_cat == "UG_Kosten" or "untergeschoss" in sender_lower or "keller" in sender_lower or "ug" in filename_lower:
            new_cat = "UG_Kosten"
            property_unit = "UG"

        # 2. Heuristics for Vehicles
        if new_cat == "Fahrzeug":
            if any(w in sender_lower or w in summary_lower or w in filename_lower or w in keywords_lower for w in ("golf", "vw", "volkswagen")):
                vehicle_id = "Golf"
            elif any(w in sender_lower or w in summary_lower or w in filename_lower or w in keywords_lower for w in ("tesla", "model 3", "model y")):
                vehicle_id = "Tesla"
            elif any(w in sender_lower or w in summary_lower or w in filename_lower or w in keywords_lower for w in ("honda", "motorrad", "zweirad")):
                vehicle_id = "Motorrad"

        # 3. Heuristics for Children
        for child in ("lena", "felix", "maximilian"):
            if child in sender_lower or child in summary_lower or child in filename_lower or child in keywords_lower:
                child_name = child.capitalize()
                # Upgrade education/school files to the new specialized category
                if cat in ("Ausbildung & Verein", "Sonstiges"):
                    new_cat = "Kinder_und_Ausbildung"
                break

        # C. Auto-Verification & Low Value Triage
        low_value = doc["low_value"]
        status = doc["status"]
        archived_at = doc["archived_at"]
        confidence = doc["confidence"]

        # Spam & Low Value Triage: Move low_value items to Temp-Archive
        if low_value == 1 or "parkschein" in summary_lower or "brötchen" in summary_lower:
            low_value = 1
            root_dir = "low_value_dump"
            # Reset retention timer to today so the 90-day shredder works correctly
            archived_at = datetime.now().isoformat(timespec="seconds")
            folder_name = ""
        else:
            # Auto-Verification Matrix (Pareto 80/20 Rule)
            if status != "locked" and new_cat != "Sonstiges" and doc["sender"]:
                # If LLM confidence was high or sender is known, auto-lock it!
                if confidence == "high" or any(k in sender_lower for k in ("allianz", "stadtwerke", "telekom", "amazon", "paypal")):
                    status = "locked"

            folder_name = NEW_FOLDER_MAP.get(new_cat, "12_Sonstiges")
            root_dir = ROOT_MAP.get(new_cat, "1_Privat_und_Alltag")

        use_year = new_cat != "Privatversicherungen" # Policies are timeless

        # Extract year
        year_match = re.search(r'\b(\d{4})\b', str(doc["date"] or ""))
        year = year_match.group() if year_match else "Unbekannt"

        # Clean sender and prepend vehicle/child tags inside folders if available
        safe_sender = re.sub(r'[\\/:*?"<>|\r\n\t]', '_', doc["sender"])[:50].strip() if doc["sender"] else "Unbekannt"

        # Form final folder path based on sub-tags
        if root_dir == "low_value_dump":
            new_dir = os.path.join(TARGET_BASE_NORM, root_dir, year)
        else:
            if new_cat == "Fahrzeug" and vehicle_id:
                folder_name = os.path.join(folder_name, vehicle_id)
            elif (new_cat == "Kinder_und_Ausbildung" or new_cat == "Gesundheit") and child_name:
                folder_name = os.path.join(folder_name, child_name)

            if use_year:
                new_dir = os.path.join(TARGET_BASE_NORM, root_dir, folder_name, safe_sender, year)
            else:
                new_dir = os.path.join(TARGET_BASE_NORM, root_dir, folder_name, safe_sender)

        os.makedirs(new_dir, exist_ok=True)
        new_path = os.path.normpath(os.path.join(new_dir, doc["filename"]))

        # D. Move physical file (NFH instant-move)
        if os.path.abspath(old_path) != os.path.abspath(new_path):
            try:
                # Handle filename collisions
                if os.path.exists(new_path):
                    base, ext = os.path.splitext(new_path)
                    counter = 1
                    while os.path.exists(f"{base}_{counter}{ext}"):
                        counter += 1
                    new_path = f"{base}_{counter}{ext}"

                shutil.move(old_path, new_path)
            except Exception as e:
                print(f"Error moving file {old_path} -> {new_path}: {e}")
                continue

        # E. Update SQLite Record
        cursor.execute(
            "UPDATE documents SET file_path = ?, category = ?, property_unit = ?, vehicle_id = ?, child_name = ?, low_value = ?, status = ?, archived_at = ? WHERE id = ?",
            (new_path, new_cat, property_unit, vehicle_id, child_name, low_value, status, archived_at, doc["id"])
        )
        migrated_count += 1

    conn.commit()
    conn.close()

    print("\n" + "="*80)
    print("MIGRATION COMPLETED SUCCESSFULLY!")
    print(f"Physically migrated & updated: {migrated_count} documents.")
    print(f"Skipped (physical file not found): {skipped_count} documents.")
    print("="*80)

if __name__ == "__main__":
    migrate()
```

### Execution:
Execute the script using the project's Python environment:
```bash
.venv/Scripts/python migrate_to_mfh.py
```
*(Since moving files on the same NTFS filesystem is simply an entry reallocation, moving 5,000+ files will take less than 5 seconds).*

---

## PHASE 4: Post-Migration Cleanup & Curation

1.  **Remove Empty Old Folders:**
    Start the PaperVault server, log into the Web-UI, navigate to `Monitor` (System), and click **"Leere Ordner bereinigen"** (or trigger `POST /monitor/cleanup-empty-folders` via curl). This will immediately remove all empty deprecated directories (e.g. `09 - Kommunikation`, `06 - Wohnen & Eigentum`) from your disk.
2.  **Curate Building-level Labels (The final polish):**
    Because the Python script maps building-level categories naively based on sender names, some invoices (like local water bills or chimney sweeps) might still have `property_unit = null`.
    *   **To do:** Go to the main **Document List** inside the frontend, filter by the category `Haus_Gemeinkosten` (which now shows all building-level costs), select the corresponding invoices, and use the **Bulk-Edit** interface to set them to `Gesamthaus` (or `OG` / `DG` / `EG` / `UG` for unit-specific maintenance).
    *   **Locking:** Once verified, these records are locked in the DB, fully protecting your 5,000+ archive from any future automated overrides!
