import { ref } from "vue";

// Owner workspace color scheme (dark | light).
// Dark is the default — it preserves the existing look for anyone who never toggles.
// The choice is persisted in localStorage and applied as `data-owner-theme` on <html>,
// which the light-mode overrides in tailwind.css key off. The attribute is only present
// while the owner layout is mounted (see activate/deactivate), so it never leaks into the
// customer or admin areas, which use their own theming.

const STORAGE_KEY = "owner-theme";
const VALID = ["dark", "light"];
const ATTR = "data-owner-theme";

const readStored = () => {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    return VALID.includes(value) ? value : "dark";
  } catch {
    return "dark";
  }
};

// Module-level singleton so every owner component shares one source of truth.
const theme = ref(readStored());

const applyAttribute = (value) => {
  try {
    document.documentElement.setAttribute(ATTR, value);
  } catch {
    /* SSR / no document — ignore */
  }
};

// Pre-paint the saved owner theme before Vue mounts — but only when the initial
// route is an owner page. This kills the flash-of-wrong-theme on a hard reload of
// an owner page (a light-mode user would otherwise see dark until OwnerLayout
// mounts) without ever leaking owner theming onto customer/admin routes. Called
// from main.js; OwnerLayout still re-applies on mount and clears on unmount.
export const primeOwnerTheme = (pathname = "") => {
  if (typeof pathname !== "string" || !pathname.startsWith("/owner")) return;
  applyAttribute(theme.value);
};

export const useOwnerTheme = () => {
  const setTheme = (value) => {
    if (!VALID.includes(value)) return;
    theme.value = value;
    try {
      localStorage.setItem(STORAGE_KEY, value);
    } catch {
      /* storage unavailable — keep in-memory value */
    }
    applyAttribute(value);
  };

  const toggleTheme = () => setTheme(theme.value === "light" ? "dark" : "light");

  // Call when the owner layout mounts — paints the current theme onto <html>.
  const activate = () => applyAttribute(theme.value);

  // Call when the owner layout unmounts — strips the attribute so customer/admin
  // pages (which share the same ui-* primitives) are never re-themed.
  const deactivate = () => {
    try {
      document.documentElement.removeAttribute(ATTR);
    } catch {
      /* ignore */
    }
  };

  return { theme, setTheme, toggleTheme, activate, deactivate };
};
