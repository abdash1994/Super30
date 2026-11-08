# Lab 05: dev, test and prod settings from the environment

**Result:** one `settings.py` loads dev, test or prod purely from environment variables, refuses to start prod with an unsafe config (listing every problem at once), and only ever allows fake data in test, proven by 21 tests.

## The problem

At a client, the same code runs on a laptop, in CI and in production. The classic incidents all come from mixing those up: a production server running with `DEBUG=true` and showing stack traces to the public, a demo password shipped to prod because it was the default, a test script that loaded fake customers into the real database, or a database password printed into a log. Each one is a configuration bug, not a code bug, and each one is avoidable at startup.

## What this lab does

`settings.py` reads `APP_ENV` (`dev`, `test` or `prod`, default `dev`) and builds a frozen `Settings` object.

| Setting | dev | test | prod |
| --- | --- | --- | --- |
| `DATABASE_URL` | `sqlite:///dev.db` | `sqlite:///:memory:` | **required**, not SQLite |
| `SECRET_KEY` | dev placeholder | test placeholder | **required**, 32+ characters, not a placeholder |
| `DEBUG` | true | false | must be false |
| `LOG_LEVEL` | DEBUG | WARNING | INFO |
| Fake data | not allowed | on (can be switched off) | not allowed |

Rules it enforces:

- **Prod has no defaults.** A missing variable in prod is an error, never a silent fallback to a dev value.
- **All problems at once.** `ConfigError` lists every bad setting, so the person deploying fixes them in one go, not one restart at a time.
- **Fake data only in test.** `FAKE_DATA=true` with `APP_ENV=dev` or `prod` is rejected, and `seed_customers()` returns an empty list outside test.
- **Secrets never print.** `repr(settings)` shows `secret_key='***'` and masks the password inside `DATABASE_URL`.
- **Fail fast.** `python settings.py` exits with code 1 on a bad config, so a deploy pipeline stops before the app serves a single request.

`.env.example` documents every variable. The real `.env` is already in `.gitignore`.

## Run it

```bash
pip install -r requirements.txt
pytest -q                                   # 21 tests

python settings.py                          # dev defaults, exit 0
APP_ENV=test python settings.py             # fake customers to seed: 3
APP_ENV=prod python settings.py; echo $?    # lists what is missing, exit 1
```

## Why it matters to a business

A config check at startup turns a production incident into a failed deploy. A failed deploy costs a few minutes and nobody outside the team notices; a leaked stack trace, a test customer receiving a real invoice, or a password in a log can cost a security review, a client's trust or a compliance finding. The rules are also readable by a non-engineer: a client's security reviewer can open one file and see that debug mode cannot reach production.

## Trade-off

This uses plain Python and `os.environ` instead of a library like `pydantic-settings`, so there are no dependencies and every rule is visible in one file, but there is no automatic type conversion or `.env` file loading (export the variables or let the deployment platform set them). The secret check is only about length and placeholders; it cannot tell a strong secret from a weak one. A real service would also read secrets from a secret manager rather than plain environment variables.
