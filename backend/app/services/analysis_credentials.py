"""Ephemeral, task-local credentials; never persist these with a job."""
from contextvars import ContextVar
from contextlib import contextmanager

from pydantic import SecretStr

user_gemini_key: ContextVar[SecretStr | None] = ContextVar('user_gemini_key', default=None)


@contextmanager
def use_gemini_key(key: SecretStr | None):
    token = user_gemini_key.set(key)
    try:
        yield
    finally:
        user_gemini_key.reset(token)
