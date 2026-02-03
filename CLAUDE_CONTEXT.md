# Quick Task Reference

## Current Problem: Zero Picks
Symptom: 5000+ props analyzed, 0 returned

## Debug Steps
1. Check threshold filter (line 3540)
2. Check esoteric scoring (lines 2352-2435)
3. Check magnitude calculation for props

## Likely Fix
File: live_data_router.py
Find: _eso_magnitude = abs(spread)
Change to use prop_line for props

## Quick Commands
# Check filtered count
curl "URL/live/best-bets/nba?debug=1" | jq '.debug.filtered_below_6_5_total'

# Check esoteric range  
curl "URL/live/best-bets/nba?debug=1" | jq '[.props.picks[].esoteric_score] | min, max'
