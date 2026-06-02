/**
 * Unit tests for SparklineChart.
 *
 * Pure SVG component — verifies the point/area math and edge-case guards
 * (empty input, single value, flat series range guard, non-finite filtering).
 * Internal geometry constants: W=80, PAD=2, default height=28 → usableH=24,
 * baseline = height - PAD = 26.
 */
import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import SparklineChart from "../SparklineChart.vue";

describe("SparklineChart", () => {
  it("draws nothing for an empty series", () => {
    const w = mount(SparklineChart, { props: { values: [] } });
    expect(w.find("polyline").exists()).toBe(false);
    expect(w.find("circle").exists()).toBe(false);
    expect(w.find("path").exists()).toBe(false);
  });

  it("renders only a dot for a single value (no line, no area)", () => {
    const w = mount(SparklineChart, { props: { values: [7] } });
    expect(w.find("polyline").exists()).toBe(false);
    expect(w.find("path").exists()).toBe(false);
    const c = w.find("circle");
    expect(c.exists()).toBe(true);
    expect(c.attributes("cx")).toBe("0");   // xStep=0 for a single point
    expect(c.attributes("cy")).toBe("26");  // flat → bottom of band
  });

  it("normalizes min→bottom and max→top across the band", () => {
    const w = mount(SparklineChart, { props: { values: [0, 10] } });
    const poly = w.find("polyline");
    expect(poly.exists()).toBe(true);
    // i0 v0 (min) → (0,26 bottom) ; i1 v10 (max) → (80,2 top)
    expect(poly.attributes("points")).toBe("0,26 80,2");
    const c = w.find("circle"); // dot tracks the last point
    expect(c.attributes("cx")).toBe("80");
    expect(c.attributes("cy")).toBe("2");
  });

  it("handles a flat series without NaN (range guard)", () => {
    const w = mount(SparklineChart, { props: { values: [5, 5, 5] } });
    const points = w.find("polyline").attributes("points");
    expect(points).toBe("0,26 40,26 80,26");
    expect(points).not.toContain("NaN");
  });

  it("filters out null / undefined / NaN values", () => {
    const w = mount(SparklineChart, { props: { values: [0, null, 10, NaN, undefined] } });
    // Only 0 and 10 survive → identical to the [0,10] case
    expect(w.find("polyline").attributes("points")).toBe("0,26 80,2");
  });

  it("omits the filled area when filled=false but keeps the line", () => {
    const w = mount(SparklineChart, { props: { values: [0, 10], filled: false } });
    expect(w.find("path").exists()).toBe(false);
    expect(w.find("polyline").exists()).toBe(true);
  });
});
