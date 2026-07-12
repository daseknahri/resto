/**
 * Unit tests for CustomerAccountProfile — the profile tab of
 * CustomerAccount.vue, extracted into a standalone presentational component
 * (RISK FE-2). Fetch/state/API-mutation ownership stays in the parent; this
 * component only renders whatever it's given and asks the parent to apply
 * mutations via emits.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k),
  }),
}));

import CustomerAccountProfile from "../CustomerAccountProfile.vue";

const RouterLinkStub = {
  name: "RouterLink",
  props: ["to"],
  template: '<a class="rl"><slot /></a>',
};

const AppIconStub = { props: ["name"], template: "<i />" };

const address = (overrides = {}) => ({
  id: 1,
  label: "Home",
  address: "12 Rue de la Paix",
  ...overrides,
});

const mountComp = (props = {}) =>
  mount(CustomerAccountProfile, {
    props: {
      customer: {},
      editableName: "",
      savingName: false,
      showEmailInput: false,
      editableEmail: "",
      savingEmail: false,
      emailError: "",
      editableBirthday: "",
      savingBirthday: false,
      savedAddresses: [],
      loadingAddresses: false,
      addingAddress: false,
      addrForm: { label: "", address: "" },
      addrError: "",
      savingAddress: false,
      editingAddressId: null,
      editForm: { label: "", address: "" },
      editError: "",
      savingEdit: false,
      deletingAddressId: null,
      addrDeleteError: "",
      localeConfigured: false,
      selectedLocale: "en",
      savingLocale: false,
      localeLabelCurrent: "English",
      currencyOptions: [{ code: "USD", symbol: "$" }, { code: "EUR", symbol: "€" }],
      selectedCurrency: "USD",
      savingPrefs: false,
      pushSupported: false,
      pushEnabled: false,
      pushSubscribed: false,
      pushLoading: false,
      serviceProfilesOpen: false,
      serviceProfiles: {},
      loadingServiceProfiles: false,
      serviceProfilesError: false,
      savingServiceProfile: "",
      enabledVerticals: ["food", "shops", "driver"],
      verticalSvcLabels: { food: "Food", shops: "Shops" },
      exportingData: false,
      requestingErasure: false,
      erasureConfirmVisible: false,
      erasureBlockedMsg: "",
      ...props,
    },
    global: { stubs: { RouterLink: RouterLinkStub, AppIcon: AppIconStub } },
  });

describe("CustomerAccountProfile", () => {
  it("shows the driver-mode join hint for a non-driver and the open hint for a driver", () => {
    const joiner = mountComp({ customer: { is_driver: false } });
    expect(joiner.text()).toContain("customerAccount.driverModeJoin");

    const driver = mountComp({ customer: { is_driver: true } });
    expect(driver.text()).toContain("customerAccount.driverModeOpen");
  });

  it("only shows the save-name button once the draft differs from the stored name, and emits save-name", async () => {
    const w = mountComp({ customer: { name: "Ada" }, editableName: "Ada" });
    expect(w.find(".ui-btn-primary").exists()).toBe(false);

    await w.setProps({ editableName: "Ada Lovelace" });
    const saveBtn = w.find(".ui-btn-primary");
    expect(saveBtn.exists()).toBe(true);
    await saveBtn.trigger("click");
    expect(w.emitted("save-name")).toBeTruthy();
  });

  it("emits update-editable-name when typing in the name field", async () => {
    const w = mountComp({ editableName: "Ada" });
    await w.find('input[autocomplete="name"]').setValue("Ada L");
    expect(w.emitted("update-editable-name")[0]).toEqual(["Ada L"]);
  });

  it("shows an add-phone button when there is no phone, and emits add-phone", async () => {
    const w = mountComp({ customer: {} });
    expect(w.text()).toContain("customerAccount.addPhone");
    await w.find("button").trigger("click"); // driver-mode link isn't a button; first button is add-phone
    // Locate specifically by text to be robust to markup order changes.
    const addPhoneBtn = w.findAll("button").find((b) => b.text().includes("customerAccount.addPhone"));
    await addPhoneBtn.trigger("click");
    expect(w.emitted("add-phone")).toBeTruthy();
  });

  it("renders the phone value and verified badge when present, without an add-phone button", () => {
    const w = mountComp({ customer: { phone: "+15551234567", phone_verified: true } });
    expect(w.text()).toContain("+15551234567");
    expect(w.text()).toContain("customerAccount.verifiedPhone");
    expect(w.text()).not.toContain("customerAccount.addPhone");
  });

  it("opens the email editor and emits open-email-input", async () => {
    const w = mountComp({ customer: {} });
    const editBtn = w.findAll("button").find((b) => b.text().includes("customerAccount.addEmail"));
    await editBtn.trigger("click");
    expect(w.emitted("open-email-input")).toBeTruthy();
  });

  it("shows the email input when showEmailInput is true, emits update-editable-email on input and save-email on Enter", async () => {
    const w = mountComp({ showEmailInput: true, editableEmail: "a@b.com" });
    const input = w.find('input[type="email"]');
    expect(input.exists()).toBe(true);

    await input.setValue("a@b.co");
    expect(w.emitted("update-editable-email")[0]).toEqual(["a@b.co"]);

    await input.trigger("keydown.enter");
    expect(w.emitted("save-email")).toBeTruthy();

    await input.trigger("keydown.escape");
    expect(w.emitted("cancel-email-input")).toBeTruthy();
  });

  it("renders the email validation error message", () => {
    const w = mountComp({ showEmailInput: true, emailError: "Invalid email" });
    expect(w.text()).toContain("Invalid email");
  });

  it("only shows the save-birthday button once the draft differs, and emits save-birthday", async () => {
    const w = mountComp({ customer: { birthday: "" }, editableBirthday: "" });
    expect(w.text()).not.toContain("customerAccount.saving");
    await w.setProps({ editableBirthday: "1990-01-01" });
    const buttons = w.findAll("button.ui-btn-primary");
    const saveBirthdayBtn = buttons[buttons.length - 1];
    await saveBirthdayBtn.trigger("click");
    expect(w.emitted("save-birthday")).toBeTruthy();
  });

  it("shows the saved-addresses empty state when there are none", () => {
    const w = mountComp({ savedAddresses: [] });
    expect(w.text()).toContain("customerAccount.savedAddressesEmpty");
  });

  it("opens the add-address form and emits add-address on submit, with field inputs emitting their drafts", async () => {
    const w = mountComp({ savedAddresses: [], addingAddress: false });
    const addBtn = w.findAll("button").find((b) => b.text().includes("customerAccount.savedAddressAdd"));
    await addBtn.trigger("click");
    expect(w.emitted("start-adding-address")).toBeTruthy();

    await w.setProps({ addingAddress: true, addrForm: { label: "", address: "" } });
    const form = w.find("form");
    expect(form.exists()).toBe(true);

    await form.find("input").setValue("Home");
    expect(w.emitted("addr-label-input")[0]).toEqual(["Home"]);

    await form.find("textarea").setValue("12 Rue de la Paix");
    expect(w.emitted("addr-address-input")[0]).toEqual(["12 Rue de la Paix"]);

    await form.trigger("submit");
    expect(w.emitted("add-address")).toBeTruthy();
  });

  it("renders a saved address and emits toggle-edit-address / start-delete-address with the address payload", async () => {
    const addr = address();
    const w = mountComp({ savedAddresses: [addr] });
    expect(w.text()).toContain("Home");
    expect(w.text()).toContain("12 Rue de la Paix");

    const [editBtn, deleteBtn] = w.findAll('button[aria-label="common.edit"], button[aria-label="common.remove"]');
    await editBtn.trigger("click");
    expect(w.emitted("toggle-edit-address")[0]).toEqual([addr]);

    await deleteBtn.trigger("click");
    expect(w.emitted("start-delete-address")[0]).toEqual([addr.id]);
  });

  it("shows the delete confirmation for the matching address and emits delete-address / cancel-delete-address", async () => {
    const addr = address();
    const w = mountComp({ savedAddresses: [addr], deletingAddressId: addr.id });
    expect(w.text()).toContain("customerAccount.savedAddressConfirmDelete");

    const buttons = w.findAll("button").filter((b) => b.text() === "common.remove" || b.text() === "common.back");
    const backBtn = buttons.find((b) => b.text() === "common.back");
    const removeBtn = buttons.find((b) => b.text() === "common.remove");

    await backBtn.trigger("click");
    expect(w.emitted("cancel-delete-address")).toBeTruthy();

    await removeBtn.trigger("click");
    expect(w.emitted("delete-address")[0]).toEqual([addr.id]);
  });

  it("shows the locale picker when unconfigured and emits set-locale, or the current locale + edit-locale when configured", async () => {
    const w = mountComp({ localeConfigured: false, selectedLocale: "fr" });
    const frBtn = w.findAll("button").find((b) => b.text() === "Français");
    await frBtn.trigger("click");
    expect(w.emitted("set-locale")[0]).toEqual(["fr"]);

    const w2 = mountComp({ localeConfigured: true, localeLabelCurrent: "Français" });
    expect(w2.text()).toContain("Français");
    const changeBtn = w2.findAll("button").find((b) => b.text() === "common.change");
    await changeBtn.trigger("click");
    expect(w2.emitted("edit-locale")).toBeTruthy();
  });

  it("emits set-currency when a currency chip is clicked", async () => {
    const w = mountComp({ currencyOptions: [{ code: "USD", symbol: "$" }], selectedCurrency: "EUR" });
    const usdBtn = w.findAll("button").find((b) => b.text().includes("USD"));
    await usdBtn.trigger("click");
    expect(w.emitted("set-currency")[0]).toEqual(["USD"]);
  });

  it("emits save-pref with the field name and checked state for each notification toggle", async () => {
    const w = mountComp({ customer: { notify_order_updates: false } });
    const checkboxes = w.findAll('input[type="checkbox"]');
    await checkboxes[0].setValue(true);
    expect(w.emitted("save-pref")[0]).toEqual(["notify_order_updates", true]);
  });

  it("shows the push-subscribe button only when supported+enabled+not subscribed, and emits push-subscribe", async () => {
    const hidden = mountComp({ pushSupported: false, pushEnabled: true });
    expect(hidden.text()).not.toContain("customerAccount.notifyEnable");

    const shown = mountComp({ pushSupported: true, pushEnabled: true, pushSubscribed: false });
    const btn = shown.findAll("button").find((b) => b.text().includes("customerAccount.notifyEnable"));
    await btn.trigger("click");
    expect(shown.emitted("push-subscribe")).toBeTruthy();
  });

  it("toggles the per-service notifications panel and emits toggle-service-profiles", async () => {
    const w = mountComp({ serviceProfilesOpen: false });
    const toggleBtn = w.findAll("button").find((b) => b.text().includes("customerAccount.perServiceNotifs"));
    await toggleBtn.trigger("click");
    expect(w.emitted("toggle-service-profiles")).toBeTruthy();
  });

  it("renders per-vertical toggles (excluding 'driver') when the panel is open, and emits save-service-pref", async () => {
    const w = mountComp({
      serviceProfilesOpen: true,
      enabledVerticals: ["food", "driver"],
      verticalSvcLabels: { food: "Food" },
      serviceProfiles: { food: { notify_updates: true, notify_promotions: false } },
    });
    expect(w.text()).toContain("Food");

    const checkboxes = w.findAll('input[type="checkbox"]');
    // 3 top-level notification toggles + 2 for the single non-driver vertical
    // ("driver" must be filtered out, so no extra pair is rendered for it).
    expect(checkboxes.length).toBe(5);
    // Last two checkboxes belong to the single rendered vertical (updates, promotions).
    const [updatesCb, promosCb] = checkboxes.slice(-2);
    await updatesCb.setValue(false);
    expect(w.emitted("save-service-pref")[0]).toEqual(["food", "notify_updates", false]);
    await promosCb.setValue(true);
    expect(w.emitted("save-service-pref")[1]).toEqual(["food", "notify_promotions", true]);
  });

  it("shows the per-service loading skeleton and error state", () => {
    const loading = mountComp({ serviceProfilesOpen: true, loadingServiceProfiles: true });
    expect(loading.findAll(".animate-pulse").length).toBeGreaterThan(0);

    const errored = mountComp({ serviceProfilesOpen: true, serviceProfilesError: true });
    expect(errored.text()).toContain("customerAccount.perServiceLoadError");
  });

  it("emits download-my-data when the export button is clicked", async () => {
    const w = mountComp();
    const btn = w.findAll("button").find((b) => b.text().includes("customerAccount.privacyExportBtn"));
    await btn.trigger("click");
    expect(w.emitted("download-my-data")).toBeTruthy();
  });

  it("walks the erasure confirm flow: start-erasure, then request-erasure / cancel-erasure", async () => {
    const w = mountComp({ erasureConfirmVisible: false });
    const startBtn = w.findAll("button").find((b) => b.text().includes("customerAccount.privacyDeleteBtn"));
    await startBtn.trigger("click");
    expect(w.emitted("start-erasure")).toBeTruthy();

    const w2 = mountComp({ erasureConfirmVisible: true });
    const confirmBtn = w2.findAll("button").find((b) => b.text().includes("customerAccount.privacyDeleteConfirmBtn"));
    await confirmBtn.trigger("click");
    expect(w2.emitted("request-erasure")).toBeTruthy();

    const cancelBtn = w2.findAll("button").find((b) => b.text() === "common.cancel");
    await cancelBtn.trigger("click");
    expect(w2.emitted("cancel-erasure")).toBeTruthy();
  });

  it("shows the erasure-blocked message when present", () => {
    const w = mountComp({ erasureBlockedMsg: "Cannot delete: active order" });
    expect(w.text()).toContain("Cannot delete: active order");
  });
});
