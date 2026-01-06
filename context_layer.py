"""
🔥 BOOKIE-O-EM CONTEXT LAYER v2.0 - MULTI-SPORT
================================================
The "EYES" for the AI Prediction Brain

Supports 5 Sports:
1. NBA - Basketball
2. NFL - Football  
3. MLB - Baseball
4. NHL - Hockey
5. NCAAB - College Basketball

Each sport has:
- Position-specific defensive rankings
- Pace/tempo metrics
- Usage/target/opportunity vacuum calculations
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from loguru import logger

# ============================================================
# SPORT CONFIGURATION
# ============================================================

SUPPORTED_SPORTS = ["NBA", "NFL", "MLB", "NHL", "NCAAB"]

SPORT_POSITIONS = {
    "NBA": ["Guard", "Wing", "Big"],
    "NFL": ["QB", "RB", "WR", "TE"],
    "MLB": ["Batter", "Pitcher"],
    "NHL": ["Center", "Winger", "Defenseman", "Goalie"],
    "NCAAB": ["Guard", "Wing", "Big"]
}

SPORT_STAT_TYPES = {
    "NBA": ["points", "rebounds", "assists", "threes", "steals", "blocks", "pts+reb", "pts+ast", "pts+reb+ast"],
    "NFL": ["passing_yards", "rushing_yards", "receiving_yards", "receptions", "touchdowns", "completions", "interceptions"],
    "MLB": ["hits", "runs", "rbis", "total_bases", "strikeouts", "walks", "hits_runs_rbis"],
    "NHL": ["goals", "assists", "points", "shots", "saves", "goals_against"],
    "NCAAB": ["points", "rebounds", "assists", "threes", "pts+reb", "pts+ast"]
}


# ============================================================
# NBA DATA (Complete)
# ============================================================

NBA_DEFENSE_VS_GUARDS = {
    "Oklahoma City Thunder": 1, "Cleveland Cavaliers": 2, "Boston Celtics": 3,
    "Houston Rockets": 4, "Memphis Grizzlies": 5, "Orlando Magic": 6,
    "Minnesota Timberwolves": 7, "Denver Nuggets": 8, "San Antonio Spurs": 9,
    "New York Knicks": 10, "Golden State Warriors": 11, "Milwaukee Bucks": 12,
    "Miami Heat": 13, "Los Angeles Clippers": 14, "Detroit Pistons": 15,
    "Phoenix Suns": 16, "Toronto Raptors": 17, "Chicago Bulls": 18,
    "Philadelphia 76ers": 19, "Brooklyn Nets": 20, "New Orleans Pelicans": 21,
    "Los Angeles Lakers": 22, "Atlanta Hawks": 23, "Indiana Pacers": 24,
    "Sacramento Kings": 25, "Dallas Mavericks": 26, "Portland Trail Blazers": 27,
    "Utah Jazz": 28, "Charlotte Hornets": 29, "Washington Wizards": 30,
}

NBA_DEFENSE_VS_WINGS = {
    "Oklahoma City Thunder": 1, "Cleveland Cavaliers": 2, "Orlando Magic": 3,
    "Houston Rockets": 4, "Boston Celtics": 5, "Memphis Grizzlies": 6,
    "Minnesota Timberwolves": 7, "Golden State Warriors": 8, "New York Knicks": 9,
    "San Antonio Spurs": 10, "Miami Heat": 11, "Denver Nuggets": 12,
    "Milwaukee Bucks": 13, "Los Angeles Clippers": 14, "Phoenix Suns": 15,
    "Detroit Pistons": 16, "Toronto Raptors": 17, "Chicago Bulls": 18,
    "Philadelphia 76ers": 19, "Los Angeles Lakers": 20, "Brooklyn Nets": 21,
    "New Orleans Pelicans": 22, "Indiana Pacers": 23, "Atlanta Hawks": 24,
    "Dallas Mavericks": 25, "Sacramento Kings": 26, "Portland Trail Blazers": 27,
    "Charlotte Hornets": 28, "Utah Jazz": 29, "Washington Wizards": 30,
}

NBA_DEFENSE_VS_BIGS = {
    "Oklahoma City Thunder": 1, "Cleveland Cavaliers": 2, "Houston Rockets": 3,
    "Orlando Magic": 4, "Boston Celtics": 5, "Memphis Grizzlies": 6,
    "New York Knicks": 7, "Minnesota Timberwolves": 8, "San Antonio Spurs": 9,
    "Golden State Warriors": 10, "Miami Heat": 11, "Milwaukee Bucks": 12,
    "Denver Nuggets": 13, "Los Angeles Clippers": 14, "Phoenix Suns": 15,
    "Detroit Pistons": 16, "Philadelphia 76ers": 17, "Toronto Raptors": 18,
    "Brooklyn Nets": 19, "Los Angeles Lakers": 20, "Chicago Bulls": 21,
    "New Orleans Pelicans": 22, "Indiana Pacers": 23, "Atlanta Hawks": 24,
    "Dallas Mavericks": 25, "Sacramento Kings": 26, "Portland Trail Blazers": 27,
    "Charlotte Hornets": 28, "Utah Jazz": 29, "Washington Wizards": 30,
}

NBA_PACE = {
    "Indiana Pacers": 103.5, "Sacramento Kings": 102.8, "Atlanta Hawks": 102.2,
    "Milwaukee Bucks": 101.5, "New Orleans Pelicans": 101.2, "Denver Nuggets": 100.8,
    "Portland Trail Blazers": 100.5, "Utah Jazz": 100.2, "Charlotte Hornets": 100.0,
    "Chicago Bulls": 99.8, "Golden State Warriors": 99.5, "Dallas Mavericks": 99.2,
    "Los Angeles Lakers": 99.0, "Phoenix Suns": 98.8, "Houston Rockets": 98.5,
    "Brooklyn Nets": 98.2, "Minnesota Timberwolves": 98.0, "Boston Celtics": 97.8,
    "Toronto Raptors": 97.5, "San Antonio Spurs": 97.2, "Philadelphia 76ers": 97.0,
    "Washington Wizards": 96.8, "Detroit Pistons": 96.5, "New York Knicks": 96.2,
    "Los Angeles Clippers": 96.0, "Orlando Magic": 95.8, "Miami Heat": 95.5,
    "Cleveland Cavaliers": 95.2, "Memphis Grizzlies": 95.0, "Oklahoma City Thunder": 94.5,
}


# ============================================================
# NFL DATA
# ============================================================

NFL_DEFENSE_VS_QB = {
    "Pittsburgh Steelers": 1, "Baltimore Ravens": 2, "Cleveland Browns": 3,
    "Buffalo Bills": 4, "San Francisco 49ers": 5, "New York Jets": 6,
    "Denver Broncos": 7, "Philadelphia Eagles": 8, "Dallas Cowboys": 9,
    "Minnesota Vikings": 10, "Kansas City Chiefs": 11, "Los Angeles Chargers": 12,
    "New England Patriots": 13, "Green Bay Packers": 14, "Miami Dolphins": 15,
    "Detroit Lions": 16, "Seattle Seahawks": 17, "Chicago Bears": 18,
    "Cincinnati Bengals": 19, "Houston Texans": 20, "Indianapolis Colts": 21,
    "Tennessee Titans": 22, "New Orleans Saints": 23, "Tampa Bay Buccaneers": 24,
    "Arizona Cardinals": 25, "Jacksonville Jaguars": 26, "Los Angeles Rams": 27,
    "Atlanta Falcons": 28, "New York Giants": 29, "Carolina Panthers": 30,
    "Las Vegas Raiders": 31, "Washington Commanders": 32,
}

NFL_DEFENSE_VS_RB = {
    "Baltimore Ravens": 1, "Pittsburgh Steelers": 2, "San Francisco 49ers": 3,
    "Buffalo Bills": 4, "Cleveland Browns": 5, "Philadelphia Eagles": 6,
    "New York Jets": 7, "Dallas Cowboys": 8, "Denver Broncos": 9,
    "Kansas City Chiefs": 10, "Minnesota Vikings": 11, "Los Angeles Chargers": 12,
    "New England Patriots": 13, "Miami Dolphins": 14, "Green Bay Packers": 15,
    "Detroit Lions": 16, "Chicago Bears": 17, "Seattle Seahawks": 18,
    "Houston Texans": 19, "Cincinnati Bengals": 20, "Tennessee Titans": 21,
    "Indianapolis Colts": 22, "Tampa Bay Buccaneers": 23, "New Orleans Saints": 24,
    "Jacksonville Jaguars": 25, "Arizona Cardinals": 26, "Atlanta Falcons": 27,
    "Los Angeles Rams": 28, "New York Giants": 29, "Las Vegas Raiders": 30,
    "Carolina Panthers": 31, "Washington Commanders": 32,
}

NFL_DEFENSE_VS_WR = {
    "Buffalo Bills": 1, "Pittsburgh Steelers": 2, "Baltimore Ravens": 3,
    "New York Jets": 4, "San Francisco 49ers": 5, "Denver Broncos": 6,
    "Philadelphia Eagles": 7, "Cleveland Browns": 8, "Dallas Cowboys": 9,
    "Kansas City Chiefs": 10, "Minnesota Vikings": 11, "New England Patriots": 12,
    "Los Angeles Chargers": 13, "Miami Dolphins": 14, "Green Bay Packers": 15,
    "Detroit Lions": 16, "Seattle Seahawks": 17, "Chicago Bears": 18,
    "Cincinnati Bengals": 19, "Houston Texans": 20, "Indianapolis Colts": 21,
    "Tennessee Titans": 22, "New Orleans Saints": 23, "Tampa Bay Buccaneers": 24,
    "Arizona Cardinals": 25, "Jacksonville Jaguars": 26, "Los Angeles Rams": 27,
    "Atlanta Falcons": 28, "New York Giants": 29, "Carolina Panthers": 30,
    "Las Vegas Raiders": 31, "Washington Commanders": 32,
}

NFL_DEFENSE_VS_TE = {
    "San Francisco 49ers": 1, "Buffalo Bills": 2, "Pittsburgh Steelers": 3,
    "Baltimore Ravens": 4, "New York Jets": 5, "Philadelphia Eagles": 6,
    "Denver Broncos": 7, "Cleveland Browns": 8, "Dallas Cowboys": 9,
    "Kansas City Chiefs": 10, "New England Patriots": 11, "Minnesota Vikings": 12,
    "Los Angeles Chargers": 13, "Green Bay Packers": 14, "Miami Dolphins": 15,
    "Detroit Lions": 16, "Seattle Seahawks": 17, "Chicago Bears": 18,
    "Cincinnati Bengals": 19, "Houston Texans": 20, "Tennessee Titans": 21,
    "Indianapolis Colts": 22, "New Orleans Saints": 23, "Tampa Bay Buccaneers": 24,
    "Arizona Cardinals": 25, "Jacksonville Jaguars": 26, "Atlanta Falcons": 27,
    "Los Angeles Rams": 28, "New York Giants": 29, "Carolina Panthers": 30,
    "Las Vegas Raiders": 31, "Washington Commanders": 32,
}

# NFL Pace = plays per game
NFL_PACE = {
    "Miami Dolphins": 68.5, "Buffalo Bills": 67.8, "Philadelphia Eagles": 67.2,
    "Dallas Cowboys": 66.8, "San Francisco 49ers": 66.5, "Detroit Lions": 66.2,
    "Kansas City Chiefs": 65.8, "Cincinnati Bengals": 65.5, "Los Angeles Chargers": 65.2,
    "Jacksonville Jaguars": 65.0, "Green Bay Packers": 64.8, "Minnesota Vikings": 64.5,
    "Seattle Seahawks": 64.2, "Houston Texans": 64.0, "Arizona Cardinals": 63.8,
    "Los Angeles Rams": 63.5, "Atlanta Falcons": 63.2, "Tampa Bay Buccaneers": 63.0,
    "Indianapolis Colts": 62.8, "New Orleans Saints": 62.5, "Denver Broncos": 62.2,
    "Chicago Bears": 62.0, "New England Patriots": 61.8, "Las Vegas Raiders": 61.5,
    "Tennessee Titans": 61.2, "Carolina Panthers": 61.0, "New York Giants": 60.8,
    "Washington Commanders": 60.5, "Cleveland Browns": 60.2, "Pittsburgh Steelers": 60.0,
    "New York Jets": 59.8, "Baltimore Ravens": 59.5,
}


# ============================================================
# MLB DATA
# ============================================================

# MLB uses park factors instead of traditional defense rankings
MLB_PARK_FACTORS = {
    # > 1.0 = hitter friendly, < 1.0 = pitcher friendly
    "Coors Field": 1.38, "Fenway Park": 1.15, "Great American Ball Park": 1.12,
    "Globe Life Field": 1.10, "Yankee Stadium": 1.08, "Citizens Bank Park": 1.06,
    "Wrigley Field": 1.05, "Guaranteed Rate Field": 1.04, "Chase Field": 1.03,
    "Minute Maid Park": 1.02, "Rogers Centre": 1.01, "American Family Field": 1.00,
    "Target Field": 0.99, "Busch Stadium": 0.98, "Nationals Park": 0.97,
    "Truist Park": 0.96, "Angel Stadium": 0.95, "Dodger Stadium": 0.94,
    "PNC Park": 0.93, "T-Mobile Park": 0.92, "Kauffman Stadium": 0.91,
    "Oracle Park": 0.90, "Tropicana Field": 0.89, "Petco Park": 0.88,
    "loanDepot Park": 0.87, "Comerica Park": 0.86, "Oakland Coliseum": 0.85,
    "Citi Field": 0.84, "Progressive Field": 0.83, "RingCentral Coliseum": 0.82,
}

MLB_TEAM_TO_PARK = {
    "Colorado Rockies": "Coors Field", "Boston Red Sox": "Fenway Park",
    "Cincinnati Reds": "Great American Ball Park", "Texas Rangers": "Globe Life Field",
    "New York Yankees": "Yankee Stadium", "Philadelphia Phillies": "Citizens Bank Park",
    "Chicago Cubs": "Wrigley Field", "Chicago White Sox": "Guaranteed Rate Field",
    "Arizona Diamondbacks": "Chase Field", "Houston Astros": "Minute Maid Park",
    "Toronto Blue Jays": "Rogers Centre", "Milwaukee Brewers": "American Family Field",
    "Minnesota Twins": "Target Field", "St. Louis Cardinals": "Busch Stadium",
    "Washington Nationals": "Nationals Park", "Atlanta Braves": "Truist Park",
    "Los Angeles Angels": "Angel Stadium", "Los Angeles Dodgers": "Dodger Stadium",
    "Pittsburgh Pirates": "PNC Park", "Seattle Mariners": "T-Mobile Park",
    "Kansas City Royals": "Kauffman Stadium", "San Francisco Giants": "Oracle Park",
    "Tampa Bay Rays": "Tropicana Field", "San Diego Padres": "Petco Park",
    "Miami Marlins": "loanDepot Park", "Detroit Tigers": "Comerica Park",
    "Oakland Athletics": "Oakland Coliseum", "New York Mets": "Citi Field",
    "Cleveland Guardians": "Progressive Field",
}

# MLB Pace = runs per game environment
MLB_PACE = {
    "Colorado Rockies": 5.8, "Boston Red Sox": 5.2, "Cincinnati Reds": 5.1,
    "Texas Rangers": 5.0, "New York Yankees": 4.9, "Philadelphia Phillies": 4.8,
    "Chicago Cubs": 4.7, "Arizona Diamondbacks": 4.7, "Houston Astros": 4.6,
    "Toronto Blue Jays": 4.6, "Milwaukee Brewers": 4.5, "Minnesota Twins": 4.5,
    "St. Louis Cardinals": 4.4, "Atlanta Braves": 4.4, "Los Angeles Angels": 4.3,
    "Los Angeles Dodgers": 4.3, "Seattle Mariners": 4.2, "Kansas City Royals": 4.2,
    "San Francisco Giants": 4.1, "Tampa Bay Rays": 4.1, "San Diego Padres": 4.0,
    "Miami Marlins": 4.0, "Detroit Tigers": 3.9, "New York Mets": 3.9,
    "Cleveland Guardians": 3.8, "Pittsburgh Pirates": 3.8, "Washington Nationals": 3.7,
    "Chicago White Sox": 3.7, "Oakland Athletics": 3.6,
}


# ============================================================
# NHL DATA
# ============================================================

NHL_DEFENSE_VS_CENTERS = {
    "Boston Bruins": 1, "Carolina Hurricanes": 2, "New Jersey Devils": 3,
    "Dallas Stars": 4, "New York Rangers": 5, "Vegas Golden Knights": 6,
    "Colorado Avalanche": 7, "Los Angeles Kings": 8, "Edmonton Oilers": 9,
    "Tampa Bay Lightning": 10, "Florida Panthers": 11, "Toronto Maple Leafs": 12,
    "Winnipeg Jets": 13, "Minnesota Wild": 14, "Seattle Kraken": 15,
    "Nashville Predators": 16, "New York Islanders": 17, "Pittsburgh Penguins": 18,
    "St. Louis Blues": 19, "Calgary Flames": 20, "Ottawa Senators": 21,
    "Detroit Red Wings": 22, "Vancouver Canucks": 23, "Buffalo Sabres": 24,
    "Philadelphia Flyers": 25, "Montreal Canadiens": 26, "Arizona Coyotes": 27,
    "Chicago Blackhawks": 28, "Anaheim Ducks": 29, "San Jose Sharks": 30,
    "Columbus Blue Jackets": 31,
}

NHL_DEFENSE_VS_WINGERS = {
    "Boston Bruins": 1, "New Jersey Devils": 2, "Carolina Hurricanes": 3,
    "Dallas Stars": 4, "Vegas Golden Knights": 5, "New York Rangers": 6,
    "Los Angeles Kings": 7, "Colorado Avalanche": 8, "Tampa Bay Lightning": 9,
    "Florida Panthers": 10, "Edmonton Oilers": 11, "Toronto Maple Leafs": 12,
    "Minnesota Wild": 13, "Winnipeg Jets": 14, "Seattle Kraken": 15,
    "New York Islanders": 16, "Nashville Predators": 17, "Pittsburgh Penguins": 18,
    "Calgary Flames": 19, "St. Louis Blues": 20, "Detroit Red Wings": 21,
    "Ottawa Senators": 22, "Vancouver Canucks": 23, "Buffalo Sabres": 24,
    "Montreal Canadiens": 25, "Philadelphia Flyers": 26, "Arizona Coyotes": 27,
    "Chicago Blackhawks": 28, "San Jose Sharks": 29, "Anaheim Ducks": 30,
    "Columbus Blue Jackets": 31,
}

NHL_DEFENSE_VS_DEFENSEMEN = {
    "Carolina Hurricanes": 1, "Boston Bruins": 2, "New Jersey Devils": 3,
    "New York Rangers": 4, "Dallas Stars": 5, "Vegas Golden Knights": 6,
    "Los Angeles Kings": 7, "Colorado Avalanche": 8, "Edmonton Oilers": 9,
    "Tampa Bay Lightning": 10, "Florida Panthers": 11, "Winnipeg Jets": 12,
    "Toronto Maple Leafs": 13, "Minnesota Wild": 14, "Seattle Kraken": 15,
    "Nashville Predators": 16, "New York Islanders": 17, "Pittsburgh Penguins": 18,
    "St. Louis Blues": 19, "Calgary Flames": 20, "Ottawa Senators": 21,
    "Vancouver Canucks": 22, "Detroit Red Wings": 23, "Buffalo Sabres": 24,
    "Philadelphia Flyers": 25, "Montreal Canadiens": 26, "Chicago Blackhawks": 27,
    "Arizona Coyotes": 28, "San Jose Sharks": 29, "Anaheim Ducks": 30,
    "Columbus Blue Jackets": 31,
}

# NHL Pace = shots per game
NHL_PACE = {
    "Colorado Avalanche": 35.5, "Florida Panthers": 35.0, "Edmonton Oilers": 34.8,
    "Toronto Maple Leafs": 34.5, "Tampa Bay Lightning": 34.2, "Boston Bruins": 34.0,
    "Vegas Golden Knights": 33.8, "Carolina Hurricanes": 33.5, "New Jersey Devils": 33.2,
    "Dallas Stars": 33.0, "New York Rangers": 32.8, "Los Angeles Kings": 32.5,
    "Winnipeg Jets": 32.2, "Seattle Kraken": 32.0, "Minnesota Wild": 31.8,
    "Pittsburgh Penguins": 31.5, "Calgary Flames": 31.2, "Nashville Predators": 31.0,
    "St. Louis Blues": 30.8, "Ottawa Senators": 30.5, "New York Islanders": 30.2,
    "Detroit Red Wings": 30.0, "Vancouver Canucks": 29.8, "Buffalo Sabres": 29.5,
    "Philadelphia Flyers": 29.2, "Montreal Canadiens": 29.0, "Arizona Coyotes": 28.8,
    "Chicago Blackhawks": 28.5, "San Jose Sharks": 28.2, "Anaheim Ducks": 28.0,
    "Columbus Blue Jackets": 27.8,
}


# ============================================================
# NCAAB DATA (Top 50 Teams)
# ============================================================

NCAAB_DEFENSE_VS_GUARDS = {
    "Houston": 1, "Auburn": 2, "Tennessee": 3, "Duke": 4, "Kansas": 5,
    "Alabama": 6, "Iowa State": 7, "Purdue": 8, "Texas": 9, "Arizona": 10,
    "Kentucky": 11, "Gonzaga": 12, "Marquette": 13, "Creighton": 14, "Baylor": 15,
    "North Carolina": 16, "UConn": 17, "Illinois": 18, "Michigan State": 19, "UCLA": 20,
    "San Diego State": 21, "BYU": 22, "Florida": 23, "Wisconsin": 24, "Texas Tech": 25,
    "TCU": 26, "Arkansas": 27, "Miami": 28, "Indiana": 29, "Villanova": 30,
    "Providence": 31, "St. John's": 32, "Virginia": 33, "Ohio State": 34, "Xavier": 35,
    "Colorado": 36, "Oregon": 37, "Memphis": 38, "Pittsburgh": 39, "Clemson": 40,
    "Iowa": 41, "Oklahoma": 42, "USC": 43, "Missouri": 44, "Michigan": 45,
    "NC State": 46, "Texas A&M": 47, "South Carolina": 48, "Kansas State": 49, "Utah": 50,
}

NCAAB_DEFENSE_VS_WINGS = {
    "Houston": 1, "Tennessee": 2, "Auburn": 3, "Duke": 4, "Alabama": 5,
    "Kansas": 6, "Purdue": 7, "Iowa State": 8, "Arizona": 9, "Texas": 10,
    "Gonzaga": 11, "Kentucky": 12, "Marquette": 13, "Creighton": 14, "UConn": 15,
    "Baylor": 16, "North Carolina": 17, "Illinois": 18, "UCLA": 19, "Michigan State": 20,
    "San Diego State": 21, "Florida": 22, "BYU": 23, "Wisconsin": 24, "Texas Tech": 25,
    "TCU": 26, "Arkansas": 27, "Miami": 28, "Indiana": 29, "Villanova": 30,
    "Providence": 31, "Virginia": 32, "St. John's": 33, "Xavier": 34, "Ohio State": 35,
    "Oregon": 36, "Colorado": 37, "Memphis": 38, "Pittsburgh": 39, "Iowa": 40,
    "Clemson": 41, "Oklahoma": 42, "USC": 43, "Michigan": 44, "Missouri": 45,
    "NC State": 46, "Texas A&M": 47, "Kansas State": 48, "South Carolina": 49, "Utah": 50,
}

NCAAB_DEFENSE_VS_BIGS = {
    "Houston": 1, "Tennessee": 2, "Purdue": 3, "Auburn": 4, "Duke": 5,
    "Alabama": 6, "Kansas": 7, "Arizona": 8, "Iowa State": 9, "Texas": 10,
    "Kentucky": 11, "Gonzaga": 12, "UConn": 13, "Marquette": 14, "Creighton": 15,
    "Baylor": 16, "Illinois": 17, "North Carolina": 18, "UCLA": 19, "Michigan State": 20,
    "San Diego State": 21, "Wisconsin": 22, "Florida": 23, "BYU": 24, "Texas Tech": 25,
    "Arkansas": 26, "TCU": 27, "Indiana": 28, "Miami": 29, "Villanova": 30,
    "Virginia": 31, "Providence": 32, "St. John's": 33, "Xavier": 34, "Ohio State": 35,
    "Colorado": 36, "Oregon": 37, "Pittsburgh": 38, "Memphis": 39, "Iowa": 40,
    "Clemson": 41, "Oklahoma": 42, "Michigan": 43, "USC": 44, "Missouri": 45,
    "Texas A&M": 46, "NC State": 47, "Kansas State": 48, "South Carolina": 49, "Utah": 50,
}

NCAAB_PACE = {
    "Gonzaga": 75.5, "Arkansas": 74.8, "Alabama": 74.5, "Auburn": 74.0,
    "Kentucky": 73.5, "Kansas": 73.0, "Duke": 72.5, "North Carolina": 72.0,
    "Creighton": 71.5, "Marquette": 71.0, "Texas": 70.5, "Arizona": 70.0,
    "Florida": 69.5, "Iowa": 69.0, "Memphis": 68.5, "BYU": 68.0,
    "Baylor": 67.5, "Illinois": 67.0, "UCLA": 66.5, "Michigan State": 66.0,
    "Indiana": 65.5, "Purdue": 65.0, "Houston": 64.5, "Tennessee": 64.0,
    "Iowa State": 63.5, "UConn": 63.0, "San Diego State": 62.5, "Texas Tech": 62.0,
    "Wisconsin": 61.5, "Virginia": 61.0, "TCU": 60.5, "Ohio State": 60.0,
}


# ============================================================
# TEAM ALIASES (All Sports)
# ============================================================

TEAM_ALIASES = {
    # NBA
    "LAL": "Los Angeles Lakers", "LAC": "Los Angeles Clippers", "GSW": "Golden State Warriors",
    "BKN": "Brooklyn Nets", "NYK": "New York Knicks", "BOS": "Boston Celtics",
    "PHI": "Philadelphia 76ers", "TOR": "Toronto Raptors", "CHI": "Chicago Bulls",
    "CLE": "Cleveland Cavaliers", "DET": "Detroit Pistons", "IND": "Indiana Pacers",
    "MIL": "Milwaukee Bucks", "ATL": "Atlanta Hawks", "CHA": "Charlotte Hornets",
    "MIA": "Miami Heat", "ORL": "Orlando Magic", "WAS": "Washington Wizards",
    "DEN": "Denver Nuggets", "MIN": "Minnesota Timberwolves", "OKC": "Oklahoma City Thunder",
    "POR": "Portland Trail Blazers", "UTA": "Utah Jazz", "DAL": "Dallas Mavericks",
    "HOU": "Houston Rockets", "MEM": "Memphis Grizzlies", "NOP": "New Orleans Pelicans",
    "SAS": "San Antonio Spurs", "PHX": "Phoenix Suns", "SAC": "Sacramento Kings",
    
    # NFL
    "KC": "Kansas City Chiefs", "SF": "San Francisco 49ers", "BUF": "Buffalo Bills",
    "DAL": "Dallas Cowboys", "PHI": "Philadelphia Eagles", "BAL": "Baltimore Ravens",
    "CIN": "Cincinnati Bengals", "JAX": "Jacksonville Jaguars", "TEN": "Tennessee Titans",
    "PIT": "Pittsburgh Steelers", "CLE": "Cleveland Browns", "LV": "Las Vegas Raiders",
    "DEN": "Denver Broncos", "LAC": "Los Angeles Chargers", "LAR": "Los Angeles Rams",
    "SEA": "Seattle Seahawks", "ARI": "Arizona Cardinals", "GB": "Green Bay Packers",
    "MIN": "Minnesota Vikings", "DET": "Detroit Lions", "CHI": "Chicago Bears",
    "NO": "New Orleans Saints", "TB": "Tampa Bay Buccaneers", "ATL": "Atlanta Falcons",
    "CAR": "Carolina Panthers", "NE": "New England Patriots", "NYJ": "New York Jets",
    "NYG": "New York Giants", "MIA": "Miami Dolphins", "IND": "Indianapolis Colts",
    "HOU": "Houston Texans", "WAS": "Washington Commanders",
    
    # MLB
    "NYY": "New York Yankees", "BOS": "Boston Red Sox", "TB": "Tampa Bay Rays",
    "TOR": "Toronto Blue Jays", "BAL": "Baltimore Orioles", "CLE": "Cleveland Guardians",
    "CWS": "Chicago White Sox", "DET": "Detroit Tigers", "KC": "Kansas City Royals",
    "MIN": "Minnesota Twins", "HOU": "Houston Astros", "LAA": "Los Angeles Angels",
    "OAK": "Oakland Athletics", "SEA": "Seattle Mariners", "TEX": "Texas Rangers",
    "ATL": "Atlanta Braves", "MIA": "Miami Marlins", "NYM": "New York Mets",
    "PHI": "Philadelphia Phillies", "WSH": "Washington Nationals", "CHC": "Chicago Cubs",
    "CIN": "Cincinnati Reds", "MIL": "Milwaukee Brewers", "PIT": "Pittsburgh Pirates",
    "STL": "St. Louis Cardinals", "ARI": "Arizona Diamondbacks", "COL": "Colorado Rockies",
    "LAD": "Los Angeles Dodgers", "SD": "San Diego Padres", "SF": "San Francisco Giants",
    
    # NHL
    "BOS": "Boston Bruins", "BUF": "Buffalo Sabres", "DET": "Detroit Red Wings",
    "FLA": "Florida Panthers", "MTL": "Montreal Canadiens", "OTT": "Ottawa Senators",
    "TB": "Tampa Bay Lightning", "TOR": "Toronto Maple Leafs", "CAR": "Carolina Hurricanes",
    "CBJ": "Columbus Blue Jackets", "NJ": "New Jersey Devils", "NYI": "New York Islanders",
    "NYR": "New York Rangers", "PHI": "Philadelphia Flyers", "PIT": "Pittsburgh Penguins",
    "WSH": "Washington Capitals", "ARI": "Arizona Coyotes", "CHI": "Chicago Blackhawks",
    "COL": "Colorado Avalanche", "DAL": "Dallas Stars", "MIN": "Minnesota Wild",
    "NSH": "Nashville Predators", "STL": "St. Louis Blues", "WPG": "Winnipeg Jets",
    "ANA": "Anaheim Ducks", "CGY": "Calgary Flames", "EDM": "Edmonton Oilers",
    "LA": "Los Angeles Kings", "SJ": "San Jose Sharks", "SEA": "Seattle Kraken",
    "VAN": "Vancouver Canucks", "VGK": "Vegas Golden Knights",
}

def standardize_team(team: str, sport: str = None) -> str:
    """Convert team abbreviation to full name"""
    return TEAM_ALIASES.get(team.upper(), team)


# ============================================================
# MULTI-SPORT DEFENSIVE RANK SERVICE
# ============================================================

class DefensiveRankService:
    """Position-specific defensive rankings for all sports"""
    
    RANKINGS = {
        "NBA": {
            "Guard": NBA_DEFENSE_VS_GUARDS,
            "Wing": NBA_DEFENSE_VS_WINGS,
            "Big": NBA_DEFENSE_VS_BIGS,
        },
        "NFL": {
            "QB": NFL_DEFENSE_VS_QB,
            "RB": NFL_DEFENSE_VS_RB,
            "WR": NFL_DEFENSE_VS_WR,
            "TE": NFL_DEFENSE_VS_TE,
        },
        "NHL": {
            "Center": NHL_DEFENSE_VS_CENTERS,
            "Winger": NHL_DEFENSE_VS_WINGERS,
            "Defenseman": NHL_DEFENSE_VS_DEFENSEMEN,
        },
        "NCAAB": {
            "Guard": NCAAB_DEFENSE_VS_GUARDS,
            "Wing": NCAAB_DEFENSE_VS_WINGS,
            "Big": NCAAB_DEFENSE_VS_BIGS,
        },
        "MLB": {
            "Batter": {},  # MLB uses park factors instead
            "Pitcher": {},
        }
    }
    
    @classmethod
    def get_rank(cls, sport: str, team: str, position: str) -> int:
        """Get defensive rank for team vs position"""
        sport = sport.upper()
        team = standardize_team(team, sport)
        
        if sport not in cls.RANKINGS:
            return 15
            
        position_map = {
            # NBA
            "pg": "Guard", "sg": "Guard", "guard": "Guard",
            "sf": "Wing", "wing": "Wing",
            "pf": "Big", "c": "Big", "big": "Big", "center": "Big",
            # NFL
            "qb": "QB", "rb": "RB", "wr": "WR", "te": "TE",
            # NHL
            "center": "Center", "c": "Center",
            "winger": "Winger", "lw": "Winger", "rw": "Winger",
            "defenseman": "Defenseman", "d": "Defenseman",
        }
        
        pos_key = position_map.get(position.lower(), position)
        
        if pos_key not in cls.RANKINGS[sport]:
            return 15
            
        rankings = cls.RANKINGS[sport][pos_key]
        return rankings.get(team, 15)
    
    @classmethod
    def get_total_teams(cls, sport: str) -> int:
        """Get number of teams for normalization"""
        totals = {"NBA": 30, "NFL": 32, "MLB": 30, "NHL": 32, "NCAAB": 50}
        return totals.get(sport.upper(), 30)
    
    @classmethod
    def rank_to_context(cls, sport: str, team: str, position: str) -> float:
        """Normalize rank to 0-1 scale"""
        rank = cls.get_rank(sport, team, position)
        total = cls.get_total_teams(sport)
        return round((rank - 1) / (total - 1), 2)
    
    @classmethod
    def get_matchup_adjustment(cls, sport: str, team: str, position: str, player_avg: float) -> Optional[Dict]:
        """Calculate stat adjustment based on matchup"""
        rank = cls.get_rank(sport, team, position)
        total = cls.get_total_teams(sport)
        
        # Soft threshold = top 25% worst defenses
        soft_threshold = int(total * 0.75)
        # Tough threshold = top 25% best defenses
        tough_threshold = int(total * 0.25)
        
        team_abbr = team[:3].upper()
        
        if rank >= soft_threshold:
            pct_boost = (rank - soft_threshold + 1) * 0.008
            boost = player_avg * pct_boost
            return {
                "label": f"Matchup ({team_abbr})",
                "icon": "🎯",
                "value": round(boost, 1),
                "reason": f"Rank #{rank}/{total} vs {position}s (SOFT)"
            }
        elif rank <= tough_threshold:
            pct_penalty = (tough_threshold - rank + 1) * 0.006
            penalty = player_avg * pct_penalty * -1
            return {
                "label": f"Matchup ({team_abbr})",
                "icon": "🔒",
                "value": round(penalty, 1),
                "reason": f"Rank #{rank}/{total} vs {position}s (TOUGH)"
            }
        return None
    
    @classmethod
    def get_rankings_for_position(cls, sport: str, position: str) -> Dict:
        """Get all rankings for a position"""
        sport = sport.upper()
        if sport not in cls.RANKINGS:
            return {}
        
        position_map = {
            "pg": "Guard", "sg": "Guard", "guard": "Guard",
            "sf": "Wing", "wing": "Wing",
            "pf": "Big", "c": "Big", "big": "Big",
            "qb": "QB", "rb": "RB", "wr": "WR", "te": "TE",
            "center": "Center", "winger": "Winger", "defenseman": "Defenseman",
        }
        pos_key = position_map.get(position.lower(), position)
        
        return cls.RANKINGS[sport].get(pos_key, {})


# ============================================================
# MULTI-SPORT PACE SERVICE
# ============================================================

class PaceVectorService:
    """Pace/tempo metrics for all sports"""
    
    PACE_DATA = {
        "NBA": NBA_PACE,
        "NFL": NFL_PACE,
        "MLB": MLB_PACE,
        "NHL": NHL_PACE,
        "NCAAB": NCAAB_PACE,
    }
    
    LEAGUE_AVG = {
        "NBA": 98.5,   # possessions
        "NFL": 63.5,   # plays
        "MLB": 4.3,    # runs
        "NHL": 31.0,   # shots
        "NCAAB": 68.0, # possessions
    }
    
    PACE_RANGE = {
        "NBA": (94, 104),
        "NFL": (59, 69),
        "MLB": (3.5, 6.0),
        "NHL": (27, 36),
        "NCAAB": (60, 76),
    }
    
    @classmethod
    def get_team_pace(cls, sport: str, team: str) -> float:
        """Get single team's pace"""
        sport = sport.upper()
        team = standardize_team(team, sport)
        pace_data = cls.PACE_DATA.get(sport, {})
        return pace_data.get(team, cls.LEAGUE_AVG.get(sport, 0))
    
    @classmethod
    def get_game_pace(cls, sport: str, team1: str, team2: str) -> float:
        """Estimate game pace from both teams"""
        pace1 = cls.get_team_pace(sport, team1)
        pace2 = cls.get_team_pace(sport, team2)
        return round((pace1 + pace2) / 2, 1)
    
    @classmethod
    def pace_to_context(cls, sport: str, team1: str, team2: str) -> float:
        """Normalize pace to 0-1 scale"""
        sport = sport.upper()
        pace = cls.get_game_pace(sport, team1, team2)
        min_pace, max_pace = cls.PACE_RANGE.get(sport, (0, 100))
        normalized = (pace - min_pace) / (max_pace - min_pace)
        return round(max(0, min(1, normalized)), 2)
    
    @classmethod
    def get_pace_adjustment(cls, sport: str, team1: str, team2: str) -> Optional[Dict]:
        """Calculate stat adjustment based on pace"""
        sport = sport.upper()
        pace = cls.get_game_pace(sport, team1, team2)
        avg = cls.LEAGUE_AVG.get(sport, pace)
        pace_diff = pace - avg
        
        # Different adjustment multipliers per sport
        multipliers = {
            "NBA": 0.3,
            "NFL": 0.15,
            "MLB": 0.4,
            "NHL": 0.1,
            "NCAAB": 0.25,
        }
        
        mult = multipliers.get(sport, 0.2)
        threshold = avg * 0.03  # 3% threshold
        
        if abs(pace_diff) <= threshold:
            return None
            
        boost = pace_diff * mult
        
        return {
            "label": "Pace",
            "icon": "⚡" if pace_diff > 0 else "🐢",
            "value": round(boost, 1),
            "reason": f"{'+' if pace_diff > 0 else ''}{pace_diff:.1f} from avg ({avg})"
        }
    
    @classmethod
    def get_all_rankings(cls, sport: str) -> Dict:
        """Get all pace rankings for a sport"""
        sport = sport.upper()
        return cls.PACE_DATA.get(sport, {})


