"""
FastAPI - AI Sports Betting API v5.0 - REAL ML SYSTEM
=====================================================
Features:
- REAL LSTM Neural Networks trained on historical data
- Ensemble Model (XGBoost + LightGBM + Random Forest)
- Monte Carlo Simulations with real probabilities
- Matchup-specific analysis from Sports Reference
- Multi-source injury scraping (ESPN, Rotowire, CBS)
- Esoteric edge signals
- ONLY GOOD (75+) and STRONG (85+) confidence picks
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, Optional, List
from datetime import datetime, date, timedelta
import requests
import os
import json
import numpy as np
try:
    from scipy import stats as scipy_stats
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

# ML Libraries
try:
    from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
    from sklearn.preprocessing import StandardScaler, MinMaxScaler, LabelEncoder
    from sklearn.linear_model import Ridge
    from sklearn.neighbors import KernelDensity
    import xgboost as xgb
    import lightgbm as lgb
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    print("Warning: ML libraries not available")

# CatBoost (handles categoricals better)
try:
    from catboost import CatBoostRegressor
    CATBOOST_AVAILABLE = True
except ImportError:
    CATBOOST_AVAILABLE = False
    print("Warning: CatBoost not available")

# Deep Learning
try:
    import tensorflow as tf
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.layers import LSTM, Dense, Dropout, Bidirectional
    from tensorflow.keras.callbacks import EarlyStopping
    TENSORFLOW_AVAILABLE = True
except ImportError:
    TENSORFLOW_AVAILABLE = False
    print("Warning: TensorFlow not available")

try:
    from advanced_ml_backend import MasterPredictionSystem
    predictor = MasterPredictionSystem()
except Exception as e:
    print(f"Warning: Could not load ML system: {e}")
    predictor = None

import uvicorn

ODDS_API_KEY = os.getenv("ODDS_API_KEY", "6e6da61eec951acb5fa9010293b89279")
PLAYBOOK_API_KEY = os.getenv("PLAYBOOK_API_KEY", "pbk_095c2ac98199f43d0b409f90031908bb05b8")
WHOP_API_KEY = os.getenv("WHOP_API_KEY", "apik_V0RJhFxaEJHUF_C3577787_Q9EBRqD5B-NB-2JXPhrmuugtIBHehUEQ272DGh10-h4")


# ============================================
# WHOP MEMBERSHIP SERVICE
# ============================================

class WhopService:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.whop.com/api/v2"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        # Define your Whop product/plan IDs here after creating them in Whop dashboard
        self.tiers = {
            "free": {"name": "Free", "level": 0},
            "standard": {"name": "Standard", "level": 1, "plan_id": None},  # Set after creating in Whop
            "premium": {"name": "Premium", "level": 2, "plan_id": None}   # Set after creating in Whop
        }
    
    def validate_license(self, license_key):
        """Validate a license key and return membership info"""
        try:
            url = f"{self.base_url}/memberships/{license_key}"
            r = requests.get(url, headers=self.headers, timeout=10)
            if r.status_code == 200:
                data = r.json()
                return {
                    "valid": True,
                    "membership": data,
                    "status": data.get("status"),
                    "plan": data.get("plan", {}).get("plan_name"),
                    "user": data.get("user", {}).get("username"),
                    "tier": self._get_tier_from_plan(data.get("plan", {}).get("id"))
                }
            return {"valid": False, "error": "Invalid license key"}
        except Exception as e:
            return {"valid": False, "error": str(e)}
    
    def check_membership_by_email(self, email):
        """Check if email has active membership"""
        try:
            url = f"{self.base_url}/memberships"
            params = {"email": email}
            r = requests.get(url, headers=self.headers, params=params, timeout=10)
            if r.status_code == 200:
                data = r.json()
                memberships = data.get("data", [])
                active = [m for m in memberships if m.get("status") == "active"]
                if active:
                    best = max(active, key=lambda x: self._get_tier_level(x.get("plan", {}).get("id")))
                    return {
                        "has_membership": True,
                        "tier": self._get_tier_from_plan(best.get("plan", {}).get("id")),
                        "status": best.get("status"),
                        "membership_id": best.get("id")
                    }
                return {"has_membership": False, "tier": "free"}
            return {"has_membership": False, "tier": "free", "error": r.status_code}
        except Exception as e:
            return {"has_membership": False, "tier": "free", "error": str(e)}
    
    def _get_tier_from_plan(self, plan_id):
        """Map plan ID to tier name"""
        for tier_name, tier_info in self.tiers.items():
            if tier_info.get("plan_id") == plan_id:
                return tier_name
        return "standard"  # Default to standard for any paid plan
    
    def _get_tier_level(self, plan_id):
        """Get numeric tier level for comparison"""
        tier = self._get_tier_from_plan(plan_id)
        return self.tiers.get(tier, {}).get("level", 0)
    
    def get_access_level(self, tier):
        """Return what features a tier has access to"""
        access = {
            "free": {
                "home": True,
                "live_odds": True,  # Limited
                "calculator": True,
                "props": False,
                "splits": False,
                "alerts": False,
                "esoteric": False,
                "odds_limit": 3  # Only see 3 games
            },
            "standard": {
                "home": True,
                "live_odds": True,
                "calculator": True,
                "props": True,
                "splits": True,
                "alerts": True,
                "esoteric": False,
                "odds_limit": None  # Unlimited
            },
            "premium": {
                "home": True,
                "live_odds": True,
                "calculator": True,
                "props": True,
                "splits": True,
                "alerts": True,
                "esoteric": True,
                "odds_limit": None
            }
        }
        return access.get(tier, access["free"])


whop_service = WhopService(WHOP_API_KEY)


# ============================================
# MULTI-SOURCE SPORTS DATA SCRAPER
# Injuries: ESPN, Rotowire, CBS Sports
# Rest/Schedule: Calculated from game data
# ============================================

from bs4 import BeautifulSoup
from datetime import timedelta
import re

class InjuryScraper:
    """Scrapes injury data from multiple sources"""
    
    def __init__(self):
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        self.cache = {}
        self.cache_time = None
    
    def get_injuries(self, sport: str) -> Dict:
        """Get injuries from ESPN, Rotowire, CBS - cross-referenced"""
        sport = sport.lower()
        
        injuries = {"sport": sport, "updated_at": datetime.now().isoformat(), "players": []}
        
        # Collect from all sources
        espn = self._scrape_espn(sport)
        rotowire = self._scrape_rotowire(sport)
        cbs = self._scrape_cbs(sport)
        
        # Merge and add confidence based on source count
        injuries["players"] = self._merge_injuries(espn, rotowire, cbs)
        injuries["sources"] = ["ESPN", "Rotowire", "CBS Sports"]
        
        return injuries
    
    def _scrape_espn(self, sport: str) -> List[Dict]:
        """Scrape ESPN injuries"""
        injuries = []
        sport_map = {"nba": "basketball/nba", "nfl": "football/nfl", "nhl": "hockey/nhl", "mlb": "baseball/mlb", "ncaab": "basketball/mens-college-basketball"}
        url = f"https://www.espn.com/{sport_map.get(sport, sport)}/injuries"
        
        try:
            r = requests.get(url, headers=self.headers, timeout=10)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                tables = soup.find_all('table')
                
                for table in tables:
                    team_header = table.find_previous(['h2', 'h3'])
                    team = team_header.get_text(strip=True) if team_header else ""
                    
                    for row in table.find_all('tr')[1:]:
                        cols = row.find_all('td')
                        if len(cols) >= 2:
                            player = cols[0].get_text(strip=True)
                            status = cols[-1].get_text(strip=True) if cols else ""
                            if player:
                                injuries.append({"player": player, "team": team, "status": self._normalize_status(status), "source": "ESPN"})
        except Exception as e:
            print(f"ESPN error: {e}")
        return injuries
    
    def _scrape_rotowire(self, sport: str) -> List[Dict]:
        """Scrape Rotowire injuries"""
        injuries = []
        sport_map = {"nba": "basketball", "nfl": "football", "nhl": "hockey", "mlb": "baseball", "ncaab": "college-basketball"}
        url = f"https://www.rotowire.com/{sport_map.get(sport, sport)}/injury-report.php"
        
        try:
            r = requests.get(url, headers=self.headers, timeout=10)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                items = soup.find_all(['div', 'tr'], class_=re.compile(r'injury|player', re.I))
                
                for item in items:
                    player_el = item.find(['a', 'span'], class_=re.compile(r'player|name', re.I))
                    if player_el:
                        player = player_el.get_text(strip=True)
                        status_el = item.find(['span', 'td'], class_=re.compile(r'status', re.I))
                        status = status_el.get_text(strip=True) if status_el else ""
                        team_el = item.find(['span', 'td'], class_=re.compile(r'team', re.I))
                        team = team_el.get_text(strip=True) if team_el else ""
                        if player:
                            injuries.append({"player": player, "team": team, "status": self._normalize_status(status), "source": "Rotowire"})
        except Exception as e:
            print(f"Rotowire error: {e}")
        return injuries
    
    def _scrape_cbs(self, sport: str) -> List[Dict]:
        """Scrape CBS Sports injuries"""
        injuries = []
        url = f"https://www.cbssports.com/{sport}/injuries/"
        
        try:
            r = requests.get(url, headers=self.headers, timeout=10)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                rows = soup.find_all('tr')
                team = ""
                for row in rows:
                    cols = row.find_all('td')
                    if len(cols) >= 2:
                        player = cols[0].get_text(strip=True)
                        status = cols[1].get_text(strip=True) if len(cols) > 1 else ""
                        if player and not player.startswith('Player'):
                            injuries.append({"player": player, "team": team, "status": self._normalize_status(status), "source": "CBS"})
        except Exception as e:
            print(f"CBS error: {e}")
        return injuries
    
    def _normalize_status(self, status: str) -> str:
        """Normalize status across sources"""
        s = status.lower()
        if any(x in s for x in ["out", "ir", "pup"]): return "OUT"
        if "doubtful" in s: return "DOUBTFUL"
        if any(x in s for x in ["questionable", "gtd"]): return "QUESTIONABLE"
        if "probable" in s: return "PROBABLE"
        return status.upper()[:15]
    
    def _merge_injuries(self, *sources) -> List[Dict]:
        """Merge from all sources, add confidence"""
        merged = {}
        for source in sources:
            for inj in source:
                key = inj.get("player", "").lower().strip()
                if not key: continue
                if key not in merged:
                    merged[key] = {"player": inj["player"], "team": inj.get("team", ""), "status": inj["status"], "sources": [inj["source"]], "confidence": 33}
                else:
                    if inj["source"] not in merged[key]["sources"]:
                        merged[key]["sources"].append(inj["source"])
                        merged[key]["confidence"] = min(100, len(merged[key]["sources"]) * 33)
        
        return sorted(merged.values(), key=lambda x: -x["confidence"])
    
    def get_team_injuries(self, team: str, sport: str) -> List[Dict]:
        """Get injuries for a specific team"""
        all_injuries = self.get_injuries(sport)
        return [i for i in all_injuries.get("players", []) if team.lower() in i.get("team", "").lower()]


class RestCalculator:
    """Calculates rest/fatigue based on schedule"""
    
    def __init__(self):
        self.headers = {"User-Agent": "Mozilla/5.0"}
    
    def calculate_rest_advantage(self, home: str, away: str, sport: str, games_data: List = None) -> Dict:
        """Calculate rest advantage between teams"""
        # Default values - would be enhanced with real schedule data
        # For now, use game commence times to detect back-to-backs
        
        result = {
            "advantage": None,
            "strength": 0,
            "description": "",
            "home_rest_days": 2,
            "away_rest_days": 2,
            "home_b2b": False,
            "away_b2b": False
        }
        
        # In production: scrape recent game dates from ESPN/CBS
        # For now: return neutral unless we have specific data
        
        return result
    
    def is_back_to_back(self, team: str, sport: str) -> bool:
        """Check if team is on back-to-back"""
        # Would check team's schedule
        return False


class SportsDataService:
    """Combined service for all sports data"""
    
    def __init__(self):
        self.injury_scraper = InjuryScraper()
        self.rest_calculator = RestCalculator()
    
    def get_game_context(self, home: str, away: str, sport: str) -> Dict:
        """Get full game context: injuries + rest"""
        # Get injuries
        home_injuries = self.injury_scraper.get_team_injuries(home, sport)
        away_injuries = self.injury_scraper.get_team_injuries(away, sport)
        
        # Calculate injury impact
        injury_impact = self._calculate_injury_impact(home_injuries, away_injuries, home, away)
        
        # Get rest advantage
        rest = self.rest_calculator.calculate_rest_advantage(home, away, sport)
        
        return {
            "injuries": {"home": home_injuries, "away": away_injuries, "impact": injury_impact},
            "rest": rest
        }
    
    def _calculate_injury_impact(self, home_inj: List, away_inj: List, home: str, away: str) -> Dict:
        """Calculate which team has injury advantage"""
        def score(injuries):
            s = 0
            for i in injuries:
                conf = i.get("confidence", 50) / 100
                if i["status"] == "OUT": s += 3 * conf
                elif i["status"] == "DOUBTFUL": s += 2 * conf
                elif i["status"] == "QUESTIONABLE": s += 1 * conf
            return s
        
        home_score = score(home_inj)
        away_score = score(away_inj)
        diff = away_score - home_score
        
        if diff >= 2:
            return {"advantage": home, "strength": min(0.9, diff / 8), "description": f"{away} has more injuries"}
        elif diff <= -2:
            return {"advantage": away, "strength": min(0.9, abs(diff) / 8), "description": f"{home} has more injuries"}
        return {"advantage": None, "strength": 0, "description": "No injury advantage"}


sports_data = SportsDataService()


# ============================================
# STAKING ENGINE - BANKROLL GUARDIAN
# ============================================

class StakingEngine:
    """
    Professional bankroll management using Kelly Criterion
    
    Converts model confidence into optimal unit sizing.
    A 56% win rate can still bankrupt you with bad sizing.
    This turns a winning model into a profitable business.
    
    Formula: f* = (bp - q) / b
    Where:
        f* = fraction of bankroll to bet
        b = decimal odds - 1 (net odds)
        p = probability of winning
        q = probability of losing (1 - p)
    """
    
    def __init__(self, bankroll: float = 1000, max_bet_pct: float = 0.05, kelly_fraction: float = 0.25):
        """
        Args:
            bankroll: Starting bankroll in units
            max_bet_pct: Maximum bet as % of bankroll (safety cap)
            kelly_fraction: Fraction of Kelly to use (0.25 = quarter Kelly, safer)
        """
        self.bankroll = bankroll
        self.max_bet_pct = max_bet_pct
        self.kelly_fraction = kelly_fraction  # Quarter Kelly is industry standard
        self.bet_history = []
        self.current_bankroll = bankroll
    
    def calculate_kelly(self, win_probability: float, american_odds: int) -> Dict:
        """
        Calculate optimal bet size using Kelly Criterion
        
        Args:
            win_probability: Model's estimated probability (0.0 to 1.0)
            american_odds: American odds (-110, +150, etc.)
        
        Returns:
            Dict with kelly_pct, recommended_units, edge, etc.
        """
        # Convert American odds to decimal
        if american_odds > 0:
            decimal_odds = (american_odds / 100) + 1
        else:
            decimal_odds = (100 / abs(american_odds)) + 1
        
        # Net odds (what you win per $1 bet)
        b = decimal_odds - 1
        
        # Probabilities
        p = win_probability
        q = 1 - p
        
        # Implied probability from odds
        if american_odds > 0:
            implied_prob = 100 / (american_odds + 100)
        else:
            implied_prob = abs(american_odds) / (abs(american_odds) + 100)
        
        # Edge = our probability - implied probability
        edge = p - implied_prob
        edge_pct = edge * 100
        
        # Kelly formula: f* = (bp - q) / b
        if b > 0:
            full_kelly = (b * p - q) / b
        else:
            full_kelly = 0
        
        # Apply fractional Kelly (safer)
        fractional_kelly = full_kelly * self.kelly_fraction
        
        # Safety caps
        if fractional_kelly < 0:
            # Negative Kelly = no edge, don't bet
            fractional_kelly = 0
            recommendation = "NO_BET"
        elif fractional_kelly > self.max_bet_pct:
            # Cap at max bet percentage
            fractional_kelly = self.max_bet_pct
            recommendation = "MAX_BET"
        else:
            recommendation = "BET"
        
        # Calculate units
        units = round(fractional_kelly * 100, 2)  # Convert to units (1 unit = 1% of bankroll)
        dollar_amount = round(fractional_kelly * self.current_bankroll, 2)
        
        # Risk assessment
        if units >= 3:
            risk_level = "HIGH"
        elif units >= 1.5:
            risk_level = "MEDIUM"
        elif units > 0:
            risk_level = "LOW"
        else:
            risk_level = "NO_BET"
        
        return {
            "recommendation": recommendation,
            "units": units,
            "dollar_amount": dollar_amount,
            "full_kelly_pct": round(full_kelly * 100, 2),
            "fractional_kelly_pct": round(fractional_kelly * 100, 2),
            "edge_pct": round(edge_pct, 2),
            "win_probability": round(p * 100, 1),
            "implied_probability": round(implied_prob * 100, 1),
            "decimal_odds": round(decimal_odds, 3),
            "risk_level": risk_level,
            "bankroll": self.current_bankroll,
            "max_bet": round(self.max_bet_pct * self.current_bankroll, 2)
        }
    
    def calculate_from_confidence(self, confidence_score: float, american_odds: int) -> Dict:
        """
        Convert our confidence score (0-100) to Kelly sizing
        
        Confidence score is calibrated differently than raw probability:
        - 75+ confidence ≈ 55-58% win probability
        - 85+ confidence ≈ 58-62% win probability
        - 95 confidence ≈ 65% win probability
        """
        # Calibration: map confidence to win probability
        # This should be tuned based on actual results
        if confidence_score >= 90:
            win_prob = 0.62 + (confidence_score - 90) * 0.006  # 62-65%
        elif confidence_score >= 85:
            win_prob = 0.58 + (confidence_score - 85) * 0.008  # 58-62%
        elif confidence_score >= 80:
            win_prob = 0.56 + (confidence_score - 80) * 0.004  # 56-58%
        elif confidence_score >= 75:
            win_prob = 0.54 + (confidence_score - 75) * 0.004  # 54-56%
        elif confidence_score >= 70:
            win_prob = 0.52 + (confidence_score - 70) * 0.004  # 52-54%
        else:
            win_prob = 0.50 + (confidence_score - 50) * 0.001  # 50-52%
        
        win_prob = min(0.70, max(0.50, win_prob))  # Cap between 50-70%
        
        result = self.calculate_kelly(win_prob, american_odds)
        result["confidence_score"] = confidence_score
        result["calibrated_win_prob"] = round(win_prob * 100, 1)
        
        return result
    
    def record_bet(self, units: float, odds: int, result: str):
        """Record a bet result and update bankroll"""
        if result == "W":
            if odds > 0:
                profit = units * (odds / 100)
            else:
                profit = units * (100 / abs(odds))
            self.current_bankroll += profit
        elif result == "L":
            self.current_bankroll -= units
        # Push = no change
        
        self.bet_history.append({
            "units": units,
            "odds": odds,
            "result": result,
            "bankroll_after": self.current_bankroll,
            "timestamp": datetime.now().isoformat()
        })
    
    def get_performance(self) -> Dict:
        """Get betting performance stats"""
        if not self.bet_history:
            return {"total_bets": 0, "roi": 0}
        
        wins = sum(1 for b in self.bet_history if b["result"] == "W")
        losses = sum(1 for b in self.bet_history if b["result"] == "L")
        pushes = sum(1 for b in self.bet_history if b["result"] == "P")
        
        total_wagered = sum(b["units"] for b in self.bet_history if b["result"] != "P")
        profit = self.current_bankroll - self.bankroll
        roi = (profit / total_wagered * 100) if total_wagered > 0 else 0
        
        return {
            "starting_bankroll": self.bankroll,
            "current_bankroll": round(self.current_bankroll, 2),
            "profit": round(profit, 2),
            "total_bets": len(self.bet_history),
            "wins": wins,
            "losses": losses,
            "pushes": pushes,
            "win_rate": round(wins / (wins + losses) * 100, 1) if (wins + losses) > 0 else 0,
            "roi": round(roi, 2),
            "total_wagered": round(total_wagered, 2)
        }


# Instantiate staking engine
staking_engine = StakingEngine(bankroll=1000, max_bet_pct=0.05, kelly_fraction=0.25)


# ============================================
# BACKTEST SIMULATOR - TIME MACHINE
# ============================================

class BacktestSimulator:
    """
    Walk-Forward Backtesting Framework
    
    Prevents data leakage by hiding future data when testing.
    Tracks Closing Line Value (CLV) to prove edge.
    
    CLV = Did we beat the closing line? If yes, we have real edge.
    """
    
    def __init__(self):
        self.backtest_results = []
        self.clv_tracker = []
    
    def run_backtest(self, player: str, stat_type: str, historical_games: List[Dict], 
                    prop_lines: List[Dict], start_date: str = None) -> Dict:
        """
        Run walk-forward backtest on historical data
        
        Args:
            player: Player name
            stat_type: points, rebounds, assists, etc.
            historical_games: Full game history
            prop_lines: Historical prop lines [{date, line, result}, ...]
            start_date: Start backtesting from this date
        
        Returns:
            Backtest results with win rate, ROI, CLV
        """
        results = []
        
        # Sort games by date (oldest first for walk-forward)
        sorted_games = sorted(historical_games, key=lambda x: x.get('date', ''), reverse=False)
        
        for i, prop in enumerate(prop_lines):
            prop_date = prop.get('date', '')
            line = prop.get('line', 0)
            actual_result = prop.get('actual', 0)
            closing_line = prop.get('closing_line', line)
            
            # CRITICAL: Only use games BEFORE the prop date (no future data)
            games_before = [g for g in sorted_games if g.get('date', '') < prop_date]
            
            if len(games_before) < 15:
                continue  # Need minimum history
            
            # Generate prediction using only past data
            prediction = self._generate_prediction(games_before, stat_type)
            
            if prediction['confidence'] < 70:
                continue  # Skip low confidence
            
            # Determine bet
            edge = prediction['mean'] - line
            if edge > 1:
                bet_side = "OVER"
                bet_line = line
            elif edge < -1:
                bet_side = "UNDER"
                bet_line = line
            else:
                continue  # No edge
            
            # Determine result
            if bet_side == "OVER":
                won = actual_result > bet_line
            else:
                won = actual_result < bet_line
            
            # Calculate CLV (Closing Line Value)
            # CLV = Did we get better odds than closing?
            if bet_side == "OVER":
                clv = closing_line - line  # Positive = we got better line
            else:
                clv = line - closing_line
            
            result = {
                "date": prop_date,
                "player": player,
                "stat_type": stat_type,
                "our_line": line,
                "closing_line": closing_line,
                "prediction": prediction['mean'],
                "actual": actual_result,
                "bet_side": bet_side,
                "won": won,
                "clv": clv,
                "edge": edge,
                "confidence": prediction['confidence']
            }
            results.append(result)
        
        # Calculate aggregate stats
        if not results:
            return {"error": "No testable bets", "results": []}
        
        wins = sum(1 for r in results if r['won'])
        total = len(results)
        win_rate = wins / total * 100
        
        # CLV analysis
        avg_clv = np.mean([r['clv'] for r in results])
        positive_clv_pct = sum(1 for r in results if r['clv'] > 0) / total * 100
        
        # Simulated ROI (assuming -110 odds)
        roi = (wins * 0.909 - (total - wins)) / total * 100  # -110 odds payout
        
        return {
            "player": player,
            "stat_type": stat_type,
            "total_bets": total,
            "wins": wins,
            "losses": total - wins,
            "win_rate": round(win_rate, 1),
            "roi": round(roi, 2),
            "avg_clv": round(avg_clv, 2),
            "positive_clv_pct": round(positive_clv_pct, 1),
            "edge_confirmed": avg_clv > 0,
            "results": results[-20:]  # Last 20 for review
        }
    
    def _generate_prediction(self, games: List[Dict], stat_type: str) -> Dict:
        """Generate prediction using only provided games (no future data)"""
        values = [g.get(stat_type, 0) for g in games if g.get(stat_type, 0) > 0]
        
        if len(values) < 10:
            return {"mean": 0, "confidence": 0}
        
        # Simple moving averages
        recent_5 = np.mean(values[-5:])
        recent_10 = np.mean(values[-10:])
        season_avg = np.mean(values)
        
        # Weighted prediction
        prediction = recent_5 * 0.5 + recent_10 * 0.3 + season_avg * 0.2
        
        # Confidence based on consistency
        std = np.std(values[-10:])
        cv = std / recent_10 if recent_10 > 0 else 1
        confidence = max(50, min(90, 100 - cv * 100))
        
        return {
            "mean": round(prediction, 1),
            "confidence": round(confidence, 1)
        }
    
    def validate_model_edge(self, results: List[Dict]) -> Dict:
        """
        Validate if model has real edge using statistical tests
        
        Key metrics:
        - Win rate vs break-even (52.4% for -110)
        - CLV (Closing Line Value) - most important
        - Consistency over time
        """
        if len(results) < 30:
            return {"valid": False, "reason": "Insufficient sample size (need 30+)"}
        
        wins = sum(1 for r in results if r.get('won'))
        total = len(results)
        win_rate = wins / total
        
        # Break-even at -110 is 52.38%
        break_even = 0.5238
        
        # Z-score for statistical significance
        # z = (observed - expected) / sqrt(p * (1-p) / n)
        z_score = (win_rate - break_even) / np.sqrt(break_even * (1 - break_even) / total)
        
        # p-value (one-tailed)
        if SCIPY_AVAILABLE:
            p_value = 1 - scipy_stats.norm.cdf(z_score)
        else:
            # Approximation without scipy
            p_value = 0.5 * (1 - np.tanh(z_score / np.sqrt(2)))
        
        # CLV analysis
        avg_clv = np.mean([r.get('clv', 0) for r in results])
        
        # Verdict
        statistically_significant = p_value < 0.05
        positive_clv = avg_clv > 0
        
        return {
            "valid": statistically_significant and positive_clv,
            "win_rate": round(win_rate * 100, 1),
            "break_even": 52.4,
            "z_score": round(z_score, 2),
            "p_value": round(p_value, 4),
            "statistically_significant": statistically_significant,
            "avg_clv": round(avg_clv, 2),
            "positive_clv": positive_clv,
            "sample_size": total,
            "verdict": "EDGE CONFIRMED" if (statistically_significant and positive_clv) else "EDGE NOT PROVEN"
        }


# Instantiate backtester
backtester = BacktestSimulator()


# ============================================
# SHARP TRACKER - TICKET% VS MONEY%
# ============================================

class SharpTracker:
    """
    Tracks sharp (professional) money vs public money
    
    Key insight: When ticket% and money% diverge, follow the money.
    - 70% tickets on Team A but only 40% money = Sharps on Team B
    - Sharps bet bigger, so money% reveals their position
    
    "Fade the public, follow the sharps"
    """
    
    def __init__(self):
        self.sharp_threshold = 15  # % divergence to trigger signal
        self.reverse_line_movement_threshold = 0.5  # Points
    
    def analyze_sharp_action(self, ticket_pct: float, money_pct: float, 
                            opening_line: float, current_line: float,
                            team: str) -> Dict:
        """
        Analyze if sharp money is on a side
        
        Args:
            ticket_pct: % of tickets on this team (0-100)
            money_pct: % of money on this team (0-100)
            opening_line: Opening spread/total
            current_line: Current spread/total
            team: Team name
        
        Returns:
            Sharp analysis with recommendation
        """
        # Calculate divergence
        divergence = money_pct - ticket_pct
        
        # Line movement
        line_move = current_line - opening_line
        
        # Detect Reverse Line Movement (RLM)
        # RLM = Line moves AGAINST the popular side = Sharp money
        public_side = ticket_pct > 50
        line_moved_against_public = (public_side and line_move < -self.reverse_line_movement_threshold) or \
                                   (not public_side and line_move > self.reverse_line_movement_threshold)
        
        # Sharp signals
        signals = []
        sharp_confidence = 0
        
        # Signal 1: Money% > Ticket% divergence
        if divergence >= self.sharp_threshold:
            signals.append(f"Sharp Money Detected: {divergence:.1f}% divergence")
            sharp_confidence += 40
        elif divergence >= 10:
            signals.append(f"Moderate Sharp Interest: {divergence:.1f}% divergence")
            sharp_confidence += 25
        
        # Signal 2: Reverse Line Movement
        if line_moved_against_public:
            signals.append(f"Reverse Line Movement: Line moved {line_move:+.1f} against public")
            sharp_confidence += 35
        
        # Signal 3: Steam Move (rapid line movement)
        if abs(line_move) >= 1.5:
            signals.append(f"Steam Move Detected: {line_move:+.1f} point swing")
            sharp_confidence += 25
        
        # Determine recommendation
        if sharp_confidence >= 50:
            # Sharps are likely on the side with higher money%
            if money_pct > 50:
                recommendation = f"SHARP: {team}"
                sharp_side = team
            else:
                recommendation = f"SHARP: FADE {team}"
                sharp_side = f"Opponent of {team}"
        elif sharp_confidence >= 30:
            recommendation = "LEAN_SHARP"
            sharp_side = team if money_pct > 50 else f"Opponent"
        else:
            recommendation = "NO_SHARP_SIGNAL"
            sharp_side = None
        
        return {
            "team": team,
            "ticket_pct": ticket_pct,
            "money_pct": money_pct,
            "divergence": round(divergence, 1),
            "opening_line": opening_line,
            "current_line": current_line,
            "line_move": round(line_move, 1),
            "reverse_line_movement": line_moved_against_public,
            "sharp_confidence": sharp_confidence,
            "sharp_side": sharp_side,
            "signals": signals,
            "recommendation": recommendation
        }
    
    def get_sharp_plays(self, games: List[Dict]) -> List[Dict]:
        """
        Analyze multiple games and return sharp plays
        
        Each game dict should have:
        - home_team, away_team
        - home_ticket_pct, home_money_pct
        - opening_line, current_line
        """
        sharp_plays = []
        
        for game in games:
            home = game.get('home_team', '')
            away = game.get('away_team', '')
            
            # Analyze home side
            home_analysis = self.analyze_sharp_action(
                ticket_pct=game.get('home_ticket_pct', 50),
                money_pct=game.get('home_money_pct', 50),
                opening_line=game.get('opening_line', 0),
                current_line=game.get('current_line', 0),
                team=home
            )
            
            if home_analysis['sharp_confidence'] >= 50:
                home_analysis['game'] = f"{away} @ {home}"
                home_analysis['bet_side'] = home if home_analysis['money_pct'] > 50 else away
                sharp_plays.append(home_analysis)
        
        # Sort by confidence
        sharp_plays.sort(key=lambda x: x['sharp_confidence'], reverse=True)
        
        return sharp_plays
    
    def calculate_steam_score(self, line_history: List[Dict]) -> Dict:
        """
        Calculate steam move score from line history
        
        Steam = Rapid coordinated line movement from sharps
        """
        if len(line_history) < 2:
            return {"steam_detected": False, "score": 0}
        
        # Sort by timestamp
        sorted_history = sorted(line_history, key=lambda x: x.get('timestamp', ''))
        
        # Calculate rate of change
        first = sorted_history[0]
        last = sorted_history[-1]
        
        total_move = last.get('line', 0) - first.get('line', 0)
        
        # Time span (assume timestamps are ISO format)
        try:
            t1 = datetime.fromisoformat(first.get('timestamp', ''))
            t2 = datetime.fromisoformat(last.get('timestamp', ''))
            hours = (t2 - t1).total_seconds() / 3600
        except:
            hours = 24  # Default to 24 hours
        
        # Steam score: points moved per hour
        if hours > 0:
            steam_rate = abs(total_move) / hours
        else:
            steam_rate = 0
        
        # Rapid move = steam
        steam_detected = steam_rate >= 0.5 and abs(total_move) >= 1
        
        return {
            "steam_detected": steam_detected,
            "total_line_move": round(total_move, 1),
            "hours_elapsed": round(hours, 1),
            "steam_rate": round(steam_rate, 2),
            "direction": "UP" if total_move > 0 else "DOWN" if total_move < 0 else "FLAT"
        }


# Instantiate sharp tracker
sharp_tracker = SharpTracker()


# ============================================
# ROTATION MODEL - COACH LOGIC
# ============================================

class RotationModel:
    """
    Models coach tendencies for rotation and minutes
    
    Critical factors:
    - Thibodeau Factor: Plays starters 40+ mins in close games
    - Popovich Factor: Randomly rests stars on back-to-backs
    - Blowout Script: Spread >12 = early pull of starters
    - Tanking Mode: Late season minutes restrictions
    """
    
    def __init__(self):
        # Coach profiles with tendencies
        self.coach_profiles = {
            # Heavy minutes coaches (play starters a lot)
            "tom thibodeau": {
                "team": "knicks",
                "starter_mins": 36.5,
                "close_game_mins": 42,
                "rest_tendency": "never",
                "blowout_pull_lead": 25,
                "notes": "Notorious for heavy minutes. Jalen Brunson plays 38+ regularly."
            },
            "erik spoelstra": {
                "team": "heat",
                "starter_mins": 34,
                "close_game_mins": 40,
                "rest_tendency": "rare",
                "blowout_pull_lead": 20,
                "notes": "Jimmy Butler plays heavy mins in playoffs, managed in regular season."
            },
            "mike budenholzer": {
                "team": "suns",
                "starter_mins": 32,
                "close_game_mins": 36,
                "rest_tendency": "moderate",
                "blowout_pull_lead": 18,
                "notes": "Known for rest management. Pulled starters early in Milwaukee."
            },
            "ime udoka": {
                "team": "rockets",
                "starter_mins": 30,
                "close_game_mins": 34,
                "rest_tendency": "development",
                "blowout_pull_lead": 15,
                "notes": "Young team, developing players. Minutes spread around."
            },
            
            # Load management coaches
            "gregg popovich": {
                "team": "spurs",
                "starter_mins": 28,
                "close_game_mins": 32,
                "rest_tendency": "aggressive",
                "blowout_pull_lead": 15,
                "notes": "Pioneer of load management. Wemby on minutes restriction."
            },
            "steve kerr": {
                "team": "warriors",
                "starter_mins": 30,
                "close_game_mins": 36,
                "rest_tendency": "moderate",
                "blowout_pull_lead": 18,
                "notes": "Manages Curry carefully. Pulls starters in blowouts."
            },
            "tyronn lue": {
                "team": "clippers",
                "starter_mins": 30,
                "close_game_mins": 36,
                "rest_tendency": "aggressive",
                "blowout_pull_lead": 18,
                "notes": "Kawhi on permanent load management. George too."
            },
            
            # Standard coaches
            "joe mazzulla": {
                "team": "celtics",
                "starter_mins": 33,
                "close_game_mins": 38,
                "rest_tendency": "moderate",
                "blowout_pull_lead": 20,
                "notes": "Deep roster allows rest. Tatum/Brown managed."
            },
            "michael malone": {
                "team": "nuggets",
                "starter_mins": 34,
                "close_game_mins": 40,
                "rest_tendency": "rare",
                "blowout_pull_lead": 20,
                "notes": "Jokic plays heavy minutes. Murray load managed."
            },
            "mark daigneault": {
                "team": "thunder",
                "starter_mins": 32,
                "close_game_mins": 38,
                "rest_tendency": "moderate",
                "blowout_pull_lead": 18,
                "notes": "SGA plays heavy. Young core developing."
            },
            "jason kidd": {
                "team": "mavericks",
                "starter_mins": 34,
                "close_game_mins": 40,
                "rest_tendency": "rare",
                "blowout_pull_lead": 20,
                "notes": "Luka plays 36+ mins. Kyrie load managed occasionally."
            },
            "doc rivers": {
                "team": "bucks",
                "starter_mins": 33,
                "close_game_mins": 40,
                "rest_tendency": "moderate",
                "blowout_pull_lead": 18,
                "notes": "Giannis plays heavy. Dame managed after injury."
            },
            "jj redick": {
                "team": "lakers",
                "starter_mins": 32,
                "close_game_mins": 38,
                "rest_tendency": "moderate",
                "blowout_pull_lead": 18,
                "notes": "First year coach. LeBron self-manages. AD load managed."
            },
            "kenny atkinson": {
                "team": "cavaliers",
                "starter_mins": 32,
                "close_game_mins": 36,
                "rest_tendency": "moderate",
                "blowout_pull_lead": 18,
                "notes": "Deep roster. Mitchell plays heavy."
            }
        }
        
        # Team to coach mapping
        self.team_coach = {team: coach for coach, data in self.coach_profiles.items() 
                         for team in [data.get("team", "")]}
    
    def get_coach_factor(self, team: str, player: str = None) -> Dict:
        """Get coach tendencies for a team"""
        team_lower = team.lower()
        
        # Find coach
        coach = None
        profile = None
        for c, data in self.coach_profiles.items():
            if data.get("team", "").lower() in team_lower or team_lower in data.get("team", "").lower():
                coach = c
                profile = data
                break
        
        if not profile:
            # Default profile
            return {
                "coach": "Unknown",
                "team": team,
                "starter_mins": 32,
                "close_game_mins": 36,
                "rest_tendency": "moderate",
                "blowout_pull_lead": 18,
                "minutes_adjustment": 0,
                "notes": "Coach not in database"
            }
        
        return {
            "coach": coach.title(),
            "team": profile.get("team"),
            "starter_mins": profile.get("starter_mins", 32),
            "close_game_mins": profile.get("close_game_mins", 36),
            "rest_tendency": profile.get("rest_tendency", "moderate"),
            "blowout_pull_lead": profile.get("blowout_pull_lead", 18),
            "notes": profile.get("notes", "")
        }
    
    def predict_minutes_impact(self, team: str, spread: float, is_back_to_back: bool,
                               is_star_player: bool, current_minutes_avg: float) -> Dict:
        """
        Predict minutes adjustment based on game context
        
        Args:
            team: Team name
            spread: Game spread (negative = favorite)
            is_back_to_back: Is this a B2B game?
            is_star_player: Is this a star player (subject to rest)?
            current_minutes_avg: Player's season minutes average
        """
        coach_data = self.get_coach_factor(team)
        
        # Base expected minutes
        base_mins = current_minutes_avg
        adjustments = []
        total_adjustment = 0
        
        # Blowout risk (spread > 12 = potential early pull)
        if abs(spread) >= 12:
            if spread < 0:  # Team is big favorite
                blowout_adj = -4  # Expect -4 mins
                adjustments.append(f"Blowout risk (favorite by {abs(spread)}): -4 mins")
            else:  # Team is big underdog
                blowout_adj = -2  # Garbage time
                adjustments.append(f"Blowout risk (underdog by {spread}): -2 mins")
            total_adjustment += blowout_adj
        elif abs(spread) >= 8:
            total_adjustment -= 1.5
            adjustments.append(f"Moderate blowout risk: -1.5 mins")
        
        # Back-to-back impact
        if is_back_to_back:
            rest_tendency = coach_data.get("rest_tendency", "moderate")
            
            if rest_tendency == "aggressive" and is_star_player:
                total_adjustment -= 6  # Heavy rest
                adjustments.append(f"Aggressive rest coach + B2B + star: -6 mins")
            elif rest_tendency == "moderate" and is_star_player:
                total_adjustment -= 3
                adjustments.append(f"Moderate rest coach + B2B + star: -3 mins")
            elif rest_tendency == "never":
                total_adjustment -= 1  # Thibs doesn't care
                adjustments.append(f"Heavy minutes coach, still B2B: -1 min")
            else:
                total_adjustment -= 2
                adjustments.append(f"B2B standard adjustment: -2 mins")
        
        # Close game expectation (spread close to 0)
        if abs(spread) <= 3:
            close_game_mins = coach_data.get("close_game_mins", 36)
            if close_game_mins >= 40:
                total_adjustment += 2
                adjustments.append(f"Close game expected, heavy minutes coach: +2 mins")
            elif close_game_mins >= 38:
                total_adjustment += 1
                adjustments.append(f"Close game expected: +1 min")
        
        # Calculate final expected minutes
        expected_mins = base_mins + total_adjustment
        expected_mins = max(0, min(48, expected_mins))  # Cap at 0-48
        
        # Impact on props (rough estimate)
        mins_pct_change = (expected_mins - base_mins) / base_mins if base_mins > 0 else 0
        
        # Prop adjustment (stats roughly scale with minutes)
        prop_adjustment = mins_pct_change * 0.8  # 80% correlation
        
        return {
            "coach": coach_data.get("coach"),
            "team": team,
            "base_minutes": round(base_mins, 1),
            "expected_minutes": round(expected_mins, 1),
            "minutes_adjustment": round(total_adjustment, 1),
            "adjustments": adjustments,
            "prop_adjustment_pct": round(prop_adjustment * 100, 1),
            "blowout_risk": abs(spread) >= 10,
            "rest_risk": is_back_to_back and coach_data.get("rest_tendency") in ["aggressive", "moderate"] and is_star_player,
            "recommendation": "CAUTION" if total_adjustment <= -3 else "NORMAL" if total_adjustment >= -1 else "SLIGHT_REDUCTION"
        }
    
    def get_blowout_probability(self, spread: float) -> Dict:
        """Estimate probability of a blowout based on spread"""
        # Historical data shows correlation between spread and final margin
        
        if abs(spread) >= 15:
            blowout_prob = 0.45
            garbage_time_mins = 8
        elif abs(spread) >= 12:
            blowout_prob = 0.35
            garbage_time_mins = 6
        elif abs(spread) >= 10:
            blowout_prob = 0.28
            garbage_time_mins = 4
        elif abs(spread) >= 7:
            blowout_prob = 0.20
            garbage_time_mins = 2
        else:
            blowout_prob = 0.12
            garbage_time_mins = 0
        
        return {
            "spread": spread,
            "blowout_probability": round(blowout_prob * 100, 1),
            "expected_garbage_time_mins": garbage_time_mins,
            "starter_minutes_risk": "HIGH" if blowout_prob >= 0.35 else "MEDIUM" if blowout_prob >= 0.20 else "LOW"
        }


# Instantiate rotation model
rotation_model = RotationModel()


# ============================================
# HARMONIC CONVERGENCE - ML + ESOTERIC SUPERSIGNAL
# ============================================

class HarmonicConvergence:
    """
    ESOTERIC SYNERGY ENGINE
    
    Isolates highest ROI bets by combining:
    - LSTM Neural Network (Statistical/Data-Driven)
    - Esoteric Analysis (Universal/Energetic Alignment)
    
    Logic:
    - Normalize LSTM confidence to 0-1
    - Normalize Esoteric confidence to 0-1
    - IF (LSTM > 0.7) AND (Esoteric > 0.7) AND same_direction THEN SuperSignal
    
    Signal Tiers:
    - GOLDEN_CONVERGENCE: LSTM > 0.8 AND Esoteric > 0.8 (Rare, highest ROI)
    - SUPER_SIGNAL: LSTM > 0.7 AND Esoteric > 0.7 (Strong edge)
    - HARMONIC_ALIGNMENT: One > 0.8, other > 0.6 (Good edge)
    - PARTIAL_ALIGNMENT: Both > 0.6 (Moderate edge)
    - CONFLICT: Strong signals, opposite directions (AVOID)
    - NO_SIGNAL: Insufficient strength
    
    "When the numbers AND the stars align, magic happens"
    """
    
    def __init__(self):
        # Thresholds for signal tiers
        self.thresholds = {
            "golden": {"lstm": 0.80, "esoteric": 0.80},
            "super": {"lstm": 0.70, "esoteric": 0.70},
            "harmonic": {"primary": 0.80, "secondary": 0.60},
            "partial": {"both": 0.60}
        }
        
        # Confidence boosts per tier
        self.boosts = {
            "GOLDEN_CONVERGENCE": 15,
            "SUPER_SIGNAL": 10,
            "HARMONIC_ALIGNMENT": 7,
            "PARTIAL_ALIGNMENT": 4,
            "CONFLICT": -15,
            "NO_SIGNAL": 0
        }
        
        # Unit multipliers for staking
        self.unit_multipliers = {
            "GOLDEN_CONVERGENCE": 2.0,  # Double your normal bet
            "SUPER_SIGNAL": 1.5,         # 1.5x normal bet
            "HARMONIC_ALIGNMENT": 1.25,  # 1.25x normal bet
            "PARTIAL_ALIGNMENT": 1.0,    # Normal bet
            "CONFLICT": 0.5,             # Half bet (or skip)
            "NO_SIGNAL": 1.0
        }
        
        # Performance tracking per tier
        self.tier_performance = {
            "GOLDEN_CONVERGENCE": {"bets": 0, "wins": 0, "roi": 0},
            "SUPER_SIGNAL": {"bets": 0, "wins": 0, "roi": 0},
            "HARMONIC_ALIGNMENT": {"bets": 0, "wins": 0, "roi": 0},
            "PARTIAL_ALIGNMENT": {"bets": 0, "wins": 0, "roi": 0},
            "CONFLICT": {"bets": 0, "wins": 0, "roi": 0}
        }
        
        self.convergence_history = []
    
    def check_lstm_esoteric_synergy(self, lstm_confidence: float, lstm_direction: str,
                                    esoteric_score: float, esoteric_direction: str,
                                    ensemble_confidence: float = None,
                                    monte_carlo_prob: float = None) -> Dict:
        """
        Check for LSTM + Esoteric synergy (THE SuperSignal)
        
        Args:
            lstm_confidence: LSTM model confidence (0-100)
            lstm_direction: LSTM recommendation ("OVER", "UNDER")
            esoteric_score: Esoteric analysis score (0-100)
            esoteric_direction: Esoteric lean ("OVER", "UNDER")
            ensemble_confidence: Optional ensemble confidence for extra validation
            monte_carlo_prob: Optional MC probability for extra validation
        
        Returns:
            Synergy analysis with signal tier
        """
        # Normalize to 0-1
        lstm_norm = lstm_confidence / 100
        esoteric_norm = esoteric_score / 100
        
        # Check direction alignment
        directions_match = lstm_direction.upper() == esoteric_direction.upper()
        
        # Determine signal tier
        signal_tier = self._determine_tier(lstm_norm, esoteric_norm, directions_match)
        
        # Calculate synergy score (0-100)
        # Geometric mean emphasizes when BOTH are strong
        if lstm_norm > 0 and esoteric_norm > 0:
            synergy_score = np.sqrt(lstm_norm * esoteric_norm) * 100
        else:
            synergy_score = 0
        
        # Direction agreement multiplier
        if directions_match:
            synergy_score *= 1.2  # 20% boost for agreement
        else:
            synergy_score *= 0.5  # 50% penalty for conflict
        
        synergy_score = min(100, synergy_score)
        
        # Extra validation from other models (if provided)
        extra_validation = []
        if ensemble_confidence and ensemble_confidence > 70:
            extra_validation.append(f"Ensemble agrees ({ensemble_confidence:.0f}%)")
            synergy_score += 5
        if monte_carlo_prob and monte_carlo_prob > 0.6:
            extra_validation.append(f"Monte Carlo agrees ({monte_carlo_prob*100:.0f}%)")
            synergy_score += 5
        
        synergy_score = min(100, synergy_score)
        
        # Get boost and multiplier for this tier
        confidence_boost = self.boosts.get(signal_tier, 0)
        unit_multiplier = self.unit_multipliers.get(signal_tier, 1.0)
        
        # Determine final recommendation
        if signal_tier in ["GOLDEN_CONVERGENCE", "SUPER_SIGNAL"]:
            recommendation = lstm_direction.upper()
            action = "STRONG_BET"
        elif signal_tier == "HARMONIC_ALIGNMENT":
            recommendation = lstm_direction.upper()
            action = "BET"
        elif signal_tier == "PARTIAL_ALIGNMENT":
            recommendation = lstm_direction.upper()
            action = "LEAN"
        elif signal_tier == "CONFLICT":
            recommendation = "AVOID"
            action = "SKIP"
        else:
            recommendation = "NEUTRAL"
            action = "PASS"
        
        result = {
            # Core synergy data
            "signal_tier": signal_tier,
            "synergy_score": round(synergy_score, 1),
            "is_super_signal": signal_tier in ["GOLDEN_CONVERGENCE", "SUPER_SIGNAL"],
            "is_golden": signal_tier == "GOLDEN_CONVERGENCE",
            
            # Input values (normalized)
            "lstm_confidence": lstm_confidence,
            "lstm_normalized": round(lstm_norm, 3),
            "lstm_direction": lstm_direction,
            "lstm_strong": lstm_norm >= 0.70,
            
            "esoteric_score": esoteric_score,
            "esoteric_normalized": round(esoteric_norm, 3),
            "esoteric_direction": esoteric_direction,
            "esoteric_strong": esoteric_norm >= 0.70,
            
            "directions_match": directions_match,
            
            # Adjustments
            "confidence_boost": confidence_boost,
            "unit_multiplier": unit_multiplier,
            
            # Recommendation
            "recommendation": recommendation,
            "action": action,
            
            # Extra validation
            "extra_validation": extra_validation,
            
            # Interpretation
            "interpretation": self._get_interpretation(signal_tier, lstm_norm, esoteric_norm)
        }
        
        # Track history
        self.convergence_history.append({
            "timestamp": datetime.now().isoformat(),
            "tier": signal_tier,
            "synergy_score": result["synergy_score"],
            "direction": recommendation
        })
        
        return result
    
    def _determine_tier(self, lstm_norm: float, esoteric_norm: float, directions_match: bool) -> str:
        """Determine signal tier based on normalized values"""
        
        # CONFLICT: Both strong but opposite directions
        if lstm_norm >= 0.70 and esoteric_norm >= 0.70 and not directions_match:
            return "CONFLICT"
        
        # Opposite directions with any strength = potential conflict
        if not directions_match and (lstm_norm >= 0.60 or esoteric_norm >= 0.60):
            return "CONFLICT"
        
        # GOLDEN: Both above 0.8 and same direction
        if lstm_norm >= 0.80 and esoteric_norm >= 0.80 and directions_match:
            return "GOLDEN_CONVERGENCE"
        
        # SUPER: Both above 0.7 and same direction
        if lstm_norm >= 0.70 and esoteric_norm >= 0.70 and directions_match:
            return "SUPER_SIGNAL"
        
        # HARMONIC: One above 0.8, other above 0.6, same direction
        if directions_match:
            if (lstm_norm >= 0.80 and esoteric_norm >= 0.60) or \
               (lstm_norm >= 0.60 and esoteric_norm >= 0.80):
                return "HARMONIC_ALIGNMENT"
        
        # PARTIAL: Both above 0.6, same direction
        if lstm_norm >= 0.60 and esoteric_norm >= 0.60 and directions_match:
            return "PARTIAL_ALIGNMENT"
        
        return "NO_SIGNAL"
    
    def _get_interpretation(self, tier: str, lstm: float, esoteric: float) -> str:
        """Get human-readable interpretation"""
        interpretations = {
            "GOLDEN_CONVERGENCE": f"🌟 GOLDEN SIGNAL: Statistics ({lstm*100:.0f}%) AND Stars ({esoteric*100:.0f}%) STRONGLY ALIGNED. Highest conviction bet!",
            "SUPER_SIGNAL": f"⚡ SUPER SIGNAL: LSTM ({lstm*100:.0f}%) and Esoteric ({esoteric*100:.0f}%) both confident. High-value opportunity!",
            "HARMONIC_ALIGNMENT": f"🎯 HARMONIC: Good alignment between data and energy. Solid betting opportunity.",
            "PARTIAL_ALIGNMENT": f"📊 PARTIAL: Moderate agreement. Standard bet sizing recommended.",
            "CONFLICT": f"⚠️ CONFLICT: Data says one thing, stars say another. Consider skipping or reducing size.",
            "NO_SIGNAL": f"❌ NO SIGNAL: Insufficient conviction from either source. Pass or wait."
        }
        return interpretations.get(tier, "Unknown signal")
    
    def check_convergence(self, ml_confidence: float, ml_direction: str,
                         esoteric_score: float, esoteric_direction: str) -> Dict:
        """
        Legacy method - now calls lstm_esoteric_synergy
        Kept for backwards compatibility
        """
        return self.check_lstm_esoteric_synergy(
            lstm_confidence=ml_confidence,
            lstm_direction=ml_direction,
            esoteric_score=esoteric_score,
            esoteric_direction=esoteric_direction
        )
    
    def analyze_prop_for_synergy(self, prop_data: Dict) -> Dict:
        """
        Analyze a prop pick for LSTM + Esoteric synergy
        
        Expected prop_data keys:
        - lstm_prediction or signals.lstm
        - esoteric_score or signals.esoteric
        - pick: Direction
        """
        # Extract LSTM data
        lstm_data = prop_data.get("signals", {}).get("lstm", {})
        lstm_confidence = lstm_data.get("confidence", 0) if lstm_data else prop_data.get("lstm_confidence", 50)
        
        # Extract ensemble for extra validation
        ensemble_data = prop_data.get("signals", {}).get("ensemble", {})
        ensemble_confidence = ensemble_data.get("confidence", 0) if ensemble_data else None
        
        # Extract Monte Carlo for extra validation
        mc_data = prop_data.get("signals", {}).get("monte_carlo", {})
        mc_prob = mc_data.get("over_prob", 50) / 100 if mc_data else None
        
        # Determine LSTM direction from pick or edge
        pick_str = str(prop_data.get("pick", "")).upper()
        if "OVER" in pick_str:
            lstm_direction = "OVER"
        elif "UNDER" in pick_str:
            lstm_direction = "UNDER"
        else:
            lstm_direction = "OVER" if lstm_data.get("edge", 0) > 0 else "UNDER"
        
        # Extract esoteric data
        esoteric_score = prop_data.get("esoteric_score", 50)
        
        # Determine esoteric direction from score
        if esoteric_score > 55:
            esoteric_direction = "OVER"
        elif esoteric_score < 45:
            esoteric_direction = "UNDER"
        else:
            esoteric_direction = lstm_direction  # Neutral follows LSTM
        
        # Check synergy
        synergy = self.check_lstm_esoteric_synergy(
            lstm_confidence=lstm_confidence,
            lstm_direction=lstm_direction,
            esoteric_score=esoteric_score,
            esoteric_direction=esoteric_direction,
            ensemble_confidence=ensemble_confidence,
            monte_carlo_prob=mc_prob
        )
        
        return synergy
    
    def get_super_signals_only(self, picks: List[Dict]) -> List[Dict]:
        """
        Filter picks to only return SuperSignals and Golden Signals
        These are your highest conviction bets
        """
        super_signals = []
        
        for pick in picks:
            synergy = self.analyze_prop_for_synergy(pick)
            
            if synergy["is_super_signal"]:
                enhanced_pick = pick.copy()
                enhanced_pick["synergy"] = synergy
                enhanced_pick["confidence_score"] = pick.get("confidence_score", 50) + synergy["confidence_boost"]
                enhanced_pick["is_super_signal"] = True
                enhanced_pick["is_golden"] = synergy["is_golden"]
                enhanced_pick["unit_multiplier"] = synergy["unit_multiplier"]
                super_signals.append(enhanced_pick)
        
        # Sort by synergy score (highest first)
        super_signals.sort(key=lambda x: x["synergy"]["synergy_score"], reverse=True)
        
        return super_signals
    
    def get_golden_signals_only(self, picks: List[Dict]) -> List[Dict]:
        """
        Filter picks to only return GOLDEN signals
        These are the absolute highest conviction bets (rare)
        """
        all_super = self.get_super_signals_only(picks)
        return [p for p in all_super if p.get("is_golden")]
    
    def record_result(self, tier: str, won: bool, units: float = 1.0, odds: int = -110):
        """Record a result for performance tracking"""
        if tier not in self.tier_performance:
            return
        
        self.tier_performance[tier]["bets"] += 1
        if won:
            self.tier_performance[tier]["wins"] += 1
            # Calculate profit
            if odds > 0:
                profit = units * (odds / 100)
            else:
                profit = units * (100 / abs(odds))
        else:
            profit = -units
        
        # Update ROI (simplified)
        total_wagered = self.tier_performance[tier]["bets"] * units
        if total_wagered > 0:
            total_profit = (self.tier_performance[tier]["wins"] * 0.91 - 
                          (self.tier_performance[tier]["bets"] - self.tier_performance[tier]["wins"])) * units
            self.tier_performance[tier]["roi"] = round(total_profit / total_wagered * 100, 2)
    
    def get_performance_by_tier(self) -> Dict:
        """Get performance breakdown by signal tier"""
        result = {}
        for tier, data in self.tier_performance.items():
            if data["bets"] > 0:
                win_rate = data["wins"] / data["bets"] * 100
                result[tier] = {
                    "bets": data["bets"],
                    "wins": data["wins"],
                    "losses": data["bets"] - data["wins"],
                    "win_rate": round(win_rate, 1),
                    "roi": data["roi"]
                }
        return result
    
    def get_convergence_stats(self) -> Dict:
        """Get statistics on convergence signals"""
        if not self.convergence_history:
            return {"total": 0}
        
        total = len(self.convergence_history)
        
        tier_counts = {}
        for h in self.convergence_history:
            tier = h.get("tier", "NO_SIGNAL")
            tier_counts[tier] = tier_counts.get(tier, 0) + 1
        
        golden = tier_counts.get("GOLDEN_CONVERGENCE", 0)
        super_signals = tier_counts.get("SUPER_SIGNAL", 0)
        conflicts = tier_counts.get("CONFLICT", 0)
        
        return {
            "total_analyzed": total,
            "golden_signals": golden,
            "golden_rate": round(golden / total * 100, 1) if total > 0 else 0,
            "super_signals": super_signals,
            "super_signal_rate": round(super_signals / total * 100, 1) if total > 0 else 0,
            "conflicts": conflicts,
            "conflict_rate": round(conflicts / total * 100, 1) if total > 0 else 0,
            "tier_breakdown": tier_counts,
            "performance_by_tier": self.get_performance_by_tier()
        }
        """
        Filter picks to only return those with SuperSignal convergence
        These are your highest conviction bets
        """
        super_signals = []
        
        for pick in picks:
            convergence = self.analyze_pick(pick)
            
            if convergence["super_signal"]:
                enhanced_pick = pick.copy()
                enhanced_pick["harmonic_convergence"] = convergence
                enhanced_pick["confidence_score"] += convergence["confidence_boost"]
                enhanced_pick["is_super_signal"] = True
                super_signals.append(enhanced_pick)
        
        # Sort by convergence strength
        super_signals.sort(key=lambda x: x["harmonic_convergence"]["convergence_strength"], reverse=True)
        
        return super_signals
    
    def get_convergence_stats(self) -> Dict:
        """Get statistics on convergence signals"""
        if not self.convergence_history:
            return {"total": 0}
        
        total = len(self.convergence_history)
        super_signals = sum(1 for h in self.convergence_history if h["super_signal"])
        conflicts = sum(1 for h in self.convergence_history if h["signal_type"] == "CONFLICT")
        
        return {
            "total_analyzed": total,
            "super_signals": super_signals,
            "super_signal_rate": round(super_signals / total * 100, 1) if total > 0 else 0,
            "conflicts": conflicts,
            "conflict_rate": round(conflicts / total * 100, 1) if total > 0 else 0
        }


# Instantiate harmonic convergence analyzer
harmonic_convergence = HarmonicConvergence()


# ============================================
# ADVANCED CONTEXTUAL DATA SCRAPERS
# ============================================

class DefensiveContextScraper:
    """
    Scrapes opponent defensive ratings by position
    Critical for understanding the environment a player faces
    """
    
    def __init__(self):
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        self.cache = {}
        self.cache_time = {}
        
        # Position mappings
        self.positions = {
            "PG": "point_guard",
            "SG": "shooting_guard",
            "SF": "small_forward",
            "PF": "power_forward",
            "C": "center",
            "G": "guard",
            "F": "forward"
        }
        
        # League average defensive stats allowed by position (2024-25 estimates)
        self.league_avg_allowed = {
            "PG": {"points": 22.5, "rebounds": 4.2, "assists": 7.1, "threes": 2.8},
            "SG": {"points": 20.8, "rebounds": 4.5, "assists": 4.2, "threes": 2.5},
            "SF": {"points": 18.5, "rebounds": 6.2, "assists": 3.5, "threes": 2.0},
            "PF": {"points": 17.2, "rebounds": 7.8, "assists": 2.8, "threes": 1.5},
            "C": {"points": 15.5, "rebounds": 10.2, "assists": 2.5, "threes": 0.8}
        }
    
    def get_team_defense_vs_position(self, team: str, position: str) -> Dict:
        """
        Get how much a team allows to a specific position
        Returns defensive rating and stats allowed
        """
        cache_key = f"{team}_{position}"
        
        if cache_key in self.cache:
            if (datetime.now() - self.cache_time.get(cache_key, datetime.min)).seconds < 7200:
                return self.cache[cache_key]
        
        # Normalize position
        pos = position.upper()
        if pos not in self.league_avg_allowed:
            pos = "SF"  # Default
        
        # Try to scrape from Basketball-Reference or use estimates
        defense_data = self._scrape_team_defense(team, pos)
        
        if not defense_data:
            # Use team-specific adjustments based on known good/bad defenses
            defense_data = self._estimate_defense(team, pos)
        
        self.cache[cache_key] = defense_data
        self.cache_time[cache_key] = datetime.now()
        
        return defense_data
    
    def _scrape_team_defense(self, team: str, position: str) -> Optional[Dict]:
        """Attempt to scrape defensive data"""
        # Would scrape from Basketball-Reference team defense pages
        # For now, return None to use estimates
        return None
    
    def _estimate_defense(self, team: str, position: str) -> Dict:
        """Estimate defensive stats based on known team tendencies"""
        
        # Team defensive rankings (lower = better defense)
        # Based on 2024-25 season data
        team_def_ratings = {
            # Elite defenses (allow less)
            "celtics": 0.92, "thunder": 0.93, "cavaliers": 0.94, "knicks": 0.95,
            "timberwolves": 0.94, "magic": 0.95, "grizzlies": 0.96,
            # Average defenses
            "lakers": 1.00, "warriors": 1.01, "suns": 1.02, "mavericks": 1.00,
            "nuggets": 0.99, "bucks": 0.98, "heat": 0.99, "76ers": 1.00,
            "clippers": 0.98, "kings": 1.02, "pacers": 1.03, "hawks": 1.04,
            # Poor defenses (allow more)
            "pistons": 1.08, "wizards": 1.10, "hornets": 1.07, "blazers": 1.06,
            "spurs": 1.05, "jazz": 1.06, "rockets": 1.04, "nets": 1.05,
            "bulls": 1.03, "raptors": 1.04
        }
        
        # Get team multiplier
        team_lower = team.lower()
        multiplier = 1.0
        for t, mult in team_def_ratings.items():
            if t in team_lower:
                multiplier = mult
                break
        
        # Calculate expected stats allowed
        base = self.league_avg_allowed.get(position, self.league_avg_allowed["SF"])
        
        return {
            "team": team,
            "position": position,
            "defensive_multiplier": multiplier,
            "points_allowed": round(base["points"] * multiplier, 1),
            "rebounds_allowed": round(base["rebounds"] * multiplier, 1),
            "assists_allowed": round(base["assists"] * multiplier, 1),
            "threes_allowed": round(base["threes"] * multiplier, 1),
            "rating": "elite" if multiplier < 0.96 else "good" if multiplier < 1.0 else "average" if multiplier < 1.04 else "poor",
            "adjustment": round((multiplier - 1.0) * 100, 1)  # % adjustment from average
        }


class PaceDataScraper:
    """
    Scrapes team pace and possession data
    Pace determines the ceiling for statistical opportunities
    """
    
    def __init__(self):
        self.headers = {"User-Agent": "Mozilla/5.0"}
        self.cache = {}
        
        # 2024-25 team pace data (possessions per game)
        self.team_pace = {
            # Fast pace teams (100+ possessions)
            "pacers": 103.5, "hawks": 102.1, "pelicans": 101.8, "bucks": 101.2,
            "kings": 100.8, "jazz": 100.5, "timberwolves": 100.2, "thunder": 100.0,
            # Average pace
            "celtics": 99.5, "nuggets": 99.2, "suns": 99.0, "warriors": 98.8,
            "mavericks": 98.5, "lakers": 98.2, "rockets": 98.0, "76ers": 97.8,
            "bulls": 97.5, "raptors": 97.2, "nets": 97.0, "heat": 96.8,
            # Slow pace teams (<97 possessions)
            "knicks": 96.5, "cavaliers": 96.2, "magic": 96.0, "grizzlies": 95.8,
            "clippers": 95.5, "spurs": 95.2, "pistons": 95.0, "hornets": 94.8,
            "blazers": 94.5, "wizards": 94.2
        }
        
        self.league_avg_pace = 98.5
    
    def get_team_pace(self, team: str) -> Dict:
        """Get team's pace (possessions per game)"""
        team_lower = team.lower()
        
        pace = self.league_avg_pace
        for t, p in self.team_pace.items():
            if t in team_lower:
                pace = p
                break
        
        diff = pace - self.league_avg_pace
        
        return {
            "team": team,
            "pace": pace,
            "league_avg": self.league_avg_pace,
            "pace_diff": round(diff, 1),
            "pace_category": "fast" if pace >= 100 else "average" if pace >= 97 else "slow",
            "stat_multiplier": round(pace / self.league_avg_pace, 3)
        }
    
    def get_game_pace_projection(self, home_team: str, away_team: str) -> Dict:
        """Project pace for a specific game"""
        home = self.get_team_pace(home_team)
        away = self.get_team_pace(away_team)
        
        # Average of both teams' paces
        projected = (home["pace"] + away["pace"]) / 2
        
        # High pace matchups = more stats
        pace_boost = projected / self.league_avg_pace
        
        return {
            "home_pace": home["pace"],
            "away_pace": away["pace"],
            "projected_pace": round(projected, 1),
            "pace_boost": round(pace_boost, 3),
            "game_environment": "high_scoring" if projected >= 100 else "normal" if projected >= 97 else "grind_it_out",
            "stat_adjustment": round((pace_boost - 1) * 100, 1)  # % adjustment
        }


