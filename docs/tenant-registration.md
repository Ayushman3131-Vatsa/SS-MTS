# Tenant registration architecture

Tenant onboarding is owned by the Platform Admin boundary and is persisted as
one database transaction.

## Write model

`POST /tenants` creates, in one transaction:

1. the tenant identity, company profile, address, and required primary contact;
2. the current subscription and database allocation;
3. the selected offering grants (UTC start/end windows);
4. system roles (`TENANT_ADMIN`, `PROJECT_MANAGER`, `EMPLOYEE`) and default
   page access for **Access Management plus currently effective offerings**;
5. the first Tenant Admin account (contact email + generated temporary password)
   and a Smartskale Admin (`ss_<CODE>_admin`, password from
   `SMARTSKALE_SETUP_PASSWORD`);
6. platform activity and tenant audit records.

The create response includes `first_access` (`email`, `username`,
`temporary_password`, `login_path: /t/{CODE}/login`, `smartskale_access`).
Email delivery is not required; the platform admin must copy those credentials
from the success screen.

If any step fails, no partial tenant is committed. Tenant codes and normalized
primary-contact emails are serialized with PostgreSQL advisory locks. A primary
contact email is rejected when another tenant already reserved it.

New registrations create the first Tenant Admin in the registration transaction.
For an older tenant where first-admin creation was skipped, the Platform Admin
**Enable Tenant** action creates or reuses the canonical tenant role, copies the
primary contact name/email into the first Tenant Admin account, and returns a
generated temporary password once after commit. A pending password can be
regenerated only before the administrator completes password setup. The CLI
`python -m scripts.bootstrap_tenant_admin --tenant-code <CODE>` provides the
same recovery workflow. Future contact edits do not rename the account.

## First tenant login

1. Open `/t/{TENANT_CODE}/login` (or `/login` and enter the organization code),
   **not** `/platform/login`.
2. Sign in with the contact email or username and temporary password from
   `first_access`.
3. Because `force_pw_reset` is true, the first screen is
   `/account/change-password`.
4. After the password change, Tenant Admin lands on
   `/t/{TENANT_CODE}/app/overview`.
5. Navigation is built from **effective entitlements** plus workspace pages
   that have no `offering_code` (Users, Roles). Example: license only
   `TASK_MANAGEMENT` → Overview, Users, Roles & Permissions, Task Management.

Smartskale Admin uses the same login URL, `SMARTSKALE_SETUP_EMAIL` or
`ss_{CODE}_admin`, and `SMARTSKALE_SETUP_PASSWORD`. That account does not
require a first-login password change.

Inactive users (`is_active = false`) cannot authenticate; existing browser
sessions are revoked on deactivate.

## Adding a future offering (Core HR, Leave, Payroll)

Each product is a **catalog row** plus **backend module** plus **frontend
routes**. Creating the catalog entry does not create the product.

| Layer | Where | What to add |
|---|---|---|
| Catalog | `offerings` table / Platform Offerings UI | `code` (stable, e.g. `CORE_HR`), display name, route slug, `ACTIVE` |
| Pages | `pages` + Alembic seed | Rows with `app_scope=tenant` and `offering_code='CORE_HR'` |
| Defaults | `app/access_control/tenant/defaults.py` | Grants for Tenant Admin / HR roles on those pages |
| API | `backend/app/modules/<product>/` | Router with `Depends(require_offering("CORE_HR"))` |
| UI | `frontend/src/pages/...` + `router.tsx` | `<OfferingRoute code="CORE_HR" />` wrapping the module |
| Nav | `TenantShell.tsx` | Same pattern as Task Management, or generic `/app/modules/:slug` |

Worked scenario: tenant buys **Leave + Payroll**, not Task Management.

1. Platform admin registers the tenant and selects Leave and Payroll windows.
2. `create_tenant` stores two `tenant_offerings` rows.
3. Session `offerings` lists only those two effective codes.
4. `tenant_pages_for_entitlements` includes Users/Roles (no offering_code) plus
   pages whose `offering_code` is `LEAVE_MANAGEMENT` or `PAYROLL`.
