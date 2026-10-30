import sqlite3
import bcrypt
import csv
import os
import shutil
from datetime import datetime
from config import (
    APP_DATA_DIR as CONFIG_APP_DATA_DIR,
    DATABASE_FILE as CONFIG_DATABASE_FILE,
    LEGACY_DATABASE_FILE as CONFIG_LEGACY_DATABASE_FILE,
    BACKUP_FILE as CONFIG_BACKUP_FILE,
    BACKUP_DIR as CONFIG_BACKUP_DIR,
    logger
)

APP_DATA_DIR = CONFIG_APP_DATA_DIR
DATABASE_FILE = CONFIG_DATABASE_FILE
LEGACY_DATABASE_FILE = CONFIG_LEGACY_DATABASE_FILE
BACKUP_FILE = CONFIG_BACKUP_FILE
BACKUP_DIR = CONFIG_BACKUP_DIR

def prepare_database_location():
    """Run once at app startup, before any create/migrate calls."""
    os.makedirs(APP_DATA_DIR, exist_ok=True)
    os.makedirs(BACKUP_DIR, exist_ok=True)

    # One-time move for people upgrading from the old relative-path version
    if os.path.exists(LEGACY_DATABASE_FILE) and not os.path.exists(DATABASE_FILE):
        shutil.copy2(LEGACY_DATABASE_FILE, DATABASE_FILE)
        logger.info(f"Migrated legacy database from {LEGACY_DATABASE_FILE} to {DATABASE_FILE}")

    # Keep a safety copy of the pre-migration data (only the first time)
    if os.path.exists(DATABASE_FILE) and not os.path.exists(BACKUP_FILE):
        shutil.copy2(DATABASE_FILE, BACKUP_FILE)
        logger.info(f"Created pre-migration safety backup at {BACKUP_FILE}")

def create_database_backup(tag=None):
    """
    Creates a timestamped snapshot of the active database in the backups directory.
    Returns the absolute path to the backup file, or None if no DB exists yet.
    """
    if not os.path.exists(DATABASE_FILE):
        return None
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = f"_{tag}" if tag else ""
    filename = f"meditrack_backup_{timestamp}{suffix}.db"
    dest = os.path.join(BACKUP_DIR, filename)
    shutil.copy2(DATABASE_FILE, dest)
    logger.info(f"Created database snapshot at {dest}")
    return dest

def check_database_integrity():
    """
    Runs SQLite integrity check.
    Returns (True, ['ok']) if healthy, or (False, [error_strings]) if issues detected.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check")
        rows = [r[0] for r in cursor.fetchall()]
        is_ok = (len(rows) == 1 and rows[0].lower() == "ok")
        return is_ok, rows
    finally:
        conn.close()

def vacuum_database():
    """
    Executes VACUUM to reclaim free space, defragment pages, and optimize indices.
    """
    conn = get_connection()
    try:
        conn.execute("VACUUM")
        logger.info("Database vacuumed and optimized successfully.")
        return True
    finally:
        conn.close()

def hash_password(plain_password):
    password_bytes = plain_password.encode("utf-8")
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed.decode("utf-8")

def check_password(plain_password, hashed_password):
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8")
    )

def get_connection():
    conn = sqlite3.connect(DATABASE_FILE)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def create_users_table():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def create_medications_table():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS medications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            dosage TEXT NOT NULL,
            time TEXT NOT NULL,
            frequency TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    conn.commit()
    conn.close()

def create_dose_records_table():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dose_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            medication_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            taken_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (medication_id) REFERENCES medications (id)
        )
    """)
    conn.commit()
    conn.close()

def create_care_recipients_table():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS care_recipients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            caregiver_user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            relationship TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (caregiver_user_id) REFERENCES users (id)
        )
    """)
    conn.commit()
    conn.close()

def add_recipient_id_column():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE medications ADD COLUMN recipient_id INTEGER REFERENCES care_recipients (id)")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    conn.close()

def add_quantity_and_expiry_columns():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE medications ADD COLUMN quantity_remaining INTEGER")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE medications ADD COLUMN expiry_date TEXT")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

def create_medication_schedules_table():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS medication_schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            medication_id INTEGER NOT NULL,
            time TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (medication_id) REFERENCES medications (id) ON DELETE CASCADE
        )
    """)
    conn.commit()
    conn.close()

def add_schedule_id_column_to_dose_records():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE dose_records ADD COLUMN schedule_id INTEGER REFERENCES medication_schedules (id) ON DELETE SET NULL")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    conn.close()

def migrate_comma_times_to_schedules():
    """
    Idempotent migration: Reads all existing medications and populates
    medication_schedules for any comma-separated (or single) times not yet migrated.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, time FROM medications")
    meds = cursor.fetchall()

    for med_id, raw_time in meds:
        if not raw_time:
            continue
        items = [t.strip() for t in raw_time.replace(";", ",").split(",") if t.strip()]
        for t in items:
            cursor.execute(
                "SELECT id FROM medication_schedules WHERE medication_id = ? AND time = ?",
                (med_id, t)
            )
            if cursor.fetchone() is None:
                cursor.execute(
                    "INSERT INTO medication_schedules (medication_id, time) VALUES (?, ?)",
                    (med_id, t)
                )
    conn.commit()
    conn.close()

def init_schema_migrations_table():
    """Initializes the version tracking table for database schema migrations."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
    finally:
        conn.close()

