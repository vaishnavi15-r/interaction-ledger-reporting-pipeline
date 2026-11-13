
import csv
import json
from pathlib import Path
from datetime import datetime, timezone

from solution.database.db import get_connection
from solution.ingestion.schema_loader import load_workflow_schema
from solution.ingestion.validators import validate_lead_row
from solution.services.encryption import encrypt_pii, hash_phone


def ingest_lead_file(file_path, workflow_id):
    """Validate and ingest one CSV lead file."""

    file_path = Path(file_path)
    batch_id = file_path.stem
    schema = load_workflow_schema(workflow_id)

    stats = {
        "total_rows": 0,
        "accepted": 0,
        "rejected": 0,
        "duplicates": 0,
        "warnings": 0,
        "skipped": False
    }

    # Find the reference field, such as policy_number or order_id
    reference_field = next(
        field["name"]
        for field in schema["fields"]
        if field.get("reference", False)
    )

    with open(file_path, "r", encoding="utf-8-sig", newline="") as file:

        reader = csv.DictReader(file)

        with get_connection() as connection:

            # Prevent processing the same file twice
            already_processed = connection.execute(
                "SELECT 1 FROM processed_lead_files WHERE file_path = ?",
                (str(file_path.resolve()),)
            ).fetchone()

            if already_processed:
                stats["skipped"] = True
                return stats

            row_number = 0

            for raw_row in reader:

                # Ignore completely blank rows
                if not any(
                    str(value or "").strip()
                    for value in raw_row.values()
                ):
                    continue

                row_number += 1
                stats["total_rows"] += 1

                values, rejection, warnings = validate_lead_row(
                    raw_row, schema
                )

                # Record rejected rows without storing PII
                if rejection:
                    connection.execute(
                        """
                        INSERT INTO rejections
                        (workflow_id, batch_id, row_number, reason)
                        VALUES (?, ?, ?, ?)
                        """,
                        (workflow_id, batch_id, row_number, rejection)
                    )

                    stats["rejected"] += 1
                    continue

                # Record optional-field warnings
                for field_name in warnings:
                    connection.execute(
                        """
                        INSERT INTO field_warnings
                        (workflow_id, batch_id, row_number, field_name)
                        VALUES (?, ?, ?, ?)
                        """,
                        (workflow_id, batch_id, row_number, field_name)
                    )

                    stats["warnings"] += 1

                # Generate deterministic identity hash
                phone_hash = hash_phone(values["phone"])

                # Encrypt every PII field before storage
                stored_fields = {}

                for field in schema["fields"]:
                    name = field["name"]
                    value = values.get(name)

                    if field.get("pii", False) and value is not None:
                        stored_fields[name] = encrypt_pii(value)
                    else:
                        stored_fields[name] = value

                customer_name_encrypted = stored_fields.get(
                    "customer_name"
                )

                phone_encrypted = stored_fields["phone"]

                external_ref = values[reference_field]

                now = datetime.now(timezone.utc).isoformat()

                # Check whether this lead already exists
                existing = connection.execute(
                    """
                    SELECT id, fields_json
                    FROM leads
                    WHERE workflow_id = ? AND phone_hash = ?
                    """,
                    (workflow_id, phone_hash)
                ).fetchone()

                if existing:
                    # Merge: update only non-null incoming fields
                    merged_fields = json.loads(existing["fields_json"])

                    for field in schema["fields"]:
                        name = field["name"]

                        if values.get(name) is not None:
                            merged_fields[name] = stored_fields[name]

                    connection.execute(
                        """
                        UPDATE leads
                        SET customer_name_encrypted = ?,
                            external_ref = ?,
                            fields_json = ?,
                            updated_at = ?
                        WHERE id = ?
                        """,
                        (
                            customer_name_encrypted,
                            external_ref,
                            json.dumps(merged_fields),
                            now,
                            existing["id"]
                        )
                    )

                    stats["duplicates"] += 1

                else:
                    # First occurrence creates the lead
                    connection.execute(
                        """
                        INSERT INTO leads (
                            workflow_id,
                            phone_hash,
                            phone_encrypted,
                            customer_name_encrypted,
                            external_ref,
                            batch_id,
                            fields_json,
                            created_at,
                            updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            workflow_id,
                            phone_hash,
                            phone_encrypted,
                            customer_name_encrypted,
                            external_ref,
                            batch_id,
                            json.dumps(stored_fields),
                            now,
                            now
                        )
                    )

                stats["accepted"] += 1


            # Persist lead ingestion statistics
            for stat_name in ("total_rows", "duplicates"):
                connection.execute(
                    """
                    INSERT INTO lead_ingestion_stats (stat_name, stat_value)
                    VALUES (?, ?)
                    ON CONFLICT(stat_name)
                    DO UPDATE SET stat_value =
                        stat_value + excluded.stat_value
                    """,
                    (stat_name, stats[stat_name]))
            # Mark the file processed in the same transaction
            connection.execute(
                """
                INSERT INTO processed_lead_files
                (file_path, processed_at)
                VALUES (?, ?)
                """,
                (str(file_path.resolve()), now)
            )

    return stats


def ingest_leads_from_drop(drop_path):
    """Ingest every workflow CSV file in one drop."""

    drop_path = Path(drop_path)
    leads_directory = drop_path / "leads"

    if not leads_directory.exists():
        raise FileNotFoundError(
            f"Leads directory not found: {leads_directory}"
        )

    csv_files = sorted(
        leads_directory.glob("*/*.csv"),
        key=lambda path: (path.name, path.parent.name)
    )

    if not csv_files:
        raise FileNotFoundError("No lead CSV files found")

    results = {}

    for file_path in csv_files:
        workflow_id = file_path.parent.name

        result = ingest_lead_file(file_path, workflow_id)

        results[str(file_path)] = result

        print(f"\nFile: {file_path}")
        print(f"Workflow: {workflow_id}")
        print(f"Results: {result}")

    return results
