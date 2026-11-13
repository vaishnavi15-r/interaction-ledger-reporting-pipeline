import json
import csv

from solution.config import SCHEMA_DIR


def load_workflow_schema(workflow_id):
    """
    Load the JSON schema for a specific workflow.
    Example: motor_renewal or policy_feedback.
    """

    schema_path = SCHEMA_DIR / f"{workflow_id}.json"

    if not schema_path.exists():
        raise FileNotFoundError(
            f"Schema not found for workflow: {workflow_id}"
        )

    with open(schema_path, "r", encoding="utf-8") as file:
        schema = json.load(file)

    return schema


def load_all_workflow_schemas():
    """
    Load all workflow schemas from the schemas directory.
    """

    schemas = {}

    for schema_path in SCHEMA_DIR.glob("*.json"):
        with open(schema_path, "r", encoding="utf-8") as file:
            schema = json.load(file)

        workflow_id = schema["workflow_id"]
        schemas[workflow_id] = schema

    return schemas


def load_dispositions():
    """
    Load disposition definitions.

    Key format:
        (workflow_id, disposition_code)
    """

    disposition_path = SCHEMA_DIR / "dispositions.csv"

    if not disposition_path.exists():
        raise FileNotFoundError("dispositions.csv not found")

    dispositions = {}

    with open(
        disposition_path,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as file:

        reader = csv.DictReader(file)

        for row in reader:
            workflow_id = row["workflow_id"].strip()
            code = row["code"].strip().lower()

            dispositions[(workflow_id, code)] = {
                "label": row["label"].strip(),
                "is_terminal": row["is_terminal"].strip().lower() == "true",
                "is_success": row["is_success"].strip().lower() == "true"
            }

    return dispositions