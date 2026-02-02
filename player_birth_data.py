"""
Player Birth Data for Esoteric Calculations
Real birth dates for biorhythm, numerology, and life path analysis.

Data Sources: Wikipedia, Sports Reference, Team Rosters
Last Updated: February 2026

Coverage:
- NBA: 109 players (stars + key role players across all 30 teams)
- NFL: 73 players (QBs, RBs, WRs, TEs + 25 defensive stars)
- MLB: 55 players (hitters, pitchers, catchers, middle infielders)
- NHL: 56 players (superstars + 2nd/3rd line scorers, defensemen, goalies)
- NCAAB: 14 top prospects
- TOTAL: 307 players
"""

from typing import Dict, Any

# =============================================================================
# NBA PLAYERS (30 teams, key players)
# =============================================================================

NBA_PLAYERS: Dict[str, Dict[str, Any]] = {
    # Lakers
    "LeBron James": {"birth_date": "1984-12-30", "jersey": 23, "team": "Lakers"},
    "Anthony Davis": {"birth_date": "1993-03-11", "jersey": 3, "team": "Lakers"},
    "Austin Reaves": {"birth_date": "1998-05-29", "jersey": 15, "team": "Lakers"},
    "D'Angelo Russell": {"birth_date": "1996-02-23", "jersey": 1, "team": "Lakers"},
    "Rui Hachimura": {"birth_date": "1998-02-08", "jersey": 28, "team": "Lakers"},
    "Gabe Vincent": {"birth_date": "1996-06-14", "jersey": 7, "team": "Lakers"},

    # Warriors
    "Stephen Curry": {"birth_date": "1988-03-14", "jersey": 30, "team": "Warriors"},
    "Draymond Green": {"birth_date": "1990-03-04", "jersey": 23, "team": "Warriors"},
    "Andrew Wiggins": {"birth_date": "1995-02-23", "jersey": 22, "team": "Warriors"},
    "Klay Thompson": {"birth_date": "1990-02-08", "jersey": 11, "team": "Warriors"},

    # Celtics
    "Jayson Tatum": {"birth_date": "1998-03-03", "jersey": 0, "team": "Celtics"},
    "Jaylen Brown": {"birth_date": "1996-10-24", "jersey": 7, "team": "Celtics"},
    "Derrick White": {"birth_date": "1994-07-02", "jersey": 9, "team": "Celtics"},
    "Kristaps Porzingis": {"birth_date": "1995-08-02", "jersey": 8, "team": "Celtics"},
    "Al Horford": {"birth_date": "1986-06-03", "jersey": 42, "team": "Celtics"},
    "Jrue Holiday": {"birth_date": "1990-06-12", "jersey": 4, "team": "Celtics"},

    # Bucks
    "Giannis Antetokounmpo": {"birth_date": "1994-12-06", "jersey": 34, "team": "Bucks"},
    "Damian Lillard": {"birth_date": "1990-07-15", "jersey": 0, "team": "Bucks"},
    "Khris Middleton": {"birth_date": "1991-08-12", "jersey": 22, "team": "Bucks"},
    "Brook Lopez": {"birth_date": "1988-04-01", "jersey": 11, "team": "Bucks"},
    "Bobby Portis": {"birth_date": "1995-02-10", "jersey": 9, "team": "Bucks"},

    # 76ers
    "Joel Embiid": {"birth_date": "1994-03-16", "jersey": 21, "team": "76ers"},
    "Tyrese Maxey": {"birth_date": "2000-11-04", "jersey": 0, "team": "76ers"},
    "Tobias Harris": {"birth_date": "1992-07-15", "jersey": 12, "team": "76ers"},

    # Suns
    "Kevin Durant": {"birth_date": "1988-09-29", "jersey": 35, "team": "Suns"},
    "Devin Booker": {"birth_date": "1996-10-30", "jersey": 1, "team": "Suns"},
    "Bradley Beal": {"birth_date": "1993-06-28", "jersey": 3, "team": "Suns"},

    # Mavericks
    "Luka Doncic": {"birth_date": "1999-02-28", "jersey": 77, "team": "Mavericks"},
    "Kyrie Irving": {"birth_date": "1992-03-23", "jersey": 11, "team": "Mavericks"},
    "Tim Hardaway Jr.": {"birth_date": "1992-03-16", "jersey": 10, "team": "Mavericks"},

    # Nuggets
    "Nikola Jokic": {"birth_date": "1995-02-19", "jersey": 15, "team": "Nuggets"},
    "Jamal Murray": {"birth_date": "1997-02-23", "jersey": 27, "team": "Nuggets"},
    "Michael Porter Jr.": {"birth_date": "1998-06-29", "jersey": 1, "team": "Nuggets"},
    "Aaron Gordon": {"birth_date": "1995-09-16", "jersey": 50, "team": "Nuggets"},
    "Kentavious Caldwell-Pope": {"birth_date": "1993-02-18", "jersey": 5, "team": "Nuggets"},
    "Reggie Jackson": {"birth_date": "1990-04-16", "jersey": 7, "team": "Nuggets"},

    # Heat
    "Jimmy Butler": {"birth_date": "1989-09-14", "jersey": 22, "team": "Heat"},
    "Bam Adebayo": {"birth_date": "1997-07-18", "jersey": 13, "team": "Heat"},
    "Tyler Herro": {"birth_date": "2000-01-20", "jersey": 14, "team": "Heat"},
    "Terry Rozier": {"birth_date": "1994-03-17", "jersey": 2, "team": "Heat"},
    "Duncan Robinson": {"birth_date": "1994-04-22", "jersey": 55, "team": "Heat"},

    # Knicks
    "Jalen Brunson": {"birth_date": "1996-08-31", "jersey": 11, "team": "Knicks"},
    "Julius Randle": {"birth_date": "1994-11-29", "jersey": 30, "team": "Knicks"},
    "RJ Barrett": {"birth_date": "2000-06-14", "jersey": 9, "team": "Knicks"},
    "Josh Hart": {"birth_date": "1995-03-06", "jersey": 3, "team": "Knicks"},
    "OG Anunoby": {"birth_date": "1997-07-17", "jersey": 8, "team": "Knicks"},
    "Mitchell Robinson": {"birth_date": "1998-04-01", "jersey": 23, "team": "Knicks"},

    # Clippers
    "Kawhi Leonard": {"birth_date": "1991-06-29", "jersey": 2, "team": "Clippers"},
    "Paul George": {"birth_date": "1990-05-02", "jersey": 13, "team": "Clippers"},
    "James Harden": {"birth_date": "1989-08-26", "jersey": 1, "team": "Clippers"},
    "Norman Powell": {"birth_date": "1993-05-25", "jersey": 24, "team": "Clippers"},
    "Ivica Zubac": {"birth_date": "1997-03-18", "jersey": 40, "team": "Clippers"},

    # Nets
    "Mikal Bridges": {"birth_date": "1996-08-30", "jersey": 1, "team": "Nets"},
    "Cam Thomas": {"birth_date": "2001-10-13", "jersey": 24, "team": "Nets"},

    # Bulls
    "DeMar DeRozan": {"birth_date": "1989-08-07", "jersey": 11, "team": "Bulls"},
    "Zach LaVine": {"birth_date": "1995-03-10", "jersey": 8, "team": "Bulls"},
    "Nikola Vucevic": {"birth_date": "1990-10-24", "jersey": 9, "team": "Bulls"},

    # Cavaliers
    "Donovan Mitchell": {"birth_date": "1996-09-07", "jersey": 45, "team": "Cavaliers"},
    "Darius Garland": {"birth_date": "2000-01-26", "jersey": 10, "team": "Cavaliers"},
    "Evan Mobley": {"birth_date": "2001-06-18", "jersey": 4, "team": "Cavaliers"},
    "Jarrett Allen": {"birth_date": "1998-04-21", "jersey": 31, "team": "Cavaliers"},

    # Kings
    "De'Aaron Fox": {"birth_date": "1997-12-20", "jersey": 5, "team": "Kings"},
    "Domantas Sabonis": {"birth_date": "1996-05-03", "jersey": 10, "team": "Kings"},
    "Keegan Murray": {"birth_date": "2000-08-19", "jersey": 13, "team": "Kings"},
    "Malik Monk": {"birth_date": "1998-02-04", "jersey": 0, "team": "Kings"},

    # Timberwolves
    "Anthony Edwards": {"birth_date": "2001-08-05", "jersey": 5, "team": "Timberwolves"},
    "Karl-Anthony Towns": {"birth_date": "1995-11-15", "jersey": 32, "team": "Timberwolves"},
    "Rudy Gobert": {"birth_date": "1992-06-26", "jersey": 27, "team": "Timberwolves"},
    "Donte DiVincenzo": {"birth_date": "1997-01-31", "jersey": 0, "team": "Timberwolves"},
    "Mike Conley": {"birth_date": "1987-10-11", "jersey": 10, "team": "Timberwolves"},

    # Thunder
    "Shai Gilgeous-Alexander": {"birth_date": "1998-07-12", "jersey": 2, "team": "Thunder"},
    "Chet Holmgren": {"birth_date": "2002-05-01", "jersey": 7, "team": "Thunder"},
    "Jalen Williams": {"birth_date": "2001-04-10", "jersey": 8, "team": "Thunder"},

    # Pelicans
    "Zion Williamson": {"birth_date": "2000-07-06", "jersey": 1, "team": "Pelicans"},
    "Brandon Ingram": {"birth_date": "1997-09-02", "jersey": 14, "team": "Pelicans"},
    "CJ McCollum": {"birth_date": "1991-09-19", "jersey": 3, "team": "Pelicans"},

    # Hawks
    "Trae Young": {"birth_date": "1998-09-19", "jersey": 11, "team": "Hawks"},
    "Dejounte Murray": {"birth_date": "1996-09-19", "jersey": 5, "team": "Hawks"},
    "John Collins": {"birth_date": "1997-09-23", "jersey": 20, "team": "Hawks"},

    # Grizzlies
    "Ja Morant": {"birth_date": "1999-08-10", "jersey": 12, "team": "Grizzlies"},
    "Desmond Bane": {"birth_date": "1998-06-25", "jersey": 22, "team": "Grizzlies"},
    "Jaren Jackson Jr.": {"birth_date": "1999-09-15", "jersey": 13, "team": "Grizzlies"},

    # Rockets
    "Jalen Green": {"birth_date": "2002-02-09", "jersey": 4, "team": "Rockets"},
    "Alperen Sengun": {"birth_date": "2002-07-25", "jersey": 28, "team": "Rockets"},
    "Fred VanVleet": {"birth_date": "1994-02-25", "jersey": 5, "team": "Rockets"},

    # Spurs
    "Victor Wembanyama": {"birth_date": "2004-01-04", "jersey": 1, "team": "Spurs"},
    "Devin Vassell": {"birth_date": "2000-08-23", "jersey": 24, "team": "Spurs"},
    "Keldon Johnson": {"birth_date": "1999-10-11", "jersey": 3, "team": "Spurs"},

    # Pacers
    "Tyrese Haliburton": {"birth_date": "2000-02-29", "jersey": 0, "team": "Pacers"},
    "Myles Turner": {"birth_date": "1996-03-24", "jersey": 33, "team": "Pacers"},
    "Buddy Hield": {"birth_date": "1992-12-17", "jersey": 7, "team": "Pacers"},

    # Trail Blazers
    "Anfernee Simons": {"birth_date": "1999-06-08", "jersey": 1, "team": "Trail Blazers"},
    "Scoot Henderson": {"birth_date": "2004-02-03", "jersey": 0, "team": "Trail Blazers"},

    # Magic
    "Paolo Banchero": {"birth_date": "2002-11-12", "jersey": 5, "team": "Magic"},
    "Franz Wagner": {"birth_date": "2001-08-27", "jersey": 22, "team": "Magic"},
    "Wendell Carter Jr.": {"birth_date": "1999-04-16", "jersey": 34, "team": "Magic"},

    # Raptors
    "Scottie Barnes": {"birth_date": "2001-08-01", "jersey": 4, "team": "Raptors"},
    "Pascal Siakam": {"birth_date": "1994-04-02", "jersey": 43, "team": "Raptors"},
    "Gary Trent Jr.": {"birth_date": "1999-01-18", "jersey": 33, "team": "Raptors"},

    # Pistons
    "Cade Cunningham": {"birth_date": "2001-09-25", "jersey": 2, "team": "Pistons"},
    "Jaden Ivey": {"birth_date": "2002-02-13", "jersey": 23, "team": "Pistons"},
    "Ausar Thompson": {"birth_date": "2003-01-30", "jersey": 5, "team": "Pistons"},

    # Hornets
    "LaMelo Ball": {"birth_date": "2001-08-22", "jersey": 1, "team": "Hornets"},
    "Brandon Miller": {"birth_date": "2003-04-21", "jersey": 24, "team": "Hornets"},
    "Mark Williams": {"birth_date": "2001-12-16", "jersey": 5, "team": "Hornets"},

    # Wizards
    "Jordan Poole": {"birth_date": "1999-06-19", "jersey": 13, "team": "Wizards"},
    "Kyle Kuzma": {"birth_date": "1995-07-24", "jersey": 33, "team": "Wizards"},

    # Jazz
    "Lauri Markkanen": {"birth_date": "1997-05-22", "jersey": 23, "team": "Jazz"},
    "John Collins": {"birth_date": "1997-09-23", "jersey": 20, "team": "Jazz"},
    "Walker Kessler": {"birth_date": "2001-07-26", "jersey": 24, "team": "Jazz"},
}

