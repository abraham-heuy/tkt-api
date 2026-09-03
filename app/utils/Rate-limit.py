"""
Rate limiting via slowapi (a thin wrapper around the `limits` library).

limiter is attached to app.state in main.py with one line. Individual
routes opt into a stricter limit with @limiter.limit(settings.rate_limit_auth)
where brute-force risk is higher (login, pin checks, recovery).
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings

settings = get_settings()

limiter = Limiter(default_limits=[settings.rate_limit_default], key_func=get_remote_address)