import { defineStore } from "pinia";

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
    },
  },
});
