/**
 * Unit tests for AdminConsoleOnboardingPackage — the "Latest Provisioning
 * Package" section of AdminConsole.vue, extracted into a standalone
 * presentational component (RISK FE-2). Provisioning mutation ownership
 * (provision / resendActivation / loadOnboardingPackage) stays in the parent;
 * this component only renders the given provisioning result and asks the
 * parent to clear it via the `clear` emit. Clipboard-copy is self-contained
 * (no server calls, no tenant mutation).
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({ t: (k) => k }),
}));

const showMock = vi.fn();
vi.mock("../../stores/toast", () => ({
  useToastStore: () => ({ show: showMock }),
}));

import AdminConsoleOnboardingPackage from "../AdminConsoleOnboardingPackage.vue";

const fullProvision = () => ({
  tenant: "Le Bistro",
  tenant_url: "https://le-bistro.example.com",
  workspace_url: "https://app.example.com/le-bistro",
  onboarding_url: "https://app.example.com/onboarding/abc",
  signin_url: "https://app.example.com/signin",
  activation_url: "https://app.example.com/activate/abc",
  public_menu_url: "https://le-bistro.example.com/menu",
  activation_token: "TOKEN-123",
  owner_next_steps: ["Verify domain", "Invite staff"],
  whatsapp_link: "https://wa.me/1234567890",
  whatsapp_message_template: "Welcome to Kepoli!",
});

const writeTextMock = vi.fn().mockResolvedValue(undefined);

const mountComp = (props = {}) =>
  mount(AdminConsoleOnboardingPackage, {
    props: {
      lastProvision: fullProvision(),
      currentDomainSuffixLabel: "Suffix: example.com",
      ...props,
    },
  });

beforeEach(() => {
  showMock.mockClear();
  writeTextMock.mockClear();
  Object.defineProperty(navigator, "clipboard", {
    value: { writeText: writeTextMock },
    configurable: true,
  });
});

describe("AdminConsoleOnboardingPackage", () => {
  it("renders the provisioning package details", () => {
    const w = mountComp();
    expect(w.text()).toContain("Le Bistro");
    expect(w.text()).toContain("Suffix: example.com");
    expect(w.text()).toContain("https://le-bistro.example.com");
    expect(w.text()).toContain("https://app.example.com/le-bistro");
    expect(w.text()).toContain("TOKEN-123");
    expect(w.text()).toContain("https://app.example.com/activate/abc");
    expect(w.text()).toContain("https://wa.me/1234567890");
    expect(w.text()).toContain("Welcome to Kepoli!");
  });

  it("renders the owner next steps as a numbered list", () => {
    const w = mountComp();
    const items = w.findAll("li");
    expect(items.length).toBe(2);
    expect(items[0].text()).toContain("Verify domain");
    expect(items[1].text()).toContain("Invite staff");
  });

  it("falls back to a dash and hides optional copy buttons when fields are missing", () => {
    const w = mountComp({ lastProvision: { tenant: "New Tenant" } });
    expect(w.findAll("li").length).toBe(0);
    expect(w.text()).toContain("-");
    // Only the always-on "copy package" and "clear" buttons remain.
    expect(w.findAll("button").length).toBe(2);
  });

  it("copies the full onboarding package text and shows a success toast", async () => {
    const w = mountComp();
    await w.get("button").trigger("click"); // "copyPackage" is the first button
    expect(writeTextMock).toHaveBeenCalledTimes(1);
    const copied = writeTextMock.mock.calls[0][0];
    expect(copied).toContain("Le Bistro");
    expect(copied).toContain("1. Verify domain");
    expect(showMock).toHaveBeenCalledWith("adminConsole.copied", "success");
  });

  it("copies a single field value from the context-band copy buttons", async () => {
    const w = mountComp();
    const contextButtons = w.findAll(".ui-context-stat button");
    expect(contextButtons.length).toBe(3);
    await contextButtons[0].trigger("click"); // tenant_url
    expect(writeTextMock).toHaveBeenCalledWith("https://le-bistro.example.com");
  });

  it("copies the whatsapp message template via the copyMessage button", async () => {
    const w = mountComp();
    const copyMessageBtn = w.findAll("button").find((b) => b.text() === "adminConsole.copyMessage");
    expect(copyMessageBtn).toBeTruthy();
    await copyMessageBtn.trigger("click");
    expect(writeTextMock).toHaveBeenCalledWith("Welcome to Kepoli!");
  });

  it("hides the copyMessage button when there is no whatsapp message template", () => {
    const w = mountComp({ lastProvision: { ...fullProvision(), whatsapp_message_template: "" } });
    const buttons = w.findAll("button");
    expect(buttons.some((b) => b.text() === "adminConsole.copyMessage")).toBe(false);
  });

  it("emits clear when the clear button is clicked", async () => {
    const w = mountComp();
    const clearBtn = w.findAll("button").find((b) => b.text() === "common.clear");
    await clearBtn.trigger("click");
    expect(w.emitted("clear")).toBeTruthy();
  });

  it("shows an error toast when the clipboard write fails", async () => {
    writeTextMock.mockRejectedValueOnce(new Error("denied"));
    const w = mountComp();
    await w.get("button").trigger("click");
    expect(showMock).toHaveBeenCalledWith("adminConsole.copyFailed", "error");
  });
});
