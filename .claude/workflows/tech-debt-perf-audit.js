export const meta = {
  name: 'tech-debt-perf-audit',
  description:
    'Exhaustive, READ-ONLY technical audit of the resto app focused on SPEED (backend ORM/query perf, DB indexes, caching/async, frontend bundle + runtime perf) and HOSTING EFFICIENCY (Docker, server runtime config, dependencies, multi-tenant scale cost). 12 expert lenses fan out across backend/frontend/infra (capped at 3 concurrent to stay gentle on the machine), every high/critical finding is adversarially re-verified against the real code, then synthesized into a prioritized backlog. Makes NO edits and runs NO builds/git.',
  whenToUse:
    'Run to produce a prioritized performance + hosting-efficiency tech-debt backlog (what to change next). Output: PERF_HOSTING_AUDIT.md. Read-only, low concurrency. Optional args: {batch:n}.',
  phases: [
    { title: 'Survey', detail: 'map backend/frontend/infra files + deps' },
    { title: 'Audit', detail: '12 read-only expert lenses, 3 at a time', model: 'sonnet' },
    { title: 'Verify', detail: 'adversarially re-verify high/critical findings', model: 'sonnet' },
    { title: 'Report', detail: 'synthesize the prioritized speed + hosting backlog', model: 'sonnet' },
  ],
}

// ── Gentle concurrency (laptop-safe) ─────────────────────────────────────────
const BATCH = (args && Number(args.batch)) || 3
const chunk = (a, n) => { const o = []; for (let i = 0; i < a.length; i += n) o.push(a.slice(i, i + n)); return o }
const runBatched = async (items, fn, label) => {
  const out = []
  let done = 0
  for (const g of chunk(items, BATCH)) {
    const r = await parallel(g.map((it, i) => () => fn(it, i)))
    out.push(...r)
    done += g.length
    log(`   …${label} ${done}/${items.length}`)
  }
  return out
}

const CONTEXT = [
  'App: resto — a production multi-tenant restaurant SaaS. Backend: Django + django-tenants (SHARED_APPS:',
  'accounts/tenancy/sales in the public schema; TENANT_APPS: menu per-tenant schema), Django REST Framework,',
  'Celery + Redis (notifications/crons), PostgreSQL. Frontend: Vue 3 + Vite + Tailwind + vue-router + pinia,',
  'leaflet for maps, custom i18n. Deployed on Coolify (manual deploy; Docker). 3 personas: owner/staff,',
  'customer, driver. It is feature-complete and just had a UI overhaul.',
  '',
  'You are a STAFF-level performance + infrastructure engineer doing a READ-ONLY audit. Find concrete,',
  'high-signal technical issues the team will want to change — prioritizing SPEED and HOSTING EFFICIENCY.',
  'Be specific: cite exact files (and line/symbol where possible), explain the impact, and give a concrete fix.',
  '',
  'STRICT RULES:',
  '- READ-ONLY: use only Read / Grep / Glob (and at most trivial, instant shell like listing a file). Do NOT',
  '  edit files, do NOT run builds / dev servers / pytest / npm / docker, do NOT run git. No heavy or long',
  '  processes — the host is resource-constrained.',
  '- No false alarms: before reporting a query/perf problem, actually read the queryset/serializer/component',
  '  to confirm it is real (e.g. do NOT claim N+1 if select_related/prefetch_related is already present).',
  '- Rate each finding by severity (critical/high/medium/low), category (speed|hosting), impact, and effort (S/M/L).',
]

