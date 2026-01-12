"""
🧠 LSTM TRAINING PIPELINE v1.0
==============================
Trains LSTM Brain with historical game data.

Data Sources:
- BallDontLie API (NBA stats)
- ESPN historical data
- Synthetic data generation for cold start

All 5 Sports: NBA, NFL, MLB, NHL, NCAAB

Training Target:
- y = (actual_stat - line) / player_avg  -> normalized error
- Positive = player went OVER
- Negative = player went UNDER
"""

import os
import json
import requests
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from loguru import logger
import random

# Import our LSTM brain
try:
    from lstm_brain import LSTMBrain, MultiSportLSTMBrain
    LSTM_AVAILABLE = True
except ImportError:
    LSTM_AVAILABLE = False
    logger.warning("lstm_brain not found - using standalone mode")


# ============================================================
# CONFIGURATION
# ============================================================

class TrainingConfig:
    """Training configuration."""

    # API Keys - Set in Railway environment variables
    # NBA: BallDontLie (requires free API key from balldontlie.io)
    BALLDONTLIE_API_KEY = os.environ.get("BALLDONTLIE_API_KEY", "")

    # NFL/NCAAB: Uses ESPN public API (no key required)
    # MLB: Uses MLB Stats API (no key required)
    # NHL: Uses NHL Stats API (no key required)

    # Optional: SportsDataIO for premium data (all sports)
    SPORTSDATAIO_API_KEY = os.environ.get("SPORTSDATAIO_API_KEY", "")

    # Training parameters
    SEQUENCE_LENGTH = 15  # Games per sequence
    NUM_FEATURES = 6      # [stat, mins, home_away, vacuum, def_rank, pace]
    
    # Training settings
    EPOCHS = 100
    BATCH_SIZE = 32
    VALIDATION_SPLIT = 0.2
    LEARNING_RATE = 0.001
    
    # Data settings
    MIN_SAMPLES_PER_SPORT = 500
    SEASONS = [2023, 2024, 2025]
    
    # Model save paths
    MODELS_DIR = "./models"


# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class GameRecord:
    """Single game record for training."""
    player_name: str
    team: str
    opponent: str
    date: str
    stat_type: str
    stat_value: float
    line: float
    minutes: float
    home_away: int  # 0=away, 1=home
    opp_def_rank: float  # 1-32
    game_pace: float
    vacuum: float
    
    @property
    def target(self) -> float:
        """Calculate training target (normalized error)."""
        if self.line > 0:
            return (self.stat_value - self.line) / max(self.line, 1.0)
        return 0.0


@dataclass 
class TrainingSequence:
    """15-game sequence for LSTM training."""
    player_name: str
    sport: str
    stat_type: str
    features: np.ndarray  # (15, 6)
    target: float         # Normalized error of final game
    
    def to_dict(self) -> Dict:
        return {
            "player_name": self.player_name,
            "sport": self.sport,
            "stat_type": self.stat_type,
            "features": self.features.tolist(),
            "target": self.target
        }


# ============================================================
# HISTORICAL DATA FETCHER
# ============================================================

