# database.py - PostgreSQL Database Models
# For auto-grader prediction storage, weight persistence, and v10.31 pick ledger

import os
import logging
import json
import hashlib
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, List
from enum import Enum as PyEnum
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Text, Index, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager

logger = logging.getLogger("database")

# Database URL - Railway provides this when PostgreSQL service is attached
DATABASE_URL = os.getenv("DATABASE_URL", "")

# SQLAlchemy setup
Base = declarative_base()
engine = None
SessionLocal = None
DB_ENABLED = False
DB_TYPE = "none"


def init_database():
    """Initialize database connection and create tables."""
    global engine, SessionLocal, DB_ENABLED, DB_TYPE

    if DATABASE_URL:
        # Production: Postgres
        # Railway PostgreSQL URLs use postgres:// but SQLAlchemy needs postgresql://
        db_url = DATABASE_URL
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)

        engine = create_engine(db_url, pool_pre_ping=True, pool_size=5, max_overflow=10)
        DB_TYPE = "postgresql"
        logger.info("Database: Using PostgreSQL (production)")
    else:
        # Local: SQLite fallback
        engine = create_engine("sqlite:///./local.db", connect_args={"check_same_thread": False})
        DB_TYPE = "sqlite"
        logger.info("Database: Using SQLite (local fallback)")

    try:
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        # Create all tables
        Base.metadata.create_all(bind=engine)

        DB_ENABLED = True
        logger.info("Database initialized successfully")
        return True
    except Exception as e:
        logger.error("Database initialization failed: %s", e)
        DB_ENABLED = False
        return False


@contextmanager
def get_db():
    """Get database session context manager."""
    if not DB_ENABLED or SessionLocal is None:
        yield None
        return

    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db_session() -> Optional[Session]:
    """Get a direct database session (caller must close)."""
    if not DB_ENABLED or SessionLocal is None:
        return None
    return SessionLocal()


# ============================================================================
# ENUMS (v10.31)
# ============================================================================

class PickResult(PyEnum):
    """Result status for graded picks."""
    PENDING = "PENDING"
    WIN = "WIN"
    LOSS = "LOSS"
    PUSH = "PUSH"
    VOID = "VOID"
    MISSING = "MISSING"  # Results provider not available


# ============================================================================
# DATABASE MODELS (Legacy)
# ============================================================================

class PredictionRecord(Base):
    """Stores predictions for grading."""
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    prediction_id = Column(String(100), unique=True, index=True)
    sport = Column(String(20), index=True)
    player_name = Column(String(100))
    stat_type = Column(String(50), index=True)
    predicted_value = Column(Float)
    actual_value = Column(Float, nullable=True)
    line = Column(Float, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    # Context features used
    defense_adjustment = Column(Float, default=0.0)
    pace_adjustment = Column(Float, default=0.0)
    vacuum_adjustment = Column(Float, default=0.0)
    lstm_adjustment = Column(Float, default=0.0)
    officials_adjustment = Column(Float, default=0.0)

    # Outcome tracking
    hit = Column(Boolean, nullable=True)
    error = Column(Float, nullable=True)
    graded = Column(Boolean, default=False)
    graded_at = Column(DateTime, nullable=True)

    # Index for common queries
    __table_args__ = (
        Index('ix_predictions_sport_stat', 'sport', 'stat_type'),
        Index('ix_predictions_ungraded', 'graded', 'timestamp'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prediction_id": self.prediction_id,
            "sport": self.sport,
            "player_name": self.player_name,
            "stat_type": self.stat_type,
            "predicted_value": self.predicted_value,
            "actual_value": self.actual_value,
            "line": self.line,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "defense_adjustment": self.defense_adjustment,
            "pace_adjustment": self.pace_adjustment,
            "vacuum_adjustment": self.vacuum_adjustment,
            "lstm_adjustment": self.lstm_adjustment,
            "officials_adjustment": self.officials_adjustment,
            "hit": self.hit,
            "error": self.error,
            "graded": self.graded
        }


class WeightConfig(Base):
    """Stores learned weights per sport/stat type."""
    __tablename__ = "weights"

    id = Column(Integer, primary_key=True, index=True)
    sport = Column(String(20), index=True)
    stat_type = Column(String(50), index=True)

    # Weights
    defense = Column(Float, default=0.15)
    pace = Column(Float, default=0.12)
    vacuum = Column(Float, default=0.18)
    lstm = Column(Float, default=0.20)
    officials = Column(Float, default=0.08)
    park_factor = Column(Float, default=0.10)

    # Learning config
    learning_rate = Column(Float, default=0.05)
    min_weight = Column(Float, default=0.05)
    max_weight = Column(Float, default=0.35)

    # Tracking
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('ix_weights_sport_stat', 'sport', 'stat_type', unique=True),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sport": self.sport,
            "stat_type": self.stat_type,
            "defense": self.defense,
            "pace": self.pace,
            "vacuum": self.vacuum,
            "lstm": self.lstm,
            "officials": self.officials,
            "park_factor": self.park_factor,
            "learning_rate": self.learning_rate,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class BiasHistory(Base):
    """Tracks bias calculations over time for monitoring."""
    __tablename__ = "bias_history"

    id = Column(Integer, primary_key=True, index=True)
    sport = Column(String(20), index=True)
    stat_type = Column(String(50))
    calculated_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Bias values
    defense_bias = Column(Float, default=0.0)
    pace_bias = Column(Float, default=0.0)
    vacuum_bias = Column(Float, default=0.0)
    lstm_bias = Column(Float, default=0.0)
    officials_bias = Column(Float, default=0.0)

    # Metrics
    mae = Column(Float, nullable=True)
    hit_rate = Column(Float, nullable=True)
    sample_size = Column(Integer, default=0)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sport": self.sport,
            "stat_type": self.stat_type,
            "calculated_at": self.calculated_at.isoformat() if self.calculated_at else None,
            "defense_bias": self.defense_bias,
            "pace_bias": self.pace_bias,
            "vacuum_bias": self.vacuum_bias,
            "lstm_bias": self.lstm_bias,
            "officials_bias": self.officials_bias,
            "mae": self.mae,
            "hit_rate": self.hit_rate,
            "sample_size": self.sample_size
        }


class DailyEnergy(Base):
    """Stores daily esoteric energy calculations for historical tracking."""
    __tablename__ = "daily_energy"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(String(10), unique=True, index=True)  # YYYY-MM-DD

    # Energy components
    numerology_score = Column(Float, default=0.0)
    moon_phase = Column(String(50))
    moon_modifier = Column(Float, default=0.0)
    tesla_alignment = Column(Boolean, default=False)
    power_number = Column(Boolean, default=False)
    day_energy = Column(String(50))

    # Final scores
    total_energy = Column(Float, default=0.0)
    energy_data = Column(Text)  # JSON blob for full energy breakdown

    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date,
            "numerology_score": self.numerology_score,
            "moon_phase": self.moon_phase,
            "moon_modifier": self.moon_modifier,
            "tesla_alignment": self.tesla_alignment,
            "power_number": self.power_number,
            "day_energy": self.day_energy,
            "total_energy": self.total_energy,
            "energy_data": json.loads(self.energy_data) if self.energy_data else None
        }


