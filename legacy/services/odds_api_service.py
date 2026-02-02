"""
The Odds API Integration Service
UPDATED: Uses ALL sportsbooks, not filtered

SECURITY: Demo data is GATED behind ENABLE_DEMO=true env var.
Without it, API failures return empty responses, not sample data.
"""

import os
import requests
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from loguru import logger

# Demo data gate - must be explicitly enabled
ENABLE_DEMO = os.getenv("ENABLE_DEMO", "").lower() == "true"


class OddsAPIService:
    BASE_URL = "https://api.the-odds-api.com/v4"
    
    # ALL supported US sportsbooks - we want data from ALL of them
    ALL_BOOKS = [
        "fanduel", "draftkings", "betmgm", "caesars", "pointsbet",
        "pinnacle", "bovada", "betonlineag", "lowvig", "mybookieag",
        "betrivers", "unibet_us", "twinspires", "betus", "wynnbet",
        "superbook", "barstool"
    ]
    
    def __init__(self):
        self.api_key = os.getenv("ODDS_API_KEY")
        if not self.api_key:
            if ENABLE_DEMO:
                logger.warning("ODDS_API_KEY not set - demo mode enabled via ENABLE_DEMO=true")
                self.demo_mode = True
            else:
                logger.warning("ODDS_API_KEY not set - returning empty data (set ENABLE_DEMO=true for demo mode)")
                self.demo_mode = False
        else:
            self.demo_mode = False
            logger.info("Odds API initialized with key: [REDACTED]")

    def get_sports(self) -> List[Dict]:
        if self.demo_mode and ENABLE_DEMO:
            return self._demo_sports()
        if not self.api_key:
            return []  # No demo data without ENABLE_DEMO
        try:
            response = requests.get(f"{self.BASE_URL}/sports", params={"apiKey": self.api_key})
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch sports: {e}")
            if ENABLE_DEMO:
                return self._demo_sports()
            return []  # Empty response, no demo data

    def get_odds(
        self,
        sport: str = "basketball_nba",
        regions: str = "us,us2",  # Multiple regions for more books
        markets: str = "h2h,spreads,totals",
        odds_format: str = "american",
        bookmakers: Optional[List[str]] = None  # None = ALL books
    ) -> List[Dict]:
        """
        Fetch odds from ALL sportsbooks (no filtering)
        """
        if self.demo_mode and ENABLE_DEMO:
            logger.info("Using demo odds (ENABLE_DEMO=true)")
            return self._demo_odds(sport)
        if not self.api_key:
            logger.warning("No API key and ENABLE_DEMO not set - returning empty")
            return []
        
        try:
            params = {
                "apiKey": self.api_key, 
                "regions": regions,  
                "markets": markets, 
                "oddsFormat": odds_format
            }
            # IMPORTANT: Don't add bookmakers param = get ALL available books
            # Only filter if explicitly requested
            if bookmakers:
                params["bookmakers"] = ",".join(bookmakers)
            
            url = f"{self.BASE_URL}/sports/{sport}/odds"
            logger.info(f"Fetching ALL sportsbook odds from: {url}")
            
            response = requests.get(url, params=params)
            logger.info(f"Odds API status: {response.status_code}")
            
            remaining = response.headers.get("x-requests-remaining", "?")
            used = response.headers.get("x-requests-used", "?")
            logger.info(f"Odds API: {remaining} requests remaining, {used} used")
            
            if response.status_code != 200:
                logger.error(f"Odds API error: {response.status_code} - {response.text}")
                if ENABLE_DEMO:
                    return self._demo_odds(sport)
                return []  # Empty, no demo

            data = response.json()

            # Log how many books we got per game
            if data:
                book_count = len(data[0].get("bookmakers", []))
                logger.success(f"Fetched {len(data)} games with {book_count} sportsbooks each")

            if not data:
                logger.warning("No games scheduled")
                return []  # Empty is valid, no demo fallback

            return data
        except Exception as e:
            logger.error(f"Odds API error: {e}")
            if ENABLE_DEMO:
                return self._demo_odds(sport)
            return []  # Empty, no demo

    def get_player_props(
        self,
        sport: str = "basketball_nba",
        event_id: str = None,
        markets: str = "player_points,player_rebounds,player_assists,player_threes,player_blocks,player_steals,player_turnovers",
        regions: str = "us,us2"
    ) -> List[Dict]:
        """Fetch player props from ALL books"""
        if self.demo_mode and ENABLE_DEMO:
            return self._demo_player_props()
        if not self.api_key:
            return {"id": event_id, "bookmakers": [], "error": "no_api_key"}
        try:
            params = {
                "apiKey": self.api_key, 
                "regions": regions,  # Multiple regions
                "markets": markets, 
                "oddsFormat": "american"
            }
            # No bookmakers filter = ALL books
            response = requests.get(
                f"{self.BASE_URL}/sports/{sport}/events/{event_id}/odds", 
                params=params
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Props error: {e}")
            if ENABLE_DEMO:
                return self._demo_player_props()
            return {"id": event_id, "bookmakers": [], "error": str(e)}
    
    def get_best_odds(self, odds_data: List[Dict]) -> List[Dict]:
        """
        Find the BEST odds across ALL sportsbooks for each game
        This is the key value-add - line shopping across 15+ books
        """
        results = []
        
        for game in odds_data:
            best = {
                "game_id": game.get("id"),
                "home_team": game.get("home_team"),
                "away_team": game.get("away_team"),
                "commence_time": game.get("commence_time"),
                "bookmaker_count": len(game.get("bookmakers", [])),
                "best_home_ml": {"odds": -9999, "book": None},
                "best_away_ml": {"odds": -9999, "book": None},
                "best_home_spread": {"odds": -9999, "line": None, "book": None},
                "best_away_spread": {"odds": -9999, "line": None, "book": None},
                "best_over": {"odds": -9999, "line": None, "book": None},
                "best_under": {"odds": -9999, "line": None, "book": None},
                "all_books": []  # Track all books for transparency
            }
            
            for bk in game.get("bookmakers", []):
                book_name = bk["key"]
                best["all_books"].append(book_name)
                
                for mkt in bk.get("markets", []):
                    for out in mkt.get("outcomes", []):
                        price = out.get("price", -9999)
                        point = out.get("point")
                        
                        if mkt["key"] == "h2h":
                            if out["name"] == game.get("home_team"):
                                if price > best["best_home_ml"]["odds"]:
                                    best["best_home_ml"] = {"odds": price, "book": book_name}
                            else:
                                if price > best["best_away_ml"]["odds"]:
                                    best["best_away_ml"] = {"odds": price, "book": book_name}
                        
                        elif mkt["key"] == "spreads":
                            if out["name"] == game.get("home_team"):
                                if price > best["best_home_spread"]["odds"]:
                                    best["best_home_spread"] = {"odds": price, "line": point, "book": book_name}
                            else:
                                if price > best["best_away_spread"]["odds"]:
                                    best["best_away_spread"] = {"odds": price, "line": point, "book": book_name}
                        
                        elif mkt["key"] == "totals":
                            if out["name"] == "Over":
                                if price > best["best_over"]["odds"]:
                                    best["best_over"] = {"odds": price, "line": point, "book": book_name}
                            elif out["name"] == "Under":
                                if price > best["best_under"]["odds"]:
                                    best["best_under"] = {"odds": price, "line": point, "book": book_name}
            
            # Calculate edge vs standard -110
            best["edges"] = {
                "home_ml_edge": self._calc_edge(best["best_home_ml"]["odds"], -110) if best["best_home_ml"]["odds"] > -9999 else 0,
                "away_ml_edge": self._calc_edge(best["best_away_ml"]["odds"], -110) if best["best_away_ml"]["odds"] > -9999 else 0,
                "over_edge": self._calc_edge(best["best_over"]["odds"], -110) if best["best_over"]["odds"] > -9999 else 0,
                "under_edge": self._calc_edge(best["best_under"]["odds"], -110) if best["best_under"]["odds"] > -9999 else 0,
            }
            
            results.append(best)
        
        return results
    
    def analyze_line_value(self, odds_data: List[Dict]) -> List[Dict]:
        """Analyze line value across ALL books"""
        analyzed = []
        for game in odds_data:
            analysis = {
                "game_id": game.get("id"), 
                "home_team": game.get("home_team"), 
                "away_team": game.get("away_team"), 
                "commence_time": game.get("commence_time"), 
                "books_compared": len(game.get("bookmakers", [])),
                "best_odds": {}, 
                "line_value_edges": []
            }
            
            best = {
                "home_ml": {"odds": -9999, "book": None}, 
                "away_ml": {"odds": -9999, "book": None}, 
                "over": {"odds": -9999, "line": None, "book": None}, 
                "under": {"odds": -9999, "line": None, "book": None}
            }
            
            for bk in game.get("bookmakers", []):
                for mkt in bk.get("markets", []):
                    for out in mkt.get("outcomes", []):
                        price = out.get("price", -9999)
                        if mkt["key"] == "h2h":
                            if out["name"] == game.get("home_team") and price > best["home_ml"]["odds"]:
                                best["home_ml"] = {"odds": price, "book": bk["key"]}
                            elif price > best["away_ml"]["odds"]:
                                best["away_ml"] = {"odds": price, "book": bk["key"]}
                        elif mkt["key"] == "totals":
                            if out["name"] == "Over" and price > best["over"]["odds"]:
                                best["over"] = {"odds": price, "line": out.get("point"), "book": bk["key"]}
                            elif out["name"] == "Under" and price > best["under"]["odds"]:
                                best["under"] = {"odds": price, "line": out.get("point"), "book": bk["key"]}
            
            analysis["best_odds"] = best
            
            # Find edges > 1% (lowered threshold to catch more value)
            for key, data in best.items():
                if data["odds"] > -115:  # Better than standard juice
                    edge = self._calc_edge(data["odds"], -110)
                    if edge > 1.0:
                        analysis["line_value_edges"].append({
                            "bet_type": key, 
                            "edge_percent": round(edge, 2), 
                            "best_book": data["book"], 
                            "best_odds": data["odds"]
                        })
            
            analyzed.append(analysis)
        return analyzed
    
    def detect_key_numbers(self, odds_data: List[Dict]) -> List[Dict]:
        results = []
        for game in odds_data:
            key_nums = [3, 7, 10, 14, 17] if "football" in game.get("sport_key", "") else [5, 6, 7, 8, 9, 10]
            for bk in game.get("bookmakers", []):
                for mkt in bk.get("markets", []):
                    if mkt["key"] == "spreads":
                        for out in mkt.get("outcomes", []):
                            spread = abs(out.get("point", 0))
                            for kn in key_nums:
                                if abs(spread - kn) <= 0.5:
                                    results.append({
                                        "game_id": game["id"], 
                                        "matchup": f"{game['away_team']} @ {game['home_team']}", 
                                        "spread": out["point"], 
                                        "key_number": kn, 
                                        "team": out["name"], 
                                        "book": bk["key"]
                                    })
                                    break
        return results
    
    def _calc_edge(self, odds1: int, odds2: int) -> float:
        p1 = 100/(odds1+100) if odds1 > 0 else abs(odds1)/(abs(odds1)+100)
        p2 = 100/(odds2+100) if odds2 > 0 else abs(odds2)/(abs(odds2)+100)
        return ((1/p1)/(1/p2) - 1) * 100 if p2 > 0 else 0
    
    def _demo_sports(self) -> List[Dict]:
        return [
            {"key": "basketball_nba", "title": "NBA", "active": True}, 
            {"key": "americanfootball_nfl", "title": "NFL", "active": True},
            {"key": "baseball_mlb", "title": "MLB", "active": True},
            {"key": "icehockey_nhl", "title": "NHL", "active": True},
            {"key": "basketball_ncaab", "title": "NCAAB", "active": True}
        ]
    
    def _demo_odds(self, sport: str) -> List[Dict]:
        logger.warning("Returning DEMO odds - multiple books")
        return [{
            "id": "demo_game_1", 
            "sport_key": sport, 
            "home_team": "Los Angeles Lakers", 
            "away_team": "Golden State Warriors", 
            "commence_time": (datetime.now() + timedelta(hours=3)).isoformat(), 
            "bookmakers": [
                {"key": "fanduel", "title": "FanDuel", "markets": [
                    {"key": "h2h", "outcomes": [{"name": "Los Angeles Lakers", "price": -145}, {"name": "Golden State Warriors", "price": 125}]}, 
                    {"key": "spreads", "outcomes": [{"name": "Los Angeles Lakers", "price": -110, "point": -3.5}, {"name": "Golden State Warriors", "price": -110, "point": 3.5}]}, 
                    {"key": "totals", "outcomes": [{"name": "Over", "price": -110, "point": 228.5}, {"name": "Under", "price": -110, "point": 228.5}]}
                ]},
                {"key": "draftkings", "title": "DraftKings", "markets": [
                    {"key": "h2h", "outcomes": [{"name": "Los Angeles Lakers", "price": -140}, {"name": "Golden State Warriors", "price": 120}]},
                    {"key": "spreads", "outcomes": [{"name": "Los Angeles Lakers", "price": -108, "point": -3.5}, {"name": "Golden State Warriors", "price": -112, "point": 3.5}]},
                    {"key": "totals", "outcomes": [{"name": "Over", "price": -108, "point": 228.5}, {"name": "Under", "price": -112, "point": 228.5}]}
                ]},
                {"key": "betmgm", "title": "BetMGM", "markets": [
                    {"key": "h2h", "outcomes": [{"name": "Los Angeles Lakers", "price": -142}, {"name": "Golden State Warriors", "price": 122}]},
                    {"key": "spreads", "outcomes": [{"name": "Los Angeles Lakers", "price": -105, "point": -3}, {"name": "Golden State Warriors", "price": -115, "point": 3}]},
                    {"key": "totals", "outcomes": [{"name": "Over", "price": -105, "point": 229}, {"name": "Under", "price": -115, "point": 229}]}
                ]},
                {"key": "caesars", "title": "Caesars", "markets": [
                    {"key": "h2h", "outcomes": [{"name": "Los Angeles Lakers", "price": -143}, {"name": "Golden State Warriors", "price": 123}]}
                ]},
                {"key": "pinnacle", "title": "Pinnacle", "markets": [
                    {"key": "h2h", "outcomes": [{"name": "Los Angeles Lakers", "price": -148}, {"name": "Golden State Warriors", "price": 138}]},
                    {"key": "spreads", "outcomes": [{"name": "Los Angeles Lakers", "price": -104, "point": -3.5}, {"name": "Golden State Warriors", "price": -106, "point": 3.5}]}
                ]}
            ]
        }]
    
    def _demo_player_props(self) -> Dict:
        return {"id": "demo", "bookmakers": []}

odds_service = OddsAPIService()
