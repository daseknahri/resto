<template>
  <details
    class="group rounded-xl border border-slate-800 bg-slate-950/30"
    :open="open"
    :aria-label="t('ownerHome.dishAvailability')"
  >
    <summary
      class="flex cursor-pointer list-none items-center justify-between gap-2 px-3 py-2.5 text-sm font-semibold text-slate-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500/60 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950 [&::-webkit-details-marker]:hidden"
      :aria-expanded="open"
      @click.prevent="toggle"
    >
      <span class="flex items-center gap-2">
        <AppIcon name="menu" class="h-3.5 w-3.5 text-slate-400" aria-hidden="true" />
        {{ t("ownerHome.dishAvailability") }}
      </span>
      <span class="flex items-center gap-2 text-xs font-normal text-slate-400">
        <span
          v-if="soldOutCount > 0"
          class="rounded-full border border-red-500/40 bg-red-500/15 px-2 py-0.5 font-semibold tabular-nums text-red-300"
        >
          {{ soldOutCount }} {{ t("ownerHome.soldOut") }}
        </span>
        <!-- Subtle spinner while lazy-loading the dish list -->
        <svg
          v-if="fetching"
          aria-hidden="true"
          class="h-3 w-3 animate-spin text-slate-500"
          viewBox="0 0 16 16"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
        >
          <circle cx="8" cy="8" r="6" stroke-dasharray="28" stroke-dashoffset="10" />
        </svg>
        <AppIcon
          :name="open ? 'chevronUp' : 'chevronDown'"
          class="h-3.5 w-3.5 shrink-0 text-slate-500 transition-transform duration-200 rtl:scale-x-[-1]"
          aria-hidden="true"
        />
      </span>
    </summary>

    <div v-if="open" class="space-y-1 border-t border-slate-800 px-3 pb-3 pt-2">
      <!-- Search + morning reset row -->
      <div class="mb-2 flex items-center gap-2">
        <input
          v-model.trim="search"
          type="search"
          class="ui-input flex-1 text-xs"
          enterkeyhint="search"
          :aria-label="t('common.search')"
          :placeholder="t('common.search')"
        />
        <button
          v-if="soldOutCount > 0"
          class="ui-press shrink-0 rounded-full border border-emerald-500/40 px-2.5 py-1 text-[10px] font-semibold text-emerald-300 transition-colors hover:bg-emerald-500/10 disabled:opacity-50"
          :disabled="resetting"
          :title="t('ownerHome.resetAvailabilityHint')"
          :aria-label="t('ownerHome.resetAvailabilityHint')"
          @click="resetAll"
        >
          {{ resetting ? "…" : t("ownerHome.resetAllAvailable") }}
        </button>
      </div>

      <!-- Skeleton while loading dishes for the first time -->
      <template v-if="fetching">
        <div v-for="i in 5" :key="i" class="flex animate-pulse items-center justify-between gap-2 rounded-xl px-2 py-1.5">
          <div class="space-y-1">
            <div class="h-3 w-32 rounded bg-slate-700/60" />
            <div class="h-2 w-20 rounded bg-slate-800/60" />
          </div>
          <div class="h-6 w-16 rounded-full bg-slate-700/40" />
        </div>
      </template>

      <div v-else-if="!dishes.length" class="ui-empty-state text-center">
        <p class="text-xs font-medium text-slate-300">{{ t("ownerHome.noDishesLoaded") }}</p>
      </div>

      <div
        v-for="(dish, index) in filtered"
        :key="dish.id"
        class="ui-reveal flex items-center justify-between gap-2 rounded-xl px-2 py-1.5 transition-colors hover:bg-slate-900/60"
        :class="!dish.is_available ? 'opacity-60' : ''"
        :style="{ '--ui-delay': `${Math.min(index, 9) * 20}ms` }"
      >
        <div class="min-w-0 flex-1">
          <p class="truncate text-xs font-medium text-slate-100">{{ dish.name }}</p>
          <p class="truncate text-[10px] text-slate-500">{{ dish.category_name || dish.category_slug }}</p>
        </div>

        <div class="flex shrink-0 items-center gap-1.5">
          <!-- Stock quantity input -->
          <div class="flex flex-col items-center gap-0.5">
            <label
              :for="`stock-${dish.id}`"
              class="text-[8px] uppercase tracking-wider text-slate-600"
            >{{ t("ownerHome.stockLabel") }}</label>
            <input
              :id="`stock-${dish.id}`"
              type="number"
              min="0"
              step="1"
              :value="dish.stock_qty ?? ''"
              :placeholder="t('ownerHome.stockUnlimited')"
              :disabled="settingStockId === dish.id"
              :aria-label="t('ownerHome.stockLabel')"
              class="w-14 rounded-lg border border-slate-700 bg-slate-900/80 px-1.5 py-0.5 text-center text-[10px] tabular-nums text-slate-200 placeholder-slate-600 focus:border-amber-500/60 focus:outline-none focus-visible:ring-1 focus-visible:ring-amber-500/40 disabled:opacity-40"
              :class="
                dish.stock_qty === 0
                  ? 'border-red-500/50 text-red-300'
                  : dish.stock_qty !== null
                  ? 'border-amber-500/30 text-amber-200'
                  : ''
              "
              @change="setStock(dish, $event.target.value)"
              @keydown.enter="$event.target.blur()"
            />
          </div>

          <!-- Available toggle -->
          <button
            class="ui-press ui-touch-target shrink-0 rounded-full border px-2.5 text-[10px] font-semibold transition-colors disabled:opacity-50"
            :class="
              dish.is_available
                ? 'border-emerald-500/40 text-emerald-300 hover:border-red-400/50 hover:bg-red-500/10 hover:text-red-300'
                : 'border-red-500/40 bg-red-500/10 text-red-300 hover:border-emerald-400/50 hover:bg-emerald-500/10 hover:text-emerald-300'
            "
            :disabled="togglingId === dish.id"
            :aria-label="
              dish.is_available
                ? `${dish.name} — ${t('ownerHome.dishAvailable')}`
                : `${dish.name} — ${t('ownerHome.dish86d')}`
            "
            @click="toggleAvailability(dish)"
          >
            {{ togglingId === dish.id ? "…" : (dish.is_available ? t("ownerHome.dishAvailable") : t("ownerHome.dish86d")) }}
          </button>
        </div>
      </div>
    </div>
  </details>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import AppIcon from "./AppIcon.vue";
