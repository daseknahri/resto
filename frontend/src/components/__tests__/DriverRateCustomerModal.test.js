/**
 * Unit tests for DriverRateCustomerModal — the driver → customer post-delivery
 * rating modal extracted from DriverPage.vue as a self-contained drawer (RISK
 * FE-2). The parent keeps the rating state + submit; here we verify open gating,
 * the two-way score/note models, disabled/busy states, and the skip/submit emits.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({ t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k) }),
}));
// The real focus trap adds document listeners on open; stub it out for the unit.
vi.mock("../../composables/useFocusTrap", () => ({ useFocusTrap: () => {} }));

import DriverRateCustomerModal from "../DriverRateCustomerModal.vue";

const job = { order_number: 42 };
const mountIt = (props = {}) =>
  mount(DriverRateCustomerModal, {
    props: { job, busy: false, score: 0, note: "", ...props },
    global: { stubs: { teleport: true } },
  });

describe("DriverRateCustomerModal", () => {
  it("renders nothing when there is no job", () => {
    expect(mountIt({ job: null }).find('[role="dialog"]').exists()).toBe(false);
  });

  it("renders the order number and five stars", () => {
    const w = mountIt();
    expect(w.text()).toContain("driver.order");
    expect(w.text()).toContain("42");
    // 5 stars + skip + submit = 7 buttons.
    expect(w.findAll("button")).toHaveLength(7);
  });

  it("emits update:score when a star is clicked", async () => {
    const w = mountIt({ score: 0 });
    await w.findAll("button")[3].trigger("click"); // 4th star
    expect(w.emitted("update:score")[0]).toEqual([4]);
  });

  it("emits update:note when the note is typed", async () => {
    const w = mountIt();
    await w.find("input").setValue("polite customer");
    expect(w.emitted("update:note")[0]).toEqual(["polite customer"]);
  });

  it("disables submit at score 0 and enables it once a score is set", () => {
    const submit = (w) => w.findAll("button").at(-1);
    expect(submit(mountIt({ score: 0 })).attributes("disabled")).toBeDefined();
    expect(submit(mountIt({ score: 5 })).attributes("disabled")).toBeUndefined();
  });

  it("shows the spinner + loading label and disables submit while busy", () => {
    const w = mountIt({ score: 5, busy: true });
    expect(w.find(".animate-spin").exists()).toBe(true);
    expect(w.text()).toContain("common.loading");
    expect(w.findAll("button").at(-1).attributes("disabled")).toBeDefined();
  });

  it("emits close from skip and submit from the primary button", async () => {
    const w = mountIt({ score: 5 });
    const buttons = w.findAll("button");
    await buttons[5].trigger("click"); // skip
    await buttons[6].trigger("click"); // submit
    expect(w.emitted("close")).toBeTruthy();
    expect(w.emitted("submit")).toBeTruthy();
  });
});