# =============================================================================
# NFL PLAYERS (Key QBs, RBs, WRs, TEs)
# =============================================================================

NFL_PLAYERS: Dict[str, Dict[str, Any]] = {
    # Quarterbacks
    "Patrick Mahomes": {"birth_date": "1995-09-17", "jersey": 15, "team": "Chiefs", "position": "QB"},
    "Josh Allen": {"birth_date": "1996-05-21", "jersey": 17, "team": "Bills", "position": "QB"},
    "Joe Burrow": {"birth_date": "1996-12-10", "jersey": 9, "team": "Bengals", "position": "QB"},
    "Lamar Jackson": {"birth_date": "1997-01-07", "jersey": 8, "team": "Ravens", "position": "QB"},
    "Jalen Hurts": {"birth_date": "1998-08-07", "jersey": 1, "team": "Eagles", "position": "QB"},
    "Justin Herbert": {"birth_date": "1998-03-10", "jersey": 10, "team": "Chargers", "position": "QB"},
    "Trevor Lawrence": {"birth_date": "1999-10-06", "jersey": 16, "team": "Jaguars", "position": "QB"},
    "Dak Prescott": {"birth_date": "1993-07-29", "jersey": 4, "team": "Cowboys", "position": "QB"},
    "Tua Tagovailoa": {"birth_date": "1998-03-02", "jersey": 1, "team": "Dolphins", "position": "QB"},
    "Brock Purdy": {"birth_date": "1999-12-28", "jersey": 13, "team": "49ers", "position": "QB"},
    "Kirk Cousins": {"birth_date": "1988-08-19", "jersey": 8, "team": "Falcons", "position": "QB"},
    "Jared Goff": {"birth_date": "1994-10-14", "jersey": 16, "team": "Lions", "position": "QB"},
    "Jordan Love": {"birth_date": "1998-11-02", "jersey": 10, "team": "Packers", "position": "QB"},
    "C.J. Stroud": {"birth_date": "2001-10-03", "jersey": 7, "team": "Texans", "position": "QB"},
    "Anthony Richardson": {"birth_date": "2002-05-21", "jersey": 5, "team": "Colts", "position": "QB"},
    "Bryce Young": {"birth_date": "2001-07-25", "jersey": 9, "team": "Panthers", "position": "QB"},
    "Caleb Williams": {"birth_date": "2001-11-18", "jersey": 18, "team": "Bears", "position": "QB"},

    # Running Backs
    "Christian McCaffrey": {"birth_date": "1996-06-07", "jersey": 23, "team": "49ers", "position": "RB"},
    "Derrick Henry": {"birth_date": "1994-01-04", "jersey": 22, "team": "Titans", "position": "RB"},
    "Nick Chubb": {"birth_date": "1995-12-27", "jersey": 24, "team": "Browns", "position": "RB"},
    "Saquon Barkley": {"birth_date": "1997-02-09", "jersey": 26, "team": "Giants", "position": "RB"},
    "Josh Jacobs": {"birth_date": "1998-02-11", "jersey": 28, "team": "Raiders", "position": "RB"},
    "Tony Pollard": {"birth_date": "1997-04-30", "jersey": 20, "team": "Cowboys", "position": "RB"},
    "Bijan Robinson": {"birth_date": "2002-02-28", "jersey": 7, "team": "Falcons", "position": "RB"},
    "Breece Hall": {"birth_date": "2001-04-21", "jersey": 20, "team": "Jets", "position": "RB"},
    "Jonathan Taylor": {"birth_date": "1999-01-19", "jersey": 28, "team": "Colts", "position": "RB"},
    "Travis Etienne Jr.": {"birth_date": "1999-01-26", "jersey": 1, "team": "Jaguars", "position": "RB"},
    "Jahmyr Gibbs": {"birth_date": "2002-04-24", "jersey": 26, "team": "Lions", "position": "RB"},

    # Wide Receivers
    "Tyreek Hill": {"birth_date": "1994-03-01", "jersey": 10, "team": "Dolphins", "position": "WR"},
    "Justin Jefferson": {"birth_date": "1999-06-16", "jersey": 18, "team": "Vikings", "position": "WR"},
    "Ja'Marr Chase": {"birth_date": "2000-03-01", "jersey": 1, "team": "Bengals", "position": "WR"},
    "CeeDee Lamb": {"birth_date": "1999-04-08", "jersey": 88, "team": "Cowboys", "position": "WR"},
    "A.J. Brown": {"birth_date": "1997-06-30", "jersey": 11, "team": "Eagles", "position": "WR"},
    "Stefon Diggs": {"birth_date": "1993-11-29", "jersey": 14, "team": "Bills", "position": "WR"},
    "Davante Adams": {"birth_date": "1992-12-24", "jersey": 17, "team": "Raiders", "position": "WR"},
    "DeVonta Smith": {"birth_date": "1998-11-14", "jersey": 6, "team": "Eagles", "position": "WR"},
    "Amon-Ra St. Brown": {"birth_date": "1999-10-24", "jersey": 14, "team": "Lions", "position": "WR"},
    "Chris Olave": {"birth_date": "2000-06-27", "jersey": 12, "team": "Saints", "position": "WR"},
    "Garrett Wilson": {"birth_date": "2000-07-22", "jersey": 17, "team": "Jets", "position": "WR"},
    "Nico Collins": {"birth_date": "1999-05-10", "jersey": 12, "team": "Texans", "position": "WR"},
    "Marvin Harrison Jr.": {"birth_date": "2002-08-16", "jersey": 18, "team": "Cardinals", "position": "WR"},

    # Tight Ends
    "Travis Kelce": {"birth_date": "1989-10-05", "jersey": 87, "team": "Chiefs", "position": "TE"},
    "George Kittle": {"birth_date": "1993-10-09", "jersey": 85, "team": "49ers", "position": "TE"},
    "Mark Andrews": {"birth_date": "1995-09-06", "jersey": 89, "team": "Ravens", "position": "TE"},
    "T.J. Hockenson": {"birth_date": "1997-07-03", "jersey": 87, "team": "Vikings", "position": "TE"},
    "Dallas Goedert": {"birth_date": "1995-01-03", "jersey": 88, "team": "Eagles", "position": "TE"},
    "Sam LaPorta": {"birth_date": "2000-03-11", "jersey": 87, "team": "Lions", "position": "TE"},
    "Evan Engram": {"birth_date": "1994-09-02", "jersey": 17, "team": "Jaguars", "position": "TE"},

    # Defensive Players - Edge Rushers
    "Micah Parsons": {"birth_date": "1999-05-26", "jersey": 11, "team": "Cowboys", "position": "LB"},
    "T.J. Watt": {"birth_date": "1994-10-11", "jersey": 90, "team": "Steelers", "position": "LB"},
    "Nick Bosa": {"birth_date": "1997-10-23", "jersey": 97, "team": "49ers", "position": "DE"},
    "Myles Garrett": {"birth_date": "1995-12-29", "jersey": 95, "team": "Browns", "position": "DE"},
    "Maxx Crosby": {"birth_date": "1997-08-22", "jersey": 98, "team": "Raiders", "position": "DE"},
    "Chris Jones": {"birth_date": "1994-07-03", "jersey": 95, "team": "Chiefs", "position": "DT"},
    "Cameron Jordan": {"birth_date": "1989-07-10", "jersey": 94, "team": "Saints", "position": "DE"},
    "Khalil Mack": {"birth_date": "1991-02-22", "jersey": 52, "team": "Chargers", "position": "LB"},

    # Defensive Players - Cornerbacks
    "Patrick Surtain II": {"birth_date": "2000-04-14", "jersey": 2, "team": "Broncos", "position": "CB"},
    "Sauce Gardner": {"birth_date": "2000-08-31", "jersey": 1, "team": "Jets", "position": "CB"},
    "Jalen Ramsey": {"birth_date": "1994-10-24", "jersey": 5, "team": "Dolphins", "position": "CB"},
    "Denzel Ward": {"birth_date": "1997-04-28", "jersey": 21, "team": "Browns", "position": "CB"},
    "Marshon Lattimore": {"birth_date": "1996-05-20", "jersey": 23, "team": "Saints", "position": "CB"},
    "Trevon Diggs": {"birth_date": "1997-09-20", "jersey": 7, "team": "Cowboys", "position": "CB"},
    "Derek Stingley Jr.": {"birth_date": "2001-09-03", "jersey": 24, "team": "Texans", "position": "CB"},

    # Defensive Players - Safeties
    "Derwin James": {"birth_date": "1996-08-03", "jersey": 3, "team": "Chargers", "position": "S"},
    "Jessie Bates": {"birth_date": "1997-02-26", "jersey": 30, "team": "Falcons", "position": "S"},
    "Minkah Fitzpatrick": {"birth_date": "1996-11-17", "jersey": 39, "team": "Steelers", "position": "S"},
    "Justin Simmons": {"birth_date": "1993-11-19", "jersey": 31, "team": "Broncos", "position": "S"},
    "Antoine Winfield Jr.": {"birth_date": "1998-08-16", "jersey": 31, "team": "Buccaneers", "position": "S"},

    # Defensive Players - Linebackers
    "Fred Warner": {"birth_date": "1996-11-19", "jersey": 54, "team": "49ers", "position": "LB"},
    "Roquan Smith": {"birth_date": "1997-04-08", "jersey": 0, "team": "Ravens", "position": "LB"},
    "Lavonte David": {"birth_date": "1990-01-23", "jersey": 54, "team": "Buccaneers", "position": "LB"},
    "Bobby Wagner": {"birth_date": "1990-06-27", "jersey": 45, "team": "Commanders", "position": "LB"},
    "Tremaine Edmunds": {"birth_date": "1998-05-02", "jersey": 49, "team": "Bears", "position": "LB"},
}