# ============================================================================
# v10.31 DATABASE MODELS
# ============================================================================

class PickLedger(Base):
    """
    v10.31: Store every pick returned to the community.
    Uses pick_uid for deduplication (prevents duplicate inserts on repeated API calls).
    """
    __tablename__ = "pick_ledger"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Deduplication key (UNIQUE)
    pick_uid = Column(String(64), unique=True, nullable=False, index=True)

    # Core pick data
    sport = Column(String(10), nullable=False, index=True)
    event_id = Column(String(100), nullable=True, index=True)
    start_time = Column(DateTime, nullable=True)
    matchup = Column(String(200), nullable=False)
    home_team = Column(String(100), nullable=True)
    away_team = Column(String(100), nullable=True)
    market = Column(String(50), nullable=False)
    selection = Column(String(200), nullable=False)
    side = Column(String(20), nullable=True)  # OVER/UNDER/HOME/AWAY
    player_name = Column(String(100), nullable=True, index=True)
    line = Column(Float, nullable=True)
    odds = Column(Integer, nullable=False)
    implied_prob = Column(Float, nullable=True)

    # Scoring data
    tier = Column(String(20), nullable=False)
    confidence_grade = Column(String(1), nullable=False)  # A/B/C
    recommended_units = Column(Float, default=0.5)
    final_score = Column(Float, nullable=False)
    research_score = Column(Float, nullable=True)
    esoteric_score = Column(Float, nullable=True)
    alignment_pct = Column(Float, nullable=True)
    alignment_gap = Column(Float, nullable=True)
    confluence_label = Column(String(50), nullable=True)
    confluence_level = Column(String(20), nullable=True)
    confluence_boost = Column(Float, default=0.0)
    reasons = Column(Text, nullable=True)  # JSON string

    # Version tracking
    version = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Grading fields
    result = Column(Enum(PickResult), default=PickResult.PENDING, index=True)
    settled_at = Column(DateTime, nullable=True)
    profit_units = Column(Float, default=0.0)
    actual_value = Column(Float, nullable=True)  # For props: actual stat value

    # v10.32: Signal attribution fields
    fired_signals = Column(Text, nullable=True)  # JSON list[str] of normalized signal keys
    fired_signal_count = Column(Integer, default=0)
    research_components = Column(Text, nullable=True)  # JSON dict of research signal weights
    esoteric_components = Column(Text, nullable=True)  # JSON dict of esoteric signal weights

    __table_args__ = (
        Index("ix_pick_ledger_sport_date", "sport", "created_at"),
        Index("ix_pick_ledger_result_date", "result", "created_at"),
    )

    @staticmethod
    def generate_pick_uid(
        sport: str,
        event_id: Optional[str],
        market: str,
        selection: str,
        line: Optional[float],
        odds: int,
        version: str,
        pick_date: date
    ) -> str:
        """
        Generate unique pick identifier for deduplication.
        Uses event_id if available, otherwise falls back to selection-based key.
        """
        if event_id:
            key = f"{sport}|{event_id}|{market}|{selection}|{line}|{odds}|{version}|{pick_date.isoformat()}"
        else:
            key = f"{sport}|{market}|{selection}|{line}|{odds}|{version}|{pick_date.isoformat()}"
        return hashlib.sha256(key.encode()).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pick_uid": self.pick_uid,
            "sport": self.sport,
            "event_id": self.event_id,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "matchup": self.matchup,
            "home_team": self.home_team,
            "away_team": self.away_team,
            "market": self.market,
            "selection": self.selection,
            "side": self.side,
            "player_name": self.player_name,
            "line": self.line,
            "odds": self.odds,
            "tier": self.tier,
            "confidence_grade": self.confidence_grade,
            "recommended_units": self.recommended_units,
            "final_score": self.final_score,
            "result": self.result.value if self.result else "PENDING",
            "profit_units": self.profit_units,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "settled_at": self.settled_at.isoformat() if self.settled_at else None
        }


class SystemConfig(Base):
    """
    v10.31: Sport-specific config values that the engine reads live.
    Stores full sport_profile blob (weights, thresholds, policies).
    """
    __tablename__ = "system_config"

    sport = Column(String(10), primary_key=True)
    config_json = Column(Text, nullable=False)  # Current config (mutable)
    factory_config_json = Column(Text, nullable=False)  # Immutable factory baseline
    last_updated = Column(DateTime, default=datetime.utcnow)
    update_reason = Column(String(500), nullable=True)

    def get_config(self) -> Dict[str, Any]:
        """Parse config_json to dict."""
        return json.loads(self.config_json) if self.config_json else {}

    def set_config(self, config: Dict[str, Any]):
        """Set config_json from dict."""
        self.config_json = json.dumps(config)

    def get_factory_config(self) -> Dict[str, Any]:
        """Parse factory_config_json to dict."""
        return json.loads(self.factory_config_json) if self.factory_config_json else {}


class ConfigChangeLog(Base):
    """
    v10.31: Audit trail for config changes.
    Enables transparency, traceability, and rollback capability.
    """
    __tablename__ = "config_change_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sport = Column(String(10), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    old_config_json = Column(Text, nullable=True)
    new_config_json = Column(Text, nullable=False)
    reason = Column(String(500), nullable=False)
    metrics_snapshot_json = Column(Text, nullable=True)  # Performance metrics at time of change

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "sport": self.sport,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "reason": self.reason,
            "old_config": json.loads(self.old_config_json) if self.old_config_json else None,
            "new_config": json.loads(self.new_config_json) if self.new_config_json else None,
            "metrics_snapshot": json.loads(self.metrics_snapshot_json) if self.metrics_snapshot_json else None
        }


# ============================================================================
# v10.32 DATABASE MODELS - Signal Attribution & Policy Learning
# ============================================================================

