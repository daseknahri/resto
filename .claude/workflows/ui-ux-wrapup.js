export const meta = {
  name: 'ui-ux-wrapup',
  description:
    'Gentle, low-concurrency (3 at a time) wrap-up of the UI/UX overhaul: a deep per-file audit (technical + product lenses) plus two professional deliverables — UI_UX_OVERHAUL_SUMMARY.md (changelog/phase summary) and NEXT_PHASE_PLAN.md (prioritized roadmap for the next phase). READ-ONLY except for writing the two docs; never commits or pushes. Sized to be heavy on Sonnet thinking but light on the laptop.',
  whenToUse:
    'Run after the UI/UX passes to consolidate the work and define the next phase, without overloading the machine. Output: frontend/UI_UX_OVERHAUL_SUMMARY.md + NEXT_PHASE_PLAN.md. Optional args: {only:[paths], batch:n, lenses:["technical","product"]}.',
  phases: [
    { title: 'Gather', detail: 'changelog stats + categorize the diff' },
    { title: 'Audit', detail: 'deep per-file review, 3 files at a time', model: 'sonnet' },
    { title: 'Summarize', detail: 'write the overhaul summary / changelog', model: 'sonnet' },
    { title: 'Roadmap', detail: 'write the prioritized next-phase plan', model: 'sonnet' },
  ],
}

const BATCH = (args && Number(args.batch)) || 3 // keep the laptop calm: only 3 concurrent agents
const short = (p) => String(p).split('/').slice(-2).join('/')
const chunk = (arr, n) => {
  const out = []
  for (let i = 0; i < arr.length; i += n) out.push(arr.slice(i, i + n))
  return out
}
const runBatched = async (items, fn) => {
  const results = []
  let done = 0
  for (const group of chunk(items, BATCH)) {
    const r = await parallel(group.map((it, i) => () => fn(it, i)))
    results.push(...r)
    done += group.length
    log(`   …audited ${done}/${items.length}`)
  }
  return results
}

const APP_CONTEXT = [
  'App: resto — Vue 3 + Vite + Tailwind multi-tenant restaurant SaaS (owner/staff, customer, driver).',
  'Mature design system: ui-* classes + CSS tokens in frontend/src/styles/tailwind.css (UI_SYSTEM.md /',
  'UI_UX_GUIDELINES.md). It just completed a 2-pass multi-agent UI/UX overhaul. You are a senior product',
  'designer + senior Vue/Tailwind engineer doing a READ-ONLY wrap-up audit to (a) confirm quality and',
  '(b) surface the best opportunities for the NEXT phase. Do NOT edit/Write/git. Be specific (file + element)',
  'and forward-looking (note higher-level opportunities, not just nitpicks). Keep fields short.',
].join('\n')

const LENS = {
  technical: 'a11y/semantics, responsive (390px), the three states (loading/empty/error), RTL/Arabic, i18n correctness, design-system consistency (ui-* + tokens), motion + render performance.',
  product: 'microcopy/UX writing, conversion & primary-action clarity, forms UX, trust/transparency (prices/fees/refunds), onboarding clarity, locale data-formatting, information density & scannability.',
}
const LENS_KEYS = (args && Array.isArray(args.lenses) && args.lenses.length) ? args.lenses : ['technical', 'product']

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
          fix: { type: 'string' },
          nextPhase: { type: 'boolean', description: 'true if this is a larger next-phase opportunity, not a quick fix' },
        },
        required: ['severity', 'title'],
      },
    },
  },
  required: ['verdict'],
}
const DISCOVER_SCHEMA = { type: 'object', properties: { files: { type: 'array', items: { type: 'string' } } }, required: ['files'] }

// ── Gather ───────────────────────────────────────────────────────────────────
phase('Gather')
const gather = await agent(
  `Summarize the UI/UX overhaul changeset for a professional changelog. From the repo root:
- Run \`git diff --shortstat main...ui-ux-pass\` and \`git diff --stat main...ui-ux-pass\` (top files).
- Run \`git log --oneline main..ui-ux-pass | wc -l\` for commit count.
- Read \`frontend/UI_UX_PASS_REPORT.md\` and \`frontend/UI_UX_REVIEW_REPORT.md\` if they exist.
- Categorize the changed .vue files by area (layouts, shared components, onboarding, customer pages, owner pages, admin pages, driver).
Return a concise prose brief: total files/insertions/deletions, commit count, per-area counts, and the headline themes of the overhaul. READ-ONLY.`,
  { phase: 'Gather', label: 'gather-stats' },
)
log(`📊 Gather done.`)

// ── Discover ─────────────────────────────────────────────────────────────────
let files = []
if (args && Array.isArray(args.only) && args.only.length) {
  files = args.only.slice()
} else {
  const disc = await agent(
    `Use Glob to list all *.vue under \`frontend/src/\` (recursive), excluding node_modules. Return repo-relative POSIX paths. {files}.`,
    { phase: 'Gather', label: 'discover', schema: DISCOVER_SCHEMA },
  )
  files = (disc && disc.files) || []
}
files = files.filter(Boolean)

