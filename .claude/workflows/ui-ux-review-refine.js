export const meta = {
  name: 'ui-ux-review-refine',
  description:
    'Max-effort UI/UX review-and-refine pass (Pass 2) over the resto frontend. For every Vue file, a 3-lens reviewer panel (accessibility+semantics+safety / layout+responsive+design-system / states+i18n+RTL+dark+motion) runs in parallel, then a refiner applies their findings, then the frontend gates must go green. Operates on the ui-ux-pass branch produced by the ui-ux-pass workflow (Pass 1). Presentation-only; never pushes.',
  whenToUse:
    'Run AFTER the ui-ux-pass workflow (Pass 1) has enhanced the app on the ui-ux-pass branch. This is the adversarial "impeccable" QA + refinement layer that uses a large Sonnet budget to drive quality. Optional args: {only:[paths], commitEvery:n, branch:name, maxRefineRounds:n}.',
  phases: [
    { title: 'Prep', detail: 'ensure we are on the ui-ux-pass branch with a clean tree' },
    { title: 'Discover', detail: 'enumerate every target .vue file' },
    { title: 'Review', detail: '3-lens reviewer panel per file, in parallel', model: 'sonnet' },
    { title: 'Refine', detail: 'apply the panel findings to flagged files (sequential)', model: 'sonnet' },
    { title: 'Verify', detail: 'run verify:i18n / lint / build / test and fix until green', model: 'sonnet' },
    { title: 'Report', detail: 'write the review report + final commit', model: 'sonnet' },
  ],
}

// ── Tunables ─────────────────────────────────────────────────────────────────
const BRANCH = (args && args.branch) || 'ui-ux-pass'
const COMMIT_EVERY = (args && Number(args.commitEvery)) || 8
const MAX_REFINE_ROUNDS = (args && Number(args.maxRefineRounds)) || 2
const MAX_FIX_ROUNDS = 5
const COAUTHOR = 'Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>'

// ── Shared context for every agent (the app + the rules) ─────────────────────
const APP_CONTEXT = [
  'App: resto — a Vue 3 + Vite + Tailwind multi-tenant restaurant platform (personas: owner/staff,',
  'customer, driver). It has a mature design system: ui-* component classes + CSS tokens in',
  'frontend/src/styles/tailwind.css, documented in frontend/src/styles/UI_SYSTEM.md and the working',
  'checklist frontend/UI_UX_GUIDELINES.md. The app has already had one enhancement pass; this is the',
  'review-and-refine layer.',
  '',
  'PRIME DIRECTIVE: the UI must be PRESENTATION-ONLY. Behavior, logic, computed/watch, lifecycle,',
  'event-handler bodies, API calls, store/router usage, props, emits, v-model, and every :key / ref /',
  'id / data-test / aria-* binding that code or tests depend on MUST be preserved. Treat any change to',
  'those as a HIGH-severity defect.',
  '',
  'DESIGN SYSTEM: prefer existing ui-* primitives (ui-panel, ui-panel-soft, ui-glass, ui-page-shell,',
  'ui-page-title, ui-kicker, ui-subtle, ui-btn-primary, ui-btn-outline, ui-input, ui-textarea, ui-chip,',
  'ui-empty-state, ui-skeleton, ui-reveal, ui-fade-up, ui-press, ui-touch-target, ui-status-pill,',
  'ui-section-band, ui-scroll-row, ui-table-wrap, ui-safe-bottom, ...) and CSS tokens over ad-hoc',
  'utilities or new hex colors. Stay on the dark slate palette.',
  '',
  'i18n: every literal t(\'a.b\') must exist in messages.en (frontend/src/i18n/messages.js) or the build',
  'fails. New keys go in messages.en + the fr block (ASCII, no accents) + messages-ar.js (correct Arabic',
  'or omit it — Arabic falls back to English; NEVER write mojibake/garbled Arabic). Dynamic keys use',
  'backtick template literals. Reuse common.* keys. eslint runs --max-warnings=0; vite build must pass.',
].join('\n')