class SignalLedger(Base):
    """
    v10.32: Granular signal attribution - one row per pick per signal fired.
    Enables ROI analysis per signal to drive learning.
    """
    __tablename__ = "signal_ledger"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pick_uid = Column(String(64), nullable=False, index=True)  # FK to PickLedger.pick_uid
    sport = Column(String(10), nullable=False, index=True)

    # Signal identification
    signal_key = Column(String(100), nullable=False, index=True)  # e.g., "PILLAR_SHARP_SPLIT"
    signal_category = Column(String(50), nullable=True)  # "RESEARCH" | "ESOTERIC" | "CONFLUENCE"
    signal_value = Column(Float, default=0.0)  # Boost value applied

    # Tracking
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("ix_signal_ledger_pick", "pick_uid"),
        Index("ix_signal_ledger_signal_sport", "signal_key", "sport"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pick_uid": self.pick_uid,
            "sport": self.sport,
            "signal_key": self.signal_key,
            "signal_category": self.signal_category,
            "signal_value": self.signal_value,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }


class SignalPolicyConfig(Base):
    """
    v10.32: Learning multipliers per sport per signal.
    Multiplier range: [0.85, 1.15] - never disables a signal.
    """
    __tablename__ = "signal_policy_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sport = Column(String(10), nullable=False)
    signal_key = Column(String(100), nullable=False)

    # Policy values
    multiplier = Column(Float, default=1.0)  # Current multiplier
    min_mult = Column(Float, default=0.85)  # Floor
    max_mult = Column(Float, default=1.15)  # Ceiling

    # Tracking
    last_updated = Column(DateTime, default=datetime.utcnow)
    update_reason = Column(String(500), nullable=True)

    __table_args__ = (
        Index("ix_signal_policy_sport_key", "sport", "signal_key", unique=True),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sport": self.sport,
            "signal_key": self.signal_key,
            "multiplier": self.multiplier,
            "min_mult": self.min_mult,
            "max_mult": self.max_mult,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "update_reason": self.update_reason
        }


class TuningAuditLog(Base):
    """
    v10.32: Immutable audit trail for policy changes.
    Enables transparency and rollback analysis.
    """
    __tablename__ = "tuning_audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sport = Column(String(10), nullable=False, index=True)
    signal_key = Column(String(100), nullable=False, index=True)

    # Change details
    old_mult = Column(Float, nullable=False)
    new_mult = Column(Float, nullable=False)
    reason = Column(String(500), nullable=False)
    window_days = Column(Integer, default=7)

    # Metrics at time of change
    roi_at_change = Column(Float, nullable=True)
    win_rate_at_change = Column(Float, nullable=True)
    sample_size = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sport": self.sport,
            "signal_key": self.signal_key,
            "old_mult": self.old_mult,
            "new_mult": self.new_mult,
            "reason": self.reason,
            "window_days": self.window_days,
            "roi_at_change": self.roi_at_change,
            "win_rate_at_change": self.win_rate_at_change,
            "sample_size": self.sample_size,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


# ============================================================================
# v10.31 FACTORY SPORT PROFILES
# ============================================================================

# v10.32: Default micro-weights for all signals (1.0 = no change)
DEFAULT_MICRO_WEIGHTS = {
    "PILLAR_SHARP_SPLIT": 1.00,
    "PILLAR_RLM": 1.00,
    "PILLAR_HOSPITAL_FADE": 1.00,
    "PILLAR_SITUATIONAL": 1.00,
    "PILLAR_EXPERT_CONSENSUS": 1.00,
    "PILLAR_HOOK_DISCIPLINE": 1.00,
    "PILLAR_PROP_CORRELATION": 1.00,
    "SIGNAL_PUBLIC_FADE": 1.00,
    "SIGNAL_LINE_VALUE": 1.00,
    "ESOTERIC_GEMATRIA": 1.00,
    "ESOTERIC_JARVIS_TRIGGER": 1.00,
    "ESOTERIC_ASTRO": 1.00,
    "ESOTERIC_FIBONACCI": 1.00,
    "CONFLUENCE_BONUS": 1.00,
    "CORRELATION_ALIGNED": 1.00,
}

FACTORY_SPORT_PROFILES = {
    "NBA": {
        "weights": {"research": 0.67, "esoteric": 0.33},
        "tiers": {
            "GOLD_STAR": 7.5,
            "EDGE_LEAN": 6.5,
            "MONITOR": 5.5,
            "PASS": 0.0
        },
        "limits": {"props": 10, "game_picks": 10},
        "conflict_policy": {"exclude_conflicts": True},
        "market_biases": {},
        "micro_weights": DEFAULT_MICRO_WEIGHTS.copy()
    },
    "NFL": {
        "weights": {"research": 0.67, "esoteric": 0.33},
        "tiers": {
            "GOLD_STAR": 7.5,
            "EDGE_LEAN": 6.5,
            "MONITOR": 5.5,
            "PASS": 0.0
        },
        "limits": {"props": 10, "game_picks": 10},
        "conflict_policy": {"exclude_conflicts": True},
        "market_biases": {},
        "micro_weights": DEFAULT_MICRO_WEIGHTS.copy()
    },
    "MLB": {
        "weights": {"research": 0.67, "esoteric": 0.33},
        "tiers": {
            "GOLD_STAR": 7.5,
            "EDGE_LEAN": 6.5,
            "MONITOR": 5.5,
            "PASS": 0.0
        },
        "limits": {"props": 10, "game_picks": 10},
        "conflict_policy": {"exclude_conflicts": True},
        "market_biases": {},
        "micro_weights": DEFAULT_MICRO_WEIGHTS.copy()
    },
    "NHL": {
        "weights": {"research": 0.67, "esoteric": 0.33},
        "tiers": {
            "GOLD_STAR": 7.5,
            "EDGE_LEAN": 6.5,
            "MONITOR": 5.5,
            "PASS": 0.0
        },
        "limits": {"props": 10, "game_picks": 10},
        "conflict_policy": {"exclude_conflicts": True},
        "market_biases": {"ml_dog_boost": 0.5},
        "micro_weights": DEFAULT_MICRO_WEIGHTS.copy()
    },
    "NCAAB": {
        "weights": {"research": 0.67, "esoteric": 0.33},
        "tiers": {
            "GOLD_STAR": 7.5,
            "EDGE_LEAN": 6.5,
            "MONITOR": 5.5,
            "PASS": 0.0
        },
        "limits": {"props": 10, "game_picks": 10},
        "conflict_policy": {"exclude_conflicts": True},
        "market_biases": {},
        "micro_weights": DEFAULT_MICRO_WEIGHTS.copy()
    }
}


