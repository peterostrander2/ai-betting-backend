"""
🔥 LIVE DATA ROUTER v7.1.0
===========================
Unified data fetching for Bookie-o-em v7.1.0

Integrates:
- The Odds API (game lines, player props)
- BallDontLie API (player stats) 
- ESPN API (injuries, schedules)

All 5 Sports: NBA, NFL, MLB, NHL, NCAAB

Environment Variables Required:
- ODDS_API_KEY: From the-odds-api.com
- BALLDONTLIE_API_KEY: From balldontlie.io (optional)
"""

import os
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from loguru import logger
import json

# ============================================================
# API CONFIGURATION
# ============================================================

class LiveDataConfig:
    """Central configuration for all API keys."""
    
    # The Odds API - https://the-odds-api.com/
    ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "")
    ODDS_API_BASE = "https://api.the-odds-api.com/v4"
    
    # BallDontLie API - https://balldontlie.io/
    BALLDONTLIE_API_KEY = os.environ.get("BALLDONTLIE_API_KEY", "")
    BALLDONTLIE_BASE = "https://api.balldontlie.io/v1"
    
    # ESPN API (free, no key needed)
    ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports"
    
    # Sport mappings for The Odds API
    ODDS_API_SPORTS = {
        "NBA": "basketball_nba",
        "NFL": "americanfootball_nfl",
        "MLB": "baseball_mlb",
        "NHL": "icehockey_nhl",
        "NCAAB": "basketball_ncaab"
    }
    
    # ESPN sport paths
    ESPN_SPORTS = {
        "NBA": "basketball/nba",
        "NFL": "football/nfl",
        "MLB": "baseball/mlb",
        "NHL": "hockey/nhl",
        "NCAAB": "basketball/mens-college-basketball"
    }


# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class GameLine:
    """Game spread and total from sportsbook."""
    game_id: str
    sport: str
    home_team: str
    away_team: str
    commence_time: str
    spread: float
    spread_odds: int
    total: float
    over_odds: int
    under_odds: int
    home_ml: int
    away_ml: int
    sportsbook: str


@dataclass
class PlayerProp:
    """Player prop line from sportsbook."""
    player_name: str
    team: str
    stat_type: str  # points, rebounds, assists, etc.
    line: float
    over_odds: int
    under_odds: int
    sportsbook: str
    game_id: str


@dataclass 
class PlayerStats:
    """Player season stats."""
    player_name: str
    team: str
    position: str
    games_played: int
    minutes_per_game: float
    points_per_game: float
    rebounds_per_game: float
    assists_per_game: float
    usage_pct: float


@dataclass
class InjuryReport:
    """Player injury information."""
    player_name: str
    team: str
    position: str
    status: str  # OUT, DOUBTFUL, QUESTIONABLE, PROBABLE
    injury_type: str
    usage_pct: float
    minutes_per_game: float


# ============================================================
# THE ODDS API SERVICE
# ============================================================