const LENSES = [
  { key: 'orm-accounts', title: 'Backend query perf — accounts app', scope: 'backend/accounts (views.py, serializers, models)', focus: 'Django ORM hot paths: N+1 (loops issuing queries, serializers fetching related per-row), missing select_related/prefetch_related, .count()/exists() misuse, unpaginated list endpoints, repeated identical queries per request, .all() then filter in Python, large IN clauses. The marketplace/directory/driver endpoints are high-traffic — scrutinize them.' },
  { key: 'orm-menu', title: 'Backend query perf — menu app (per-tenant)', scope: 'backend/menu (views.py, models, serializers)', focus: 'Per-tenant menu/order/category/dish queries: N+1 across dishes/options/categories, customer menu endpoint efficiency (heavily hit), order placement query count, missing prefetch on nested option groups, image/URL building per-row, kitchen/owner order lists.' },
  { key: 'orm-sales-tenancy', title: 'Backend query perf — sales + tenancy', scope: 'backend/sales + backend/tenancy', focus: 'Provisioning, leads/reservations, subscriptions/tiering, wallet ledger queries; cross-schema lookups; enforce_subscriptions/cron query cost; any full-table scans.' },
  { key: 'db-indexes', title: 'DB schema & indexes', scope: 'all backend models + migrations', focus: 'Missing db_index on fields used in filter()/order_by()/FK lookups; missing composite indexes for common (tenant_id, status, created_at)-style queries; unindexed unique/lookup fields (slugs, order_number, tokens, phone/email); JSONField query patterns; over-wide text columns; index bloat or redundant indexes; missing Meta.ordering causing unbounded sorts.' },
  { key: 'cache-async', title: 'Backend caching & async', scope: 'backend config/settings + views + tasks', focus: 'Synchronous external I/O in the request path (push/SMS/email/WhatsApp/geocoding) that should be queued; cacheable-but-uncached hot reads (customer menu, marketplace, directory, business hours, tiering); cache backend config; DATABASES CONN_MAX_AGE / connection reuse / pooling; DRF throttle cache backend; repeated settings/profile reads; Celery task granularity and beat frequency cost.' },
  { key: 'fe-bundle', title: 'Frontend bundle & build', scope: 'frontend (vite.config, package.json, router, main.js, heavy imports)', focus: 'Route-level code-splitting (are pages lazy-imported or all eager?), lazy-loading heavy deps (leaflet, any chart lib) only where used, the large index chunk (~470KB) — what is in it, duplicate/heavy deps, vendor chunking, sourcemaps shipped to prod, tree-shaking blockers (side-effectful imports), Tailwind purge/content config, unused dependencies.' },
  { key: 'fe-runtime', title: 'Frontend runtime perf & leaks', scope: 'frontend pages/components with timers, polling, maps, large lists', focus: 'Polling intervals (OrderStatus, ChargeApprovalWatcher, DeliveryTracker GPS, marketplace) — frequency + are they cleared on unmount; setInterval/setTimeout/addEventListener without cleanup (memory leaks); expensive computed/watchers re-running; large lists without virtualization; images without width/height/lazy; reactivity over large objects; redundant API calls on locale/route change.' },
  { key: 'docker', title: 'Containerization & image size', scope: 'Dockerfile(s), .dockerignore, docker-compose, build scripts', focus: 'Multi-stage builds, layer caching order (copy deps manifest before source), final image base (slim/alpine vs full), build deps left in runtime image, image size, .dockerignore completeness (node_modules/.git/tests excluded from context), frontend build artifact handling, number of images/containers.' },
  { key: 'server-runtime', title: 'Server runtime & static/media serving', scope: 'gunicorn/uvicorn config, settings, static/media, Coolify config', focus: 'WSGI/ASGI server + worker/thread count vs container CPU/RAM, whitenoise vs nginx vs CDN for static, media storage (local disk vs object storage), gzip/brotli + cache-control headers, healthcheck cost/frequency, Celery worker + beat as separate processes and their resource cost, DEBUG/logging in prod, SSL redirect overhead.' },
  { key: 'deps-footprint', title: 'Dependencies & footprint', scope: 'requirements.txt, package.json, lockfiles', focus: 'Heavy or unused Python/Node deps, unpinned versions, dev deps leaking into prod, duplicate functionality libs, large transitive deps, Python/Node version, anything inflating build time or image size.' },
  { key: 'multitenant-scale', title: 'Multi-tenant scale & cost', scope: 'django-tenants usage, middleware, public-schema queries', focus: 'Schema-switch cost per request, public-schema marketplace/directory queries scanning all tenants, connection-per-schema patterns, search/filter efficiency across many tenants, migrate_schemas cost as tenants grow, per-tenant cache key strategy, anything that gets linearly slower/pricier with more tenants or more orders.' },
  { key: 'ops-cost', title: 'Observability & ops cost', scope: 'logging, Sentry, crons/beat, notifications, backups', focus: 'Log volume/verbosity in prod, Sentry sampling, cron/beat frequencies (sweep/enforce/reminders) and their per-run query cost, notification fan-out cost, DB backup strategy, anything that quietly costs CPU/$ at scale or risks runaway growth (unbounded tables/logs).' },
]

