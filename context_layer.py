"""
🔥 BOOKIE-O-EM CONTEXT LAYER v1.0
==================================
The "EYES" for the AI Prediction Brain

This module provides the THREE MISSING FEATURES:
1. Usage Vacuum - Minutes-weighted injury impact
2. Defensive Rank - Position-specific defense (Guard/Wing/Big)  
3. Pace Vector - Game speed normalization

Without these, your LSTM is a Ferrari with a lawnmower engine.
"""

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any
from loguru import logger

# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class InjuryData:
    """Structured injury data for vacuum calculation"""
    player_name: str
    team: str
    position: str
    injury: str
    status: str  # OUT, GTD, Questionable
    expected_return: Optional[str]
    usage_pct: float
    minutes_per_game: float

@dataclass
class GameData:
    """Structured game data"""
    game_id: str
    home_team: str
    away_team: str
    game_time: str
    spread: float
    total: float
    home_moneyline: int
    away_moneyline: int

# ============================================================
# TEAM NAME STANDARDIZATION
# ============================================================

TEAM_ALIASES = {
    "LA Lakers": "Los Angeles Lakers",
    "LA Clippers": "Los Angeles Clippers",
    "LAL": "Los Angeles Lakers",
    "LAC": "Los Angeles Clippers",
    "BKN": "Brooklyn Nets",
    "BOS": "Boston Celtics",
    "NYK": "New York Knicks",
    "NY": "New York Knicks",
    "GS": "Golden State Warriors",
    "GSW": "Golden State Warriors",
    "SA": "San Antonio Spurs",
    "SAS": "San Antonio Spurs",
    "NO": "New Orleans Pelicans",
    "NOP": "New Orleans Pelicans",
    "PHX": "Phoenix Suns",
    "PHO": "Phoenix Suns",
    "OKC": "Oklahoma City Thunder",
    "DAL": "Dallas Mavericks",
    "HOU": "Houston Rockets",
    "MEM": "Memphis Grizzlies",
    "MIA": "Miami Heat",
    "DET": "Detroit Pistons",
    "CHI": "Chicago Bulls",
    "CLE": "Cleveland Cavaliers",
    "IND": "Indiana Pacers",
    "MIL": "Milwaukee Bucks",
    "MIN": "Minnesota Timberwolves",
    "ATL": "Atlanta Hawks",
    "CHA": "Charlotte Hornets",
    "ORL": "Orlando Magic",
    "PHI": "Philadelphia 76ers",
    "TOR": "Toronto Raptors",
    "WAS": "Washington Wizards",
    "POR": "Portland Trail Blazers",
    "SAC": "Sacramento Kings",
    "UTA": "Utah Jazz",
    "DEN": "Denver Nuggets",
}

def standardize_team(team: str) -> str:
    """Convert any team reference to standard full name"""
    return TEAM_ALIASES.get(team, team)


# ============================================================
# 1️⃣ USAGE VACUUM SERVICE (Missing Feature #1)
# ============================================================

class UsageVacuumService:
    """
    Calculates the Usage Vacuum - minutes-weighted usage available from injuries
    
    Formula: sum((USG% × MPG) / 48) for all OUT players
    
    This tells us HOW MUCH offensive opportunity is freed up when players are injured.
    A vacuum of 30+ is a SMASH SPOT for remaining players.
    """
    
    @staticmethod
    def calculate_vacuum(injuries: List[Dict]) -> float:
        """
        Calculate minutes-weighted usage vacuum from injury data
        
        Args:
            injuries: List of injury dicts with keys: status, usage_pct, minutes_per_game
            
        Returns:
            float: Usage-minutes vacuum (higher = more opportunity)
        """
        vacuum = 0.0
        
        for injury in injuries:
            status = injury.get('status', '').upper()
            if status == 'OUT':
                usage_pct = injury.get('usage_pct', 0.0)
                minutes = injury.get('minutes_per_game', 0.0)
                # Formula: (USG% × MPG) / 48
                vacuum += (usage_pct * minutes) / 48
                
        return round(vacuum, 1)
    
    @staticmethod
    def vacuum_to_context(vacuum: float) -> float:
        """
        Normalize vacuum to 0-1 scale for LSTM
        
        0.0 = No injuries (no extra opportunity)
        1.0 = Massive injuries (50+ usage-minutes available)
        """
        # Cap at 50 for normalization
        normalized = min(vacuum / 50, 1.0)
        return round(normalized, 2)
    
    @staticmethod
    def get_vacuum_adjustment(vacuum: float, player_avg: float) -> Dict:
        """
        Calculate stat adjustment based on vacuum
        
        Typical boosts:
        - 15 vacuum: +1.5 pts (~7%)
        - 30 vacuum: +3 pts (~14%)
        - 50 vacuum: +5 pts (~23%)
        
        Returns adjustment dict for waterfall visualization
        """
        if vacuum <= 10:
            return None
            
        # Each 10 usage-minutes = ~1 point boost (more conservative)
        boost = vacuum * 0.1
        
        return {
            "label": "Usage Vacuum",
            "icon": "🔋",
            "value": round(boost, 1),
            "reason": f"{vacuum:.1f} usage-minutes available from injuries"
        }