def get_applied_migrations():
    """Returns a set of all integer version numbers that have been applied."""
    init_schema_migrations_table()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT version FROM schema_migrations")
        return {row[0] for row in cursor.fetchall()}
    finally:
        conn.close()

def record_migration(version, name):
    """Records that a migration step has completed successfully."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO schema_migrations (version, name) VALUES (?, ?)",
            (version, name)
        )
        conn.commit()
    finally:
        conn.close()

def run_all_migrations():
    """
    Unified entry point for database setup and sequential schema migrations.
    Safely executes pending migrations and marks them in schema_migrations.
    """
    applied = get_applied_migrations()

    # Step 1: Base Relational Schema
    if 1 not in applied:
        create_users_table()
        create_medications_table()
        create_dose_records_table()
        create_care_recipients_table()
        record_migration(1, "create_base_tables")
        logger.info("Applied migration 1: create_base_tables")

    # Step 2: Inventory & Expiry Columns
    if 2 not in applied:
        add_recipient_id_column()
        add_quantity_and_expiry_columns()
        record_migration(2, "add_recipient_and_stock_columns")
        logger.info("Applied migration 2: add_recipient_and_stock_columns")

    # Step 3: 1NF Medication Schedules & Dose Slot Linking
    if 3 not in applied:
        create_medication_schedules_table()
        add_schedule_id_column_to_dose_records()
        migrate_comma_times_to_schedules()
        record_migration(3, "normalize_schedules_table_1nf")
        logger.info("Applied migration 3: normalize_schedules_table_1nf")

def insert_user(name, email, password_hash):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, password_hash)
        )
        conn.commit()
        return True, f"User '{name}' created successfully."
    except sqlite3.IntegrityError:
        return False, f"Could not create user: the email '{email}' is already registered."
    finally:
        conn.close()

def get_all_users():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users")
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_user_by_email(email):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    row = cursor.fetchone()
    conn.close()
    return row

def login_user(email, password):
    user = get_user_by_email(email)
    if user is None:
        return False, "No account found with that email."

    stored_hash = user[3]
    if check_password(password, stored_hash):
        return True, f"Welcome back, {user[1]}!"
    else:
        return False, "Incorrect password."

def insert_medication(user_id, name, dosage, time, frequency, recipient_id=None, quantity_remaining=None, expiry_date=None):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO medications (user_id, name, dosage, time, frequency, recipient_id, quantity_remaining, expiry_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, name, dosage, time, frequency, recipient_id, quantity_remaining, expiry_date)
        )
        medication_id = cursor.lastrowid
        if time:
            for t in [x.strip() for x in time.replace(";", ",").split(",") if x.strip()]:
                cursor.execute(
                    "INSERT INTO medication_schedules (medication_id, time) VALUES (?, ?)",
                    (medication_id, t)
                )
        conn.commit()
        return medication_id
    finally:
        conn.close()

def insert_medications_batch(user_id, medications):
    """
    Inserts multiple medications in a single atomic transaction.
    Each item in medications is a tuple:
    (name, dosage, time, frequency, recipient_id, quantity_remaining, expiry_date)
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        for m in medications:
            cursor.execute(
                """
                INSERT INTO medications (user_id, name, dosage, time, frequency, recipient_id, quantity_remaining, expiry_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, m[0], m[1], m[2], m[3], m[4], m[5], m[6])
            )
            med_id = cursor.lastrowid
            raw_time = m[2]
            if raw_time:
                for t in [x.strip() for x in raw_time.replace(";", ",").split(",") if x.strip()]:
                    cursor.execute(
                        "INSERT INTO medication_schedules (medication_id, time) VALUES (?, ?)",
                        (med_id, t)
                    )
        conn.commit()
    finally:
        conn.close()

def get_medications_for_user(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT medications.id, medications.user_id, medications.name, medications.dosage,
               medications.time, medications.frequency, medications.created_at,
               medications.recipient_id, care_recipients.name,
               medications.quantity_remaining, medications.expiry_date
        FROM medications
        LEFT JOIN care_recipients ON medications.recipient_id = care_recipients.id
        WHERE medications.user_id = ?
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_schedules_for_medication(medication_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, medication_id, time FROM medication_schedules WHERE medication_id = ? ORDER BY time", (medication_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_all_schedules_for_user(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT medication_schedules.id, medication_schedules.medication_id, medication_schedules.time,
               medications.name, medications.dosage, medications.recipient_id, care_recipients.name
        FROM medication_schedules
        JOIN medications ON medication_schedules.medication_id = medications.id
        LEFT JOIN care_recipients ON medications.recipient_id = care_recipients.id
        WHERE medications.user_id = ?
        ORDER BY medication_schedules.time
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def update_medication(medication_id, name, dosage, time, frequency, recipient_id=None, quantity_remaining=None, expiry_date=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE medications
        SET name = ?, dosage = ?, time = ?, frequency = ?, recipient_id = ?, quantity_remaining = ?, expiry_date = ?
        WHERE id = ?
        """,
        (name, dosage, time, frequency, recipient_id, quantity_remaining, expiry_date, medication_id)
    )
    cursor.execute("DELETE FROM medication_schedules WHERE medication_id = ?", (medication_id,))
    if time:
        for t in [x.strip() for x in time.replace(";", ",").split(",") if x.strip()]:
            cursor.execute(
                "INSERT INTO medication_schedules (medication_id, time) VALUES (?, ?)",
                (medication_id, t)
            )
    conn.commit()
    conn.close()

