# Production review — September 30, 2026

The application was reviewed locally. This is not a certification that all defects or vulnerabilities have been eliminated.

## Changes

- Custom account-approval, AI import/settings, and inventory export/template admin views now require model permissions, rather than accepting any staff account.
- Login (including admin login), signup and password-reset POSTs are rate limited: 15 per address/identity and 100 per address per five-minute window. Forwarded IP headers are not trusted. The default local-memory cache is appropriate only for this application's documented single-process deployment; retain edge rate limits, and use a shared cache before scaling to multiple processes. Shared-proxy users share the address limit unless the proxy safely supplies the remote address.
- Waitress enforces the configured request body limit and a 32 KB header limit before Django processes uploads.
- Django is pinned to 5.2.17 and python-dotenv to 1.2.2. Dependency audit results are in logs/dependency-audit.json. Django advisory: https://docs.djangoproject.com/en/5.2/releases/5.2.17/
- Staging clears old selections on loading, ignores stale responses, and blocks tab changes during mutations. Approval rejects boolean values in row IDs.
- The image viewer traps keyboard focus and cancels stale close timers when reopened.

## Verification results

- Full Django suite: 127 tests run, 126 passed, one optional supplied-workbook integration test skipped.
- All six JavaScript regression scripts passed.
- pip-audit against requirements.txt: no known vulnerabilities reported after upgrades.
- Django system checks, migration consistency, pip dependency consistency, and diff whitespace checks passed.
- Static collection completed. Waitress with DEBUG=false serves the local login page and static CSS with HTTP 200.
- Strict deployment check intentionally remains failing on the five configuration warnings below.

## Required production configuration

The deployment check reports placeholder SMTP configuration and disabled HTTPS redirect, secure session cookie, secure CSRF cookie, and HSTS settings. Local HTTP configuration was deliberately preserved. Before publishing:

1. Configure the real domain, TLS certificate/reverse proxy, explicit allowed hosts and trusted CSRF origins, and the HTTPS settings documented in .env.example. Trust proxy headers only from a controlled proxy that strips incoming spoofed headers. Confirm HTTPS before enabling HSTS.
2. Configure working SMTP credentials and test password-reset and account-approval delivery. Do not put credentials into source control.
3. Set DEBUG=false. Install requirements, apply migrations, collect static assets and run `python manage.py check --deploy --fail-level WARNING`, `python manage.py migrate --check`, and `python -m pip check` using the actual service environment.
4. Back up the SQLite database using SQLite's backup API (do not copy a live WAL database file alone) and the uploads directory. Verify restoration and run the service as a restricted account. Keep one application process, as required by the existing write-lock design.
5. Smoke-test authenticated roles and desktop/mobile layouts on the production-like deployment. The local browser was signed out, so authenticated visual verification is still outstanding; automated tests cover permissions and UI state logic.

Do not regard a successful local test run as proof of TLS, proxy configuration, SMTP delivery, backups, or production load capacity.
