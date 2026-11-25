# Identity, authentication and multi-tenancy (M2)

## Schema

| Table            | Scope        | Key columns / constraints |
| ---------------- | ------------ | ------------------------- |
| `institutions`   | global       | `slug` unique + format check, `status` (active/suspended/archived), `allow_self_registration` (default **false**) |
| `users`          | global       | `email` unique, CHECK lowercase; `password_hash` (Argon2id); `is_active`; `is_platform_admin` |
| `memberships`    | **tenant**   | `institution_id` FK, `user_id` FK, `role` (student/faculty/college_admin), `status`; UNIQUE(institution_id, user_id); index on user_id; **RLS** |
| `auth_sessions`  | user         | `user_id`, `active_institution_id`, `expires_at` (absolute), `revoked_at`, `revoke_reason` |
| `refresh_tokens` | user/session | `session_id`, `token_hash` unique (SHA-256), `expires_at`, `rotated_at` |

All tables use UUID keys and `timestamptz` timestamps. Users and institutions
are independent; a user reaches an institution only through a membership, and
can hold several.

`platform_admin` is deliberately **not** a membership role: it is a
platform-wide flag on `users`, settable only with `python -m app.cli
create-platform-admin`.

## Authentication flow

```
login / register ──► Argon2id verify / hash
                 ──► auth_sessions row (+ active institution)
                 ──► refresh_tokens row (hash only)
                 ◄── JSON: access token (JWT, 10 min) + profile
                 ◄── Set-Cookie: refresh token (HttpOnly) + CSRF token

API call         ──► Authorization: Bearer <access token>
                     verify signature/exp/iss/aud (HS256 pinned)
                     load session by sid → must be live          (401)
                     load membership in session's tenant         (403)
                     role check from membership row              (403)

refresh          ──► refresh cookie + X-CSRF-Token header
                     lock token row; must be unrotated & unexpired
                     mark rotated, issue new token + access token
                     old token replayed within 20 s → "superseded" (retry)
                     old token replayed later      → session revoked

logout           ──► revoke session → its access tokens die immediately
```

- **Passwords:** Argon2id (t=3, m=64 MiB, p=4). 12–128 characters, no
  composition rules. Hashes are upgraded on login if parameters change. An
  unknown email still costs one Argon2 verification, so timing and response
  body do not reveal whether an account exists.
- **Access token:** short-lived JWT with `sub`, `sid`, `exp`, `iat`, `iss`,
  `aud`, `typ`. It carries **no role and no tenant**: both are read from the
  database per request, so demotions, suspensions and tenant switches apply
  immediately. Every request also checks the session row, so revocation is
  immediate rather than waiting for expiry.
- **Refresh token:** 256-bit random opaque value. Only its SHA-256 is stored
  (a slow hash is unnecessary for high-entropy input). Single-use; rotated on
  every refresh. Rotated rows are kept for reuse detection.
- **Sessions:** 7-day refresh window, 30-day absolute cap. Users can list and
  revoke their own sessions (`GET/DELETE /api/auth/sessions`).

## Token storage and cookies

| Item           | Where                         | Why |
| -------------- | ----------------------------- | --- |
| Access token   | JavaScript memory only        | Not in localStorage/sessionStorage; gone when the tab closes; short-lived |
| Refresh token  | `HttpOnly` cookie, `Path=/api/auth` | Unreadable by JS; sent only to auth endpoints |
| CSRF token     | readable cookie, `Path=/`     | Echoed by the SPA in `X-CSRF-Token` (double-submit) |

**Production** (`OPENCAMPUS_COOKIE_SECURE=true`, the default):
`Secure; HttpOnly; SameSite=Strict`, names prefixed `__Secure-`, which
browsers refuse to set without `Secure`. The app refuses to start with
`OPENCAMPUS_ENV=production` and insecure cookies. Serve UI and API from the
**same origin** (reverse proxy) so `SameSite=Strict` cookies always flow.

**Development** (`OPENCAMPUS_COOKIE_SECURE=false`): same flags minus
`Secure`, unprefixed names, because the Vite dev server is plain
`http://localhost`. The Vite proxy keeps UI and API on one origin.

**CSRF.** Only `/api/auth/refresh` and `/api/auth/logout` authenticate by
cookie; every other endpoint requires the `Authorization` header, which a
cross-site page cannot attach. The two cookie endpoints require
`SameSite=Strict` **and** a matching `X-CSRF-Token` header **and** an allowed
`Origin` when one is sent. Login/register take JSON bodies, which cross-site
forms cannot send without a CORS preflight.

## Roles

| Role            | Granted by                                  | Can (M2) |
| --------------- | ------------------------------------------- | -------- |
| student         | public registration (always), college admin | own profile, sessions |
| faculty         | college admin                               | as student |
| college_admin   | platform admin only                         | list members; set student/faculty; suspend members (not other admins or self) |
| platform_admin  | CLI only                                    | create institutions, change status/registration, provision college admins |

Registration bodies reject unknown fields, so `"role": "college_admin"` is a
422, not a silent no-op. Roles are never read from the client.

## Tenant isolation

1. **Resolution.** The tenant is the session's `active_institution_id`, set
   at login (first active membership, or a requested slug the user belongs
   to) or via `POST /api/auth/switch-institution`, which verifies membership.
   Tenant IDs in query strings, headers or bodies of other endpoints are
   ignored. Platform-admin operations on a named institution set that tenant
   only *after* the platform role is verified.
2. **Fail closed.** No active institution → `403 tenant_required`. Membership
   or institution not active → `403 tenant_access_denied`.
3. **Application filter.** Every tenant-scoped query includes
   `WHERE institution_id = :tenant`.
4. **Row-level security** (backstop for a forgotten filter). `memberships`
   has RLS `ENABLE`d and `FORCE`d. Policies compare `institution_id` with
   `app_current_tenant()`, which reads the setting `app.tenant_id`; reads may
   additionally see the signed-in user's own memberships (`app.user_id`) so
   "my institutions" works. Writes are restricted to the current tenant. A
   missing setting yields NULL, which matches nothing.
5. **Database roles.** Migrations run as `opencampus_owner`. The API runs as
   `opencampus_app`: not superuser, not owner, `NOBYPASSRLS`, no `TRUNCATE`
   or DDL rights.

### Connection pooling and tenant context

The context is set with `set_config('app.tenant_id', …, is_local => true)`,
i.e. **transaction-scoped**. PostgreSQL discards it at `COMMIT`/`ROLLBACK`, so
a pooled connection never carries one request's tenant into the next
(verified by `test_tenant_context_does_not_leak_across_pooled_connections`).
A session-level `SET` would leak and must never be used. This also works
behind PgBouncer in transaction-pooling mode.

The values live on the SQLAlchemy `Session` (`session.info`); an
`after_begin` listener re-applies them at the start of every transaction, so
a handler that commits mid-request does not lose context. If context was
never set, the listener sets empty strings → NULL → no rows.

### Why not RLS everywhere

`users` and `institutions` are global (identity and registry), and
`auth_sessions`/`refresh_tokens` are looked up by token hash *before* a user
is known; they are only reachable through the auth service. RLS applies to
tenant-owned tables. Every future institution-owned table must have
`institution_id NOT NULL`, be added to RLS in its migration, and be covered
by an isolation test.

## Known gaps (not yet implemented)

- No rate limiting or lockout on login/registration/refresh.
- No email verification, password reset or MFA.
- Registration reveals whether an email is registered (409). Inherent to
  self-service sign-up without email verification.
- HS256 with one shared secret; no key rotation (`kid`) yet.
- No audit log of administrative actions.