# =============================================================================
# MLB PLAYERS (Key hitters, pitchers)
# =============================================================================

MLB_PLAYERS: Dict[str, Dict[str, Any]] = {
    # Superstars
    "Shohei Ohtani": {"birth_date": "1994-07-05", "jersey": 17, "team": "Dodgers", "position": "DH/P"},
    "Mike Trout": {"birth_date": "1991-08-07", "jersey": 27, "team": "Angels", "position": "CF"},
    "Mookie Betts": {"birth_date": "1992-10-07", "jersey": 50, "team": "Dodgers", "position": "RF"},
    "Aaron Judge": {"birth_date": "1992-04-26", "jersey": 99, "team": "Yankees", "position": "RF"},
    "Ronald Acuna Jr.": {"birth_date": "1997-12-18", "jersey": 13, "team": "Braves", "position": "RF"},
    "Freddie Freeman": {"birth_date": "1989-09-12", "jersey": 5, "team": "Dodgers", "position": "1B"},
    "Juan Soto": {"birth_date": "1998-10-25", "jersey": 22, "team": "Padres", "position": "RF"},
    "Corey Seager": {"birth_date": "1994-04-27", "jersey": 5, "team": "Rangers", "position": "SS"},
    "Fernando Tatis Jr.": {"birth_date": "1999-01-02", "jersey": 23, "team": "Padres", "position": "RF"},
    "Trea Turner": {"birth_date": "1993-06-30", "jersey": 7, "team": "Phillies", "position": "SS"},

    # More Hitters
    "Manny Machado": {"birth_date": "1992-07-06", "jersey": 13, "team": "Padres", "position": "3B"},
    "Pete Alonso": {"birth_date": "1994-12-07", "jersey": 20, "team": "Mets", "position": "1B"},
    "Matt Olson": {"birth_date": "1994-03-29", "jersey": 28, "team": "Braves", "position": "1B"},
    "Marcus Semien": {"birth_date": "1990-09-17", "jersey": 2, "team": "Rangers", "position": "2B"},
    "Bo Bichette": {"birth_date": "1998-03-05", "jersey": 11, "team": "Blue Jays", "position": "SS"},
    "Vladimir Guerrero Jr.": {"birth_date": "1999-03-16", "jersey": 27, "team": "Blue Jays", "position": "1B"},
    "Rafael Devers": {"birth_date": "1996-10-24", "jersey": 11, "team": "Red Sox", "position": "3B"},
    "Julio Rodriguez": {"birth_date": "2000-12-29", "jersey": 44, "team": "Mariners", "position": "CF"},
    "Adley Rutschman": {"birth_date": "1998-02-06", "jersey": 35, "team": "Orioles", "position": "C"},
    "Gunnar Henderson": {"birth_date": "2001-06-29", "jersey": 2, "team": "Orioles", "position": "SS"},
    "Bobby Witt Jr.": {"birth_date": "2000-06-14", "jersey": 7, "team": "Royals", "position": "SS"},
    "Elly De La Cruz": {"birth_date": "2002-01-11", "jersey": 44, "team": "Reds", "position": "SS"},
    "Corbin Carroll": {"birth_date": "2000-08-21", "jersey": 7, "team": "Diamondbacks", "position": "CF"},

    # Top Pitchers
    "Spencer Strider": {"birth_date": "1998-10-28", "jersey": 65, "team": "Braves", "position": "SP"},
    "Gerrit Cole": {"birth_date": "1990-09-08", "jersey": 45, "team": "Yankees", "position": "SP"},
    "Max Scherzer": {"birth_date": "1984-07-27", "jersey": 21, "team": "Rangers", "position": "SP"},
    "Jacob deGrom": {"birth_date": "1988-06-19", "jersey": 48, "team": "Rangers", "position": "SP"},
    "Zack Wheeler": {"birth_date": "1990-05-30", "jersey": 45, "team": "Phillies", "position": "SP"},
    "Aaron Nola": {"birth_date": "1993-06-04", "jersey": 27, "team": "Phillies", "position": "SP"},
    "Corbin Burnes": {"birth_date": "1994-10-22", "jersey": 39, "team": "Brewers", "position": "SP"},
    "Dylan Cease": {"birth_date": "1995-12-28", "jersey": 84, "team": "Padres", "position": "SP"},
    "Kevin Gausman": {"birth_date": "1991-01-06", "jersey": 34, "team": "Blue Jays", "position": "SP"},
    "Shane McClanahan": {"birth_date": "1997-04-28", "jersey": 18, "team": "Rays", "position": "SP"},
    "Logan Webb": {"birth_date": "1996-11-18", "jersey": 62, "team": "Giants", "position": "SP"},
    "Yoshinobu Yamamoto": {"birth_date": "1998-08-17", "jersey": 18, "team": "Dodgers", "position": "SP"},

    # Closers
    "Josh Hader": {"birth_date": "1994-04-07", "jersey": 71, "team": "Astros", "position": "RP"},
    "Edwin Diaz": {"birth_date": "1994-03-22", "jersey": 39, "team": "Mets", "position": "RP"},
    "Emmanuel Clase": {"birth_date": "1998-03-18", "jersey": 48, "team": "Guardians", "position": "RP"},
    "Devin Williams": {"birth_date": "1994-09-21", "jersey": 38, "team": "Brewers", "position": "RP"},

    # Catchers
    "J.T. Realmuto": {"birth_date": "1991-03-18", "jersey": 10, "team": "Phillies", "position": "C"},
    "Will Smith": {"birth_date": "1995-03-28", "jersey": 16, "team": "Dodgers", "position": "C"},
    "Salvador Perez": {"birth_date": "1990-05-10", "jersey": 13, "team": "Royals", "position": "C"},
    "Sean Murphy": {"birth_date": "1994-10-04", "jersey": 12, "team": "Braves", "position": "C"},
    "William Contreras": {"birth_date": "1997-12-24", "jersey": 24, "team": "Brewers", "position": "C"},
    "Cal Raleigh": {"birth_date": "1996-11-26", "jersey": 29, "team": "Mariners", "position": "C"},
    "Jonah Heim": {"birth_date": "1995-06-27", "jersey": 28, "team": "Rangers", "position": "C"},
    "Tyler Stephenson": {"birth_date": "1996-08-16", "jersey": 37, "team": "Reds", "position": "C"},

    # Middle Infielders
    "Xander Bogaerts": {"birth_date": "1992-10-01", "jersey": 2, "team": "Padres", "position": "SS"},
    "Tommy Edman": {"birth_date": "1995-05-09", "jersey": 19, "team": "Cardinals", "position": "2B"},
    "Andres Gimenez": {"birth_date": "1998-09-04", "jersey": 0, "team": "Guardians", "position": "2B"},
    "Jorge Polanco": {"birth_date": "1993-07-05", "jersey": 11, "team": "Twins", "position": "2B"},
    "Nico Hoerner": {"birth_date": "1997-05-13", "jersey": 2, "team": "Cubs", "position": "SS"},
    "Carlos Correa": {"birth_date": "1994-09-22", "jersey": 4, "team": "Twins", "position": "SS"},
    "Jeremy Pena": {"birth_date": "1997-09-22", "jersey": 3, "team": "Astros", "position": "SS"},
    "CJ Abrams": {"birth_date": "2000-10-03", "jersey": 5, "team": "Nationals", "position": "SS"},
}

