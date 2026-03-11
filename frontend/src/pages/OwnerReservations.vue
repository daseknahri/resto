<template>
  <section class="space-y-6 ui-safe-bottom pb-28 sm:pb-6">
    <header class="space-y-3 ui-fade-up">
      <p class="ui-kicker">{{ t("ownerReservations.kicker") }}</p>
      <h2 class="ui-page-title ui-display">{{ t("ownerReservations.title") }}</h2>
      <p class="max-w-3xl text-sm text-slate-300">{{ t("ownerReservations.description") }}</p>
    </header>

    <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
      <article class="ui-panel p-4">
        <p class="text-xs uppercase tracking-[0.2em] text-slate-400">{{ t("ownerReservations.total") }}</p>
        <p class="mt-2 text-2xl font-semibold text-white">{{ counts.total }}</p>
      </article>
      <article class="ui-panel p-4">
        <p class="text-xs uppercase tracking-[0.2em] text-slate-400">{{ t("ownerReservations.new") }}</p>
        <p class="mt-2 text-2xl font-semibold text-amber-300">{{ counts.new }}</p>
      </article>
      <article class="ui-panel p-4">
        <p class="text-xs uppercase tracking-[0.2em] text-slate-400">{{ t("ownerReservations.overdue") }}</p>
        <p class="mt-2 text-2xl font-semibold text-rose-300">{{ counts.overdue_new }}</p>
      </article>
      <article class="ui-panel p-4">
        <p class="text-xs uppercase tracking-[0.2em] text-slate-400">{{ t("ownerReservations.contacted") }}</p>
        <p class="mt-2 text-2xl font-semibold text-sky-300">{{ counts.contacted }}</p>
      </article>
      <article class="ui-panel p-4">
        <p class="text-xs uppercase tracking-[0.2em] text-slate-400">{{ t("ownerReservations.confirmed") }}</p>
        <p class="mt-2 text-2xl font-semibold text-emerald-300">{{ counts.won }}</p>
      </article>
    </div>

    <article class="ui-panel p-4 space-y-2">
      <div class="flex items-center justify-between gap-2">
        <p class="text-sm text-slate-300">{{ t("ownerReservations.followUpCompletion") }}</p>
        <span class="text-sm font-semibold text-[var(--color-secondary)]">{{ followUpProgress }}%</span>
      </div>
      <div class="h-2 overflow-hidden rounded-full bg-slate-800">
        <div class="h-full rounded-full bg-[var(--color-secondary)] transition-all duration-300" :style="{ width: `${followUpProgress}%` }"></div>
      </div>
      <p class="text-xs text-slate-500">{{ t("ownerReservations.resolvedProgress", { resolved: resolvedCount, total: counts.total }) }}</p>
    </article>

    <section class="ui-panel p-4 space-y-4">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div class="ui-scroll-row">
          <button
            v-for="option in statusOptions"
            :key="option.value"
            class="ui-pill-nav text-xs"
            :class="statusFilter === option.value ? 'border-[var(--color-secondary)] bg-[var(--color-secondary)]/10 text-[var(--color-secondary)]' : ''"
            @click="setFilter(option.value)"
          >
            {{ option.label }}
          </button>
        </div>
        <span class="text-xs text-slate-500">{{ t("ownerReservations.statusFilter") }}</span>
      </div>

      <div class="flex flex-wrap items-center justify-between gap-3">
        <div class="ui-scroll-row">
          <button
            v-for="option in reminderOptions"
            :key="option.value"
            class="ui-pill-nav text-xs"
            :class="reminderFilter === option.value ? reminderFilterClass(option.value) : ''"
            @click="setReminderFilter(option.value)"
          >
            {{ option.label }}
          </button>
        </div>
        <button
          class="ui-btn-outline px-3 py-1.5 text-xs"
          :class="reminderFilter === 'failed' ? 'border-rose-400 text-rose-200' : ''"
          @click="setReminderFilter(reminderFilter === 'failed' ? '' : 'failed')"
        >
          {{ reminderFilter === "failed" ? t("ownerReservations.exitRetryQueue") : t("ownerReservations.retryQueue") }}
        </button>
      </div>

      <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-[1fr,auto,auto,auto]">
        <input
          v-model.trim="searchQuery"
          class="ui-input"
          :placeholder="t('ownerReservations.searchPlaceholder')"
          @keyup.enter="applyFilters"
        />
        <input v-model="dateFrom" type="date" class="ui-input" />
        <input v-model="dateTo" type="date" class="ui-input" />
        <div class="flex flex-wrap items-center gap-2 sm:col-span-2 xl:col-span-1">
          <select v-model.number="pageSize" class="ui-input w-24" @change="onPageSizeChange">
            <option :value="10">10</option>
            <option :value="20">20</option>
            <option :value="50">50</option>
          </select>
          <button class="ui-btn-primary px-4 py-2 text-sm" :disabled="loading" @click="applyFilters">
            {{ t("common.apply") }}
          </button>
          <button class="ui-btn-outline px-4 py-2 text-sm" :disabled="loading" @click="clearFilters">
            {{ t("common.clear") }}
          </button>
          <button class="ui-btn-outline px-4 py-2 text-sm" :disabled="exporting" @click="exportCsv">
            {{ exporting ? t("ownerReservations.exporting") : t("ownerReservations.exportCsv") }}
          </button>
          <button class="ui-btn-outline px-4 py-2 text-sm" :disabled="loading" @click="fetchReservations">
            {{ loading ? t("common.loading") : t("common.refresh") }}
          </button>
        </div>
      </div>

      <div class="rounded-xl border border-slate-800 bg-slate-950/40 p-3">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <label class="inline-flex items-center gap-2 text-xs text-slate-300">
            <input type="checkbox" :checked="allSelectedOnPage" @change="toggleSelectAllOnPage" />
            {{ t("ownerReservations.selectPage") }}
          </label>
          <p class="text-xs text-slate-400">{{ t("ownerReservations.selectedCount", { count: selectedCount }) }}</p>
        </div>
        <div class="mt-2 flex flex-wrap gap-2">
          <button
            class="ui-btn-outline px-3 py-1.5 text-xs"
            :class="reminderFilter === 'failed' ? 'border-rose-400 text-rose-200' : ''"
            :disabled="!selectedCount || bulkReminderLoading"
            @click="bulkRetryReminders"
          >
            {{ bulkReminderLoading ? t("ownerReservations.preparing") : t("ownerReservations.bulkRetryReminders") }}
          </button>
          <button class="ui-btn-outline px-3 py-1.5 text-xs" :disabled="!selectedCount || bulkUpdating" @click="bulkUpdateStatus('contacted')">
            {{ t("ownerReservations.markContacted") }}
          </button>
          <button class="ui-btn-outline px-3 py-1.5 text-xs" :disabled="!selectedCount || bulkUpdating" @click="bulkUpdateStatus('won')">
            {{ t("ownerReservations.markConfirmed") }}
          </button>
          <button class="ui-btn-outline px-3 py-1.5 text-xs" :disabled="!selectedCount || bulkUpdating" @click="bulkUpdateStatus('lost')">
            {{ t("ownerReservations.markUnavailable") }}
          </button>
          <button class="ui-btn-outline px-3 py-1.5 text-xs" :disabled="!selectedCount || bulkUpdating" @click="bulkUpdateStatus('new')">
            {{ t("ownerReservations.resetNew") }}
          </button>
        </div>
        <div v-if="pendingReminderReconciliation.length" class="mt-3 rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-xs space-y-2">
          <p class="text-amber-200">
            {{ t("ownerReservations.pendingReminderCount", { count: pendingReminderReconciliation.length }) }}
          </p>
          <p class="text-amber-100/80">{{ t("ownerReservations.pendingReminderHelp") }}</p>
          <div class="flex flex-wrap gap-2">
            <button
              class="rounded-full border border-emerald-500/70 px-3 py-1.5 text-xs font-semibold text-emerald-200 disabled:opacity-60"
              :disabled="bulkReconcileLoading"
              @click="reconcilePendingReminders('opened')"
            >
              {{ bulkReconcileLoading ? t("ownerReservations.saving") : t("ownerReservations.markOpened") }}
            </button>
            <button
              class="rounded-full border border-rose-500/70 px-3 py-1.5 text-xs font-semibold text-rose-200 disabled:opacity-60"
              :disabled="bulkReconcileLoading"
              @click="reconcilePendingReminders('failed')"
            >
              {{ bulkReconcileLoading ? t("ownerReservations.saving") : t("ownerReservations.markFailed") }}
            </button>
            <button
              class="rounded-full border border-slate-600 px-3 py-1.5 text-xs font-semibold text-slate-300 disabled:opacity-60"
              :disabled="bulkReconcileLoading"
              @click="clearPendingReminderReconciliation"
            >
              {{ t("ownerReservations.clearPending") }}
            </button>
          </div>
        </div>
      </div>

      <p v-if="error" class="text-sm text-red-300">{{ error }}</p>
      <p v-else-if="loading" class="text-sm text-slate-400">{{ t("ownerReservations.loadingReservations") }}</p>
      <p v-else-if="!reservations.length" class="text-sm text-slate-400">{{ t("ownerReservations.noReservations") }}</p>

      <div class="grid gap-3 lg:grid-cols-2">
        <article
          v-for="reservation in reservations"
          :key="reservation.id"
          class="rounded-2xl border bg-slate-900/70 p-4 space-y-3"
          :class="reservationCardClass(reservation)"
        >
          <div class="flex items-start justify-between gap-3">
            <label class="inline-flex items-center gap-2">
              <input
                type="checkbox"
                :checked="isSelected(reservation.id)"
                @change="toggleSelection(reservation.id)"
              />
              <span class="text-base font-semibold text-slate-100">{{ reservation.name || t("ownerReservations.fallbackReservationName", { id: reservation.id }) }}</span>
            </label>
            <span class="rounded-full px-2 py-1 text-[11px] font-semibold" :class="statusClass(reservation.status)">
              {{ statusLabel(reservation.status) }}
            </span>
          </div>
          <div v-if="reservation.sla_state && reservation.sla_state !== 'not_applicable'" class="flex flex-wrap items-center gap-2">
            <span class="rounded-full px-2 py-1 text-[11px] font-semibold" :class="slaClass(reservation.sla_state)">
              {{ slaLabel(reservation) }}
            </span>
            <span v-if="reservation.follow_up_due_at" class="text-[11px] text-slate-500">
              {{ t("ownerReservations.dueLabel", { date: formatDate(reservation.follow_up_due_at) }) }}
            </span>
          </div>

          <p class="text-xs text-slate-400">{{ formatDate(reservation.created_at) }}</p>

          <div class="space-y-1 text-sm">
            <p class="text-slate-200">{{ reservation.phone || "-" }}</p>
            <p class="text-slate-400">{{ reservation.email || "-" }}</p>
          </div>

          <p class="rounded-xl border border-slate-800 bg-slate-950/50 p-2 text-xs text-slate-300 whitespace-pre-line">
            {{ reservation.notes || t("ownerReservations.noCustomerNote") }}
          </p>

          <div class="flex flex-wrap items-center gap-2 text-[11px]">
            <span class="rounded-full border border-slate-700 px-2 py-1 text-slate-300">
              {{ t("ownerReservations.reminders") }} {{ reservation.reminder_count || 0 }}
            </span>
            <span class="rounded-full border border-slate-700 px-2 py-1 text-slate-400">
              {{ t("ownerReservations.opened") }} {{ reservation.reminder_opened_count || 0 }}
            </span>
            <span class="rounded-full border border-slate-700 px-2 py-1 text-slate-400">
              {{ t("ownerReservations.failed") }} {{ reservation.reminder_failed_count || 0 }}
            </span>
            <span
              v-if="reservation.last_reminder_status"
              class="rounded-full px-2 py-1 font-semibold"
              :class="reminderStatusClass(reservation.last_reminder_status)"
            >
              {{ t("ownerReservations.last") }} {{ reminderStatusLabel(reservation.last_reminder_status) }}
            </span>
            <span v-if="reservation.last_reminder_at" class="text-slate-500">
              {{ formatDate(reservation.last_reminder_at) }}
            </span>
          </div>

          <div class="flex flex-wrap items-center gap-2">
            <a
              v-if="telHref(reservation)"
              :href="telHref(reservation)"
              class="rounded-full border border-slate-700 px-3 py-1.5 text-xs text-slate-100 hover:border-[var(--color-secondary)]"
            >
              {{ t("common.call") }}
            </a>
            <a
              v-if="whatsappHref(reservation)"
              :href="whatsappHref(reservation)"
              target="_blank"
              rel="noopener noreferrer"
              class="rounded-full border border-slate-700 px-3 py-1.5 text-xs text-slate-100 hover:border-[var(--color-secondary)]"
            >
              {{ t("ownerReservations.quickChat") }}
            </a>
          </div>

          <div class="grid grid-cols-2 gap-2 sm:grid-cols-3">
            <button
              class="rounded-full border border-emerald-500/70 px-3 py-1.5 text-xs font-semibold text-emerald-200 disabled:opacity-60"
              :disabled="isReminderSending(reservation.id) || !canSendReminder(reservation)"
              @click="sendReminder(reservation)"
            >
              {{ isReminderSending(reservation.id) ? t("ownerReservations.opening") : t("ownerReservations.reminder") }}
            </button>
            <button
              class="rounded-full bg-sky-500/90 px-3 py-1.5 text-xs font-semibold text-slate-950 disabled:opacity-60"
              :disabled="isUpdating(reservation.id)"
              @click="updateStatus(reservation, 'contacted')"
            >
              {{ t("ownerReservations.contacted") }}
            </button>
            <button
              class="rounded-full bg-emerald-500/90 px-3 py-1.5 text-xs font-semibold text-slate-950 disabled:opacity-60"
              :disabled="isUpdating(reservation.id)"
              @click="updateStatus(reservation, 'won')"
            >
              {{ t("ownerReservations.confirmed") }}
            </button>
            <button
              class="rounded-full border border-rose-500/70 px-3 py-1.5 text-xs font-semibold text-rose-200 disabled:opacity-60"
              :disabled="isUpdating(reservation.id)"
              @click="updateStatus(reservation, 'lost')"
            >
              {{ t("ownerReservations.unavailable") }}
            </button>
            <button
              class="rounded-full border border-slate-700 px-3 py-1.5 text-xs font-semibold text-slate-200 disabled:opacity-60"
              :disabled="isUpdating(reservation.id)"
              @click="updateStatus(reservation, 'new')"
            >
              {{ t("ownerReservations.resetNew") }}
            </button>
            <button
              class="rounded-full border border-slate-700 px-3 py-1.5 text-xs font-semibold text-slate-200 disabled:opacity-60"
              :disabled="isTimelineLoading(reservation.id)"
              @click="toggleTimeline(reservation.id)"
            >
              {{ isTimelineOpen(reservation.id) ? t("ownerReservations.hideTimeline") : t("ownerReservations.timeline") }}
            </button>
          </div>

          <div v-if="isTimelineOpen(reservation.id)" class="rounded-xl border border-slate-800 bg-slate-950/40 p-3 space-y-3">
            <p class="text-xs uppercase tracking-[0.18em] text-slate-400">{{ t("ownerReservations.timelineTitle") }}</p>
            <p v-if="isTimelineLoading(reservation.id)" class="text-xs text-slate-500">{{ t("ownerReservations.loadingTimeline") }}</p>
            <ul v-else class="space-y-2 text-xs">
              <li
                v-for="entry in timelineFor(reservation.id)"
                :key="entry.id"
                class="rounded-lg border border-slate-800 bg-slate-900/70 p-2"
              >
                <div class="flex items-center justify-between gap-2">
                  <span class="font-semibold text-slate-200">{{ timelineActionLabel(entry.action) }}</span>
                  <span class="text-slate-500">{{ formatDate(entry.created_at) }}</span>
                </div>
                <p v-if="entry.note" class="mt-1 whitespace-pre-line text-slate-300">{{ entry.note }}</p>
                <p v-if="entry.previous_status || entry.new_status" class="mt-1 text-slate-400">
                  {{ statusLabel(entry.previous_status) || "-" }} -> {{ statusLabel(entry.new_status) || "-" }}
                </p>
                <p v-if="entry.actor_username" class="mt-1 text-slate-500">{{ t("ownerReservations.byActor", { actor: entry.actor_username }) }}</p>
              </li>
              <li v-if="!timelineFor(reservation.id).length" class="text-slate-500">{{ t("ownerReservations.noTimelineEntries") }}</li>
            </ul>

            <div class="flex flex-wrap items-start gap-2">
              <textarea
                v-model.trim="timelineNote[reservation.id]"
                rows="2"
                class="ui-textarea min-w-[220px] flex-1"
                :placeholder="t('ownerReservations.addFollowUpNote')"
              ></textarea>
              <button
                class="ui-btn-outline px-3 py-2 text-xs disabled:opacity-60"
                :disabled="isTimelineSubmitting(reservation.id)"
                @click="addTimelineNote(reservation.id)"
              >
                {{ isTimelineSubmitting(reservation.id) ? t("ownerReservations.saving") : t("ownerReservations.addNote") }}
              </button>
            </div>
          </div>
        </article>
      </div>

      <div class="flex flex-wrap items-center justify-between gap-2 border-t border-slate-800 pt-3">
        <p class="text-xs text-slate-400">
          {{ t("ownerReservations.pageSummary", { page: pagination.page, pages: pagination.pages, total: pagination.total }) }}
        </p>
        <div class="flex items-center gap-2">
          <button class="ui-btn-outline px-3 py-1.5 text-xs" :disabled="!pagination.has_prev || loading" @click="goPrevPage">
            {{ t("common.previous") }}
          </button>
          <button class="ui-btn-outline px-3 py-1.5 text-xs" :disabled="!pagination.has_next || loading" @click="goNextPage">
            {{ t("common.next") }}
          </button>
        </div>
      </div>
    </section>

    <div
      v-if="selectedCount"
      class="fixed bottom-4 left-3 right-3 z-20 rounded-2xl border border-slate-700/80 bg-slate-950/92 p-3 shadow-xl shadow-black/40 backdrop-blur lg:hidden"
    >
      <div class="space-y-2">
        <p class="text-xs text-slate-300">{{ t("ownerReservations.selectedCount", { count: selectedCount }) }}</p>
        <div class="grid grid-cols-3 gap-2">
          <button class="ui-btn-outline justify-center text-xs" :disabled="bulkUpdating" @click="bulkUpdateStatus('contacted')">{{ t("ownerReservations.contacted") }}</button>
          <button class="ui-btn-outline justify-center text-xs" :disabled="bulkUpdating" @click="bulkUpdateStatus('won')">{{ t("ownerReservations.confirmed") }}</button>
          <button
            class="ui-btn-outline justify-center text-xs"
            :disabled="bulkReminderLoading"
            :class="reminderFilter === 'failed' ? 'border-rose-400 text-rose-200' : ''"
            @click="bulkRetryReminders"
          >
            {{ t("ownerReservations.retryQueue") }}
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useI18n } from "../composables/useI18n";
import api from "../lib/api";
import { useToastStore } from "../stores/toast";

