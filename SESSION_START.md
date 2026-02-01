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

## Common tasks

- If data looks like demo/fallback, verify `ODDS_API_KEY` and `PLAYBOOK_API_KEY` in the backend environment.
- Auth gating uses `API_AUTH_ENABLED` + `API_AUTH_KEY`.
