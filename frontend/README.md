# Secure multi-tenant frontend

React and TypeScript frontend for the multi-tenant application. The first
release provides organization-member and Platform Admin sign-in, opaque cookie
session restoration, role-aware redirects, route guards, and a dynamic
Platform Admin dashboard.

## Run locally

Prerequisites:

- Node.js 20.19+ or 22.12+
- The FastAPI backend running at `http://127.0.0.1:8000`
- Backend database migrations applied

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Open `http://127.0.0.1:5173`. Vite proxies `/api/*` to the backend and removes
the `/api` prefix.

Copy `.env.example` to `.env.local` only when you need to override the public
product name or API base path. Never put secrets in `VITE_*` variables; Vite
embeds them in the browser bundle.

## Commands

```powershell
npm.cmd run test
npm.cmd run lint
npm.cmd run build
npm.cmd run preview
```

## Architecture

```text
src/
  app/                 application composition, providers, router and guards
  pages/               route-level login and protected screens
  features/auth/       authentication API, forms and schemas
  features/platform-dashboard/ typed dashboard API, polling state and UI
  entities/session/    principal contracts, context and role routing
  shared/api/          credentialed HTTP client, CSRF and typed failures
  shared/ui/           reusable accessible controls
  shared/styles/       design tokens and global browser defaults
```

Dependency direction is `pages → features → entities/shared`. `app` is the
composition root and may wire every layer together. Shared modules never import
pages or features.

## Authentication flow

1. At startup, `AuthProvider` requests `GET /api/auth/session`.
2. Organization members submit email and password to
   `POST /api/auth/session/tenant`.
3. Platform Admins use `POST /api/auth/session/platform`.
4. The backend stores the opaque session in the HttpOnly `mt_session` cookie.
   JavaScript cannot read it.
5. Unsafe requests attach the readable double-submit `mt_csrf` cookie in the
   `X-CSRF-Token` header.
6. `DELETE /api/auth/session` revokes the server session and signs out.
7. A protected-request 401 clears local principal state and returns the user to
   sign-in.
8. A bootstrap account is routed to `/account/change-password`; successful
   change rotates the cookies and keeps the browser signed in.

The API client always uses `credentials: "include"`. Credentials and session
tokens and login identifiers are never written to localStorage or
sessionStorage.

## Role routing

| Principal | Destination |
| --- | --- |
| Platform Admin | `/platform` |
| Tenant Admin | `/app/overview` |
| Project Manager | `/app/overview` |
| Employee | `/app/my-work` |

Entering another role’s area redirects to `/forbidden`; entering a protected
route without a session redirects to `/login`.

## Platform Admin dashboard

The Platform Admin shell contains Dashboard, All Tenants, and Register Tenant.
The latter two routes are explicit placeholders for the next release.

Dashboard values come from `GET /api/platform/dashboard`; readiness comes from
`GET /api/health/ready`. The page polls every 60 seconds only while visible,
refreshes on focus and preset changes, and preserves the last successful
snapshot after a background failure. Recharts renders the visual charts, with
expandable data tables available as accessible alternatives.

Metric definitions and backend persistence are documented in
[`../docs/platform-dashboard.md`](../docs/platform-dashboard.md).

## Validation policy

Login validates RFC-style email syntax and field lengths. It requires a
password without reapplying password-creation strength
rules. This is intentional: existing valid passwords must remain usable.
Strong-password enforcement belongs to backend account creation and password
change operations.

## Production deployment

Serve the compiled `dist/` application and backend `/api` routes under one
HTTPS origin. Ensure the backend sets `mt_session` with `HttpOnly`, `Secure`,
`SameSite=Lax`, and `Path=/`, and configures the corresponding CSRF cookie.
The frontend router requires the web server to fall back to `index.html` for
unknown non-API paths.