class HistoricalDataFetcher:
    """Fetches historical game data from various sources."""
    
    @classmethod
    def fetch_nba_games(cls, player_id: int, season: int = 2025) -> List[Dict]:
        """Fetch NBA player game logs from BallDontLie API."""
        if not TrainingConfig.BALLDONTLIE_API_KEY:
            logger.warning("BALLDONTLIE_API_KEY not set - using synthetic data")
            return []
        
        headers = {"Authorization": TrainingConfig.BALLDONTLIE_API_KEY}
        url = f"https://api.balldontlie.io/v1/stats"
        
        all_games = []
        cursor = None
        
        try:
            while True:
                params = {
                    "player_ids[]": player_id,
                    "seasons[]": season,
                    "per_page": 100
                }
                if cursor:
                    params["cursor"] = cursor
                
                response = requests.get(url, headers=headers, params=params, timeout=15)
                
                if response.status_code != 200:
                    logger.error(f"BallDontLie error: {response.status_code}")
                    break
                
                data = response.json()
                all_games.extend(data.get("data", []))
                
                cursor = data.get("meta", {}).get("next_cursor")
                if not cursor:
                    break
            
            logger.info(f"Fetched {len(all_games)} games for player {player_id}")
            return all_games
            
        except Exception as e:
            logger.error(f"Error fetching NBA games: {e}")
            return []
    
    @classmethod
    def fetch_nba_players(cls, per_page: int = 100) -> List[Dict]:
        """Fetch NBA player list."""
        if not TrainingConfig.BALLDONTLIE_API_KEY:
            return []

        headers = {"Authorization": TrainingConfig.BALLDONTLIE_API_KEY}
        url = "https://api.balldontlie.io/v1/players"

        try:
            response = requests.get(url, headers=headers, params={"per_page": per_page}, timeout=10)
            if response.status_code == 200:
                return response.json().get("data", [])
            return []
        except:
            return []

    @classmethod
    def fetch_nfl_games(cls, player_name: str, season: int = 2025) -> List[Dict]:
        """Fetch NFL player game logs from ESPN API (no key required)."""
        # ESPN public API for NFL player stats
        url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/athletes"

        try:
            # Search for player
            response = requests.get(url, params={"search": player_name}, timeout=10)
            if response.status_code != 200:
                return []

            data = response.json()
            athletes = data.get("athletes", [])
            if not athletes:
                logger.debug(f"NFL player not found: {player_name}")
                return []

            player_id = athletes[0].get("id")

            # Get player game log
            stats_url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/athletes/{player_id}/gamelog"
            stats_response = requests.get(stats_url, timeout=10)

            if stats_response.status_code == 200:
                return stats_response.json().get("events", [])
            return []
        except Exception as e:
            logger.debug(f"Error fetching NFL games: {e}")
            return []

    @classmethod
    def fetch_mlb_games(cls, player_id: int, season: int = 2025) -> List[Dict]:
        """Fetch MLB player game logs from MLB Stats API (no key required)."""
        url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats"

        try:
            params = {
                "stats": "gameLog",
                "season": season,
                "group": "hitting"
            }
            response = requests.get(url, params=params, timeout=15)

            if response.status_code == 200:
                data = response.json()
                stats = data.get("stats", [])
                if stats:
                    return stats[0].get("splits", [])
            return []
        except Exception as e:
            logger.debug(f"Error fetching MLB games: {e}")
            return []

    @classmethod
    def fetch_mlb_players(cls, season: int = 2025) -> List[Dict]:
        """Fetch active MLB players from MLB Stats API."""
        url = "https://statsapi.mlb.com/api/v1/sports/1/players"

        try:
            params = {"season": season}
            response = requests.get(url, params=params, timeout=15)
            if response.status_code == 200:
                return response.json().get("people", [])
            return []
        except:
            return []

    @classmethod
    def fetch_nhl_games(cls, player_id: int, season: str = "20242025") -> List[Dict]:
        """Fetch NHL player game logs from NHL Stats API (no key required)."""
        url = f"https://api-web.nhle.com/v1/player/{player_id}/game-log/{season}/2"

        try:
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                return response.json().get("gameLog", [])
            return []
        except Exception as e:
            logger.debug(f"Error fetching NHL games: {e}")
            return []

    @classmethod
    def fetch_nhl_players(cls) -> List[Dict]:
        """Fetch active NHL players."""
        # Get from NHL API teams roster
        teams_url = "https://api-web.nhle.com/v1/standings/now"
        players = []

        try:
            response = requests.get(teams_url, timeout=10)
            if response.status_code != 200:
                return []

            standings = response.json().get("standings", [])
            for team in standings[:10]:  # Limit to first 10 teams
                team_abbrev = team.get("teamAbbrev", {}).get("default", "")
                if team_abbrev:
                    roster_url = f"https://api-web.nhle.com/v1/roster/{team_abbrev}/current"
                    roster_resp = requests.get(roster_url, timeout=10)
                    if roster_resp.status_code == 200:
                        roster = roster_resp.json()
                        for pos in ["forwards", "defensemen", "goalies"]:
                            players.extend(roster.get(pos, []))
            return players
        except:
            return []

    @classmethod
    def fetch_ncaab_games(cls, player_name: str, team: str = None) -> List[Dict]:
        """Fetch NCAAB player game logs from ESPN API (no key required)."""
        url = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/athletes"

        try:
            response = requests.get(url, params={"search": player_name}, timeout=10)
            if response.status_code != 200:
                return []

            data = response.json()
            athletes = data.get("athletes", [])
            if not athletes:
                return []

            player_id = athletes[0].get("id")
            stats_url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/athletes/{player_id}/gamelog"
            stats_response = requests.get(stats_url, timeout=10)

            if stats_response.status_code == 200:
                return stats_response.json().get("events", [])
            return []
        except Exception as e:
            logger.debug(f"Error fetching NCAAB games: {e}")
            return []


