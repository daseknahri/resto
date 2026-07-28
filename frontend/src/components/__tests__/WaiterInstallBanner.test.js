/**
 * Unit tests for WaiterInstallBanner — the "install the app" nudge of WaiterPage,
 * a DUMB presentational child (RISK FE-2). It shows the install prompt + CTA when
 * the browser can prompt (canInstall), or manual instructions otherwise; the CTA
 * emits `install` and the ✕ emits `dismiss`. The parent owns the install prompt +
 * standalone/dismissed state.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({ t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k) }),
}));

import WaiterInstallBanner from "../WaiterInstallBanner.vue";

const mountIt = (props = {}) => mount(WaiterInstallBanner, { props: { canInstall: false, ...props } });

describe("WaiterInstallBanner", () => {
  it("shows the prompt copy + install CTA when the browser can prompt", () => {
    const w = mountIt({ canInstall: true });
    expect(w.text()).toContain("waiterInstall.prompt");
    expect(w.text()).toContain("waiterInstall.cta");
    // Two buttons: install CTA + dismiss.
    expect(w.findAll("button")).toHaveLength(2);
  });

  it("shows the manual copy and no install CTA when the browser cannot prompt", () => {
    const w = mountIt({ canInstall: false });
    expect(w.text()).toContain("waiterInstall.manual");
    expect(w.text()).not.toContain("waiterInstall.cta");
    // Only the dismiss button remains.
    expect(w.findAll("button")).toHaveLength(1);
  });

  it("emits install when the CTA is clicked", async () => {
    const w = mountIt({ canInstall: true });
    await w.findAll("button")[0].trigger("click");
    expect(w.emitted("install")).toBeTruthy();
  });

  it("emits dismiss when the ✕ is clicked", async () => {
    const w = mountIt({ canInstall: false });
    await w.find("button").trigger("click");
    expect(w.emitted("dismiss")).toBeTruthy();
  });
});
