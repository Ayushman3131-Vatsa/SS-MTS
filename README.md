# Multi-Tenant Task Management

A secure multi-tenant task/project application built on a shared PostgreSQL
schema with a `tenant_id` discriminator. The backend uses **FastAPI +
SQLAlchemy 2.0 (async) + asyncpg + Alembic + PostgreSQL**. The browser client
uses **React + Vite + TypeScript + CSS Modules**.

API clients can continue to use bearer JWTs. The React application uses
revocable opaque sessions stored in HttpOnly cookies; raw browser-session
tokens are never stored in PostgreSQL or exposed to JavaScript.

## 1. Architecture recap

- **Isolation model**: one Postgres database, one set of tables; every
  tenant-owned row carries a `tenant_id`. There is no per-tenant schema or
  database (yet) — see [`backend/app/db/session.py`](backend/app/db/session.py) for the seam
  where that would change if it ever needs to.
- **Role hierarchy**: `platform_admins` (not tenant-scoped) creates
  `tenants` + seeds the first `Tenant Admin` user in one transaction. A
  Tenant Admin then provisions `Project Manager` / `Employee` users within
  their own tenant.
- **Concurrency**: every `projects`/`tasks`/`users` row has a `version`
  column; every UPDATE is a single `WHERE ... AND version = :version`
  statement — see any `update_*` function in a module's `service.py`.
- **Audit trail**: `audit_logs` rows are written in the same transaction as
  the mutation they describe (see [`backend/app/common/audit.py`](backend/app/common/audit.py)).

## 2. Project layout

```
backend/
  app/
  core/                 # cross-cutting infra, no domain knowledge
    config.py              Settings (reads .env via pydantic-settings)
    security.py            Argon2id/bcrypt, password policy, normalization, JWT
    exceptions.py          AppError hierarchy (404/403/409/422/401) -> HTTP status codes

  db/                    # database connection layer, kept isolated on purpose
    base.py                shared SQLAlchemy DeclarativeBase
    session.py             DatabaseSessionManager + get_db() FastAPI dependency.
                            session_for(tenant_id=...) is the single seam to touch
                            if this ever moves to schema-per-tenant.

  models/                # SQLAlchemy ORM models, one file per table, mirrors the DDL exactly
    platform_admin.py, tenant.py, user.py, project.py, task.py,
    task_comment.py, daily_progress_log.py, audit_log.py,
    browser_session.py, auth_rate_limit.py, subscription_plan.py,
    tenant_subscription.py, tenant_database_allocation.py,
    tenant_offering.py, platform_activity_event.py

  schemas/               # Pydantic request/response models, one file per domain
    auth.py, tenant.py, platform_dashboard.py, user.py, project.py, task.py,
    comment.py, daily_log.py

  middleware/
    auth_middleware.py     accepts bearer JWTs or opaque browser sessions
    security_middleware.py request-size limits and response security headers

  common/                # security & cross-module helpers shared by all modules
    deps.py                Principal dataclass + get_current_principal (DB-backed
                            identity/role load), require_platform_admin,
                            require_tenant_user, require_roles(*roles)
    authz.py               resource-level checks: can a given Principal manage this
                            Project / access this Task? (Tenant Admin: all;
                            PM: projects they manage; Employee: tasks assigned to them)
    audit.py               record_audit() — appends an audit_logs row in the caller's
                            transaction

  modules/               # one folder per domain, each with router + service + repository
    auth/                  login endpoints (admin + tenant user)
    platform_dashboard/    cross-tenant metrics, charts, activity, readiness
    tenants/               tenant onboarding (platform-admin only)
    users/                 user provisioning (Tenant Admin only)
    projects/              project CRUD
    tasks/                 task/sub-task CRUD, closure guard, actual_hours calc
    comments/               task comments (append-only)
    daily_logs/            daily progress logs (hours worked)
    task_management/       cohesive task-management offering and canonical API

    each module's:
      router.py    HTTP layer — path, method, Depends() for auth, calls service
      service.py   business rules, orchestration, calls repository + audit
      repository.py  raw SQLAlchemy queries, returns ORM objects — no business logic

  main.py                FastAPI app, middleware, error handlers, OpenAPI, routers

  alembic/
    env.py                 Alembic's own (separate, throwaway) DB connection for migrations
    versions/              initial schema plus secure-login migrations

  scripts/
    seed_platform_admin.py   one-off CLI to bootstrap the very first platform_admins row
                              (Administrator is "seeded/self" — nothing in the API creates one)
    cleanup_auth_state.py     scheduled cleanup for expired/revoked sessions and
                              stale login-throttle counters

  tests/                   backend unit and PostgreSQL integration tests
  alembic.ini              migration configuration
  requirements.txt         Python dependencies
  .env.example             backend environment template

frontend/
  src/app/                routing and providers
  src/pages/              login, PlatformShell, dashboard and destinations
  src/features/auth/      forms, validation, and login operations
  src/features/platform-dashboard/ typed API, polling state, charts and activity
  src/entities/session/   principal state and role routing
  src/shared/             API transport, reusable UI, and design tokens
```