# =============================================================================
# NHL PLAYERS (Key forwards, defensemen, goalies)
# =============================================================================

NHL_PLAYERS: Dict[str, Dict[str, Any]] = {
    # Superstars
    "Connor McDavid": {"birth_date": "1997-01-13", "jersey": 97, "team": "Oilers", "position": "C"},
    "Nathan MacKinnon": {"birth_date": "1995-09-01", "jersey": 29, "team": "Avalanche", "position": "C"},
    "Auston Matthews": {"birth_date": "1997-09-17", "jersey": 34, "team": "Maple Leafs", "position": "C"},
    "Leon Draisaitl": {"birth_date": "1995-10-27", "jersey": 29, "team": "Oilers", "position": "C"},
    "Cale Makar": {"birth_date": "1998-10-30", "jersey": 8, "team": "Avalanche", "position": "D"},
    "David Pastrnak": {"birth_date": "1996-05-25", "jersey": 88, "team": "Bruins", "position": "RW"},
    "Nikita Kucherov": {"birth_date": "1993-06-17", "jersey": 86, "team": "Lightning", "position": "RW"},
    "Kirill Kaprizov": {"birth_date": "1997-04-26", "jersey": 97, "team": "Wild", "position": "LW"},

    # More Forwards
    "Sidney Crosby": {"birth_date": "1987-08-07", "jersey": 87, "team": "Penguins", "position": "C"},
    "Alex Ovechkin": {"birth_date": "1985-09-17", "jersey": 8, "team": "Capitals", "position": "LW"},
    "Mitch Marner": {"birth_date": "1997-05-05", "jersey": 16, "team": "Maple Leafs", "position": "RW"},
    "Matthew Tkachuk": {"birth_date": "1997-12-11", "jersey": 19, "team": "Panthers", "position": "LW"},
    "Jack Hughes": {"birth_date": "2001-05-14", "jersey": 86, "team": "Devils", "position": "C"},
    "Aleksander Barkov": {"birth_date": "1995-09-02", "jersey": 16, "team": "Panthers", "position": "C"},
    "Mikko Rantanen": {"birth_date": "1996-10-29", "jersey": 96, "team": "Avalanche", "position": "RW"},
    "Tim Stutzle": {"birth_date": "2002-01-15", "jersey": 18, "team": "Senators", "position": "C"},
    "Trevor Zegras": {"birth_date": "2001-03-20", "jersey": 11, "team": "Ducks", "position": "C"},
    "Cole Caufield": {"birth_date": "2001-01-02", "jersey": 22, "team": "Canadiens", "position": "RW"},
    "Jason Robertson": {"birth_date": "1999-07-22", "jersey": 21, "team": "Stars", "position": "LW"},
    "Jack Eichel": {"birth_date": "1996-10-28", "jersey": 9, "team": "Golden Knights", "position": "C"},
    "Tage Thompson": {"birth_date": "1997-10-30", "jersey": 72, "team": "Sabres", "position": "C"},
    "Dylan Larkin": {"birth_date": "1996-07-30", "jersey": 71, "team": "Red Wings", "position": "C"},
    "Sebastian Aho": {"birth_date": "1997-07-26", "jersey": 20, "team": "Hurricanes", "position": "C"},
    "Brayden Point": {"birth_date": "1996-03-13", "jersey": 21, "team": "Lightning", "position": "C"},
    "William Nylander": {"birth_date": "1996-05-01", "jersey": 88, "team": "Maple Leafs", "position": "RW"},
    "Elias Pettersson": {"birth_date": "1998-11-12", "jersey": 40, "team": "Canucks", "position": "C"},
    "Roope Hintz": {"birth_date": "1996-11-17", "jersey": 24, "team": "Stars", "position": "C"},
    "Brady Tkachuk": {"birth_date": "1999-09-16", "jersey": 7, "team": "Senators", "position": "LW"},
    "Artemi Panarin": {"birth_date": "1991-10-30", "jersey": 10, "team": "Rangers", "position": "LW"},
    "Mika Zibanejad": {"birth_date": "1993-04-18", "jersey": 93, "team": "Rangers", "position": "C"},
    "Evgeni Malkin": {"birth_date": "1986-07-31", "jersey": 71, "team": "Penguins", "position": "C"},
    "Kyle Connor": {"birth_date": "1996-12-09", "jersey": 81, "team": "Jets", "position": "LW"},
    "Mark Scheifele": {"birth_date": "1993-03-15", "jersey": 55, "team": "Jets", "position": "C"},
    "J.T. Miller": {"birth_date": "1993-03-14", "jersey": 9, "team": "Canucks", "position": "C"},
    "Brock Boeser": {"birth_date": "1997-02-25", "jersey": 6, "team": "Canucks", "position": "RW"},
    "Andrei Svechnikov": {"birth_date": "2000-03-26", "jersey": 37, "team": "Hurricanes", "position": "RW"},
    "Seth Jarvis": {"birth_date": "2002-02-01", "jersey": 24, "team": "Hurricanes", "position": "RW"},
    "Clayton Keller": {"birth_date": "1998-07-29", "jersey": 9, "team": "Coyotes", "position": "C"},
    "Dylan Cozens": {"birth_date": "2001-02-09", "jersey": 24, "team": "Sabres", "position": "C"},
    "Matty Beniers": {"birth_date": "2002-11-05", "jersey": 10, "team": "Kraken", "position": "C"},

    # Defensemen
    "Adam Fox": {"birth_date": "1998-02-17", "jersey": 23, "team": "Rangers", "position": "D"},
    "Quinn Hughes": {"birth_date": "1999-10-14", "jersey": 43, "team": "Canucks", "position": "D"},
    "Rasmus Dahlin": {"birth_date": "2000-04-13", "jersey": 26, "team": "Sabres", "position": "D"},
    "Miro Heiskanen": {"birth_date": "1999-07-18", "jersey": 4, "team": "Stars", "position": "D"},
    "Charlie McAvoy": {"birth_date": "1997-12-21", "jersey": 73, "team": "Bruins", "position": "D"},
    "Moritz Seider": {"birth_date": "2001-04-06", "jersey": 53, "team": "Red Wings", "position": "D"},
    "Roman Josi": {"birth_date": "1990-06-01", "jersey": 59, "team": "Predators", "position": "D"},
    "Victor Hedman": {"birth_date": "1990-12-18", "jersey": 77, "team": "Lightning", "position": "D"},

    # Goalies
    "Igor Shesterkin": {"birth_date": "1995-12-30", "jersey": 31, "team": "Rangers", "position": "G"},
    "Connor Hellebuyck": {"birth_date": "1993-05-19", "jersey": 37, "team": "Jets", "position": "G"},
    "Ilya Sorokin": {"birth_date": "1995-08-04", "jersey": 30, "team": "Islanders", "position": "G"},
    "Andrei Vasilevskiy": {"birth_date": "1994-07-25", "jersey": 88, "team": "Lightning", "position": "G"},
    "Jake Oettinger": {"birth_date": "1998-12-18", "jersey": 29, "team": "Stars", "position": "G"},
    "Juuse Saros": {"birth_date": "1995-04-19", "jersey": 74, "team": "Predators", "position": "G"},
    "Stuart Skinner": {"birth_date": "1998-11-01", "jersey": 74, "team": "Oilers", "position": "G"},
    "Sergei Bobrovsky": {"birth_date": "1988-09-20", "jersey": 72, "team": "Panthers", "position": "G"},
}

