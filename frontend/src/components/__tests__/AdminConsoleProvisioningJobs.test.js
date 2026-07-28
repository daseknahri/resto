/**
 * Unit tests for AdminConsoleProvisioningJobs — the "Provisioning Jobs"
 * section of AdminConsole.vue, extracted into a standalone presentational
 * component (RISK FE-2). Fetching (fetchJobs) and the expand/collapse panel
 * state stay owned by the parent; this component only renders the given job
 * list/loading state and asks the parent to toggle/refresh via emits.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({ t: (k) => k, currentLocale: { value: "en" } }),
}));

import AdminConsoleProvisioningJobs from "../AdminConsoleProvisioningJobs.vue";

const sampleJobs = () => [
  { id: 1, lead_name: "Le Bistro", tenant_slug: "le-bistro", status: "success", log: "Provisioned OK", updated_at: "2026-07-01T10:00:00Z" },
  { id: 2, lead_name: "Cafe Luna", tenant_slug: "", status: "running", log: "Working...", updated_at: "2026-07-02T11:00:00Z" },
  { id: 3, lead_name: "Pizza Roma", tenant_slug: "pizza-roma", status: "failed", log: "DNS error", updated_at: "2026-07-03T12:00:00Z" },
];

const mountComp = (props = {}) =>
  mount(AdminConsoleProvisioningJobs, {
    props: {
      jobs: [],
      loading: false,
      expanded: true,
      ...props,
    },
  });

describe("AdminConsoleProvisioningJobs", () => {
  it("renders the section header", () => {
    const w = mountComp();
    expect(w.text()).toContain("adminConsole.provisioningJobs");
  });

  it("shows the empty state when there are no jobs and not loading", () => {
    const w = mountComp({ jobs: [] });
    expect(w.text()).toContain("adminConsole.noJobsYet");
  });

  it("shows the loading skeleton instead of the empty state while loading", () => {
    const w = mountComp({ jobs: [], loading: true });
    expect(w.text()).not.toContain("adminConsole.noJobsYet");
    expect(w.find(".ui-skeleton").exists()).toBe(true);
  });

  it("does not render the body when collapsed", () => {
    const w = mountComp({ jobs: sampleJobs(), expanded: false });
    expect(w.text()).not.toContain("Le Bistro");
    expect(w.text()).not.toContain("adminConsole.noJobsYet");
  });

  it("renders job rows (mobile cards + desktop table) when jobs are present", () => {
    const w = mountComp({ jobs: sampleJobs() });
    // Mobile cards (one per job) + desktop table rows both render the same data.
    expect(w.findAll(".ui-admin-card").length).toBe(3);
    expect(w.findAll("tbody tr").length).toBe(3);
    expect(w.text()).toContain("Le Bistro");
    expect(w.text()).toContain("Cafe Luna");
    expect(w.text()).toContain("DNS error");
  });

  it("falls back to a dash for a job with no tenant slug", () => {
    const w = mountComp({ jobs: [sampleJobs()[1]] });
    expect(w.text()).toContain("adminConsole.tenant: -");
  });

  it("disables the refresh button while loading or collapsed", () => {
    const collapsed = mountComp({ expanded: false });
    const collapsedRefresh = collapsed.findAll("button")[1];
    expect(collapsedRefresh.attributes("disabled")).toBeDefined();

    const loadingExpanded = mountComp({ loading: true, expanded: true });
    const loadingRefresh = loadingExpanded.findAll("button")[1];
    expect(loadingRefresh.attributes("disabled")).toBeDefined();
  });

  it("emits toggle-expanded when the show/hide button is clicked", async () => {
    const w = mountComp();
    await w.findAll("button")[0].trigger("click");
    expect(w.emitted("toggle-expanded")).toBeTruthy();
  });

  it("emits refresh when the refresh button is clicked", async () => {
    const w = mountComp();
    await w.findAll("button")[1].trigger("click");
    expect(w.emitted("refresh")).toBeTruthy();
  });

  it("shows the show/hide label based on the expanded prop", () => {
    const shown = mountComp({ expanded: true });
    expect(shown.text()).toContain("adminConsole.hide");
    const hidden = mountComp({ expanded: false });
    expect(hidden.text()).toContain("adminConsole.show");
  });
});
