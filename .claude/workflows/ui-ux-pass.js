export const meta = {
  name: 'ui-ux-pass',
  description:
    'Full-app UI/UX enhancement pass for the resto frontend: on a safe branch, refine every Vue page/layout/component against the existing ui-* design system (responsive, a11y, states, motion, RTL, i18n) without changing behavior, then verify-and-fix until the frontend gates are green.',
  whenToUse:
    'Run when you want a thorough, unattended, hours-long UI/UX polish sweep over the whole Vue frontend. Each file is enhanced by the ui-ux-pro-max agent (pinned to Sonnet). Lands on branch ui-ux-pass with checkpoint commits for review — never pushes. Optional args: {only:[paths], commitEvery:n, branch:name, skipBranch:bool}.',
  phases: [
    { title: 'Prep', detail: 'guard clean tree + create/checkout the ui-ux-pass branch' },
    { title: 'Discover', detail: 'enumerate every target .vue file' },
    { title: 'Guidelines', detail: 'write the distilled UI/UX checklist + ui-* catalog', model: 'sonnet' },
    { title: 'Enhance', detail: 'sequential per-file enhancement (ui-ux-pro-max, Sonnet) + checkpoint commits', model: 'sonnet' },
    { title: 'Verify', detail: 'run verify:i18n / lint / build / test and fix until green', model: 'sonnet' },
    { title: 'Report', detail: 'write the pass report + final commit', model: 'sonnet' },
  ],
}

// ── Tunables (overridable via args) ──────────────────────────────────────────
const BRANCH = (args && args.branch) || 'ui-ux-pass'
const COMMIT_EVERY = (args && Number(args.commitEvery)) || 8
const MAX_FIX_ROUNDS = 5
const COAUTHOR = 'Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>'

// ── Schemas ──────────────────────────────────────────────────────────────────
const PREP_SCHEMA = {
  type: 'object',
  properties: {
    ok: { type: 'boolean', description: 'true if it is safe to proceed (branch ready)' },
    branch: { type: 'string' },
    reason: { type: 'string', description: 'why ok is false, or what was done' },
  },
  required: ['ok', 'reason'],
}

const DISCOVER_SCHEMA = {
  type: 'object',
  properties: {
    files: {
      type: 'array',
      items: { type: 'string' },
      description: 'repo-relative POSIX paths to every target .vue file',
    },
    count: { type: 'integer' },
  },
  required: ['files'],
}

const ENHANCE_SCHEMA = {
  type: 'object',
  properties: {
    file: { type: 'string' },
    status: { type: 'string', enum: ['enhanced', 'already-good', 'skipped'] },
    changes: { type: 'array', items: { type: 'string' } },
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
        properties: {
          name: { type: 'string' },
          passed: { type: 'boolean' },
          output: { type: 'string', description: 'tail of the command output' },
        },
        required: ['name', 'passed'],
      },
    },
    failureSummary: { type: 'string' },
  },
  required: ['passed'],
}

// ── Helpers ──────────────────────────────────────────────────────────────────
const short = (p) => String(p).split('/').slice(-2).join('/')

const VERIFY_PROMPT = `You are the frontend QA gate for the resto app. Working dir: the repo root.
From the \`frontend/\` directory, run these four gates IN ORDER and capture results:
  1. \`npm run verify:i18n\`   (Arabic integrity + every literal t('a.b') key exists in messages.en)
  2. \`npm run lint\`          (eslint --max-warnings=0 — zero warnings allowed)
  3. \`npm run build\`         (vite production build must succeed)
  4. \`npm test\`             (vitest — all tests must pass)
Run each even if an earlier one fails (so we see the full picture), unless a gate cannot run because a prior one left the repo unbuildable.
Return the structured result: passed = true ONLY if ALL four gates pass. For each gate include name, passed, and the TAIL of its output (the error lines if it failed; a short success line if it passed). Put a concise human-readable failureSummary of what is broken and where.
Do NOT modify any files — you are only reporting.`