5. Task Management APIs return 403 (`require_offering("TASK_MANAGEMENT")`).
6. Later, platform grants Task Management on the tenant detail page; after
   refresh the tenant session shows the new module without a code change.

File map for Task Management (copy this shape):

```
backend/app/modules/task_management/   # offering-owned API
backend/app/task_management/            # compatibility routers
backend/alembic/versions/0014_*     # tables
backend/alembic/versions/0019_*     # page offering_code
frontend/src/pages/Task*Page/
frontend/src/app/router/router.tsx   # OfferingRoute code="TASK_MANAGEMENT"
```

## Catalogs and entitlements

Plans and offerings are database catalogs. The platform registration UI reads
`GET /tenants/registration-options`; it does not embed plan, status, database,
or module choices. Each offering has a stable code, route slug, display name,
description, icon key, status, and sort order.

Tenant sessions include only currently effective offerings licensed to that
tenant. An entitlement is effective when its status is `ACTIVE`, its
`starts_at` has been reached, its `ends_at` has not been reached, and the tenant
itself is `ACTIVE`. The end timestamp is exclusive. Tenant suspension consumes
the entitlement window; it never extends `ends_at`.

Platform admins manage entitlements with:

- `GET /tenants?page=1&page_size=25&query=...&status=ACTIVE`;
- `POST /tenants/{tenant_id}/suspend` and `/activate`;
- `POST /tenants/{tenant_id}/enable` and `/regenerate-initial-password` for the
  first Tenant Admin;
- `GET /tenants/offering-catalog`;
- `GET /tenants/{tenant_id}/offering-entitlements`;
- `GET /tenants/{tenant_id}/offering-entitlements/history` for immutable transition events;
- `POST /tenants/{tenant_id}/offering-entitlements` to grant an offering;
- entitlement `suspend`, `resume`, and terminal `deactivate` actions;
- `DELETE /tenants/{tenant_id}/offering-entitlements/{entitlement_id}` to
  permanently remove a deactivated or expired entitlement with a required
  reason and expected version.

Platform admins manage the offering catalog separately with:

- `GET /offerings` to list every active and inactive offering and its usage;
- `POST /offerings` to create a catalog offering;
- `PATCH /offerings/{offering_id}` to edit its metadata (the stable code is immutable);
- `POST /offerings/{offering_id}/activate` and `/deactivate` to control new licensing;
- `DELETE /offerings/{offering_id}` to permanently remove an unused offering.

Catalog deactivation hides an offering from tenant registration and rejects new
grants, while preserving existing tenant entitlements. Deletion is blocked if
the offering has historical tenant entitlements or configuration categories.
Creating a catalog entry does not create a product module: its frontend and
backend functionality must be delivered separately and bound to the stable
offering code.

Platform default templates are managed at `/platform/default-templates`.
Publishing changes updates tenants that still inherit the default on their
next read or render. The first tenant customization stores a complete
subject/body snapshot, so later platform edits do not leak into customized
content; resetting deletes only that override and reveals the newest default.

Grant and transition requests carry an `expected_version` where applicable
and should carry an `Idempotency-Key`. The backend writes entitlement event,
platform activity, and audit rows in the same transaction. A re-grant creates
a new entitlement record. Deactivated and expired records are retained for 90
days by default, then the scheduled
`python -m scripts.reconcile_offering_entitlements` job permanently deletes the
entitlement and its transition events. Manual removal is available immediately
for retired records. Both paths retain only a minimal audit tombstone. Configure
the period with `DEACTIVATED_OFFERING_RETENTION_DAYS`. The same scheduled job
marks due active or suspended records as `EXPIRED`; request-time database checks
remain the hard access cutoff if the job is delayed.

The tenant shell builds module navigation from the effective session data. A
direct URL to an unlicensed module is rejected by the client route, while all
backend tenant data access is checked again against the current tenant and
entitlement state. Existing bearer tokens and browser sessions therefore lose
access immediately after tenant suspension or entitlement expiry.

## Read model

`GET /tenants` and `GET /tenants/{tenant_id}` join the current plan and database
allocation, calculate the live user count, and attach licensed offerings. The
platform registry therefore renders:

`Tenant | Status | Plan | Database | Users | Created | Actions`

without frontend fixtures or duplicated business state.
