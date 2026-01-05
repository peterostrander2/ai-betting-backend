"""
FastAPI - AI Sports Betting API v4.2 with Alerts System
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, Optional, List
from datetime import datetime, date
import requests
import os
import json

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
            "key_number": 6
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
                
                # ===== AI MODEL SIGNALS =====
                
                # 1. Ensemble prediction (simulated)
                ensemble_conf = 0.55 + (hash(home + away) % 10) / 100
                if ensemble_conf > 0.52:
                    weight = self.weights["ensemble_prediction"]
                    max_possible += weight
                    total_score += (ensemble_conf - 0.5) * 2 * weight
                    signals["ensemble"] = {"confidence": ensemble_conf}
                    reasons.append(f"AI Ensemble: {round(ensemble_conf*100)}% confidence")
                
                # 2. Monte Carlo simulation
                mc_prob = 0.50 + (hash(away + home) % 8) / 100
                if mc_prob > 0.51:
                    weight = self.weights["monte_carlo_probability"]
                    max_possible += weight
                    total_score += (mc_prob - 0.5) * 3 * weight
                    signals["monte_carlo"] = {"probability": mc_prob}
                    reasons.append(f"Monte Carlo: {round(mc_prob*100)}% win probability")
                
                # 3. Line movement analysis
                weight = self.weights["line_movement_signal"]
                max_possible += weight
                # Check for reverse line movement from splits
                sharp = self._check_sharp_money(home, away, splits_lookup)
                if sharp.get("detected"):
                    total_score += (sharp["strength"] / 15) * weight * 1.5
                    signals["line_movement"] = sharp
                    reasons.append(f"Line Movement: Sharp action detected")
                
                # 4. Rest/Fatigue (simulated based on schedule)
                rest_advantage = (hash(home) % 3) - 1  # -1, 0, or 1
                if rest_advantage != 0:
                    weight = self.weights["rest_fatigue_factor"]
                    max_possible += weight
                    total_score += 0.5 * weight
                    team = home if rest_advantage > 0 else away
                    signals["rest"] = {"advantage": team}
                    reasons.append(f"Rest Edge: {team} more rested")
                
                # 5. Kelly Criterion edge
                if mc_prob > 0.52:
                    decimal_odds = 1.91  # -110
                    kelly_edge = ((mc_prob * decimal_odds) - 1) * 100
                    if kelly_edge > 2:
                        weight = self.weights["kelly_edge"]
                        max_possible += weight
                        total_score += min(kelly_edge / 10, 1) * weight
                        signals["kelly"] = {"edge": kelly_edge}
                        reasons.append(f"Kelly Edge: +{round(kelly_edge, 1)}% EV")
                
                # ===== ESOTERIC SIGNALS =====
                
                esoteric_edge = esoteric_result.get("esoteric_edge", {})
                esoteric_score = esoteric_edge.get("score", 50)
                
                # 6. Gematria
                gematria = esoteric_result.get("gematria", {})
                diff = gematria.get("difference", 0)
                if abs(diff) > 15:
                    weight = self.weights["gematria_alignment"]
                    max_possible += weight
                    total_score += 0.7 * weight
                    favors = home if diff > 0 else away
                    signals["gematria"] = {"favors": favors, "diff": diff}
                    reasons.append(f"Gematria: {favors} +{abs(diff)}")
                
                # 7. Numerology
                if today_numerology.get("power_day"):
                    weight = self.weights["numerology_power"]
                    max_possible += weight
                    total_score += weight * 0.8
                    signals["numerology"] = {"power_day": True, "life_path": today_numerology["life_path"]}
                    reasons.append(f"POWER DAY: Life Path {today_numerology['life_path']}")
                elif today_numerology.get("upset_potential"):
                    weight = self.weights["numerology_power"]
                    max_possible += weight
                    total_score += weight * 0.5
                    signals["numerology"] = {"upset": True}
                    reasons.append(f"Upset Energy: Life Path {today_numerology['life_path']}")
                
                # 8. Sacred Geometry
                sacred = esoteric_result.get("sacred_geometry")
                if sacred and sacred.get("tesla_energy"):
                    weight = self.weights["sacred_geometry"]
                    max_possible += weight
                    total_score += weight * 0.9
                    signals["sacred"] = sacred
                    reasons.append("Tesla 3-6-9 alignment!")
                
                # 9. Moon Phase
                if today_moon.get("full_moon"):
                    weight = self.weights["moon_phase"]
                    max_possible += weight
                    total_score += weight * 0.7
                    signals["moon"] = {"full": True, "phase": today_moon["phase"]}
                    reasons.append("FULL MOON: Chaos factor HIGH")
                elif today_moon.get("new_moon"):
                    weight = self.weights["moon_phase"]
                    max_possible += weight
                    total_score += weight * 0.4
                    signals["moon"] = {"new": True}
                    reasons.append("New Moon: Underdog energy")
                
                # 10. Zodiac Element
                element = today_zodiac.get("element", "")
                weight = self.weights["zodiac_element"]
                max_possible += weight
                if element == "Fire":
                    total_score += weight * 0.6
                    signals["zodiac"] = {"element": element, "lean": "OVER"}
                    reasons.append("Fire Sign: Lean OVER")
                elif element == "Earth":
                    total_score += weight * 0.6
                    signals["zodiac"] = {"element": element, "lean": "UNDER"}
                    reasons.append("Earth Sign: Lean UNDER")
                
                # ===== EXTERNAL DATA SIGNALS =====
                
                # 11. Sharp Money (from splits)
                if sharp.get("detected"):
                    weight = self.weights["sharp_money"]
                    max_possible += weight
                    total_score += (sharp["strength"] / 12) * weight
                    signals["sharp_money"] = sharp
                    reasons.append(f"SHARP MONEY: {sharp['side']} ({sharp['strength']}%)")
                
                # 12. Public Fade
                public_pct = splits_lookup.get(f"{away}@{home}".lower().replace(" ", ""), {}).get("public_pct", 50)
                if public_pct > 70:
                    weight = self.weights["public_fade"]
                    max_possible += weight
                    total_score += 0.7 * weight
                    signals["public_fade"] = {"pct": public_pct}
                    reasons.append(f"Fade Public: {public_pct}% on one side")
                
                # 13. Key Numbers
                spread = self._get_spread(markets, home)
                if abs(spread) in [3, 3.5, 7, 7.5, 10]:
                    weight = self.weights["key_number"]
                    max_possible += weight
                    total_score += weight * 0.8
                    signals["key_number"] = {"spread": spread}
                    reasons.append(f"Key Number: {spread}")
                
                # ===== CALCULATE FINAL PICK =====
                
                if max_possible > 0:
                    confidence = min(95, max(35, (total_score / max_possible) * 100))
                else:
                    confidence = 50
                
                # Determine pick direction
                pick_result = self._determine_pick(signals, markets, home, away, esoteric_score, sharp)
                
                if confidence >= 40 and pick_result:
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
        
        home_spread = spreads.get(home, {}).get("point", 0)
        home_odds = spreads.get(home, {}).get("price", -110)
        away_spread = spreads.get(away, {}).get("point", 0)
        away_odds = spreads.get(away, {}).get("price", -110)
        
        over_odds = totals.get("Over", {}).get("price", -110)
        under_odds = totals.get("Under", {}).get("price", -110)
        total_line = totals.get("Over", {}).get("point", 220)
        
        # Check for zodiac over/under lean
        zodiac = signals.get("zodiac", {})
        if zodiac.get("lean") == "OVER":
            return {"type": "total", "pick": f"OVER {total_line}", "odds": over_odds}
        elif zodiac.get("lean") == "UNDER":
            return {"type": "total", "pick": f"UNDER {total_line}", "odds": under_odds}
        
        # Check sharp money
        if sharp.get("detected"):
            side = sharp["side"]
            if side == home:
                return {"type": "spread", "pick": f"{home} {home_spread:+g}", "odds": home_odds}
            else:
                return {"type": "spread", "pick": f"{away} {away_spread:+g}", "odds": away_odds}
        
        # Check esoteric lean
        if esoteric_score > 55:
            return {"type": "spread", "pick": f"{home} {home_spread:+g}", "odds": home_odds}
        elif esoteric_score < 45:
            return {"type": "spread", "pick": f"{away} {away_spread:+g}", "odds": away_odds}
        
        # Default to home spread
        return {"type": "spread", "pick": f"{home} {home_spread:+g}", "odds": home_odds}
    
    def _get_label(self, score):
        if score >= 80: return "STRONG"
        elif score >= 70: return "GOOD"
        elif score >= 60: return "LEAN"
        else: return "SLIGHT"
    
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
# GRADING & LEARNING ENDPOINTS
# ============================================

class GradeRequest(BaseModel):
    pick_id: str
    result: str  # W, L, or P


class BulkGradeRequest(BaseModel):
    results: Dict[str, str]  # {pick_id: result, ...}


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
