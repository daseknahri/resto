import { describe, it, expect, vi, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";

const { post } = vi.hoisted(() => ({ post: vi.fn() }));
vi.mock("../../lib/api", async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, default: { post } };
});

import { useActivationStore } from "../activation";

// accounts.serializers: plain DRF ValidationErrors → {"non_field_errors": [msg]}.
const reject = (message) => Promise.reject({ response: { status: 400, data: { non_field_errors: [message] } } });

describe("activation store — server error classification", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    post.mockReset();
  });

  it("flags an already-activated account (ACTIVATION_ALREADY_DONE)", async () => {
    post.mockReturnValue(
      reject('This account is already activated. Sign in, or use "Forgot password" to reset your password.'),
    );
    const store = useActivationStore();
    await store.activate("t", "Zx9kLmop-42qR");
    expect(store.alreadyActivated).toBe(true);
    expect(store.tokenExpiredOrUsed).toBe(false);
    expect(store.error).toContain("already activated");
  });

  it("flags an expired/used token, not an activated account", async () => {
    post.mockReturnValue(reject("Token expired or used"));
    const store = useActivationStore();
    await store.activate("t", "Zx9kLmop-42qR");
    expect(store.tokenExpiredOrUsed).toBe(true);
    expect(store.alreadyActivated).toBe(false);
  });

  it("clears both flags on a new successful attempt", async () => {
    const store = useActivationStore();
    store.$patch({ alreadyActivated: true, tokenExpiredOrUsed: true });
    post.mockResolvedValue({ data: {} });
    await store.activate("t", "Zx9kLmop-42qR");
    expect(store.success).toBe(true);
    expect(store.alreadyActivated).toBe(false);
    expect(store.tokenExpiredOrUsed).toBe(false);
  });
});
