import subprocess
import sys
from pathlib import Path

import pytest

from settings import ConfigError, load_settings, mask_url, seed_customers

GOOD_PROD = {
    "APP_ENV": "prod",
    "DATABASE_URL": "postgresql://app:s3cr3t-pass@db.internal:5432/app",
    "SECRET_KEY": "x" * 40,
}


def problems_for(environ):
    with pytest.raises(ConfigError) as exc:
        load_settings(environ)
    return exc.value.problems


# --- each environment loads with the right defaults ---

def test_no_variables_means_dev_with_safe_defaults():
    s = load_settings({})
    assert s.env == "dev"
    assert s.database_url == "sqlite:///dev.db"
    assert s.debug is True
    assert s.fake_data is False


def test_test_env_uses_in_memory_db_and_fake_data():
    s = load_settings({"APP_ENV": "test"})
    assert s.database_url == "sqlite:///:memory:"
    assert s.fake_data is True
    assert s.debug is False


def test_good_prod_config_loads():
    s = load_settings(GOOD_PROD)
    assert s.env == "prod"
    assert s.debug is False
    assert s.fake_data is False
    assert s.log_level == "INFO"


def test_environment_variable_overrides_default():
    s = load_settings({"APP_ENV": "dev", "DATABASE_URL": "sqlite:///other.db", "LOG_LEVEL": "info"})
    assert s.database_url == "sqlite:///other.db"
    assert s.log_level == "INFO"


def test_unknown_env_is_rejected():
    assert "APP_ENV must be one of" in problems_for({"APP_ENV": "staging"})[0]


# --- prod refuses unsafe configuration ---

def test_prod_with_nothing_set_lists_every_problem_at_once():
    problems = problems_for({"APP_ENV": "prod"})
    assert any("DATABASE_URL is required" in p for p in problems)
    assert any("SECRET_KEY is required" in p for p in problems)
    assert len(problems) == 2


@pytest.mark.parametrize("override, expected", [
    ({"DATABASE_URL": "sqlite:///prod.db"}, "must not be SQLite"),
    ({"SECRET_KEY": "short"}, "at least 32 characters"),
    ({"SECRET_KEY": "dev-only-secret-not-for-production-padding"}, "dev/test default"),
    ({"DEBUG": "true"}, "DEBUG must be false"),
    ({"DEBUG": "maybe"}, "DEBUG must be true or false"),
    ({"LOG_LEVEL": "LOUD"}, "LOG_LEVEL must be"),
])
def test_prod_rejects_each_unsafe_setting(override, expected):
    problems = problems_for({**GOOD_PROD, **override})
    assert any(expected in p for p in problems), problems


# --- fake data only in test ---

@pytest.mark.parametrize("env", ["dev", "prod"])
def test_fake_data_outside_test_is_an_error(env):
    environ = {**GOOD_PROD, "APP_ENV": env, "FAKE_DATA": "true"}
    assert any("FAKE_DATA is only allowed" in p for p in problems_for(environ))


def test_seed_returns_fake_customers_only_in_test():
    assert len(seed_customers(load_settings({"APP_ENV": "test"}))) == 3
    assert seed_customers(load_settings({"APP_ENV": "dev"})) == []
    assert seed_customers(load_settings(GOOD_PROD)) == []


def test_test_env_can_switch_fake_data_off():
    assert load_settings({"APP_ENV": "test", "FAKE_DATA": "false"}).fake_data is False


def test_seed_returns_copies_so_callers_cannot_change_the_fixtures():
    rows = seed_customers(load_settings({"APP_ENV": "test"}))
    rows[0]["name"] = "changed"
    assert seed_customers(load_settings({"APP_ENV": "test"}))[0]["name"] == "Test Customer One"


# --- secrets never leak into logs ---

def test_repr_masks_secret_and_db_password():
    text = repr(load_settings(GOOD_PROD))
    assert "x" * 40 not in text
    assert "s3cr3t-pass" not in text
    assert "app:***@db.internal" in text


def test_mask_url_leaves_urls_without_credentials_alone():
    assert mask_url("sqlite:///dev.db") == "sqlite:///dev.db"


# --- the CLI fails fast with a non-zero exit code ---

def run_cli(environ):
    script = Path(__file__).with_name("settings.py")
    return subprocess.run([sys.executable, str(script)], env=environ, capture_output=True, text=True)


def test_cli_exits_1_on_bad_prod_config():
    result = run_cli({"APP_ENV": "prod"})
    assert result.returncode == 1
    assert "DATABASE_URL is required in prod" in result.stderr


def test_cli_prints_masked_settings_on_good_config():
    result = run_cli(GOOD_PROD)
    assert result.returncode == 0
    assert "secret_key='***'" in result.stdout
    assert "s3cr3t-pass" not in result.stdout
