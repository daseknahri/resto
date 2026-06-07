export const meta = {
  name: 'ui-ux-deep-audit',
  description:
    'Massively-parallel, READ-ONLY deep UI/UX audit of the resto frontend. Fans out 8 expert lenses across every Vue file (~hundreds of concurrent Sonnet agents) to produce a prioritized, actionable backlog. Makes NO code edits and runs NO git, so it is safe to run concurrently with an editing pass (ui-ux-pass / ui-ux-review-refine).',
  whenToUse:
    'Run to spend a large Sonnet budget quickly and safely on analysis (e.g. while an editing pass is mid-flight, or to generate a backlog). Output: frontend/UI_UX_DEEP_AUDIT.md. Optional args: {only:[paths]}.',
  phases: [
    { title: 'Discover', detail: 'enumerate every target .vue file' },
    { title: 'Audit', detail: '8 read-only expert lenses per file, all in parallel', model: 'sonnet' },
    { title: 'Report', detail: 'aggregate findings into a prioritized backlog', model: 'sonnet' },
  ],
}

const APP_CONTEXT = [
  'App: resto — Vue 3 + Vite + Tailwind multi-tenant restaurant platform (owner/staff, customer, driver).',
  'Mature design system: ui-* component classes + CSS tokens in frontend/src/styles/tailwind.css, documented',
  'in frontend/src/styles/UI_SYSTEM.md and frontend/UI_UX_GUIDELINES.md. The app just went through an',
  'enhancement pass, so judge the CURRENT state of each file.',
  '',
  'You are a READ-ONLY auditor. Do NOT edit, Write, or run git — only Read/Grep/Glob and analyze. Your job is',
  'to find concrete, specific, actionable issues a senior product designer + senior Vue/Tailwind engineer would',
  'flag. Reference the exact element/line and give a crisp suggested fix. Keep each field short (title <= 120',
  'chars, detail <= 280, fix <= 240). If the file is genuinely excellent on your lens, return verdict "clean".',
]

const LENSES = [
  { key: 'a11y', title: 'Accessibility / WCAG', focus: 'Semantic HTML (button vs div@click, nav/main/header, ul/li, label[for]), heading order, ARIA (label/labelledby/current/expanded/role), icon-only buttons labelled, alt text, color contrast on the dark palette, form errors announced.' },
  { key: 'keyboard', title: 'Keyboard & focus management', focus: 'Tab order, visible focus-visible rings, no positive tabindex, modals/sheets/menus trap + restore focus and close on Esc, skip-to-content where relevant, clickable non-buttons reachable by keyboard.' },
  { key: 'responsive', title: 'Responsive & mobile ergonomics', focus: 'No horizontal overflow at 390x844, breakpoints, min-w-0 on scroll-row parents, truncate/line-clamp, tap targets >= 44px, tables have md:hidden card fallback, sticky/dock elements respect safe-area.' },
  { key: 'visual', title: 'Visual hierarchy, spacing & design-system consistency', focus: 'One primary CTA per section, consistent space-y rhythm, aligned paddings, kicker+title pattern, uses ui-* primitives + tokens (not ad-hoc utility soup or new hex colors), consistent with polished siblings (Cart.vue, Home.vue).' },
  { key: 'i18n', title: 'i18n completeness & correctness', focus: 'Hardcoded user-visible strings that should be t(...), literal t() keys that may be missing from messages.en, string-concatenated dynamic keys (should be backtick template literals), untranslated aria-labels/placeholders/alts.' },
  { key: 'rtl', title: 'RTL / Arabic mirroring', focus: 'Physical ml/mr/left/right/text-left/right/pl/pr that should be logical (ms/me, ps/pe, start/end, text-start/end), directional icons that should flip under html[lang="ar"], absolute-positioned elements pinned to a physical side.' },
  { key: 'states', title: 'Loading / empty / error states & resilience', focus: 'Every async/data/list section should render a loading skeleton, a friendly empty state with an action, and a clear error state with retry. Flag missing states, blank flashes, dead ends, unguarded awaits.' },
  { key: 'perf', title: 'Motion, reduced-motion & render performance', focus: 'Motion tasteful + reduced-motion-safe (rely on ui-* primitives), one animation per element; v-for has stable :key (not index where it matters); avoid heavy work in computed/templates; large inline SVG/asset or heavy import that could be lazy.' },
]

const FINDINGS_SCHEMA = {
  type: 'object',
  properties: {
    verdict: { type: 'string', enum: ['clean', 'issues'] },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          severity: { type: 'string', enum: ['high', 'medium', 'low'] },
          area: { type: 'string' },
          title: { type: 'string' },
          detail: { type: 'string' },
          fix: { type: 'string' },
        },
        required: ['severity', 'title'],
      },
    },
  },
  required: ['verdict'],
}

const DISCOVER_SCHEMA = {
  type: 'object',
  properties: { files: { type: 'array', items: { type: 'string' } }, count: { type: 'integer' } },
  required: ['files'],
}

