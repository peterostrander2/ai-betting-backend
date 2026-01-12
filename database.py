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