# ============================================================
# MULTI-SPORT USAGE VACUUM SERVICE
# ============================================================

class UsageVacuumService:
    """Usage/target/opportunity vacuum for all sports"""
    
    # Default weights for vacuum calculation
    VACUUM_WEIGHTS = {
        "NBA": {"usage": 1.0, "minutes": 48},      # (USG% × MPG) / 48
        "NFL": {"targets": 1.0, "snaps": 65},      # (Target% × Snaps) / 65
        "MLB": {"plate_apps": 1.0, "lineup": 9},   # Plate appearances / 9
        "NHL": {"toi": 1.0, "period": 60},         # Time on ice / 60
        "NCAAB": {"usage": 1.0, "minutes": 40},    # (USG% × MPG) / 40
    }
    
    @classmethod
    def calculate_vacuum(cls, sport: str, injuries: List[Dict]) -> float:
        """Calculate vacuum based on sport-specific metrics"""
        sport = sport.upper()
        vacuum = 0.0
        
        weights = cls.VACUUM_WEIGHTS.get(sport, {"usage": 1.0, "minutes": 48})
        
        for injury in injuries:
            status = injury.get('status', '').upper()
            if status == 'OUT':
                if sport in ["NBA", "NCAAB"]:
                    usage_pct = injury.get('usage_pct', 0.0)
                    minutes = injury.get('minutes_per_game', 0.0)
                    vacuum += (usage_pct * minutes) / weights["minutes"]
                elif sport == "NFL":
                    target_share = injury.get('target_share', 0.0)
                    snaps = injury.get('snaps_per_game', 0.0)
                    vacuum += (target_share * snaps) / weights["snaps"]
                elif sport == "NHL":
                    toi = injury.get('time_on_ice', 0.0)
                    vacuum += toi / weights["period"] * 10
                elif sport == "MLB":
                    plate_apps = injury.get('plate_appearances', 0.0)
                    vacuum += plate_apps / weights["lineup"]
                    
        return round(vacuum, 1)
    
    @classmethod
    def vacuum_to_context(cls, vacuum: float) -> float:
        """Normalize vacuum to 0-1 scale"""
        normalized = min(vacuum / 50, 1.0)
        return round(normalized, 2)
    
    @classmethod
    def get_vacuum_adjustment(cls, sport: str, vacuum: float, player_avg: float) -> Optional[Dict]:
        """Calculate stat adjustment based on vacuum"""
        if vacuum <= 10:
            return None
        
        # Sport-specific boost multipliers
        multipliers = {
            "NBA": 0.10,
            "NFL": 0.12,
            "MLB": 0.08,
            "NHL": 0.10,
            "NCAAB": 0.10,
        }
        
        mult = multipliers.get(sport.upper(), 0.10)
        boost = vacuum * mult
        
        return {
            "label": "Usage Vacuum",
            "icon": "🔋",
            "value": round(boost, 1),
            "reason": f"{vacuum:.1f} opportunity available from injuries"
        }


