"""
The Odds API Integration Service
"""

import os
import requests
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from loguru import logger

class OddsAPIService:
    BASE_URL = "https://api.the-odds-api.com/v4"
    PRIORITY_BOOKS = ["fanduel", "draftkings", "betmgm", "caesars", "pointsbet", "pinnacle"]
    
    def __init__(self):
        self.api_key = os.getenv("ODDS_API_KEY")
        if not self.api_key:
            logger.warning("ODDS_API_KEY not set - using demo mode")
            self.demo_mode = True
        else:
            self.demo_mode = False
            logger.info(f"Odds API initialized with key: {self.api_key[:8]}...")
    
    def get_sports(self) -> List[Dict]:
        if self.demo_mode:
            return self._demo_sports()
        try:
            response = requests.get(f"{self.BASE_URL}/sports", params={"apiKey": self.api_key})
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch sports: {e}")
            return self._demo_sports()
    
    def get_odds(self, sport: str = "basketball_nba", regions: str = "us", markets: str = "h2h,spreads,totals", odds_format: str = "american", bookmakers: Optional[List[str]] = None) -> List[Dict]:
        if self.demo_mode:
            logger.info("Using demo odds (no API key)")
            return self._demo_odds(sport)
        
        try:
            params = {"apiKey": self.api_key, "regions": regions, "markets": markets, "oddsFormat": odds_format}
            if bookmakers:
                params["bookmakers"] = ",".join(bookmakers)
            
            url = f"{self.BASE_URL}/sports/{sport}/odds"
            logger.info(f"Fetching live odds from: {url}")
            
            response = requests.get(url, params=params)
            logger.info(f"Odds API status: {response.status_code}")
            
            remaining = response.headers.get("x-requests-remaining", "?")
            logger.info(f"Odds API requests remaining: {remaining}")
            
            if response.status_code != 200:
                logger.error(f"Odds API error: {response.status_code} - {response.text}")
                return self._demo_odds(sport)
            
            data = response.json()
            logger.success(f"Fetched {len(data)} live games")
            
            if not data:
                logger.warning("No games scheduled - using demo")
                return self._demo_odds(sport)
            
            return data
        except Exception as e:
            logger.error(f"Odds API error: {e}")
            return self._demo_odds(sport)
    
    def get_player_props(self, sport: str = "basketball_nba", event_id: str = None, markets: str = "player_points,player_rebounds,player_assists", regions: str = "us") -> List[Dict]:
        if self.demo_mode:
            return self._demo_player_props()
        try:
            params = {"apiKey": self.api_key, "regions": regions, "markets": markets, "oddsFormat": "american"}
            response = requests.get(f"{self.BASE_URL}/sports/{sport}/events/{event_id}/odds", params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Props error: {e}")
            return self._demo_player_props()
    
    def analyze_line_value(self, odds_data: List[Dict]) -> List[Dict]:
        analyzed = []
        for game in odds_data:
            analysis = {"game_id": game.get("id"), "home_team": game.get("home_team"), "away_team": game.get("away_team"), "commence_time": game.get("commence_time"), "best_odds": {}, "line_value_edges": []}
            best = {"home_ml": {"odds": -9999, "book": None}, "away_ml": {"odds": -9999, "book": None}, "over": {"odds": -9999, "line": None, "book": None}, "under": {"odds": -9999, "line": None, "book": None}}
            
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
            for key, data in best.items():
                if data["odds"] > -110:
                    edge = self._calc_edge(data["odds"], -110)
                    if edge > 2.0:
                        analysis["line_value_edges"].append({"bet_type": key, "edge_percent": round(edge, 2), "best_book": data["book"], "best_odds": data["odds"]})
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
                                    results.append({"game_id": game["id"], "matchup": f"{game['away_team']} @ {game['home_team']}", "spread": out["point"], "key_number": kn, "team": out["name"], "book": bk["key"]})
                                    break
        return results
    
    def _calc_edge(self, odds1: int, odds2: int) -> float:
        p1 = 100/(odds1+100) if odds1 > 0 else abs(odds1)/(abs(odds1)+100)
        p2 = 100/(odds2+100) if odds2 > 0 else abs(odds2)/(abs(odds2)+100)
        return ((1/p1)/(1/p2) - 1) * 100 if p2 > 0 else 0
    
    def _demo_sports(self) -> List[Dict]:
        return [{"key": "basketball_nba", "title": "NBA", "active": True}, {"key": "americanfootball_nfl", "title": "NFL", "active": True}]
    
    def _demo_odds(self, sport: str) -> List[Dict]:
        logger.warning("Returning DEMO odds")
        return [{"id": "demo_game_1", "sport_key": sport, "home_team": "Los Angeles Lakers", "away_team": "Golden State Warriors", "commence_time": (datetime.now() + timedelta(hours=3)).isoformat(), "bookmakers": [
            {"key": "fanduel", "title": "FanDuel", "markets": [{"key": "h2h", "outcomes": [{"name": "Los Angeles Lakers", "price": -145}, {"name": "Golden State Warriors", "price": 125}]}, {"key": "spreads", "outcomes": [{"name": "Los Angeles Lakers", "price": -110, "point": -3.5}, {"name": "Golden State Warriors", "price": -110, "point": 3.5}]}, {"key": "totals", "outcomes": [{"name": "Over", "price": -110, "point": 228.5}, {"name": "Under", "price": -110, "point": 228.5}]}]},
            {"key": "draftkings", "title": "DraftKings", "markets": [{"key": "h2h", "outcomes": [{"name": "Los Angeles Lakers", "price": -140}, {"name": "Golden State Warriors", "price": 120}]}]},
            {"key": "pinnacle", "title": "Pinnacle", "markets": [{"key": "h2h", "outcomes": [{"name": "Los Angeles Lakers", "price": -148}, {"name": "Golden State Warriors", "price": 138}]}]}
        ]}]
    
    def _demo_player_props(self) -> Dict:
        return {"id": "demo", "bookmakers": []}

odds_service = OddsAPIService()
