
import csv
from pathlib import Path

from solution.database.db import get_connection
from solution.ingestion.schema_loader import load_workflow_schema
from solution.ingestion.validators import validate_lead_row


def main():
    drops = [Path("data/drop_1"), Path("data/drop_2")]

    with get_connection() as connection:
        processed_files = {
            row["file_path"]
            for row in connection.execute(
                "SELECT file_path FROM processed_lead_files"
            ).fetchall()
        }

    seen_leads = set()
    total_rows = 0
    duplicates = 0
    processed_count = 0

    for drop in drops:
        leads_directory = drop / "leads"

        csv_files = sorted(
            leads_directory.glob("*/*.csv"),
            key=lambda path: (path.name, path.parent.name)
        )

        for file_path in csv_files:
            if str(file_path.resolve()) not in processed_files:
                continue

            workflow_id = file_path.parent.name
            schema = load_workflow_schema(workflow_id)

            with open(
                file_path, "r", encoding="utf-8-sig", newline=""
            ) as file:
                reader = csv.DictReader(file)

                for raw_row in reader:
                    if not any(
                        str(value or "").strip()
                        for value in raw_row.values()
                    ):
                        continue

                    total_rows += 1

                    values, rejection, warnings = validate_lead_row(
                        raw_row, schema
                    )

                    if rejection:
                        continue

                    identity = (workflow_id, values["phone"])

                    if identity in seen_leads:
                        duplicates += 1
                    else:
                        seen_leads.add(identity)

            processed_count += 1

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO lead_ingestion_stats (stat_name, stat_value)
            VALUES ('total_rows', ?)
            ON CONFLICT(stat_name)
            DO UPDATE SET stat_value = excluded.stat_value
            """,
            (total_rows,)
        )

        connection.execute(
            """
            INSERT INTO lead_ingestion_stats (stat_name, stat_value)
            VALUES ('duplicates', ?)
            ON CONFLICT(stat_name)
            DO UPDATE SET stat_value = excluded.stat_value
            """,
            (duplicates,)
        )

    print("Backfill completed!")
    print("Processed files:", processed_count)
    print("Total nonblank rows:", total_rows)
    print("Duplicate lead rows:", duplicates)


if __name__ == "__main__":
    main()