# ============================================================
# MLB PARK FACTOR SERVICE
# ============================================================

class ParkFactorService:
    """MLB-specific park factors"""
    
    @classmethod
    def get_park_factor(cls, team: str) -> float:
        """Get park factor for a team's home stadium"""
        team = standardize_team(team, "MLB")
        park = MLB_TEAM_TO_PARK.get(team)
        if park:
            return MLB_PARK_FACTORS.get(park, 1.0)
        return 1.0
    
    @classmethod
    def get_game_environment(cls, home_team: str, away_team: str) -> Dict:
        """Get park factor context for a game"""
        factor = cls.get_park_factor(home_team)
        
        if factor >= 1.10:
            environment = "HITTER FRIENDLY 🔥"
        elif factor <= 0.90:
            environment = "PITCHER FRIENDLY 🧊"
        else:
            environment = "NEUTRAL"
        
        return {
            "park_factor": factor,
            "environment": environment,
            "home_team": home_team
        }
    
    @classmethod
    def get_adjustment(cls, home_team: str, player_avg: float, is_batter: bool) -> Optional[Dict]:
        """Calculate adjustment based on park factor"""
        factor = cls.get_park_factor(home_team)
        
        if 0.95 <= factor <= 1.05:
            return None
            
        if is_batter:
            adjustment = (factor - 1.0) * player_avg * 0.5
        else:
            adjustment = (1.0 - factor) * player_avg * 0.3
            
        park = MLB_TEAM_TO_PARK.get(standardize_team(home_team, "MLB"), "Unknown")
        
        return {
            "label": f"Park ({park[:12]})",
            "icon": "🏟️",
            "value": round(adjustment, 1),
            "reason": f"Park factor {factor:.2f}"
        }


