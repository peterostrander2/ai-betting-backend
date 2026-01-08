# new_endpoints.py - Add these endpoints to your FastAPI backend
# Copy the imports to your main.py and add the routes

from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date
import hashlib
import random

# ============================================
# MODELS
# ============================================

class VoteRequest(BaseModel):
    side: str  # "home", "away", "over", "under"

class VoteResponse(BaseModel):
    game_vote_id: str
    home: int
    away: int
    over: int
    under: int
    total: int
    userVote: Optional[str]

class SharpSignal(BaseModel):
    game: str
    sport: str
    side: str
    line: float
    book: str
    divergence: float
    direction: str
    strength: str
    timestamp: str

class GradedPick(BaseModel):
    id: str
    game: str
    pick: str
    result: str
    clv: float
    graded_at: str

# ============================================
# IN-MEMORY STORAGE (Replace with DB for production)
# ============================================

votes_store = {}
graded_picks_store = []

# ============================================
# HELPER FUNCTIONS
# ============================================

def get_user_id(request: Request) -> str:
    """Get user ID from IP (replace with Whop auth in production)"""
    ip = request.client.host if request.client else "anonymous"
    return hashlib.md5(ip.encode()).hexdigest()[:12]

def get_moon_phase():
    """Simple moon phase calculation"""
    phases = ["New Moon", "Waxing Crescent", "First Quarter", "Waxing Gibbous", 
              "Full Moon", "Waning Gibbous", "Last Quarter", "Waning Crescent"]
    day_of_year = datetime.now().timetuple().tm_yday
    return phases[day_of_year % 8]

def get_life_path():
    """Calculate life path number for today"""
    today = datetime.now()
    digits = str(today.year) + str(today.month).zfill(2) + str(today.day).zfill(2)
    total = sum(int(d) for d in digits)
    while total > 9:
        total = sum(int(d) for d in str(total))
    return total

def get_zodiac():
    """Get current zodiac sign"""
    today = datetime.now()
    zodiacs = [
        (120, "Capricorn"), (219, "Aquarius"), (320, "Pisces"), (420, "Aries"),
        (521, "Taurus"), (621, "Gemini"), (722, "Cancer"), (823, "Leo"),
        (923, "Virgo"), (1023, "Libra"), (1122, "Scorpio"), (1222, "Sagittarius"),
        (1231, "Capricorn")
    ]
    date_num = today.month * 100 + today.day
    for cutoff, sign in zodiacs:
        if date_num <= cutoff:
            return sign
    return "Capricorn"

# ============================================
# ENDPOINTS - Add these to your FastAPI app
# ============================================

# ----- COMMUNITY VOTING -----

@app.get("/votes/{game_vote_id}")
async def get_votes(game_vote_id: str, request: Request):
    """Get current vote counts for a game"""
    user_id = get_user_id(request)
    
    if game_vote_id not in votes_store:
        return VoteResponse(
            game_vote_id=game_vote_id,
            home=0, away=0, over=0, under=0,
            total=0, userVote=None
        )
    
    data = votes_store[game_vote_id]
    user_vote = data.get("user_votes", {}).get(user_id)
    
    return VoteResponse(
        game_vote_id=game_vote_id,
        home=data.get("home", 0),
        away=data.get("away", 0),
        over=data.get("over", 0),
        under=data.get("under", 0),
        total=sum([data.get(k, 0) for k in ["home", "away", "over", "under"]]),
        userVote=user_vote
    )

@app.post("/votes/{game_vote_id}")
async def submit_vote(game_vote_id: str, vote: VoteRequest, request: Request):
    """Submit or update a vote"""
    user_id = get_user_id(request)
    
    if vote.side not in ["home", "away", "over", "under"]:
        raise HTTPException(status_code=400, detail="Invalid vote side")
    
    if game_vote_id not in votes_store:
        votes_store[game_vote_id] = {
            "home": 0, "away": 0, "over": 0, "under": 0,
            "user_votes": {}
        }
    
    data = votes_store[game_vote_id]
    
    # Remove previous vote if exists
    if user_id in data["user_votes"]:
        old_vote = data["user_votes"][user_id]
        data[old_vote] = max(0, data[old_vote] - 1)
    
    # Add new vote
    data[vote.side] += 1
    data["user_votes"][user_id] = vote.side
    
    return VoteResponse(
        game_vote_id=game_vote_id,
        home=data["home"],
        away=data["away"],
        over=data["over"],
        under=data["under"],
        total=sum([data[k] for k in ["home", "away", "over", "under"]]),
        userVote=vote.side
    )

