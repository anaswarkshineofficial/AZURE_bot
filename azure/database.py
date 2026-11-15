import json
import sqlite3
from pathlib import Path

from azure.config import BASE_DIR

DB_PATH = BASE_DIR / "data" / "azure.db"


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database():
    conn = _connect()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id TEXT PRIMARY KEY,
                template_name TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT,
                event_type TEXT,
                summary TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS backups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT,
                snapshot TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS guild_themes (
                guild_id TEXT PRIMARY KEY,
                theme_name TEXT NOT NULL DEFAULT 'azor_redline',
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS managed_resources (
                guild_id TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                resource_id TEXT NOT NULL,
                resource_name TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (guild_id, resource_type, resource_id)
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def set_guild_template(guild_id: str, template_name: str):
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO guild_settings (guild_id, template_name) VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET template_name = excluded.template_name, updated_at = CURRENT_TIMESTAMP",
            (str(guild_id), template_name),
        )
        conn.commit()
    finally:
        conn.close()


def get_guild_template(guild_id: str):
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT template_name FROM guild_settings WHERE guild_id = ?",
            (str(guild_id),),
        ).fetchone()
        return row["template_name"] if row else None
    finally:
        conn.close()


def log_event(guild_id: str, event_type: str, summary: str):
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO audit_logs (guild_id, event_type, summary) VALUES (?, ?, ?)",
            (str(guild_id), event_type, summary),
        )
        conn.commit()
    finally:
        conn.close()


def save_backup(guild_id: str, snapshot: dict):
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO backups (guild_id, snapshot) VALUES (?, ?)",
            (str(guild_id), json.dumps(snapshot, ensure_ascii=False)),
        )
        conn.commit()
    finally:
        conn.close()


def list_backups(guild_id: str):
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT id, created_at, snapshot FROM backups WHERE guild_id = ? ORDER BY id DESC LIMIT 10",
            (str(guild_id),),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def track_managed_resource(guild_id: int | str, resource_type: str, resource_id: int | str, resource_name: str):
    """Record only resources AZURE itself created; cleanup never guesses by name."""
    conn = _connect()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO managed_resources (guild_id, resource_type, resource_id, resource_name) VALUES (?, ?, ?, ?)",
            (str(guild_id), resource_type, str(resource_id), resource_name),
        )
        conn.commit()
    finally:
        conn.close()


def list_managed_resources(guild_id: int | str):
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT resource_type, resource_id, resource_name, created_at FROM managed_resources WHERE guild_id = ? ORDER BY resource_type, resource_name",
            (str(guild_id),),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def forget_managed_resource(guild_id: int | str, resource_type: str, resource_id: int | str):
    conn = _connect()
    try:
        conn.execute(
            "DELETE FROM managed_resources WHERE guild_id = ? AND resource_type = ? AND resource_id = ?",
            (str(guild_id), resource_type, str(resource_id)),
        )
        conn.commit()
    finally:
        conn.close()


def set_guild_theme(guild_id: int | str, theme_name: str):
    conn = _connect()
    try:
        conn.execute(
            """INSERT INTO guild_themes (guild_id, theme_name) VALUES (?, ?)
               ON CONFLICT(guild_id) DO UPDATE SET theme_name=excluded.theme_name,
               updated_at=CURRENT_TIMESTAMP""",
            (str(guild_id), theme_name),
        )
        conn.commit()
    finally:
        conn.close()


def get_guild_theme(guild_id: int | str):
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT theme_name FROM guild_themes WHERE guild_id=?",
            (str(guild_id),),
        ).fetchone()
        return row["theme_name"] if row else "azor_redline"
    finally:
        conn.close()


def initialize_community_tables():
    """Create storage for verification, whitelist applications and support tickets."""
    conn = _connect()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS whitelist_applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                game_name TEXT NOT NULL,
                age TEXT NOT NULL,
                experience TEXT NOT NULL,
                reason TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                review_channel_id TEXT,
                review_message_id TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS support_tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT NOT NULL,
                channel_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                ticket_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
    finally:
        conn.close()


def create_whitelist_application(guild_id, user_id, game_name, age, experience, reason):
    conn = _connect()
    try:
        cur = conn.execute(
            """INSERT INTO whitelist_applications
               (guild_id,user_id,game_name,age,experience,reason)
               VALUES (?,?,?,?,?,?)""",
            (str(guild_id), str(user_id), game_name, age, experience, reason),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def set_whitelist_review_message(application_id, channel_id, message_id):
    conn = _connect()
    try:
        conn.execute(
            "UPDATE whitelist_applications SET review_channel_id=?, review_message_id=? WHERE id=?",
            (str(channel_id), str(message_id), int(application_id)),
        )
        conn.commit()
    finally:
        conn.close()


def get_whitelist_application(application_id):
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM whitelist_applications WHERE id=?", (int(application_id),)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_whitelist_status(application_id, status):
    conn = _connect()
    try:
        conn.execute(
            "UPDATE whitelist_applications SET status=? WHERE id=? AND status='pending'",
            (status, int(application_id)),
        )
        conn.commit()
        return conn.total_changes > 0
    finally:
        conn.close()


def create_support_ticket(guild_id, channel_id, user_id, ticket_type):
    conn = _connect()
    try:
        cur = conn.execute(
            """INSERT INTO support_tickets (guild_id,channel_id,user_id,ticket_type)
               VALUES (?,?,?,?)""",
            (str(guild_id), str(channel_id), str(user_id), ticket_type),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def close_support_ticket(channel_id):
    conn = _connect()
    try:
        conn.execute(
            "UPDATE support_tickets SET status='closed' WHERE channel_id=? AND status='open'",
            (str(channel_id),),
        )
        conn.commit()
    finally:
        conn.close()
