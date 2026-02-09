# Bookie-o-em Code Standards

Claude Code: Follow these standards for ALL code modifications.

## Core Principles

1. **Preserve Functionality** - Never change what code does, only how it does it
2. **Clarity Over Brevity** - Explicit, readable code beats clever one-liners
3. **Consistency** - Follow existing patterns in the codebase

## Python Standards (FastAPI Backend)

### Formatting
- Use 4-space indentation
- Max line length: 100 characters
- Use type hints for function parameters and returns
- Use f-strings for string formatting (not .format() or %)

### Functions
```python
# GOOD: Explicit return type, clear name
def calculate_research_score(sharp_money: float, line_variance: float) -> float:
    """Calculate research score from sharp money and line variance."""
    base = 2.0
    sharp_bonus = min(sharp_money * 0.5, 3.0)
    variance_bonus = min(line_variance * 0.3, 3.0)
    return base + sharp_bonus + variance_bonus

# BAD: No types, unclear name
def calc(s, l):
    return 2.0 + min(s * 0.5, 3.0) + min(l * 0.3, 3.0)
```

### Conditionals
```python
# GOOD: Clear if/elif chain
def get_bet_tier(score: float) -> str:
    if score >= 9.0:
        return "TITANIUM"
    elif score >= 7.5:
        return "GOLD_STAR"
    elif score >= 6.5:
        return "EDGE_LEAN"
    else:
        return "MONITOR"

# BAD: Nested ternary (never use)
tier = "TITANIUM" if score >= 9.0 else "GOLD_STAR" if score >= 7.5 else "EDGE_LEAN" if score >= 6.5 else "MONITOR"
```

### Error Handling
```python
# GOOD: Let errors propagate, handle at boundaries
def fetch_odds(game_id: str) -> dict:
    response = requests.get(f"{API_URL}/odds/{game_id}")
    response.raise_for_status()
    return response.json()

# BAD: Swallowing errors silently
def fetch_odds(game_id: str) -> dict:
    try:
        response = requests.get(f"{API_URL}/odds/{game_id}")
        return response.json()
    except:
        return {}  # Silent failure = hidden bugs
```

### Imports
```python
# Order: stdlib → third-party → local
import json
from datetime import datetime
from typing import Optional, List

import httpx
from fastapi import APIRouter, HTTPException

from core.time_et import get_today_et
from core.invariants import TIER_THRESHOLDS
```

## Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Functions | snake_case | `calculate_esoteric_score` |
| Variables | snake_case | `sharp_money_pct` |
| Constants | UPPER_SNAKE | `MINIMUM_SCORE_THRESHOLD` |
| Classes | PascalCase | `PredictionEngine` |
| Files | snake_case | `live_data_router.py` |

## What NOT To Do

1. **No nested ternaries** - Use if/elif/else or match/case
2. **No bare except** - Always specify exception type
3. **No magic numbers** - Use named constants
4. **No commented-out code** - Delete it (git has history)
5. **No print() for debugging** - Use logging module
6. **No overly clever code** - Future you won't remember why

## Refactoring Guidelines

When simplifying code:
- Keep changes minimal and focused
- Test after each change
- Don't combine unrelated refactors
- Preserve all existing functionality
- If unsure, ask before changing

## Bookie-o-em Specific

### Scoring Constants (Never Hardcode)
```python
# Use from core/invariants.py
from core.invariants import (
    AI_WEIGHT,           # 0.25
    RESEARCH_WEIGHT,     # 0.30
    ESOTERIC_WEIGHT,     # 0.20
    JARVIS_WEIGHT,       # 0.15
    MINIMUM_SCORE,       # 6.5
)
```

### Time Handling (Always ET)
```python
# ALWAYS use this for today's date
from core.time_et import get_today_et

today = get_today_et()  # Returns ET date, not UTC
```

### Storage Paths (Never Change)
```python
# All paths relative to /app/grader_data on Railway
PREDICTIONS_FILE = "/app/grader_data/grader/predictions.jsonl"
WEIGHTS_FILE = "/app/grader_data/grader_data/weights.json"
```
