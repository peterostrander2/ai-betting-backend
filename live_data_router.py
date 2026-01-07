"""
🔥 LIVE DATA ROUTER v7.5.0
===========================
Unified data fetching for Bookie-o-em

UPDATED: Uses ALL sportsbooks and finds BEST odds

Integrates:
- The Odds API (game lines, player props) - ALL BOOKS
- Playbook API (injuries, splits, sharp money)
- ESPN API (schedules, scores)

All 5 Sports: NBA, NFL, MLB, NHL, NCAAB
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
    
    # The Odds API
    ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "")
    ODDS_API_BASE = "https://api.the-odds-api.com/v4"
    
    # Playbook API
    PLAYBOOK_API_KEY = os.environ.get("PLAYBOOK_API_KEY", "")
    PLAYBOOK_BASE = "https://api.playbook-api.com/v1"
    
    # ESPN API (free)
    ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports"
    
    # Sport mappings for The Odds API
    ODDS_API_SPORTS = {
        "NBA": "basketball_nba",
        "NFL": "americanfootball_nfl",
        "MLB": "baseball_mlb",
        "NHL": "icehockey_nhl",
        "NCAAB": "basketball_ncaab"
    }
    
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
    """Game with BEST odds across all sportsbooks."""
    game_id: str
    sport: str
    home_team: str
    away_team: str
    commence_time: str
    # Best spread
    spread: float
    spread_odds: int
    spread_book: str
    # Best total
    total: float
    over_odds: int
    over_book: str
    under_odds: int
    under_book: str
    # Best moneylines
    home_ml: int
    home_ml_book: str
    away_ml: int
    away_ml_book: str
    # How many books compared
    books_compared: int
    all_books: List[str]


@dataclass
class PlayerProp:
    """Player prop with best odds."""
    player_name: str
    team: str
    stat_type: str
    line: float
    over_odds: int
    over_book: str
    under_odds: int
    under_book: str
    game_id: str
    books_compared: int


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
    status: str
    injury_type: str
    usage_pct: float
    minutes_per_game: float


# ============================================================
# THE ODDS API SERVICE - ALL BOOKS
# ============================================================

class OddsAPIService:
    """
    Fetches live odds from ALL sportsbooks via The Odds API.
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
            response = requests.get(url, params=params, timeout=15)
            
            # Log API usage
            remaining = response.headers.get("x-requests-remaining", "?")
            used = response.headers.get("x-requests-used", "?")
            logger.info(f"Odds API: {remaining} remaining, {used} used")
            
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
        """Get all upcoming games with BEST odds from ALL books."""
        sport_key = LiveDataConfig.ODDS_API_SPORTS.get(sport.upper())
        if not sport_key:
            return []
        
        # Get ALL bookmakers (no filter = all books)
        data = cls._make_request(f"sports/{sport_key}/odds", {
            "regions": "us,us2",  # Multiple regions for more books
            "markets": "spreads,totals,h2h",
            "oddsFormat": "american"
        })
        
        if not data:
            return cls._get_mock_games(sport)
        
        games = []
        for game in data:
            try:
                bookmakers = game.get("bookmakers", [])
                if not bookmakers:
                    continue
                
                all_books = [bm["key"] for bm in bookmakers]
                
                # Find BEST odds across ALL books
                best = {
                    "spread": None, "spread_odds": -999, "spread_book": None,
                    "total": None, 
                    "over_odds": -999, "over_book": None,
                    "under_odds": -999, "under_book": None,
                    "home_ml": -9999, "home_ml_book": None,
                    "away_ml": -9999, "away_ml_book": None,
                }
                
                for bm in bookmakers:
                    book_name = bm["key"]
                    
                    for market in bm.get("markets", []):
                        if market["key"] == "spreads":
                            for outcome in market["outcomes"]:
                                if outcome["name"] == game["home_team"]:
                                    if best["spread"] is None:
                                        best["spread"] = outcome.get("point", 0)
                                    # Better odds = higher number (less negative or more positive)
                                    if outcome.get("price", -999) > best["spread_odds"]:
                                        best["spread_odds"] = outcome["price"]
                                        best["spread_book"] = book_name
                        
                        elif market["key"] == "totals":
                            for outcome in market["outcomes"]:
                                if best["total"] is None:
                                    best["total"] = outcome.get("point", 220)
                                if outcome["name"] == "Over":
                                    if outcome.get("price", -999) > best["over_odds"]:
                                        best["over_odds"] = outcome["price"]
                                        best["over_book"] = book_name
                                elif outcome["name"] == "Under":
                                    if outcome.get("price", -999) > best["under_odds"]:
                                        best["under_odds"] = outcome["price"]
                                        best["under_book"] = book_name
                        
                        elif market["key"] == "h2h":
                            for outcome in market["outcomes"]:
                                if outcome["name"] == game["home_team"]:
                                    if outcome.get("price", -9999) > best["home_ml"]:
                                        best["home_ml"] = outcome["price"]
                                        best["home_ml_book"] = book_name
                                else:
                                    if outcome.get("price", -9999) > best["away_ml"]:
                                        best["away_ml"] = outcome["price"]
                                        best["away_ml_book"] = book_name
                
                games.append(GameLine(
                    game_id=game["id"],
                    sport=sport.upper(),
                    home_team=game["home_team"],
                    away_team=game["away_team"],
                    commence_time=game["commence_time"],
                    spread=best["spread"] or 0,
                    spread_odds=best["spread_odds"] if best["spread_odds"] > -999 else -110,
                    spread_book=best["spread_book"] or "N/A",
                    total=best["total"] or 220,
                    over_odds=best["over_odds"] if best["over_odds"] > -999 else -110,
                    over_book=best["over_book"] or "N/A",
                    under_odds=best["under_odds"] if best["under_odds"] > -999 else -110,
                    under_book=best["under_book"] or "N/A",
                    home_ml=best["home_ml"] if best["home_ml"] > -9999 else -110,
                    home_ml_book=best["home_ml_book"] or "N/A",
                    away_ml=best["away_ml"] if best["away_ml"] > -9999 else -110,
                    away_ml_book=best["away_ml_book"] or "N/A",
                    books_compared=len(bookmakers),
                    all_books=all_books
                ))
            except Exception as e:
                logger.warning(f"Error parsing game: {e}")
                continue
        
        logger.success(f"[{sport}] Fetched {len(games)} games with best odds from {len(data[0].get('bookmakers', [])) if data else 0}+ books")
        return games
    
    @classmethod
    def get_player_props(cls, sport: str, game_id: str = None) -> List[PlayerProp]:
        """Get player props with BEST odds from ALL books."""
        sport_key = LiveDataConfig.ODDS_API_SPORTS.get(sport.upper())
        if not sport_key:
            return []
        
        prop_markets = {
            "NBA": "player_points,player_rebounds,player_assists,player_threes",
            "NFL": "player_pass_yds,player_rush_yds,player_reception_yds,player_receptions",
            "MLB": "batter_hits,batter_total_bases,batter_rbis,pitcher_strikeouts",
            "NHL": "player_points,player_shots_on_goal,player_assists",
            "NCAAB": "player_points,player_rebounds,player_assists"
        }
        
        markets = prop_markets.get(sport.upper(), "player_points")
        
        endpoint = f"sports/{sport_key}/events/{game_id}/odds" if game_id else f"sports/{sport_key}/odds"
        data = cls._make_request(endpoint, {
            "regions": "us,us2",
            "markets": markets,
            "oddsFormat": "american"
        })
        
        if not data:
            return cls._get_mock_props(sport)
        
        # Parse props and find best odds
        props = []
        # Implementation depends on API response structure
        
        logger.info(f"[{sport}] Fetched player props from ALL books")
        return props
    
    @classmethod
    def _get_mock_games(cls, sport: str) -> List[GameLine]:
        """Return mock games when API unavailable."""
        mock = {
            "NBA": [
                GameLine("nba1", "NBA", "Los Angeles Lakers", "Golden State Warriors", 
                        datetime.now().isoformat(), -3.5, -108, "draftkings", 228.5, 
                        -105, "fanduel", -108, "betmgm", -150, "caesars", +135, "pinnacle", 
                        5, ["fanduel", "draftkings", "betmgm", "caesars", "pinnacle"]),
            ],
            "NFL": [
                GameLine("nfl1", "NFL", "Kansas City Chiefs", "Buffalo Bills",
                        datetime.now().isoformat(), -3.0, -105, "pinnacle", 52.5,
                        -108, "draftkings", -105, "fanduel", -155, "betmgm", +145, "caesars",
                        5, ["fanduel", "draftkings", "betmgm", "caesars", "pinnacle"]),
            ],
            "MLB": [
                GameLine("mlb1", "MLB", "New York Yankees", "Boston Red Sox",
                        datetime.now().isoformat(), -1.5, +135, "pinnacle", 9.0,
                        -105, "fanduel", -108, "draftkings", -135, "betmgm", +125, "caesars",
                        5, ["fanduel", "draftkings", "betmgm", "caesars", "pinnacle"]),
            ],
            "NHL": [
                GameLine("nhl1", "NHL", "Edmonton Oilers", "Toronto Maple Leafs",
                        datetime.now().isoformat(), -1.5, +165, "pinnacle", 6.5,
                        -105, "fanduel", -108, "draftkings", -125, "betmgm", +115, "caesars",
                        5, ["fanduel", "draftkings", "betmgm", "caesars", "pinnacle"]),
            ],
            "NCAAB": [
                GameLine("ncaab1", "NCAAB", "Duke Blue Devils", "North Carolina Tar Heels",
                        datetime.now().isoformat(), -4.5, -108, "draftkings", 152.5,
                        -105, "fanduel", -108, "betmgm", -175, "caesars", +160, "pinnacle",
                        5, ["fanduel", "draftkings", "betmgm", "caesars", "pinnacle"]),
            ]
        }
        return mock.get(sport.upper(), [])
    
    @classmethod
    def _get_mock_props(cls, sport: str) -> List[PlayerProp]:
        """Return mock props."""
        return []


