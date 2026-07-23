/**
 * Unit tests for WaiterIdleTableAlert — the idle-table alert banner of WaiterPage's
 * floor view, a DUMB presentational child (RISK FE-2). It renders the count + the
 * table labels and emits `dismiss`. The parent owns the urgent-tile computation +
 * dismissed state + the mounting v-if.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({ t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k) }),
}));

import WaiterIdleTableAlert from "../WaiterIdleTableAlert.vue";

const tiles = [{ tableLabel: "T1" }, { tableLabel: "T2" }, { tableLabel: "T3" }];

describe("WaiterIdleTableAlert", () => {
  it("renders the count (via the i18n param) and the joined table labels", () => {
    const w = mount(WaiterIdleTableAlert, { props: { tiles } });
    expect(w.text()).toContain('waiterPage.idleAlert:{"n":3}');
    expect(w.text()).toContain("T1, T2, T3");
  });

  it("emits dismiss when the ✕ is clicked", async () => {
    const w = mount(WaiterIdleTableAlert, { props: { tiles } });
    await w.find("button").trigger("click");
    expect(w.emitted("dismiss")).toBeTruthy();
  });
});