# ============================================================================
# DATABASE HELPER FUNCTIONS (Legacy)
# ============================================================================

def save_prediction(db: Session, prediction_data: Dict[str, Any]) -> Optional[PredictionRecord]:
    """Save a prediction to the database."""
    if not db:
        return None

    try:
        record = PredictionRecord(**prediction_data)
        db.add(record)
        db.flush()
        return record
    except Exception as e:
        logger.error("Failed to save prediction: %s", e)
        return None


def get_ungraded_predictions(db: Session, sport: str = None, limit: int = 100):
    """Get predictions that haven't been graded yet."""
    if not db:
        return []

    query = db.query(PredictionRecord).filter(PredictionRecord.graded == False)
    if sport:
        query = query.filter(PredictionRecord.sport == sport.upper())
    return query.order_by(PredictionRecord.timestamp.desc()).limit(limit).all()


def grade_prediction(db: Session, prediction_id: str, actual_value: float):
    """Grade a prediction with actual outcome."""
    if not db:
        return None

    record = db.query(PredictionRecord).filter(
        PredictionRecord.prediction_id == prediction_id
    ).first()

    if record:
        record.actual_value = actual_value
        record.error = record.predicted_value - actual_value
        if record.line is not None:
            record.hit = (record.predicted_value > record.line) == (actual_value > record.line)
        record.graded = True
        record.graded_at = datetime.utcnow()
        db.flush()

    return record


def get_weights(db: Session, sport: str, stat_type: str) -> Optional[WeightConfig]:
    """Get weights for a sport/stat combination."""
    if not db:
        return None

    return db.query(WeightConfig).filter(
        WeightConfig.sport == sport.upper(),
        WeightConfig.stat_type == stat_type
    ).first()


def save_weights(db: Session, sport: str, stat_type: str, weights: Dict[str, float]):
    """Save or update weights."""
    if not db:
        return None

    existing = get_weights(db, sport, stat_type)
    if existing:
        for key, value in weights.items():
            if hasattr(existing, key):
                setattr(existing, key, value)
        db.flush()
        return existing
    else:
        record = WeightConfig(sport=sport.upper(), stat_type=stat_type, **weights)
        db.add(record)
        db.flush()
        return record


def get_database_status() -> Dict[str, Any]:
    """Get database connection status."""
    return {
        "enabled": DB_ENABLED,
        "configured": bool(DATABASE_URL),
        "url_set": "DATABASE_URL" in os.environ,
        "db_type": DB_TYPE
    }


# ============================================================================
# v10.31 DATABASE HELPER FUNCTIONS
# ============================================================================

def load_sport_config(sport: str, db: Session = None) -> Dict[str, Any]:
    """
    Load config for a sport. If not found, insert factory defaults.
    Returns the config dict.
    """
    if db is None:
        with get_db() as db:
            if db is None:
                # Database not available, return factory defaults
                sport_upper = sport.upper()
                return FACTORY_SPORT_PROFILES.get(sport_upper, FACTORY_SPORT_PROFILES["NBA"])
            return _load_sport_config_impl(sport, db)
    else:
        return _load_sport_config_impl(sport, db)


def _load_sport_config_impl(sport: str, db: Session) -> Dict[str, Any]:
    """Internal implementation of load_sport_config."""
    sport_upper = sport.upper()
    config = db.query(SystemConfig).filter(SystemConfig.sport == sport_upper).first()

    if config is None:
        # Insert factory defaults
        factory = FACTORY_SPORT_PROFILES.get(sport_upper, FACTORY_SPORT_PROFILES["NBA"])
        config = SystemConfig(
            sport=sport_upper,
            config_json=json.dumps(factory),
            factory_config_json=json.dumps(factory),
            last_updated=datetime.utcnow(),
            update_reason="Factory defaults initialized"
        )
        db.add(config)
        db.flush()
        logger.info(f"Initialized factory config for {sport_upper}")
        return factory

    return config.get_config()


def save_sport_config(
    sport: str,
    new_config: Dict[str, Any],
    reason: str,
    metrics_snapshot: Optional[Dict[str, Any]] = None,
    db: Session = None
) -> bool:
    """
    Save updated config for a sport and log the change.
    Returns True on success.
    """
    if db is None:
        with get_db() as db:
            if db is None:
                logger.warning("Cannot save config: database not available")
                return False
            return _save_sport_config_impl(sport, new_config, reason, metrics_snapshot, db)
    else:
        return _save_sport_config_impl(sport, new_config, reason, metrics_snapshot, db)


def _save_sport_config_impl(
    sport: str,
    new_config: Dict[str, Any],
    reason: str,
    metrics_snapshot: Optional[Dict[str, Any]],
    db: Session
) -> bool:
    """Internal implementation of save_sport_config."""
    try:
        sport_upper = sport.upper()
        config = db.query(SystemConfig).filter(SystemConfig.sport == sport_upper).first()

        if config is None:
            logger.error(f"Cannot save config for {sport_upper}: not found")
            return False

        old_config_json = config.config_json

        # Update config
        config.config_json = json.dumps(new_config)
        config.last_updated = datetime.utcnow()
        config.update_reason = reason

        # Log the change
        change_log = ConfigChangeLog(
            sport=sport_upper,
            old_config_json=old_config_json,
            new_config_json=config.config_json,
            reason=reason,
            metrics_snapshot_json=json.dumps(metrics_snapshot) if metrics_snapshot else None
        )
        db.add(change_log)
        db.flush()

        logger.info(f"Config updated for {sport_upper}: {reason}")
        return True
    except Exception as e:
        logger.exception(f"Failed to save config for {sport}: {e}")
        return False


def upsert_pick(pick_data: Dict[str, Any], db: Session = None) -> bool:
    """
    Insert a pick into the ledger if it doesn't exist (dedupe by pick_uid).
    Returns True if inserted, False if already exists or error.
    """
    if db is None:
        with get_db() as db:
            if db is None:
                return False
            return _upsert_pick_impl(pick_data, db)
    else:
        return _upsert_pick_impl(pick_data, db)