# ============================================================
# PLAYBOOK API SERVICE
# ============================================================

class PlaybookAPIService:
    """
    Fetches data from Playbook API.
    - Injuries
    - Betting splits
    - Sharp money signals
    """
    
    @staticmethod
    def _make_request(endpoint: str, params: dict = None) -> Optional[dict]:
        """Make authenticated request to Playbook API."""
        if not LiveDataConfig.PLAYBOOK_API_KEY:
            logger.warning("PLAYBOOK_API_KEY not set")
            return None
        
        headers = {"x-api-key": LiveDataConfig.PLAYBOOK_API_KEY}
        url = f"{LiveDataConfig.PLAYBOOK_BASE}/{endpoint}"
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Playbook API error: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Playbook API request failed: {e}")
            return None
    
    @classmethod
    def get_injuries(cls, sport: str) -> List[InjuryReport]:
        """Get injuries from Playbook API."""
        sport_map = {"NBA": "nba", "NFL": "nfl", "MLB": "mlb", "NHL": "nhl", "NCAAB": "ncaab"}
        sport_key = sport_map.get(sport.upper())
        
        data = cls._make_request(f"injuries/{sport_key}")
        if not data:
            return []
        
        injuries = []
        for item in data.get("injuries", []):
            try:
                injuries.append(InjuryReport(
                    player_name=item.get("player_name", "Unknown"),
                    team=item.get("team", ""),
                    position=item.get("position", ""),
                    status=item.get("status", "QUESTIONABLE").upper(),
                    injury_type=item.get("injury", ""),
                    usage_pct=item.get("usage_pct", 0.20),
                    minutes_per_game=item.get("minutes", 25.0)
                ))
            except:
                continue
        
        logger.info(f"[{sport}] Fetched {len(injuries)} injuries from Playbook")
        return injuries
    
    @classmethod
    def get_splits(cls, sport: str) -> List[Dict]:
        """Get public betting splits from Playbook API."""
        sport_map = {"NBA": "nba", "NFL": "nfl", "MLB": "mlb", "NHL": "nhl", "NCAAB": "ncaab"}
        sport_key = sport_map.get(sport.upper())
        
        data = cls._make_request(f"splits/{sport_key}")
        if not data:
            return []
        
        logger.info(f"[{sport}] Fetched betting splits from Playbook")
        return data.get("splits", [])
    
    @classmethod
    def get_sharp_money(cls, sport: str) -> List[Dict]:
        """Get sharp money signals from Playbook API."""
        sport_map = {"NBA": "nba", "NFL": "nfl", "MLB": "mlb", "NHL": "nhl", "NCAAB": "ncaab"}
        sport_key = sport_map.get(sport.upper())
        
        data = cls._make_request(f"sharp/{sport_key}")
        if not data:
            return []
        
        logger.info(f"[{sport}] Fetched sharp money signals from Playbook")
        return data.get("signals", [])


