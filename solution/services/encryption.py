import hmac
import hashlib
from cryptography.fernet import Fernet

from solution.config import ENCRYPTION_KEY, HMAC_KEY


def get_fernet():
    """Create Fernet encryption instance."""
    if not ENCRYPTION_KEY:
        raise ValueError("ENCRYPTION_KEY is not configured")

    return Fernet(ENCRYPTION_KEY.encode())


def encrypt_pii(value):
    """Encrypt sensitive information."""
    if value is None:
        return None

    return get_fernet().encrypt(str(value).encode()).decode()


def decrypt_pii(encrypted_value):
    """Decrypt sensitive information."""
    if encrypted_value is None:
        return None

    return get_fernet().decrypt(encrypted_value.encode()).decode()


def hash_phone(phone):
    """Generate deterministic HMAC hash for phone matching."""
    if not HMAC_KEY:
        raise ValueError("HMAC_KEY is not configured")

    return hmac.new(
        HMAC_KEY.encode(),
        phone.encode(),
        hashlib.sha256
    ).hexdigest()