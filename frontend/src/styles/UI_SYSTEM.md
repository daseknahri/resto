# UI System Layer

This document is the contract for shared UI primitives across:
- Landing interface
- Customer menu interface
- Owner workspace
- Admin console

Source of truth styles live in:
- `frontend/src/styles/tailwind.css`

## 1. Design Tokens

Core tokens are defined in `:root`:
- Color: `--color-primary`, `--color-secondary`, `--color-surface`, `--color-elevated`, `--color-border`, `--color-text`
- Motion: `--motion-fast`, `--motion-base`, `--motion-slow`, `--ease-fluid`
- Safe areas: `--safe-top`, `--safe-bottom`

Rules:
- Use these tokens instead of hardcoding new brand colors in views.
- New product themes should map through token values first.

## 2. Layout Primitives

Use these classes before custom layout wrappers:
- `ui-shell`: full-page shell baseline
- `ui-header`: sticky top header with blur and safe-area top
- `ui-footer`: shared footer rhythm
- `ui-page-shell`: max-width content container
- `ui-safe-bottom`: safe-area padding for mobile bottom bars
- `ui-divider`: subtle section separator

Rules:
- Keep page containers on `max-w-6xl` rhythm.
- Add `min-w-0` for grid/flex children that host scrollable rows.

## 3. Surface Primitives

- `ui-panel`: standard card/panel
- `ui-panel-soft`: softer elevated panel
- `ui-glass`: premium glass panel variant
- `ui-table-wrap`: shared horizontal-safe table shell

Rules:
- Default to `ui-panel` unless there is a clear reason for `ui-glass`.
- Reuse panel primitives for all list/detail cards before adding new variants.

## 4. Form Primitives

- `ui-input`
- `ui-textarea`
- `ui-touch-target` (minimum tap target)

Rules:
- All interactive inputs should use focus-visible ring behavior from these classes.
- Keep control height mobile-safe (`>= 44px`) using `ui-touch-target` when needed.

## 5. Action Primitives

- `ui-btn-primary`
- `ui-btn-outline`
- `ui-pill-nav`
- `ui-chip`
- `ui-top-link`

Rules:
- Primary action per section should use `ui-btn-primary`.
- Secondary/tertiary actions use `ui-btn-outline` or `ui-pill-nav`.
- Do not invent page-local button styles unless the primitive is insufficient.

## 6. Data Patterns

### Card lists
- Use `ui-panel` + `rounded-xl border border-slate-800 bg-slate-900/80 p-3`.
- Include explicit loading and empty states in the same section.

### Tables
- Desktop table in `ui-table-wrap` with `min-w-*`.
- Mobile fallback must use card mode (`md:hidden`) to avoid forced horizontal scroll.

### Scroll rows
- Use `ui-scroll-row`.
- For parent containers, add `min-w-0 max-w-full` to prevent viewport overflow.

## 7. Typography

- `ui-display`: premium display font (Fraunces)
- `ui-page-title`: page heading baseline
- `ui-kicker`: uppercase section kicker
- `ui-subtle`: secondary text rhythm

Rules:
- One display headline per major section max.
- Avoid mixing multiple ad-hoc tracking/line-height systems in same page.

## 8. Motion and Accessibility

- `ui-fade-up`, `ui-reveal`: entry motion primitives
- `ui-surface-lift`, `ui-press`: feedback motion primitives
- `prefers-reduced-motion` fallback is mandatory and already centralized

Rules:
- Keep motion meaningful; avoid adding parallel animations for the same element.
- Always validate keyboard focus visibility for new interactive elements.

## 9. QA Gate (UI)

Before merging UI work:
1. Verify no horizontal overflow at 390x844 on affected pages.
2. Verify loading, empty, and error states.
3. Verify reduced-motion behavior does not break interactions.
4. Verify one primary CTA per section and no duplicated navigation actions.

Automated coverage:
- `npm run e2e:mobile`
- `npm run e2e`
