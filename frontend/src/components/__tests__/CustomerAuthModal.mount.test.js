/**
 * Mount test for CustomerAuthModal.vue — the customer phone/OTP sign-in dialog.
 *
 * WHY: this component had NO test file at all. Mounting it runs its real
 * setup() (useCustomerStore, Google One-Tap gating, focus trap, resend
 * countdown) plus the phone/verify/setup step templates, so a setup()-time
 * crash fails CI here instead of in production.
 *
 * WHAT THIS COMPONENT IS (verified by reading it):
 *   - <script setup> imports AppIcon, useI18n ({ t } only), useCustomerStore,
 *     api (default) and PLATFORM_NAME (real, pure).
 *   - Teleport to="body" wraps a role="dialog" card; Teleport is stubbed
 *     inline so the dialog content stays inside wrapper.text().
 *   - No fetch at mount: onMounted only saves the trigger element, installs
 *     the keydown trap and focuses the first control; Google One-Tap is
 *     env-gated (VITE_GOOGLE_CLIENT_ID unset in tests) so it returns early.
 *   - Steps: 'phone' (default) -> 'verify' (after a successful OTP request)
 *     -> 'setup' (first sign-up, no name yet). The OTP auto-submits at 6
 *     digits via a watcher; tests below never type 6 digits, so no
 *     auto-submit fires.
 *   - lib/api is mocked with the full shape every consumer needs (the modal
 *     uses post/patch; the customer store imports the same module).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
  }),
}));
vi.mock("../AppIcon.vue", () => ({
  default: { name: "AppIcon", props: ["name"], template: '<span class="app-icon" />' },
}));
vi.mock("../../lib/api", () => ({
  extractApiErrorMessage: (err, fallback = "") => fallback,
  default: {
    get: vi.fn(() => Promise.resolve({ data: {} })),
    post: vi.fn(() => Promise.resolve({ data: {} })),
    patch: vi.fn(() => Promise.resolve({ data: {} })),
    delete: vi.fn(() => Promise.resolve({ data: {} })),
  },
}));

import api from "../../lib/api";
import CustomerAuthModal from "../CustomerAuthModal.vue";

const mountModal = () =>
  mount(CustomerAuthModal, {
    global: {
      stubs: {
        // Teleport is stubbed inline so the dialog content renders inside the
        // wrapper (detail/error text IS in wrapper.text()).
        Teleport: { template: "<slot />" },
      },
    },
  });

describe("CustomerAuthModal — mount smoke + C-13 aria-describedby", () => {
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

  // ── (1) default mount: the phone step ─────────────────────────────────────
  it("mounts the phone step without a setup() crash", async () => {
    expect(() => {
      wrapper = mountModal();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    expect(wrapper.text()).toContain("customerAuth.title");
    expect(wrapper.text()).toContain("customerAuth.phoneLabel");
    expect(wrapper.text()).toContain("customerAuth.sendCode");
    expect(api.post).not.toHaveBeenCalled();
  });

  // ── (2) C-13 phone: no dangling aria-describedby without an error ─────────
  it("phone input has no aria-describedby until a phone error is shown", async () => {
    wrapper = mountModal();
    await flushPromises();

    const phoneInput = wrapper.find('input[type="tel"]');
    expect(phoneInput.exists()).toBe(true);
    expect(phoneInput.attributes("aria-describedby")).toBeUndefined();
    expect(wrapper.find("#auth-phone-error").exists()).toBe(false);

    // Drive the error path: a phone is typed, Enter submits, the OTP request
    // fails -> phoneError is set and the target element appears.
    await phoneInput.setValue("0612345678");
    api.post.mockRejectedValueOnce({
      response: { data: { detail: "Send failed" } },
    });
    await phoneInput.trigger("keydown.enter");
    await flushPromises();

    expect(wrapper.find("#auth-phone-error").exists()).toBe(true);
    expect(wrapper.text()).toContain("Send failed");
    expect(wrapper.find('input[type="tel"]').attributes("aria-describedby")).toBe("auth-phone-error");
  });

  // ── (3) C-13 OTP: conditional aria-describedby + happy-path render ────────
  // Reaches the verify step via a successful OTP request, then checks the OTP
  // field renders (placeholder, 6-digit maxlength) with no dangling reference
  // until an OTP error is shown (empty-code submit via Enter).
  it("OTP input renders and gains aria-describedby only when an OTP error is shown", async () => {
    wrapper = mountModal();
    await flushPromises();

    const phoneInput = wrapper.find('input[type="tel"]');
    await phoneInput.setValue("0612345678");
    api.post.mockResolvedValueOnce({ data: {} });
    await phoneInput.trigger("keydown.enter");
    await flushPromises();

    // Happy-path OTP-field render: the verify step is showing.
    const otpInput = wrapper.find('input[maxlength="6"]');
    expect(otpInput.exists()).toBe(true);
    expect(otpInput.attributes("placeholder")).toBe("customerAuth.otpPlaceholder");
    expect(wrapper.text()).toContain("customerAuth.verify");
    // No error yet -> no dangling reference.
    expect(otpInput.attributes("aria-describedby")).toBeUndefined();
    expect(wrapper.find("#auth-otp-error").exists()).toBe(false);

    // Empty-code submit -> otpError set, target element appears.
    await otpInput.trigger("keydown.enter");
    await flushPromises();

    expect(wrapper.find("#auth-otp-error").exists()).toBe(true);
    expect(wrapper.text()).toContain("customerAuth.otpRequired");
    expect(wrapper.find('input[maxlength="6"]').attributes("aria-describedby")).toBe("auth-otp-error");
  });
});
