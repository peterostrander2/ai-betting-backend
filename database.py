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


# ============================================================================
# OFFICIAL TRACKING MODELS (v18.0 - Automated Officials)
# ============================================================================

class OfficialGameRecord(Base):
    """
    Track official assignments and game outcomes for tendency calculation.
    Records referee assignments when bets are made, outcomes after games complete.
    """
    __tablename__ = "official_game_records"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String(100), nullable=False, index=True)
    sport = Column(String(20), nullable=False, index=True)
    season = Column(String(20))  # "2025-26"

    # Teams
    home_team = Column(String(100))
    away_team = Column(String(100))

    # Officials (from ESPN)
    lead_official = Column(String(100), index=True)
    official_2 = Column(String(100))
    official_3 = Column(String(100))

    # Game timing
    game_date = Column(String(10), index=True)  # YYYY-MM-DD
    game_start_time = Column(DateTime(timezone=True))

    # Lines at game time (for determining over/under result)
    over_under_line = Column(Float, nullable=True)
    spread_line = Column(Float, nullable=True)

    # Outcomes (populated after game ends)
    final_total = Column(Float, nullable=True)  # Actual combined score
    spread_result = Column(Float, nullable=True)  # Home team margin (home - away)
    home_score = Column(Integer, nullable=True)
    away_score = Column(Integer, nullable=True)

    # Derived (calculated when outcome is recorded)
    went_over = Column(Boolean, nullable=True)  # final_total > over_under_line
    home_covered = Column(Boolean, nullable=True)  # spread_result > spread_line

    # Metadata
    recorded_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    outcome_recorded_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index('ix_official_games_sport_date', 'sport', 'game_date'),
        Index('ix_official_games_lead_official', 'lead_official', 'sport'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "event_id": self.event_id,
            "sport": self.sport,
            "season": self.season,
            "home_team": self.home_team,
            "away_team": self.away_team,
            "lead_official": self.lead_official,
            "official_2": self.official_2,
            "official_3": self.official_3,
            "game_date": self.game_date,
            "game_start_time": self.game_start_time.isoformat() if self.game_start_time else None,
            "over_under_line": self.over_under_line,
            "spread_line": self.spread_line,
            "final_total": self.final_total,
            "spread_result": self.spread_result,
            "home_score": self.home_score,
            "away_score": self.away_score,
            "went_over": self.went_over,
            "home_covered": self.home_covered,
            "recorded_at": self.recorded_at.isoformat() if self.recorded_at else None,
            "outcome_recorded_at": self.outcome_recorded_at.isoformat() if self.outcome_recorded_at else None,
        }


class OfficialTendency(Base):
    """
    Computed referee tendencies, refreshed weekly from game history.
    Used by OfficialsService to provide data-driven adjustments.
    """
    __tablename__ = "official_tendencies"

    id = Column(Integer, primary_key=True, index=True)
    sport = Column(String(20), nullable=False, index=True)
    official_name = Column(String(100), nullable=False, index=True)
    season = Column(String(20))  # "2025-26" or "all-time"

    # Core metrics
    total_games = Column(Integer, default=0)
    over_games = Column(Integer, default=0)
    over_pct = Column(Float, nullable=True)  # over_games / total_games

    home_cover_games = Column(Integer, default=0)
    home_cover_pct = Column(Float, nullable=True)  # home_cover_games / total_games
    home_bias = Column(Float, nullable=True)  # home_cover_pct - 0.50

    # Whistle rate (HIGH/MEDIUM/LOW) - for NBA foul rate, NFL flag rate, NHL penalty rate
    whistle_rate = Column(String(20), nullable=True)
    avg_total_points = Column(Float, nullable=True)  # Average final total in their games

    # Confidence
    sample_size_sufficient = Column(Boolean, default=False)  # >= 50 games

    last_updated = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index('ix_tendencies_sport_official', 'sport', 'official_name', unique=False),
        Index('ix_tendencies_season', 'season'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sport": self.sport,
            "official_name": self.official_name,
            "season": self.season,
            "total_games": self.total_games,
            "over_games": self.over_games,
            "over_pct": self.over_pct,
            "home_cover_games": self.home_cover_games,
            "home_cover_pct": self.home_cover_pct,
            "home_bias": self.home_bias,
            "whistle_rate": self.whistle_rate,
            "avg_total_points": self.avg_total_points,
            "sample_size_sufficient": self.sample_size_sufficient,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
        }


# ============================================================================
# OFFICIAL TRACKING HELPER FUNCTIONS (v18.0)
# ============================================================================

def save_official_game_record(
    db: Session,
    event_id: str,
    sport: str,
    home_team: str,
    away_team: str,
    lead_official: str,
    game_date: str,
    over_under_line: float = None,
    spread_line: float = None,
    official_2: str = None,
    official_3: str = None,
    game_start_time: datetime = None,
    season: str = None
) -> Optional[OfficialGameRecord]:
    """Save an official assignment record for tracking."""
    if not db or not event_id or not lead_official:
        return None

    try:
        # Check if record already exists for this event
        existing = db.query(OfficialGameRecord).filter(
            OfficialGameRecord.event_id == event_id
        ).first()

        if existing:
            # Update existing record (officials might be added later)
            if lead_official:
                existing.lead_official = lead_official
            if official_2:
                existing.official_2 = official_2
            if official_3:
                existing.official_3 = official_3
            db.flush()
            return existing

        # Create new record
        record = OfficialGameRecord(
            event_id=event_id,
            sport=sport.upper(),
            season=season or _get_current_season(),
            home_team=home_team,
            away_team=away_team,
            lead_official=lead_official,
            official_2=official_2,
            official_3=official_3,
            game_date=game_date,
            game_start_time=game_start_time,
            over_under_line=over_under_line,
            spread_line=spread_line,
        )
        db.add(record)
        db.flush()
        return record
    except Exception as e:
        logger.error("Failed to save official game record: %s", e)
        return None