const toast = useToastStore();
const { t, formatDateTime } = useI18n();
const reservations = ref([]);
const loading = ref(false);
const error = ref("");
const statusFilter = ref("");
const reminderFilter = ref("");
const searchQuery = ref("");
const dateFrom = ref("");
const dateTo = ref("");
const exporting = ref(false);
const bulkUpdating = ref(false);
const bulkReminderLoading = ref(false);
const bulkReconcileLoading = ref(false);
const updating = ref({});
const reminderLoading = ref({});
const pendingReminderReconciliation = ref([]);
const selectedIds = ref([]);
const timelineOpen = ref({});
const timelineLoading = ref({});
const timelineItems = ref({});
const timelineNote = ref({});
const timelineSubmitting = ref({});
const page = ref(1);
const pageSize = ref(20);
const pagination = ref({
  page: 1,
  page_size: 20,
  total: 0,
  pages: 1,
  has_next: false,
  has_prev: false,
});
const counts = ref({
  total: 0,
  new: 0,
  overdue_new: 0,
  contacted: 0,
  won: 0,
  lost: 0,
});

const statusOptions = computed(() => [
  { value: "", label: t("ownerReservations.allStatuses") },
  { value: "new", label: t("ownerReservations.new") },
  { value: "contacted", label: t("ownerReservations.contacted") },
  { value: "won", label: t("ownerReservations.confirmed") },
  { value: "lost", label: t("ownerReservations.unavailable") },
]);

