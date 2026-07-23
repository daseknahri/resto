/**
 * Unit tests for WaiterFirstRunBanner — the one-time first-run welcome banner of
 * WaiterPage, a DUMB presentational child (RISK FE-2). It renders the welcome
 * copy + a dismiss button; the tap emits `dismiss`. The parent owns the
 * seen/localStorage state.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({ t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k) }),
}));

import WaiterFirstRunBanner from "../WaiterFirstRunBanner.vue";

describe("WaiterFirstRunBanner", () => {
  it("renders the welcome title, body and dismiss label", () => {
    const w = mount(WaiterFirstRunBanner);
    expect(w.text()).toContain("waiter.firstRunTitle");
    expect(w.text()).toContain("waiter.firstRunBody");
    expect(w.text()).toContain("waiter.firstRunDismiss");
  });

  it("emits dismiss when the button is clicked", async () => {
    const w = mount(WaiterFirstRunBanner);
    await w.find("button").trigger("click");
    expect(w.emitted("dismiss")).toBeTruthy();
  });
});
