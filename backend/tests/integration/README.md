# PostgreSQL authentication integration tests

These tests exercise the real Alembic migrations, PostgreSQL constraints, and
FastAPI server. They never migrate, truncate, or drop the database named in
your URL.

The URL is used only for PostgreSQL host and credential discovery. The test
harness connects to the server's `postgres` maintenance database, creates a
random database named `mt_auth_test_<32 hex characters>`, and registers
prefix-validated cleanup before applying any migration.

The PostgreSQL role must be able to create databases and install the
`uuid-ossp` and `citext` extensions in a database it owns.

PowerShell:

```powershell
Set-Location backend
$env:TEST_DATABASE_URL = "postgresql+asyncpg://user:password@localhost:5432/any_existing_database"
.\.venv\Scripts\python.exe -m unittest tests.integration.test_postgres_auth -v
```

`DATABASE_URL` is accepted when `TEST_DATABASE_URL` is not set. Prefer
`TEST_DATABASE_URL` in CI so the integration-test dependency is explicit.

The harness:

1. creates the disposable database;
2. upgrades it to Alembic revision `0001`;
3. inserts deterministic legacy rows;
4. upgrades from `0001` through `head`;
5. launches Uvicorn on an ephemeral localhost port;
6. runs database and HTTP authentication scenarios; and
7. stops Uvicorn, terminates remaining connections to the exact disposable
   database, and drops only that database.

If the PostgreSQL role lacks `CREATEDB`, the suite skips with a setup message.
Migration, application, or assertion failures are reported as test failures,
and cleanup still runs.
