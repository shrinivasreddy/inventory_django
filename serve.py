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
import hashlib
import tempfile
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "inventory_project.settings")

import django  # noqa: E402
django.setup()

from inventory_project.wsgi import application  # noqa: E402


def acquire_single_instance_lock(port):
    """Keep only one inventory server instance per workspace and port."""
    workspace = str(Path(__file__).resolve().parent).casefold()
    workspace_key = hashlib.sha256(workspace.encode("utf-8")).hexdigest()[:12]
    lock_path = Path(tempfile.gettempdir()) / f"bluedome-inventory-{workspace_key}-{port}.lock"
    lock_path.touch(exist_ok=True)
    lock_file = lock_path.open("r+b")
    if lock_path.stat().st_size == 0:
        lock_file.write(b"\0")
        lock_file.flush()
    try:
        if os.name == "nt":
            import msvcrt

            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (OSError, BlockingIOError):
        lock_file.close()
        raise SystemExit(
            f"Another inventory server is already running for this workspace on port {port}."
        )
    return lock_file

if __name__ == "__main__":
    host = os.environ.get("SERVER_HOST", "127.0.0.1")
    port = int(os.environ.get("SERVER_PORT", "8000"))
    thread_count = int(os.environ.get("SERVER_THREADS", "32"))
    instance_lock = acquire_single_instance_lock(port)

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
