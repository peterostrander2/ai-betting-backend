"""
The Odds API Integration Service
Fetches live odds from 20+ sportsbooks for real-time line comparison
Powers: Live Odds, Line Value, Key Numbers signals
"""

import os
import requests
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from loguru import logger
import json

class OddsAPIService:
    """
    Integration with The Odds API for real-time sportsbook odds
    API Key: Set ODDS_API_KEY environment variable
    Docs: https://the-odds-api.com/
    """
    
    BASE_URL = "https://api.the-odds-api.com/v4"
    
    # Priority sportsbooks for best lines
    PRIORITY_BOOKS = [
        "fanduel",
        "draftkings", 
        "betmgm",
        "caesars",
        "pointsbet",
        "pinnacle"  # Sharp book for reference
    ]
    
    def __init__(self):
        self.api_key = os.getenv("ODDS_API_KEY")
        if not self.api_key:
            logger.warning("ODDS_API_KEY not set - using demo mode")
            self.demo_mode = True
        else:
            self.demo_mode = False
            logger.info("Odds API initialized with live key")
    
    # ==========================================
    # CORE API METHODS
    # ==========================================
    
    def get_sports(self) -> List[Dict]:
        """Get list of available sports"""
        if self.demo_mode:
            return self._demo_sports()
        
        try:
            response = requests.get(
                f"{self.BASE_URL}/sports",
                params={"apiKey": self.api_key}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch sports: {e}")
            return self._demo_sports()
    
    def get_odds(
        self,
        sport: str = "basketball_nba",
        regions: str = "us",
        markets: str = "h2h,spreads,totals",
        odds_format: str = "american",
        bookmakers: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Get live odds for a sport
        
        Args:
            sport: Sport key (basketball_nba, americanfootball_nfl, etc)
            regions: us, us2, uk, eu, au
            markets: h2h (moneyline), spreads, totals, player props
            odds_format: american or decimal
            bookmakers: Specific books to query
        """
        if self.demo_mode:
            return self._demo_odds(sport)
        
        try:
            params = {
                "apiKey": self.api_key,
                "regions": regions,
                "markets": markets,
                "oddsFormat": odds_format
            }
            
            if bookmakers:
                params["bookmakers"] = ",".join(bookmakers)
            
            response = requests.get(
                f"{self.BASE_URL}/sports/{sport}/odds",
                params=params
            )
            response.raise_for_status()
            
            # Log remaining requests
            remaining = response.headers.get("x-requests-remaining", "?")
            logger.info(f"Odds API requests remaining: {remaining}")
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Failed to fetch odds: {e}")
            return self._demo_odds(sport)
    
    def get_player_props(
        self,
        sport: str = "basketball_nba",
        event_id: str = None,
        markets: str = "player_points,player_rebounds,player_assists",
        regions: str = "us"
    ) -> List[Dict]:
        """
        Get player prop odds for a specific game
        
        Markets available:
        - player_points, player_rebounds, player_assists
        - player_threes, player_blocks, player_steals
        - player_points_rebounds_assists, player_double_double
        """
        if self.demo_mode:
            return self._demo_player_props()
        
        try:
            params = {
                "apiKey": self.api_key,
                "regions": regions,
                "markets": markets,
                "oddsFormat": "american"
            }
            
            url = f"{self.BASE_URL}/sports/{sport}/events/{event_id}/odds"
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"Failed to fetch player props: {e}")
            return self._demo_player_props()
    
    # ==========================================
    # SIGNAL ANALYSIS METHODS
    # ==========================================
    
    def analyze_line_value(self, odds_data: List[Dict]) -> List[Dict]:
        """
        Signal #14: LINE VALUE
        Find best available odds across all books
        Returns games where significant line discrepancies exist
        """
        analyzed = []
        
        for game in odds_data:
            game_analysis = {
                "game_id": game.get("id"),
                "home_team": game.get("home_team"),
                "away_team": game.get("away_team"),
                "commence_time": game.get("commence_time"),
                "best_odds": {},
                "line_value_edges": []
            }
            
            # Track best odds per outcome
            best_home_ml = {"odds": -9999, "book": None}
            best_away_ml = {"odds": -9999, "book": None}
            best_over = {"odds": -9999, "line": None, "book": None}
            best_under = {"odds": -9999, "line": None, "book": None}
            
            for bookmaker in game.get("bookmakers", []):
                book_name = bookmaker.get("key")
                
                for market in bookmaker.get("markets", []):
                    market_key = market.get("key")
                    
                    for outcome in market.get("outcomes", []):
                        price = outcome.get("price", -9999)
                        
                        if market_key == "h2h":
                            if outcome.get("name") == game.get("home_team"):
                                if price > best_home_ml["odds"]:
                                    best_home_ml = {"odds": price, "book": book_name}
                            else:
                                if price > best_away_ml["odds"]:
                                    best_away_ml = {"odds": price, "book": book_name}
                        
                        elif market_key == "totals":
                            line = outcome.get("point")
                            if outcome.get("name") == "Over":
                                if price > best_over["odds"]:
                                    best_over = {"odds": price, "line": line, "book": book_name}
                            else:
                                if price > best_under["odds"]:
                                    best_under = {"odds": price, "line": line, "book": book_name}
            
            game_analysis["best_odds"] = {
                "home_ml": best_home_ml,
                "away_ml": best_away_ml,
                "over": best_over,
                "under": best_under
            }
            
            # Calculate line value edges (compare to -110 standard)
            for key, data in game_analysis["best_odds"].items():
                if data.get("odds") and data["odds"] > -110:
                    edge = self._calculate_edge(data["odds"], -110)
                    if edge > 2.0:  # 2%+ edge
                        game_analysis["line_value_edges"].append({
                            "bet_type": key,
                            "edge_percent": round(edge, 2),
                            "best_book": data["book"],
                            "best_odds": data["odds"]
                        })
            
            analyzed.append(game_analysis)
        
        return analyzed
    
    def detect_key_numbers(self, odds_data: List[Dict]) -> List[Dict]:
        """
        Signal #15: KEY NUMBERS
        Identify spreads/totals near key numbers (3, 7, 10 for NFL; 5, 6, 7 for NBA)
        These are high-value hook opportunities
        """
        NBA_KEY_NUMBERS = [5, 6, 7, 8, 9, 10]
        NFL_KEY_NUMBERS = [3, 7, 10, 14, 17]
        
        key_number_games = []
        
        for game in odds_data:
            sport = game.get("sport_key", "")
            key_nums = NFL_KEY_NUMBERS if "football" in sport else NBA_KEY_NUMBERS
            
            for bookmaker in game.get("bookmakers", []):
                for market in bookmaker.get("markets", []):
                    if market.get("key") == "spreads":
                        for outcome in market.get("outcomes", []):
                            spread = abs(outcome.get("point", 0))
                            
                            # Check if on or near key number
                            for kn in key_nums:
                                if abs(spread - kn) <= 0.5:
                                    key_number_games.append({
                                        "game_id": game.get("id"),
                                        "matchup": f"{game.get('away_team')} @ {game.get('home_team')}",
                                        "spread": outcome.get("point"),
                                        "key_number": kn,
                                        "hook_value": "HIGH" if spread == kn else "MEDIUM",
                                        "team": outcome.get("name"),
                                        "book": bookmaker.get("key")
                                    })
                                    break
        
        return key_number_games
    
    def compare_to_pinnacle(self, odds_data: List[Dict]) -> List[Dict]:
        """
        Compare recreational book lines to Pinnacle (sharp reference)
        Edges vs Pinnacle = potential +EV opportunities
        """
        comparisons = []
        
        for game in odds_data:
            pinnacle_odds = None
            other_odds = []
            
            for bookmaker in game.get("bookmakers", []):
                book_key = bookmaker.get("key")
                
                if book_key == "pinnacle":
                    pinnacle_odds = bookmaker
                elif book_key in self.PRIORITY_BOOKS:
                    other_odds.append(bookmaker)
            
            if pinnacle_odds and other_odds:
                comparisons.append({
                    "game_id": game.get("id"),
                    "matchup": f"{game.get('away_team')} @ {game.get('home_team')}",
                    "pinnacle": pinnacle_odds,
                    "recreational_books": other_odds,
                    "edges": self._find_edges_vs_sharp(pinnacle_odds, other_odds)
                })
        
        return comparisons
    
    # ==========================================
    # HELPER METHODS
    # ==========================================
    
    def _calculate_edge(self, your_odds: int, market_odds: int) -> float:
        """Calculate edge percentage between two American odds"""
        your_prob = self._american_to_probability(your_odds)
        market_prob = self._american_to_probability(market_odds)
        
        if market_prob == 0:
            return 0
        
        edge = ((1 / your_prob) / (1 / market_prob) - 1) * 100
        return edge
    
    def _american_to_probability(self, odds: int) -> float:
        """Convert American odds to implied probability"""
        if odds > 0:
            return 100 / (odds + 100)
        else:
            return abs(odds) / (abs(odds) + 100)
    
    def _find_edges_vs_sharp(self, sharp_book: Dict, rec_books: List[Dict]) -> List[Dict]:
        """Find edges where recreational books offer better odds than sharp"""
        edges = []
        
        sharp_markets = {m["key"]: m for m in sharp_book.get("markets", [])}
        
        for rec_book in rec_books:
            for market in rec_book.get("markets", []):
                market_key = market["key"]
                
                if market_key in sharp_markets:
                    sharp_market = sharp_markets[market_key]
                    
                    for outcome in market.get("outcomes", []):
                        # Find matching outcome in sharp book
                        sharp_outcome = next(
                            (o for o in sharp_market.get("outcomes", [])
                             if o.get("name") == outcome.get("name")),
                            None
                        )
                        
                        if sharp_outcome:
                            rec_odds = outcome.get("price", -9999)
                            sharp_odds = sharp_outcome.get("price", -9999)
                            
                            if rec_odds > sharp_odds:
                                edge = self._calculate_edge(rec_odds, sharp_odds)
                                if edge > 1.0:  # 1%+ edge vs sharp
                                    edges.append({
                                        "market": market_key,
                                        "outcome": outcome.get("name"),
                                        "rec_book": rec_book.get("key"),
                                        "rec_odds": rec_odds,
                                        "sharp_odds": sharp_odds,
                                        "edge_percent": round(edge, 2)
                                    })
        
        return edges
    
    # ==========================================
    # DEMO DATA (when API key not available)
    # ==========================================
    
    def _demo_sports(self) -> List[Dict]:
        return [
            {"key": "basketball_nba", "title": "NBA", "active": True},
            {"key": "americanfootball_nfl", "title": "NFL", "active": True},
            {"key": "icehockey_nhl", "title": "NHL", "active": True},
            {"key": "baseball_mlb", "title": "MLB", "active": False}
        ]
    
    def _demo_odds(self, sport: str) -> List[Dict]:
        """Return demo odds data for testing"""
        return [
            {
                "id": "demo_game_1",
                "sport_key": sport,
                "home_team": "Los Angeles Lakers",
                "away_team": "Golden State Warriors",
                "commence_time": (datetime.now() + timedelta(hours=3)).isoformat(),
                "bookmakers": [
                    {
                        "key": "fanduel",
                        "title": "FanDuel",
                        "markets": [
                            {
                                "key": "h2h",
                                "outcomes": [
                                    {"name": "Los Angeles Lakers", "price": -145},
                                    {"name": "Golden State Warriors", "price": 125}
                                ]
                            },
                            {
                                "key": "spreads",
                                "outcomes": [
                                    {"name": "Los Angeles Lakers", "price": -110, "point": -3.5},
                                    {"name": "Golden State Warriors", "price": -110, "point": 3.5}
                                ]
                            },
                            {
                                "key": "totals",
                                "outcomes": [
                                    {"name": "Over", "price": -110, "point": 228.5},
                                    {"name": "Under", "price": -110, "point": 228.5}
                                ]
                            }
                        ]
                    },
                    {
                        "key": "draftkings",
                        "title": "DraftKings",
                        "markets": [
                            {
                                "key": "h2h",
                                "outcomes": [
                                    {"name": "Los Angeles Lakers", "price": -140},
                                    {"name": "Golden State Warriors", "price": 120}
                                ]
                            },
                            {
                                "key": "spreads",
                                "outcomes": [
                                    {"name": "Los Angeles Lakers", "price": -108, "point": -3.5},
                                    {"name": "Golden State Warriors", "price": -112, "point": 3.5}
                                ]
                            }
                        ]
                    },
                    {
                        "key": "pinnacle",
                        "title": "Pinnacle",
                        "markets": [
                            {
                                "key": "h2h",
                                "outcomes": [
                                    {"name": "Los Angeles Lakers", "price": -148},
                                    {"name": "Golden State Warriors", "price": 138}
                                ]
                            }
                        ]
                    }
                ]
            }
        ]
    
    def _demo_player_props(self) -> List[Dict]:
        """Return demo player props for testing"""
        return {
            "id": "demo_game_1",
            "bookmakers": [
                {
                    "key": "fanduel",
                    "markets": [
                        {
                            "key": "player_points",
                            "outcomes": [
                                {"name": "LeBron James", "description": "Over", "price": -115, "point": 25.5},
                                {"name": "LeBron James", "description": "Under", "price": -105, "point": 25.5},
                                {"name": "Stephen Curry", "description": "Over", "price": -110, "point": 27.5},
                                {"name": "Stephen Curry", "description": "Under", "price": -110, "point": 27.5}
                            ]
                        }
                    ]
                }
            ]
        }


# Singleton instance
odds_service = OddsAPIService()
