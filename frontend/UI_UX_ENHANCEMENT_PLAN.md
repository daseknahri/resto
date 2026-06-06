# UI/UX Enhancement Pass — Plan

> **Goal:** a complete, app-wide UI/UX polish of the `resto` Vue frontend — every page,
> layout, and component brought up to one consistent, accessible, mobile-first, RTL- and
> i18n-correct standard — **without changing any behavior.** Built to run **unattended for
> hours** on Sonnet via a multi-agent workflow.

This plan is paired with two committed, reusable artifacts:

- **`.claude/agents/ui-ux-pro-max.md`** — the "UI/UX pro max" expert agent (senior product
  designer + senior Vue/Tailwind engineer). Pinned to **Sonnet**. Restricted tools
  (`Read, Edit, Grep, Glob`) so an unattended run cannot wander.
- **`.claude/workflows/ui-ux-pass.js`** — the runnable, long-running workflow that drives the
  whole pass: safe branch → distilled guidelines → sequential per-file enhancement →
  verify-and-fix loop → report.

---

## Why a refinement pass (not a redesign)

The app already has a **mature, intentional design system**: ~95 `ui-*` component classes in
`src/styles/tailwind.css`, CSS design tokens (`--color-*`, `--motion-*`, `--ease-fluid`,
safe-area insets), a dark-first palette, RTL/Arabic handling, and a documented contract in
`src/styles/UI_SYSTEM.md`. Polished screens (e.g. `Cart.vue`, `Home.vue`) already show the
house style.

So the highest-value work is **consistency + completeness + polish**, applied uniformly:
- Use the existing primitives everywhere (kill ad-hoc utility soup and one-off colors).
- Fill the gaps: missing loading / empty / error states, weak mobile layouts, missing ARIA,
  RTL slips, un-internationalized strings.
- Raise the finish: spacing rhythm, visual hierarchy, tasteful reduced-motion-safe motion.

**We refine and complete the system. We never reinvent it, and we never change behavior.**

---

## The prime directive (safety)

Presentation changes only. The per-file agent must **never** touch `<script>` logic, computed
values, watchers, props, emits, `v-model`, event-handler bodies, API calls, store/router usage,
or any business logic — and must preserve every binding, `:key`, `ref`, `id`, and `data-test`
attribute that other code or tests depend on. If a file is already excellent, it makes minimal
tweaks or none and reports `already-good`.

Edit surface per file: the **one target `.vue` file** + the i18n catalogues (only to register
new visible strings). Nothing else.

---

## Per-file enhancement checklist

Each file is enhanced against this checklist (full version in the agent + the generated
`UI_UX_GUIDELINES.md`):

1. **Responsive / overflow** — no horizontal scroll at 390×844; breakpoints; `min-w-0` on
   scroll-row parents; `truncate`/`line-clamp`; tables get a mobile card fallback.
2. **Visual hierarchy & spacing** — one primary CTA per section; consistent `space-y-*` rhythm;
   `ui-kicker` + title pattern; grouped controls.
3. **Accessibility** — semantic elements, `aria-*` where text doesn't convey meaning, icon-only
   buttons labelled, meaningful `alt`, visible `focus-visible` rings, adequate contrast.
4. **The three states** — every data section renders **loading** (`ui-skeleton`/spinner),
   **empty** (`ui-empty-state` + helpful action), and **error** (clear, with retry).
5. **Motion** — tasteful `ui-reveal`/`ui-fade-up`/`ui-press`; one animation per element; all of
   it degrades under `prefers-reduced-motion` (handled centrally by the primitives).
6. **Dark mode & RTL** — stay on the dark palette + tokens; logical spacing (`ms/me/ps/pe`,
   `start/end`, `text-start/end`) so Arabic mirrors correctly; no hardcoded left/right.
7. **i18n safety** — no hardcoded visible strings; every literal `t('a.b')` exists in
   `messages.en`; add `en`+`fr` (ASCII, matching the existing accent-free entries) + Arabic in
   `messages-ar.js` (omit Arabic rather than risk mojibake — English auto-falls-back). Reuse
   `common.*`. Dynamic keys use backtick template literals.
8. **Consistency** — align each file with its siblings and the system so the app reads as one
   product.

---

## Workflow phases (`.claude/workflows/ui-ux-pass.js`)

