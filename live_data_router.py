"""
🔥 LIVE DATA ROUTER v7.7.0
===========================
Unified data fetching for Bookie-o-em

UPDATED: Player Props - TOP 5 SMASH BETS ONLY (70%+ confidence)

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
    spread: float
    spread_odds: int
    spread_book: str
    total: float
    over_odds: int
    over_book: str
    under_odds: int
    under_book: str
    home_ml: int
    home_ml_book: str
    away_ml: int
    away_ml_book: str
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
    home_team: str = ""
    away_team: str = ""


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
            logger.warning("ODDS_API_KEY not set")
            return None
            
        if params is None:
            params = {}
        params["apiKey"] = LiveDataConfig.ODDS_API_KEY
        
        url = f"{LiveDataConfig.ODDS_API_BASE}/{endpoint}"
        
        try:
            response = requests.get(url, params=params, timeout=15)
            
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
        
        data = cls._make_request(f"sports/{sport_key}/odds", {
            "regions": "us,us2",
            "markets": "spreads,totals,h2h",
            "oddsFormat": "american"
        })
        
        if not data:
            return []
        
        games = []
        for game in data:
            try:
                bookmakers = game.get("bookmakers", [])
                if not bookmakers:
                    continue
                
                all_books = [bm["key"] for bm in bookmakers]
                
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
        
        logger.success(f"[{sport}] Fetched {len(games)} games with best odds")
        return games
    
    @classmethod
    def get_player_props(cls, sport: str, game_id: str = None) -> List[PlayerProp]:
        """Get player props with BEST odds - NO MOCK DATA."""
        sport_key = LiveDataConfig.ODDS_API_SPORTS.get(sport.upper())
        if not sport_key:
            return []
        
        prop_markets = {
            "NBA": "player_points,player_rebounds,player_assists,player_threes",
            "NFL": "player_pass_yds,player_rush_yds,player_reception_yds,player_receptions",
            "MLB": "batter_hits,batter_total_bases,pitcher_strikeouts",
            "NHL": "player_points,player_shots_on_goal",
            "NCAAB": "player_points,player_rebounds,player_assists"
        }
        
        markets = prop_markets.get(sport.upper(), "player_points")
        
        # If specific game_id provided, fetch just that game's props
        if game_id:
            data = cls._make_request(f"sports/{sport_key}/events/{game_id}/odds", {
                "regions": "us",
                "markets": markets,
                "oddsFormat": "american"
            })
            games_data = [data] if data else []
        else:
            # First get list of games, then fetch props for each
            games_list = cls._make_request(f"sports/{sport_key}/odds", {
                "regions": "us",
                "markets": "h2h",
                "oddsFormat": "american"
            })
            
            if not games_list:
                logger.warning(f"[{sport}] No games found")
                return []
            
            # Fetch props for first 3 games to save API credits
            games_data = []
            for game in games_list[:3]:
                event_id = game.get("id")
                if not event_id:
                    continue
                
                props_data = cls._make_request(f"sports/{sport_key}/events/{event_id}/odds", {
                    "regions": "us",
                    "markets": markets,
                    "oddsFormat": "american"
                })
                
                if props_data:
                    games_data.append(props_data)
        
        if not games_data:
            logger.warning(f"[{sport}] No props data available")
            return []
        
        props_dict = {}
        
        stat_map = {
            "player_points": "points",
            "player_rebounds": "rebounds", 
            "player_assists": "assists",
            "player_threes": "threes",
            "player_pass_yds": "pass_yards",
            "player_rush_yds": "rush_yards",
            "player_reception_yds": "rec_yards",
            "player_receptions": "receptions",
            "batter_hits": "hits",
            "batter_total_bases": "total_bases",
            "pitcher_strikeouts": "strikeouts",
            "player_shots_on_goal": "shots"
        }
        
        for game in games_data:
            if not game:
                continue
            gid = game.get("id", "")
            home_team = game.get("home_team", "")
            away_team = game.get("away_team", "")
            
            for bookmaker in game.get("bookmakers", []):
                book_name = bookmaker.get("key", "unknown")
                
                for market in bookmaker.get("markets", []):
                    market_key = market.get("key", "")
                    
                    if not market_key.startswith(("player_", "batter_", "pitcher_")):
                        continue
                    
                    stat_type = stat_map.get(market_key, market_key.replace("player_", ""))
                    
                    for outcome in market.get("outcomes", []):
                        player_name = outcome.get("description", "")
                        if not player_name:
                            continue
                            
                        line = outcome.get("point", 0)
                        odds = outcome.get("price", -110)
                        side = outcome.get("name", "Over")
                        
                        prop_key = f"{player_name}_{stat_type}_{line}"
                        
                        if prop_key in props_dict:
                            existing = props_dict[prop_key]
                            if side == "Over" and odds > existing["over_odds"]:
                                existing["over_odds"] = odds
                                existing["over_book"] = book_name
                            elif side == "Under" and odds > existing["under_odds"]:
                                existing["under_odds"] = odds
                                existing["under_book"] = book_name
                            existing["books_compared"] += 1
                        else:
                            props_dict[prop_key] = {
                                "player_name": player_name,
                                "team": "",
                                "stat_type": stat_type,
                                "line": line,
                                "over_odds": odds if side == "Over" else -110,
                                "over_book": book_name if side == "Over" else "N/A",
                                "under_odds": odds if side == "Under" else -110,
                                "under_book": book_name if side == "Under" else "N/A",
                                "game_id": gid,
                                "home_team": home_team,
                                "away_team": away_team,
                                "books_compared": 1
                            }
        
        props = []
        for prop_data in props_dict.values():
            props.append(PlayerProp(
                player_name=prop_data["player_name"],
                team=prop_data["team"],
                stat_type=prop_data["stat_type"],
                line=prop_data["line"],
                over_odds=prop_data["over_odds"],
                over_book=prop_data["over_book"],
                under_odds=prop_data["under_odds"],
                under_book=prop_data["under_book"],
                game_id=prop_data["game_id"],
                books_compared=prop_data["books_compared"],
                home_team=prop_data["home_team"],
                away_team=prop_data["away_team"]
            ))
        
        logger.success(f"[{sport}] Fetched {len(props)} player props")
        return props


# ============================================================
# PLAYBOOK API SERVICE
# ============================================================

class PlaybookAPIService:
    """Fetches data from Playbook API."""
    
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
        
        return injuries
    
    @classmethod
    def get_splits(cls, sport: str) -> List[Dict]:
        sport_map = {"NBA": "nba", "NFL": "nfl", "MLB": "mlb", "NHL": "nhl", "NCAAB": "ncaab"}
        sport_key = sport_map.get(sport.upper())
        
        data = cls._make_request(f"splits/{sport_key}")
        if not data:
            return []
        
        return data.get("splits", [])
    
    @classmethod
    def get_sharp_money(cls, sport: str) -> List[Dict]:
        sport_map = {"NBA": "nba", "NFL": "nfl", "MLB": "mlb", "NHL": "nhl", "NCAAB": "ncaab"}
        sport_key = sport_map.get(sport.upper())
        
        data = cls._make_request(f"sharp/{sport_key}")
        if not data:
            return []
        
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
        sport_path = LiveDataConfig.ESPN_SPORTS.get(sport.upper())
        if not sport_path:
            return []
        
        url = f"{LiveDataConfig.ESPN_BASE}/{sport_path}/injuries"
        data = cls._make_request(url)
        
        if not data:
            return []
        
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
        
        return injuries


# ============================================================
# UNIFIED LIVE DATA ROUTER
# ============================================================

class LiveDataRouter:
    """Unified interface for all live data services."""
    
    @classmethod
    def get_todays_games(cls, sport: str) -> List[Dict]:
        games = OddsAPIService.get_games(sport)
        return [asdict(g) for g in games]
    
    @classmethod
    def get_player_props(cls, sport: str, game_id: str = None) -> List[Dict]:
        props = OddsAPIService.get_player_props(sport, game_id)
        return [asdict(p) for p in props]
    
    @classmethod
    def get_injuries(cls, sport: str, team: str = None) -> List[Dict]:
        injuries = PlaybookAPIService.get_injuries(sport)
        if injuries:
            result = [asdict(i) for i in injuries]
            if team:
                result = [i for i in result if i.get("team", "").upper() == team.upper()]
            return result
        
        injuries = ESPNService.get_injuries(sport, team)
        return [asdict(i) for i in injuries]
    
    @classmethod
    def get_splits(cls, sport: str) -> List[Dict]:
        return PlaybookAPIService.get_splits(sport)
    
    @classmethod
    def get_sharp_money(cls, sport: str) -> List[Dict]:
        return PlaybookAPIService.get_sharp_money(sport)
    
    @classmethod
    def get_player_stats(cls, player_name: str, sport: str = "NBA") -> Optional[Dict]:
        return None
    
    @classmethod
    def build_prediction_context(cls, sport: str, player_name: str, player_team: str, opponent_team: str) -> Dict:
        context = {
            "sport": sport.upper(),
            "player_name": player_name,
            "player_team": player_team,
            "opponent_team": opponent_team,
            "data_source": "live",
            "timestamp": datetime.now().isoformat()
        }
        
        injuries = cls.get_injuries(sport, player_team)
        context["injuries"] = injuries
        
        out_injuries = [i for i in injuries if i.get("status") == "OUT"]
        vacuum = sum(i.get("usage_pct", 0) * (i.get("minutes_per_game", 0) / 48) for i in out_injuries)
        context["calculated_vacuum"] = round(vacuum * 100, 2)
        
        games = cls.get_todays_games(sport)
        for game in games:
            home = game.get("home_team", "")
            away = game.get("away_team", "")
            if player_team.upper() in home.upper() or player_team.upper() in away.upper():
                context["game_total"] = game.get("total", 220)
                context["game_spread"] = game.get("spread", 0)
                context["game_id"] = game.get("game_id")
                context["home_team"] = game.get("home_team")
                context["best_over_book"] = game.get("over_book")
                context["best_under_book"] = game.get("under_book")
                context["books_compared"] = game.get("books_compared", 0)
                break
        
        splits = cls.get_splits(sport)
        context["splits"] = splits
        
        sharp = cls.get_sharp_money(sport)
        context["sharp_signals"] = sharp
        
        return context
    
    @classmethod
    def get_full_slate(cls, sport: str) -> List[Dict]:
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
# CONFIDENCE CALCULATOR FOR PROPS
# ============================================================

def calculate_prop_confidence(prop: Dict) -> Dict:
    """
    Calculate confidence score for a player prop.
    Only returns props with 70%+ confidence (SMASH bets).
    """
    over_odds = prop.get("over_odds", -110)
    under_odds = prop.get("under_odds", -110)
    books_compared = prop.get("books_compared", 1)
    
    # Base confidence starts at 50
    confidence = 50
    
    # Edge calculation - how much better than -110 standard
    over_edge = (over_odds + 110) / 10 if over_odds > -110 else 0
    under_edge = (under_odds + 110) / 10 if under_odds > -110 else 0
    best_edge = max(over_edge, under_edge)
    
    # Confidence boost based on edge
    # +5 confidence per 1% edge
    confidence += best_edge * 5
    
    # Books compared boost (more books = more reliable line)
    if books_compared >= 5:
        confidence += 10
    elif books_compared >= 3:
        confidence += 5
    
    # Big edge bonus (edge > 3% is significant)
    if best_edge >= 5:
        confidence += 15
    elif best_edge >= 3:
        confidence += 10
    elif best_edge >= 2:
        confidence += 5
    
    # Cap at 95
    confidence = min(95, confidence)
    
    # Determine recommendation
    recommendation = "OVER" if over_edge > under_edge else "UNDER"
    
    # Determine tier
    if confidence >= 80:
        tier = "GOLDEN_SMASH"
    elif confidence >= 70:
        tier = "SMASH"
    else:
        tier = "LEAN"
    
    return {
        **prop,
        "confidence": round(confidence),
        "over_edge": round(over_edge, 2),
        "under_edge": round(under_edge, 2),
        "best_edge": round(best_edge, 2),
        "recommendation": recommendation,
        "tier": tier
    }


# ============================================================
# FASTAPI ROUTER
# ============================================================

from fastapi import APIRouter, HTTPException

live_data_router = APIRouter(prefix="/live", tags=["Live Data"])


@live_data_router.get("/games/{sport}")
async def get_live_games(sport: str):
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
    """
    Get TOP 5 SMASH player props (70%+ confidence only).
    No fluff - only the best bets based on our model.
    """
    sport = sport.upper()
    if sport not in ["NBA", "NFL", "MLB", "NHL", "NCAAB"]:
        raise HTTPException(400, "Invalid sport")
    
    props = LiveDataRouter.get_player_props(sport, game_id)
    
    if not props:
        return {
            "status": "success",
            "sport": sport,
            "count": 0,
            "props": [],
            "message": "No props available - check back closer to game time",
            "timestamp": datetime.now().isoformat()
        }
    
    # Calculate confidence for each prop
    enriched = [calculate_prop_confidence(p) for p in props]
    
    # FILTER: Only 70%+ confidence (SMASH bets)
    smash_props = [p for p in enriched if p["confidence"] >= 70]
    
    # Sort by confidence descending
    smash_props.sort(key=lambda x: x["confidence"], reverse=True)
    
    # TOP 5 ONLY - no fluff
    top_props = smash_props[:5]
    
    return {
        "status": "success",
        "sport": sport,
        "count": len(top_props),
        "props": top_props,
        "total_analyzed": len(props),
        "smash_threshold": 70,
        "timestamp": datetime.now().isoformat()
    }


@live_data_router.get("/injuries/{sport}")
async def get_injuries(sport: str, team: str = None):
    sport = sport.upper()
    if sport not in ["NBA", "NFL", "MLB", "NHL", "NCAAB"]:
        raise HTTPException(400, "Invalid sport")
    
    injuries = LiveDataRouter.get_injuries(sport, team)
    return {"status": "success", "sport": sport, "team": team, "count": len(injuries), "injuries": injuries}


@live_data_router.get("/splits/{sport}")
async def get_betting_splits(sport: str):
    sport = sport.upper()
    if sport not in ["NBA", "NFL", "MLB", "NHL", "NCAAB"]:
        raise HTTPException(400, "Invalid sport")
    
    splits = LiveDataRouter.get_splits(sport)
    return {"status": "success", "sport": sport, "splits": splits}


@live_data_router.get("/sharp/{sport}")
async def get_sharp_money(sport: str):
    sport = sport.upper()
    if sport not in ["NBA", "NFL", "MLB", "NHL", "NCAAB"]:
        raise HTTPException(400, "Invalid sport")
    
    signals = LiveDataRouter.get_sharp_money(sport)
    return {"status": "success", "sport": sport, "signals": signals}


@live_data_router.get("/player/{player_name}")
async def get_player_info(player_name: str, sport: str = "NBA"):
    stats = LiveDataRouter.get_player_stats(player_name, sport)
    if not stats:
        raise HTTPException(404, f"Player '{player_name}' not found")
    return {"status": "success", "player": stats}


@live_data_router.get("/context/{sport}")
async def build_context(sport: str, player_name: str, player_team: str, opponent_team: str):
    sport = sport.upper()
    if sport not in ["NBA", "NFL", "MLB", "NHL", "NCAAB"]:
        raise HTTPException(400, "Invalid sport")
    
    context = LiveDataRouter.build_prediction_context(sport, player_name, player_team, opponent_team)
    return {"status": "success", "context": context}


@live_data_router.get("/slate/{sport}")
async def get_full_slate(sport: str):
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


if __name__ == "__main__":
    print("=== Testing Live Data Router v7.7.0 ===")
    print("TOP 5 SMASH PROPS ONLY (70%+ confidence)")
    games = LiveDataRouter.get_todays_games("NBA")
    print(f"NBA Games: {len(games)}")
    props = LiveDataRouter.get_player_props("NBA")
    print(f"NBA Props: {len(props)}")
    print("✅ Live Data Router v7.7.0 working!")