const SURVEY_SCHEMA = {
  type: 'object',
  properties: {
    backend: { type: 'array', items: { type: 'string' } },
    frontend: { type: 'array', items: { type: 'string' } },
    infra: { type: 'array', items: { type: 'string' } },
    deps: { type: 'array', items: { type: 'string' } },
    notes: { type: 'string' },
  },
  required: ['notes'],
}

const FINDINGS_SCHEMA = {
  type: 'object',
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low'] },
          category: { type: 'string', enum: ['speed', 'hosting'] },
          title: { type: 'string' },
          detail: { type: 'string' },
          files: { type: 'array', items: { type: 'string' } },
          fix: { type: 'string' },
          impact: { type: 'string' },
          effort: { type: 'string', enum: ['S', 'M', 'L'] },
        },
        required: ['severity', 'category', 'title', 'fix'],
      },
    },
  },
  required: ['findings'],
}

const VERDICT_SCHEMA = {
  type: 'object',
  properties: {
    confirmed: { type: 'boolean' },
    reason: { type: 'string' },
    correctedSeverity: { type: 'string', enum: ['critical', 'high', 'medium', 'low'] },
  },
  required: ['confirmed', 'reason'],
}

const short = (p) => String(p).split('/').slice(-2).join('/')

// ── Survey ───────────────────────────────────────────────────────────────────
phase('Survey')
const survey = await agent(
  `${CONTEXT.join('\n')}\n\n--- SURVEY (read-only) ---\nMap the repo so the audit can target real files. Use Glob/Grep/Read lightly.\nReturn:\n- backend: key Python files for perf (views.py per app, models.py, serializers, config/settings.py, config/celery.py, requirements.txt).\n- frontend: key files (vite.config.*, package.json, src/router*, src/main.js, the heaviest pages/components, anything importing leaflet/charts).\n- infra: Dockerfile(s), .dockerignore, docker-compose*, any Coolify/nixpacks/Procfile/start scripts, gunicorn/uvicorn config.\n- deps: dependency manifests + lockfiles.\n- notes: a short orientation (where the hot paths and biggest files are).`,
  { phase: 'Survey', label: 'survey', schema: SURVEY_SCHEMA },
)
log(`🗺️ Survey done. ${String(survey && survey.notes || '').slice(0, 200)}`)
const surveyBlob = JSON.stringify(survey || {}, null, 0).slice(0, 6000)

// ── Audit (12 lenses, batched) ───────────────────────────────────────────────
phase('Audit')
log(`🔬 ${LENSES.length} lenses, ${BATCH} at a time.`)
const lensResults = await runBatched(
  LENSES,
  (lens) =>
    agent(
      `${CONTEXT.join('\n')}\n\n--- AUDIT LENS: ${lens.title} ---\nPrimary scope: ${lens.scope}\nLook for: ${lens.focus}\n\nRepo survey (for file locations):\n${surveyBlob}\n\nRead the relevant files thoroughly and return specific, verified findings with file references, concrete fixes, impact, and effort. Quality over quantity — only real issues. READ-ONLY (no edits/builds/git).`,
      { model: 'sonnet', phase: 'Audit', label: `audit:${lens.key}`, schema: FINDINGS_SCHEMA },
    )
      .then((r) => ({ lens: lens.key, findings: (r && r.findings) || [] }))
      .catch((e) => ({ lens: lens.key, findings: [], error: String(e).slice(0, 160) })),
  'audited',
)

// Flatten + tag with an index
const all = []
lensResults.forEach((lr) => (lr.findings || []).forEach((f) => all.push({ ...f, lens: lr.lens })))
const sev = (s) => ({ critical: 0, high: 1, medium: 2, low: 3 }[s] ?? 4)
all.sort((a, b) => sev(a.severity) - sev(b.severity))
const counts = {
  total: all.length,
  critical: all.filter((f) => f.severity === 'critical').length,
  high: all.filter((f) => f.severity === 'high').length,
  medium: all.filter((f) => f.severity === 'medium').length,
  low: all.filter((f) => f.severity === 'low').length,
}
log(`🧾 ${counts.total} findings (${counts.critical} critical, ${counts.high} high, ${counts.medium} medium).`)

