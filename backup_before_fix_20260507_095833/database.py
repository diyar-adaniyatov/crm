import sqlite3
from datetime import datetime

DB_PATH = "bot_data.db"


def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn

def init_users_table():
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password_hash TEXT,
        email TEXT
    )
    """)

    conn.commit()
    conn.close()


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create clinics table first (referenced by other tables)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS clinics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        timezone TEXT DEFAULT 'Asia/Almaty',
        work_start TEXT DEFAULT '09:00',
        work_end TEXT DEFAULT '18:00',
        slot_step_minutes INTEGER DEFAULT 60,
        is_active INTEGER DEFAULT 1
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_state (
        chat_id TEXT PRIMARY KEY,
        clinic_id INTEGER NOT NULL DEFAULT 1,
        service TEXT,
        full_name TEXT,
        phone TEXT,
        preferred_datetime TEXT,
        status TEXT,
        next_field TEXT,
        booking_status TEXT,
        intent TEXT,
        FOREIGN KEY(clinic_id) REFERENCES clinics(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        clinic_id INTEGER NOT NULL DEFAULT 1,
        chat_id TEXT NOT NULL,
        service TEXT,
        full_name TEXT,
        phone TEXT,
        appointment_at TEXT NOT NULL,
        duration_minutes INTEGER NOT NULL DEFAULT 60,
        status TEXT NOT NULL DEFAULT 'active',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        reminder_24h_sent INTEGER NOT NULL DEFAULT 0,
        reminder_2h_sent INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY(clinic_id) REFERENCES clinics(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS clinic_settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        clinic_id INTEGER NOT NULL DEFAULT 1,
        work_start TEXT NOT NULL DEFAULT '09:00',
        work_end TEXT NOT NULL DEFAULT '18:00',
        slot_step_minutes INTEGER NOT NULL DEFAULT 60,
        clinic_name TEXT DEFAULT 'Клиника',
        FOREIGN KEY(clinic_id) REFERENCES clinics(id)
    )
    """)

    cursor.execute("""
CREATE TABLE IF NOT EXISTS clinic_channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clinic_id INTEGER NOT NULL,
    channel_type TEXT NOT NULL,
    channel_key TEXT NOT NULL UNIQUE,
    channel_token TEXT,
    channel_name TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (clinic_id) REFERENCES clinics(id)
)
    )
    """)
    cursor.execute("PRAGMA table_info(clinic_channels)")
    channel_columns = {row[1] for row in cursor.fetchall()}

    if "channel_token" not in channel_columns:
        cursor.execute("""
        ALTER TABLE clinic_channels ADD COLUMN channel_token TEXT
        """)
    
    
    def get_channel_by_key(channel_type, channel_key):
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
        SELECT clinic_id, channel_key, channel_token, channel_name
        FROM clinic_channels
        WHERE channel_type = ? AND channel_key = ? AND is_active = 1
        """, (channel_type, channel_key))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return {
            "clinic_id": row[0],
            "channel_key": row[1],
            "channel_token": row[2],
            "channel_name": row[3],
        }