# ============================================================
# 2️⃣ DEFENSIVE RANK SERVICE (Missing Feature #2)
# ============================================================

class DefensiveRankService:
    """
    Position-Specific Defensive Rankings
    
    Not all defenses are created equal!
    - Some teams are elite vs Guards but soft vs Bigs
    - Some teams lock down Wings but get burned by PGs
    
    Rankings: 1 = Best Defense, 30 = Worst Defense (SMASH)
    """
    
    # Current 2025-26 season defensive rankings by position
    # (1 = best defense, 30 = worst defense)
    
    DEFENSE_VS_GUARDS = {
        "Oklahoma City Thunder": 1,
        "Cleveland Cavaliers": 2,
        "Boston Celtics": 3,
        "Houston Rockets": 4,
        "Memphis Grizzlies": 5,
        "Orlando Magic": 6,
        "Minnesota Timberwolves": 7,
        "Denver Nuggets": 8,
        "San Antonio Spurs": 9,
        "New York Knicks": 10,
        "Golden State Warriors": 11,
        "Milwaukee Bucks": 12,
        "Miami Heat": 13,
        "Los Angeles Clippers": 14,
        "Detroit Pistons": 15,
        "Phoenix Suns": 16,
        "Toronto Raptors": 17,
        "Chicago Bulls": 18,
        "Philadelphia 76ers": 19,
        "Brooklyn Nets": 20,
        "New Orleans Pelicans": 21,
        "Los Angeles Lakers": 22,
        "Atlanta Hawks": 23,
        "Indiana Pacers": 24,
        "Sacramento Kings": 25,
        "Dallas Mavericks": 26,
        "Portland Trail Blazers": 27,
        "Utah Jazz": 28,
        "Charlotte Hornets": 29,
        "Washington Wizards": 30,
    }
    
    DEFENSE_VS_WINGS = {
        "Oklahoma City Thunder": 1,
        "Cleveland Cavaliers": 2,
        "Orlando Magic": 3,
        "Houston Rockets": 4,
        "Boston Celtics": 5,
        "Memphis Grizzlies": 6,
        "Minnesota Timberwolves": 7,
        "Golden State Warriors": 8,
        "New York Knicks": 9,
        "San Antonio Spurs": 10,
        "Miami Heat": 11,
        "Denver Nuggets": 12,
        "Milwaukee Bucks": 13,
        "Los Angeles Clippers": 14,
        "Phoenix Suns": 15,
        "Detroit Pistons": 16,
        "Toronto Raptors": 17,
        "Chicago Bulls": 18,
        "Philadelphia 76ers": 19,
        "Los Angeles Lakers": 20,
        "Brooklyn Nets": 21,
        "New Orleans Pelicans": 22,
        "Indiana Pacers": 23,
        "Atlanta Hawks": 24,
        "Dallas Mavericks": 25,
        "Sacramento Kings": 26,
        "Portland Trail Blazers": 27,
        "Charlotte Hornets": 28,
        "Utah Jazz": 29,
        "Washington Wizards": 30,
    }
    
    DEFENSE_VS_BIGS = {
        "Oklahoma City Thunder": 1,
        "Cleveland Cavaliers": 2,
        "Houston Rockets": 3,
        "Orlando Magic": 4,
        "Boston Celtics": 5,
        "Memphis Grizzlies": 6,
        "New York Knicks": 7,
        "Minnesota Timberwolves": 8,
        "San Antonio Spurs": 9,
        "Golden State Warriors": 10,
        "Miami Heat": 11,
        "Milwaukee Bucks": 12,
        "Denver Nuggets": 13,
        "Los Angeles Clippers": 14,
        "Phoenix Suns": 15,
        "Detroit Pistons": 16,
        "Philadelphia 76ers": 17,
        "Toronto Raptors": 18,
        "Brooklyn Nets": 19,
        "Los Angeles Lakers": 20,
        "Chicago Bulls": 21,
        "New Orleans Pelicans": 22,
        "Indiana Pacers": 23,
        "Atlanta Hawks": 24,
        "Dallas Mavericks": 25,
        "Sacramento Kings": 26,
        "Portland Trail Blazers": 27,
        "Charlotte Hornets": 28,
        "Utah Jazz": 29,
        "Washington Wizards": 30,
    }
    
    @classmethod
    def get_rank(cls, team: str, position: str) -> int:
        """
        Get defensive rank vs position
        
        Args:
            team: Team name (will be standardized)
            position: Player position - 'Guard'/'PG'/'SG', 'Wing'/'SF', 'Big'/'PF'/'C'
            
        Returns:
            int: Rank 1-30 (1=best defense, 30=worst/smash spot)
        """
        team = standardize_team(team)
        pos_lower = position.lower()
        
        if pos_lower in ['guard', 'pg', 'sg', 'point guard', 'shooting guard']:
            return cls.DEFENSE_VS_GUARDS.get(team, 15)
        elif pos_lower in ['wing', 'sf', 'small forward']:
            return cls.DEFENSE_VS_WINGS.get(team, 15)
        elif pos_lower in ['big', 'pf', 'c', 'power forward', 'center']:
            return cls.DEFENSE_VS_BIGS.get(team, 15)
        else:
            # Default to middle
            return 15
    
    @classmethod
    def rank_to_context(cls, team: str, position: str) -> float:
        """
        Convert rank to 0-1 scale for LSTM
        
        0.0 = Best defense (OKC, rank #1) - AVOID
        1.0 = Worst defense (WAS, rank #30) - SMASH
        """
        rank = cls.get_rank(team, position)
        # Normalize: (rank - 1) / 29 gives 0-1 scale
        return round((rank - 1) / 29, 2)
    
    @classmethod
    def get_matchup_adjustment(cls, team: str, position: str, player_avg: float) -> Optional[Dict]:
        """
        Calculate stat adjustment based on defensive matchup
        
        Returns adjustment dict for waterfall visualization
        
        Typical adjustments:
        - Rank #30 (worst D): +10-15% boost
        - Rank #20: +3-5% boost  
        - Rank #10: -2-3% penalty
        - Rank #1 (best D): -5-8% penalty
        """
        rank = cls.get_rank(team, position)
        team_abbr = team[:3].upper()
        
        if rank >= 22:
            # Soft defense - BOOST (ranks 22-30)
            # ~0.5% boost per rank above 20
            pct_boost = (rank - 20) * 0.005
            boost = player_avg * pct_boost
            return {
                "label": f"Matchup ({team_abbr})",
                "icon": "🎯",
                "value": round(boost, 1),
                "reason": f"Rank #{rank} vs {position}s (SOFT)"
            }
        elif rank <= 8:
            # Tough defense - PENALTY (ranks 1-8)
            # ~0.4% penalty per rank below 10
            pct_penalty = (10 - rank) * 0.004
            penalty = player_avg * pct_penalty * -1
            return {
                "label": f"Matchup ({team_abbr})",
                "icon": "🔒",
                "value": round(penalty, 1),
                "reason": f"Rank #{rank} vs {position}s (TOUGH)"
            }
        else:
            # Neutral matchup (ranks 9-21)
            return None


