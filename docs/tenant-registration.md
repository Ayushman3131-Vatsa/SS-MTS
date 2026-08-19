# Tenant registration architecture

Tenant onboarding is owned by the Platform Admin boundary and is persisted as
one database transaction.

## Write model

`POST /tenants` creates:

1. the tenant identity, company profile, address, and business contact;
2. the current subscription;
3. the database allocation;
4. the selected tenant-offering grants, including their UTC validity windows;
5. the first user with the `Tenant Admin` role;
6. platform activity and tenant audit records.

If any step fails, no partial workspace is committed. Workspace slugs and tenant
codes are serialized with PostgreSQL advisory locks before their unique
constraints are reached, which makes concurrent registrations deterministic.
Passwords are validated and stored only as Argon2id hashes.

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
