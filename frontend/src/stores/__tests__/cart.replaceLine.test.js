/**
 * Unit tests for the cart store's `replaceLine` action, which powers the
 * "edit a cart line in place" flow: the QuickAddSheet re-opens seeded with a
 * line's current options/qty/note, and on save we swap the old line for the
 * rebuilt one — merging on key collision rather than producing duplicates.
 */
import { describe, it, expect, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useCartStore } from "../cart";

const line = (over = {}) => ({
  slug: "burger",
  name: "Burger",
  price: 10,
  currency: "MAD",
  qty: 1,
  note: "",
  option_ids: [],
  option_labels: [],
  ...over,
});

describe("cart.replaceLine — edit a line in place", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
  });

  it("replaces a line in place, keeping its position", () => {
    const cart = useCartStore();
    cart.add(line({ slug: "fries", name: "Fries", key: "fries::" }));
    cart.add(line({ slug: "burger", name: "Burger", key: "burger::1", option_ids: [1], qty: 1 }));
    cart.add(line({ slug: "cola", name: "Cola", key: "cola::" }));
    const oldKey = cart.items[1].key;

    // Edit the burger: swap option 1 -> option 2, bump qty to 3.
    cart.replaceLine(oldKey, line({ slug: "burger", name: "Burger", key: "burger::2", option_ids: [2], qty: 3 }));

    expect(cart.items).toHaveLength(3);
    expect(cart.items[1].slug).toBe("burger"); // position preserved
    expect(cart.items[1].option_ids).toEqual([2]);
    expect(cart.items[1].qty).toBe(3);
    expect(cart.items[1].key).not.toBe(oldKey);
  });

  it("merges quantities when the edited line collides with another line", () => {
    const cart = useCartStore();
    // Two distinct burger lines: one plain, one with option 1.
    cart.add(line({ key: "burger::", option_ids: [], qty: 2 }));
    cart.add(line({ key: "burger::1", option_ids: [1], qty: 1 }));
    expect(cart.items).toHaveLength(2);

    // Edit the second line to match the first (drop option 1) -> they merge.
    cart.replaceLine("burger::1", line({ key: "burger::", option_ids: [], qty: 1 }));

    expect(cart.items).toHaveLength(1);
    expect(cart.items[0].key).toBe("burger::");
    expect(cart.items[0].qty).toBe(3); // 2 + 1 merged
  });

  it("preserves a changed note on the replaced line", () => {
    const cart = useCartStore();
    cart.add(line({ key: "burger::::", note: "" }));
    const oldKey = cart.items[0].key;
    cart.replaceLine(oldKey, line({ key: "burger::::no onions", note: "no onions" }));
    expect(cart.items).toHaveLength(1);
    expect(cart.items[0].note).toBe("no onions");
  });

  it("falls back to add() when the old line no longer exists", () => {
    const cart = useCartStore();
    cart.replaceLine("missing::key", line({ key: "burger::", qty: 2 }));
    expect(cart.items).toHaveLength(1);
    expect(cart.items[0].slug).toBe("burger");
    expect(cart.items[0].qty).toBe(2);
  });

  it("ignores a replacement with no slug", () => {
    const cart = useCartStore();
    cart.add(line({ key: "burger::" }));
    cart.replaceLine("burger::", { slug: "", name: "Bad", qty: 1 });
    expect(cart.items).toHaveLength(1);
    expect(cart.items[0].slug).toBe("burger");
  });

  it("persists the change to localStorage", () => {
    const cart = useCartStore();
    cart.add(line({ key: "burger::1", option_ids: [1] }));
    cart.replaceLine("burger::1", line({ key: "burger::2", option_ids: [2] }));
    const stored = JSON.parse(localStorage.getItem(`cart:${window.location.hostname}`) || "[]");
    expect(stored).toHaveLength(1);
    expect(stored[0].option_ids).toEqual([2]);
  });
});