@app.get("/votes/leaderboard")
async def get_leaderboard():
    """Get voting leaderboard (placeholder)"""
    return {
        "weekly": [],
        "ai_record": {"correct": 0, "total": 0, "accuracy": 0}
    }

# ----- SHARP MONEY -----

@app.get("/sharp-money/{sport}")
async def get_sharp_money(sport: str):
    """Get sharp money signals for a sport"""
    # In production, this would pull from your data source
    # For now, return empty or sample data
    return {
        "signals": [],
        "sport": sport,
        "updated_at": datetime.now().isoformat()
    }

# ----- LIVE ODDS -----

@app.get("/live/odds/{sport}")
async def get_live_odds(sport: str):
    """Get live odds from multiple sportsbooks"""
    # In production, integrate with odds API (The Odds API, etc.)
    return {
        "games": [],
        "sport": sport,
        "books": ["FanDuel", "DraftKings", "BetMGM", "Caesars", "PointsBet", "BetRivers", "Barstool", "WynnBet"],
        "updated_at": datetime.now().isoformat()
    }

# ----- BETTING SPLITS -----

@app.get("/live/splits/{sport}")
async def get_splits(sport: str):
    """Get public betting percentages"""
    # In production, scrape from Action Network or similar
    return []

# ----- GRADED PICKS -----

@app.get("/grader/picks")
async def get_graded_picks():
    """Get all graded picks"""
    return graded_picks_store

@app.post("/grader/grade")
async def grade_pick(data: dict):
    """Grade a pick"""
    pick = {
        "id": data.get("pick_id", str(len(graded_picks_store))),
        "result": data.get("result"),
        "graded_at": datetime.now().isoformat()
    }
    graded_picks_store.append(pick)
    return {"success": True, "pick": pick}

# ----- ESOTERIC / TODAY ENERGY -----

@app.get("/esoteric/today-energy")
async def get_today_energy():
    """Get today's cosmic energy readings"""
    moon = get_moon_phase()
    life_path = get_life_path()
    zodiac = get_zodiac()
    
    moon_meanings = {
        "New Moon": "Fresh starts - take calculated risks",
        "Full Moon": "High volatility - expect upsets",
        "Waxing Crescent": "Building momentum - ride streaks",
        "Waning Gibbous": "Fading energy - fade public",
    }
    
    life_path_meanings = {
        1: "Leadership day - favorites strong",
        2: "Balance day - look for pushes",
        3: "Creative day - props favored",
        4: "Foundation day - unders trend",
        5: "Change day - underdogs bark",
        6: "Harmony day - home teams edge",
        7: "Spiritual day - trust the model",
        8: "Power day - big favorites cover",
        9: "Completion day - revenge games",
    }
    
    zodiac_meanings = {
        "Capricorn": "Earth energy - lean UNDERS",
        "Aquarius": "Air energy - contrarian plays",
        "Pisces": "Water energy - trust intuition",
        "Aries": "Fire energy - overs hit",
        "Taurus": "Earth energy - favorites grind",
        "Gemini": "Air energy - first half bets",
        "Cancer": "Water energy - home teams",
        "Leo": "Fire energy - star players shine",
        "Virgo": "Earth energy - unders & defense",
        "Libra": "Air energy - balanced spreads",
        "Scorpio": "Water energy - revenge spots",
        "Sagittarius": "Fire energy - overs & points",
    }
    
    return {
        "moon_phase": moon,
        "moon_meaning": moon_meanings.get(moon, "Normal energy"),
        "life_path": life_path,
        "life_path_meaning": life_path_meanings.get(life_path, "Standard day"),
        "zodiac": zodiac,
        "zodiac_meaning": zodiac_meanings.get(zodiac, "Neutral energy"),
        "date": date.today().isoformat()
    }