const reminderOptions = computed(() => [
  { value: "", label: t("ownerReservations.allReminders") },
  { value: "failed", label: t("ownerReservations.failed") },
  { value: "sent", label: t("ownerReservations.sent") },
  { value: "opened", label: t("ownerReservations.opened") },
  { value: "none", label: t("ownerReservations.noReminders") },
]);

const selectedCount = computed(() => selectedIds.value.length);
const allSelectedOnPage = computed(() => {
  if (!reservations.value.length) return false;
  const pageIds = reservations.value.map((row) => row.id);
  return pageIds.every((id) => selectedIds.value.includes(id));
});
const resolvedCount = computed(() => Number(counts.value.contacted || 0) + Number(counts.value.won || 0) + Number(counts.value.lost || 0));
const followUpProgress = computed(() => {
  const total = Number(counts.value.total || 0);
  if (!total) return 0;
  return Math.round((resolvedCount.value / total) * 100);
});

const parseApiError = (err, fallback) => {
  const data = err?.response?.data;
  if (typeof data?.detail === "string") return data.detail;
  if (typeof data === "string" && data.trim()) return data;
  return fallback;
};

const formatDate = (value) => formatDateTime(value) || "-";

const sanitizePhone = (value) => String(value || "").replace(/\D/g, "");
const sanitizeTel = (value) =>
  String(value || "")
    .replace(/[^\d+]/g, "")
    .replace(/(?!^)\+/g, "");

