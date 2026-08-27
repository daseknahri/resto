import { describe, it, expect, vi } from "vitest";
import { ref } from "vue";

// Pure mirror of DriverPage.vue's submitPackageCode() / submitDeliveryCode() re-entrancy
// guards (same convention as driverTerminalOutcome.test.js — the full page is impractical to
// mount). Locks the contract that an in-flight submit cannot be re-fired: the button's
// :disabled blocks a click while submitting, but the code field's @keydown.enter handler
// bypasses :disabled, so a fast double-Enter must NOT trigger a second network call.
// Sibling of the DriverDeliveryCodeModal double-submit fix (#269).

// Mirrors submitPackageCode(): gated by the shared `busy` ref that disables the submit button.
function makePackageSubmitter(api) {
  const busy = ref(false);
  const packageCodeInput = ref("123456");
  const submit = async () => {
    const code = packageCodeInput.value.trim();
    if (!code) return;
    if (busy.value) return; // guard: Enter can re-fire while the click-path submit is in flight
    busy.value = true;
    try {
      await api.post(code);
      packageCodeInput.value = "";
    } finally {
      busy.value = false;
    }
  };
  return { submit, busy, packageCodeInput };
}

// Mirrors submitDeliveryCode(): gated by the `codeSubmitting` ref bound to the modal's
// :submitting (which disables its confirm button).
function makeDeliverySubmitter(api) {
  const codeSubmitting = ref(false);
  const codeInput = ref("654321");
  const proofPhotoFile = ref(null);
  const submit = async () => {
    if (codeSubmitting.value) return; // defense-in-depth re-entry guard
    const code = codeInput.value.trim();
    if (!code && !proofPhotoFile.value) return;
    codeSubmitting.value = true;
    try {
      await api.patch(code);
    } finally {
      codeSubmitting.value = false;
    }
  };
  return { submit, codeSubmitting, codeInput };
}

describe("DriverPage code-submit re-entrancy guards", () => {
  it("submitPackageCode fires the network call only once for a concurrent double-Enter", async () => {
    let resolveCall;
    const api = { post: vi.fn(() => new Promise((r) => { resolveCall = r; })) };
    const { submit } = makePackageSubmitter(api);

    const first = submit();      // starts the in-flight submit, sets busy=true
    const second = submit();     // simulates a second Enter while the first is pending
    await second;                // the guarded call returns immediately (no-op)
    expect(api.post).toHaveBeenCalledTimes(1);

    resolveCall();
    await first;
    expect(api.post).toHaveBeenCalledTimes(1);
  });

  it("submitPackageCode can submit again after the first call settles", async () => {
    const api = { post: vi.fn(() => Promise.resolve()) };
    const { submit, packageCodeInput } = makePackageSubmitter(api);

    await submit();
    packageCodeInput.value = "222222"; // input was cleared on success; new code entered
    await submit();
    expect(api.post).toHaveBeenCalledTimes(2);
  });

  it("submitDeliveryCode fires the network call only once for a concurrent double-Enter", async () => {
    let resolveCall;
    const api = { patch: vi.fn(() => new Promise((r) => { resolveCall = r; })) };
    const { submit } = makeDeliverySubmitter(api);

    const first = submit();
    const second = submit();
    await second;
    expect(api.patch).toHaveBeenCalledTimes(1);

    resolveCall();
    await first;
    expect(api.patch).toHaveBeenCalledTimes(1);
  });
});
