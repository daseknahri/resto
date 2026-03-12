# Release Candidate Freeze
## Snapshot
- Date: 2026-03-10
- Scope: v1 SaaS baseline for Basic tier launch
- Interfaces covered: public landing, customer flow, owner workspace, platform admin
- Deployment target: Coolify + wildcard tenant subdomains

## Verified Baseline
The following checks were rerun and passed against the current repository state:

- Backend system check
  - Command: `cd backend && .\.venv\Scripts\python.exe manage.py check`
  - Result: `System check identified no issues (0 silenced).`

- Migration drift check
  - Command: `cd backend && .\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run`
  - Result: `No changes detected`

- Backend test suite
  - Command: `cd backend && ..\backend\.venv\Scripts\python.exe manage.py test tests -v 1`
  - Result: `Found 179 test(s)` -> `OK`
  - Note: test output includes expected security/provisioning log lines from observability coverage.

- Frontend lint
  - Command: `cd frontend && npm run lint`
  - Result: pass

- Frontend production build
  - Command: `cd frontend && npm run build`
  - Result: pass

## Product State
The codebase is no longer missing core v1 product surfaces.

Built and connected:
- Public landing and lead capture
- Customer 4-page flow: info, browse, cart, reserve
- Owner workspace: dashboard, onboarding, tables, reservations, launch
- Platform admin console: leads, provisioning, lifecycle, audit, reservation alerts, upgrade decisions
- Host-based tenant resolution for production subdomains
- Basic-tier ordering path via WhatsApp handoff
- I18n foundation and localized runtime messaging

## Current Launch Blockers
These items should be closed before treating the product as sales-ready production:

1. Real transactional email delivery
- Live provider credentials still need to be configured
- SPF/DKIM/DMARC must be verified on the real sending domain
- Activation and reset emails must be validated end-to-end in production

2. First production restore drill evidence
- Backup/restore tooling exists
- A real documented restore drill result is still missing

3. First real production tenant smoke
- Run the exact end-to-end operator flow on live domains:
  - lead submission
  - admin provision
  - activation
  - owner onboarding
  - publish
  - tenant menu open on `slug.kepoli.com`

4. Release checkpoint discipline
- The repository is intentionally still in a large working state from active product build-out
- Freeze should happen by cutting a release branch/tag from the verified state, not by manually cleaning unrelated history

## Non-Blocking After Launch
These can continue after first sales without weakening the Basic tier launch:

- Deeper multilingual content expansion
- Additional mobile/UI polish passes
- S3/object-storage media migration
- Growth/Pro tier implementation
- Payment integration
- Threshold tuning for alerting and Sentry noise control

## Recommended Freeze Procedure
1. Freeze feature work temporarily.
2. Re-run:
   - Windows: `powershell -ExecutionPolicy Bypass -File .\infra\release_candidate_freeze.ps1`
   - Linux/macOS: `bash ./infra/release_candidate_freeze.sh`
3. Run manual checks in:
   - `Pre_Deployment_QA_Checklist.md`
   - `First_Tenant_Production_QA.md`
4. Confirm production email delivery.
5. Confirm backup restore drill evidence.
6. Cut release branch/tag.
7. Deploy using `infra/DEPLOYMENT_RUNBOOK.md`.

## Decision
Current state is suitable for release-candidate freeze for the Basic tier.

It is not yet fully release-approved until:
- live email delivery is verified
- first production restore drill is documented
- first real tenant smoke is executed on production domains
