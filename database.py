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
