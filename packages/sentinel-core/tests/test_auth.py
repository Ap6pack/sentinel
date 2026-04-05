# Copyright (c) 2026 Veritas Aequitas Holdings LLC. All rights reserved.

import jwt
import pytest

from sentinel_core.auth.tokens import ALGORITHM, TTL_SECONDS, issue_token, verify_token
from sentinel_core.auth.users import authenticate
from sentinel_core.config import core_settings


def test_issue_and_verify_token():
    token = issue_token("admin")
    payload = verify_token(token)
    assert payload["sub"] == "admin"
    assert "exp" in payload
    assert "iat" in payload


def test_verify_invalid_token():
    with pytest.raises(jwt.InvalidTokenError):
        verify_token("not-a-valid-token")


def test_verify_wrong_secret():
    token = jwt.encode(
        {"sub": "admin", "iat": 0, "exp": 9999999999},
        "wrong-secret",
        algorithm=ALGORITHM,
    )
    with pytest.raises(jwt.InvalidSignatureError):
        verify_token(token)


def test_authenticate_valid():
    assert authenticate(core_settings.admin_username, core_settings.admin_password) is True


def test_authenticate_invalid():
    assert authenticate("admin", "wrong-password") is False
    assert authenticate("nobody", "admin") is False
