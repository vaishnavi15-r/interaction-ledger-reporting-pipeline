
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from solution.database.db import get_connection
from solution.services.encryption import encrypt_pii, hash_phone
from solution.ingestion.validators import normalize_phone
from solution.ingestion.schema_loader import load_dispositions


IST = ZoneInfo("Asia/Kolkata")


def parse_event_timestamp(value):
    """Convert event timestamps into ISO format in IST."""
    value = value.strip()

    if value.endswith("Z"):
        value = value[:-1] + "+00:00"

    parsed = datetime.fromisoformat(value)

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=IST)

    return parsed.astimezone(IST).isoformat()


def increment_stat(connection, stat_name, amount=1):
    """Increase a persistent data-quality counter."""
    connection.execute(
        """
        INSERT INTO event_ingestion_stats (stat_name, stat_value)
        VALUES (?, ?)
        ON CONFLICT(stat_name)
        DO UPDATE SET stat_value = stat_value + excluded.stat_value
        """,
        (stat_name, amount)
    )


def link_events_to_leads(connection):
    """Link events to leads using workflow and hashed phone."""
    connection.execute(
        """
        UPDATE events
        SET lead_id = (
            SELECT leads.id
            FROM leads
            WHERE leads.workflow_id = events.workflow_id
            AND leads.phone_hash = events.phone_hash
        )
        WHERE lead_id IS NULL
        AND phone_hash IS NOT NULL
        """
    )

    # Override events have no phone, so link them through call_id.
    connection.execute(
        """
        UPDATE events
        SET lead_id = (
            SELECT related.lead_id
            FROM events AS related
            WHERE related.call_id = events.call_id
            AND related.lead_id IS NOT NULL
            LIMIT 1
        )
        WHERE lead_id IS NULL
        AND event_type = 'disposition.override'
        AND call_id IS NOT NULL
        """
    )


def ingest_event_file(file_path):
    """Read, validate, encrypt and store one JSONL event file."""
    file_path = Path(file_path)
    dispositions = load_dispositions()

    stats = {
        "events_total": 0,
        "malformed_events": 0,
        "duplicate_events_dropped": 0,
        "orphan_events": 0,
        "unknown_disposition_events": 0
    }

    with get_connection() as connection:

        stored_file = connection.execute(
            """
            SELECT 1 FROM processed_event_files
            WHERE file_path = ?
            """,
            (str(file_path),)
        ).fetchone()

        if stored_file:
            print(f"Already processed: {file_path.name}")
            return {"skipped": True}

        with open(file_path, "r", encoding="utf-8") as file:

            for line in file:
                if not line.strip():
                    continue

                stats["events_total"] += 1

                try:
                    event = json.loads(line)

                    if not isinstance(event, dict):
                        raise ValueError("Event must be a JSON object")

                    required_fields = [
                        "event_id",
                        "event_type",
                        "workflow_id",
                        "call_id",
                        "occurred_at"
                    ]

                    if any(
                        not event.get(field)
                        for field in required_fields
                    ):
                        raise ValueError("Missing required event field")

                    event_id = str(event["event_id"]).strip()
                    event_type = str(event["event_type"]).strip()
                    workflow_id = str(event["workflow_id"]).strip()
                    call_id = str(event["call_id"]).strip()

                    occurred_at = parse_event_timestamp(
                        event["occurred_at"]
                    )

                    payload = event.get("payload", {})

                    if not isinstance(payload, dict):
                        raise ValueError("Invalid event payload")

                    disposition_code = payload.get(
                        "disposition_code"
                    )

                    if disposition_code is not None:
                        disposition_code = str(
                            disposition_code
                        ).strip().lower()

                        if (
                            workflow_id,
                            disposition_code
                        ) not in dispositions:
                            stats["unknown_disposition_events"] += 1
                            increment_stat(
                                connection,
                                "unknown_disposition_events"
                            )
                            continue

                    phone_hash = None

                    if event.get("phone"):
                        try:
                            canonical_phone = normalize_phone(
                                event["phone"]
                            )
                            phone_hash = hash_phone(canonical_phone)
                        except ValueError:
                            phone_hash = None

                    encrypted_payload = encrypt_pii(
                        json.dumps(payload, ensure_ascii=False)
                    )

                    lead_id = None

                    if phone_hash:
                        lead = connection.execute(
                            """
                            SELECT id FROM leads
                            WHERE workflow_id = ?
                            AND phone_hash = ?
                            """,
                            (workflow_id, phone_hash)
                        ).fetchone()

                        if lead:
                            lead_id = lead["id"]

                    if event_type == "disposition.override":
                        related = connection.execute(
                            """
                            SELECT lead_id
                            FROM events
                            WHERE call_id = ?
                            AND lead_id IS NOT NULL
                            LIMIT 1
                            """,
                            (call_id,)
                        ).fetchone()

                        if related:
                            lead_id = related["lead_id"]

                    cursor = connection.execute(
                        """
                        INSERT OR IGNORE INTO events (
                            event_id,
                            workflow_id,
                            event_type,
                            call_id,
                            phone_hash,
                            occurred_at,
                            disposition_code,
                            payload_encrypted,
                            lead_id
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            event_id,
                            workflow_id,
                            event_type,
                            call_id,
                            phone_hash,
                            occurred_at,
                            disposition_code,
                            encrypted_payload,
                            lead_id
                        )
                    )

                    if cursor.rowcount == 0:
                        stats["duplicate_events_dropped"] += 1
                        increment_stat(
                            connection,
                            "duplicate_events_dropped"
                        )

                except (ValueError, TypeError, KeyError):
                    stats["malformed_events"] += 1
                    increment_stat(
                        connection,
                        "malformed_events"
                    )

                except json.JSONDecodeError:
                    stats["malformed_events"] += 1
                    increment_stat(
                        connection,
                        "malformed_events"
                    )

        # Link events that may have arrived before their leads.
        link_events_to_leads(connection)

        # Count currently unresolved events.
        stats["orphan_events"] = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM events
            WHERE lead_id IS NULL
            """
        ).fetchone()["total"]

        increment_stat(
            connection,
            "events_total",
            stats["events_total"]
        )

        connection.execute(
            """
            INSERT INTO processed_event_files (
                file_path,
                processed_at
            )
            VALUES (?, ?)
            """,
            (
                str(file_path),
                datetime.now(IST).isoformat()
            )
        )

    return stats


def ingest_events_from_drop(drop_path):
    """Ingest all JSONL event files in a drop."""
    drop_path = Path(drop_path)
    event_directory = drop_path / "events"

    if not event_directory.exists():
        print(f"No events directory found in {drop_path}")
        return

    event_files = sorted(event_directory.glob("*.jsonl"))

    for event_file in event_files:
        print(f"\nProcessing: {event_file.name}")

        result = ingest_event_file(event_file)

        print("Results:", result)

    print("\nEvent ingestion completed.")
