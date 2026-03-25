# Eneo backend

## Documentation

- [Type Checking](docs/TYPE_CHECKING.md) - Pyright baseline setup and local commands
- [Installation Guide](../docs/INSTALLATION.md) - Full setup instructions including manual setup

## Running Locally

See [docs/INSTALLATION.md](../docs/INSTALLATION.md) for full setup instructions. Quick start:

```bash
# Start dependencies
docker compose up -d

# Run migrations (development DB)
TESTING=false uv run alembic upgrade head

# Start the server
uv run gunicorn src.intric.server.main:app --workers 1 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## Testing

### Setup

Tests use a separate database named `<POSTGRES_DB>_test` (default: `postgres_test`). When `TESTING=true` (set in `.env`), Alembic automatically redirects all migrations to this database.

Create the test database before running tests for the first time:

```bash
docker exec <postgres-container-name> psql -U postgres -c "CREATE DATABASE postgres_test;"
```

Then run migrations for the test DB:

```bash
# TESTING=true is set in .env by default, so alembic targets postgres_test
uv run alembic upgrade head
```

### Running Tests

```bash
# All tests
uv run pytest

# Unit tests only
uv run pytest tests/unit/

# Integration tests only
uv run pytest tests/integration/ -m integration

# Migration isolation tests (run separately — they modify DB schema)
uv run pytest -m migration_isolation
```

## Type Checking

Run Pyright for audit focus and new changes:

```bash
./scripts/typecheck_changed.sh
```

## Environment variables

| Variable                         | Required | Explanation                                              |
|----------------------------------|----------|----------------------------------------------------------|
| OPENAI_API_KEY                   |          | Api key for openai                                       |
| ANTHROPIC_API_KEY                |          | Api key for anthropic                                    |
| AZURE_API_KEY                    |          | Api key for azure                                        |
| AZURE_MODEL_DEPLOYMENT           |          | Deployment for azure                                     |
| AZURE_ENDPOINT                   |          | Endpoint for azure                                       |
| AZURE_API_VERSION                |          | Api version for azure                                    |
| POSTGRES_USER                    | x        |                                                          |
| POSTGRES_PASSWORD                | x        |                                                          |
| POSTGRES_PORT                    | x        |                                                          |
| POSTGRES_HOST                    | x        |                                                          |
| POSTGRES_DB                      | x        |                                                          |
| REDIS_HOST                       | x        |                                                          |
| REDIS_PORT                       | x        |                                                          |
| MOBILITYGUARD_DISCOVERY_ENDPOINT |          |                                                          |
| MOBILITYGUARD_CLIENT_ID          |          |                                                          |
| MOBILITYGUARD_CLIENT_SECRET      |          |                                                          |
| UPLOAD_FILE_TO_SESSION_MAX_SIZE  | x        | Max text file size for uploading to a session            |
| UPLOAD_IMAGE_TO_SESSION_MAX_SIZE | x        | Max image file size for uploading to a session           |
| UPLOAD_MAX_FILE_SIZE             | x        | Max file size for uploading to a collection              |
| TRANSCRIPTION_MAX_FILE_SIZE      | x        | Max file size for uploading to a collection              |
| MAX_IN_QUESTION                  | x        | Max files in a question                                  |
| USING_ACCESS_MANAGEMENT          | x        | Feature flag if using access management (example: False) |
| USING_AZURE_MODELS               | x        | Feature flag if using azure models (example: False)      |
| API_PREFIX                       | x        | Api prefix - eg `/api/v1/`                               |
| API_KEY_LENGTH                   | x        | Length of the generated api keys                         |
| API_KEY_HEADER_NAME              | x        | Header name for the api keys                             |
| JWT_AUDIENCE                     | x        | Example: *                                               |
| JWT_ISSUER                       | x        |                                                          |
| JWT_EXPIRY_TIME                  | x        | In seconds. Determines how long a user should be logged in before they are required to login again |
| JWT_ALGORITHM                    | x        | Example: HS256                                           |
| JWT_SECRET                       | x        |                                                          |
| JWT_TOKEN_PREFIX                 | x        | In the header - eg `Bearer`                              |
| URL_SIGNING_KEY                  | x        | Key for temporary file access URLs (use a strong random string) |
| LOGLEVEL                         |          | one of ´INFO´, ´DEBUG´, ´WARNING´, ´ERROR´               |
| TESTING                          |          | When `true`, migrations target `<POSTGRES_DB>_test` instead of `<POSTGRES_DB>`. Default: `false` |
| CRAWL_MAX_LENGTH                 |          | Maximum duration (seconds) for a crawl job. Must be less than `TENANT_WORKER_SEMAPHORE_TTL_SECONDS` |
| TENANT_WORKER_SEMAPHORE_TTL_SECONDS |       | TTL (seconds) for the per-tenant worker semaphore. Must be greater than `CRAWL_MAX_LENGTH` |
| ENCRYPTION_KEY                   |          | Key for encrypting HTTP auth credentials used by the web crawler. Generate with: `uv run python -m intric.cli.generate_encryption_key` |
| ENEO_SUPER_API_KEY               |          | API key granting access to sysadmin endpoints             |
| ENEO_SUPER_DUPER_API_KEY         |          | API key granting access to higher-privilege module endpoints |
| DEFAULT_TENANT_NAME              |          | Tenant name to create on first run via `init_db.py`       |
| DEFAULT_TENANT_QUOTA_LIMIT       |          | Token quota limit for the default tenant                  |
| DEFAULT_USER_NAME                |          | Display name of the default user created by `init_db.py`  |
| DEFAULT_USER_EMAIL               |          | Email of the default user created by `init_db.py`         |
| DEFAULT_USER_PASSWORD            |          | Password of the default user created by `init_db.py`      |
| OIDC_REDIRECT_GRACE_PERIOD_SECONDS |        | Grace period for OIDC state TTL. Capped to state TTL if larger. |
