/**
 * Unit tests for AdminConsoleDeliveryPricingDrawer — the tenant delivery-pricing
 * modal extracted from AdminConsole.vue as a fully self-contained drawer (RISK
 * FE-2). The parent keeps the fetch / validation / save; here we verify the
 * open/loading gating, the two-way form model, and the close/submit emits.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({ t: (k) => k }),
}));

import AdminConsoleDeliveryPricingDrawer from "../AdminConsoleDeliveryPricingDrawer.vue";

const form = () => ({
  delivery_fee: 5,
  delivery_base_fee: 0,
  delivery_per_km: 0,
  delivery_free_over: 0,
  delivery_minimum_order: 0,
  delivery_radius_km_raw: "",
  delivery_zone_description: "",
  delivery_commission_pct: 10,
  platform_delivery_enabled: false,
});

const mountIt = (props = {}) =>
  mount(AdminConsoleDeliveryPricingDrawer, {
    props: { open: true, tenant: { name: "Chez Test" }, loading: false, saving: false, error: "", form: form(), ...props },
    global: { stubs: { teleport: true, transition: true } },
  });

describe("AdminConsoleDeliveryPricingDrawer", () => {
  it("renders nothing when closed", () => {
    expect(mountIt({ open: false }).find('[role="dialog"]').exists()).toBe(false);
  });

  it("shows the tenant name and the loading skeleton while loading", () => {
    const w = mountIt({ loading: true });
    expect(w.text()).toContain("Chez Test");
    expect(w.find(".ui-skeleton").exists()).toBe(true);
    // The form fields are hidden behind the loading branch.
    expect(w.findAll('input[type="number"]').length).toBe(0);
  });

  it("renders the form fields (seeded from the model) when not loading", () => {
    const w = mountIt();
    const fee = w.find('input[type="number"]');
    expect(fee.element.value).toBe("5");
    // 7 number inputs + radius + commission = several; checkbox + text also present.
    expect(w.find('input[type="checkbox"]').exists()).toBe(true);
  });

  it("mutates the shared form model in place (two-way) as fields change", async () => {
    const model = form();
    const w = mount(AdminConsoleDeliveryPricingDrawer, {
      props: { open: true, tenant: { name: "T" }, loading: false, saving: false, error: "", form: model },
      global: { stubs: { teleport: true, transition: true } },
    });
    await w.find('input[type="number"]').setValue("9");
    expect(model.delivery_fee).toBe(9); // .number modifier -> Number, same object the parent holds
  });

  it("shows the error alert when error is set", () => {
    expect(mountIt({ error: "Bad radius" }).text()).toContain("Bad radius");
    expect(mountIt({ error: "" }).find('[role="alert"]').exists()).toBe(false);
  });

  it("disables save + shows the spinner while saving", () => {
    const w = mountIt({ saving: true });
    const save = w.findAll("button").find((b) => b.text().includes("adminConsole.delivery.save") || b.attributes("aria-busy") === "true");
    expect(w.find(".animate-spin").exists()).toBe(true);
    expect(save.attributes("disabled")).toBeDefined();
  });

  it("emits submit from the save button", async () => {
    const w = mountIt();
    await w.findAll("button").at(-1).trigger("click"); // save is the last button
    expect(w.emitted("submit")).toBeTruthy();
  });

  it("emits close from the header + footer close buttons", async () => {
    const w = mountIt();
    const closers = w.findAll("button").filter((b) => b.text().includes("adminConsole.delivery.close"));
    expect(closers.length).toBe(2);
    await closers[0].trigger("click");
    expect(w.emitted("close")).toBeTruthy();
  });
});
