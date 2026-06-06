# UI/UX Enhancement Guidelines — Per-File Agent Checklist

> **Audience:** Every per-file UI/UX agent in this enhancement pass.
> **Source of truth:** `frontend/src/styles/tailwind.css` (@layer components block) + `frontend/src/styles/UI_SYSTEM.md`.

---

## 1. Prime Directive

**Enhance presentation only. Never change behavior, logic, props, emits, API calls, router navigation, or store mutations.**

Specifically forbidden:
- Adding, removing, or renaming props or emits
- Changing v-model bindings or computed logic
- Touching `<script setup>` beyond adding/removing purely cosmetic CSS class strings
- Altering route targets, store dispatches, or fetch calls
- Changing i18n key names that already exist (only add new keys)

If a visual improvement requires a logic change, leave a `<!-- TODO: requires logic change -->` comment and skip it.

---

## 2. Enhancement Checklist

Work through every item before marking a file done.

### 2.1 Responsive / Overflow
- [ ] No horizontal scroll at 390 x 844 (iPhone 14 viewport). Confirm every row/table/scroll-area is contained.
- [ ] All flex/grid children that host horizontal scroll rows have `min-w-0` on the parent.
- [ ] Tables use `ui-table-wrap` with `min-w-*` on the table + `md:hidden` card fallback on mobile.
- [ ] Horizontal scroll rows use `ui-scroll-row` (never bare `overflow-x-auto` without `shrink-0` on children).
- [ ] Text that may overflow uses `truncate` or `min-w-0 flex-1`; never causes layout blowout.
- [ ] Page container sits inside `ui-page-shell` (max-w-6xl rhythm) or equivalent `mx-auto max-w-6xl px-4`.

### 2.2 Hierarchy & Spacing
- [ ] One `ui-display` headline per major section maximum.
- [ ] Every section that has a title also has a `ui-kicker` above it (uppercase tracking label).
- [ ] Spacing rhythm: sections separated by `space-y-3 sm:space-y-4`; internal card content uses `space-y-2` or `space-y-3`.
- [ ] Chip/metadata rows use `ui-chip` in a `flex flex-wrap gap-1.5` or `ui-scroll-row` — never bare inline text.
- [ ] Primary CTA per section is `ui-btn-primary`; secondary is `ui-btn-outline` or `ui-pill-nav`. One primary CTA per section.
- [ ] Header pattern: `ui-hero-ribbon` or `ui-workspace-stage` wrapping a `flex items-start justify-between` with kicker+title on the left, chip row on the right.

### 2.3 Accessibility (a11y)
- [ ] All interactive controls (buttons, links used as buttons) have accessible labels: `aria-label`, `aria-pressed`, or visible text.
- [ ] Icon-only buttons have `aria-label` or `<span class="sr-only">`.
- [ ] Form inputs are wrapped in `<label>` or have `aria-label` + `aria-describedby` pointing to error text.
- [ ] Error messages have `role="alert"` or `id` referenced by `aria-describedby`.
- [ ] Focus ring is visible on all interactive elements (ui-btn-primary, ui-btn-outline, ui-input, ui-textarea already include `focus-visible` rings — do not strip them).
- [ ] Toggle switches use `role="switch"` + `aria-checked`.
- [ ] Minimum tap target 44 px: add `ui-touch-target` to any button smaller than 44 px tall on mobile.
- [ ] Color alone never conveys state — always pair color with icon or text.

### 2.4 Three States: Loading / Empty / Error
Every data-driven section MUST render all three states explicitly:

**Loading:**
- Use `ui-skeleton` for card-shaped placeholders, or `animate-pulse` inline `div`s with approximate height.
- Never show a blank white rectangle or a raw spinner without context text.
- Pattern: `<div v-if="loading" class="ui-skeleton h-24" />`.

**Empty:**
- Use `ui-empty-state` wrapper with a brief heading + secondary text + optional CTA.
- Pattern: `<div v-else-if="!items.length" class="ui-empty-state text-center p-5 space-y-1">`.

**Error:**
- Render inline with `role="alert"`, red border (`border-red-500/30 bg-red-500/8`), icon, and message text.
- Never silently swallow errors or show only a console log.