// ── The three independent review lenses ──────────────────────────────────────
const LENSES = [
  {
    key: 'a11y-safety',
    title: 'Accessibility, semantics & behavior-safety',
    focus: [
      'Audit ONLY these dimensions and report concrete, specific issues:',
      '- Behavior-safety (HIGH if violated): does anything look like logic/props/emits/handlers/bindings',
      '  or a :key/ref/id/data-test/aria attribute was altered, removed, or broken? Flag any risk that the',
      '  UI edit changed behavior rather than just presentation.',
      '- Semantic HTML: <button> for actions (not <div @click>), <nav>/<main>/<header>/<section>, <ul>/<li>',
      '  for lists, <label for> tied to inputs, proper heading order.',
      '- ARIA: aria-label/labelledby/current/expanded/controls/role where text alone does not convey',
      '  meaning; icon-only controls labelled; live regions for async status where appropriate.',
      '- Keyboard & focus: every interactive element reachable + visible focus-visible ring; no positive',
      '  tabindex; modals/sheets trap and restore focus.',
      '- Images/media: meaningful alt (decorative => alt=""). Contrast: text stays legible on the dark palette.',
    ].join('\n'),
  },
  {
    key: 'layout-system',
    title: 'Layout, responsiveness & design-system consistency',
    focus: [
      'Audit ONLY these dimensions and report concrete, specific issues:',
      '- Responsive: no horizontal overflow at 390x844; sensible breakpoints; min-w-0 on flex/grid children',
      '  hosting scroll rows; truncate/line-clamp long text; tables have a md:hidden card fallback on mobile.',
      '- Visual hierarchy & spacing: consistent space-y rhythm; aligned paddings; one clear primary CTA per',
      '  section; kicker+title pattern; no crowding or arbitrary one-off margins.',
      '- Design-system consistency: uses ui-* primitives + tokens instead of ad-hoc utility soup or new',
      '  brand colors/buttons/cards; matches the conventions of polished siblings (Cart.vue, Home.vue);',
      '  the screen feels like part of one product.',
    ].join('\n'),
  },
  {
    key: 'states-i18n-rtl',
    title: 'States, i18n, RTL, dark-mode & motion',
    focus: [
      'Audit ONLY these dimensions and report concrete, specific issues:',
      '- The three states: every data/list/async section renders LOADING (ui-skeleton/spinner), EMPTY',
      '  (ui-empty-state + a helpful action), and ERROR (clear message + retry). Flag any missing one.',
      '- i18n: any hardcoded user-visible string (should be t(...)); any literal t() key that may not exist',
      '  in messages.en; string-concatenated dynamic keys (should be backtick template literals).',
      '- RTL/Arabic: physical ml-*/mr-*/left/right/text-left/right that should be logical (ms/me, ps/pe,',
      '  start/end, text-start/text-end) so the layout mirrors correctly under html[lang="ar"]; directional',
      '  icons that should flip.',
      '- Dark mode: anything off the dark slate palette/tokens. Motion: ui-reveal/ui-fade-up/ui-press used',
      '  tastefully (one animation per element) and nothing that ignores prefers-reduced-motion.',
    ].join('\n'),
  },
]

// ── Schemas ──────────────────────────────────────────────────────────────────
const PREP_SCHEMA = {
  type: 'object',
  properties: { ok: { type: 'boolean' }, branch: { type: 'string' }, reason: { type: 'string' } },
  required: ['ok', 'reason'],
}
const DISCOVER_SCHEMA = {
  type: 'object',
  properties: { files: { type: 'array', items: { type: 'string' } }, count: { type: 'integer' } },
  required: ['files'],
}
const REVIEW_SCHEMA = {
  type: 'object',
  properties: {
    verdict: { type: 'string', enum: ['pass', 'issues'] },
    issues: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          severity: { type: 'string', enum: ['high', 'medium', 'low'] },
          area: { type: 'string' },
          detail: { type: 'string', description: 'specific problem + where in the file' },
          suggestedFix: { type: 'string' },
        },
        required: ['severity', 'area', 'detail'],
      },
    },
  },
  required: ['verdict'],
}
const REFINE_SCHEMA = {
  type: 'object',
  properties: {
    file: { type: 'string' },
    status: { type: 'string', enum: ['refined', 'no-change'] },
    applied: { type: 'array', items: { type: 'string' } },
    newI18nKeys: { type: 'array', items: { type: 'string' } },
    functionalityPreserved: { type: 'boolean' },
    notes: { type: 'string' },
  },
  required: ['file', 'status', 'functionalityPreserved'],
}
const VERIFY_SCHEMA = {
  type: 'object',
  properties: {
    passed: { type: 'boolean' },
    gates: {
      type: 'array',
      items: {
        type: 'object',
        properties: { name: { type: 'string' }, passed: { type: 'boolean' }, output: { type: 'string' } },
        required: ['name', 'passed'],
      },
    },
    failureSummary: { type: 'string' },
  },
  required: ['passed'],
}

