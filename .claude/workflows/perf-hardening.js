export const meta = {
  name: 'perf-hardening',
  description:
    'Implement the verified, lower-risk performance + hosting items from PERF_HOSTING_AUDIT.md, production-safely: SEQUENTIAL (one agent at a time — backend edits share files and add migrations, so no parallelism), per-item commits, then full verification (backend pytest green + manage.py check + makemigrations --check + frontend lint/build/test) with a bounded fixer loop. Lands on branch perf-hardening; NEVER pushes or merges. Excludes the cache/denormalization structural pieces (handled separately with dedicated tests).',
  whenToUse:
    'Run to apply the audit Phase-1 quick wins + driver-batching + Dockerfile multi-stage as a long, verified, reviewable batch. Output: branch perf-hardening (green) + PERF_HARDENING_REPORT.md.',
  phases: [
    { title: 'Prep', detail: 'clean-tree guard + perf-hardening branch' },
    { title: 'Implement', detail: 'apply each verified fix sequentially + commit', model: 'sonnet' },
    { title: 'Verify', detail: 'backend pytest + checks + frontend gates, fix until green', model: 'sonnet' },
    { title: 'Report', detail: 'write the hardening report + final commit', model: 'sonnet' },
  ],
}

const BRANCH = 'perf-hardening'
const MAX_FIX_ROUNDS = 4
const COAUTHOR = 'Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>'

// Exact backend commands for THIS repo (git-bash subagent shell; system Python, no venv; DEBUG required).
const PY = 'C:/Python312/python.exe'
const BACKEND_TEST = `cd backend && DJANGO_DEBUG=True ${PY} -m pytest -q`
const BACKEND_CHECK = `cd backend && DJANGO_DEBUG=True ${PY} manage.py check`
const BACKEND_MAKEMIG = `cd backend && DJANGO_DEBUG=True ${PY} manage.py makemigrations`
const BACKEND_MAKEMIG_CHECK = `cd backend && DJANGO_DEBUG=True ${PY} manage.py makemigrations --check --dry-run`

const CONTEXT = [
  'App: resto — Django + django-tenants (SHARED_APPS: accounts/tenancy/sales public schema; TENANT_APPS: menu',
  'per-tenant), DRF, Celery+Redis, Postgres; Vue 3 + Vite frontend. The fixes below come from a VERIFIED audit',
  '(PERF_HOSTING_AUDIT.md, in the repo) — line numbers are approximate, so confirm the real code before editing.',
  '',
  'PRODUCTION-SAFE RULES:',
  '- Change ONLY what the item specifies. Preserve behavior + API contracts + response shape exactly (these are',
  '  perf refactors, not feature changes). If a refactor would change output, keep the output identical.',
  '- Keep the existing test suite green. If your change adds/needs behavior, extend the relevant tests',
  '  (SimpleTestCase + mocks pattern; no real DB). Do not weaken assertions to pass.',
  '- For new DB indexes / model fields: edit the model, then RUN makemigrations for that app so a migration file',
  `  is generated (\`${BACKEND_MAKEMIG} <app>\`). Migrations must be additive/zero-downtime (indexes, nullable/`,
  '  defaulted fields). Never edit an existing migration.',
  '- Backend test/verify commands for THIS repo (git-bash):',
  `    tests:        ${BACKEND_TEST}     (GREEN = "N passed, 0 failed"; ~25 "errors" are Postgres-needing env`,
  '                  tests and are NOT regressions — ignore them. Only "failed" matters.)',
  `    check:        ${BACKEND_CHECK}`,
  `    makemig:      ${BACKEND_MAKEMIG} <app>   |   verify: ${BACKEND_MAKEMIG_CHECK}`,
  '- Do NOT run heavy parallel processes. One command at a time. Do NOT push or merge.',
].join('\n')

