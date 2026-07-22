# Multi-Tenant Task Management POC

A multi-tenant task/project management API built on the "shared database,
shared schema, `tenant_id` discriminator" model described in the
architecture doc. Stack: **FastAPI + SQLAlchemy 2.0 (async) + asyncpg +
Alembic + PostgreSQL**, JWT-based auth.

## 1. Architecture recap

- **Isolation model**: one Postgres database, one set of tables; every
  tenant-owned row carries a `tenant_id`. There is no per-tenant schema or
  database (yet) — see [`app/db/session.py`](app/db/session.py) for the seam
  where that would change if it ever needs to.
- **Role hierarchy**: `platform_admins` (not tenant-scoped) creates
  `tenants` + seeds the first `Tenant Admin` user in one transaction. A
  Tenant Admin then provisions `Project Manager` / `Employee` users within
  their own tenant.
- **Concurrency**: every `projects`/`tasks`/`users` row has a `version`
  column; every UPDATE is a single `WHERE ... AND version = :version`
  statement — see any `update_*` function in a module's `service.py`.
- **Audit trail**: `audit_logs` rows are written in the same transaction as
  the mutation they describe (see [`app/common/audit.py`](app/common/audit.py)).

## 2. Project layout

```
app/
  core/                 # cross-cutting infra, no domain knowledge
    config.py              Settings (reads .env via pydantic-settings)
    security.py            password hashing (bcrypt) + JWT encode/decode
    exceptions.py          AppError hierarchy (404/403/409/422/401) -> HTTP status codes

  db/                    # database connection layer, kept isolated on purpose
    base.py                shared SQLAlchemy DeclarativeBase
    session.py             DatabaseSessionManager + get_db() FastAPI dependency.
                            session_for(tenant_id=...) is the single seam to touch
                            if this ever moves to schema-per-tenant.

  models/                # SQLAlchemy ORM models, one file per table, mirrors the DDL exactly
    platform_admin.py, tenant.py, user.py, project.py, task.py,
    task_comment.py, daily_progress_log.py, audit_log.py

  schemas/               # Pydantic request/response models, one file per domain
    auth.py, tenant.py, user.py, project.py, task.py, comment.py, daily_log.py

  middleware/
    auth_middleware.py     JWTGateMiddleware — runs in front of EVERY request
                            (except /auth/*, /docs, /health). Verifies the JWT
                            signature/expiry only; does not touch the DB.

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
    tenants/               tenant onboarding (platform-admin only)
    users/                 user provisioning (Tenant Admin only)
    projects/              project CRUD
    tasks/                 task/sub-task CRUD, closure guard, actual_hours calc
    comments/               task comments (append-only)
    daily_logs/            daily progress logs (hours worked)

    each module's:
      router.py    HTTP layer — path, method, Depends() for auth, calls service
      service.py   business rules, orchestration, calls repository + audit
      repository.py  raw SQLAlchemy queries, returns ORM objects — no business logic

  main.py                FastAPI() app, registers JWTGateMiddleware, exception
                          handler, and every module's router

alembic/
  env.py                 Alembic's own (separate, throwaway) DB connection for migrations
  versions/0001_initial_schema.py   the DDL from the architecture doc, applied verbatim

scripts/
  seed_platform_admin.py   one-off CLI to bootstrap the very first platform_admins row
                            (Administrator is "seeded/self" — nothing in the API creates one)
```

**Why `repository` / `service` / `router` per module?** Keeps DB queries,
business rules, and HTTP concerns in separate files so each is easy to find
and test independently, and so `db/session.py` stays the only place that
knows how a connection is actually obtained.

## 3. Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # then edit DATABASE_URL / JWT_SECRET_KEY

alembic upgrade head                       # creates all tables + indexes

python -m scripts.seed_platform_admin \
  --name "Platform Admin" --email admin@platform.io --password "AdminPass123"

uvicorn app.main:app --reload              # http://localhost:8000/docs
```

## 4. API reference

All endpoints except `/auth/*`, `/health`, `/docs` require
`Authorization: Bearer <token>`. "Role" below is enforced twice: once by the
route's `Depends()` (coarse role gate) and again inside the service layer
for resource-level scoping (e.g. a PM can only touch projects they manage).

### Auth (`/auth`) — public

| Method | Path | Description |
|---|---|---|
| POST | `/auth/admin/login` | Platform admin login → JWT |
| POST | `/auth/login` | Tenant user login (requires `tenant_id` + `email` + `password` — see note below) |

> Tenant user emails are only unique **within** a tenant
> (`UNIQUE(tenant_id, email)`), not globally, so login must disambiguate
> which tenant. This POC takes `tenant_id` explicitly in the login request;
> a real deployment would resolve it from a subdomain/org-slug instead.

### Tenants (`/tenants`) — platform admin only

| Method | Path | Description |
|---|---|---|
| POST | `/tenants` | Create a tenant + seed its first Tenant Admin, one transaction |
| GET | `/tenants` | List all tenants |
| GET | `/tenants/{tenant_id}` | Get one tenant |

### Users (`/users`) — tenant-scoped

| Method | Path | Role | Description |
|---|---|---|---|
| POST | `/users` | Tenant Admin | Provision a Project Manager or Employee |
| GET | `/users` | any | List users in your tenant |
| GET | `/users/{user_id}` | any | Get one user in your tenant |
| PATCH | `/users/{user_id}` | Tenant Admin | Update name/status (optimistic lock via `version`) |

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

1. `JWTGateMiddleware` (app/middleware/auth_middleware.py) intercepts every
   request first, rejecting anything without a valid, unexpired JWT.
2. `get_current_principal` (app/common/deps.py) then re-loads the user/admin
   from the DB on every request — a deactivated user's still-valid token
   stops working immediately rather than at next expiry.
3. `require_roles(...)` gates coarse role access at the route level.
4. Each module's `service.py` does the fine-grained, resource-level check
   (`app/common/authz.py`) — e.g. an Employee can only reach tasks they're
   assigned to, never another employee's.