### 2.5 Motion + Reduced-Motion
- [ ] Entry animations: use `ui-reveal` (preferred over raw `ui-fade-up`) on cards entering the viewport.
- [ ] Stagger lists: `:style="{ '--ui-delay': \`${Math.min(index, 9) * 28}ms\` }"` on list items with `ui-reveal`.
- [ ] Hover/press feedback: add `ui-surface-lift` to interactive cards; `ui-press` to small buttons.
- [ ] `prefers-reduced-motion` is already handled globally — do NOT add `!important` overrides or local media queries that conflict.
- [ ] Do NOT add `animate-spin` or `animate-bounce` that has no reduced-motion fallback.
- [ ] Keep motion meaningful: one animation per element, not stacked parallel transforms.

### 2.6 Dark Mode
The app is dark-only (`color-scheme: dark`). Do not add `dark:` variants. All palette work uses tokens or slate-* classes.

### 2.7 RTL Support
- [ ] Do not hardcode `left`/`right` margin/padding utility classes where RTL would break layout. Prefer `start`/`end` variants (`ms-*`, `me-*`, `ps-*`, `pe-*`) or `rtl:` prefixes for directional nudges.
- [ ] `ui-display`: Arabic RTL auto-switches to Noto Naskh Arabic — do not add custom font-family inline.
- [ ] `ui-kicker` / `ui-section-kicker`: letter-spacing and text-transform are reset to 0/none for RTL automatically — do not override.
- [ ] Accent bars (left-side color strips) should use `ltr:left-0 rtl:right-0` or `inset-y-0 start-0`.
- [ ] Horizontal scroll rows scroll in the natural inline direction — no forced `dir` attributes.

### 2.8 i18n Safety
See Section 6 for full rules. Quick checks:
- [ ] Zero hardcoded user-visible English strings in the template. Every string is `t('namespace.key')`.
- [ ] Dynamic keys use backtick template literals: `` t(`status.${status}`) ``.
- [ ] New keys are added to `messages.en` (EN), `messages.fr` (FR, ASCII no accents), and `messages-ar.js` (omit if unsure — English auto-falls-back).
- [ ] Reuse `common.*` keys for generic labels (save, cancel, close, remove, available, etc.).
- [ ] Numbers/prices use `formatPrice()` or `toLocaleString()` — never raw template concatenation.

### 2.9 Consistency
- [ ] Do not invent new card/panel variants — use the closest existing `ui-*` surface class.
- [ ] Do not add page-local button styles unless no primitive fits.
- [ ] `tabular-nums` on all numeric values that may change width (prices, counts, stats).
- [ ] Icon sizes: `h-3.5 w-3.5` inline, `h-4 w-4` in buttons, `h-5 w-5` standalone. Use `<AppIcon name="..." />`.

---

## 3. Quick-Reference: `ui-*` Class Catalog

Classes that exist in `tailwind.css` `@layer components`. Do not invent new `ui-*` names.

### Layout
| Class | Use for |
|---|---|
| `ui-shell` | Full-page root wrapper (`min-h-screen text-slate-50`) |
| `ui-header` | Sticky top header with blur + safe-area top |
| `ui-footer` | Page footer with standard rhythm |
| `ui-bottom-dock` | Fixed bottom bar (mobile nav / cart bar) with safe-area |
| `ui-bottom-dock-grid` | Inner grid inside `ui-bottom-dock` |
| `ui-page-shell` | Max-width content container (`mx-auto max-w-6xl px-4 py-6`) |
| `ui-safe-bottom` | Padding for content above a fixed bottom bar |
| `ui-divider` | Horizontal gradient rule between sections |
| `ui-scroll-row` | Horizontal pill/chip scroll row (flex, overflow-x-auto) |
| `ui-workspace-grid` | Two-column owner workspace layout |
| `ui-toolbar-grid` | Toolbar-row responsive grid |
| `ui-content-auto` | Long lists — skips off-screen rendering |

