import binascii
import secrets
import hashlib


def hash_password(password: str) -> str:
    """Hash a password for storing."""
    salt = hashlib.sha256(
        secrets.token_bytes(60)
    ).hexdigest().encode('ascii')
    pwdhash = hashlib.pbkdf2_hmac(
        'sha512',
        password.encode('utf-8'),
        salt,
        100000
    )
    pwdhash = binascii.hexlify(pwdhash)
    return (salt + pwdhash).decode('ascii')


def verify_password(password: str, challenger: str) -> bool:
    """Verify a stored password against one provided by user"""
    salt = password[:64]
    password = password[64:]
    pwdhash = hashlib.pbkdf2_hmac(
        'sha512',
        challenger.encode('utf-8'),
        salt.encode('ascii'),
        100000
    )
    pwdhash = binascii.hexlify(pwdhash).decode('ascii')
    return pwdhash == password
