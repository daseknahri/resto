<template>
  <svg
    :viewBox="icon.viewBox"
    fill="none"
    stroke="currentColor"
    stroke-linecap="round"
    stroke-linejoin="round"
    :stroke-width="strokeWidth"
    aria-hidden="true"
  >
    <path v-for="(path, index) in icon.paths" :key="`${name}-${index}`" :d="path" />
  </svg>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  name: {
    type: String,
    required: true,
  },
  strokeWidth: {
    type: [String, Number],
    default: 1.9,
  },
});

const ICONS = {
  home: {
    viewBox: "0 0 24 24",
    paths: ["M3 10.5 12 3l9 7.5", "M5 9.5V21h14V9.5", "M10 21v-6h4v6"],
  },
  menu: {
    viewBox: "0 0 24 24",
    paths: ["M4 6h16", "M4 12h16", "M4 18h16"],
  },
  info: {
    viewBox: "0 0 24 24",
    paths: ["M12 22a10 10 0 1 1 0-20 10 10 0 0 1 0 20", "M12 16v-5", "M12 8h.01"],
  },
  cart: {
    viewBox: "0 0 24 24",
    paths: [
      "M3 4h2l2.4 11.2a2 2 0 0 0 2 1.6h7.9a2 2 0 0 0 2-1.6L21 7H7",
      "M9 20a1 1 0 1 0 0 .01",
      "M18 20a1 1 0 1 0 0 .01",
    ],
  },
  qr: {
    viewBox: "0 0 24 24",
    paths: [
      "M4 4h6v6H4z",
      "M14 4h6v6h-6z",
      "M4 14h6v6H4z",
      "M14 14h2",
      "M18 14h2",
      "M14 18h2",
      "M18 18h2",
      "M16 16h2",
    ],
  },
  calendar: {
    viewBox: "0 0 24 24",
    paths: ["M7 3v4", "M17 3v4", "M4 8h16", "M5 5h14a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1"],
  },
  settings: {
    viewBox: "0 0 24 24",
    paths: [
      "M12 3l1.1 2.53a1 1 0 0 0 .82.58l2.77.24-1.84 2.08a1 1 0 0 0-.24.9l.54 2.72-2.55-1.5a1 1 0 0 0-.98 0l-2.55 1.5.54-2.72a1 1 0 0 0-.24-.9L8.31 6.35l2.77-.24a1 1 0 0 0 .82-.58L12 3z",
      "M12 15.25a3.25 3.25 0 1 0 0-6.5 3.25 3.25 0 0 0 0 6.5z"
    ],
  },
  logout: {
    viewBox: "0 0 24 24",
    paths: ["M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4", "M10 17l5-5-5-5", "M15 12H3"],
  },
  refresh: {
    viewBox: "0 0 24 24",
    paths: ["M21 12a9 9 0 1 1-2.64-6.36", "M21 3v6h-6"],
  },
  plus: {
    viewBox: "0 0 24 24",
    paths: ["M12 5v14", "M5 12h14"],
  },
  minus: {
    viewBox: "0 0 24 24",
    paths: ["M5 12h14"],
  },
  check: {
    viewBox: "0 0 24 24",
    paths: ["M20 6 9 17l-5-5"],
  },
  close: {
    viewBox: "0 0 24 24",
    paths: ["M6 6l12 12", "M18 6 6 18"],
  },
  copy: {
    viewBox: "0 0 24 24",
    paths: ["M9 9h10v12H9z", "M5 3h10v12", "M5 3h10v12H5z"],
  },
  eye: {
    viewBox: "0 0 24 24",
    paths: ["M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7", "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6"],
  },
  chart: {
    viewBox: "0 0 24 24",
    paths: ["M4 20V10", "M10 20V4", "M16 20v-8", "M22 20v-5", "M3 20h20"],
  },
  download: {
    viewBox: "0 0 24 24",
    paths: ["M12 3v12", "M7 10l5 5 5-5", "M4 21h16"],
  },
  print: {
    viewBox: "0 0 24 24",
    paths: ["M6 9V4h12v5", "M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2", "M6 14h12v7H6z"],
  },
  search: {
    viewBox: "0 0 24 24",
    paths: ["m21 21-4.35-4.35", "M11 19a8 8 0 1 1 0-16 8 8 0 0 1 0 16z"],
  },
  filter: {
    viewBox: "0 0 24 24",
    paths: ["M3 5h18", "M6 12h12", "M10 19h4"],
  },
  link: {
    viewBox: "0 0 24 24",
    paths: ["M10 14 6 18a3 3 0 1 1-4-4l4-4a3 3 0 0 1 4 0", "M14 10 18 6a3 3 0 1 1 4 4l-4 4a3 3 0 0 1-4 0", "M8 16l8-8"],
  },
  table: {
    viewBox: "0 0 24 24",
    paths: ["M3 7h18", "M5 7v5h14V7", "M8 12v8", "M16 12v8", "M4 20h16"],
  },
  chat: {
    viewBox: "0 0 24 24",
    paths: ["M4 5h16a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H8l-4 3v-3H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1"],
  },
  user: {
    viewBox: "0 0 24 24",
    paths: ["M20 21a8 8 0 1 0-16 0", "M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z"],
  },
  phone: {
    viewBox: "0 0 24 24",
    paths: ["M22 16.92v3a2 2 0 0 1-2.18 2A19.8 19.8 0 0 1 2.08 4.18 2 2 0 0 1 4.06 2h3a2 2 0 0 1 2 1.72c.12.9.33 1.78.62 2.62a2 2 0 0 1-.45 2.11L8 9.93a16 16 0 0 0 6.07 6.07l1.48-1.23a2 2 0 0 1 2.11-.45c.84.29 1.72.5 2.62.62A2 2 0 0 1 22 16.92z"],
  },
  chevronDown: {
    viewBox: "0 0 24 24",
    paths: ["M6 9l6 6 6-6"],
  },
  location: {
    viewBox: "0 0 24 24",
    paths: ["M12 21C12 21 5 13.5 5 8.5a7 7 0 0 1 14 0c0 5-7 12.5-7 12.5z", "M12 11a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z"],
  },
  sparkles: {
    viewBox: "0 0 24 24",
    paths: ["M12 3L13.5 8.5H19L14.5 12L16 17.5L12 14L8 17.5L9.5 12L5 8.5H10.5L12 3Z", "M5 3l.5 2", "M19 3l-.5 2", "M3 10l2 .5", "M21 10l-2 .5"],
  },
  "check-circle": {
    viewBox: "0 0 24 24",
    paths: ["M22 11.08V12a10 10 0 1 1-5.93-9.14", "M22 4L12 14.01l-3-3"],
  },
  chevronUp: {
    viewBox: "0 0 24 24",
    paths: ["M6 15l6-6 6 6"],
  },
  star: {
    viewBox: "0 0 24 24",
    paths: ["M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"],
  },
  share: {
    viewBox: "0 0 24 24",
    paths: ["M4 12v7a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-7", "M12 3v12", "M8 7l4-4 4 4"],
  },
  upload: {
    viewBox: "0 0 24 24",
    paths: ["M4 17v2a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-2", "M12 15V3", "M8 7l4-4 4 4"],
  },
  arrowLeft: {
    viewBox: "0 0 24 24",
    paths: ["M19 12H5", "M12 5l-7 7 7 7"],
  },
  arrowRight: {
    viewBox: "0 0 24 24",
    paths: ["M5 12h14", "M12 5l7 7-7 7"],
  },
  tag: {
    viewBox: "0 0 24 24",
    paths: ["M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z", "M7 7h.01"],
  },
  truck: {
    viewBox: "0 0 24 24",
    paths: ["M1 3h15v13H1z", "M16 8h4l3 3v5h-7V8z", "M5.5 21a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z", "M18.5 21a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z"],
  },
};

const fallbackIcon = ICONS.menu;
const icon = computed(() => ICONS[props.name] || fallbackIcon);
</script>
