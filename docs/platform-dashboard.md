# Platform Admin dashboard

The Platform Admin dashboard is the cross-tenant operational view. It is
available only to authenticated Platform Admin principals at `/platform` in
the React application and through `GET /platform/dashboard` in FastAPI.

## Navigation and frontend flow

The protected `PlatformShell` owns the existing top navigation, identity, and
logout controls. Its three nested routes are:

| Route | Module |
| --- | --- |
| `/platform` | Dynamic dashboard |
| `/platform/tenants` | All Tenants placeholder |
| `/platform/tenants/register` | Register Tenant placeholder |

The dashboard requests `/api/platform/dashboard` and `/api/health/ready`.
Vite removes `/api` in development; production must expose the frontend and
backend API under the same origin.

Growth supports 6, 12, and 24-month presets. New registrations supports 7,
30, and 90-day presets. Data refreshes when the page loads, a preset changes,
the window regains focus, the tab becomes visible, the operator selects
Refresh, or the 60-second visible-tab interval elapses. A failed background
refresh keeps the last successful snapshot on screen.

## Metric definitions

| Metric | Backend definition |
| --- | --- |
| Total Tenants | Every tenant, including suspended tenants |
| Active Tenants | Tenant is `ACTIVE`, its allocation is `READY`, and its current `ACTIVE` subscription is not expired |
| Dedicated Databases | `DEDICATED` allocations in `READY` state |
| Shared Database Tenants | `SHARED` allocations in `READY` state |
| Total Users | Every tenant-user row |
| New Tenants This Month | Tenants created in the current UTC calendar month |
| Expired Subscriptions | Tenants whose current subscription has an end time earlier than database time |
| System Health | API and primary PostgreSQL readiness only |

Tenant growth is a cumulative month-end series. New registrations is a
zero-filled daily tenant-creation series. Subscription distribution groups
current tenant subscriptions by stable plan code.

## Persistence

Alembic revisions `0005` through `0007` add:

- tenant lifecycle state and reporting indexes;
- the `FREE`, `BASIC`, `PRO`, and `ENTERPRISE` plan catalog;
- current and historical tenant subscriptions;
- Shared/Dedicated allocation intent and provisioning state; and
- durable platform activity events.

Existing tenants are backfilled as Active, Shared/Ready, and non-expiring on
their existing recognized plan. An unknown legacy plan value stops the
migration rather than silently changing customer data.

New tenant creation defaults to a non-expiring Free subscription and a
Shared/Ready allocation. Paid plans require a timezone-aware future
`subscription_ends_at`. Actual Dedicated PostgreSQL provisioning, billing,
plan-limit enforcement, and tenant status/plan management screens remain
separate future workflows.

## API contracts

```http
GET /platform/dashboard?growth_months=12&registration_days=30&activity_limit=10
```

- Requires a Platform Admin bearer token or browser session.
- Returns `Cache-Control: private, no-store`.
- Accepts activity limits from 1 through 25.
- Uses a dedicated `REPEATABLE READ, READ ONLY` PostgreSQL transaction so
  cards, charts, and activity describe one committed snapshot.

```http
GET /health/ready
```

This minimal public readiness probe returns `200` when the API and primary
database are healthy and `503` when the API is reachable but PostgreSQL is
unavailable. It returns component states only, never connection details.
Network failure is represented as Unavailable by the frontend.

## Verification

Backend dashboard behavior is covered both by unit tests and by the disposable
PostgreSQL integration suite. Frontend behavior is covered by Vitest and
Playwright, including route protection, shell navigation, dynamic values,
refresh behavior, and the mobile navigation drawer.
