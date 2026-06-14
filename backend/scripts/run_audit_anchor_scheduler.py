from __future__ import annotations

import json
import os
import sys
from pathlib import Path


backend_root = Path(__file__).resolve().parents[1]
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.core.settings import settings
from app.db.session import SessionLocal
from app.services.audit_anchor_scheduler import run_scheduled_audit_anchors


def main() -> int:
    if not settings.LUMENAI_AUDIT_ANCHOR_SCHEDULING_ENABLED:
        print(json.dumps({"status": "disabled", "anchors_created": 0}))
        return 0

    if os.getenv("LUMENAI_AUDIT_ANCHOR_PROVIDER", settings.LUMENAI_AUDIT_ANCHOR_PROVIDER) != "internal":
        raise SystemExit("Only the internal audit anchor provider is supported.")

    db = SessionLocal()
    try:
        summary = run_scheduled_audit_anchors(db)
    finally:
        db.close()

    print(json.dumps({"status": "ok", **summary}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
