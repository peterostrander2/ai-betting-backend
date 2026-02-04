# Learning Loop Audit

Date ET: 2026-02-04

## Scope
- Autograder + trap learning loop + grader_store persistence
- Railway volume paths and restart behavior
- ET-aware timestamp handling

## Storage & Persistence (Railway volume)
- Predictions (append-only JSONL): `RAILWAY_VOLUME_MOUNT_PATH/grader/predictions.jsonl`
- Weights (daily overwrite): `RAILWAY_VOLUME_MOUNT_PATH/grader_data/weights.json`
- Audit logs: `RAILWAY_VOLUME_MOUNT_PATH/grader/audits/*`

Source of truth:
- `storage_paths.py` defines all derived paths.
- `grader_store.py` writes predictions JSONL only.
- `auto_grader.py` writes weights only.

## Call Chain (grading loop)
```
/live/best-bets/* -> grader_store.persist_pick() -> predictions.jsonl
                         |
                         v
              auto_grader.AutoGrader() -> weights.json
```

## ET-Aware Time Handling
- `auto_grader.py` uses `now_et()` and normalizes `fromisoformat()` timestamps with tzinfo checks before comparisons.
- Tests ensure the ET-aware comparison pattern remains intact.

## Tests (evidence)
- `tests/test_learning_system_audit.py::test_predictions_roundtrip_survives_reload`
- `tests/test_learning_system_audit.py::test_training_ignores_picks_below_min_score`
- `tests/test_learning_system_audit.py::test_training_dedup_by_pick_id`
- `tests/test_learning_system_audit.py::test_auto_grader_uses_et_aware_comparisons`
- `tests/test_persistence_volume_path.py` (volume mount paths)

## Observability
- `/live/grader/status` (health + last run)
- `/live/grader/daily-lesson` (daily learning summary)
- `/internal/storage/health` (volume mount + write checks)

## Findings
- Persistence paths are correctly rooted under `RAILWAY_VOLUME_MOUNT_PATH`.
- Predictions are append-only; weights are write-once per run.
- ET-aware comparisons are enforced in autograder logic.

## Action Items
- None required for correctness.
