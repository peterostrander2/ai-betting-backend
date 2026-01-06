"""
FastAPI endpoints for AI sports betting predictions
v7.2.0 - Multi-Sport Context Layer + Officials + LSTM Brain + Auto-Grader + Live Data (NBA, NFL, MLB, NHL, NCAAB)
"""

import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime
from context_layer import (
    ContextGenerator, 
    DefensiveRankService, 
    PaceVectorService, 
    UsageVacuumService,
    ParkFactorService,
    OfficialsService,
    SUPPORTED_SPORTS,
    SPORT_POSITIONS,
    SPORT_STAT_TYPES,
    LEAGUE_AVERAGES
)
from lstm_brain import LSTMBrain, MultiSportLSTMBrain, integrate_lstm_prediction
from auto_grader import AutoGrader, ContextFeatureCalculator, get_grader
from live_data_router import LiveDataRouter, live_data_router
from loguru import logger
import uvicorn

# Initialize LSTM Brain (sport-specific models)
lstm_brain_manager = MultiSportLSTMBrain()

# Initialize Auto-Grader (feedback loop)
auto_grader = get_grader()

app = FastAPI(
    title="AI Sports Betting API",
    description="Multi-Sport AI Predictions with Context Layer + Officials + LSTM Brain + Auto-Grader + Live Data (NBA, NFL, MLB, NHL, NCAAB)",
    version="7.2.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Live Data Router
app.include_router(live_data_router)

# ============================================
# ESOTERIC MODELS (The "Magic")
# ============================================

class GematriaCalculator:
    """Hebrew numerology - maps letters to numbers, finds patterns."""
    
    HEBREW_VALUES = {
        'a': 1, 'b': 2, 'c': 3, 'd': 4, 'e': 5, 'f': 6, 'g': 7, 'h': 8, 'i': 9,
        'j': 10, 'k': 20, 'l': 30, 'm': 40, 'n': 50, 'o': 60, 'p': 70, 'q': 80, 'r': 90,
        's': 100, 't': 200, 'u': 300, 'v': 400, 'w': 500, 'x': 600, 'y': 700, 'z': 800
    }
    
    @classmethod
    def calculate_value(cls, text: str) -> int:
        """Calculate gematria value of a string."""
        total = sum(cls.HEBREW_VALUES.get(c.lower(), 0) for c in text if c.isalpha())
        return total
    
    @classmethod
    def reduce_to_single(cls, value: int) -> int:
        """Reduce to single digit (1-9)."""
        while value > 9:
            value = sum(int(d) for d in str(value))
        return value
    
    @classmethod
    def analyze(cls, player_name: str, opponent: str, line: float) -> Dict:
        """Full gematria analysis for a matchup."""
        player_val = cls.calculate_value(player_name)
        player_reduced = cls.reduce_to_single(player_val)
        opponent_val = cls.calculate_value(opponent)
        opponent_reduced = cls.reduce_to_single(opponent_val)
        line_reduced = cls.reduce_to_single(int(abs(line * 10)))
        
        # Power numbers: 1, 3, 7, 9 are traditionally favorable
        power_numbers = {1, 3, 7, 9}
        player_power = player_reduced in power_numbers
        alignment = player_reduced == line_reduced
        
        signal = "NEUTRAL"
        if player_power and alignment:
            signal = "STRONG_OVER"
        elif player_power:
            signal = "LEAN_OVER"
        elif alignment:
            signal = "LEAN_UNDER"
        
        return {
            "player_gematria": player_val,
            "player_reduced": player_reduced,
            "opponent_gematria": opponent_val,
            "opponent_reduced": opponent_reduced,
            "line_reduced": line_reduced,
            "is_power_number": player_power,
            "is_aligned": alignment,
            "signal": signal,
            "confidence": 0.65 if signal.startswith("STRONG") else 0.55 if signal.startswith("LEAN") else 0.50
        }


class NumerologyEngine:
    """Birth dates, jersey numbers, game dates - life path analysis."""
    
    MASTER_NUMBERS = {11, 22, 33}
    LUCKY_NUMBERS = {3, 7, 9}
    
    @classmethod
    def calculate_life_path(cls, birth_date: str) -> int:
        """Calculate life path number from birth date (YYYY-MM-DD)."""
        try:
            digits = [int(d) for d in birth_date if d.isdigit()]
            total = sum(digits)
            while total > 9 and total not in cls.MASTER_NUMBERS:
                total = sum(int(d) for d in str(total))
            return total
        except:
            return 5  # Default neutral
    
    @classmethod
    def analyze_game_date(cls, game_date: datetime) -> Dict:
        """Analyze game date numerology."""
        day_num = game_date.day % 9 or 9
        month_num = game_date.month % 9 or 9
        combined = (day_num + month_num) % 9 or 9
        
        return {
            "day_number": day_num,
            "month_number": month_num,
            "combined": combined,
            "is_lucky_day": day_num in cls.LUCKY_NUMBERS,
            "is_master_day": game_date.day in cls.MASTER_NUMBERS
        }
    
    @classmethod
    def analyze(cls, player_name: str, jersey_number: int, game_date: datetime, line: float) -> Dict:
        """Full numerology analysis."""
        date_analysis = cls.analyze_game_date(game_date)
        jersey_reduced = jersey_number % 9 or 9
        line_int = int(abs(line))
        line_reduced = line_int % 9 or 9
        
        # Check alignments
        jersey_date_align = jersey_reduced == date_analysis["day_number"]
        jersey_line_align = jersey_reduced == line_reduced
        
        signal = "NEUTRAL"
        if jersey_date_align and date_analysis["is_lucky_day"]:
            signal = "STRONG_OVER"
        elif jersey_date_align or jersey_line_align:
            signal = "LEAN_OVER"
        elif date_analysis["is_master_day"]:
            signal = "LEAN_OVER"
        
        return {
            "jersey_number": jersey_number,
            "jersey_reduced": jersey_reduced,
            "date_analysis": date_analysis,
            "line_reduced": line_reduced,
            "jersey_date_alignment": jersey_date_align,
            "jersey_line_alignment": jersey_line_align,
            "signal": signal,
            "confidence": 0.62 if signal.startswith("STRONG") else 0.54 if signal.startswith("LEAN") else 0.50
        }


class SacredGeometryAnalyzer:
    """Fibonacci, golden ratio, pi - patterns in lines and stats."""
    
    FIBONACCI = [1, 2, 3, 5, 8, 13, 21, 34, 55, 89]
    PHI = 1.618033988749895  # Golden ratio
    PI = 3.14159265358979
    
    @classmethod
    def is_fibonacci_adjacent(cls, value: float, tolerance: float = 0.5) -> bool:
        """Check if value is close to a Fibonacci number."""
        return any(abs(value - f) < tolerance for f in cls.FIBONACCI)
    
    @classmethod
    def golden_ratio_check(cls, a: float, b: float) -> bool:
        """Check if ratio approximates golden ratio."""
        if b == 0:
            return False
        ratio = max(a, b) / min(a, b) if min(a, b) > 0 else 0
        return abs(ratio - cls.PHI) < 0.15
    
    @classmethod
    def analyze(cls, spread: float, total: float, line: float, player_avg: float) -> Dict:
        """Full sacred geometry analysis."""
        spread_fib = cls.is_fibonacci_adjacent(abs(spread))
        line_fib = cls.is_fibonacci_adjacent(line)
        total_fib = cls.is_fibonacci_adjacent(total / 10)  # Scale down
        
        avg_line_golden = cls.golden_ratio_check(player_avg, line) if player_avg > 0 else False
        spread_total_golden = cls.golden_ratio_check(abs(spread), total / 10) if spread != 0 else False
        
        alignments = sum([spread_fib, line_fib, total_fib, avg_line_golden, spread_total_golden])
        
        signal = "NEUTRAL"
        if alignments >= 3:
            signal = "STRONG_ALIGNMENT"
        elif alignments >= 2:
            signal = "MODERATE_ALIGNMENT"
        elif alignments >= 1:
            signal = "WEAK_ALIGNMENT"
        
        return {
            "spread_fibonacci": spread_fib,
            "line_fibonacci": line_fib,
            "total_fibonacci": total_fib,
            "avg_line_golden_ratio": avg_line_golden,
            "spread_total_golden_ratio": spread_total_golden,
            "total_alignments": alignments,
            "signal": signal,
            "confidence": 0.60 + (alignments * 0.05)
        }


class AstrologyTracker:
    """Moon phases, zodiac, planetary alignments."""
    
    ZODIAC_SIGNS = [
        "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
        "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
    ]
    
    MOON_PHASES = ["New Moon", "Waxing Crescent", "First Quarter", "Waxing Gibbous",
                   "Full Moon", "Waning Gibbous", "Last Quarter", "Waning Crescent"]
    
    # Fire signs favor OVER, Earth signs favor UNDER, Air/Water neutral
    FIRE_SIGNS = {"Aries", "Leo", "Sagittarius"}
    EARTH_SIGNS = {"Taurus", "Virgo", "Capricorn"}
    
    @classmethod
    def get_moon_phase(cls, game_date: datetime) -> str:
        """Approximate moon phase based on date."""
        # Simple approximation: lunar cycle ~29.5 days
        days_since_new = (game_date - datetime(2024, 1, 11)).days % 30  # Jan 11, 2024 was new moon
        phase_index = int(days_since_new / 3.75) % 8
        return cls.MOON_PHASES[phase_index]
    
    @classmethod
    def get_sun_sign(cls, game_date: datetime) -> str:
        """Get zodiac sign for date."""
        day = game_date.day
        month = game_date.month
        
        zodiac_dates = [
            (1, 20, "Capricorn"), (2, 19, "Aquarius"), (3, 20, "Pisces"),
            (4, 20, "Aries"), (5, 21, "Taurus"), (6, 21, "Gemini"),
            (7, 22, "Cancer"), (8, 23, "Leo"), (9, 23, "Virgo"),
            (10, 23, "Libra"), (11, 22, "Scorpio"), (12, 22, "Sagittarius")
        ]
        
        for m, d, sign in zodiac_dates:
            if month == m and day <= d:
                return sign
            if month == m - 1 or (month == 12 and m == 1):
                return zodiac_dates[(zodiac_dates.index((m, d, sign)) - 1) % 12][2]
        return "Capricorn"
    
    @classmethod
    def analyze(cls, game_date: datetime, player_birth_date: Optional[str] = None) -> Dict:
        """Full astrology analysis."""
        moon_phase = cls.get_moon_phase(game_date)
        sun_sign = cls.get_sun_sign(game_date)
        
        # Full moon = high energy = OVER tendency
        # New moon = low energy = UNDER tendency
        moon_signal = "NEUTRAL"
        if moon_phase == "Full Moon":
            moon_signal = "STRONG_OVER"
        elif moon_phase in ["Waxing Gibbous", "First Quarter"]:
            moon_signal = "LEAN_OVER"
        elif moon_phase == "New Moon":
            moon_signal = "LEAN_UNDER"
        
        # Fire signs = action = OVER
        zodiac_signal = "NEUTRAL"
        if sun_sign in cls.FIRE_SIGNS:
            zodiac_signal = "LEAN_OVER"
        elif sun_sign in cls.EARTH_SIGNS:
            zodiac_signal = "LEAN_UNDER"
        
        # Combine signals
        combined_signal = "NEUTRAL"
        if moon_signal.endswith("OVER") and zodiac_signal.endswith("OVER"):
            combined_signal = "STRONG_OVER"
        elif moon_signal.endswith("OVER") or zodiac_signal.endswith("OVER"):
            combined_signal = "LEAN_OVER"
        elif moon_signal.endswith("UNDER") and zodiac_signal.endswith("UNDER"):
            combined_signal = "LEAN_UNDER"
        
        return {
            "moon_phase": moon_phase,
            "sun_sign": sun_sign,
            "moon_signal": moon_signal,
            "zodiac_signal": zodiac_signal,
            "combined_signal": combined_signal,
            "confidence": 0.58 if combined_signal.startswith("STRONG") else 0.52 if combined_signal.startswith("LEAN") else 0.50
        }


class EsotericEngine:
    """Master engine combining all esoteric models + Harmonic Convergence detection."""
    
    @classmethod
    def analyze(
        cls,
        player_name: str,
        opponent: str,
        line: float,
        game_date: datetime,
        player_avg: float = 0.0,
        spread: float = 0.0,
        total: float = 220.0,
        jersey_number: int = 0
    ) -> Dict:
        """Run all esoteric models and detect Harmonic Convergence."""
        
        gematria = GematriaCalculator.analyze(player_name, opponent, line)
        numerology = NumerologyEngine.analyze(player_name, jersey_number, game_date, line)
        geometry = SacredGeometryAnalyzer.analyze(spread, total, line, player_avg)
        astrology = AstrologyTracker.analyze(game_date)
        
        # Count OVER signals
        over_signals = sum([
            1 if "OVER" in gematria["signal"] else 0,
            1 if "OVER" in numerology["signal"] else 0,
            1 if geometry["total_alignments"] >= 2 else 0,
            1 if "OVER" in astrology["combined_signal"] else 0
        ])
        
        under_signals = sum([
            1 if "UNDER" in gematria["signal"] else 0,
            1 if "UNDER" in numerology["signal"] else 0,
            1 if "UNDER" in astrology["combined_signal"] else 0
        ])
        
        # Harmonic Convergence: 3+ esoteric models agree
        harmonic_convergence = over_signals >= 3 or under_signals >= 3
        esoteric_direction = "OVER" if over_signals > under_signals else "UNDER" if under_signals > over_signals else "NEUTRAL"
        
        # Esoteric edge score (0-100)
        esoteric_score = (max(over_signals, under_signals) / 4) * 100
        
        return {
            "gematria": gematria,
            "numerology": numerology,
            "sacred_geometry": geometry,
            "astrology": astrology,
            "summary": {
                "over_signals": over_signals,
                "under_signals": under_signals,
                "direction": esoteric_direction,
                "harmonic_convergence": harmonic_convergence,
                "esoteric_score": round(esoteric_score, 1),
                "confidence": round((esoteric_score / 100) * 0.3 + 0.5, 2)  # 50-80% range
            }
        }


# Initialize esoteric engine
esoteric_engine = EsotericEngine()

# ============================================
# TEAM NAME MAPPER (Cross-Source Normalization)
# ============================================

class TeamNameMapper:
    """
    Normalizes team names across different data sources.
    ESPN uses abbreviations (NYK), Odds API uses full names (New York Knicks),
    internal systems may use various formats.
    """
    
    # NBA Teams: abbrev -> (full_name, city, aliases)
    NBA_TEAMS = {
        "ATL": ("Atlanta Hawks", "Atlanta", ["hawks", "atl"]),
        "BOS": ("Boston Celtics", "Boston", ["celtics", "bos"]),
        "BKN": ("Brooklyn Nets", "Brooklyn", ["nets", "bkn", "nj", "njn"]),
        "CHA": ("Charlotte Hornets", "Charlotte", ["hornets", "cha", "cho"]),
        "CHI": ("Chicago Bulls", "Chicago", ["bulls", "chi"]),
        "CLE": ("Cleveland Cavaliers", "Cleveland", ["cavaliers", "cavs", "cle"]),
        "DAL": ("Dallas Mavericks", "Dallas", ["mavericks", "mavs", "dal"]),
        "DEN": ("Denver Nuggets", "Denver", ["nuggets", "den"]),
        "DET": ("Detroit Pistons", "Detroit", ["pistons", "det"]),
        "GSW": ("Golden State Warriors", "Golden State", ["warriors", "gsw", "gs"]),
        "HOU": ("Houston Rockets", "Houston", ["rockets", "hou"]),
        "IND": ("Indiana Pacers", "Indiana", ["pacers", "ind"]),
        "LAC": ("Los Angeles Clippers", "LA Clippers", ["clippers", "lac"]),
        "LAL": ("Los Angeles Lakers", "LA Lakers", ["lakers", "lal"]),
        "MEM": ("Memphis Grizzlies", "Memphis", ["grizzlies", "mem"]),
        "MIA": ("Miami Heat", "Miami", ["heat", "mia"]),
        "MIL": ("Milwaukee Bucks", "Milwaukee", ["bucks", "mil"]),
        "MIN": ("Minnesota Timberwolves", "Minnesota", ["timberwolves", "wolves", "min"]),
        "NOP": ("New Orleans Pelicans", "New Orleans", ["pelicans", "nop", "no"]),
        "NYK": ("New York Knicks", "New York", ["knicks", "nyk", "ny"]),
        "OKC": ("Oklahoma City Thunder", "Oklahoma City", ["thunder", "okc"]),
        "ORL": ("Orlando Magic", "Orlando", ["magic", "orl"]),
        "PHI": ("Philadelphia 76ers", "Philadelphia", ["76ers", "sixers", "phi"]),
        "PHX": ("Phoenix Suns", "Phoenix", ["suns", "phx"]),
        "POR": ("Portland Trail Blazers", "Portland", ["blazers", "por"]),
        "SAC": ("Sacramento Kings", "Sacramento", ["kings", "sac"]),
        "SAS": ("San Antonio Spurs", "San Antonio", ["spurs", "sas", "sa"]),
        "TOR": ("Toronto Raptors", "Toronto", ["raptors", "tor"]),
        "UTA": ("Utah Jazz", "Utah", ["jazz", "uta"]),
        "WAS": ("Washington Wizards", "Washington", ["wizards", "was", "wsh"]),
    }
    
    # NFL Teams
    NFL_TEAMS = {
        "ARI": ("Arizona Cardinals", "Arizona", ["cardinals", "ari"]),
        "ATL": ("Atlanta Falcons", "Atlanta", ["falcons", "atl"]),
        "BAL": ("Baltimore Ravens", "Baltimore", ["ravens", "bal"]),
        "BUF": ("Buffalo Bills", "Buffalo", ["bills", "buf"]),
        "CAR": ("Carolina Panthers", "Carolina", ["panthers", "car"]),
        "CHI": ("Chicago Bears", "Chicago", ["bears", "chi"]),
        "CIN": ("Cincinnati Bengals", "Cincinnati", ["bengals", "cin"]),
        "CLE": ("Cleveland Browns", "Cleveland", ["browns", "cle"]),
        "DAL": ("Dallas Cowboys", "Dallas", ["cowboys", "dal"]),
        "DEN": ("Denver Broncos", "Denver", ["broncos", "den"]),
        "DET": ("Detroit Lions", "Detroit", ["lions", "det"]),
        "GB": ("Green Bay Packers", "Green Bay", ["packers", "gb", "gnb"]),
        "HOU": ("Houston Texans", "Houston", ["texans", "hou"]),
        "IND": ("Indianapolis Colts", "Indianapolis", ["colts", "ind"]),
        "JAX": ("Jacksonville Jaguars", "Jacksonville", ["jaguars", "jax", "jac"]),
        "KC": ("Kansas City Chiefs", "Kansas City", ["chiefs", "kc"]),
        "LV": ("Las Vegas Raiders", "Las Vegas", ["raiders", "lv", "lvr", "oak"]),
        "LAC": ("Los Angeles Chargers", "LA Chargers", ["chargers", "lac", "sd"]),
        "LAR": ("Los Angeles Rams", "LA Rams", ["rams", "lar", "stl"]),
        "MIA": ("Miami Dolphins", "Miami", ["dolphins", "mia"]),
        "MIN": ("Minnesota Vikings", "Minnesota", ["vikings", "min"]),
        "NE": ("New England Patriots", "New England", ["patriots", "ne", "nep"]),
        "NO": ("New Orleans Saints", "New Orleans", ["saints", "no", "nos"]),
        "NYG": ("New York Giants", "NY Giants", ["giants", "nyg"]),
        "NYJ": ("New York Jets", "NY Jets", ["jets", "nyj"]),
        "PHI": ("Philadelphia Eagles", "Philadelphia", ["eagles", "phi"]),
        "PIT": ("Pittsburgh Steelers", "Pittsburgh", ["steelers", "pit"]),
        "SF": ("San Francisco 49ers", "San Francisco", ["49ers", "niners", "sf"]),
        "SEA": ("Seattle Seahawks", "Seattle", ["seahawks", "sea"]),
        "TB": ("Tampa Bay Buccaneers", "Tampa Bay", ["buccaneers", "bucs", "tb"]),
        "TEN": ("Tennessee Titans", "Tennessee", ["titans", "ten"]),
        "WAS": ("Washington Commanders", "Washington", ["commanders", "was", "wsh"]),
    }
    
    # MLB Teams
    MLB_TEAMS = {
        "ARI": ("Arizona Diamondbacks", "Arizona", ["diamondbacks", "dbacks", "ari"]),
        "ATL": ("Atlanta Braves", "Atlanta", ["braves", "atl"]),
        "BAL": ("Baltimore Orioles", "Baltimore", ["orioles", "bal"]),
        "BOS": ("Boston Red Sox", "Boston", ["red sox", "redsox", "bos"]),
        "CHC": ("Chicago Cubs", "Chicago Cubs", ["cubs", "chc"]),
        "CHW": ("Chicago White Sox", "Chicago White Sox", ["white sox", "whitesox", "chw", "cws"]),
        "CIN": ("Cincinnati Reds", "Cincinnati", ["reds", "cin"]),
        "CLE": ("Cleveland Guardians", "Cleveland", ["guardians", "cle", "indians"]),
        "COL": ("Colorado Rockies", "Colorado", ["rockies", "col"]),
        "DET": ("Detroit Tigers", "Detroit", ["tigers", "det"]),
        "HOU": ("Houston Astros", "Houston", ["astros", "hou"]),
        "KC": ("Kansas City Royals", "Kansas City", ["royals", "kc"]),
        "LAA": ("Los Angeles Angels", "LA Angels", ["angels", "laa", "ana"]),
        "LAD": ("Los Angeles Dodgers", "LA Dodgers", ["dodgers", "lad"]),
        "MIA": ("Miami Marlins", "Miami", ["marlins", "mia", "fla"]),
        "MIL": ("Milwaukee Brewers", "Milwaukee", ["brewers", "mil"]),
        "MIN": ("Minnesota Twins", "Minnesota", ["twins", "min"]),
        "NYM": ("New York Mets", "NY Mets", ["mets", "nym"]),
        "NYY": ("New York Yankees", "NY Yankees", ["yankees", "nyy"]),
        "OAK": ("Oakland Athletics", "Oakland", ["athletics", "a's", "oak"]),
        "PHI": ("Philadelphia Phillies", "Philadelphia", ["phillies", "phi"]),
        "PIT": ("Pittsburgh Pirates", "Pittsburgh", ["pirates", "pit"]),
        "SD": ("San Diego Padres", "San Diego", ["padres", "sd"]),
        "SF": ("San Francisco Giants", "San Francisco", ["giants", "sf"]),
        "SEA": ("Seattle Mariners", "Seattle", ["mariners", "sea"]),
        "STL": ("St. Louis Cardinals", "St. Louis", ["cardinals", "stl"]),
        "TB": ("Tampa Bay Rays", "Tampa Bay", ["rays", "tb"]),
        "TEX": ("Texas Rangers", "Texas", ["rangers", "tex"]),
        "TOR": ("Toronto Blue Jays", "Toronto", ["blue jays", "bluejays", "tor"]),
        "WAS": ("Washington Nationals", "Washington", ["nationals", "nats", "was"]),
    }
    
    # NHL Teams
    NHL_TEAMS = {
        "ANA": ("Anaheim Ducks", "Anaheim", ["ducks", "ana"]),
        "ARI": ("Arizona Coyotes", "Arizona", ["coyotes", "ari", "phx"]),
        "BOS": ("Boston Bruins", "Boston", ["bruins", "bos"]),
        "BUF": ("Buffalo Sabres", "Buffalo", ["sabres", "buf"]),
        "CGY": ("Calgary Flames", "Calgary", ["flames", "cgy"]),
        "CAR": ("Carolina Hurricanes", "Carolina", ["hurricanes", "canes", "car"]),
        "CHI": ("Chicago Blackhawks", "Chicago", ["blackhawks", "chi"]),
        "COL": ("Colorado Avalanche", "Colorado", ["avalanche", "avs", "col"]),
        "CBJ": ("Columbus Blue Jackets", "Columbus", ["blue jackets", "cbj"]),
        "DAL": ("Dallas Stars", "Dallas", ["stars", "dal"]),
        "DET": ("Detroit Red Wings", "Detroit", ["red wings", "det"]),
        "EDM": ("Edmonton Oilers", "Edmonton", ["oilers", "edm"]),
        "FLA": ("Florida Panthers", "Florida", ["panthers", "fla"]),
        "LA": ("Los Angeles Kings", "Los Angeles", ["kings", "la", "lak"]),
        "MIN": ("Minnesota Wild", "Minnesota", ["wild", "min"]),
        "MTL": ("Montreal Canadiens", "Montreal", ["canadiens", "habs", "mtl"]),
        "NSH": ("Nashville Predators", "Nashville", ["predators", "preds", "nsh"]),
        "NJ": ("New Jersey Devils", "New Jersey", ["devils", "nj", "njd"]),
        "NYI": ("New York Islanders", "NY Islanders", ["islanders", "nyi"]),
        "NYR": ("New York Rangers", "NY Rangers", ["rangers", "nyr"]),
        "OTT": ("Ottawa Senators", "Ottawa", ["senators", "sens", "ott"]),
        "PHI": ("Philadelphia Flyers", "Philadelphia", ["flyers", "phi"]),
        "PIT": ("Pittsburgh Penguins", "Pittsburgh", ["penguins", "pens", "pit"]),
        "SJ": ("San Jose Sharks", "San Jose", ["sharks", "sj"]),
        "SEA": ("Seattle Kraken", "Seattle", ["kraken", "sea"]),
        "STL": ("St. Louis Blues", "St. Louis", ["blues", "stl"]),
        "TB": ("Tampa Bay Lightning", "Tampa Bay", ["lightning", "bolts", "tb", "tbl"]),
        "TOR": ("Toronto Maple Leafs", "Toronto", ["maple leafs", "leafs", "tor"]),
        "VAN": ("Vancouver Canucks", "Vancouver", ["canucks", "van"]),
        "VGK": ("Vegas Golden Knights", "Vegas", ["golden knights", "knights", "vgk"]),
        "WAS": ("Washington Capitals", "Washington", ["capitals", "caps", "was", "wsh"]),
        "WPG": ("Winnipeg Jets", "Winnipeg", ["jets", "wpg"]),
    }
    
    # NCAAB - Top 50 programs (expandable)
    NCAAB_TEAMS = {
        "DUKE": ("Duke Blue Devils", "Duke", ["blue devils", "duke"]),
        "UNC": ("North Carolina Tar Heels", "North Carolina", ["tar heels", "unc", "carolina"]),
        "UK": ("Kentucky Wildcats", "Kentucky", ["wildcats", "uk", "kentucky"]),
        "KU": ("Kansas Jayhawks", "Kansas", ["jayhawks", "ku", "kansas"]),
        "UCLA": ("UCLA Bruins", "UCLA", ["bruins", "ucla"]),
        "GONZ": ("Gonzaga Bulldogs", "Gonzaga", ["bulldogs", "zags", "gonz", "gonzaga"]),
        "MICH": ("Michigan Wolverines", "Michigan", ["wolverines", "mich"]),
        "MSU": ("Michigan State Spartans", "Michigan State", ["spartans", "msu"]),
        "OSU": ("Ohio State Buckeyes", "Ohio State", ["buckeyes", "osu"]),
        "IU": ("Indiana Hoosiers", "Indiana", ["hoosiers", "iu", "indiana"]),
        "LOU": ("Louisville Cardinals", "Louisville", ["cardinals", "lou", "louisville"]),
        "NOVA": ("Villanova Wildcats", "Villanova", ["wildcats", "nova", "villanova"]),
        "UVA": ("Virginia Cavaliers", "Virginia", ["cavaliers", "uva", "virginia"]),
        "BAYLOR": ("Baylor Bears", "Baylor", ["bears", "baylor"]),
        "TENN": ("Tennessee Volunteers", "Tennessee", ["volunteers", "vols", "tenn"]),
        "ARIZ": ("Arizona Wildcats", "Arizona", ["wildcats", "ariz", "arizona"]),
        "CONN": ("UConn Huskies", "UConn", ["huskies", "conn", "uconn", "connecticut"]),
        "ARK": ("Arkansas Razorbacks", "Arkansas", ["razorbacks", "hogs", "ark"]),
        "AUB": ("Auburn Tigers", "Auburn", ["tigers", "aub", "auburn"]),
        "PUR": ("Purdue Boilermakers", "Purdue", ["boilermakers", "pur", "purdue"]),
    }
    
    @classmethod
    def get_team_map(cls, sport: str) -> Dict:
        """Get team mapping for a sport."""
        sport = sport.upper()
        return {
            "NBA": cls.NBA_TEAMS,
            "NFL": cls.NFL_TEAMS,
            "MLB": cls.MLB_TEAMS,
            "NHL": cls.NHL_TEAMS,
            "NCAAB": cls.NCAAB_TEAMS
        }.get(sport, {})
    
    @classmethod
    def normalize(cls, team_input: str, sport: str) -> str:
        """
        Normalize any team name input to standard abbreviation.
        
        Args:
            team_input: Any form of team name (abbrev, full name, city, nickname)
            sport: Sport league (NBA, NFL, MLB, NHL, NCAAB)
        
        Returns:
            Standard abbreviation (e.g., "NYK", "LAL")
        """
        team_map = cls.get_team_map(sport)
        if not team_map:
            return team_input.upper()[:3]
        
        # Check if already an abbreviation
        if team_input.upper() in team_map:
            return team_input.upper()
        
        # Search through all teams
        input_lower = team_input.lower().strip()
        for abbrev, (full_name, city, aliases) in team_map.items():
            # Check full name
            if input_lower == full_name.lower():
                return abbrev
            # Check city
            if input_lower == city.lower():
                return abbrev
            # Check aliases
            if input_lower in [a.lower() for a in aliases]:
                return abbrev
            # Partial match on full name
            if input_lower in full_name.lower() or full_name.lower() in input_lower:
                return abbrev
        
        # Fallback: return uppercase truncated
        return team_input.upper()[:3]
    
    @classmethod
    def to_full_name(cls, abbrev: str, sport: str) -> str:
        """Convert abbreviation to full team name."""
        team_map = cls.get_team_map(sport)
        if abbrev.upper() in team_map:
            return team_map[abbrev.upper()][0]
        return abbrev
    
    @classmethod
    def to_city(cls, abbrev: str, sport: str) -> str:
        """Convert abbreviation to city/region name."""
        team_map = cls.get_team_map(sport)
        if abbrev.upper() in team_map:
            return team_map[abbrev.upper()][1]
        return abbrev
    
    @classmethod
    def match_teams(cls, team1: str, team2: str, sport: str) -> bool:
        """Check if two team name inputs refer to the same team."""
        return cls.normalize(team1, sport) == cls.normalize(team2, sport)


# Initialize mapper
team_mapper = TeamNameMapper()

# ============================================
# REQUEST MODELS
# ============================================

class InjuryInput(BaseModel):
    player_name: Optional[str] = None
    status: str = "OUT"
    usage_pct: Optional[float] = None
    minutes_per_game: Optional[float] = None
    target_share: Optional[float] = None
    snaps_per_game: Optional[float] = None
    time_on_ice: Optional[float] = None
    plate_appearances: Optional[float] = None

class LSTMHistoryInput(BaseModel):
    """
    Historical game features for LSTM sequence (single game).
    Aligned with spec: [stat, mins, home_away, vacuum, def_rank, pace]
    """
    stat: float = Field(0.0, description="Player's stat value for that game")
    player_avg: float = Field(20.0, description="Player's season average (for normalization)")
    mins: float = Field(30.0, description="Minutes played in that game")
    home_away: int = Field(0, description="0 = away, 1 = home")
    vacuum: float = Field(0.0, description="Usage vacuum factor (0 to 1)")
    def_rank: float = Field(16, description="Opponent defense rank (1-32)")
    pace: float = Field(100.0, description="Game pace factor")

class ContextRequest(BaseModel):
    sport: str
    player_name: str
    player_team: str
    opponent_team: str
    position: str
    player_avg: float
    stat_type: Optional[str] = "points"
    injuries: List[InjuryInput] = Field(default_factory=list)
    game_total: Optional[float] = 0.0
    game_spread: Optional[float] = 0.0
    home_team: Optional[str] = None
    line: Optional[float] = None
    odds: Optional[int] = None
    # LSTM Spec Fields
    expected_mins: Optional[float] = Field(
        default=None,
        description="Expected minutes for this game (for LSTM input)"
    )
    jersey_number: Optional[int] = Field(
        default=None,
        description="Player's jersey number (for Esoteric analysis)"
    )
    # Officials
    lead_official: Optional[str] = None
    official_2: Optional[str] = None
    official_3: Optional[str] = None
    # LSTM Brain historical context (up to 14 past games)
    historical_features: Optional[List[LSTMHistoryInput]] = Field(
        default=None,
        description="Historical game features for LSTM sequence (max 14 games)"
    )
    use_lstm_brain: Optional[bool] = Field(
        default=True,
        description="Enable LSTM neural prediction adjustment"
    )

class BatchContextRequest(BaseModel):
    predictions: List[ContextRequest]

class DefenseRankRequest(BaseModel):
    sport: str
    team: str
    position: str

class VacuumRequest(BaseModel):
    sport: str
    injuries: List[InjuryInput]

class PaceRequest(BaseModel):
    sport: str
    team1: str
    team2: str

class ParkFactorRequest(BaseModel):
    team: str

class EdgeCalculationRequest(BaseModel):
    your_probability: float = Field(..., ge=0, le=1)
    betting_odds: int

class OfficialsRequest(BaseModel):
    sport: str
    lead_official: str
    official_2: Optional[str] = ""
    official_3: Optional[str] = ""
    bet_type: Optional[str] = "total"  # total, spread, props
    is_home: Optional[bool] = False
    is_star: Optional[bool] = False

class EsotericRequest(BaseModel):
    """Request for esoteric analysis (Gematria, Numerology, Sacred Geometry, Astrology)."""
    player_name: str = Field(..., description="Player name for gematria analysis")
    opponent: str = Field(..., description="Opponent team for matchup analysis")
    line: float = Field(..., description="Betting line")
    game_date: Optional[str] = Field(None, description="Game date (YYYY-MM-DD), defaults to today")
    player_avg: Optional[float] = Field(0.0, description="Player's season average")
    spread: Optional[float] = Field(0.0, description="Game spread")
    total: Optional[float] = Field(220.0, description="Game total")
    jersey_number: Optional[int] = Field(0, description="Player's jersey number")

# ============================================
# ROOT
# ============================================

@app.get("/")
async def root():
    return {
        "status": "online",
        "message": "Multi-Sport AI Betting API with Context Layer + Officials + LSTM Brain + Auto-Grader + Esoteric Edge + Live Data",
        "version": "7.2.0",
        "supported_sports": SUPPORTED_SPORTS,
        "models": {
            "ai": ["Ensemble", "LSTM Brain", "Monte Carlo", "Line Movement", "Rest/Fatigue", "Injury Impact", "Matchup", "Edge Calculator"],
            "esoteric": ["Gematria", "Numerology", "Sacred Geometry", "Astrology"]
        },
        "endpoints": {
            "predictions": ["/predict-context", "/predict-batch", "/predict-live"],
            "live_data": ["/live/games/{sport}", "/live/props/{sport}", "/live/injuries/{sport}", "/live/player/{name}", "/live/slate/{sport}"],
            "brain": ["/brain/predict", "/brain/status"],
            "grader": ["/grader/weights", "/grader/grade", "/grader/audit", "/grader/bias"],
            "esoteric": ["/esoteric/analyze", "/esoteric/gematria", "/esoteric/numerology", "/esoteric/astrology"],
            "teams": ["/teams/normalize", "/teams/match", "/teams/{sport}", "/teams/{sport}/{abbrev}"],
            "sports_info": ["/sports", "/sports/{sport}/positions", "/sports/{sport}/stat-types"],
            "defense": ["/defense-rank", "/defense-rankings/{sport}/{position}"],
            "pace": ["/game-pace", "/pace-rankings/{sport}"],
            "vacuum": ["/usage-vacuum"],
            "officials": ["/officials-analysis", "/officials/{sport}", "/official/{sport}/{name}"],
            "mlb": ["/park-factor", "/park-factors"],
            "edge": ["/calculate-edge"],
            "system": ["/health", "/model-status", "/docs"]
        }
    }

@app.get("/sports")
async def get_supported_sports():
    return {
        "status": "success",
        "sports": SUPPORTED_SPORTS,
        "details": {sport: {"positions": SPORT_POSITIONS.get(sport, []), "stat_types": SPORT_STAT_TYPES.get(sport, [])} for sport in SUPPORTED_SPORTS}
    }

@app.get("/sports/{sport}/positions")
async def get_sport_positions(sport: str):
    sport = sport.upper()
    if sport not in SUPPORTED_SPORTS:
        raise HTTPException(status_code=400, detail=f"Sport must be one of: {SUPPORTED_SPORTS}")
    return {"status": "success", "sport": sport, "positions": SPORT_POSITIONS.get(sport, [])}

@app.get("/sports/{sport}/stat-types")
async def get_sport_stat_types(sport: str):
    sport = sport.upper()
    if sport not in SUPPORTED_SPORTS:
        raise HTTPException(status_code=400, detail=f"Sport must be one of: {SUPPORTED_SPORTS}")
    return {"status": "success", "sport": sport, "stat_types": SPORT_STAT_TYPES.get(sport, [])}

# ============================================
# TEAM NAME MAPPER ENDPOINTS
# ============================================

@app.post("/teams/normalize")
async def normalize_team_name(team_input: str, sport: str):
    """
    Normalize any team name input to standard abbreviation.
    Handles ESPN names, Odds API names, full names, cities, nicknames.
    """
    sport = sport.upper()
    if sport not in SUPPORTED_SPORTS:
        raise HTTPException(status_code=400, detail=f"Sport must be one of: {SUPPORTED_SPORTS}")
    
    abbrev = TeamNameMapper.normalize(team_input, sport)
    full_name = TeamNameMapper.to_full_name(abbrev, sport)
    city = TeamNameMapper.to_city(abbrev, sport)
    
    return {
        "status": "success",
        "input": team_input,
        "sport": sport,
        "normalized": {
            "abbreviation": abbrev,
            "full_name": full_name,
            "city": city
        }
    }


@app.post("/teams/match")
async def check_team_match(team1: str, team2: str, sport: str):
    """
    Check if two team name inputs refer to the same team.
    Useful for matching data from different sources.
    """
    sport = sport.upper()
    if sport not in SUPPORTED_SPORTS:
        raise HTTPException(status_code=400, detail=f"Sport must be one of: {SUPPORTED_SPORTS}")
    
    is_match = TeamNameMapper.match_teams(team1, team2, sport)
    norm1 = TeamNameMapper.normalize(team1, sport)
    norm2 = TeamNameMapper.normalize(team2, sport)
    
    return {
        "status": "success",
        "team1": {"input": team1, "normalized": norm1},
        "team2": {"input": team2, "normalized": norm2},
        "is_match": is_match
    }


@app.get("/teams/{sport}")
async def list_all_teams(sport: str):
    """Get all teams for a sport with abbreviations and full names."""
    sport = sport.upper()
    if sport not in SUPPORTED_SPORTS:
        raise HTTPException(status_code=400, detail=f"Sport must be one of: {SUPPORTED_SPORTS}")
    
    team_map = TeamNameMapper.get_team_map(sport)
    teams = []
    for abbrev, (full_name, city, aliases) in team_map.items():
        teams.append({
            "abbreviation": abbrev,
            "full_name": full_name,
            "city": city,
            "aliases": aliases
        })
    
    return {
        "status": "success",
        "sport": sport,
        "team_count": len(teams),
        "teams": sorted(teams, key=lambda x: x["abbreviation"])
    }


@app.get("/teams/{sport}/{abbrev}")
async def get_team_info(sport: str, abbrev: str):
    """Get detailed info for a specific team."""
    sport = sport.upper()
    if sport not in SUPPORTED_SPORTS:
        raise HTTPException(status_code=400, detail=f"Sport must be one of: {SUPPORTED_SPORTS}")
    
    team_map = TeamNameMapper.get_team_map(sport)
    normalized = TeamNameMapper.normalize(abbrev, sport)
    
    if normalized not in team_map:
        raise HTTPException(status_code=404, detail=f"Team '{abbrev}' not found in {sport}")
    
    full_name, city, aliases = team_map[normalized]
    
    return {
        "status": "success",
        "sport": sport,
        "team": {
            "abbreviation": normalized,
            "full_name": full_name,
            "city": city,
            "aliases": aliases
        }
    }


# ============================================
# CONTEXT PREDICTIONS
# ============================================

@app.post("/predict-context")
async def predict_with_context(request: ContextRequest):
    try:
        sport = request.sport.upper()
        if sport not in SUPPORTED_SPORTS:
            raise HTTPException(status_code=400, detail=f"Sport must be one of: {SUPPORTED_SPORTS}")
        
        # =====================
        # TEAM NAME NORMALIZATION
        # =====================
        player_team_normalized = TeamNameMapper.normalize(request.player_team, sport)
        opponent_team_normalized = TeamNameMapper.normalize(request.opponent_team, sport)
        
        logger.info(f"[{sport}] Context prediction: {request.player_name} ({player_team_normalized}) vs {opponent_team_normalized}")
        injuries = [inj.dict() for inj in request.injuries]
        
        # =====================
        # CONTEXT LAYER INJECTION (Nano Banana Upgrade)
        # Calculate context features BEFORE AI models
        # =====================
        game_stats = {
            "home_pace": LEAGUE_AVERAGES.get(sport, {}).get("pace", 100.0),
            "away_pace": LEAGUE_AVERAGES.get(sport, {}).get("pace", 100.0),
            "total": request.game_total or 0.0,
            "spread": request.game_spread or 0.0
        }
        
        # Calculate context for player's team (use normalized names)
        player_context = ContextFeatureCalculator.calculate_context_features(
            sport=sport,
            team_id=player_team_normalized,
            injuries=injuries,
            game_stats=game_stats
        )
        
        # Calculate context for opponent team (empty injuries = no vacuum boost for them)
        opponent_context = ContextFeatureCalculator.calculate_context_features(
            sport=sport,
            team_id=opponent_team_normalized,
            injuries=[],  # We don't have opponent injuries in this request
            game_stats=game_stats
        )
        
        logger.info(f"[{sport}] Context Layer: vacuum={player_context['vacuum']}, pace_vector={player_context['pace_vector']}, smash={player_context['is_smash_spot']}")
        
        # =====================
        # GENERATE FULL CONTEXT (use normalized team names)
        # =====================
        context = ContextGenerator.generate_context(
            sport=sport, player_name=request.player_name, player_team=player_team_normalized,
            opponent_team=opponent_team_normalized, position=request.position, player_avg=request.player_avg,
            stat_type=request.stat_type or "points", injuries=injuries, game_total=request.game_total or 0.0,
            game_spread=request.game_spread or 0.0, home_team=request.home_team
        )
        
        waterfall = context["waterfall"]
        final_pred = waterfall["finalPrediction"]
        
        # =====================
        # LSTM FEATURES (Aligned with spec: [stat, mins, home_away, vacuum, def_rank, pace])
        # =====================
        # Capture original context values before reassigning
        original_def_rank = context["lstm_features"].get("def_rank", context["lstm_features"].get("defense_rank", 16))
        original_pace = context["lstm_features"].get("pace", 100.0)
        
        # Determine home/away status
        is_home = 1 if request.home_team and TeamNameMapper.match_teams(
            request.player_team, request.home_team, sport
        ) else 0
        
        # Default expected minutes by sport
        default_mins = {"NBA": 32.0, "NFL": 55.0, "MLB": 6.0, "NHL": 18.0, "NCAAB": 30.0}
        expected_mins = request.expected_mins or default_mins.get(sport, 30.0)
        
        # Build spec-compliant lstm_features
        context["lstm_features"] = {
            # Spec features: [stat, mins, home_away, vacuum, def_rank, pace]
            "stat": request.player_avg,  # Use player average as baseline stat (actual comes from history)
            "player_avg": request.player_avg,  # For normalization
            "mins": expected_mins,  # Expected minutes for this game
            "home_away": is_home,
            "vacuum": player_context["vacuum"],
            "def_rank": original_def_rank,
            "pace": original_pace,
            # Additional context (for reference/debugging)
            "calculated_vacuum": player_context["vacuum"],
            "calculated_pace_vector": player_context["pace_vector"],
            "calculated_smash_spot": player_context["is_smash_spot"],
            "opponent_vacuum": opponent_context["vacuum"],
            "defense_rank": original_def_rank,  # Legacy field for backwards compatibility
        }
        
        # =====================
        # LSTM BRAIN PREDICTION (Now with spec-compliant features)
        # =====================
        lstm_prediction = None
        if request.use_lstm_brain:
            try:
                # Convert historical features if provided
                historical_features = None
                if request.historical_features:
                    historical_features = [h.dict() for h in request.historical_features]
                
                # Get LSTM prediction from sport-specific brain with calculated context
                lstm_prediction = lstm_brain_manager.predict(
                    sport=sport,
                    current_features=context["lstm_features"],
                    historical_features=historical_features,
                    scale_factor=5.0  # Adjust prediction by up to ±5 points
                )
                
                # Apply LSTM adjustment to waterfall
                lstm_adjustment = lstm_prediction.get("adjustment", 0)
                if abs(lstm_adjustment) > 0.1:  # Only apply significant adjustments
                    waterfall["adjustments"].append({
                        "factor": "lstm_brain",
                        "value": round(lstm_adjustment, 2),
                        "reason": f"Neural pattern analysis ({lstm_prediction.get('method', 'unknown')})"
                    })
                    final_pred += lstm_adjustment
                    waterfall["finalPrediction"] = round(final_pred, 1)
                    
                    # Add brain badge if high confidence
                    if lstm_prediction.get("confidence", 0) >= 50:
                        context["badges"].append({
                            "icon": "🧠", 
                            "label": "brain", 
                            "active": True,
                            "confidence": lstm_prediction.get("confidence")
                        })
                
                logger.info(f"[{sport}] LSTM Brain: adjustment={lstm_adjustment:.2f}, confidence={lstm_prediction.get('confidence', 0):.1f}%")
                
            except Exception as lstm_error:
                logger.warning(f"LSTM Brain error (non-critical): {str(lstm_error)}")
                lstm_prediction = {"error": str(lstm_error), "method": "skipped"}
        
        # Add officials adjustment if provided
        officials_analysis = None
        if request.lead_official:
            officials_analysis = OfficialsService.analyze_crew(
                sport, request.lead_official, 
                request.official_2 or "", 
                request.official_3 or ""
            )
            
            if officials_analysis.get("has_data"):
                # Get props adjustment for star players
                is_star = request.player_avg > 20 if sport in ["NBA", "NCAAB"] else request.player_avg > 80
                officials_adj = OfficialsService.get_adjustment(
                    sport, request.lead_official,
                    request.official_2 or "", request.official_3 or "",
                    bet_type="props", is_star=is_star
                )
                
                if officials_adj:
                    waterfall["adjustments"].append(officials_adj)
                    final_pred += officials_adj["value"]
                    waterfall["finalPrediction"] = round(final_pred, 1)
                    context["badges"].append({"icon": "🦓", "label": "officials", "active": True})
        
        # =====================
        # ESOTERIC ANALYSIS (The "Magic")
        # =====================
        esoteric_result = None
        try:
            esoteric_result = EsotericEngine.analyze(
                player_name=request.player_name,
                opponent=opponent_team_normalized,
                line=request.line or request.player_avg,
                game_date=datetime.now(),
                player_avg=request.player_avg,
                spread=request.game_spread or 0.0,
                total=request.game_total or 220.0,
                jersey_number=request.jersey_number or 0
            )
            
            # Check for Harmonic Convergence (Math + Magic align)
            if esoteric_result["summary"]["harmonic_convergence"]:
                esoteric_direction = esoteric_result["summary"]["direction"]
                math_direction = "OVER" if waterfall["finalPrediction"] > (request.line or request.player_avg) else "UNDER"
                
                if esoteric_direction == math_direction:
                    # TRUE HARMONIC CONVERGENCE: Math and Magic agree!
                    context["badges"].append({
                        "icon": "✨", 
                        "label": "harmonic_convergence", 
                        "active": True,
                        "direction": esoteric_direction,
                        "esoteric_score": esoteric_result["summary"]["esoteric_score"]
                    })
                    logger.info(f"[{sport}] ✨ HARMONIC CONVERGENCE: Math={math_direction}, Magic={esoteric_direction}")
                else:
                    # Esoteric models agree but conflict with math
                    context["badges"].append({
                        "icon": "🔮", 
                        "label": "esoteric_divergence", 
                        "active": True,
                        "math_direction": math_direction,
                        "magic_direction": esoteric_direction
                    })
            elif esoteric_result["summary"]["esoteric_score"] >= 50:
                # Some esoteric signal but not full convergence
                context["badges"].append({
                    "icon": "🔮", 
                    "label": "esoteric_lean", 
                    "active": True,
                    "direction": esoteric_result["summary"]["direction"],
                    "score": esoteric_result["summary"]["esoteric_score"]
                })
                
        except Exception as esoteric_error:
            logger.warning(f"Esoteric analysis error (non-critical): {str(esoteric_error)}")
            esoteric_result = {"error": str(esoteric_error)}
        
        response = {
            "status": "success", "sport": sport,
            "prediction": {
                "player": request.player_name, 
                "team": player_team_normalized,
                "team_full": TeamNameMapper.to_full_name(player_team_normalized, sport),
                "opponent": opponent_team_normalized,
                "opponent_full": TeamNameMapper.to_full_name(opponent_team_normalized, sport),
                "position": request.position, "stat_type": request.stat_type, "base": request.player_avg,
                "final": waterfall["finalPrediction"], "line": request.line, "recommendation": None,
                "confidence": waterfall["confidence"], "is_smash_spot": waterfall["isSmashSpot"]
            },
            "team_normalization": {
                "player_team": {"input": request.player_team, "normalized": player_team_normalized},
                "opponent_team": {"input": request.opponent_team, "normalized": opponent_team_normalized}
            },
            "calculated_context": {
                "player_team": player_context,
                "opponent_team": opponent_context
            },
            "lstm_features": context["lstm_features"], 
            "lstm_brain": lstm_prediction,
            "esoteric": esoteric_result,
            "waterfall": waterfall,
            "badges": context["badges"], "raw_context": context["raw_context"],
            "dynamic_weights": auto_grader.get_weights(sport, request.stat_type or "points")
        }
        
        # Log prediction for grading (feedback loop)
        adjustments_for_log = {}
        for adj in waterfall.get("adjustments", []):
            factor = adj.get("factor", "unknown")
            adjustments_for_log[factor] = adj.get("value", 0)
        
        prediction_id = auto_grader.log_prediction(
            sport=sport,
            player_name=request.player_name,
            stat_type=request.stat_type or "points",
            predicted_value=waterfall["finalPrediction"],
            line=request.line,
            adjustments=adjustments_for_log
        )
        response["prediction_id"] = prediction_id  # Return for grading later
        
        # Add officials analysis if available
        if officials_analysis and officials_analysis.get("has_data"):
            response["officials"] = {
                "crew": officials_analysis.get("officials_found", []),
                "total_recommendation": officials_analysis.get("total_recommendation"),
                "props_lean": officials_analysis.get("props_lean"),
                "over_pct": officials_analysis.get("over_pct"),
                "confidence": officials_analysis.get("confidence")
            }
        
        if request.line:
            edge = waterfall["finalPrediction"] - request.line
            response["prediction"]["recommendation"] = "OVER" if edge > 0 else "UNDER"
            response["edge"] = {"raw": round(edge, 1), "percent": round((edge / request.line) * 100, 1) if request.line != 0 else 0, "direction": "OVER" if edge > 0 else "UNDER"}
        
        if request.odds and request.line:
            edge_pct = (waterfall["finalPrediction"] - request.line) / request.line if request.line != 0 else 0
            implied_prob = abs(request.odds) / (abs(request.odds) + 100) if request.odds < 0 else 100 / (request.odds + 100)
            our_prob = max(0.1, min(0.9, 0.5 + (edge_pct * 2)))
            ev = (our_prob * 100) - ((1 - our_prob) * 100)
            response["ev"] = {"percent": round(ev, 1), "per_100": round(ev, 2), "implied_prob": round(implied_prob * 100, 1), "our_prob": round(our_prob * 100, 1)}
        
        logger.success(f"[{sport}] Prediction: {waterfall['finalPrediction']} | Smash: {waterfall['isSmashSpot']}")
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Context prediction error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# PREDICT WITH LIVE DATA
# ============================================

class LivePredictionRequest(BaseModel):
    """Minimal request - live data fills the rest."""
    sport: str
    player_name: str
    player_team: str
    opponent_team: str
    stat_type: Optional[str] = "points"
    use_lstm_brain: Optional[bool] = True


@app.post("/predict-live")
async def predict_with_live_data(request: LivePredictionRequest):
    """
    Make prediction using LIVE DATA from APIs.
    
    Automatically fetches:
    - Player stats (avg, minutes)
    - Team injuries (for vacuum)
    - Game odds (spread, total)
    - Player props (line)
    
    Then runs full prediction pipeline.
    """
    try:
        sport = request.sport.upper()
        if sport not in SUPPORTED_SPORTS:
            raise HTTPException(status_code=400, detail=f"Sport must be one of: {SUPPORTED_SPORTS}")
        
        logger.info(f"[{sport}] Live prediction: {request.player_name} ({request.player_team}) vs {request.opponent_team}")
        
        # =====================
        # FETCH LIVE DATA
        # =====================
        live_context = LiveDataRouter.build_prediction_context(
            sport=sport,
            player_name=request.player_name,
            player_team=request.player_team,
            opponent_team=request.opponent_team
        )
        
        # Normalize team names
        player_team_normalized = TeamNameMapper.normalize(request.player_team, sport)
        opponent_team_normalized = TeamNameMapper.normalize(request.opponent_team, sport)
        
        # Build injuries list from live data
        injuries = []
        for inj in live_context.get("injuries", []):
            injuries.append({
                "player_name": inj.get("player_name"),
                "status": inj.get("status", "OUT"),
                "usage_pct": inj.get("usage_pct", 0.15),
                "minutes_per_game": inj.get("minutes_per_game", 25.0)
            })
        
        # Get player average from live data or use default
        player_avg = live_context.get("player_avg", 20.0)
        position = live_context.get("position", "G")
        expected_mins = live_context.get("expected_mins", 30.0)
        game_total = live_context.get("game_total", 220.0)
        game_spread = live_context.get("game_spread", 0.0)
        line = live_context.get("line", player_avg)
        home_team = live_context.get("home_team")
        
        # =====================
        # CONTEXT LAYER INJECTION
        # =====================
        game_stats = {
            "home_pace": LEAGUE_AVERAGES.get(sport, {}).get("pace", 100.0),
            "away_pace": LEAGUE_AVERAGES.get(sport, {}).get("pace", 100.0),
            "total": game_total,
            "spread": game_spread
        }
        
        player_context = ContextFeatureCalculator.calculate_context_features(
            sport=sport,
            team_id=player_team_normalized,
            injuries=injuries,
            game_stats=game_stats
        )
        
        opponent_context = ContextFeatureCalculator.calculate_context_features(
            sport=sport,
            team_id=opponent_team_normalized,
            injuries=[],
            game_stats=game_stats
        )
        
        # =====================
        # GENERATE PREDICTION
        # =====================
        context = ContextGenerator.generate_context(
            sport=sport, 
            player_name=request.player_name, 
            player_team=player_team_normalized,
            opponent_team=opponent_team_normalized, 
            position=position, 
            player_avg=player_avg,
            stat_type=request.stat_type or "points", 
            injuries=injuries, 
            game_total=game_total,
            game_spread=game_spread, 
            home_team=home_team
        )
        
        waterfall = context["waterfall"]
        final_pred = waterfall["finalPrediction"]
        
        # =====================
        # LSTM BRAIN (if enabled)
        # =====================
        lstm_prediction = None
        if request.use_lstm_brain:
            try:
                is_home = 1 if home_team and TeamNameMapper.match_teams(request.player_team, home_team, sport) else 0
                lstm_features = {
                    "stat": player_avg,
                    "player_avg": player_avg,
                    "mins": expected_mins,
                    "home_away": is_home,
                    "vacuum": player_context["vacuum"],
                    "def_rank": context["lstm_features"].get("def_rank", 16),
                    "pace": context["lstm_features"].get("pace", 100.0)
                }
                
                lstm_prediction = lstm_brain_manager.predict(
                    sport=sport,
                    current_features=lstm_features,
                    historical_features=None,
                    scale_factor=5.0
                )
                
                lstm_adjustment = lstm_prediction.get("adjustment", 0)
                if abs(lstm_adjustment) > 0.1:
                    waterfall["adjustments"].append({
                        "factor": "lstm_brain",
                        "value": round(lstm_adjustment, 2),
                        "reason": f"Neural pattern analysis ({lstm_prediction.get('method', 'unknown')})"
                    })
                    final_pred += lstm_adjustment
                    waterfall["finalPrediction"] = round(final_pred, 1)
                    
                    if lstm_prediction.get("confidence", 0) >= 50:
                        context["badges"].append({"icon": "🧠", "label": "brain", "active": True})
                        
            except Exception as e:
                logger.warning(f"LSTM error (non-critical): {e}")
        
        # =====================
        # ESOTERIC ANALYSIS
        # =====================
        esoteric_result = None
        try:
            esoteric_result = EsotericEngine.analyze(
                player_name=request.player_name,
                opponent=opponent_team_normalized,
                line=line,
                game_date=datetime.now(),
                player_avg=player_avg,
                spread=game_spread,
                total=game_total,
                jersey_number=0
            )
            
            if esoteric_result["summary"]["harmonic_convergence"]:
                esoteric_direction = esoteric_result["summary"]["direction"]
                math_direction = "OVER" if final_pred > line else "UNDER"
                
                if esoteric_direction == math_direction:
                    context["badges"].append({
                        "icon": "✨", "label": "harmonic_convergence", "active": True,
                        "direction": esoteric_direction
                    })
        except Exception as e:
            logger.warning(f"Esoteric error: {e}")
        
        # =====================
        # BUILD RESPONSE
        # =====================
        edge = final_pred - line if line else 0
        recommendation = "OVER" if edge > 0 else "UNDER" if edge < 0 else "HOLD"
        
        response = {
            "status": "success",
            "sport": sport,
            "data_source": "LIVE",
            "prediction": {
                "player": request.player_name,
                "team": player_team_normalized,
                "opponent": opponent_team_normalized,
                "stat_type": request.stat_type,
                "player_avg": player_avg,
                "final": waterfall["finalPrediction"],
                "line": line,
                "edge": round(edge, 1),
                "recommendation": recommendation,
                "confidence": waterfall["confidence"],
                "is_smash_spot": waterfall["isSmashSpot"]
            },
            "live_data": {
                "game_total": game_total,
                "game_spread": game_spread,
                "injuries_found": len(injuries),
                "vacuum": round(player_context["vacuum"] * 100, 1),
                "home_team": home_team
            },
            "waterfall": waterfall,
            "badges": context["badges"],
            "lstm_brain": lstm_prediction,
            "esoteric": esoteric_result,
            "timestamp": datetime.now().isoformat()
        }
        
        # Log for grading
        adjustments_for_log = {adj.get("factor", "unknown"): adj.get("value", 0) for adj in waterfall.get("adjustments", [])}
        prediction_id = auto_grader.log_prediction(
            sport=sport,
            player_name=request.player_name,
            stat_type=request.stat_type or "points",
            predicted_value=waterfall["finalPrediction"],
            line=line,
            adjustments=adjustments_for_log
        )
        response["prediction_id"] = prediction_id
        
        logger.success(f"[{sport}] LIVE Prediction: {final_pred} vs {line} | {recommendation} | Vacuum: {player_context['vacuum']:.2f}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Live prediction error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/predict-batch")
async def predict_batch(request: BatchContextRequest):
    try:
        results, smash_spots, by_sport = [], [], {}
        for pred_request in request.predictions:
            sport = pred_request.sport.upper()
            injuries = [inj.dict() for inj in pred_request.injuries]
            context = ContextGenerator.generate_context(
                sport=sport, player_name=pred_request.player_name, player_team=pred_request.player_team,
                opponent_team=pred_request.opponent_team, position=pred_request.position, player_avg=pred_request.player_avg,
                stat_type=pred_request.stat_type or "points", injuries=injuries, game_total=pred_request.game_total or 0.0,
                game_spread=pred_request.game_spread or 0.0, home_team=pred_request.home_team
            )
            waterfall = context["waterfall"]
            final_pred = waterfall["finalPrediction"]
            result = {"sport": sport, "player": pred_request.player_name, "team": pred_request.player_team,
                      "opponent": pred_request.opponent_team, "position": pred_request.position, "stat_type": pred_request.stat_type,
                      "base": pred_request.player_avg, "final": final_pred, "line": pred_request.line,
                      "confidence": waterfall["confidence"], "is_smash_spot": waterfall["isSmashSpot"],
                      "badges": [b["icon"] for b in context["badges"]]}
            if pred_request.line:
                edge = final_pred - pred_request.line
                result["recommendation"] = "OVER" if edge > 0 else "UNDER"
                result["edge"] = round(edge, 1)
            results.append(result)
            if sport not in by_sport:
                by_sport[sport] = []
            by_sport[sport].append(result)
            if waterfall["isSmashSpot"]:
                smash_spots.append(result)
        return {"status": "success", "count": len(results), "smash_spot_count": len(smash_spots), "predictions": results, "smash_spots": smash_spots, "by_sport": by_sport}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# OFFICIALS ENDPOINTS (ALL SPORTS)
# ============================================

@app.post("/officials-analysis")
async def analyze_officials(request: OfficialsRequest):
    """
    Analyze officiating crew for ANY sport
    
    Supports: NBA, NFL, MLB, NHL, NCAAB
    
    Returns tendencies for:
    - Totals (over/under)
    - Spreads (home advantage)
    - Props (foul/penalty rates)
    """
    try:
        sport = request.sport.upper()
        if sport not in SUPPORTED_SPORTS:
            raise HTTPException(status_code=400, detail=f"Sport must be one of: {SUPPORTED_SPORTS}")
        
        analysis = OfficialsService.analyze_crew(
            sport, request.lead_official,
            request.official_2 or "",
            request.official_3 or ""
        )
        
        if not analysis.get("has_data"):
            return {"status": "no_data", "message": "Official(s) not found in database", "sport": sport}
        
        adjustment = None
        if request.bet_type:
            adjustment = OfficialsService.get_adjustment(
                sport, request.lead_official,
                request.official_2 or "", request.official_3 or "",
                bet_type=request.bet_type,
                is_home=request.is_home or False,
                is_star=request.is_star or False
            )
        
        return {
            "status": "success",
            "sport": sport,
            "analysis": analysis,
            "adjustment": adjustment,
            "league_avg": LEAGUE_AVERAGES.get(sport, {})
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Officials analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/officials/{sport}")
async def get_all_officials(sport: str):
    """Get all officials for a sport grouped by tendency"""
    try:
        sport = sport.upper()
        if sport not in SUPPORTED_SPORTS:
            raise HTTPException(status_code=400, detail=f"Sport must be one of: {SUPPORTED_SPORTS}")
        
        grouped = OfficialsService.get_all_officials_by_tendency(sport)
        
        # Count by tendency
        summary = {tendency: len(officials) for tendency, officials in grouped.items()}
        
        return {
            "status": "success",
            "sport": sport,
            "officials": grouped,
            "summary": summary,
            "league_avg": LEAGUE_AVERAGES.get(sport, {})
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Officials fetch error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/official/{sport}/{name}")
async def get_official_profile(sport: str, name: str):
    """Get profile for a single official in any sport"""
    try:
        sport = sport.upper()
        if sport not in SUPPORTED_SPORTS:
            raise HTTPException(status_code=400, detail=f"Sport must be one of: {SUPPORTED_SPORTS}")
        
        profile = OfficialsService.get_official_profile(sport, name)
        
        if not profile:
            raise HTTPException(status_code=404, detail=f"Official '{name}' not found in {sport}")
        
        league_avg = LEAGUE_AVERAGES.get(sport, {})
        
        # Calculate edges vs league average
        edges = {}
        for key, value in profile.items():
            if key != "tendency" and isinstance(value, (int, float)) and key in league_avg:
                edges[key] = round(value - league_avg[key], 1)
        
        return {
            "status": "success",
            "sport": sport,
            "name": name.title(),
            "profile": profile,
            "edges_vs_avg": edges,
            "league_avg": league_avg
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Official profile error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# DEFENSE RANKINGS
# ============================================

@app.post("/defense-rank")
async def get_defense_rank(request: DefenseRankRequest):
    try:
        sport = request.sport.upper()
        if sport not in SUPPORTED_SPORTS:
            raise HTTPException(status_code=400, detail=f"Sport must be one of: {SUPPORTED_SPORTS}")
        rank = DefensiveRankService.get_rank(sport, request.team, request.position)
        context = DefensiveRankService.rank_to_context(sport, request.team, request.position)
        total = DefensiveRankService.get_total_teams(sport)
        soft_threshold, tough_threshold = int(total * 0.75), int(total * 0.25)
        quality = "SOFT 🎯" if rank >= soft_threshold else "TOUGH 🔒" if rank <= tough_threshold else "NEUTRAL"
        return {"status": "success", "sport": sport, "team": request.team, "position": request.position, "rank": rank, "total_teams": total, "context": context, "quality": quality}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/defense-rankings/{sport}/{position}")
async def get_defense_rankings(sport: str, position: str):
    try:
        sport = sport.upper()
        if sport not in SUPPORTED_SPORTS:
            raise HTTPException(status_code=400, detail=f"Sport must be one of: {SUPPORTED_SPORTS}")
        rankings = DefensiveRankService.get_rankings_for_position(sport, position)
        if not rankings:
            raise HTTPException(status_code=400, detail=f"Invalid position for {sport}. Valid: {SPORT_POSITIONS.get(sport, [])}")
        sorted_rankings = dict(sorted(rankings.items(), key=lambda x: x[1]))
        total = len(rankings)
        smash_teams = [team for team, rank in rankings.items() if rank >= int(total * 0.8)]
        return {"status": "success", "sport": sport, "position": position, "total_teams": total, "rankings": sorted_rankings, "smash_spots": smash_teams, "best_defense": list(sorted_rankings.keys())[0], "worst_defense": list(sorted_rankings.keys())[-1]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# VACUUM & PACE
# ============================================

@app.post("/usage-vacuum")
async def calculate_usage_vacuum(request: VacuumRequest):
    try:
        sport = request.sport.upper()
        if sport not in SUPPORTED_SPORTS:
            raise HTTPException(status_code=400, detail=f"Sport must be one of: {SUPPORTED_SPORTS}")
        injuries = [inj.dict() for inj in request.injuries]
        vacuum = UsageVacuumService.calculate_vacuum(sport, injuries)
        context = UsageVacuumService.vacuum_to_context(vacuum)
        impact = "SMASH SPOT 💎" if vacuum >= 35 else "SIGNIFICANT 🔥" if vacuum >= 20 else "MODERATE ⚡" if vacuum >= 10 else "MINIMAL"
        return {"status": "success", "sport": sport, "vacuum": vacuum, "context": context, "impact": impact, "injuries_counted": len([i for i in injuries if i.get('status', '').upper() == 'OUT'])}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/game-pace")
async def get_game_pace(request: PaceRequest):
    try:
        sport = request.sport.upper()
        if sport not in SUPPORTED_SPORTS:
            raise HTTPException(status_code=400, detail=f"Sport must be one of: {SUPPORTED_SPORTS}")
        pace = PaceVectorService.get_game_pace(sport, request.team1, request.team2)
        context = PaceVectorService.pace_to_context(sport, request.team1, request.team2)
        pace1, pace2 = PaceVectorService.get_team_pace(sport, request.team1), PaceVectorService.get_team_pace(sport, request.team2)
        league_avg = PaceVectorService.LEAGUE_AVG.get(sport, 0)
        category = "FAST ⚡" if context >= 0.7 else "SLOW 🐢" if context <= 0.3 else "AVERAGE"
        return {"status": "success", "sport": sport, "game_pace": pace, "context": context, "category": category, "team1_pace": pace1, "team2_pace": pace2, "league_avg": league_avg}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/pace-rankings/{sport}")
async def get_pace_rankings(sport: str):
    try:
        sport = sport.upper()
        if sport not in SUPPORTED_SPORTS:
            raise HTTPException(status_code=400, detail=f"Sport must be one of: {SUPPORTED_SPORTS}")
        rankings = PaceVectorService.get_all_rankings(sport)
        sorted_pace = dict(sorted(rankings.items(), key=lambda x: x[1], reverse=True))
        league_avg = PaceVectorService.LEAGUE_AVG.get(sport, 0)
        fast_teams = [team for team, pace in rankings.items() if pace > league_avg * 1.03]
        return {"status": "success", "sport": sport, "rankings": sorted_pace, "fast_teams": fast_teams, "fastest": list(sorted_pace.keys())[0] if sorted_pace else None, "slowest": list(sorted_pace.keys())[-1] if sorted_pace else None, "league_avg": league_avg}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# MLB PARK FACTORS
# ============================================

@app.post("/park-factor")
async def get_park_factor(request: ParkFactorRequest):
    try:
        factor = ParkFactorService.get_park_factor(request.team)
        env = ParkFactorService.get_game_environment(request.team, "")
        return {"status": "success", "team": request.team, "park_factor": factor, "environment": env["environment"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/park-factors")
async def get_all_park_factors():
    try:
        from context_layer import MLB_PARK_FACTORS, MLB_TEAM_TO_PARK
        sorted_parks = dict(sorted(MLB_PARK_FACTORS.items(), key=lambda x: x[1], reverse=True))
        hitter_parks = [park for park, factor in MLB_PARK_FACTORS.items() if factor >= 1.05]
        pitcher_parks = [park for park, factor in MLB_PARK_FACTORS.items() if factor <= 0.92]
        return {"status": "success", "park_factors": sorted_parks, "team_to_park": MLB_TEAM_TO_PARK, "hitter_friendly": hitter_parks, "pitcher_friendly": pitcher_parks}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# EDGE & HEALTH
# ============================================

@app.post("/calculate-edge")
async def calculate_betting_edge(request: EdgeCalculationRequest):
    try:
        if request.betting_odds < 0:
            decimal_odds = 1 + (100 / abs(request.betting_odds))
            implied_prob = abs(request.betting_odds) / (abs(request.betting_odds) + 100)
        else:
            decimal_odds = 1 + (request.betting_odds / 100)
            implied_prob = 100 / (request.betting_odds + 100)
        edge = request.your_probability - implied_prob
        edge_percent = edge * 100
        ev = (request.your_probability * (decimal_odds - 1) * 100) - ((1 - request.your_probability) * 100)
        kelly = max(0, edge / (decimal_odds - 1)) if decimal_odds > 1 else 0
        confidence = "HIGH" if edge_percent >= 10 else "MEDIUM" if edge_percent >= 5 else "LOW" if edge_percent > 0 else "NO EDGE"
        return {"status": "success", "edge_analysis": {"your_probability": round(request.your_probability * 100, 1), "implied_probability": round(implied_prob * 100, 1), "edge_percent": round(edge_percent, 2), "ev_per_100": round(ev, 2), "kelly_bet_size": round(kelly * 100, 1), "decimal_odds": round(decimal_odds, 3), "confidence": confidence}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# LSTM BRAIN ENDPOINTS
# ============================================

class LSTMPredictRequest(BaseModel):
    """Direct LSTM Brain prediction request."""
    sport: str
    current_features: LSTMHistoryInput
    historical_features: Optional[List[LSTMHistoryInput]] = None
    scale_factor: Optional[float] = 5.0

@app.post("/brain/predict")
async def lstm_brain_predict(request: LSTMPredictRequest):
    """
    Direct LSTM Brain prediction.
    
    Runs the (15, 6) LSTM neural network on provided features.
    """
    try:
        sport = request.sport.upper()
        if sport not in SUPPORTED_SPORTS:
            raise HTTPException(status_code=400, detail=f"Sport must be one of: {SUPPORTED_SPORTS}")
        
        historical = None
        if request.historical_features:
            historical = [h.dict() for h in request.historical_features]
        
        result = lstm_brain_manager.predict(
            sport=sport,
            current_features=request.current_features.dict(),
            historical_features=historical,
            scale_factor=request.scale_factor or 5.0
        )
        
        return {
            "status": "success",
            "sport": sport,
            "brain_output": result
        }
    except Exception as e:
        logger.error(f"LSTM Brain error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/brain/status")
async def lstm_brain_status():
    """Get LSTM Brain status for all sports."""
    return {
        "status": "success",
        "brain_type": "Multi-Sport LSTM",
        "input_shape": "(15, 6)",
        "architecture": "Bidirectional LSTM (64) -> LSTM (32) -> Dense (32) -> Dense (16) -> Output",
        "sports": lstm_brain_manager.get_status()
    }

# ============================================
# AUTO-GRADER ENDPOINTS (FEEDBACK LOOP)
# ============================================

class GradeRequest(BaseModel):
    """Grade a prediction with actual result."""
    prediction_id: str
    actual_value: float

class BulkGradeRequest(BaseModel):
    """Bulk grade predictions."""
    sport: str
    results: List[Dict]  # [{"player_name": str, "stat_type": str, "actual": float}]

class BiasRequest(BaseModel):
    """Request bias analysis."""
    sport: str
    stat_type: Optional[str] = "all"
    days_back: Optional[int] = 1

class AuditRequest(BaseModel):
    """Request daily audit."""
    days_back: Optional[int] = 1

@app.get("/grader/weights")
async def get_grader_weights():
    """
    Get current dynamic weights for all sports.
    
    These weights are adjusted automatically by the feedback loop.
    """
    return {
        "status": "success",
        "weights": auto_grader.get_all_weights(),
        "description": "Weights are dynamically adjusted based on prediction accuracy"
    }

@app.get("/grader/weights/{sport}")
async def get_sport_weights(sport: str, stat_type: str = "points"):
    """Get weights for a specific sport and stat type."""
    sport = sport.upper()
    if sport not in SUPPORTED_SPORTS:
        raise HTTPException(status_code=400, detail=f"Sport must be one of: {SUPPORTED_SPORTS}")
    
    return {
        "status": "success",
        "sport": sport,
        "stat_type": stat_type,
        "weights": auto_grader.get_weights(sport, stat_type)
    }

@app.post("/grader/grade")
async def grade_prediction(request: GradeRequest):
    """
    Grade a single prediction with actual result.
    
    Call this after game completes with actual player stats.
    """
    result = auto_grader.grade_prediction(request.prediction_id, request.actual_value)
    
    if result is None:
        raise HTTPException(status_code=404, detail=f"Prediction not found: {request.prediction_id}")
    
    return {
        "status": "success",
        "grading": result
    }

@app.post("/grader/grade-bulk")
async def grade_bulk_predictions(request: BulkGradeRequest):
    """
    Grade multiple predictions at once.
    
    Useful for end-of-day grading of all predictions.
    """
    sport = request.sport.upper()
    if sport not in SUPPORTED_SPORTS:
        raise HTTPException(status_code=400, detail=f"Sport must be one of: {SUPPORTED_SPORTS}")
    
    result = auto_grader.bulk_grade(sport, request.results)
    
    return {
        "status": "success",
        "sport": sport,
        "grading": result
    }

@app.post("/grader/bias")
async def get_bias_analysis(request: BiasRequest):
    """
    Get bias analysis for predictions.
    
    Shows which factors are over/under-predicting.
    """
    sport = request.sport.upper()
    if sport not in SUPPORTED_SPORTS:
        raise HTTPException(status_code=400, detail=f"Sport must be one of: {SUPPORTED_SPORTS}")
    
    result = auto_grader.calculate_bias(sport, request.stat_type or "all", request.days_back or 1)
    
    return {
        "status": "success",
        "bias_analysis": result
    }

@app.post("/grader/audit")
async def run_daily_audit(request: AuditRequest):
    """
    Run daily audit to adjust weights.
    
    This is the core feedback loop - call daily after grading predictions.
    It analyzes yesterday's bias and adjusts weights to improve accuracy.
    """
    result = auto_grader.run_daily_audit(request.days_back or 1)
    
    return {
        "status": "success",
        "audit": result
    }

@app.post("/grader/adjust-weights")
async def adjust_weights(sport: str, stat_type: str = "points", days_back: int = 1, apply: bool = True):
    """
    Manually trigger weight adjustment for specific sport/stat.
    """
    sport = sport.upper()
    if sport not in SUPPORTED_SPORTS:
        raise HTTPException(status_code=400, detail=f"Sport must be one of: {SUPPORTED_SPORTS}")
    
    result = auto_grader.adjust_weights(sport, stat_type, days_back, apply_changes=apply)
    
    return {
        "status": "success",
        "adjustment": result
    }

# ============================================
# ESOTERIC ENDPOINTS (The "Magic")
# ============================================

@app.post("/esoteric/analyze")
async def esoteric_full_analysis(request: EsotericRequest):
    """
    Full esoteric analysis combining all 4 models:
    - Gematria (Hebrew numerology)
    - Numerology (birth dates, jersey numbers)
    - Sacred Geometry (Fibonacci, golden ratio)
    - Astrology (moon phase, zodiac)
    
    Also detects "Harmonic Convergence" when 3+ models agree.
    """
    try:
        # Parse game date
        if request.game_date:
            game_date = datetime.strptime(request.game_date, "%Y-%m-%d")
        else:
            game_date = datetime.now()
        
        result = EsotericEngine.analyze(
            player_name=request.player_name,
            opponent=request.opponent,
            line=request.line,
            game_date=game_date,
            player_avg=request.player_avg or 0.0,
            spread=request.spread or 0.0,
            total=request.total or 220.0,
            jersey_number=request.jersey_number or 0
        )
        
        return {
            "status": "success",
            "player": request.player_name,
            "opponent": request.opponent,
            "line": request.line,
            "game_date": game_date.strftime("%Y-%m-%d"),
            "analysis": result
        }
        
    except Exception as e:
        logger.error(f"Esoteric analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Esoteric analysis failed: {str(e)}")


@app.post("/esoteric/gematria")
async def gematria_analysis(player_name: str, opponent: str, line: float):
    """Gematria (Hebrew numerology) analysis only."""
    result = GematriaCalculator.analyze(player_name, opponent, line)
    return {"status": "success", "analysis": result}


@app.post("/esoteric/numerology")
async def numerology_analysis(player_name: str, jersey_number: int = 0, game_date: str = None, line: float = 0.0):
    """Numerology analysis only."""
    date = datetime.strptime(game_date, "%Y-%m-%d") if game_date else datetime.now()
    result = NumerologyEngine.analyze(player_name, jersey_number, date, line)
    return {"status": "success", "analysis": result}


@app.post("/esoteric/sacred-geometry")
async def sacred_geometry_analysis(spread: float = 0.0, total: float = 220.0, line: float = 0.0, player_avg: float = 0.0):
    """Sacred Geometry (Fibonacci, golden ratio) analysis only."""
    result = SacredGeometryAnalyzer.analyze(spread, total, line, player_avg)
    return {"status": "success", "analysis": result}


@app.post("/esoteric/astrology")
async def astrology_analysis(game_date: str = None):
    """Astrology (moon phase, zodiac) analysis only."""
    date = datetime.strptime(game_date, "%Y-%m-%d") if game_date else datetime.now()
    result = AstrologyTracker.analyze(date)
    return {"status": "success", "analysis": result}


# ============================================
# SYSTEM STATUS
# ============================================

@app.get("/health")
async def health_check():
    return {
        "status": "healthy", 
        "timestamp": datetime.now().isoformat(), 
        "version": "7.2.0", 
        "context_layer": "active", 
        "officials_layer": "active",
        "lstm_brain": "active",
        "auto_grader": "active",
        "esoteric_engine": "active",
        "live_data_router": "active",
        "supported_sports": SUPPORTED_SPORTS
    }

@app.get("/model-status")
async def model_status():
    return {
        "version": "7.2.0",
        "supported_sports": SUPPORTED_SPORTS,
        "context_layer": {
            "usage_vacuum": "ready",
            "defensive_rank": "ready",
            "pace_vector": "ready",
            "park_factor": "ready (MLB)",
            "context_generator": "ready"
        },
        "officials_layer": {
            "nba_officials": "35+ refs",
            "nfl_officials": "20+ refs",
            "mlb_officials": "20+ umps",
            "nhl_officials": "20+ refs",
            "ncaab_officials": "20+ refs"
        },
        "lstm_brain": lstm_brain_manager.get_status(),
        "auto_grader": {
            "status": "active",
            "weights_per_sport": len(auto_grader.weights),
            "predictions_logged": sum(len(p) for p in auto_grader.predictions.values())
        },
        "live_data": {
            "odds_api": "ready (set ODDS_API_KEY)",
            "espn": "ready (free)",
            "balldontlie": "ready (set BALLDONTLIE_API_KEY)",
            "endpoints": ["/live/games", "/live/props", "/live/injuries", "/live/slate"]
        },
        "esoteric_engine": {
            "gematria": "active",
            "numerology": "active",
            "sacred_geometry": "active",
            "astrology": "active",
            "harmonic_convergence": "active"
        }
    }

if __name__ == "__main__":
    logger.info("Starting Multi-Sport AI Betting API v7.2.0...")
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
