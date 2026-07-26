/**
 * Unit tests for MarketplaceCheckoutSchedule — the ASAP/scheduled "when" picker of
 * the Marketplace checkout drawer (RISK FE-2). scheduleEnabled + scheduledFor are
 * two-way models; the datetime input appears only when scheduling.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({ useI18n: () => ({ t: (k) => k }) }));

import MarketplaceCheckoutSchedule from "../MarketplaceCheckoutSchedule.vue";

const mountIt = (props = {}) =>
  mount(MarketplaceCheckoutSchedule, {
    props: { scheduleEnabled: false, scheduledFor: "", minScheduleDatetime: "2026-07-25T10:00", ...props },
  });

describe("MarketplaceCheckoutSchedule", () => {
  it("hides the datetime input when ASAP is selected and marks ASAP active", () => {
    const w = mountIt({ scheduleEnabled: false });
    expect(w.find('input[type="datetime-local"]').exists()).toBe(false);
    expect(w.findAll("button")[0].attributes("aria-pressed")).toBe("true");
  });

  it("shows the datetime input (with min) when scheduling later", () => {
    const w = mountIt({ scheduleEnabled: true });
    const input = w.find('input[type="datetime-local"]');
    expect(input.exists()).toBe(true);
    expect(input.attributes("min")).toBe("2026-07-25T10:00");
  });

  it("emits update:scheduleEnabled from the ASAP/later buttons", async () => {
    const w = mountIt({ scheduleEnabled: false });
    await w.findAll("button")[1].trigger("click"); // later
    expect(w.emitted("update:scheduleEnabled")[0]).toEqual([true]);
  });

  it("emits update:scheduledFor as the time is chosen", async () => {
    const w = mountIt({ scheduleEnabled: true });
    await w.find('input[type="datetime-local"]').setValue("2026-07-26T12:30");
    expect(w.emitted("update:scheduledFor")[0]).toEqual(["2026-07-26T12:30"]);
  });
});
