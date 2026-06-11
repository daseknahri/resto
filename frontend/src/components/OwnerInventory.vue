<template>
  <div class="space-y-3">
    <!-- Header band: auto-reset toggle + search + low-stock filter -->
    <div class="ui-panel space-y-3 p-3 sm:p-4">
      <!-- Auto-reset row -->
      <div class="flex items-start justify-between gap-3">
        <div class="min-w-0 leading-snug">
          <p class="text-xs font-semibold text-slate-200">{{ t("inventory.autoResetTitle") }}</p>
          <p class="mt-0.5 text-[11px] text-slate-500">{{ t("inventory.autoResetHint") }}</p>
        </div>
        <button
          role="switch"
          class="ui-press ui-touch-target shrink-0 rounded-full border px-3 py-1 text-[11px] font-semibold transition-colors disabled:opacity-50"
          :class="autoReset
            ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300'
            : 'border-slate-700/60 text-slate-400 hover:border-slate-600 hover:text-slate-300'"
          :disabled="savingReset"
          :aria-checked="autoReset"
          :aria-busy="savingReset"
          @click="toggleAutoReset"
        >
          <svg v-if="savingReset" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="me-1 inline h-3 w-3 animate-spin"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
          {{ autoReset ? t("common.open") : t("common.closed") }}
        </button>
      </div>

      <!-- Search + low-stock filter -->
      <div class="flex flex-wrap items-center gap-2">
        <div class="relative min-w-0 flex-1">
          <AppIcon name="search" class="pointer-events-none absolute start-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" aria-hidden="true" />
          <input
            v-model.trim="search"
            type="search"
            class="ui-input w-full ps-8 text-xs"
            :placeholder="t('inventory.searchPlaceholder')"
            :aria-label="t('inventory.searchPlaceholder')"
            enterkeyhint="search"
          />
        </div>
        <button
          class="ui-press ui-touch-target shrink-0 rounded-full border px-3 py-1 text-[11px] font-semibold transition-colors"
          :class="filterLowOnly
            ? 'border-amber-500/50 bg-amber-500/10 text-amber-300'
            : 'border-slate-700/60 text-slate-400 hover:border-slate-600 hover:text-slate-300'"
          :aria-pressed="filterLowOnly"
          @click="filterLowOnly = !filterLowOnly"
        >
          {{ t("inventory.lowOnly") }}
        </button>
      </div>
    </div>

    <!-- Loading skeleton -->
    <template v-if="fetching">
      <div
        v-for="i in 6"
        :key="i"
        class="ui-panel animate-pulse px-3 py-3"
      >
        <div class="flex items-center justify-between gap-3">
          <div class="space-y-1.5">
            <div class="h-3 w-36 rounded bg-slate-700/60" />
            <div class="h-2.5 w-24 rounded bg-slate-800/60" />
          </div>
          <div class="flex gap-2">
            <div class="h-7 w-16 rounded-lg bg-slate-700/40" />
            <div class="h-7 w-16 rounded-lg bg-slate-700/40" />
          </div>
        </div>
      </div>
    </template>

    <!-- Empty state -->
    <div v-else-if="!dishes.length" class="ui-empty-state py-12 text-center">
      <AppIcon name="menu" class="mx-auto mb-3 h-8 w-8 text-slate-600" aria-hidden="true" />
      <p class="text-sm font-medium text-slate-400">{{ t("inventory.empty") }}</p>
    </div>

    <!-- No matches -->
    <div v-else-if="!filtered.length" class="ui-empty-state py-10 text-center">
      <p class="text-xs text-slate-500">{{ t("inventory.empty") }}</p>
    </div>

    <!-- Dish rows -->
    <ul v-else role="list" class="space-y-1.5">
      <li
        v-for="(dish, index) in filtered"
        :key="dish.id"
        class="ui-panel ui-reveal px-3 py-3"
        :class="!dish.is_available ? 'opacity-70' : ''"
        :style="{ '--ui-delay': `${Math.min(index, 14) * 15}ms` }"
      >
        <!-- Row: name + controls -->
        <div class="flex flex-wrap items-center gap-2 sm:flex-nowrap">
          <!-- Name + category -->
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-1.5">
              <p class="truncate text-xs font-semibold text-slate-100">{{ dish.name }}</p>
              <span
                v-if="!dish.is_available"
                class="shrink-0 rounded-full border border-red-500/40 bg-red-500/10 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-red-300"
              >{{ t("inventory.soldOut") }}</span>
              <span
                v-else-if="isLow(dish)"
                class="shrink-0 rounded-full border border-amber-500/40 bg-amber-500/10 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-amber-300"
              >{{ t("ownerHome.lowStockLeft", { n: dish.stock_qty }) }}</span>
            </div>
            <p class="mt-0.5 truncate text-[10px] text-slate-500">{{ dish.category_name || dish.category_slug }}</p>
          </div>

          <!-- Controls: stock + threshold + quick buttons -->
          <div class="flex shrink-0 flex-wrap items-end gap-2 sm:flex-nowrap">
            <!-- Stock qty input -->
            <div class="flex flex-col items-center gap-0.5">
              <label :for="`inv-stock-${dish.id}`" class="text-[9px] uppercase tracking-wider text-slate-500">
                {{ t("inventory.stockLabel") }}
              </label>
              <div class="flex items-center gap-0.5">
                <!-- -1 -->
                <button
                  class="ui-press flex h-6 w-6 items-center justify-center rounded-md border border-slate-700/60 text-slate-400 transition hover:border-slate-600 hover:text-slate-200 disabled:opacity-40"
                  :disabled="savingId === dish.id || (dish.stock_qty !== null && dish.stock_qty <= 0)"
                  :aria-label="`-1 ${dish.name}`"
                  @click="adjustStock(dish, -1)"
                >
                  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" class="h-3 w-3" aria-hidden="true"><path d="M3 8h10"/></svg>
                </button>

                <input
                  :id="`inv-stock-${dish.id}`"
                  type="number"
                  min="0"
                  step="1"
                  :value="dish.stock_qty ?? ''"
                  :placeholder="t('inventory.unlimited')"
                  :disabled="savingId === dish.id"
                  class="ui-input w-16 py-0.5 text-center text-[11px] tabular-nums placeholder-slate-600 disabled:opacity-40"
                  :class="
                    dish.stock_qty === 0
                      ? 'border-red-500/50 text-red-300'
                      : dish.stock_qty !== null && isLow(dish)
                      ? 'border-amber-500/40 text-amber-200'
                      : dish.stock_qty !== null
                      ? 'border-slate-600 text-slate-100'
                      : ''
                  "
                  @change="commitStock(dish, $event.target.value)"
                  @keydown.enter="$event.target.blur()"
                />

                <!-- +10 -->
                <button
                  class="ui-press flex h-6 w-7 items-center justify-center rounded-md border border-slate-700/60 text-[10px] font-semibold text-slate-400 transition hover:border-slate-600 hover:text-slate-200 disabled:opacity-40"
                  :disabled="savingId === dish.id"
                  :aria-label="`+10 ${dish.name}`"
                  @click="adjustStock(dish, 10)"
                >
                  +10
                </button>
              </div>
            </div>

            <!-- Threshold input -->
            <div class="flex flex-col items-center gap-0.5">
              <label :for="`inv-thresh-${dish.id}`" class="text-[9px] uppercase tracking-wider text-slate-500">
                {{ t("inventory.thresholdLabel") }}
              </label>
              <input
                :id="`inv-thresh-${dish.id}`"
                type="number"
                min="0"
                step="1"
                :value="dish.low_stock_threshold ?? ''"
                :placeholder="t('inventory.unlimited')"
                :disabled="savingId === dish.id"
                class="ui-input w-16 py-0.5 text-center text-[11px] tabular-nums placeholder-slate-600 disabled:opacity-40"
                @change="commitThreshold(dish, $event.target.value)"
                @keydown.enter="$event.target.blur()"
              />
            </div>

            <!-- Saving spinner -->
            <div class="flex h-7 w-5 items-center justify-center">
              <svg
                v-if="savingId === dish.id"
                aria-hidden="true"
                class="h-3.5 w-3.5 animate-spin text-slate-500"
                viewBox="0 0 16 16"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
              >
                <circle cx="8" cy="8" r="6" stroke-dasharray="28" stroke-dashoffset="10" />
              </svg>
            </div>
          </div>
        </div>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import AppIcon from "./AppIcon.vue";
