# region agent log
"""Debug-mode NDJSON logger. Safe to remove after verification."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

_SESSION_ID = "0ac8d2"
_LOG_PATH = Path(__file__).resolve().parents[3] / "debug-0ac8d2.log"


def dbg(location: str, message: str, data: dict[str, Any] | None = None, hypothesis_id: str | None = None) -> None:
    try:
        payload = {
            "sessionId": _SESSION_ID,
            "timestamp": int(time.time() * 1000),
            "location": location,
            "message": message,
            "data": data or {},
        }
        if hypothesis_id is not None:
            payload["hypothesisId"] = hypothesis_id
        with open(_LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
    except Exception:  # noqa: BLE001
        pass
# endregion
