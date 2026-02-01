# Backend Recovery Guide

## 1) Sample/fallback data

Symptoms:
- Responses contain sample teams or `source: "fallback"`

Fix:
- Set `ODDS_API_KEY` and `PLAYBOOK_API_KEY` in the backend environment
- Restart the backend service

## 2) Auth errors (401/403)

Fix:
- Ensure `API_AUTH_ENABLED=true` only when `API_AUTH_KEY` is set
- Confirm the client is sending `X-API-Key`

## 3) Cache / Redis issues

Fix:
- If `REDIS_URL` not set, backend uses in-memory cache
- If Redis is set but unavailable, remove `REDIS_URL` or fix Redis connection

## 4) Persistence not working

Fix:
- Ensure `RAILWAY_VOLUME_MOUNT_PATH` (or `GRADER_MOUNT_ROOT`) is set for persistent storage
- Verify that the grader data directory is writable

## 5) Startup failures

Fix:
- Check startup validation logs in `integration_registry.py`
- Run `./scripts/ci_sanity_check.sh` locally to pinpoint failing session checks