import { useI18n } from "../composables/useI18n";
import { useTenantStore } from "../stores/tenant";
import { useToastStore } from "../stores/toast";
import api from "../lib/api";
import { bustCache } from "../lib/staleCache";

const { t } = useI18n();
const tenant = useTenantStore();
const toast = useToastStore();

// ── Local state ───────────────────────────────────────────────────────────────
const dishes = ref([]);
const fetching = ref(false);
const savingId = ref(null);
const savingReset = ref(false);
const search = ref("");
const filterLowOnly = ref(false);

// ── Profile-derived: auto_reset_availability ──────────────────────────────────
const autoReset = computed(() => tenant.meta?.profile?.auto_reset_availability === true);

// ── Filtering ─────────────────────────────────────────────────────────────────
const isLow = (dish) =>
  dish.stock_qty !== null &&
  dish.stock_qty !== undefined &&
  dish.low_stock_threshold !== null &&
  dish.low_stock_threshold !== undefined &&
  dish.stock_qty <= dish.low_stock_threshold;

const filtered = computed(() => {
  let list = dishes.value.filter((d) => d.is_published);

  if (filterLowOnly.value) {
    list = list.filter((d) => isLow(d));
  }

  const q = search.value.toLowerCase();
  if (q) {
    list = list.filter(
      (d) =>
        (d.name || "").toLowerCase().includes(q) ||
        (d.category_name || "").toLowerCase().includes(q) ||
        (d.category_slug || "").toLowerCase().includes(q)
    );
  }

  // Sort: sold-out first, then low-stock, then by name
  return [...list].sort((a, b) => {
    const aWeight = !a.is_available ? 0 : isLow(a) ? 1 : 2;
    const bWeight = !b.is_available ? 0 : isLow(b) ? 1 : 2;
    if (aWeight !== bWeight) return aWeight - bWeight;
    return (a.name || "").localeCompare(b.name || "");
  });
});