def _upsert_pick_impl(pick_data: Dict[str, Any], db: Session) -> bool:
    """Internal implementation of upsert_pick."""
    try:
        # Generate pick_uid
        pick_uid = PickLedger.generate_pick_uid(
            sport=pick_data.get("sport", "NBA"),
            event_id=pick_data.get("event_id"),
            market=pick_data.get("market", ""),
            selection=pick_data.get("selection", ""),
            line=pick_data.get("line"),
            odds=pick_data.get("odds", -110),
            version=pick_data.get("version", "production_v10.31"),
            pick_date=datetime.utcnow().date()
        )

        # Check if exists
        existing = db.query(PickLedger).filter(PickLedger.pick_uid == pick_uid).first()
        if existing:
            return False  # Already exists

        # Parse start_time if string
        start_time = pick_data.get("start_time") or pick_data.get("game_time")
        if isinstance(start_time, str):
            try:
                start_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                start_time = None

        # Get scoring breakdown
        scoring_breakdown = pick_data.get("scoring_breakdown", {})

        # Create new pick
        pick = PickLedger(
            pick_uid=pick_uid,
            sport=pick_data.get("sport", "NBA").upper(),
            event_id=pick_data.get("event_id"),
            start_time=start_time,
            matchup=pick_data.get("matchup", pick_data.get("game", "")),
            home_team=pick_data.get("home_team"),
            away_team=pick_data.get("away_team"),
            market=pick_data.get("market", ""),
            selection=pick_data.get("selection", ""),
            side=pick_data.get("side") or pick_data.get("over_under"),
            player_name=pick_data.get("player_name"),
            line=pick_data.get("line"),
            odds=pick_data.get("odds", -110),
            implied_prob=pick_data.get("implied_prob"),
            tier=pick_data.get("tier", "MONITOR"),
            confidence_grade=pick_data.get("confidence_grade", "C"),
            recommended_units=pick_data.get("recommended_units", 0.5),
            final_score=pick_data.get("final_score", pick_data.get("smash_score", 5.0)),
            research_score=scoring_breakdown.get("research_score"),
            esoteric_score=scoring_breakdown.get("esoteric_score"),
            alignment_pct=pick_data.get("alignment_pct"),
            alignment_gap=pick_data.get("alignment_gap"),
            confluence_label=pick_data.get("confluence_label"),
            confluence_level=pick_data.get("confluence_level"),
            confluence_boost=pick_data.get("confluence_boost", 0.0),
            reasons=json.dumps(pick_data.get("reasons", [])),
            version=pick_data.get("version", pick_data.get("source", "production_v10.32")),
            # v10.32 signal attribution
            fired_signals=json.dumps(pick_data.get("fired_signals", [])),
            fired_signal_count=pick_data.get("fired_signal_count", 0),
            research_components=json.dumps(pick_data.get("research_components", {})),
            esoteric_components=json.dumps(pick_data.get("esoteric_components", {})),
        )

        db.add(pick)
        db.flush()
        return True
    except Exception as e:
        logger.exception(f"Failed to upsert pick: {e}")
        return False


def get_pending_picks_for_date(
    target_date: date,
    sport: Optional[str] = None,
    db: Session = None
) -> List[PickLedger]:
    """Get all PENDING picks for a specific date."""
    if db is None:
        with get_db() as db:
            if db is None:
                return []
            return _get_pending_picks_impl(target_date, sport, db)
    else:
        return _get_pending_picks_impl(target_date, sport, db)


def _get_pending_picks_impl(target_date: date, sport: Optional[str], db: Session) -> List[PickLedger]:
    """Internal implementation."""
    query = db.query(PickLedger).filter(
        PickLedger.result == PickResult.PENDING,
        PickLedger.created_at >= datetime.combine(target_date, datetime.min.time()),
        PickLedger.created_at < datetime.combine(target_date + timedelta(days=1), datetime.min.time())
    )

    if sport:
        query = query.filter(PickLedger.sport == sport.upper())

    return query.all()


def get_settled_picks(
    sport: str,
    days_back: int = 7,
    db: Session = None
) -> List[PickLedger]:
    """Get settled picks for a sport within the rolling window."""
    if db is None:
        with get_db() as db:
            if db is None:
                return []
            return _get_settled_picks_impl(sport, days_back, db)
    else:
        return _get_settled_picks_impl(sport, days_back, db)


def _get_settled_picks_impl(sport: str, days_back: int, db: Session) -> List[PickLedger]:
    """Internal implementation."""
    cutoff = datetime.utcnow() - timedelta(days=days_back)

    return db.query(PickLedger).filter(
        PickLedger.sport == sport.upper(),
        PickLedger.result.in_([PickResult.WIN, PickResult.LOSS, PickResult.PUSH]),
        PickLedger.settled_at >= cutoff
    ).all()


def get_picks_for_date(
    target_date: date,
    sport: Optional[str] = None,
    db: Session = None
) -> List[PickLedger]:
    """Get all picks for a specific date (any status)."""
    if db is None:
        with get_db() as db:
            if db is None:
                return []
            return _get_picks_for_date_impl(target_date, sport, db)
    else:
        return _get_picks_for_date_impl(target_date, sport, db)


def _get_picks_for_date_impl(target_date: date, sport: Optional[str], db: Session) -> List[PickLedger]:
    """Internal implementation."""
    query = db.query(PickLedger).filter(
        PickLedger.created_at >= datetime.combine(target_date, datetime.min.time()),
        PickLedger.created_at < datetime.combine(target_date + timedelta(days=1), datetime.min.time())
    )

    if sport:
        query = query.filter(PickLedger.sport == sport.upper())

    return query.all()


def get_config_changes(
    sport: str,
    days_back: int = 7,
    db: Session = None
) -> List[ConfigChangeLog]:
    """Get recent config changes for a sport."""
    if db is None:
        with get_db() as db:
            if db is None:
                return []
            return _get_config_changes_impl(sport, days_back, db)
    else:
        return _get_config_changes_impl(sport, days_back, db)


def _get_config_changes_impl(sport: str, days_back: int, db: Session) -> List[ConfigChangeLog]:
    """Internal implementation."""
    cutoff = datetime.utcnow() - timedelta(days=days_back)

    return db.query(ConfigChangeLog).filter(
        ConfigChangeLog.sport == sport.upper(),
        ConfigChangeLog.timestamp >= cutoff
    ).order_by(ConfigChangeLog.timestamp.desc()).all()


def update_pick_result(
    pick_uid: str,
    result: PickResult,
    profit_units: float,
    actual_value: Optional[float] = None,
    db: Session = None
) -> bool:
    """Update a pick's result after grading."""
    if db is None:
        with get_db() as db:
            if db is None:
                return False
            return _update_pick_result_impl(pick_uid, result, profit_units, actual_value, db)
    else:
        return _update_pick_result_impl(pick_uid, result, profit_units, actual_value, db)


