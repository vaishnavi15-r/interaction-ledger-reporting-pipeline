
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def normalize_header(header):
    """
    Normalize CSV headers:
    ' Mobile_No ' -> 'mobile no'
    'Customer   Name' -> 'customer name'
    """
    return re.sub(r"[_\s]+", " ", header.strip().lower())


def normalize_phone(value):
    """Convert valid Indian phone numbers to +91XXXXXXXXXX."""

    digits = re.sub(r"\D", "", str(value))

    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]

    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]

    if len(digits) != 10 or digits[0] not in "6789":
        raise ValueError("invalid_phone")

    return "+91" + digits


def validate_date(value):
    """Parse supported date formats and return YYYY-MM-DD."""

    formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d-%b-%Y"
    ]

    for date_format in formats:
        try:
            parsed_date = datetime.strptime(value, date_format)
            return parsed_date.strftime("%Y-%m-%d")
        except ValueError:
            continue

    raise ValueError("invalid_date")


def validate_decimal(value):
    """Parse non-negative decimal values, including Indian currency formats."""

    cleaned = re.sub(
        r"^(?:₹|rs\.?|inr)\s*",
        "",
        value.strip(),
        flags=re.IGNORECASE
    )

    pattern = r"(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?"

    if not re.fullmatch(pattern, cleaned):
        raise ValueError("invalid_decimal")

    try:
        amount = Decimal(cleaned.replace(",", ""))
    except InvalidOperation:
        raise ValueError("invalid_decimal")

    if amount < 0:
        raise ValueError("invalid_decimal")

    return str(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def validate_field_value(field, raw_value):
    """
    Validate a single field using its JSON schema definition.

    Returns:
        Normalized value, or None if blank.

    Raises:
        ValueError if the value is invalid.
    """

    if raw_value is None:
        return None

    value = str(raw_value).strip()

    if not value:
        return None

    field_type = field["type"]

    if field_type == "string":
        return value

    if field_type == "phone":
        return normalize_phone(value)

    if field_type == "date":
        return validate_date(value)

    if field_type == "decimal":
        return validate_decimal(value)

    if field_type == "enum":
        normalized = value.lower()
        allowed_values = [item.lower() for item in field["values"]]

        if normalized not in allowed_values:
            raise ValueError("invalid_enum")

        return normalized

    raise ValueError(f"unsupported_type:{field_type}")



def validate_lead_row(raw_row, schema):
    """
    Validate one CSV row against a workflow schema.

    Returns:
        values: Validated field values
        rejection_reason: None or first rejection reason
        warnings: List of invalid optional fields
    """

    values = {}
    warnings = []

    # Map normalized CSV headers and aliases to schema fields
    header_mapping = {}

    for field in schema["fields"]:
        header_mapping[normalize_header(field["name"])] = field["name"]

        for alias in field.get("aliases", []):
            header_mapping[normalize_header(alias)] = field["name"]

    # Normalize the CSV row's headers
    normalized_row = {}

    for header, value in raw_row.items():
        if header is None:
            continue

        normalized_header = normalize_header(header)
        field_name = header_mapping.get(normalized_header)

        # Ignore unknown columns
        if field_name:
            normalized_row[field_name] = value

    # Process fields in schema order
    for field in schema["fields"]:
        field_name = field["name"]
        raw_value = normalized_row.get(field_name)

        try:
            validated_value = validate_field_value(field, raw_value)

            if validated_value is None and field.get("required", False):
                return (
                    values,
                    f"missing_required:{field_name}",
                    warnings
                )

            values[field_name] = validated_value

        except ValueError as error:
            if field.get("required", False):
                return values, str(error), warnings

            values[field_name] = None
            warnings.append(field_name)

    return values, None, warnings