def record_game_outcome(
    db: Session,
    event_id: str,
    final_total: float,
    home_score: int,
    away_score: int
) -> Optional[OfficialGameRecord]:
    """Record game outcome for an existing official assignment."""
    if not db or not event_id:
        return None

    try:
        record = db.query(OfficialGameRecord).filter(
            OfficialGameRecord.event_id == event_id
        ).first()

        if not record:
            logger.warning("No official record found for event_id: %s", event_id)
            return None

        # Update with outcome
        record.final_total = final_total
        record.home_score = home_score
        record.away_score = away_score
        record.spread_result = home_score - away_score
        record.outcome_recorded_at = datetime.utcnow()

        # Calculate derived fields
        if record.over_under_line is not None:
            record.went_over = final_total > record.over_under_line
        if record.spread_line is not None:
            record.home_covered = record.spread_result > record.spread_line

        db.flush()
        logger.info("Recorded outcome for event %s: total=%s, went_over=%s",
                    event_id, final_total, record.went_over)
        return record
    except Exception as e:
        logger.error("Failed to record game outcome: %s", e)
        return None


def get_official_tendency(
    db: Session,
    sport: str,
    official_name: str,
    season: str = None
) -> Optional[Dict[str, Any]]:
    """Get computed tendency for an official."""
    if not db or not official_name:
        return None

    try:
        query = db.query(OfficialTendency).filter(
            OfficialTendency.sport == sport.upper(),
            OfficialTendency.official_name == official_name
        )

        if season:
            query = query.filter(OfficialTendency.season == season)
        else:
            # Prefer current season, fall back to all-time
            query = query.order_by(OfficialTendency.season.desc())

        record = query.first()
        if record:
            return record.to_dict()
        return None
    except Exception as e:
        logger.error("Failed to get official tendency: %s", e)
        return None


def save_official_tendency(
    db: Session,
    sport: str,
    official_name: str,
    season: str,
    total_games: int,
    over_games: int,
    home_cover_games: int,
    avg_total_points: float = None,
    whistle_rate: str = None
) -> Optional[OfficialTendency]:
    """Save or update computed tendency for an official."""
    if not db or not official_name:
        return None

    try:
        # Check for existing
        existing = db.query(OfficialTendency).filter(
            OfficialTendency.sport == sport.upper(),
            OfficialTendency.official_name == official_name,
            OfficialTendency.season == season
        ).first()

        if existing:
            record = existing
        else:
            record = OfficialTendency(
                sport=sport.upper(),
                official_name=official_name,
                season=season
            )
            db.add(record)

        # Update metrics
        record.total_games = total_games
        record.over_games = over_games
        record.home_cover_games = home_cover_games
        record.avg_total_points = avg_total_points
        record.whistle_rate = whistle_rate
        record.last_updated = datetime.utcnow()

        # Calculate derived fields
        if total_games > 0:
            record.over_pct = over_games / total_games
            record.home_cover_pct = home_cover_games / total_games
            record.home_bias = record.home_cover_pct - 0.50
        else:
            record.over_pct = None
            record.home_cover_pct = None
            record.home_bias = None

        record.sample_size_sufficient = total_games >= 50

        db.flush()
        return record
    except Exception as e:
        logger.error("Failed to save official tendency: %s", e)
        return None


def get_official_game_history(
    db: Session,
    sport: str,
    official_name: str,
    season: str = None,
    limit: int = 100
) -> list:
    """Get game history for an official (for tendency calculation)."""
    if not db or not official_name:
        return []

    try:
        query = db.query(OfficialGameRecord).filter(
            OfficialGameRecord.sport == sport.upper(),
            OfficialGameRecord.lead_official == official_name,
            OfficialGameRecord.outcome_recorded_at.isnot(None)  # Only graded games
        )

        if season:
            query = query.filter(OfficialGameRecord.season == season)

        records = query.order_by(
            OfficialGameRecord.game_date.desc()
        ).limit(limit).all()

        return [r.to_dict() for r in records]
    except Exception as e:
        logger.error("Failed to get official game history: %s", e)
        return []


def _get_current_season() -> str:
    """Get current season string (e.g., '2025-26')."""
    now = datetime.utcnow()
    # Season starts in October, so before October = previous season
    if now.month >= 10:
        return f"{now.year}-{str(now.year + 1)[-2:]}"
    else:
        return f"{now.year - 1}-{str(now.year)[-2:]}"


def get_database_status() -> Dict[str, Any]:
    """Get database connection status."""
    return {
        "enabled": DB_ENABLED,
        "configured": bool(DATABASE_URL),
        "url_set": "DATABASE_URL" in os.environ
    }