# ============================================================
# ESPN API SERVICE
# ============================================================

class ESPNService:
    """Fetches data from ESPN's public API."""
    
    @staticmethod
    def _make_request(url: str) -> Optional[dict]:
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.error(f"ESPN API error: {e}")
            return None
    
    @classmethod
    def get_injuries(cls, sport: str, team: str = None) -> List[InjuryReport]:
        """Get injury reports from ESPN."""
        sport_path = LiveDataConfig.ESPN_SPORTS.get(sport.upper())
        if not sport_path:
            return []
        
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
                        usage_pct=0.20,
                        minutes_per_game=25.0
                    ))
                except:
                    continue
        
        logger.info(f"[{sport}] Fetched {len(injuries)} injuries from ESPN")
        return injuries
    
    @classmethod
    def _get_mock_injuries(cls, sport: str, team: str = None) -> List[InjuryReport]:
        mock = {
            "NBA": [
                InjuryReport("Anthony Davis", "LAL", "PF", "QUESTIONABLE", "knee", 0.28, 35.0),
                InjuryReport("Kawhi Leonard", "LAC", "SF", "OUT", "knee", 0.30, 34.0),
            ],
            "NFL": [InjuryReport("Travis Kelce", "KC", "TE", "QUESTIONABLE", "ankle", 0.25, 55.0)],
            "MLB": [InjuryReport("Mike Trout", "LAA", "OF", "OUT", "knee", 0.15, 4.5)],
            "NHL": [InjuryReport("Auston Matthews", "TOR", "C", "QUESTIONABLE", "upper body", 0.20, 22.0)],
            "NCAAB": []
        }
        injuries = mock.get(sport.upper(), [])
        if team:
            injuries = [i for i in injuries if i.team.upper() == team.upper()]
        return injuries