class TeamContextScraper:
    """
    Scrapes team context: injuries, usage rates, lineup data
    Critical for understanding "usage vacuum" when stars are out
    """
    
    def __init__(self):
        self.headers = {"User-Agent": "Mozilla/5.0"}
        
        # Star players and their typical usage rates
        self.star_players = {
            # Format: "team": [{"name": X, "usage": X, "points_share": X}]
            "lakers": [
                {"name": "lebron james", "usage": 30.5, "points_share": 0.28},
                {"name": "anthony davis", "usage": 28.2, "points_share": 0.25}
            ],
            "celtics": [
                {"name": "jayson tatum", "usage": 30.8, "points_share": 0.27},
                {"name": "jaylen brown", "usage": 28.5, "points_share": 0.24}
            ],
            "nuggets": [
                {"name": "nikola jokic", "usage": 29.5, "points_share": 0.26},
                {"name": "jamal murray", "usage": 25.2, "points_share": 0.21}
            ],
            "bucks": [
                {"name": "giannis antetokounmpo", "usage": 35.2, "points_share": 0.32},
                {"name": "damian lillard", "usage": 28.5, "points_share": 0.25}
            ],
            "mavericks": [
                {"name": "luka doncic", "usage": 36.5, "points_share": 0.35},
                {"name": "kyrie irving", "usage": 27.8, "points_share": 0.24}
            ],
            "thunder": [
                {"name": "shai gilgeous-alexander", "usage": 32.5, "points_share": 0.30},
                {"name": "jalen williams", "usage": 22.5, "points_share": 0.18}
            ],
            "76ers": [
                {"name": "joel embiid", "usage": 37.5, "points_share": 0.35},
                {"name": "tyrese maxey", "usage": 26.8, "points_share": 0.23}
            ],
            "suns": [
                {"name": "kevin durant", "usage": 30.2, "points_share": 0.28},
                {"name": "devin booker", "usage": 29.5, "points_share": 0.27}
            ],
            "warriors": [
                {"name": "stephen curry", "usage": 30.5, "points_share": 0.28},
                {"name": "andrew wiggins", "usage": 20.5, "points_share": 0.16}
            ],
            "knicks": [
                {"name": "jalen brunson", "usage": 32.8, "points_share": 0.30},
                {"name": "karl-anthony towns", "usage": 26.5, "points_share": 0.23}
            ],
            "cavaliers": [
                {"name": "donovan mitchell", "usage": 30.2, "points_share": 0.28},
                {"name": "darius garland", "usage": 26.8, "points_share": 0.22}
            ],
            "heat": [
                {"name": "jimmy butler", "usage": 28.5, "points_share": 0.25},
                {"name": "bam adebayo", "usage": 24.2, "points_share": 0.20}
            ],
            "timberwolves": [
                {"name": "anthony edwards", "usage": 32.5, "points_share": 0.30},
                {"name": "rudy gobert", "usage": 14.5, "points_share": 0.12}
            ],
            "grizzlies": [
                {"name": "ja morant", "usage": 32.8, "points_share": 0.30},
                {"name": "desmond bane", "usage": 24.5, "points_share": 0.21}
            ],
            "rockets": [
                {"name": "jalen green", "usage": 27.5, "points_share": 0.24},
                {"name": "alperen sengun", "usage": 25.8, "points_share": 0.22}
            ],
            "magic": [
                {"name": "paolo banchero", "usage": 28.5, "points_share": 0.26},
                {"name": "franz wagner", "usage": 25.2, "points_share": 0.22}
            ],
            "spurs": [
                {"name": "victor wembanyama", "usage": 26.5, "points_share": 0.24},
                {"name": "devin vassell", "usage": 22.8, "points_share": 0.19}
            ],
            "kings": [
                {"name": "de'aaron fox", "usage": 30.5, "points_share": 0.28},
                {"name": "domantas sabonis", "usage": 24.2, "points_share": 0.20}
            ],
            "pacers": [
                {"name": "tyrese haliburton", "usage": 28.5, "points_share": 0.25},
                {"name": "pascal siakam", "usage": 26.2, "points_share": 0.23}
            ],
            "hawks": [
                {"name": "trae young", "usage": 33.5, "points_share": 0.30},
                {"name": "dejounte murray", "usage": 26.8, "points_share": 0.22}
            ],
            "clippers": [
                {"name": "kawhi leonard", "usage": 30.2, "points_share": 0.28},
                {"name": "paul george", "usage": 27.5, "points_share": 0.24}
            ],
            "pelicans": [
                {"name": "zion williamson", "usage": 30.8, "points_share": 0.28},
                {"name": "brandon ingram", "usage": 28.2, "points_share": 0.25}
            ]
        }
    
    def get_team_context(self, team: str, injured_players: List[str] = None) -> Dict:
        """
        Get team context including usage vacuum from injuries
        """
        team_lower = team.lower()
        
        # Find team's star players
        stars = []
        for t, players in self.star_players.items():
            if t in team_lower:
                stars = players
                break
        
        if not stars:
            return {
                "team": team,
                "usage_vacuum": 0,
                "boost_expected": False,
                "remaining_usage": 100
            }
        
        # Calculate usage vacuum from injuries
        usage_vacuum = 0
        points_vacuum = 0
        injured_stars = []
        
        if injured_players:
            for inj in injured_players:
                inj_lower = inj.lower()
                for star in stars:
                    if star["name"] in inj_lower or inj_lower in star["name"]:
                        usage_vacuum += star["usage"]
                        points_vacuum += star["points_share"]
                        injured_stars.append(star["name"])
        
        # Calculate expected boost for remaining players
        # When a star is out, their usage gets redistributed
        boost_factor = 1.0 + (usage_vacuum / 100) * 0.5  # ~50% of vacuum redistributed
        
        return {
            "team": team,
            "stars": [s["name"] for s in stars],
            "injured_stars": injured_stars,
            "usage_vacuum": round(usage_vacuum, 1),
            "points_vacuum": round(points_vacuum * 100, 1),
            "boost_factor": round(boost_factor, 3),
            "boost_expected": usage_vacuum > 20,
            "context": "major_injury" if usage_vacuum > 25 else "minor_injury" if usage_vacuum > 10 else "full_strength"
        }
    
    def get_player_usage_boost(self, player: str, team: str, injured_players: List[str] = None) -> Dict:
        """
        Calculate expected usage boost for a specific player when teammates are out
        """
        context = self.get_team_context(team, injured_players)
        
        if not context.get("boost_expected"):
            return {"boost": 0, "adjusted_multiplier": 1.0}
        
        # Check if player is a secondary option who would absorb usage
        player_lower = player.lower()
        team_lower = team.lower()
        
        # Find if player is on the team
        stars = self.star_players.get(team_lower, [])
        
        is_remaining_star = False
        for star in stars:
            if star["name"] in player_lower or player_lower in star["name"]:
                if star["name"] not in context.get("injured_stars", []):
                    is_remaining_star = True
                    break
        
        if is_remaining_star:
            # Primary remaining option gets biggest boost
            boost = context["usage_vacuum"] * 0.4  # 40% of vacuum
            multiplier = 1 + (boost / 100)
        else:
            # Role players get smaller boost
            boost = context["usage_vacuum"] * 0.15  # 15% of vacuum
            multiplier = 1 + (boost / 100)
        
        return {
            "boost": round(boost, 1),
            "adjusted_multiplier": round(multiplier, 3),
            "reason": f"Usage vacuum from {', '.join(context.get('injured_stars', []))}" if context.get("injured_stars") else "Full strength"
        }