### Surface (cards / panels)
| Class | Use for |
|---|---|
| `ui-panel` | Standard card (rounded-2xl, border, bg-slate-900/55) |
| `ui-panel-soft` | Softer elevated card (rounded-3xl) |
| `ui-glass` | Premium glass-blur card with amber top shimmer |
| `ui-hero-stage` | Large hero section container |
| `ui-hero-ribbon` | Medium hero panel (page headers, Cart-style) |
| `ui-workspace-stage` | Owner workspace primary panel |
| `ui-command-deck` | Dark command/summary panel |
| `ui-section-band` | Inline feature/feature band inside a section |
| `ui-orbit-card` | Feature orbit card |
| `ui-metric-card` | Metric tile with left gradient accent bar |
| `ui-spotlight-card` | Highlight card with corner glow |
| `ui-stat-tile` | Individual stat tile |
| `ui-action-tile` | Action card with amber top edge |
| `ui-focus-card` | Focus/detail card |
| `ui-story-card` | Narrative/story card |
| `ui-admin-card` | Admin list card |
| `ui-admin-subcard` | Nested sub-card inside admin panels |
| `ui-reservation-card` | Reservation entry card |
| `ui-checklist-card` | Checklist item card (supports `data-complete`, `data-warning`) |
| `ui-readiness-item` | Readiness checklist row |
| `ui-selection-card` | Selectable option card (supports `data-active`, `data-warning`) |
| `ui-journey-rail` | Multi-step journey container |
| `ui-journey-step` | Individual step inside a journey rail |
| `ui-context-band` | Contextual info band |
| `ui-state-strip` | State/status strip |
| `ui-toolbar-band` | Toolbar container band |
| `ui-table-wrap` | Horizontal-safe table shell (overflow-x-auto) |
| `ui-auth-page` | Auth page background |
| `ui-auth-card` | Auth form card |
| `ui-auth-stage` | Auth page two-column layout |
| `ui-auth-spotlight` | Auth right-column spotlight (hidden on mobile) |

### Form
| Class | Use for |
|---|---|
| `ui-input` | Text input (full-width, focus ring, dark bg) |
| `ui-textarea` | Textarea (same as ui-input) |
| `ui-touch-target` | Enforces 44 px min-height on any interactive element |

### Action / Navigation
| Class | Use for |
|---|---|
| `ui-btn-primary` | Primary CTA (amber background, one per section) |
| `ui-btn-outline` | Secondary/ghost button |
| `ui-pill-nav` | Navigation pill (router-link-active aware) |
| `ui-chip` | Metadata chip / tag (router-link-active aware) |
| `ui-chip-strong` | Emphasized chip (amber border, used for badges) |
| `ui-top-link` | Header navigation text link |

### Data / Status
| Class | Use for |
|---|---|
| `ui-skeleton` | Loading placeholder (shimmer animation) |
| `ui-empty-state` | Empty-state container (rounded, glass-light bg) |
| `ui-status-pill` | Status badge pill |
| `ui-live-dot` | Pulsing live indicator dot |
| `ui-state-chip` | Filterable state chip (supports `data-active`) |
| `ui-segmented` | Segmented control container |
| `ui-segmented-button` | Individual segment (supports `data-active`) |
| `ui-stat-tile` | Standalone stat tile |
| `ui-stat-label` | `text-[11px] uppercase tracking text-slate-500` |
| `ui-stat-value` | `text-2xl font-semibold text-white` |
| `ui-stat-note` | `text-xs text-slate-400` below a stat value |
| `ui-context-stat` | Small contextual stat box |
| `ui-data-strip` | Inline data strip pill |
| `ui-route-badge` | Small uppercase route/category badge |
| `ui-step-badge` | Numbered step badge (amber) |
| `ui-readiness-dot` | Dot inside a readiness item |
| `ui-journey-progress` | Progress bar container |
| `ui-cart-bar` | Floating cart bottom bar |
| `ui-dish-bar` | Dish detail sticky bottom bar |
| `ui-qty-control` | Quantity stepper control |
| `ui-share-btn` | Share icon button |
| `ui-nav-item-inactive` | Inactive bottom nav item |
| `ui-menu-category-nav` | Sticky category nav bar (menu page) |

### Typography
| Class | Use for |
|---|---|
| `ui-display` | Premium serif display headline (Fraunces / Noto Naskh Arabic in RTL) |
| `ui-page-title` | Page h1 (`text-3xl font-semibold tracking-tight`, responsive) |
| `ui-kicker` / `ui-section-kicker` | Uppercase section eyebrow label above a title |
| `ui-subtle` | Secondary body text (`text-sm text-slate-300`) |