// ── The verified, lower-risk work items (sequential) ─────────────────────────
const ITEMS = [
  {
    key: 'conn-health',
    title: 'Enable CONN_HEALTH_CHECKS (prevent stale-connection 500s)',
    prompt: `In \`backend/config/settings.py\`, in DATABASES['default'] (around the conn_max_age config), add \`'CONN_HEALTH_CHECKS': True\` (Django 4.1+). One key. This makes Django ping a reused connection before use so a Postgres restart can't cause minutes of silent 500s. Confirm \`${BACKEND_CHECK}\` still passes.`,
  },
  {
    key: 'mktplace-batch',
    title: 'Marketplace: batch flash-sale lookups + dedupe filter extraction',
    prompt: `In \`backend/accounts/views.py\` MarketplaceView (and DirectoryView where the same pattern exists): (1) the per-tenant Python loop currently queries PlatformFlashSaleOptIn / PlatformFlashSale once PER tenant — instead, fetch them ONCE before the loop into a dict/set (e.g. opted_map = {...}, live_flash_sales = set(PlatformFlashSale.objects.filter(is_active=True).values_list(...))) and read from those inside the loop. (2) The cities/cuisines/tags filter lists are built via extra full-table Profile scans after the loop — instead derive them from the rows already fetched (the qs/results already in memory). Keep the response JSON byte-for-byte identical. Run the relevant tests (test_directory_marketplace_views.py if present) + \`${BACKEND_TEST}\` and keep 0 failed.`,
  },
  {
    key: 'admin-orders-ref',
    title: 'AdminCustomerOrdersView: use CustomerOrderRef instead of cross-schema scan',
    prompt: `In \`backend/accounts/views.py\` AdminCustomerOrdersView iterates up to 500 tenant schemas. Replace that with the denormalized CustomerOrderRef table exactly like CustomerMarketplaceOrdersView already does (CustomerOrderRef.objects.filter(customer_id=...).order_by('-order_created_at')[:N]). Keep the response shape identical. Mirror/extend the existing admin test if there is one. Keep \`${BACKEND_TEST}\` at 0 failed.`,
  },
  {
    key: 'driver-batch',
    title: 'DriverJobListView: batch order summaries by tenant (one schema switch each)',
    prompt: `In \`backend/accounts/views.py\` DriverJobListView, _job_order_summary currently does a Tenant lookup + schema_context switch PER job. Refactor so jobs are grouped by tenant_id; for each unique tenant switch context once and batch-fetch all needed orders (Order.objects.filter(order_number__in=[...])), then map back. Keep output identical. This endpoint is polled by every online driver. Keep \`${BACKEND_TEST}\` at 0 failed.`,
  },
  {
    key: 'profile-index',
    title: 'Profile partial composite index (marketplace predicate)',
    prompt: `In \`backend/tenancy/models.py\` Profile model, add a composite (ideally partial) index on the marketplace filter predicate, e.g. in Meta.indexes: models.Index(fields=['directory_opt_in','is_menu_published'], name='profile_marketplace_idx') (use a condition=Q(...) partial index if the codebase/Postgres supports it cleanly; otherwise a plain composite index). Then run \`${BACKEND_MAKEMIG} tenancy\` to generate the migration. Confirm \`${BACKEND_MAKEMIG_CHECK}\` reports no remaining changes.`,
  },
  {
    key: 'order-index',
    title: 'Order(status, updated_at) index (staff delta-poll)',
    prompt: `In \`backend/menu/models.py\` Order.Meta.indexes, add models.Index(fields=['status','updated_at']) (the staff ?since= delta-poll filters on updated_at, currently unindexed). Run \`${BACKEND_MAKEMIG} menu\` to generate the migration. Confirm \`${BACKEND_MAKEMIG_CHECK}\` shows no remaining changes.`,
  },
  {
    key: 'owner-orders-1q',
    title: 'OwnerOrderListView: one query instead of count()+slice',
    prompt: `In \`backend/menu/views.py\` OwnerOrderListView, replace the separate count() + slice (two queries per poll) with a single fetch: rows = list(qs[:201]); has_more = len(rows) > 200; rows = rows[:200]. Preserve the response (including whatever pagination/has_more field it returns). Keep \`${BACKEND_TEST}\` at 0 failed.`,
  },
  {
    key: 'anon-throttle',
    title: 'Anon throttles on public Marketplace/Directory endpoints',
    prompt: `In \`backend/accounts/views.py\`, add DRF throttling to MarketplaceView and DirectoryView (both AllowAny, currently unthrottled). Use the project's existing throttle approach — add throttle_classes (e.g. [AnonRateThrottle]) and, if the project defines named scopes in config/rest_framework or settings, add a scope at a sane rate (~100/min). Don't break existing tests; if tests hit these endpoints many times, ensure throttle config doesn't make them fail (use a scope so it's tunable, or confirm test client isn't rate-limited). Keep \`${BACKEND_TEST}\` at 0 failed.`,
  },
  {
    key: 'dockerfile-multistage',
    title: 'Backend Dockerfile: drop build-essential from runtime image',
    prompt: `In \`backend/Dockerfile\`, stop shipping build-essential in the final image. Prefer a two-stage build: a builder stage installs build-essential and runs \`pip wheel --no-deps -r requirements.txt -w /wheels\`; the runtime stage copies /wheels and \`pip install --no-index --find-links=/wheels -r requirements.txt\` with NO build toolchain. If a two-stage build is risky for any package that needs compilation at install, instead purge in the same RUN layer (\`&& apt-get purge -y build-essential && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*\`). Keep the runtime behavior/entrypoint identical. Also ensure \`backend/.dockerignore\` excludes tests/, .git, __pycache__, *.md (create/extend it). Do NOT run docker (can't build here) — just make the Dockerfile correct and minimal.`,
  },
]

