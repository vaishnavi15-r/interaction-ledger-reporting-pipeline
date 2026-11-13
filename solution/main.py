
import argparse

from solution.database.db import initialize_database
from solution.ingestion.lead_ingestor import ingest_leads_from_drop
from solution.ingestion.event_ingestor import ingest_events_from_drop
from solution.reports.report_generator import generate_reports


def main():
    parser = argparse.ArgumentParser(
        description="Interaction Ledger & Reporting Pipeline"
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True
    )

    # Ingestion command
    ingest_parser = subparsers.add_parser(
        "ingest",
        help="Ingest lead and event data from a drop"
    )

    ingest_parser.add_argument(
        "drop_path",
        help="Path to the data drop directory"
    )

    # Report command
    report_parser = subparsers.add_parser(
        "report",
        help="Generate all reports"
    )

    report_parser.add_argument(
        "--out",
        required=True,
        help="Output directory for reports"
    )

    args = parser.parse_args()

    initialize_database()

    if args.command == "ingest":
        print(f"\n========== INGESTING {args.drop_path} ==========")

        print("\n========== LEAD INGESTION ==========")
        ingest_leads_from_drop(args.drop_path)

        print("\n========== EVENT INGESTION ==========")
        ingest_events_from_drop(args.drop_path)

        print("\n========== INGESTION COMPLETED ==========")

    elif args.command == "report":
        print("\n========== REPORT GENERATION ==========")
        generate_reports(args.out)


if __name__ == "__main__":
    main()
