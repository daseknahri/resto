<template>
  <!-- Station filter bar -->
  <nav class="kitchen-filter-bar" :aria-label="t('kitchen.stationFilterNav')">
    <button
      v-for="f in stationFilters"
      :key="f.value"
      class="kitchen-filter-btn ui-press focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
      :class="activeStationFilter === f.value ? 'kitchen-filter-btn--active' : ''"
      :aria-pressed="activeStationFilter === f.value"
      @click="emit('set-station-filter', f.value)"
    >
      {{ f.label }}
      <span v-if="f.count > 0" class="kitchen-filter-count" aria-hidden="true">{{ f.count }}</span>
    </button>
  </nav>

  <!-- Prep station filter bar (only shown when station-tagged items exist) -->
  <nav v-if="prepStationFilters.length > 1" class="kitchen-filter-bar" :aria-label="t('kitchen.prepStationNav')">
    <button
      v-for="f in prepStationFilters"
      :key="f.value"
      class="kitchen-filter-btn ui-press focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
      :class="activePrepStation === f.value ? 'kitchen-filter-btn--active' : ''"
      :aria-pressed="activePrepStation === f.value"
      @click="emit('set-prep-station', f.value)"
    >
      {{ f.label }}
      <span v-if="f.count > 0" class="kitchen-filter-count" aria-hidden="true">{{ f.count }}</span>
    </button>
  </nav>
</template>

<script setup>
// Station / prep-station filter bars of OwnerKitchen.vue, extracted as a
// standalone presentational child (RISK FE-2). The filter VALUES
// (stationFilter, prepStation refs), the derived option lists
// (stationFilters, prepStationFilters computeds), the auto-reset watchers,
// and every order fetch/poll/status-mutation concern stay owned by the
// parent — prepStation in particular is also read directly by the parent's
// order-card template (to dim items outside the selected station). This
// component only renders the two nav bars from the option lists + current
// value it's given, and asks the parent to change the selection via emits.
import { useI18n } from "../composables/useI18n";

const { t } = useI18n();

defineProps({
  /** { value, label, count } options for the fulfillment-type filter. */
  stationFilters: { type: Array, default: () => [] },
  /** Currently selected station-filter value ('all' | 'table' | 'pickup' | 'delivery'). */
  activeStationFilter: { type: String, default: "all" },
  /** { value, label, count } options for the prep-station filter (only rendered when >1). */
  prepStationFilters: { type: Array, default: () => [] },
  /** Currently selected prep-station value ('' = all stations). */
  activePrepStation: { type: String, default: "" },
});

const emit = defineEmits(["set-station-filter", "set-prep-station"]);
</script>

<style scoped>
/* Station filter bar — duplicated from OwnerKitchen.vue's scoped styles
   because .kitchen-filter-btn/--active are ALSO used by buttons that stay in
   the parent (the all-day toggle in the topbar, the includeHeld toggle in
   the all-day section); Vue scoped CSS only stamps this component's root
   node(s) with the parent's data-v- attribute, not the buttons nested
   inside, so the parent's rules alone would not reach these buttons. */
.kitchen-filter-bar {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
  flex-shrink: 0;
}

.kitchen-filter-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  border-radius: 9999px;
  border: 1px solid rgba(51, 65, 85, 0.6);
  background: rgba(30, 41, 59, 0.5);
  padding: 0.375rem 1rem;
  font-size: 0.8rem;
  font-weight: 600;
  color: rgb(148, 163, 184);
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s, background 0.15s;
}

.kitchen-filter-btn:hover {
  border-color: rgba(100, 116, 139, 0.8);
  color: rgb(203, 213, 225);
  background: rgba(30, 41, 59, 0.7);
}

.kitchen-filter-btn--active {
  border-color: rgba(245, 158, 11, 0.5);
  background: rgba(245, 158, 11, 0.12);
  color: rgb(251, 191, 36);
  font-weight: 700;
}

.kitchen-filter-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 1.35rem;
  height: 1.35rem;
  border-radius: 9999px;
  background: rgba(51, 65, 85, 0.9);
  font-size: 0.7rem;
  font-weight: 700;
  color: rgb(148, 163, 184);
  padding: 0 0.3rem;
}

.kitchen-filter-btn--active .kitchen-filter-count {
  background: rgba(245, 158, 11, 0.25);
  color: rgb(251, 191, 36);
}
</style>
