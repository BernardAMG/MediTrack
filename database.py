import sqlite3
import bcrypt

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
    return sqlite3.connect("meditrack.db")

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

    stored_hash = user[3]  # column order: id, name, email, password_hash, created_at
    if check_password(password, stored_hash):
        return True, f"Welcome back, {user[1]}!"
    else:
        return False, "Incorrect password."

def insert_medication(user_id, name, dosage, time, frequency):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO medications (user_id, name, dosage, time, frequency) VALUES (?, ?, ?, ?, ?)",
        (user_id, name, dosage, time, frequency)
    )
    conn.commit()
    conn.close()

def get_medications_for_user(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM medications WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def update_medication(medication_id, name, dosage, time, frequency):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE medications
        SET name = ?, dosage = ?, time = ?, frequency = ?
        WHERE id = ?
        """,
        (name, dosage, time, frequency, medication_id)
    )
    conn.commit()
    conn.close()

def delete_medication(medication_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM medications WHERE id = ?", (medication_id,))
    conn.commit()
    conn.close()

def insert_dose_record(medication_id, status):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO dose_records (medication_id, status) VALUES (?, ?)",
        (medication_id, status)
    )
    conn.commit()
    conn.close()

def get_dose_history_for_user(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT medications.name, dose_records.status, dose_records.taken_at
        FROM dose_records
        JOIN medications ON dose_records.medication_id = medications.id
        WHERE medications.user_id = ?
        ORDER BY dose_records.taken_at DESC
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

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