# ADR-0005: Hand-rolled i18n runtime with a dual-source catalog

- **Status:** **Superseded (2026-07-24)** — the dual source was collapsed. `messages.js` (the redundant
  inline en+fr catalog read only by the gates) was **deleted**; both verify gates now read the same
  runtime files (`messages-en.js` / `messages-fr.js` / `messages-ar.js`). One source per locale. See the
  "Resolution" section below and [FE-1](../RISK_REGISTER.md).
- **Date:** documented 2026-07-10; resolved 2026-07-24
- **Related risk:** [FE-1](../RISK_REGISTER.md) (resolved), [FE-3](../RISK_REGISTER.md)

## Context
Kepoli ships in English, French, and **Arabic (RTL)**. It needs runtime locale switching, a way
to guarantee Arabic completeness, and build-time gates that catch missing/misused keys.

> **Correction to older docs:** several root docs and `CLAUDE.md` describe the frontend as using
> **vue-i18n**. It does **not**. The runtime is a **hand-rolled `composables/useI18n.js`** over the
> `src/i18n/` catalogs. Treat this ADR as authoritative.

## Decision
A hand-rolled i18n runtime with a **dual-source** catalog and two verify gates:
- `messages.js` — inline `en` + inline `fr` in one file. **This is the runtime source** for EN/FR
  and is read by both the FR-parity gate and the key-usage gate. FR text is ASCII-only by
  convention (avoids mojibake).
- `messages-ar.js` — real Arabic (runtime AR = clone-of-en + these overrides).
- `messages-en.js` — the AR-parity source (what Arabic is checked for completeness against).
- Gates: `verify-i18n.mjs` (Arabic completeness/mojibake) + `verify-i18n-usage.mjs` (every
  `t('...')` key used in templates exists).

## Consequences

### Good
- Full control, no external i18n dependency; RTL/Arabic is first-class and actually adopted.
- The two gates genuinely catch missing Arabic and unused/misspelled keys in CI.

### Bad / honest tradeoffs
- **A single new string requires FOUR coordinated edits** — `messages.js` inline `en` **and**
  inline `fr`, plus `messages-ar.js`, plus `messages-en.js`. Edit only some and you pass one gate
  but fail the other (or ship raw keys at runtime). This has already bitten this project. (FE-1)
- **~500KB of locale data loads up front**, blocking first paint — worst for the Arabic visitor
  the RTL support is *for*. (FE-3)
- Two representations of "English" (`messages.js` inline en + `messages-en.js`) that must be kept
  in lockstep by hand.

## Alternatives considered
- **A single keyed catalog per locale** (`en.json`/`fr.json`/`ar.json`), with the parity files
  *generated* from one source instead of hand-maintained. One edit per string; gates run against
  the generated artifacts. This is the recommended target.
- **Adopt vue-i18n** for lazy per-namespace catalogs and pluralization — more standard, but a
  larger migration; the single-source cleanup captures most of the value at less cost.

## When to revisit
Largely settled. Lazy per-namespace/route splitting for further first-paint wins (FE-3) is the only
remaining thread; the single-source cleanup (FE-1) is done.

## Resolution (2026-07-24) — FE-1
FE-3's earlier code-split had already moved the **runtime** onto `messages-en.js` / `messages-fr.js` /
`messages-ar.js`, which left `messages.js` (11,776 lines) as pure duplication read **only by the two
verify gates** — the hand-sync source of the drift. That drift had already produced **live raw-key bugs**
(template keys under `mktMenu.*` / `customerAccount.*` that existed in `messages.js` but only under a
*different* namespace — `cartPage.*` / `menu.*` — in the runtime files, so they rendered as raw keys). The fix:
- reconciled the ~7 drifted keys into the runtime files under the namespace the templates use (bug fix);
- repointed **both** gates to the runtime files (FR-parity = `messages-en.js` vs `messages-fr.js`; the
  usage gate reads `messages-en.js`; the mojibake scan covers the real files);
- **deleted `messages.js`.**

Result: **one source of truth per locale**, each consumed by both runtime and gates. A new string is
**3 edits** (en/fr/ar — the irreducible one-per-language minimum), and a key that passes the gates is the
key the runtime ships. The ADR's old "generate parity files from one source" idea is moot — `messages-en.js`
*is* the parity source directly, no codegen needed. The four-edit rule in `CLAUDE.md` is retired.