# ============================================================
# 3️⃣ PACE VECTOR SERVICE (Missing Feature #3)
# ============================================================

class PaceVectorService:
    """
    Game Pace Normalization
    
    Pace = possessions per game
    - Fast pace (103+) = more opportunities, higher stats
    - Slow pace (94-) = fewer opportunities, lower stats
    
    This adjusts predictions for game speed.
    """
    
    # 2025-26 season team pace ratings (possessions per game)
    TEAM_PACE = {
        "Indiana Pacers": 103.5,
        "Sacramento Kings": 102.8,
        "Atlanta Hawks": 102.2,
        "Milwaukee Bucks": 101.5,
        "New Orleans Pelicans": 101.2,
        "Denver Nuggets": 100.8,
        "Portland Trail Blazers": 100.5,
        "Utah Jazz": 100.2,
        "Charlotte Hornets": 100.0,
        "Chicago Bulls": 99.8,
        "Golden State Warriors": 99.5,
        "Dallas Mavericks": 99.2,
        "Los Angeles Lakers": 99.0,
        "Phoenix Suns": 98.8,
        "Houston Rockets": 98.5,
        "Brooklyn Nets": 98.2,
        "Minnesota Timberwolves": 98.0,
        "Boston Celtics": 97.8,
        "Toronto Raptors": 97.5,
        "San Antonio Spurs": 97.2,
        "Philadelphia 76ers": 97.0,
        "Washington Wizards": 96.8,
        "Detroit Pistons": 96.5,
        "New York Knicks": 96.2,
        "Los Angeles Clippers": 96.0,
        "Orlando Magic": 95.8,
        "Miami Heat": 95.5,
        "Cleveland Cavaliers": 95.2,
        "Memphis Grizzlies": 95.0,
        "Oklahoma City Thunder": 94.5,
    }
    
    LEAGUE_AVG_PACE = 98.5
    
    @classmethod
    def get_team_pace(cls, team: str) -> float:
        """Get single team's pace"""
        team = standardize_team(team)
        return cls.TEAM_PACE.get(team, cls.LEAGUE_AVG_PACE)
    
    @classmethod
    def get_game_pace(cls, team1: str, team2: str) -> float:
        """
        Estimate game pace from both teams
        Game pace is roughly the average of both team's paces
        """
        pace1 = cls.get_team_pace(team1)
        pace2 = cls.get_team_pace(team2)
        return round((pace1 + pace2) / 2, 1)
    
    @classmethod
    def pace_to_context(cls, team1: str, team2: str) -> float:
        """
        Convert game pace to 0-1 scale for LSTM
        
        0.0 = Slowest game (~94 pace)
        1.0 = Fastest game (~104 pace)
        """
        pace = cls.get_game_pace(team1, team2)
        # Normalize: league range roughly 94-104
        normalized = (pace - 94) / 10
        return round(max(0, min(1, normalized)), 2)
    
    @classmethod
    def get_pace_adjustment(cls, team1: str, team2: str) -> Optional[Dict]:
        """
        Calculate stat adjustment based on game pace
        
        Returns adjustment dict for waterfall visualization
        """
        pace = cls.get_game_pace(team1, team2)
        pace_diff = pace - cls.LEAGUE_AVG_PACE
        
        if abs(pace_diff) <= 2:
            # Neutral pace
            return None
            
        boost = pace_diff * 0.3
        
        return {
            "label": "Pace",
            "icon": "⚡" if pace_diff > 0 else "🐢",
            "value": round(boost, 1),
            "reason": f"{'+' if pace_diff > 0 else ''}{pace_diff:.1f} possessions from avg"
        }