// ─────────────────────────────────────────────────────────────────────────────
// Phase: Prep — guard the working tree and create/checkout the branch
// ─────────────────────────────────────────────────────────────────────────────
phase('Prep')
let prep = { ok: true, branch: BRANCH, reason: 'branch step skipped via args' }
if (!(args && args.skipBranch)) {
  prep = await agent(
    `Prepare a safe branch for an unattended UI/UX pass in the repo at the current working directory.
Steps:
1. Run \`git status --porcelain\`. If the working tree is NOT clean (any staged/unstaged/untracked changes other than files under \`.claude/\`), STOP and return ok=false with a reason listing the dirty paths — we must not mix the user's uncommitted work into this pass. (Files under \`.claude/\` are this workflow's own config and are fine to ignore/leave.)
2. If clean: ensure we are on a branch named \`${BRANCH}\`. If it already exists, check it out; otherwise create it from the current HEAD (\`git checkout -b ${BRANCH}\`).
3. Confirm with \`git rev-parse --abbrev-ref HEAD\` and \`git log --oneline -1\`.
Return ok=true with reason describing the branch state (created vs reused, base commit). Do NOT push. Do NOT commit anything.`,
    { phase: 'Prep', label: 'prep-branch', schema: PREP_SCHEMA },
  )
}
if (!prep || !prep.ok) {
  log(`⛔ Prep aborted: ${prep ? prep.reason : 'no result'}`)
  return { aborted: true, reason: prep ? prep.reason : 'prep failed', branch: BRANCH }
}
log(`✅ Prep ok — branch ${prep.branch || BRANCH}: ${prep.reason}`)

// ─────────────────────────────────────────────────────────────────────────────
// Phase: Discover — enumerate the target files (or use args.only)
// ─────────────────────────────────────────────────────────────────────────────
phase('Discover')
let files = []
if (args && Array.isArray(args.only) && args.only.length) {
  files = args.only.slice()
  log(`Using ${files.length} file(s) from args.only`)
} else {
  const disc = await agent(
    `List every target Vue single-file component for a UI/UX enhancement pass.
Use Glob to find all \`*.vue\` files under \`frontend/src/\` (recursive). EXCLUDE anything under \`node_modules\`, and EXCLUDE the i18n catalogues (\`messages.js\`, \`messages-ar.js\`, which are not .vue anyway).
Return repo-relative POSIX paths like \`frontend/src/pages/Home.vue\`.
Order them deliberately so shared building blocks are enhanced before the screens that use them:
  (1) layouts  (frontend/src/layouts/*.vue)
  (2) components (frontend/src/components/**/*.vue, including onboarding/wizard subfolders)
  (3) pages    (frontend/src/pages/*.vue)
Within each group, sort alphabetically. Return the full list and the count.`,
    { phase: 'Discover', label: 'discover-files', schema: DISCOVER_SCHEMA },
  )
  files = (disc && disc.files) || []
}
files = files.filter(Boolean)
if (!files.length) {
  log('⛔ No files discovered — aborting.')
  return { aborted: true, reason: 'no target files found', branch: BRANCH }
}
log(`🗂  ${files.length} files queued for enhancement.`)

// ─────────────────────────────────────────────────────────────────────────────
// Phase: Guidelines — distill the design system into a per-pass checklist
// ─────────────────────────────────────────────────────────────────────────────
phase('Guidelines')
const guidelines = await agent(
  `You are a senior design-systems engineer. Produce the authoritative working checklist that every per-file UI/UX agent in this pass will follow.
1. Read \`frontend/src/styles/UI_SYSTEM.md\` and \`frontend/src/styles/tailwind.css\` in full. Extract the COMPLETE catalog of \`ui-*\` component classes that actually exist (grep the @layer components block), the CSS design tokens (--color-*, --motion-*, --ease-*, safe-area), and the RTL/dark-mode handling.
2. Read 2–3 already-polished screens for the house style (try \`frontend/src/pages/Cart.vue\`, \`frontend/src/pages/Home.vue\`, and one owner page) — note header rhythm, kicker+title pattern, chip metadata rows, spacing rhythm, empty/loading state patterns.
3. Write \`frontend/UI_UX_GUIDELINES.md\` containing:
   - The prime directive: enhance presentation only, never change behavior/logic/props/emits/API/router/store.
   - The full enhancement checklist (responsive/overflow, hierarchy & spacing, a11y, the three states loading/empty/error, motion + reduced-motion, dark + RTL, i18n safety, consistency).
   - A quick-reference table of the available \`ui-*\` classes grouped by purpose (layout / surface / form / action / data / typography / motion) with a one-line "use for" each — ONLY classes that truly exist in tailwind.css.
   - The design tokens and the rule to use them instead of new hex colors.
   - The i18n rules: every literal t('a.b') must exist in messages.en (gate-enforced); add en+fr (ASCII, no accents to match existing entries) + Arabic in messages-ar.js (omit Arabic rather than risk mojibake — English auto-falls-back); reuse common.* keys; dynamic keys use backtick template literals.
   - The lint/build constraints (eslint --max-warnings=0, prettier formatting, vite build must pass).
   - The QA gate from UI_SYSTEM §9 (no horizontal overflow at 390x844; all three states; reduced-motion; one primary CTA per section).
Keep it tight and actionable — it is a checklist, not an essay. Write the file with the Write tool. Return a one-paragraph summary of what you captured and confirm the file was written.`,
  { phase: 'Guidelines', model: 'sonnet', label: 'write-guidelines' },
)
log(`📐 Guidelines ready: ${String(guidelines).slice(0, 280)}`)

