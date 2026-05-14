from datetime import timedelta

import pytest
from jose import JWTError

from app.core.security import create_access_token, decode_token, hash_password, verify_password


def test_hash_password_and_verify():
    plain = "MySecurePass123!"
    hashed = hash_password(plain)
    assert hashed != plain
    assert verify_password(plain, hashed)


def test_verify_password_wrong_password():
    hashed = hash_password("correct_password")
    assert not verify_password("wrong_password", hashed)


def test_create_and_decode_token():
    token = create_access_token("user-123")
    payload = decode_token(token)
    assert payload["sub"] == "user-123"
    assert payload["type"] == "access"


def test_token_expiration():
    token = create_access_token("user-456", expires_delta=timedelta(seconds=-1))
    with pytest.raises(JWTError):
        decode_token(token)


def test_invalid_token():
    with pytest.raises(JWTError):
        decode_token("not.a.valid.token")
