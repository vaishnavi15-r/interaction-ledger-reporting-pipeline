# Submission

> Replace everything in _italics_. Be concise: bullet points are fine. We read every word.

## Candidate
- **Name:** Vaishnavi Vishvas Bovane
- **Assignment chosen:** A (Data)
- **Time spent (honest estimate):** 11 hr

## How to run

Requirements: Python 3.10+ and pip.

```bash
# Create and activate a virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create a .env file in the project root with:
# ENCRYPTION_KEY=<a Fernet key>
# HMAC_KEY=<a strong random secret>

# Initialize and ingest data in order
python -m solution.main ingest data/drop_1
python -m solution.main ingest data/drop_2

# Generate reports
python -m solution.main report --out reports/

# Run tests
python -m pytest -v
```

Generate an encryption key with:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Generate an HMAC secret with:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## Design

The solution is a Python command-line pipeline with separate ingestion, validation, security, database, and reporting modules.

- The lead ingestion module reads CSV files and validates records using workflow-specific JSON schemas.
- The event ingestion module reads JSONL events, validates event data, detects duplicate event IDs, and links events to leads.
- The validation layer normalizes headers and validates phone numbers, dates, decimal values, and enums.
- The security layer encrypts PII using Fernet and hashes canonical phone numbers using HMAC-SHA256 for identity matching.
- The reporting layer calculates lead buckets, call statistics, dispositions, and data-quality metrics.

SQLite is used as the persistent database.

Main database tables include:
- `leads`: customer records, encrypted PII, phone hashes, workflow and batch information.
- `events`: call and disposition events, encrypted payloads, and lead associations.
- `rejections`: rejected CSV rows and reasons.
- `field_warnings`: optional-field validation warnings.
- `processed_lead_files` and `processed_event_files`: ingestion tracking for idempotency.
- Ingestion statistics tables: persistent data-quality counters.

The unique constraint on `(workflow_id, phone_hash)` prevents duplicate lead identities. Event IDs are stored as primary keys to prevent duplicate event insertion.

## Decisions & assumptions

| Decision | Why | Alternative considered |
|---|---|---|
| SQLite for persistence | Simple, local, and suitable for this assignment | PostgreSQL |
| Fernet encryption for PII | Provides authenticated symmetric encryption | Plain-text storage |
| HMAC-SHA256 for phone identity | Supports deterministic matching without storing the phone as the identity key | Direct phone-number comparison |
| Store timestamps in IST | Makes reporting consistent with the required reporting timezone | Keeping all report dates in UTC |
| Preserve the first lead's batch ID | Maintains the original batch attribution when duplicate records are merged | Moving the lead to the latest batch |
| Ignore unknown CSV columns | Allows input files to contain additional fields without breaking ingestion | Rejecting rows with extra columns |
| Track processed files | Prevents repeated ingestion of the same file | Reprocessing every file |

## Failure modes considered

- Invalid or malformed CSV values are rejected or recorded as optional-field warnings.
- Invalid phone numbers and dates are handled by field validation.
- Duplicate lead identities are merged rather than inserted as separate leads.
- Duplicate event IDs are dropped.
- Events that cannot yet be linked to a lead remain orphaned and can be linked when matching lead data becomes available.
- Unknown disposition codes are counted and ignored.
- Reprocessing an already processed file is skipped.
- PII is encrypted before being stored, and phone identity matching uses HMAC hashes.

Known limitations:
- Automated tests currently cover encryption and validation; full end-to-end ingestion and reporting scenarios are not covered by the existing test suite.
- The final data contains orphan events that could not be linked to a lead.
- The implementation uses SQLite rather than a production database deployment.

## Testing

Executed:
```bash
python -m pytest -v
```

Result: 10 tests passed.

Coverage includes:
- Encryption and decryption.
- Phone hashing.
- Header normalization.
- Phone normalization.
- Date and decimal validation.
- Enum validation.
- Valid lead-row processing.
- Missing required fields.
- Invalid optional fields.

Also manually verified:
- Both data drops can be ingested through the CLI.
- Repeated ingestion skips already processed files.
- All five report files are generated.
- CSV output row counts and data-quality metrics.

Not yet covered by automated tests:
- Full lead and event ingestion integration.
- Late event linking across drops.
- Report calculations and edge cases.
- Crash recovery during file ingestion.

## Results

Generated all five required reports:

- `batch_summary.csv`: 6 data rows.
- `daily_overview.csv`: 33 data rows.
- `lead_report.csv`: 1,892 data rows.
- `rejections.csv`: 108 data rows.
- `data_quality.json`: generated successfully.

Data-quality results:
- Lead rows processed: 2,057.
- Rejected lead rows: 108.
- Duplicate lead rows merged: 57.
- Field warnings: 122.
- Events read: 8,745.
- Malformed events: 8.
- Duplicate events dropped: 235.
- Orphan events remaining: 461.
- Unknown disposition events: 21.

One notable result was that some events initially could not be linked because their lead records arrived in a later data drop. The pipeline supports linking events after additional lead data is ingested, although 461 events remained orphaned in the final dataset.

## If I had another day

1. Add automated integration tests for lead ingestion, event ingestion, duplicate merging, and late event linking.
2. Add report-generation tests with controlled sample datasets.
3. Improve crash recovery and transactional handling for file ingestion.
4. Add structured logging and clearer error reporting.
5. Evaluate PostgreSQL support for larger datasets.
