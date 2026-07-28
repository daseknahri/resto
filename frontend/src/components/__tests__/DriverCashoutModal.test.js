/**
 * Unit tests for DriverCashoutModal — the driver cash-out (payout) amount modal
 * extracted from DriverPage.vue (RISK FE-2). MONEY-PATH: the parent keeps the
 * validation + POST /driver/cashout/; here we verify open gating, the amount/error
 * models, the max/prompt wiring, busy state, and the close/submit emits.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({ t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k) }),
}));
vi.mock("../../composables/useFocusTrap", () => ({ useFocusTrap: () => {} }));

import DriverCashoutModal from "../DriverCashoutModal.vue";

const mountIt = (props = {}) =>
  mount(DriverCashoutModal, {
    props: { open: true, busy: false, maxAmount: 120, fmtMoney: (n) => `${Number(n).toFixed(2)} DH`, amount: "", error: "", ...props },
    global: { stubs: { teleport: true } },
  });

describe("DriverCashoutModal", () => {
  it("renders nothing when closed", () => {
    expect(mountIt({ open: false }).find('[role="dialog"]').exists()).toBe(false);
  });

  it("shows the formatted max in the prompt and as the input ceiling", () => {
    const w = mountIt({ maxAmount: 120 });
    expect(w.text()).toContain('driver.cashOutAmountPrompt:{"max":"120.00 DH"}');
    expect(w.find('input[type="number"]').attributes("max")).toBe("120");
  });

  it("emits update:amount as the amount is typed", async () => {
    const w = mountIt();
    await w.find('input[type="number"]').setValue("40");
    expect(w.emitted("update:amount")[0]).toEqual([40]); // type=number coerces
  });

  it("emits submit on Enter and on the confirm button", async () => {
    const w = mountIt();
    await w.find('input[type="number"]').trigger("keydown.enter");
    await w.findAll("button").at(-1).trigger("click");
    expect(w.emitted("submit")).toHaveLength(2);
  });

  it("shows the inline error when error is set", () => {
    expect(mountIt({ error: "over the max" }).find('[role="alert"]').text()).toContain("over the max");
    expect(mountIt({ error: "" }).find('[role="alert"]').exists()).toBe(false);
  });

  it("shows the spinner and disables confirm while busy", () => {
    const w = mountIt({ busy: true });
    expect(w.find(".animate-spin").exists()).toBe(true);
    expect(w.findAll("button").at(-1).attributes("disabled")).toBeDefined();
  });

  it("emits close from cancel and the backdrop", async () => {
    const w = mountIt();
    const cancel = w.findAll("button").find((b) => b.text().includes("common.cancel"));
    await cancel.trigger("click");
    expect(w.emitted("close")).toBeTruthy();
  });
});
