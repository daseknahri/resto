/**
 * Unit tests for WaiterStaleTablesWarning — the stale-table-statuses warning of
 * WaiterPage's floor view, a STATIC presentational child (RISK FE-2). No
 * props/state/emits; it only renders the fixed warning copy.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({ t: (k) => k }),
}));

import WaiterStaleTablesWarning from "../WaiterStaleTablesWarning.vue";

describe("WaiterStaleTablesWarning", () => {
  it("renders the stale-statuses warning copy with an alert role", () => {
    const w = mount(WaiterStaleTablesWarning);
    expect(w.text()).toContain("waiterPage.tableStatusStale");
    expect(w.find('[role="alert"]').exists()).toBe(true);
  });
});
