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
    """)
    
    
    cursor.execute("PRAGMA table_info(clinic_channels)")
    channel_columns = {row[1] for row in cursor.fetchall()}

    if "channel_token" not in channel_columns:
        cursor.execute("""
        ALTER TABLE clinic_channels ADD COLUMN channel_token TEXT
        """)
    # Create clinics table first (referenced by other tables)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS clinics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        address TEXT DEFAULT '',
        timezone TEXT DEFAULT 'Asia/Almaty',
        work_start TEXT DEFAULT '09:00',
        work_end TEXT DEFAULT '18:00',
        slot_step_minutes INTEGER DEFAULT 60,
        working_days TEXT DEFAULT '0,1,2,3,4,5',
        is_active INTEGER DEFAULT 1
    )
    """)

    cursor.execute("PRAGMA table_info(clinics)")
    clinic_columns = {row[1] for row in cursor.fetchall()}

    if "timezone" not in clinic_columns:
        cursor.execute("ALTER TABLE clinics ADD COLUMN timezone TEXT DEFAULT 'Asia/Almaty'")
    if "address" not in clinic_columns:
        cursor.execute("ALTER TABLE clinics ADD COLUMN address TEXT DEFAULT ''")
    if "work_start" not in clinic_columns:
        cursor.execute("ALTER TABLE clinics ADD COLUMN work_start TEXT DEFAULT '09:00'")
    if "work_end" not in clinic_columns:
        cursor.execute("ALTER TABLE clinics ADD COLUMN work_end TEXT DEFAULT '18:00'")
    if "slot_step_minutes" not in clinic_columns:
        cursor.execute("ALTER TABLE clinics ADD COLUMN slot_step_minutes INTEGER DEFAULT 60")
    if "working_days" not in clinic_columns:
        cursor.execute("ALTER TABLE clinics ADD COLUMN working_days TEXT DEFAULT '0,1,2,3,4,5'")
    if "is_active" not in clinic_columns:
        cursor.execute("ALTER TABLE clinics ADD COLUMN is_active INTEGER DEFAULT 1")
    

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
        working_days TEXT NOT NULL DEFAULT '0,1,2,3,4,5',
        bot_pause_hours INTEGER NOT NULL DEFAULT 12,
        clinic_name TEXT DEFAULT 'Клиника',
        address TEXT DEFAULT '',
        FOREIGN KEY(clinic_id) REFERENCES clinics(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS services (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        clinic_id INTEGER NOT NULL DEFAULT 1,
        name TEXT NOT NULL,
        price INTEGER,
        duration_minutes INTEGER NOT NULL DEFAULT 60,
        is_active INTEGER NOT NULL DEFAULT 1,
        UNIQUE(clinic_id, name),
        FOREIGN KEY(clinic_id) REFERENCES clinics(id)
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS doctors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        clinic_id INTEGER NOT NULL DEFAULT 1,
        full_name TEXT NOT NULL,
        profession TEXT NOT NULL,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(clinic_id) REFERENCES clinics(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS faq_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        clinic_id INTEGER NOT NULL DEFAULT 1,
        question TEXT NOT NULL,
        answer TEXT NOT NULL,
        is_active INTEGER NOT NULL DEFAULT 1,
        UNIQUE(clinic_id, question),
        FOREIGN KEY(clinic_id) REFERENCES clinics(id)
    )
    """)

    # Migration: Check for and add missing columns to existing tables
    
    # Migrate user_state table
    cursor.execute("PRAGMA table_info(user_state)")
    user_state_columns = {row[1] for row in cursor.fetchall()}
    
    if "clinic_id" not in user_state_columns:
        cursor.execute("""
        ALTER TABLE user_state ADD COLUMN clinic_id INTEGER NOT NULL DEFAULT 1
        """)

    # Migrate bookings table
    cursor.execute("PRAGMA table_info(bookings)")
    booking_columns = {row[1] for row in cursor.fetchall()}
    
    if "clinic_id" not in booking_columns:
        cursor.execute("""
        ALTER TABLE bookings ADD COLUMN clinic_id INTEGER NOT NULL DEFAULT 1
        """)
    
    if "reminder_24h_sent" not in booking_columns:
        cursor.execute("""
        ALTER TABLE bookings ADD COLUMN reminder_24h_sent INTEGER NOT NULL DEFAULT 0
        """)
    
    if "reminder_2h_sent" not in booking_columns:
        cursor.execute("""
        ALTER TABLE bookings ADD COLUMN reminder_2h_sent INTEGER NOT NULL DEFAULT 0
        """)

    if "duration_minutes" not in booking_columns:
        cursor.execute("""
        ALTER TABLE bookings ADD COLUMN duration_minutes INTEGER NOT NULL DEFAULT 60
        """)

    # Migrate services table
    cursor.execute("PRAGMA table_info(services)")
    services_columns = {row[1] for row in cursor.fetchall()}
    
    if "clinic_id" not in services_columns:
        cursor.execute("""
        ALTER TABLE services ADD COLUMN clinic_id INTEGER NOT NULL DEFAULT 1
        """)

    if "price" not in services_columns:
        cursor.execute("""
        ALTER TABLE services ADD COLUMN price INTEGER
        """)

    if "duration_minutes" not in services_columns:
        cursor.execute("""
        ALTER TABLE services ADD COLUMN duration_minutes INTEGER NOT NULL DEFAULT 60
        """)

    if "category" not in services_columns:
        cursor.execute("""
        ALTER TABLE services ADD COLUMN category TEXT
        """)

    if "description" not in services_columns:
        cursor.execute("""
        ALTER TABLE services ADD COLUMN description TEXT
        """)

    if "sort_order" not in services_columns:
        cursor.execute("""
        ALTER TABLE services ADD COLUMN sort_order INTEGER DEFAULT 0
        """)

    # Migrate faq_items table
    cursor.execute("PRAGMA table_info(faq_items)")
    faq_columns = {row[1] for row in cursor.fetchall()}
    
    if "clinic_id" not in faq_columns:
        cursor.execute("""
        ALTER TABLE faq_items ADD COLUMN clinic_id INTEGER NOT NULL DEFAULT 1
        """)

    # Migrate clinic_settings table
    cursor.execute("PRAGMA table_info(clinic_settings)")
    settings_columns = {row[1] for row in cursor.fetchall()}
    
    if "clinic_id" not in settings_columns:
        cursor.execute("""
        ALTER TABLE clinic_settings ADD COLUMN clinic_id INTEGER NOT NULL DEFAULT 1
        """)
    if "working_days" not in settings_columns:
        cursor.execute("""
        ALTER TABLE clinic_settings ADD COLUMN working_days TEXT NOT NULL DEFAULT '0,1,2,3,4,5'
        """)
    if "bot_pause_hours" not in settings_columns:
        cursor.execute("""
        ALTER TABLE clinic_settings ADD COLUMN bot_pause_hours INTEGER NOT NULL DEFAULT 12
        """)
    if "clinic_name" not in settings_columns:
        cursor.execute("""
        ALTER TABLE clinic_settings ADD COLUMN clinic_name TEXT DEFAULT 'Клиника'
        """)
    if "address" not in settings_columns:
        cursor.execute("""
        ALTER TABLE clinic_settings ADD COLUMN address TEXT DEFAULT ''
        """)

    # Ensure default clinic exists
    cursor.execute("SELECT COUNT(*) FROM clinics")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
        INSERT INTO clinics (id, name, timezone, work_start, work_end, slot_step_minutes, working_days, is_active)
        VALUES (1, 'Клиника', 'Asia/Almaty', '09:00', '18:00', 60, '0,1,2,3,4,5', 1)
        """)
        
    cursor.execute("SELECT COUNT(*) FROM clinic_settings WHERE clinic_id = 1")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
        INSERT INTO clinic_settings (clinic_id, work_start, work_end, slot_step_minutes, working_days, bot_pause_hours, clinic_name, address)
        VALUES (1, '10:00', '19:00', 30, '0,1,2,3,4,5', 12, 'Клиника', '')
        """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS platform_admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL UNIQUE,
        granted_by TEXT NOT NULL,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Create clinic_admins table if missing
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS clinic_admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        clinic_id INTEGER NOT NULL,
        email TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL,
        is_active INTEGER NOT NULL DEFAULT 1,
        FOREIGN KEY(clinic_id) REFERENCES clinics(id)
    )
    """)

    # Create conversations table if missing
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        clinic_id INTEGER NOT NULL,
        chat_id TEXT NOT NULL,
        full_name TEXT,
        phone TEXT,
        last_user_message TEXT,
        last_bot_reply TEXT,
        status TEXT NOT NULL DEFAULT 'active',
        needs_operator INTEGER NOT NULL DEFAULT 0,
        has_booking INTEGER NOT NULL DEFAULT 0,
        is_lost INTEGER NOT NULL DEFAULT 0,
        follow_up_sent INTEGER NOT NULL DEFAULT 0,
        bot_paused_until TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(clinic_id) REFERENCES clinics(id)
    )
    """)

    # Migrate conversations table columns if already exists
    cursor.execute("PRAGMA table_info(conversations)")
    conversations_columns = {row[1] for row in cursor.fetchall()}

    if "clinic_id" not in conversations_columns:
        cursor.execute("""
        ALTER TABLE conversations ADD COLUMN clinic_id INTEGER NOT NULL DEFAULT 1
        """)

    if "chat_id" not in conversations_columns:
        cursor.execute("""
        ALTER TABLE conversations ADD COLUMN chat_id TEXT NOT NULL DEFAULT ''
        """)

    if "full_name" not in conversations_columns:
        cursor.execute("""
        ALTER TABLE conversations ADD COLUMN full_name TEXT
        """)

    if "phone" not in conversations_columns:
        cursor.execute("""
        ALTER TABLE conversations ADD COLUMN phone TEXT
        """)

    if "last_user_message" not in conversations_columns:
        cursor.execute("""
        ALTER TABLE conversations ADD COLUMN last_user_message TEXT
        """)

    if "last_bot_reply" not in conversations_columns:
        cursor.execute("""
        ALTER TABLE conversations ADD COLUMN last_bot_reply TEXT
        """)

    if "status" not in conversations_columns:
        cursor.execute("""
        ALTER TABLE conversations ADD COLUMN status TEXT NOT NULL DEFAULT 'active'
        """)

    if "needs_operator" not in conversations_columns:
        cursor.execute("""
        ALTER TABLE conversations ADD COLUMN needs_operator INTEGER NOT NULL DEFAULT 0
        """)

    if "has_booking" not in conversations_columns:
        cursor.execute("""
        ALTER TABLE conversations ADD COLUMN has_booking INTEGER NOT NULL DEFAULT 0
        """)

    if "is_lost" not in conversations_columns:
        cursor.execute("""
        ALTER TABLE conversations ADD COLUMN is_lost INTEGER NOT NULL DEFAULT 0
        """)

    if "created_at" not in conversations_columns:
        cursor.execute("""
        ALTER TABLE conversations ADD COLUMN created_at TEXT NOT NULL DEFAULT ''
        """)

    if "updated_at" not in conversations_columns:
        cursor.execute("""
        ALTER TABLE conversations ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''
        """)

    if "follow_up_sent" not in conversations_columns:
        cursor.execute("""
        ALTER TABLE conversations ADD COLUMN follow_up_sent INTEGER NOT NULL DEFAULT 0
        """)

    if "bot_paused_until" not in conversations_columns:
        cursor.execute("""
        ALTER TABLE conversations ADD COLUMN bot_paused_until TEXT
        """)

    # Create messages table for full conversation history
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id INTEGER NOT NULL,
        chat_id TEXT NOT NULL,
        sender_type TEXT NOT NULL DEFAULT 'user',
        text TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(conversation_id) REFERENCES conversations(id)
    )
    """)

    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_messages_conversation_created
    ON messages (conversation_id, created_at DESC, id DESC)
    """)

    # Safe CRM integrity cleanup
    cleanup_ts = datetime.now().isoformat()

    # Remove fully empty/orphaned conversation rows
    cursor.execute("""
    DELETE FROM conversations
    WHERE COALESCE(TRIM(chat_id), '') = ''
      AND COALESCE(TRIM(full_name), '') = ''
      AND COALESCE(TRIM(phone), '') = ''
      AND COALESCE(TRIM(last_user_message), '') = ''
      AND COALESCE(TRIM(last_bot_reply), '') = ''
    """)

    # Remove synthetic ghost rows with no meaningful CRM data
    cursor.execute("""
    DELETE FROM conversations
    WHERE COALESCE(TRIM(chat_id), '') <> ''
      AND TRIM(chat_id) GLOB '*[^0-9-]*'
      AND COALESCE(TRIM(full_name), '') = ''
      AND COALESCE(TRIM(phone), '') = ''
      AND COALESCE(TRIM(last_user_message), '') = ''
      AND COALESCE(TRIM(last_bot_reply), '') = ''
      AND COALESCE(has_booking, 0) = 0
      AND COALESCE(needs_operator, 0) = 0
    """)

    # Normalize message history rows and keep only meaningful linked activity
    cursor.execute("""
    DELETE FROM messages
    WHERE COALESCE(TRIM(text), '') = ''
    """)

    cursor.execute("""
    UPDATE messages
    SET sender_type = 'user'
    WHERE COALESCE(TRIM(sender_type), '') NOT IN ('user', 'bot', 'operator')
    """)

    cursor.execute("""
    UPDATE messages
    SET chat_id = COALESCE(
        NULLIF(TRIM(chat_id), ''),
        (SELECT chat_id FROM conversations WHERE conversations.id = messages.conversation_id)
    )
    WHERE COALESCE(TRIM(chat_id), '') = ''
    """)

    # Keep one CRM conversation row per clinic/chat for real chat IDs
    cursor.execute("""
    DELETE FROM conversations
    WHERE id NOT IN (
        SELECT MAX(id)
        FROM conversations
        WHERE COALESCE(TRIM(chat_id), '') <> ''
        GROUP BY clinic_id, chat_id
    )
      AND COALESCE(TRIM(chat_id), '') <> ''
    """)

    cursor.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS idx_conversations_unique_chat
    ON conversations (clinic_id, chat_id)
    WHERE TRIM(chat_id) <> ''
    """)

    # Sync conversation booking flags with real booking status
    cursor.execute("""
    UPDATE conversations
    SET has_booking = 1,
        is_lost = 0,
        follow_up_sent = 1,
        status = CASE WHEN needs_operator = 1 THEN 'waiting_operator' ELSE 'booked' END,
        updated_at = ?
    WHERE EXISTS (
        SELECT 1 FROM bookings b
        WHERE b.clinic_id = conversations.clinic_id
          AND b.chat_id = conversations.chat_id
          AND b.status = 'active'
    )
    """, (cleanup_ts,))

    cursor.execute("""
    UPDATE conversations
    SET has_booking = 0,
        needs_operator = 0,
        follow_up_sent = 1,
        is_lost = CASE WHEN is_lost = 1 THEN 1 ELSE 0 END,
        status = CASE
            WHEN is_lost = 1 THEN 'no_show'
            WHEN status = 'closed' THEN 'closed'
            ELSE 'cancelled'
        END,
        updated_at = ?
    WHERE status IN ('active', 'booked', 'cancelled', 'lost', 'no_show')
      AND NOT EXISTS (
        SELECT 1 FROM bookings b
        WHERE b.clinic_id = conversations.clinic_id
          AND b.chat_id = conversations.chat_id
          AND b.status = 'active'
    )
      AND EXISTS (
        SELECT 1 FROM bookings b
        WHERE b.clinic_id = conversations.clinic_id
          AND b.chat_id = conversations.chat_id
          AND b.status = 'cancelled'
    )
    """, (cleanup_ts,))

    cursor.execute("""
    UPDATE conversations
    SET has_booking = 0,
        needs_operator = 0,
        is_lost = 0,
        follow_up_sent = 1,
        status = CASE WHEN status = 'closed' THEN 'closed' ELSE 'completed' END,
        updated_at = ?
    WHERE EXISTS (
        SELECT 1 FROM bookings b
        WHERE b.clinic_id = conversations.clinic_id
          AND b.chat_id = conversations.chat_id
          AND b.status = 'completed'
    )
      AND NOT EXISTS (
        SELECT 1 FROM bookings b
        WHERE b.clinic_id = conversations.clinic_id
          AND b.chat_id = conversations.chat_id
          AND b.status = 'active'
    )
    """, (cleanup_ts,))

    cursor.execute("""
    UPDATE conversations
    SET has_booking = 0,
        needs_operator = 0,
        is_lost = 1,
        follow_up_sent = 1,
        status = 'no_show',
        updated_at = ?
    WHERE EXISTS (
        SELECT 1 FROM bookings b
        WHERE b.clinic_id = conversations.clinic_id
          AND b.chat_id = conversations.chat_id
          AND b.status = 'no_show'
    )
      AND NOT EXISTS (
        SELECT 1 FROM bookings b
        WHERE b.clinic_id = conversations.clinic_id
          AND b.chat_id = conversations.chat_id
          AND b.status = 'active'
    )
    """, (cleanup_ts,))

    # Ensure legacy lost statuses remain clinic-friendly in current CRM
    cursor.execute("""
    UPDATE conversations
    SET status = 'no_show', updated_at = ?
    WHERE status = 'lost' AND is_lost = 1
    """, (cleanup_ts,))

    # Backfill latest visible CRM activity from real message history
    cursor.execute("""
    UPDATE conversations
    SET last_user_message = COALESCE(
            (
                SELECT m.text
                FROM messages m
                WHERE m.conversation_id = conversations.id
                  AND m.sender_type = 'user'
                  AND COALESCE(TRIM(m.text), '') <> ''
                ORDER BY datetime(m.created_at) DESC, m.id DESC
                LIMIT 1
            ),
            COALESCE(last_user_message, '')
        ),
        last_bot_reply = COALESCE(
            (
                SELECT CASE
                    WHEN m.sender_type = 'operator' THEN '[Оператор] ' || m.text
                    ELSE m.text
                END
                FROM messages m
                WHERE m.conversation_id = conversations.id
                  AND m.sender_type IN ('bot', 'operator')
                  AND COALESCE(TRIM(m.text), '') <> ''
                ORDER BY datetime(m.created_at) DESC, m.id DESC
                LIMIT 1
            ),
            COALESCE(last_bot_reply, '')
        ),
        updated_at = COALESCE(
            (
                SELECT m.created_at
                FROM messages m
                WHERE m.conversation_id = conversations.id
                  AND COALESCE(TRIM(m.text), '') <> ''
                ORDER BY datetime(m.created_at) DESC, m.id DESC
                LIMIT 1
            ),
            updated_at,
            ?
        )
    WHERE COALESCE(TRIM(chat_id), '') <> ''
    """, (cleanup_ts,))

    # Ensure closed/no-show rows do not stay in active follow-up queues
    cursor.execute("""
    UPDATE conversations
    SET follow_up_sent = 1
    WHERE status IN ('closed', 'lost', 'no_show', 'cancelled')
    """)

    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_bookings_clinic_status_time
    ON bookings (clinic_id, status, appointment_at)
    """)

    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_bookings_chat_status
    ON bookings (clinic_id, chat_id, status)
    """)

    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_user_state_clinic
    ON user_state (clinic_id)
    """)

    # Ensure default admin exists
    cursor.execute("SELECT COUNT(*) FROM clinic_admins WHERE email = 'admin@clinic.local'")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
        INSERT INTO clinic_admins (clinic_id, email, password, is_active)
        VALUES (1, 'admin@clinic.local', 'admin123', 1)
        """)

    conn.commit()
    conn.close()
def add_clinic_channel(clinic_id, channel_type, channel_key, channel_token=None, channel_name=None):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT OR REPLACE INTO clinic_channels 
    (clinic_id, channel_type, channel_key, channel_token, channel_name, is_active)
    VALUES (?, ?, ?, ?, ?, 1)
    """, (clinic_id, channel_type, channel_key, channel_token, channel_name))

    conn.commit()
    conn.close()


def get_clinic_id_by_channel(channel_type, channel_key):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT clinic_id FROM clinic_channels
    WHERE channel_type = ? AND channel_key = ? AND is_active = 1
    """, (channel_type, channel_key))

    row = cursor.fetchone()
    conn.close()

    return row[0] if row else None

def init_auth_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS clinics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        clinic_id INTEGER NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS password_resets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        token TEXT NOT NULL UNIQUE,
        expires_at TEXT NOT NULL,
        used INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS clinic_channels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        clinic_id INTEGER NOT NULL,
        channel_type TEXT NOT NULL,
        channel_key TEXT NOT NULL UNIQUE,
        channel_name TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (clinic_id) REFERENCES clinics(id)
    )
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
    