const telHref = (reservation) => {
  const tel = sanitizeTel(reservation?.phone || "");
  return tel ? `tel:${tel}` : "";
};

const whatsappHref = (reservation) => {
  const phone = sanitizePhone(reservation?.phone || "");
  if (!phone) return "";
  const name = String(reservation?.name || t("ownerReservations.guestFallback")).trim();
  const text = encodeURIComponent(t("ownerReservations.whatsappTemplate", { name }));
  return `https://wa.me/${phone}?text=${text}`;
};

const statusClass = (status) => {
  if (status === "new") return "bg-amber-500/20 text-amber-200";
  if (status === "contacted") return "bg-sky-500/20 text-sky-200";
  if (status === "won") return "bg-emerald-500/20 text-emerald-200";
  if (status === "lost") return "bg-rose-500/20 text-rose-200";
  return "bg-slate-700 text-slate-200";
};

const statusLabel = (status) => {
  if (status === "new") return t("ownerReservations.new");
  if (status === "contacted") return t("ownerReservations.contacted");
  if (status === "won") return t("ownerReservations.confirmed");
  if (status === "lost") return t("ownerReservations.unavailable");
  return status ? String(status) : "";
};

const slaClass = (slaState) => {
  if (slaState === "overdue") return "bg-rose-500/20 text-rose-200";
  if (slaState === "due_soon") return "bg-amber-500/20 text-amber-200";
  if (slaState === "on_track") return "bg-emerald-500/20 text-emerald-200";
  if (slaState === "resolved") return "bg-slate-700/60 text-slate-300";
  return "bg-slate-800 text-slate-400";
};

