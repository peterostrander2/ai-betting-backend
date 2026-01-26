"""
Name Normalizer - Standardizes player and team names for matching

Rules:
- Lowercase
- Remove punctuation
- Remove accents
- Collapse whitespace
- Drop suffixes: jr/sr/ii/iii/iv
"""

import re
import unicodedata
from typing import Optional

# Suffixes to remove (case-insensitive)
PLAYER_SUFFIXES = [
    r'\s+jr\.?$',
    r'\s+sr\.?$',
    r'\s+iv$',
    r'\s+iii$',
    r'\s+ii$',
    r'\s+i$',
    r'\s+v$',
]

# Common nickname mappings
NICKNAME_MAP = {
    'lebron': 'lebron james',
    'lbj': 'lebron james',
    'kd': 'kevin durant',
    'steph': 'stephen curry',
    'steph curry': 'stephen curry',
    'giannis': 'giannis antetokounmpo',
    'greek freak': 'giannis antetokounmpo',
    'ad': 'anthony davis',
    'cp3': 'chris paul',
    'pg': 'paul george',
    'pg13': 'paul george',
    'dame': 'damian lillard',
    'ant': 'anthony edwards',
    'ant man': 'anthony edwards',
    'ja': 'ja morant',
    'trae': 'trae young',
    'ice trae': 'trae young',
    'luka': 'luka doncic',
    'embiid': 'joel embiid',
    'jokic': 'nikola jokic',
    'joker': 'nikola jokic',
    'kawhi': 'kawhi leonard',
    'kyrie': 'kyrie irving',
    'zion': 'zion williamson',
    'lamelo': 'lamelo ball',
    'melo': 'carmelo anthony',
    'dbook': 'devin booker',
    'book': 'devin booker',
    'cade': 'cade cunningham',
    'scottie': 'scottie barnes',
    'jalen': 'jalen brunson',  # Context-dependent, may need team hint
    'tyrese': 'tyrese haliburton',  # Context-dependent
    'sga': 'shai gilgeous-alexander',
    'pat bev': 'patrick beverley',
    'dray': 'draymond green',
    'klay': 'klay thompson',
    'jimmy': 'jimmy butler',
    'jimmy buckets': 'jimmy butler',
    'bam': 'bam adebayo',
    'dejounte': 'dejounte murray',
    'mikal': 'mikal bridges',
    'franz': 'franz wagner',
    'paolo': 'paolo banchero',
    'wemby': 'victor wembanyama',
    'wembanyama': 'victor wembanyama',
}

