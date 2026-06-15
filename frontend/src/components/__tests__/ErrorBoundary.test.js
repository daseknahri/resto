/**
 * Unit test for ErrorBoundary — the app-wide fallback (App.vue wraps RouterView
 * in it). In the NORMAL state it must add NO <main> of its own: the active layout
 * inside the slot owns the single <main id="main-content">, so an extra main here
 * would create a duplicate-main / id collision. (In the ERROR state the fallback
 * renders its own <main id="main-content" tabindex="-1"> as the landmark + focus
 * target — that path is a small structural wrap verified by build/lint; triggering
 * a captured render error in @vue/test-utils rethrows out of mount(), so it is not
 * unit-tested here.)
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({ t: (k) => k }),
}));

import ErrorBoundary from "../ErrorBoundary.vue";

describe("ErrorBoundary (landmark hygiene)", () => {
  it("adds NO <main> in the normal (non-error) state — the layout owns the single main", () => {
    const w = mount(ErrorBoundary, {
      slots: { default: "<div data-test='ok'>ok</div>" },
      global: { stubs: { RouterLink: { template: "<a><slot /></a>" } } },
    });
    expect(w.find("[data-test='ok']").exists()).toBe(true);
    expect(w.findAll("main")).toHaveLength(0);
  });
});
