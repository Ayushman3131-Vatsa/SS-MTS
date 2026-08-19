# HRMS Domain — Architecture & Database Design

**Status: design only.** Nothing in this document has been applied to the
codebase or database yet — no models, migrations, or endpoints were
changed. This is the plan to review before any of it gets built.

**Decisions this document assumes** (confirmed with you before writing it):
1. The HRMS domain is **added alongside** the existing task-management
   domain (`tenants`/`users`/`projects`/`tasks`/`task_comments`/
   `daily_progress_logs`) — nothing existing is removed.
2. Tenant isolation for the new HRMS tables uses **Postgres Row-Level
   Security (RLS)**, not the app-layer `tenant_id` filtering the existing
   tables use. This means the same database will run **two different
   isolation strategies side by side** (see §3).

---

## 1. What already exists vs. what's new

Current schema (already migrated, already running):

| Table | Purpose |
|---|---|
| `platform_admins` | Platform-level, not tenant-scoped |
| `tenants` | Tenant registry |
| `users` | Tenant Admin / Project Manager / Employee — task-app identities |
| `projects`, `tasks`, `task_comments`, `daily_progress_logs`, `audit_logs` | Task-management domain |

No naming collisions with the new HRMS tables — the only shared table is
`tenants`, which the HRMS domain reuses rather than duplicates (see §2).
`hr_users` (HRMS login credentials) is a **separate table from `users`**
(task-app login credentials) on purpose: they represent different
identities with different roles (`hr_admin`/`finance` vs. `Tenant
Admin`/`Project Manager`/`Employee`) and different login endpoints. A
person could plausibly need both if your org uses both apps — this design
doesn't try to unify them.

## 2. Required change to the existing `tenants` table

The HRMS spec's own `tenants` table (`id`, `name`, `subdomain`,
`created_at`) differs from the one already running:

| Existing column | HRMS spec column | Resolution |
|---|---|---|
| `tenant_id` (PK) | `id` (PK) | **Keep `tenant_id`.** Every new HRMS table's FK targets `tenants.tenant_id`, not `.id`. Renaming a live PK is disruptive for no real benefit. |
| `org_name` | `name` | Keep `org_name` — same meaning, don't rename. |
| `subscription_plan` | *(not present)* | Keep — unrelated to HRMS, no conflict. |
| *(not present)* | `subdomain VARCHAR(63) UNIQUE` | **Add this column.** The HRMS spec routes requests by subdomain; nothing today provides that. One additive migration: `ALTER TABLE tenants ADD COLUMN subdomain VARCHAR(63) UNIQUE;` (nullable at first, since existing tenant rows won't have one — backfill before making it `NOT NULL`, or enforce `NOT NULL` only for tenants provisioned after HRMS ships). |
| `created_by_admin_id` | *(not present)* | Keep — unrelated to HRMS, no conflict. |

No other change to `tenants` is needed. `platform_admins` is untouched.

## 3. Two isolation models in one database — what that actually means

This is the part most likely to bite in practice, so it's worth being
explicit:

- **Existing tables** (`users`, `projects`, `tasks`, ...): isolation is
  enforced entirely in application code — every query has an explicit
  `WHERE tenant_id = :tenant_id`. Nothing in Postgres stops a bug from
  reading across tenants; the discipline lives in `app/modules/*/repository.py`.
- **New HRMS tables**: isolation is enforced by Postgres itself via RLS
  policies keyed off a session variable, `app.tenant_id`. The database
  refuses to return rows for the wrong tenant *even if the application
  forgets a WHERE clause*.

Consequences of running both in the same Postgres instance:

1. **The DB connection role matters enormously for RLS, and not at all for
   app-layer filtering.** RLS policies are bypassed entirely for
   superusers and for the table owner unless `FORCE ROW LEVEL SECURITY` is
   set (the spec does set `FORCE`) — but even `FORCE` does **not** stop a
   role with the `BYPASSRLS` attribute, and superusers always bypass RLS
   regardless of `FORCE`. Today's `.env` connects as `postgres`, which is
   a superuser. **If the app keeps connecting as `postgres`, every RLS
   policy on the HRMS tables is silently a no-op.** A new, non-superuser,
   non-`BYPASSRLS` Postgres role (e.g. `hrms_app`) must be created and
   granted only `SELECT/INSERT/UPDATE/DELETE` on the HRMS tables, and the
   application must connect as that role for RLS to do anything.
2. **Two different "how do I know the current tenant" mechanisms.** The
   task-app already has this solved via JWT claims → `Principal.tenant_id`
   → passed explicitly into repository queries. HRMS additionally needs
   the tenant id pushed into Postgres itself via `SET LOCAL app.tenant_id`
   at the start of every transaction — this has to happen for *every* HRMS
   request or every HRMS query returns zero rows (RLS with no session
   variable set matches nothing, by design of `current_tenant_id()`
   returning `NULL`).
3. **These two mechanisms should not be conflated.** The existing
   `get_db()` dependency in `app/db/session.py` should stay as-is for the
   task-app modules. A **new** dependency (e.g. `get_hrms_db()`) is needed
   for HRMS modules that both (a) connects using the non-superuser HRMS
   role and (b) runs `SET LOCAL app.tenant_id` via the SQLAlchemy
   `after_transaction_create` event hook described in the spec. This is
   exactly the seam `DatabaseSessionManager.session_for(tenant_id=...)`
   in `app/db/session.py` was already built to accommodate — it currently
   accepts and ignores `tenant_id`; HRMS is the first real consumer of
   that parameter.

## 4. Complete HRMS table list

All FKs to `tenants` reference `tenants.tenant_id` (per §2). All tables use
a single UUID `id` primary key (not composite, unlike the existing
tenant-app tables) — isolation is RLS's job, not the primary key's.

```
tenants (existing, altered — see §2)
   |
   +-- persons                         unified identity for candidates + employees
          |
          +-- hr_users                  HR/finance login credentials
          |
          +-- candidates                recruitment pipeline
          |      +-- candidate_status_log
          |
          +-- employees                 active workforce
                 +-- employee_bank_details
                 +-- employee_education
                 +-- employee_emergency_contacts
                 +-- employee_employment_history
                 +-- employee_dependents
                 +-- employee_employment_details   (SCD Type 2: designation/dept/location over time)
                 +-- exit_interviews
                 +-- departments            (references employees.id for manager_id)
                 +-- designations
                 +-- work_locations
                 +-- salary_structures       (SCD Type 2, owner: employee XOR candidate)
                 +-- payroll_records
                 +-- documents               (owner: persons, not employees — candidates have documents too)
                 +-- email_logs
```

The DDL for every table above is exactly what's in your spec message
(§3.2), with the one change from §2: every `REFERENCES tenants(id)`
becomes `REFERENCES tenants(tenant_id)`. I'm not re-pasting all ~20
`CREATE TABLE` statements here since they're already fully specified in
your message — the only edit needed before running them is that one FK
target rename, applied uniformly.

### `current_tenant_id()` — one addition worth flagging

The spec's function:

```sql
CREATE OR REPLACE FUNCTION current_tenant_id()
RETURNS UUID AS $$
BEGIN
    RETURN NULLIF(current_setting('app.tenant_id', true), '')::UUID;
EXCEPTION WHEN OTHERS THEN RETURN NULL;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
```

is correct as written. Worth knowing: when `app.tenant_id` isn't set (e.g.
a query runs outside the `SET LOCAL` wrapper — a stray script, a manual
`psql` session, a missed `await` in middleware), this returns `NULL`, and
`tenant_id = NULL` is never true in SQL — so the *safe* failure mode is
"see nothing," not "see everything." That's the right default, but it
also means a wiring bug looks like "the API returns empty lists," not an
obvious error — worth a health-check query in staging that deliberately
checks `SELECT current_tenant_id()` returns non-null before trusting any
HRMS response as "correctly empty."

## 5. Application-layer plan (design only, not yet built)

New pieces needed in `app/`, following the module-per-domain pattern
already in place:

