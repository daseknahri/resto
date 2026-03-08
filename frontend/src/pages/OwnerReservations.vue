<template>
  <section class="space-y-6 ui-safe-bottom pb-28 sm:pb-6">
    <header class="space-y-3 ui-fade-up">
      <p class="ui-kicker">Owner inbox</p>
      <h2 class="ui-page-title ui-display">Reservation Requests</h2>
      <p class="max-w-3xl text-sm text-slate-300">
        Manage table reservation leads from your menu landing. Update status as you contact guests.
      </p>
    </header>

    <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
      <article class="ui-panel p-4">
        <p class="text-xs uppercase tracking-[0.2em] text-slate-400">Total</p>
        <p class="mt-2 text-2xl font-semibold text-white">{{ counts.total }}</p>
      </article>
      <article class="ui-panel p-4">
        <p class="text-xs uppercase tracking-[0.2em] text-slate-400">New</p>
        <p class="mt-2 text-2xl font-semibold text-amber-300">{{ counts.new }}</p>
      </article>
      <article class="ui-panel p-4">
        <p class="text-xs uppercase tracking-[0.2em] text-slate-400">Overdue</p>
        <p class="mt-2 text-2xl font-semibold text-rose-300">{{ counts.overdue_new }}</p>
      </article>
      <article class="ui-panel p-4">
        <p class="text-xs uppercase tracking-[0.2em] text-slate-400">Contacted</p>
        <p class="mt-2 text-2xl font-semibold text-sky-300">{{ counts.contacted }}</p>
      </article>
      <article class="ui-panel p-4">
        <p class="text-xs uppercase tracking-[0.2em] text-slate-400">Confirmed</p>
        <p class="mt-2 text-2xl font-semibold text-emerald-300">{{ counts.won }}</p>
      </article>
    </div>

    <article class="ui-panel p-4 space-y-2">
      <div class="flex items-center justify-between gap-2">
        <p class="text-sm text-slate-300">Follow-up completion</p>
        <span class="text-sm font-semibold text-[var(--color-secondary)]">{{ followUpProgress }}%</span>
      </div>
      <div class="h-2 overflow-hidden rounded-full bg-slate-800">
        <div class="h-full rounded-full bg-[var(--color-secondary)] transition-all duration-300" :style="{ width: `${followUpProgress}%` }"></div>
      </div>
      <p class="text-xs text-slate-500">{{ resolvedCount }} resolved or contacted out of {{ counts.total }} total.</p>
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
        <span class="text-xs text-slate-500">Status filter</span>
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
          {{ reminderFilter === "failed" ? "Exit retry queue" : "Retry queue" }}
        </button>
      </div>

      <div class="grid gap-3 md:grid-cols-[1fr,auto,auto,auto]">
        <input
          v-model.trim="searchQuery"
          class="ui-input"
          placeholder="Search by guest name, phone, email, or note"
          @keyup.enter="applyFilters"
        />
        <input v-model="dateFrom" type="date" class="ui-input" />
        <input v-model="dateTo" type="date" class="ui-input" />
        <div class="flex flex-wrap items-center gap-2">
          <select v-model.number="pageSize" class="ui-input w-24" @change="onPageSizeChange">
            <option :value="10">10</option>
            <option :value="20">20</option>
            <option :value="50">50</option>
          </select>
          <button class="ui-btn-primary px-4 py-2 text-sm" :disabled="loading" @click="applyFilters">
            Apply
          </button>
          <button class="ui-btn-outline px-4 py-2 text-sm" :disabled="loading" @click="clearFilters">
            Clear
          </button>
          <button class="ui-btn-outline px-4 py-2 text-sm" :disabled="exporting" @click="exportCsv">
            {{ exporting ? "Exporting..." : "Export CSV" }}
          </button>
          <button class="ui-btn-outline px-4 py-2 text-sm" :disabled="loading" @click="fetchReservations">
            {{ loading ? "Refreshing..." : "Refresh" }}
          </button>
        </div>
      </div>

      <div class="rounded-xl border border-slate-800 bg-slate-950/40 p-3">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <label class="inline-flex items-center gap-2 text-xs text-slate-300">
            <input type="checkbox" :checked="allSelectedOnPage" @change="toggleSelectAllOnPage" />
            Select page
          </label>
          <p class="text-xs text-slate-400">{{ selectedCount }} selected</p>
        </div>
        <div class="mt-2 flex flex-wrap gap-2">
          <button
            class="ui-btn-outline px-3 py-1.5 text-xs"
            :class="reminderFilter === 'failed' ? 'border-rose-400 text-rose-200' : ''"
            :disabled="!selectedCount || bulkReminderLoading"
            @click="bulkRetryReminders"
          >
            {{ bulkReminderLoading ? "Preparing..." : "Bulk retry reminders" }}
          </button>
          <button class="ui-btn-outline px-3 py-1.5 text-xs" :disabled="!selectedCount || bulkUpdating" @click="bulkUpdateStatus('contacted')">
            Mark contacted
          </button>
          <button class="ui-btn-outline px-3 py-1.5 text-xs" :disabled="!selectedCount || bulkUpdating" @click="bulkUpdateStatus('won')">
            Mark confirmed
          </button>
          <button class="ui-btn-outline px-3 py-1.5 text-xs" :disabled="!selectedCount || bulkUpdating" @click="bulkUpdateStatus('lost')">
            Mark unavailable
          </button>
          <button class="ui-btn-outline px-3 py-1.5 text-xs" :disabled="!selectedCount || bulkUpdating" @click="bulkUpdateStatus('new')">
            Reset new
          </button>
        </div>
        <div v-if="pendingReminderReconciliation.length" class="mt-3 rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-xs space-y-2">
          <p class="text-amber-200">
            {{ pendingReminderReconciliation.length }} reminders waiting reconciliation.
          </p>
          <p class="text-amber-100/80">
            Mark these as opened after you send them, or failed if delivery was not completed.
          </p>
          <div class="flex flex-wrap gap-2">
            <button
              class="rounded-full border border-emerald-500/70 px-3 py-1.5 text-xs font-semibold text-emerald-200 disabled:opacity-60"
              :disabled="bulkReconcileLoading"
              @click="reconcilePendingReminders('opened')"
            >
              {{ bulkReconcileLoading ? "Saving..." : "Mark opened" }}
            </button>
            <button
              class="rounded-full border border-rose-500/70 px-3 py-1.5 text-xs font-semibold text-rose-200 disabled:opacity-60"
              :disabled="bulkReconcileLoading"
              @click="reconcilePendingReminders('failed')"
            >
              {{ bulkReconcileLoading ? "Saving..." : "Mark failed" }}
            </button>
            <button
              class="rounded-full border border-slate-600 px-3 py-1.5 text-xs font-semibold text-slate-300 disabled:opacity-60"
              :disabled="bulkReconcileLoading"
              @click="clearPendingReminderReconciliation"
            >
              Clear pending
            </button>
          </div>
        </div>
      </div>

      <p v-if="error" class="text-sm text-red-300">{{ error }}</p>
      <p v-else-if="loading" class="text-sm text-slate-400">Loading reservations...</p>
      <p v-else-if="!reservations.length" class="text-sm text-slate-400">No reservation requests in this filter.</p>

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
              <span class="text-base font-semibold text-slate-100">{{ reservation.name || `Reservation #${reservation.id}` }}</span>
            </label>
            <span class="rounded-full px-2 py-1 text-[11px] font-semibold" :class="statusClass(reservation.status)">
              {{ reservation.status }}
            </span>
          </div>
          <div v-if="reservation.sla_state && reservation.sla_state !== 'not_applicable'" class="flex flex-wrap items-center gap-2">
            <span class="rounded-full px-2 py-1 text-[11px] font-semibold" :class="slaClass(reservation.sla_state)">
              {{ slaLabel(reservation) }}
            </span>
            <span v-if="reservation.follow_up_due_at" class="text-[11px] text-slate-500">
              Due {{ formatDate(reservation.follow_up_due_at) }}
            </span>
          </div>

          <p class="text-xs text-slate-400">{{ formatDate(reservation.created_at) }}</p>

          <div class="space-y-1 text-sm">
            <p class="text-slate-200">{{ reservation.phone || "-" }}</p>
            <p class="text-slate-400">{{ reservation.email || "-" }}</p>
          </div>

          <p class="rounded-xl border border-slate-800 bg-slate-950/50 p-2 text-xs text-slate-300 whitespace-pre-line">
            {{ reservation.notes || "No customer note" }}
          </p>

          <div class="flex flex-wrap items-center gap-2 text-[11px]">
            <span class="rounded-full border border-slate-700 px-2 py-1 text-slate-300">
              Reminders {{ reservation.reminder_count || 0 }}
            </span>
            <span class="rounded-full border border-slate-700 px-2 py-1 text-slate-400">
              Opened {{ reservation.reminder_opened_count || 0 }}
            </span>
            <span class="rounded-full border border-slate-700 px-2 py-1 text-slate-400">
              Failed {{ reservation.reminder_failed_count || 0 }}
            </span>
            <span
              v-if="reservation.last_reminder_status"
              class="rounded-full px-2 py-1 font-semibold"
              :class="reminderStatusClass(reservation.last_reminder_status)"
            >
              Last {{ reminderStatusLabel(reservation.last_reminder_status) }}
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
              Call
            </a>
            <a
              v-if="whatsappHref(reservation)"
              :href="whatsappHref(reservation)"
              target="_blank"
              rel="noopener noreferrer"
              class="rounded-full border border-slate-700 px-3 py-1.5 text-xs text-slate-100 hover:border-[var(--color-secondary)]"
            >
              Quick chat
            </a>
          </div>

          <div class="flex flex-wrap gap-2">
            <button
              class="rounded-full border border-emerald-500/70 px-3 py-1.5 text-xs font-semibold text-emerald-200 disabled:opacity-60"
              :disabled="isReminderSending(reservation.id) || !canSendReminder(reservation)"
              @click="sendReminder(reservation)"
            >
              {{ isReminderSending(reservation.id) ? "Opening..." : "Reminder" }}
            </button>
            <button
              class="rounded-full bg-sky-500/90 px-3 py-1.5 text-xs font-semibold text-slate-950 disabled:opacity-60"
              :disabled="isUpdating(reservation.id)"
              @click="updateStatus(reservation, 'contacted')"
            >
              Contacted
            </button>
            <button
              class="rounded-full bg-emerald-500/90 px-3 py-1.5 text-xs font-semibold text-slate-950 disabled:opacity-60"
              :disabled="isUpdating(reservation.id)"
              @click="updateStatus(reservation, 'won')"
            >
              Confirmed
            </button>
            <button
              class="rounded-full border border-rose-500/70 px-3 py-1.5 text-xs font-semibold text-rose-200 disabled:opacity-60"
              :disabled="isUpdating(reservation.id)"
              @click="updateStatus(reservation, 'lost')"
            >
              Unavailable
            </button>
            <button
              class="rounded-full border border-slate-700 px-3 py-1.5 text-xs font-semibold text-slate-200 disabled:opacity-60"
              :disabled="isUpdating(reservation.id)"
              @click="updateStatus(reservation, 'new')"
            >
              Reset New
            </button>
            <button
              class="rounded-full border border-slate-700 px-3 py-1.5 text-xs font-semibold text-slate-200 disabled:opacity-60"
              :disabled="isTimelineLoading(reservation.id)"
              @click="toggleTimeline(reservation.id)"
            >
              {{ isTimelineOpen(reservation.id) ? "Hide timeline" : "Timeline" }}
            </button>
          </div>

          <div v-if="isTimelineOpen(reservation.id)" class="rounded-xl border border-slate-800 bg-slate-950/40 p-3 space-y-3">
            <p class="text-xs uppercase tracking-[0.18em] text-slate-400">Follow-up timeline</p>
            <p v-if="isTimelineLoading(reservation.id)" class="text-xs text-slate-500">Loading timeline...</p>
            <ul v-else class="space-y-2 text-xs">
              <li
                v-for="entry in timelineFor(reservation.id)"
                :key="entry.id"
                class="rounded-lg border border-slate-800 bg-slate-900/70 p-2"
              >
                <div class="flex items-center justify-between gap-2">
                  <span class="font-semibold text-slate-200">{{ entry.action }}</span>
                  <span class="text-slate-500">{{ formatDate(entry.created_at) }}</span>
                </div>
                <p v-if="entry.note" class="mt-1 whitespace-pre-line text-slate-300">{{ entry.note }}</p>
                <p v-if="entry.previous_status || entry.new_status" class="mt-1 text-slate-400">
                  {{ entry.previous_status || "-" }} -> {{ entry.new_status || "-" }}
                </p>
                <p v-if="entry.actor_username" class="mt-1 text-slate-500">by {{ entry.actor_username }}</p>
              </li>
              <li v-if="!timelineFor(reservation.id).length" class="text-slate-500">No timeline entries yet.</li>
            </ul>

            <div class="flex flex-wrap items-start gap-2">
              <textarea
                v-model.trim="timelineNote[reservation.id]"
                rows="2"
                class="ui-textarea min-w-[220px] flex-1"
                placeholder="Add follow-up note..."
              ></textarea>
              <button
                class="ui-btn-outline px-3 py-2 text-xs disabled:opacity-60"
                :disabled="isTimelineSubmitting(reservation.id)"
                @click="addTimelineNote(reservation.id)"
              >
                {{ isTimelineSubmitting(reservation.id) ? "Saving..." : "Add note" }}
              </button>
            </div>
          </div>
        </article>
      </div>

      <div class="flex flex-wrap items-center justify-between gap-2 border-t border-slate-800 pt-3">
        <p class="text-xs text-slate-400">
          Page {{ pagination.page }} / {{ pagination.pages }} - {{ pagination.total }} total records
        </p>
        <div class="flex items-center gap-2">
          <button class="ui-btn-outline px-3 py-1.5 text-xs" :disabled="!pagination.has_prev || loading" @click="goPrevPage">
            Previous
          </button>
          <button class="ui-btn-outline px-3 py-1.5 text-xs" :disabled="!pagination.has_next || loading" @click="goNextPage">
            Next
          </button>
        </div>
      </div>
    </section>

    <div
      v-if="selectedCount"
      class="fixed bottom-4 left-3 right-3 z-20 rounded-2xl border border-slate-700/80 bg-slate-950/92 p-3 shadow-xl shadow-black/40 backdrop-blur lg:hidden"
    >
      <div class="space-y-2">
        <p class="text-xs text-slate-300">{{ selectedCount }} selected</p>
        <div class="grid grid-cols-3 gap-2">
          <button class="ui-btn-outline justify-center text-xs" :disabled="bulkUpdating" @click="bulkUpdateStatus('contacted')">Contacted</button>
          <button class="ui-btn-outline justify-center text-xs" :disabled="bulkUpdating" @click="bulkUpdateStatus('won')">Confirmed</button>
          <button
            class="ui-btn-outline justify-center text-xs"
            :disabled="bulkReminderLoading"
            :class="reminderFilter === 'failed' ? 'border-rose-400 text-rose-200' : ''"
            @click="bulkRetryReminders"
          >
            Retry
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import api from "../lib/api";
import { useToastStore } from "../stores/toast";

