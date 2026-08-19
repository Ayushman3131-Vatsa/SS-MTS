# Task management backend

Task management is a self-contained backend offering under
`backend/app/modules/task_management`. Shared authentication, tenants, users,
entitlements, audit, and database infrastructure remain in their existing shared
packages.

## Ownership and module boundaries

```text
task_management/
  router.py                 canonical offering router and entitlement gate
  access.py                 request-aware authorization orchestration
  domain/                   enums, transitions, pure policies, domain errors
  projects/                 model, schemas, repository, service, router
  memberships/              model, schemas, repository, service
  tasks/                    model, schemas, repository, service, router
  comments/                 model, schemas, repository, service, router
  time_entries/             model, schemas, repository, service, router
  attachments/              model, storage protocol, local adapter, service, router
  activity/                 append-only task history
  compat/                   boundary for the retained legacy APIs
```

Routers own HTTP translation only. Services own authorization, workflow,
transactions, and audit/activity orchestration. Repositories own tenant-scoped
SQLAlchemy queries. Domain policies and transitions do not depend on FastAPI or
SQLAlchemy. Offering models are re-exported by `app.models` for Alembic discovery.

## APIs and compatibility

`/task-management/*` is canonical and uses paginated list envelopes. It covers
projects, memberships, typed tasks and hierarchy, transitions, links, comments,
time entries, attachments, activity, archive, and restore. List page size is
capped at 100 and task sorting is allowlisted with a stable UUID tie-breaker.

The existing `/projects`, `/tasks`, task comments, and task logs routes are kept
as compatibility adapters. Their paths, request fields, array responses, UUIDs,
and response fields are unchanged. New integrations should use the canonical API.

## Authorization and workflow

Tenant admins have tenant-wide access. Project access is additionally governed by
`MANAGER`, `MEMBER`, or `VIEWER` membership. Managers plan and administer work;
members create unassigned tasks and collaborate; viewers are read-only; assignees
may update execution fields, transition their work, and log time. Inactive users
cannot be added or assigned, and employees cannot receive manager membership.

Task status transitions are fixed in `domain/transitions.py`. The dedicated
transition endpoint requires the current optimistic-lock version. A parent cannot
complete while it has an incomplete child. Assigning a `New` task changes it to
`Assigned`; other statuses are not changed implicitly.

## Database migration and RLS rollout

Migration `0014_task_management_expansion` adds and backfills the schema without
renaming or recreating legacy tables. It creates RLS policies but leaves RLS off.
Migration `0015_enable_task_management_rls` applies non-null contracts and enables
and forces RLS after application instances are capable of setting transaction
context.

Use two PostgreSQL roles in production:

- `MIGRATION_DATABASE_URL`: table-owning migration role.
- `DATABASE_URL`: runtime login without ownership, superuser, or `BYPASSRLS`.

Production startup rejects a missing migration URL or identical runtime/migration
usernames. Every authenticated request transaction sets local `app.tenant_id` and
`app.principal_type` from verified claims. Missing context sees no task-management
rows; platform scope is set only from a verified platform-admin principal.
Alembic explicitly sets platform scope on its owner connection so later data
migrations continue to work after forced RLS. Background work must use an explicit
tenant-scoped session; the ordinary session API rejects unverified platform scope.

Deploy application context support first, apply migration 0014, validate data and
queries, then apply 0015. Do not enable forced RLS while older application
instances remain in service.

## Attachments

Uploads use opaque generated storage keys outside the served application tree.
Configure `ATTACHMENT_STORAGE_ROOT`, `ATTACHMENT_MAX_BYTES` (10 MiB default),
`ATTACHMENT_MAX_PER_TASK` (20 default), and the media-type allowlist. Downloads go
through an authorized endpoint. The storage protocol is intentionally independent
of the local adapter so an S3-compatible implementation can be introduced later.