// ── Fetch ─────────────────────────────────────────────────────────────────────
const fetchDishes = async () => {
  if (fetching.value) return;
  fetching.value = true;
  try {
    const { data } = await api.get("/dishes/", { timeout: 8000 });
    dishes.value = Array.isArray(data) ? data : [];
  } catch {
    toast.show(t("ownerHome.noDishesLoaded"), "error");
  } finally {
    fetching.value = false;
  }
};

onMounted(fetchDishes);

// ── Stock helpers ─────────────────────────────────────────────────────────────

// Separate debounce timers so a stock edit and a threshold edit do not
// cancel each other when typed in quick succession.
let _stockTimer = null;
let _threshTimer = null;

const patchDish = async (dish, payload) => {
  if (savingId.value === dish.id) return;
  savingId.value = dish.id;
  try {
    await api.patch(`/dishes/${dish.id}/`, payload);
    Object.assign(dish, payload);
    // Auto-restore availability when stock is set above zero
    if (payload.stock_qty != null && payload.stock_qty > 0 && !dish.is_available) {
      await api.patch(`/dishes/${dish.id}/`, { is_available: true });
      dish.is_available = true;
    }
    bustCache("menu.categories");
    toast.show(t("inventory.saved"), "success");
  } catch {
    toast.show(t("inventory.saveFailed"), "error");
  } finally {
    savingId.value = null;
  }
};

const commitStock = (dish, rawValue) => {
  const trimmed = String(rawValue ?? "").trim();
  const newQty = trimmed === "" ? null : parseInt(trimmed, 10);
  if (newQty !== null && (isNaN(newQty) || newQty < 0)) return;
  if (newQty === dish.stock_qty) return;
  clearTimeout(_stockTimer);
  _stockTimer = setTimeout(() => patchDish(dish, { stock_qty: newQty }), 600);
};

const commitThreshold = (dish, rawValue) => {
  const trimmed = String(rawValue ?? "").trim();
  // Empty input = "reset to default" (3). The model field is non-nullable, so
  // sending null would 400 with an unhelpful generic error.
  const newVal = trimmed === "" ? 3 : parseInt(trimmed, 10);
  if (isNaN(newVal) || newVal < 0) return;
  if (newVal === dish.low_stock_threshold) return;
  clearTimeout(_threshTimer);
  _threshTimer = setTimeout(() => patchDish(dish, { low_stock_threshold: newVal }), 600);
};

const adjustStock = (dish, delta) => {
  const current = dish.stock_qty ?? 0;
  const next = Math.max(0, current + delta);
  if (next === dish.stock_qty) return;
  clearTimeout(_stockTimer);
  patchDish(dish, { stock_qty: next });
};

// ── Auto-reset toggle ─────────────────────────────────────────────────────────
const toggleAutoReset = async () => {
  if (savingReset.value) return;
  savingReset.value = true;
  const newValue = !autoReset.value;
  try {
    await api.patch("/profile/", { auto_reset_availability: newValue });
    tenant.mergeProfile({ auto_reset_availability: newValue });
  } catch {
    toast.show(t("inventory.saveFailed"), "error");
  } finally {
    savingReset.value = false;
  }
};
</script>