def _update_pick_result_impl(
    pick_uid: str,
    result: PickResult,
    profit_units: float,
    actual_value: Optional[float],
    db: Session
) -> bool:
    """Internal implementation."""
    try:
        pick = db.query(PickLedger).filter(PickLedger.pick_uid == pick_uid).first()
        if pick is None:
            return False

        pick.result = result
        pick.profit_units = profit_units
        pick.settled_at = datetime.utcnow()
        if actual_value is not None:
            pick.actual_value = actual_value

        db.flush()
        return True
    except Exception as e:
        logger.exception(f"Failed to update pick result: {e}")
        return False


# ============================================================================
# v10.32 MICRO-WEIGHTS HELPERS
# ============================================================================

def get_micro_weights(sport: str, db: Session = None) -> Dict[str, float]:
    """
    Get micro-weights for a sport.
    Returns DEFAULT_MICRO_WEIGHTS if not found.
    """
    config = load_sport_config(sport, db)
    return config.get("micro_weights", DEFAULT_MICRO_WEIGHTS.copy())


def get_graded_picks_for_window(
    sport: str,
    window_days: int = 7,
    db: Session = None
) -> List[PickLedger]:
    """
    Get all graded (WIN/LOSS/PUSH) picks for attribution analysis.
    """
    if db is None:
        with get_db() as db:
            if db is None:
                return []
            return _get_graded_picks_impl(sport, window_days, db)
    else:
        return _get_graded_picks_impl(sport, window_days, db)


def _get_graded_picks_impl(sport: str, window_days: int, db: Session) -> List[PickLedger]:
    """Internal implementation."""
    cutoff = datetime.utcnow() - timedelta(days=window_days)

    return db.query(PickLedger).filter(
        PickLedger.sport == sport.upper(),
        PickLedger.result.in_([PickResult.WIN, PickResult.LOSS, PickResult.PUSH]),
        PickLedger.created_at >= cutoff
    ).all()


# ============================================================================
# v10.32 SIGNAL LEDGER & POLICY HELPERS
# ============================================================================

def save_signal_ledger(
    pick_uid: str,
    sport: str,
    signals: List[Dict[str, Any]],
    db: Session = None
) -> int:
    """
    Save signal entries to SignalLedger for a pick.
    Returns count of signals saved.
    """
    if db is None:
        with get_db() as db:
            if db is None:
                return 0
            return _save_signal_ledger_impl(pick_uid, sport, signals, db)
    else:
        return _save_signal_ledger_impl(pick_uid, sport, signals, db)


def _save_signal_ledger_impl(
    pick_uid: str,
    sport: str,
    signals: List[Dict[str, Any]],
    db: Session
) -> int:
    """Internal implementation."""
    count = 0
    try:
        for sig in signals:
            entry = SignalLedger(
                pick_uid=pick_uid,
                sport=sport.upper(),
                signal_key=sig.get("signal_key", "UNKNOWN"),
                signal_category=sig.get("category"),
                signal_value=sig.get("value", 0.0)
            )
            db.add(entry)
            count += 1
        db.flush()
    except Exception as e:
        logger.exception(f"Failed to save signal ledger: {e}")
    return count


def get_signal_policy(sport: str, db: Session = None) -> Dict[str, float]:
    """
    Get all signal policy multipliers for a sport.
    Returns dict of signal_key -> multiplier.
    """
    if db is None:
        with get_db() as db:
            if db is None:
                return DEFAULT_MICRO_WEIGHTS.copy()
            return _get_signal_policy_impl(sport, db)
    else:
        return _get_signal_policy_impl(sport, db)


def _get_signal_policy_impl(sport: str, db: Session) -> Dict[str, float]:
    """Internal implementation."""
    try:
        policies = db.query(SignalPolicyConfig).filter(
            SignalPolicyConfig.sport == sport.upper()
        ).all()

        result = DEFAULT_MICRO_WEIGHTS.copy()
        for p in policies:
            result[p.signal_key] = p.multiplier
        return result
    except Exception as e:
        logger.warning(f"Failed to get signal policy: {e}")
        return DEFAULT_MICRO_WEIGHTS.copy()


def upsert_signal_policy(
    sport: str,
    signal_key: str,
    new_mult: float,
    reason: str,
    roi: float = None,
    win_rate: float = None,
    sample_size: int = None,
    window_days: int = 7,
    db: Session = None
) -> bool:
    """
    Update or insert signal policy, log to audit trail.
    Returns True on success.
    """
    if db is None:
        with get_db() as db:
            if db is None:
                return False
            return _upsert_signal_policy_impl(
                sport, signal_key, new_mult, reason,
                roi, win_rate, sample_size, window_days, db
            )
    else:
        return _upsert_signal_policy_impl(
            sport, signal_key, new_mult, reason,
            roi, win_rate, sample_size, window_days, db
        )


def _upsert_signal_policy_impl(
    sport: str,
    signal_key: str,
    new_mult: float,
    reason: str,
    roi: float,
    win_rate: float,
    sample_size: int,
    window_days: int,
    db: Session
) -> bool:
    """Internal implementation."""
    try:
        sport = sport.upper()

        # Find or create policy
        policy = db.query(SignalPolicyConfig).filter(
            SignalPolicyConfig.sport == sport,
            SignalPolicyConfig.signal_key == signal_key
        ).first()

        old_mult = 1.0
        if policy:
            old_mult = policy.multiplier
            policy.multiplier = new_mult
            policy.last_updated = datetime.utcnow()
            policy.update_reason = reason
        else:
            policy = SignalPolicyConfig(
                sport=sport,
                signal_key=signal_key,
                multiplier=new_mult,
                update_reason=reason
            )
            db.add(policy)

        # Log to audit trail
        audit = TuningAuditLog(
            sport=sport,
            signal_key=signal_key,
            old_mult=old_mult,
            new_mult=new_mult,
            reason=reason,
            window_days=window_days,
            roi_at_change=roi,
            win_rate_at_change=win_rate,
            sample_size=sample_size
        )
        db.add(audit)
        db.flush()
        return True
    except Exception as e:
        logger.exception(f"Failed to upsert signal policy: {e}")
        return False


def get_signal_performance(
    sport: str,
    window_days: int = 7,
    db: Session = None
) -> Dict[str, Dict[str, Any]]:
    """
    Compute ROI and win rate per signal for a sport.
    Returns dict of signal_key -> {count, win_rate, roi, total_units, profit_units}
    """
    if db is None:
        with get_db() as db:
            if db is None:
                return {}
            return _get_signal_performance_impl(sport, window_days, db)
    else:
        return _get_signal_performance_impl(sport, window_days, db)