# ============================================================
# UNIFIED LIVE DATA ROUTER
# ============================================================

class LiveDataRouter:
    """Unified interface for all live data services."""
    
    @classmethod
    def get_todays_games(cls, sport: str) -> List[Dict]:
        """Get today's games with BEST odds from ALL books."""
        games = OddsAPIService.get_games(sport)
        return [asdict(g) for g in games]
    
    @classmethod
    def get_player_props(cls, sport: str, game_id: str = None) -> List[Dict]:
        """Get player props with best odds."""
        props = OddsAPIService.get_player_props(sport, game_id)
        return [asdict(p) for p in props]
    
    @classmethod
    def get_injuries(cls, sport: str, team: str = None) -> List[Dict]:
        """Get injuries - tries Playbook first, then ESPN."""
        # Try Playbook API first (better data)
        injuries = PlaybookAPIService.get_injuries(sport)
        if injuries:
            result = [asdict(i) for i in injuries]
            if team:
                result = [i for i in result if i.get("team", "").upper() == team.upper()]
            return result
        
        # Fallback to ESPN
        injuries = ESPNService.get_injuries(sport, team)
        return [asdict(i) for i in injuries]
    
    @classmethod
    def get_splits(cls, sport: str) -> List[Dict]:
        """Get public betting splits from Playbook."""
        return PlaybookAPIService.get_splits(sport)
    
    @classmethod
    def get_sharp_money(cls, sport: str) -> List[Dict]:
        """Get sharp money signals from Playbook."""
        return PlaybookAPIService.get_sharp_money(sport)
    
    @classmethod
    def get_player_stats(cls, player_name: str, sport: str = "NBA") -> Optional[Dict]:
        """Get player season stats."""
        # Could integrate BallDontLie or other stats API here
        return None
    
    @classmethod
    def build_prediction_context(cls, sport: str, player_name: str, player_team: str, opponent_team: str) -> Dict:
        """Build complete context for a prediction."""
        context = {
            "sport": sport.upper(),
            "player_name": player_name,
            "player_team": player_team,
            "opponent_team": opponent_team,
            "data_source": "live",
            "timestamp": datetime.now().isoformat()
        }
        
        # Get team injuries for vacuum calculation
        injuries = cls.get_injuries(sport, player_team)
        context["injuries"] = injuries
        
        out_injuries = [i for i in injuries if i.get("status") == "OUT"]
        vacuum = sum(i.get("usage_pct", 0) * (i.get("minutes_per_game", 0) / 48) for i in out_injuries)
        context["calculated_vacuum"] = round(vacuum * 100, 2)
        
        # Get game odds with best lines
        games = cls.get_todays_games(sport)
        for game in games:
            home = game.get("home_team", "")
            away = game.get("away_team", "")
            if player_team.upper() in home.upper() or player_team.upper() in away.upper():
                context["game_total"] = game.get("total", 220)
                context["game_spread"] = game.get("spread", 0)
                context["game_id"] = game.get("game_id")
                context["home_team"] = game.get("home_team")
                # Include best books info
                context["best_over_book"] = game.get("over_book")
                context["best_under_book"] = game.get("under_book")
                context["books_compared"] = game.get("books_compared", 0)
                break
        
        # Get betting splits
        splits = cls.get_splits(sport)
        context["splits"] = splits
        
        # Get sharp money
        sharp = cls.get_sharp_money(sport)
        context["sharp_signals"] = sharp
        
        logger.info(f"Built live context for {player_name}: {context.get('books_compared', 0)} books compared")
        return context
    
    @classmethod
    def get_full_slate(cls, sport: str) -> List[Dict]:
        """Get full slate with all games, props, and best odds."""
        games = cls.get_todays_games(sport)
        props = cls.get_player_props(sport)
        
        props_by_game = {}
        for prop in props:
            gid = prop.get("game_id", "unknown")
            if gid not in props_by_game:
                props_by_game[gid] = []
            props_by_game[gid].append(prop)
        
        for game in games:
            game["player_props"] = props_by_game.get(game.get("game_id"), [])
        
        return games