const short = (p) => String(p).split('/').slice(-2).join('/')

// ── Discover ─────────────────────────────────────────────────────────────────
phase('Discover')
let files = []
if (args && Array.isArray(args.only) && args.only.length) {
  files = args.only.slice()
} else {
  const disc = await agent(
    `List every target Vue file for an audit. Use Glob to find all *.vue under \`frontend/src/\` (recursive),
EXCLUDING node_modules. Return repo-relative POSIX paths, ordered layouts -> components -> pages. {files, count}.`,
    { phase: 'Discover', label: 'discover', schema: DISCOVER_SCHEMA },
  )
  files = (disc && disc.files) || []
}
files = files.filter(Boolean)
if (!files.length) return { aborted: true, reason: 'no files' }
log(`🔬 Deep audit: ${files.length} files x ${LENSES.length} lenses = ${files.length * LENSES.length} parallel read-only agents.`)

// ── Audit (max parallelism: one big fan-out) ─────────────────────────────────
phase('Audit')
const tasks = []
for (const f of files) for (const lens of LENSES) tasks.push({ f, lens })
const raw = await parallel(
  tasks.map((t) => () =>
    agent(
      `${APP_CONTEXT.join('\n')}\n\n--- AUDIT LENS: ${t.lens.title} ---\nLook for: ${t.lens.focus}\n\n` +
        `Read \`frontend/UI_UX_GUIDELINES.md\` (if present) and the ENTIRE file \`${t.f}\`, plus grep \`frontend/src/styles/tailwind.css\` for any ui-* class you need to confirm. Audit ONLY through this lens and return specific, actionable findings (or verdict "clean"). READ-ONLY — never edit/write/git.`,
      { model: 'sonnet', phase: 'Audit', label: `${t.lens.key}:${short(t.f)}`, schema: FINDINGS_SCHEMA },
    )
      .then((r) => ({ file: t.f, lens: t.lens.key, findings: (r && r.findings) || [] }))
      .catch(() => ({ file: t.f, lens: t.lens.key, findings: [] })),
  ),
)

// ── Aggregate ────────────────────────────────────────────────────────────────
const all = []
raw.filter(Boolean).forEach((r) => {
  ;(r.findings || []).forEach((fnd) => all.push({ file: r.file, lens: r.lens, ...fnd }))
})
const sev = (s) => (s === 'high' ? 0 : s === 'medium' ? 1 : 2)
all.sort((a, b) => sev(a.severity) - sev(b.severity))
const highs = all.filter((f) => f.severity === 'high')
const meds = all.filter((f) => f.severity === 'medium')
const counts = { total: all.length, high: highs.length, medium: meds.length, low: all.length - highs.length - meds.length }
log(`🧾 Findings: ${counts.total} (${counts.high} high, ${counts.medium} medium, ${counts.low} low).`)

// Per-file compact rollup (counts + high/medium titles) to keep the report prompt bounded.
const byFile = {}
all.forEach((f) => {
  const e = (byFile[f.file] = byFile[f.file] || { high: 0, medium: 0, low: 0, items: [] })
  e[f.severity]++
  if (f.severity !== 'low') e.items.push(`[${f.severity}/${f.lens}] ${f.title}${f.fix ? ' -> ' + f.fix : ''}`)
})
const rollup = Object.keys(byFile)
  .sort((a, b) => byFile[b].high - byFile[a].high || byFile[b].medium - byFile[a].medium)
  .map((file) => ({ file, ...byFile[file], items: byFile[file].items.slice(0, 12) }))

// ── Report (no git; just write the file) ─────────────────────────────────────
phase('Report')
await agent(
  `Write a prioritized UI/UX deep-audit backlog to \`frontend/UI_UX_DEEP_AUDIT.md\` using the Write tool. Do NOT run git.

Totals: ${JSON.stringify(counts)}
Lenses: ${LENSES.map((l) => l.key).join(', ')}

Per-file rollup (sorted by high then medium; each item is "[severity/lens] title -> fix"):
${JSON.stringify(rollup, null, 2).slice(0, 14000)}

Structure the report:
1. Executive summary (totals, the 8 lenses, the highest-impact themes you see across files).
2. "Top priorities" — the high-severity findings grouped by theme (a11y, responsive, i18n/RTL, states, ...), each with the files affected and the fix.
3. Per-file table: file | high | medium | low | top items.
4. "Quick wins" — low-effort/high-impact fixes.
5. A short note that this is a READ-ONLY audit (no code changed) and how to act on it (feed into a future apply-pass).
Keep it skimmable and concrete. Return a 4-6 line executive summary.`,
  { phase: 'Report', model: 'sonnet', label: 'audit-report' },
)

return { filesAudited: files.length, lenses: LENSES.length, counts, report: 'frontend/UI_UX_DEEP_AUDIT.md' }