const toast = useToastStore();
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

const statusOptions = [
  { value: "", label: "All" },
  { value: "new", label: "New" },
  { value: "contacted", label: "Contacted" },
  { value: "won", label: "Confirmed" },
  { value: "lost", label: "Unavailable" },
];

const reminderOptions = [
  { value: "", label: "All reminders" },
  { value: "failed", label: "Failed" },
  { value: "sent", label: "Sent" },
  { value: "opened", label: "Opened" },
  { value: "none", label: "No reminders" },
];

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

const formatDate = (value) => {
  if (!value) return "-";
  try {
    return new Date(value).toLocaleString();
  } catch (e) {
    return String(value);
  }
};

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
  const name = String(reservation?.name || "there").trim();
  const text = encodeURIComponent(`Hi ${name}, this is your table reservation follow-up.`);
  return `https://wa.me/${phone}?text=${text}`;
};

const statusClass = (status) => {
  if (status === "new") return "bg-amber-500/20 text-amber-200";
  if (status === "contacted") return "bg-sky-500/20 text-sky-200";
  if (status === "won") return "bg-emerald-500/20 text-emerald-200";
  if (status === "lost") return "bg-rose-500/20 text-rose-200";
  return "bg-slate-700 text-slate-200";
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
    return minutes > 0 ? `Overdue ${minutes}m` : "Overdue";
  }
  if (state === "due_soon") return "Due soon";
  if (state === "on_track") return "On track";
  if (state === "resolved") return "Resolved";
  return "No SLA";
};