# Team name standardization
TEAM_ALIASES = {
    # NBA
    'lakers': 'los angeles lakers',
    'la lakers': 'los angeles lakers',
    'lal': 'los angeles lakers',
    'clippers': 'los angeles clippers',
    'la clippers': 'los angeles clippers',
    'lac': 'los angeles clippers',
    'warriors': 'golden state warriors',
    'gsw': 'golden state warriors',
    'dubs': 'golden state warriors',
    'celtics': 'boston celtics',
    'bos': 'boston celtics',
    'heat': 'miami heat',
    'mia': 'miami heat',
    'knicks': 'new york knicks',
    'nyk': 'new york knicks',
    'nets': 'brooklyn nets',
    'bkn': 'brooklyn nets',
    'sixers': 'philadelphia 76ers',
    '76ers': 'philadelphia 76ers',
    'phi': 'philadelphia 76ers',
    'bulls': 'chicago bulls',
    'chi': 'chicago bulls',
    'cavs': 'cleveland cavaliers',
    'cavaliers': 'cleveland cavaliers',
    'cle': 'cleveland cavaliers',
    'pistons': 'detroit pistons',
    'det': 'detroit pistons',
    'pacers': 'indiana pacers',
    'ind': 'indiana pacers',
    'bucks': 'milwaukee bucks',
    'mil': 'milwaukee bucks',
    'hawks': 'atlanta hawks',
    'atl': 'atlanta hawks',
    'hornets': 'charlotte hornets',
    'cha': 'charlotte hornets',
    'magic': 'orlando magic',
    'orl': 'orlando magic',
    'wizards': 'washington wizards',
    'was': 'washington wizards',
    'wiz': 'washington wizards',
    'raptors': 'toronto raptors',
    'tor': 'toronto raptors',
    'mavs': 'dallas mavericks',
    'mavericks': 'dallas mavericks',
    'dal': 'dallas mavericks',
    'rockets': 'houston rockets',
    'hou': 'houston rockets',
    'grizzlies': 'memphis grizzlies',
    'mem': 'memphis grizzlies',
    'pelicans': 'new orleans pelicans',
    'pels': 'new orleans pelicans',
    'nop': 'new orleans pelicans',
    'spurs': 'san antonio spurs',
    'sas': 'san antonio spurs',
    'nuggets': 'denver nuggets',
    'den': 'denver nuggets',
    'timberwolves': 'minnesota timberwolves',
    'wolves': 'minnesota timberwolves',
    'min': 'minnesota timberwolves',
    'thunder': 'oklahoma city thunder',
    'okc': 'oklahoma city thunder',
    'blazers': 'portland trail blazers',
    'trail blazers': 'portland trail blazers',
    'por': 'portland trail blazers',
    'jazz': 'utah jazz',
    'uta': 'utah jazz',
    'suns': 'phoenix suns',
    'phx': 'phoenix suns',
    'kings': 'sacramento kings',
    'sac': 'sacramento kings',

    # NFL (common ones)
    'chiefs': 'kansas city chiefs',
    'kc': 'kansas city chiefs',
    'eagles': 'philadelphia eagles',
    'pats': 'new england patriots',
    'patriots': 'new england patriots',
    'niners': 'san francisco 49ers',
    '49ers': 'san francisco 49ers',
    'pack': 'green bay packers',
    'packers': 'green bay packers',
    'cowboys': 'dallas cowboys',
    'boys': 'dallas cowboys',
    'bills': 'buffalo bills',
    'ravens': 'baltimore ravens',
    'bengals': 'cincinnati bengals',
    'steelers': 'pittsburgh steelers',
    'lions': 'detroit lions',
    'bears': 'chicago bears',
    'vikings': 'minnesota vikings',
    'saints': 'new orleans saints',
    'bucs': 'tampa bay buccaneers',
    'buccaneers': 'tampa bay buccaneers',
    'falcons': 'atlanta falcons',
    'panthers': 'carolina panthers',
    'seahawks': 'seattle seahawks',
    'hawks': 'seattle seahawks',  # Context needed vs Atlanta
    'rams': 'los angeles rams',
    'la rams': 'los angeles rams',
    'cardinals': 'arizona cardinals',
    'cards': 'arizona cardinals',
    'broncos': 'denver broncos',
    'raiders': 'las vegas raiders',
    'chargers': 'los angeles chargers',
    'la chargers': 'los angeles chargers',
    'dolphins': 'miami dolphins',
    'fins': 'miami dolphins',
    'jets': 'new york jets',
    'giants': 'new york giants',
    'jags': 'jacksonville jaguars',
    'jaguars': 'jacksonville jaguars',
    'texans': 'houston texans',
    'titans': 'tennessee titans',
    'colts': 'indianapolis colts',
    'browns': 'cleveland browns',
    'commanders': 'washington commanders',

    # MLB (common ones)
    'yankees': 'new york yankees',
    'nyy': 'new york yankees',
    'red sox': 'boston red sox',
    'sox': 'boston red sox',  # Context needed
    'dodgers': 'los angeles dodgers',
    'lad': 'los angeles dodgers',
    'mets': 'new york mets',
    'nym': 'new york mets',
    'braves': 'atlanta braves',
    'phillies': 'philadelphia phillies',
    'astros': 'houston astros',
    'padres': 'san diego padres',
    'cubs': 'chicago cubs',
    'white sox': 'chicago white sox',
    'chw': 'chicago white sox',
    'mariners': 'seattle mariners',
    'guardians': 'cleveland guardians',
    'twins': 'minnesota twins',
    'royals': 'kansas city royals',
    'rangers': 'texas rangers',
    'angels': 'los angeles angels',
    'laa': 'los angeles angels',
    'athletics': 'oakland athletics',
    'as': 'oakland athletics',
    'blue jays': 'toronto blue jays',
    'jays': 'toronto blue jays',
    'orioles': 'baltimore orioles',
    'rays': 'tampa bay rays',
    'marlins': 'miami marlins',
    'nationals': 'washington nationals',
    'nats': 'washington nationals',
    'reds': 'cincinnati reds',
    'pirates': 'pittsburgh pirates',
    'brewers': 'milwaukee brewers',
    'cardinals': 'st louis cardinals',
    'cards': 'st louis cardinals',  # Context needed
    'rockies': 'colorado rockies',
    'diamondbacks': 'arizona diamondbacks',
    'dbacks': 'arizona diamondbacks',

    # NHL (common ones)
    'bruins': 'boston bruins',
    'canadiens': 'montreal canadiens',
    'habs': 'montreal canadiens',
    'maple leafs': 'toronto maple leafs',
    'leafs': 'toronto maple leafs',
    'red wings': 'detroit red wings',
    'wings': 'detroit red wings',
    'blackhawks': 'chicago blackhawks',
    'penguins': 'pittsburgh penguins',
    'pens': 'pittsburgh penguins',
    'flyers': 'philadelphia flyers',
    'capitals': 'washington capitals',
    'caps': 'washington capitals',
    'islanders': 'new york islanders',
    'isles': 'new york islanders',
    'nyi': 'new york islanders',
    'rangers': 'new york rangers',
    'nyr': 'new york rangers',
    'devils': 'new jersey devils',
    'sabres': 'buffalo sabres',
    'hurricanes': 'carolina hurricanes',
    'canes': 'carolina hurricanes',
    'lightning': 'tampa bay lightning',
    'bolts': 'tampa bay lightning',
    'panthers': 'florida panthers',  # Context needed vs Carolina
    'blue jackets': 'columbus blue jackets',
    'cbj': 'columbus blue jackets',
    'predators': 'nashville predators',
    'preds': 'nashville predators',
    'wild': 'minnesota wild',
    'jets': 'winnipeg jets',  # Context needed vs NY
    'avalanche': 'colorado avalanche',
    'avs': 'colorado avalanche',
    'stars': 'dallas stars',
    'blues': 'st louis blues',
    'oilers': 'edmonton oilers',
    'flames': 'calgary flames',
    'canucks': 'vancouver canucks',
    'kraken': 'seattle kraken',
    'golden knights': 'vegas golden knights',
    'vgk': 'vegas golden knights',
    'knights': 'vegas golden knights',
    'coyotes': 'arizona coyotes',
    'yotes': 'arizona coyotes',
    'ducks': 'anaheim ducks',
    'sharks': 'san jose sharks',
    'senators': 'ottawa senators',
    'sens': 'ottawa senators',
}