# =============================================================================
# NCAAB PLAYERS (Top college players - rotate annually)
# =============================================================================

NCAAB_PLAYERS: Dict[str, Dict[str, Any]] = {
    # 2024-25 Top Prospects/Players
    "Cooper Flagg": {"birth_date": "2006-12-21", "jersey": 2, "team": "Duke", "position": "F"},
    "Dylan Harper": {"birth_date": "2006-03-04", "jersey": 2, "team": "Rutgers", "position": "G"},
    "Ace Bailey": {"birth_date": "2005-06-13", "jersey": 5, "team": "Rutgers", "position": "F"},
    "VJ Edgecombe": {"birth_date": "2005-05-08", "jersey": 3, "team": "Baylor", "position": "G"},
    "Tre Johnson": {"birth_date": "2005-11-22", "jersey": 1, "team": "Texas", "position": "G"},
    "Kasparas Jakucionis": {"birth_date": "2005-05-23", "jersey": 3, "team": "Illinois", "position": "G"},
    "Kon Knueppel": {"birth_date": "2005-02-14", "jersey": 5, "team": "Duke", "position": "G"},
    "Ian Jackson": {"birth_date": "2005-09-17", "jersey": 24, "team": "North Carolina", "position": "G"},

    # Returning Stars
    "Hunter Dickinson": {"birth_date": "2000-12-27", "jersey": 1, "team": "Kansas", "position": "C"},
    "Mark Sears": {"birth_date": "2001-06-10", "jersey": 1, "team": "Alabama", "position": "G"},
    "Johnell Davis": {"birth_date": "2001-10-05", "jersey": 1, "team": "Arkansas", "position": "G"},
    "Ryan Dunn": {"birth_date": "2003-03-10", "jersey": 13, "team": "Virginia", "position": "F"},
    "RJ Davis": {"birth_date": "2001-02-07", "jersey": 4, "team": "North Carolina", "position": "G"},
    "Tyler Kolek": {"birth_date": "2001-11-19", "jersey": 11, "team": "Marquette", "position": "G"},
}