# ============================================================
# MASTER CONTEXT GENERATOR (MULTI-SPORT)
# ============================================================

class ContextGenerator:
    """Generates complete context for predictions across all sports"""
    
    @staticmethod
    def generate_context(
        sport: str,
        player_name: str,
        player_team: str,
        opponent_team: str,
        position: str,
        player_avg: float,
        stat_type: str = "points",
        injuries: List[Dict] = None,
        game_total: float = 0.0,
        game_spread: float = 0.0,
        home_team: str = None,  # For MLB park factors
    ) -> Dict[str, Any]:
        """Generate full context for a player prediction"""
        
        sport = sport.upper()
        injuries = injuries or []
        
        # =====================
        # 1. USAGE VACUUM
        # =====================
        vacuum = UsageVacuumService.calculate_vacuum(sport, injuries)
        vacuum_context = UsageVacuumService.vacuum_to_context(vacuum)
        vacuum_adj = UsageVacuumService.get_vacuum_adjustment(sport, vacuum, player_avg)
        
        # =====================
        # 2. DEFENSIVE RANK
        # =====================
        defense_rank = DefensiveRankService.get_rank(sport, opponent_team, position)
        defense_context = DefensiveRankService.rank_to_context(sport, opponent_team, position)
        defense_adj = DefensiveRankService.get_matchup_adjustment(sport, opponent_team, position, player_avg)
        
        # =====================
        # 3. PACE VECTOR
        # =====================
        pace = PaceVectorService.get_game_pace(sport, player_team, opponent_team)
        pace_context = PaceVectorService.pace_to_context(sport, player_team, opponent_team)
        pace_adj = PaceVectorService.get_pace_adjustment(sport, player_team, opponent_team)
        
        # =====================
        # 4. MLB PARK FACTOR
        # =====================
        park_adj = None
        park_factor = 1.0
        if sport == "MLB" and home_team:
            park_factor = ParkFactorService.get_park_factor(home_team)
            is_batter = position.lower() in ["batter", "hitter", "dh"]
            park_adj = ParkFactorService.get_adjustment(home_team, player_avg, is_batter)
        
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
        if park_adj:
            adjustments.append(park_adj)
            
        # Blowout risk (mainly for NBA/NCAAB)
        if sport in ["NBA", "NCAAB"] and abs(game_spread) > 10:
            blowout_penalty = -1.0 if abs(game_spread) > 15 else -0.5
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
        total_teams = DefensiveRankService.get_total_teams(sport)
        soft_threshold = 0.7 if total_teams <= 32 else 0.8  # Adjust for NCAAB
        
        is_smash = (
            defense_context > soft_threshold or
            vacuum_context > 0.5 or
            (defense_context > 0.5 and vacuum_context > 0.3) or
            (sport == "MLB" and park_factor >= 1.15)
        )
        
        # =====================
        # CALCULATE CONFIDENCE
        # =====================
        confidence = 65
        if is_smash:
            confidence += 20
        if len([a for a in adjustments if a["value"] > 0]) >= 2:
            confidence += 10
        confidence = min(95, confidence)
        
        # =====================
        # BUILD BADGES
        # =====================
        badges = ContextGenerator._build_badges(
            defense_context, vacuum_context, pace_context, is_smash, sport, park_factor
        )
        
        # =====================
        # BUILD RESPONSE
        # =====================
        return {
            "sport": sport,
            "player_name": player_name,
            "player_team": player_team,
            "opponent_team": opponent_team,
            "position": position,
            "stat_type": stat_type,
            
            "lstm_features": {
                "defense_rank": defense_rank,
                "defense_context": defense_context,
                "pace": pace,
                "pace_context": pace_context,
                "vacuum": vacuum,
                "vacuum_context": vacuum_context,
                "total": game_total,
                "spread": game_spread,
                "park_factor": park_factor if sport == "MLB" else None,
            },
            
            "waterfall": {
                "baseAverage": player_avg,
                "finalPrediction": round(final_prediction, 1),
                "adjustments": adjustments,
                "isSmashSpot": is_smash,
                "confidence": confidence
            },
            
            "badges": badges,
            
            "raw_context": {
                "defense": {"rank": defense_rank, "normalized": defense_context},
                "vacuum": {"value": vacuum, "normalized": vacuum_context},
                "pace": {"value": pace, "normalized": pace_context},
                "park_factor": park_factor if sport == "MLB" else None,
            }
        }
    
    @staticmethod
    def _build_badges(defense_ctx, vacuum_ctx, pace_ctx, is_smash, sport, park_factor=1.0):
        """Build compact badge indicators"""
        badges = []
        
        if vacuum_ctx > 0.3:
            badges.append({"icon": "🔋", "label": "vacuum", "active": True})
            
        if defense_ctx > 0.6:
            badges.append({"icon": "🎯", "label": "matchup", "active": True})
        elif defense_ctx < 0.3:
            badges.append({"icon": "🛡️", "label": "defense", "active": True})
            
        if pace_ctx > 0.6:
            badges.append({"icon": "⚡", "label": "pace", "active": True})
        elif pace_ctx < 0.3:
            badges.append({"icon": "🐢", "label": "slow", "active": True})
            
        if sport == "MLB" and park_factor >= 1.10:
            badges.append({"icon": "🏟️", "label": "hitter park", "active": True})
        elif sport == "MLB" and park_factor <= 0.90:
            badges.append({"icon": "🧊", "label": "pitcher park", "active": True})
            
        if is_smash:
            badges.append({"icon": "💎", "label": "smash", "active": True})
            
        return badges


