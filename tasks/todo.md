# Todo - AI Betting Backend

> Plan tracking: Current and upcoming work

---

## Status: FROZEN (As of Jan 29, 2026)

The backend is production-ready and frozen. Only modify for:
- Critical production bugs
- Security vulnerabilities
- Explicit user requests

---

## Maintenance Tasks

### Monitoring
- [ ] Check `/live/api-usage` for quota warnings
- [ ] Review `/internal/storage/health` periodically
- [ ] Monitor grader status via `/live/grader/status`

### Daily Operations
- [ ] Grading runs at 5:00 AM ET (automatic)
- [ ] Audit runs at 6:30 AM ET (automatic)
- [ ] Props fetches at 10 AM, 12 PM, 2 PM, 6 PM ET (automatic)

---

## If Unfreezing for Changes

Before making ANY changes:

1. [ ] Read `CLAUDE.md` fully
2. [ ] Check `tasks/lessons.md` for past mistakes
3. [ ] Verify production health endpoints
4. [ ] Run `scripts/prod_sanity_check.sh`
5. [ ] Get explicit user approval

After making changes:

1. [ ] Run full test suite: `pytest`
2. [ ] Run sanity check: `scripts/prod_sanity_check.sh`
3. [ ] Verify filter_date matches et_date
4. [ ] Push and verify Railway deployment
5. [ ] Document any new lessons in `tasks/lessons.md`

---

## Known Technical Debt

*Reviewed Feb 4, 2026 - all items resolved or N/A*

- [x] ~~Consolidate duplicate Titanium logic~~ - **N/A**: Already consolidated. `tiering.check_titanium_rule()` calls `core/titanium.evaluate_titanium()`.
- [x] ~~Clean up legacy files in `services/`~~ - **N/A**: Both files (`officials_tracker.py`, `ml_data_pipeline.py`) are actively used in v18.x production.
- [x] Remove deprecated `new_endpoints.py` - **DONE**: Deleted Feb 4, 2026 (~370 lines of dead code removed)

---

## Integration Health Checklist

Run quarterly or after major changes:

- [ ] Odds API quota healthy (< 75% used)
- [ ] Playbook API connectivity verified
- [ ] BallDontLie API key valid
- [ ] Railway storage mountpoint verified
- [ ] Redis cache connected
- [ ] All 14 integrations showing VALIDATED/CONFIGURED

---

## Template: Adding Tasks

```markdown
### [Task Title]
**Priority:** High/Medium/Low
**Status:** Not Started / In Progress / Blocked / Done
**Depends on:** [Other tasks if any]

Description of what needs to be done.

**Acceptance criteria:**
- [ ] Criterion 1
- [ ] Criterion 2
```
