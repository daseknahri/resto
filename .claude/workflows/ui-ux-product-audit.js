export const meta = {
  name: 'ui-ux-product-audit',
  description:
    'Massively-parallel, READ-ONLY PRODUCT/CONTENT audit of the resto frontend. Complements the technical ui-ux-deep-audit with a different lens set (microcopy, conversion, forms UX, empty-state helpfulness, onboarding clarity, trust signals, locale data-formatting, information density). Makes NO code edits and runs NO git — safe to run concurrently with editing/audit passes.',
  whenToUse:
    'Run alongside ui-ux-deep-audit to spend a large Sonnet budget on distinct product-quality analysis. Output: frontend/UI_UX_PRODUCT_AUDIT.md. Optional args: {only:[paths]}.',
  phases: [
    { title: 'Discover', detail: 'enumerate every target .vue file' },
    { title: 'Audit', detail: '8 read-only product lenses per file, all in parallel', model: 'sonnet' },
    { title: 'Report', detail: 'aggregate into a prioritized product backlog', model: 'sonnet' },
  ],
}

const APP_CONTEXT = [
  'App: resto — Vue 3 + Vite + Tailwind multi-tenant restaurant platform (owner/staff, customer, driver).',
  'i18n lives in src/i18n/messages.js (en+fr) + messages-ar.js (ar). It just had a UI enhancement pass; judge',
  'the CURRENT state. You are a senior PRODUCT designer + UX writer + conversion specialist.',
  '',
  'You are READ-ONLY: do NOT edit, Write, or run git — only Read/Grep/Glob and analyze. Find concrete, specific,',
  'actionable product/content issues. Reference the exact element/string and give a crisp suggested improvement',
  '(including better copy where relevant). Keep fields short (title <= 120, detail <= 280, fix <= 240). If the',
  'file is genuinely strong on your lens, return verdict "clean".',
]

const LENSES = [
  { key: 'microcopy', title: 'Microcopy & UX writing', focus: 'Clarity, tone, and consistency of labels/buttons/headings/helper text; jargon; vague CTAs ("Submit" vs "Place order"); sentence case consistency; concise empty/error copy; consistent terminology across screens.' },
  { key: 'conversion', title: 'Conversion & primary-action clarity', focus: 'Is the next step obvious? One unambiguous primary CTA; friction in key journeys (browse->cart->checkout, onboarding, reservation); reassurance near commit points (price, fees, totals, what happens next); dead ends without a forward path.' },
  { key: 'forms', title: 'Form & input UX', focus: 'Labels + placeholders + helper text, inline validation + clear error messages, correct input types/inputmode/autocomplete, required-field indication, disabled/submitting states, sensible defaults, not asking for more than needed.' },
  { key: 'empty', title: 'Empty-state & first-run helpfulness', focus: 'Empty states that teach + offer a clear action (not just "No data"); zero/first-run guidance; skeletons vs spinners; encouraging tone; previews/examples where it helps the owner or customer get started.' },
  { key: 'onboarding', title: 'Onboarding & owner setup clarity', focus: 'Wizard/onboarding steps clarity, progress indication, ability to go back, value framing, defaults that reduce effort, clear success/next-step after publish; reduce cognitive load for non-technical restaurant owners.' },
  { key: 'trust', title: 'Trust, safety & transparency', focus: 'Are prices/fees/delivery costs/totals shown clearly before commit? Payment/refund/cancellation clarity; data/privacy reassurance; no surprising charges; clear order/delivery status; honest availability/closed-state messaging.' },
  { key: 'locale', title: 'Locale & data formatting', focus: 'Dates/times/currency (MAD)/numbers formatted per locale + RTL; relative times ("5m ago") localized; pluralization; phone/address formats; no hardcoded "$" or English-only date formats; correct fr/ar coverage of visible copy.' },
  { key: 'density', title: 'Information density & scannability', focus: 'Is the most important info first and scannable? Overload vs clarity; grouping + hierarchy; meaningful badges/status pills; tables vs cards on mobile; progressive disclosure for advanced/owner-heavy screens.' },
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
log(`🛍️ Product audit: ${files.length} files x ${LENSES.length} lenses = ${files.length * LENSES.length} parallel read-only agents.`)

phase('Audit')
const tasks = []
for (const f of files) for (const lens of LENSES) tasks.push({ f, lens })
const raw = await parallel(
  tasks.map((t) => () =>
    agent(
      `${APP_CONTEXT.join('\n')}\n\n--- PRODUCT LENS: ${t.lens.title} ---\nLook for: ${t.lens.focus}\n\n` +
        `Read the ENTIRE file \`${t.f}\` (and grep src/i18n/messages.js for any t() key whose copy you want to judge). Audit ONLY through this lens; return specific, actionable findings with improved copy where relevant (or verdict "clean"). READ-ONLY — never edit/write/git.`,
      { model: 'sonnet', phase: 'Audit', label: `${t.lens.key}:${short(t.f)}`, schema: FINDINGS_SCHEMA },
    )
      .then((r) => ({ file: t.f, lens: t.lens.key, findings: (r && r.findings) || [] }))
      .catch(() => ({ file: t.f, lens: t.lens.key, findings: [] })),
  ),
)

const all = []
raw.filter(Boolean).forEach((r) => {
  ;(r.findings || []).forEach((fnd) => all.push({ file: r.file, lens: r.lens, ...fnd }))
})
const sev = (s) => (s === 'high' ? 0 : s === 'medium' ? 1 : 2)
all.sort((a, b) => sev(a.severity) - sev(b.severity))
const counts = {
  total: all.length,
  high: all.filter((f) => f.severity === 'high').length,
  medium: all.filter((f) => f.severity === 'medium').length,
  low: all.filter((f) => f.severity === 'low').length,
}
log(`🧾 Product findings: ${counts.total} (${counts.high} high, ${counts.medium} medium, ${counts.low} low).`)

const byFile = {}
all.forEach((f) => {
  const e = (byFile[f.file] = byFile[f.file] || { high: 0, medium: 0, low: 0, items: [] })
  e[f.severity]++
  if (f.severity !== 'low') e.items.push(`[${f.severity}/${f.lens}] ${f.title}${f.fix ? ' -> ' + f.fix : ''}`)
})
const rollup = Object.keys(byFile)
  .sort((a, b) => byFile[b].high - byFile[a].high || byFile[b].medium - byFile[a].medium)
  .map((file) => ({ file, ...byFile[file], items: byFile[file].items.slice(0, 12) }))

phase('Report')
await agent(
  `Write a prioritized PRODUCT/CONTENT backlog to \`frontend/UI_UX_PRODUCT_AUDIT.md\` using the Write tool. Do NOT run git.

Totals: ${JSON.stringify(counts)}
Lenses: ${LENSES.map((l) => l.key).join(', ')}

Per-file rollup (sorted by high then medium; each item is "[severity/lens] title -> fix"):
${JSON.stringify(rollup, null, 2).slice(0, 14000)}

Structure: 1) Executive summary + top product themes; 2) Top priorities grouped by theme (microcopy, conversion, forms, trust, locale, ...) with affected files + the fix/better copy; 3) Per-file table (file | high | medium | low | top items); 4) Quick wins; 5) note this is READ-ONLY (no code changed) and how to act on it. Keep it concrete and skimmable. Return a 4-6 line executive summary.`,
  { phase: 'Report', model: 'sonnet', label: 'product-report' },
)

return { filesAudited: files.length, lenses: LENSES.length, counts, report: 'frontend/UI_UX_PRODUCT_AUDIT.md' }
