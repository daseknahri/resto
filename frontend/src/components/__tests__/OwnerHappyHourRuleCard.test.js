/**
 * Unit tests for OwnerHappyHourRuleCard — a single happy-hour rule card from
 * OwnerPromotions.vue's Happy Hours list, extracted into a standalone
 * presentational component (RISK FE-2). Display only: it renders one rule and
 * forwards edit / delete to the parent via emits; the parent keeps the rules
 * list and API mutations.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k),
  }),
}));

import OwnerHappyHourRuleCard from "../OwnerHappyHourRuleCard.vue";

const rule = (overrides = {}) => ({
  id: 3,
  name: "Sunset 15%",
  is_active: true,
  percent_off: 15,
  start_time: "17:00",
  end_time: "19:00",
  days: [0, 1, 2],
  category_ids: [],
  ...overrides,
});

const isOvernight = (r) => r.start_time > r.end_time;
const dayLabels = (days) => `days(${days.join("/")})`;

const mountCard = (props = {}) =>
  mount(OwnerHappyHourRuleCard, {
    props: { rule: rule(), index: 0, isOvernight, dayLabels, deleting: false, ...props },
  });

describe("OwnerHappyHourRuleCard", () => {
  it("renders the name, percent off and time window", () => {
    const w = mountCard();
    expect(w.text()).toContain("Sunset 15%");
    expect(w.text()).toContain("-15%");
    expect(w.text()).toContain("17:00");
    expect(w.text()).toContain("19:00");
  });

  it("shows the active / inactive badge", () => {
    expect(mountCard({ rule: rule({ is_active: true }) }).text()).toContain("happyHour.activeNow");
    expect(mountCard({ rule: rule({ is_active: false }) }).text()).toContain("happyHour.inactive");
  });

  it("shows the overnight hint only when the predicate says so", () => {
    expect(mountCard({ rule: rule({ start_time: "22:00", end_time: "02:00" }) }).text()).toContain("happyHour.overnightHint");
    expect(mountCard({ rule: rule({ start_time: "17:00", end_time: "19:00" }) }).text()).not.toContain("happyHour.overnightHint");
  });

  it("renders day labels via the formatter, or the fallback hint when empty", () => {
    expect(mountCard({ rule: rule({ days: [0, 1] }) }).text()).toContain("days(0/1)");
    expect(mountCard({ rule: rule({ days: [] }) }).text()).toContain("ownerPromotions.daysHint");
  });

  it("shows the scope line: some categories vs all", () => {
    expect(mountCard({ rule: rule({ category_ids: [4, 5] }) }).text()).toContain('happyHour.scope_some:{"n":2}');
    expect(mountCard({ rule: rule({ category_ids: [] }) }).text()).toContain("happyHour.allCategories");
  });

  it("emits edit with the rule", async () => {
    const r = rule();
    const w = mountCard({ rule: r });
    const editBtn = w.findAll("button").find((b) => b.text() === "common.edit");
    await editBtn.trigger("click");
    expect(w.emitted("edit")[0]).toEqual([r]);
  });

  it("emits delete with the rule", async () => {
    const r = rule();
    const w = mountCard({ rule: r });
    const deleteBtn = w.findAll("button").find((b) => b.text() === "common.delete");
    await deleteBtn.trigger("click");
    expect(w.emitted("delete")[0]).toEqual([r]);
  });

  it("disables the delete button while its request is in flight", () => {
    const w = mountCard({ deleting: true });
    const deleteBtn = w.findAll("button").find((b) => b.text() === "common.delete");
    expect(deleteBtn.attributes("disabled")).toBeDefined();
  });
});