const reminderStatusClass = (status) => {
  if (status === "opened") return "bg-emerald-500/20 text-emerald-200";
  if (status === "failed") return "bg-rose-500/20 text-rose-200";
  if (status === "sent") return "bg-amber-500/20 text-amber-200";
  return "bg-slate-700/60 text-slate-300";
};

const reminderStatusLabel = (status) => {
  if (status === "opened") return "Opened";
  if (status === "failed") return "Failed";
  if (status === "sent") return "Sent";
  return "Unknown";
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
    const message = parseApiError(err, "Unable to load reservations");
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
    toast.show("Reservation updated", "success");
    await fetchReservations();
  } catch (err) {
    toast.show(parseApiError(err, "Unable to update reservation"), "error");
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
        error: opened ? "" : "Popup blocked by browser",
      });
    }
    if (popup) {
      toast.show("Reminder opened in WhatsApp", "success");
    } else {
      if (link && navigator?.clipboard?.writeText) {
        try {
          await navigator.clipboard.writeText(link);
        } catch (e) {
          // Ignore clipboard errors and still show fallback guidance.
        }
      }
      toast.show("Reminder prepared, but popup was blocked", "error");
    }
    await fetchReservations();
    if (isTimelineOpen(id)) {
      await fetchTimeline(id);
    }
  } catch (err) {
    toast.show(parseApiError(err, "Unable to prepare reminder"), "error");
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
      } catch (e) {
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
                error: firstPopup ? "" : "Popup blocked by browser",
              },
            ],
          });
          if (Number(res?.data?.updated_count || 0) > 0) {
            pendingReminderReconciliation.value = pendingReminderReconciliation.value.slice(1);
          }
        } catch (e) {
          // Best effort tracking; do not fail whole operation.
        }
      }
    }

    if (!preparedCount) {
      toast.show("No reminders prepared for current selection", "info");
    } else if (firstPopup) {
      toast.show(`Prepared ${preparedCount} reminders. First chat opened.`, "success");
    } else {
      toast.show(`Prepared ${preparedCount} reminders. Links copied for manual send.`, "info");
    }

    if (skippedNoPhone || skippedUnavailable || skippedNotFailed) {
      toast.show(
        `Skipped ${skippedNoPhone} no-phone, ${skippedUnavailable} unavailable, ${skippedNotFailed} not-failed.`,
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
    toast.show(parseApiError(err, "Unable to prepare bulk reminders"), "error");
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
      error: status === "failed" ? "Owner marked as not delivered" : "",
    }));
    const res = await api.post("/owner/reservations/bulk-reminder-result/", { items });
    const updatedCount = Number(res?.data?.updated_count || 0);
    const missingCount = Number(res?.data?.missing_count || 0);
    pendingReminderReconciliation.value = [];
    toast.show(
      missingCount
        ? `Updated ${updatedCount} reminders (${missingCount} missing).`
        : `Updated ${updatedCount} reminders.`,
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
    toast.show(parseApiError(err, "Unable to reconcile prepared reminders"), "error");
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
        ? `Updated ${updatedCount}. ${missingCount} no longer available.`
        : `Updated ${updatedCount} reservations.`,
      "success"
    );
    await fetchReservations();
  } catch (err) {
    toast.show(parseApiError(err, "Unable to update selected reservations"), "error");
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
    toast.show(parseApiError(err, "Unable to load timeline"), "error");
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
    toast.show("Write a short note first", "info");
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
    toast.show("Timeline note added", "success");
  } catch (err) {
    toast.show(parseApiError(err, "Unable to add timeline note"), "error");
  } finally {
    const clone = { ...timelineSubmitting.value };
    delete clone[reservationId];
    timelineSubmitting.value = clone;
  }
};

const parseFilename = (contentDisposition) => {
  const value = String(contentDisposition || "");
  const match = /filename\*?=(?:UTF-8''|")?([^\";]+)/i.exec(value);
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
    toast.show("Reservation export ready", "success");
  } catch (err) {
    toast.show("Unable to export reservations", "error");
  } finally {
    exporting.value = false;
  }
};

onMounted(fetchReservations);
</script>
