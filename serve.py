"""
Production entrypoint: run this instead of `manage.py runserver`.

`manage.py runserver` is Django's own development server -- same category
of problem as Flask's dev server, not meant for multiple simultaneous
users. This script serves the exact same Django app through waitress, a
real production WSGI server, the same way the Flask version's app.py did.

Usage:
    python serve.py
"""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "inventory_project.settings")

import django  # noqa: E402
django.setup()

from inventory_project.wsgi import application  # noqa: E402

if __name__ == "__main__":
    host = os.environ.get("SERVER_HOST", "127.0.0.1")
    port = int(os.environ.get("SERVER_PORT", "8000"))
    thread_count = int(os.environ.get("SERVER_THREADS", "32"))

    try:
        from waitress import serve
        print(f"Serving with waitress on http://{host}:{port} ({thread_count} threads)")
        print(
            "IMPORTANT (multi-user deployment): run this as a single process, not "
            "multiple worker processes/instances behind a load balancer. The "
            "per-tab write locks only coordinate within one process -- a second "
            "process would have its own separate locks and could race with the "
            "first on writes."
        )
        serve(application, host=host, port=port, threads=thread_count)
    except ImportError:
        print(
            "waitress isn't installed -- install it (already in requirements.txt) "
            "and re-run. Refusing to fall back to `manage.py runserver` here since "
            "that server is not suitable for multiple simultaneous users."
        )
        raise SystemExit(1)
