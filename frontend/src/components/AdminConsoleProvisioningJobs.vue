<template>
  <section class="ui-workspace-stage p-4 space-y-3">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <div>
        <p class="ui-kicker">{{ t("adminConsole.reservationFollowUpSla") }}</p>
        <h2 class="ui-display text-2xl font-semibold text-white">{{ t("adminConsole.provisioningJobs") }}</h2>
      </div>
      <div class="ui-scroll-row">
        <button class="ui-btn-outline px-3 py-1.5 text-xs" @click="emit('toggle-expanded')">
          {{ expanded ? t("adminConsole.hide") : t("adminConsole.show") }}
        </button>
        <button class="ui-btn-outline px-4 py-2 text-sm disabled:opacity-50" :disabled="loading || !expanded" @click="emit('refresh')">{{ t("common.refresh") }}</button>
      </div>
    </div>
    <template v-if="expanded">
    <div v-if="loading" class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
      <article v-for="n in 3" :key="`job-skeleton-${n}`" class="ui-admin-card space-y-3">
        <div class="flex items-center justify-between gap-3">
          <div class="ui-skeleton h-4 w-32 rounded-full"></div>
          <div class="ui-skeleton h-4 w-16 rounded-full"></div>
        </div>
        <div class="space-y-2">
          <div class="ui-skeleton h-3 w-5/6 rounded-full"></div>
          <div class="ui-skeleton h-16 rounded-2xl"></div>
        </div>
      </article>
    </div>
    <article v-else-if="!jobs.length" class="ui-empty-state">
      <p class="ui-kicker">{{ t("adminConsole.provisioningJobs") }}</p>
      <h3 class="text-xl font-semibold text-white">{{ t("adminConsole.noJobsYet") }}</h3>
      <p class="max-w-2xl text-sm text-slate-400">{{ t("adminConsole.provisioningOperations") }}</p>
    </article>
    <div v-else class="space-y-2 md:hidden">
      <article
        v-for="(job, index) in jobs"
        :key="`job-mobile-${job.id}`"
        class="ui-admin-card ui-surface-lift ui-reveal space-y-2"
        :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
      >
        <div class="flex items-center justify-between gap-2">
          <p class="min-w-0 truncate text-sm font-semibold text-slate-100">#{{ job.id }} - {{ job.lead_name }}</p>
          <span class="ui-status-pill shrink-0 text-[10px] font-semibold" :class="statusClass(job.status)">{{ job.status }}</span>
        </div>
        <p class="text-xs text-slate-400">{{ t("adminConsole.tenant") }}: {{ job.tenant_slug || '-' }}</p>
        <p class="text-xs text-slate-400">{{ t("adminConsole.updated") }}: {{ formatDate(job.updated_at) }}</p>
        <p class="rounded-lg border border-slate-800 bg-slate-950/50 p-2 text-xs text-slate-300 whitespace-pre-wrap break-words">{{ job.log || "-" }}</p>
      </article>
    </div>

    <div v-if="jobs.length" class="ui-table-wrap hidden md:block">
      <table class="w-full min-w-[920px] text-sm">
        <thead class="bg-slate-900/70 text-slate-300">
          <tr>
            <th scope="col" class="px-4 py-3 text-start">{{ t("adminConsole.id") }}</th>
            <th scope="col" class="px-4 py-3 text-start">{{ t("adminConsole.lead") }}</th>
            <th scope="col" class="px-4 py-3 text-start">{{ t("adminConsole.tenant") }}</th>
            <th scope="col" class="px-4 py-3 text-start">{{ t("common.status") }}</th>
            <th scope="col" class="px-4 py-3 text-start">{{ t("adminConsole.log") }}</th>
            <th scope="col" class="px-4 py-3 text-start">{{ t("adminConsole.updated") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="job in jobs" :key="job.id" class="border-t border-slate-800">
            <td class="px-4 py-3 text-slate-100">#{{ job.id }}</td>
            <td class="px-4 py-3 text-slate-200">{{ job.lead_name }}</td>
            <td class="px-4 py-3 text-slate-200">{{ job.tenant_slug || '-' }}</td>
            <td class="px-4 py-3">
              <span class="ui-status-pill text-[10px] font-semibold" :class="statusClass(job.status)">{{ job.status }}</span>
            </td>
            <td class="px-4 py-3 text-slate-300 whitespace-pre-line text-xs leading-snug max-w-[320px]">{{ job.log }}</td>
            <td class="px-4 py-3 text-slate-400">{{ formatDate(job.updated_at) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    </template>
  </section>
</template>

<script setup>
// "Provisioning Jobs" section of AdminConsole.vue, extracted as a standalone
// child component (RISK FE-2). Fetching (fetchJobs) and the expand/collapse
// panel state (adminPanels.jobs) stay owned by the parent — this component is
// purely presentational: it renders whatever job list/loading state it's
// given and asks the parent to toggle/refresh via emits. `statusClass` is
// only ever used by this section, so it moves here in full; `formatDate` is
// shared across the parent so it's duplicated here as a small pure function
// of the current locale (same approach as AdminConsoleOnboardingPackage).
import { useI18n } from "../composables/useI18n";

defineProps({
  /** Provisioning job records to render. */
  jobs: { type: Array, default: () => [] },
  /** Whether a fetch is in-flight (drives the skeleton state). */
  loading: { type: Boolean, default: false },
  /** Whether the panel body is expanded (parent-owned show/hide toggle). */
  expanded: { type: Boolean, default: false },
});

const emit = defineEmits(["toggle-expanded", "refresh"]);

const { t, currentLocale } = useI18n();

const statusClass = (status) => {
  if (status === "success") return "bg-emerald-600/30 text-emerald-200";
  if (status === "running") return "bg-amber-500/30 text-amber-200";
  if (status === "failed") return "bg-red-600/30 text-red-200";
  return "bg-slate-700/50 text-slate-200";
};

const formatDate = (value) => {
  if (!value) return "-";
  try {
    return new Intl.DateTimeFormat(currentLocale.value, { dateStyle: "short", timeStyle: "short" }).format(new Date(value));
  } catch {
    return String(value);
  }
};
</script>