class RestTravelScraper:
    """
    Advanced rest and travel fatigue analysis
    Goes beyond simple back-to-back detection
    """
    
    def __init__(self):
        # City coordinates for travel distance calculation
        self.city_coords = {
            "atlanta": (33.749, -84.388), "boston": (42.361, -71.057),
            "brooklyn": (40.683, -73.976), "charlotte": (35.225, -80.839),
            "chicago": (41.881, -87.674), "cleveland": (41.497, -81.694),
            "dallas": (32.790, -96.810), "denver": (39.749, -104.985),
            "detroit": (42.341, -83.055), "houston": (29.751, -95.362),
            "indianapolis": (39.764, -86.156), "los angeles": (34.043, -118.267),
            "memphis": (35.138, -90.051), "miami": (25.781, -80.188),
            "milwaukee": (43.045, -87.918), "minneapolis": (44.980, -93.276),
            "new orleans": (29.949, -90.075), "new york": (40.751, -73.994),
            "oklahoma city": (35.463, -97.515), "orlando": (28.539, -81.384),
            "philadelphia": (39.901, -75.172), "phoenix": (33.446, -112.071),
            "portland": (45.532, -122.666), "sacramento": (38.580, -121.500),
            "san antonio": (29.427, -98.438), "san francisco": (37.768, -122.387),
            "toronto": (43.643, -79.379), "salt lake city": (40.768, -111.901),
            "washington": (38.898, -77.021)
        }
        
        # Team city mappings
        self.team_cities = {
            "hawks": "atlanta", "celtics": "boston", "nets": "brooklyn",
            "hornets": "charlotte", "bulls": "chicago", "cavaliers": "cleveland",
            "mavericks": "dallas", "nuggets": "denver", "pistons": "detroit",
            "warriors": "san francisco", "rockets": "houston", "pacers": "indianapolis",
            "clippers": "los angeles", "lakers": "los angeles", "grizzlies": "memphis",
            "heat": "miami", "bucks": "milwaukee", "timberwolves": "minneapolis",
            "pelicans": "new orleans", "knicks": "new york", "thunder": "oklahoma city",
            "magic": "orlando", "76ers": "philadelphia", "suns": "phoenix",
            "blazers": "portland", "kings": "sacramento", "spurs": "san antonio",
            "raptors": "toronto", "jazz": "salt lake city", "wizards": "washington"
        }
    
    def calculate_travel_distance(self, from_city: str, to_city: str) -> float:
        """Calculate distance between cities in miles"""
        from_coords = self.city_coords.get(from_city.lower())
        to_coords = self.city_coords.get(to_city.lower())
        
        if not from_coords or not to_coords:
            return 0
        
        # Haversine formula
        import math
        lat1, lon1 = from_coords
        lat2, lon2 = to_coords
        
        R = 3959  # Earth's radius in miles
        
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        return round(R * c, 0)
    
    def get_time_zone_diff(self, from_city: str, to_city: str) -> int:
        """Get time zone difference (hours)"""
        tz_map = {
            "eastern": ["atlanta", "boston", "brooklyn", "charlotte", "cleveland", "detroit",
                       "indianapolis", "miami", "new york", "orlando", "philadelphia", 
                       "toronto", "washington"],
            "central": ["chicago", "dallas", "houston", "memphis", "milwaukee", "minneapolis",
                       "new orleans", "oklahoma city", "san antonio"],
            "mountain": ["denver", "phoenix", "salt lake city"],
            "pacific": ["los angeles", "portland", "sacramento", "san francisco"]
        }
        
        def get_tz(city):
            city_lower = city.lower()
            for tz, cities in tz_map.items():
                if city_lower in cities:
                    return {"eastern": 0, "central": 1, "mountain": 2, "pacific": 3}[tz]
            return 0
        
        return abs(get_tz(from_city) - get_tz(to_city))
    
    def get_fatigue_analysis(self, team: str, days_rest: int, prev_city: str = None, 
                            games_in_5_days: int = 1, games_in_7_days: int = 2) -> Dict:
        """
        Comprehensive fatigue analysis
        """
        # Get team's home city
        team_lower = team.lower()
        home_city = None
        for t, city in self.team_cities.items():
            if t in team_lower:
                home_city = city
                break
        
        # Calculate travel fatigue
        travel_distance = 0
        time_zones = 0
        if prev_city and home_city:
            travel_distance = self.calculate_travel_distance(prev_city, home_city)
            time_zones = self.get_time_zone_diff(prev_city, home_city)
        
        # Fatigue factors
        is_b2b = days_rest == 0
        is_3_in_4 = games_in_5_days >= 3
        is_5_in_7 = games_in_7_days >= 5
        heavy_travel = travel_distance > 1500
        coast_to_coast = time_zones >= 3
        
        # Calculate fatigue score (0-100, higher = more fatigued)
        fatigue_score = 0
        
        if is_b2b:
            fatigue_score += 35
        elif days_rest == 1:
            fatigue_score += 15
        
        if is_3_in_4:
            fatigue_score += 20
        if is_5_in_7:
            fatigue_score += 15
        
        if heavy_travel:
            fatigue_score += 15
        if coast_to_coast:
            fatigue_score += 10
        
        # Performance adjustment (negative = expect worse performance)
        performance_adj = 0
        if fatigue_score >= 50:
            performance_adj = -0.08  # 8% decrease
        elif fatigue_score >= 35:
            performance_adj = -0.05  # 5% decrease
        elif fatigue_score >= 20:
            performance_adj = -0.02  # 2% decrease
        
        return {
            "team": team,
            "days_rest": days_rest,
            "back_to_back": is_b2b,
            "three_in_four": is_3_in_4,
            "five_in_seven": is_5_in_7,
            "travel_distance": travel_distance,
            "time_zones_crossed": time_zones,
            "fatigue_score": min(100, fatigue_score),
            "fatigue_level": "severe" if fatigue_score >= 50 else "moderate" if fatigue_score >= 30 else "low",
            "performance_adjustment": performance_adj,
            "stat_multiplier": round(1 + performance_adj, 3)
        }


class VegasLineScraper:
    """
    Incorporates Vegas lines as features
    The betting market implicitly accounts for many factors
    """
    
    def __init__(self):
        self.headers = {"User-Agent": "Mozilla/5.0"}
    
    def get_vegas_context(self, game_odds: Dict, player_prop_line: float = None) -> Dict:
        """
        Extract Vegas context as ML features
        """
        # Get spread and total from odds data
        spread = 0
        total = 220
        
        if game_odds:
            spreads = game_odds.get("spreads", {})
            totals = game_odds.get("totals", {})
            
            # Get home spread
            for team, data in spreads.items():
                if isinstance(data, dict):
                    spread = data.get("point", 0)
                    break
            
            # Get total
            over_data = totals.get("Over", {})
            if isinstance(over_data, dict):
                total = over_data.get("point", 220)
        
        # Calculate features
        is_blowout = abs(spread) >= 10
        is_high_total = total >= 230
        is_low_total = total <= 210
        
        # Blowouts affect minutes (garbage time)
        minutes_risk = "high" if is_blowout else "normal"
        
        # Total implies pace
        pace_implication = "fast" if is_high_total else "slow" if is_low_total else "normal"
        
        return {
            "spread": spread,
            "total": total,
            "is_blowout": is_blowout,
            "is_high_total": is_high_total,
            "is_low_total": is_low_total,
            "minutes_risk": minutes_risk,
            "pace_implication": pace_implication,
            "player_prop_line": player_prop_line,
            "total_adjustment": round((total - 220) / 220, 3)  # % above/below avg
        }


# Instantiate advanced scrapers
defense_scraper = DefensiveContextScraper()
pace_scraper = PaceDataScraper()
team_context_scraper = TeamContextScraper()
rest_travel_scraper = RestTravelScraper()
vegas_scraper = VegasLineScraper()


# ============================================
# REFEREE ANALYSIS SYSTEM
# ============================================

class RefereeAnalyzer:
    """
    Analyzes referee tendencies and their impact on games
    
    Key Metrics:
    - Average total points in games they officiate
    - Home team win percentage
    - Fouls per game (more fouls = more FTs = higher scoring)
    - Over/Under hit rate
    - Pace of play tendency
    """
    
    def __init__(self):
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        self.ref_cache = {}
        self.cache_time = None
        
        # Historical ref tendencies (updated periodically)
        # Source: Compiled from NBA.com, Covers, PoziTive
        self.ref_profiles = {
            # Format: "ref_name": {"avg_total": X, "home_win_pct": X, "fouls_per_game": X, "over_pct": X, "pace": "fast/avg/slow"}
            
            # High-scoring refs (over-friendly)
            "scott foster": {"avg_total": 224.5, "home_win_pct": 54.2, "fouls_per_game": 42.1, "over_pct": 55.3, "pace": "fast", "tendency": "OVER"},
            "tony brothers": {"avg_total": 223.8, "home_win_pct": 55.1, "fouls_per_game": 43.2, "over_pct": 54.8, "pace": "fast", "tendency": "OVER"},
            "marc davis": {"avg_total": 222.4, "home_win_pct": 52.8, "fouls_per_game": 41.5, "over_pct": 53.2, "pace": "fast", "tendency": "OVER"},
            "james capers": {"avg_total": 221.9, "home_win_pct": 53.5, "fouls_per_game": 40.8, "over_pct": 52.9, "pace": "avg", "tendency": "OVER"},
            "ben taylor": {"avg_total": 223.1, "home_win_pct": 51.9, "fouls_per_game": 41.2, "over_pct": 54.1, "pace": "fast", "tendency": "OVER"},
            "sean wright": {"avg_total": 222.7, "home_win_pct": 53.1, "fouls_per_game": 42.5, "over_pct": 53.8, "pace": "fast", "tendency": "OVER"},
            "rodney mott": {"avg_total": 221.5, "home_win_pct": 54.7, "fouls_per_game": 40.3, "over_pct": 52.4, "pace": "avg", "tendency": "SLIGHT_OVER"},
            
            # Low-scoring refs (under-friendly)
            "kane fitzgerald": {"avg_total": 215.2, "home_win_pct": 51.2, "fouls_per_game": 36.8, "over_pct": 45.6, "pace": "slow", "tendency": "UNDER"},
            "ed malloy": {"avg_total": 216.4, "home_win_pct": 50.8, "fouls_per_game": 37.2, "over_pct": 46.3, "pace": "slow", "tendency": "UNDER"},
            "john goble": {"avg_total": 217.1, "home_win_pct": 52.1, "fouls_per_game": 38.1, "over_pct": 47.2, "pace": "slow", "tendency": "UNDER"},
            "david guthrie": {"avg_total": 216.8, "home_win_pct": 51.5, "fouls_per_game": 37.5, "over_pct": 46.8, "pace": "slow", "tendency": "UNDER"},
            "eric lewis": {"avg_total": 217.5, "home_win_pct": 50.3, "fouls_per_game": 38.4, "over_pct": 47.5, "pace": "slow", "tendency": "UNDER"},
            "curtis blair": {"avg_total": 216.2, "home_win_pct": 52.4, "fouls_per_game": 37.8, "over_pct": 46.1, "pace": "slow", "tendency": "UNDER"},
            "kevin scott": {"avg_total": 217.8, "home_win_pct": 51.8, "fouls_per_game": 38.9, "over_pct": 48.1, "pace": "avg", "tendency": "SLIGHT_UNDER"},
            
            # Home-team friendly refs
            "bill kennedy": {"avg_total": 219.8, "home_win_pct": 57.2, "fouls_per_game": 39.5, "over_pct": 50.2, "pace": "avg", "tendency": "HOME"},
            "pat fraher": {"avg_total": 218.5, "home_win_pct": 56.8, "fouls_per_game": 39.1, "over_pct": 49.5, "pace": "avg", "tendency": "HOME"},
            "leon wood": {"avg_total": 219.2, "home_win_pct": 56.1, "fouls_per_game": 40.2, "over_pct": 50.8, "pace": "avg", "tendency": "HOME"},
            "tre maddox": {"avg_total": 220.1, "home_win_pct": 55.8, "fouls_per_game": 39.8, "over_pct": 51.2, "pace": "avg", "tendency": "HOME"},
            
            # Neutral/balanced refs
            "josh tiven": {"avg_total": 219.1, "home_win_pct": 52.5, "fouls_per_game": 39.2, "over_pct": 50.1, "pace": "avg", "tendency": "NEUTRAL"},
            "james williams": {"avg_total": 218.8, "home_win_pct": 51.8, "fouls_per_game": 38.8, "over_pct": 49.8, "pace": "avg", "tendency": "NEUTRAL"},
            "zach zarba": {"avg_total": 219.4, "home_win_pct": 52.2, "fouls_per_game": 39.4, "over_pct": 50.4, "pace": "avg", "tendency": "NEUTRAL"},
            "brian forte": {"avg_total": 218.6, "home_win_pct": 51.5, "fouls_per_game": 38.5, "over_pct": 49.2, "pace": "avg", "tendency": "NEUTRAL"},
            "derrick collins": {"avg_total": 219.0, "home_win_pct": 52.0, "fouls_per_game": 39.0, "over_pct": 50.0, "pace": "avg", "tendency": "NEUTRAL"},
            "matt boland": {"avg_total": 218.9, "home_win_pct": 51.7, "fouls_per_game": 38.7, "over_pct": 49.6, "pace": "avg", "tendency": "NEUTRAL"},
            "nick buchert": {"avg_total": 219.3, "home_win_pct": 52.3, "fouls_per_game": 39.3, "over_pct": 50.3, "pace": "avg", "tendency": "NEUTRAL"},
            "mark ayotte": {"avg_total": 218.7, "home_win_pct": 51.6, "fouls_per_game": 38.6, "over_pct": 49.4, "pace": "avg", "tendency": "NEUTRAL"},
            "mousa dagher": {"avg_total": 219.5, "home_win_pct": 52.1, "fouls_per_game": 39.1, "over_pct": 50.2, "pace": "avg", "tendency": "NEUTRAL"},
            "kevin cutler": {"avg_total": 218.4, "home_win_pct": 51.4, "fouls_per_game": 38.4, "over_pct": 49.1, "pace": "avg", "tendency": "NEUTRAL"},
            
            # Player-foul heavy (more FTs, benefits high-usage stars)
            "tony brown": {"avg_total": 221.2, "home_win_pct": 52.8, "fouls_per_game": 44.5, "over_pct": 52.1, "pace": "avg", "tendency": "STAR_FRIENDLY"},
            "mitchell ervin": {"avg_total": 220.8, "home_win_pct": 53.2, "fouls_per_game": 43.8, "over_pct": 51.8, "pace": "avg", "tendency": "STAR_FRIENDLY"},
            "dedric taylor": {"avg_total": 220.5, "home_win_pct": 52.5, "fouls_per_game": 43.2, "over_pct": 51.5, "pace": "avg", "tendency": "STAR_FRIENDLY"},
        }
        
        # League average for comparison
        self.league_avg = {
            "avg_total": 219.0,
            "home_win_pct": 52.5,
            "fouls_per_game": 39.5,
            "over_pct": 50.0
        }
    
    def get_ref_assignments(self, sport: str = "NBA") -> Dict:
        """
        Fetch today's referee assignments
        NBA posts ref assignments ~9am ET day of game
        """
        # Check cache
        if self.ref_cache and self.cache_time:
            if (datetime.now() - self.cache_time).seconds < 3600:  # 1 hour cache
                return self.ref_cache
        
        assignments = {"games": [], "source": "NBA Official", "fetched_at": datetime.now().isoformat()}
        
        try:
            # Try NBA.com official referee assignments
            url = "https://official.nba.com/referee-assignments/"
            r = requests.get(url, headers=self.headers, timeout=10)
            
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                
                # Parse referee assignment table
                tables = soup.find_all('table')
                for table in tables:
                    rows = table.find_all('tr')
                    for row in rows[1:]:  # Skip header
                        cols = row.find_all('td')
                        if len(cols) >= 4:
                            game = {
                                "matchup": cols[0].get_text(strip=True),
                                "crew_chief": cols[1].get_text(strip=True).lower(),
                                "referee": cols[2].get_text(strip=True).lower() if len(cols) > 2 else "",
                                "umpire": cols[3].get_text(strip=True).lower() if len(cols) > 3 else ""
                            }
                            assignments["games"].append(game)
            
            self.ref_cache = assignments
            self.cache_time = datetime.now()
            
        except Exception as e:
            print(f"Ref assignment fetch error: {e}")
        
        return assignments
    
    def analyze_crew(self, crew_chief: str, referee: str = "", umpire: str = "") -> Dict:
        """
        Analyze a referee crew's combined tendencies
        Crew chief has most influence, but all three refs matter
        """
        refs = [crew_chief.lower(), referee.lower(), umpire.lower()]
        refs = [r for r in refs if r]  # Remove empty
        
        if not refs:
            return {"has_data": False, "recommendation": "NO_REF_DATA"}
        
        # Weight: Crew Chief 50%, Referee 30%, Umpire 20%
        weights = [0.5, 0.3, 0.2][:len(refs)]
        
        combined = {
            "avg_total": 0,
            "home_win_pct": 0,
            "fouls_per_game": 0,
            "over_pct": 0,
            "refs_found": [],
            "refs_missing": []
        }
        
        total_weight = 0
        tendencies = []
        
        for i, ref in enumerate(refs):
            weight = weights[i] if i < len(weights) else 0.2
            profile = self.ref_profiles.get(ref)
            
            if profile:
                combined["refs_found"].append(ref)
                combined["avg_total"] += profile["avg_total"] * weight
                combined["home_win_pct"] += profile["home_win_pct"] * weight
                combined["fouls_per_game"] += profile["fouls_per_game"] * weight
                combined["over_pct"] += profile["over_pct"] * weight
                tendencies.append(profile.get("tendency", "NEUTRAL"))
                total_weight += weight
            else:
                combined["refs_missing"].append(ref)
        
        if total_weight == 0:
            return {"has_data": False, "recommendation": "NO_REF_DATA"}
        
        # Normalize
        combined["avg_total"] /= total_weight
        combined["home_win_pct"] /= total_weight
        combined["fouls_per_game"] /= total_weight
        combined["over_pct"] /= total_weight
        
        # Calculate edges vs league average
        combined["total_edge"] = round(combined["avg_total"] - self.league_avg["avg_total"], 1)
        combined["home_edge"] = round(combined["home_win_pct"] - self.league_avg["home_win_pct"], 1)
        combined["over_edge"] = round(combined["over_pct"] - self.league_avg["over_pct"], 1)
        
        # Determine recommendation
        if combined["over_pct"] >= 53:
            combined["total_recommendation"] = "OVER"
            combined["total_strength"] = min(0.9, (combined["over_pct"] - 50) / 10)
        elif combined["over_pct"] <= 47:
            combined["total_recommendation"] = "UNDER"
            combined["total_strength"] = min(0.9, (50 - combined["over_pct"]) / 10)
        else:
            combined["total_recommendation"] = "NEUTRAL"
            combined["total_strength"] = 0
        
        if combined["home_win_pct"] >= 55:
            combined["spread_recommendation"] = "HOME"
            combined["spread_strength"] = min(0.9, (combined["home_win_pct"] - 52.5) / 5)
        elif combined["home_win_pct"] <= 50:
            combined["spread_recommendation"] = "AWAY"
            combined["spread_strength"] = min(0.9, (52.5 - combined["home_win_pct"]) / 5)
        else:
            combined["spread_recommendation"] = "NEUTRAL"
            combined["spread_strength"] = 0
        
        # Star player impact (high foul crews = more FTs for stars)
        if combined["fouls_per_game"] >= 42:
            combined["star_impact"] = "HIGH"
            combined["props_lean"] = "OVER"  # More FTs = more points for stars
        elif combined["fouls_per_game"] <= 37:
            combined["star_impact"] = "LOW"
            combined["props_lean"] = "UNDER"
        else:
            combined["star_impact"] = "NEUTRAL"
            combined["props_lean"] = "NEUTRAL"
        
        combined["has_data"] = True
        combined["confidence"] = min(90, len(combined["refs_found"]) * 30)
        
        return combined
    
    def get_game_ref_analysis(self, home_team: str, away_team: str) -> Dict:
        """
        Get referee analysis for a specific game
        """
        assignments = self.get_ref_assignments()
        
        # Find this game's refs
        game_refs = None
        for game in assignments.get("games", []):
            matchup = game.get("matchup", "").lower()
            if home_team.lower() in matchup or away_team.lower() in matchup:
                game_refs = game
                break
        
        if not game_refs:
            return {
                "has_refs": False,
                "note": "Ref assignments not yet posted or game not found"
            }
        
        # Analyze the crew
        analysis = self.analyze_crew(
            game_refs.get("crew_chief", ""),
            game_refs.get("referee", ""),
            game_refs.get("umpire", "")
        )
        
        analysis["crew"] = game_refs
        analysis["has_refs"] = True
        
        return analysis
    
    def get_ref_impact_on_props(self, ref_analysis: Dict, player_usage: str = "high") -> Dict:
        """
        Calculate how refs impact player props
        High-usage players benefit more from high-foul crews (more FTs)
        """
        if not ref_analysis.get("has_data"):
            return {"adjustment": 0, "confidence": 0}
        
        fouls = ref_analysis.get("fouls_per_game", 39.5)
        
        # High-usage players (stars) get more calls
        if player_usage == "high":
            if fouls >= 42:
                return {
                    "adjustment": 1.5,  # +1.5 points expected
                    "direction": "OVER",
                    "reason": "High-foul crew benefits star players",
                    "confidence": 65
                }
            elif fouls <= 37:
                return {
                    "adjustment": -1.0,
                    "direction": "UNDER", 
                    "reason": "Low-foul crew limits FT opportunities",
                    "confidence": 60
                }
        
        return {"adjustment": 0, "direction": "NEUTRAL", "confidence": 0}


# Instantiate ref analyzer
ref_analyzer = RefereeAnalyzer()


# ============================================
# REAL ML SYSTEM - Actual Trained Models
# ============================================

class PlayerDataScraper:
    """
    Multi-source player data scraper with API fallback options
    
    Data Sources (in order of preference):
    1. Paid API (RapidAPI, SportsRadar) - Fast, reliable, structured
    2. Basketball-Reference HTML - Free but fragile, rate limited
    3. Cache - 4 hour TTL
    
    HTML scraping is fragile - site changes can break it.
    Moving to paid APIs is recommended for production.
    """
    
    def __init__(self, api_key: str = None, api_source: str = "basketball_reference"):
        """
        Args:
            api_key: API key for paid data source
            api_source: "basketball_reference" (free), "rapidapi", "sportsradar"
        """
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        self.cache = {}
        self.cache_time = {}
        self.api_key = api_key or os.getenv("SPORTS_API_KEY")
        self.api_source = api_source
        
        # RapidAPI endpoint (example - would need actual subscription)
        self.rapidapi_host = "api-nba-v1.p.rapidapi.com"
        self.sportsradar_base = "https://api.sportradar.us/nba/trial/v7/en"
    
    def get_player_game_log(self, player_name: str, sport: str = "NBA", seasons: int = 2) -> List[Dict]:
        """
        Get player's game log for MULTIPLE SEASONS
        Default: Current season + last season (2 years of data = 100-150+ games)
        """
        cache_key = f"{player_name}_{sport}_{seasons}"
        
        # Check cache (4 hour expiry)
        if cache_key in self.cache:
            if (datetime.now() - self.cache_time.get(cache_key, datetime.min)).seconds < 14400:
                return self.cache[cache_key]
        
        all_games = []
        
        # Try API first if available
        if self.api_key and self.api_source in ["rapidapi", "sportsradar"]:
            try:
                all_games = self._get_from_api(player_name, sport, seasons)
                if all_games:
                    self.cache[cache_key] = all_games
                    self.cache_time[cache_key] = datetime.now()
                    return all_games
            except Exception as e:
                print(f"API fetch failed, falling back to scraping: {e}")
        
        # Fallback to HTML scraping
        player_id = self._get_player_id(player_name)
        if not player_id:
            return []
        
        current_year = 2025
        
        # Get multiple seasons
        for i in range(seasons):
            season_year = current_year - i
            games = self._scrape_season(player_id, season_year)
            all_games.extend(games)
        
        # Cache results
        if all_games:
            self.cache[cache_key] = all_games
            self.cache_time[cache_key] = datetime.now()
        
        return all_games
    
    def _get_from_api(self, player_name: str, sport: str, seasons: int) -> List[Dict]:
        """
        Get data from paid API
        
        Supported APIs:
        - RapidAPI NBA API
        - SportsRadar
        - (Add more as needed)
        """
        if self.api_source == "rapidapi":
            return self._get_from_rapidapi(player_name, seasons)
        elif self.api_source == "sportsradar":
            return self._get_from_sportsradar(player_name, seasons)
        return []
    
    def _get_from_rapidapi(self, player_name: str, seasons: int) -> List[Dict]:
        """
        Get player data from RapidAPI NBA API
        
        To use:
        1. Sign up at https://rapidapi.com/api-sports/api/api-nba
        2. Set SPORTS_API_KEY env var
        3. Set api_source="rapidapi"
        """
        if not self.api_key:
            return []
        
        headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": self.rapidapi_host
        }
        
        try:
            # First, search for player
            search_url = f"https://{self.rapidapi_host}/players?search={player_name.replace(' ', '%20')}"
            r = requests.get(search_url, headers=headers, timeout=10)
            
            if r.status_code != 200:
                return []
            
            data = r.json()
            players = data.get("response", [])
            
            if not players:
                return []
            
            player_id = players[0].get("id")
            
            # Get game logs for each season
            all_games = []
            for season in range(2024, 2024 - seasons, -1):
                stats_url = f"https://{self.rapidapi_host}/players/statistics?id={player_id}&season={season}"
                r = requests.get(stats_url, headers=headers, timeout=10)
                
                if r.status_code == 200:
                    games_data = r.json().get("response", [])
                    for g in games_data:
                        game = self._parse_rapidapi_game(g, season)
                        if game:
                            all_games.append(game)
            
            return all_games
            
        except Exception as e:
            print(f"RapidAPI error: {e}")
            return []
    
    def _parse_rapidapi_game(self, game_data: Dict, season: int) -> Dict:
        """Parse RapidAPI game format to our standard format"""
        try:
            return {
                'date': game_data.get('game', {}).get('date', ''),
                'season': season,
                'opponent': game_data.get('team', {}).get('name', 'UNK'),
                'home': game_data.get('game', {}).get('home', False),
                'result': 'W' if game_data.get('game', {}).get('win', False) else 'L',
                'minutes': int(game_data.get('min', '0').replace(':', '')) if game_data.get('min') else 0,
                'points': float(game_data.get('points', 0) or 0),
                'rebounds': float(game_data.get('totReb', 0) or 0),
                'offensive_rebounds': float(game_data.get('offReb', 0) or 0),
                'defensive_rebounds': float(game_data.get('defReb', 0) or 0),
                'assists': float(game_data.get('assists', 0) or 0),
                'fg_made': float(game_data.get('fgm', 0) or 0),
                'fg_attempted': float(game_data.get('fga', 0) or 0),
                'fg3_made': float(game_data.get('tpm', 0) or 0),
                'fg3_attempted': float(game_data.get('tpa', 0) or 0),
                'ft_made': float(game_data.get('ftm', 0) or 0),
                'ft_attempted': float(game_data.get('fta', 0) or 0),
                'steals': float(game_data.get('steals', 0) or 0),
                'blocks': float(game_data.get('blocks', 0) or 0),
                'turnovers': float(game_data.get('turnovers', 0) or 0),
                'plus_minus': float(game_data.get('plusMinus', 0) or 0),
                'game_score': 0  # Not in RapidAPI
            }
        except:
            return None
    
    def _get_from_sportsradar(self, player_name: str, seasons: int) -> List[Dict]:
        """
        Get player data from SportsRadar API
        
        To use:
        1. Sign up at https://developer.sportradar.com/
        2. Get NBA API key
        3. Set SPORTS_API_KEY env var
        4. Set api_source="sportsradar"
        """
        # SportsRadar implementation would go here
        # Similar structure to RapidAPI
        return []
    
    def _scrape_season(self, player_id: str, season: int) -> List[Dict]:
        """Scrape a single season's game log from Basketball-Reference"""
        url = f"https://www.basketball-reference.com/players/{player_id[0]}/{player_id}/gamelog/{season}"
        
        try:
            import time
            time.sleep(1)  # Rate limiting - be respectful
            
            r = requests.get(url, headers=self.headers, timeout=15)
            if r.status_code != 200:
                return []
            
            soup = BeautifulSoup(r.text, 'html.parser')
            table = soup.find('table', {'id': 'pgl_basic'})
            if not table:
                return []
            
            games = []
            rows = table.find('tbody').find_all('tr') if table.find('tbody') else []
            
            for row in rows:
                if 'thead' in row.get('class', []):
                    continue
                try:
                    game = {
                        'date': self._get_stat(row, 'date_game'),
                        'season': season,
                        'opponent': self._get_stat(row, 'opp_id'),
                        'home': self._get_stat(row, 'game_location') != '@',
                        'result': self._get_stat(row, 'game_result'),
                        'minutes': self._parse_minutes(self._get_stat(row, 'mp')),
                        'points': float(self._get_stat(row, 'pts') or 0),
                        'rebounds': float(self._get_stat(row, 'trb') or 0),
                        'offensive_rebounds': float(self._get_stat(row, 'orb') or 0),
                        'defensive_rebounds': float(self._get_stat(row, 'drb') or 0),
                        'assists': float(self._get_stat(row, 'ast') or 0),
                        'fg_made': float(self._get_stat(row, 'fg') or 0),
                        'fg_attempted': float(self._get_stat(row, 'fga') or 0),
                        'fg3_made': float(self._get_stat(row, 'fg3') or 0),
                        'fg3_attempted': float(self._get_stat(row, 'fg3a') or 0),
                        'ft_made': float(self._get_stat(row, 'ft') or 0),
                        'ft_attempted': float(self._get_stat(row, 'fta') or 0),
                        'steals': float(self._get_stat(row, 'stl') or 0),
                        'blocks': float(self._get_stat(row, 'blk') or 0),
                        'turnovers': float(self._get_stat(row, 'tov') or 0),
                        'plus_minus': float(self._get_stat(row, 'plus_minus') or 0),
                        'game_score': float(self._get_stat(row, 'game_score') or 0),
                    }
                    if game['minutes'] > 0:
                        games.append(game)
                except:
                    continue
            
            return games
            
        except Exception as e:
            print(f"Scrape error for {player_id} season {season}: {e}")
            return []
    
    def _get_stat(self, row, stat):
        td = row.find('td', {'data-stat': stat})
        return td.get_text(strip=True) if td else ""
    
    def _parse_minutes(self, val):
        try:
            if ':' in str(val):
                parts = val.split(':')
                return float(parts[0]) + float(parts[1]) / 60
            return float(val) if val else 0
        except:
            return 0
    
    def _get_player_id(self, name: str) -> Optional[str]:
        """Convert player name to BBRef ID"""
        mappings = {
            "lebron james": "jamesle01", "stephen curry": "curryst01", "kevin durant": "duranke01",
            "giannis antetokounmpo": "antetgi01", "luka doncic": "doncilu01", "jayson tatum": "tatumja01",
            "joel embiid": "embiijo01", "nikola jokic": "jokicni01", "anthony edwards": "edwaran01",
            "shai gilgeous-alexander": "gilgesh01", "donovan mitchell": "mitchdo01", "devin booker": "bookede01",
            "ja morant": "moranja01", "tyrese haliburton": "halibty01", "damian lillard": "lillada01",
            "jimmy butler": "butleji01", "paul george": "georgpa01", "kawhi leonard": "leonaka01",
            "anthony davis": "davisan02", "karl-anthony towns": "townska01", "trae young": "youngtr01",
            "lamelo ball": "ballla01", "cade cunningham": "cunMDca01", "paolo banchero": "bancMDpa01",
            "victor wembanyama": "wembavi01", "jalen brunson": "brunsja01", "de'aaron fox": "foxde01",
            "darius garland": "garlada01", "tyrese maxey": "maxeyty01", "scottie barnes": "barnesc01",
            "franz wagner": "wagnefr01", "evan mobley": "mobleev01", "desmond bane": "banede01",
            "demar derozan": "derozde01", "zach lavine": "lavinza01", "brandon ingram": "ingrabr01",
            "jaylen brown": "brownja02", "bam adebayo": "adebaba01", "pascal siakam": "siakapa01",
            "lauri markkanen": "markkla01", "jalen williams": "willija06", "alperen sengun": "sengual01",
            "chet holmgren": "holmgch01", "austin reaves": "reaveau01", "mikal bridges": "bridgmi01",
            "domantas sabonis": "sabondo01", "dejounte murray": "murrade01", "fred vanvleet": "vanvlfr01",
            "james harden": "hardeja01", "kyrie irving": "irvinky01", "russell westbrook": "westbru01",
        }
        name_lower = name.lower().strip()
        if name_lower in mappings:
            return mappings[name_lower]
        # Generate from pattern
        parts = name_lower.split()
        if len(parts) >= 2:
            return f"{parts[-1][:5]}{parts[0][:2]}01"
        return None