const slaLabel = (reservation) => {
  const state = String(reservation?.sla_state || "");
  if (state === "overdue") {
    const minutes = Number(reservation?.sla_minutes_overdue || 0);
    return minutes > 0 ? `${t("ownerReservations.statusOverdue")} ${minutes}m` : t("ownerReservations.statusOverdue");
  }
  if (state === "due_soon") return t("ownerReservations.statusDueSoon");
  if (state === "on_track") return t("ownerReservations.statusOnTrack");
  if (state === "resolved") return t("ownerReservations.statusResolved");
  return t("ownerReservations.noSla");
};

const reminderStatusClass = (status) => {
  if (status === "opened") return "bg-emerald-500/20 text-emerald-200";
  if (status === "failed") return "bg-rose-500/20 text-rose-200";
  if (status === "sent") return "bg-amber-500/20 text-amber-200";
  return "bg-slate-700/60 text-slate-300";
};

const reminderStatusLabel = (status) => {
  if (status === "opened") return t("ownerReservations.opened");
  if (status === "failed") return t("ownerReservations.failed");
  if (status === "sent") return t("ownerReservations.sent");
  return t("ownerReservations.unknown");
};

const timelineActionLabel = (action) => {
  const normalized = String(action || "").toLowerCase();
  if (normalized.includes("status")) return t("ownerReservations.timelineActionStatusChange");
  if (normalized.includes("note")) return t("ownerReservations.timelineActionNote");
  if (normalized.includes("reminder")) return t("ownerReservations.timelineActionReminder");
  return action ? String(action) : t("ownerReservations.timelineActionUnknown");
};