### Motion / Transition
| Class | Use for |
|---|---|
| `ui-fade-up` | One-shot entry animation (opacity + translateY) |
| `ui-reveal` | Entry animation respecting `--ui-delay` CSS var for stagger |
| `ui-surface-lift` | Hover lift transition on interactive cards |
| `ui-press` | Scale-down on `:active` for small buttons |
| `ui-fade-enter-active` / `ui-fade-leave-active` | Vue `<Transition name="ui-fade">` classes |

---

## 4. Design Tokens

All defined in `:root` in `tailwind.css`. Use these instead of hardcoding new hex values.

| Token | Value | Use for |
|---|---|---|
| `--color-primary` | `#0f766e` (teal) | Primary brand accents |
| `--color-secondary` | `#f59e0b` (amber) | CTAs, active states, highlights |
| `--color-surface` | `#0d1722` | Base surface color |
| `--color-elevated` | `#0f1d2b` | Raised surface |
| `--color-border` | `rgba(148,163,184,0.24)` | Standard border |
| `--color-text` | `#e2e8f0` | Body text |
| `--motion-fast` | `180ms` | Quick micro-interactions |
| `--motion-base` | `260ms` | Standard transitions |
| `--motion-slow` | `360ms` | Deliberate / progress transitions |
| `--ease-fluid` | `cubic-bezier(0.22,1,0.36,1)` | All card/button easing |
| `--safe-top` | `env(safe-area-inset-top, 0px)` | iOS status bar clearance |
| `--safe-bottom` | `env(safe-area-inset-bottom, 0px)` | iOS home indicator clearance |

**Rule:** Reference tokens with `var(--color-secondary)` in inline styles or CSS; in Tailwind use `text-[var(--color-secondary)]`. Never add new raw hex values in component files.

---

## 5. RTL / Dark-Mode Rules (Summary)

- **Dark-only app.** Do not add `dark:` prefixes.
- **RTL font swap** is automatic via `html[lang="ar"]` selector — do not override font-family.
- **Letter-spacing / text-transform** on kickers reset automatically for RTL — do not add `rtl:tracking-normal`.
- **Directional spacing:** use `ms-*`/`me-*` instead of `ml-*`/`mr-*` where direction matters.
- **Accent bars** (left-edge color strips): use `ltr:left-0 rtl:right-0 inset-y-0` or `start-0`.
- **Absolute-positioned decorations** that are left/right specific: add `rtl:` mirror variant.
- **Icons with directional meaning** (arrows, chevrons): apply `rtl:scale-x-[-1]`.
- **`ui-scroll-row`** scrolls in inline-start direction automatically — no forced `dir`.

---

## 6. i18n Rules

### Must-Follow Rules
1. **Zero hardcoded user-visible strings in templates.** Every string goes through `t('namespace.key')`.
2. **Gate-enforced:** every `t('a.b')` call must have a matching entry in `messages.en`. The `verify:i18n` lint gate will fail the build otherwise.
3. **Add all three locales** when adding a new key:
   - `messages.en` — English (canonical, required)
   - `messages.fr` — French translation, **ASCII only, no accented characters** (match existing entry style)
   - `messages-ar.js` — Arabic. **If unsure of the translation, omit the key entirely** — vue-i18n falls back to English automatically.
4. **Reuse `common.*` keys** for generic labels: `common.save`, `common.cancel`, `common.close`, `common.remove`, `common.available`, `common.plan`, `common.demo`, `common.soon`, etc.
5. **Dynamic keys** use backtick template literals: `` t(`status.${order.status}`) `` — never string concatenation.
6. **Pluralization** uses vue-i18n plural syntax: `t('cart.items', count)` with `| 0 items | 1 item | {count} items` in the message string.
7. **Numbers and prices** go through `formatPrice()` or `Number.toLocaleString()` — never embed raw numbers in translated strings unless using i18n named params: `t('cart.total', { amount: formatPrice(total) })`.
8. **Namespace convention:** `pageNameCamelCase.keyName` for page-specific keys; `common.keyName` for shared; `ownerXxx.keyName` for owner pages.