// ─────────────────────────────────────────────────────────────────────────────
// Phase: Enhance — SEQUENTIAL per-file pass (shared i18n files => no parallel)
// ─────────────────────────────────────────────────────────────────────────────
phase('Enhance')
const results = []
let sinceCommit = 0
for (let i = 0; i < files.length; i++) {
  const file = files[i]
  const n = i + 1
  let r
  try {
    r = await agent(
      `Enhance the UI/UX of EXACTLY ONE file and nothing else: \`${file}\` (file ${n} of ${files.length}).

Before editing, read \`frontend/UI_UX_GUIDELINES.md\`, \`frontend/src/styles/UI_SYSTEM.md\`, and the relevant part of \`frontend/src/styles/tailwind.css\`, then read the full target file.

Apply your full enhancement checklist (responsive/overflow at 390px, visual hierarchy & spacing, accessibility, the three states loading/empty/error, tasteful reduced-motion-safe motion, dark-mode + RTL/Arabic correctness, i18n safety, cross-page consistency) USING the existing \`ui-*\` design system and CSS tokens — do not invent new colors, buttons, or components.

PRIME DIRECTIVE (absolute): change presentation only. Do NOT alter <script> logic, props, emits, v-model, event handlers, API calls, store/router usage, computed/watch, or any business logic. Preserve every binding, key, ref, id, and data-test attribute. If the file is already excellent, make only minimal high-confidence tweaks (or none) and report status "already-good".

You may ONLY edit: this one .vue file, and — solely to register NEW visible strings you introduce — \`frontend/src/i18n/messages.js\` (en + fr blocks) and \`frontend/src/i18n/messages-ar.js\` (ar). Every literal t('a.b') you add MUST exist in messages.en or the build fails. Reuse common.* keys where possible; most screens are already internationalized so you should add few or no keys. Never write mojibake/guessed Arabic — omit the Arabic key instead (English falls back).

Return the structured result.`,
      {
        agentType: 'ui-ux-pro-max',
        model: 'sonnet',
        phase: 'Enhance',
        label: `enhance:${short(file)}`,
        schema: ENHANCE_SCHEMA,
      },
    )
  } catch (e) {
    r = {
      file,
      status: 'skipped',
      changes: [],
      newI18nKeys: [],
      functionalityPreserved: true,
      notes: `agent error: ${String(e).slice(0, 300)}`,
    }
    log(`⚠️  ${short(file)} errored, continuing: ${String(e).slice(0, 160)}`)
  }
  results.push(r || { file, status: 'skipped', functionalityPreserved: true, notes: 'no result' })

  sinceCommit++
  const last = i === files.length - 1
  if (sinceCommit >= COMMIT_EVERY || last) {
    await agent(
      `On branch ${BRANCH}, create a checkpoint commit for the UI/UX pass.
Run \`git add -A\` then commit with this message (use it verbatim, multi-line):

ui/ux pass: enhance files through ${n}/${files.length}

Automated UI/UX enhancement pass (presentation-only; behavior preserved).
Last file: ${file}

${COAUTHOR}

If there is nothing to commit, that is fine — just report it. Do NOT push. Do NOT switch branches. Return one line on what happened.`,
      { phase: 'Enhance', model: 'sonnet', label: `checkpoint@${n}` },
    )
    sinceCommit = 0
    log(`💾 checkpoint @ ${n}/${files.length}`)
  }
}

const enhanced = results.filter((r) => r && r.status === 'enhanced').length
const alreadyGood = results.filter((r) => r && r.status === 'already-good').length
const skipped = results.filter((r) => r && r.status === 'skipped').length
const unsafe = results.filter((r) => r && r.functionalityPreserved === false)
log(`🎨 Enhance done — ${enhanced} enhanced, ${alreadyGood} already-good, ${skipped} skipped, ${unsafe.length} flagged-unsafe.`)

