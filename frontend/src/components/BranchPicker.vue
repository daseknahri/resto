<template>
  <div
    v-if="branchStore.hasChoice"
    class="rounded-2xl border border-slate-700/50 bg-slate-900/40 px-4 py-3"
  >
    <label
      for="branch-picker-select"
      class="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-400"
    >
      <AppIcon name="info" class="h-3.5 w-3.5 shrink-0 text-slate-500" aria-hidden="true" />
      {{ t('branchPicker.label') }}
    </label>
    <select
      id="branch-picker-select"
      class="mt-2 w-full rounded-xl border border-slate-700/60 bg-slate-900 px-3 py-2.5 text-sm font-medium text-white focus:border-slate-500 focus:outline-none"
      :value="branchStore.selectedSlug"
      @change="branchStore.select($event.target.value)"
    >
      <option
        v-for="b in branchStore.branches"
        :key="b.slug"
        :value="b.slug"
      >
        {{ b.name }}
      </option>
    </select>
    <p
      v-if="branchStore.selectedBranch && branchStore.selectedBranch.address"
      class="mt-1.5 text-[11px] leading-relaxed text-slate-400"
    >
      {{ branchStore.selectedBranch.address }}
    </p>
  </div>
</template>

<script setup>
// Phase 3 multi-branch (decision D3) — the storefront location picker.
// Presentational shell over useBranchStore: renders only when the tenant
// has more than one active branch (a real choice), and forwards the
// selection to the store, which persists it and feeds Cart's place-order
// payload (`branch` slug → backend resolve_order_branch). Single-branch
// tenants see nothing and behave exactly as before.
import { onMounted } from 'vue';
import AppIcon from './AppIcon.vue';
import { useI18n } from '../composables/useI18n';
import { useBranchStore } from '../stores/branch';

const { t } = useI18n();
const branchStore = useBranchStore();

onMounted(() => {
  branchStore.load();
});
</script>