# =============================================================================
# COMBINED PLAYER DATABASE
# =============================================================================

def get_all_players() -> Dict[str, Dict[str, Any]]:
    """Get all players from all sports combined."""
    all_players = {}
    all_players.update(NBA_PLAYERS)
    all_players.update(NFL_PLAYERS)
    all_players.update(MLB_PLAYERS)
    all_players.update(NHL_PLAYERS)
    all_players.update(NCAAB_PLAYERS)
    return all_players


def get_players_by_sport(sport: str) -> Dict[str, Dict[str, Any]]:
    """Get players for a specific sport."""
    sport = sport.upper()
    if sport == "NBA":
        return NBA_PLAYERS
    elif sport == "NFL":
        return NFL_PLAYERS
    elif sport == "MLB":
        return MLB_PLAYERS
    elif sport == "NHL":
        return NHL_PLAYERS
    elif sport == "NCAAB":
        return NCAAB_PLAYERS
    else:
        return {}


def get_player_data(player_name: str) -> Dict[str, Any]:
    """
    Look up player data by name.
    Returns None if player not found.
    """
    all_players = get_all_players()

    # Exact match
    if player_name in all_players:
        return all_players[player_name]

    # Case-insensitive match
    player_lower = player_name.lower()
    for name, data in all_players.items():
        if name.lower() == player_lower:
            return data

    # Partial match (last name)
    for name, data in all_players.items():
        if player_lower in name.lower() or name.lower().endswith(player_lower):
            return data

    return None


# Statistics
PLAYER_COUNTS = {
    "NBA": len(NBA_PLAYERS),
    "NFL": len(NFL_PLAYERS),
    "MLB": len(MLB_PLAYERS),
    "NHL": len(NHL_PLAYERS),
    "NCAAB": len(NCAAB_PLAYERS),
    "TOTAL": len(get_all_players()),
}