const VERIFY_SCHEMA = {
  type: 'object',
  properties: {
    passed: { type: 'boolean' },
    gates: { type: 'array', items: { type: 'object', properties: { name: { type: 'string' }, passed: { type: 'boolean' }, output: { type: 'string' } }, required: ['name', 'passed'] } },
    failureSummary: { type: 'string' },
  },
  required: ['passed'],
}
const PREP_SCHEMA = { type: 'object', properties: { ok: { type: 'boolean' }, reason: { type: 'string' } }, required: ['ok', 'reason'] }

const VERIFY_PROMPT = `${CONTEXT}\n\n--- FULL VERIFICATION GATE ---\nWorking dir = repo root. Run, in order, and capture each:\n1. Backend tests: \`${BACKEND_TEST}\`  → GREEN = "0 failed" (ignore the ~25 Postgres env "errors").\n2. Backend system check: \`${BACKEND_CHECK}\`\n3. Migrations complete: \`${BACKEND_MAKEMIG_CHECK}\`  → GREEN = "No changes detected".\n4. Frontend (from frontend/): \`npm run verify:i18n\` , \`npm run lint\` , \`npm run build\` , \`npm test\`.\nReturn passed=true ONLY if backend has 0 failed AND check passes AND no missing migrations AND all 4 frontend gates pass. Include each gate's name/passed/output-tail and a concise failureSummary. Do NOT modify files — report only.`

// ── Prep ─────────────────────────────────────────────────────────────────────
phase('Prep')
const prep = await agent(
  `Prepare branch ${BRANCH} for an implementation run (repo root). 1) \`git status --porcelain\`: if dirty with anything OUTSIDE .claude/, return ok=false listing it. 2) Ensure on a clean ${BRANCH} branched from main: if it exists check it out, else \`git checkout -b ${BRANCH}\` from main (\`git checkout main\` first). 3) Confirm with rev-parse + \`git log --oneline -1\`. Return ok=true with the branch HEAD. Do NOT commit/push.`,
  { phase: 'Prep', label: 'prep', schema: PREP_SCHEMA },
)
if (!prep || !prep.ok) { log(`⛔ Prep aborted: ${prep ? prep.reason : 'no result'}`); return { aborted: true, reason: prep ? prep.reason : 'prep failed' } }
log(`✅ Prep: ${prep.reason}`)

