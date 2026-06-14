import { nextTick } from "vue";
import { START_LOCATION } from "vue-router";

// ── SPA route-change focus management (WCAG 2.4.3 Focus Order) ───────────────
// A client-side navigation swaps the view without a document reload, so the
// browser never resets focus — a keyboard or screen-reader user stays parked on
// the (now-gone) link, and the skip-link target shipped in B12 is meaningless.
// On every non-initial navigation we move focus to <main id="main-content">
// (tabindex="-1" in every layout) so assistive tech announces the new view and
// keyboard tabbing resumes from the top of the fresh content.

const focusHeldByDialog = () => {
  const active = document.activeElement;
  if (!active || typeof active.closest !== "function") return false;
  return Boolean(active.closest('[role="dialog"], [aria-modal="true"], .modal, [data-dialog]'));
};

// Returns a vue-router afterEach guard that moves focus to #main-content after
// each non-initial navigation. Dependency-light and SSR-safe (guards typeof
// document/window). Exported as a factory so it is trivially unit-testable.
export function createMainContentFocusGuard() {
  return (to, from) => {
    if (typeof document === "undefined" || typeof window === "undefined") return;
    // Skip the very first navigation (cold load): we must not yank focus on the
    // initial render, where the browser's default focus behaviour is correct.
    if (from === START_LOCATION || from.name == null) return;

    // Defer until the new view has rendered so #main-content exists in the DOM.
    nextTick(() => {
      const main = document.getElementById("main-content");
      if (!main) return; // defensive: layout without a main region
      // Don't steal focus from an open modal/dialog that currently holds it.
      if (focusHeldByDialog()) return;
      // preventScroll so we don't fight scrollBehavior's scroll-to-top.
      main.focus({ preventScroll: true });
    });
  };
}
