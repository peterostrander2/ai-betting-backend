# Weekly Maintenance Checklist

## Overview
Follow this schedule to keep the ai-betting-backend codebase clean and healthy.

---

## Monday: Health Check

- [ ] Run daily health check
  ```bash
  ./scripts/daily_health_check.sh
  ```
- [ ] Review any issues flagged
- [ ] Check for new TODOs added last week
- [ ] Verify all tests pass
  ```bash
  pytest tests/ -v --tb=short
  ```

---

## Tuesday: Cleanup

- [ ] Run auto cleanup (dry run first)
  ```bash
  ./scripts/auto_cleanup.sh --dry-run
  ./scripts/auto_cleanup.sh
  ```
- [ ] Review large files (>100KB)
- [ ] Archive or remove stale artifacts in `artifacts/`
- [ ] Clean up any temporary branches
  ```bash
  git branch --merged | grep -v main | xargs -r git branch -d
  ```

---

## Wednesday: Dependencies

- [ ] Check for outdated packages
  ```bash
  pip list --outdated
  ```
- [ ] Review `requirements.txt` for unused deps
- [ ] Check for security advisories
  ```bash
  pip-audit 2>/dev/null || echo "Install: pip install pip-audit"
  ```
- [ ] Update minor versions if safe

---

## Thursday: Tests

- [ ] Run full test suite
  ```bash
  pytest tests/ -v
  ```
- [ ] Check test coverage
  ```bash
  pytest tests/ --cov=. --cov-report=term-missing
  ```
- [ ] Review any skipped or xfail tests
- [ ] Add tests for new code from this week

---

## Friday: Documentation Review

- [ ] Update CLAUDE.md if architecture changed
- [ ] Review and update README.md
- [ ] Check that API docs match implementation
- [ ] Run docs contract scan
  ```bash
  ./scripts/docs_contract_scan.sh
  ```
- [ ] Update PROJECT_MAP.md
  ```bash
  ./scripts/generate_project_map.sh
  ```

---

## Quick Reference

### Daily (2 min)
```bash
cd ~/ai-betting-backend
./scripts/daily_health_check.sh
```

### Before Each Commit
```bash
pytest tests/ -v --tb=short
./scripts/ci_sanity_check.sh
```

### Before Deploy
```bash
./scripts/prod_go_nogo.sh
./scripts/prod_sanity_check.sh
```

---

## Automation

These tasks are already automated:
- Pre-commit hooks: `./scripts/install_git_hooks.sh`
- CI sanity: Runs on every push
- Daily sanity: `./scripts/daily_sanity_report.sh`

To enable pre-commit hooks:
```bash
./scripts/install_git_hooks.sh
```

---

## Issue Triage

If health check finds issues:

| Issue Type | Action |
|------------|--------|
| Duplicate functions | Refactor or rename |
| Large files (>100KB) | Split into modules |
| Missing `__init__.py` | Add empty init file |
| Stale TODOs | Address or remove |
| Failing tests | Fix before merging |

---

Last updated: February 2025
