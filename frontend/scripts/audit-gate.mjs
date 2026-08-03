#!/usr/bin/env node
// CI dependency-audit gate for the frontend tree (R6).
//
// Wraps `npm audit` so we can DEFER a single, documented, dev-only advisory
// that has no viable in-range fix — WITHOUT weakening the gate for anything
// else. Any moderate-or-higher advisory whose GHSA id is NOT in ALLOWLIST
// fails the build, exactly like the old `npm audit --audit-level=moderate`.
//
// This is the npm-audit equivalent of pip-audit's `--ignore-vuln` and Trivy's
// `.trivyignore` (npm audit has no native per-advisory ignore). Keep the
// ALLOWLIST here in lockstep with the repo-root `.trivyignore`. Only ever add
// an entry that is (a) dev/build-tooling only — never in the shipped bundle —
// and (b) genuinely unfixable in range, each with a written justification.
// Never blanket-disable.

import { execSync } from 'node:child_process'

// GHSA id -> justification. Every deferral MUST be dev/build-tooling only.
const ALLOWLIST = {
  'GHSA-mh99-v99m-4gvg':
    'brace-expansion OOM DoS (CVE-2026-14257). Present only in build/lint/test ' +
    'tooling (eslint, glob, minimatch, workbox-build, vitest js-beautify) — never ' +
    'in the shipped bundle, and only ever expands our own source globs, never ' +
    'untrusted input. Fixed only in brace-expansion 5.0.8, whose named-export ' +
    "shape breaks minimatch 3.x (eslint's) with `expand is not a function`, and " +
    "npm's only alternative is downgrading eslint a major — no in-range fix. " +
    'Mirrored in .trivyignore.',
  'GHSA-rgw5-rvv9-x895':
    'brace-expansion DoS via unbounded intermediate arrays — a follow-up advisory ' +
    'that bypasses the CVE-2026-14257 / 5.0.8 mitigation. SAME dev/build-tooling-only ' +
    'package and usage as GHSA-mh99-v99m-4gvg above: never in the shipped bundle, only ' +
    'ever expands our own source globs, never untrusted input. Still no in-range fix — ' +
    "any patched brace-expansion breaks eslint's minimatch 3.x the same way, and eslint " +
    '9 cannot be bumped to unbind it (eslint-plugin-vue 9.29.0 peer-caps eslint at 9). ' +
    'Mirrored in .trivyignore. Revisit when the eslint/minimatch chain ships a patched ' +
    'brace-expansion in range.',
}

// Match the old gate: fail on moderate and above (low stays informational).
const BLOCKING = new Set(['moderate', 'high', 'critical'])

function runAudit() {
  try {
    const out = execSync('npm audit --json', {
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
    })
    return JSON.parse(out)
  } catch (err) {
    // npm audit exits non-zero when vulnerabilities exist; the JSON report is
    // still written to stdout, so parse that rather than treating it as fatal.
    if (err.stdout) return JSON.parse(err.stdout)
    throw err
  }
}

const report = runAudit()
const vulns = report.vulnerabilities || {}

const offenders = []
const seenAllowed = new Set()

for (const [name, entry] of Object.entries(vulns)) {
  if (!BLOCKING.has(entry.severity)) continue
  // `via` holds either package-name strings (transitive dependents) or the
  // source advisory objects (the package that actually carries the CVE). Only
  // the objects have a GHSA url — dependents inherit and are accepted once
  // their root advisory is deferred.
  const advisories = (entry.via || []).filter((v) => v && typeof v === 'object' && v.url)
  for (const adv of advisories) {
    const ghsa = String(adv.url).split('/').pop()
    if (ALLOWLIST[ghsa]) {
      seenAllowed.add(ghsa)
    } else {
      offenders.push({ name, ghsa, title: adv.title || '', severity: adv.severity || entry.severity })
    }
  }
}

if (seenAllowed.size) {
  console.log('Deferred advisories (documented, dev-only, no in-range fix):')
  for (const ghsa of seenAllowed) console.log(`  - ${ghsa}: ${ALLOWLIST[ghsa]}`)
}

// Hygiene: flag allowlist entries that no longer match anything, so a stale
// deferral gets noticed (and removed) once the dependency is finally fixable.
const stale = Object.keys(ALLOWLIST).filter((g) => !seenAllowed.has(g))
if (stale.length) {
  console.log(`\nNote: allowlist entries no longer present in the tree (safe to remove): ${stale.join(', ')}`)
}

if (offenders.length) {
  console.error(`\n::error::npm audit gate: ${offenders.length} non-allowlisted moderate+ advisory(ies):`)
  for (const o of offenders) console.error(`  - ${o.name} [${o.severity}] ${o.ghsa} ${o.title}`)
  process.exit(1)
}

console.log('\nnpm audit gate: clean (no non-allowlisted moderate+ advisories).')