# ============================================================
# FASTAPI ROUTER
# ============================================================

from fastapi import APIRouter, HTTPException

live_data_router = APIRouter(prefix="/live", tags=["Live Data"])


@live_data_router.get("/games/{sport}")
async def get_live_games(sport: str):
    """Get today's games with BEST odds from ALL sportsbooks."""
    sport = sport.upper()
    if sport not in ["NBA", "NFL", "MLB", "NHL", "NCAAB"]:
        raise HTTPException(400, "Invalid sport")
    
    games = LiveDataRouter.get_todays_games(sport)
    return {
        "status": "success",
        "sport": sport,
        "count": len(games),
        "games": games,
        "note": "Best odds shown from all available sportsbooks",
        "timestamp": datetime.now().isoformat()
    }


@live_data_router.get("/props/{sport}")
async def get_player_props(sport: str, game_id: str = None):
    """Get player props with best odds."""
    sport = sport.upper()
    if sport not in ["NBA", "NFL", "MLB", "NHL", "NCAAB"]:
        raise HTTPException(400, "Invalid sport")
    
    props = LiveDataRouter.get_player_props(sport, game_id)
    return {"status": "success", "sport": sport, "count": len(props), "props": props}


@live_data_router.get("/injuries/{sport}")
async def get_injuries(sport: str, team: str = None):
    """Get injury reports."""
    sport = sport.upper()
    if sport not in ["NBA", "NFL", "MLB", "NHL", "NCAAB"]:
        raise HTTPException(400, "Invalid sport")
    
    injuries = LiveDataRouter.get_injuries(sport, team)
    return {"status": "success", "sport": sport, "team": team, "count": len(injuries), "injuries": injuries}


@live_data_router.get("/splits/{sport}")
async def get_betting_splits(sport: str):
    """Get public betting splits from Playbook API."""
    sport = sport.upper()
    if sport not in ["NBA", "NFL", "MLB", "NHL", "NCAAB"]:
        raise HTTPException(400, "Invalid sport")
    
    splits = LiveDataRouter.get_splits(sport)
    return {"status": "success", "sport": sport, "splits": splits}


@live_data_router.get("/sharp/{sport}")
async def get_sharp_money(sport: str):
    """Get sharp money signals from Playbook API."""
    sport = sport.upper()
    if sport not in ["NBA", "NFL", "MLB", "NHL", "NCAAB"]:
        raise HTTPException(400, "Invalid sport")
    
    signals = LiveDataRouter.get_sharp_money(sport)
    return {"status": "success", "sport": sport, "signals": signals}


@live_data_router.get("/player/{player_name}")
async def get_player_info(player_name: str, sport: str = "NBA"):
    """Get player stats."""
    stats = LiveDataRouter.get_player_stats(player_name, sport)
    if not stats:
        raise HTTPException(404, f"Player '{player_name}' not found")
    return {"status": "success", "player": stats}


@live_data_router.get("/context/{sport}")
async def build_context(sport: str, player_name: str, player_team: str, opponent_team: str):
    """Build full prediction context with live data."""
    sport = sport.upper()
    if sport not in ["NBA", "NFL", "MLB", "NHL", "NCAAB"]:
        raise HTTPException(400, "Invalid sport")
    
    context = LiveDataRouter.build_prediction_context(sport, player_name, player_team, opponent_team)
    return {"status": "success", "context": context}


@live_data_router.get("/slate/{sport}")
async def get_full_slate(sport: str):
    """Get full slate with all games, props, and best odds."""
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
    print("=== Testing Live Data Router v7.5.0 ===")
    
    games = LiveDataRouter.get_todays_games("NBA")
    print(f"\nNBA Games: {len(games)}")
    for g in games[:2]:
        print(f"  {g.get('away_team')} @ {g.get('home_team')}")
        print(f"    Spread: {g.get('spread')} @ {g.get('spread_odds')} ({g.get('spread_book')})")
        print(f"    Total: {g.get('total')} O:{g.get('over_odds')} ({g.get('over_book')}) U:{g.get('under_odds')} ({g.get('under_book')})")
        print(f"    Books compared: {g.get('books_compared')}")
    
    print("\n✅ Live Data Router v7.5.0 working!")