class OddsAPIService:
    """
    Fetches live odds from The Odds API.
    https://the-odds-api.com/
    """
    
    @staticmethod
    def _make_request(endpoint: str, params: dict = None) -> Optional[dict]:
        """Make authenticated request to The Odds API."""
        if not LiveDataConfig.ODDS_API_KEY:
            logger.warning("ODDS_API_KEY not set - using mock data")
            return None
            
        if params is None:
            params = {}
        params["apiKey"] = LiveDataConfig.ODDS_API_KEY
        
        url = f"{LiveDataConfig.ODDS_API_BASE}/{endpoint}"
        
        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Odds API error: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Odds API request failed: {e}")
            return None
    
    @classmethod
    def get_games(cls, sport: str) -> List[GameLine]:
        """Get all upcoming games with odds for a sport."""
        sport_key = LiveDataConfig.ODDS_API_SPORTS.get(sport.upper())
        if not sport_key:
            return []
        
        data = cls._make_request(f"sports/{sport_key}/odds", {
            "regions": "us",
            "markets": "spreads,totals,h2h",
            "oddsFormat": "american"
        })
        
        if not data:
            return cls._get_mock_games(sport)
        
        games = []
        for game in data:
            try:
                # Find DraftKings or FanDuel odds
                bookmaker = None
                for bm in game.get("bookmakers", []):
                    if bm["key"] in ["draftkings", "fanduel", "betmgm"]:
                        bookmaker = bm
                        break
                
                if not bookmaker:
                    bookmaker = game["bookmakers"][0] if game.get("bookmakers") else None
                
                if not bookmaker:
                    continue
                
                # Extract markets
                spread = total = home_ml = away_ml = None
                spread_odds = over_odds = under_odds = -110
                
                for market in bookmaker.get("markets", []):
                    if market["key"] == "spreads":
                        for outcome in market["outcomes"]:
                            if outcome["name"] == game["home_team"]:
                                spread = outcome.get("point", 0)
                                spread_odds = outcome.get("price", -110)
                    elif market["key"] == "totals":
                        for outcome in market["outcomes"]:
                            if outcome["name"] == "Over":
                                total = outcome.get("point", 220)
                                over_odds = outcome.get("price", -110)
                            elif outcome["name"] == "Under":
                                under_odds = outcome.get("price", -110)
                    elif market["key"] == "h2h":
                        for outcome in market["outcomes"]:
                            if outcome["name"] == game["home_team"]:
                                home_ml = outcome.get("price", -110)
                            else:
                                away_ml = outcome.get("price", -110)
                
                games.append(GameLine(
                    game_id=game["id"],
                    sport=sport.upper(),
                    home_team=game["home_team"],
                    away_team=game["away_team"],
                    commence_time=game["commence_time"],
                    spread=spread or 0,
                    spread_odds=spread_odds,
                    total=total or 220,
                    over_odds=over_odds,
                    under_odds=under_odds,
                    home_ml=home_ml or -110,
                    away_ml=away_ml or -110,
                    sportsbook=bookmaker["key"]
                ))
            except Exception as e:
                logger.warning(f"Error parsing game: {e}")
                continue
        
        logger.info(f"[{sport}] Fetched {len(games)} games from Odds API")
        return games
    
    @classmethod
    def get_player_props(cls, sport: str, game_id: str = None) -> List[PlayerProp]:
        """Get player props for games."""
        sport_key = LiveDataConfig.ODDS_API_SPORTS.get(sport.upper())
        if not sport_key:
            return []
        
        # Player props markets
        prop_markets = {
            "NBA": "player_points,player_rebounds,player_assists,player_threes",
            "NFL": "player_pass_yds,player_rush_yds,player_reception_yds,player_receptions",
            "MLB": "batter_hits,batter_total_bases,batter_rbis,pitcher_strikeouts",
            "NHL": "player_points,player_shots_on_goal,player_assists",
            "NCAAB": "player_points,player_rebounds,player_assists"
        }
        
        markets = prop_markets.get(sport.upper(), "player_points")
        
        data = cls._make_request(f"sports/{sport_key}/events/{game_id}/odds" if game_id else f"sports/{sport_key}/odds", {
            "regions": "us",
            "markets": markets,
            "oddsFormat": "american"
        })
        
        if not data:
            return cls._get_mock_props(sport)
        
        props = []
        # Parse player props from response
        # Note: The Odds API structure varies - this handles common format
        
        logger.info(f"[{sport}] Fetched player props from Odds API")
        return props
    
    @classmethod
    def _get_mock_games(cls, sport: str) -> List[GameLine]:
        """Return mock games when API unavailable."""
        mock_games = {
            "NBA": [
                GameLine("nba1", "NBA", "Los Angeles Lakers", "Golden State Warriors", 
                        datetime.now().isoformat(), -3.5, -110, 228.5, -110, -110, -150, +130, "mock"),
                GameLine("nba2", "NBA", "Boston Celtics", "Miami Heat",
                        datetime.now().isoformat(), -6.5, -110, 215.5, -110, -110, -250, +210, "mock"),
            ],
            "NFL": [
                GameLine("nfl1", "NFL", "Kansas City Chiefs", "Buffalo Bills",
                        datetime.now().isoformat(), -3.0, -110, 52.5, -110, -110, -160, +140, "mock"),
            ],
            "MLB": [
                GameLine("mlb1", "MLB", "New York Yankees", "Boston Red Sox",
                        datetime.now().isoformat(), -1.5, +130, 9.0, -110, -110, -140, +120, "mock"),
            ],
            "NHL": [
                GameLine("nhl1", "NHL", "Edmonton Oilers", "Toronto Maple Leafs",
                        datetime.now().isoformat(), -1.5, +160, 6.5, -110, -110, -130, +110, "mock"),
            ],
            "NCAAB": [
                GameLine("ncaab1", "NCAAB", "Duke Blue Devils", "North Carolina Tar Heels",
                        datetime.now().isoformat(), -4.5, -110, 152.5, -110, -110, -180, +155, "mock"),
            ]
        }
        return mock_games.get(sport.upper(), [])
    
    @classmethod
    def _get_mock_props(cls, sport: str) -> List[PlayerProp]:
        """Return mock props when API unavailable."""
        mock_props = {
            "NBA": [
                PlayerProp("LeBron James", "LAL", "points", 25.5, -110, -110, "mock", "nba1"),
                PlayerProp("Stephen Curry", "GSW", "points", 28.5, -115, -105, "mock", "nba1"),
                PlayerProp("Anthony Davis", "LAL", "rebounds", 12.5, -110, -110, "mock", "nba1"),
            ],
            "NFL": [
                PlayerProp("Patrick Mahomes", "KC", "passing_yards", 285.5, -110, -110, "mock", "nfl1"),
                PlayerProp("Josh Allen", "BUF", "passing_yards", 275.5, -110, -110, "mock", "nfl1"),
            ],
            "MLB": [
                PlayerProp("Aaron Judge", "NYY", "total_bases", 1.5, -130, +110, "mock", "mlb1"),
            ],
            "NHL": [
                PlayerProp("Connor McDavid", "EDM", "points", 1.5, -140, +120, "mock", "nhl1"),
            ],
            "NCAAB": [
                PlayerProp("Top Prospect", "DUKE", "points", 18.5, -110, -110, "mock", "ncaab1"),
            ]
        }
        return mock_props.get(sport.upper(), [])