# ============================================================
# SYNTHETIC DATA GENERATOR
# ============================================================

class SyntheticDataGenerator:
    """
    Generates realistic synthetic training data.
    Used for cold start when no API data available.
    """
    
    # Realistic stat distributions by sport/position
    STAT_DISTRIBUTIONS = {
        "NBA": {
            "points": {"mean": 15.0, "std": 8.0, "min": 0, "max": 60},
            "rebounds": {"mean": 5.0, "std": 3.0, "min": 0, "max": 25},
            "assists": {"mean": 4.0, "std": 3.0, "min": 0, "max": 20},
        },
        "NFL": {
            "passing_yards": {"mean": 250.0, "std": 80.0, "min": 50, "max": 500},
            "rushing_yards": {"mean": 60.0, "std": 35.0, "min": 0, "max": 200},
            "receiving_yards": {"mean": 50.0, "std": 35.0, "min": 0, "max": 200},
        },
        "MLB": {
            "hits": {"mean": 1.0, "std": 0.8, "min": 0, "max": 5},
            "total_bases": {"mean": 1.5, "std": 1.2, "min": 0, "max": 10},
            "strikeouts": {"mean": 6.0, "std": 2.5, "min": 0, "max": 15},
        },
        "NHL": {
            "points": {"mean": 0.8, "std": 0.7, "min": 0, "max": 5},
            "shots": {"mean": 2.5, "std": 1.5, "min": 0, "max": 10},
        },
        "NCAAB": {
            "points": {"mean": 12.0, "std": 6.0, "min": 0, "max": 40},
            "rebounds": {"mean": 4.0, "std": 2.5, "min": 0, "max": 15},
        }
    }
    
    # Minutes distributions
    MINUTES_DISTRIBUTIONS = {
        "NBA": {"mean": 28.0, "std": 8.0, "min": 5, "max": 48},
        "NFL": {"mean": 55.0, "std": 10.0, "min": 20, "max": 70},
        "MLB": {"mean": 4.0, "std": 1.5, "min": 1, "max": 9},  # Plate appearances / innings
        "NHL": {"mean": 18.0, "std": 5.0, "min": 5, "max": 28},
        "NCAAB": {"mean": 25.0, "std": 8.0, "min": 5, "max": 40},
    }
    
    @classmethod
    def generate_player_season(
        cls,
        sport: str,
        stat_type: str,
        num_games: int = 82,
        player_skill: float = 0.5  # 0-1, affects consistency
    ) -> List[GameRecord]:
        """Generate a full season of synthetic game data for one player."""
        
        sport = sport.upper()
        stat_dist = cls.STAT_DISTRIBUTIONS.get(sport, {}).get(stat_type)
        mins_dist = cls.MINUTES_DISTRIBUTIONS.get(sport)
        
        if not stat_dist or not mins_dist:
            logger.warning(f"No distribution for {sport}/{stat_type}")
            return []
        
        # Player's baseline (affected by skill)
        player_mean = stat_dist["mean"] * (0.5 + player_skill)
        player_std = stat_dist["std"] * (1.5 - player_skill)  # Higher skill = more consistent
        
        games = []
        player_name = f"Player_{sport}_{random.randint(1000, 9999)}"
        team = f"TEAM_{random.randint(1, 30)}"
        
        for game_num in range(num_games):
            # Generate context factors
            opp_def_rank = random.uniform(1, 32)  # 1 = best defense, 32 = worst
            game_pace = random.gauss(100, 5)
            home_away = random.choice([0, 1])
            vacuum = random.uniform(0, 0.3)  # Usually low
            
            # Occasional high vacuum (injuries)
            if random.random() < 0.1:
                vacuum = random.uniform(0.3, 0.8)
            
            # Context effects on performance
            def_effect = (opp_def_rank - 16) / 32 * stat_dist["std"] * 0.5  # Weak D = boost
            pace_effect = (game_pace - 100) / 10 * stat_dist["std"] * 0.3  # Fast pace = boost
            home_effect = home_away * stat_dist["std"] * 0.2  # Home = slight boost
            vacuum_effect = vacuum * stat_dist["std"] * 1.0  # Vacuum = opportunity
            
            # Generate stat
            context_boost = def_effect + pace_effect + home_effect + vacuum_effect
            stat_value = random.gauss(player_mean + context_boost, player_std)
            stat_value = max(stat_dist["min"], min(stat_dist["max"], stat_value))
            
            # Generate minutes
            minutes = random.gauss(mins_dist["mean"], mins_dist["std"])
            minutes = max(mins_dist["min"], min(mins_dist["max"], minutes))
            
            # Generate line (slightly off from player mean)
            line = player_mean + random.gauss(0, stat_dist["std"] * 0.3)
            line = round(line * 2) / 2  # Round to 0.5
            
            # Generate date
            season_start = datetime(2024, 10, 1)
            game_date = season_start + timedelta(days=game_num * 2 + random.randint(0, 1))
            
            games.append(GameRecord(
                player_name=player_name,
                team=team,
                opponent=f"OPP_{random.randint(1, 30)}",
                date=game_date.strftime("%Y-%m-%d"),
                stat_type=stat_type,
                stat_value=round(stat_value, 1),
                line=round(line, 1),
                minutes=round(minutes, 1),
                home_away=home_away,
                opp_def_rank=round(opp_def_rank, 1),
                game_pace=round(game_pace, 1),
                vacuum=round(vacuum, 3)
            ))
        
        return games
    
    @classmethod
    def generate_training_data(
        cls,
        sport: str,
        stat_type: str,
        num_players: int = 50,
        games_per_player: int = 82
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Generate full training dataset.
        
        Returns:
            X: (n_samples, 15, 6) feature sequences
            y: (n_samples,) target values
        """
        all_sequences = []
        all_targets = []
        
        for player_idx in range(num_players):
            # Vary player skill
            skill = random.uniform(0.2, 0.9)
            
            games = cls.generate_player_season(sport, stat_type, games_per_player, skill)
            
            if len(games) < TrainingConfig.SEQUENCE_LENGTH:
                continue
            
            # Create sequences from rolling window
            for i in range(len(games) - TrainingConfig.SEQUENCE_LENGTH):
                sequence_games = games[i:i + TrainingConfig.SEQUENCE_LENGTH]
                target_game = sequence_games[-1]
                
                # Build feature matrix (15, 6)
                features = np.zeros((TrainingConfig.SEQUENCE_LENGTH, TrainingConfig.NUM_FEATURES))
                
                player_avg = np.mean([g.stat_value for g in sequence_games[:-1]])  # Avg before target
                
                for j, game in enumerate(sequence_games):
                    # [stat, mins, home_away, vacuum, def_rank, pace]
                    features[j, 0] = game.stat_value / max(player_avg, 1.0)  # Normalized stat
                    features[j, 1] = game.minutes / 48.0  # Normalized mins (NBA)
                    features[j, 2] = game.home_away
                    features[j, 3] = game.vacuum
                    features[j, 4] = (game.opp_def_rank - 1) / 31.0  # Normalized rank
                    features[j, 5] = (game.game_pace - 90) / 20.0  # Normalized pace
                
                # Target: normalized error of final game
                target = target_game.target
                
                all_sequences.append(features)
                all_targets.append(target)
        
        X = np.array(all_sequences, dtype=np.float32)
        y = np.array(all_targets, dtype=np.float32)
        
        # Clip targets to reasonable range
        y = np.clip(y, -2.0, 2.0)
        
        logger.info(f"Generated {len(X)} training sequences for {sport}/{stat_type}")
        
        return X, y


# ============================================================
# TRAINING PIPELINE
# ============================================================

class LSTMTrainingPipeline:
    """
    Main training pipeline for LSTM Brain.
    """
    
    def __init__(self, models_dir: str = "./models"):
        self.models_dir = models_dir
        os.makedirs(models_dir, exist_ok=True)
    
    def train_sport(
        self,
        sport: str,
        stat_type: str = "points",
        use_synthetic: bool = True,
        num_players: int = 100,
        epochs: int = 100
    ) -> Dict:
        """
        Train LSTM for a specific sport/stat combination.
        
        Args:
            sport: Sport to train (NBA, NFL, MLB, NHL, NCAAB)
            stat_type: Stat type to train on
            use_synthetic: Use synthetic data if API unavailable
            num_players: Number of synthetic players
            epochs: Training epochs
            
        Returns:
            Training results dict
        """
        sport = sport.upper()
        logger.info(f"Training LSTM for {sport}/{stat_type}...")
        
        # Generate training data
        if use_synthetic:
            X, y = SyntheticDataGenerator.generate_training_data(
                sport=sport,
                stat_type=stat_type,
                num_players=num_players,
                games_per_player=82 if sport in ["NBA", "NHL"] else 17 if sport == "NFL" else 162
            )
        else:
            # TODO: Implement real data fetching
            logger.warning("Real data fetching not implemented - using synthetic")
            X, y = SyntheticDataGenerator.generate_training_data(sport, stat_type, num_players)
        
        if len(X) < 100:
            return {"error": f"Insufficient training data: {len(X)} samples"}
        
        logger.info(f"Training data: {X.shape[0]} samples, {X.shape[1]} timesteps, {X.shape[2]} features")
        logger.info(f"Target range: [{y.min():.3f}, {y.max():.3f}], mean: {y.mean():.3f}")
        
        # Initialize LSTM brain
        brain = LSTMBrain(sport=sport)
        
        # Train
        save_path = os.path.join(self.models_dir, f"lstm_{sport.lower()}_{stat_type}.weights.h5")
        
        result = brain.train(
            X=X,
            y=y,
            validation_split=TrainingConfig.VALIDATION_SPLIT,
            epochs=epochs,
            batch_size=TrainingConfig.BATCH_SIZE,
            save_path=save_path
        )
        
        result["sport"] = sport
        result["stat_type"] = stat_type
        result["samples"] = len(X)
        result["model_path"] = save_path
        
        logger.success(f"Training complete: val_loss={result.get('best_val_loss', 'N/A'):.4f}")
        
        return result
    
    def train_all_sports(self, epochs: int = 100) -> Dict:
        """Train LSTM for all sports."""
        results = {}
        
        sport_stats = {
            "NBA": ["points", "rebounds", "assists"],
            "NFL": ["passing_yards", "rushing_yards", "receiving_yards"],
            "MLB": ["hits", "total_bases", "strikeouts"],
            "NHL": ["points", "shots"],
            "NCAAB": ["points", "rebounds"]
        }
        
        for sport, stat_types in sport_stats.items():
            results[sport] = {}
            for stat_type in stat_types:
                try:
                    result = self.train_sport(sport, stat_type, epochs=epochs)
                    results[sport][stat_type] = result
                except Exception as e:
                    logger.error(f"Error training {sport}/{stat_type}: {e}")
                    results[sport][stat_type] = {"error": str(e)}
        
        return results
    
    def evaluate_model(self, sport: str, stat_type: str = "points") -> Dict:
        """Evaluate trained model on held-out data."""
        sport = sport.upper()
        
        # Generate test data
        X_test, y_test = SyntheticDataGenerator.generate_training_data(
            sport=sport,
            stat_type=stat_type,
            num_players=20,
            games_per_player=30
        )
        
        # Load trained model
        model_path = os.path.join(self.models_dir, f"lstm_{sport.lower()}_{stat_type}.weights.h5")
        brain = LSTMBrain(model_path=model_path, sport=sport)
        
        # Evaluate
        predictions = []
        for i in range(len(X_test)):
            result = brain.predict(X_test[i:i+1])
            predictions.append(result["raw_output"])
        
        predictions = np.array(predictions)
        
        # Calculate metrics
        mae = np.mean(np.abs(predictions - y_test))
        mse = np.mean((predictions - y_test) ** 2)
        
        # Direction accuracy (did we predict OVER/UNDER correctly?)
        direction_correct = np.sum((predictions > 0) == (y_test > 0))
        direction_accuracy = direction_correct / len(y_test)
        
        return {
            "sport": sport,
            "stat_type": stat_type,
            "test_samples": len(X_test),
            "mae": round(mae, 4),
            "mse": round(mse, 4),
            "rmse": round(np.sqrt(mse), 4),
            "direction_accuracy": round(direction_accuracy * 100, 1)
        }


# ============================================================
# FASTAPI ROUTER FOR TRAINING
# ============================================================

from fastapi import APIRouter, HTTPException, BackgroundTasks

training_router = APIRouter(prefix="/training", tags=["Training"])

# Global pipeline instance
pipeline = LSTMTrainingPipeline()


@training_router.post("/train/{sport}")
async def train_sport_model(
    sport: str,
    stat_type: str = "points",
    epochs: int = 50,
    num_players: int = 100,
    background_tasks: BackgroundTasks = None
):
    """Train LSTM for a specific sport."""
    sport = sport.upper()
    if sport not in ["NBA", "NFL", "MLB", "NHL", "NCAAB"]:
        raise HTTPException(400, "Invalid sport")
    
    # Run training (can be moved to background for long training)
    result = pipeline.train_sport(
        sport=sport,
        stat_type=stat_type,
        epochs=epochs,
        num_players=num_players
    )
    
    return {
        "status": "complete",
        "result": result
    }


@training_router.post("/train-all")
async def train_all_models(epochs: int = 50):
    """Train LSTM for all sports (takes several minutes)."""
    results = pipeline.train_all_sports(epochs=epochs)
    return {
        "status": "complete",
        "results": results
    }


@training_router.get("/evaluate/{sport}")
async def evaluate_model(sport: str, stat_type: str = "points"):
    """Evaluate trained model."""
    sport = sport.upper()
    if sport not in ["NBA", "NFL", "MLB", "NHL", "NCAAB"]:
        raise HTTPException(400, "Invalid sport")
    
    result = pipeline.evaluate_model(sport, stat_type)
    return {
        "status": "success",
        "evaluation": result
    }


@training_router.get("/status")
async def training_status():
    """Check which models are trained."""
    models_dir = pipeline.models_dir
    
    trained = {}
    for sport in ["NBA", "NFL", "MLB", "NHL", "NCAAB"]:
        trained[sport] = {}
        for stat in ["points", "rebounds", "assists", "passing_yards", "rushing_yards", "hits"]:
            path = os.path.join(models_dir, f"lstm_{sport.lower()}_{stat}.weights.h5")
            trained[sport][stat] = os.path.exists(path)
    
    return {
        "status": "success",
        "models_dir": models_dir,
        "trained_models": trained
    }


# ============================================================
# STANDALONE EXECUTION
# ============================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Train LSTM Brain")
    parser.add_argument("--sport", type=str, default="NBA", help="Sport to train")
    parser.add_argument("--stat", type=str, default="points", help="Stat type")
    parser.add_argument("--epochs", type=int, default=50, help="Training epochs")
    parser.add_argument("--players", type=int, default=100, help="Number of synthetic players")
    parser.add_argument("--all", action="store_true", help="Train all sports")
    
    args = parser.parse_args()
    
    pipeline = LSTMTrainingPipeline()
    
    if args.all:
        print("Training all sports...")
        results = pipeline.train_all_sports(epochs=args.epochs)
        print(json.dumps(results, indent=2))
    else:
        print(f"Training {args.sport}/{args.stat}...")
        result = pipeline.train_sport(
            sport=args.sport,
            stat_type=args.stat,
            epochs=args.epochs,
            num_players=args.players
        )
        print(json.dumps(result, indent=2))
        
        # Evaluate
        print("\nEvaluating...")
        eval_result = pipeline.evaluate_model(args.sport, args.stat)
        print(json.dumps(eval_result, indent=2))
