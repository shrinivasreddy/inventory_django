"""Process-wide coordination for per-section inventory writes.

The supported Waitress deployment uses one process with multiple threads.
Keeping the locks in a separate module lets manual entry and admin imports
share the same lock instead of racing on the visible per-section ID.
"""

import threading

from .specs import TAB_ORDER


section_write_locks = {key: threading.Lock() for key in TAB_ORDER}
