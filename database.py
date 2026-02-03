# database.py - PostgreSQL Database Models
# For auto-grader prediction storage and weight persistence

import os
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Text, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
import json

logger = logging.getLogger("database")

# Database URL - Railway provides this when PostgreSQL service is attached
DATABASE_URL = os.getenv("DATABASE_URL", "")

# SQLAlchemy setup
Base = declarative_base()
engine = None
SessionLocal = None
DB_ENABLED = False


def init_database():
    """Initialize database connection and create tables."""
    global engine, SessionLocal, DB_ENABLED

    if not DATABASE_URL:
        logger.warning("DATABASE_URL not set - database features disabled")
        return False

    try:
        # Railway PostgreSQL URLs use postgres:// but SQLAlchemy needs postgresql://
        db_url = DATABASE_URL
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)

        engine = create_engine(db_url, pool_pre_ping=True, pool_size=5)
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


# ============================================================================
# DATABASE MODELS
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
# LINE HISTORY MODELS (v17.6 - For Hurst Exponent & Fibonacci)
# ============================================================================

class LineSnapshot(Base):
    """
    Line snapshots captured periodically for Hurst Exponent analysis.
    Hurst Exponent requires 20+ sequential line values to calculate market regime.
    """
    __tablename__ = "line_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String(100), nullable=False, index=True)
    sport = Column(String(20), nullable=False, index=True)
    home_team = Column(String(100))
    away_team = Column(String(100))
    book = Column(String(50))

    # Line data
    spread = Column(Float, nullable=True)
    spread_odds = Column(Integer, nullable=True)
    total = Column(Float, nullable=True)
    total_odds = Column(Integer, nullable=True)

    # Context
    public_pct = Column(Float, nullable=True)
    money_pct = Column(Float, nullable=True)

    captured_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    game_start_time = Column(DateTime, nullable=True)

    __table_args__ = (
        Index('ix_lines_event_time', 'event_id', 'captured_at'),
        Index('ix_lines_sport_time', 'sport', 'captured_at'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "sport": self.sport,
            "home_team": self.home_team,
            "away_team": self.away_team,
            "book": self.book,
            "spread": self.spread,
            "spread_odds": self.spread_odds,
            "total": self.total,
            "total_odds": self.total_odds,
            "public_pct": self.public_pct,
            "money_pct": self.money_pct,
            "captured_at": self.captured_at.isoformat() if self.captured_at else None,
            "game_start_time": self.game_start_time.isoformat() if self.game_start_time else None
        }


class SeasonExtreme(Base):
    """
    Season extremes for Fibonacci Retracement analysis.
    Fibonacci needs season_high and season_low to calculate retracement levels.
    """
    __tablename__ = "season_extremes"

    id = Column(Integer, primary_key=True, index=True)
    sport = Column(String(20), nullable=False, index=True)
    season = Column(String(20), nullable=False)  # "2025-26"
    stat_type = Column(String(50), nullable=False)  # "points", "spread", "total", etc.
    subject_id = Column(String(100), nullable=True)  # player_id or team_id
    subject_name = Column(String(100), nullable=True)

    season_high = Column(Float, nullable=True)
    season_low = Column(Float, nullable=True)
    current_value = Column(Float, nullable=True)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('ix_extremes_sport_season', 'sport', 'season', 'stat_type', 'subject_id', unique=True),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sport": self.sport,
            "season": self.season,
            "stat_type": self.stat_type,
            "subject_id": self.subject_id,
            "subject_name": self.subject_name,
            "season_high": self.season_high,
            "season_low": self.season_low,
            "current_value": self.current_value,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


# ============================================================================
# LINE HISTORY HELPER FUNCTIONS (v17.6)
# ============================================================================

def save_line_snapshot(db: Session, event_id: str, sport: str, home_team: str, away_team: str,
                      spread: float = None, total: float = None, book: str = None,
                      spread_odds: int = None, total_odds: int = None,
                      public_pct: float = None, money_pct: float = None,
                      game_start_time: datetime = None) -> Optional[LineSnapshot]:
    """Save a line snapshot for Hurst Exponent analysis."""
    if not db:
        return None

    try:
        record = LineSnapshot(
            event_id=event_id,
            sport=sport.upper(),
            home_team=home_team,
            away_team=away_team,
            book=book,
            spread=spread,
            spread_odds=spread_odds,
            total=total,
            total_odds=total_odds,
            public_pct=public_pct,
            money_pct=money_pct,
            game_start_time=game_start_time
        )
        db.add(record)
        db.flush()
        return record
    except Exception as e:
        logger.error("Failed to save line snapshot: %s", e)
        return None


def get_line_history(db: Session, event_id: str, limit: int = 30) -> list:
    """
    Get line history for an event (for Hurst Exponent).
    Returns list of spread/total values in chronological order.
    """
    if not db:
        return []

    records = db.query(LineSnapshot).filter(
        LineSnapshot.event_id == event_id
    ).order_by(LineSnapshot.captured_at.asc()).limit(limit).all()

    return [r.to_dict() for r in records]


def get_line_history_values(db: Session, event_id: str, value_type: str = "spread", limit: int = 30) -> list:
    """
    Get raw numeric values for Hurst Exponent calculation.

    Args:
        event_id: Event ID to query
        value_type: "spread" or "total"
        limit: Max records to return

    Returns:
        List of floats (spread or total values) in chronological order
    """
    if not db:
        return []

    records = db.query(LineSnapshot).filter(
        LineSnapshot.event_id == event_id
    ).order_by(LineSnapshot.captured_at.asc()).limit(limit).all()

    if value_type == "spread":
        return [r.spread for r in records if r.spread is not None]
    elif value_type == "total":
        return [r.total for r in records if r.total is not None]
    return []


def update_season_extreme(db: Session, sport: str, season: str, stat_type: str,
                         subject_id: str = None, subject_name: str = None,
                         current_value: float = None) -> Optional[SeasonExtreme]:
    """
    Update season high/low for Fibonacci Retracement.
    Automatically tracks high and low based on current_value.
    """
    if not db or current_value is None:
        return None

    try:
        # Find existing record
        record = db.query(SeasonExtreme).filter(
            SeasonExtreme.sport == sport.upper(),
            SeasonExtreme.season == season,
            SeasonExtreme.stat_type == stat_type,
            SeasonExtreme.subject_id == subject_id
        ).first()

        if record:
            # Update current value
            record.current_value = current_value
            # Update high/low if necessary
            if record.season_high is None or current_value > record.season_high:
                record.season_high = current_value
            if record.season_low is None or current_value < record.season_low:
                record.season_low = current_value
        else:
            # Create new record
            record = SeasonExtreme(
                sport=sport.upper(),
                season=season,
                stat_type=stat_type,
                subject_id=subject_id,
                subject_name=subject_name,
                current_value=current_value,
                season_high=current_value,
                season_low=current_value
            )
            db.add(record)

        db.flush()
        return record
    except Exception as e:
        logger.error("Failed to update season extreme: %s", e)
        return None


def get_season_extreme(db: Session, sport: str, season: str, stat_type: str,
                      subject_id: str = None) -> Optional[Dict[str, Any]]:
    """Get season high/low for Fibonacci Retracement."""
    if not db:
        return None

    record = db.query(SeasonExtreme).filter(
        SeasonExtreme.sport == sport.upper(),
        SeasonExtreme.season == season,
        SeasonExtreme.stat_type == stat_type,
        SeasonExtreme.subject_id == subject_id
    ).first()

    if record:
        return record.to_dict()
    return None


# ============================================================================
# DATABASE HELPER FUNCTIONS
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
        "url_set": "DATABASE_URL" in os.environ
    }