// ── Audit (deep, gentle: BATCH at a time) ────────────────────────────────────
phase('Audit')
const tasks = []
for (const f of files) for (const k of LENS_KEYS) tasks.push({ f, k })
log(`🔬 Deep audit: ${files.length} files x ${LENS_KEYS.length} lenses = ${tasks.length} agents, ${BATCH} at a time.`)
const raw = await runBatched(tasks, (t) =>
  agent(
    `${APP_CONTEXT}\n\n--- LENS: ${t.k} ---\nReview for: ${LENS[t.k]}\n\nRead the ENTIRE file \`${t.f}\` and review it deeply through this lens. Return specific findings (severity, area, short title, short fix, and nextPhase=true for larger opportunities), or verdict "clean". READ-ONLY.`,
    { model: 'sonnet', phase: 'Audit', label: `${t.k}:${short(t.f)}`, schema: FINDINGS_SCHEMA },
  )
    .then((r) => ({ file: t.f, lens: t.k, findings: (r && r.findings) || [] }))
    .catch(() => ({ file: t.f, lens: t.k, findings: [] })),
)

// Aggregate
const all = []
raw.filter(Boolean).forEach((r) => (r.findings || []).forEach((f) => all.push({ file: r.file, lens: r.lens, ...f })))
const counts = {
  total: all.length,
  high: all.filter((f) => f.severity === 'high').length,
  medium: all.filter((f) => f.severity === 'medium').length,
  low: all.filter((f) => f.severity === 'low').length,
  nextPhase: all.filter((f) => f.nextPhase).length,
}
log(`🧾 ${counts.total} findings (${counts.high} high, ${counts.medium} medium, ${counts.nextPhase} next-phase).`)

const sev = (s) => (s === 'high' ? 0 : s === 'medium' ? 1 : 2)
const topFixes = all.filter((f) => f.severity !== 'low').sort((a, b) => sev(a.severity) - sev(b.severity))
  .slice(0, 120).map((f) => `[${f.severity}/${f.lens}] ${short(f.file)}: ${f.title}${f.fix ? ' -> ' + f.fix : ''}`)
const nextPhaseItems = all.filter((f) => f.nextPhase).slice(0, 80).map((f) => `[${f.lens}] ${short(f.file)}: ${f.title}${f.fix ? ' -> ' + f.fix : ''}`)

// ── Summarize: the overhaul changelog/summary ────────────────────────────────
phase('Summarize')
await agent(
  `Write \`frontend/UI_UX_OVERHAUL_SUMMARY.md\` (Write tool; do NOT git). A professional phase summary + changelog of the UI/UX overhaul.
Use this gathered brief:
"""${String(gather).slice(0, 4000)}"""
Audit health: ${JSON.stringify(counts)}.
Top remaining quick-fix findings (sample):
${topFixes.join('\n').slice(0, 6000)}

Sections: 1) Executive summary (what the overhaul achieved, in business terms). 2) Scope & scale (files/insertions/deletions/commits, per-area). 3) What changed, by theme (design-system consolidation, accessibility, responsive/mobile, loading/empty/error states, i18n/RTL, motion, dead-code cleanup). 4) How it was done (2-pass multi-agent Sonnet workflow: enhance -> adversarial 3-lens review -> refine -> gate-verified verify:i18n/lint/build/test). 5) Verification status (all gates green) + known caveats (round-2 polish partial; recovered after a mid-run interruption). 6) How to review & merge (git diff main...ui-ux-pass; deploy manual via Coolify). Keep it crisp and skimmable. Return a 5-line executive summary.`,
  { phase: 'Summarize', model: 'sonnet', label: 'summary-doc' },
)
log(`📝 Summary written.`)

// ── Roadmap: the next-phase plan ─────────────────────────────────────────────
phase('Roadmap')
await agent(
  `Write \`NEXT_PHASE_PLAN.md\` at the repo root (Write tool; do NOT git). A professional, prioritized roadmap for the NEXT phase of the resto app, written like a senior product+eng lead.
Inputs:
- Remaining UI/UX quick-fix backlog (sample):
${topFixes.join('\n').slice(0, 5000)}
- Larger next-phase opportunities surfaced by the audit (sample):
${nextPhaseItems.join('\n').slice(0, 4000)}
- Known strategic/deferred items already on record for this app (include + frame these): (a) Stripe payments as a wallet top-up funding source (keep the existing closed-loop wallet; only add the seam); (b) multi-business "stores" generalization (business_type + capability flags; Dish->Item rename lands last via migrate_schemas); (c) durable notification worker on Coolify (Celery/Redis) — already coded, needs the worker process; (d) visual/RTL screenshot QA pass on a live dev server; (e) finishing the round-2 UI polish + regenerating the two audit reports.

Structure: 1) Where we are (one paragraph: the app is a feature-complete, production-hardened, now UI-overhauled 3-persona platform). 2) Themes for the next phase. 3) A prioritized backlog table (P0/P1/P2 | item | why | rough effort S/M/L | risk). 4) Recommended sequencing (what to do first and why). 5) Definition of done for the next phase. Be concrete and realistic; group the UI nitpicks into themes rather than listing all. Return a 6-line executive summary of the recommended next phase.`,
  { phase: 'Roadmap', model: 'sonnet', label: 'roadmap-doc' },
)
log(`🗺️ Next-phase plan written.`)

return {
  filesAudited: files.length,
  lenses: LENS_KEYS,
  counts,
  deliverables: ['frontend/UI_UX_OVERHAUL_SUMMARY.md', 'NEXT_PHASE_PLAN.md'],
  note: 'docs written but NOT committed — commit after review',
}
