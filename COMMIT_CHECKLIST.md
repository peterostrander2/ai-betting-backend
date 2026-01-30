# Commit Checklist - Follow EVERY Time

## Before You Push ANY Fix:

### 1. ✅ Fix the Code
- [ ] Made the code change
- [ ] Tested locally (if possible)

### 2. ✅ Update Documentation (CRITICAL - DON'T SKIP)
- [ ] Does this change an **INVARIANT**? → Update CLAUDE.md
- [ ] Does this change **how scoring works**? → Update SCORING_LOGIC.md
- [ ] Does this add a **new file/module**? → Update PROJECT_MAP.md
- [ ] Does this change **API endpoints**? → Update CLAUDE.md API section

### 3. ✅ Commit BOTH Together
```bash
git add <code_files>
git add <doc_files>
git commit -m "fix: description + docs: update invariants"
git push origin main
```

### 4. ✅ Verify on Railway
- [ ] Check Railway logs (no errors)
- [ ] Run health check: `curl https://web-production-7b2a.up.railway.app/health`

---

## Common Mistakes (DON'T DO THESE):

❌ **Fix code, forget docs** → Next session, bug comes back
❌ **Update docs, forget code** → Docs lie, system broken
❌ **Commit separately** → Code and docs out of sync

✅ **ALWAYS commit code + docs together**

---

## Quick Reference: What Goes Where

| Change Type | Update These Files |
|-------------|-------------------|
| ET window, storage paths, titanium rule | CLAUDE.md (Master Invariants) |
| Scoring algorithm, engine weights | SCORING_LOGIC.md |
| New file/module added | PROJECT_MAP.md |
| API endpoint added/changed | CLAUDE.md (API section) |
| Bug fix (no invariant change) | Code only (no doc update needed) |

---

## Example: ET Window Fix

**Bad Way (What You've Been Doing):**
```bash
# Fix core/time_et.py
git commit -m "fix: ET window"
git push
# Docs still say 00:00:00 → bug comes back next session
```

**Good Way (Do This Instead):**
```bash
# 1. Fix core/time_et.py (00:01:00)
# 2. Update CLAUDE.md INVARIANT 4 (00:01:00)
git add core/time_et.py CLAUDE.md
git commit -m "fix: ET window 00:01:00 + docs: update INVARIANT 4"
git push origin main
# Code and docs match → bug NEVER comes back
```

---

## TL;DR (Too Long; Didn't Read)

**ONE RULE:** Code and docs MUST match. Update both. Commit together. Forever.

Print this file. Put it next to your computer. Follow it every time.