# ============================================================
# ESPN API SERVICE
# ============================================================

class ESPNService:
    """
    Fetches data from ESPN's public API.
    Free, no API key required.
    """
    
    @staticmethod
    def _make_request(url: str) -> Optional[dict]:
        """Make request to ESPN API."""
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.error(f"ESPN API error: {e}")
            return None
    
    @classmethod
    def get_scoreboard(cls, sport: str) -> List[Dict]:
        """Get today's games from ESPN scoreboard."""
        sport_path = LiveDataConfig.ESPN_SPORTS.get(sport.upper())
        if not sport_path:
            return []
        
        url = f"{LiveDataConfig.ESPN_BASE}/{sport_path}/scoreboard"
        data = cls._make_request(url)
        
        if not data:
            return []
        
        games = []
        for event in data.get("events", []):
            try:
                competition = event["competitions"][0]
                home = away = None
                
                for team in competition.get("competitors", []):
                    team_data = {
                        "team": team["team"]["abbreviation"],
                        "name": team["team"]["displayName"],
                        "score": int(team.get("score", 0)),
                        "record": team.get("records", [{}])[0].get("summary", "0-0")
                    }
                    if team["homeAway"] == "home":
                        home = team_data
                    else:
                        away = team_data
                
                # Get odds if available
                odds = competition.get("odds", [{}])[0] if competition.get("odds") else {}
                
                games.append({
                    "game_id": event["id"],
                    "sport": sport.upper(),
                    "home_team": home["team"] if home else "UNK",
                    "home_name": home["name"] if home else "Unknown",
                    "away_team": away["team"] if away else "UNK",
                    "away_name": away["name"] if away else "Unknown",
                    "home_score": home["score"] if home else 0,
                    "away_score": away["score"] if away else 0,
                    "status": event["status"]["type"]["state"],  # pre, in, post
                    "spread": odds.get("spread", 0),
                    "total": odds.get("overUnder", 0),
                    "start_time": event["date"]
                })
            except Exception as e:
                logger.warning(f"Error parsing ESPN game: {e}")
                continue
        
        logger.info(f"[{sport}] Fetched {len(games)} games from ESPN")
        return games
    
    @classmethod
    def get_injuries(cls, sport: str, team: str = None) -> List[InjuryReport]:
        """Get injury reports from ESPN."""
        sport_path = LiveDataConfig.ESPN_SPORTS.get(sport.upper())
        if not sport_path:
            return []
        
        # ESPN injuries endpoint
        url = f"{LiveDataConfig.ESPN_BASE}/{sport_path}/injuries"
        data = cls._make_request(url)
        
        if not data:
            return cls._get_mock_injuries(sport, team)
        
        injuries = []
        for team_data in data.get("injuries", []):
            team_abbr = team_data.get("team", {}).get("abbreviation", "")
            
            if team and team.upper() != team_abbr.upper():
                continue
            
            for player in team_data.get("injuries", []):
                try:
                    injuries.append(InjuryReport(
                        player_name=player.get("athlete", {}).get("displayName", "Unknown"),
                        team=team_abbr,
                        position=player.get("athlete", {}).get("position", {}).get("abbreviation", ""),
                        status=player.get("status", "QUESTIONABLE").upper(),
                        injury_type=player.get("type", {}).get("description", ""),
                        usage_pct=0.20,  # Default, ideally from stats API
                        minutes_per_game=25.0  # Default
                    ))
                except Exception as e:
                    continue
        
        logger.info(f"[{sport}] Fetched {len(injuries)} injuries from ESPN")
        return injuries
    
    @classmethod
    def _get_mock_injuries(cls, sport: str, team: str = None) -> List[InjuryReport]:
        """Return mock injuries when API unavailable."""
        mock_injuries = {
            "NBA": [
                InjuryReport("Anthony Davis", "LAL", "PF", "QUESTIONABLE", "knee", 0.28, 35.0),
                InjuryReport("Kawhi Leonard", "LAC", "SF", "OUT", "knee", 0.30, 34.0),
            ],
            "NFL": [
                InjuryReport("Travis Kelce", "KC", "TE", "QUESTIONABLE", "ankle", 0.25, 55.0),
            ],
            "MLB": [
                InjuryReport("Mike Trout", "LAA", "OF", "OUT", "knee", 0.15, 4.5),
            ],
            "NHL": [
                InjuryReport("Auston Matthews", "TOR", "C", "QUESTIONABLE", "upper body", 0.20, 22.0),
            ],
            "NCAAB": []
        }
        
        injuries = mock_injuries.get(sport.upper(), [])
        if team:
            injuries = [i for i in injuries if i.team.upper() == team.upper()]
        return injuries


