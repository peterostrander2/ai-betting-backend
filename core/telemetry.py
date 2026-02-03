from typing import Any, Dict, Set


def apply_used_integrations_debug(result: Dict[str, Any], used_integrations: Set[str], debug_mode: bool) -> None:
    """Attach used_integrations only in debug responses."""
    if not debug_mode:
        return
    result.setdefault("debug", {})
    result["debug"]["used_integrations"] = sorted(used_integrations)
