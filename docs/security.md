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

## Open registration

The sign-up page no longer asks for an institution. Accounts registered
without a code join the institution named by `OPENCAMPUS_OPEN_REGISTRATION`
(default `opencampus`, "OpenCampus Community", in development; **off** by
default in production) as **students**. It is created on first use from
configuration only, never from request input. A platform admin can close it
like any other institution (suspend it or turn off self-registration).
Multi-tenancy is unchanged: the API still accepts an `institution_slug` to
join a specific institution, and all tenant isolation and RLS rules apply.

## Rate limiting (M3.1)

### Architecture

- **Store:** PostgreSQL table `rate_limit_buckets` (`key_hash`, `window_start`,
  `count`, `expires_at`; primary key `(key_hash, window_start)`, index on
  `expires_at`). Global security infrastructure: no `institution_id`, no RLS.
  The app role has `SELECT, INSERT, UPDATE, DELETE` only.
- **Algorithm:** fixed windows aligned to database time
  (`date_bin(window, now(), epoch)`). One atomic upsert per request covers
  every applicable policy:
  `INSERT … ON CONFLICT (key_hash, window_start) DO UPDATE SET count = count + 1 RETURNING count`.
  Concurrent hits serialise on the row, so the limit cannot be exceeded
  (tested with 20 simultaneous requests against a limit of 5).
- **Own transaction:** each check runs on a separate connection and commits
  immediately. It must: a failed login raises an error and rolls back the
  request transaction, which would otherwise discard the failure count.
- **Keys:** `HMAC-SHA256(OPENCAMPUS_RATE_LIMIT_SECRET, policy ‖ identity)`.
  Raw emails, IP addresses and session ids are never stored and cannot be
  recovered or linked without the secret. The secret must differ from the JWT
  secret; rotating it simply resets all counters.
- **Fixed-window limitation:** a client can use its full allowance at the end
  of one window and again at the start of the next, up to 2× the limit in a
  short burst. Pairing a short and a long window (5/min + 20/hour) bounds
  this. A sliding-window or token-bucket algorithm can replace it later
  without changing callers.

### Policies (defaults; all configurable via `OPENCAMPUS_RATE_LIMIT_*`)

| Endpoint | Identity | Limits | Counts |
| -------- | -------- | ------ | ------ |
| login    | client IP | 5/min, 20/hour | every attempt |
| login    | normalised email | 5/15 min, 20/hour | **failed** attempts only (unknown email or wrong password); cleared on success |
| register | client IP | 3/hour | every attempt (after body validation, before hashing) |
| refresh  | session (looked up from the refresh token) | 30/min, 120/hour | every attempt |
| refresh  | client IP | 120/min, 1200/hour | every attempt |

Rationale and trade-offs:

- **Enumeration:** the account bucket is keyed on the email whether or not an
  account exists, unknown emails accumulate failures exactly like real ones,
  and every 429 has the same body. Limits therefore reveal nothing about which
  emails are registered (tested).
- **Targeted lockout (DoS):** anyone can spend another user's failure
  allowance by guessing wrong passwords for their email, blocking that
  account's logins for up to 15 minutes (or an hour at 20 failures). This is
  the price of stopping distributed password guessing. It is bounded: no
  permanent lockout, the attacker's own IPs are limited, and a successful
  login resets the count. Future mitigations: per-device trust cookies or
  CAPTCHA instead of a hard block.
- **Shared IPs (campus NAT):** many students can share one public address.
  The login IP limit (5/min) can affect a lab full of students signing in at
  once; raise `OPENCAMPUS_RATE_LIMIT_LOGIN_IP` for such deployments. Refresh
  IP limits are deliberately generous for the same reason; the per-session
  limit is the strict one.
- **Refresh and the 20 s grace window:** the refresh guard runs after CSRF
  and *before* rotation. A rate-limited refresh never rotates a token, never
  enters reuse detection and never revokes a session. Parallel-tab refreshes
  keep their existing "superseded, retry" behaviour (tested with 4
  simultaneous refreshes of one token: one rotates, three get
  `refresh_superseded`, nothing is revoked).
- Logout is not rate limited: it only ever reduces access.

### Responses

- Over a limit: `429` with `Retry-After` (seconds, from database time) and
  `{"detail": "Too many attempts. Please wait and try again.", "code": "rate_limit_exceeded"}`.
  The code follows the existing lower-snake-case convention.
- Storage failure (e.g. database unavailable or permission error): `503`
  `{"code": "rate_limit_unavailable"}` with `Retry-After: 30`. The protected
  request does **not** proceed: it fails closed, and a storage fault is never
  reported as a 429.

### Client IP and trusted proxies

