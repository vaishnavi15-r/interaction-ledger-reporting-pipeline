
import os
from pathlib import Path
from dotenv import load_dotenv

# Root directory of the assignment repository
BASE_DIR = Path(__file__).resolve().parent.parent

# 2. Load .env from the project root
load_dotenv(BASE_DIR / ".env")

# Assignment data directories
SCHEMA_DIR = BASE_DIR / "assignment-a-data" / "schemas"
DATA_DIR = BASE_DIR / "data"

# Application directories
SOLUTION_DIR = Path(__file__).resolve().parent

# SQLite database location
DATABASE_DIR = SOLUTION_DIR / "database"
DATABASE_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_PATH = DATABASE_DIR / "interaction_ledger.db"

# Security keys from environment variables
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
HMAC_KEY = os.getenv("HMAC_KEY")

# Report output directory
REPORT_DIR = SOLUTION_DIR / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