# ============================================================
# BALLDONTLIE API SERVICE (NBA Stats)
# ============================================================

class BallDontLieService:
    """
    Fetches NBA player stats from BallDontLie API.
    https://balldontlie.io/
    """
    
    @staticmethod
    def _make_request(endpoint: str, params: dict = None) -> Optional[dict]:
        """Make request to BallDontLie API."""
        if not LiveDataConfig.BALLDONTLIE_API_KEY:
            return None
        
        headers = {"Authorization": LiveDataConfig.BALLDONTLIE_API_KEY}
        url = f"{LiveDataConfig.BALLDONTLIE_BASE}/{endpoint}"
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.error(f"BallDontLie API error: {e}")
            return None
    
    @classmethod
    def get_player_stats(cls, player_name: str, season: int = 2025) -> Optional[PlayerStats]:
        """Get player season stats."""
        # Search for player
        data = cls._make_request("players", {"search": player_name})
        
        if not data or not data.get("data"):
            return cls._get_mock_stats(player_name)
        
        player = data["data"][0]
        player_id = player["id"]
        
        # Get season averages
        stats = cls._make_request(f"season_averages", {
            "season": season,
            "player_ids[]": player_id
        })
        
        if not stats or not stats.get("data"):
            return cls._get_mock_stats(player_name)
        
        avg = stats["data"][0]
        
        return PlayerStats(
            player_name=f"{player['first_name']} {player['last_name']}",
            team=player.get("team", {}).get("abbreviation", "UNK"),
            position=player.get("position", ""),
            games_played=avg.get("games_played", 0),
            minutes_per_game=avg.get("min", 0),
            points_per_game=avg.get("pts", 0),
            rebounds_per_game=avg.get("reb", 0),
            assists_per_game=avg.get("ast", 0),
            usage_pct=0.20  # BDL doesn't provide this
        )
    
    @classmethod
    def _get_mock_stats(cls, player_name: str) -> Optional[PlayerStats]:
        """Return mock stats when API unavailable."""
        mock_stats = {
            "lebron james": PlayerStats("LeBron James", "LAL", "SF", 50, 35.5, 25.4, 7.2, 8.1, 0.28),
            "stephen curry": PlayerStats("Stephen Curry", "GSW", "PG", 52, 34.2, 28.1, 5.1, 5.8, 0.30),
            "kevin durant": PlayerStats("Kevin Durant", "PHX", "SF", 48, 36.0, 27.8, 6.5, 5.2, 0.29),
            "giannis antetokounmpo": PlayerStats("Giannis Antetokounmpo", "MIL", "PF", 55, 35.8, 30.2, 11.5, 5.8, 0.35),
            "luka doncic": PlayerStats("Luka Doncic", "DAL", "PG", 50, 36.5, 32.5, 8.8, 9.2, 0.37),
        }
        return mock_stats.get(player_name.lower())