const reminderFilterClass = (value) => {
  if (value === "failed") return "border-rose-400 bg-rose-500/10 text-rose-200";
  if (value === "sent") return "border-amber-400 bg-amber-500/10 text-amber-200";
  if (value === "opened") return "border-emerald-400 bg-emerald-500/10 text-emerald-200";
  if (value === "none") return "border-slate-500 bg-slate-500/10 text-slate-200";
  return "border-[var(--color-secondary)] bg-[var(--color-secondary)]/10 text-[var(--color-secondary)]";
};

const reservationCardClass = (reservation) => {
  if (reservation?.last_reminder_status === "failed") return "border-rose-500/70";
  if (reservation?.last_reminder_status === "opened") return "border-emerald-500/60";
  if (reservation?.last_reminder_status === "sent") return "border-amber-500/60";
  return "border-slate-800";
};

const isUpdating = (id) => Boolean(updating.value[id]);
const isReminderSending = (id) => Boolean(reminderLoading.value[id]);
const isSelected = (id) => selectedIds.value.includes(id);
const isTimelineOpen = (id) => Boolean(timelineOpen.value[id]);
const isTimelineLoading = (id) => Boolean(timelineLoading.value[id]);
const isTimelineSubmitting = (id) => Boolean(timelineSubmitting.value[id]);
const timelineFor = (id) => (Array.isArray(timelineItems.value[id]) ? timelineItems.value[id] : []);
const canSendReminder = (reservation) => Boolean(whatsappHref(reservation)) && reservation?.status !== "lost";

const buildFilterParams = () => {
  const params = {};
  if (statusFilter.value) params.status = statusFilter.value;
  if (reminderFilter.value) params.reminder_status = reminderFilter.value;
  if (searchQuery.value) params.q = searchQuery.value;
  if (dateFrom.value) params.from = dateFrom.value;
  if (dateTo.value) params.to = dateTo.value;
  return params;
};

const buildListParams = () => ({
  ...buildFilterParams(),
  page: page.value,
  page_size: pageSize.value,
});

const fetchReservations = async () => {
  loading.value = true;
  error.value = "";
  try {
    const res = await api.get("/owner/reservations/", { params: buildListParams() });
    const payload = res?.data || {};
    if (Array.isArray(payload)) {
      reservations.value = payload;
      pagination.value = {
        page: 1,
        page_size: payload.length,
        total: payload.length,
        pages: 1,
        has_next: false,
        has_prev: false,
      };
      counts.value = {
        total: payload.length,
        new: payload.filter((row) => row.status === "new").length,
        overdue_new: payload.filter((row) => row.sla_state === "overdue").length,
        contacted: payload.filter((row) => row.status === "contacted").length,
        won: payload.filter((row) => row.status === "won").length,
        lost: payload.filter((row) => row.status === "lost").length,
      };
    } else {
      reservations.value = Array.isArray(payload.results) ? payload.results : [];
      pagination.value = payload.pagination || pagination.value;
      counts.value = { ...counts.value, ...(payload.counts || {}) };
      page.value = Number(pagination.value.page || page.value);
    }
    selectedIds.value = [];
  } catch (err) {
    const message = parseApiError(err, t("ownerReservations.loadFailed"));
    error.value = message;
    toast.show(message, "error");
  } finally {
    loading.value = false;
  }
};

const updateStatus = async (reservation, status) => {
  const id = reservation?.id;
  if (!id) return;
  updating.value = { ...updating.value, [id]: true };
  try {
    await api.put(`/owner/reservations/${id}/`, { status });
    toast.show(t("ownerReservations.updatedReservation"), "success");
    await fetchReservations();
  } catch (err) {
    toast.show(parseApiError(err, t("ownerReservations.updateReservationFailed")), "error");
  } finally {
    const clone = { ...updating.value };
    delete clone[id];
    updating.value = clone;
  }
};

const sendReminder = async (reservation) => {
  const id = reservation?.id;
  if (!id || !canSendReminder(reservation)) return;
  reminderLoading.value = { ...reminderLoading.value, [id]: true };
  try {
    const res = await api.post(`/owner/reservations/${id}/reminder/`, {});
    const fallback = whatsappHref(reservation);
    const link = String(res?.data?.whatsapp_link || fallback || "");
    const reminderId = Number(res?.data?.id || 0);
    let popup = null;
    if (link) {
      popup = window.open(link, "_blank", "noopener,noreferrer");
    }
    if (reminderId > 0) {
      const opened = Boolean(popup);
      await api.post(`/owner/reservations/${id}/reminder-result/`, {
        reminder_id: reminderId,
        status: opened ? "opened" : "failed",
        error: opened ? "" : t("ownerReservations.reminderBlocked"),
      });
    }
    if (popup) {
      toast.show(t("ownerReservations.reminderOpened"), "success");
    } else {
      if (link && navigator?.clipboard?.writeText) {
        try {
          await navigator.clipboard.writeText(link);
        } catch {
          // Ignore clipboard errors and still show fallback guidance.
        }
      }
      toast.show(t("ownerReservations.reminderBlocked"), "error");
    }
    await fetchReservations();
    if (isTimelineOpen(id)) {
      await fetchTimeline(id);
    }
  } catch (err) {
    toast.show(parseApiError(err, t("ownerReservations.prepareReminderFailed")), "error");
  } finally {
    const clone = { ...reminderLoading.value };
    delete clone[id];
    reminderLoading.value = clone;
  }
};