---

## 7. Lint / Build Constraints

Before marking a file complete, these gates must pass:

| Gate | Command | Constraint |
|---|---|---|
| ESLint | `npm run lint` | `--max-warnings=0` — zero warnings allowed |
| Prettier | `npm run format:check` | All files must be Prettier-formatted |
| i18n | `npm run verify:i18n` | Every `t('a.b')` must exist in `messages.en` |
| Type check | `npm run type-check` | No TypeScript/Vue template errors |
| Build | `npm run build` | Vite production build must succeed with no errors |
| Unit tests | `npm run test` | 75 passing tests must remain green |

**Never add `// eslint-disable` comments** unless the existing codebase already uses one for the same rule in the same file.

---

## 8. QA Gate (from UI_SYSTEM §9)

Run these checks manually or via e2e before closing a file:

1. **No horizontal overflow at 390 x 844.** Open DevTools, set viewport to iPhone 14, scroll every section. No scrollbar on `<body>`.
2. **All three states render correctly:** loading skeleton, empty state with CTA, error with `role="alert"`.
3. **Reduced-motion:** toggle OS "Reduce Motion". Interactions must still work; no layout shifts caused by removed animations.
4. **One primary CTA per section.** Count `ui-btn-primary` instances per logical section — max one. All others must be `ui-btn-outline` or `ui-pill-nav`.
5. **Keyboard navigation:** Tab through the page. Focus ring visible on every interactive element.
6. **RTL sanity:** If the page has directional layout elements, flip `dir="rtl"` in DevTools and verify no broken layout.

Automated coverage (run in CI):
- `npm run e2e:mobile` — mobile viewport e2e suite
- `npm run e2e` — full e2e suite

---

## 9. House Style Patterns (from Polished Screens)

Observed in Cart.vue, Home.vue, OwnerHome.vue — replicate these patterns exactly:

**Header rhythm:**
```html
<header class="ui-hero-ribbon ui-reveal px-4 py-3.5 md:px-5 md:py-4">
  <div class="flex items-center justify-between gap-3">
    <div>
      <p class="ui-kicker">{{ t('page.kicker') }}</p>
      <h1 class="ui-display text-xl font-semibold tracking-tight text-white md:text-2xl leading-tight">
        {{ t('page.title') }}
      </h1>
    </div>
    <div class="flex items-center gap-1.5">
      <span class="ui-chip">{{ metadataA }}</span>
      <span class="ui-chip">{{ metadataB }}</span>
    </div>
  </div>
</header>
```

**Empty state:**
```html
<div class="ui-empty-state text-center p-5 space-y-1">
  <p class="text-sm font-semibold text-slate-100">{{ t('page.emptyTitle') }}</p>
  <p class="text-xs text-slate-400">{{ t('page.emptyBody') }}</p>
  <RouterLink to="..." class="ui-btn-primary mt-3 inline-flex items-center gap-1.5 px-5 py-2 text-sm">
    {{ t('page.emptyCta') }}
  </RouterLink>
</div>
```

**Loading skeleton (inline):**
```html
<div v-if="loading" class="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-slate-800 bg-slate-800/70 sm:grid-cols-4">
  <div v-for="i in 4" :key="i" class="animate-pulse space-y-2 bg-slate-950/60 px-3 py-2.5">
    <div class="h-2.5 w-14 rounded bg-slate-700/60" />
    <div class="h-7 w-16 rounded bg-slate-700/40" />
  </div>
</div>
```

**Error inline:**
```html
<div v-if="error" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
  <AppIcon name="info" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" aria-hidden="true" />
  <p class="flex-1 text-sm text-red-300">{{ error }}</p>
</div>
```

**Staggered list:**
```html
<article
  v-for="(item, index) in items"
  :key="item.id"
  class="ui-panel ui-surface-lift ui-reveal"
  :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
>
```

**Section with kicker + title (mid-page):**
```html
<div class="space-y-2">
  <p class="ui-kicker">{{ t('section.kicker') }}</p>
  <h2 class="ui-display text-2xl font-semibold text-white md:text-3xl">{{ t('section.title') }}</h2>
  <p class="ui-subtle max-w-2xl">{{ t('section.subtitle') }}</p>
</div>
```
