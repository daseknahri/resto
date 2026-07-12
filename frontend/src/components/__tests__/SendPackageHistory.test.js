/**
 * Unit tests for SendPackageHistory — the package-history section of
 * SendPackagePage.vue (send-package request flow), extracted into a
 * standalone presentational component (RISK FE-2). This component does no
 * fetching and no address/fee/geocode logic; it only renders whatever
 * history it's given and asks the parent to rebook via the `rebook` emit.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k),
    formatPrice: (n) => `$${n}`,
    currentLocale: { value: "en" },
  }),
}));

import SendPackageHistory from "../SendPackageHistory.vue";

const pkg = (overrides = {}) => ({
  id: 1,
  recipient_name: "Amine",
  pickup_address: "12 Rue Atlas",
  dropoff_address: "45 Avenue Hassan II",
  created_at: "2026-07-01T12:00:00Z",
  fare: 32,
  status: "completed",
  ...overrides,
});

const mountComp = (props = {}) =>
  mount(SendPackageHistory, {
    props: {
      history: [],
      loading: false,
      isAuthenticated: false,
      ...props,
    },
  });

describe("SendPackageHistory", () => {
  it("renders nothing when there is no history, not loading, and not authenticated", () => {
    const w = mountComp();
    expect(w.text()).toBe("");
  });

  it("renders the loading skeleton when loading with no history yet", () => {
    const w = mountComp({ loading: true });
    expect(w.findAll(".animate-pulse").length).toBe(3);
    expect(w.text()).toContain("sendPackage.historyTitle");
  });

  it("renders the empty state only once loading has finished and the customer is authenticated", () => {
    const w = mountComp({ loading: false, history: [], isAuthenticated: true });
    expect(w.text()).toContain("sendPackage.historyEmpty");
  });

  it("does not render the empty state when not authenticated (mirrors the original guard)", () => {
    const w = mountComp({ loading: false, history: [], isAuthenticated: false });
    expect(w.text()).not.toContain("sendPackage.historyEmpty");
  });

  it("renders a history row with recipient name, formatted date, price, and status", () => {
    const w = mountComp({ history: [pkg()] });
    expect(w.text()).toContain("Amine");
    expect(w.text()).toContain("$32");
    expect(w.text()).toContain("sendPackage.delivered");
    // fmtDate uses the mocked "en" locale — assert on the year to avoid
    // coupling the test to a specific ICU month/day rendering.
    expect(w.text()).toContain("2026");
  });

  it("falls back to dropoff then pickup address when recipient_name is absent", () => {
    const w = mountComp({ history: [pkg({ recipient_name: "" })] });
    expect(w.text()).toContain("45 Avenue Hassan II");

    const w2 = mountComp({ history: [pkg({ recipient_name: "", dropoff_address: "" })] });
    expect(w2.text()).toContain("12 Rue Atlas");
  });

  it("shows the rebook button for a completed package and emits rebook with the package on click", async () => {
    const p = pkg({ status: "completed" });
    const w = mountComp({ history: [p] });
    const rebookBtn = w.find("button");
    expect(rebookBtn.exists()).toBe(true);
    expect(rebookBtn.text()).toContain("sendPackage.rebookCta");

    await rebookBtn.trigger("click");
    expect(w.emitted("rebook")).toBeTruthy();
    expect(w.emitted("rebook")[0]).toEqual([p]);
  });

  it("hides the rebook button and shows the cancelled label for a cancelled package", () => {
    const w = mountComp({ history: [pkg({ status: "cancelled" })] });
    expect(w.find("button").exists()).toBe(false);
    expect(w.text()).toContain("sendPackage.cancelled");
  });

  it("renders the section (not the empty state) once history has rows, even while re-fetching", () => {
    const w = mountComp({ history: [pkg()], loading: true });
    expect(w.text()).not.toContain("sendPackage.historyEmpty");
    expect(w.text()).toContain("Amine");
  });
});