**Why `repository` / `service` / `router` per module?** Keeps DB queries,
business rules, and HTTP concerns in separate files so each is easy to find
and test independently, and so `db/session.py` stays the only place that
knows how a connection is actually obtained.

## 3. Setup

```powershell
Set-Location backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

Copy-Item .env.example .env   # then set DATABASE_URL and a strong JWT_SECRET_KEY
python -m alembic upgrade head

python -m scripts.seed_platform_admin `

# Enter and confirm the password at the hidden prompt.

python -m uvicorn app.main:app --reload     # API: http://127.0.0.1:8000/docs

Set-Location ..\frontend
npm install
npm run dev                                # UI: http://127.0.0.1:5173
```

Vite proxies `/api` to FastAPI during development. Deploy the frontend and
`/api` behind one public origin in production.

The backend liveness endpoint is `GET http://127.0.0.1:8000/health`, and
API/database readiness is available at `/health/ready`. The interactive API
documentation is at `/docs`. The React landing page is served by Vite at
`http://127.0.0.1:5173`.

## 4. API reference

Protected endpoints accept either `Authorization: Bearer <token>` or the
opaque browser session. Role and tenant scope are enforced again after
authentication by database-backed dependencies and service rules.

### Auth (`/auth`) — public

| Method | Path | Description |
|---|---|---|
| POST | `/auth/session/platform` | Platform Admin browser login using secure cookies |
| POST | `/auth/session/tenant` | Tenant-user browser login using email and password |
| POST | `/auth/password/change` | Replace a tenant user's temporary password and rotate credentials |
| GET | `/auth/session` | Restore the current browser principal |
| DELETE | `/auth/session` | Revoke the browser session and clear cookies |
| POST | `/auth/admin/login` | Platform admin login → JWT |
| POST | `/auth/login` | Tenant user login using email and password |

> Tenant-user emails are globally case-insensitively unique. Both browser and
> bearer login resolve the tenant from the matched account.

### Tenants (`/tenants`) — platform admin only

