# Launch Closure Plan
## Goal
Close the remaining production gaps for the `basic` tier before expanding features, UI polish, or higher tiers.

This plan is intentionally strict. It is not a backlog of ideas. It is the minimum execution sequence required to move from "working SaaS" to "sellable and supportable production system".

## Current Position
The platform already has:
- public platform host
- admin platform host
- tenant wildcard routing
- lead capture and provisioning
- activation and owner onboarding
- menu publish flow
- owner workspace
- customer menu/cart/reservation flow
- admin operations

What remains is mostly:
- production validation
- operational hardening
- support readiness

## Phase 1 - Production Validation Closure
This phase must be completed first.

### 1. First Real Tenant Full Smoke
Use:
- [First_Tenant_Production_QA.md](C:\Users\user\resto\First_Tenant_Production_QA.md)
- [Kepoli_Production_Smoke_Execution.md](C:\Users\user\resto\Kepoli_Production_Smoke_Execution.md)

Required outcome:
- one tenant fully validated from lead to published menu
- no blocking issues in:
  - admin provisioning
  - owner activation
  - owner onboarding
  - owner dashboard
  - public tenant pages
  - customer cart/reservation flow

Evidence to record:
- tenant slug
- timestamp
- smoke script output
- screenshots for key milestones
- issues found and fixed

### 2. Production Email Delivery Verification
Use:
- [infra/COOLIFY_EMAIL_VERIFICATION.md](C:\Users\user\resto\infra\COOLIFY_EMAIL_VERIFICATION.md)

Must complete:
- configure real SMTP/API provider
- verify SPF
- verify DKIM
- verify DMARC
- verify activation email end-to-end
- verify password reset email end-to-end

Required outcome:
- production mail delivery is reliable enough for onboarding and recovery

### 3. Restore Drill Evidence
Use:
- backup/restore scripts already in `infra/coolify`

Must complete:
- execute one real restore drill on production backup material
- record:
  - backup file used
  - timestamp
  - restore target
  - post-restore validation endpoints

Required outcome:
- restore process is proven, not assumed

## Phase 2 - Wildcard and Operations Hardening
This phase makes the deployment supportable after first sales.

### 1. Wildcard Tenant Proxy Hardening
Current state:
- wildcard routing works
- current implementation is operational but fragile

Must complete:
- replace ad-hoc target dependency with a stable forwarding strategy
- update runbook with exact current working configuration
- verify wildcard routing still survives redeploy/restart

Required outcome:
- `*.menu.kepoli.com` remains stable across routine operations

### 2. Deploy/Recovery Discipline
Use:
- [infra/DEPLOYMENT_RUNBOOK.md](C:\Users\user\resto\infra\DEPLOYMENT_RUNBOOK.md)
- [Release_Candidate_Freeze.md](C:\Users\user\resto\Release_Candidate_Freeze.md)

Must complete:
- freeze a release candidate checkpoint
- record exact working deploy inputs
- record exact rollback checkpoint

Required outcome:
- no future deployment depends on memory or trial-and-error

### 3. Monitoring Confirmation
Must complete:
- confirm uptime checks are working
- confirm alert webhook is working
- confirm security/throttle monitoring is active
- confirm Sentry captures at least one backend and one frontend event in production

Required outcome:
- production failures become observable within minutes, not discovered by customers

## Phase 3 - Product Surface Cleanup
This phase is still pre-expansion work. It is about making the current app cleaner and easier to support.

### 1. Owner Workspace Cleanup
Focus:
- dashboard responsiveness
- menu builder stability
- tables and reservations consistency
- reduce unnecessary background requests

Required outcome:
- owner workspace remains fast and predictable after login and during normal actions

### 2. Admin Console Cleanup
Focus:
- further split overloaded operational modules if needed
- keep provisioning flow always responsive
- isolate optional monitoring/flags/audit surfaces from core provisioning flow

Required outcome:
- admin can provision, resend, inspect packages, and manage tenants without UI stalls

### 3. Customer Flow Final QA
Focus:
- menu browse
- dish detail
- cart
- reservation
- table QR context
- WhatsApp handoff

Required outcome:
- the `basic` tier customer flow is fully stable on mobile

## Phase 4 - Only Then Move Forward
Only after Phases 1-3 are complete should work continue on:
- deeper i18n content support
- more UI polish
- S3/object storage migration
- Growth tier
- Pro tier
- payments

## Execution Rule
Do not start new feature work while any of these are incomplete:
- first full tenant smoke
- real production email delivery
- restore drill evidence
- wildcard hardening

## Practical Next Order
1. Re-run first tenant production QA on the current live stack
2. Complete live email provider setup and verification
3. Execute and document one restore drill
4. Harden wildcard tenant proxy operations
5. Do a focused owner/admin cleanup pass
6. Re-run final production smoke
7. Freeze release candidate
