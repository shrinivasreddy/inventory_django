# Inventory Web — Django Migration

Same app (Sign / Pavement / Lane / Curb inventory, all four tabs, full
feature parity with the desktop app), migrated from Flask to Django.

## What actually changed, and why

**Storage moved from flat JSON files to Django's ORM + SQLite.** The Flask
version stored records as JSON files with hand-rolled atomic writes and
locking. Django is built around an ORM and a real database -- fighting that
to keep flat files would work against the framework instead of with it, and
a real database is a genuine upgrade: transactions with automatic
rollback-on-error (Django's `transaction.atomic()`), proper indexing, and
Django's built-in admin site as a free data-browsing/editing UI (see below).

Two models cover everything (`inventory/models.py`):
- `TabRecord` — one row per record; the tab-specific columns (21 for Sign,
  17 for Pavement, etc.) are stored as a JSONField rather than fixed DB
  columns, preserving the same spec-driven design the Flask version used.
- `TabState` — one row per tab holding its dropdown options, MUTCD tables,
  and auto-fill type-map. Direct DB equivalent of the Flask version's
  in-memory `state[key]` dict.

**Everything else is unchanged on purpose:**
- `inventory/specs.py` — the four tab specs and `compute_auto_fields` are
  copied verbatim from the Flask version (pure functions over dicts, no
  framework dependency) -- this is the most-tested, most-reviewed part of
  the whole app, so it was deliberately left alone rather than rewritten.
- `templates/index.html` — the entire frontend (all the form-building,
  MUTCD linking, the Lane conditional-dropdown exception, lat/long paste,
  everything) is **byte-for-byte the same file**, with exactly one line
  changed (`{{ tabs | tojson }}` → `{{ tabs_json|safe }}`, since Django
  templates don't have Jinja's `tojson` filter). The API URLs and JSON
  shapes were kept identical specifically so the frontend wouldn't need to
  change and re-risk all that already-verified logic.

## Testing done for this migration
Ran the exact same regression suite that validated the Flask version,
against Django's test client: Sign UID generation, MUTCD classification
linking, Pavement/Lane/Curb auto-fill, Lane's 27B conditional-dropdown
exception (both valid and invalid submitted values), Curb's default field
value, malformed-request validation, per-tab and all-tabs Excel export, and
unknown-tab 404 handling. Also re-ran the same 20-concurrent-request stress
test against a real running waitress+Django server and confirmed zero ID
collisions, same as the Flask version.

## What changed in this review pass (production hardening)

**A real bug, not just config:** the Django admin site (and any future
static assets) had no way to actually serve its CSS/JS files under this
deployment setup -- `waitress` doesn't serve static files, and Django only
auto-serves them when `DEBUG=True` (via `runserver`, which this app
deliberately doesn't use). Under the previous version, `/admin/` would have
loaded completely unstyled in a real deployment. Fixed with `whitenoise`,
which serves static files directly from the same process -- verified by
actually starting a real waitress server with `DEBUG=false` and confirming
the CSS file loads with a 200, not just that the HTML page loads.

**Everything hardcoded is now configurable** (see `.env.example` for the
full list, all optional except the first three which already had sane
defaults):
- `DJANGO_TIME_ZONE`, `DJANGO_LANGUAGE_CODE` -- were hardcoded to UTC/en-us
- `DJANGO_DB_PATH` -- lets you put the SQLite file on a different drive
- `DJANGO_ADMIN_URL` -- change from the default `admin/` if you want
- `DJANGO_CSRF_TRUSTED_ORIGINS` -- for reverse-proxied HTTPS deployments

**Other hardening:**
- Basic logging now writes warnings/errors to `logs/django_errors.log`
  (rotating, 5MB × 5 files) in addition to console output, so problems are
  diagnosable after the fact instead of only visible in a terminal that's
  no longer open.
- `CSRF_COOKIE_HTTPONLY` and `X_FRAME_OPTIONS` set explicitly (safe
  regardless of HTTP/HTTPS, unlike the SSL-only settings left to the
  reverse proxy).

## Setup
Requires Python 3.8 or newer (Django 4.2 LTS, pinned in requirements.txt,
supports 3.8 through 3.12 -- check with `python --version` if install
fails with a "no matching distribution" error).

```bash
pip install -r requirements.txt
cp .env.example .env
# edit .env: set DJANGO_SECRET_KEY (see the comment in .env.example),
# and DJANGO_ALLOWED_HOSTS once you know your server's hostname/IP

python manage.py migrate
python manage.py collectstatic --noinput
python serve.py
```
Open `http://<host>:8000` (port 8000 by default this time, not 5000 --
change `SERVER_PORT` in `.env` if you want to match the old Flask port).

**Don't use `python manage.py runserver`** for anything but your own local
testing -- same category of problem as Flask's dev server (not built for
multiple simultaneous users). Always use `python serve.py`, which serves
the same Django app through waitress, a real production server.

Re-run `python manage.py collectstatic --noinput` after any future code
update (safe to run repeatedly) -- it refreshes the static files whitenoise
serves for the admin site.

## Bonus: built-in admin site
Django ships a full admin UI for free once models are registered (already
done in `inventory/admin.py`). To use it:
```bash
python manage.py createsuperuser
```
Then visit `/admin/` to browse and edit raw records directly -- handy for
fixing a bad record without going through the form, though the main app UI
is still the intended way to enter data day-to-day.

## Deploying for your team (50 users)
Same guidance as the Flask version, same reasoning:
- `deploy/install_windows_service.bat` (NSSM) / `deploy/inventory-web.service`
  (systemd) -- wraps `serve.py` as a background service that starts on boot,
  exactly like Tomcat's always-on behavior.
- Put IIS/Nginx in front for HTTPS; don't expose the app port directly.
- **Run as one process.** The per-tab write locks and SQLite's own locking
  both assume a single process. Don't run multiple instances behind a load
  balancer -- if you outgrow one process, migrate to Postgres/MySQL first
  (a config change in `settings.py`'s `DATABASES`, not a rewrite, since the
  ORM code doesn't care which database engine is underneath).
- Back up `db.sqlite3` the way you'd back up any database -- it now holds
  everything `store/*.json` used to hold in the Flask version.

## CSRF note
The `/api/...` endpoints are marked `@csrf_exempt` since they're called as
a JSON API from the same-origin frontend with no session-based
authentication to protect. If you add login later, switch these to proper
CSRF-token-protected requests instead of exempting them.

## About `manage.py check --deploy`
Running this will show warnings about `SECURE_SSL_REDIRECT`,
`SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, and HSTS. These are all
about HTTPS enforcement, deliberately left unset here rather than hardcoded
-- forcing HTTPS redirects before your reverse proxy is actually serving
HTTPS would just break the app. Once IIS/Nginx is confirmed handling HTTPS
in front of this, you can set those four in `settings.py` for extra
hardening; they're not required for the app to function correctly.

## Not part of this migration
No functional changes were made beyond the framework swap -- if you spot
anything behaving differently from the Flask version, that's a bug in the
migration, not an intentional change, and worth flagging.
