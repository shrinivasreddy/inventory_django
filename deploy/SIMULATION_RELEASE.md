# Deploy the simulation review update

This release adds separate Sign day/night uploads, per-record comparison, and the `Night Sumulation Visibility` Yes/No export column. Database migrations 0019 and 0020 add separate staging storage and revision numbers. Run migrate before starting the updated app; no existing inventory rows are deleted. Existing image paths remain readable. Replacing either image clears its review answer.

## Before deployment

- Back up the server database using SQLite's backup API or stop the service before copying it. Back up the complete configured upload directory alongside it.
- Deploy source changes only. Preserve the server `.env`, database, uploads, and logs. Do not upload local `db.sqlite3`, `db.sqlite3-wal`, or `db.sqlite3-shm`; the latter two are currently tracked in this checkout despite the new ignore entries.
- Preserve old upload folders. New Sign images use `day-simulation/<project>/<ID>/` and `night-simulation/<project>/<ID>/`. Stored paths continue working after a project rename. Existing images are not moved by this release.
- The service account needs write access to the upload directory and logs. Image URLs require login and project/record access, including links opened from Excel.

## Server configuration

Set the actual hostnames in `DJANGO_ALLOWED_HOSTS`, the public HTTPS URL in `DJANGO_APP_BASE_URL`, and HTTPS origins in `DJANGO_CSRF_TRUSTED_ORIGINS`. Keep `DJANGO_DEBUG=false`. Configure real SMTP credentials and validate account approval/password reset emails. Local deployment checks currently report a placeholder SMTP host.

Once the reverse proxy serves HTTPS, enable `DJANGO_SESSION_COOKIE_SECURE=true`, `DJANGO_CSRF_COOKIE_SECURE=true`, and HTTPS redirection at the proxy or with `DJANGO_SECURE_SSL_REDIRECT=true`. Configure `DJANGO_TRUST_PROXY_SSL_HEADER` only when the trusted proxy overwrites that header. Set `DJANGO_SECURE_HSTS_SECONDS` according to the server's HTTPS policy. These remain disabled locally so HTTP login works.

Allow a request body of at least 25 MB at the proxy. Run exactly one application process, as required by the existing SQLite/write-lock design.

## Release commands

Stop the existing application service, deploy the changed source, then run with the server's Python environment:

```powershell
python -m pip install -r requirements.txt
python -m pip check
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py check --deploy
python manage.py test --noinput
```

Resolve deployment warnings appropriate to the server before reopening traffic. Restart the existing service using `serve.py`.

## Acceptance check

Sign in as a regular user and as an administrator. Upload day and night images to a test record, open its Compare button, verify both IDs and images, select Yes, navigate away/back, then select No. Export both a single section and all sections and verify the saved visibility value and public image hostname. Replace an image and confirm its previous review clears. Check mobile layout and keyboard navigation. Confirm another project's user cannot access the image/review. Verify backups can be restored.

For rollback, restore the previous source and collected static assets. Restore the backed-up database and uploads together if data rollback is required; avoid mixing snapshots from different times.


## September 22 review fixes

- Optional `NIGHT_SIMULATION_LINK` (also `Night Simulation Image`) imports independently of legacy Y/N/NV/NA visibility codes. Blank/missing links are supported.
- `SECTION ID` maps to ST_ID without adding an export column. Zero-valued coordinates and levels survive import.
- Configure `DJANGO_INVENTORY_IMAGE_ORIGINS` as comma-separated trusted HTTPS origins for externally hosted image previews. Default: `https://stpaul.bluedometech.com`. This affects browser image loading only; the application never downloads remote URLs server-side.
- Staging renders 100 rows per page and retains Select filtered across pages. Staging edit/approval versions now use integer revisions, avoiding rapid-edit timestamp collisions.
- Configuration tab labels use Django's escaped JSON output. Imported links reject non-HTTP(S) schemes and credentials.
- Run `node tests/frontend_review.cjs` for frontend pagination and URL policy tests. For an optional real-workbook integration check, set `INVENTORY_REVIEW_WORKBOOK` to a local XLSX path before running the Django suite; it uses an isolated test database and does not import into production.

Production readiness still requires validation on the target host: TLS/proxy configuration, SMTP delivery, backup restore, browser acceptance testing, and appropriate load tests. Local automated checks are not a certification that all production risks are eliminated.
