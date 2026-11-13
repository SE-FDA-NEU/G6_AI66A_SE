"""Account-owned Gemini keys encrypted at rest, separate from job results."""
import base64

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from fastapi import HTTPException
from pydantic import SecretStr

from app.core.config import settings


def validate_key(value: str) -> SecretStr:
    key = value.strip()
    if not key or len(key) > 256 or any(ord(char) < 33 or ord(char) > 126 for char in key):
        raise HTTPException(400, 'Enter your Gemini API key to analyze documents.')
    return SecretStr(key)


def cipher():
    # Derive a separate encryption key from the stable server secret.
    derived = HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
                   info=b'documind/saved-gemini-key/v1').derive(settings.SECRET_KEY.encode())
    return Fernet(base64.urlsafe_b64encode(derived))


def encrypt_key(owner_id: int, key: SecretStr) -> str:
    return cipher().encrypt(f'{owner_id}:{key.get_secret_value()}'.encode()).decode('ascii')


def decrypt_key(user) -> SecretStr:
    if not user.gemini_api_key_encrypted:
        raise HTTPException(400, 'Enter your Gemini API key to analyze documents.')
    try:
        payload = cipher().decrypt(user.gemini_api_key_encrypted.encode('ascii')).decode()
        owner, key = payload.split(':', 1)
        if owner != str(user.id):
            raise ValueError
        return validate_key(key)
    except (InvalidToken, UnicodeError, ValueError, HTTPException):
        raise HTTPException(409, 'Saved Gemini API key could not be read. Please replace it.') from None
