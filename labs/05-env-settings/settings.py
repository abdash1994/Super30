"""Lab 05: one codebase, three environments (dev, test, prod), configured only by environment variables.

Run `python settings.py` to print the effective settings (secrets masked).
It exits with code 1 and lists every problem if the configuration is unsafe.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Mapping

ENVIRONMENTS = ("dev", "test", "prod")
MIN_SECRET_LENGTH = 32

# Safe defaults for the two non-production environments. Production has no defaults on purpose:
# anything prod needs must be set explicitly, so a missing variable fails loudly instead of
# silently falling back to a dev value.
DEFAULTS = {
    "dev": {"DATABASE_URL": "sqlite:///dev.db", "DEBUG": "true", "LOG_LEVEL": "DEBUG",
            "SECRET_KEY": "dev-only-secret-not-for-production"},
    "test": {"DATABASE_URL": "sqlite:///:memory:", "DEBUG": "false", "LOG_LEVEL": "WARNING",
             "SECRET_KEY": "test-only-secret-not-for-production"},
    "prod": {"LOG_LEVEL": "INFO", "DEBUG": "false"},
}

TRUE_WORDS = {"1", "true", "yes", "on"}
FALSE_WORDS = {"0", "false", "no", "off", ""}


class ConfigError(Exception):
    """Raised at startup when the configuration is unsafe. Carries every problem, not just the first."""

    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("Invalid configuration:\n- " + "\n- ".join(problems))


@dataclass(frozen=True)
class Settings:
    env: str
    database_url: str
    secret_key: str
    debug: bool
    log_level: str
    fake_data: bool

    def __repr__(self) -> str:  # never print the secret, even by accident in a log line
        return (f"Settings(env={self.env!r}, database_url={mask_url(self.database_url)!r}, "
                f"secret_key='***', debug={self.debug}, log_level={self.log_level!r}, "
                f"fake_data={self.fake_data})")


def mask_url(url: str) -> str:
    """Hide the password in a URL like postgres://user:pass@host/db."""
    if "://" in url and "@" in url:
        scheme, rest = url.split("://", 1)
        creds, host = rest.rsplit("@", 1)
        user = creds.split(":", 1)[0]
        return f"{scheme}://{user}:***@{host}"
    return url


def _parse_bool(name: str, raw: str, problems: list[str]) -> bool:
    value = raw.strip().lower()
    if value in TRUE_WORDS:
        return True
    if value in FALSE_WORDS:
        return False
    problems.append(f"{name} must be true or false, got {raw!r}")
    return False


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    """Build Settings from environment variables. Pass a dict in tests; defaults to os.environ."""
    environ = os.environ if environ is None else environ
    problems: list[str] = []

    env = environ.get("APP_ENV", "dev").strip().lower()
    if env not in ENVIRONMENTS:
        raise ConfigError([f"APP_ENV must be one of {', '.join(ENVIRONMENTS)}, got {env!r}"])

    def get(name: str) -> str | None:
        value = environ.get(name)
        if value is None or value.strip() == "":
            return DEFAULTS[env].get(name)
        return value.strip()

    database_url = get("DATABASE_URL")
    secret_key = get("SECRET_KEY")
    debug = _parse_bool("DEBUG", get("DEBUG") or "", problems)
    log_level = (get("LOG_LEVEL") or "INFO").upper()
    if log_level not in {"DEBUG", "INFO", "WARNING", "ERROR"}:
        problems.append(f"LOG_LEVEL must be DEBUG, INFO, WARNING or ERROR, got {log_level!r}")

    # Fake data is on in test, and only in test. Asking for it anywhere else is an error,
    # so demo customers can never end up in a real database.
    fake_data = env == "test"
    if environ.get("FAKE_DATA") is not None:
        asked = _parse_bool("FAKE_DATA", environ["FAKE_DATA"], problems)
        if asked and env != "test":
            problems.append(f"FAKE_DATA is only allowed when APP_ENV=test (APP_ENV is {env})")
        fake_data = fake_data and asked

    if env == "prod":
        if not database_url:
            problems.append("DATABASE_URL is required in prod")
        elif database_url.startswith("sqlite"):
            problems.append("DATABASE_URL must not be SQLite in prod")
        if not secret_key:
            problems.append("SECRET_KEY is required in prod")
        elif len(secret_key) < MIN_SECRET_LENGTH:
            problems.append(f"SECRET_KEY must be at least {MIN_SECRET_LENGTH} characters in prod")
        elif "not-for-production" in secret_key:
            problems.append("SECRET_KEY is a dev/test default; set a real one in prod")
        if debug:
            problems.append("DEBUG must be false in prod")

    if problems:
        raise ConfigError(problems)

    return Settings(env=env, database_url=database_url or "", secret_key=secret_key or "",
                    debug=debug, log_level=log_level, fake_data=fake_data)


FAKE_CUSTOMERS = (
    {"id": "cus-001", "name": "Test Customer One", "email": "one@example.test"},
    {"id": "cus-002", "name": "Test Customer Two", "email": "two@example.test"},
    {"id": "cus-003", "name": "Test Customer Three", "email": "three@example.test"},
)


def seed_customers(settings: Settings) -> list[dict]:
    """Return fake customers to load into the database, or an empty list outside test."""
    if not settings.fake_data:
        return []
    return [dict(c) for c in FAKE_CUSTOMERS]


def main() -> int:
    try:
        settings = load_settings()
    except ConfigError as exc:
        print(exc, file=sys.stderr)
        return 1
    print(repr(settings))
    print(f"fake customers to seed: {len(seed_customers(settings))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
