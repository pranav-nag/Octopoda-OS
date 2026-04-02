"""
Report node usage to a backend (e.g. for tier limits / warning emails).
Fire-and-forget; does not block startup.
Optional: requires 'requests'. URLs must be set via env (no default endpoints).
"""

import os
import threading
from typing import Optional

try:
    import requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

# Set via env only; no default URLs (vendor-specific).
SYNRIX_VALIDATE_URL = os.getenv("SYNRIX_VALIDATE_LICENSE_URL", "").strip()
SYNRIX_UPDATE_USAGE_URL = os.getenv("SYNRIX_UPDATE_USAGE_URL", "").strip()


def report_usage_to_backend(
    license_key: str,
    current_usage: int,
    hardware_id: Optional[str] = None,
    instance_id: Optional[str] = None,
) -> None:
    """
    Report current node usage to backend (fire-and-forget).
    instance_id: optional stable id for this lattice so backend can sum across instances.
    """
    if not license_key or current_usage is None or not _HAS_REQUESTS or not SYNRIX_UPDATE_USAGE_URL:
        return
    payload = {"license_key": license_key, "current_usage": int(current_usage)}
    if hardware_id:
        payload["hardware_id"] = hardware_id
    if instance_id:
        payload["instance_id"] = instance_id

    def _post():
        try:
            requests.post(SYNRIX_UPDATE_USAGE_URL, json=payload, timeout=5)
        except Exception:
            pass

    threading.Thread(target=_post, daemon=True).start()
