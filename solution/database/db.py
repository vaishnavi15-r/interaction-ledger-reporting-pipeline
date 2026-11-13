
import sqlite3
from contextlib import contextmanager

from solution.config import DATABASE_PATH


@contextmanager
def get_connection():
    """Create and safely close a SQLite database connection."""
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database():
    """Create the tables required by the interaction ledger."""

    with get_connection() as connection:

        connection.executescript("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_id TEXT NOT NULL,
            phone_hash TEXT NOT NULL,
            phone_encrypted TEXT NOT NULL,
            customer_name_encrypted TEXT NOT NULL,
            external_ref TEXT NOT NULL,
            batch_id TEXT NOT NULL,
            fields_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(workflow_id, phone_hash)
        );

        CREATE TABLE IF NOT EXISTS events (
            event_id TEXT PRIMARY KEY,
            workflow_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            call_id TEXT,
            phone_hash TEXT,
            occurred_at TEXT NOT NULL,
            disposition_code TEXT,
            payload_encrypted TEXT NOT NULL,
            lead_id INTEGER,
            FOREIGN KEY (lead_id) REFERENCES leads(id)
        );

        CREATE TABLE IF NOT EXISTS rejections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_id TEXT NOT NULL,
            batch_id TEXT NOT NULL,
            row_number INTEGER NOT NULL,
            reason TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS field_warnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_id TEXT NOT NULL,
            batch_id TEXT NOT NULL,
            row_number INTEGER NOT NULL,
            field_name TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS processed_drops (
            drop_path TEXT PRIMARY KEY,
            processed_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_leads_workflow
        ON leads(workflow_id);

        CREATE INDEX IF NOT EXISTS idx_events_call
        ON events(call_id);

        CREATE INDEX IF NOT EXISTS idx_events_lead
        ON events(lead_id);

        CREATE INDEX IF NOT EXISTS idx_events_phone
        ON events(workflow_id, phone_hash);

        CREATE TABLE IF NOT EXISTS processed_lead_files (
        file_path TEXT PRIMARY KEY,
        processed_at TEXT NOT NULL);


        CREATE TABLE IF NOT EXISTS processed_event_files (
        file_path TEXT PRIMARY KEY,
        processed_at TEXT NOT NULL);


        CREATE TABLE IF NOT EXISTS event_ingestion_stats (
        stat_name TEXT PRIMARY KEY,
        stat_value INTEGER NOT NULL DEFAULT 0);


        CREATE TABLE IF NOT EXISTS lead_ingestion_stats (
            stat_name TEXT PRIMARY KEY,
            stat_value INTEGER NOT NULL DEFAULT 0);

        """)


if __name__ == "__main__":
    initialize_database()
    print("Database initialized successfully.")
