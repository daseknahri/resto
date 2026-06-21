/**
 * WAITER-COURSING — course assignment + Hold/Send-now at order entry.
 *
 * Verifies WaiterNewOrder.vue:
 *   - Surfaces the per-line course picker + Send/Hold toggle ONLY when the owner
 *     opted into coursing (a category carries course > 0).
 *   - Sends a per-line `course` override + `fired_course` (place) / `send_now`
 *     (append) in the payloads when coursing is on.
 *   - DEFAULT-PRESERVING: when NO category has a course, the payload is identical
 *     to today — no `course`, no `fired_course`, no `send_now` keys.
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { ref } from "vue";
import { mount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

// Deterministic i18n + Teleport stub so the modal renders inline in jsdom.
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({ t: (k) => k, currentLocale: ref("en") }),
}));

// Mock the api module — capture posts, resolve gets used by onMounted.
const posted = [];
vi.mock("../../lib/api", () => ({
  default: {
    get: vi.fn(async () => ({ data: [] })),
    post: vi.fn(async (url, body) => {
      posted.push({ url, body });
      return { data: { order_number: "ORD-1", status: "pending" } };
    }),
  },
}));

vi.mock("../../lib/idempotency", () => ({ newIdempotencyKey: () => "idem-key" }));

import api from "../../lib/api";
import WaiterNewOrder from "../WaiterNewOrder.vue";
import { useMenuStore } from "../../stores/menu";

const STEAK = { slug: "steak", name: "Steak", price: 50, currency: "MAD", options: [], option_groups: [] };
const SALAD = { slug: "salad", name: "Salad", price: 10, currency: "MAD", options: [], option_groups: [] };

function seedMenu({ steakCourse = 0 } = {}) {
  const menu = useMenuStore();
  menu.categories = [
    { slug: "mains", name: "Mains", course: steakCourse },
    { slug: "starters", name: "Starters", course: 0 },
  ];
  menu.dishes = { mains: [STEAK], starters: [SALAD] };
  return menu;
}

const mountModal = (props = {}) =>
  mount(WaiterNewOrder, {
    props,
    global: { stubs: { Teleport: true, AppIcon: true } },
  });

describe("WaiterNewOrder — coursing at entry", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    posted.length = 0;
    api.post.mockClear();
    localStorage.clear();
  });

  it("DEFAULT: no category course → place-order payload carries no course/fired_course", async () => {
    seedMenu({ steakCourse: 0 });
    const w = mountModal();
    await flushPromises();
    w.vm.tableSlug = "t1";
    w.vm.tableLabel = "T1";
    w.vm.addDish(STEAK);
    await w.vm.submit();

    const place = posted.find((p) => p.url === "/place-order/");
    expect(place).toBeTruthy();
    expect(place.body.items[0]).not.toHaveProperty("course");
    expect(place.body).not.toHaveProperty("fired_course");
  });

  it("coursing on (category course 2) → place-order line carries course=2", async () => {
    seedMenu({ steakCourse: 2 });
    const w = mountModal();
    await flushPromises();
    w.vm.tableSlug = "t1";
    w.vm.tableLabel = "T1";
    w.vm.addDish(STEAK);
    expect(w.vm.coursingEnabled).toBe(true);
    await w.vm.submit();

    const place = posted.find((p) => p.url === "/place-order/");
    expect(place.body.items[0].course).toBe(2);
  });

  it("Send-now with a held course → fired_course=4 on place-order", async () => {
    seedMenu({ steakCourse: 2 });
    const w = mountModal();
    await flushPromises();
    w.vm.tableSlug = "t1";
    w.vm.tableLabel = "T1";
    w.vm.addDish(STEAK);          // course 2 = held by default fired_course=1
    w.vm.sendMode = "send";
    await w.vm.submit();

    const place = posted.find((p) => p.url === "/place-order/");
    expect(place.body.fired_course).toBe(4);
  });

  it("Hold with a held course → no fired_course (courses stay paced)", async () => {
    seedMenu({ steakCourse: 2 });
    const w = mountModal();
    await flushPromises();
    w.vm.tableSlug = "t1";
    w.vm.tableLabel = "T1";
    w.vm.addDish(STEAK);
    w.vm.sendMode = "hold";
    await w.vm.submit();

    const place = posted.find((p) => p.url === "/place-order/");
    expect(place.body).not.toHaveProperty("fired_course");
  });

  it("append (Send now) posts course + send_now=true", async () => {
    seedMenu({ steakCourse: 2 });
    const w = mountModal({ appendToOrderId: 77, appendOrderNumber: 5 });
    await flushPromises();
    w.vm.addDish(STEAK);
    w.vm.sendMode = "send";
    await w.vm.submit();

    const append = posted.find((p) => p.url === "/staff/orders/77/items/");
    expect(append).toBeTruthy();
    expect(append.body.items[0].course).toBe(2);
    expect(append.body.send_now).toBe(true);
  });

  it("append (Hold) posts course + send_now=false", async () => {
    seedMenu({ steakCourse: 2 });
    const w = mountModal({ appendToOrderId: 77, appendOrderNumber: 5 });
    await flushPromises();
    w.vm.addDish(STEAK);
    w.vm.sendMode = "hold";
    await w.vm.submit();

    const append = posted.find((p) => p.url === "/staff/orders/77/items/");
    expect(append.body.send_now).toBe(false);
  });

  it("DEFAULT append: no coursing → append body carries no course/send_now", async () => {
    seedMenu({ steakCourse: 0 });
    const w = mountModal({ appendToOrderId: 77, appendOrderNumber: 5 });
    await flushPromises();
    w.vm.addDish(SALAD);
    await w.vm.submit();

    const append = posted.find((p) => p.url === "/staff/orders/77/items/");
    expect(append.body.items[0]).not.toHaveProperty("course");
    expect(append.body).not.toHaveProperty("send_now");
  });

  it("per-line course override is respected over the category default", async () => {
    seedMenu({ steakCourse: 2 });
    const w = mountModal();
    await flushPromises();
    w.vm.tableSlug = "t1";
    w.vm.tableLabel = "T1";
    w.vm.addDish(STEAK);
    // Waiter re-assigns this line to course 3.
    w.vm.cartItems[0].course = 3;
    await w.vm.submit();

    const place = posted.find((p) => p.url === "/place-order/");
    expect(place.body.items[0].course).toBe(3);
  });
});
