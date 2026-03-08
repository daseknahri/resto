import { defineStore } from "pinia";

export const useToastStore = defineStore("toast", {
  state: () => ({
    message: "",
    type: "info", // info | success | error
    visible: false,
    timeoutId: null,
  }),
  actions: {
    show(message, type = "info", duration = 2200) {
      this.message = message;
      this.type = type;
      this.visible = true;
      if (this.timeoutId) clearTimeout(this.timeoutId);
      if (duration) {
        this.timeoutId = setTimeout(() => this.hide(), duration);
      }
    },
    hide() {
      this.visible = false;
      this.message = "";
      this.type = "info";
      if (this.timeoutId) clearTimeout(this.timeoutId);
      this.timeoutId = null;
    },
  },
});
