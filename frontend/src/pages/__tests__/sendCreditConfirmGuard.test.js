import { describe, it, expect, vi } from "vitest";
import { ref } from "vue";

// Pure mirror of CustomerAccount.vue's sendCredit() confirm gate (same convention as
// driverCodeSubmitGuard.test.js — mounting the whole account page is impractical). A
// P2P wallet transfer is IRREVERSIBLE and the recipient is resolved by an exact
// verified-phone match, so this locks the contract for owner bug #10:
//   1. the money-moving api.post must NOT fire until the user confirms, and
//   2. must NEVER fire if the user cancels, and
//   3. the success message names the recipient echoed back by the transfer response.
// Kept faithful to sendCredit() in ../CustomerAccount.vue; update both together.

function makeSender({ api, confirm, formatPrice = (n) => `${n} MAD` }) {
  const sendPhone = ref("");
  const sendAmount = ref("");
  const sendNote = ref("");
  const sendError = ref("");
  const sendSuccess = ref("");
  const sending = ref(false);

  const sendCredit = async () => {
    sendError.value = "";
    sendSuccess.value = "";
    const amount = parseFloat(sendAmount.value);
    const recipientPhone = sendPhone.value.trim();
    if (!recipientPhone) { sendError.value = "phone-required"; return; }
    if (!amount || amount <= 0) { sendError.value = "amount-required"; return; }
    const ok = await confirm({
      title: "sendConfirmTitle",
      body: `sendConfirmBody|${formatPrice(amount)}|${recipientPhone}`,
      confirmLabel: "sendBtn",
      danger: false,
    });
    if (!ok) return;
    sending.value = true;
    try {
      const res = await api.post("/customer/wallet/transfer/", {
        recipient_phone: recipientPhone,
        amount: amount.toFixed(2),
        note: sendNote.value.trim(),
      });
      const recipient = res.data.recipient_name || res.data.recipient_phone || recipientPhone;
      sendSuccess.value = `sent|${res.data.amount}|${recipient}`;
      sendPhone.value = "";
      sendAmount.value = "";
      sendNote.value = "";
    } finally {
      sending.value = false;
    }
  };

  return { sendCredit, sendPhone, sendAmount, sendNote, sendError, sendSuccess, sending };
}

describe("CustomerAccount sendCredit() confirm gate", () => {
  it("does NOT fire the transfer until the confirm resolves", async () => {
    let resolveConfirm;
    const confirm = vi.fn(() => new Promise((r) => { resolveConfirm = r; }));
    const api = { post: vi.fn(() => Promise.resolve({ data: { amount: "10.00", recipient_phone: "+212612345678" } })) };
    const s = makeSender({ api, confirm });
    s.sendPhone.value = "+212612345678";
    s.sendAmount.value = "10";

    const p = s.sendCredit();
    // Confirm was requested, but the irreversible transfer must still be pending.
    expect(confirm).toHaveBeenCalledTimes(1);
    expect(api.post).not.toHaveBeenCalled();

    resolveConfirm(true); // user approves
    await p;
    expect(api.post).toHaveBeenCalledTimes(1);
  });

  it("shows the amount + typed recipient number in the confirm body (catch a mistype)", async () => {
    const confirm = vi.fn(() => Promise.resolve(false));
    const api = { post: vi.fn() };
    const s = makeSender({ api, confirm });
    s.sendPhone.value = "  +212600112233  "; // whitespace trimmed before the guard
    s.sendAmount.value = "25";

    await s.sendCredit();
    const opts = confirm.mock.calls[0][0];
    expect(opts.body).toContain("+212600112233");
    expect(opts.body).toContain("25 MAD");
  });

  it("NEVER fires the transfer when the user cancels the confirm", async () => {
    const confirm = vi.fn(() => Promise.resolve(false));
    const api = { post: vi.fn() };
    const s = makeSender({ api, confirm });
    s.sendPhone.value = "+212612345678";
    s.sendAmount.value = "10";

    await s.sendCredit();
    expect(confirm).toHaveBeenCalledTimes(1);
    expect(api.post).not.toHaveBeenCalled();
    expect(s.sending.value).toBe(false);
  });

  it("does not even ask to confirm when input is invalid", async () => {
    const confirm = vi.fn(() => Promise.resolve(true));
    const api = { post: vi.fn() };
    const s = makeSender({ api, confirm });

    s.sendPhone.value = "";        // missing phone
    s.sendAmount.value = "10";
    await s.sendCredit();
    expect(confirm).not.toHaveBeenCalled();

    s.sendPhone.value = "+212612345678";
    s.sendAmount.value = "0";      // non-positive amount
    await s.sendCredit();
    expect(confirm).not.toHaveBeenCalled();
    expect(api.post).not.toHaveBeenCalled();
  });

  it("names the resolved recipient from the transfer response in the success message", async () => {
    const confirm = vi.fn(() => Promise.resolve(true));
    const api = { post: vi.fn(() => Promise.resolve({ data: { amount: "10.00", recipient_phone: "+212612345678", new_balance: "5.00" } })) };
    const s = makeSender({ api, confirm });
    s.sendPhone.value = "+212612345678";
    s.sendAmount.value = "10";

    await s.sendCredit();
    expect(s.sendSuccess.value).toContain("+212612345678");
    expect(s.sendSuccess.value).toContain("10.00");
  });

  it("prefers a recipient_name over the phone when the response provides one", async () => {
    const confirm = vi.fn(() => Promise.resolve(true));
    const api = { post: vi.fn(() => Promise.resolve({ data: { amount: "10.00", recipient_name: "Sara", recipient_phone: "+212612345678" } })) };
    const s = makeSender({ api, confirm });
    s.sendPhone.value = "+212612345678";
    s.sendAmount.value = "10";

    await s.sendCredit();
    expect(s.sendSuccess.value).toContain("Sara");
  });
});
