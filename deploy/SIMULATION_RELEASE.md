# Deploy the simulation review update

This release adds separate Sign day/night uploads, per-record comparison, and the `Night Sumulation Visibility` Yes/No export column. No database schema migration is introduced; fields are stored in existing record JSON. Existing image paths remain readable. Replacing either image clears its review answer.

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