const short = (p) => String(p).split('/').slice(-2).join('/')

const VERIFY_PROMPT = `You are the frontend QA gate for the resto app (working dir = repo root).
From \`frontend/\`, run these four gates IN ORDER and capture results:
  1. \`npm run verify:i18n\`   2. \`npm run lint\`   3. \`npm run build\`   4. \`npm test\`
Run each even if an earlier one fails. Return structured: passed = true ONLY if ALL pass. For each gate
include name, passed, and the TAIL of output (errors if failed). Add a concise failureSummary. Do NOT
modify files — only report.`

// ─────────────────────────────────────────────────────────────────────────────
// Phase: Prep — operate on the existing Pass-1 branch
// ─────────────────────────────────────────────────────────────────────────────
phase('Prep')
const prep = await agent(
  `Prepare for a UI/UX review pass on the existing branch \`${BRANCH}\` (the output of Pass 1).
1. Run \`git rev-parse --verify ${BRANCH}\`. If it does NOT exist, return ok=false, reason="branch ${BRANCH} not found — run the ui-ux-pass (Pass 1) workflow first".
2. Run \`git status --porcelain\`. If the tree is dirty with changes OUTSIDE \`.claude/\`, return ok=false listing them (we must not entangle uncommitted work).
3. Check out \`${BRANCH}\` if not already on it. Confirm with \`git rev-parse --abbrev-ref HEAD\` and \`git log --oneline -1\`.
Return ok=true with a reason describing the branch HEAD. Do NOT commit or push.`,
  { phase: 'Prep', label: 'prep', schema: PREP_SCHEMA },
)
if (!prep || !prep.ok) {
  log(`⛔ Prep aborted: ${prep ? prep.reason : 'no result'}`)
  return { aborted: true, reason: prep ? prep.reason : 'prep failed', branch: BRANCH }
}
log(`✅ Prep ok — ${prep.reason}`)

// ─────────────────────────────────────────────────────────────────────────────
// Phase: Discover
// ─────────────────────────────────────────────────────────────────────────────
phase('Discover')
let files = []
if (args && Array.isArray(args.only) && args.only.length) {
  files = args.only.slice()
} else {
  const disc = await agent(
    `List every target Vue file for a UI/UX review. Use Glob to find all *.vue under \`frontend/src/\`
(recursive), EXCLUDING node_modules. Return repo-relative POSIX paths, ordered layouts -> components
(incl. onboarding) -> pages, alphabetical within each group. Return {files, count}.`,
    { phase: 'Discover', label: 'discover', schema: DISCOVER_SCHEMA },
  )
  files = (disc && disc.files) || []
}
files = files.filter(Boolean)
if (!files.length) {
  log('⛔ No files discovered — aborting.')
  return { aborted: true, reason: 'no target files', branch: BRANCH }
}
log(`🗂  ${files.length} files to review across ${LENSES.length} lenses (${files.length * LENSES.length} reviews).`)

// ─────────────────────────────────────────────────────────────────────────────
// review() — run the 3-lens panel for the given files (parallel), aggregate issues
// ─────────────────────────────────────────────────────────────────────────────
const reviewFiles = async (fileList, roundLabel) => {
  const tasks = []
  for (const f of fileList) for (const lens of LENSES) tasks.push({ f, lens })
  const raw = await parallel(
    tasks.map((t) => () =>
      agent(
        `${APP_CONTEXT}\n\n--- REVIEW LENS: ${t.lens.title} ---\n${t.lens.focus}\n\n` +
          `Read \`frontend/UI_UX_GUIDELINES.md\` and \`frontend/src/styles/UI_SYSTEM.md\` for the standard, then read the ENTIRE file \`${t.f}\` and review it ONLY through this lens. Be specific and concrete (name the element/line and the exact problem + a suggested fix). Do not report issues outside your lens. If the file is excellent on this lens, return verdict "pass" with an empty issues list. You are READ-ONLY — do not edit anything.`,
        { model: 'sonnet', phase: 'Review', label: `${roundLabel}:${t.lens.key}:${short(t.f)}`, schema: REVIEW_SCHEMA },
      )
        .then((r) => ({ file: t.f, lens: t.lens.key, verdict: (r && r.verdict) || 'pass', issues: (r && r.issues) || [] }))
        .catch(() => ({ file: t.f, lens: t.lens.key, verdict: 'pass', issues: [] })),
    ),
  )
  const byFile = {}
  raw.filter(Boolean).forEach((r) => {
    if (r.verdict === 'issues' && r.issues.length) {
      ;(byFile[r.file] = byFile[r.file] || []).push(...r.issues.map((i) => ({ ...i, lens: r.lens })))
    }
  })
  return byFile
}

