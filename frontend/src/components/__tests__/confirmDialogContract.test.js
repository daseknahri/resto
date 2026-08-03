/**
 * App-wide fitness test for the confirm() dialog contract.
 *
 * ConfirmModal.vue renders `options.body` and falls back to a GENERIC default when
 * it is missing — so a caller that passes `message:` (a natural typo, since toasts
 * and many libs use `message`) silently shows boilerplate instead of its real,
 * often amount-bearing, explanation. Seven such sites had drifted in across the
 * customer / cart / waiter flows; this guards the whole app against reintroducing
 * that blank-body-confirm bug class, everywhere, in one cheap source scan.
 */
import { describe, it, expect } from "vitest";

// Raw text of every SFC + module under src/ (Vite glob-import — strings, no execution).
const sources = import.meta.glob("../../**/*.{vue,js}", {
  query: "?raw",
  import: "default",
  eager: true,
});

// A confirm(...) call whose options object carries a `message:` key. `[^}]*` is
// bounded by the first `}`, so it only inspects that single options object.
const MESSAGE_IN_CONFIRM = /confirm\(\s*\{[^}]*\bmessage\s*:/;

describe("confirm() dialog contract", () => {
  it("actually scanned the source tree (guards against a vacuous pass)", () => {
    // 100+ SFCs/modules live under src/; a near-empty glob means the scan silently broke.
    expect(Object.keys(sources).length).toBeGreaterThan(50);
  });

  it("no confirm({ … message: … }) anywhere — ConfirmModal reads `body`, not `message`", () => {
    const offenders = Object.entries(sources)
      .filter(([path]) => !path.includes("__tests__")) // skip test files (incl. this one)
      .filter(([, src]) => MESSAGE_IN_CONFIRM.test(src))
      .map(([path]) => path);
    expect(
      offenders,
      `confirm() must pass body: not message: — offenders:\n${offenders.join("\n")}`,
    ).toEqual([]);
  });
});