const bulkRetryReminders = async () => {
  if (!selectedIds.value.length) return;
  bulkReminderLoading.value = true;
  try {
    const res = await api.post("/owner/reservations/bulk-reminder/", {
      ids: selectedIds.value,
      require_failed_last_reminder: reminderFilter.value === "failed",
    });
    const payload = res?.data || {};
    const preparedCount = Number(payload.prepared_count || 0);
    const skippedNoPhone = Array.isArray(payload.skipped_no_phone_ids) ? payload.skipped_no_phone_ids.length : 0;
    const skippedUnavailable = Array.isArray(payload.skipped_unavailable_ids) ? payload.skipped_unavailable_ids.length : 0;
    const skippedNotFailed = Array.isArray(payload.skipped_not_failed_ids) ? payload.skipped_not_failed_ids.length : 0;
    const results = Array.isArray(payload.results) ? payload.results : [];
    const links = results.map((item) => String(item?.whatsapp_link || "").trim()).filter(Boolean);
    pendingReminderReconciliation.value = results;

    let firstPopup = null;
    if (links.length) {
      firstPopup = window.open(links[0], "_blank", "noopener,noreferrer");
    }
    if (links.length && navigator?.clipboard?.writeText) {
      try {
        await navigator.clipboard.writeText(links.join("\n"));
      } catch {
        // Ignore clipboard errors and keep summary toast.
      }
    }
    if (results.length) {
      const first = results[0];
      if (first?.lead_id && first?.reminder_id) {
        try {
          const res = await api.post("/owner/reservations/bulk-reminder-result/", {
            items: [
              {
                lead_id: first.lead_id,
                reminder_id: first.reminder_id,
                status: firstPopup ? "opened" : "failed",
                error: firstPopup ? "" : t("ownerReservations.reminderBlocked"),
              },
            ],
          });
          if (Number(res?.data?.updated_count || 0) > 0) {
            pendingReminderReconciliation.value = pendingReminderReconciliation.value.slice(1);
          }
        } catch {
          // Best effort tracking; do not fail whole operation.
        }
      }
    }

    if (!preparedCount) {
      toast.show(t("ownerReservations.noRemindersPrepared"), "info");
    } else if (firstPopup) {
      toast.show(t("ownerReservations.preparedAndOpened", { count: preparedCount }), "success");
    } else {
      toast.show(t("ownerReservations.preparedAndCopied", { count: preparedCount }), "info");
    }

    if (skippedNoPhone || skippedUnavailable || skippedNotFailed) {
      toast.show(
        t("ownerReservations.skippedSummary", {
          noPhone: skippedNoPhone,
          unavailable: skippedUnavailable,
          notFailed: skippedNotFailed,
        }),
        "info"
      );
    }

    await fetchReservations();
    for (const reservationId of Object.keys(timelineOpen.value)) {
      const parsed = Number(reservationId);
      if (Number.isFinite(parsed) && parsed > 0) {
        await fetchTimeline(parsed);
      }
    }
  } catch (err) {
    toast.show(parseApiError(err, t("ownerReservations.prepareBulkReminderFailed")), "error");
  } finally {
    bulkReminderLoading.value = false;
  }
};

const clearPendingReminderReconciliation = () => {
  pendingReminderReconciliation.value = [];
};

const reconcilePendingReminders = async (status) => {
  if (!pendingReminderReconciliation.value.length) return;
  bulkReconcileLoading.value = true;
  try {
    const items = pendingReminderReconciliation.value.map((item) => ({
      lead_id: item.lead_id,
      reminder_id: item.reminder_id,
      status,
      error: status === "failed" ? t("ownerReservations.markFailed") : "",
    }));
    const res = await api.post("/owner/reservations/bulk-reminder-result/", { items });
    const updatedCount = Number(res?.data?.updated_count || 0);
    const missingCount = Number(res?.data?.missing_count || 0);
    pendingReminderReconciliation.value = [];
    toast.show(
      missingCount
        ? t("ownerReservations.reconciledWithMissing", { updated: updatedCount, missing: missingCount })
        : t("ownerReservations.reconciled", { updated: updatedCount }),
      "success"
    );
    await fetchReservations();
    for (const reservationId of Object.keys(timelineOpen.value)) {
      const parsed = Number(reservationId);
      if (Number.isFinite(parsed) && parsed > 0) {
        await fetchTimeline(parsed);
      }
    }
  } catch (err) {
    toast.show(parseApiError(err, t("ownerReservations.reconcileFailed")), "error");
  } finally {
    bulkReconcileLoading.value = false;
  }
};

