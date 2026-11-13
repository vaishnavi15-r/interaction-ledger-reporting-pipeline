
from solution.services.encryption import (
    encrypt_pii,
    decrypt_pii,
    hash_phone
)


def test_encryption():
    original = "9876543210"

    encrypted = encrypt_pii(original)

    assert encrypted != original
    assert decrypt_pii(encrypted) == original


def test_phone_hash():
    phone = "+919876543210"

    first_hash = hash_phone(phone)
    second_hash = hash_phone(phone)

    assert first_hash == second_hash
    assert first_hash != phone
