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
    """Integration with Playbook Sports API for player data"""
    
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
        if self.demo_mode:
            return None
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        try:
            response = requests.get(f"{self.BASE_URL}/{endpoint}", headers=headers, params=params or {})
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Playbook API error: {e}")
            return None
    
    def get_player_splits(self, player_id: str, sport: str = "nba", split_type: str = "all") -> Dict:
        if self.demo_mode:
            return self._demo_player_splits(player_id)
        data = self._make_request(f"players/{player_id}/splits", {"sport": sport, "type": split_type})
        return data or self._demo_player_splits(player_id)
    
    def analyze_splits_for_prop(self, player_id: str, stat_type: str, line: float,
                                 opponent_id: str = None, is_home: bool = True, days_rest: int = 1) -> Dict:
        splits = self.get_player_splits(player_id)
        analysis = {"player_id": player_id, "stat_type": stat_type, "line": line, "factors": [], "weighted_prediction": 0, "confidence": 0}
        
        location = "home" if is_home else "away"
        if splits.get("home_away", {}).get(location):
            loc_avg = splits["home_away"][location].get(stat_type, 0)
            over_rate = splits["home_away"][location].get(f"{stat_type}_over_rate", 0.5)
            analysis["factors"].append({"name": f"{location.title()} Games", "average": loc_avg, "over_rate_at_line": over_rate, "weight": 0.20})
        
        rest_key = f"{days_rest}_days" if days_rest <= 3 else "4plus_days"
        if splits.get("rest_days", {}).get(rest_key):
            rest_avg = splits["rest_days"][rest_key].get(stat_type, 0)
            over_rate = splits["rest_days"][rest_key].get(f"{stat_type}_over_rate", 0.5)
            analysis["factors"].append({"name": f"{days_rest} Day(s) Rest", "average": rest_avg, "over_rate_at_line": over_rate, "weight": 0.25})
        
        if opponent_id and splits.get("vs_team", {}).get(opponent_id):
            opp_avg = splits["vs_team"][opponent_id].get(stat_type, 0)
            over_rate = splits["vs_team"][opponent_id].get(f"{stat_type}_over_rate", 0.5)
            analysis["factors"].append({"name": f"vs {opponent_id.upper()}", "average": opp_avg, "over_rate_at_line": over_rate, "weight": 0.25})
        
        if splits.get("last_n", {}).get("last_10"):
            recent_avg = splits["last_n"]["last_10"].get(stat_type, 0)
            over_rate = splits["last_n"]["last_10"].get(f"{stat_type}_over_rate", 0.5)
            analysis["factors"].append({"name": "Last 10 Games", "average": recent_avg, "over_rate_at_line": over_rate, "weight": 0.30})
        
        if analysis["factors"]:
            total_weight = sum(f["weight"] for f in analysis["factors"])
            weighted_avg = sum(f["average"] * f["weight"] for f in analysis["factors"]) / total_weight
            weighted_over_rate = sum(f["over_rate_at_line"] * f["weight"] for f in analysis["factors"]) / total_weight
            analysis["weighted_prediction"] = round(weighted_avg, 1)
            analysis["over_probability"] = round(weighted_over_rate, 3)
            analysis["recommendation"] = "OVER" if weighted_avg > line else "UNDER"
            analysis["edge"] = round(abs(weighted_avg - line), 1)
            analysis["confidence"] = self._calculate_confidence(analysis["factors"])
        
        return analysis
    
    def get_betting_percentages(self, game_id: str = None, sport: str = "nba") -> Dict:
        if self.demo_mode:
            return self._demo_betting_percentages(game_id)
        data = self._make_request("betting/percentages", {"game_id": game_id, "sport": sport})
        return data or self._demo_betting_percentages(game_id)
    
    def detect_sharp_money(self, percentages: Dict) -> Dict:
        analysis = {"sharp_side": None, "confidence": 0, "indicators": []}
        home = percentages.get("home", {})
        home_tickets = home.get("ticket_percent", 50)
        home_money = home.get("money_percent", 50)
        ticket_money_split = abs(home_tickets - home_money)
        
        if ticket_money_split >= 15:
            sharp_on_home = home_money > home_tickets
            analysis["indicators"].append({
                "type": "money_ticket_divergence",
                "description": f"Home: {home_tickets}% tickets, {home_money}% money",
                "strength": "HIGH" if ticket_money_split >= 25 else "MEDIUM"
            })
            analysis["sharp_side"] = "home" if sharp_on_home else "away"
            analysis["confidence"] += 0.3
        
        opening_line = percentages.get("opening_line", 0)
        current_line = percentages.get("current_line", 0)
        
        if opening_line and current_line:
            line_moved_toward_home = current_line < opening_line
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
        
        analysis["confidence"] = min(analysis["confidence"], 1.0)
        analysis["signal_strength"] = "STRONG" if analysis["confidence"] >= 0.5 else "MODERATE" if analysis["confidence"] >= 0.25 else "WEAK"
        return analysis
    
    def detect_public_fade(self, percentages: Dict) -> Dict:
        analysis = {"fade_side": None, "public_side": None, "fade_confidence": 0, "reasoning": []}
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
        
        if percentages.get("is_primetime", False):
            analysis["fade_confidence"] += 0.1
            analysis["reasoning"].append("Primetime game - public bias amplified")
        
        spread = abs(percentages.get("current_line", 0))
        if spread >= 7:
            analysis["fade_confidence"] += 0.1
            analysis["reasoning"].append(f"Large spread ({spread}) - public overvaluing favorite")
        
        return analysis
    
    def get_injuries(self, sport: str = "nba", team_id: str = None) -> List[Dict]:
        if self.demo_mode:
            return self._demo_injuries(sport)
        params = {"sport": sport}
        if team_id:
            params["team"] = team_id
        data = self._make_request("injuries", params)
        return data or self._demo_injuries(sport)
    
    def calculate_injury_impact(self, injuries: List[Dict], team_id: str, stat_type: str = "points") -> Dict:
        total_impact = 0
        injured_players = []
        team_injuries = [i for i in injuries if i.get("team_id") == team_id]
        
        for injury in team_injuries:
            if injury["status"] in ["out", "doubtful"]:
                player_avg = injury.get(f"avg_{stat_type}", 0)
                status_weight = 1.0 if injury["status"] == "out" else 0.75
                impact = player_avg * status_weight
                total_impact += impact
                injured_players.append({"name": injury["player_name"], "status": injury["status"], "impact": round(impact, 1)})
        
        return {
            "team_id": team_id,
            "total_adjustment": round(-total_impact, 1),
            "injured_players": injured_players,
            "severity": "HIGH" if total_impact >= 15 else "MEDIUM" if total_impact >= 8 else "LOW"
        }
    
    def _calculate_confidence(self, factors: List[Dict]) -> float:
        if not factors:
            return 0
        recommendations = [f["over_rate_at_line"] > 0.5 for f in factors]
        agreement = sum(recommendations) / len(recommendations)
        if agreement >= 0.8 or agreement <= 0.2:
            return 0.85
        elif agreement >= 0.6 or agreement <= 0.4:
            return 0.65
        else:
            return 0.45
    
    def _demo_player_splits(self, player_id: str) -> Dict:
        return {
            "player_id": player_id,
            "home_away": {
                "home": {"games": 25, "points": 27.8, "points_over_rate": 0.62, "rebounds": 7.4, "rebounds_over_rate": 0.54, "assists": 7.1, "assists_over_rate": 0.58},
                "away": {"games": 23, "points": 25.2, "points_over_rate": 0.48, "rebounds": 6.8, "rebounds_over_rate": 0.52, "assists": 6.9, "assists_over_rate": 0.55}
            },
            "rest_days": {
                "0_days": {"games": 8, "points": 23.1, "points_over_rate": 0.38},
                "1_days": {"games": 28, "points": 26.4, "points_over_rate": 0.54},
                "2_days": {"games": 10, "points": 28.9, "points_over_rate": 0.70},
                "4plus_days": {"games": 2, "points": 30.5, "points_over_rate": 1.0}
            },
            "last_n": {
                "last_5": {"points": 29.2, "points_over_rate": 0.80, "trend": "hot"},
                "last_10": {"points": 27.5, "points_over_rate": 0.60, "trend": "above_average"},
                "last_20": {"points": 26.1, "points_over_rate": 0.55, "trend": "average"}
            },
            "vs_team": {
                "gsw": {"games": 4, "points": 31.5, "points_over_rate": 0.75},
                "bos": {"games": 3, "points": 24.3, "points_over_rate": 0.33}
            }
        }
    
    def _demo_betting_percentages(self, game_id: str) -> Dict:
        return {
            "game_id": game_id or "demo_game",
            "home": {"team": "Los Angeles Lakers", "ticket_percent": 68, "money_percent": 45},
            "away": {"team": "Golden State Warriors", "ticket_percent": 32, "money_percent": 55},
            "opening_line": -4.5,
            "current_line": -3.5,
            "is_primetime": True,
            "total_bets": 15420,
            "sharp_action": "away"
        }
    
    def _demo_injuries(self, sport: str) -> List[Dict]:
        return [
            {"player_id": "anthony_davis", "player_name": "Anthony Davis", "team_id": "lal", "position": "PF/C", "status": "questionable", "injury": "knee soreness", "avg_points": 24.5, "avg_rebounds": 11.2, "usage_rate": 0.28},
            {"player_id": "draymond_green", "player_name": "Draymond Green", "team_id": "gsw", "position": "PF", "status": "out", "injury": "calf strain", "avg_points": 9.2, "avg_rebounds": 6.8, "usage_rate": 0.14}
        ]


playbook_service = PlaybookAPIService()
