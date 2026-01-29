"""
Book field sanitizer - Ensures all picks have required book fields.

CRITICAL: Never allow empty book_key (breaks grading).
Applied at:
1. API serialization (before response)
2. Pick logging (before write)
3. Pick loading (auto-heal legacy rows)
"""

from typing import Dict, Any


def ensure_book_fields(pick_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enforce book_key, book, sportsbook_name, sportsbook_event_url defaults.

    Fallback: "consensus" for all book fields if missing.

    Args:
        pick_data: Pick dictionary (modified in-place)

    Returns:
        pick_data (same reference, modified)
    """
    book = pick_data.get("book", "")
    book_key = pick_data.get("book_key", "")

    # If book_key is empty, use fallback
    if not book_key:
        book_key = "consensus"

    # If book is empty, use fallback
    if not book:
        book = "Consensus"

    # Update pick_data with corrected values (in-place)
    pick_data["book_key"] = book_key
    pick_data["book"] = book
    pick_data["sportsbook_name"] = pick_data.get("sportsbook_name") or book
    pick_data["sportsbook_event_url"] = pick_data.get("sportsbook_event_url") or ""

    return pick_data