| Method | Path | Description |
|---|---|---|
| POST | `/tenants` | Create a tenant profile and commercial configuration; does not create users or roles |
| GET | `/tenants` | Paginated tenant list with search and `status` filtering |
| GET | `/tenants/{tenant_id}` | Get one tenant |
| GET | `/tenants/offering-catalog` | List active and inactive offering catalog entries |
| GET | `/offerings` | List and inspect all platform offering catalog entries |
| POST | `/offerings` | Create an offering catalog entry |
| PATCH | `/offerings/{offering_id}` | Update offering metadata (code is immutable) |
| POST | `/offerings/{offering_id}/activate` | Make an offering available for new licensing |
| POST | `/offerings/{offering_id}/deactivate` | Remove an offering from new licensing without revoking tenants |
| DELETE | `/offerings/{offering_id}` | Delete an unused offering catalog entry |
| GET | `/platform/default-templates?offering_id={offering_id}` | List an offering's platform defaults and tenant impact |
| GET | `/platform/default-templates/{template_id}` | Get one editable platform default |
| POST | `/platform/default-templates` | Create and immediately publish a platform default |
| PATCH | `/platform/default-templates/{template_id}` | Publish safe edits using `expected_version` |
| POST | `/platform/default-templates/preview` | Validate and render an unsaved default-template draft |
| POST | `/tenants/{tenant_id}/suspend` | Suspend tenant access using an expected tenant version |
| POST | `/tenants/{tenant_id}/activate` | Activate tenant access using an expected tenant version |
| GET | `/tenants/{tenant_id}/offering-entitlements` | List current and historical grants |
| GET | `/tenants/{tenant_id}/offering-entitlements/history` | List immutable grant transition events |
| POST | `/tenants/{tenant_id}/offering-entitlements` | Grant an offering with UTC start/end timestamps |
| POST | `/tenants/{tenant_id}/offering-entitlements/{entitlement_id}/suspend` | Suspend one grant |
| POST | `/tenants/{tenant_id}/offering-entitlements/{entitlement_id}/resume` | Resume one grant without extending its end date |
| POST | `/tenants/{tenant_id}/offering-entitlements/{entitlement_id}/deactivate` | Terminally deactivate one grant |
| DELETE | `/tenants/{tenant_id}/offering-entitlements/{entitlement_id}` | Permanently remove a deactivated or expired grant with version and reason |

Offering entitlements are independent historical records. Access is effective
only when the tenant is `ACTIVE`, the grant is `ACTIVE`, and database time is
within `[starts_at, ends_at)`. New grants require UTC timestamps and an
`Idempotency-Key`; destructive transitions require a reason and all mutations
use optimistic versions. Existing pre-migration assignments are grandfathered
with no expiry. A globally `INACTIVE` catalog offering blocks new grants but
does not revoke existing valid entitlements.

Schedule the idempotent entitlement reconciler in the deployment platform.
It marks elapsed grants as expired and permanently purges deactivated or
expired grants after `DEACTIVATED_OFFERING_RETENTION_DAYS` (90 days by default):

```powershell
Set-Location backend
python -m scripts.reconcile_offering_entitlements
```

### Platform dashboard — platform admin only

| Method | Path | Description |
|---|---|---|
| GET | `/platform/dashboard` | Dynamic KPI, chart, and recent-activity snapshot |
| GET | `/health/ready` | Minimal public API/PostgreSQL readiness probe |

See [docs/platform-dashboard.md](docs/platform-dashboard.md) for metric
definitions, filters, persistence, and frontend refresh behavior.

### Users (`/users`) — tenant-scoped

| Method | Path | Role | Description |
|---|---|---|---|
| POST | `/users` | Tenant Admin | Provision a Project Manager or Employee |
| GET | `/users` | any | List users in your tenant |
| GET | `/users/{user_id}` | any | Get one user in your tenant |
| PATCH | `/users/{user_id}` | Tenant Admin | Update name/status (optimistic lock via `version`) |

The routes below are retained compatibility APIs. New integrations should use the
paginated `/task-management/*` API described in
[docs/task-management.md](docs/task-management.md).

### Projects (`/projects`) — tenant-scoped

| Method | Path | Role | Description |
|---|---|---|---|
| POST | `/projects` | Tenant Admin, PM | Create a project |
| GET | `/projects` | any | List — Tenant Admin sees all, PM sees managed projects, Employee sees projects with a task assigned to them |
| GET | `/projects/{project_id}` | any (scoped) | Get one project, 403 if out of scope |
| PATCH | `/projects/{project_id}` | Tenant Admin, managing PM | Update (optimistic lock via `version`) |