import { useI18n } from "../composables/useI18n";
import api from "../lib/api";
import { bustCache } from "../lib/staleCache";
import { useToastStore } from "../stores/toast";

const { t } = useI18n();
const toast = useToastStore();

// ── Props from parent: initial sold-out count so summary shows before lazy load ─
const props = defineProps({
  /** Pre-computed sold-out count from the parent (shown in summary before panel opens) */
  initialSoldOutCount: { type: Number, default: 0 },
  /**
   * Dishes already fetched by OwnerDashboardReadiness — if provided, the panel
   * uses this data immediately when opened and skips the /dishes/ network call.
   */
  preloadedDishes: { type: Array, default: null },
});

// ── Panel state ───────────────────────────────────────────────────────────────
const open = ref(false);
const fetched = ref(false);   // true after the first successful load
const fetching = ref(false);  // true while the fetch is in flight
const dishes = ref([]);
const search = ref("");
const togglingId = ref(null);
const settingStockId = ref(null);
const resetting = ref(false);

// Use a local sold-out count that starts from the parent hint and updates as
// dishes are loaded and toggled.
const soldOutCount = computed(() => {
  if (!fetched.value) return props.initialSoldOutCount;
  return dishes.value.filter((d) => d.is_published && !d.is_available).length;
});

// Auto-open when sold-out dishes appear (e.g. after first data load)
watch(soldOutCount, (n, o) => {
  if (n > 0 && o === 0) open.value = true;
});

