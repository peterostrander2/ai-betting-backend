# System Architecture

> How the components connect and data flows through the system.

---

## High-Level Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              CLIENT                                      │
│                    (Mobile App / Web Dashboard)                         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         LIVE DATA ROUTER                                 │
│                       (live_data_router.py)                             │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐  ┌──────────────┐  │
│  │ /health     │  │ /live/best-  │  │ /props      │  │ /games       │  │
│  │             │  │ bets/{sport} │  │             │  │              │  │
│  └─────────────┘  └──────┬───────┘  └─────────────┘  └──────────────┘  │
└──────────────────────────┼──────────────────────────────────────────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │  calculate_pick_score  │
              │      (~line 3200)      │
              └───────────┬────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│   GLITCH      │ │  Fibonacci    │ │   Other       │
│   Aggregate   │ │  Signals      │ │   Esoteric    │
└───────┬───────┘ └───────┬───────┘ └───────┬───────┘
        │                 │                 │
        └─────────────────┴─────────────────┘
                          │
                          ▼
              ┌────────────────────────┐
              │     ESOTERIC ENGINE    │
              │   (esoteric_engine.py) │
              └───────────┬────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│   DATABASE    │ │    PHYSICS    │ │   EXTERNAL    │
│ (database.py) │ │   SIGNALS     │ │     APIs      │
│               │ │(signals/*.py) │ │               │
│ - line_       │ │ - Hurst       │ │ - Space Wx    │
│   snapshots   │ │ - Chaos       │ │ - Astronomy   │
│ - season_     │ │               │ │               │
│   extremes    │ │               │ │               │
└───────────────┘ └───────────────┘ └───────────────┘
```

---

## Component Details

### 1. Live Data Router (`live_data_router.py`)

**Purpose**: Main API entry point, request routing, response formatting

**Key Functions**:
| Function | Line | Purpose |
|----------|------|---------|
| `get_best_bets()` | ~500 | Main endpoint handler |
| `calculate_pick_score()` | ~3200 | Core scoring logic |
| `format_response()` | ~4000 | Response structure |

**Data Flow**:
```
Request → Validate API Key → Fetch Raw Data → Calculate Scores → Format → Response
```

### 2. Esoteric Engine (`esoteric_engine.py`)

**Purpose**: All esoteric/unconventional signal calculations

**Key Functions**:
| Function | Line | Purpose |
|----------|------|---------|
| `get_glitch_aggregate()` | ~1100 | Combine GLITCH signals |
| `calculate_fibonacci_retracement()` | ~651 | Season range position |
| `calculate_chrome_resonance()` | ~200 | Birth date numerology |
| `check_void_moon()` | ~400 | Lunar position |

### 3. Physics Signals (`signals/physics.py`)

**Purpose**: Physics-based market indicators

**Key Functions**:
| Function | Line | Purpose |
|----------|------|---------|
| `calculate_hurst_exponent()` | ~395 | Trend vs mean-reversion |
| `calculate_chaos_indicator()` | ~550 | Market volatility |

### 4. Database (`database.py`)

**Purpose**: PostgreSQL connection and queries

**Key Functions**:
| Function | Purpose |
|----------|---------|
| `get_db()` | Context manager for connections |
| `get_line_history_values()` | Fetch historical lines |
| `get_season_extreme()` | Fetch season high/low |
| `save_line_snapshot()` | Store current line |

### 5. Daily Scheduler (`daily_scheduler.py`)

**Purpose**: Cron jobs for data collection

**Jobs**:
| Job | Schedule | Purpose |
|-----|----------|---------|
| `snapshot_lines()` | Every 30 min | Capture current lines |
| `update_season_extremes()` | Daily 5 AM ET | Calculate high/low |
| `cleanup_old_data()` | Daily 3 AM ET | Remove stale records |

---

## GLITCH Protocol Flow

```
                    ┌──────────────────────────────┐
                    │     get_glitch_aggregate()   │
                    └──────────────┬───────────────┘
                                   │
         ┌────────────────────────┬┴┬────────────────────────┐
         │                        │ │                        │
         ▼                        ▼ ▼                        ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Chrome Resonance│    │   Void Moon     │    │    Noosphere    │
│   (0.25 weight) │    │  (0.20 weight)  │    │  (0.15 weight)  │
│                 │    │                 │    │                 │
│ birth_date_str  │    │ game_date,      │    │ game_time       │
│ game_date       │    │ game_time       │    │                 │
└────────┬────────┘    └────────┬────────┘    └────────┬────────┘
         │                      │                      │
         │    ┌─────────────────┴──────────────────┐   │
         │    │                                    │   │
         ▼    ▼                                    ▼   ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Hurst Exponent  │    │    Kp-Index     │    │ Benford Anomaly │
│  (0.25 weight)  │    │  (0.25 weight)  │    │  (0.10 weight)  │
│                 │    │                 │    │                 │
│ line_history    │    │ game_date       │    │ value_for_      │
│ (from DB)       │    │ (space weather) │    │ benford         │
└────────┬────────┘    └────────┬────────┘    └────────┬────────┘
         │                      │                      │
         └──────────────────────┴──────────────────────┘
                                │
                                ▼
                    ┌──────────────────────────────┐
                    │   Weighted Average Score     │
                    │   + Combined Reasons List    │
                    └──────────────────────────────┘
```

---

## Data Flow: Hurst Exponent

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Scheduler  │────▶│ line_       │────▶│   Hurst     │
│  (30 min)   │     │ snapshots   │     │ Calculation │
└─────────────┘     │   table     │     └──────┬──────┘
                    └─────────────┘            │
                                               ▼
┌─────────────────────────────────────────────────────────┐
│                  Data Requirements                       │
│  • Minimum 10 snapshots per event_id                    │
│  • Each snapshot: event_id, value_type, value, timestamp│
│  • Accumulation time: ~5 hours (10 × 30 min)            │
└─────────────────────────────────────────────────────────┘
```

**Query**:
```python
get_line_history_values(db, event_id="abc123", value_type="spread", limit=30)
# Returns: [3.5, 3.0, 3.5, 4.0, ...] (list of float values)
```

---

## Data Flow: Fibonacci Retracement

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Scheduler  │────▶│  season_    │────▶│  Fibonacci  │
│  (5 AM ET)  │     │  extremes   │     │ Retracement │
└─────────────┘     │   table     │     └──────┬──────┘
                    └─────────────┘            │
                                               ▼
┌─────────────────────────────────────────────────────────┐
│                  Data Requirements                       │
│  • season_high and season_low for sport/season/stat     │
│  • Updated daily by scheduler                           │
│  • Season format: "2025-26" (Sept-Aug)                  │
└─────────────────────────────────────────────────────────┘
```

**Query**:
```python
get_season_extreme(db, sport="NBA", season="2025-26", stat_type="spread")
# Returns: {"season_high": 15.5, "season_low": 1.0}
```

**Calculation**:
```python
# Fibonacci levels: 23.6%, 38.2%, 50%, 61.8%, 78.6%
range = season_high - season_low
current_position = (current_line - season_low) / range
# Check if current_position is within 2% of any Fib level
```

---

## Database Schema Relationships

```
┌─────────────────────────────────────────┐
│              line_snapshots             │
├─────────────────────────────────────────┤
│ id (PK)                                 │
│ event_id (VARCHAR) ──────────┐          │
│ value_type (VARCHAR)         │          │
│ value (DECIMAL)              │          │
│ captured_at (TIMESTAMP)      │          │
└──────────────────────────────┼──────────┘
                               │
                               │ Used by
                               │ Hurst Exponent
                               │
┌──────────────────────────────┼──────────┐
│              events          │          │
├──────────────────────────────┴──────────┤
│ id (PK) ◀────────────────────┘          │
│ sport                                   │
│ home_team                               │
│ away_team                               │
│ game_date                               │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│            season_extremes              │
├─────────────────────────────────────────┤
│ id (PK)                                 │
│ sport (VARCHAR)                         │
│ season (VARCHAR) ─────── "2025-26"      │
│ stat_type (VARCHAR)                     │
│ season_high (DECIMAL)                   │
│ season_low (DECIMAL)                    │
│ updated_at (TIMESTAMP)                  │
└─────────────────────────────────────────┘
        │
        │ Used by
        │ Fibonacci Retracement
        ▼
```

---

## External API Dependencies

| API | Purpose | Failure Mode |
|-----|---------|--------------|
| Odds API | Raw betting lines | Fallback to cached data |
| Space Weather | Kp-Index | Use default neutral value |
| Astronomy API | Void Moon periods | Skip signal |

---

## Performance Considerations

| Operation | Target | Mitigation |
|-----------|--------|------------|
| DB queries per request | < 5 | Batch queries, caching |
| External API calls | < 3 | Caching, timeouts |
| Total response time | < 500ms | Async where possible |

---

## Future Architecture Notes

1. **Caching Layer**: Consider Redis for frequently accessed season_extremes
2. **Async Signals**: Move external API calls to async
3. **Signal Registry**: Abstract signal loading for plugin architecture