const bulkUpdateStatus = async (status) => {
  if (!selectedIds.value.length) return;
  bulkUpdating.value = true;
  try {
    const res = await api.post("/owner/reservations/bulk-status/", {
      ids: selectedIds.value,
      status,
    });
    const updatedCount = Number(res?.data?.updated_count || 0);
    const missingCount = Array.isArray(res?.data?.missing_ids) ? res.data.missing_ids.length : 0;
    toast.show(
      missingCount
        ? t("ownerReservations.bulkUpdatedWithMissing", { updated: updatedCount, missing: missingCount })
        : t("ownerReservations.bulkUpdated", { updated: updatedCount }),
      "success"
    );
    await fetchReservations();
  } catch (err) {
    toast.show(parseApiError(err, t("ownerReservations.bulkUpdateFailed")), "error");
  } finally {
    bulkUpdating.value = false;
  }
};

const toggleSelection = (id) => {
  if (selectedIds.value.includes(id)) {
    selectedIds.value = selectedIds.value.filter((item) => item !== id);
    return;
  }
  selectedIds.value = [...selectedIds.value, id];
};

const toggleSelectAllOnPage = () => {
  const pageIds = reservations.value.map((row) => row.id);
  if (!pageIds.length) return;
  if (allSelectedOnPage.value) {
    selectedIds.value = selectedIds.value.filter((id) => !pageIds.includes(id));
    return;
  }
  const merged = new Set([...selectedIds.value, ...pageIds]);
  selectedIds.value = Array.from(merged);
};

const setFilter = async (value) => {
  statusFilter.value = value;
  page.value = 1;
  await fetchReservations();
};

const setReminderFilter = async (value) => {
  reminderFilter.value = value;
  page.value = 1;
  await fetchReservations();
};

const applyFilters = async () => {
  page.value = 1;
  await fetchReservations();
};

const clearFilters = async () => {
  statusFilter.value = "";
  reminderFilter.value = "";
  searchQuery.value = "";
  dateFrom.value = "";
  dateTo.value = "";
  page.value = 1;
  await fetchReservations();
};

const onPageSizeChange = async () => {
  page.value = 1;
  await fetchReservations();
};

const goPrevPage = async () => {
  if (!pagination.value.has_prev) return;
  page.value = Math.max(1, page.value - 1);
  await fetchReservations();
};

const goNextPage = async () => {
  if (!pagination.value.has_next) return;
  page.value += 1;
  await fetchReservations();
};

const fetchTimeline = async (reservationId) => {
  timelineLoading.value = { ...timelineLoading.value, [reservationId]: true };
  try {
    const res = await api.get(`/owner/reservations/${reservationId}/timeline/`, {
      params: { limit: 80 },
    });
    timelineItems.value = {
      ...timelineItems.value,
      [reservationId]: Array.isArray(res.data) ? res.data : [],
    };
  } catch (err) {
    toast.show(parseApiError(err, t("ownerReservations.loadTimelineFailed")), "error");
  } finally {
    const clone = { ...timelineLoading.value };
    delete clone[reservationId];
    timelineLoading.value = clone;
  }
};

const toggleTimeline = async (reservationId) => {
  const isOpen = isTimelineOpen(reservationId);
  if (isOpen) {
    const next = { ...timelineOpen.value };
    delete next[reservationId];
    timelineOpen.value = next;
    return;
  }
  timelineOpen.value = { ...timelineOpen.value, [reservationId]: true };
  if (!timelineItems.value[reservationId]) {
    await fetchTimeline(reservationId);
  }
};

const addTimelineNote = async (reservationId) => {
  const note = String(timelineNote.value[reservationId] || "").trim();
  if (!note) {
    toast.show(t("ownerReservations.writeShortNote"), "info");
    return;
  }
  timelineSubmitting.value = { ...timelineSubmitting.value, [reservationId]: true };
  try {
    const res = await api.post(`/owner/reservations/${reservationId}/timeline/`, { note });
    const existing = timelineFor(reservationId);
    timelineItems.value = {
      ...timelineItems.value,
      [reservationId]: [res.data, ...existing],
    };
    timelineNote.value = { ...timelineNote.value, [reservationId]: "" };
    toast.show(t("ownerReservations.noteAdded"), "success");
  } catch (err) {
    toast.show(parseApiError(err, t("ownerReservations.addTimelineFailed")), "error");
  } finally {
    const clone = { ...timelineSubmitting.value };
    delete clone[reservationId];
    timelineSubmitting.value = clone;
  }
};

const parseFilename = (contentDisposition) => {
  const value = String(contentDisposition || "");
  const match = /filename\*?=(?:UTF-8''|")?([^";]+)/i.exec(value);
  if (!match?.[1]) return "reservations.csv";
  return decodeURIComponent(match[1]).replace(/"/g, "").trim() || "reservations.csv";
};

const exportCsv = async () => {
  exporting.value = true;
  try {
    const response = await api.get("/owner/reservations/export/", {
      params: buildFilterParams(),
      responseType: "blob",
    });
    const contentDisposition = response?.headers?.["content-disposition"];
    const filename = parseFilename(contentDisposition);
    const blob = response?.data instanceof Blob ? response.data : new Blob([response?.data || ""], { type: "text/csv" });
    const objectUrl = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = objectUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(objectUrl);
    toast.show(t("ownerReservations.exportReady"), "success");
  } catch {
    toast.show(t("ownerReservations.exportFailed"), "error");
  } finally {
    exporting.value = false;
  }
};

onMounted(fetchReservations);
</script>