def _get_signal_performance_impl(
    sport: str,
    window_days: int,
    db: Session
) -> Dict[str, Dict[str, Any]]:
    """Internal implementation."""
    try:
        cutoff = datetime.utcnow() - timedelta(days=window_days)
        sport = sport.upper()

        # Get all settled picks in window
        picks = db.query(PickLedger).filter(
            PickLedger.sport == sport,
            PickLedger.result.in_([PickResult.WIN, PickResult.LOSS, PickResult.PUSH]),
            PickLedger.created_at >= cutoff
        ).all()

        # Get signal entries for these picks
        pick_uids = [p.pick_uid for p in picks]
        if not pick_uids:
            return {}

        signals = db.query(SignalLedger).filter(
            SignalLedger.pick_uid.in_(pick_uids)
        ).all()

        # Map pick_uid to pick result/units
        pick_map = {
            p.pick_uid: {
                "result": p.result,
                "profit_units": p.profit_units or 0,
                "recommended_units": p.recommended_units or 0.5
            }
            for p in picks
        }

        # Aggregate per signal
        signal_stats = {}
        for sig in signals:
            key = sig.signal_key
            if key not in signal_stats:
                signal_stats[key] = {
                    "count": 0,
                    "wins": 0,
                    "losses": 0,
                    "pushes": 0,
                    "total_units": 0.0,
                    "profit_units": 0.0
                }

            pick_data = pick_map.get(sig.pick_uid)
            if pick_data:
                signal_stats[key]["count"] += 1
                signal_stats[key]["total_units"] += pick_data["recommended_units"]
                signal_stats[key]["profit_units"] += pick_data["profit_units"]

                if pick_data["result"] == PickResult.WIN:
                    signal_stats[key]["wins"] += 1
                elif pick_data["result"] == PickResult.LOSS:
                    signal_stats[key]["losses"] += 1
                else:
                    signal_stats[key]["pushes"] += 1

        # Calculate rates
        for key, stats in signal_stats.items():
            total = stats["wins"] + stats["losses"]
            stats["win_rate"] = (stats["wins"] / total * 100) if total > 0 else 0
            stats["roi"] = (stats["profit_units"] / stats["total_units"] * 100) if stats["total_units"] > 0 else 0

        return signal_stats
    except Exception as e:
        logger.exception(f"Failed to get signal performance: {e}")
        return {}


def get_tuning_history(
    sport: str,
    days_back: int = 30,
    db: Session = None
) -> List[Dict[str, Any]]:
    """Get tuning audit history for a sport."""
    if db is None:
        with get_db() as db:
            if db is None:
                return []
            return _get_tuning_history_impl(sport, days_back, db)
    else:
        return _get_tuning_history_impl(sport, days_back, db)


def _get_tuning_history_impl(sport: str, days_back: int, db: Session) -> List[Dict[str, Any]]:
    """Internal implementation."""
    try:
        cutoff = datetime.utcnow() - timedelta(days=days_back)

        audits = db.query(TuningAuditLog).filter(
            TuningAuditLog.sport == sport.upper(),
            TuningAuditLog.created_at >= cutoff
        ).order_by(TuningAuditLog.created_at.desc()).all()

        return [a.to_dict() for a in audits]
    except Exception as e:
        logger.exception(f"Failed to get tuning history: {e}")
        return []


# ============================================================================
# v10.32+ DATABASE HEALTH CHECK
# ============================================================================

def get_db_health() -> Dict[str, Any]:
    """
    Comprehensive database health check for /live/db/status endpoint.
    Returns connection status, table counts, and any errors.
    """
    health = {
        "db_url_present": bool(DATABASE_URL),
        "db_connect_ok": False,
        "db_type": DB_TYPE,
        "db_enabled": DB_ENABLED,
        "tables_found": [],
        "missing_tables": [],
        "table_counts": {},
        "last_error": None
    }

    expected_tables = [
        "predictions", "weights", "bias_history", "daily_energy",
        "pick_ledger", "system_config", "config_change_log",
        "signal_ledger", "signal_policy_config", "tuning_audit_log"
    ]

    if not DB_ENABLED or engine is None:
        health["last_error"] = "Database not initialized"
        health["missing_tables"] = expected_tables
        return health

    try:
        with get_db() as db:
            if db is None:
                health["last_error"] = "Could not acquire database session"
                return health

            # Test connection
            db.execute("SELECT 1")
            health["db_connect_ok"] = True

            # Check tables exist and get counts
            for table in expected_tables:
                try:
                    result = db.execute(f"SELECT COUNT(*) FROM {table}")
                    count = result.scalar()
                    health["tables_found"].append(table)
                    health["table_counts"][table] = count
                except Exception:
                    health["missing_tables"].append(table)

    except Exception as e:
        health["last_error"] = str(e)

    return health


def get_signal_ledger_stats(sport: str, window_days: int = 7, db: Session = None) -> Dict[str, Any]:
    """
    Get aggregated stats from SignalLedger for signal-report.
    Returns pick counts, win/loss/push breakdown, and per-signal stats.
    """
    if db is None:
        with get_db() as db:
            if db is None:
                return _empty_signal_stats()
            return _get_signal_ledger_stats_impl(sport, window_days, db)
    else:
        return _get_signal_ledger_stats_impl(sport, window_days, db)


def _empty_signal_stats() -> Dict[str, Any]:
    """Return empty stats structure when DB not available."""
    return {
        "totals": {
            "picks_logged": 0,
            "wins": 0,
            "losses": 0,
            "pushes": 0,
            "pending": 0,
            "win_rate": 0.0,
            "roi": 0.0
        },
        "signal_breakdown": [],
        "top_positive_signals": [],
        "top_negative_signals": [],
        "synergy_pairs": []
    }