// ── Verify (adversarial, high + critical only) ───────────────────────────────
phase('Verify')
const toVerify = all.filter((f) => f.severity === 'critical' || f.severity === 'high')
log(`🕵️ Adversarially verifying ${toVerify.length} high/critical findings.`)
const verdicts = await runBatched(
  toVerify,
  (f, i) =>
    agent(
      `${CONTEXT.join('\n')}\n\n--- ADVERSARIALLY VERIFY ONE FINDING ---\nA performance/hosting finding was reported. Your job is to REFUTE it if you can — read the actual cited code and decide whether it is genuinely real and correctly rated. Default to confirmed=false if the evidence does not clearly support it (e.g. the claimed N+1 already has prefetch, the index already exists, the dep is actually used, the interval IS cleared on unmount).\n\nFinding: ${JSON.stringify({ severity: f.severity, category: f.category, title: f.title, detail: f.detail, files: f.files, fix: f.fix })}\n\nRead the referenced files and return {confirmed, reason, correctedSeverity}. READ-ONLY.`,
      { model: 'sonnet', phase: 'Verify', label: `verify:${short((f.files && f.files[0]) || f.title)}`, schema: VERDICT_SCHEMA },
    )
      .then((v) => ({ ...f, verdict: v || { confirmed: false, reason: 'no verdict' } }))
      .catch(() => ({ ...f, verdict: { confirmed: true, reason: 'verifier errored — kept pending review' } })),
  'verified',
)
const confirmed = verdicts.filter((f) => f.verdict.confirmed)
const refuted = verdicts.filter((f) => !f.verdict.confirmed)
log(`✅ ${confirmed.length} confirmed, ❌ ${refuted.length} refuted (false positives dropped).`)

// Apply corrected severities; keep medium/low (unverified) separately.
confirmed.forEach((f) => { if (f.verdict.correctedSeverity) f.severity = f.verdict.correctedSeverity })
const mediumLow = all.filter((f) => f.severity === 'medium' || f.severity === 'low')

const fmt = (f) => `- [${f.severity}/${f.category}/${f.lens}] ${f.title}${(f.files && f.files.length) ? ` (${f.files.map(short).join(', ')})` : ''} — ${f.fix}${f.impact ? ` | impact: ${f.impact}` : ''}${f.effort ? ` | effort: ${f.effort}` : ''}`
const confirmedBlob = confirmed.sort((a, b) => sev(a.severity) - sev(b.severity)).map(fmt).join('\n').slice(0, 9000)
const refutedBlob = refuted.map((f) => `- ${f.title} — refuted: ${f.verdict.reason}`).join('\n').slice(0, 2500)
const mediumLowBlob = mediumLow.map(fmt).join('\n').slice(0, 6000)

// ── Report ───────────────────────────────────────────────────────────────────
phase('Report')
await agent(
  `Write \`PERF_HOSTING_AUDIT.md\` at the repo root (Write tool; do NOT git). A staff-level, prioritized technical backlog for SPEED + HOSTING EFFICIENCY, based on this audit.

Verified high/critical findings:
${confirmedBlob}

Medium/low findings (not individually re-verified):
${mediumLowBlob}

Refuted (false positives — note these were checked and dismissed):
${refutedBlob}

Totals before verification: ${JSON.stringify(counts)}.

Structure the report:
1. Executive summary — the 3-5 biggest wins for speed and for hosting cost, in plain terms.
2. SPEED backlog — table (Pri | Issue | Files | Fix | Impact | Effort), grouped: backend queries/indexes, caching/async, frontend bundle, frontend runtime. Verified items first.
3. HOSTING EFFICIENCY backlog — table: Docker/image, server runtime & static/media, dependencies, multi-tenant scale, ops cost.
4. Recommended sequencing — quick wins first (high impact / low effort), then the structural ones.
5. "Verified vs needs-confirmation" note + the dismissed false positives (transparency).
Keep it concrete and skimmable. Return a 6-8 line executive summary of the top recommendations.`,
  { phase: 'Report', model: 'sonnet', label: 'audit-report' },
)

return {
  lenses: LENSES.length,
  counts,
  verifiedHighCritical: confirmed.length,
  refutedFalsePositives: refuted.length,
  report: 'PERF_HOSTING_AUDIT.md',
  note: 'read-only audit; report written but NOT committed — commit after review',
}
