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

# NCAAB team name to short name mapping (mascot stripping)
# Maps "North Carolina Tar Heels" -> "North Carolina", etc.
NCAAB_TEAM_MAPPING = {
    # ACC
    "North Carolina Tar Heels": "North Carolina", "Duke Blue Devils": "Duke",
    "Virginia Cavaliers": "Virginia", "Syracuse Orange": "Syracuse",
    "NC State Wolfpack": "NC State", "Wake Forest Demon Deacons": "Wake Forest",
    "Clemson Tigers": "Clemson", "Louisville Cardinals": "Louisville",
    "Pittsburgh Panthers": "Pittsburgh", "Notre Dame Fighting Irish": "Notre Dame",
    "Florida State Seminoles": "Florida State", "Miami Hurricanes": "Miami",
    "Boston College Eagles": "Boston College", "Georgia Tech Yellow Jackets": "Georgia Tech",
    "Virginia Tech Hokies": "Virginia Tech", "California Golden Bears": "California",
    "Stanford Cardinal": "Stanford", "SMU Mustangs": "SMU",

    # SEC
    "Kentucky Wildcats": "Kentucky", "Tennessee Volunteers": "Tennessee",
    "Auburn Tigers": "Auburn", "Alabama Crimson Tide": "Alabama",
    "Arkansas Razorbacks": "Arkansas", "Florida Gators": "Florida",
    "Texas A&M Aggies": "Texas A&M", "LSU Tigers": "LSU",
    "Mississippi State Bulldogs": "Mississippi State", "Ole Miss Rebels": "Ole Miss",
    "Missouri Tigers": "Missouri", "South Carolina Gamecocks": "South Carolina",
    "Vanderbilt Commodores": "Vanderbilt", "Georgia Bulldogs": "Georgia",
    "Texas Longhorns": "Texas", "Oklahoma Sooners": "Oklahoma",

    # Big Ten
    "Purdue Boilermakers": "Purdue", "Michigan State Spartans": "Michigan State",
    "Illinois Fighting Illini": "Illinois", "Michigan Wolverines": "Michigan",
    "Indiana Hoosiers": "Indiana", "Ohio State Buckeyes": "Ohio State",
    "Wisconsin Badgers": "Wisconsin", "Iowa Hawkeyes": "Iowa",
    "Maryland Terrapins": "Maryland", "Minnesota Golden Gophers": "Minnesota",
    "Nebraska Cornhuskers": "Nebraska", "Northwestern Wildcats": "Northwestern",
    "Penn State Nittany Lions": "Penn State", "Rutgers Scarlet Knights": "Rutgers",
    "UCLA Bruins": "UCLA", "USC Trojans": "USC", "Oregon Ducks": "Oregon",
    "Washington Huskies": "Washington",

    # Big 12
    "Kansas Jayhawks": "Kansas", "Baylor Bears": "Baylor",
    "Houston Cougars": "Houston", "Iowa State Cyclones": "Iowa State",
    "Texas Tech Red Raiders": "Texas Tech", "TCU Horned Frogs": "TCU",
    "BYU Cougars": "BYU", "Cincinnati Bearcats": "Cincinnati",
    "UCF Knights": "UCF", "Kansas State Wildcats": "Kansas State",
    "West Virginia Mountaineers": "West Virginia", "Oklahoma State Cowboys": "Oklahoma State",
    "Arizona Wildcats": "Arizona", "Arizona State Sun Devils": "Arizona State",
    "Colorado Buffaloes": "Colorado", "Utah Utes": "Utah",

    # Big East
    "UConn Huskies": "UConn", "Marquette Golden Eagles": "Marquette",
    "Creighton Bluejays": "Creighton", "Villanova Wildcats": "Villanova",
    "Xavier Musketeers": "Xavier", "Providence Friars": "Providence",
    "St. John's Red Storm": "St. John's", "Seton Hall Pirates": "Seton Hall",
    "Georgetown Hoyas": "Georgetown", "Butler Bulldogs": "Butler",
    "DePaul Blue Demons": "DePaul",

    # Other Power Programs
    "Gonzaga Bulldogs": "Gonzaga", "San Diego State Aztecs": "San Diego State",
    "Memphis Tigers": "Memphis", "Saint Mary's Gaels": "Saint Mary's",
    "Nevada Wolf Pack": "Nevada", "New Mexico Lobos": "New Mexico",
    "VCU Rams": "VCU", "Dayton Flyers": "Dayton",
}

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
    """Convert team name to standardized format for context layer lookup.

    For NCAAB: Strips mascot suffixes ("North Carolina Tar Heels" -> "North Carolina")
    For NHL: Handles accent characters ("Montréal" -> "Montreal")
    For other sports: Handles abbreviations via TEAM_ALIASES
    """
    if not team:
        return team

    # NHL accent normalization (v17.2)
    # ESPN may return "Montréal Canadiens" but our data uses "Montreal Canadiens"
    NHL_ACCENT_MAP = {
        "Montréal Canadiens": "Montreal Canadiens",
        "Montréal": "Montreal",
    }
    if team in NHL_ACCENT_MAP:
        team = NHL_ACCENT_MAP[team]

    # Check NCAAB mascot mapping first (exact match)
    if team in NCAAB_TEAM_MAPPING:
        return NCAAB_TEAM_MAPPING[team]

    # Check abbreviation aliases
    if team.upper() in TEAM_ALIASES:
        return TEAM_ALIASES[team.upper()]

    # For NCAAB, try conservative fuzzy matching
    # Only strip if the suffix is a common mascot word (not a school identifier like "St" or "Central")
    if sport and sport.upper() == "NCAAB":
        # Common mascot suffixes that are safe to strip
        MASCOT_SUFFIXES = {
            "Wildcats", "Tigers", "Bulldogs", "Eagles", "Bears", "Cardinals",
            "Cougars", "Huskies", "Terrapins", "Volunteers", "Crimson Tide",
            "Blue Devils", "Tar Heels", "Seminoles", "Hurricanes", "Cavaliers",
            "Yellow Jackets", "Hokies", "Demon Deacons", "Fighting Irish",
            "Orange", "Panthers", "Razorbacks", "Gators", "Gamecocks",
            "Commodores", "Rebels", "Aggies", "Longhorns", "Sooners",
            "Boilermakers", "Spartans", "Fighting Illini", "Wolverines",
            "Hoosiers", "Buckeyes", "Badgers", "Hawkeyes", "Golden Gophers",
            "Cornhuskers", "Nittany Lions", "Scarlet Knights", "Bruins",
            "Trojans", "Ducks", "Jayhawks", "Cyclones", "Red Raiders",
            "Horned Frogs", "Mountaineers", "Cowboys", "Sun Devils",
            "Buffaloes", "Utes", "Golden Eagles", "Bluejays", "Musketeers",
            "Friars", "Red Storm", "Pirates", "Hoyas", "Blue Demons",
            "Gaels", "Aztecs", "Rams", "Flyers", "Wolf Pack", "Lobos",
        }

        words = team.split()
        if len(words) >= 2:
            # Check if the last 1-2 words are a mascot
            for suffix_len in [2, 1]:
                if len(words) > suffix_len:
                    suffix = " ".join(words[-suffix_len:])
                    if suffix in MASCOT_SUFFIXES:
                        prefix = " ".join(words[:-suffix_len])
                        if prefix in NCAAB_PACE or prefix in NCAAB_DEFENSE_VS_GUARDS:
                            return prefix

    return team


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
            
            # LSTM Features - ALIGNED WITH SPEC: [stat, mins, home_away, vacuum, def_rank, pace]
            "lstm_features": {
                # Spec-aligned fields (for LSTM input)
                "stat": player_avg,          # Current game uses avg as baseline (actual filled from history)
                "player_avg": player_avg,    # For normalization
                "mins": 32.0,                # Expected minutes (filled from history for past games)
                "home_away": 1 if home_team and home_team.upper() == player_team.upper() else 0,
                "vacuum": vacuum,
                "def_rank": defense_rank,
                "pace": pace,
                
                # Additional context (for debugging/display)
                "defense_context": defense_context,
                "pace_context": pace_context,
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


# ============================================================
# NBA REFEREE ANALYSIS SERVICE
# ============================================================

NBA_REFEREE_PROFILES = {
    # Over-Friendly Refs (High-Scoring Games)
    "scott foster": {"avg_total": 224.5, "home_win_pct": 54.2, "fouls_per_game": 42.1, "over_pct": 55.3, "tendency": "OVER"},
    "tony brothers": {"avg_total": 223.8, "home_win_pct": 55.1, "fouls_per_game": 43.2, "over_pct": 54.8, "tendency": "OVER"},
    "marc davis": {"avg_total": 222.4, "home_win_pct": 52.8, "fouls_per_game": 41.5, "over_pct": 53.2, "tendency": "OVER"},
    "james capers": {"avg_total": 221.9, "home_win_pct": 53.5, "fouls_per_game": 40.8, "over_pct": 52.9, "tendency": "OVER"},
    "ben taylor": {"avg_total": 223.1, "home_win_pct": 51.9, "fouls_per_game": 41.2, "over_pct": 54.1, "tendency": "OVER"},
    "sean wright": {"avg_total": 222.7, "home_win_pct": 53.1, "fouls_per_game": 42.5, "over_pct": 53.8, "tendency": "OVER"},
    
    # Under-Friendly Refs (Low-Scoring Games)
    "kane fitzgerald": {"avg_total": 215.2, "home_win_pct": 51.2, "fouls_per_game": 36.8, "over_pct": 45.6, "tendency": "UNDER"},
    "ed malloy": {"avg_total": 216.4, "home_win_pct": 50.8, "fouls_per_game": 37.2, "over_pct": 46.3, "tendency": "UNDER"},
    "john goble": {"avg_total": 217.1, "home_win_pct": 52.1, "fouls_per_game": 38.1, "over_pct": 47.2, "tendency": "UNDER"},
    "david guthrie": {"avg_total": 216.8, "home_win_pct": 51.5, "fouls_per_game": 37.5, "over_pct": 46.8, "tendency": "UNDER"},
    "eric lewis": {"avg_total": 217.5, "home_win_pct": 50.3, "fouls_per_game": 38.4, "over_pct": 47.5, "tendency": "UNDER"},
    
    # Home-Team Friendly Refs
    "bill kennedy": {"avg_total": 219.8, "home_win_pct": 57.2, "fouls_per_game": 39.5, "over_pct": 50.2, "tendency": "HOME"},
    "pat fraher": {"avg_total": 218.5, "home_win_pct": 56.8, "fouls_per_game": 39.1, "over_pct": 49.5, "tendency": "HOME"},
    "leon wood": {"avg_total": 219.2, "home_win_pct": 56.1, "fouls_per_game": 40.2, "over_pct": 50.8, "tendency": "HOME"},
    "tre maddox": {"avg_total": 220.1, "home_win_pct": 55.8, "fouls_per_game": 39.8, "over_pct": 51.2, "tendency": "HOME"},
    
    # Star-Friendly Refs (High Foul = More FTs for Stars)
    "tony brown": {"avg_total": 221.2, "home_win_pct": 52.8, "fouls_per_game": 44.5, "over_pct": 52.1, "tendency": "STAR_FRIENDLY"},
    "mitchell ervin": {"avg_total": 220.8, "home_win_pct": 53.2, "fouls_per_game": 43.8, "over_pct": 51.8, "tendency": "STAR_FRIENDLY"},
    "dedric taylor": {"avg_total": 220.5, "home_win_pct": 52.5, "fouls_per_game": 43.2, "over_pct": 51.5, "tendency": "STAR_FRIENDLY"},
    
    # Neutral/Balanced Refs
    "josh tiven": {"avg_total": 219.1, "home_win_pct": 52.5, "fouls_per_game": 39.2, "over_pct": 50.1, "tendency": "NEUTRAL"},
    "james williams": {"avg_total": 218.8, "home_win_pct": 51.8, "fouls_per_game": 38.8, "over_pct": 49.8, "tendency": "NEUTRAL"},
    "zach zarba": {"avg_total": 219.4, "home_win_pct": 52.2, "fouls_per_game": 39.4, "over_pct": 50.4, "tendency": "NEUTRAL"},
    "brian forte": {"avg_total": 218.6, "home_win_pct": 51.5, "fouls_per_game": 38.5, "over_pct": 49.2, "tendency": "NEUTRAL"},
    "derrick collins": {"avg_total": 219.0, "home_win_pct": 52.0, "fouls_per_game": 39.0, "over_pct": 50.0, "tendency": "NEUTRAL"},
    "matt boland": {"avg_total": 218.9, "home_win_pct": 51.7, "fouls_per_game": 38.7, "over_pct": 49.6, "tendency": "NEUTRAL"},
    "nick buchert": {"avg_total": 219.3, "home_win_pct": 52.3, "fouls_per_game": 39.3, "over_pct": 50.3, "tendency": "NEUTRAL"},
    "mark ayotte": {"avg_total": 218.7, "home_win_pct": 51.6, "fouls_per_game": 38.6, "over_pct": 49.4, "tendency": "NEUTRAL"},
    "rodney mott": {"avg_total": 221.5, "home_win_pct": 54.7, "fouls_per_game": 40.3, "over_pct": 52.4, "tendency": "SLIGHT_OVER"},
    "curtis blair": {"avg_total": 216.2, "home_win_pct": 52.4, "fouls_per_game": 37.8, "over_pct": 46.1, "tendency": "SLIGHT_UNDER"},
    "kevin scott": {"avg_total": 217.8, "home_win_pct": 51.8, "fouls_per_game": 38.9, "over_pct": 48.1, "tendency": "SLIGHT_UNDER"},
    "mousa dagher": {"avg_total": 219.5, "home_win_pct": 52.1, "fouls_per_game": 39.1, "over_pct": 50.2, "tendency": "NEUTRAL"},
    "kevin cutler": {"avg_total": 218.4, "home_win_pct": 51.4, "fouls_per_game": 38.4, "over_pct": 49.1, "tendency": "NEUTRAL"},
}

NBA_LEAGUE_AVG_REFS = {
    "avg_total": 219.0,
    "home_win_pct": 52.5,
    "fouls_per_game": 39.5,
    "over_pct": 50.0
}


class RefereeService:
    """NBA Referee Analysis - Impact on totals, spreads, and props"""
    
    @classmethod
    def get_ref_profile(cls, ref_name: str) -> Optional[Dict]:
        """Get profile for a single referee"""
        return NBA_REFEREE_PROFILES.get(ref_name.lower())
    
    @classmethod
    def analyze_crew(cls, crew_chief: str, referee: str = "", umpire: str = "") -> Dict:
        """
        Analyze a referee crew's combined tendencies
        Weights: Crew Chief 50%, Referee 30%, Umpire 20%
        """
        refs = [r.lower().strip() for r in [crew_chief, referee, umpire] if r]
        
        if not refs:
            return {"has_data": False, "recommendation": "NO_REF_DATA"}
        
        weights = [0.5, 0.3, 0.2][:len(refs)]
        
        combined = {
            "avg_total": 0, "home_win_pct": 0, "fouls_per_game": 0, "over_pct": 0,
            "refs_found": [], "refs_missing": []
        }
        
        total_weight = 0
        tendencies = []
        
        for i, ref in enumerate(refs):
            weight = weights[i] if i < len(weights) else 0.2
            profile = NBA_REFEREE_PROFILES.get(ref)
            
            if profile:
                combined["refs_found"].append(ref.title())
                combined["avg_total"] += profile["avg_total"] * weight
                combined["home_win_pct"] += profile["home_win_pct"] * weight
                combined["fouls_per_game"] += profile["fouls_per_game"] * weight
                combined["over_pct"] += profile["over_pct"] * weight
                tendencies.append(profile.get("tendency", "NEUTRAL"))
                total_weight += weight
            else:
                combined["refs_missing"].append(ref.title())
        
        if total_weight == 0:
            return {"has_data": False, "recommendation": "NO_REF_DATA"}
        
        # Normalize
        combined["avg_total"] = round(combined["avg_total"] / total_weight, 1)
        combined["home_win_pct"] = round(combined["home_win_pct"] / total_weight, 1)
        combined["fouls_per_game"] = round(combined["fouls_per_game"] / total_weight, 1)
        combined["over_pct"] = round(combined["over_pct"] / total_weight, 1)
        
        # Calculate edges vs league average
        combined["total_edge"] = round(combined["avg_total"] - NBA_LEAGUE_AVG_REFS["avg_total"], 1)
        combined["home_edge"] = round(combined["home_win_pct"] - NBA_LEAGUE_AVG_REFS["home_win_pct"], 1)
        combined["over_edge"] = round(combined["over_pct"] - NBA_LEAGUE_AVG_REFS["over_pct"], 1)
        
        # Determine recommendations
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
            combined["props_lean"] = "OVER"
        elif combined["fouls_per_game"] <= 37:
            combined["star_impact"] = "LOW"
            combined["props_lean"] = "UNDER"
        else:
            combined["star_impact"] = "NEUTRAL"
            combined["props_lean"] = "NEUTRAL"
        
        combined["has_data"] = True
        combined["tendencies"] = tendencies
        combined["confidence"] = min(90, len(combined["refs_found"]) * 30)
        
        return combined
    
    @classmethod
    def get_ref_adjustment(cls, crew_chief: str, referee: str = "", umpire: str = "", 
                          bet_type: str = "total", is_home: bool = False, is_star: bool = False) -> Optional[Dict]:
        """
        Calculate adjustment based on referee crew
        
        Args:
            crew_chief: Lead referee name
            referee: Second referee name
            umpire: Third referee name
            bet_type: "total", "spread", or "props"
            is_home: True if betting on home team (for spread)
            is_star: True if player is high-usage star (for props)
        """
        analysis = cls.analyze_crew(crew_chief, referee, umpire)
        
        if not analysis.get("has_data"):
            return None
        
        if bet_type == "total":
            if analysis["total_recommendation"] == "OVER" and analysis["total_strength"] > 0.3:
                return {
                    "label": "Ref Crew",
                    "icon": "🦓",
                    "value": round(analysis["total_edge"], 1),
                    "reason": f"{analysis['over_pct']}% over rate ({', '.join(analysis['refs_found'][:2])})",
                    "recommendation": "OVER"
                }
            elif analysis["total_recommendation"] == "UNDER" and analysis["total_strength"] > 0.3:
                return {
                    "label": "Ref Crew",
                    "icon": "🦓",
                    "value": round(analysis["total_edge"], 1),
                    "reason": f"{analysis['over_pct']}% over rate ({', '.join(analysis['refs_found'][:2])})",
                    "recommendation": "UNDER"
                }
        
        elif bet_type == "spread":
            if analysis["spread_recommendation"] == "HOME" and is_home and analysis["spread_strength"] > 0.3:
                return {
                    "label": "Ref Crew",
                    "icon": "🦓",
                    "value": round(analysis["home_edge"] * 0.3, 1),
                    "reason": f"{analysis['home_win_pct']}% home win rate",
                    "recommendation": "HOME"
                }
        
        elif bet_type == "props":
            if is_star and analysis["star_impact"] == "HIGH":
                return {
                    "label": "Ref Crew",
                    "icon": "🦓",
                    "value": 1.5,
                    "reason": f"High-foul crew ({analysis['fouls_per_game']} fouls/game) benefits stars",
                    "recommendation": "OVER"
                }
            elif is_star and analysis["star_impact"] == "LOW":
                return {
                    "label": "Ref Crew",
                    "icon": "🦓",
                    "value": -1.0,
                    "reason": f"Low-foul crew ({analysis['fouls_per_game']} fouls/game) limits FTs",
                    "recommendation": "UNDER"
                }
        
        return None
    
    @classmethod
    def get_all_refs_by_tendency(cls) -> Dict:
        """Get all refs grouped by their tendency"""
        grouped = {
            "over_friendly": [],
            "under_friendly": [],
            "home_friendly": [],
            "star_friendly": [],
            "neutral": []
        }
        
        for ref, profile in NBA_REFEREE_PROFILES.items():
            tendency = profile.get("tendency", "NEUTRAL")
            ref_data = {"name": ref.title(), **profile}
            
            if tendency == "OVER":
                grouped["over_friendly"].append(ref_data)
            elif tendency == "UNDER":
                grouped["under_friendly"].append(ref_data)
            elif tendency == "HOME":
                grouped["home_friendly"].append(ref_data)
            elif tendency == "STAR_FRIENDLY":
                grouped["star_friendly"].append(ref_data)
            else:
                grouped["neutral"].append(ref_data)
        
        # Sort each group by their key metric
        grouped["over_friendly"].sort(key=lambda x: x["over_pct"], reverse=True)
        grouped["under_friendly"].sort(key=lambda x: x["over_pct"])
        grouped["home_friendly"].sort(key=lambda x: x["home_win_pct"], reverse=True)
        grouped["star_friendly"].sort(key=lambda x: x["fouls_per_game"], reverse=True)
        
        return grouped
"""
🦓 BOOKIE-O-EM OFFICIALS LAYER - MULTI-SPORT
=============================================
Referee/Umpire analysis for ALL 5 sports

Sports Covered:
- NBA: Referees (3 per game)
- NFL: Officials (7 per game, lead referee key)
- MLB: Umpires (4 per game, home plate key)
- NHL: Referees (2) + Linesmen (2)
- NCAAB: Referees (3 per game)

Impact Areas:
- Totals (over/under tendency)
- Spreads (home team advantage)
- Props (foul/penalty rates affect player stats)
"""

from typing import Dict, List, Optional
from dataclasses import dataclass


# ============================================================
# NBA OFFICIALS (35+ Referees)
# ============================================================

NBA_OFFICIALS = {
    # Over-Friendly Refs (High-Scoring Games)
    "scott foster": {"avg_total": 224.5, "home_win_pct": 54.2, "fouls_per_game": 42.1, "over_pct": 55.3, "tendency": "OVER"},
    "tony brothers": {"avg_total": 223.8, "home_win_pct": 55.1, "fouls_per_game": 43.2, "over_pct": 54.8, "tendency": "OVER"},
    "marc davis": {"avg_total": 222.4, "home_win_pct": 52.8, "fouls_per_game": 41.5, "over_pct": 53.2, "tendency": "OVER"},
    "james capers": {"avg_total": 221.9, "home_win_pct": 53.5, "fouls_per_game": 40.8, "over_pct": 52.9, "tendency": "OVER"},
    "ben taylor": {"avg_total": 223.1, "home_win_pct": 51.9, "fouls_per_game": 41.2, "over_pct": 54.1, "tendency": "OVER"},
    "sean wright": {"avg_total": 222.7, "home_win_pct": 53.1, "fouls_per_game": 42.5, "over_pct": 53.8, "tendency": "OVER"},
    
    # Under-Friendly Refs (Low-Scoring Games)
    "kane fitzgerald": {"avg_total": 215.2, "home_win_pct": 51.2, "fouls_per_game": 36.8, "over_pct": 45.6, "tendency": "UNDER"},
    "ed malloy": {"avg_total": 216.4, "home_win_pct": 50.8, "fouls_per_game": 37.2, "over_pct": 46.3, "tendency": "UNDER"},
    "john goble": {"avg_total": 217.1, "home_win_pct": 52.1, "fouls_per_game": 38.1, "over_pct": 47.2, "tendency": "UNDER"},
    "david guthrie": {"avg_total": 216.8, "home_win_pct": 51.5, "fouls_per_game": 37.5, "over_pct": 46.8, "tendency": "UNDER"},
    "eric lewis": {"avg_total": 217.5, "home_win_pct": 50.3, "fouls_per_game": 38.4, "over_pct": 47.5, "tendency": "UNDER"},
    
    # Home-Team Friendly Refs
    "bill kennedy": {"avg_total": 219.8, "home_win_pct": 57.2, "fouls_per_game": 39.5, "over_pct": 50.2, "tendency": "HOME"},
    "pat fraher": {"avg_total": 218.5, "home_win_pct": 56.8, "fouls_per_game": 39.1, "over_pct": 49.5, "tendency": "HOME"},
    "leon wood": {"avg_total": 219.2, "home_win_pct": 56.1, "fouls_per_game": 40.2, "over_pct": 50.8, "tendency": "HOME"},
    "tre maddox": {"avg_total": 220.1, "home_win_pct": 55.8, "fouls_per_game": 39.8, "over_pct": 51.2, "tendency": "HOME"},
    
    # Star-Friendly Refs (High Foul = More FTs for Stars)
    "tony brown": {"avg_total": 221.2, "home_win_pct": 52.8, "fouls_per_game": 44.5, "over_pct": 52.1, "tendency": "STAR_FRIENDLY"},
    "mitchell ervin": {"avg_total": 220.8, "home_win_pct": 53.2, "fouls_per_game": 43.8, "over_pct": 51.8, "tendency": "STAR_FRIENDLY"},
    "dedric taylor": {"avg_total": 220.5, "home_win_pct": 52.5, "fouls_per_game": 43.2, "over_pct": 51.5, "tendency": "STAR_FRIENDLY"},
    
    # Neutral/Balanced Refs
    "josh tiven": {"avg_total": 219.1, "home_win_pct": 52.5, "fouls_per_game": 39.2, "over_pct": 50.1, "tendency": "NEUTRAL"},
    "james williams": {"avg_total": 218.8, "home_win_pct": 51.8, "fouls_per_game": 38.8, "over_pct": 49.8, "tendency": "NEUTRAL"},
    "zach zarba": {"avg_total": 219.4, "home_win_pct": 52.2, "fouls_per_game": 39.4, "over_pct": 50.4, "tendency": "NEUTRAL"},
    "brian forte": {"avg_total": 218.6, "home_win_pct": 51.5, "fouls_per_game": 38.5, "over_pct": 49.2, "tendency": "NEUTRAL"},
    "derrick collins": {"avg_total": 219.0, "home_win_pct": 52.0, "fouls_per_game": 39.0, "over_pct": 50.0, "tendency": "NEUTRAL"},
    "matt boland": {"avg_total": 218.9, "home_win_pct": 51.7, "fouls_per_game": 38.7, "over_pct": 49.6, "tendency": "NEUTRAL"},
    "nick buchert": {"avg_total": 219.3, "home_win_pct": 52.3, "fouls_per_game": 39.3, "over_pct": 50.3, "tendency": "NEUTRAL"},
    "mark ayotte": {"avg_total": 218.7, "home_win_pct": 51.6, "fouls_per_game": 38.6, "over_pct": 49.4, "tendency": "NEUTRAL"},
    "rodney mott": {"avg_total": 221.5, "home_win_pct": 54.7, "fouls_per_game": 40.3, "over_pct": 52.4, "tendency": "SLIGHT_OVER"},
    "curtis blair": {"avg_total": 216.2, "home_win_pct": 52.4, "fouls_per_game": 37.8, "over_pct": 46.1, "tendency": "SLIGHT_UNDER"},
    "kevin scott": {"avg_total": 217.8, "home_win_pct": 51.8, "fouls_per_game": 38.9, "over_pct": 48.1, "tendency": "SLIGHT_UNDER"},
    "mousa dagher": {"avg_total": 219.5, "home_win_pct": 52.1, "fouls_per_game": 39.1, "over_pct": 50.2, "tendency": "NEUTRAL"},
    "kevin cutler": {"avg_total": 218.4, "home_win_pct": 51.4, "fouls_per_game": 38.4, "over_pct": 49.1, "tendency": "NEUTRAL"},
}


# ============================================================
# NFL OFFICIALS (Lead Referees)
# ============================================================

NFL_OFFICIALS = {
    # Flag-Happy (More Penalties = More Stoppages = Can Favor UNDER or extend drives)
    "shawn hochuli": {"penalties_per_game": 14.2, "home_win_pct": 54.5, "over_pct": 48.2, "pass_int_rate": 0.8, "tendency": "FLAG_HEAVY"},
    "brad allen": {"penalties_per_game": 13.8, "home_win_pct": 53.2, "over_pct": 47.5, "pass_int_rate": 0.9, "tendency": "FLAG_HEAVY"},
    "clay martin": {"penalties_per_game": 13.5, "home_win_pct": 52.8, "over_pct": 48.8, "pass_int_rate": 0.7, "tendency": "FLAG_HEAVY"},
    "carl cheffers": {"penalties_per_game": 13.2, "home_win_pct": 55.1, "over_pct": 49.2, "pass_int_rate": 0.85, "tendency": "FLAG_HEAVY"},
    
    # Let Them Play (Fewer Flags = Faster Game = Can Favor OVER)
    "bill vinovich": {"penalties_per_game": 10.2, "home_win_pct": 51.5, "over_pct": 54.2, "pass_int_rate": 0.4, "tendency": "LET_PLAY"},
    "ron torbert": {"penalties_per_game": 10.5, "home_win_pct": 50.8, "over_pct": 53.8, "pass_int_rate": 0.45, "tendency": "LET_PLAY"},
    "clete blakeman": {"penalties_per_game": 10.8, "home_win_pct": 52.1, "over_pct": 52.5, "pass_int_rate": 0.5, "tendency": "LET_PLAY"},
    "john hussey": {"penalties_per_game": 11.0, "home_win_pct": 51.2, "over_pct": 52.2, "pass_int_rate": 0.48, "tendency": "LET_PLAY"},
    
    # Home-Friendly
    "jerome boger": {"penalties_per_game": 12.5, "home_win_pct": 57.8, "over_pct": 50.5, "pass_int_rate": 0.6, "tendency": "HOME"},
    "alex kemp": {"penalties_per_game": 12.2, "home_win_pct": 56.5, "over_pct": 51.2, "pass_int_rate": 0.55, "tendency": "HOME"},
    "land clark": {"penalties_per_game": 11.8, "home_win_pct": 55.8, "over_pct": 50.8, "pass_int_rate": 0.58, "tendency": "HOME"},
    
    # Over-Friendly (High Scoring Games)
    "scott novak": {"penalties_per_game": 11.5, "home_win_pct": 52.5, "over_pct": 55.8, "pass_int_rate": 0.52, "tendency": "OVER"},
    "tra blake": {"penalties_per_game": 11.2, "home_win_pct": 51.8, "over_pct": 54.5, "pass_int_rate": 0.5, "tendency": "OVER"},
    "adrian hill": {"penalties_per_game": 12.0, "home_win_pct": 53.0, "over_pct": 53.8, "pass_int_rate": 0.55, "tendency": "OVER"},
    
    # Under-Friendly (Low Scoring Games)
    "craig wrolstad": {"penalties_per_game": 12.8, "home_win_pct": 52.2, "over_pct": 45.5, "pass_int_rate": 0.65, "tendency": "UNDER"},
    "shawn smith": {"penalties_per_game": 13.0, "home_win_pct": 51.5, "over_pct": 46.2, "pass_int_rate": 0.7, "tendency": "UNDER"},
    "alan eck": {"penalties_per_game": 12.5, "home_win_pct": 50.8, "over_pct": 47.0, "pass_int_rate": 0.62, "tendency": "UNDER"},
    
    # Neutral
    "tony corrente": {"penalties_per_game": 11.8, "home_win_pct": 52.0, "over_pct": 50.5, "pass_int_rate": 0.55, "tendency": "NEUTRAL"},
    "craig wrolstad": {"penalties_per_game": 12.0, "home_win_pct": 51.8, "over_pct": 50.2, "pass_int_rate": 0.58, "tendency": "NEUTRAL"},
}


# ============================================================
# MLB UMPIRES (Home Plate Umpires)
# ============================================================

MLB_OFFICIALS = {
    # Wide Strike Zone (Pitcher Friendly = UNDER)
    "angel hernandez": {"strike_zone": "wide", "runs_per_game": 7.8, "home_win_pct": 52.5, "over_pct": 45.2, "k_rate": 18.5, "tendency": "UNDER"},
    "cb bucknor": {"strike_zone": "wide", "runs_per_game": 7.5, "home_win_pct": 51.8, "over_pct": 44.8, "k_rate": 19.2, "tendency": "UNDER"},
    "joe west": {"strike_zone": "wide", "runs_per_game": 7.6, "home_win_pct": 53.2, "over_pct": 45.5, "k_rate": 18.8, "tendency": "UNDER"},
    "laz diaz": {"strike_zone": "wide", "runs_per_game": 7.9, "home_win_pct": 52.0, "over_pct": 46.2, "k_rate": 18.2, "tendency": "UNDER"},
    "marvin hudson": {"strike_zone": "wide", "runs_per_game": 7.7, "home_win_pct": 51.5, "over_pct": 45.8, "k_rate": 18.6, "tendency": "UNDER"},
    "hunter wendelstedt": {"strike_zone": "wide", "runs_per_game": 7.4, "home_win_pct": 52.2, "over_pct": 44.5, "k_rate": 19.5, "tendency": "UNDER"},
    
    # Tight Strike Zone (Hitter Friendly = OVER)
    "pat hoberg": {"strike_zone": "tight", "runs_per_game": 9.8, "home_win_pct": 51.2, "over_pct": 56.5, "k_rate": 15.2, "tendency": "OVER"},
    "nic lentz": {"strike_zone": "tight", "runs_per_game": 9.5, "home_win_pct": 50.8, "over_pct": 55.8, "k_rate": 15.5, "tendency": "OVER"},
    "chris guccione": {"strike_zone": "tight", "runs_per_game": 9.6, "home_win_pct": 52.5, "over_pct": 55.2, "k_rate": 15.8, "tendency": "OVER"},
    "dan bellino": {"strike_zone": "tight", "runs_per_game": 9.4, "home_win_pct": 51.5, "over_pct": 54.8, "k_rate": 16.0, "tendency": "OVER"},
    "adam hamari": {"strike_zone": "tight", "runs_per_game": 9.2, "home_win_pct": 50.5, "over_pct": 54.2, "k_rate": 16.2, "tendency": "OVER"},
    "john tumpane": {"strike_zone": "tight", "runs_per_game": 9.3, "home_win_pct": 51.8, "over_pct": 54.5, "k_rate": 16.1, "tendency": "OVER"},
    
    # Home-Friendly
    "ted barrett": {"strike_zone": "average", "runs_per_game": 8.5, "home_win_pct": 57.2, "over_pct": 50.5, "k_rate": 17.0, "tendency": "HOME"},
    "bill welke": {"strike_zone": "average", "runs_per_game": 8.4, "home_win_pct": 56.5, "over_pct": 50.2, "k_rate": 17.2, "tendency": "HOME"},
    "larry vanover": {"strike_zone": "average", "runs_per_game": 8.6, "home_win_pct": 55.8, "over_pct": 51.0, "k_rate": 16.8, "tendency": "HOME"},
    
    # Neutral/Consistent
    "james hoye": {"strike_zone": "average", "runs_per_game": 8.5, "home_win_pct": 52.0, "over_pct": 50.2, "k_rate": 17.0, "tendency": "NEUTRAL"},
    "mark carlson": {"strike_zone": "average", "runs_per_game": 8.6, "home_win_pct": 51.8, "over_pct": 50.5, "k_rate": 16.9, "tendency": "NEUTRAL"},
    "brian gorman": {"strike_zone": "average", "runs_per_game": 8.4, "home_win_pct": 52.2, "over_pct": 49.8, "k_rate": 17.1, "tendency": "NEUTRAL"},
    "alfonso marquez": {"strike_zone": "average", "runs_per_game": 8.5, "home_win_pct": 51.5, "over_pct": 50.0, "k_rate": 17.0, "tendency": "NEUTRAL"},
    "todd tichenor": {"strike_zone": "average", "runs_per_game": 8.7, "home_win_pct": 52.5, "over_pct": 50.8, "k_rate": 16.8, "tendency": "NEUTRAL"},
}


# ============================================================
# NHL OFFICIALS (Referees)
# ============================================================

NHL_OFFICIALS = {
    # Whistle-Happy (More Penalties = More Power Plays = Can favor skilled teams)
    "chris lee": {"penalties_per_game": 8.5, "home_win_pct": 53.5, "over_pct": 52.5, "pp_opportunities": 7.8, "tendency": "WHISTLE_HAPPY"},
    "wes mccauley": {"penalties_per_game": 8.2, "home_win_pct": 52.8, "over_pct": 53.2, "pp_opportunities": 7.5, "tendency": "WHISTLE_HAPPY"},
    "francois st laurent": {"penalties_per_game": 8.0, "home_win_pct": 54.2, "over_pct": 52.8, "pp_opportunities": 7.2, "tendency": "WHISTLE_HAPPY"},
    "gord dwyer": {"penalties_per_game": 7.8, "home_win_pct": 53.0, "over_pct": 51.5, "pp_opportunities": 7.0, "tendency": "WHISTLE_HAPPY"},
    
    # Let Them Play (Fewer Penalties = Faster, physical game)
    "kelly sutherland": {"penalties_per_game": 5.2, "home_win_pct": 51.5, "over_pct": 48.5, "pp_opportunities": 4.8, "tendency": "LET_PLAY"},
    "eric furlatt": {"penalties_per_game": 5.5, "home_win_pct": 50.8, "over_pct": 47.8, "pp_opportunities": 5.0, "tendency": "LET_PLAY"},
    "dan o'halloran": {"penalties_per_game": 5.8, "home_win_pct": 52.0, "over_pct": 48.2, "pp_opportunities": 5.2, "tendency": "LET_PLAY"},
    "kevin pollock": {"penalties_per_game": 5.6, "home_win_pct": 51.2, "over_pct": 48.0, "pp_opportunities": 5.1, "tendency": "LET_PLAY"},
    
    # Home-Friendly
    "tim peel": {"penalties_per_game": 6.8, "home_win_pct": 58.2, "over_pct": 50.5, "pp_opportunities": 6.2, "tendency": "HOME"},
    "brad meier": {"penalties_per_game": 6.5, "home_win_pct": 56.8, "over_pct": 51.2, "pp_opportunities": 6.0, "tendency": "HOME"},
    "garrett rank": {"penalties_per_game": 6.2, "home_win_pct": 55.5, "over_pct": 50.8, "pp_opportunities": 5.8, "tendency": "HOME"},
    
    # Over-Friendly (High-Scoring Games)
    "steve kozari": {"penalties_per_game": 7.0, "home_win_pct": 52.5, "over_pct": 55.5, "pp_opportunities": 6.5, "tendency": "OVER"},
    "tom kowal": {"penalties_per_game": 6.8, "home_win_pct": 51.8, "over_pct": 54.8, "pp_opportunities": 6.2, "tendency": "OVER"},
    "jean hebert": {"penalties_per_game": 7.2, "home_win_pct": 53.0, "over_pct": 54.2, "pp_opportunities": 6.8, "tendency": "OVER"},
    
    # Under-Friendly (Low-Scoring Games)
    "frederick l'ecuyer": {"penalties_per_game": 6.0, "home_win_pct": 52.0, "over_pct": 45.5, "pp_opportunities": 5.5, "tendency": "UNDER"},
    "brian pochmara": {"penalties_per_game": 5.8, "home_win_pct": 51.5, "over_pct": 46.2, "pp_opportunities": 5.2, "tendency": "UNDER"},
    "tj luxmore": {"penalties_per_game": 6.2, "home_win_pct": 52.2, "over_pct": 46.8, "pp_opportunities": 5.8, "tendency": "UNDER"},
    
    # Neutral
    "dan o'rourke": {"penalties_per_game": 6.5, "home_win_pct": 52.0, "over_pct": 50.2, "pp_opportunities": 6.0, "tendency": "NEUTRAL"},
    "marc joannette": {"penalties_per_game": 6.4, "home_win_pct": 51.8, "over_pct": 50.5, "pp_opportunities": 5.9, "tendency": "NEUTRAL"},
    "chris rooney": {"penalties_per_game": 6.6, "home_win_pct": 52.2, "over_pct": 49.8, "pp_opportunities": 6.1, "tendency": "NEUTRAL"},
}


# ============================================================
# NCAAB OFFICIALS (College Basketball Referees)
# ============================================================

NCAAB_OFFICIALS = {
    # Over-Friendly (High Scoring)
    "ted valentine": {"avg_total": 148.5, "home_win_pct": 55.2, "fouls_per_game": 38.5, "over_pct": 56.2, "tendency": "OVER"},
    "roger ayers": {"avg_total": 147.8, "home_win_pct": 54.5, "fouls_per_game": 37.8, "over_pct": 55.5, "tendency": "OVER"},
    "tony greene": {"avg_total": 146.5, "home_win_pct": 53.8, "fouls_per_game": 36.5, "over_pct": 54.8, "tendency": "OVER"},
    "pat driscoll": {"avg_total": 145.8, "home_win_pct": 52.5, "fouls_per_game": 37.2, "over_pct": 54.2, "tendency": "OVER"},
    "mike eades": {"avg_total": 146.2, "home_win_pct": 53.2, "fouls_per_game": 36.8, "over_pct": 53.8, "tendency": "OVER"},
    
    # Under-Friendly (Low Scoring)
    "john higgins": {"avg_total": 138.5, "home_win_pct": 51.5, "fouls_per_game": 32.5, "over_pct": 44.5, "tendency": "UNDER"},
    "doug sirmons": {"avg_total": 139.2, "home_win_pct": 52.0, "fouls_per_game": 33.2, "over_pct": 45.2, "tendency": "UNDER"},
    "kipp kissinger": {"avg_total": 140.0, "home_win_pct": 51.8, "fouls_per_game": 33.8, "over_pct": 46.0, "tendency": "UNDER"},
    "mike stuart": {"avg_total": 139.8, "home_win_pct": 50.8, "fouls_per_game": 33.5, "over_pct": 45.8, "tendency": "UNDER"},
    "brian o'connell": {"avg_total": 140.5, "home_win_pct": 51.2, "fouls_per_game": 34.0, "over_pct": 46.5, "tendency": "UNDER"},
    
    # Home-Friendly (College crowds are LOUD)
    "karl hess": {"avg_total": 143.5, "home_win_pct": 62.5, "fouls_per_game": 35.5, "over_pct": 50.5, "tendency": "HOME"},
    "jamie luckie": {"avg_total": 142.8, "home_win_pct": 60.8, "fouls_per_game": 35.0, "over_pct": 51.2, "tendency": "HOME"},
    "terry oglesby": {"avg_total": 144.0, "home_win_pct": 59.5, "fouls_per_game": 35.8, "over_pct": 50.8, "tendency": "HOME"},
    "bert smith": {"avg_total": 143.2, "home_win_pct": 58.2, "fouls_per_game": 34.8, "over_pct": 51.0, "tendency": "HOME"},
    
    # Star-Friendly (More fouls = more FTs for stars)
    "tv teddy": {"avg_total": 145.5, "home_win_pct": 54.0, "fouls_per_game": 42.0, "over_pct": 52.5, "tendency": "STAR_FRIENDLY"},
    "tony padilla": {"avg_total": 144.8, "home_win_pct": 53.5, "fouls_per_game": 40.5, "over_pct": 51.8, "tendency": "STAR_FRIENDLY"},
    "ray natili": {"avg_total": 145.2, "home_win_pct": 52.8, "fouls_per_game": 39.8, "over_pct": 52.0, "tendency": "STAR_FRIENDLY"},
    
    # Neutral
    "bo boroski": {"avg_total": 142.5, "home_win_pct": 52.5, "fouls_per_game": 35.2, "over_pct": 50.2, "tendency": "NEUTRAL"},
    "rick crawford": {"avg_total": 143.0, "home_win_pct": 52.0, "fouls_per_game": 35.5, "over_pct": 50.5, "tendency": "NEUTRAL"},
    "mike nance": {"avg_total": 142.8, "home_win_pct": 51.8, "fouls_per_game": 35.0, "over_pct": 50.0, "tendency": "NEUTRAL"},
    "randy mcall": {"avg_total": 143.2, "home_win_pct": 52.2, "fouls_per_game": 35.8, "over_pct": 50.8, "tendency": "NEUTRAL"},
}


# ============================================================
# LEAGUE AVERAGES
# ============================================================

LEAGUE_AVERAGES = {
    "NBA": {"avg_total": 219.0, "home_win_pct": 52.5, "fouls_per_game": 39.5, "over_pct": 50.0},
    "NFL": {"penalties_per_game": 12.0, "home_win_pct": 52.5, "over_pct": 50.0, "pass_int_rate": 0.6},
    "MLB": {"runs_per_game": 8.5, "home_win_pct": 52.0, "over_pct": 50.0, "k_rate": 17.0},
    "NHL": {"penalties_per_game": 6.5, "home_win_pct": 52.0, "over_pct": 50.0, "pp_opportunities": 6.0},
    "NCAAB": {"avg_total": 143.0, "home_win_pct": 55.0, "fouls_per_game": 35.0, "over_pct": 50.0},
}


# ============================================================
# MULTI-SPORT OFFICIALS SERVICE
# ============================================================

class OfficialsService:
    """Multi-sport officials analysis"""
    
    OFFICIALS_DATA = {
        "NBA": NBA_OFFICIALS,
        "NFL": NFL_OFFICIALS,
        "MLB": MLB_OFFICIALS,
        "NHL": NHL_OFFICIALS,
        "NCAAB": NCAAB_OFFICIALS,
    }
    
    @classmethod
    def get_official_profile(cls, sport: str, official_name: str) -> Optional[Dict]:
        """Get profile for a single official"""
        sport = sport.upper()
        officials = cls.OFFICIALS_DATA.get(sport, {})
        return officials.get(official_name.lower())
    
    @classmethod
    def analyze_crew(cls, sport: str, lead_official: str, 
                     official_2: str = "", official_3: str = "") -> Dict:
        """
        Analyze an officiating crew
        
        Args:
            sport: NBA, NFL, MLB, NHL, NCAAB
            lead_official: Crew chief / Head referee / Home plate umpire
            official_2: Second official (if applicable)
            official_3: Third official (if applicable)
        """
        sport = sport.upper()
        officials_data = cls.OFFICIALS_DATA.get(sport, {})
        league_avg = LEAGUE_AVERAGES.get(sport, {})
        
        if not officials_data:
            return {"has_data": False, "error": f"Sport {sport} not supported"}
        
        officials = [o.lower().strip() for o in [lead_official, official_2, official_3] if o]
        
        if not officials:
            return {"has_data": False, "recommendation": "NO_OFFICIAL_DATA"}
        
        # Weights based on sport
        if sport in ["NBA", "NCAAB"]:
            weights = [0.5, 0.3, 0.2][:len(officials)]
        elif sport == "NFL":
            weights = [0.7, 0.2, 0.1][:len(officials)]  # Head ref dominates
        elif sport == "MLB":
            weights = [0.8, 0.1, 0.1][:len(officials)]  # Home plate ump is key
        elif sport == "NHL":
            weights = [0.5, 0.5][:len(officials)]  # Two refs share duties
        else:
            weights = [1.0 / len(officials)] * len(officials)
        
        # Initialize combined stats
        combined = {"officials_found": [], "officials_missing": []}
        stat_totals = {}
        total_weight = 0
        tendencies = []
        
        for i, official in enumerate(officials):
            weight = weights[i] if i < len(weights) else 0.2
            profile = officials_data.get(official)
            
            if profile:
                combined["officials_found"].append(official.title())
                tendencies.append(profile.get("tendency", "NEUTRAL"))
                total_weight += weight
                
                for key, value in profile.items():
                    if key != "tendency" and isinstance(value, (int, float)):
                        if key not in stat_totals:
                            stat_totals[key] = 0
                        stat_totals[key] += value * weight
            else:
                combined["officials_missing"].append(official.title())
        
        if total_weight == 0:
            return {"has_data": False, "recommendation": "NO_OFFICIAL_DATA"}
        
        # Normalize stats
        for key in stat_totals:
            combined[key] = round(stat_totals[key] / total_weight, 1)
        
        # Calculate edges vs league average
        combined["edges"] = {}
        for key in stat_totals:
            if key in league_avg:
                combined["edges"][key] = round(combined[key] - league_avg[key], 1)
        
        # Determine recommendations based on sport
        combined.update(cls._get_recommendations(sport, combined, tendencies))
        
        combined["has_data"] = True
        combined["sport"] = sport
        combined["tendencies"] = tendencies
        combined["confidence"] = min(90, len(combined["officials_found"]) * 30)
        
        return combined
    
    @classmethod
    def _get_recommendations(cls, sport: str, combined: Dict, tendencies: List) -> Dict:
        """Generate sport-specific recommendations"""
        recs = {}
        
        over_pct = combined.get("over_pct", 50)
        home_pct = combined.get("home_win_pct", 52)
        
        # Total recommendation
        if over_pct >= 53:
            recs["total_recommendation"] = "OVER"
            recs["total_strength"] = min(0.9, (over_pct - 50) / 10)
        elif over_pct <= 47:
            recs["total_recommendation"] = "UNDER"
            recs["total_strength"] = min(0.9, (50 - over_pct) / 10)
        else:
            recs["total_recommendation"] = "NEUTRAL"
            recs["total_strength"] = 0
        
        # Spread recommendation (home-friendly)
        home_threshold = 55 if sport != "NCAAB" else 58  # College crowds are louder
        if home_pct >= home_threshold:
            recs["spread_recommendation"] = "HOME"
            recs["spread_strength"] = min(0.9, (home_pct - 52) / 6)
        elif home_pct <= 50:
            recs["spread_recommendation"] = "AWAY"
            recs["spread_strength"] = min(0.9, (52 - home_pct) / 6)
        else:
            recs["spread_recommendation"] = "NEUTRAL"
            recs["spread_strength"] = 0
        
        # Props recommendation (sport-specific)
        if sport in ["NBA", "NCAAB"]:
            fouls = combined.get("fouls_per_game", 35)
            if fouls >= 40:
                recs["props_lean"] = "OVER"
                recs["star_impact"] = "HIGH"
            elif fouls <= 34:
                recs["props_lean"] = "UNDER"
                recs["star_impact"] = "LOW"
            else:
                recs["props_lean"] = "NEUTRAL"
                recs["star_impact"] = "NEUTRAL"
        
        elif sport == "NFL":
            penalties = combined.get("penalties_per_game", 12)
            if penalties >= 13:
                recs["props_lean"] = "UNDER"  # More stoppages
                recs["game_flow"] = "CHOPPY"
            elif penalties <= 11:
                recs["props_lean"] = "OVER"  # Faster game
                recs["game_flow"] = "SMOOTH"
            else:
                recs["props_lean"] = "NEUTRAL"
                recs["game_flow"] = "NEUTRAL"
        
        elif sport == "MLB":
            zone = combined.get("strike_zone", "average")
            if isinstance(zone, str):
                if zone == "tight":
                    recs["props_lean"] = "OVER"
                    recs["zone_impact"] = "HITTER_FRIENDLY"
                elif zone == "wide":
                    recs["props_lean"] = "UNDER"
                    recs["zone_impact"] = "PITCHER_FRIENDLY"
            else:
                runs = combined.get("runs_per_game", 8.5)
                if runs >= 9.2:
                    recs["props_lean"] = "OVER"
                    recs["zone_impact"] = "HITTER_FRIENDLY"
                elif runs <= 7.8:
                    recs["props_lean"] = "UNDER"
                    recs["zone_impact"] = "PITCHER_FRIENDLY"
                else:
                    recs["props_lean"] = "NEUTRAL"
                    recs["zone_impact"] = "NEUTRAL"
        
        elif sport == "NHL":
            penalties = combined.get("penalties_per_game", 6.5)
            if penalties >= 7.5:
                recs["props_lean"] = "OVER"  # More PP = more goals
                recs["pp_impact"] = "HIGH"
            elif penalties <= 5.5:
                recs["props_lean"] = "UNDER"
                recs["pp_impact"] = "LOW"
            else:
                recs["props_lean"] = "NEUTRAL"
                recs["pp_impact"] = "NEUTRAL"
        
        return recs
    
    @classmethod
    def get_adjustment(cls, sport: str, lead_official: str, 
                       official_2: str = "", official_3: str = "",
                       bet_type: str = "total", is_home: bool = False, 
                       is_star: bool = False) -> Optional[Dict]:
        """
        Get betting adjustment based on officials
        """
        analysis = cls.analyze_crew(sport, lead_official, official_2, official_3)
        
        if not analysis.get("has_data"):
            return None
        
        sport = sport.upper()
        
        # TOTAL adjustment
        if bet_type == "total":
            rec = analysis.get("total_recommendation", "NEUTRAL")
            strength = analysis.get("total_strength", 0)
            
            if rec in ["OVER", "UNDER"] and strength > 0.3:
                edge = analysis.get("edges", {}).get("over_pct", 0)
                return {
                    "label": "Officials",
                    "icon": "🦓",
                    "value": round(edge * 0.1, 1),  # Convert % to points
                    "reason": f"{analysis.get('over_pct', 50)}% over rate - {', '.join(analysis['officials_found'][:2])}",
                    "recommendation": rec
                }
        
        # SPREAD adjustment
        elif bet_type == "spread":
            rec = analysis.get("spread_recommendation", "NEUTRAL")
            strength = analysis.get("spread_strength", 0)
            
            if rec == "HOME" and is_home and strength > 0.3:
                edge = analysis.get("edges", {}).get("home_win_pct", 0)
                return {
                    "label": "Officials",
                    "icon": "🦓",
                    "value": round(edge * 0.05, 1),
                    "reason": f"{analysis.get('home_win_pct', 52)}% home win rate",
                    "recommendation": "HOME"
                }
        
        # PROPS adjustment
        elif bet_type == "props":
            props_lean = analysis.get("props_lean", "NEUTRAL")
            star_impact = analysis.get("star_impact", "NEUTRAL")
            
            if is_star and star_impact == "HIGH":
                return {
                    "label": "Officials",
                    "icon": "🦓",
                    "value": 1.5,
                    "reason": f"High-foul officials benefit stars",
                    "recommendation": "OVER"
                }
            elif is_star and star_impact == "LOW":
                return {
                    "label": "Officials",
                    "icon": "🦓",
                    "value": -1.0,
                    "reason": f"Low-foul officials limit FT opportunities",
                    "recommendation": "UNDER"
                }
        
        return None
    
    @classmethod
    def get_all_officials_by_tendency(cls, sport: str) -> Dict:
        """Get all officials for a sport grouped by tendency"""
        sport = sport.upper()
        officials_data = cls.OFFICIALS_DATA.get(sport, {})
        
        grouped = {}
        
        for official, profile in officials_data.items():
            tendency = profile.get("tendency", "NEUTRAL")
            if tendency not in grouped:
                grouped[tendency] = []
            grouped[tendency].append({"name": official.title(), **profile})
        
        # Sort each group
        for tendency in grouped:
            if "over_pct" in grouped[tendency][0]:
                if "OVER" in tendency:
                    grouped[tendency].sort(key=lambda x: x.get("over_pct", 50), reverse=True)
                elif "UNDER" in tendency:
                    grouped[tendency].sort(key=lambda x: x.get("over_pct", 50))
        
        return grouped
    
    @classmethod
    def get_supported_sports(cls) -> List[str]:
        """Get list of sports with officials data"""
        return list(cls.OFFICIALS_DATA.keys())


# ============================================================
# QUICK TEST
# ============================================================

if __name__ == "__main__":
    print("=" * 70)
    print("🦓 BOOKIE-O-EM OFFICIALS LAYER - MULTI-SPORT")
    print("=" * 70)
    
    # Test NBA
    print("\n🏀 NBA: Scott Foster + Tony Brothers")
    nba = OfficialsService.analyze_crew("NBA", "Scott Foster", "Tony Brothers")
    print(f"   Over %: {nba.get('over_pct')}% | Rec: {nba.get('total_recommendation')}")
    
    # Test NFL
    print("\n🏈 NFL: Bill Vinovich")
    nfl = OfficialsService.analyze_crew("NFL", "Bill Vinovich")
    print(f"   Over %: {nfl.get('over_pct')}% | Penalties: {nfl.get('penalties_per_game')}")
    
    # Test MLB
    print("\n⚾ MLB: Pat Hoberg")
    mlb = OfficialsService.analyze_crew("MLB", "Pat Hoberg")
    print(f"   Over %: {mlb.get('over_pct')}% | Zone: {mlb.get('zone_impact', 'N/A')}")
    
    # Test NHL
    print("\n🏒 NHL: Wes McCauley")
    nhl = OfficialsService.analyze_crew("NHL", "Wes McCauley")
    print(f"   Over %: {nhl.get('over_pct')}% | Penalties: {nhl.get('penalties_per_game')}")
    
    # Test NCAAB
    print("\n🎓 NCAAB: Ted Valentine")
    ncaab = OfficialsService.analyze_crew("NCAAB", "Ted Valentine")
    print(f"   Over %: {ncaab.get('over_pct')}% | Rec: {ncaab.get('total_recommendation')}")
    
    print("\n" + "=" * 70)
    print("✅ MULTI-SPORT OFFICIALS LAYER READY!")
    print("=" * 70)