def _get_signal_ledger_stats_impl(sport: str, window_days: int, db: Session) -> Dict[str, Any]:
    """Internal implementation of signal ledger stats."""
    try:
        cutoff = datetime.utcnow() - timedelta(days=window_days)
        sport = sport.upper()

        # Get all picks in window
        query = db.query(PickLedger).filter(
            PickLedger.created_at >= cutoff
        )
        if sport != "ALL":
            query = query.filter(PickLedger.sport == sport)

        picks = query.all()

        if not picks:
            return _empty_signal_stats()

        # Calculate totals
        wins = sum(1 for p in picks if p.result == PickResult.WIN)
        losses = sum(1 for p in picks if p.result == PickResult.LOSS)
        pushes = sum(1 for p in picks if p.result == PickResult.PUSH)
        pending = sum(1 for p in picks if p.result == PickResult.PENDING)
        total_graded = wins + losses

        total_units = sum(p.recommended_units or 0.5 for p in picks if p.result in [PickResult.WIN, PickResult.LOSS])
        profit_units = sum(p.profit_units or 0 for p in picks if p.result in [PickResult.WIN, PickResult.LOSS])

        totals = {
            "picks_logged": len(picks),
            "wins": wins,
            "losses": losses,
            "pushes": pushes,
            "pending": pending,
            "win_rate": round((wins / total_graded * 100) if total_graded > 0 else 0, 2),
            "roi": round((profit_units / total_units * 100) if total_units > 0 else 0, 2)
        }

        # Get signal breakdown from SignalLedger
        graded_pick_uids = [p.pick_uid for p in picks if p.result in [PickResult.WIN, PickResult.LOSS]]

        signal_breakdown = []
        top_positive = []
        top_negative = []

        if graded_pick_uids:
            signals = db.query(SignalLedger).filter(
                SignalLedger.pick_uid.in_(graded_pick_uids)
            ).all()

            # Map pick_uid to result
            pick_map = {
                p.pick_uid: {
                    "result": p.result,
                    "profit_units": p.profit_units or 0,
                    "units": p.recommended_units or 0.5
                }
                for p in picks if p.result in [PickResult.WIN, PickResult.LOSS]
            }

            # Aggregate by signal
            signal_stats = {}
            for sig in signals:
                key = sig.signal_key
                if key not in signal_stats:
                    signal_stats[key] = {
                        "signal_key": key,
                        "fired_count": 0,
                        "wins": 0,
                        "losses": 0,
                        "total_units": 0.0,
                        "profit_units": 0.0,
                        "avg_value": []
                    }

                pick_data = pick_map.get(sig.pick_uid)
                if pick_data:
                    signal_stats[key]["fired_count"] += 1
                    signal_stats[key]["total_units"] += pick_data["units"]
                    signal_stats[key]["profit_units"] += pick_data["profit_units"]
                    signal_stats[key]["avg_value"].append(sig.signal_value or 0)

                    if pick_data["result"] == PickResult.WIN:
                        signal_stats[key]["wins"] += 1
                    else:
                        signal_stats[key]["losses"] += 1

            # Calculate rates and sort
            for key, stats in signal_stats.items():
                total = stats["wins"] + stats["losses"]
                stats["win_rate"] = round((stats["wins"] / total * 100) if total > 0 else 0, 2)
                stats["roi"] = round((stats["profit_units"] / stats["total_units"] * 100) if stats["total_units"] > 0 else 0, 2)
                stats["avg_score_delta"] = round(sum(stats["avg_value"]) / len(stats["avg_value"]), 3) if stats["avg_value"] else 0
                del stats["avg_value"]  # Remove temp list

            signal_breakdown = sorted(signal_stats.values(), key=lambda x: x["fired_count"], reverse=True)

            # Top positive (best ROI with min 3 samples)
            top_positive = sorted(
                [s for s in signal_breakdown if s["fired_count"] >= 3],
                key=lambda x: x["roi"],
                reverse=True
            )[:5]

            # Top negative (worst ROI with min 3 samples)
            top_negative = sorted(
                [s for s in signal_breakdown if s["fired_count"] >= 3],
                key=lambda x: x["roi"]
            )[:5]

        return {
            "totals": totals,
            "signal_breakdown": signal_breakdown,
            "top_positive_signals": top_positive,
            "top_negative_signals": top_negative,
            "synergy_pairs": []  # MVP: implement later
        }

    except Exception as e:
        logger.exception(f"Failed to get signal ledger stats: {e}")
        return _empty_signal_stats()


# ============================================================================
# v10.32+ SEASON CALENDAR HELPER
# ============================================================================

# Approximate season dates (month, day)
SEASON_CALENDAR = {
    "NFL": {
        "start": (9, 5),    # Early September
        "end": (2, 15)      # Mid February (Super Bowl)
    },
    "NBA": {
        "start": (10, 15),  # Mid October
        "end": (6, 20)      # Mid June (Finals)
    },
    "MLB": {
        "start": (3, 28),   # Late March
        "end": (11, 5)      # Early November (World Series)
    },
    "NHL": {
        "start": (10, 5),   # Early October
        "end": (6, 25)      # Late June (Stanley Cup)
    },
    "NCAAB": {
        "start": (11, 5),   # Early November
        "end": (4, 8)       # Early April (Championship)
    }
}


def is_sport_in_season(sport: str, check_date: date = None) -> bool:
    """
    Check if a sport is currently in season.
    NFL wraps around year boundary (Sep -> Feb).
    """
    if check_date is None:
        check_date = date.today()

    sport = sport.upper()
    if sport not in SEASON_CALENDAR:
        return True  # Unknown sport, assume active

    cal = SEASON_CALENDAR[sport]
    start_month, start_day = cal["start"]
    end_month, end_day = cal["end"]

    # Handle NFL (wraps around new year: Sep-Feb)
    if sport == "NFL":
        # In season if: Sep-Dec OR Jan-Feb
        if check_date.month >= start_month:  # Sep onwards
            return True
        if check_date.month <= end_month:  # Jan-Feb
            if check_date.month < end_month or check_date.day <= end_day:
                return True
        return False

    # Regular sports (start < end within same year)
    start_date = date(check_date.year, start_month, start_day)
    end_date = date(check_date.year, end_month, end_day)

    return start_date <= check_date <= end_date


def get_active_sports(check_date: date = None) -> List[str]:
    """
    Get list of sports currently in season.
    """
    all_sports = ["NFL", "NBA", "MLB", "NHL", "NCAAB"]
    return [s for s in all_sports if is_sport_in_season(s, check_date)]


def get_season_status() -> Dict[str, Any]:
    """
    Get comprehensive season status for all sports.
    """
    today = date.today()
    status = {
        "check_date": today.isoformat(),
        "active_sports": get_active_sports(today),
        "sports": {}
    }

    for sport in ["NFL", "NBA", "MLB", "NHL", "NCAAB"]:
        in_season = is_sport_in_season(sport, today)
        cal = SEASON_CALENDAR[sport]
        status["sports"][sport] = {
            "in_season": in_season,
            "season_start": f"{cal['start'][0]:02d}-{cal['start'][1]:02d}",
            "season_end": f"{cal['end'][0]:02d}-{cal['end'][1]:02d}"
        }

    return status
