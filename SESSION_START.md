# Backend Session Start

If you are opening a new session, read these in order:

1) `docs/MASTER_INDEX.md` (system map)
2) `core/scoring_contract.py` (single source of tier/threshold truth)
3) `integration_registry.py` (env requirements and startup validation)
4) `scripts/ci_sanity_check.sh` (session checks)

## Fast checks

```bash
./scripts/ci_sanity_check.sh
```

## Daily ops checklist (best-bets readiness)

```bash
# 1) Daily sanity report (best-bets + ET-only + cache headers)
API_KEY=your_key \
API_BASE=https://web-production-7b2a.up.railway.app \
SPORTS="NBA NFL NHL MLB" \
bash scripts/daily_sanity_report.sh
```

Quick spot-check (optional):
```bash
curl -s "https://web-production-7b2a.up.railway.app/live/best-bets/NBA" \
  -H "X-API-Key: your_key" | jq '.game_picks.picks[0] | {start_time_et, rest_days, book_count, market_book_count, bet_string}'
```

## Common tasks

- If data looks like demo/fallback, verify `ODDS_API_KEY` and `PLAYBOOK_API_KEY` in the backend environment.
- Auth gating uses `API_AUTH_ENABLED` + `API_AUTH_KEY`.
