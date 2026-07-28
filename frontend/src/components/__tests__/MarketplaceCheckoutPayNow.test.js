/**
 * Unit tests for MarketplaceCheckoutPayNow — the pay-now panel of the Marketplace
 * checkout drawer (RISK FE-2). paymentMethod is a two-way model; the wallet/cash
 * panels + shortfall nudge are gated by parent-computed props.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({ t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k) }),
}));

import MarketplaceCheckoutPayNow from "../MarketplaceCheckoutPayNow.vue";

const base = {
  paymentMethod: "wallet", codEligible: false, codChosen: false, walletCoversTotal: true,
  walletBalance: 200, currency: "DH", orderTotal: 100, walletBalanceNum: 200,
  fmtPrice: (n) => `$${Number(n).toFixed(2)}`,
};
const stubs = { global: { stubs: { RouterLink: { template: "<a><slot /></a>" } } } };
const mountIt = (props = {}) => mount(MarketplaceCheckoutPayNow, { props: { ...base, ...props }, ...stubs });

describe("MarketplaceCheckoutPayNow", () => {
  it("shows the wallet/cash selector only when COD is eligible", () => {
    expect(mountIt({ codEligible: false }).text()).not.toContain("mktMenu.payMethodWallet");
    const w = mountIt({ codEligible: true, paymentMethod: "wallet" });
    const btns = w.findAll('button[aria-pressed]');
    expect(btns).toHaveLength(2);
    expect(btns[0].attributes("aria-pressed")).toBe("true"); // wallet active
  });

  it("emits update:paymentMethod when a method is chosen", async () => {
    const w = mountIt({ codEligible: true, paymentMethod: "wallet" });
    await w.findAll('button[aria-pressed]')[1].trigger("click"); // cash
    expect(w.emitted("update:paymentMethod")[0]).toEqual(["cash"]);
  });

  it("shows the cash-on-handover panel when cod is chosen", () => {
    expect(mountIt({ codChosen: true }).text()).toContain("mktMenu.payCashOnHandoverTitle");
    // ...and hides the wallet panel in that case.
    expect(mountIt({ codChosen: true }).text()).not.toContain("mktMenu.payFromWalletTitle");
  });

  it("shows the wallet panel with the balance line when cod is not chosen", () => {
    const w = mountIt({ codChosen: false, walletBalance: 200, currency: "DH" });
    expect(w.text()).toContain("mktMenu.payFromWalletTitle");
    expect(w.text()).toContain('mktMenu.walletBalanceLine:{"balance":"200 DH"}');
  });

  it("shows the shortfall notice + top-up link only when the wallet is short", () => {
    expect(mountIt({ walletCoversTotal: true }).text()).not.toContain("mktMenu.walletShortNotice");
    const w = mountIt({ walletCoversTotal: false, orderTotal: 100, walletBalanceNum: 70 });
    expect(w.text()).toContain('mktMenu.walletShortNotice:{"amount":"$30.00"}'); // 100 - 70
    expect(w.text()).toContain("mktMenu.topUpWallet");
  });
});