def delete_medication(medication_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM dose_records WHERE medication_id = ?", (medication_id,))
    cursor.execute("DELETE FROM medication_schedules WHERE medication_id = ?", (medication_id,))
    cursor.execute("DELETE FROM medications WHERE id = ?", (medication_id,))
    conn.commit()
    conn.close()

def decrement_quantity(medication_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE medications SET quantity_remaining = quantity_remaining - 1 WHERE id = ? AND quantity_remaining IS NOT NULL AND quantity_remaining > 0",
        (medication_id,)
    )
    conn.commit()
    conn.close()

def refill_medication(medication_id, added_quantity):
    """Adds added_quantity to medication's quantity_remaining."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE medications
            SET quantity_remaining = COALESCE(quantity_remaining, 0) + ?
            WHERE id = ?
            """,
            (added_quantity, medication_id)
        )
        conn.commit()
    finally:
        conn.close()

def insert_dose_record(medication_id, status, schedule_id=None):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO dose_records (medication_id, status, schedule_id) VALUES (?, ?, ?)",
            (medication_id, status, schedule_id)
        )
        conn.commit()
    finally:
        conn.close()

def get_dose_history_for_user(user_id):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT medications.name, dose_records.status, dose_records.taken_at, medication_schedules.time
            FROM dose_records
            JOIN medications ON dose_records.medication_id = medications.id
            LEFT JOIN medication_schedules ON dose_records.schedule_id = medication_schedules.id
            WHERE medications.user_id = ?
            ORDER BY dose_records.taken_at DESC
        """, (user_id,))
        rows = cursor.fetchall()
        return rows
    finally:
        conn.close()

def get_adherence_report_data(user_id):
    """
    Retrieves full adherence report data for a user including medication details,
    scheduled slot, caregiver recipient, taken timestamp, and status.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT dose_records.taken_at,
                   medications.name,
                   medications.dosage,
                   COALESCE(medication_schedules.time, 'N/A') AS scheduled_time,
                   COALESCE(care_recipients.name, 'Myself') AS recipient_name,
                   dose_records.status
            FROM dose_records
            JOIN medications ON dose_records.medication_id = medications.id
            LEFT JOIN medication_schedules ON dose_records.schedule_id = medication_schedules.id
            LEFT JOIN care_recipients ON medications.recipient_id = care_recipients.id
            WHERE medications.user_id = ?
            ORDER BY dose_records.taken_at DESC
        """, (user_id,))
        return cursor.fetchall()
    finally:
        conn.close()

def export_adherence_to_csv(user_id, output_path):
    """
    Exports the user's adherence records to a CSV file.
    Returns (True, output_path) on success, or (False, error_message) on failure.
    """
    try:
        rows = get_adherence_report_data(user_id)
        with open(output_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Date & Time", "Medication", "Dosage", "Scheduled Slot", "Recipient", "Status"])
            for r in rows:
                writer.writerow(r)
        return True, output_path
    except Exception as e:
        return False, str(e)

def insert_care_recipient(caregiver_user_id, name, relationship):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO care_recipients (caregiver_user_id, name, relationship) VALUES (?, ?, ?)",
        (caregiver_user_id, name, relationship)
    )
    conn.commit()
    conn.close()

def get_care_recipients_for_caregiver(caregiver_user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM care_recipients WHERE caregiver_user_id = ?", (caregiver_user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def update_care_recipient(recipient_id, name, relationship):
    """Updates an existing care recipient's name and relationship."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE care_recipients SET name = ?, relationship = ? WHERE id = ?",
        (name, relationship, recipient_id)
    )
    conn.commit()
    conn.close()

def delete_care_recipient(recipient_id):
    """
    Deletes a care recipient safely.
    First unlinks any medications associated with this recipient (sets recipient_id to NULL),
    preventing orphaned references, then deletes the recipient record.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE medications SET recipient_id = NULL WHERE recipient_id = ?", (recipient_id,))
    cursor.execute("DELETE FROM care_recipients WHERE id = ?", (recipient_id,))
    conn.commit()
    conn.close()