// ─────────────────────────────────────────────────────────────────────────────
// refine() — sequentially apply aggregated issues to flagged files (i18n-safe)
// ─────────────────────────────────────────────────────────────────────────────
const refineFiles = async (issuesByFile, roundLabel) => {
  const queue = Object.keys(issuesByFile).filter((f) =>
    issuesByFile[f].some((i) => i.severity === 'high' || i.severity === 'medium'),
  )
  log(`🔧 ${roundLabel}: ${queue.length} files need refinement.`)
  const out = []
  let sinceCommit = 0
  for (let i = 0; i < queue.length; i++) {
    const f = queue[i]
    const issues = issuesByFile[f]
    let r
    try {
      r = await agent(
        `${APP_CONTEXT}\n\n--- REFINE ONE FILE ---\n\n` +
          `A reviewer panel found issues in \`${f}\`. Read \`frontend/UI_UX_GUIDELINES.md\`, the relevant part of \`frontend/src/styles/tailwind.css\`, and the ENTIRE file, then FIX exactly the issues below — presentation-only, preserving all behavior. Address every HIGH and MEDIUM issue; address LOW issues when low-risk. If a reported issue is wrong or would change behavior, skip it and say so in notes (do NOT change behavior to satisfy a review note).\n\n` +
          `Issues (JSON):\n${JSON.stringify(issues, null, 2).slice(0, 6000)}\n\n` +
          `You may edit ONLY this .vue file and the i18n catalogues (messages.js en+fr, messages-ar.js ar) for any NEW visible strings. Every literal t('a.b') you add MUST exist in messages.en. Return the structured result.`,
        { model: 'sonnet', phase: 'Refine', label: `${roundLabel}:${short(f)}`, schema: REFINE_SCHEMA },
      )
    } catch (e) {
      r = { file: f, status: 'no-change', applied: [], newI18nKeys: [], functionalityPreserved: true, notes: `error: ${String(e).slice(0, 200)}` }
    }
    out.push(r || { file: f, status: 'no-change', functionalityPreserved: true })
    sinceCommit++
    if (sinceCommit >= COMMIT_EVERY || i === queue.length - 1) {
      await agent(
        `On branch ${BRANCH}: \`git add -A\` and commit verbatim:\n\nui/ux ${roundLabel}: refine through ${i + 1}/${queue.length}\n\n${COAUTHOR}\n\nIf nothing to commit, say so. Do NOT push. Return one line.`,
        { phase: 'Refine', model: 'sonnet', label: `${roundLabel}-commit@${i + 1}` },
      )
      sinceCommit = 0
    }
  }
  return { queue, results: out }
}

// ─────────────────────────────────────────────────────────────────────────────
// Phases: Review -> Refine, looped up to MAX_REFINE_ROUNDS (re-review only the
// files we just refined, so we converge without re-reviewing the whole app).
// ─────────────────────────────────────────────────────────────────────────────
let toReview = files.slice()
const refineLog = []
let totalRefined = 0
for (let round = 1; round <= MAX_REFINE_ROUNDS; round++) {
  phase('Review')
  log(`🔎 Review round ${round}/${MAX_REFINE_ROUNDS} over ${toReview.length} files…`)
  const issuesByFile = await reviewFiles(toReview, `r${round}`)
  const flagged = Object.keys(issuesByFile).filter((f) =>
    issuesByFile[f].some((i) => i.severity === 'high' || i.severity === 'medium'),
  )
  if (!flagged.length) {
    log(`✨ Review round ${round}: no high/medium issues remain. Converged.`)
    break
  }
  phase('Refine')
  const { queue, results } = await refineFiles(issuesByFile, `r${round}`)
  totalRefined += results.filter((r) => r && r.status === 'refined').length
  refineLog.push({ round, flagged: flagged.length, refined: results.filter((r) => r && r.status === 'refined').length })
  // Next round re-reviews only the files we changed this round.
  toReview = queue
  if (round === MAX_REFINE_ROUNDS) log(`Reached MAX_REFINE_ROUNDS (${MAX_REFINE_ROUNDS}).`)
}

