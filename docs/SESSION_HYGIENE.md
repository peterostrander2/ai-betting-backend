# Session Hygiene Guide

How to prevent Claude Code context limit errors.

## Problem

Claude Code has a context window limit. When you hit it:
```
Context limit reached · /compact or /clear to continue
```

This interrupts work and requires manual intervention.

## Prevention Strategy

### 1. Commit Frequently (Every 30-60 Minutes)

**Bad:** One giant session, 200 file changes, 5 hours
**Good:** Checkpoint commits every hour
```bash
# Quick checkpoint
./scripts/checkpoint_commit.sh
```

### 2. Use Checkpoints Between Tasks

After completing each discrete task:
```bash
git add -A
git commit -m "feat: completed X"
# Tell Claude: "committed, continue"
```

This frees context window.

### 3. Recognize Warning Signs

When Claude Code starts showing these, checkpoint immediately:
- "Conversation compacted" messages
- Slower responses
- Repeated file reads
- Large diffs in output

### 4. Split Large Refactors

**Bad:** "Refactor entire codebase"
**Good:**
- Session 1: Refactor module A
- Commit, push
- Session 2: Refactor module B
- Commit, push

### 5. Use /compact Command

In Claude Code, when you see warning signs:
```
/compact
```

This compresses context without losing state.

## Optimal Session Pattern
```
[Start session]
├─ Read SESSION_START.md
├─ Work on Task 1 (30-60 min)
├─ Checkpoint commit
├─ /compact (optional)
├─ Work on Task 2 (30-60 min)
├─ Final commit
└─ [End session]
```

## Emergency Recovery

If you hit context limit mid-work:

1. **Save current state:**
```bash
   ./scripts/checkpoint_commit.sh
```

2. **In Claude Code, use:**
```
   /compact
```

3. **Continue with:**
   "Read the checkpoint commit and continue from there"

## Checkpoint vs Final Commits

**Checkpoint commits:**
- Quick WIP saves
- Can be rebased/squashed later
- Free up context window
- Message format: `checkpoint: YYYY-MM-DD HH:MM`

**Final commits:**
- Follow conventional commits
- Include tests/docs
- Follow COMMIT_CHECKLIST.md
- Message format: `feat: description`

## Git Workflow
```bash
# During session - checkpoint frequently
./scripts/checkpoint_commit.sh

# At end of session - clean up
git rebase -i HEAD~5  # Squash checkpoints if needed
git push origin main
```

## Claude Code Specific Tips

1. **Don't show large files repeatedly**
   - Cache file contents in session
   - Use `view` instead of re-reading

2. **Avoid massive diffs**
   - Checkpoint before large refactors
   - Split across multiple commits

3. **Clear between unrelated tasks**
```
   /clear
```
   Then start fresh with SESSION_START.md

## Automation Helpers
```bash
# Quick checkpoint (no push)
./scripts/checkpoint_commit.sh

# Full commit with validation
# (follow COMMIT_CHECKLIST.md)

# Health check before long session
./scripts/daily_health_check.sh
```

## Summary

**Prevent context limits by:**
- Checkpoint commits every 30-60 min
- /compact when you see warning signs
- Split large refactors across sessions
- Use checkpoint script liberally
- Don't try to do everything in one session
