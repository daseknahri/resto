/**
 * Unit tests for OrderStatusTimeline — the status-timeline display of
 * OrderStatus.vue, extracted into a standalone presentational component
 * (RISK FE-2). All status derivation (current step, done-ness, timestamps,
 * progress %, labels) is owned by the parent and passed in as props/function
 * props; this component only renders what it's given.
 */
import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import OrderStatusTimeline from "../OrderStatusTimeline.vue";

const steps = [
  { value: "pending", label: "Pending" },
  { value: "confirmed", label: "Confirmed" },
  { value: "preparing", label: "Preparing" },
  { value: "ready", label: "Ready" },
  { value: "completed", label: "Completed" },
];

const mountComp = (props = {}) =>
  mount(OrderStatusTimeline, {
    props: {
      steps,
      currentStepIndex: 2,
      progressPercent: 60,
      orderStatus: "preparing",
      stepClass: (value) => `class-${value}`,
      isStepDone: (value) => steps.findIndex((s) => s.value === value) <= 2,
      stepTimestamp: (value, idx) => (idx === 0 ? "10:00" : null),
      statusLabel: (status) => `label:${status}`,
      ...props,
    },
  });

describe("OrderStatusTimeline", () => {
  it("renders one step circle per step, in order, with its label", () => {
    const w = mountComp();
    const items = w.findAll("li");
    expect(items.length).toBe(steps.length);
    steps.forEach((step) => {
      expect(w.text()).toContain(step.label);
    });
  });

  it("marks steps up to and including currentStepIndex as done (checkmark) except the current one", () => {
    const w = mountComp({ currentStepIndex: 2 });
    const items = w.findAll("li");
    // step 0 (pending) and 1 (confirmed) are done and not current -> checkmark
    expect(items[0].text()).toContain("✓");
    expect(items[1].text()).toContain("✓");
    // step 2 (preparing) is the current step -> no checkmark, shows pulsing dot instead
    expect(items[2].text()).not.toContain("✓");
    // steps after current show their 1-based index
    expect(items[3].text()).toContain("4");
    expect(items[4].text()).toContain("5");
  });

  it("calls the stepClass function prop for each step's circle", () => {
    const w = mountComp();
    expect(w.text()).not.toBeNull();
    // stepClass("preparing") -> "class-preparing" should be applied as a class
    expect(w.html()).toContain("class-preparing");
    expect(w.html()).toContain("class-pending");
  });

  it("shows the pulse ring only on the current step, and not when the order is completed", () => {
    const active = mountComp({ currentStepIndex: 2, orderStatus: "preparing" });
    expect(active.find(".motion-safe\\:animate-ping").exists()).toBe(true);

    const completed = mountComp({ currentStepIndex: 4, orderStatus: "completed" });
    expect(completed.find(".motion-safe\\:animate-ping").exists()).toBe(false);
  });

  it("renders a step timestamp only when stepTimestamp returns a value", () => {
    const w = mountComp();
    expect(w.text()).toContain("10:00");
  });

  it("renders the progress bar with the given percentage and aria attributes from statusLabel", () => {
    const w = mountComp({ progressPercent: 42, orderStatus: "ready" });
    const bar = w.find('[role="progressbar"]');
    expect(bar.attributes("aria-valuenow")).toBe("42");
    expect(bar.attributes("aria-label")).toBe("label:ready");
    expect(bar.attributes("aria-valuetext")).toBe("label:ready");
    const fill = bar.find("span");
    expect(fill.attributes("style")).toContain("width: 42%");
  });
});
