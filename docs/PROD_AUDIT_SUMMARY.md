# Production Audit Summary — Option A / Best-Bets / Live Betting

Date: 2026-02-03

## Executive Summary

- **Scoring contract**: Option A only (4-engine base + bounded context modifier). Guard tests exist.
- **Boosts**: confluence/MSRF/Jason/SERP/ensemble documented and enforced in math checks.
- **Learning loop**: persistence checks + thresholds enforced (local/offline checks available).
- **Live betting**: endpoints are filters over best-bets; live adjustment is explicit and bounded. Odds staleness guard still flagged in learning audit report.
- **Env drift**: strict scan implemented; must be run to validate all env vars are documented.

## Pass/Fail Matrix (This Run)

| Check | Status | Notes |
|---|---|---|
| `scripts/docs_contract_scan.sh` | PASS | Option A docs + caps aligned |
| `scripts/env_drift_scan.sh` | PASS | Env mapping strict scan |
| `scripts/endpoint_matrix_sanity.sh` | SKIPPED | `SKIP_NETWORK=1` |
| `scripts/api_proof_check.sh` | SKIPPED | `SKIP_NETWORK=1` |
| `scripts/learning_loop_sanity.sh` | PASS | Local/offline check via `prod_go_nogo` |
| `python3 -m pytest -q` | NOT RUN | Targeted tests executed (Option A guards) |

**Targeted tests run:**
- `python3 -m pytest -q tests/test_option_a_scoring_guard.py tests/test_scoring_single_source.py`

## Required Artifacts

Artifacts are written by `scripts/prod_go_nogo.sh` into `artifacts/` using ET date stamps:
- `artifacts/prod_go_nogo_<YYYYMMDD>_ET.txt`
- `artifacts/env_drift_<YYYYMMDD>_ET.txt`
- `artifacts/docs_contract_<YYYYMMDD>_ET.txt`
- `artifacts/endpoint_matrix_<YYYYMMDD>_ET.json`
- `artifacts/learning_sanity_<YYYYMMDD>_ET.json`

## Commands to Run

```
./scripts/prod_go_nogo.sh
./scripts/env_drift_scan.sh
./scripts/endpoint_matrix_sanity.sh
./scripts/learning_loop_sanity.sh
```

## References
- `docs/ENDPOINT_CONTRACT.md` — endpoint + payload contract
- `CLAUDE.md` — Option A invariants and non-negotiable adjustment rule
- `docs/LEARNING_AUDIT_REPORT.md` — learning loop + live betting audit