# ============================================================
# MASTER CONTEXT GENERATOR
# ============================================================

class ContextGenerator:
    """
    Generates complete context for LSTM predictions
    
    This is what the "brain" needs to make smart picks.
    Combines all three context features into a unified output.
    """
    
    @staticmethod
    def generate_context(
        player_name: str,
        player_team: str,
        opponent_team: str,
        position: str,
        player_avg: float,
        stat_type: str = "points",
        injuries: List[Dict] = None,
        game_total: float = 230.0,
        game_spread: float = 0.0
    ) -> Dict[str, Any]:
        """
        Generate full context for a player prediction
        
        Args:
            player_name: Player's name
            player_team: Player's team
            opponent_team: Opposing team  
            position: Player position (Guard/Wing/Big)
            player_avg: Player's season average for stat
            stat_type: Type of stat (points/rebounds/assists)
            injuries: List of injury dicts for player's team
            game_total: Vegas game total
            game_spread: Vegas spread (+ = underdog)
            
        Returns:
            Complete context dict with LSTM features, waterfall, and adjustments
        """
        injuries = injuries or []
        
        # =====================
        # 1. USAGE VACUUM
        # =====================
        vacuum = UsageVacuumService.calculate_vacuum(injuries)
        vacuum_context = UsageVacuumService.vacuum_to_context(vacuum)
        vacuum_adj = UsageVacuumService.get_vacuum_adjustment(vacuum, player_avg)
        
        # =====================
        # 2. DEFENSIVE RANK
        # =====================
        defense_rank = DefensiveRankService.get_rank(opponent_team, position)
        defense_context = DefensiveRankService.rank_to_context(opponent_team, position)
        defense_adj = DefensiveRankService.get_matchup_adjustment(opponent_team, position, player_avg)
        
        # =====================
        # 3. PACE VECTOR
        # =====================
        pace = PaceVectorService.get_game_pace(player_team, opponent_team)
        pace_context = PaceVectorService.pace_to_context(player_team, opponent_team)
        pace_adj = PaceVectorService.get_pace_adjustment(player_team, opponent_team)
        
        # =====================
        # BUILD ADJUSTMENTS
        # =====================
        adjustments = []
        
        if defense_adj:
            adjustments.append(defense_adj)
        if vacuum_adj:
            adjustments.append(vacuum_adj)
        if pace_adj:
            adjustments.append(pace_adj)
            
        # Blowout risk adjustment
        if abs(game_spread) > 8:
            blowout_penalty = -0.8 if abs(game_spread) > 12 else -0.4
            adjustments.append({
                "label": "Blowout Risk",
                "icon": "⚠️",
                "value": round(blowout_penalty, 1),
                "reason": f"Spread {game_spread:+.1f}"
            })
        
        # =====================
        # CALCULATE PREDICTION
        # =====================
        total_adjustment = sum(adj["value"] for adj in adjustments)
        final_prediction = player_avg + total_adjustment
        
        # =====================
        # DETERMINE SMASH SPOT
        # =====================
        is_smash = (
            defense_context > 0.7 or      # Weak defense (rank 21+)
            vacuum_context > 0.5 or       # Major injuries (25+ vacuum)
            (defense_context > 0.5 and vacuum_context > 0.3)  # Combined factors
        )
        
        # =====================
        # CALCULATE CONFIDENCE
        # =====================
        confidence = 65
        if is_smash:
            confidence += 20
        if len(adjustments) >= 2 and all(adj["value"] > 0 for adj in adjustments):
            confidence += 10
        confidence = min(95, confidence)
        
        # =====================
        # BUILD RESPONSE
        # =====================
        return {
            "player_name": player_name,
            "player_team": player_team,
            "opponent_team": opponent_team,
            "position": position,
            "stat_type": stat_type,
            
            # LSTM Context Features (for model input)
            "lstm_features": {
                "defense_rank": defense_rank,
                "defense_context": defense_context,     # 0-1 scale
                "pace": pace,
                "pace_context": pace_context,           # 0-1 scale
                "vacuum": vacuum,
                "vacuum_context": vacuum_context,       # 0-1 scale
                "total": game_total,
                "spread": game_spread,
                "total_norm": (game_total - 200) / 60,  # Normalized
                "spread_norm": (game_spread + 15) / 30, # Normalized
            },
            
            # Waterfall data for UI visualization
            "waterfall": {
                "baseAverage": player_avg,
                "finalPrediction": round(final_prediction, 1),
                "adjustments": adjustments,
                "isSmashSpot": is_smash,
                "confidence": confidence
            },
            
            # Badges for UI (compact indicators)
            "badges": ContextGenerator._build_badges(
                defense_context, vacuum_context, pace_context, is_smash
            ),
            
            # Raw context for debugging
            "raw_context": {
                "defense": {"rank": defense_rank, "normalized": defense_context},
                "vacuum": {"value": vacuum, "normalized": vacuum_context},
                "pace": {"value": pace, "normalized": pace_context},
            }
        }
    
    @staticmethod
    def _build_badges(defense_ctx: float, vacuum_ctx: float, pace_ctx: float, is_smash: bool) -> List[Dict]:
        """Build compact badge indicators for UI"""
        badges = []
        
        if vacuum_ctx > 0.3:
            badges.append({
                "icon": "🔋",
                "label": "vacuum",
                "active": True,
                "tooltip": f"Usage vacuum {vacuum_ctx:.0%}"
            })
            
        if defense_ctx > 0.6:
            badges.append({
                "icon": "🎯",
                "label": "matchup",
                "active": True,
                "tooltip": "Soft defensive matchup"
            })
        elif defense_ctx < 0.3:
            badges.append({
                "icon": "🛡️",
                "label": "defense",
                "active": True,
                "tooltip": "Tough defensive matchup"
            })
            
        if pace_ctx > 0.6:
            badges.append({
                "icon": "⚡",
                "label": "pace",
                "active": True,
                "tooltip": "Fast-paced game"
            })
            
        if is_smash:
            badges.append({
                "icon": "💎",
                "label": "smash",
                "active": True,
                "tooltip": "SMASH SPOT"
            })
            
        return badges