### Tasks (`/tasks`) — tenant-scoped

| Method | Path | Role | Description |
|---|---|---|---|
| POST | `/tasks` | Tenant Admin, managing PM | Create a task/sub-task (`parent_task_id`, one level deep max) |
| GET | `/tasks?project_id=` | any | List — scoped same as projects |
| GET | `/tasks/{task_id}` | any (scoped) | Get one task, includes computed `actual_hours` |
| PATCH | `/tasks/{task_id}` | scoped | Update; Employees may only change `status`/`remarks`/`attachment_url`. Blocks `status=Completed` if any sub-task is `New`/`In Progress` |

`actual_hours` is never stored — every response computes
`SUM(hours_worked)` from `daily_progress_logs` at read time.

### Comments (`/tasks/{task_id}/comments`) — append-only

| Method | Path | Description |
|---|---|---|
| POST | `/tasks/{task_id}/comments` | Post a comment (same access rule as the task) |
| GET | `/tasks/{task_id}/comments` | List comments on a task |

### Daily logs (`/tasks/{task_id}/logs`)

| Method | Path | Description |
|---|---|---|
| POST | `/tasks/{task_id}/logs` | Log hours worked (Employees: only if they're the task's assignee) |
| GET | `/tasks/{task_id}/logs` | List log entries for a task |

## 5. Request flow / security

1. Authentication middleware accepts a signed bearer JWT or looks up the
   SHA-256 digest of an opaque browser cookie in `browser_sessions`.
2. Unsafe cookie-authenticated requests must also supply the matching CSRF
   cookie through `X-CSRF-Token`.
3. `get_current_principal` (`backend/app/common/deps.py`) then re-loads the user/admin
   from the DB on every request — a deactivated user's still-valid token
   stops working immediately rather than at next expiry.
4. `require_roles(...)` gates coarse role access at the route level.
5. Each module's `service.py` does the fine-grained, resource-level check
   (`backend/app/common/authz.py`) — e.g. an Employee can only reach tasks they're
   assigned to, never another employee's.

Account creation enforces a 12–128 character password with uppercase,
lowercase, number, and special-character requirements plus common/contextual
password rejection. Login deliberately does not reapply creation-time
strength rules, so valid legacy passwords remain usable.

See [docs/authentication.md](docs/authentication.md) for browser sessions,
CSRF, validation, throttling, and frontend module boundaries.
See [docs/user-access-management.md](docs/user-access-management.md) for the
platform RBAC, tenant RBAC, page/action permission, and HRMS resource-policy
design.

## 6. Verification

Fast checks:

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m alembic check

Set-Location ..\frontend
npm.cmd run test
npm.cmd run lint
npm.cmd run build
npm.cmd run test:e2e
```

The PostgreSQL integration suite creates and drops only a random database
matching `mt_auth_test_<32 hex characters>`:

```powershell
$env:TEST_DATABASE_URL = $env:DATABASE_URL
Set-Location backend
.\.venv\Scripts\python.exe -m unittest tests.integration.test_postgres_auth -v
```

The database role used for that suite needs `CREATEDB`. See
[backend/tests/integration/README.md](backend/tests/integration/README.md) for its safety
contract.

## 7. Production operations

- Serve the compiled frontend and `/api` behind one HTTPS origin.
- Set `ENVIRONMENT=production`, a unique `JWT_SECRET_KEY` of at least 32
  characters, and matching backend/frontend CSRF cookie names.
- Configure Uvicorn to trust forwarding headers only from the actual reverse
  proxy, for example:

  ```powershell
  Set-Location backend
  python -m uvicorn app.main:app --proxy-headers --forwarded-allow-ips "10.0.0.10"
  ```

  Never use `*` unless the application server is otherwise network-isolated;
  the canonical client IP is used for shared login throttling.
- Run `python -m scripts.cleanup_auth_state` from `backend/` on a schedule (every 15 minutes is
  a suitable default).
