<template>
  <img
    v-if="src && !failed"
    :src="src"
    :alt="name"
    :class="imgClass"
    :loading="loading"
    :fetchpriority="fetchpriority"
    decoding="async"
    @error="failed = true"
  />
  <div
    v-else
    :class="imgClass"
    class="flex items-center justify-center select-none"
    :style="placeholderStyle"
    role="img"
    :aria-label="name"
  >
    <span class="font-semibold tracking-tight text-white/95" :style="letterStyle" aria-hidden="true">{{ initial }}</span>
  </div>
</template>

<script setup>
/**
 * DishImage — dish/category image with a tasteful branded placeholder.
 *
 * When there's no image (or it fails to load) it renders a deterministic
 * gradient + the item's initial instead of a generic stock photo. This keeps
 * photo-less menus (e.g. fresh template menus) looking intentional and
 * professional, with no external image dependency.
 */
import { computed, ref, watch } from "vue";

const props = defineProps({
  src: { type: String, default: "" },
  name: { type: String, default: "" },
  // Stable key for the colour (e.g. slug) so the same item always looks the same.
  seed: { type: String, default: "" },
  imgClass: { type: String, default: "h-full w-full object-cover" },
  loading: { type: String, default: "lazy" },
  fetchpriority: { type: String, default: "auto" },
});

const failed = ref(false);
watch(() => props.src, () => { failed.value = false; });

const initial = computed(() => ((props.name || "").trim().charAt(0).toUpperCase() || "•"));

// Deterministic hue from the seed/name → distinct but cohesive placeholders.
const hue = computed(() => {
  const s = String(props.seed || props.name || "");
  let h = 0;
  for (let i = 0; i < s.length; i += 1) h = (h * 31 + s.charCodeAt(i)) % 360;
  return h;
});

const placeholderStyle = computed(() => ({
  background: `linear-gradient(135deg, hsl(${hue.value} 46% 38%), hsl(${(hue.value + 38) % 360} 50% 26%))`,
}));

const letterStyle = { fontSize: "clamp(1.5rem, 7vw, 3.5rem)" };
</script>