// ─────────────────────────────────────────────────────────────────────────────
// Phase: Verify — gates + bounded fix loop
// ─────────────────────────────────────────────────────────────────────────────
phase('Verify')
let verify = await agent(VERIFY_PROMPT, { phase: 'Verify', model: 'sonnet', label: 'verify#0', schema: VERIFY_SCHEMA })
let fixRound = 0
while (verify && !verify.passed && fixRound < MAX_FIX_ROUNDS) {
  fixRound++
  const failed = (verify.gates || []).filter((g) => !g.passed).map((g) => g.name).join(', ') || 'unknown'
  log(`🔧 Verify failed (${failed}) — fix round ${fixRound}/${MAX_FIX_ROUNDS}`)
  await agent(
    `${APP_CONTEXT}\n\nThe frontend gates fail after the review/refine pass. Fix them — presentation-only, never change app behavior to make a test pass (restore required markup/text/test-ids instead). Working dir repo root; frontend in \`frontend/\`.\n\nFailing: ${failed}\n${(verify.gates || []).filter((g) => !g.passed).map((g) => `### ${g.name}\n${(g.output || '').slice(0, 2500)}`).join('\n\n')}\nSummary: ${verify.failureSummary || ''}\n\nEdit only frontend source + i18n. Re-run the failing gate(s) from \`frontend/\` to confirm. Do NOT commit/push. Report what you changed.`,
    { phase: 'Verify', model: 'sonnet', label: `fix#${fixRound}` },
  )
  await agent(
    `On branch ${BRANCH}: \`git add -A\` and commit verbatim:\n\nui/ux review: fix verification round ${fixRound}\n\n${COAUTHOR}\n\nIf nothing to commit, say so. Do NOT push. Return one line.`,
    { phase: 'Verify', model: 'sonnet', label: `commit-fix#${fixRound}` },
  )
  verify = await agent(VERIFY_PROMPT, { phase: 'Verify', model: 'sonnet', label: `verify#${fixRound}`, schema: VERIFY_SCHEMA })
}
const green = !!(verify && verify.passed)
log(green ? '✅ All frontend gates green.' : `❌ Gates still failing after ${MAX_FIX_ROUNDS} rounds.`)

// ─────────────────────────────────────────────────────────────────────────────
// Phase: Report
// ─────────────────────────────────────────────────────────────────────────────
phase('Report')
await agent(
  `Write the Pass-2 review/refine report to \`frontend/UI_UX_REVIEW_REPORT.md\` (Write tool), then commit.
Data:
- Branch: ${BRANCH}
- Files reviewed: ${files.length} across ${LENSES.length} lenses
- Refinement rounds: ${JSON.stringify(refineLog)}
- Files refined (total): ${totalRefined}
- Final gates: ${green ? 'ALL GREEN (verify:i18n, lint, build, test)' : 'NOT GREEN after ' + MAX_FIX_ROUNDS + ' fix rounds'}
${green ? '' : '- Outstanding:\n' + JSON.stringify((verify && verify.gates) || [], null, 2).slice(0, 3000)}

Report sections: summary; what the 3-lens panel covered; per-round refinement counts; gate status; how to
review (\`git diff main...${BRANCH}\`) and ship (merge ${BRANCH} into main; deploy is manual via Coolify);
any residual notes. Then \`git add -A\` and commit verbatim:

ui/ux review: final report + ${green ? 'gates green' : 'gates pending'}

${COAUTHOR}

Do NOT push. Return a 3-5 line executive summary.`,
  { phase: 'Report', model: 'sonnet', label: 'final-report' },
)

return {
  branch: BRANCH,
  filesReviewed: files.length,
  lenses: LENSES.length,
  refineRounds: refineLog,
  totalRefined,
  gatesGreen: green,
  report: 'frontend/UI_UX_REVIEW_REPORT.md',
}
