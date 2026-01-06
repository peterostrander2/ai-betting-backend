"""
Playbook API Integration Service
Fetches player splits, injuries, and advanced stats
Powers: Splits, Sharp Money, Public Fade, Injury Impact signals
"""

import os
import requests
from typing import Dict, List, Optional
from datetime import datetime
from loguru import logger

class PlaybookAPIService:
    """
    Integration with Playbook Sports API for player data
    API Key: Set PLAYBOOK_API_KEY environment variable
    """
    
    BASE_URL = "https://api.playbook.com/v1"
    
    def __init__(self):
        self.api_key = os.getenv("PLAYBOOK_API_KEY")
        if not self.api_key:
            logger.warning("PLAYBOOK_API_KEY not set - using demo mode")
            self.demo_mode = True
        else:
            self.demo_mode = False
            logger.info("Playbook API initialized with live key")
    
    def _make_request(self, endpoint: str, params: Dict = None) -> Dict:
        """Make authenticated request to Playbook API"""
        if self.demo_mode:
            return None
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.get(
                f"{self.BASE_URL}/{endpoint}",
                headers=headers,
                params=params or {}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Playbook API error: {e}")
            return None
    
    # ==========================================
    # PLAYER SPLITS (Signal #16)
    # ==========================================
    
    def get_player_splits(
        self,
        player_id: str,
        sport: str = "nba",
        split_type: str = "all"
    ) -> Dict:
        """
        Get comprehensive player splits
        
        Split types:
        - home_away: Performance at home vs road
        - vs_team: Historical vs specific opponent
        - rest_days: Performance by days rest
        - game_time: Day vs night games
        - monthly: Month-by-month trends
        - last_n: Last 5/10/15/20 games
        """
        if self.demo_mode:
            return self._demo_player_splits(player_id)
        
        data = self._make_request(
            f"players/{player_id}/splits",
            {"sport": sport, "type": split_type}
        )
        
        return data or self._demo_player_splits(player_id)
    
    def analyze_splits_for_prop(
        self,
        player_id: str,
        stat_type: str,
        line: float,
        opponent_id: str = None,
        is_home: bool = True,
        days_rest: int = 1
    ) -> Dict:
        """
        Analyze all relevant splits for a specific prop bet
        Returns weighted probability based on situational factors
        """
        splits = self.get_player_splits(player_id)
        
        analysis = {
            "player_id": player_id,
            "stat_type": stat_type,
            "line": line,
            "factors": [],
            "weighted_prediction": 0,
            "confidence": 0
        }
        
        # Home/Away split
        location = "home" if is_home else "away"
        if splits.get("home_away", {}).get(location):
            loc_avg = splits["home_away"][location].get(stat_type, 0)
            over_rate = splits["home_away"][location].get(f"{stat_type}_over_rate", 0.5)
            
            analysis["factors"].append({
                "name": f"{location.title()} Games",
                "average": loc_avg,
                "over_rate_at_line": over_rate,
                "weight": 0.20
            })
        
        # Days rest split
        rest_key = f"{days_rest}_days" if days_rest <= 3 else "4plus_days"
        if splits.get("rest_days", {}).get(rest_key):
            rest_avg = splits["rest_days"][rest_key].get(stat_type, 0)
            over_rate = splits["rest_days"][rest_key].get(f"{stat_type}_over_rate", 0.5)
            
            analysis["factors"].append({
                "name": f"{days_rest} Day(s) Rest",
                "average": rest_avg,
                "over_rate_at_line": over_rate,
                "weight": 0.25
            })
        
        # Opponent split
        if opponent_id and splits.get("vs_team", {}).get(opponent_id):
            opp_avg = splits["vs_team"][opponent_id].get(stat_type, 0)
            over_rate = splits["vs_team"][opponent_id].get(f"{stat_type}_over_rate", 0.5)
            
            analysis["factors"].append({
                "name": f"vs {opponent_id.upper()}",
                "average": opp_avg,
                "over_rate_at_line": over_rate,
                "weight": 0.25
            })
        
        # Last 10 games trend
        if splits.get("last_n", {}).get("last_10"):
            recent_avg = splits["last_n"]["last_10"].get(stat_type, 0)
            over_rate = splits["last_n"]["last_10"].get(f"{stat_type}_over_rate", 0.5)
            
            analysis["factors"].append({
                "name": "Last 10 Games",
                "average": recent_avg,
                "over_rate_at_line": over_rate,
                "weight": 0.30
            })
        
        # Calculate weighted prediction
        if analysis["factors"]:
            total_weight = sum(f["weight"] for f in analysis["factors"])
            weighted_avg = sum(
                f["average"] * f["weight"] for f in analysis["factors"]
            ) / total_weight
            
            weighted_over_rate = sum(
                f["over_rate_at_line"] * f["weight"] for f in analysis["factors"]
            ) / total_weight
            
            analysis["weighted_prediction"] = round(weighted_avg, 1)
            analysis["over_probability"] = round(weighted_over_rate, 3)
            analysis["recommendation"] = "OVER" if weighted_avg > line else "UNDER"
            analysis["edge"] = round(abs(weighted_avg - line), 1)
            analysis["confidence"] = self._calculate_confidence(analysis["factors"])
        
        return analysis
    
    # ==========================================
    # BETTING PERCENTAGES (Signals #11, #12)
    # ==========================================
    
    def get_betting_percentages(
        self,
        game_id: str = None,
        sport: str = "nba"
    ) -> Dict:
        """
        Get public vs sharp money percentages
        Powers: Sharp Money and Public Fade signals
        """
        if self.demo_mode:
            return self._demo_betting_percentages(game_id)
        
        data = self._make_request(
            f"betting/percentages",
            {"game_id": game_id, "sport": sport}
        )
        
        return data or self._demo_betting_percentages(game_id)
    
    def detect_sharp_money(self, percentages: Dict) -> Dict:
        """
        Signal #11: SHARP MONEY
        Detect when money % diverges from ticket % (sharp indicator)
        
        Key patterns:
        - Reverse line movement: Line moves opposite to public %
        - Money/ticket split: >60% tickets but <40% money
        - Steam moves: Sudden line movement across multiple books
        """
        analysis = {
            "sharp_side": None,
            "confidence": 0,
            "indicators": []
        }
        
        home = percentages.get("home", {})
        away = percentages.get("away", {})
        
        # Check for money/ticket divergence
        home_tickets = home.get("ticket_percent", 50)
        home_money = home.get("money_percent", 50)
        
        ticket_money_split = abs(home_tickets - home_money)
        
        if ticket_money_split >= 15:
            # Significant divergence - sharps on opposite side of public
            sharp_on_home = home_money > home_tickets
            
            analysis["indicators"].append({
                "type": "money_ticket_divergence",
                "description": f"Home: {home_tickets}% tickets, {home_money}% money",
                "strength": "HIGH" if ticket_money_split >= 25 else "MEDIUM"
            })
            
            analysis["sharp_side"] = "home" if sharp_on_home else "away"
            analysis["confidence"] += 0.3
        
        # Check for reverse line movement
        opening_line = percentages.get("opening_line", 0)
        current_line = percentages.get("current_line", 0)
        
        if opening_line and current_line:
            line_moved_toward_home = current_line < opening_line  # More negative = more toward home
            public_on_home = home_tickets > 55
            
            if line_moved_toward_home and not public_on_home:
                analysis["indicators"].append({
                    "type": "reverse_line_movement",
                    "description": f"Line moved from {opening_line} to {current_line} despite public on away",
                    "strength": "HIGH"
                })
                analysis["sharp_side"] = "home"
                analysis["confidence"] += 0.35
            
            elif not line_moved_toward_home and public_on_home:
                analysis["indicators"].append({
                    "type": "reverse_line_movement", 
                    "description": f"Line moved from {opening_line} to {current_line} despite public on home",
                    "strength": "HIGH"
                })
                analysis["sharp_side"] = "away"
                analysis["confidence"] += 0.35
        
        # Calculate final confidence
        analysis["confidence"] = min(analysis["confidence"], 1.0)
        analysis["signal_strength"] = (
            "STRONG" if analysis["confidence"] >= 0.5
            else "MODERATE" if analysis["confidence"] >= 0.25
            else "WEAK"
        )
        
        return analysis
    
    def detect_public_fade(self, percentages: Dict) -> Dict:
        """
        Signal #12: PUBLIC FADE
        Identify heavy public favorites worth fading
        
        Fade triggers:
        - >75% public on one side
        - Combined with negative line value
        - Best in primetime/national TV games
        """
        analysis = {
            "fade_side": None,
            "public_side": None,
            "fade_confidence": 0,
            "reasoning": []
        }
        
        home_tickets = percentages.get("home", {}).get("ticket_percent", 50)
        
        if home_tickets >= 75:
            analysis["public_side"] = "home"
            analysis["fade_side"] = "away"
            analysis["fade_confidence"] = 0.6
            analysis["reasoning"].append(f"{home_tickets}% public on home - contrarian value on away")
        
        elif home_tickets <= 25:
            analysis["public_side"] = "away"
            analysis["fade_side"] = "home"
            analysis["fade_confidence"] = 0.6
            analysis["reasoning"].append(f"{100 - home_tickets}% public on away - contrarian value on home")
        
        # Boost confidence for primetime games
        if percentages.get("is_primetime", False):
            analysis["fade_confidence"] += 0.1
            analysis["reasoning"].append("Primetime game - public bias amplified")
        
        # Boost for heavy favorites
        spread = abs(percentages.get("current_line", 0))
        if spread >= 7:
            analysis["fade_confidence"] += 0.1
            analysis["reasoning"].append(f"Large spread ({spread}) - public overvaluing favorite")
        
        return analysis
    
    # ==========================================
    # INJURIES (Feeds Injury Impact Model)
    # ==========================================
    
    def get_injuries(
        self,
        sport: str = "nba",
        team_id: str = None
    ) -> List[Dict]:
        """
        Get current injury report
        Feeds into existing Injury Impact AI model
        """
        if self.demo_mode:
            return self._demo_injuries(sport)
        
        params = {"sport": sport}
        if team_id:
            params["team"] = team_id
        
        data = self._make_request("injuries", params)
        return data or self._demo_injuries(sport)
    
    def calculate_injury_impact(
        self,
        injuries: List[Dict],
        team_id: str,
        stat_type: str = "points"
    ) -> Dict:
        """
        Calculate cumulative impact of injuries on team totals
        Returns adjustment factors for predictions
        """
        total_impact = 0
        injured_players = []
        
        team_injuries = [i for i in injuries if i.get("team_id") == team_id]
        
        for injury in team_injuries:
            if injury["status"] in ["out", "doubtful"]:
                # Use player's per-game contribution
                player_avg = injury.get(f"avg_{stat_type}", 0)
                usage = injury.get("usage_rate", 0.15)
                
                # Weight by status
                status_weight = 1.0 if injury["status"] == "out" else 0.75
                
                impact = player_avg * status_weight
                total_impact += impact
                
                injured_players.append({
                    "name": injury["player_name"],
                    "status": injury["status"],
                    "impact": round(impact, 1)
                })
        
        return {
            "team_id": team_id,
            "total_adjustment": round(-total_impact, 1),
            "injured_players": injured_players,
            "severity": (
                "HIGH" if total_impact >= 15
                else "MEDIUM" if total_impact >= 8
                else "LOW"
            )
        }
    
    # ==========================================
    # HELPER METHODS
    # ==========================================
    
    def _calculate_confidence(self, factors: List[Dict]) -> float:
        """Calculate confidence based on factor agreement"""
        if not factors:
            return 0
        
        recommendations = [
            f["over_rate_at_line"] > 0.5 for f in factors
        ]
        
        agreement = sum(recommendations) / len(recommendations)
        
        # Higher confidence when all factors agree
        if agreement >= 0.8 or agreement <= 0.2:
