import { describe, it, expect, vi } from "vitest";

// Pure mirror of OwnerZReport.vue's fetchDrawerSessions error handling. The bug
// this locks: a network/API failure used to be swallowed and defaulted to an
// empty sessions list, making a failed fetch indistinguishable from a genuine
// "no sessions today". That hid the amber close-shift prompt (openDrawerSession
// became null), so a live shift could silently never be closed. The fix tracks
// the failure separately via drawerError so a distinct inline error + Retry is
// surfaced instead of a silent empty state.
async function fetchDrawerSessions(apiGet, state, selectedDate) {
  state.drawerError = false;
  try {
    const params = {};
    if (selectedDate) params.date = selectedDate;
    const { data } = await apiGet("/owner/drawer/history/", { params, timeout: 5000 });
    state.sessions = data?.sessions ?? [];
  } catch {
    state.sessions = [];
    state.drawerError = true;
  }
}

// Mirror of the openDrawerSession computed.
const openDrawerSession = (sessions) => sessions.find((s) => s.status === "open") ?? null;

describe("z-report drawer-session fetch error handling", () => {
  it("populates sessions and clears drawerError on a successful fetch", async () => {
    const state = { sessions: [], drawerError: true };
    const apiGet = vi.fn().mockResolvedValue({ data: { sessions: [{ id: 1, status: "open" }] } });

    await fetchDrawerSessions(apiGet, state, "");

    expect(state.drawerError).toBe(false);
    expect(state.sessions).toHaveLength(1);
    expect(openDrawerSession(state.sessions)).not.toBeNull();
  });

  it("treats a legitimately empty result as no-error (empty list, no drawerError)", async () => {
    const state = { sessions: [{ id: 9 }], drawerError: true };
    const apiGet = vi.fn().mockResolvedValue({ data: { sessions: [] } });

    await fetchDrawerSessions(apiGet, state, "2026-08-27");

    expect(state.drawerError).toBe(false);
    expect(state.sessions).toEqual([]);
    expect(openDrawerSession(state.sessions)).toBeNull();
  });

  it("flags drawerError on a fetch failure instead of silently defaulting to []", async () => {
    const state = { sessions: [], drawerError: false };
    const apiGet = vi.fn().mockRejectedValue(new Error("network down"));

    await fetchDrawerSessions(apiGet, state, "");

    // The key invariant: a failure is NOT the same as "no sessions". Sessions is
    // empty (so openDrawerSession is null and the amber card is correctly hidden),
    // but drawerError is true so the UI surfaces a distinct error + Retry instead.
    expect(state.sessions).toEqual([]);
    expect(state.drawerError).toBe(true);
    expect(openDrawerSession(state.sessions)).toBeNull();
  });

  it("forwards the selected service day as a query param when set", async () => {
    const state = { sessions: [], drawerError: false };
    const apiGet = vi.fn().mockResolvedValue({ data: { sessions: [] } });

    await fetchDrawerSessions(apiGet, state, "2026-08-27");

    expect(apiGet).toHaveBeenCalledWith(
      "/owner/drawer/history/",
      { params: { date: "2026-08-27" }, timeout: 5000 }
    );
  });
});
