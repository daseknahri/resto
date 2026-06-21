/**
 * Unit tests for RoleSwitcher — the Order / Drive / Manage segmented control.
 *
 * Locks in: the control hides itself when the identity holds only one role;
 * Drive appears for drivers; Manage appears for tenant owners/staff; and the
 * current mode renders as a non-link (aria-current) while others are RouterLinks.
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { mount } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({ t: (k) => k }),
}));

import RoleSwitcher from "../RoleSwitcher.vue";
import { useCustomerStore } from "../../stores/customer";

const RouterLinkStub = {
  name: "RouterLink",
  props: ["to"],
  template: '<a class="rl"><slot /></a>',
};

function mountSwitcher(customer, props = {}) {
  const store = useCustomerStore();
  store.setCustomer(customer);
  return mount(RoleSwitcher, {
    props,
    global: { stubs: { RouterLink: RouterLinkStub } },
  });
}

describe("RoleSwitcher", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it("hides when the identity has only the order role", () => {
    const w = mountSwitcher({ id: 1, is_driver: false, has_tenant: false });
    expect(w.find("nav").exists()).toBe(false);
  });

  it("shows Drive for drivers", () => {
    const w = mountSwitcher({ id: 1, is_driver: true });
    expect(w.text()).toContain("roleSwitch.driveAndEarn");
    expect(w.text()).toContain("roleSwitch.orderMode");
  });

  it("shows Manage for tenant owners/staff", () => {
    const w = mountSwitcher({ id: 1, has_tenant: true });
    expect(w.text()).toContain("roleSwitch.manageMode");
  });

  it("renders the current mode as non-link with aria-current", () => {
    const w = mountSwitcher({ id: 1, is_driver: true }, { current: "order" });
    const current = w.find('[aria-current="true"]');
    expect(current.exists()).toBe(true);
    expect(current.element.tagName.toLowerCase()).toBe("span");
    // Drive is offered as a RouterLink (not the current surface).
    const links = w.findAll("a.rl");
    expect(links.length).toBe(1);
    expect(links[0].text()).toContain("roleSwitch.driveAndEarn");
  });
});
