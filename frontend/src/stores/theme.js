import { defineStore } from "pinia";

// Mirrors the hardcoded <meta name="theme-color"> baseline in index.html. Used to
// restore the platform default when leaving a tenant-branded customer surface.
const DEFAULT_THEME_COLOR = "#0b1c1a";

// Update the browser/PWA theme-color meta (mobile URL bar + splash). External
// here (not an inline script) so CSP can stay script-src 'self'.
const setThemeColorMeta = (color) => {
  if (typeof document === "undefined") return;
  const value = String(color || "").trim() || DEFAULT_THEME_COLOR;
  const node = document.head.querySelector('meta[name="theme-color"]');
  if (node) node.setAttribute("content", value);
};

export const useThemeStore = defineStore("theme", {
  state: () => ({
    primary: "#0F766E",
    secondary: "#F59E0B",
  }),
  actions: {
    apply(profile) {
      if (!profile) return;
      this.primary = profile.primary_color || this.primary;
      this.secondary = profile.secondary_color || this.secondary;
      const root = document.documentElement;
      root.style.setProperty("--color-primary", this.primary);
      root.style.setProperty("--color-secondary", this.secondary);
      // Sync the mobile URL bar / PWA splash to the tenant's brand color so the
      // chrome reflects the brand on customer surfaces.
      setThemeColorMeta(this.primary);
    },
    // Restore the platform default theme-color when off tenant (customer) routes.
    resetThemeColor() {
      setThemeColorMeta(DEFAULT_THEME_COLOR);
    },
  },
});
