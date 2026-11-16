/**
 * Unit tests for WaiterNewOrder — cart line identity (B-11) and append-error
 * mapping + option max-select hint (B-46).
 *
 * WHY: the new-order cart used to merge repeated dishes by dish + options only,
 * so the same dish could not be split across seats (seat/course/note were
 * per-line state edited after adding, and the second add's note was dropped).
 * The append endpoint's 409 codes also collapsed to one generic message, and
 * taps beyond an option group's max_select were silently ignored.
 *
 * Harness: follows the existing WaiterNewOrder tests in this folder
 * (WaiterNewOrderCoursing / WaiterNewOrderSearchLoading) — real menu store
 * seeded via useMenuStore(), the component driven through w.vm (addDish /
 * submit / cartItems), api mocked with a `posted` capture array, i18n mocked
 * with a param-aware t so keys + params stay assertable. Each describe has
 * its own isolation beforeEach (localStorage.clear + setActivePinia(createPinia)
 * + vi.clearAllMocks + targeted api resets); nothing relies on another
 * describe's hook.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { ref } from "vue";
import { mount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

// Deterministic i18n + Teleport/AppIcon stubs so the modal renders inline.
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k),
    currentLocale: ref("en"),
  }),
}));

// Mock the api module — capture posts, resolve gets used by onMounted.
const posted = [];
vi.mock("../../lib/api", () => ({
  default: {
    get: vi.fn(async () => ({ data: [] })),
    post: vi.fn(async (url, body) => {
      posted.push({ url, body });
      return { data: {} };
    }),
    patch: vi.fn(async () => ({ data: {} })),
    delete: vi.fn(async () => ({ data: {} })),
  },
}));

vi.mock("../../lib/idempotency", () => ({ newIdempotencyKey: () => "idem-key" }));

import api from "../../lib/api";
import WaiterNewOrder from "../WaiterNewOrder.vue";
import { useMenuStore } from "../../stores/menu";
import { useToastStore } from "../../stores/toast";

// ── Fixtures ────────────────────────────────────────────────────────────────
const plainDish = (overrides = {}) => ({
  slug: "tomato-soup",
  name: "Tomato Soup",
  description: "Warm and rich.",
  price: 45,
  is_available: true,
  ...overrides,
});

const extrasDish = (overrides = {}) => ({
  slug: "pizza",
  name: "Pizza",
  description: "Wood-fired.",
  price: 80,
  is_available: true,
  option_groups: [
    {
      id: 1,
      name: "Extras",
      min_select: 0,
      max_select: 2,
      options: [
        { id: 11, name: "Cheese", price_delta: 5 },
        { id: 12, name: "Bacon", price_delta: 8 },
        { id: 13, name: "Mushrooms", price_delta: 6 },
      ],
    },
  ],
  ...overrides,
});

const sizeDish = (overrides = {}) => ({
  slug: "pasta",
  name: "Pasta",
  description: "Fresh daily.",
  price: 60,
  is_available: true,
  option_groups: [
    {
      id: 2,
      name: "Size",
      min_select: 1,
      max_select: 1,
      options: [
        { id: 21, name: "Regular", price_delta: 0 },
        { id: 22, name: "Large", price_delta: 10 },
      ],
    },
  ],
  ...overrides,
});

const seedMenu = (dishes, category = {}) => {
  const menu = useMenuStore();
  menu.categories = [{ slug: "mains", name: "Mains", course: 0, ...category }];
  menu.dishes = { mains: dishes };
  return menu;
};

// ── Mount + query helpers ───────────────────────────────────────────────────
let wrapper;

const mountModal = async (props = {}) => {
  wrapper = mount(WaiterNewOrder, {
    props,
    global: { stubs: { Teleport: true, AppIcon: true } },
  });
  await flushPromises();
  return wrapper;
};

// One seat select per cart line (dine-in); the table dropdown has a different
// aria-label and is excluded by this selector.
const seatSelects = () =>
  wrapper.findAll('select[aria-label*="waiterPage.seatPickerLabel"]');
// One qty span per cart line (the dish-list stepper span has no aria-label).
const cartQtySpans = () =>
  wrapper.findAll('span[aria-label*="waiterPage.newOrderQtyLabel"]');
const courseChipButtons = (n) =>
  wrapper
    .findAll("button")
    .filter((b) => b.text() === `waiterPage.courseChip:${JSON.stringify({ n })}`);
const addToOrderButton = () =>
  wrapper
    .findAll("button")
    .find((b) => b.text().includes("waiterPage.newOrderAddToOrder"));

const isolate = () => {
  localStorage.clear();
  setActivePinia(createPinia());
  vi.clearAllMocks();
  posted.length = 0;
  api.get.mockReset();
  api.get.mockResolvedValue({ data: [] });
  api.post.mockReset();
  api.post.mockImplementation(async (url, body) => {
    posted.push({ url, body });
    return { data: {} };
  });
};

const unmount = () => {
  if (wrapper) wrapper.unmount();
  wrapper = undefined;
};

// ── B-11: cart line identity ────────────────────────────────────────────────
describe("WaiterNewOrder — cart lines split across seats/courses/notes (B-11)", () => {
  beforeEach(isolate);
  afterEach(unmount);

  it("merges a repeat add of the same dish with untouched seat/course/note", async () => {
    const dish = plainDish();
    seedMenu([dish]);
    await mountModal();
    wrapper.vm.addDish(dish);
    wrapper.vm.addDish(dish);
    await wrapper.vm.$nextTick();

    expect(wrapper.vm.cartItems).toHaveLength(1);
    expect(wrapper.vm.cartItems[0].qty).toBe(2);
    expect(seatSelects()).toHaveLength(1);
    expect(cartQtySpans()[0].text()).toBe("2");
  });

  it("splits the same dish across seats: seat edited, then re-added", async () => {
    const dish = plainDish();
    seedMenu([dish]);
    await mountModal();
    wrapper.vm.addDish(dish);
    // Seat the first line at seat 2, then add the same dish again.
    wrapper.vm.cartItems[0].seat = 2;
    wrapper.vm.addDish(dish);
    await wrapper.vm.$nextTick();

    expect(wrapper.vm.cartItems).toHaveLength(2);
    expect(wrapper.vm.cartItems.map((i) => i.seat)).toEqual([2, 0]);
    // Each line keeps qty 1 — the second add did not collapse into the first.
    expect(wrapper.vm.cartItems.map((i) => i.qty)).toEqual([1, 1]);
    expect(seatSelects()).toHaveLength(2);
    expect(seatSelects()[0].element.value).toBe("2");
    expect(seatSelects()[1].element.value).toBe("0");
  });

  it("splits the same dish when the first line carries a note", async () => {
    const dish = plainDish();
    seedMenu([dish]);
    await mountModal();
    wrapper.vm.addDish(dish);
    wrapper.vm.cartItems[0].note = "no salt";
    wrapper.vm.addDish(dish);
    await wrapper.vm.$nextTick();

    expect(wrapper.vm.cartItems).toHaveLength(2);
    expect(wrapper.vm.cartItems.map((i) => i.note)).toEqual(["no salt", ""]);
    expect(wrapper.vm.cartItems.map((i) => i.qty)).toEqual([1, 1]);
  });

  it("splits the same dish across courses", async () => {
    const dish = plainDish();
    seedMenu([dish], { course: 1 });
    await mountModal();
    wrapper.vm.addDish(dish);
    // Move the first line to course 2, then add the same dish again.
    wrapper.vm.cartItems[0].course = 2;
    wrapper.vm.addDish(dish);
    await wrapper.vm.$nextTick();

    expect(wrapper.vm.cartItems).toHaveLength(2);
    // Line 1 sits on course 2, line 2 on the category default (course 1).
    expect(wrapper.vm.cartItems.map((i) => i.course)).toEqual([2, 1]);
    expect(courseChipButtons(2).map((b) => b.attributes("data-active"))).toEqual(["true", "false"]);
    expect(courseChipButtons(1).map((b) => b.attributes("data-active"))).toEqual(["false", "true"]);
  });

  it("keeps different option combinations on separate lines", async () => {
    const dish = extrasDish();
    seedMenu([dish]);
    await mountModal();
    // Line 1: Cheese only.
    wrapper.vm.addDish(dish);
    await wrapper.vm.$nextTick();
    const boxes = () => wrapper.findAll('input[type="checkbox"]');
    expect(boxes()).toHaveLength(3);
    await boxes()[0].setChecked(true);
    await addToOrderButton().trigger("click");
    await flushPromises();
    // Line 2: Bacon only.
    wrapper.vm.addDish(dish);
    await wrapper.vm.$nextTick();
    await boxes()[1].setChecked(true);
    await addToOrderButton().trigger("click");
    await flushPromises();

    expect(wrapper.vm.cartItems).toHaveLength(2);
    expect(wrapper.vm.cartItems.map((i) => i.option_ids)).toEqual([[11], [12]]);
    expect(wrapper.vm.cartItems.map((i) => i.qty)).toEqual([1, 1]);
    expect(seatSelects()).toHaveLength(2);
  });
});

// ── B-46: append error mapping ──────────────────────────────────────────────
describe("WaiterNewOrder — append error mapping (B-46)", () => {
  beforeEach(isolate);
  afterEach(unmount);

  const mountAppendWithItem = async () => {
    const dish = plainDish();
    seedMenu([dish]);
    await mountModal({ appendToOrderId: 42, appendOrderNumber: 7 });
    wrapper.vm.addDish(dish);
    await wrapper.vm.$nextTick();
  };

  const rejectAppend = (data) =>
    api.post.mockRejectedValueOnce({ response: { data } });

  it("maps already_paid to its own message", async () => {
    await mountAppendWithItem();
    rejectAppend({ code: "already_paid", detail: "Order is already paid." });
    await wrapper.vm.submit();
    await wrapper.vm.$nextTick();

    expect(wrapper.vm.submitError).toBe("waiterPage.addFailedAlreadyPaid");
    expect(wrapper.find('[role="alert"]').text()).toContain(
      "waiterPage.addFailedAlreadyPaid"
    );
    // mockRejectedValueOnce bypasses the posted-capture impl, so read the
    // call straight off the mock.
    expect(api.post.mock.calls[0][0]).toBe("/staff/orders/42/items/");
  });

  it("maps not_table to its own message", async () => {
    await mountAppendWithItem();
    rejectAppend({ code: "not_table", detail: "Items can only be appended to table orders." });
    await wrapper.vm.submit();
    await wrapper.vm.$nextTick();

    expect(wrapper.vm.submitError).toBe("waiterPage.addFailedNotTable");
    expect(wrapper.find('[role="alert"]').text()).toContain(
      "waiterPage.addFailedNotTable"
    );
  });

  it("maps bad_status to its own message", async () => {
    await mountAppendWithItem();
    rejectAppend({ code: "bad_status", detail: "Order is not in an editable state." });
    await wrapper.vm.submit();
    await wrapper.vm.$nextTick();

    expect(wrapper.vm.submitError).toBe("waiterPage.addFailedBadStatus");
    expect(wrapper.find('[role="alert"]').text()).toContain(
      "waiterPage.addFailedBadStatus"
    );
  });

  it("keeps the backend detail for out_of_stock", async () => {
    await mountAppendWithItem();
    rejectAppend({ code: "out_of_stock", detail: "Only 1 left in stock." });
    await wrapper.vm.submit();
    await wrapper.vm.$nextTick();

    expect(wrapper.vm.submitError).toBe("Only 1 left in stock.");
  });

  it("falls back to the generic message for unknown failures", async () => {
    await mountAppendWithItem();
    api.post.mockRejectedValueOnce(new Error("boom"));
    await wrapper.vm.submit();
    await wrapper.vm.$nextTick();

    expect(wrapper.vm.submitError).toBe("waiterPage.addFailed");
  });
});

// ── B-46: option max-select hint ────────────────────────────────────────────
describe("WaiterNewOrder — option max-select hint (B-46)", () => {
  beforeEach(isolate);
  afterEach(unmount);

  it("blocks a third pick at max_select 2: toast + box reset, selection kept", async () => {
    const dish = extrasDish();
    seedMenu([dish]);
    await mountModal();
    const show = vi.spyOn(useToastStore(), "show");
    wrapper.vm.addDish(dish);
    await wrapper.vm.$nextTick();
    const boxes = () => wrapper.findAll('input[type="checkbox"]');
    expect(boxes()).toHaveLength(3);

    await boxes()[0].setChecked(true);
    await boxes()[1].setChecked(true);
    expect(boxes()[0].element.checked).toBe(true);
    expect(boxes()[1].element.checked).toBe(true);

    await boxes()[2].setChecked(true);
    await flushPromises();

    const fresh = boxes();
    expect(fresh[0].element.checked).toBe(true);
    expect(fresh[1].element.checked).toBe(true);
    // The refused pick is reset to unchecked (C-11 pattern): without the
    // event-target reset the box would stay visually checked.
    expect(fresh[2].element.checked).toBe(false);
    expect(show).toHaveBeenCalledWith(
      'dishPage.maxSelectReached:{"n":2}',
      "error"
    );
  });

  it("single-select (radio) groups still swap without a toast", async () => {
    const dish = sizeDish();
    seedMenu([dish]);
    await mountModal();
    const show = vi.spyOn(useToastStore(), "show");
    wrapper.vm.addDish(dish);
    await wrapper.vm.$nextTick();
    const radios = () => wrapper.findAll('input[type="radio"]');
    expect(radios()).toHaveLength(2);
    // Size is required (min_select 1), so Regular is pre-selected.
    expect(radios()[0].element.checked).toBe(true);

    await radios()[1].setChecked(true);
    await flushPromises();

    const fresh = radios();
    expect(fresh[0].element.checked).toBe(false);
    expect(fresh[1].element.checked).toBe(true);
    expect(show).not.toHaveBeenCalled();
  });
});