# ============================================================
# QUICK TEST
# ============================================================

if __name__ == "__main__":
    print("=" * 70)
    print("🔥 BOOKIE-O-EM CONTEXT LAYER v2.0 - MULTI-SPORT")
    print("=" * 70)
    
    # Test NBA
    print("\n📊 NBA TEST - Pascal Siakam vs Washington")
    nba_ctx = ContextGenerator.generate_context(
        sport="NBA",
        player_name="Pascal Siakam",
        player_team="Indiana Pacers",
        opponent_team="Washington Wizards",
        position="Wing",
        player_avg=21.5,
        stat_type="points",
        injuries=[{"status": "OUT", "usage_pct": 26.0, "minutes_per_game": 34}],
        game_total=241.0,
        game_spread=-5.5
    )
    print(f"  Final: {nba_ctx['waterfall']['finalPrediction']} pts")
    print(f"  Smash: {'✅' if nba_ctx['waterfall']['isSmashSpot'] else '❌'}")
    
    # Test NFL
    print("\n🏈 NFL TEST - CeeDee Lamb vs Giants")
    nfl_ctx = ContextGenerator.generate_context(
        sport="NFL",
        player_name="CeeDee Lamb",
        player_team="Dallas Cowboys",
        opponent_team="New York Giants",
        position="WR",
        player_avg=85.5,
        stat_type="receiving_yards",
        injuries=[{"status": "OUT", "target_share": 28.0, "snaps_per_game": 58}],
        game_spread=-6.5
    )
    print(f"  Final: {nfl_ctx['waterfall']['finalPrediction']} yds")
    print(f"  Smash: {'✅' if nfl_ctx['waterfall']['isSmashSpot'] else '❌'}")
    
    # Test MLB
    print("\n⚾ MLB TEST - Shohei Ohtani at Coors Field")
    mlb_ctx = ContextGenerator.generate_context(
        sport="MLB",
        player_name="Shohei Ohtani",
        player_team="Los Angeles Dodgers",
        opponent_team="Colorado Rockies",
        position="Batter",
        player_avg=1.8,
        stat_type="total_bases",
        home_team="Colorado Rockies"
    )
    print(f"  Final: {mlb_ctx['waterfall']['finalPrediction']} TB")
    print(f"  Park Factor: {mlb_ctx['lstm_features']['park_factor']}")
    print(f"  Smash: {'✅' if mlb_ctx['waterfall']['isSmashSpot'] else '❌'}")
    
    # Test NHL
    print("\n🏒 NHL TEST - Connor McDavid vs Columbus")
    nhl_ctx = ContextGenerator.generate_context(
        sport="NHL",
        player_name="Connor McDavid",
        player_team="Edmonton Oilers",
        opponent_team="Columbus Blue Jackets",
        position="Center",
        player_avg=1.5,
        stat_type="points",
        injuries=[{"status": "OUT", "time_on_ice": 22.0}]
    )
    print(f"  Final: {nhl_ctx['waterfall']['finalPrediction']} pts")
    print(f"  Smash: {'✅' if nhl_ctx['waterfall']['isSmashSpot'] else '❌'}")
    
    print("\n" + "=" * 70)
    print("✅ MULTI-SPORT CONTEXT LAYER READY!")
    print("=" * 70)
