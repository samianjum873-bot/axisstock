# AxisStock Patch Notes

## Security Fixes
- Super-admin cookie is now HttpOnly + SameSite=strict (was trivially forgeable)
- `SUPER_ADMIN_PASS` must be set via env var; login is disabled if empty
- `SESSION_SECRET` read from env var; no more hardcoded 'change-this-secret-key'
- Tenant schema name sanitised to alphanumeric+underscore only
- Subdomain validated to alphanumeric+hyphen only
- Password minimum 6 chars enforced on create/reset
- `items_map` JSON-encoded server-side with `json.dumps(..., default=str)`;
  templates use `| safe` on the result which is safe because the data is
  application-generated (not user-raw).  For full XSS hardening consider
  `markupsafe.Markup(json.dumps(...))` and removing `| safe`.

## Bug Fixes
- `view_customer_detailed_profile`: `if not profile` check now happens BEFORE
  `dict()` conversion – fixes crash on missing CNIC.
- `checkout`: replaced `lastval()` with `RETURNING id` to avoid race conditions.
- `analytics_page`: `date_join` (with/without WHERE) is now separate from
  `date_where`, fixing broken SQL when joining sale_items.
- `migrate_existing_tenants` is now called inside lifespan (was never called).
- Middleware: `finally` block always resets `search_path` and releases
  connection even on exceptions – fixes connection leaks.
- `toggle_user_status` now prevents disabling yourself (parity with delete).

## Code Quality
- Removed duplicated `get_user_permissions` double-calls in user management routes.
- Added `_assert_users_manage()` helper to DRY auth checks.
- `require_login` and `require_permission` decorators added (with functools.wraps).
- `pos` and `index` routes deduplicated.
- `smart-add` permission check uses `inventory_write` (was incorrectly `sales_read`).
- `recent_sales` accepts `pos_access` OR `sales_read` (cashiers need it).

## New Files
- `.env.example` – documents required environment variables.
- `PATCHNOTES.md` – this file.