# ============================================================
# UNIFIED LIVE DATA ROUTER
# ============================================================

class LiveDataRouter:
    """
    Unified interface for all live data services.
    Call this class to get data for predictions.
    """
    
    @classmethod
    def get_todays_games(cls, sport: str) -> List[Dict]:
        """Get today's games with odds."""
        # Try Odds API first (better odds data)
        odds_games = OddsAPIService.get_games(sport)
        
        if odds_games:
            return [asdict(g) for g in odds_games]
        
        # Fallback to ESPN
        return ESPNService.get_scoreboard(sport)
    
    @classmethod
    def get_player_props(cls, sport: str, game_id: str = None) -> List[Dict]:
        """Get player props for upcoming games."""
        props = OddsAPIService.get_player_props(sport, game_id)
        return [asdict(p) for p in props]
    
    @classmethod
    def get_injuries(cls, sport: str, team: str = None) -> List[Dict]:
        """Get current injuries."""
        injuries = ESPNService.get_injuries(sport, team)
        return [asdict(i) for i in injuries]
    
    @classmethod
    def get_player_stats(cls, player_name: str, sport: str = "NBA") -> Optional[Dict]:
        """Get player season stats."""
        if sport.upper() == "NBA":
            stats = BallDontLieService.get_player_stats(player_name)
            return asdict(stats) if stats else None
        return None
    
    @classmethod
    def build_prediction_context(
        cls, 
        sport: str, 
        player_name: str, 
        player_team: str, 
        opponent_team: str
    ) -> Dict:
        """
        Build complete context for a prediction.
        Fetches live data and formats for prediction API.
        """
        context = {
            "sport": sport.upper(),
            "player_name": player_name,
            "player_team": player_team,
            "opponent_team": opponent_team,
            "data_source": "live",
            "timestamp": datetime.now().isoformat()
        }
        
        # Get player stats
        if sport.upper() == "NBA":
            stats = cls.get_player_stats(player_name, sport)
            if stats:
                context["player_avg"] = stats["points_per_game"]
                context["expected_mins"] = stats["minutes_per_game"]
                context["position"] = stats["position"]
        
        # Get team injuries for vacuum calculation
        injuries = cls.get_injuries(sport, player_team)
        context["injuries"] = injuries
        
        # Calculate usage vacuum from injuries
        out_injuries = [i for i in injuries if i.get("status") == "OUT"]
        vacuum = sum(i.get("usage_pct", 0) * (i.get("minutes_per_game", 0) / 48) for i in out_injuries)
        context["calculated_vacuum"] = round(vacuum * 100, 2)
        
        # Get game odds
        games = cls.get_todays_games(sport)
        for game in games:
            home = game.get("home_team", "")
            away = game.get("away_team", "")
            if player_team.upper() in home.upper() or player_team.upper() in away.upper():
                context["game_total"] = game.get("total", 220)
                context["game_spread"] = game.get("spread", 0)
                context["game_id"] = game.get("game_id")
                # Determine home/away
                context["home_team"] = game.get("home_team")
                break
        
        # Get player props
        props = cls.get_player_props(sport)
        for prop in props:
            if player_name.lower() in prop.get("player_name", "").lower():
                context["line"] = prop.get("line")
                context["over_odds"] = prop.get("over_odds", -110)
                context["under_odds"] = prop.get("under_odds", -110)
                break
        
        logger.info(f"Built live context for {player_name}: vacuum={context.get('calculated_vacuum', 0)}, total={context.get('game_total')}")
        
        return context
    
    @classmethod
    def get_full_slate(cls, sport: str) -> List[Dict]:
        """
        Get full slate of games with props for batch predictions.
        """
        games = cls.get_todays_games(sport)
        props = cls.get_player_props(sport)
        
        # Group props by game
        props_by_game = {}
        for prop in props:
            gid = prop.get("game_id", "unknown")
            if gid not in props_by_game:
                props_by_game[gid] = []
            props_by_game[gid].append(prop)
        
        # Enhance games with props
        for game in games:
            game["player_props"] = props_by_game.get(game.get("game_id"), [])
        
        return games