def remove_accents(text: str) -> str:
    """Remove accents/diacritics from text."""
    # Normalize to decomposed form (NFD), then filter out combining chars
    normalized = unicodedata.normalize('NFD', text)
    return ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')


def normalize_player_name(raw_name: str, expand_nicknames: bool = True) -> str:
    """
    Normalize a player name for matching.

    Rules:
    - Lowercase
    - Remove accents
    - Remove punctuation
    - Collapse whitespace
    - Drop suffixes (Jr., Sr., II, III, IV)
    - Optionally expand common nicknames

    Returns:
        Normalized name string
    """
    if not raw_name:
        return ""

    # Lowercase
    name = raw_name.lower().strip()

    # Remove accents
    name = remove_accents(name)

    # Remove punctuation (except spaces and hyphens initially)
    name = re.sub(r"[^\w\s\-]", "", name)

    # Convert hyphens to spaces for consistent matching
    name = name.replace("-", " ")

    # Remove suffixes
    for suffix_pattern in PLAYER_SUFFIXES:
        name = re.sub(suffix_pattern, "", name, flags=re.IGNORECASE)

    # Collapse whitespace
    name = " ".join(name.split())

    # Expand nicknames if enabled
    if expand_nicknames and name in NICKNAME_MAP:
        name = NICKNAME_MAP[name]

    return name


def normalize_team_name(raw_team: str) -> str:
    """
    Normalize a team name for matching.

    Returns:
        Normalized team name string
    """
    if not raw_team:
        return ""

    # Lowercase
    team = raw_team.lower().strip()

    # Remove accents
    team = remove_accents(team)

    # Remove punctuation
    team = re.sub(r"[^\w\s]", "", team)

    # Collapse whitespace
    team = " ".join(team.split())

    # Check aliases
    if team in TEAM_ALIASES:
        team = TEAM_ALIASES[team]

    return team


def get_name_variants(name: str) -> list[str]:
    """
    Generate common variants of a player name for fuzzy matching.

    Returns:
        List of possible name variants
    """
    normalized = normalize_player_name(name, expand_nicknames=False)
    variants = [normalized]

    parts = normalized.split()
    if len(parts) >= 2:
        # First initial + last name: "L James"
        variants.append(f"{parts[0][0]} {parts[-1]}")

        # First name + last initial: "LeBron J"
        variants.append(f"{parts[0]} {parts[-1][0]}")

        # Last name only
        variants.append(parts[-1])

        # First name only
        variants.append(parts[0])

        # Reversed: "James LeBron"
        if len(parts) == 2:
            variants.append(f"{parts[1]} {parts[0]}")

    return list(set(variants))


def calculate_name_similarity(name1: str, name2: str) -> float:
    """
    Calculate similarity score between two names (0.0 to 1.0).

    Uses a combination of:
    - Exact match
    - Variant matching
    - Character-level similarity (Jaccard on character bigrams)
    """
    n1 = normalize_player_name(name1)
    n2 = normalize_player_name(name2)

    # Exact match
    if n1 == n2:
        return 1.0

    # Check if one is a variant of the other
    v1 = set(get_name_variants(name1))
    v2 = set(get_name_variants(name2))

    if n1 in v2 or n2 in v1:
        return 0.95

    if v1 & v2:  # Any overlap in variants
        return 0.85

    # Character bigram similarity (Jaccard)
    def get_bigrams(s: str) -> set:
        s = s.replace(" ", "")
        return set(s[i:i+2] for i in range(len(s) - 1)) if len(s) > 1 else {s}

    b1 = get_bigrams(n1)
    b2 = get_bigrams(n2)

    if not b1 or not b2:
        return 0.0

    intersection = len(b1 & b2)
    union = len(b1 | b2)

    return intersection / union if union > 0 else 0.0


def extract_last_name(name: str) -> str:
    """Extract the last name from a full name."""
    normalized = normalize_player_name(name, expand_nicknames=False)
    parts = normalized.split()
    return parts[-1] if parts else ""


def extract_first_name(name: str) -> str:
    """Extract the first name from a full name."""
    normalized = normalize_player_name(name, expand_nicknames=False)
    parts = normalized.split()
    return parts[0] if parts else ""
