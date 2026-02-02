from __future__ import annotations

import re
from typing import Any

# Keys we NEVER want to ship in member-facing payloads
DROP_EXACT = {
    "timestamp",
    "generated_at",
    "persisted_at",
    "_cached_at",
    "_elapsed_s",
    "_timed_out_components",
    "commence_time",
    "commence_time_iso",
    "game_time",
    "startTime",
    "startTimeEst",
    "start_time",
}

DROP_SUFFIXES = (
    "_utc",
    "_iso",
    "_epoch",
    "_timestamp",
)

# Safety net: ISO-8601-ish / UTC offset strings (only applied to known time keys,
# not arbitrary strings like IDs).
ISO_LIKE_RE = re.compile(r"(?:\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})|(?:Z$)|(?:\+\d{2}:\d{2}$)")

# If you want to be strict: remove any private telemetry keys starting with "_"
DROP_PRIVATE_PREFIX = "_"

_DROP_EXACT_LOWER = {k.lower() for k in DROP_EXACT}


def _should_drop_key(k: str) -> bool:
    if k in DROP_EXACT or k.lower() in _DROP_EXACT_LOWER:
        return True
    if k.startswith(DROP_PRIVATE_PREFIX):
        return True
    for suf in DROP_SUFFIXES:
        if k.lower().endswith(suf):
            return True
    return False


def sanitize_public_payload(obj: Any) -> Any:
    """
    Recursively removes UTC/ISO/telemetry from member-facing API responses.
    Keeps ET fields like: date_et, run_timestamp_et, start_time_et, start_time_timezone.
    """
    if isinstance(obj, list):
        return [sanitize_public_payload(x) for x in obj]

    if isinstance(obj, dict):
        clean: dict[str, Any] = {}
        for k, v in obj.items():
            if _should_drop_key(k):
                continue

            if isinstance(k, str) and (
                k.lower().endswith("_utc")
                or k.lower().endswith("_iso")
                or k.lower().endswith("_timestamp")
                or k.lower().endswith("_epoch")
            ):
                continue

            vv = sanitize_public_payload(v)

            if isinstance(k, str) and any(tok in k.lower() for tok in ("time", "date", "timestamp", "generated", "persisted")):
                if isinstance(vv, str) and ISO_LIKE_RE.search(vv):
                    if " ET" not in vv and " EDT" not in vv and " EST" not in vv:
                        continue

            clean[k] = vv
        return clean

    return obj