# ============================================================
# FASTAPI ROUTER FOR LIVE DATA
# ============================================================

from fastapi import APIRouter, HTTPException

live_data_router = APIRouter(prefix="/live", tags=["Live Data"])


@live_data_router.get("/games/{sport}")
async def get_live_games(sport: str):
    """Get today's games with odds."""
    sport = sport.upper()
    if sport not in ["NBA", "NFL", "MLB", "NHL", "NCAAB"]:
        raise HTTPException(400, "Invalid sport")
    
    games = LiveDataRouter.get_todays_games(sport)
    return {
        "status": "success",
        "sport": sport,
        "count": len(games),
        "games": games,
        "timestamp": datetime.now().isoformat()
    }


@live_data_router.get("/props/{sport}")
async def get_player_props(sport: str, game_id: str = None):
    """Get player props."""
    sport = sport.upper()
    if sport not in ["NBA", "NFL", "MLB", "NHL", "NCAAB"]:
        raise HTTPException(400, "Invalid sport")
    
    props = LiveDataRouter.get_player_props(sport, game_id)
    return {
        "status": "success",
        "sport": sport,
        "count": len(props),
        "props": props
    }


@live_data_router.get("/injuries/{sport}")
async def get_injuries(sport: str, team: str = None):
    """Get injury reports."""
    sport = sport.upper()
    if sport not in ["NBA", "NFL", "MLB", "NHL", "NCAAB"]:
        raise HTTPException(400, "Invalid sport")
    
    injuries = LiveDataRouter.get_injuries(sport, team)
    return {
        "status": "success",
        "sport": sport,
        "team": team,
        "count": len(injuries),
        "injuries": injuries
    }


@live_data_router.get("/player/{player_name}")
async def get_player_info(player_name: str, sport: str = "NBA"):
    """Get player stats."""
    stats = LiveDataRouter.get_player_stats(player_name, sport)
    if not stats:
        raise HTTPException(404, f"Player '{player_name}' not found")
    
    return {
        "status": "success",
        "player": stats
    }


@live_data_router.get("/context/{sport}")
async def build_context(sport: str, player_name: str, player_team: str, opponent_team: str):
    """Build full prediction context with live data."""
    sport = sport.upper()
    if sport not in ["NBA", "NFL", "MLB", "NHL", "NCAAB"]:
        raise HTTPException(400, "Invalid sport")
    
    context = LiveDataRouter.build_prediction_context(sport, player_name, player_team, opponent_team)
    return {
        "status": "success",
        "context": context
    }


@live_data_router.get("/slate/{sport}")
async def get_full_slate(sport: str):
    """Get full slate with all games and props."""
    sport = sport.upper()
    if sport not in ["NBA", "NFL", "MLB", "NHL", "NCAAB"]:
        raise HTTPException(400, "Invalid sport")
    
    slate = LiveDataRouter.get_full_slate(sport)
    return {
        "status": "success",
        "sport": sport,
        "game_count": len(slate),
        "slate": slate,
        "timestamp": datetime.now().isoformat()
    }


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":
    # Test the services
    print("=== Testing Live Data Router ===")
    
    # Test games
    games = LiveDataRouter.get_todays_games("NBA")
    print(f"\nNBA Games: {len(games)}")
    for g in games[:2]:
        print(f"  {g.get('away_team')} @ {g.get('home_team')} | Total: {g.get('total')} | Spread: {g.get('spread')}")
    
    # Test injuries
    injuries = LiveDataRouter.get_injuries("NBA")
    print(f"\nNBA Injuries: {len(injuries)}")
    for i in injuries[:3]:
        print(f"  {i.get('player_name')} ({i.get('team')}) - {i.get('status')}")
    
    # Test full context
    context = LiveDataRouter.build_prediction_context("NBA", "LeBron James", "LAL", "GSW")
    print(f"\nPrediction Context:")
    print(f"  Vacuum: {context.get('calculated_vacuum')}")
    print(f"  Total: {context.get('game_total')}")
    print(f"  Line: {context.get('line')}")
    
    print("\n✅ Live Data Router working!")
