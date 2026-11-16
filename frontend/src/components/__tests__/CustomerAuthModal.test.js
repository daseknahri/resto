import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
  }),
}));

vi.mock("../../lib/api", () => ({
  default: {
    get: vi.fn(() => Promise.resolve({ data: {} })),
    post: vi.fn(() => Promise.resolve({ data: {} })),
  },
  // C-06 contract double: known code -> localized apiClient key, else fallback.
  extractApiErrorMessage: (err, fallback = "") => {
    const code = err?.response?.data?.code;
    const MAP = {
      otp_expired: "apiClient.otpExpired",
      too_many_attempts: "apiClient.tooManyAttempts",
      invalid_code: "apiClient.invalidCode",
      otp_rate_limited: "apiClient.otpRateLimited",
      otp_cooldown: "apiClient.otpCooldown",
      invalid_phone: "apiClient.invalidPhone",
      phone_taken: "apiClient.phoneTaken",
      invalid_credential: "apiClient.invalidCredential",
      not_configured: "apiClient.notConfigured",
    };
    if (code && MAP[code]) return MAP[code];
    return fallback;
  },
}));

vi.mock("../../stores/customer", () => ({
  useCustomerStore: () => ({
    customer: null,
    setCustomer: vi.fn(),
  }),
}));

vi.mock("../../lib/brand", () => ({
  PLATFORM_NAME: "Rostoy",
}));

import api from "../../lib/api";
import CustomerAuthModal from "../CustomerAuthModal.vue";

const mountModal = () =>
  shallowMount(CustomerAuthModal, {
    global: {
      stubs: {
        Teleport: { template: "<slot />" },
        Transition: { template: "<slot />" },
      },
    },
  });

const clickButtonWith = (wrapper, text) => {
  const btn = wrapper.findAll("button").find((b) => b.text().includes(text));
  if (!btn) throw new Error(`button not found: ${text}`);
  return btn.trigger("click");
};

describe("CustomerAuthModal — C-06 errors never surface raw backend detail", () => {
  let wrapper;

  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
  });

  it("OTP send failure shows the localized message for a known code, not the raw detail", async () => {
    wrapper = mountModal();
    await flushPromises();
    api.post.mockRejectedValueOnce({
      response: { data: { code: "otp_rate_limited", detail: "Too many codes requested for this recipient." } },
    });
    await wrapper.find('input[type="tel"]').setValue("+212600000000");
    await clickButtonWith(wrapper, "customerAuth.sendCode");
    await flushPromises();
    expect(wrapper.find("#auth-phone-error").text()).toBe("apiClient.otpRateLimited");
    expect(wrapper.text()).not.toContain("Too many codes requested for this recipient.");
  });

  it("OTP send failure shows the localized generic for an unmapped code", async () => {
    wrapper = mountModal();
    await flushPromises();
    api.post.mockRejectedValueOnce({
      response: { data: { code: "something_new", detail: "SMS gateway exploded." } },
    });
    await wrapper.find('input[type="tel"]').setValue("+212600000000");
    await clickButtonWith(wrapper, "customerAuth.sendCode");
    await flushPromises();
    expect(wrapper.find("#auth-phone-error").text()).toBe("customerAuth.sendError");
    expect(wrapper.text()).not.toContain("SMS gateway exploded.");
  });

  it("OTP verify failure falls back to the localized generic for an unmapped code", async () => {
    wrapper = mountModal();
    await flushPromises();
    // Reach the verify step first: a successful send flips step to "verify".
    api.post.mockResolvedValueOnce({ data: {} });
    await wrapper.find('input[type="tel"]').setValue("+212600000000");
    await clickButtonWith(wrapper, "customerAuth.sendCode");
    await flushPromises();
    expect(wrapper.text()).toContain("customerAuth.verify");
    api.post.mockRejectedValueOnce({
      response: { data: { code: "something_new", detail: "Verification service is down." } },
    });
    await wrapper.find('input[inputmode="numeric"]').setValue("123456");
    await clickButtonWith(wrapper, "customerAuth.verify");
    await flushPromises();
    expect(wrapper.find("#auth-otp-error").text()).toBe("customerAuth.verifyError");
    expect(wrapper.text()).not.toContain("Verification service is down.");
  });
});