- The client is the direct TCP peer, unless that peer is in
  `OPENCAMPUS_TRUSTED_PROXIES` (IPs/CIDRs). Only then is `X-Forwarded-For`
  read, right to left: trusted hops are skipped and the first untrusted
  address is the client. Entries further left were written by the client and
  are ignored. `Forwarded` and `X-Real-IP` are not used.
- IPv6 clients are grouped by /64 (one end site), IPv4 per address.
- **Uvicorn trusts `X-Forwarded-For` from 127.0.0.1 by default.** Run it with
  `--no-proxy-headers` so the app setting above is the single source of truth.
  The Vite dev proxy additionally strips client-supplied forwarding headers.
- Production behind nginx/Caddy: set `OPENCAMPUS_TRUSTED_PROXIES` to the
  proxy's address and make the proxy *append* the peer address
  (`proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;`).

### Cleanup and operations

- 1% of checks also delete up to 500 expired rows. For predictable upkeep,
  schedule `python -m app.cli purge-rate-limits` (e.g. daily).
- To unblock someone during an incident, delete their rows, or wait: every
  block expires with its window.
- Watch for sustained 429 or 503 rates: 429 spikes suggest an attack or a
  limit too low for a shared IP; 503 means the rate-limit store is failing and
  sign-in is down.

## Password recovery (M3.2)

### Lifecycle

1. `POST /api/auth/password-reset/request {email}` → always `202` with the
   same message. Rate limited per IP (5/15 min, 20/hour) and per email
   (3/hour, counted whether or not the account exists).
2. For an **active** account only: earlier unused tokens are deleted, a new
   token is created (32 bytes from the OS CSPRNG, URL-safe), and only its
   SHA-256 hash is stored with a 30-minute expiry (`password_reset_tokens`).
3. The email is sent as a background task **after** the response, so SMTP
   latency cannot reveal whether the account exists. Delivery failures are
   logged by exception type only, never with the link.
4. The link is `OPENCAMPUS_FRONTEND_URL/reset-password#token=…`. The token is in
   the **fragment**: browsers never send it to servers, proxies, access logs or
   in `Referer`. The page reads it and immediately removes it from the
   address bar and history.
5. `POST /api/auth/password-reset/confirm {token, new_password}` (rate limited
   per IP, 10/15 min, 30/hour; password policy as registration, 12–128 chars).
   In **one transaction**:
   - `UPDATE … SET used_at = now() WHERE token_hash = :h AND used_at IS NULL AND expires_at > now() RETURNING user_id`:
     a single statement, so concurrent confirmations race on the row and
     exactly one wins (tested with 6 at once);
   - new Argon2id hash for *that* user (the user comes only from the token row);
   - remaining unused tokens deleted;
   - **every session revoked** (`revoke_reason = password_reset`), which kills
     all refresh tokens and, because access tokens are checked against their
     session, all access tokens immediately.
   Any failure rolls all of it back. Afterwards the account's login-failure
   counters are cleared and this browser's auth cookies are deleted; the
   user must sign in with the new password.
6. Invalid, expired and used tokens all return `400 reset_token_invalid`.

Token lookup is by hash through a unique index; the attacker never controls
the stored value, so comparison timing reveals nothing useful. Raw tokens
exist only in the email and the user's browser.

### Email delivery

- `dev_file` (development default): each email is written as an `.eml` file
  to `backend/.dev-mail/`; the log records only the recipient's domain and the
  file path. `python -m app.cli dev-mail` prints the newest. **Refused at
  startup when `OPENCAMPUS_ENV=production`.**
- `smtp`: Python's standard `smtplib`, no extra dependency. `starttls`
  (default) or `ssl`, with certificate and hostname verification
  (`ssl.create_default_context()`). `none` is only for local relays and is
  refused in production or when credentials are set. Host, port, username,
  password and sender come from environment variables; the password is
  excluded from the settings' `repr` and never logged.
- Production also requires `OPENCAMPUS_FRONTEND_URL` with `https`. Links are
  never built from `Host`/`X-Forwarded-Host` (tested).

### Limitations

- Possession of the mailbox is the only factor: anyone who controls the
  user's email can reset the password (standard for email recovery; MFA would
  address it).
- Small timing difference remains between existing and unknown accounts (one
  extra insert on the request path); delivery itself is off the request path.
- Delivery is in-process: if the API process stops right after responding,
  that email is lost (the user can request again). A persistent mail queue
  would fix this.
- The per-email request limit means an attacker can use up a victim's 3
  reset emails per hour (the victim can still sign in normally).

## Known gaps (not yet implemented)

- Rate limits are fixed-window (see above); no CAPTCHA or device trust yet.
- No email verification, password reset or MFA.
- Registration reveals whether an email is registered (409). Inherent to
  self-service sign-up without email verification.
- HS256 with one shared secret; no key rotation (`kid`) yet.
- No audit log of administrative actions.
