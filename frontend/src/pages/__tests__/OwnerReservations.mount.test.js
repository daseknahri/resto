/**
 * Mount smoke test for OwnerReservations.vue (the owner reservations / bookings
 * management page, ~1304 lines).
 *
 * WHY: the app's recurring production bug class is "a page white-screens on load
 * because a setup()-time error (TDZ, undefined-map access, an unguarded browser
 * API) was never caught by a test". OwnerReservations is a busy owner surface —
 * an onMounted that reads a localStorage-backed SWR cache then fires two GETs
 * (/owner/reservations/ + /owner/waitlist/), a dozen status/SLA/reminder mapping
 * helpers, and a list v-for with per-reservation date math (formatDateTime),
 * tel:/wa.me href builders, and timeline/selection state maps. Mounting runs all
 * of that for real, so a crash in setup() or the initial render fails CI here
 * instead of in production.
 *
 * Pattern-faithful to pages/__tests__/OwnerHome.mount.test.js (URL-routed api
 * mock + real pinia):
 *   - shallowMount (auto-stubs the heavy children: ReservationCalendar,
 *     OwnerReservationsCalendarDetail, OwnerReservationsWaitlist, AppIcon)
 *   - real pinia (the toast store runs for real) + a mocked lib/api
 *   - useI18n mocked to exactly { t, formatDateTime } (the page's real destructure)
 *
 * NOT mocked / left REAL because they are jsdom-safe and never touched at mount:
 *   - useConfirmModal (module-level refs only; confirm() runs on user action, not
 *     at setup)
 *   - lib/staleCache readCache/writeCache (try/catch localStorage — an empty cache
 *     falls through to the mocked network). localStorage.clear() in beforeEach so
 *     one test's default-view cache write can't leak into the next.
 *   - lib/escape safeExternalUrl (only called inside reminder handlers)
 *
 * The page imports NOTHING from 'vue-router' (verified), so vue-router is NOT
 * mocked and no vi.hoisted RouterLink stub is needed. There is no poll / interval
 * / WebSocket registered at mount, but afterEach still unmounts as hygiene.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    // t returns the key verbatim (params, when present, are appended so the raw
    // key path is still asserted-on). formatDateTime is a plain stringify.
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    formatDateTime: (v) => String(v),
  }),
}));

// URL-routed api mock: onMounted fires GET /owner/reservations/ and
// GET /owner/waitlist/. Default: everything resolves { data: {} } so the empty
// list path renders. Tests set _routes to drive the loaded path.
// _routes/_match are plain (not vi.hoisted): they are only read lazily inside the
// vi.fn callback when api.get is actually invoked at mount — never during the
// hoisted factory's own evaluation — so there is no TDZ.
let _routes = {};
const _match = (url) => {
  const hit = Object.keys(_routes).find((frag) => url.includes(frag));
  return hit ? _routes[hit] : { data: {} };
};
vi.mock("../../lib/api", () => ({
  // shared canonical extractor (added to lib/api; mock returns the fallback)
  extractApiErrorMessage: (err, fallback = "") => fallback,
  default: {
    get: vi.fn((url) => Promise.resolve(_match(url))),
    post: vi.fn(() => Promise.resolve({ data: {} })),
    put: vi.fn(() => Promise.resolve({ data: {} })),
    patch: vi.fn(() => Promise.resolve({ data: {} })),
    delete: vi.fn(() => Promise.resolve({ data: {} })),
  },
}));

import OwnerReservations from "../OwnerReservations.vue";

const mountPage = () => shallowMount(OwnerReservations);

// A realistic reservation row with the fields the page's own template + computeds
// read: name, status, booked_for/party_size, created_at, sla_state, phone/email,
// notes, reminder counters + last_reminder_status.
const reservation = (overrides = {}) => ({
  id: 1,
  name: "Sara Bennani",
  status: "new",
  booked_for: "2026-09-10T19:30:00Z",
  party_size: 4,
  created_at: "2026-09-05T12:00:00Z",
  follow_up_due_at: "2026-09-06T09:00:00Z",
  sla_state: "on_track",
  phone: "+212612345678",
  email: "sara@example.com",
  notes: "Window table please",
  reminder_count: 1,
  reminder_opened_count: 0,
  reminder_failed_count: 0,
  last_reminder_status: "sent",
  last_reminder_at: "2026-09-05T13:00:00Z",
  ...overrides,
});

describe("OwnerReservations — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
    // fetchReservations writes the default (unfiltered, page-1) view into the REAL
    // localStorage-backed staleCache. Clear it so test 1's write can't be served
    // to test 2 and mask its /owner/reservations/ mock payload.
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  // ── (1) empty / default mount ──────────────────────────────────────────────
  // The core guard: the onMounted cache-read + fetchReservations() + fetchWaitlist()
  // and the whole list-view template must render with empty data and not throw.
  it("mounts with empty data (no reservations) without a setup() crash", async () => {
    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    // Header (always rendered, outside every v-if) — the crash-guard anchor.
    expect(wrapper.text()).toContain("ownerReservations.title");
    expect(wrapper.text()).toContain("ownerReservations.kicker");
    // Default view is "list"; empty results → the empty-state article renders.
    expect(wrapper.text()).toContain("ownerReservations.noReservations");
  });

  // ── (2) loaded state with a realistic reservations payload ─────────────────
  // Drives the list v-for + every per-row helper (statusLabel/statusClass,
  // slaLabel/slaClass, reminderStatusLabel/reservationCardClass, telHref/whatsappHref,
  // formatDate over booked_for/created_at/follow_up_due_at) — the own-template
  // paths that only run with a non-empty reservations array.
  it("mounts with a loaded reservations payload without a crash", async () => {
    _routes = {
      "/owner/reservations/": {
        data: {
          results: [
            reservation(),
            reservation({
              id: 2,
              name: "Youssef Alami",
              status: "contacted",
              sla_state: "overdue",
              sla_minutes_overdue: 45,
              last_reminder_status: "failed",
              last_reminder_failure_reason: "Invalid number",
              reminder_failed_count: 1,
            }),
          ],
          pagination: { page: 1, page_size: 20, total: 2, pages: 1, has_next: false, has_prev: false },
          counts: { total: 2, new: 1, contacted: 1, won: 0, lost: 0, overdue_new: 1 },
        },
      },
    };

    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    expect(wrapper.text()).toContain("ownerReservations.title");
    // The v-for rendered the loaded rows (proves the loaded list path ran clean).
    expect(wrapper.text()).toContain("Sara Bennani");
    expect(wrapper.text()).toContain("Youssef Alami");
  });
});


// ── Run 8 S1-D (B-06 / B-07) — reminder preparation + pending reconciliation ──
// Appended 2026-11-15. Base above untouched: the new tests only ADD coverage.
//
// B-06: tapping Reminder must NOT auto-mark the reminder opened/failed from
// whether the WhatsApp popup opened. The backend records it as prepared
// (status "sent") and the entry joins the pending list for the owner to
// confirm the real outcome from the banner.
// B-07: bulk prepare keeps ALL prepared items pending (no first-item
// auto-reconcile), the pending list survives reload via localStorage, and
// reconciling drops only the rows the backend actually updated — rows it
// could not find stay pending for retry.
import api from "../../lib/api";

const PENDING_KEY = "owner.reservations.pendingReminders";

const _loadedPayload = (rows) => ({
  data: {
    results: rows,
    pagination: { page: 1, page_size: 20, total: rows.length, pages: 1, has_next: false, has_prev: false },
    counts: { total: rows.length, new: 1, contacted: 0, won: 0, lost: 0, overdue_new: 0 },
  },
});

describe("OwnerReservations — reminders (Run 8 S1-D, B-06/B-07)", () => {
  let wrapper;
  let _postHandler;
  let _openResult;

  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
    _postHandler = () => Promise.resolve({ data: {} });
    _openResult = { closed: false };
    api.post.mockImplementation((url, body) => _postHandler(url, body));
    vi.spyOn(window, "open").mockImplementation(() => _openResult);
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
    vi.restoreAllMocks();
  });

  const _buttonWith = (text) => wrapper.findAll("button").find((b) => b.text().includes(text));
  const _pendingFromStorage = () => JSON.parse(localStorage.getItem(PENDING_KEY) || "null");
  const _postedUrls = () => api.post.mock.calls.map((c) => c[0]);

  // ── B-06: single reminder ────────────────────────────────────────────────

  it("single reminder prepares without auto-marking opened/failed", async () => {
    _routes = { "/owner/reservations/": _loadedPayload([reservation()]) };
    _postHandler = (url) => {
      if (url.includes("/reminder/") && !url.includes("reminder-result")) {
        return Promise.resolve({
          data: { id: 55, status: "sent", whatsapp_link: "https://wa.me/212612345678?text=hi" },
        });
      }
      return Promise.resolve({ data: {} });
    };
    wrapper = mountPage();
    await flushPromises();

    const btn = _buttonWith("ownerReservations.reminder");
    expect(btn.exists()).toBe(true);
    await btn.trigger("click");
    await flushPromises();

    expect(_postedUrls()).toContain("/owner/reservations/1/reminder/");
    // No outcome is inferred from the popup: no reminder-result call at all.
    expect(_postedUrls().filter((u) => u.includes("reminder-result"))).toEqual([]);
    // The prepared reminder waits in the pending banner, persisted for retry.
    expect(wrapper.text()).toContain('ownerReservations.pendingReminderCount({"count":1})');
    expect(_pendingFromStorage()).toEqual([
      { lead_id: 1, reminder_id: 55, whatsapp_link: "https://wa.me/212612345678?text=hi" },
    ]);
  });

  it("single reminder with a blocked popup still queues as prepared, not failed", async () => {
    _openResult = null; // window.open blocked
    _routes = { "/owner/reservations/": _loadedPayload([reservation()]) };
    _postHandler = (url) => {
      if (url.includes("/reminder/") && !url.includes("reminder-result")) {
        return Promise.resolve({
          data: { id: 56, status: "sent", whatsapp_link: "https://wa.me/212612345678?text=hi" },
        });
      }
      return Promise.resolve({ data: {} });
    };
    wrapper = mountPage();
    await flushPromises();

    await _buttonWith("ownerReservations.reminder").trigger("click");
    await flushPromises();

    expect(_postedUrls().filter((u) => u.includes("reminder-result"))).toEqual([]);
    expect(wrapper.text()).toContain('ownerReservations.pendingReminderCount({"count":1})');
    expect(_pendingFromStorage()).toHaveLength(1);
    expect(_pendingFromStorage()[0].reminder_id).toBe(56);
  });

  // ── B-07: bulk prepare ───────────────────────────────────────────────────

  it("bulk retry keeps every prepared item pending and never auto-reconciles", async () => {
    _routes = {
      "/owner/reservations/": _loadedPayload([
        reservation(),
        reservation({ id: 2, name: "Youssef Alami", phone: "+212622222222" }),
      ]),
    };
    _postHandler = (url) => {
      if (url.includes("/bulk-reminder/") && !url.includes("bulk-reminder-result")) {
        return Promise.resolve({
          data: {
            prepared_count: 2,
            results: [
              { lead_id: 1, reminder_id: 11, whatsapp_link: "https://wa.me/111?text=x" },
              { lead_id: 2, reminder_id: 12, whatsapp_link: "https://wa.me/222?text=x" },
            ],
            missing_ids: [99],
            skipped_no_phone_ids: [],
            skipped_unavailable_ids: [],
            skipped_not_failed_ids: [],
          },
        });
      }
      return Promise.resolve({ data: {} });
    };
    wrapper = mountPage();
    await flushPromises();

    // Select the two REAL rows (aria-label is the reservation name).
    await wrapper.find('input[aria-label="Sara Bennani"]').setChecked(true);
    await wrapper.find('input[aria-label="Youssef Alami"]').setChecked(true);
    await _buttonWith("ownerReservations.bulkRetryReminders").trigger("click");
    await flushPromises();

    expect(_postedUrls()).toContain("/owner/reservations/bulk-reminder/");
    // The old code auto-reconciled the first item here; nothing is reconciled now.
    expect(_postedUrls().filter((u) => u.includes("bulk-reminder-result"))).toEqual([]);
    // Both prepared items wait in the banner, persisted across reloads.
    expect(wrapper.text()).toContain('ownerReservations.pendingReminderCount({"count":2})');
    expect(_pendingFromStorage()).toHaveLength(2);
  });

  // ── B-07: reconcile per-item outcomes + persistence ──────────────────────

  it("reconcile drops updated rows but keeps the ones the backend could not find", async () => {
    localStorage.setItem(
      PENDING_KEY,
      JSON.stringify([
        { lead_id: 1, reminder_id: 11, whatsapp_link: "https://wa.me/111?text=x" },
        { lead_id: 2, reminder_id: 12, whatsapp_link: "https://wa.me/222?text=x" },
      ])
    );
    _routes = { "/owner/reservations/": _loadedPayload([reservation()]) };
    _postHandler = (url) => {
      if (url.includes("bulk-reminder-result")) {
        return Promise.resolve({
          data: {
            updated_count: 1,
            missing_count: 1,
            updated: [{ lead_id: 1, reminder_id: 11, status: "opened" }],
            missing: [{ lead_id: 2, reminder_id: 12, reason: "not_found" }],
            already_reconciled: [],
          },
        });
      }
      return Promise.resolve({ data: {} });
    };
    wrapper = mountPage();
    await flushPromises();

    // Restored from localStorage on mount.
    expect(wrapper.text()).toContain('ownerReservations.pendingReminderCount({"count":2})');

    await _buttonWith("ownerReservations.markOpened").trigger("click");
    await flushPromises();

    const resultCalls = api.post.mock.calls.filter((c) => c[0].includes("bulk-reminder-result"));
    expect(resultCalls).toHaveLength(1);
    expect(resultCalls[0][1]).toEqual({
      items: [
        { lead_id: 1, reminder_id: 11, status: "opened", error: "" },
        { lead_id: 2, reminder_id: 12, status: "opened", error: "" },
      ],
    });
    // The missing row stays pending (and persisted) for retry; the updated one leaves.
    expect(wrapper.text()).toContain('ownerReservations.pendingReminderCount({"count":1})');
    expect(_pendingFromStorage()).toHaveLength(1);
    expect(_pendingFromStorage()[0].reminder_id).toBe(12);
  });

  it("pending reminders are restored from storage on mount without any network write", async () => {
    localStorage.setItem(
      PENDING_KEY,
      JSON.stringify([{ lead_id: 1, reminder_id: 11, whatsapp_link: "https://wa.me/111?text=x" }])
    );
    _routes = { "/owner/reservations/": _loadedPayload([reservation()]) };
    wrapper = mountPage();
    await flushPromises();

    expect(wrapper.text()).toContain('ownerReservations.pendingReminderCount({"count":1})');
    expect(api.post).not.toHaveBeenCalled();
  });

  it("rows the backend reports as already reconciled leave the pending list", async () => {
    localStorage.setItem(
      PENDING_KEY,
      JSON.stringify([
        { lead_id: 1, reminder_id: 11, whatsapp_link: "https://wa.me/111?text=x" },
        { lead_id: 2, reminder_id: 12, whatsapp_link: "https://wa.me/222?text=x" },
      ])
    );
    _routes = { "/owner/reservations/": _loadedPayload([reservation()]) };
    _postHandler = (url) => {
      if (url.includes("bulk-reminder-result")) {
        return Promise.resolve({
          data: {
            updated_count: 0,
            missing_count: 0,
            already_reconciled_count: 2,
            updated: [],
            missing: [],
            already_reconciled: [
              { lead_id: 1, reminder_id: 11, status: "opened" },
              { lead_id: 2, reminder_id: 12, status: "failed" },
            ],
          },
        });
      }
      return Promise.resolve({ data: {} });
    };
    wrapper = mountPage();
    await flushPromises();

    await _buttonWith("ownerReservations.markOpened").trigger("click");
    await flushPromises();

    expect(wrapper.text()).not.toContain("ownerReservations.pendingReminderCount");
    expect(localStorage.getItem(PENDING_KEY)).toBeNull();
  });
});

describe("OwnerReservations — S1-I B-15 wa.me links", () => {
  let wrapper;

  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  // B-15: national-format lead phone ("06…") links to wa.me/212…; bare digits
  // with no leading 0 / + / 00 are refused, never guessed — no link renders.
  it("builds wa.me links with the 212 country code, and hides the link for bare digits (B-15)", async () => {
    _routes = {
      "/owner/reservations/": {
        data: {
          results: [
            reservation({ phone: "0678901234" }),
            reservation({
              id: 2,
              name: "Youssef Alami",
              status: "contacted",
              sla_state: "overdue",
              sla_minutes_overdue: 45,
              last_reminder_status: "failed",
              last_reminder_failure_reason: "Invalid number",
              reminder_failed_count: 1,
              phone: "612345678",
            }),
          ],
          pagination: { page: 1, page_size: 20, total: 2, pages: 1, has_next: false, has_prev: false },
          counts: { total: 2, new: 1, contacted: 1, won: 0, lost: 0, overdue_new: 1 },
        },
      },
    };

    wrapper = mountPage();
    await flushPromises();

    const html = wrapper.html();
    expect(html).toContain("wa.me/212678901234");
    expect(html).not.toContain("wa.me/0678901234");
    // Bare digits refused (tel: link still renders — only the wa.me link is gone).
    expect(html).not.toContain("wa.me/612345678");
  });
});

// ── Run 8 G4b-A (B-18 / B-19) — inverted date range toast + timeline load-more ──
// Appended 2026-11-15. Base above untouched: the new tests only ADD coverage.
//
// B-18: applying an inverted date range still swaps the dates (as before) but
// now toasts ownerReservations.dateRangeSwapped, matching OwnerOrders.
// B-19: the timeline endpoint takes `limit` only (max 200, no offset —
// sales/views.py OwnerReservationTimelineView), so load-more raises the limit
// 80 -> 160 -> 200; at the 200 cap the max note shows instead of the button.
import { useToastStore } from "../../stores/toast";

describe("OwnerReservations — G4b-A (B-18 date-range toast / B-19 timeline load-more)", () => {
  let wrapper;

  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
    // Restore the factory default GET implementation (a later test overrides it).
    api.get.mockImplementation((url) => Promise.resolve(_match(url)));
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
    api.get.mockImplementation((url) => Promise.resolve(_match(url)));
  });

  const _buttonWith = (text) => wrapper.findAll("button").find((b) => b.text().includes(text));
  const _timelineCalls = () => api.get.mock.calls.filter((c) => c[0].includes("/timeline/"));
  const _timelineEntries = (n) =>
    Array.from({ length: n }, (_, i) => ({
      id: i + 1,
      action: "NOTE",
      note: `Note ${i + 1}`,
      created_at: "2026-09-05T12:00:00Z",
    }));

  // ── B-18 ─────────────────────────────────────────────────────────────────

  it("inverted date range is swapped AND toasted (B-18)", async () => {
    _routes = { "/owner/reservations/": _loadedPayload([reservation()]) };
    wrapper = mountPage();
    await flushPromises();

    const dates = wrapper.findAll('input[type="date"]');
    expect(dates).toHaveLength(2);
    await dates[0].setValue("2026-09-10");
    await dates[1].setValue("2026-09-01");
    await _buttonWith("common.apply").trigger("click");
    await flushPromises();

    // The swap is announced instead of silent.
    expect(useToastStore().message).toContain("ownerReservations.dateRangeSwapped");
    // And the refetch that follows carries the corrected range.
    const listCalls = api.get.mock.calls.filter(
      (c) => c[0].includes("/owner/reservations/") && !c[0].includes("timeline") && !c[0].includes("waitlist")
    );
    const lastParams = listCalls[listCalls.length - 1][1]?.params || {};
    expect(lastParams.from).toBe("2026-09-01");
    expect(lastParams.to).toBe("2026-09-10");
  });

  it("a valid date range applies without the swap toast (B-18)", async () => {
    _routes = { "/owner/reservations/": _loadedPayload([reservation()]) };
    wrapper = mountPage();
    await flushPromises();

    const dates = wrapper.findAll('input[type="date"]');
    await dates[0].setValue("2026-09-01");
    await dates[1].setValue("2026-09-10");
    await _buttonWith("common.apply").trigger("click");
    await flushPromises();

    expect(useToastStore().message || "").not.toContain("ownerReservations.dateRangeSwapped");
  });

  // ── B-19 ─────────────────────────────────────────────────────────────────

  const _openTimeline = async () => {
    await _buttonWith("ownerReservations.timeline").trigger("click");
    await flushPromises();
  };

  it("timeline loads 80 first, shows Load more, and load-more refetches with limit 160 (B-19)", async () => {
    _routes = {
      "/owner/reservations/1/timeline/": { data: _timelineEntries(80) },
      "/owner/reservations/": _loadedPayload([reservation()]),
    };
    wrapper = mountPage();
    await flushPromises();

    await _openTimeline();
    expect(_timelineCalls()).toHaveLength(1);
    expect(_timelineCalls()[0][1]?.params?.limit).toBe(80);
    // The server filled the whole requested limit, so more may exist.
    expect(wrapper.text()).toContain("ownerReservations.loadMoreTimeline");

    await _buttonWith("ownerReservations.loadMoreTimeline").trigger("click");
    await flushPromises();
    expect(_timelineCalls()).toHaveLength(2);
    expect(_timelineCalls()[1][1]?.params?.limit).toBe(160);
    // The mock still returns 80 rows, fewer than the 160 requested: no more.
    expect(wrapper.text()).not.toContain("ownerReservations.loadMoreTimeline");
  });

  it("timeline at the 200 cap shows the max note instead of Load more (B-19)", async () => {
    const all = _timelineEntries(250);
    _routes = { "/owner/reservations/": _loadedPayload([reservation()]) };
    api.get.mockImplementation((url, cfg) => {
      if (url.includes("/timeline/")) {
        return Promise.resolve({ data: all.slice(0, cfg?.params?.limit ?? 80) });
      }
      return Promise.resolve(_match(url));
    });
    wrapper = mountPage();
    await flushPromises();

    await _openTimeline();
    expect(_timelineCalls()[0][1]?.params?.limit).toBe(80);
    expect(wrapper.text()).toContain("ownerReservations.loadMoreTimeline");

    await _buttonWith("ownerReservations.loadMoreTimeline").trigger("click");
    await flushPromises();
    expect(_timelineCalls()[1][1]?.params?.limit).toBe(160);

    await _buttonWith("ownerReservations.loadMoreTimeline").trigger("click");
    await flushPromises();
    expect(_timelineCalls()[2][1]?.params?.limit).toBe(200);
    // Cap reached with a full page: no Load more, and the limit is named.
    expect(wrapper.text()).not.toContain("ownerReservations.loadMoreTimeline");
    expect(wrapper.text()).toContain("ownerReservations.timelineMaxReached");
  });

  it("timeline shorter than the limit shows neither Load more nor the max note (B-19)", async () => {
    _routes = {
      "/owner/reservations/1/timeline/": { data: _timelineEntries(3) },
      "/owner/reservations/": _loadedPayload([reservation()]),
    };
    wrapper = mountPage();
    await flushPromises();

    await _openTimeline();
    expect(wrapper.text()).not.toContain("ownerReservations.loadMoreTimeline");
    expect(wrapper.text()).not.toContain("ownerReservations.timelineMaxReached");
  });
});