// ─────────────────────────────────────────────────────────────────────────────
// Phase: Verify — run the gates, then fix-and-recheck until green (bounded)
// ─────────────────────────────────────────────────────────────────────────────
phase('Verify')
let verify = await agent(VERIFY_PROMPT, { phase: 'Verify', model: 'sonnet', label: 'verify#0', schema: VERIFY_SCHEMA })
let round = 0
while (verify && !verify.passed && round < MAX_FIX_ROUNDS) {
  round++
  const failed = (verify.gates || []).filter((g) => !g.passed).map((g) => g.name).join(', ') || 'unknown'
  log(`🔧 Verify failed (${failed}) — fix round ${round}/${MAX_FIX_ROUNDS}`)
  await agent(
    `The frontend gates are failing after the UI/UX pass. Fix the failures so all gates pass. Working dir: repo root; frontend lives in \`frontend/\`.

Failing gates: ${failed}
Details:
${(verify.gates || []).filter((g) => !g.passed).map((g) => `### ${g.name}\n${(g.output || '').slice(0, 2500)}`).join('\n\n')}
Summary: ${verify.failureSummary || '(none)'}

Rules while fixing:
- Stay within the spirit of the pass: presentation-only. Do NOT change app behavior/logic to make a test pass — if a UI edit broke a test by changing required markup/text/test-id, restore what the test needs.
- Common fixes: a t('a.b') key referenced but not added to messages.en; an eslint warning (unused import/var, console, formatting); a Vue template syntax error; a snapshot/text assertion that a label change broke (prefer restoring the original user-facing text or its i18n key).
- For i18n: add missing keys to messages.js (en+fr) and messages-ar.js (ar; omit Arabic rather than risk mojibake). Never introduce mojibake.
- After fixing, re-run the specific failing gate(s) from \`frontend/\` to confirm locally.
Edit only frontend source + i18n files. Do NOT commit, push, or switch branches. Report what you changed.`,
    { phase: 'Verify', model: 'sonnet', label: `fix#${round}` },
  )
  // commit the fixes so progress is preserved even if a later round stalls
  await agent(
    `On branch ${BRANCH}: \`git add -A\` and commit verbatim:

ui/ux pass: fix verification round ${round}

${COAUTHOR}

If nothing to commit, say so. Do NOT push. Return one line.`,
    { phase: 'Verify', model: 'sonnet', label: `commit-fix#${round}` },
  )
  verify = await agent(VERIFY_PROMPT, { phase: 'Verify', model: 'sonnet', label: `verify#${round}`, schema: VERIFY_SCHEMA })
}
const green = !!(verify && verify.passed)
log(green ? '✅ All frontend gates green.' : `❌ Gates still failing after ${MAX_FIX_ROUNDS} rounds — see report.`)

// ─────────────────────────────────────────────────────────────────────────────
// Phase: Report — write the human-facing report + final commit
// ─────────────────────────────────────────────────────────────────────────────
phase('Report')
const perFile = results
  .map((r) => `- ${r.file} — ${r.status}${r.functionalityPreserved === false ? ' ⚠️ FUNCTIONALITY-FLAG' : ''}${(r.newI18nKeys && r.newI18nKeys.length) ? ` (+${r.newI18nKeys.length} i18n keys)` : ''}${r.notes ? ` — ${String(r.notes).slice(0, 160)}` : ''}`)
  .join('\n')

await agent(
  `Write the final report for this UI/UX enhancement pass to \`frontend/UI_UX_PASS_REPORT.md\` (use the Write tool), then make a final commit.

Use this data:
- Branch: ${BRANCH}
- Files processed: ${files.length} (enhanced: ${enhanced}, already-good: ${alreadyGood}, skipped: ${skipped})
- Functionality-flagged files (need human review): ${unsafe.length ? unsafe.map((r) => r.file).join(', ') : 'none'}
- Final gate status: ${green ? 'ALL GREEN (verify:i18n, lint, build, test)' : 'NOT GREEN after ' + MAX_FIX_ROUNDS + ' fix rounds'}
${green ? '' : '- Outstanding failures:\n' + JSON.stringify((verify && verify.gates) || [], null, 2).slice(0, 3000)}

Per-file results:
${perFile}

The report should have: a summary header, the gate status, a "Review these first" section (functionality-flagged files + anything skipped/errored), the per-file table, how to review the branch (\`git log --oneline\`, \`git diff main...${BRANCH}\`), and how to ship (review, then merge ${BRANCH} into main; deploy is manual via Coolify).

Then run \`git add -A\` and commit verbatim:

ui/ux pass: final report + ${green ? 'gates green' : 'gates pending'}

${COAUTHOR}

Do NOT push. Return a 3-5 line executive summary of the whole pass.`,
  { phase: 'Report', model: 'sonnet', label: 'final-report' },
)

return {
  branch: BRANCH,
  filesProcessed: files.length,
  enhanced,
  alreadyGood,
  skipped,
  functionalityFlagged: unsafe.map((r) => r.file),
  gatesGreen: green,
  report: 'frontend/UI_UX_PASS_REPORT.md',
  guidelines: 'frontend/UI_UX_GUIDELINES.md',
}