```
app/
  db/
    session.py            EXTEND: implement session_for(tenant_id) for real —
                           connect via the hrms_app role, run
                           `SET LOCAL app.tenant_id = :tenant_id` per transaction
                           via the after_transaction_create event hook
  models/
    person.py, hr_user.py, candidate.py, candidate_status_log.py,
    employee.py, department.py, designation.py, work_location.py,
    employee_bank_detail.py, employee_education.py,
    employee_emergency_contact.py, employee_employment_history.py,
    employee_dependent.py, employee_employment_detail.py,
    exit_interview.py, salary_structure.py, payroll_record.py,
    document.py, email_log.py
  common/
    hrms_deps.py           get_current_hr_principal() — separate from the
                           task-app's get_current_principal(); different
                           JWT claims (hr_admin/finance/employee-ess),
                           per REQ-AUTH-001/002 using asymmetric signatures
                           (a change from the task-app's current HS256 —
                           needs its own decision, out of scope here)
  modules/
    persons/, hr_auth/, candidates/, employees/, departments/,
    salary_structures/, payroll/, documents/, email_logs/
       each with router.py / service.py / repository.py, same shape as
       the existing tasks/ projects/ modules
```

Existing modules (`auth`, `tenants`, `users`, `projects`, `tasks`,
`comments`, `daily_logs`) are untouched.

## 6. Migration sequencing (once you say go)

Alembic revisions, in order:

1. `ALTER TABLE tenants ADD COLUMN subdomain ...` (the one existing-schema change from §2)
2. `CREATE FUNCTION current_tenant_id()`
3. `CREATE TABLE persons` (references `tenants.tenant_id`)
4. `CREATE TABLE hr_users`
5. `CREATE TABLE candidates`, `candidate_status_log`
6. `CREATE TABLE departments`, `designations`, `work_locations`
7. `CREATE TABLE employees` (self-references for `reporting_manager_id`; `departments.manager_id` also references `employees.id` — a circular FK pair, so `departments` and `employees` need to be created without that FK first, then `ALTER TABLE ... ADD CONSTRAINT` after both tables exist)
8. `CREATE TABLE employee_bank_details, employee_education, employee_emergency_contacts, employee_employment_history, employee_dependents, employee_employment_details, exit_interviews`
9. `CREATE TABLE salary_structures, payroll_records, documents, email_logs`
10. All composite indexes (§3.2 of the spec, section 9)
11. `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` + `FORCE ROW LEVEL SECURITY` + `CREATE POLICY tenant_isolation ...` for every HRMS table
12. `CREATE ROLE hrms_app LOGIN PASSWORD '...'` (non-superuser, no `BYPASSRLS`) + `GRANT` statements scoped to the HRMS tables only

Step 7's circular FK is the one ordering wrinkle not spelled out in the
spec's flat DDL block — everything else can run top-to-bottom as given.

## 7. Open decisions (need answers before implementation, not before this doc)

- **Auth signing**: task-app JWTs are HS256 (shared secret). The HRMS spec
  says "asymmetric signatures." Sharing one auth scheme vs. two separate
  ones is a real decision, not just an implementation detail.
- **`persons.email` uniqueness**: spec doesn't declare it unique per
  tenant or globally — needs a decision before the `hire` conversion flow
  (REQ-CAND-011) can dedupe correctly.
- **Sequential code generation** (`candidate_code`, `employee_code`):
  needs a concurrency-safe strategy (e.g. a `tenant_sequences` table with
  `SELECT ... FOR UPDATE`, or a Postgres sequence per tenant) — naive
  `MAX(code)+1` races under concurrent hires.
- **`hrms_app` Postgres role provisioning**: who creates it and where the
  password lives (should not go in `.env` in plaintext long-term — same
  concern as any other DB credential, just flagging it exists now that
  there'll be a second one).
- **Document generation & email service** (WeasyPrint/Jinja2, Microsoft
  Graph) are not addressed in this document at all — they're application
  services, not schema, and out of scope for "db changes."