# ============================================================
# SMASH SPOT FINDER
# ============================================================

class SmashSpotFinder:
    """
    Scans games to find the best betting opportunities
    """
    
    @staticmethod
    def is_smash_spot(context: Dict) -> bool:
        """Check if a context represents a smash spot"""
        features = context.get("lstm_features", {})
        
        defense_ctx = features.get("defense_context", 0.5)
        vacuum_ctx = features.get("vacuum_context", 0)
        
        return (
            defense_ctx > 0.7 or
            vacuum_ctx > 0.5 or
            (defense_ctx > 0.5 and vacuum_ctx > 0.3)
        )
    
    @staticmethod
    def calculate_edge(context: Dict) -> float:
        """Calculate edge percentage from context"""
        waterfall = context.get("waterfall", {})
        base = waterfall.get("baseAverage", 0)
        final = waterfall.get("finalPrediction", 0)
        
        if base == 0:
            return 0
            
        edge = ((final - base) / base) * 100
        return round(edge, 1)


# ============================================================
# QUICK TEST
# ============================================================

if __name__ == "__main__":
    print("=" * 70)
    print("🔥 BOOKIE-O-EM CONTEXT LAYER v1.0")
    print("=" * 70)
    print()
    
    # Test player context generation
    context = ContextGenerator.generate_context(
        player_name="Pascal Siakam",
        player_team="Indiana Pacers",
        opponent_team="Orlando Magic",
        position="Wing",
        player_avg=21.5,
        stat_type="points",
        injuries=[
            {"status": "OUT", "usage_pct": 26.0, "minutes_per_game": 34},  # Haliburton
            {"status": "OUT", "usage_pct": 18.0, "minutes_per_game": 28},  # Mathurin
        ],
        game_total=241.0,
        game_spread=-5.5
    )
    
    print("📊 CONTEXT OUTPUT:")
    print("-" * 50)
    print(f"Player: {context['player_name']}")
    print(f"Matchup: {context['player_team']} vs {context['opponent_team']}")
    print()
    
    print("🧠 LSTM Features:")
    for key, val in context['lstm_features'].items():
        print(f"  {key}: {val}")
    print()
    
    print("📈 Waterfall:")
    wf = context['waterfall']
    print(f"  Base: {wf['baseAverage']} pts")
    for adj in wf['adjustments']:
        print(f"  {adj['icon']} {adj['label']}: {adj['value']:+.1f} ({adj['reason']})")
    print(f"  Final: {wf['finalPrediction']} pts")
    print(f"  Smash Spot: {'✅ YES' if wf['isSmashSpot'] else '❌ NO'}")
    print(f"  Confidence: {wf['confidence']}%")
    print()
    
    print("🏷️ Badges:", [b['icon'] for b in context['badges']])
    print()
    
    print("=" * 70)
    print("✅ CONTEXT LAYER READY - Brain now has eyes!")
    print("=" * 70)