// ── Implement (sequential, per-item commit) ──────────────────────────────────
phase('Implement')
const results = []
for (let i = 0; i < ITEMS.length; i++) {
  const it = ITEMS[i]
  const n = i + 1
  let r
  try {
    r = await agent(
      `${CONTEXT}\n\n--- IMPLEMENT ITEM ${n}/${ITEMS.length}: ${it.title} ---\n${it.prompt}\n\nMake the change carefully and minimally, update/extend tests as needed, and confirm the relevant local check passes before finishing. Report exactly what you changed (files + summary) and the result of any check you ran.`,
      { model: 'sonnet', phase: 'Implement', label: `impl:${it.key}` },
    )
  } catch (e) { r = `ERROR: ${String(e).slice(0, 200)}` }
  results.push({ item: it.key, title: it.title, summary: String(r).slice(0, 500) })
  await agent(
    `On branch ${BRANCH}: \`git add -A\` then commit verbatim:\n\nperf: ${it.title}\n\n${COAUTHOR}\n\nIf nothing to commit, say so. Do NOT push. One-line result.`,
    { phase: 'Implement', model: 'sonnet', label: `commit:${it.key}` },
  )
  log(`✔ ${n}/${ITEMS.length} ${it.key}`)
}

// ── Verify (+ bounded fixer loop) ────────────────────────────────────────────
phase('Verify')
let verify = await agent(VERIFY_PROMPT, { phase: 'Verify', model: 'sonnet', label: 'verify#0', schema: VERIFY_SCHEMA })
let round = 0
while (verify && !verify.passed && round < MAX_FIX_ROUNDS) {
  round++
  const failed = (verify.gates || []).filter((g) => !g.passed).map((g) => g.name).join(', ') || 'unknown'
  log(`🔧 Verify failed (${failed}) — fix ${round}/${MAX_FIX_ROUNDS}`)
  await agent(
    `${CONTEXT}\n\nThe verification gate is failing after the perf-hardening changes. Fix the cause WITHOUT regressing behavior or weakening tests (these were perf refactors — restore exact behavior if a refactor broke something).\n\nFailing: ${failed}\n${(verify.gates || []).filter((g) => !g.passed).map((g) => `### ${g.name}\n${(g.output || '').slice(0, 2500)}`).join('\n\n')}\nSummary: ${verify.failureSummary || ''}\n\nEdit only what's needed; re-run the failing gate to confirm. Do NOT push/merge.`,
    { phase: 'Verify', model: 'sonnet', label: `fix#${round}` },
  )
  await agent(
    `On branch ${BRANCH}: \`git add -A\` and commit verbatim:\n\nperf: fix verification round ${round}\n\n${COAUTHOR}\n\nIf nothing to commit, say so. No push. One line.`,
    { phase: 'Verify', model: 'sonnet', label: `commit-fix#${round}` },
  )
  verify = await agent(VERIFY_PROMPT, { phase: 'Verify', model: 'sonnet', label: `verify#${round}`, schema: VERIFY_SCHEMA })
}
const green = !!(verify && verify.passed)
log(green ? '✅ All gates green.' : `❌ Not green after ${MAX_FIX_ROUNDS} rounds — see report.`)

// ── Report ───────────────────────────────────────────────────────────────────
phase('Report')
await agent(
  `Write \`PERF_HARDENING_REPORT.md\` (repo root, Write tool) then commit it. Summarize this implementation run.
Branch: ${BRANCH}. Final gate status: ${green ? 'ALL GREEN (backend 0 failed + check + migrations + frontend gates)' : 'NOT GREEN after ' + MAX_FIX_ROUNDS + ' rounds'}.
${green ? '' : 'Outstanding:\n' + JSON.stringify((verify && verify.gates) || [], null, 2).slice(0, 2500)}
Items implemented:
${results.map((r) => `- ${r.item}: ${r.title} — ${r.summary}`).join('\n').slice(0, 7000)}
Sections: what changed (per item, with new migrations listed), verification status, how to review (git diff main...${BRANCH}) and ship (review → merge → Coolify redeploy runs migrate_schemas), and what's deferred (Redis response cache + rating denormalization — to be done with dedicated tests). Then \`git add -A\` and commit verbatim:

perf-hardening: report + ${green ? 'gates green' : 'gates pending'}

${COAUTHOR}

Do NOT push or merge. Return a 5-line executive summary.`,
  { phase: 'Report', model: 'sonnet', label: 'report' },
)

return { branch: BRANCH, items: ITEMS.length, gatesGreen: green, report: 'PERF_HARDENING_REPORT.md', deferred: ['redis-response-cache', 'rating-denormalization'] }