| Phase | What it does | Parallelism |
|------|---------------|-------------|
| **Prep** | Guards a **clean working tree** (aborts if dirty so it never mixes in your uncommitted work), then creates/checks out branch **`ui-ux-pass`**. Never pushes. | 1 agent |
| **Discover** | Enumerates every target `.vue` under `src/` (layouts → components → pages), or uses `args.only`. | 1 agent |
| **Guidelines** | Reads `UI_SYSTEM.md` + `tailwind.css` + exemplar pages and writes **`frontend/UI_UX_GUIDELINES.md`** — the distilled checklist + true `ui-*` catalog every worker follows. | 1 agent |
| **Enhance** | **Sequential** loop: one `ui-ux-pro-max` agent per file (Sonnet, structured output). **Checkpoint commit every 8 files** so multi-hour progress is never lost. | **Sequential by design** |
| **Verify** | Runs `verify:i18n` → `lint` → `build` → `test`. If red, a fixer agent repairs (presentation-only), commits, and re-checks — **up to 5 rounds**. | 1 agent/round |
| **Report** | Writes **`frontend/UI_UX_PASS_REPORT.md`** (per-file results, files to review first, how to ship) + a final commit. | 1 agent |

### Why the Enhance phase is sequential (not fanned out)
`messages.js` and `messages-ar.js` are **shared-write surfaces** — every file that adds an i18n
key edits them. Parallel agents would race and corrupt those files. The design system also
prizes correctness over speed here, and you have effectively unlimited Sonnet tokens and time,
so **sequential is the deliberate, bulletproof choice** for an unattended run. Read-only and
verification work is the only place concurrency would help, and there's no write contention to
win there. Net effect: the pass takes **hours** (exactly the intent) and cannot self-corrupt.

### Runs on Sonnet, by whoever launches it
Every worker/verify/fix/report agent is pinned to **`model: 'sonnet'`** in the workflow, and the
agent persona itself is pinned to Sonnet. So the heavy, hours-long work runs on your maxed-out
Sonnet tokens **whether you launch it or I do** — the orchestration overhead is negligible.

---

## Safety & recovery

- **Branch-isolated.** All work lands on `ui-ux-pass`; `main` is untouched. **Nothing is ever
  pushed** — you review locally, then merge when happy.
- **Clean-tree guard.** Aborts immediately if you have uncommitted work, so it can't entangle
  with yours.
- **Checkpoint commits** every 8 files + after each fix round → a crash at file 70 keeps 1–69.
- **Resumable.** Re-running is idempotent (branch is reused); the Workflow engine can also
  resume an interrupted run (`resumeFromRunId`) so the unchanged prefix is cached.
- **Gate-enforced.** The pass isn't "done" until `verify:i18n`, `lint` (`--max-warnings=0`),
  `build`, and `test` (vitest 75) are all green, or it reports exactly what remains.
- **Honest reporting.** Any file the agent couldn't guarantee behavior-safe is flagged
  `FUNCTIONALITY-FLAG` in the report's "review first" section.

---

## Scope (target surface)

~94 Vue files: **53 pages** (`src/pages`), **30 components** (`src/components`, incl.
onboarding/wizard), **4 layouts** (`src/layouts`). Backend is untouched — this is a pure
frontend pass, so only the frontend gates run.

---

## How to run it

### Option A — you run it on Sonnet (recommended; matches your token setup)
1. Switch the session model to **Sonnet 4.6**.
2. Ensure the working tree is clean (commit/stash anything in progress).
3. Launch the workflow:
   > "Run the **ui-ux-pass** workflow."
   (or invoke the `ui-ux-pass` workflow directly). Leave it running — it self-paces for hours,
   commits checkpoints, and writes the report when done.

### Option B — I launch it now
I trigger the `ui-ux-pass` workflow from here. Because the workers are pinned to Sonnet, the
expensive work still runs on Sonnet regardless of the session model.

### Optional arguments
- `only: ["frontend/src/pages/Cart.vue", …]` — restrict to a subset (great for a pilot run).
- `commitEvery: 8` — checkpoint commit cadence.
- `branch: "ui-ux-pass"` — target branch name.
- `skipBranch: true` — operate on the current branch (advanced; skips the clean-tree guard).

### After it finishes
```
git log --oneline ui-ux-pass            # the checkpoint + fix + report commits
git diff main...ui-ux-pass              # the full visual diff to review
```
Read `frontend/UI_UX_PASS_REPORT.md` (start with the "review first" section), spot-check the
flagged files, then **merge `ui-ux-pass` into `main`** when satisfied. Deploy stays **manual
via Coolify**.

---

## Deliverables produced by the pass
- Enhanced `.vue` files across the whole frontend (on `ui-ux-pass`).
- `frontend/UI_UX_GUIDELINES.md` — the distilled, reusable checklist + `ui-*` catalog.
- `frontend/UI_UX_PASS_REPORT.md` — per-file results, review list, ship instructions.
- Green frontend gates (or an explicit list of what remains).

---

## Pilot first (suggested)
Before the full multi-hour run, do a **pilot** on a handful of varied screens to confirm the
output quality matches your taste:
> Run **ui-ux-pass** with `only: ["frontend/src/layouts/CustomerLayout.vue",
> "frontend/src/pages/Home.vue", "frontend/src/pages/OwnerOrders.vue",
> "frontend/src/components/DishCard.vue"]`.

Review that small diff, tune the agent/guidelines if needed, then run the full pass.