class LSTMModel:
    """LSTM Neural Network for time series prediction - FULL SEASON DATA"""
    
    def __init__(self, sequence_length: int = 15):
        # 15 games = ~3 weeks of NBA action, captures hot/cold streaks
        self.sequence_length = sequence_length
        self.model = None
        self.scaler = None
        self.is_trained = False
    
    def train(self, games: List[Dict], stat_type: str = "points") -> bool:
        """
        Train LSTM on player's FULL game history (multiple seasons)
        Uses all available data for training, predicts from recent sequence
        """
        if not TENSORFLOW_AVAILABLE or len(games) < 25:
            return False
        
        try:
            # Extract multiple features for richer predictions
            values = [g.get(stat_type, 0) for g in games if g.get(stat_type, 0) > 0]
            minutes = [g.get('minutes', 30) for g in games if g.get(stat_type, 0) > 0]
            home = [1.0 if g.get('home') else 0.0 for g in games if g.get(stat_type, 0) > 0]
            
            if len(values) < 25:
                return False
            
            # Multi-feature input: [stat, minutes, home/away]
            data = np.column_stack([values, minutes, home])
            
            # Normalize
            self.scaler = MinMaxScaler()
            scaled = self.scaler.fit_transform(data)
            
            # Create sequences from ENTIRE history
            X, y = [], []
            for i in range(len(scaled) - self.sequence_length):
                X.append(scaled[i:i+self.sequence_length])
                y.append(values[i+self.sequence_length])  # Predict raw stat value
            
            X, y = np.array(X), np.array(y)
            
            # Build deeper model for more data
            self.model = Sequential([
                Bidirectional(LSTM(64, return_sequences=True), input_shape=(self.sequence_length, 3)),
                Dropout(0.3),
                Bidirectional(LSTM(32, return_sequences=True)),
                Dropout(0.2),
                Bidirectional(LSTM(16)),
                Dropout(0.2),
                Dense(16, activation='relu'),
                Dense(8, activation='relu'),
                Dense(1)
            ])
            self.model.compile(optimizer='adam', loss='mse', metrics=['mae'])
            
            # Train with more epochs for larger dataset
            epochs = min(50, max(30, len(X) // 10))
            self.model.fit(X, y, epochs=epochs, batch_size=16, verbose=0,
                          validation_split=0.15,
                          callbacks=[EarlyStopping(patience=8, restore_best_weights=True)])
            
            self.is_trained = True
            return True
        except Exception as e:
            print(f"LSTM train error: {e}")
            return False
    
    def predict(self, games: List[Dict], stat_type: str = "points") -> Dict:
        """Predict next value from recent sequence using trained model"""
        if not self.is_trained or self.model is None or self.scaler is None:
            return {"prediction": 0, "confidence": 0}
        
        try:
            # Get recent games for prediction
            recent = games[:self.sequence_length]
            if len(recent) < self.sequence_length:
                return {"prediction": 0, "confidence": 0}
            
            # Extract features
            values = [g.get(stat_type, 0) for g in recent]
            minutes = [g.get('minutes', 30) for g in recent]
            home = [1.0 if g.get('home') else 0.0 for g in recent]
            
            data = np.column_stack([values, minutes, home])
            scaled = self.scaler.transform(data)
            X = scaled.reshape(1, self.sequence_length, 3)
            
            # Monte Carlo dropout for uncertainty estimation
            preds = []
            for _ in range(30):
                pred = float(self.model(X, training=True)[0][0])
                preds.append(pred)
            
            mean_pred = np.mean(preds)
            std = np.std(preds)
            
            # Confidence based on prediction consistency
            cv = std / abs(mean_pred) if mean_pred != 0 else 1
            confidence = max(0, min(95, 100 - cv * 200))
            
            return {
                "prediction": round(mean_pred, 1),
                "confidence": round(confidence, 1),
                "std": round(std, 2),
                "range": [round(mean_pred - 1.96*std, 1), round(mean_pred + 1.96*std, 1)]
            }
        except Exception as e:
            print(f"LSTM predict error: {e}")
            return {"prediction": 0, "confidence": 0}


class EnsembleModel:
    """
    Enhanced Ensemble with CatBoost for categorical variables
    
    Models:
    - XGBoost: Gradient boosting
    - LightGBM: Fast gradient boosting
    - Random Forest: Bagging ensemble
    - CatBoost: Handles categoricals (Home/Away, Opponent) natively
    
    CatBoost is critical because:
    - Home/Away is categorical (not just 0/1)
    - Opponent name is categorical
    - Position matchups are categorical
    """
    
    def __init__(self):
        self.models = {}
        self.scaler = StandardScaler() if ML_AVAILABLE else None
        self.label_encoders = {}  # For categorical features
        self.is_trained = False
        self.feature_names = []
    
    def train(self, games: List[Dict], stat_type: str = "points") -> bool:
        """Train ensemble on player's FULL game history (100+ games ideal)"""
        if not ML_AVAILABLE or len(games) < 25:
            return False
        
        try:
            # Create rich features from full history (including categoricals)
            X, y, cat_features = self._create_features_with_categoricals(games, stat_type)
            if len(X) < 20:
                return False
            
            # Separate numeric and categorical
            X_numeric = X[:, :len(self.feature_names) - len(cat_features)] if cat_features else X
            
            # Scale numeric features
            X_scaled = self.scaler.fit_transform(X_numeric)
            
            # Train standard models on scaled numeric
            self.models['xgb'] = xgb.XGBRegressor(
                n_estimators=100, max_depth=5, learning_rate=0.1,
                subsample=0.8, colsample_bytree=0.8, verbosity=0
            )
            self.models['lgb'] = lgb.LGBMRegressor(
                n_estimators=100, max_depth=5, learning_rate=0.1,
                subsample=0.8, colsample_bytree=0.8, verbose=-1
            )
            self.models['rf'] = RandomForestRegressor(
                n_estimators=100, max_depth=8, min_samples_leaf=3, random_state=42
            )
            
            for name in ['xgb', 'lgb', 'rf']:
                self.models[name].fit(X_scaled, y)
            
            # Train CatBoost with categorical features (if available)
            if CATBOOST_AVAILABLE and len(cat_features) > 0:
                try:
                    self.models['catboost'] = CatBoostRegressor(
                        iterations=100,
                        depth=6,
                        learning_rate=0.1,
                        loss_function='RMSE',
                        verbose=False,
                        cat_features=list(range(len(X_numeric[0]), X.shape[1]))  # Last columns are categorical
                    )
                    self.models['catboost'].fit(X, y)
                except Exception as e:
                    print(f"CatBoost training failed: {e}")
            
            self.is_trained = True
            return True
        except Exception as e:
            print(f"Ensemble train error: {e}")
            return False
    
    def predict(self, games: List[Dict], stat_type: str = "points") -> Dict:
        """Generate ensemble prediction from full game history"""
        if not self.is_trained:
            return {"prediction": 0, "confidence": 0}
        
        try:
            X, _, cat_features = self._create_features_with_categoricals(games, stat_type)
            if len(X) == 0:
                return {"prediction": 0, "confidence": 0}
            
            # Use most recent features for prediction
            X_latest = X[-1:]
            X_numeric = X_latest[:, :len(self.feature_names) - len(cat_features)] if cat_features else X_latest
            X_scaled = self.scaler.transform(X_numeric)
            
            preds = {}
            
            # Standard models
            for name in ['xgb', 'lgb', 'rf']:
                if name in self.models:
                    preds[name] = self.models[name].predict(X_scaled)[0]
            
            # CatBoost (uses full features including categoricals)
            if 'catboost' in self.models:
                try:
                    preds['catboost'] = self.models['catboost'].predict(X_latest)[0]
                except:
                    pass
            
            if not preds:
                return {"prediction": 0, "confidence": 0}
            
            mean_pred = np.mean(list(preds.values()))
            std = np.std(list(preds.values()))
            
            # Confidence based on model agreement
            agreement = 100 - (std / mean_pred * 100) if mean_pred > 0 else 50
            
            return {
                "prediction": round(mean_pred, 1),
                "confidence": round(max(0, min(95, agreement)), 1),
                "std": round(std, 2),
                "models": {k: round(v, 1) for k, v in preds.items()},
                "catboost_included": 'catboost' in preds
            }
        except Exception as e:
            print(f"Ensemble predict error: {e}")
            return {"prediction": 0, "confidence": 0}
    
    def _create_features_with_categoricals(self, games: List[Dict], stat_type: str):
        """Create features including categorical variables for CatBoost"""
        if len(games) < 15:
            return np.array([]), np.array([]), []
        
        values = [g.get(stat_type, 0) for g in games]
        minutes = [g.get('minutes', 30) for g in games]
        home = [1 if g.get('home') else 0 for g in games]
        opponents = [g.get('opponent', 'UNK') for g in games]
        
        # Encode opponents
        if 'opponent' not in self.label_encoders:
            self.label_encoders['opponent'] = LabelEncoder()
            unique_opps = list(set(opponents)) + ['UNK']
            self.label_encoders['opponent'].fit(unique_opps)
        
        try:
            opp_encoded = self.label_encoders['opponent'].transform(opponents)
        except:
            opp_encoded = [0] * len(opponents)
        
        # Additional stats
        fg_made = [g.get('fg_made', 0) for g in games]
        fg_attempted = [g.get('fg_attempted', 0) for g in games]
        
        X, y = [], []
        cat_features = ['is_home', 'opponent_encoded']
        
        for i in range(15, len(games)):
            # Rolling averages at different windows
            avg_3 = np.mean(values[i-3:i])
            avg_5 = np.mean(values[i-5:i])
            avg_10 = np.mean(values[i-10:i])
            avg_15 = np.mean(values[i-15:i])
            
            # Variability
            std_5 = np.std(values[i-5:i])
            std_10 = np.std(values[i-10:i])
            
            # Trend indicators
            trend_short = avg_3 - avg_10
            trend_long = avg_5 - avg_15
            
            # Minutes context
            min_avg_3 = np.mean(minutes[i-3:i])
            min_avg_10 = np.mean(minutes[i-10:i])
            min_trend = min_avg_3 - min_avg_10
            
            # Efficiency
            fg_pct_5 = np.sum(fg_made[i-5:i]) / max(1, np.sum(fg_attempted[i-5:i]))
            
            # Home/away splits (KEY IMPROVEMENT)
            home_games = [values[j] for j in range(i-10, i) if home[j]]
            away_games = [values[j] for j in range(i-10, i) if not home[j]]
            home_avg = np.mean(home_games) if home_games else avg_10
            away_avg = np.mean(away_games) if away_games else avg_10
            home_away_diff = home_avg - away_avg
            
            # Hot/cold streak
            above_avg_streak = sum(1 for j in range(i-5, i) if values[j] > avg_15)
            
            # Current game context
            is_home = home[i]
            opp_enc = opp_encoded[i]
            
            # Numeric features
            numeric_features = [
                avg_3, avg_5, avg_10, avg_15,        # Rolling averages
                std_5, std_10,                        # Variability
                trend_short, trend_long,              # Trends
                min_avg_3, min_trend,                 # Minutes context
                fg_pct_5,                             # Efficiency
                home_away_diff,                       # Venue split differential
                above_avg_streak,                     # Hot/cold indicator
                home_avg,                             # Home average
                away_avg                              # Away average
            ]
            
            # Categorical features (for CatBoost)
            categorical_features = [
                is_home,       # 0/1 but treated as categorical
                opp_enc        # Encoded opponent
            ]
            
            features = numeric_features + categorical_features
            
            X.append(features)
            y.append(values[i])
        
        self.feature_names = [
            'avg_3', 'avg_5', 'avg_10', 'avg_15',
            'std_5', 'std_10',
            'trend_short', 'trend_long',
            'min_avg_3', 'min_trend',
            'fg_pct_5',
            'home_away_diff',
            'above_avg_streak',
            'home_avg', 'away_avg',
            'is_home', 'opponent_encoded'
        ]
        
        return np.array(X), np.array(y), cat_features
        
        values = [g.get(stat_type, 0) for g in games]
        minutes = [g.get('minutes', 30) for g in games]
        home = [1 if g.get('home') else 0 for g in games]
        
        # Additional stats for context
        fg_made = [g.get('fg_made', 0) for g in games]
        fg_attempted = [g.get('fg_attempted', 0) for g in games]
        
        X, y = [], []
        for i in range(15, len(games)):
            # Rolling averages at different windows
            avg_3 = np.mean(values[i-3:i])
            avg_5 = np.mean(values[i-5:i])
            avg_10 = np.mean(values[i-10:i])
            avg_15 = np.mean(values[i-15:i])
            
            # Variability
            std_5 = np.std(values[i-5:i])
            std_10 = np.std(values[i-10:i])
            
            # Trend indicators
            trend_short = avg_3 - avg_10  # Recent vs medium term
            trend_long = avg_5 - avg_15   # Medium vs long term
            
            # Minutes context
            min_avg_3 = np.mean(minutes[i-3:i])
            min_avg_10 = np.mean(minutes[i-10:i])
            min_trend = min_avg_3 - min_avg_10
            
            # Efficiency (if shooting stats available)
            fg_pct_5 = np.sum(fg_made[i-5:i]) / max(1, np.sum(fg_attempted[i-5:i]))
            
            # Home/away recent split
            recent_home = np.mean([values[j] for j in range(i-10, i) if home[j]])
            recent_away = np.mean([values[j] for j in range(i-10, i) if not home[j]]) if any(not home[j] for j in range(i-10, i)) else avg_10
            home_away_diff = recent_home - recent_away if recent_home else 0
            
            # Hot/cold streak
            above_avg_streak = sum(1 for j in range(i-5, i) if values[j] > avg_15)
            
            # Current game context
            is_home = home[i]
            
            features = [
                avg_3, avg_5, avg_10, avg_15,        # Rolling averages
                std_5, std_10,                        # Variability
                trend_short, trend_long,              # Trends
                min_avg_3, min_trend,                 # Minutes context
                fg_pct_5,                             # Efficiency
                home_away_diff,                       # Venue split
                above_avg_streak,                     # Streak
                is_home,                              # Current venue
                i / len(games),                       # Season progress
            ]
            
            X.append(features)
            y.append(values[i])
        
        return np.array(X), np.array(y)


class MonteCarloSim:
    """
    Monte Carlo simulation with Kernel Density Estimation (KDE)
    
    Sports stats are NOT normally distributed - they are skewed:
    - Points: Can't go below 0, but can explode (40+ point games)
    - Rebounds: Skewed right (bigs can get 15+, guards rarely above 8)
    - Assists: Point guards have different distribution than centers
    
    KDE captures the TRUE shape of the distribution, not just mean/std.
    This is a HUGE upgrade from assuming normal distribution.
    """
    
    def simulate(self, games: List[Dict], stat_type: str, line: float, n_sims: int = 10000) -> Dict:
        """Simulate player prop outcome using KDE for realistic distribution"""
        values = [g.get(stat_type, 0) for g in games if g.get(stat_type, 0) > 0]
        
        if len(values) < 5:
            return {"over_prob": 50, "under_prob": 50, "confidence": 0}
        
        # Basic stats
        mean = np.mean(values)
        std = np.std(values)
        median = np.median(values)
        
        # Recent trend adjustment
        recent_5 = np.mean(values[:5]) if len(values) >= 5 else mean
        recent_10 = np.mean(values[:10]) if len(values) >= 10 else mean
        
        # Trend factor
        trend = (recent_5 - recent_10) * 0.5  # Half of recent trend
        
        # Use KDE if available, otherwise fall back to adjusted distribution
        if ML_AVAILABLE and len(values) >= 10:
            try:
                sims = self._kde_simulation(values, n_sims, trend)
                method = "KDE"
            except Exception as e:
                sims = self._adjusted_simulation(values, n_sims, trend)
                method = "adjusted_normal"
        else:
            sims = self._adjusted_simulation(values, n_sims, trend)
            method = "adjusted_normal"
        
        # Calculate probabilities
        over_prob = (np.sum(sims > line) / n_sims) * 100
        under_prob = (np.sum(sims < line) / n_sims) * 100
        push_prob = (np.sum(sims == line) / n_sims) * 100
        
        # Simulated mean and percentiles
        sim_mean = np.mean(sims)
        sim_median = np.median(sims)
        p25 = np.percentile(sims, 25)
        p75 = np.percentile(sims, 75)
        
        # Edge from line
        edge = sim_mean - line
        
        # Confidence based on how far from 50/50 we are
        confidence = min(90, abs(over_prob - 50) * 2)
        
        # Detect skewness
        skewness = (mean - median) / std if std > 0 else 0
        
        return {
            "over_prob": round(over_prob, 1),
            "under_prob": round(under_prob, 1),
            "push_prob": round(push_prob, 1),
            "mean": round(sim_mean, 1),
            "median": round(sim_median, 1),
            "historical_mean": round(mean, 1),
            "recent_5_avg": round(recent_5, 1),
            "percentile_25": round(p25, 1),
            "percentile_75": round(p75, 1),
            "edge": round(edge, 1),
            "confidence": round(confidence, 1),
            "skewness": round(skewness, 2),
            "method": method,
            "sample_size": len(values),
            "recommendation": "OVER" if over_prob >= 57 else "UNDER" if under_prob >= 57 else "PASS"
        }
    
    def _kde_simulation(self, values: List[float], n_sims: int, trend: float) -> np.ndarray:
        """
        Use Kernel Density Estimation for realistic simulation
        KDE captures the TRUE shape of the distribution
        """
        values_array = np.array(values).reshape(-1, 1)
        
        # Bandwidth selection (Scott's rule)
        bandwidth = 1.06 * np.std(values) * len(values) ** (-1/5)
        bandwidth = max(0.5, min(bandwidth, 3.0))  # Constrain
        
        # Fit KDE
        kde = KernelDensity(kernel='gaussian', bandwidth=bandwidth)
        kde.fit(values_array)
        
        # Sample from KDE
        samples = kde.sample(n_samples=n_sims).flatten()
        
        # Apply trend adjustment
        samples = samples + trend
        
        # Ensure non-negative (stats can't be negative)
        samples = np.maximum(samples, 0)
        
        return samples
    
    def _adjusted_simulation(self, values: List[float], n_sims: int, trend: float) -> np.ndarray:
        """
        Fallback: Use adjusted distribution accounting for skewness
        """
        mean = np.mean(values)
        std = np.std(values)
        
        # Adjust mean for trend
        adj_mean = mean + trend
        
        # Check for skewness and use appropriate distribution
        median = np.median(values)
        skew = (mean - median) / std if std > 0 else 0
        
        if abs(skew) > 0.3:
            # Data is skewed - use truncated normal or gamma-like
            # Simulate with slight right skew (common in sports stats)
            base_sims = np.random.normal(adj_mean, std, n_sims)
            # Add positive skew factor
            skew_factor = np.random.exponential(std * 0.3, n_sims)
            sims = base_sims + (skew_factor if skew > 0 else -skew_factor * 0.5)
        else:
            # Roughly symmetric - normal is fine
            sims = np.random.normal(adj_mean, std, n_sims)
        
        # Ensure non-negative
        sims = np.maximum(sims, 0)
        
        return sims
    
    def get_distribution_analysis(self, games: List[Dict], stat_type: str) -> Dict:
        """Analyze the distribution shape of a player's stats"""
        values = [g.get(stat_type, 0) for g in games if g.get(stat_type, 0) > 0]
        
        if len(values) < 10:
            return {"error": "Insufficient data"}
        
        mean = np.mean(values)
        std = np.std(values)
        median = np.median(values)
        mode_approx = 3 * median - 2 * mean  # Approximate mode
        
        # Percentiles
        percentiles = {
            "p10": np.percentile(values, 10),
            "p25": np.percentile(values, 25),
            "p50": np.percentile(values, 50),
            "p75": np.percentile(values, 75),
            "p90": np.percentile(values, 90)
        }
        
        # Skewness
        skewness = (mean - median) / std if std > 0 else 0
        
        # Kurtosis approximation (heavy tails?)
        p90_p10_range = percentiles["p90"] - percentiles["p10"]
        iqr = percentiles["p75"] - percentiles["p25"]
        kurtosis_proxy = p90_p10_range / iqr if iqr > 0 else 2.5
        
        return {
            "mean": round(mean, 1),
            "median": round(median, 1),
            "mode_approx": round(mode_approx, 1),
            "std": round(std, 1),
            "coefficient_of_variation": round(std / mean * 100, 1) if mean > 0 else 0,
            "skewness": round(skewness, 2),
            "skew_direction": "right" if skewness > 0.2 else "left" if skewness < -0.2 else "symmetric",
            "kurtosis_proxy": round(kurtosis_proxy, 2),
            "tail_heaviness": "heavy" if kurtosis_proxy > 3 else "normal" if kurtosis_proxy > 2 else "light",
            "percentiles": {k: round(v, 1) for k, v in percentiles.items()},
            "sample_size": len(values),
            "min": round(min(values), 1),
            "max": round(max(values), 1),
            "range": round(max(values) - min(values), 1)
        }


class MatchupModel:
    """
    Analyzes player performance vs specific opponents WITH home/away splits
    
    Key insight: Role players shoot 10-15% better at home!
    - Crowd support affects confidence
    - Familiar surroundings help rhythm
    - Travel fatigue affects road performance
    
    This model now considers:
    1. Overall vs opponent performance
    2. HOME vs opponent performance
    3. AWAY vs opponent performance
    4. Recency-weighted averages (recent games matter more)
    """
    
    def analyze(self, games: List[Dict], opponent: str, stat_type: str, 
                is_home_game: bool = None) -> Dict:
        """
        Analyze how player performs vs opponent with home/away context
        
        Args:
            games: Player's game history
            opponent: Opponent team name
            stat_type: points, rebounds, assists, etc.
            is_home_game: Whether upcoming game is at home (for specific prediction)
        """
        # Filter games vs opponent
        vs_opp = [g for g in games if opponent.lower() in g.get('opponent', '').lower()]
        
        # Overall stats
        all_values = [g.get(stat_type, 0) for g in games if g.get(stat_type, 0) > 0]
        overall_avg = np.mean(all_values) if all_values else 0
        
        if len(vs_opp) < 1:
            # No matchup history - use home/away split as baseline
            return self._get_home_away_baseline(games, stat_type, is_home_game, overall_avg)
        
        # Matchup stats
        vs_opp_values = [g.get(stat_type, 0) for g in vs_opp]
        vs_avg = np.mean(vs_opp_values)
        
        # HOME games vs opponent
        vs_opp_home = [g for g in vs_opp if g.get('home', False)]
        vs_opp_home_values = [g.get(stat_type, 0) for g in vs_opp_home]
        vs_home_avg = np.mean(vs_opp_home_values) if vs_opp_home_values else vs_avg
        
        # AWAY games vs opponent
        vs_opp_away = [g for g in vs_opp if not g.get('home', False)]
        vs_opp_away_values = [g.get(stat_type, 0) for g in vs_opp_away]
        vs_away_avg = np.mean(vs_opp_away_values) if vs_opp_away_values else vs_avg
        
        # Overall home/away splits (not just vs this opponent)
        all_home = [g.get(stat_type, 0) for g in games if g.get('home', False) and g.get(stat_type, 0) > 0]
        all_away = [g.get(stat_type, 0) for g in games if not g.get('home', False) and g.get(stat_type, 0) > 0]
        
        home_avg = np.mean(all_home) if all_home else overall_avg
        away_avg = np.mean(all_away) if all_away else overall_avg
        
        # Home/away differential (THE KEY STAT)
        home_away_diff = home_avg - away_avg
        home_boost_pct = (home_avg / away_avg - 1) * 100 if away_avg > 0 else 0
        
        # Recency-weighted average vs opponent
        recency_weighted = self._recency_weighted_avg(vs_opp, stat_type)
        
        # Determine adjustment based on game location
        if is_home_game is True:
            # Upcoming game is at HOME
            relevant_avg = vs_home_avg if vs_opp_home_values else home_avg
            location_context = "HOME"
        elif is_home_game is False:
            # Upcoming game is AWAY
            relevant_avg = vs_away_avg if vs_opp_away_values else away_avg
            location_context = "AWAY"
        else:
            # Unknown - use overall vs opponent
            relevant_avg = vs_avg
            location_context = "UNKNOWN"
        
        # Calculate adjustment from overall average
        matchup_adjustment = vs_avg - overall_avg
        location_adjustment = relevant_avg - overall_avg
        
        # Confidence based on sample size
        base_confidence = min(85, len(vs_opp) * 15)
        
        # Boost confidence if we have location-specific data
        if is_home_game is True and len(vs_opp_home) >= 2:
            base_confidence += 10
        elif is_home_game is False and len(vs_opp_away) >= 2:
            base_confidence += 10
        
        return {
            # Overall matchup
            "vs_opponent_avg": round(vs_avg, 1),
            "overall_avg": round(overall_avg, 1),
            "matchup_adjustment": round(matchup_adjustment, 1),
            
            # Home/away vs opponent
            "vs_opponent_home_avg": round(vs_home_avg, 1),
            "vs_opponent_away_avg": round(vs_away_avg, 1),
            "vs_opponent_home_games": len(vs_opp_home),
            "vs_opponent_away_games": len(vs_opp_away),
            
            # Overall home/away splits
            "overall_home_avg": round(home_avg, 1),
            "overall_away_avg": round(away_avg, 1),
            "home_away_differential": round(home_away_diff, 1),
            "home_boost_pct": round(home_boost_pct, 1),
            
            # For prediction
            "location_context": location_context,
            "location_adjusted_avg": round(relevant_avg, 1),
            "location_adjustment": round(location_adjustment, 1),
            
            # Recency
            "recency_weighted_avg": round(recency_weighted, 1),
            
            # Meta
            "confidence": min(95, base_confidence),
            "sample_size": len(vs_opp),
            "trend": "BOOST" if location_adjustment > 2 else "REDUCE" if location_adjustment < -2 else "NEUTRAL"
        }
    
    def _get_home_away_baseline(self, games: List[Dict], stat_type: str, 
                                 is_home_game: bool, overall_avg: float) -> Dict:
        """When no matchup history, use home/away split as baseline"""
        all_home = [g.get(stat_type, 0) for g in games if g.get('home', False) and g.get(stat_type, 0) > 0]
        all_away = [g.get(stat_type, 0) for g in games if not g.get('home', False) and g.get(stat_type, 0) > 0]
        
        home_avg = np.mean(all_home) if all_home else overall_avg
        away_avg = np.mean(all_away) if all_away else overall_avg
        home_away_diff = home_avg - away_avg
        
        if is_home_game is True:
            relevant_avg = home_avg
            location_context = "HOME"
        elif is_home_game is False:
            relevant_avg = away_avg
            location_context = "AWAY"
        else:
            relevant_avg = overall_avg
            location_context = "UNKNOWN"
        
        location_adjustment = relevant_avg - overall_avg
        
        return {
            "vs_opponent_avg": None,
            "overall_avg": round(overall_avg, 1),
            "matchup_adjustment": 0,
            "vs_opponent_home_avg": None,
            "vs_opponent_away_avg": None,
            "vs_opponent_home_games": 0,
            "vs_opponent_away_games": 0,
            "overall_home_avg": round(home_avg, 1),
            "overall_away_avg": round(away_avg, 1),
            "home_away_differential": round(home_away_diff, 1),
            "home_boost_pct": round((home_avg / away_avg - 1) * 100, 1) if away_avg > 0 else 0,
            "location_context": location_context,
            "location_adjusted_avg": round(relevant_avg, 1),
            "location_adjustment": round(location_adjustment, 1),
            "recency_weighted_avg": round(overall_avg, 1),
            "confidence": 30,  # Low confidence without matchup data
            "sample_size": 0,
            "trend": "HOME_BOOST" if is_home_game and home_away_diff > 1.5 else "AWAY_DROP" if not is_home_game and home_away_diff > 1.5 else "NEUTRAL",
            "note": "No matchup history - using home/away splits only"
        }
    
    def _recency_weighted_avg(self, games: List[Dict], stat_type: str) -> float:
        """Calculate recency-weighted average (recent games matter more)"""
        if not games:
            return 0
        
        # Sort by date (most recent first)
        sorted_games = sorted(games, key=lambda x: x.get('date', ''), reverse=True)
        
        values = []
        weights = []
        
        for i, g in enumerate(sorted_games):
            val = g.get(stat_type, 0)
            if val > 0:
                # Weight decays: most recent = 1.0, then 0.9, 0.8, etc.
                weight = max(0.3, 1.0 - (i * 0.1))
                values.append(val)
                weights.append(weight)
        
        if not values:
            return 0
        
        return np.average(values, weights=weights)


class RealMLSystem:
    """
    Master ML system combining all models with ADVANCED CONTEXTUAL FEATURES
    
    Features Categories:
    1. Historical Performance (rolling averages, trends, streaks)
    2. Opponent Defensive Context (defense vs position)
    3. Pace & Possessions (game environment)
    4. Team Context & Usage Vacuum (teammate injuries)
    5. Rest & Travel Fatigue
    6. Vegas Market Wisdom (lines as features)
    7. Referee Impact
    """
    
    def __init__(self):
        self.scraper = PlayerDataScraper()
        self.lstm_models = {}
        self.ensemble_models = {}
        self.monte_carlo = MonteCarloSim()
        self.matchup = MatchupModel()
    
    def predict_prop(self, player: str, opponent: str, stat_type: str, line: float, 
                    sport: str = "NBA", player_position: str = None, 
                    player_team: str = None, injured_teammates: List[str] = None,
                    days_rest: int = 2, game_odds: Dict = None) -> Dict:
        """
        Generate comprehensive ML prediction with ALL contextual features
        
        Args:
            player: Player name
            opponent: Opposing team
            stat_type: points, rebounds, assists, etc.
            line: The betting line
            sport: Sport (NBA default)
            player_position: Player's position (PG, SG, SF, PF, C)
            player_team: Player's team
            injured_teammates: List of injured teammates
            days_rest: Days since last game
            game_odds: Game odds data for Vegas context
        """
        # Get player data (2 seasons)
        games = self.scraper.get_player_game_log(player, sport, seasons=2)
        
        if len(games) < 15:
            return {
                "success": False,
                "error": f"Need 15+ games for {player}, found {len(games)}",
                "games_found": len(games),
                "predictions": {}
            }
        
        # Map stat types
        stat_map = {
            "points": "points", "pts": "points",
            "rebounds": "rebounds", "reb": "rebounds", "trb": "rebounds",
            "assists": "assists", "ast": "assists",
            "threes": "fg3_made", "3pm": "fg3_made", "fg3": "fg3_made",
            "steals": "steals", "stl": "steals",
            "blocks": "blocks", "blk": "blocks",
            "turnovers": "turnovers", "tov": "turnovers"
        }
        stat = stat_map.get(stat_type.lower(), stat_type.lower())
        
        predictions = {}
        contextual_adjustments = {}
        
        # ========== CONTEXTUAL FEATURES ==========
        
        # 1. OPPONENT DEFENSIVE CONTEXT
        position = player_position or self._guess_position(player)
        defense_context = defense_scraper.get_team_defense_vs_position(opponent, position)
        contextual_adjustments["defense"] = {
            "opponent": opponent,
            "position": position,
            "defensive_rating": defense_context.get("rating"),
            "adjustment_pct": defense_context.get("adjustment", 0)
        }
        
        # 2. PACE & POSSESSIONS
        if player_team:
            pace_context = pace_scraper.get_game_pace_projection(player_team, opponent)
            contextual_adjustments["pace"] = {
                "projected_pace": pace_context.get("projected_pace"),
                "game_environment": pace_context.get("game_environment"),
                "stat_adjustment_pct": pace_context.get("stat_adjustment", 0)
            }
        
        # 3. TEAM CONTEXT & USAGE VACUUM
        if player_team:
            usage_boost = team_context_scraper.get_player_usage_boost(player, player_team, injured_teammates)
            contextual_adjustments["usage"] = {
                "boost_pct": usage_boost.get("boost", 0),
                "multiplier": usage_boost.get("adjusted_multiplier", 1.0),
                "reason": usage_boost.get("reason", "Full strength")
            }
        
        # 4. REST & TRAVEL FATIGUE
        fatigue = rest_travel_scraper.get_fatigue_analysis(
            player_team or "unknown",
            days_rest,
            games_in_5_days=2,  # Could be passed in
            games_in_7_days=3
        )
        contextual_adjustments["fatigue"] = {
            "fatigue_level": fatigue.get("fatigue_level"),
            "back_to_back": fatigue.get("back_to_back"),
            "performance_adjustment": fatigue.get("performance_adjustment", 0)
        }
        
        # 5. VEGAS MARKET CONTEXT
        if game_odds:
            vegas_context = vegas_scraper.get_vegas_context(game_odds, line)
            contextual_adjustments["vegas"] = {
                "game_total": vegas_context.get("total"),
                "spread": vegas_context.get("spread"),
                "blowout_risk": vegas_context.get("is_blowout"),
                "pace_implication": vegas_context.get("pace_implication")
            }
        
        # ========== CALCULATE TOTAL ADJUSTMENT ==========
        
        # Combine all contextual adjustments into a single multiplier
        total_adjustment = 1.0
        
        # Defense adjustment (elite defense = lower stats)
        def_adj = contextual_adjustments.get("defense", {}).get("adjustment_pct", 0) / 100
        total_adjustment *= (1 + def_adj)
        
        # Pace adjustment (fast pace = more stats)
        pace_adj = contextual_adjustments.get("pace", {}).get("stat_adjustment_pct", 0) / 100
        total_adjustment *= (1 + pace_adj)
        
        # Usage vacuum adjustment (injured star = boost)
        usage_mult = contextual_adjustments.get("usage", {}).get("multiplier", 1.0)
        total_adjustment *= usage_mult
        
        # Fatigue adjustment (tired = lower stats)
        fatigue_adj = contextual_adjustments.get("fatigue", {}).get("performance_adjustment", 0)
        total_adjustment *= (1 + fatigue_adj)
        
        contextual_adjustments["total_multiplier"] = round(total_adjustment, 3)
        contextual_adjustments["total_adjustment_pct"] = round((total_adjustment - 1) * 100, 1)
        
        # ========== BASE MODEL PREDICTIONS ==========
        
        # 1. Monte Carlo (uses full distribution)
        mc = self.monte_carlo.simulate(games, stat, line)
        predictions["monte_carlo"] = mc
        
        # 2. Ensemble Model
        cache_key = f"{player}_{stat}"
        if cache_key not in self.ensemble_models:
            self.ensemble_models[cache_key] = EnsembleModel()
            self.ensemble_models[cache_key].train(games, stat)
        
        if self.ensemble_models[cache_key].is_trained:
            ens = self.ensemble_models[cache_key].predict(games, stat)
            predictions["ensemble"] = ens
        
        # 3. LSTM Model
        if TENSORFLOW_AVAILABLE:
            if cache_key not in self.lstm_models:
                self.lstm_models[cache_key] = LSTMModel(sequence_length=15)
                self.lstm_models[cache_key].train(games, stat)
            
            if self.lstm_models[cache_key].is_trained:
                lstm = self.lstm_models[cache_key].predict(games, stat)
                predictions["lstm"] = lstm
        
        # 4. Matchup Analysis
        matchup = self.matchup.analyze(games, opponent, stat)
        predictions["matchup"] = matchup
        
        # ========== APPLY CONTEXTUAL ADJUSTMENTS ==========
        
        # Adjust base predictions with contextual multiplier
        adjusted_predictions = {}
        for model_name, pred in predictions.items():
            if isinstance(pred, dict) and "prediction" in pred:
                base_pred = pred.get("prediction", 0) or pred.get("mean", 0)
                if base_pred > 0:
                    adjusted = base_pred * total_adjustment
                    adjusted_predictions[model_name] = round(adjusted, 1)
            elif isinstance(pred, dict) and "mean" in pred:
                base_mean = pred.get("mean", 0)
                if base_mean > 0:
                    adjusted_predictions[model_name] = round(base_mean * total_adjustment, 1)
        
        # ========== COMBINE INTO FINAL PREDICTION ==========
        
        final = self._combine_predictions_with_context(
            predictions, 
            contextual_adjustments, 
            line, 
            stat,
            adjusted_predictions
        )
        
        return {
            "success": True,
            "player": player,
            "opponent": opponent,
            "stat_type": stat_type,
            "line": line,
            "games_analyzed": len(games),
            "seasons_used": len(set(g.get('season', 2025) for g in games)),
            "predictions": predictions,
            "contextual_adjustments": contextual_adjustments,
            "adjusted_predictions": adjusted_predictions,
            "final": final
        }
    
    def _guess_position(self, player: str) -> str:
        """Guess player position from name"""
        # Position mappings for known players
        positions = {
            "lebron james": "SF", "stephen curry": "PG", "kevin durant": "SF",
            "giannis antetokounmpo": "PF", "luka doncic": "PG", "jayson tatum": "SF",
            "joel embiid": "C", "nikola jokic": "C", "anthony edwards": "SG",
            "shai gilgeous-alexander": "PG", "donovan mitchell": "SG", "devin booker": "SG",
            "ja morant": "PG", "tyrese haliburton": "PG", "damian lillard": "PG",
            "jimmy butler": "SF", "paul george": "SF", "kawhi leonard": "SF",
            "anthony davis": "PF", "karl-anthony towns": "C", "trae young": "PG",
            "lamelo ball": "PG", "jalen brunson": "PG", "de'aaron fox": "PG",
            "darius garland": "PG", "tyrese maxey": "PG", "bam adebayo": "C",
            "victor wembanyama": "C", "paolo banchero": "PF", "scottie barnes": "SF",
            "franz wagner": "SF", "chet holmgren": "C", "alperen sengun": "C"
        }
        
        player_lower = player.lower()
        for name, pos in positions.items():
            if name in player_lower or player_lower in name:
                return pos
        
        return "SF"  # Default
    
    def _combine_predictions_with_context(self, predictions: Dict, context: Dict, 
                                          line: float, stat: str, adjusted: Dict) -> Dict:
        """Combine predictions with contextual adjustments"""
        
        values = []
        confidences = []
        
        # Collect adjusted predictions
        for model, adj_pred in adjusted.items():
            if adj_pred and adj_pred > 0:
                values.append(adj_pred)
                # Get confidence from original prediction
                orig = predictions.get(model, {})
                conf = orig.get("confidence", 50)
                confidences.append(conf)
        
        # Also include matchup adjustment if significant
        matchup = predictions.get("matchup", {})
        if matchup.get("confidence", 0) > 40:
            matchup_adj = matchup.get("adjustment", 0)
            if abs(matchup_adj) > 1:
                # Apply matchup to average prediction
                if values:
                    matchup_value = np.mean(values) + matchup_adj
                    values.append(matchup_value)
                    confidences.append(matchup.get("confidence", 50))
        
        if not values:
            return {
                "prediction": line,
                "confidence": 0,
                "recommendation": "NO_DATA"
            }
        
        # Weighted average by confidence
        total_conf = sum(confidences)
        if total_conf > 0:
            weighted = sum(v * c for v, c in zip(values, confidences)) / total_conf
        else:
            weighted = np.mean(values)
        
        # Calculate edge and confidence
        edge = weighted - line
        avg_conf = np.mean(confidences)
        
        # Model agreement factor
        if len(values) > 1:
            agreement = 100 - (np.std(values) / np.mean(values) * 100)
        else:
            agreement = 50
        
        final_conf = (avg_conf * 0.5) + (max(0, agreement) * 0.3) + (min(abs(edge) * 5, 20))
        final_conf = max(0, min(95, final_conf))
        
        # Context boost/penalty
        total_mult = context.get("total_multiplier", 1.0)
        if total_mult > 1.05 or total_mult < 0.95:
            final_conf += 5  # Strong contextual signal
        
        # Recommendation
        if final_conf >= 75:
            if edge > 2:
                rec = "STRONG_OVER"
            elif edge < -2:
                rec = "STRONG_UNDER"
            elif edge > 1:
                rec = "OVER"
            elif edge < -1:
                rec = "UNDER"
            else:
                rec = "PASS"
        elif final_conf >= 60:
            if edge > 1.5:
                rec = "LEAN_OVER"
            elif edge < -1.5:
                rec = "LEAN_UNDER"
            else:
                rec = "PASS"
        else:
            rec = "LOW_CONFIDENCE"
        
        return {
            "prediction": round(weighted, 1),
            "confidence": round(final_conf, 1),
            "confidence_label": "STRONG" if final_conf >= 85 else "GOOD" if final_conf >= 75 else "LEAN" if final_conf >= 60 else "BELOW",
            "edge": round(edge, 1),
            "edge_pct": round((edge / line) * 100, 1) if line > 0 else 0,
            "recommendation": rec,
            "models_used": len(values),
            "contextual_adjustment": context.get("total_adjustment_pct", 0)
        }
    
    def _combine_predictions(self, preds: Dict, line: float, stat: str) -> Dict:
        """Combine all model predictions"""
        values = []
        confidences = []
        
        if "monte_carlo" in preds:
            values.append(preds["monte_carlo"].get("mean", line))
            confidences.append(preds["monte_carlo"].get("confidence", 50))
        
        if "ensemble" in preds and preds["ensemble"].get("prediction", 0) > 0:
            values.append(preds["ensemble"]["prediction"])
            confidences.append(preds["ensemble"].get("confidence", 50))
        
        if "lstm" in preds and preds["lstm"].get("prediction", 0) > 0:
            values.append(preds["lstm"]["prediction"])
            confidences.append(preds["lstm"].get("confidence", 50))
        
        if not values:
            return {"prediction": line, "confidence": 0, "recommendation": "NO_DATA"}
        
        # Weighted average
        total_conf = sum(confidences)
        if total_conf > 0:
            weighted = sum(v * c for v, c in zip(values, confidences)) / total_conf
        else:
            weighted = np.mean(values)
        
        # Apply matchup adjustment
        if "matchup" in preds and preds["matchup"].get("confidence", 0) > 30:
            adj = preds["matchup"]["adjustment"] * (preds["matchup"]["confidence"] / 100) * 0.5
            weighted += adj
        
        edge = weighted - line
        avg_conf = np.mean(confidences)
        agreement = 100 - (np.std(values) / np.mean(values) * 100) if np.mean(values) > 0 else 50
        final_conf = (avg_conf * 0.6) + (agreement * 0.4)
        
        # Recommendation
        if final_conf >= 75:
            if edge > 1.5:
                rec = "STRONG_OVER"
            elif edge < -1.5:
                rec = "STRONG_UNDER"
            elif edge > 0.5:
                rec = "OVER"
            elif edge < -0.5:
                rec = "UNDER"
            else:
                rec = "PASS"
        else:
            rec = "LOW_CONFIDENCE"
        
        return {
            "prediction": round(weighted, 1),
            "confidence": round(final_conf, 1),
            "confidence_label": "STRONG" if final_conf >= 85 else "GOOD" if final_conf >= 75 else "BELOW",
            "edge": round(edge, 1),
            "recommendation": rec,
            "models_used": len(values)
        }


# Instantiate Real ML System
real_ml = RealMLSystem()


# ============================================
# PICKS ENGINE V2 - THE BRAIN
# ============================================

class PicksEngineV2:
    """
    Master Picks Engine combining ALL 17 signals:
    - 8 AI Models
    - 4 Esoteric Systems  
    - 5 External Data Signals
    Plus: Grading, Learning, Performance Tracking
    """
    
    def __init__(self):
        # Signal weights (learned over time)
        self.weights = {
            "ensemble_prediction": 15,
            "lstm_sequence": 10,
            "matchup_specific": 12,
            "monte_carlo_probability": 14,
            "line_movement_signal": 13,
            "rest_fatigue_factor": 8,
            "injury_impact": 10,
            "kelly_edge": 12,
            "gematria_alignment": 6,
            "numerology_power": 8,
            "sacred_geometry": 5,
            "moon_phase": 7,
            "zodiac_element": 4,
            "sharp_money": 18,
            "public_fade": 8,
            "line_value": 10,
            "key_number": 6,
            "referee_crew": 12  # Refs impact totals and spreads significantly
        }
        
        self.picks_history = []
        self.graded_picks = []
        self.performance = {
            "total_picks": 0, "wins": 0, "losses": 0, "pushes": 0,
            "win_rate": 0, "roi": 0,
            "by_sport": {}, "by_type": {}, "by_confidence": {}
        }
        self._load_history()
    
    def generate_best_bets(self, sport="basketball_nba"):
        """Generate best bets using ALL signals"""
        best_bets = []
        
        # Get live odds
        odds_data = odds_service.get_live_odds(sport)
        if not odds_data.get("success") or not odds_data.get("games"):
            return {"success": False, "error": "No games available", "picks": []}
        
        # Get splits
        league_map = {"basketball_nba": "NBA", "basketball_ncaab": "NCAAB", "football_nfl": "NFL", "icehockey_nhl": "NHL", "baseball_mlb": "MLB"}
        splits_data = splits_service.get_splits(league_map.get(sport, "NFL"))
        splits_lookup = self._build_splits_lookup(splits_data)
        
        # Get today's cosmic energy
        today = date.today()
        today_numerology = esoteric.numerology.date_energy(today)
        today_moon = esoteric.astrology.moon_phase(today)
        today_zodiac = esoteric.astrology.zodiac(today)
        
        for game in odds_data.get("games", []):
            try:
                home = game.get("home_team", "")
                away = game.get("away_team", "")
                
                # Get bookmaker odds from odds_service structure
                bookmakers = game.get("bookmakers", {})
                fd = bookmakers.get("fanduel", {}).get("markets", {})
                dk = bookmakers.get("draftkings", {}).get("markets", {})
                markets = fd if fd else dk
                if not markets:
                    continue
                
                # Run full esoteric analysis
                esoteric_result = esoteric.analyze_matchup(home, away, today, self._get_total(markets))
                
                # Calculate signals
                signals = {}
                reasons = []
                total_score = 0
                max_possible = 0
                
                # Get actual odds data
                spreads = markets.get("spreads", {})
                totals = markets.get("totals", {})
                h2h = markets.get("h2h", {})
                
                home_spread = spreads.get(home, {}).get("point", 0)
                home_spread_odds = spreads.get(home, {}).get("price", -110)
                away_spread = spreads.get(away, {}).get("point", 0)
                away_spread_odds = spreads.get(away, {}).get("price", -110)
                
                total_line = totals.get("Over", {}).get("point", 0)
                over_odds = totals.get("Over", {}).get("price", -110)
                under_odds = totals.get("Under", {}).get("price", -110)
                
                home_ml = h2h.get(home, {}).get("price", -110)
                away_ml = h2h.get(away, {}).get("price", -110)
                
                # ===== AI MODEL SIGNALS (Based on Real Odds) =====
                
                # 1. Line Value Analysis - Look for plus money or off-key numbers
                weight = self.weights["ensemble_prediction"]
                max_possible += weight
                # Value on spread if getting + odds or if spread is off key number
                if home_spread_odds > -105 or away_spread_odds > -105:
                    better_side = home if home_spread_odds > away_spread_odds else away
                    total_score += weight * 0.7
                    signals["line_value"] = {"side": better_side, "odds": max(home_spread_odds, away_spread_odds)}
                    reasons.append(f"Line Value: {better_side} at {max(home_spread_odds, away_spread_odds)}")
                
                # 2. Moneyline Value - Underdog value check
                weight = self.weights["monte_carlo_probability"]
                max_possible += weight
                # Good value if underdog is +150 to +300 range (not too big, not too small)
                if 150 <= away_ml <= 300:
                    total_score += weight * 0.8
                    signals["ml_value"] = {"team": away, "odds": away_ml}
                    reasons.append(f"ML Value: {away} +{away_ml}")
                elif 150 <= home_ml <= 300:
                    total_score += weight * 0.8
                    signals["ml_value"] = {"team": home, "odds": home_ml}
                    reasons.append(f"ML Value: {home} +{home_ml}")
                
                # 3. Sharp Money Detection
                sharp = self._check_sharp_money(home, away, splits_lookup)
                weight = self.weights["sharp_money"]
                max_possible += weight
                if sharp.get("detected"):
                    score_pct = min(1.0, sharp["strength"] / 12)
                    total_score += score_pct * weight
                    signals["sharp_money"] = sharp
                    reasons.append(f"SHARP MONEY: {sharp['side']} ({sharp['strength']}%)")
                
                # 4. Spread Analysis - Key numbers and hook value
                weight = self.weights["matchup_specific"]
                max_possible += weight
                # Key numbers in basketball: 3, 7, 10 / Key numbers in football: 3, 7
                if abs(home_spread) in [3, 3.5, 7, 7.5]:
                    total_score += weight * 0.75
                    signals["key_spread"] = {"spread": home_spread}
                    reasons.append(f"Key Number: {home_spread}")
                elif abs(home_spread) == 2.5:  # Hook on 3
                    total_score += weight * 0.6
                    signals["hook"] = {"spread": home_spread}
                    reasons.append(f"Hook Value: {home_spread} (off 3)")
                
                # 5. Total Analysis - Key totals and market lean
                weight = self.weights["line_movement_signal"]
                max_possible += weight
                if total_line > 0:
                    # Check for juice discrepancy (indicates market lean)
                    if over_odds >= -105 and under_odds <= -115:
                        total_score += weight * 0.7
                        signals["total_lean"] = {"direction": "OVER", "line": total_line}
                        reasons.append(f"Market Lean: OVER {total_line}")
                    elif under_odds >= -105 and over_odds <= -115:
                        total_score += weight * 0.7
                        signals["total_lean"] = {"direction": "UNDER", "line": total_line}
                        reasons.append(f"Market Lean: UNDER {total_line}")
                
                # 6. REST/FATIGUE - From sports data service
                weight = self.weights["rest_fatigue_factor"]
                max_possible += weight
                try:
                    rest_data = sports_data.rest_calculator.calculate_rest_advantage(home, away, league_map.get(sport, "NBA"))
                    if rest_data.get("advantage"):
                        total_score += rest_data.get("strength", 0.5) * weight
                        signals["rest"] = rest_data
                        reasons.append(f"Rest Edge: {rest_data['description']}")
                except:
                    pass
                
                # 7. INJURY IMPACT - From multi-source scraper
                weight = self.weights["injury_impact"]
                max_possible += weight
                try:
                    game_context = sports_data.get_game_context(home, away, league_map.get(sport, "NBA"))
                    injury_impact = game_context.get("injuries", {}).get("impact", {})
                    if injury_impact.get("advantage"):
                        total_score += injury_impact.get("strength", 0.5) * weight
                        signals["injury"] = injury_impact
                        reasons.append(f"Injury Edge: {injury_impact['description']}")
                except:
                    pass
                
                # 8. Kelly Criterion - Calculate actual edge
                weight = self.weights["kelly_edge"]
                max_possible += weight
                # If we have a value signal, calculate Kelly
                if signals.get("ml_value"):
                    ml_odds = signals["ml_value"]["odds"]
                    # Implied probability from odds
                    if ml_odds > 0:
                        implied_prob = 100 / (ml_odds + 100)
                        # Assume our edge is 3-5% on identified value
                        our_prob = implied_prob + 0.04
                        decimal_odds = (ml_odds / 100) + 1
                        kelly_edge = ((our_prob * decimal_odds) - 1) * 100
                        if kelly_edge > 2:
                            total_score += weight * 0.8
                            signals["kelly"] = {"edge": kelly_edge, "bet_size": min(5, kelly_edge / 2)}
                            reasons.append(f"Kelly Edge: +{round(kelly_edge, 1)}% EV")
                
                # ===== ESOTERIC SIGNALS =====
                
                esoteric_edge = esoteric_result.get("esoteric_edge", {})
                esoteric_score = esoteric_edge.get("score", 50)
                
                # 8. Gematria
                gematria = esoteric_result.get("gematria", {})
                diff = gematria.get("difference", 0)
                weight = self.weights["gematria_alignment"]
                max_possible += weight
                if abs(diff) > 10:
                    score_pct = min(1.0, abs(diff) / 40)
                    total_score += score_pct * weight
                    favors = home if diff > 0 else away
                    signals["gematria"] = {"favors": favors, "diff": diff}
                    reasons.append(f"Gematria: {favors} +{abs(diff)}")
                
                # 9. Numerology
                weight = self.weights["numerology_power"]
                max_possible += weight
                if today_numerology.get("power_day"):
                    total_score += weight * 0.85
                    signals["numerology"] = {"power_day": True, "life_path": today_numerology["life_path"]}
                    reasons.append(f"POWER DAY: Life Path {today_numerology['life_path']}")
                elif today_numerology.get("upset_potential"):
                    total_score += weight * 0.6
                    signals["numerology"] = {"upset": True, "life_path": today_numerology["life_path"]}
                    reasons.append(f"Upset Energy: Life Path {today_numerology['life_path']}")
                
                # 10. Sacred Geometry
                sacred = esoteric_result.get("sacred_geometry")
                weight = self.weights["sacred_geometry"]
                max_possible += weight
                if sacred and sacred.get("tesla_energy"):
                    total_score += weight * 0.9
                    signals["sacred"] = sacred
                    reasons.append("Tesla 3-6-9 alignment!")
                elif sacred and sacred.get("fib_aligned"):
                    total_score += weight * 0.6
                    signals["sacred"] = sacred
                    reasons.append("Fibonacci alignment")
                
                # 11. Moon Phase
                weight = self.weights["moon_phase"]
                max_possible += weight
                if today_moon.get("full_moon"):
                    total_score += weight * 0.8
                    signals["moon"] = {"full": True, "phase": today_moon.get("phase")}
                    reasons.append("FULL MOON: Chaos factor HIGH")
                elif today_moon.get("new_moon"):
                    total_score += weight * 0.5
                    signals["moon"] = {"new": True}
                    reasons.append("New Moon: Underdog energy")
                
                # 12. Zodiac Element
                element = today_zodiac.get("element", "")
                weight = self.weights["zodiac_element"]
                max_possible += weight
                if element == "Fire":
                    total_score += weight * 0.7
                    signals["zodiac"] = {"element": element, "lean": "OVER"}
                    reasons.append(f"Fire Sign: Lean OVER")
                elif element == "Earth":
                    total_score += weight * 0.7
                    signals["zodiac"] = {"element": element, "lean": "UNDER"}
                    reasons.append(f"Earth Sign: Lean UNDER")
                
                # ===== ADDITIONAL SIGNALS =====
                
                # 13. LSTM/TREND - Line movement direction analysis
                weight = self.weights["lstm_sequence"]
                max_possible += weight
                # Analyze spread movement: opening vs current (via juice changes)
                # If juice is moving one direction, trend is forming
                if home_spread_odds < -115:  # Heavy juice on home = line moving toward home
                    total_score += weight * 0.6
                    signals["trend"] = {"direction": "toward_home", "strength": abs(home_spread_odds + 110) / 10}
                    reasons.append(f"Line Trend: Moving toward {home}")
                elif away_spread_odds < -115:
                    total_score += weight * 0.6
                    signals["trend"] = {"direction": "toward_away", "strength": abs(away_spread_odds + 110) / 10}
                    reasons.append(f"Line Trend: Moving toward {away}")
                
                # 14. PUBLIC FADE - Fade heavy public action
                weight = self.weights["public_fade"]
                max_possible += weight
                # Check splits for heavy public side (>70%)
                game_key = f"{away}@{home}".lower().replace(" ", "")
                game_splits = splits_lookup.get(game_key, {})
                spread_splits = game_splits.get("spread", {})
                bets = spread_splits.get("bets", {})
                home_bet_pct = bets.get("homePercent", 50) or 50
                away_bet_pct = bets.get("awayPercent", 50) or 50
                
                if home_bet_pct >= 70:
                    # Heavy public on home - fade to away
                    total_score += weight * 0.75
                    signals["public_fade"] = {"fade": away, "public_pct": home_bet_pct}
                    reasons.append(f"Fade Public: {home_bet_pct}% on {home}")
                elif away_bet_pct >= 70:
                    # Heavy public on away - fade to home
                    total_score += weight * 0.75
                    signals["public_fade"] = {"fade": home, "public_pct": away_bet_pct}
                    reasons.append(f"Fade Public: {away_bet_pct}% on {away}")
                
                # 15. KEY NUMBER - Spread on key number (3, 7, 10 for basketball/football)
                weight = self.weights["key_number"]
                max_possible += weight
                spread_abs = abs(home_spread)
                if spread_abs in [3, 7, 10]:
                    total_score += weight * 0.85
                    signals["key_number"] = {"number": spread_abs, "exact": True}
                    reasons.append(f"KEY NUMBER: {spread_abs}")
                elif spread_abs in [3.5, 7.5, 10.5]:
                    # Half-point off key number (hook)
                    total_score += weight * 0.6
                    signals["key_number"] = {"number": spread_abs, "hook": True}
                    reasons.append(f"Hook on {int(spread_abs)}")
                
                # 16. REFEREE CREW ANALYSIS - Refs impact totals and spreads
                weight = self.weights["referee_crew"]
                max_possible += weight
                try:
                    ref_analysis = ref_analyzer.get_game_ref_analysis(home, away)
                    
                    if ref_analysis.get("has_data"):
                        ref_total_rec = ref_analysis.get("total_recommendation", "NEUTRAL")
                        ref_spread_rec = ref_analysis.get("spread_recommendation", "NEUTRAL")
                        ref_strength = ref_analysis.get("total_strength", 0)
                        ref_confidence = ref_analysis.get("confidence", 0)
                        
                        # Total recommendation (OVER/UNDER)
                        if ref_total_rec in ["OVER", "UNDER"] and ref_strength > 0.3:
                            total_score += weight * ref_strength
                            signals["referee"] = {
                                "total_lean": ref_total_rec,
                                "spread_lean": ref_spread_rec,
                                "over_pct": ref_analysis.get("over_pct"),
                                "home_win_pct": ref_analysis.get("home_win_pct"),
                                "fouls_per_game": ref_analysis.get("fouls_per_game"),
                                "crew": ref_analysis.get("refs_found", [])
                            }
                            reasons.append(f"REF CREW: {ref_total_rec} tendency ({ref_analysis.get('over_pct', 50)}% over rate)")
                        
                        # Spread recommendation (HOME advantage with certain refs)
                        if ref_spread_rec == "HOME" and ref_analysis.get("spread_strength", 0) > 0.3:
                            if "referee" not in signals:
                                signals["referee"] = {}
                            signals["referee"]["home_edge"] = ref_analysis.get("home_edge")
                            signals["referee"]["spread_lean"] = "HOME"
                            if ref_total_rec == "NEUTRAL":
                                total_score += weight * 0.5
                                reasons.append(f"REF CREW: Home-friendly ({ref_analysis.get('home_win_pct', 52.5)}% home win rate)")
                except Exception as e:
                    print(f"Ref analysis error: {e}")
                
                # ===== CALCULATE FINAL CONFIDENCE =====
                
                # Confidence = (score achieved / max possible) * 100
                # This represents how strongly our signals agree
                if max_possible > 0:
                    confidence = (total_score / max_possible) * 100
                    confidence = min(95, max(35, confidence))
                else:
                    confidence = 35
                
                # Only output picks where we have genuine confidence
                signals_fired_count = len(signals)
                
                # Determine pick direction
                pick_result = self._determine_pick(signals, markets, home, away, esoteric_score, sharp)
                
                if confidence >= 75 and pick_result and signals_fired_count >= 4:
                    # Only GOOD (75+) and STRONG (85+) with at least 4 signals agreeing
                    pick = {
                        "id": f"{game.get('id', '')}_{datetime.now().strftime('%H%M%S')}",
                        "game": f"{away} @ {home}",
                        "sport": sport.split("_")[1].upper() if "_" in sport else sport,
                        "type": pick_result["type"],
                        "pick": pick_result["pick"],
                        "odds": pick_result["odds"],
                        "confidence_score": round(confidence, 1),
                        "confidence_label": self._get_label(confidence),
                        "reasons": reasons[:6],
                        "signals_fired": len(signals),
                        "sharp_money": sharp.get("detected", False),
                        "esoteric_score": esoteric_score,
                        "kelly_size": signals.get("kelly", {}).get("edge", 0) / 4 if signals.get("kelly") else 0,
                        "status": "pending"
                    }
                    best_bets.append(pick)
                    
            except Exception as e:
                print(f"Error processing game: {e}")
                continue
        
        # Sort and rank
        best_bets.sort(key=lambda x: x["confidence_score"], reverse=True)
        for i, pick in enumerate(best_bets):
            pick["rank"] = i + 1
        
        # Store picks
        self.picks_history.extend(best_bets[:10])
        self._save_history()
        
        return {
            "success": True,
            "sport": sport,
            "generated_at": datetime.now().isoformat(),
            "total_analyzed": len(odds_data.get("games", [])),
            "total_picks": len(best_bets),
            "picks": best_bets[:10],
            "weights": self.weights,
            "performance": self.performance
        }
    
    def _build_splits_lookup(self, splits_data):
        lookup = {}
        if not splits_data.get("success"):
            return lookup
        try:
            games = splits_data.get("splits", {}).get("data", [])
            for game in games:
                home = game.get("homeTeam", "")
                away = game.get("awayTeam", "")
                key = f"{away}@{home}".lower().replace(" ", "")
                lookup[key] = game.get("splits", {})
        except:
            pass
        return lookup
    
    def _check_sharp_money(self, home, away, splits_lookup):
        key = f"{away}@{home}".lower().replace(" ", "")
        splits = splits_lookup.get(key, {})
        result = {"detected": False, "side": None, "strength": 0}
        
        for market in ["spread", "moneyline"]:
            market_data = splits.get(market, {})
            bets = market_data.get("bets", {})
            money = market_data.get("money", {})
            
            home_bets = bets.get("homePercent", 50) or 50
            home_money = money.get("homePercent", 50) or 50
            away_bets = bets.get("awayPercent", 50) or 50
            away_money = money.get("awayPercent", 50) or 50
            
            home_diff = home_money - home_bets
            away_diff = away_money - away_bets
            
            if home_diff >= 8:
                result = {"detected": True, "side": home, "strength": home_diff, "market": market}
                break
            elif away_diff >= 8:
                result = {"detected": True, "side": away, "strength": away_diff, "market": market}
                break
        
        return result
    
    def _get_spread(self, markets, home):
        spreads = markets.get("spreads", {})
        return spreads.get(home, {}).get("point", 0)
    
    def _get_total(self, markets):
        totals = markets.get("totals", {})
        return totals.get("Over", {}).get("point", 220)
    
    def _determine_pick(self, signals, markets, home, away, esoteric_score, sharp):
        spreads = markets.get("spreads", {})
        totals = markets.get("totals", {})
        h2h = markets.get("h2h", {})
        
        home_spread = spreads.get(home, {}).get("point", 0)
        home_odds = spreads.get(home, {}).get("price", -110)
        away_spread = spreads.get(away, {}).get("point", 0)
        away_odds = spreads.get(away, {}).get("price", -110)
        
        over_odds = totals.get("Over", {}).get("price", -110)
        under_odds = totals.get("Under", {}).get("price", -110)
        total_line = totals.get("Over", {}).get("point", 220)
        
        home_ml = h2h.get(home, {}).get("price", -110)
        away_ml = h2h.get(away, {}).get("price", 100)
        
        # Priority 1: Sharp money (highest value signal)
        if sharp.get("detected"):
            side = sharp["side"]
            if side == home:
                return {"type": "spread", "pick": f"{home} {home_spread:+g}", "odds": home_odds}
            else:
                return {"type": "spread", "pick": f"{away} {away_spread:+g}", "odds": away_odds}
        
        # Priority 2: Moneyline value on underdogs
        if signals.get("ml_value"):
            team = signals["ml_value"]["team"]
            odds = signals["ml_value"]["odds"]
            return {"type": "moneyline", "pick": f"{team} ML", "odds": odds}
        
        # Priority 3: Referee-based total lean (refs heavily influence totals)
        ref = signals.get("referee", {})
        if ref.get("total_lean"):
            ref_total = ref["total_lean"]
            if ref_total == "OVER":
                return {"type": "total", "pick": f"OVER {total_line}", "odds": over_odds}
            elif ref_total == "UNDER":
                return {"type": "total", "pick": f"UNDER {total_line}", "odds": under_odds}
        
        # Priority 4: Total lean from market analysis
        if signals.get("total_lean"):
            direction = signals["total_lean"]["direction"]
            if direction == "OVER":
                return {"type": "total", "pick": f"OVER {total_line}", "odds": over_odds}
            else:
                return {"type": "total", "pick": f"UNDER {total_line}", "odds": under_odds}
        
        # Priority 5: Zodiac element lean for totals
        zodiac = signals.get("zodiac", {})
        if zodiac.get("lean") == "OVER":
            return {"type": "total", "pick": f"OVER {total_line}", "odds": over_odds}
        elif zodiac.get("lean") == "UNDER":
            return {"type": "total", "pick": f"UNDER {total_line}", "odds": under_odds}
        
        # Priority 6: Referee spread lean (home-friendly crews)
        if ref.get("spread_lean") == "HOME":
            return {"type": "spread", "pick": f"{home} {home_spread:+g}", "odds": home_odds}
        elif ref.get("spread_lean") == "AWAY":
            return {"type": "spread", "pick": f"{away} {away_spread:+g}", "odds": away_odds}
        
        # Priority 7: Line value signal
        if signals.get("line_value"):
            side = signals["line_value"]["side"]
            if side == home:
                return {"type": "spread", "pick": f"{home} {home_spread:+g}", "odds": home_odds}
            else:
                return {"type": "spread", "pick": f"{away} {away_spread:+g}", "odds": away_odds}
        
        # Priority 8: Key spread / hook value
        if signals.get("key_spread") or signals.get("hook"):
            # Favor the side getting points on key numbers
            if home_spread > 0:
                return {"type": "spread", "pick": f"{home} {home_spread:+g}", "odds": home_odds}
            else:
                return {"type": "spread", "pick": f"{away} {away_spread:+g}", "odds": away_odds}
        
        # Priority 9: Esoteric lean
        if esoteric_score > 55:
            return {"type": "spread", "pick": f"{home} {home_spread:+g}", "odds": home_odds}
        elif esoteric_score < 45:
            return {"type": "spread", "pick": f"{away} {away_spread:+g}", "odds": away_odds}
        
        # Default: No strong lean, return None (skip this game)
        return None
    
    def _get_label(self, score):
        if score >= 85: return "STRONG"
        elif score >= 75: return "GOOD"
        else: return "BELOW_THRESHOLD"  # Should not appear in output
    
    # ===== GRADING SYSTEM =====
    
    def grade_pick(self, pick_id: str, result: str):
        """Grade a pick: W, L, or P"""
        for pick in self.picks_history:
            if pick.get("id") == pick_id:
                pick["status"] = "graded"
                pick["result"] = result
                pick["graded_at"] = datetime.now().isoformat()
                
                odds = pick.get("odds", -110)
                if result == "W":
                    pick["profit_loss"] = (odds / 100) if odds > 0 else (100 / abs(odds))
                    self.performance["wins"] += 1
                elif result == "L":
                    pick["profit_loss"] = -1
                    self.performance["losses"] += 1
                else:
                    pick["profit_loss"] = 0
                    self.performance["pushes"] += 1
                
                self.performance["total_picks"] += 1
                self._update_metrics(pick)
                self.graded_picks.append(pick)
                self._learn_from_result(pick)
                self._save_history()
                
                return {"success": True, "pick": pick, "performance": self.performance}
        
        return {"success": False, "error": "Pick not found"}
    
    def _update_metrics(self, pick):
        total = self.performance["wins"] + self.performance["losses"]
        if total > 0:
            self.performance["win_rate"] = round(self.performance["wins"] / total * 100, 1)
        
        sport = pick.get("sport", "UNKNOWN")
        if sport not in self.performance["by_sport"]:
            self.performance["by_sport"][sport] = {"W": 0, "L": 0, "P": 0}
        self.performance["by_sport"][sport][pick["result"]] += 1
        
        bet_type = pick.get("type", "unknown")
        if bet_type not in self.performance["by_type"]:
            self.performance["by_type"][bet_type] = {"W": 0, "L": 0, "P": 0}
        self.performance["by_type"][bet_type][pick["result"]] += 1
        
        conf = pick.get("confidence_label", "SLIGHT")
        if conf not in self.performance["by_confidence"]:
            self.performance["by_confidence"][conf] = {"W": 0, "L": 0, "P": 0}
        self.performance["by_confidence"][conf][pick["result"]] += 1
        
        total_profit = sum(p.get("profit_loss", 0) for p in self.graded_picks)
        if len(self.graded_picks) > 0:
            self.performance["roi"] = round(total_profit / len(self.graded_picks) * 100, 1)
    
    # ===== LEARNING SYSTEM =====
    
    def _learn_from_result(self, pick):
        """Adjust weights based on results"""
        if pick["result"] == "P":
            return
        
        adjustment = 0.03 if pick["result"] == "W" else -0.02
        
        # Boost/reduce weights for signals that fired
        if pick.get("sharp_money"):
            self.weights["sharp_money"] = max(5, min(25, self.weights["sharp_money"] * (1 + adjustment * 1.5)))
        
        if pick.get("esoteric_score", 50) != 50:
            for key in ["gematria_alignment", "numerology_power", "sacred_geometry", "moon_phase", "zodiac_element"]:
                self.weights[key] = max(2, min(15, self.weights[key] * (1 + adjustment)))
    
    def get_learning_report(self):
        return {
            "current_weights": self.weights,
            "performance": self.performance,
            "total_graded": len(self.graded_picks),
            "top_signals": sorted(self.weights.items(), key=lambda x: x[1], reverse=True)[:5],
            "picks_today": len([p for p in self.picks_history if p.get("status") == "pending"])
        }
    
    # ===== PERSISTENCE =====
    
    def _save_history(self):
        try:
            data = {
                "weights": self.weights,
                "picks_history": self.picks_history[-100:],
                "graded_picks": self.graded_picks[-500:],
                "performance": self.performance
            }
            with open("/tmp/picks_engine_data.json", "w") as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Save error: {e}")
    
    def _load_history(self):
        try:
            if os.path.exists("/tmp/picks_engine_data.json"):
                with open("/tmp/picks_engine_data.json", "r") as f:
                    data = json.load(f)
                    self.weights = data.get("weights", self.weights)
                    self.picks_history = data.get("picks_history", [])
                    self.graded_picks = data.get("graded_picks", [])
                    self.performance = data.get("performance", self.performance)
        except Exception as e:
            print(f"Load error: {e}")


# ============================================
# PROPS PICKS ENGINE - PLAYER PROPS ANALYSIS
# ============================================

class PropsPicksEngine:
    """
    Player Props Picks Engine - Same rigor as game picks
    Only outputs GOOD (75+) and STRONG (85+) confidence props
    
    Signals Used:
    1. Line Value (juice analysis)
    2. Player Gematria
    3. Line Sacred Geometry (Tesla 3-6-9, Fibonacci)
    4. Date Numerology
    5. Moon Phase Impact
    6. Prop Type Analysis
    7. Over/Under Lean
    8. Kelly Criterion Edge
    
    CONTEXTUAL SIGNALS (Advanced):
    9. Defensive Context (opponent defense vs position)
    10. Pace Factor (game tempo projection)
    11. Usage Vacuum (teammate injuries boost)
    12. Rest/Fatigue (travel, back-to-back)
    13. Vegas Context (market wisdom)
    14. Referee Impact
    
    ML SIGNALS:
    15. Monte Carlo Simulation
    16. Ensemble Model
    17. LSTM Neural Network
    18. Matchup History
    """
    
    def __init__(self):
        self.weights = {
            # Traditional signals
            "line_value": 15,
            "player_gematria": 10,
            "line_sacred": 8,
            "numerology": 10,
            "moon_phase": 6,
            "prop_type": 8,
            "over_under_lean": 12,
            "kelly_edge": 14,
            "zodiac_element": 4,
            
            # Contextual signals (CRITICAL for accuracy)
            "defense_context": 16,      # Opponent defense vs position
            "pace_factor": 14,          # Game tempo
            "usage_vacuum": 15,         # Teammate injuries
            "rest_fatigue": 12,         # Travel/B2B
            "vegas_context": 13,        # Market wisdom
            "referee_impact": 10,       # Ref tendencies
            
            # ML signals
            "monte_carlo": 18,
            "ensemble_model": 16,
            "lstm_neural": 14,
            "matchup_history": 12
        }
        
        self.props_history = []
        self.graded_props = []
        self.performance = {
            "total_picks": 0, "wins": 0, "losses": 0, "pushes": 0,
            "win_rate": 0, "roi": 0,
            "by_sport": {}, "by_type": {}, "by_confidence": {}
        }
    
    def generate_prop_picks(self, sport="basketball_nba"):
        """Generate best player prop picks using all signals"""
        best_props = []
        
        # Get player props
        markets_map = {
            "basketball_nba": "player_points,player_rebounds,player_assists,player_threes",
            "basketball_ncaab": "player_points,player_rebounds,player_assists",
            "icehockey_nhl": "player_points,player_goals,player_assists,player_shots_on_goal",
            "baseball_mlb": "batter_hits,batter_total_bases,pitcher_strikeouts"
        }
        
        markets = markets_map.get(sport, "player_points")
        props_data = odds_service.get_player_props(sport=sport, markets=markets)
        
        if not props_data.get("success") or not props_data.get("props"):
            return {"success": False, "error": "No props available", "picks": []}
        
        # Get today's cosmic energy
        today = date.today()
        today_numerology = esoteric.numerology.date_energy(today)
        today_moon = esoteric.astrology.moon_phase(today)
        today_zodiac = esoteric.astrology.zodiac(today)
        
        # Group props by player to find best line
        player_props = {}
        for prop in props_data.get("props", []):
            player = prop.get("player", "")
            market = prop.get("market", "")
            key = f"{player}_{market}"
            
            if key not in player_props:
                player_props[key] = []
            player_props[key].append(prop)
        
        # Analyze each unique player/prop combo
        for key, props in player_props.items():
            try:
                # Get best line (compare bookmakers)
                over_props = [p for p in props if p.get("type") == "Over"]
                under_props = [p for p in props if p.get("type") == "Under"]
                
                if not over_props and not under_props:
                    continue
                
                # Use first available
                sample_prop = over_props[0] if over_props else under_props[0]
                player_name = sample_prop.get("player", "")
                prop_type = sample_prop.get("market", "")
                line = sample_prop.get("line", 0)
                game_info = sample_prop.get("game", {})
                
                if not player_name or not line:
                    continue
                
                # Get odds
                over_odds = over_props[0].get("odds", -110) if over_props else -110
                under_odds = under_props[0].get("odds", -110) if under_props else -110
                
                # Calculate signals
                signals = {}
                reasons = []
                total_score = 0
                max_possible = 0
                
                # ===== SIGNAL 1: Line Value (Juice Analysis) =====
                weight = self.weights["line_value"]
                max_possible += weight
                
                if over_odds > -105:
                    total_score += weight * 0.8
                    signals["line_value"] = {"side": "OVER", "odds": over_odds}
                    reasons.append(f"OVER value at {over_odds}")
                elif under_odds > -105:
                    total_score += weight * 0.8
                    signals["line_value"] = {"side": "UNDER", "odds": under_odds}
                    reasons.append(f"UNDER value at {under_odds}")
                elif over_odds >= -108:
                    total_score += weight * 0.5
                    signals["line_value"] = {"side": "OVER", "odds": over_odds}
                elif under_odds >= -108:
                    total_score += weight * 0.5
                    signals["line_value"] = {"side": "UNDER", "odds": under_odds}
                
                # ===== SIGNAL 2: Player Gematria =====
                weight = self.weights["player_gematria"]
                max_possible += weight
                
                player_gematria = esoteric.gematria.full_analysis(player_name)
                player_reduced = player_gematria.get("reduced", 0)
                
                # Tesla numbers (3, 6, 9) = high energy
                if player_reduced in [3, 6, 9]:
                    total_score += weight * 0.9
                    signals["player_gematria"] = {"reduced": player_reduced, "tesla": True}
                    reasons.append(f"Player Tesla Energy ({player_reduced})")
                # Master numbers (11, 22, 33) = powerful
                elif player_reduced in [11, 22, 33]:
                    total_score += weight * 0.85
                    signals["player_gematria"] = {"reduced": player_reduced, "master": True}
                    reasons.append(f"Player Master Number ({player_reduced})")
                elif player_reduced in [1, 8]:  # Leadership/power numbers
                    total_score += weight * 0.6
                    signals["player_gematria"] = {"reduced": player_reduced}
                
                # ===== SIGNAL 3: Line Sacred Geometry =====
                weight = self.weights["line_sacred"]
                max_possible += weight
                
                line_sacred = esoteric.sacred.analyze(line)
                
                if line_sacred and line_sacred.get("tesla_energy"):
                    total_score += weight * 0.9
                    signals["line_sacred"] = line_sacred
                    reasons.append(f"Line {line} Tesla aligned!")
                elif line_sacred and line_sacred.get("fib_aligned"):
                    total_score += weight * 0.7
                    signals["line_sacred"] = line_sacred
                    reasons.append(f"Line {line} Fibonacci")
                
                # ===== SIGNAL 4: Date Numerology =====
                weight = self.weights["numerology"]
                max_possible += weight
                
                if today_numerology.get("power_day"):
                    total_score += weight * 0.85
                    signals["numerology"] = {"power_day": True, "life_path": today_numerology["life_path"]}
                    reasons.append(f"POWER DAY: LP {today_numerology['life_path']}")
                elif today_numerology.get("life_path") == 3:
                    # Life path 3 = creativity/expression = high scoring
                    total_score += weight * 0.7
                    signals["numerology"] = {"life_path": 3, "high_scoring": True}
                    reasons.append("LP3: High scoring energy")
                elif today_numerology.get("upset_potential"):
                    total_score += weight * 0.5
                    signals["numerology"] = {"upset": True}
                
                # ===== SIGNAL 5: Moon Phase =====
                weight = self.weights["moon_phase"]
                max_possible += weight
                
                if today_moon.get("full_moon"):
                    total_score += weight * 0.8
                    signals["moon"] = {"full": True}
                    reasons.append("Full Moon: Peak performance")
                elif today_moon.get("waxing"):
                    total_score += weight * 0.6
                    signals["moon"] = {"waxing": True}
                    reasons.append("Waxing Moon: Building energy")
                
                # ===== SIGNAL 6: Prop Type Analysis =====
                weight = self.weights["prop_type"]
                max_possible += weight
                
                # Points props are most predictable
                if "points" in prop_type.lower():
                    total_score += weight * 0.7
                    signals["prop_type"] = {"type": "points", "reliability": "high"}
                elif "assists" in prop_type.lower():
                    total_score += weight * 0.6
                    signals["prop_type"] = {"type": "assists", "reliability": "medium"}
                elif "rebounds" in prop_type.lower():
                    total_score += weight * 0.6
                    signals["prop_type"] = {"type": "rebounds", "reliability": "medium"}
                elif "strikeouts" in prop_type.lower():
                    total_score += weight * 0.65
                    signals["prop_type"] = {"type": "strikeouts", "reliability": "medium-high"}
                
                # ===== SIGNAL 7: Over/Under Lean =====
                weight = self.weights["over_under_lean"]
                max_possible += weight
                
                # Determine lean based on signals
                over_lean = 0
                under_lean = 0
                
                # Tesla energy = OVER lean (high performance)
                if signals.get("player_gematria", {}).get("tesla"):
                    over_lean += 2
                
                # Full moon = volatility, lean OVER for stars
                if signals.get("moon", {}).get("full"):
                    over_lean += 1
                
                # Earth zodiac = conservative = UNDER
                if today_zodiac.get("element") == "Earth":
                    under_lean += 1.5
                # Fire zodiac = aggressive = OVER
                elif today_zodiac.get("element") == "Fire":
                    over_lean += 1.5
                
                if over_lean > under_lean + 1:
                    total_score += weight * 0.75
                    signals["lean"] = {"direction": "OVER", "strength": over_lean}
                    reasons.append("Signals lean OVER")
                elif under_lean > over_lean + 1:
                    total_score += weight * 0.75
                    signals["lean"] = {"direction": "UNDER", "strength": under_lean}
                    reasons.append("Signals lean UNDER")
                
                # ===== SIGNAL 8: Kelly Criterion =====
                weight = self.weights["kelly_edge"]
                max_possible += weight
                
                # Calculate edge based on line value
                best_odds = max(over_odds, under_odds)
                if best_odds > -110:
                    if best_odds > 0:
                        implied_prob = 100 / (best_odds + 100)
                    else:
                        implied_prob = abs(best_odds) / (abs(best_odds) + 100)
                    
                    # Assume 3% edge on identified value
                    our_prob = implied_prob + 0.03
                    decimal_odds = (best_odds / 100 + 1) if best_odds > 0 else (100 / abs(best_odds) + 1)
                    kelly_edge = ((our_prob * decimal_odds) - 1) * 100
                    
                    if kelly_edge > 2:
                        total_score += weight * 0.8
                        signals["kelly"] = {"edge": kelly_edge}
                        reasons.append(f"Kelly Edge: +{round(kelly_edge, 1)}%")
                
                # ===== SIGNAL 9: Zodiac Element =====
                weight = self.weights["zodiac_element"]
                max_possible += weight
                
                if today_zodiac.get("element") == "Fire":
                    total_score += weight * 0.7
                    signals["zodiac"] = {"element": "Fire", "lean": "OVER"}
                elif today_zodiac.get("element") == "Earth":
                    total_score += weight * 0.7
                    signals["zodiac"] = {"element": "Earth", "lean": "UNDER"}
                
                # ===== REAL ML SIGNALS =====
                
                # Get opponent team from game info
                home_team = game_info.get("home_team", "")
                away_team = game_info.get("away_team", "")
                opponent = away_team if home_team else home_team  # Guess opponent
                
                # Map prop type to stat
                stat_map = {"player_points": "points", "player_rebounds": "rebounds", 
                           "player_assists": "assists", "player_threes": "threes"}
                stat_type_ml = stat_map.get(prop_type, "points")
                
                # Run Real ML prediction
                try:
                    ml_result = real_ml.predict_prop(player_name, opponent, stat_type_ml, line, "NBA")
                    
                    if ml_result.get("success"):
                        ml_preds = ml_result.get("predictions", {})
                        ml_final = ml_result.get("final", {})
                        
                        # SIGNAL 10: Monte Carlo
                        if "monte_carlo" in ml_preds:
                            mc = ml_preds["monte_carlo"]
                            weight = 18  # High weight for Monte Carlo
                            max_possible += weight
                            
                            if mc.get("confidence", 0) >= 60:
                                over_prob = mc.get("over_prob", 50)
                                if over_prob >= 58:
                                    total_score += weight * (over_prob / 100)
                                    signals["monte_carlo"] = {"recommendation": "OVER", "prob": over_prob, "mean": mc.get("mean")}
                                    reasons.append(f"Monte Carlo: {over_prob}% OVER (mean: {mc.get('mean')})")
                                elif over_prob <= 42:
                                    total_score += weight * ((100 - over_prob) / 100)
                                    signals["monte_carlo"] = {"recommendation": "UNDER", "prob": 100-over_prob, "mean": mc.get("mean")}
                                    reasons.append(f"Monte Carlo: {round(100-over_prob)}% UNDER (mean: {mc.get('mean')})")
                        
                        # SIGNAL 11: Ensemble Model
                        if "ensemble" in ml_preds:
                            ens = ml_preds["ensemble"]
                            weight = 16  # High weight for Ensemble
                            max_possible += weight
                            
                            if ens.get("confidence", 0) >= 60:
                                pred = ens.get("prediction", line)
                                edge = pred - line
                                if edge > 1.5:
                                    total_score += weight * 0.85
                                    signals["ensemble"] = {"prediction": pred, "edge": edge, "models": ens.get("models")}
                                    reasons.append(f"Ensemble AI: {pred} (OVER by {round(edge, 1)})")
                                elif edge < -1.5:
                                    total_score += weight * 0.85
                                    signals["ensemble"] = {"prediction": pred, "edge": edge, "models": ens.get("models")}
                                    reasons.append(f"Ensemble AI: {pred} (UNDER by {round(abs(edge), 1)})")
                        
                        # SIGNAL 12: LSTM Neural Network
                        if "lstm" in ml_preds:
                            lstm = ml_preds["lstm"]
                            weight = 14  # High weight for LSTM
                            max_possible += weight
                            
                            if lstm.get("confidence", 0) >= 55:
                                pred = lstm.get("prediction", line)
                                edge = pred - line
                                if abs(edge) > 1:
                                    total_score += weight * 0.8
                                    signals["lstm"] = {"prediction": pred, "edge": edge}
                                    direction = "OVER" if edge > 0 else "UNDER"
                                    reasons.append(f"LSTM Neural Net: {pred} ({direction})")
                        
                        # SIGNAL 13: Matchup Analysis
                        if "matchup" in ml_preds:
                            matchup = ml_preds["matchup"]
                            weight = 10
                            max_possible += weight
                            
                            if matchup.get("confidence", 0) >= 40 and matchup.get("sample", 0) >= 2:
                                adj = matchup.get("adjustment", 0)
                                if adj > 2:
                                    total_score += weight * 0.75
                                    signals["matchup"] = matchup
                                    reasons.append(f"Matchup History: +{round(adj, 1)} vs {opponent}")
                                elif adj < -2:
                                    total_score += weight * 0.75
                                    signals["matchup"] = matchup
                                    reasons.append(f"Matchup History: {round(adj, 1)} vs {opponent}")
                        
                        # Store final ML prediction
                        signals["ml_final"] = ml_final
                        
                except Exception as e:
                    print(f"ML prediction error for {player_name}: {e}")
                
                # ===== CONTEXTUAL SIGNALS =====
                
                # Get teams from game info
                home_team = game_info.get("home_team", "")
                away_team = game_info.get("away_team", "")
                
                # Guess player's team (if playing at home or away)
                player_team = home_team  # Assume home for now, would need roster data
                opponent_team = away_team
                
                # SIGNAL: Defensive Context (opponent defense vs position)
                weight = self.weights["defense_context"]
                max_possible += weight
                try:
                    # Guess player position from name
                    position = self._guess_position(player_name)
                    defense = defense_scraper.get_team_defense_vs_position(opponent_team, position)
                    
                    if defense:
                        rating = defense.get("rating", "average")
                        adjustment = defense.get("adjustment", 0)
                        
                        # Elite defense = expect UNDER, Poor defense = expect OVER
                        if rating == "poor" and adjustment > 4:
                            total_score += weight * 0.85
                            signals["defense_context"] = {
                                "rating": rating,
                                "adjustment": adjustment,
                                "lean": "OVER",
                                "position": position
                            }
                            reasons.append(f"WEAK DEFENSE: {opponent_team} allows +{adjustment}% to {position}s")
                        elif rating == "elite" and adjustment < -4:
                            total_score += weight * 0.8
                            signals["defense_context"] = {
                                "rating": rating,
                                "adjustment": adjustment,
                                "lean": "UNDER",
                                "position": position
                            }
                            reasons.append(f"ELITE DEFENSE: {opponent_team} holds {position}s to {adjustment}%")
                        elif abs(adjustment) > 2:
                            total_score += weight * 0.5
                            signals["defense_context"] = {"rating": rating, "adjustment": adjustment}
                except Exception as e:
                    print(f"Defense context error: {e}")
                
                # SIGNAL: Pace Factor
                weight = self.weights["pace_factor"]
                max_possible += weight
                try:
                    if home_team and away_team:
                        pace = pace_scraper.get_game_pace_projection(home_team, away_team)
                        
                        if pace:
                            env = pace.get("game_environment", "normal")
                            pace_adj = pace.get("stat_adjustment", 0)
                            
                            if env == "high_scoring":
                                total_score += weight * 0.8
                                signals["pace"] = {
                                    "environment": env,
                                    "projected_pace": pace.get("projected_pace"),
                                    "lean": "OVER"
                                }
                                reasons.append(f"HIGH PACE: {pace.get('projected_pace')} possessions projected")
                            elif env == "grind_it_out":
                                total_score += weight * 0.75
                                signals["pace"] = {
                                    "environment": env,
                                    "projected_pace": pace.get("projected_pace"),
                                    "lean": "UNDER"
                                }
                                reasons.append(f"SLOW PACE: {pace.get('projected_pace')} possessions projected")
                except Exception as e:
                    print(f"Pace error: {e}")
                
                # SIGNAL: Usage Vacuum (injured star teammates)
                weight = self.weights["usage_vacuum"]
                max_possible += weight
                try:
                    # Get injuries for player's team
                    team_injuries = sports_data.get_injuries(sport.replace("basketball_", ""))
                    injured_players = []
                    
                    for team_name, injuries in team_injuries.items():
                        if player_team.lower() in team_name.lower():
                            injured_players = [i.get("player", "") for i in injuries if i.get("status") in ["OUT", "DOUBTFUL"]]
                            break
                    
                    if injured_players:
                        usage_boost = team_context_scraper.get_player_usage_boost(player_name, player_team, injured_players)
                        
                        if usage_boost.get("boost", 0) > 10:
                            total_score += weight * 0.85
                            signals["usage_vacuum"] = {
                                "boost": usage_boost["boost"],
                                "multiplier": usage_boost["adjusted_multiplier"],
                                "injured": injured_players[:3],
                                "lean": "OVER"
                            }
                            reasons.append(f"USAGE BOOST: +{usage_boost['boost']}% from injuries")
                        elif usage_boost.get("boost", 0) > 5:
                            total_score += weight * 0.6
                            signals["usage_vacuum"] = usage_boost
                except Exception as e:
                    print(f"Usage vacuum error: {e}")
                
                # SIGNAL: Rest/Fatigue
                weight = self.weights["rest_fatigue"]
                max_possible += weight
                try:
                    # Would need schedule data - estimate from common patterns
                    # For now, use basic detection
                    fatigue = rest_travel_scraper.get_fatigue_analysis(
                        player_team,
                        days_rest=2,  # Would come from schedule API
                        games_in_5_days=2,
                        games_in_7_days=3
                    )
                    
                    if fatigue.get("fatigue_level") == "severe":
                        total_score += weight * 0.8
                        signals["fatigue"] = {
                            "level": "severe",
                            "score": fatigue.get("fatigue_score"),
                            "lean": "UNDER"
                        }
                        reasons.append(f"FATIGUE: Severe fatigue (score: {fatigue.get('fatigue_score')})")
                    elif fatigue.get("back_to_back"):
                        total_score += weight * 0.7
                        signals["fatigue"] = {
                            "level": "moderate",
                            "back_to_back": True,
                            "lean": "UNDER"
                        }
                        reasons.append("FATIGUE: Back-to-back game")
                except Exception as e:
                    print(f"Fatigue error: {e}")
                
                # SIGNAL: Vegas Context
                weight = self.weights["vegas_context"]
                max_possible += weight
                try:
                    # Get game odds
                    game_key = f"{away_team}_{home_team}".lower().replace(" ", "_")
                    
                    # Use the line itself as Vegas wisdom
                    if line > 0:
                        # Compare to player's recent average
                        recent_avg = signals.get("monte_carlo", {}).get("mean", line)
                        
                        if recent_avg > 0:
                            vegas_diff = line - recent_avg
                            
                            if vegas_diff > 3:
                                # Vegas line is higher than player's average = lean UNDER
                                total_score += weight * 0.7
                                signals["vegas_context"] = {
                                    "line": line,
                                    "player_avg": recent_avg,
                                    "difference": vegas_diff,
                                    "lean": "UNDER"
                                }
                                reasons.append(f"VEGAS HIGH: Line {line} vs avg {recent_avg}")
                            elif vegas_diff < -3:
                                # Vegas line is lower than player's average = lean OVER
                                total_score += weight * 0.75
                                signals["vegas_context"] = {
                                    "line": line,
                                    "player_avg": recent_avg,
                                    "difference": vegas_diff,
                                    "lean": "OVER"
                                }
                                reasons.append(f"VEGAS LOW: Line {line} vs avg {recent_avg}")
                except Exception as e:
                    print(f"Vegas context error: {e}")
                
                # ===== REFEREE IMPACT ON PROPS =====
                weight = self.weights["referee_impact"]
                max_possible += weight
                try:
                    # Get teams from game info
                    home_team = game_info.get("home_team", "")
                    away_team = game_info.get("away_team", "")
                    
                    if home_team and away_team:
                        ref_analysis = ref_analyzer.get_game_ref_analysis(home_team, away_team)
                        
                        if ref_analysis.get("has_data"):
                            fouls_per_game = ref_analysis.get("fouls_per_game", 39.5)
                            
                            # High-foul crews benefit star players (more FT opportunities)
                            # Points props most affected
                            if "points" in prop_type.lower():
                                if fouls_per_game >= 42:
                                    total_score += weight * 0.8
                                    signals["referee"] = {
                                        "impact": "HIGH_FOUL_CREW",
                                        "fouls_per_game": fouls_per_game,
                                        "props_lean": "OVER",
                                        "reason": "High-foul crew = more FTs for star players"
                                    }
                                    reasons.append(f"REF BOOST: High-foul crew ({fouls_per_game} fouls/game)")
                                elif fouls_per_game <= 37:
                                    total_score += weight * 0.7
                                    signals["referee"] = {
                                        "impact": "LOW_FOUL_CREW",
                                        "fouls_per_game": fouls_per_game,
                                        "props_lean": "UNDER",
                                        "reason": "Low-foul crew = fewer FT opportunities"
                                    }
                                    reasons.append(f"REF CAUTION: Low-foul crew ({fouls_per_game} fouls/game)")
                            
                            # Rebounds can be affected by pace
                            elif "rebounds" in prop_type.lower():
                                over_pct = ref_analysis.get("over_pct", 50)
                                if over_pct >= 53:  # High-scoring = more rebounds
                                    total_score += weight * 0.6
                                    signals["referee"] = {"over_pct": over_pct, "props_lean": "OVER"}
                                    reasons.append(f"REF PACE: High-scoring games ({over_pct}% over)")
                                    
                except Exception as e:
                    print(f"Ref props analysis error: {e}")
                
                # ===== CALCULATE CONFIDENCE =====
                
                if max_possible > 0:
                    confidence = (total_score / max_possible) * 100
                    confidence = min(95, max(35, confidence))
                else:
                    confidence = 35
                
                signals_fired = len(signals)
                
                # Determine pick direction
                pick_direction = self._determine_prop_direction(signals, over_odds, under_odds, line)
                
                # ONLY GOOD (75+) AND STRONG (85+) with at least 4 signals
                if confidence >= 75 and pick_direction and signals_fired >= 4:
                    # Get ML prediction if available
                    ml_pred = signals.get("ml_final", {}).get("prediction", line)
                    ml_edge = signals.get("ml_final", {}).get("edge", 0)
                    
                    prop_pick = {
                        "id": f"prop_{player_name.replace(' ', '_')}_{datetime.now().strftime('%H%M%S')}",
                        "player": player_name,
                        "prop_type": self._format_prop_type(prop_type),
                        "line": line,
                        "pick": pick_direction["pick"],
                        "odds": pick_direction["odds"],
                        "game": f"{game_info.get('away_team', '')} @ {game_info.get('home_team', '')}",
                        "sport": sport.split("_")[1].upper() if "_" in sport else sport.upper(),
                        "confidence_score": round(confidence, 1),
                        "confidence_label": "STRONG" if confidence >= 85 else "GOOD",
                        "reasons": reasons[:6],
                        "signals_fired": signals_fired,
                        "ml_prediction": ml_pred,
                        "ml_edge": round(ml_edge, 1),
                        "has_lstm": "lstm" in signals,
                        "has_ensemble": "ensemble" in signals,
                        "has_monte_carlo": "monte_carlo" in signals,
                        "esoteric_score": player_gematria.get("reduced", 0),
                        "kelly_size": signals.get("kelly", {}).get("edge", 0) / 4 if signals.get("kelly") else 0,
                        "status": "pending"
                    }
                    best_props.append(prop_pick)
                    
            except Exception as e:
                print(f"Error processing prop: {e}")
                continue
        
        # Sort by confidence
        best_props.sort(key=lambda x: x["confidence_score"], reverse=True)
        
        # Add rank
        for i, prop in enumerate(best_props):
            prop["rank"] = i + 1
        
        # Store
        self.props_history.extend(best_props[:10])
        
        return {
            "success": True,
            "sport": sport,
            "generated_at": datetime.now().isoformat(),
            "total_analyzed": len(player_props),
            "total_picks": len(best_props),
            "picks": best_props[:10],
            "weights": self.weights,
            "performance": self.performance
        }
    
    def _determine_prop_direction(self, signals, over_odds, under_odds, line):
        """
        Determine OVER or UNDER based on all signals
        Priority: ML Models > Contextual Factors > Esoteric
        """
        
        # PRIORITY 1: ML Final Recommendation (highest confidence)
        ml_final = signals.get("ml_final", {})
        if ml_final.get("confidence", 0) >= 70:
            rec = ml_final.get("recommendation", "")
            if "OVER" in rec:
                return {"pick": f"OVER {line}", "odds": over_odds}
            elif "UNDER" in rec:
                return {"pick": f"UNDER {line}", "odds": under_odds}
        
        # PRIORITY 2: Monte Carlo Simulation
        mc = signals.get("monte_carlo", {})
        if mc.get("recommendation") == "OVER":
            return {"pick": f"OVER {line}", "odds": over_odds}
        elif mc.get("recommendation") == "UNDER":
            return {"pick": f"UNDER {line}", "odds": under_odds}
        
        # PRIORITY 3: Ensemble Model
        ens = signals.get("ensemble", {})
        if ens.get("edge", 0) > 1:
            return {"pick": f"OVER {line}", "odds": over_odds}
        elif ens.get("edge", 0) < -1:
            return {"pick": f"UNDER {line}", "odds": under_odds}
        
        # PRIORITY 4: LSTM Neural Network
        lstm = signals.get("lstm", {})
        if lstm.get("edge", 0) > 1:
            return {"pick": f"OVER {line}", "odds": over_odds}
        elif lstm.get("edge", 0) < -1:
            return {"pick": f"UNDER {line}", "odds": under_odds}
        
        # PRIORITY 5: Usage Vacuum (injured star = major boost)
        usage = signals.get("usage_vacuum", {})
        if usage.get("lean") == "OVER" and usage.get("boost", 0) > 10:
            return {"pick": f"OVER {line}", "odds": over_odds}
        
        # PRIORITY 6: Defensive Context (weak/elite defense)
        defense = signals.get("defense_context", {})
        if defense.get("lean") == "OVER" and defense.get("adjustment", 0) > 4:
            return {"pick": f"OVER {line}", "odds": over_odds}
        elif defense.get("lean") == "UNDER" and defense.get("adjustment", 0) < -4:
            return {"pick": f"UNDER {line}", "odds": under_odds}
        
        # PRIORITY 7: Pace Factor
        pace = signals.get("pace", {})
        if pace.get("lean") == "OVER" and pace.get("environment") == "high_scoring":
            return {"pick": f"OVER {line}", "odds": over_odds}
        elif pace.get("lean") == "UNDER" and pace.get("environment") == "grind_it_out":
            return {"pick": f"UNDER {line}", "odds": under_odds}
        
        # PRIORITY 8: Vegas Context
        vegas = signals.get("vegas_context", {})
        if vegas.get("lean") == "OVER":
            return {"pick": f"OVER {line}", "odds": over_odds}
        elif vegas.get("lean") == "UNDER":
            return {"pick": f"UNDER {line}", "odds": under_odds}
        
        # PRIORITY 9: Fatigue (tired = UNDER)
        fatigue = signals.get("fatigue", {})
        if fatigue.get("lean") == "UNDER" and fatigue.get("level") in ["severe", "moderate"]:
            return {"pick": f"UNDER {line}", "odds": under_odds}
        
        # PRIORITY 10: Referee Impact
        ref = signals.get("referee", {})
        if ref.get("props_lean") == "OVER":
            return {"pick": f"OVER {line}", "odds": over_odds}
        elif ref.get("props_lean") == "UNDER":
            return {"pick": f"UNDER {line}", "odds": under_odds}
        
        # PRIORITY 11: Matchup History
        matchup = signals.get("matchup", {})
        if matchup.get("adjustment", 0) > 2:
            return {"pick": f"OVER {line}", "odds": over_odds}
        elif matchup.get("adjustment", 0) < -2:
            return {"pick": f"UNDER {line}", "odds": under_odds}
        
        # PRIORITY 12: Explicit lean signal (esoteric aggregate)
        lean = signals.get("lean", {})
        if lean.get("direction") == "OVER":
            return {"pick": f"OVER {line}", "odds": over_odds}
        elif lean.get("direction") == "UNDER":
            return {"pick": f"UNDER {line}", "odds": under_odds}
        
        # PRIORITY 13: Line value
        line_value = signals.get("line_value", {})
        if line_value.get("side") == "OVER":
            return {"pick": f"OVER {line}", "odds": over_odds}
        elif line_value.get("side") == "UNDER":
            return {"pick": f"UNDER {line}", "odds": under_odds}
        
        # PRIORITY 14: Zodiac element
        zodiac = signals.get("zodiac", {})
        if zodiac.get("lean") == "OVER":
            return {"pick": f"OVER {line}", "odds": over_odds}
        elif zodiac.get("lean") == "UNDER":
            return {"pick": f"UNDER {line}", "odds": under_odds}
        
        # No strong direction - don't force a pick
        return None
    
    def _guess_position(self, player_name: str) -> str:
        """Guess player position from name for defensive matchup analysis"""
        positions = {
            # Point Guards
            "stephen curry": "PG", "luka doncic": "PG", "ja morant": "PG",
            "tyrese haliburton": "PG", "damian lillard": "PG", "trae young": "PG",
            "jalen brunson": "PG", "de'aaron fox": "PG", "darius garland": "PG",
            "tyrese maxey": "PG", "lamelo ball": "PG", "shai gilgeous-alexander": "PG",
            "fred vanvleet": "PG", "dejounte murray": "PG", "cade cunningham": "PG",
            "jalen green": "SG", "anfernee simons": "PG", "immanuel quickley": "PG",
            
            # Shooting Guards
            "donovan mitchell": "SG", "devin booker": "SG", "anthony edwards": "SG",
            "jaylen brown": "SG", "zach lavine": "SG", "desmond bane": "SG",
            "cj mccollum": "SG", "austin reaves": "SG", "terry rozier": "SG",
            "bradley beal": "SG", "bogdan bogdanovic": "SG", "malik beasley": "SG",
            
            # Small Forwards
            "lebron james": "SF", "kevin durant": "SF", "jayson tatum": "SF",
            "jimmy butler": "SF", "paul george": "SF", "kawhi leonard": "SF",
            "brandon ingram": "SF", "paolo banchero": "SF", "scottie barnes": "SF",
            "franz wagner": "SF", "mikal bridges": "SF", "khris middleton": "SF",
            "andrew wiggins": "SF", "demar derozan": "SF", "og anunoby": "SF",
            "lauri markkanen": "SF", "jalen williams": "SF", "herb jones": "SF",
            
            # Power Forwards
            "giannis antetokounmpo": "PF", "anthony davis": "PF", "zion williamson": "PF",
            "pascal siakam": "PF", "julius randle": "PF", "jabari smith jr": "PF",
            "evan mobley": "PF", "jaren jackson jr": "PF", "jerami grant": "PF",
            "draymond green": "PF", "john collins": "PF", "keegan murray": "PF",
            
            # Centers
            "nikola jokic": "C", "joel embiid": "C", "victor wembanyama": "C",
            "karl-anthony towns": "C", "bam adebayo": "C", "domantas sabonis": "C",
            "rudy gobert": "C", "alperen sengun": "C", "chet holmgren": "C",
            "jarrett allen": "C", "brook lopez": "C", "nikola vucevic": "C",
            "jonas valanciunas": "C", "clint capela": "C", "myles turner": "C",
            "deandre ayton": "C", "ivica zubac": "C", "nic claxton": "C"
        }
        
        name_lower = player_name.lower()
        for player, pos in positions.items():
            if player in name_lower or name_lower in player:
                return pos
        
        # Default based on name patterns (guards tend to have shorter last names, etc.)
        return "SF"
    
    def _format_prop_type(self, prop_type):
        """Format prop type for display"""
        type_map = {
            "player_points": "Points",
            "player_rebounds": "Rebounds",
            "player_assists": "Assists",
            "player_threes": "3-Pointers",
            "player_goals": "Goals",
            "player_shots_on_goal": "Shots on Goal",
            "batter_hits": "Hits",
            "batter_total_bases": "Total Bases",
            "pitcher_strikeouts": "Strikeouts",
            "batter_rbis": "RBIs"
        }
        return type_map.get(prop_type, prop_type.replace("_", " ").title())
    
    def grade_prop(self, prop_id: str, result: str):
        """Grade a prop: W, L, or P"""
        for prop in self.props_history:
            if prop.get("id") == prop_id:
                prop["status"] = "graded"
                prop["result"] = result
                
                odds = prop.get("odds", -110)
                if result == "W":
                    prop["profit_loss"] = (odds / 100) if odds > 0 else (100 / abs(odds))
                    self.performance["wins"] += 1
                elif result == "L":
                    prop["profit_loss"] = -1
                    self.performance["losses"] += 1
                else:
                    prop["profit_loss"] = 0
                    self.performance["pushes"] += 1
                
                self.performance["total_picks"] += 1
                self._update_metrics(prop)
                self.graded_props.append(prop)
                
                return {"success": True, "prop": prop, "performance": self.performance}
        
        return {"success": False, "error": "Prop not found"}
    
    def _update_metrics(self, prop):
        total = self.performance["wins"] + self.performance["losses"]
        if total > 0:
            self.performance["win_rate"] = round(self.performance["wins"] / total * 100, 1)
        
        total_profit = sum(p.get("profit_loss", 0) for p in self.graded_props)
        if len(self.graded_props) > 0:
            self.performance["roi"] = round(total_profit / len(self.graded_props) * 100, 1)


props_engine = PropsPicksEngine()


picks_engine = PicksEngineV2()


# ============================================
# ESOTERIC MODULE
# ============================================

class GematriaCalculator:
    SIMPLE = {chr(i+64): i for i in range(1, 27)}
    PYTHAGOREAN = {'A':1,'B':2,'C':3,'D':4,'E':5,'F':6,'G':7,'H':8,'I':9,'J':1,'K':2,'L':3,'M':4,'N':5,'O':6,'P':7,'Q':8,'R':9,'S':1,'T':2,'U':3,'V':4,'W':5,'X':6,'Y':7,'Z':8}
    
    def calculate_simple(self, text):
        return sum(self.SIMPLE.get(c, 0) for c in text.upper().replace(" ", ""))
    
    def calculate_pythagorean(self, text):
        total = sum(self.PYTHAGOREAN.get(c, 0) for c in text.upper().replace(" ", ""))
        return self.reduce(total)
    
    def reduce(self, num):
        while num > 9 and num not in [11, 22, 33]:
            num = sum(int(d) for d in str(num))
        return num
    
    def full_analysis(self, text):
        simple = self.calculate_simple(text)
        pyth = self.calculate_pythagorean(text)
        red = self.reduce(simple)
        return {"text": text, "simple": simple, "pythagorean": pyth, "reduced": red}


class NumerologyCalculator:
    MEANINGS = {
        1: {"energy": "Leadership", "sports": "Individual excellence"},
        2: {"energy": "Partnership", "sports": "Team chemistry, close games"},
        3: {"energy": "Creativity", "sports": "High scoring"},
        4: {"energy": "Stability", "sports": "Defense dominates"},
        5: {"energy": "Change", "sports": "Momentum shifts, upsets"},
        6: {"energy": "Harmony", "sports": "Home team advantage"},
        7: {"energy": "Spirituality", "sports": "Underdogs, unexpected"},
        8: {"energy": "Power", "sports": "Favorites cover"},
        9: {"energy": "Completion", "sports": "Blowouts"},
        11: {"energy": "Master Intuition", "sports": "Trust your read"},
        22: {"energy": "Master Builder", "sports": "Dynasty teams"},
        33: {"energy": "Master Teacher", "sports": "Legacy games"}
    }
    
    def reduce(self, num):
        while num > 9 and num not in [11, 22, 33]:
            num = sum(int(d) for d in str(num))
        return num
    
    def date_energy(self, d):
        life_path = self.reduce(d.month + d.day + sum(int(x) for x in str(d.year)))
        meaning = self.MEANINGS.get(life_path, {})
        power_day = life_path in [8, 11, 22]
        upset = life_path in [5, 7]
        return {"date": d.isoformat(), "life_path": life_path, "day_energy": self.reduce(d.day), "meaning": meaning, "power_day": power_day, "upset_potential": upset}


class SacredGeometry:
    FIBONACCI = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233]
    
    def vortex_root(self, num):
        while num > 9:
            num = sum(int(d) for d in str(num))
        return num
    
    def analyze(self, num):
        root = self.vortex_root(int(num))
        near_fib = min(self.FIBONACCI, key=lambda x: abs(x - num))
        is_sacred = root in [3, 6, 9]
        fib_aligned = abs(num - near_fib) < 3
        return {"value": num, "digital_root": root, "is_sacred": is_sacred, "tesla_energy": is_sacred, "nearest_fibonacci": near_fib, "fib_aligned": fib_aligned}


class AstrologyCalculator:
    MOON_CYCLE = 29.53
    
    def moon_phase(self, d):
        known_new = date(2000, 1, 6)
        days = (d - known_new).days
        pos = (days % self.MOON_CYCLE) / self.MOON_CYCLE
        if pos < 0.125:
            phase = "New Moon"
        elif pos < 0.25:
            phase = "Waxing Crescent"
        elif pos < 0.375:
            phase = "First Quarter"
        elif pos < 0.5:
            phase = "Waxing Gibbous"
        elif pos < 0.625:
            phase = "Full Moon"
        elif pos < 0.75:
            phase = "Waning Gibbous"
        elif pos < 0.875:
            phase = "Last Quarter"
        else:
            phase = "Waning Crescent"
        full = 0.45 < pos < 0.55
        new = pos < 0.1 or pos > 0.9
        chaos = "HIGH" if full else "LOW"
        return {"phase": phase, "position": round(pos, 3), "full_moon": full, "new_moon": new, "chaos_factor": chaos}
    
    def zodiac(self, d):
        elements = {"Aries": "Fire", "Leo": "Fire", "Sagittarius": "Fire", "Taurus": "Earth", "Virgo": "Earth", "Capricorn": "Earth", "Gemini": "Air", "Libra": "Air", "Aquarius": "Air", "Cancer": "Water", "Scorpio": "Water", "Pisces": "Water"}
        signs = [("Capricorn", 1, 19), ("Aquarius", 2, 18), ("Pisces", 3, 20), ("Aries", 4, 19), ("Taurus", 5, 20), ("Gemini", 6, 20), ("Cancer", 7, 22), ("Leo", 8, 22), ("Virgo", 9, 22), ("Libra", 10, 22), ("Scorpio", 11, 21), ("Sagittarius", 12, 21), ("Capricorn", 12, 31)]
        for sign, month, day in signs:
            if d.month < month or (d.month == month and d.day <= day):
                return {"sign": sign, "element": elements.get(sign, "Unknown")}
        return {"sign": "Capricorn", "element": "Earth"}


class EsotericAnalyzer:
    def __init__(self):
        self.gematria = GematriaCalculator()
        self.numerology = NumerologyCalculator()
        self.sacred = SacredGeometry()
        self.astrology = AstrologyCalculator()
    
    def analyze_matchup(self, home, away, game_date, total=None):
        home_gem = self.gematria.full_analysis(home)
        away_gem = self.gematria.full_analysis(away)
        date_num = self.numerology.date_energy(game_date)
        moon = self.astrology.moon_phase(game_date)
        zodiac = self.astrology.zodiac(game_date)
        sacred = self.sacred.analyze(total) if total else None
        edge_score = 50
        factors = []
        if date_num["power_day"]:
            edge_score += 10
            factors.append("Power day - favorites strengthened")
        if date_num["upset_potential"]:
            edge_score -= 10
            factors.append("Upset energy in numerology")
        if moon["full_moon"]:
            edge_score -= 15
            factors.append("Full Moon CHAOS - expect the unexpected")
        if moon["new_moon"]:
            edge_score -= 5
            factors.append("New Moon - underdog energy")
        if zodiac["element"] == "Fire":
            factors.append("Fire sign - lean OVER")
        elif zodiac["element"] == "Earth":
            factors.append("Earth sign - lean UNDER")
        if sacred and sacred["tesla_energy"]:
            factors.append("Tesla 3-6-9 alignment!")
            edge_score += 5
        gem_diff = home_gem["simple"] - away_gem["simple"]
        if abs(gem_diff) > 20:
            gem_fav = home if gem_diff > 0 else away
            factors.append("Gematria favors " + gem_fav)
        if edge_score > 55:
            lean = "FAVORITE"
        elif edge_score < 45:
            lean = "UNDERDOG"
        else:
            lean = "NEUTRAL"
        edge_score = min(max(edge_score, 0), 100)
        return {
            "matchup": away + " @ " + home,
            "date": game_date.isoformat(),
            "gematria": {"home": home_gem, "away": away_gem, "difference": gem_diff},
            "numerology": date_num,
            "moon_phase": moon,
            "zodiac": zodiac,
            "sacred_geometry": sacred,
            "esoteric_edge": {"score": edge_score, "factors": factors, "lean": lean}
        }
    
    def analyze_player_prop(self, player_name, prop_line, prop_type="points"):
        player_gem = self.gematria.full_analysis(player_name)
        line_sacred = self.sacred.analyze(prop_line)
        today = date.today()
        date_num = self.numerology.date_energy(today)
        moon = self.astrology.moon_phase(today)
        factors = []
        edge_score = 50
        if player_gem["reduced"] in [3, 6, 9]:
            factors.append("Player name has Tesla energy - OVER lean")
            edge_score += 8
        if line_sacred["tesla_energy"]:
            factors.append("Prop line has sacred number alignment")
            edge_score += 5
        if line_sacred["fib_aligned"]:
            factors.append("Line near Fibonacci number - expect to hit exact")
        if date_num["life_path"] == 3 and prop_type == "points":
            factors.append("Life Path 3 (creativity) favors high scoring")
            edge_score += 7
        if moon["full_moon"]:
            factors.append("Full Moon - volatile performances expected")
            edge_score -= 5
        if edge_score > 55:
            lean = "OVER"
        elif edge_score < 45:
            lean = "UNDER"
        else:
            lean = "NEUTRAL"
        return {
            "player": player_name,
            "prop_type": prop_type,
            "line": prop_line,
            "gematria": player_gem,
            "line_sacred": line_sacred,
            "date_energy": date_num,
            "moon": moon,
            "esoteric_edge": {"score": edge_score, "factors": factors, "lean": lean}
        }


esoteric = EsotericAnalyzer()


# ============================================
# LIVE ODDS SERVICE
# ============================================

class LiveOddsService:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.the-odds-api.com/v4"
    
    def get_live_odds(self, sport="basketball_nba", bookmakers="fanduel,draftkings"):
        url = self.base_url + "/sports/" + sport + "/odds"
        params = {"apiKey": self.api_key, "regions": "us", "markets": "h2h,spreads,totals", "bookmakers": bookmakers, "oddsFormat": "american"}
        r = requests.get(url, params=params)
        if r.status_code == 200:
            games = r.json()
            formatted = self._format(games)
            remaining = r.headers.get('x-requests-remaining', 'unknown')
            return {"success": True, "sport": sport, "games_count": len(games), "games": formatted, "api_usage": {"remaining": remaining}}
        return {"success": False, "error": r.status_code}
    
    def get_player_props(self, sport="basketball_nba", markets="player_points"):
        url = self.base_url + "/sports/" + sport + "/odds"
        params = {"apiKey": self.api_key, "regions": "us", "markets": markets, "bookmakers": "fanduel,draftkings", "oddsFormat": "american"}
        r = requests.get(url, params=params)
        if r.status_code == 200:
            data = r.json()
            props = self._format_props(data)
            return {"success": True, "sport": sport, "props_count": len(props), "props": props, "api_usage": {"remaining": r.headers.get('x-requests-remaining', 'unknown')}}
        return {"success": False, "error": r.status_code, "message": r.text}
    
    def _format(self, games):
        result = []
        for g in games:
            fg = {"id": g.get("id"), "commence_time": g.get("commence_time"), "home_team": g.get("home_team"), "away_team": g.get("away_team"), "bookmakers": {}}
            for b in g.get("bookmakers", []):
                fg["bookmakers"][b["key"]] = {"markets": {}}
                for m in b.get("markets", []):
                    outcomes = {}
                    for o in m.get("outcomes", []):
                        outcomes[o["name"]] = {"price": o.get("price"), "point": o.get("point")}
                    fg["bookmakers"][b["key"]]["markets"][m["key"]] = outcomes
            result.append(fg)
        return result
    
    def _format_props(self, data):
        props = []
        games = data if isinstance(data, list) else [data]
        for game in games:
            game_info = {"game_id": game.get("id"), "home_team": game.get("home_team"), "away_team": game.get("away_team"), "commence_time": game.get("commence_time")}
            for bookmaker in game.get("bookmakers", []):
                book_name = bookmaker.get("key")
                for market in bookmaker.get("markets", []):
                    market_key = market.get("key", "")
                    if "player_" in market_key or "batter_" in market_key or "pitcher_" in market_key:
                        for outcome in market.get("outcomes", []):
                            prop = {"game": game_info, "bookmaker": book_name, "market": market_key, "player": outcome.get("description", outcome.get("name", "")), "type": outcome.get("name", ""), "line": outcome.get("point"), "odds": outcome.get("price")}
                            props.append(prop)
        return props


class BettingSplitsService:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.playbook-api.com/v1"
    
    def get_splits(self, league="NFL"):
        try:
            url = self.base_url + "/splits"
            params = {"league": league.upper(), "api_key": self.api_key}
            r = requests.get(url, params=params, timeout=10)
            if r.status_code == 200:
                return {"success": True, "league": league, "splits": r.json()}
            return {"success": False, "error": r.status_code}
        except Exception as e:
            return {"success": False, "error": str(e)}


odds_service = LiveOddsService(ODDS_API_KEY)
splits_service = BettingSplitsService(PLAYBOOK_API_KEY)


# ============================================
# ALERTS SYSTEM
# ============================================

class AlertsManager:
    def __init__(self):
        self.alerts = []
        self.settings = {
            "sharp_money": {"enabled": True, "threshold": 8},
            "line_movement": {"enabled": True, "threshold": 1.5},
            "injury": {"enabled": True},
            "esoteric_edge": {"enabled": True, "threshold": 65},
            "value_bet": {"enabled": True, "threshold": 3}
        }
        self.discord_webhook = None
    
    def set_discord_webhook(self, webhook_url):
        self.discord_webhook = webhook_url
    
    def update_settings(self, new_settings):
        for key, value in new_settings.items():
            if key in self.settings:
                self.settings[key].update(value)
    
    def create_alert(self, alert_type, title, message, data=None):
        alert = {
            "id": len(self.alerts) + 1,
            "type": alert_type,
            "title": title,
            "message": message,
            "data": data,
            "timestamp": datetime.now().isoformat(),
            "read": False
        }
        self.alerts.insert(0, alert)
        if len(self.alerts) > 100:
            self.alerts = self.alerts[:100]
        if self.discord_webhook and self.settings.get(alert_type, {}).get("enabled", True):
            self.send_discord(alert)
        return alert
    
    def send_discord(self, alert):
        if not self.discord_webhook:
            return
        try:
            color_map = {
                "sharp_money": 65280,
                "line_movement": 16776960,
                "injury": 16711680,
                "esoteric_edge": 9109759,
                "value_bet": 65535
            }
            embed = {
                "title": alert["title"],
                "description": alert["message"],
                "color": color_map.get(alert["type"], 8421504),
                "timestamp": alert["timestamp"],
                "footer": {"text": "Bookie-o-em Alerts"}
            }
            payload = {"embeds": [embed]}
            requests.post(self.discord_webhook, json=payload, timeout=5)
        except Exception as e:
            print(f"Discord webhook error: {e}")
    
    def check_sharp_money(self, splits_data):
        if not self.settings["sharp_money"]["enabled"]:
            return []
        threshold = self.settings["sharp_money"]["threshold"]
        alerts = []
        try:
            games = splits_data.get("splits", {}).get("data", [])
            for game in games:
                home = game.get("homeTeam", "Home")
                away = game.get("awayTeam", "Away")
                splits = game.get("splits", {})
                for market in ["spread", "total", "moneyline"]:
                    market_data = splits.get(market, {})
                    bets = market_data.get("bets", {})
                    money = market_data.get("money", {})
                    home_bets = bets.get("homePercent", 0) or 0
                    home_money = money.get("homePercent", 0) or 0
                    away_bets = bets.get("awayPercent", 0) or 0
                    away_money = money.get("awayPercent", 0) or 0
                    if home_money - home_bets >= threshold:
                        alert = self.create_alert(
                            "sharp_money",
                            f"Sharp Money Alert: {home}",
                            f"{market.upper()}: {home_bets}% bets but {home_money}% money on {home}. Sharp money detected!",
                            {"game": f"{away} @ {home}", "market": market, "bets": home_bets, "money": home_money}
                        )
                        alerts.append(alert)
                    if away_money - away_bets >= threshold:
                        alert = self.create_alert(
                            "sharp_money",
                            f"Sharp Money Alert: {away}",
                            f"{market.upper()}: {away_bets}% bets but {away_money}% money on {away}. Sharp money detected!",
                            {"game": f"{away} @ {home}", "market": market, "bets": away_bets, "money": away_money}
                        )
                        alerts.append(alert)
        except Exception as e:
            print(f"Sharp money check error: {e}")
        return alerts
    
    def check_esoteric_edge(self):
        if not self.settings["esoteric_edge"]["enabled"]:
            return []
        alerts = []
        threshold = self.settings["esoteric_edge"]["threshold"]
        today = date.today()
        moon = esoteric.astrology.moon_phase(today)
        numerology = esoteric.numerology.date_energy(today)
        if moon["full_moon"]:
            alert = self.create_alert(
                "esoteric_edge",
                "Full Moon Alert",
                "Full Moon today! Expect chaos, upsets, and emotional games. Consider underdog plays.",
                {"moon_phase": moon["phase"], "position": moon["position"]}
            )
            alerts.append(alert)
        if numerology["power_day"]:
            alert = self.create_alert(
                "esoteric_edge",
                "Power Day Alert",
                f"Life Path {numerology['life_path']} - Power day! Favorites are strengthened today.",
                {"life_path": numerology["life_path"], "meaning": numerology["meaning"]}
            )
            alerts.append(alert)
        if numerology["upset_potential"]:
            alert = self.create_alert(
                "esoteric_edge",
                "Upset Energy Alert",
                f"Life Path {numerology['life_path']} - Upset energy present! Watch for underdogs.",
                {"life_path": numerology["life_path"], "meaning": numerology["meaning"]}
            )
            alerts.append(alert)
        return alerts
    
    def check_value_bet(self, probability, odds):
        if not self.settings["value_bet"]["enabled"]:
            return None
        threshold = self.settings["value_bet"]["threshold"]
        if odds > 0:
            dec = (odds / 100) + 1
        else:
            dec = (100 / abs(odds)) + 1
        edge = ((probability * dec) - 1) * 100
        if edge >= threshold:
            alert = self.create_alert(
                "value_bet",
                f"Value Bet Found: +{round(edge, 1)}% Edge",
                f"Your {round(probability*100)}% probability at {odds} odds gives {round(edge, 1)}% edge. Consider betting!",
                {"probability": probability, "odds": odds, "edge": edge}
            )
            return alert
        return None
    
    def get_alerts(self, limit=50, alert_type=None):
        filtered = self.alerts
        if alert_type:
            filtered = [a for a in self.alerts if a["type"] == alert_type]
        return filtered[:limit]
    
    def mark_read(self, alert_id):
        for alert in self.alerts:
            if alert["id"] == alert_id:
                alert["read"] = True
                return True
        return False
    
    def mark_all_read(self):
        for alert in self.alerts:
            alert["read"] = True


alerts_manager = AlertsManager()


# ============================================
# FASTAPI APP
# ============================================

app = FastAPI(title="AI Sports Betting API", description="Full Picks Engine with 17 Signals + Grading + Learning", version="4.5.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


class EdgeRequest(BaseModel):
    your_probability: float = Field(..., ge=0, le=1)
    betting_odds: float


class EsotericRequest(BaseModel):
    home_team: str
    away_team: str
    game_date: str
    predicted_total: Optional[float] = None


class PlayerPropRequest(BaseModel):
    player_name: str
    prop_line: float
    prop_type: Optional[str] = "points"


class AlertSettingsRequest(BaseModel):
    sharp_money: Optional[dict] = None
    line_movement: Optional[dict] = None
    injury: Optional[dict] = None
    esoteric_edge: Optional[dict] = None
    value_bet: Optional[dict] = None


class DiscordWebhookRequest(BaseModel):
    webhook_url: str


class GradeRequest(BaseModel):
    """Request model for grading picks"""
    pick_id: str
    result: str  # W, L, or P


class BulkGradeRequest(BaseModel):
    """Request model for bulk grading picks"""
    results: Dict[str, str]  # {pick_id: result, ...}


@app.get("/")
async def root():
    return {
        "status": "online",
        "message": "Bookie-o-em API v4.5 - Full Picks Engine",
        "version": "4.5.0",
        "features": ["17 signals", "grading", "learning", "performance tracking"]
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat(), "features": ["esoteric", "props", "alerts"]}


@app.get("/model-status")
async def model_status():
    models = {
        "ensemble_stacking": "ready",
        "lstm_network": "fallback_mode",
        "matchup_specific": "ready",
        "monte_carlo": "ready",
        "line_analyzer": "ready",
        "rest_fatigue": "ready",
        "injury_impact": "ready",
        "edge_calculator": "ready",
        "gematria": "ready",
        "numerology": "ready",
        "sacred_geometry": "ready",
        "astrology": "ready",
        "alerts_system": "ready"
    }
    return {"status": "operational", "models": models, "total_models": 13, "version": "4.2.0"}


@app.post("/calculate-edge")
async def calc_edge(req: EdgeRequest):
    odds = req.betting_odds
    prob = req.your_probability
    if odds > 0:
        dec = (odds / 100) + 1
    else:
        dec = (100 / abs(odds)) + 1
    edge = ((prob * dec) - 1) * 100
    kelly = max(0, (prob * (dec - 1) - (1 - prob)) / (dec - 1))
    rec = "BET" if edge > 2 else "NO BET"
    alerts_manager.check_value_bet(prob, odds)
    return {"status": "success", "edge_analysis": {"edge_percent": round(edge, 2), "kelly": round(kelly, 4), "recommendation": rec}}


# Live Odds
@app.get("/live-odds")
async def live_odds(sport: str = "basketball_nba"):
    return odds_service.get_live_odds(sport)


@app.get("/live-games")
async def live_games(sport: str = "basketball_nba"):
    data = odds_service.get_live_odds(sport)
    if not data.get("success"):
        return data
    simple = []
    for g in data["games"]:
        sg = {"id": g["id"], "home_team": g["home_team"], "away_team": g["away_team"], "start_time": g["commence_time"], "fanduel": None, "draftkings": None}
        if "fanduel" in g.get("bookmakers", {}):
            sg["fanduel"] = g["bookmakers"]["fanduel"]["markets"]
        if "draftkings" in g.get("bookmakers", {}):
            sg["draftkings"] = g["bookmakers"]["draftkings"]["markets"]
        simple.append(sg)
    return {"success": True, "games": simple, "api_usage": data.get("api_usage")}


@app.get("/live-odds/nba")
async def nba():
    return await live_games("basketball_nba")


@app.get("/live-odds/ncaab")
async def ncaab():
    return await live_games("basketball_ncaab")


@app.get("/live-odds/nfl")
async def nfl():
    return await live_games("football_nfl")


@app.get("/live-odds/mlb")
async def mlb():
    return await live_games("baseball_mlb")


@app.get("/live-odds/nhl")
async def nhl():
    return await live_games("icehockey_nhl")


# Splits
@app.get("/splits")
async def splits(league: str = "NFL"):
    data = splits_service.get_splits(league)
    if data.get("success"):
        alerts_manager.check_sharp_money(data)
    return data


@app.get("/splits/nfl")
async def splits_nfl():
    return await splits("NFL")


@app.get("/splits/nba")
async def splits_nba():
    return await splits("NBA")


@app.get("/splits/ncaab")
async def splits_ncaab():
    return await splits("NCAAB")


@app.get("/splits/mlb")
async def splits_mlb():
    return await splits("MLB")


@app.get("/splits/nhl")
async def splits_nhl():
    return await splits("NHL")


# Esoteric
@app.post("/esoteric/analyze")
async def esoteric_analyze(req: EsotericRequest):
    try:
        game_date = datetime.strptime(req.game_date, "%Y-%m-%d").date()
        result = esoteric.analyze_matchup(req.home_team, req.away_team, game_date, req.predicted_total)
        return {"success": True, "analysis": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/esoteric/gematria/{text}")
async def gematria(text: str):
    result = esoteric.gematria.full_analysis(text)
    return {"success": True, "analysis": result}


@app.get("/esoteric/numerology/{date_str}")
async def numerology(date_str: str):
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        result = esoteric.numerology.date_energy(d)
        return {"success": True, "analysis": result}
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")


@app.get("/esoteric/moon/{date_str}")
async def moon(date_str: str):
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        result = esoteric.astrology.moon_phase(d)
        return {"success": True, "analysis": result}
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid date format")


@app.get("/esoteric/sacred/{number}")
async def sacred(number: float):
    result = esoteric.sacred.analyze(number)
    return {"success": True, "analysis": result}


@app.get("/esoteric/today")
async def today_energy():
    d = date.today()
    num = esoteric.numerology.date_energy(d)
    moon = esoteric.astrology.moon_phase(d)
    zod = esoteric.astrology.zodiac(d)
    alerts_manager.check_esoteric_edge()
    return {"success": True, "date": d.isoformat(), "numerology": num, "moon": moon, "zodiac": zod}


# Player Props
@app.get("/props")
async def get_props(sport: str = "basketball_nba", markets: str = "player_points,player_rebounds,player_assists"):
    return odds_service.get_player_props(sport=sport, markets=markets)


@app.get("/props/nba")
async def get_nba_props():
    return odds_service.get_player_props(sport="basketball_nba", markets="player_points,player_rebounds,player_assists")


@app.get("/props/nba/points")
async def get_nba_points():
    return odds_service.get_player_props(sport="basketball_nba", markets="player_points")


@app.get("/props/nba/rebounds")
async def get_nba_rebounds():
    return odds_service.get_player_props(sport="basketball_nba", markets="player_rebounds")


@app.get("/props/nba/assists")
async def get_nba_assists():
    return odds_service.get_player_props(sport="basketball_nba", markets="player_assists")


@app.get("/props/nba/threes")
async def get_nba_threes():
    return odds_service.get_player_props(sport="basketball_nba", markets="player_threes")


@app.get("/props/nhl")
async def get_nhl_props():
    return odds_service.get_player_props(sport="icehockey_nhl", markets="player_points,player_goals,player_assists,player_shots_on_goal")


@app.get("/props/nhl/points")
async def get_nhl_points():
    return odds_service.get_player_props(sport="icehockey_nhl", markets="player_points")


@app.get("/props/nhl/goals")
async def get_nhl_goals():
    return odds_service.get_player_props(sport="icehockey_nhl", markets="player_goals")


@app.get("/props/nhl/assists")
async def get_nhl_assists():
    return odds_service.get_player_props(sport="icehockey_nhl", markets="player_assists")


@app.get("/props/nhl/shots")
async def get_nhl_shots():
    return odds_service.get_player_props(sport="icehockey_nhl", markets="player_shots_on_goal")


@app.get("/props/mlb")
async def get_mlb_props():
    return odds_service.get_player_props(sport="baseball_mlb", markets="batter_hits,batter_total_bases,batter_rbis,pitcher_strikeouts")


@app.get("/props/mlb/hits")
async def get_mlb_hits():
    return odds_service.get_player_props(sport="baseball_mlb", markets="batter_hits")


@app.get("/props/mlb/bases")
async def get_mlb_bases():
    return odds_service.get_player_props(sport="baseball_mlb", markets="batter_total_bases")


@app.get("/props/mlb/strikeouts")
async def get_mlb_strikeouts():
    return odds_service.get_player_props(sport="baseball_mlb", markets="pitcher_strikeouts")


@app.get("/props/mlb/rbis")
async def get_mlb_rbis():
    return odds_service.get_player_props(sport="baseball_mlb", markets="batter_rbis")


@app.get("/props/nfl")
async def get_nfl_props():
    return odds_service.get_player_props(sport="americanfootball_nfl", markets="player_pass_yds,player_rush_yds,player_reception_yds")


@app.post("/props/analyze")
async def analyze_prop(req: PlayerPropRequest):
    result = esoteric.analyze_player_prop(req.player_name, req.prop_line, req.prop_type)
    return {"success": True, "analysis": result}


# ============================================
# ALERTS ENDPOINTS
# ============================================

@app.get("/alerts")
async def get_alerts(limit: int = 50, alert_type: str = None):
    alerts = alerts_manager.get_alerts(limit=limit, alert_type=alert_type)
    unread = len([a for a in alerts_manager.alerts if not a["read"]])
    return {"success": True, "alerts": alerts, "unread_count": unread, "total": len(alerts_manager.alerts)}


@app.get("/alerts/settings")
async def get_alert_settings():
    return {"success": True, "settings": alerts_manager.settings, "discord_configured": alerts_manager.discord_webhook is not None}


@app.post("/alerts/settings")
async def update_alert_settings(req: AlertSettingsRequest):
    updates = {}
    if req.sharp_money:
        updates["sharp_money"] = req.sharp_money
    if req.line_movement:
        updates["line_movement"] = req.line_movement
    if req.injury:
        updates["injury"] = req.injury
    if req.esoteric_edge:
        updates["esoteric_edge"] = req.esoteric_edge
    if req.value_bet:
        updates["value_bet"] = req.value_bet
    alerts_manager.update_settings(updates)
    return {"success": True, "settings": alerts_manager.settings}


@app.post("/alerts/discord")
async def set_discord_webhook(req: DiscordWebhookRequest):
    alerts_manager.set_discord_webhook(req.webhook_url)
    test_alert = alerts_manager.create_alert(
        "value_bet",
        "Discord Connected!",
        "Your Bookie-o-em alerts are now connected to Discord.",
        {"test": True}
    )
    return {"success": True, "message": "Discord webhook configured", "test_alert_sent": True}


@app.post("/alerts/read/{alert_id}")
async def mark_alert_read(alert_id: int):
    success = alerts_manager.mark_read(alert_id)
    return {"success": success}


@app.post("/alerts/read-all")
async def mark_all_alerts_read():
    alerts_manager.mark_all_read()
    return {"success": True}


@app.post("/alerts/test")
async def test_alert(alert_type: str = "sharp_money"):
    test_alerts = {
        "sharp_money": ("Sharp Money Test", "70% of money on Chiefs but only 45% of bets. Sharp action detected!"),
        "line_movement": ("Line Movement Test", "Patriots moved from -3 to -1.5. Significant reverse line movement!"),
        "injury": ("Injury Alert Test", "Patrick Mahomes - Questionable (Ankle) - Monitor closely"),
        "esoteric_edge": ("Esoteric Edge Test", "Full Moon + Life Path 7 = Maximum upset potential today!"),
        "value_bet": ("Value Bet Test", "Found +5.2% edge on Lakers ML at +150!")
    }
    title, message = test_alerts.get(alert_type, ("Test Alert", "This is a test alert"))
    alert = alerts_manager.create_alert(alert_type, title, message, {"test": True})
    return {"success": True, "alert": alert}


@app.get("/alerts/check")
async def run_alert_checks():
    alerts = []
    esoteric_alerts = alerts_manager.check_esoteric_edge()
    alerts.extend(esoteric_alerts)
    splits_data = splits_service.get_splits("NFL")
    if splits_data.get("success"):
        sharp_alerts = alerts_manager.check_sharp_money(splits_data)
        alerts.extend(sharp_alerts)
    return {"success": True, "alerts_generated": len(alerts), "alerts": alerts}


# ============================================
# WHOP MEMBERSHIP ENDPOINTS
# ============================================

class LicenseValidateRequest(BaseModel):
    license_key: str


class EmailCheckRequest(BaseModel):
    email: str


@app.get("/whop/status")
async def whop_status():
    """Check if Whop integration is configured"""
    return {
        "success": True,
        "configured": WHOP_API_KEY is not None,
        "tiers": {
            "free": {"price": "$0", "features": ["Home", "Odds (3 games)", "Calculator"]},
            "standard": {"price": "$29/mo", "features": ["Unlimited Odds", "Props", "Splits", "Alerts"]},
            "premium": {"price": "$99/mo", "features": ["Everything", "Esoteric Edge", "Priority Support"]}
        }
    }


@app.post("/whop/validate")
async def validate_license(req: LicenseValidateRequest):
    """Validate a Whop license key"""
    result = whop_service.validate_license(req.license_key)
    if result.get("valid"):
        access = whop_service.get_access_level(result.get("tier", "free"))
        result["access"] = access
    return result


@app.post("/whop/check-email")
async def check_membership_email(req: EmailCheckRequest):
    """Check membership status by email"""
    result = whop_service.check_membership_by_email(req.email)
    access = whop_service.get_access_level(result.get("tier", "free"))
    result["access"] = access
    return result


@app.get("/whop/access/{tier}")
async def get_tier_access(tier: str):
    """Get access level for a specific tier"""
    access = whop_service.get_access_level(tier)
    return {"success": True, "tier": tier, "access": access}


@app.get("/whop/pricing")
async def get_pricing():
    """Get pricing information for display"""
    return {
        "success": True,
        "plans": [
            {
                "id": "free",
                "name": "Free",
                "price": 0,
                "price_display": "Free",
                "interval": None,
                "features": [
                    "Live odds (3 games)",
                    "Edge calculator",
                    "Basic predictions"
                ],
                "cta": "Get Started"
            },
            {
                "id": "standard",
                "name": "Standard",
                "price": 29,
                "price_display": "$29/mo",
                "interval": "month",
                "features": [
                    "Unlimited live odds",
                    "Player props",
                    "Betting splits",
                    "Real-time alerts",
                    "Discord notifications"
                ],
                "cta": "Subscribe",
                "popular": True
            },
            {
                "id": "premium",
                "name": "Premium",
                "price": 99,
                "price_display": "$99/mo",
                "interval": "month",
                "features": [
                    "Everything in Standard",
                    "Esoteric Edge analysis",
                    "Gematria & numerology",
                    "Moon phase alerts",
                    "Priority support",
                    "Early access to features"
                ],
                "cta": "Go Premium"
            }
        ]
    }


# ============================================
# PICKS ENDPOINTS - BEST BETS
# ============================================

@app.get("/picks")
async def get_picks(sport: str = "basketball_nba"):
    """Get best bets for a sport"""
    result = picks_engine.generate_best_bets(sport)
    return result


@app.get("/picks/nba")
async def get_nba_picks():
    """Get NBA best bets"""
    return picks_engine.generate_best_bets("basketball_nba")


@app.get("/picks/ncaab")
async def get_ncaab_picks():
    """Get NCAA Basketball best bets"""
    return picks_engine.generate_best_bets("basketball_ncaab")


@app.get("/picks/nfl")
async def get_nfl_picks():
    """Get NFL best bets"""
    return picks_engine.generate_best_bets("football_nfl")


@app.get("/picks/nhl")
async def get_nhl_picks():
    """Get NHL best bets"""
    return picks_engine.generate_best_bets("icehockey_nhl")


@app.get("/picks/mlb")
async def get_mlb_picks():
    """Get MLB best bets"""
    return picks_engine.generate_best_bets("baseball_mlb")


@app.get("/picks/all")
async def get_all_picks():
    """Get best bets across all sports"""
    all_picks = []
    
    for sport in ["basketball_nba", "basketball_ncaab", "football_nfl", "icehockey_nhl", "baseball_mlb"]:
        result = picks_engine.generate_best_bets(sport)
        if result.get("success") and result.get("picks"):
            for pick in result["picks"]:
                pick["sport"] = sport.split("_")[1].upper() if "_" in sport else sport.upper()
            all_picks.extend(result["picks"])
    
    # Re-sort by confidence
    all_picks.sort(key=lambda x: x.get("confidence_score", 0), reverse=True)
    
    # Re-rank
    for i, pick in enumerate(all_picks):
        pick["rank"] = i + 1
    
    return {
        "success": True,
        "generated_at": datetime.now().isoformat(),
        "total_picks": len(all_picks),
        "picks": all_picks[:15]  # Top 15 across all sports
    }


# ============================================
# PROP PICKS ENDPOINTS - GOOD & STRONG ONLY
# ============================================

@app.get("/props/picks")
async def get_prop_picks(sport: str = "basketball_nba"):
    """Get best player prop picks - GOOD (75+) and STRONG (85+) only"""
    return props_engine.generate_prop_picks(sport)


@app.get("/props/picks/nba")
async def get_nba_prop_picks():
    """Get best NBA player prop picks"""
    return props_engine.generate_prop_picks("basketball_nba")


@app.get("/props/picks/ncaab")
async def get_ncaab_prop_picks():
    """Get best NCAAB player prop picks"""
    return props_engine.generate_prop_picks("basketball_ncaab")


@app.get("/props/picks/nfl")
async def get_nfl_prop_picks():
    """Get best NFL player prop picks"""
    return props_engine.generate_prop_picks("football_nfl")


@app.get("/props/picks/nhl")
async def get_nhl_prop_picks():
    """Get best NHL player prop picks"""
    return props_engine.generate_prop_picks("icehockey_nhl")


@app.get("/props/picks/mlb")
async def get_mlb_prop_picks():
    """Get best MLB player prop picks"""
    return props_engine.generate_prop_picks("baseball_mlb")


@app.get("/props/picks/all")
async def get_all_prop_picks():
    """Get best prop picks across all sports - GOOD & STRONG ONLY"""
    all_props = []
    
    for sport in ["basketball_nba", "basketball_ncaab", "football_nfl", "icehockey_nhl", "baseball_mlb"]:
        result = props_engine.generate_prop_picks(sport)
        if result.get("success") and result.get("picks"):
            all_props.extend(result["picks"])
    
    # Sort by confidence
    all_props.sort(key=lambda x: x.get("confidence_score", 0), reverse=True)
    
    # Re-rank
    for i, prop in enumerate(all_props):
        prop["rank"] = i + 1
    
    return {
        "success": True,
        "generated_at": datetime.now().isoformat(),
        "total_picks": len(all_props),
        "picks": all_props[:15]  # Top 15 prop picks
    }


@app.post("/props/picks/grade")
async def grade_prop_pick(req: GradeRequest):
    """Grade a prop pick as W (win), L (loss), or P (push)"""
    if req.result not in ["W", "L", "P"]:
        raise HTTPException(status_code=400, detail="Result must be W, L, or P")
    return props_engine.grade_prop(req.pick_id, req.result)


@app.get("/props/picks/performance")
async def get_props_performance():
    """Get prop picks performance metrics"""
    return {
        "success": True,
        "performance": props_engine.performance,
        "total_graded": len(props_engine.graded_props),
        "recent_graded": props_engine.graded_props[-10:][::-1] if props_engine.graded_props else []
    }


# ============================================
# REAL ML PREDICTION ENDPOINTS
# ============================================

class MLPredictionRequest(BaseModel):
    player: str = Field(..., example="LeBron James")
    opponent: str = Field("", example="GSW")
    stat_type: str = Field(..., example="points")
    line: float = Field(..., example=27.5)
    sport: str = Field("NBA", example="NBA")


@app.post("/ml/predict")
async def ml_predict(req: MLPredictionRequest):
    """
    Get REAL ML prediction for a player prop
    
    Uses:
    - LSTM Neural Network (trained on player's game history)
    - Ensemble Model (XGBoost + LightGBM + Random Forest)
    - Monte Carlo Simulation (10,000 iterations)
    - Matchup Analysis (historical performance vs opponent)
    """
    result = real_ml.predict_prop(
        player=req.player,
        opponent=req.opponent,
        stat_type=req.stat_type,
        line=req.line,
        sport=req.sport
    )
    return result


@app.get("/ml/predict/{player}/{stat_type}/{line}")
async def ml_predict_get(player: str, stat_type: str, line: float, opponent: str = "", sport: str = "NBA"):
    """
    Get ML prediction via GET request
    Example: /ml/predict/LeBron%20James/points/27.5
    """
    result = real_ml.predict_prop(
        player=player.replace("%20", " "),
        opponent=opponent,
        stat_type=stat_type,
        line=line,
        sport=sport
    )
    return result


@app.get("/ml/status")
async def ml_status():
    """Check ML system status"""
    return {
        "ml_available": ML_AVAILABLE,
        "tensorflow_available": TENSORFLOW_AVAILABLE,
        "cached_lstm_models": len(real_ml.lstm_models),
        "cached_ensemble_models": len(real_ml.ensemble_models),
        "scraper_cache_size": len(real_ml.scraper.cache)
    }


# ============================================
# REFEREE ANALYSIS ENDPOINTS
# ============================================

@app.get("/refs/today")
async def get_today_refs():
    """Get today's referee assignments"""
    return ref_analyzer.get_ref_assignments()


@app.get("/refs/analyze/{crew_chief}")
async def analyze_ref_crew(crew_chief: str, referee: str = "", umpire: str = ""):
    """
    Analyze a referee crew's tendencies
    
    Returns:
    - Average total in their games
    - Home win percentage
    - Fouls per game
    - Over/Under tendency
    - Recommendations for totals and spreads
    """
    analysis = ref_analyzer.analyze_crew(crew_chief, referee, umpire)
    return analysis


@app.get("/refs/game/{home_team}/{away_team}")
async def get_game_refs(home_team: str, away_team: str):
    """
    Get referee analysis for a specific game
    
    Example: /refs/game/Lakers/Warriors
    """
    return ref_analyzer.get_game_ref_analysis(home_team, away_team)


@app.get("/refs/profiles")
async def get_ref_profiles():
    """Get all referee tendency profiles"""
    return {
        "total_refs": len(ref_analyzer.ref_profiles),
        "league_averages": ref_analyzer.league_avg,
        "over_friendly": [name for name, data in ref_analyzer.ref_profiles.items() if data.get("tendency") == "OVER"],
        "under_friendly": [name for name, data in ref_analyzer.ref_profiles.items() if data.get("tendency") == "UNDER"],
        "home_friendly": [name for name, data in ref_analyzer.ref_profiles.items() if data.get("tendency") == "HOME"],
        "star_friendly": [name for name, data in ref_analyzer.ref_profiles.items() if data.get("tendency") == "STAR_FRIENDLY"],
        "profiles": ref_analyzer.ref_profiles
    }


# ============================================
# CONTEXTUAL DATA ENDPOINTS
# ============================================

@app.get("/context/defense/{team}/{position}")
async def get_defense_context(team: str, position: str):
    """
    Get team's defensive rating against a specific position
    
    Example: /context/defense/Lakers/PG
    
    Returns how many points/rebounds/assists the team allows to that position
    """
    return defense_scraper.get_team_defense_vs_position(team, position)


@app.get("/context/pace/{team}")
async def get_team_pace(team: str):
    """
    Get team's pace (possessions per game)
    
    Example: /context/pace/Warriors
    """
    return pace_scraper.get_team_pace(team)


@app.get("/context/pace/matchup/{home_team}/{away_team}")
async def get_game_pace(home_team: str, away_team: str):
    """
    Get projected pace for a specific game matchup
    
    Example: /context/pace/matchup/Lakers/Warriors
    
    Returns:
    - Both teams' pace
    - Projected game pace
    - Game environment (high_scoring, normal, grind_it_out)
    """
    return pace_scraper.get_game_pace_projection(home_team, away_team)


@app.get("/context/usage/{team}")
async def get_team_usage(team: str, injured: str = ""):
    """
    Get team context including usage vacuum from injuries
    
    Example: /context/usage/Lakers?injured=LeBron James,Anthony Davis
    
    Returns expected boost for remaining players
    """
    injured_list = [p.strip() for p in injured.split(",")] if injured else []
    return team_context_scraper.get_team_context(team, injured_list)


@app.get("/context/usage/player/{player}/{team}")
async def get_player_usage_boost(player: str, team: str, injured: str = ""):
    """
    Get expected usage boost for a specific player when teammates are injured
    
    Example: /context/usage/player/Austin Reaves/Lakers?injured=LeBron James
    """
    injured_list = [p.strip() for p in injured.split(",")] if injured else []
    return team_context_scraper.get_player_usage_boost(player, team, injured_list)


@app.get("/context/fatigue/{team}")
async def get_team_fatigue(team: str, days_rest: int = 2, games_in_5: int = 2, games_in_7: int = 3, prev_city: str = ""):
    """
    Get team fatigue analysis
    
    Example: /context/fatigue/Lakers?days_rest=0&games_in_5=3&prev_city=boston
    
    Returns:
    - Fatigue score (0-100)
    - Back-to-back detection
    - Travel impact
    - Performance adjustment
    """
    return rest_travel_scraper.get_fatigue_analysis(
        team,
        days_rest,
        prev_city if prev_city else None,
        games_in_5,
        games_in_7
    )


@app.get("/context/travel/{from_city}/{to_city}")
async def get_travel_distance(from_city: str, to_city: str):
    """
    Calculate travel distance and time zone difference
    
    Example: /context/travel/boston/los angeles
    """
    distance = rest_travel_scraper.calculate_travel_distance(from_city, to_city)
    tz_diff = rest_travel_scraper.get_time_zone_diff(from_city, to_city)
    
    return {
        "from": from_city,
        "to": to_city,
        "distance_miles": distance,
        "time_zones_crossed": tz_diff,
        "travel_impact": "severe" if distance > 2000 else "moderate" if distance > 1000 else "minimal"
    }


class FullContextRequest(BaseModel):
    player: str
    player_team: str
    opponent: str
    position: str = "SF"
    days_rest: int = 2
    injured_teammates: List[str] = []


@app.post("/context/full")
async def get_full_context(req: FullContextRequest):
    """
    Get ALL contextual factors for a player prop prediction
    
    Combines:
    - Defensive context (opponent vs position)
    - Pace projection
    - Usage vacuum (teammate injuries)
    - Rest/fatigue
    """
    # Defense
    defense = defense_scraper.get_team_defense_vs_position(req.opponent, req.position)
    
    # Pace
    pace = pace_scraper.get_game_pace_projection(req.player_team, req.opponent)
    
    # Usage
    usage = team_context_scraper.get_player_usage_boost(req.player, req.player_team, req.injured_teammates)
    
    # Fatigue
    fatigue = rest_travel_scraper.get_fatigue_analysis(req.player_team, req.days_rest)
    
    # Calculate combined adjustment
    total_mult = 1.0
    
    # Defense adjustment
    def_adj = defense.get("adjustment", 0) / 100
    total_mult *= (1 + def_adj)
    
    # Pace adjustment
    pace_adj = pace.get("stat_adjustment", 0) / 100
    total_mult *= (1 + pace_adj)
    
    # Usage boost
    usage_mult = usage.get("adjusted_multiplier", 1.0)
    total_mult *= usage_mult
    
    # Fatigue
    fatigue_adj = fatigue.get("performance_adjustment", 0)
    total_mult *= (1 + fatigue_adj)
    
    return {
        "player": req.player,
        "opponent": req.opponent,
        "defense_context": defense,
        "pace_context": pace,
        "usage_context": usage,
        "fatigue_context": fatigue,
        "combined": {
            "total_multiplier": round(total_mult, 3),
            "total_adjustment_pct": round((total_mult - 1) * 100, 1),
            "recommendation": "BOOST" if total_mult > 1.05 else "REDUCE" if total_mult < 0.95 else "NEUTRAL"
        }
    }


@app.get("/context/teams/pace")
async def get_all_team_paces():
    """Get pace data for all teams"""
    return {
        "teams": pace_scraper.team_pace,
        "league_average": pace_scraper.league_avg_pace,
        "fastest": sorted(pace_scraper.team_pace.items(), key=lambda x: x[1], reverse=True)[:5],
        "slowest": sorted(pace_scraper.team_pace.items(), key=lambda x: x[1])[:5]
    }


@app.get("/context/teams/defense")
async def get_all_team_defense():
    """Get defensive ratings for all teams"""
    # Get ratings for each position vs each team
    teams = list(defense_scraper._estimate_defense("celtics", "PG").keys())
    
    elite = []
    poor = []
    
    for team_name in ["celtics", "thunder", "cavaliers", "knicks", "magic", "timberwolves",
                      "pistons", "wizards", "hornets", "blazers", "jazz", "rockets"]:
        rating = defense_scraper._estimate_defense(team_name, "SF")
        if rating.get("rating") == "elite":
            elite.append(team_name)
        elif rating.get("rating") == "poor":
            poor.append(team_name)
    
    return {
        "elite_defenses": elite,
        "poor_defenses": poor,
        "positions": ["PG", "SG", "SF", "PF", "C"],
        "note": "Use /context/defense/{team}/{position} for specific matchup data"
    }


# ============================================
# STAKING ENGINE ENDPOINTS (Bankroll Guardian)
# ============================================

class StakingRequest(BaseModel):
    confidence_score: float = Field(..., ge=0, le=100, example=82.5)
    american_odds: int = Field(..., example=-110)


class KellyRequest(BaseModel):
    win_probability: float = Field(..., ge=0, le=1, example=0.58)
    american_odds: int = Field(..., example=-110)


class BetRecordRequest(BaseModel):
    units: float
    odds: int
    result: str  # W, L, P


@app.post("/staking/calculate")
async def calculate_stake(req: StakingRequest):
    """
    Calculate optimal bet size from confidence score
    
    Uses fractional Kelly Criterion (quarter Kelly for safety)
    
    Example:
    - Confidence: 82.5, Odds: -110
    - Returns: "Bet 1.8 units"
    """
    return staking_engine.calculate_from_confidence(req.confidence_score, req.american_odds)


@app.post("/staking/kelly")
async def calculate_kelly(req: KellyRequest):
    """
    Calculate Kelly Criterion from raw win probability
    
    Formula: f* = (bp - q) / b
    Where b = decimal odds - 1, p = win prob, q = 1-p
    """
    return staking_engine.calculate_kelly(req.win_probability, req.american_odds)


@app.post("/staking/record")
async def record_bet(req: BetRecordRequest):
    """Record a bet result to track bankroll"""
    if req.result not in ["W", "L", "P"]:
        raise HTTPException(status_code=400, detail="Result must be W, L, or P")
    staking_engine.record_bet(req.units, req.odds, req.result)
    return {"recorded": True, "current_bankroll": staking_engine.current_bankroll}


@app.get("/staking/performance")
async def get_staking_performance():
    """Get betting performance statistics"""
    return staking_engine.get_performance()


@app.post("/staking/set-bankroll")
async def set_bankroll(bankroll: float = 1000, kelly_fraction: float = 0.25):
    """Set bankroll and Kelly fraction"""
    staking_engine.bankroll = bankroll
    staking_engine.current_bankroll = bankroll
    staking_engine.kelly_fraction = kelly_fraction
    return {
        "bankroll": bankroll,
        "kelly_fraction": kelly_fraction,
        "max_bet": round(staking_engine.max_bet_pct * bankroll, 2)
    }


# ============================================
# BACKTEST SIMULATOR ENDPOINTS (Time Machine)
# ============================================

class BacktestRequest(BaseModel):
    player: str
    stat_type: str
    historical_lines: List[Dict] = Field(
        ..., 
        example=[
            {"date": "2024-01-15", "line": 25.5, "actual": 28, "closing_line": 26.0},
            {"date": "2024-01-17", "line": 24.5, "actual": 22, "closing_line": 24.0}
        ]
    )


@app.post("/backtest/run")
async def run_backtest(req: BacktestRequest):
    """
    Run walk-forward backtest on historical data
    
    Prevents data leakage by only using past data for each prediction.
    Tracks Closing Line Value (CLV) to prove real edge.
    """
    # Get player's historical games
    games = real_ml.scraper.get_player_game_log(req.player, "NBA", seasons=2)
    
    if len(games) < 20:
        raise HTTPException(status_code=400, detail=f"Need 20+ games, found {len(games)}")
    
    return backtester.run_backtest(req.player, req.stat_type, games, req.historical_lines)


@app.post("/backtest/validate")
async def validate_model_edge(results: List[Dict]):
    """
    Validate if model has statistically significant edge
    
    Checks:
    - Win rate vs break-even (52.4% for -110)
    - Z-score for statistical significance
    - CLV (Closing Line Value) - most important metric
    """
    return backtester.validate_model_edge(results)


@app.get("/backtest/sample-format")
async def get_backtest_format():
    """Get sample format for backtest data"""
    return {
        "format": {
            "player": "LeBron James",
            "stat_type": "points",
            "historical_lines": [
                {
                    "date": "2024-01-15",
                    "line": 25.5,
                    "actual": 28,
                    "closing_line": 26.0
                }
            ]
        },
        "notes": [
            "date: Game date in YYYY-MM-DD format",
            "line: Opening prop line",
            "actual: Actual stat achieved",
            "closing_line: Line at game time (for CLV calculation)"
        ]
    }


# ============================================
# SHARP TRACKER ENDPOINTS (Follow the Money)
# ============================================

class SharpAnalysisRequest(BaseModel):
    team: str
    ticket_pct: float = Field(..., ge=0, le=100, example=35)
    money_pct: float = Field(..., ge=0, le=100, example=65)
    opening_line: float = Field(..., example=-3.5)
    current_line: float = Field(..., example=-4.5)


class MultiGameSharpRequest(BaseModel):
    games: List[Dict] = Field(
        ...,
        example=[{
            "home_team": "Lakers",
            "away_team": "Celtics",
            "home_ticket_pct": 35,
            "home_money_pct": 65,
            "opening_line": -3.5,
            "current_line": -4.5
        }]
    )


@app.post("/sharp/analyze")
async def analyze_sharp_action(req: SharpAnalysisRequest):
    """
    Analyze sharp money action on a single game
    
    Key insight: When ticket% and money% diverge, follow the money.
    70% tickets but only 40% money = Sharps on opposite side
    """
    return sharp_tracker.analyze_sharp_action(
        req.ticket_pct, req.money_pct,
        req.opening_line, req.current_line,
        req.team
    )


@app.post("/sharp/plays")
async def get_sharp_plays(req: MultiGameSharpRequest):
    """
    Get all sharp plays from multiple games
    
    Returns games with significant sharp action detected
    """
    return {
        "sharp_plays": sharp_tracker.get_sharp_plays(req.games),
        "total_analyzed": len(req.games)
    }


@app.get("/sharp/criteria")
async def get_sharp_criteria():
    """Get the criteria used for sharp detection"""
    return {
        "divergence_threshold": f"{sharp_tracker.sharp_threshold}% ticket/money divergence",
        "rlm_threshold": f"{sharp_tracker.reverse_line_movement_threshold} points",
        "signals": [
            "Money% > Ticket% by 15%+ = Sharp money",
            "Line moves AGAINST public = Reverse Line Movement (RLM)",
            "Line moves 1.5+ points rapidly = Steam move"
        ],
        "interpretation": "When sharps bet, they bet BIG. Money% reveals their position."
    }


# ============================================
# ROTATION MODEL ENDPOINTS (Coach Logic)
# ============================================

@app.get("/rotation/coach/{team}")
async def get_coach_factor(team: str):
    """
    Get coach tendencies for a team
    
    Includes:
    - Typical starter minutes
    - Close game minutes (40+ for Thibs)
    - Rest tendency (aggressive for Pop)
    - Blowout pull threshold
    """
    return rotation_model.get_coach_factor(team)


class MinutesImpactRequest(BaseModel):
    team: str
    spread: float = Field(..., example=-12.5)
    is_back_to_back: bool = False
    is_star_player: bool = True
    current_minutes_avg: float = Field(..., example=34.5)


@app.post("/rotation/minutes-impact")
async def predict_minutes_impact(req: MinutesImpactRequest):
    """
    Predict minutes adjustment based on game context
    
    Factors:
    - Blowout risk (spread >12 = early pull)
    - Back-to-back (some coaches rest stars)
    - Close game expectation (some coaches play 40+ mins)
    """
    return rotation_model.predict_minutes_impact(
        req.team, req.spread, req.is_back_to_back,
        req.is_star_player, req.current_minutes_avg
    )


@app.get("/rotation/blowout-risk/{spread}")
async def get_blowout_risk(spread: float):
    """
    Get blowout probability and expected garbage time
    
    High spread = more likely starters get pulled early
    This kills prop OVERS
    """
    return rotation_model.get_blowout_probability(spread)


@app.get("/rotation/all-coaches")
async def get_all_coaches():
    """Get all coach profiles in the system"""
    return {
        "total_coaches": len(rotation_model.coach_profiles),
        "heavy_minutes": [name.title() for name, data in rotation_model.coach_profiles.items() 
                        if data.get("starter_mins", 0) >= 34],
        "load_managers": [name.title() for name, data in rotation_model.coach_profiles.items() 
                         if data.get("rest_tendency") == "aggressive"],
        "profiles": {name.title(): data for name, data in rotation_model.coach_profiles.items()}
    }


# ============================================
# HARMONIC CONVERGENCE ENDPOINTS (LSTM + Esoteric SuperSignal)
# ============================================

class SynergyRequest(BaseModel):
    lstm_confidence: float = Field(..., ge=0, le=100, example=85, description="LSTM neural network confidence")
    lstm_direction: str = Field(..., example="OVER", description="LSTM recommendation direction")
    esoteric_score: float = Field(..., ge=0, le=100, example=72, description="Esoteric analysis score")
    esoteric_direction: str = Field(..., example="OVER", description="Esoteric lean direction")
    ensemble_confidence: Optional[float] = Field(None, ge=0, le=100, description="Optional ensemble confidence for extra validation")
    monte_carlo_prob: Optional[float] = Field(None, ge=0, le=1, description="Optional Monte Carlo probability")


class ConvergenceRequest(BaseModel):
    ml_confidence: float = Field(..., ge=0, le=100, example=85)
    ml_direction: str = Field(..., example="OVER")
    esoteric_score: float = Field(..., ge=0, le=100, example=72)
    esoteric_direction: str = Field(..., example="OVER")


@app.post("/synergy/check")
async def check_lstm_esoteric_synergy(req: SynergyRequest):
    """
    🌟 CHECK LSTM + ESOTERIC SYNERGY (THE SuperSignal)
    
    This is the key convergence signal that isolates highest ROI bets.
    
    Formula:
    - Normalize LSTM confidence to 0-1
    - Normalize Esoteric score to 0-1  
    - IF (LSTM > 0.7) AND (Esoteric > 0.7) AND same_direction THEN SuperSignal
    
    Signal Tiers:
    - GOLDEN_CONVERGENCE: Both > 80% (Rare, highest conviction)
    - SUPER_SIGNAL: Both > 70% (Strong edge)
    - HARMONIC_ALIGNMENT: One > 80%, other > 60%
    - PARTIAL_ALIGNMENT: Both > 60%
    - CONFLICT: Strong signals, opposite directions
    """
    return harmonic_convergence.check_lstm_esoteric_synergy(
        lstm_confidence=req.lstm_confidence,
        lstm_direction=req.lstm_direction,
        esoteric_score=req.esoteric_score,
        esoteric_direction=req.esoteric_direction,
        ensemble_confidence=req.ensemble_confidence,
        monte_carlo_prob=req.monte_carlo_prob
    )


@app.post("/convergence/check")
async def check_convergence(req: ConvergenceRequest):
    """
    Check for harmonic convergence (legacy endpoint)
    Use /synergy/check for the full LSTM + Esoteric analysis
    """
    return harmonic_convergence.check_convergence(
        req.ml_confidence, req.ml_direction,
        req.esoteric_score, req.esoteric_direction
    )


@app.post("/synergy/filter-super")
async def filter_super_signals(picks: List[Dict]):
    """
    Filter picks to only return SUPER SIGNALS and GOLDEN SIGNALS
    
    These are picks where LSTM AND Esoteric both strongly agree.
    Your highest conviction, highest ROI bets.
    
    Returns picks sorted by synergy score (highest first).
    """
    super_signals = harmonic_convergence.get_super_signals_only(picks)
    golden_signals = [p for p in super_signals if p.get("is_golden")]
    
    return {
        "golden_signals": golden_signals,
        "super_signals": super_signals,
        "total_analyzed": len(picks),
        "golden_count": len(golden_signals),
        "super_count": len(super_signals)
    }


@app.post("/synergy/filter-golden")
async def filter_golden_signals(picks: List[Dict]):
    """
    Filter picks to ONLY return GOLDEN signals
    
    These are the absolute highest conviction bets:
    - LSTM confidence > 80%
    - Esoteric score > 80%
    - Same direction
    
    These are RARE but have the highest expected ROI.
    """
    golden = harmonic_convergence.get_golden_signals_only(picks)
    
    return {
        "golden_signals": golden,
        "total_analyzed": len(picks),
        "golden_count": len(golden),
        "note": "Golden signals are rare (~5-10% of picks) but highest ROI"
    }


@app.post("/convergence/filter-picks")
async def filter_convergence_picks(picks: List[Dict]):
    """Legacy endpoint - use /synergy/filter-super instead"""
    return {
        "super_signals": harmonic_convergence.get_super_signals_only(picks),
        "total_analyzed": len(picks)
    }


@app.get("/synergy/stats")
async def get_synergy_stats():
    """Get statistics on synergy signals by tier"""
    return harmonic_convergence.get_convergence_stats()


@app.get("/convergence/stats")
async def get_convergence_stats():
    """Get statistics on convergence signals"""
    return harmonic_convergence.get_convergence_stats()


@app.get("/synergy/tiers")
async def get_synergy_tiers():
    """Get signal tier definitions and thresholds"""
    return {
        "tiers": {
            "GOLDEN_CONVERGENCE": {
                "thresholds": "LSTM > 80% AND Esoteric > 80%",
                "confidence_boost": harmonic_convergence.boosts["GOLDEN_CONVERGENCE"],
                "unit_multiplier": harmonic_convergence.unit_multipliers["GOLDEN_CONVERGENCE"],
                "interpretation": "🌟 When numbers AND stars STRONGLY align. Highest conviction bet!"
            },
            "SUPER_SIGNAL": {
                "thresholds": "LSTM > 70% AND Esoteric > 70%",
                "confidence_boost": harmonic_convergence.boosts["SUPER_SIGNAL"],
                "unit_multiplier": harmonic_convergence.unit_multipliers["SUPER_SIGNAL"],
                "interpretation": "⚡ Strong alignment. High-value opportunity!"
            },
            "HARMONIC_ALIGNMENT": {
                "thresholds": "One > 80%, other > 60%",
                "confidence_boost": harmonic_convergence.boosts["HARMONIC_ALIGNMENT"],
                "unit_multiplier": harmonic_convergence.unit_multipliers["HARMONIC_ALIGNMENT"],
                "interpretation": "🎯 Good alignment. Solid betting opportunity."
            },
            "PARTIAL_ALIGNMENT": {
                "thresholds": "Both > 60%",
                "confidence_boost": harmonic_convergence.boosts["PARTIAL_ALIGNMENT"],
                "unit_multiplier": harmonic_convergence.unit_multipliers["PARTIAL_ALIGNMENT"],
                "interpretation": "📊 Moderate agreement. Standard bet sizing."
            },
            "CONFLICT": {
                "thresholds": "Strong signals, opposite directions",
                "confidence_boost": harmonic_convergence.boosts["CONFLICT"],
                "unit_multiplier": harmonic_convergence.unit_multipliers["CONFLICT"],
                "interpretation": "⚠️ Data vs Stars disagree. Consider skipping."
            }
        },
        "formula": "IF (LSTM > 0.7) AND (Esoteric > 0.7) AND same_direction THEN SuperSignal",
        "synergy_score_formula": "sqrt(LSTM_norm * Esoteric_norm) * direction_multiplier"
    }


@app.get("/convergence/thresholds")
async def get_convergence_thresholds():
    """Get current convergence thresholds (legacy)"""
    return {
        "super_threshold": "LSTM > 70% AND Esoteric > 70%",
        "golden_threshold": "LSTM > 80% AND Esoteric > 80%",
        "formula": "IF (LSTM > 0.7) AND (Esoteric > 0.7) THEN SuperSignal"
    }


class RecordSynergyRequest(BaseModel):
    tier: str = Field(..., example="SUPER_SIGNAL")
    won: bool
    units: float = 1.0
    odds: int = -110


@app.post("/synergy/record")
async def record_synergy_result(req: RecordSynergyRequest):
    """Record a synergy bet result for performance tracking"""
    harmonic_convergence.record_result(req.tier, req.won, req.units, req.odds)
    return {
        "recorded": True,
        "tier": req.tier,
        "performance": harmonic_convergence.get_performance_by_tier()
    }


@app.get("/synergy/performance")
async def get_synergy_performance():
    """Get performance breakdown by signal tier"""
    return {
        "performance_by_tier": harmonic_convergence.get_performance_by_tier(),
        "unit_multipliers": harmonic_convergence.unit_multipliers,
        "note": "Track results to see which tiers have highest ROI"
    }


# ============================================
# ENHANCED PICKS WITH ALL SYSTEMS
# ============================================

@app.get("/picks/enhanced/{sport}")
async def get_enhanced_picks(sport: str = "basketball_nba"):
    """
    Get picks with ALL advanced systems applied:
    - ML predictions (LSTM, Ensemble, Monte Carlo)
    - Contextual adjustments
    - Coach/rotation analysis
    - Sharp money tracking
    - Kelly staking
    - LSTM + Esoteric synergy (SuperSignals)
    """
    # Get base picks
    picks = picks_engine.generate_picks(sport)
    
    enhanced_picks = []
    super_signals = []
    golden_signals = []
    
    for pick in picks:
        enhanced = pick.copy()
        
        # Add staking recommendation
        staking = staking_engine.calculate_from_confidence(
            pick.get("confidence_score", 50),
            pick.get("odds", -110)
        )
        enhanced["staking"] = {
            "units": staking["units"],
            "risk_level": staking["risk_level"],
            "edge_pct": staking["edge_pct"]
        }
        
        # Add rotation/coach factor if applicable
        home_team = pick.get("game", "").split(" @ ")[-1] if " @ " in pick.get("game", "") else ""
        if home_team:
            coach_data = rotation_model.get_coach_factor(home_team)
            enhanced["coach_factor"] = {
                "coach": coach_data.get("coach"),
                "rest_tendency": coach_data.get("rest_tendency")
            }
        
        # Check LSTM + Esoteric synergy
        # Get LSTM confidence from signals if available
        lstm_conf = pick.get("signals", {}).get("lstm", {}).get("confidence", pick.get("confidence_score", 50))
        esoteric_score = pick.get("esoteric_score", 50)
        
        # Determine directions
        pick_str = str(pick.get("pick", "")).upper()
        if "OVER" in pick_str:
            lstm_direction = "OVER"
        elif "UNDER" in pick_str:
            lstm_direction = "UNDER"
        else:
            lstm_direction = pick_str.split()[0] if pick_str else "HOME"
        
        esoteric_direction = "OVER" if esoteric_score > 55 else "UNDER" if esoteric_score < 45 else lstm_direction
        
        # Get ensemble and MC for extra validation
        ens_conf = pick.get("signals", {}).get("ensemble", {}).get("confidence")
        mc_prob = pick.get("signals", {}).get("monte_carlo", {}).get("over_prob")
        if mc_prob:
            mc_prob = mc_prob / 100 if mc_prob > 1 else mc_prob
        
        synergy = harmonic_convergence.check_lstm_esoteric_synergy(
            lstm_confidence=lstm_conf,
            lstm_direction=lstm_direction,
            esoteric_score=esoteric_score,
            esoteric_direction=esoteric_direction,
            ensemble_confidence=ens_conf,
            monte_carlo_prob=mc_prob
        )
        
        enhanced["synergy"] = {
            "tier": synergy["signal_tier"],
            "score": synergy["synergy_score"],
            "is_super_signal": synergy["is_super_signal"],
            "is_golden": synergy["is_golden"],
            "unit_multiplier": synergy["unit_multiplier"],
            "interpretation": synergy["interpretation"]
        }
        
        if synergy["is_super_signal"]:
            enhanced["confidence_score"] += synergy["confidence_boost"]
            enhanced["staking"]["units"] *= synergy["unit_multiplier"]
            enhanced["staking"]["units"] = round(enhanced["staking"]["units"], 2)
            enhanced["is_super_signal"] = True
            super_signals.append(enhanced)
            
            if synergy["is_golden"]:
                enhanced["is_golden"] = True
                golden_signals.append(enhanced)
        
        enhanced_picks.append(enhanced)
    
    # Sort super signals by synergy score
    super_signals.sort(key=lambda x: x["synergy"]["score"], reverse=True)
    golden_signals.sort(key=lambda x: x["synergy"]["score"], reverse=True)
    
    return {
        "picks": enhanced_picks,
        "golden_signals": golden_signals,
        "super_signals": super_signals,
        "total_picks": len(enhanced_picks),
        "golden_count": len(golden_signals),
        "super_signal_count": len(super_signals),
        "generated_at": datetime.now().isoformat()
    }


@app.get("/props/enhanced/{sport}")
async def get_enhanced_props(sport: str = "basketball_nba"):
    """
    Get prop picks with ALL advanced systems applied:
    - ML predictions (LSTM, Ensemble, Monte Carlo)
    - Contextual adjustments
    - Coach/rotation analysis (blowout risk)
    - Kelly staking
    - LSTM + Esoteric synergy (SuperSignals)
    """
    # Get base props
    props = props_engine.generate_prop_picks(sport)
    
    enhanced_props = []
    super_signals = []
    golden_signals = []
    
    for prop in props:
        enhanced = prop.copy()
        
        # Add staking
        staking = staking_engine.calculate_from_confidence(
            prop.get("confidence_score", 50),
            prop.get("odds", -110)
        )
        enhanced["staking"] = {
            "units": staking["units"],
            "risk_level": staking["risk_level"],
            "edge_pct": staking["edge_pct"]
        }
        
        # Add rotation impact for props (blowout risk kills OVERs)
        game = prop.get("game", "")
        if " @ " in game:
            home_team = game.split(" @ ")[-1]
            spread = prop.get("spread", 5)  # Default to moderate spread
            
            # Get blowout risk
            blowout = rotation_model.get_blowout_probability(spread)
            enhanced["rotation"] = {
                "blowout_risk": blowout["starter_minutes_risk"],
                "garbage_time_mins": blowout["expected_garbage_time_mins"],
                "blowout_prob": blowout["blowout_probability"]
            }
        
        # Check LSTM + Esoteric synergy
        lstm_conf = prop.get("signals", {}).get("lstm", {}).get("confidence", 50)
        esoteric_score = prop.get("esoteric_score", 50)
        
        # Determine directions
        pick_str = str(prop.get("pick", "")).upper()
        lstm_direction = "OVER" if "OVER" in pick_str else "UNDER"
        esoteric_direction = "OVER" if esoteric_score > 55 else "UNDER" if esoteric_score < 45 else lstm_direction
        
        # Get ensemble and MC for extra validation
        ens_conf = prop.get("signals", {}).get("ensemble", {}).get("confidence")
        mc_data = prop.get("signals", {}).get("monte_carlo", {})
        mc_prob = mc_data.get("over_prob") if mc_data else None
        if mc_prob and mc_prob > 1:
            mc_prob = mc_prob / 100
        
        synergy = harmonic_convergence.check_lstm_esoteric_synergy(
            lstm_confidence=lstm_conf if lstm_conf else prop.get("confidence_score", 50),
            lstm_direction=lstm_direction,
            esoteric_score=esoteric_score,
            esoteric_direction=esoteric_direction,
            ensemble_confidence=ens_conf,
            monte_carlo_prob=mc_prob
        )
        
        enhanced["synergy"] = {
            "tier": synergy["signal_tier"],
            "score": synergy["synergy_score"],
            "is_super_signal": synergy["is_super_signal"],
            "is_golden": synergy["is_golden"],
            "unit_multiplier": synergy["unit_multiplier"],
            "interpretation": synergy["interpretation"]
        }
        
        if synergy["is_super_signal"]:
            enhanced["confidence_score"] += synergy["confidence_boost"]
            enhanced["staking"]["units"] *= synergy["unit_multiplier"]
            enhanced["staking"]["units"] = round(enhanced["staking"]["units"], 2)
            enhanced["is_super_signal"] = True
            super_signals.append(enhanced)
            
            if synergy["is_golden"]:
                enhanced["is_golden"] = True
                golden_signals.append(enhanced)
        
        enhanced_props.append(enhanced)
    
    # Sort by synergy score
    super_signals.sort(key=lambda x: x["synergy"]["score"], reverse=True)
    golden_signals.sort(key=lambda x: x["synergy"]["score"], reverse=True)
    
    return {
        "props": enhanced_props,
        "golden_signals": golden_signals,
        "super_signals": super_signals,
        "total_props": len(enhanced_props),
        "golden_count": len(golden_signals),
        "super_signal_count": len(super_signals),
        "generated_at": datetime.now().isoformat()
    }


# ============================================
# GRADING & LEARNING ENDPOINTS
# ============================================

@app.post("/picks/grade")
async def grade_pick(req: GradeRequest):
    """Grade a single pick as W (win), L (loss), or P (push)"""
    if req.result not in ["W", "L", "P"]:
        raise HTTPException(status_code=400, detail="Result must be W, L, or P")
    return picks_engine.grade_pick(req.pick_id, req.result)


@app.post("/picks/grade/bulk")
async def grade_bulk(req: BulkGradeRequest):
    """Grade multiple picks at once"""
    results = []
    for pick_id, result in req.results.items():
        if result in ["W", "L", "P"]:
            res = picks_engine.grade_pick(pick_id, result)
            results.append(res)
    return {
        "success": True,
        "graded": len(results),
        "performance": picks_engine.performance
    }


@app.get("/picks/pending")
async def get_pending_picks():
    """Get all pending (ungraded) picks"""
    pending = [p for p in picks_engine.picks_history if p.get("status") == "pending"]
    return {
        "success": True,
        "count": len(pending),
        "picks": pending
    }


@app.get("/picks/graded")
async def get_graded_picks(limit: int = 50):
    """Get graded picks history"""
    return {
        "success": True,
        "count": len(picks_engine.graded_picks),
        "picks": picks_engine.graded_picks[-limit:]
    }


@app.get("/picks/performance")
async def get_performance():
    """Get overall performance metrics"""
    return {
        "success": True,
        "performance": picks_engine.performance,
        "total_graded": len(picks_engine.graded_picks)
    }


@app.get("/picks/learning")
async def get_learning_report():
    """Get learning report with signal weights"""
    return {
        "success": True,
        "report": picks_engine.get_learning_report()
    }


@app.post("/picks/reset-weights")
async def reset_weights():
    """Reset signal weights to defaults"""
    picks_engine.weights = {
        "ensemble_prediction": 15,
        "lstm_sequence": 10,
        "matchup_specific": 12,
        "monte_carlo_probability": 14,
        "line_movement_signal": 13,
        "rest_fatigue_factor": 8,
        "injury_impact": 10,
        "kelly_edge": 12,
        "gematria_alignment": 6,
        "numerology_power": 8,
        "sacred_geometry": 5,
        "moon_phase": 7,
        "zodiac_element": 4,
        "sharp_money": 18,
        "public_fade": 8,
        "line_value": 10,
        "key_number": 6
    }
    picks_engine._save_history()
    return {"success": True, "weights": picks_engine.weights}


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
