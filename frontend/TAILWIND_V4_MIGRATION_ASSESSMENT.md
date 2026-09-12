# Tailwind CSS v3 → v4 migration assessment

Read-only assessment for Dependabot **#154** (`tailwindcss` 3.4.13 → 4.3.3). No code was
changed. Grounded in this repo's actual Tailwind usage (surveyed 2026-09-12) + the official
[v4 upgrade guide](https://tailwindcss.com/docs/upgrade-guide).

## TL;DR / verdict

The migration is **mechanically cheap** — Tailwind's codemod (`npx @tailwindcss/upgrade`)
automates the bulk of it, and this codebase is unusually well-positioned (no Sass/preprocessor,
explicit utility sizes, `[var(--x)]` arbitrary values rather than the shorthand that v4 broke,
CSS-custom-property theming that is independent of Tailwind's config). Realistic code effort:
**~0.5–1 day**, most of which is diff review — plus the real cost, **thorough visual QA** across
every surface (no local render here).

**But the deciding factor is not effort — it's browser support.** Tailwind v4 hard-drops
pre-2023 browsers (Safari 16.4+, Chrome 111+, Firefox 128+; it depends on `@property` and
`color-mix()`, which degrade *badly*, not gracefully). For a Morocco-market consumer
food-ordering app running on whatever phone a customer has, that is a **reach risk**, not a code
risk — and v4 buys us **no feature we currently need** (it's faster builds + smaller CSS).

**Recommendation: defer** until one of these is true:
1. Your consumer-traffic **browser analytics** (pull from Sentry — `@sentry/vue` is already wired
   and records browser/OS) show the user base is overwhelmingly on Safari 16.4+ / Chrome 111+
   (≈ mid-2023-or-newer devices); **or**
2. There's a concrete trigger — Tailwind v3 reaching EOL, or a v4-only capability we actually want.

It is cheap to re-run this assessment and the codemod whenever that changes. Nothing about staying
on v3.4.13 is costing us today (it's current within the v3 line, no known CVE gate it on `main`).

---

## Compatibility prerequisites — all MET

| Prereq | v4 needs | This repo | OK |
|--------|----------|-----------|----|
| Node | ≥ 20 (codemod + build) | CI/build on Node 22 | ✅ |
| Vite | recent (for `@tailwindcss/vite`) | Vite 8.2.2 | ✅ |
| No CSS preprocessor | v4 drops Sass/Less/Stylus support | plain CSS (`src/styles/tailwind.css`) | ✅ |

## The decision input: browser support (HIGH — product, not code)

> "Tailwind CSS v4.0 is designed for Safari 16.4+, Chrome 111+, and Firefox 128+. If you need to
> support older browsers, stick with v3.4." — official upgrade guide

- Safari 16.4 = **iOS 16.4+** (March 2023). Chrome 111 = March 2023.
- This is **hard breakage** on older browsers (core relies on `@property`/`color-mix()`), not a
  progressive-enhancement fallback — an old phone would render the app visibly broken.
- **Action before any go decision:** pull the browser/OS distribution of *consumer* (storefront +
  marketplace) traffic from Sentry and confirm the long tail of pre-2023 browsers is negligible.
  If a meaningful slice of customers are on old Android/iOS, **do not migrate.**

---

## Migration scope (when it's scheduled)

### A. Automated by `npx @tailwindcss/upgrade` (codemod)
- **Renamed utilities** — confirmed occurrences in `src/` (the codemod rewrites all of these):
  - `outline-none` → `outline-hidden`: **~357** (almost all `focus-visible:outline-none`)
  - `blur-sm` / `backdrop-blur-sm` → `blur-xs` / `backdrop-blur-xs`: **~64**
  - `shadow-sm` → `shadow-xs`: **~18**
  - `rounded-sm` → `rounded-xs`: **~16**
  - bare `rounded` → `rounded-sm`: **~212**
  - bare `ring` → `ring-3` (default ring width changed 3px → 1px): **~12**
  - bare `shadow` → `shadow-sm`: **~4**
- `flex-shrink-*` → `shrink-*`: **~15** (and `flex-grow-*` → `grow-*`: 0 present)
- `@tailwind base/components/utilities` → `@import "tailwindcss"`.
- JS config migrated to CSS (or kept via `@config`).
- `!`-important modifier moves to the end (`!mt-0` → `mt-0!`). Note: a raw grep can't separate
  Tailwind's `!` from JavaScript negation (`v-if="!x"`), so trust the codemod here rather than a
  count.

### B. Required manual changes (codemod may assist — verify each)
1. **Safelist → `@source inline()`** (easy to miss, real breakage if missed). v4 **drops** the JS
   `safelist` option entirely. The current config safelists `grid-cols-(3|4|5|6)`, which protects
   **dynamically-composed** grid classes built via `:class` ternaries/template-literals in
   `WaiterShiftPanel.vue`, `Cart.vue`, `OwnerLayout.vue`, `OwnerBilling.vue`,
   `OwnerDashboardRevenue.vue`. Replace with `@source inline("grid-cols-{3,4,5,6}")` (or equivalent)
   or those columns get purged → broken multi-column layouts that **won't show up in a quick smoke
   test** (only when that conditional branch renders).
2. **Three `.vue` `<style>` blocks use `@apply`** — `AdminConsole.vue`, `Cart.vue`,
   `MarketplaceMenuPage.vue`. In v4 a `<style>` block has no implicit theme access; add
   `@reference "../styles/tailwind.css"` to each (or convert those few rules to `var(--…)`).
3. **PostCSS → Vite plugin.** Replace the `postcss.config.js` `{ tailwindcss, autoprefixer }` with
   the dedicated `@tailwindcss/vite` plugin in `vite.config.js` (recommended for Vite). **Remove
   `autoprefixer`** (bundled in v4) and drop `tailwindcss` as a PostCSS plugin. `postcss.config.js`
   likely becomes empty/removable (no other PostCSS plugins in use).
4. **Config extensions** (`theme.extend.fontFamily` display/body with the Arabic fallback;
   `colors.brand.{primary,secondary,surface}`). Keep via `@config "./tailwind.config.js"` for a
   low-touch move, or migrate into `@theme { }`. Note the existing comment says `colors.brand` is
   hardcoded hex *"because /opacity syntax requires a literal color"* — in v4 the opacity syntax
   uses `color-mix()` and works with CSS-var colors too, so that constraint relaxes (optional
   cleanup, not required).

### C. No change needed (verified)
- **`[var(--x)]` arbitrary values: ~812 occurrences** — the explicit `var()` form still works in
  v4. (v4 only broke the `[--x]` *shorthand*, of which this repo has **0**.)
- **~102 `@apply` in `src/styles/tailwind.css`** (the `ui-*` design system, inside `@layer
  components`) — same file as `@import "tailwindcss"`, so they keep theme access. `@layer
  components` + `@apply` still works; **0** uses of `@layer utilities` (which would have needed the
  new `@utility` directive).
- **CSS custom properties** in `:root` (`--color-*`, `--motion-*`, …) are plain CSS, unaffected.

---

## Effort & risk

| Item | Effort | Risk |
|------|--------|------|
| Codemod renames (~680 edits) | minutes (automated) | LOW — review diff |
| Safelist → `@source inline` | minutes | **MED** — silent purge of dynamic `grid-cols` if missed |
| 3 `@apply` `.vue` files → `@reference` | minutes | LOW |
| PostCSS → Vite plugin, drop autoprefixer | minutes | LOW (CI build catches) |
| **Visual QA across every surface** | **the bulk** | **MED** — the 102-`@apply` `ui-*` system, dark mode, RTL/Arabic, 390px, focus rings (width shift) must be eyeballed; no local render here |
| **Browser-support reach** | n/a | **HIGH — product decision** (see above) |

## Recommended procedure (when scheduled)
1. Branch; `npx @tailwindcss/upgrade` (Node ≥ 20).
2. Apply the manual B-items (safelist, 3 `@apply` files, Vite plugin, config).
3. Review the full diff; `npm run lint` + `npm run build` + `npm run test` green.
4. **Deploy to staging and visually QA every surface** — customer storefront + marketplace, owner,
   waiter, admin; dark mode; Arabic/RTL; 390px; focus-visible rings. This is the real gate (the
   codemod's correctness is only provable by eye).
5. Merge. Rollback = revert the branch (it's a closed frontend-only change; no data/migration).

## Bottom line
Low code-effort, well-prepared codebase, **but gated on consumer browser reach and offering no
functional benefit today.** Defer #154 until the browser-analytics check clears or a concrete
trigger appears; this doc + the codemod make the eventual migration a short, low-surprise task.
