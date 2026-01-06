"""
The Odds API Integration Service
Fetches live odds from 20+ sportsbooks
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
            logger.info(f"Odds API initialized with live key: {self.api_key[:8]}...")
    
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
    
    def get_odds(self, sport: str = "basketball_nba", regions: str = "us",
                 markets: str = "h2h,spreads,totals", odds_format: str = "american",
                 bookmakers: Optional[List[str]] = None) -> List[Dict]:
        if self.demo_mode:
            logger.info("Using demo odds (no API key)")
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
            
            url = f"{self.BASE_URL}/sports/{sport}/odds"
            logger.info(f"Fetching live odds from: {url}")
            
            response = requests.get(url, params=params)
