# Parchi — Build Log

A running log of what's been built so far, in the order it happened. Kept for context if work continues later or hands off to someone else.

---

## 1. Project scoping

Parchi is a multi-tenant inventory + billing web app for small Indian businesses (e.g. a farsan/kirana shop), built in Django, targeting PythonAnywhere hosting with an Android APK wrapper built via GitHub Actions. Name "Parchi" = the chit/slip a shopkeeper scribbles a sale on.

Key decisions locked in early (see [humble-inventing-spark.md plan](~/.claude/plans/humble-inventing-spark.md) for full detail):
- **WhatsApp send**: plain `wa.me` click-to-chat link with the bill's public URL — no paid WhatsApp Business API, no server-side credentials.
- **"Real-time" inventory**: simple polling (~7s) of a small JSON endpoint, not WebSockets — PythonAnywhere's standard hosting can't hold long-lived socket connections anyway.
- **Mobile app**: a Capacitor WebView wrapper pointing at the live site, built by GitHub Actions — not a separate native app.
- **Multi-tenancy**: single shared database, every tenant-scoped model has a `business` FK, enforced via middleware + manager + view mixins (see §4).
- **No GST/tax for MVP** — bills are a plain subtotal, explicitly labeled "not a tax invoice."
- **Signup**: self-serve, username/password, no OTP/SMS.
- **UI**: must look like a real modern app, not a default Django form site — Tailwind (CDN), mobile-first, bottom nav + FAB + cards.

---

## 2. Project scaffold

