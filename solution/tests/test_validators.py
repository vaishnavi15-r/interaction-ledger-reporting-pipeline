from solution.ingestion.validators import (
    normalize_header,
    normalize_phone,
    validate_date,
    validate_decimal,
    validate_field_value,
    validate_lead_row
)
from solution.ingestion.schema_loader import load_workflow_schema


def test_normalize_header():
    assert normalize_header(" Mobile_No ") == "mobile no"


def test_normalize_phone():
    assert normalize_phone("9876543210") == "+919876543210"
    assert normalize_phone("919876543210") == "+919876543210"


def test_validate_date():
    assert validate_date("13/11/2026") == "2026-11-13"


def test_validate_decimal():
    assert validate_decimal("₹1,250.50") == "1250.50"


def test_validate_enum():
    field = {
        "type": "enum",
        "values": ["en", "hi", "mr"]
    }

    assert validate_field_value(field, "MR") == "mr"



def test_valid_motor_renewal_row():
    schema = load_workflow_schema("motor_renewal")

    row = {
        "Name": " Rahul ",
        "Mobile_No": "9876543210",
        "Policy No": "POL123",
        "Premium": "1,500",
        "Language": "MR"
    }

    values, rejection, warnings = validate_lead_row(row, schema)

    assert rejection is None
    assert values["customer_name"] == "Rahul"
    assert values["phone"] == "+919876543210"
    assert values["preferred_language"] == "mr"
    assert warnings == []


def test_missing_required_field():
    schema = load_workflow_schema("motor_renewal")

    row = {
        "customer_name": "Rahul",
        "policy_number": "POL123"
    }

    values, rejection, warnings = validate_lead_row(row, schema)

    assert rejection == "missing_required:phone"


def test_invalid_optional_field():
    schema = load_workflow_schema("motor_renewal")

    row = {
        "customer_name": "Rahul",
        "phone": "9876543210",
        "policy_number": "POL123",
        "premium_amount": "invalid"
    }

    values, rejection, warnings = validate_lead_row(row, schema)

    assert rejection is None
    assert values["premium_amount"] is None
    assert "premium_amount" in warnings