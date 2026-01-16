# Claude Code Handoff — React + Next.js Best Practices (Vercel)

You are working inside this repository.
Default goal: ship correct, fast, and maintainable React/Next.js code with minimal bundle size and minimal client-side JS.

## 1) Always follow the Vercel React Best Practices skill
This repo includes (or should include) the Vercel agent skill:
`.claude/skills/react-best-practices/SKILL.md`

When editing any React/Next.js code, you MUST apply that skill's rules.
If the skill is missing, instruct to install it with:
`npx add-skill vercel-labs/agent-skills`

## 2) Decision rules (hard rules)
### Server vs Client
- Default to **Server Components** in Next.js App Router.
- Only use `"use client"` when needed (event handlers, state, browser APIs, refs).
- If adding `"use client"`, justify it in a short comment or PR note.

### Data fetching
- Prefer server-side data fetching (RSC) and keep waterfalls out of the client.
- Avoid fetch chains inside `useEffect`. If it must exist, explain why and minimize.

### Performance + bundle size
- Do not import large libraries into client components unless unavoidable.
- Prefer dynamic import for heavy/rare UI.
- Avoid re-render traps:
  - Memoize expensive computations (`useMemo`)
  - Stabilize handlers (`useCallback`) only when it prevents real rerenders
  - Avoid creating new objects/arrays inline in hot paths

### Rendering correctness
- No state derived from props unless necessary (prefer computed values).
- Avoid unnecessary `useEffect`. Prefer direct rendering from state/props.
- Keep components small and focused.

### Styling/UI
- Keep UI consistent with existing design system.
- Don't introduce a new UI library without explicit request.

## 3) When you code, ALWAYS do this checklist
Before final output:
- [ ] Can this be a Server Component instead of Client?
- [ ] Did I accidentally add `"use client"` to a whole page/layout unnecessarily?
- [ ] Any avoidable `useEffect` data fetching?
- [ ] Any waterfall risks (client fetch after render)?
- [ ] Any obvious rerender causes (inline objects, unstable props)?
- [ ] Any heavy deps pulled into client bundle?
- [ ] Error/loading states handled where needed?
- [ ] Types correct (TypeScript) and no `any` unless unavoidable?

## 4) Output format expectations
When making code changes:
1) Give a brief "what changed + why" summary.
2) Provide the minimal diff or full updated files.
3) Call out any tradeoffs (perf vs complexity).

## 5) Safe defaults for Next.js App Router
- Prefer `app/` routing patterns
- Prefer `next/image` for images
- Prefer server actions / route handlers where applicable
- Keep API keys server-only (never in client code)

## 6) If user asks for a performance pass
Do a strict audit and propose fixes in this priority:
1) Remove unnecessary client components
2) Remove client-side fetch waterfalls
3) Reduce client bundle size
4) Fix rerenders / memoization
5) Improve caching strategy