- Django 5.1 project `parchi`, four apps: `accounts` (tenancy, auth, staff, super-admin), `inventory` (products/units), `billing` (bills/PDF/WhatsApp), `reports` (analytics).
- Dependencies: `django`, `reportlab` (PDF), `whitenoise` (static files), `django-hijack` (impersonation) — all mainstream, widely-used PyPI packages, installed only after explicitly naming each one and confirming with the user first.
- `.gitignore` set up (excludes `venv/`, `db.sqlite3`, `media/`, `staticfiles/`, `.env`; keeps `mobile/android/` for when the Capacitor project exists, since that's meant to be committed).
- `TIME_ZONE = 'Asia/Kolkata'`, env-driven `SECRET_KEY`/`DEBUG`/`ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS` so the same settings file works locally and on PythonAnywhere.

---

## 3. Data model

- **`Business`** — name, slug, owner, phone, **email**, address. Has `product_count` / `staff_count` / `bill_count` / `total_revenue` convenience properties (shared by Django admin and the super-admin dashboard).
- **`Membership`** — links a `User` one-to-one to a `Business` with a role (`ADMIN`/`STAFF`) and an `is_active` flag (lets an Admin disable a staff login without deleting it).
- **`Unit`** — global defaults seeded via data migration (kg, g, L, ml, pc, dozen, box, packet, bundle) plus per-business custom units.
- **`Product`** — business-scoped, `Decimal` stock/prices (never float), soft-delete via `is_active`, unique product name per business.
- **`Bill`** / **`BillLineItem`** — `Bill.public_id` is a UUID (the only identifier ever exposed in the public share URL). Line items snapshot the product name/unit/price/cost *at time of sale*, so later price edits or product renames never retroactively change historical bills or reports.

All money/quantity fields are `Decimal` with explicit `max_digits`/`decimal_places`.

---

## 4. Multi-tenant safety (the part treated as most safety-critical)

Three redundant layers, in `accounts/`:
1. **`BusinessMiddleware`** — attaches `request.business` / `request.membership` from the logged-in user's `Membership`.
2. **`BusinessScopedManager`** — `Model.objects.for_business(business)`; convention is to never call a bare `.filter()` on a tenant-scoped model.
3. **View mixins** — `BusinessRequiredMixin` (must have a business), `AdminRequiredMixin` (must be that business's Admin, checked *before* the view body runs so a non-admin POST never executes), `BusinessQuerysetMixin` (forces `get_queryset()` to scope by business, so a guessed URL for another tenant's object 404s instead of leaking).
4. Later added **`SuperuserRequiredMixin`** for the platform-admin-only pages.

The one deliberate, clearly-commented exception: the public bill-share view looks up by `public_id` (UUID) with no auth/business filter at all — that's intentional, since it's the link a customer opens from WhatsApp with no Parchi login.

**Verified directly** (not just by inspection):
- Cross-tenant object access (guessing another business's product/bill URL) → **404**.
- Staff hitting admin-only pages (product create, reports, staff list) → **403**; staff can still create bills → **200**.
- A fresh Django `Client` test walked through: business-1 admin blocked from business-2's data, staff blocked from admin screens.

---

## 5. Billing flow

`billing/services.py::create_bill` runs in `transaction.atomic()`:
- Locks the relevant `Product` rows with `select_for_update()`.
- Decrements stock via a single conditional `UPDATE ... WHERE stock_qty >= qty` (`Product.objects.filter(...).update(...)`) — if zero rows match, raises a clean "stock changed, please retry" instead of ever allowing negative stock. This is a race-safety measure for two staff members selling the last unit at the same moment.
- Snapshots price/cost/name onto `BillLineItem` at the moment of sale.

After the transaction commits: a PDF is rendered and saved, and the staff member is shown a "Send on WhatsApp" button linking to `wa.me/<phone>?text=<message with bill link>` — no server-side WhatsApp API call at any point.

**Verified**: total calculation, stock decrement, and the full HTTP round-trip (`POST /bills/new/` → PDF generated → WhatsApp page) all tested directly against the running app.

---

## 6. Bill PDF (redesigned after user feedback — "the PDF should be good")

Original version (reportlab, plain A5 page) had two real problems, found by actually reading the generated PDF rather than assuming: bare Helvetica can't render the ₹ glyph at all (prices showed with no currency symbol, not even a broken character — it was silently just missing), and a short 2-item bill left most of an A5 page blank.

Rewritten (`billing/pdf.py`) as a compact, dynamically-sized receipt:
- Uses `Rs.` instead of the ₹ glyph — a universally-rendering ASCII-safe choice that needs no embedded font file.
- Page size is `100mm` wide with height computed from the actual number of line items, instead of a fixed A5 sheet — eliminates the dead blank space problem at its root rather than papering over it.
- Branded green header banner (matches the app's Tailwind brand color), dashed section dividers, bold total line, thank-you footer, short human-readable bill number (`Bill #19AF3024`, derived from the UUID).
- Item names use wrapping `Paragraph` cells (not raw strings) so a long product name wraps to multiple lines instead of overflowing its column.

**Stress-tested** (not just eyeballed once): a single-item bill with a deliberately long product name, and a 3-item mixed bill with one wrapped name — both stayed on one page with correct totals. Verified via the `Read` tool's actual PDF rendering, not just "should work" reasoning.

---

## 7. Frontend / UI

- Shared `templates/base.html` shell: sticky header with the Parchi mark + current business name, bottom tab bar (Products / New Bill / Reports / Staff for Admins; Products / New Bill / Logout for Staff), floating "+" action button pattern on list screens.
- Tailwind via CDN, custom brand green palette, Inter font, card-based lists everywhere instead of Django's default form-table look.
- Fixed a Tailwind base-reset quirk where `<ul>` bullets (e.g. Django's password-requirements list) were rendering with no bullet markers — added a scoped `main ul` rule.
- Fixed a responsive bug on the Reports date-filter row (Filter button was overflowing off-screen on narrow phones) by stacking it under the date inputs instead of forcing everything into one row.
- Verified at 375px mobile width throughout, since the Android app is literally this site in a WebView — the web UI *is* the app UI.

---

## 8. Super-admin / platform-operator panel

Two iterations:
1. First pass reused Django's built-in `/admin/` (enhanced `BusinessAdmin` with computed columns: product/staff/bill count, revenue) plus `django-hijack` for "log in as this user" impersonation (adds an Impersonate button to the user admin automatically via `hijack.contrib.admin`).
2. User asked for it to live in the app's own UI instead of raw Django admin. Added:
   - `SuperuserRequiredMixin` and `SuperAdminDashboardView` (`accounts/views.py`), listing every business as a Tailwind card (name, owner, phone/email, product/staff/bill counts, revenue), with search.
   - A **"View as [owner]"** button per card that posts directly to `django-hijack`'s own `acquire` endpoint — no custom impersonation logic written, just wired into the existing safe mechanism.
   - Superusers now land on this dashboard straight from login (`ParchiLoginView.get_success_url` override).
   - A custom `templates/403.html` so a superuser with no business (the normal case) sees a friendly branded page ("this account has no shop to view, go to admin panel") instead of Django's bare default 403 text — this was found as a real rough edge by actually clicking through the release-impersonation flow in the browser, not anticipated in advance.
   - Raw Django admin kept as a fallback link ("Open Django admin") for bulk/raw data edits.

**Verified**: hijack acquire/release round-trip via Django test client (impersonated session correctly resolves the target business; release correctly restores the superuser session), and the same flow clicked through in the browser end-to-end.

---

## 9. Business contact info on bills

Per user request: `Business.email` field added (migration `accounts/0002_business_email.py`). Signup form reorganized into two visually distinct cards — "Business details" (Name, Email, Mobile — all three now required, with a note that they're shown to customers on the bill) and "Your login" (Username, Password) — using Django's `field_order` to control layout instead of relying on declaration order. Phone + email now shown on both the customer-facing public bill page and the PDF.

---

## 10. Deployment documentation

`DEPLOYMENT.md` written (not executed — no git/GitHub actions were taken, per explicit instruction): covers pushing the code to GitHub, creating the PythonAnywhere web app, environment variables, editing the WSGI file, static/media file mappings, running migrations, and PythonAnywhere-specific notes (SQLite vs. MySQL upgrade path, no background workers needed, `wa.me` links aren't affected by the free tier's outbound restrictions, disk space management for accumulated bill PDFs).

---

## 11. Testing approach used throughout

Browser automation proved flaky this session (stale coordinate frames after auto-scroll-on-focus, a dev-server autoreload that silently failed to pick up a new template, occasional blank/0-viewport reads). Every functional and security claim above was cross-checked with either the Django test client (`django.test.Client`) or direct `manage.py shell` calls against the real database/service functions, not just a single browser click-through — that's why the log above says "verified" rather than "should work" in several places.

---

## What's not done yet

- Actual deployment to PythonAnywhere (guide written, not executed).
- The Capacitor Android wrapper + GitHub Actions APK build pipeline.
- Automated test suite (the plan calls out the stock-race condition and business-scoping/IDOR checks as the two highest-value tests to formalize).
- Code has not been pushed to GitHub or committed to git at all yet — the working directory isn't a git repository yet.