const filtered = computed(() => {
  const q = search.value.toLowerCase();
  const list = [...dishes.value]
    .filter((d) => d.is_published)
    .sort((a, b) => {
      // 86'd dishes float to top
      if (!a.is_available && b.is_available) return -1;
      if (a.is_available && !b.is_available) return 1;
      return 0;
    });
  if (!q) return list;
  return list.filter(
    (d) =>
      (d.name || "").toLowerCase().includes(q) ||
      (d.category_name || "").toLowerCase().includes(q) ||
      (d.category_slug || "").toLowerCase().includes(q)
  );
});

// ── Lazy fetch — skipped when the parent provides pre-loaded data ─────────────
const fetchDishes = async () => {
  if (fetched.value || fetching.value) return;

  // Use pre-loaded data from the readiness component if available — avoids
  // a second /dishes/ call on the same page load.
  if (props.preloadedDishes && props.preloadedDishes.length > 0) {
    dishes.value = props.preloadedDishes;
    fetched.value = true;
    return;
  }

  fetching.value = true;
  try {
    const { data } = await api.get("/dishes/", { timeout: 6000 });
    dishes.value = Array.isArray(data) ? data : [];
    fetched.value = true;
  } catch {
    toast.show(t("ownerHome.noDishesLoaded"), "error");
  } finally {
    fetching.value = false;
  }
};

const toggle = () => {
  open.value = !open.value;
  if (open.value) fetchDishes();
};

// ── Dish operations ───────────────────────────────────────────────────────────
const toggleAvailability = async (dish) => {
  if (togglingId.value === dish.id) return;
  togglingId.value = dish.id;
  const newValue = !dish.is_available;
  try {
    await api.patch(`/dishes/${dish.id}/`, { is_available: newValue });
    dish.is_available = newValue;
    bustCache("menu.categories");
    toast.show(
      newValue
        ? t("ownerHome.dishRestored", { name: dish.name })
        : t("ownerHome.dish86dToast", { name: dish.name }),
      newValue ? "success" : "info"
    );
  } catch {
    toast.show(t("ownerHome.dish86Failed"), "error");
  } finally {
    togglingId.value = null;
  }
};

const setStock = async (dish, rawValue) => {
  if (settingStockId.value === dish.id) return;
  const trimmed = String(rawValue ?? "").trim();
  const newQty = trimmed === "" ? null : parseInt(trimmed, 10);
  if (newQty !== null && (isNaN(newQty) || newQty < 0)) return;
  if (newQty === dish.stock_qty) return;
  settingStockId.value = dish.id;
  try {
    const payload = { stock_qty: newQty };
    if (newQty !== null && newQty > 0 && !dish.is_available) payload.is_available = true;
    await api.patch(`/dishes/${dish.id}/`, payload);
    dish.stock_qty = newQty;
    if (payload.is_available !== undefined) dish.is_available = payload.is_available;
    bustCache("menu.categories");
    toast.show(
      newQty === null
        ? t("ownerHome.stockUnlimitedSet", { name: dish.name })
        : t("ownerHome.stockSet", { name: dish.name, qty: newQty }),
      "success"
    );
  } catch {
    toast.show(t("ownerHome.stockSetFailed"), "error");
  } finally {
    settingStockId.value = null;
  }
};

const resetAll = async () => {
  if (resetting.value) return;
  resetting.value = true;
  try {
    const { data } = await api.post("/owner/dishes/reset-availability/");
    dishes.value.forEach((d) => {
      if (d.is_published && !d.is_available) d.is_available = true;
      if (d.stock_qty === 0) d.stock_qty = null;
    });
    bustCache("menu.categories");
    const count = data?.restored ?? 0;
    toast.show(
      count > 0
        ? t("ownerHome.resetAvailabilityDone", { count })
        : t("ownerHome.resetAvailabilityNone"),
      "success"
    );
  } catch {
    toast.show(t("ownerHome.resetAvailabilityFailed"), "error");
  } finally {
    resetting.value = false;
  }
};
</script>
