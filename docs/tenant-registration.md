# Tenant registration architecture

Tenant onboarding is owned by the Platform Admin boundary and is persisted as
one database transaction.

## Write model

`POST /tenants` creates:

1. the tenant identity, company profile, address, and business contact;
2. the current subscription;
3. the database allocation;
4. the selected tenant-offering licenses;
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

Tenant sessions include only active offerings licensed to that tenant. The
tenant shell builds its module navigation from that session data. A direct URL
to an unlicensed module is rejected by the client route, while all backend
tenant data access remains tenant-scoped by the authenticated principal.

## Read model

`GET /tenants` and `GET /tenants/{tenant_id}` join the current plan and database
allocation, calculate the live user count, and attach licensed offerings. The
platform registry therefore renders:

`Tenant | Status | Plan | Database | Users | Created | Actions`

without frontend fixtures or duplicated business state.
