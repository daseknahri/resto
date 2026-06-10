<template>
  <div class="space-y-4 pb-6 max-w-2xl">
    <!-- Header -->
    <header class="ui-hero-ribbon ui-reveal px-4 py-3.5 md:px-5 md:py-4">
      <div class="flex items-start justify-between gap-3">
        <div class="min-w-0">
          <p class="ui-kicker">{{ t("ownerStaff.kicker") }}</p>
          <h1 class="ui-display text-xl font-semibold leading-tight tracking-tight text-white sm:text-2xl">{{ t("ownerStaff.title") }}</h1>
          <p class="ui-subtle mt-0.5">{{ t("ownerStaff.subtitle") }}</p>
        </div>
        <svg v-if="updatingStaff" class="mt-1 h-4 w-4 shrink-0 animate-spin text-slate-500" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true">
          <path d="M13.5 8a5.5 5.5 0 1 1-1.1-3.3M13.5 2v3.5H10"/>
        </svg>
        <span v-if="updatingStaff" class="sr-only">{{ t("ownerStaff.updating") }}</span>
      </div>
    </header>

    <!-- Create form -->
    <section class="ui-panel ui-reveal p-4 space-y-4" style="--ui-delay:40ms">
      <div>
        <p class="ui-kicker">{{ t("ownerStaff.inviteSection") }}</p>
      </div>
      <div class="grid gap-3 sm:grid-cols-2">
        <input
          v-model="form.name"
          type="text"
          autocomplete="off"
          :placeholder="t('ownerStaff.namePlaceholder')"
          :aria-label="t('ownerStaff.namePlaceholder')"
          class="ui-input"
          :disabled="creating"
          aria-required="true"
          @keyup.enter="createStaff"
        />
        <input
          v-model="form.email"
          type="email"
          :placeholder="t('ownerStaff.emailPlaceholder')"
          :aria-label="t('ownerStaff.emailPlaceholder')"
          autocomplete="email"
          spellcheck="false"
          class="ui-input"
          :disabled="creating"
          aria-required="true"
          @keyup.enter="createStaff"
        />
      </div>
      <div v-if="formError" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
        <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
        <p class="flex-1 text-sm text-red-300">{{ formError }}</p>
      </div>
      <button
        class="ui-btn-primary ui-touch-target inline-flex items-center justify-center gap-2"
        :disabled="creating || !form.name.trim() || !form.email.trim()"
        :aria-busy="creating"
        @click="createStaff"
      >
        <svg v-if="creating" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-4 w-4 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
        {{ creating ? t("ownerStaff.inviting") : t("ownerStaff.inviteBtn") }}
      </button>
    </section>

    <!-- Created credentials (shown once) -->
    <div
      v-if="newCredentials"
      role="alert"
      class="ui-reveal rounded-2xl border border-emerald-500/30 bg-emerald-500/8 p-4 space-y-3"
    >
      <p class="text-sm font-semibold tracking-tight text-emerald-300">{{ t("ownerStaff.credentialsTitle") }}</p>
      <p class="text-xs text-slate-400">{{ t("ownerStaff.credentialsHint") }}</p>
      <div class="rounded-xl border border-slate-700/50 bg-slate-900/60 p-4 space-y-2.5 font-mono text-sm">
        <div class="flex items-center justify-between gap-3">
          <span class="shrink-0 text-xs font-medium uppercase tracking-wider text-slate-500">{{ t("common.email") }}</span>
          <span class="min-w-0 truncate text-slate-100">{{ newCredentials.email }}</span>
        </div>
        <div class="border-t border-slate-700/40 pt-2.5 flex items-center justify-between gap-3">
          <span class="shrink-0 text-xs font-medium uppercase tracking-wider text-slate-500">{{ t("ownerStaff.credentialsPasswordLabel") }}</span>
          <span class="text-emerald-300 font-bold tracking-wider tabular-nums">{{ newCredentials.temp_password }}</span>
        </div>
      </div>
      <div class="flex flex-wrap gap-2">
        <button
          class="ui-btn-primary px-4 py-2 text-xs font-semibold ui-press"
          @click="copyCredentials"
        >
          {{ copied ? t("ownerStaff.credentialsCopied") : t("ownerStaff.credentialsCopy") }}
        </button>
        <button
          class="ui-btn-outline px-4 py-2 text-xs font-semibold ui-press"
          @click="newCredentials = null; copied = false"
        >
          {{ t("ownerStaff.credentialsDone") }}
        </button>
      </div>
    </div>

    <!-- Staff list -->
    <div class="space-y-3">
      <div class="flex items-center justify-between gap-2 min-w-0 px-0.5">
        <p class="text-sm font-semibold tracking-tight text-slate-300 truncate">{{ t("ownerStaff.teamSection") }}</p>
        <div
          role="group"
          :aria-label="t('ownerStaff.periodLabel')"
          class="flex shrink-0 items-center gap-0.5 rounded-xl border border-slate-700/50 bg-slate-800/40 p-0.5"
        >
          <button
            v-for="opt in periodOptions"
            :key="opt.days"
            class="rounded-lg px-2.5 py-1 text-[11px] font-semibold transition-colors ui-press disabled:opacity-50"
            :class="selectedDays === opt.days ? 'bg-slate-700 text-white' : 'text-slate-400 hover:text-slate-200'"
            :aria-pressed="selectedDays === opt.days"
            :disabled="loadingStaff"
            @click="changePeriod(opt.days)"
          >{{ t(opt.labelKey) }}</button>
        </div>
      </div>

      <div v-if="loadingStaff" class="space-y-2" aria-busy="true" role="status" :aria-label="t('ownerStaff.loading')">
        <div v-for="i in 3" :key="i" class="ui-skeleton h-[4.5rem]" />
      </div>

      <div
        v-else-if="staffError"
        role="alert"
        class="flex items-start gap-3 rounded-2xl border border-red-500/30 bg-red-500/8 px-4 py-3"
      >
        <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor">
          <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm-.75-9.25a.75.75 0 011.5 0v3.5a.75.75 0 01-1.5 0v-3.5zm.75 6a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd" />
        </svg>
        <p class="flex-1 text-sm text-red-300">{{ t("ownerStaff.fetchError") }}</p>
        <button
          class="shrink-0 rounded-lg border border-red-500/40 px-3 py-1 text-xs font-semibold text-red-300 transition hover:bg-red-500/10 ui-touch-target ui-press"
          @click="fetchStaff"
        >{{ t("common.retry") }}</button>
      </div>

      <div
        v-else-if="staffList.length === 0"
        class="ui-empty-state flex flex-col items-center text-center p-8 space-y-3"
      >
        <div class="flex h-12 w-12 items-center justify-center rounded-2xl border border-slate-700/80 bg-slate-950/70 text-slate-400">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="h-6 w-6" aria-hidden="true">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>
          </svg>
        </div>
        <div class="space-y-1.5">
          <p class="text-sm font-semibold text-slate-200">{{ t("ownerStaff.noStaff") }}</p>
          <p class="text-xs text-slate-500">{{ t("ownerStaff.noStaffHint") }}</p>
        </div>
      </div>

      <div
        v-for="(member, index) in staffList"
        :key="member.id"
        class="ui-panel ui-surface-lift ui-reveal overflow-hidden"
        :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
      >
        <!-- Staff card header -->
        <div class="flex items-center justify-between gap-3 px-4 py-3.5">
          <div class="min-w-0 space-y-0.5">
            <p class="text-sm font-semibold tracking-tight text-slate-100 truncate">{{ member.name }}</p>
            <p class="text-xs text-slate-500 truncate">{{ member.email }}</p>
            <p class="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px] text-slate-400">
              <span class="tabular-nums">{{ t('ownerStaff.statOrders', { n: member.stats?.orders_handled || 0 }) }}</span>
              <span class="text-slate-600" aria-hidden="true">·</span>
              <span class="font-semibold text-emerald-400/90 tabular-nums">{{ fmtMoney(member.stats?.revenue) }}</span>
              <span class="text-slate-600">{{ t('ownerStaff.statsPeriod', { days: statsDays }) }}</span>
            </p>
          </div>
          <button
            class="shrink-0 inline-flex items-center gap-1.5 rounded-xl border border-slate-700/60 bg-slate-800/60 px-3 py-1.5 text-xs font-medium text-slate-400 hover:border-slate-600 hover:text-slate-200 transition-colors ui-press ui-touch-target"
            :aria-expanded="expandedIds.has(member.id)"
            :aria-controls="'staff-panel-' + member.id"
            @click="toggleExpanded(member.id)"
          >
            {{ t("ownerStaff.manage") }}
            <svg
              class="h-3 w-3 transition-transform duration-200"
              :class="{ 'rotate-180': expandedIds.has(member.id) }"
              viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"
              aria-hidden="true"
            >
              <path d="M2 4l4 4 4-4"/>
            </svg>
          </button>
        </div>

        <!-- Permissions panel (expandable) -->
        <Transition name="staff-expand">
          <div
            v-if="expandedIds.has(member.id)"
            :id="'staff-panel-' + member.id"
            class="border-t border-slate-700/40 bg-slate-900/40 px-4 py-4 space-y-4"
          >
            <!-- Work stats -->
            <div class="space-y-2">
              <p class="ui-kicker">{{ t('ownerStaff.statsTitle', { days: statsDays }) }}</p>
              <div class="grid grid-cols-3 gap-px overflow-hidden rounded-xl border border-slate-700/50 bg-slate-700/30">
                <div class="bg-slate-900/60 p-3 text-center">
                  <p class="text-lg font-bold text-white tabular-nums">{{ member.stats?.orders_handled || 0 }}</p>
                  <p class="ui-stat-label mt-0.5">{{ t('ownerStaff.statOrdersLabel') }}</p>
                </div>
                <div class="bg-slate-900/60 p-3 text-center">
                  <p class="text-base font-bold text-emerald-300 tabular-nums leading-tight">{{ fmtMoney(member.stats?.revenue) }}</p>
                  <p class="ui-stat-label mt-0.5">{{ t('ownerStaff.statRevenueLabel') }}</p>
                </div>
                <div class="bg-slate-900/60 p-3 text-center">
                  <p
                    class="text-sm font-semibold leading-snug"
                    :class="member.stats?.last_active ? 'text-sky-300' : 'text-slate-500 italic'"
                  >{{ member.stats?.last_active ? fmtRelative(member.stats.last_active) : t('ownerStaff.neverActive') }}</p>
                  <p class="ui-stat-label mt-0.5">{{ t('ownerStaff.statLastActiveLabel') }}</p>
                </div>
              </div>
            </div>

            <!-- Permission toggles -->
            <div class="space-y-1">
              <p class="ui-kicker mb-2">{{ t("ownerStaff.permissionsTitle") }}</p>
              <div class="divide-y divide-slate-700/30 rounded-xl border border-slate-700/40 bg-slate-900/40 overflow-hidden">
                <div
                  v-for="perm in permDefs"
                  :key="perm.key"
                  class="flex items-center justify-between gap-4 px-3.5 py-3"
                >
                  <div class="min-w-0">
                    <p class="text-sm font-medium text-slate-200">{{ t(perm.labelKey) }}</p>
                    <p class="text-xs text-slate-500 mt-0.5">{{ t(perm.descKey) }}</p>
                  </div>
                  <button
                    class="staff-toggle shrink-0"
                    :class="member.permissions[perm.key] ? 'staff-toggle-on' : 'staff-toggle-off'"
                    :disabled="savingId === member.id"
                    :aria-label="t(perm.labelKey)"
                    role="switch"
                    :aria-checked="member.permissions[perm.key]"
                    @click="togglePerm(member, perm.key)"
                  >
                    <span class="staff-toggle-thumb" />
                  </button>
                </div>
              </div>
            </div>

            <!-- Saving / save-error indicators -->
            <p v-if="savingId === member.id" class="text-xs text-slate-500 italic">
              {{ t("ownerStaff.saving") }}
            </p>
            <div
              v-if="saveError[member.id]"
              role="alert"
              class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5"
            >
              <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor">
                <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/>
              </svg>
              <p class="flex-1 text-xs text-red-300">{{ saveError[member.id] }}</p>
            </div>

            <!-- Remove -->
            <div class="flex items-center justify-end gap-2 border-t border-slate-800/60 pt-3">
              <button
                class="rounded-xl border border-red-500/30 bg-red-500/8 px-4 py-1.5 text-xs font-medium text-red-400 hover:border-red-500/60 hover:text-red-300 transition-colors disabled:opacity-50 ui-touch-target ui-press"
                :disabled="removingId === member.id"
                @click="removeStaff(member)"
              >{{ removingId === member.id ? t("ownerStaff.removing") : t("ownerStaff.remove") }}</button>
            </div>
          </div>
        </Transition>
      </div>
    </div>

    <!-- Permissions legend -->
    <div class="rounded-xl border border-slate-800/60 bg-slate-900/30 p-4 space-y-1.5">
      <p class="ui-kicker">{{ t("ownerStaff.legendTitle") }}</p>
      <p class="text-xs text-slate-500 leading-relaxed">{{ t("ownerStaff.legendOwner") }}</p>
      <p class="text-xs text-slate-500 leading-relaxed">{{ t("ownerStaff.legendStaff") }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onActivated, onMounted, reactive } from "vue";
import { useConfirmModal } from "../composables/useConfirmModal";
import { useI18n } from "../composables/useI18n";
import api from "../lib/api";
import { useToastStore } from "../stores/toast";
import { isFresh, readCache, writeCache } from "../lib/staleCache";

const { t, currentLocale } = useI18n();
const toast = useToastStore();

// ── Permission definitions ─────────────────────────────────────────────────────
const permDefs = [
  {
    key: "manage_orders",
    labelKey: "ownerStaff.permManageOrders",
    descKey: "ownerStaff.permManageOrdersDesc",
  },
  {
    key: "view_revenue",
    labelKey: "ownerStaff.permViewRevenue",
    descKey: "ownerStaff.permViewRevenueDesc",
  },
  {
    key: "edit_menu",
    labelKey: "ownerStaff.permEditMenu",
    descKey: "ownerStaff.permEditMenuDesc",
  },
];

const STAFF_CACHE_KEY = "owner.staff";
const STAFF_TTL_MS = 5 * 60 * 1000; // 5 min

// ── State ──────────────────────────────────────────────────────────────────────
const staffList = ref([]);
const loadingStaff = ref(false);
const updatingStaff = ref(false);
const staffError = ref(false);
const expandedIds = ref(new Set());
const savingId = ref(null);
const saveError = reactive({});
const removingId = ref(null);
const { confirm } = useConfirmModal();

const form = ref({ name: "", email: "" });
const formError = ref("");
const creating = ref(false);
const newCredentials = ref(null);
const copied = ref(false);

// ── Per-staff work stats ─────────────────────────────────────────────────────
const statsDays = ref(7);
const statsCurrency = ref("MAD");
const selectedDays = ref(7);
const periodOptions = [
  { days: 1, labelKey: "ownerStaff.periodToday" },
  { days: 7, labelKey: "ownerStaff.period7d" },
  { days: 30, labelKey: "ownerStaff.period30d" },
];
const changePeriod = (days) => {
  if (days === selectedDays.value) return;
  selectedDays.value = days;
  fetchStaff(true);
};

const fmtMoney = (v) => {
  const n = parseFloat(v || 0);
  try {
    return new Intl.NumberFormat(currentLocale.value, {
      style: "currency",
      currency: statsCurrency.value || "MAD",
      maximumFractionDigits: 2,
    }).format(n);
  } catch {
    return n.toFixed(2);
  }
};

const fmtRelative = (iso) => {
  if (!iso) return "—";
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return t("ownerStaff.justNow");
  if (mins < 60) return t("ownerStaff.minsAgo", { n: mins });
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return t("ownerStaff.hrsAgo", { n: hrs });
  return t("ownerStaff.daysAgo", { n: Math.round(hrs / 24) });
};

// ── Staff list ─────────────────────────────────────────────────────────────────
const mapStaff = (s) => ({
  ...s,
  permissions: s.permissions ?? { manage_orders: true, view_revenue: false, edit_menu: false },
});

const fetchStaff = async (force = false) => {
  // Cache only the default 7-day view; other periods always fetch fresh.
  const useCache = !force && selectedDays.value === 7;
  const cached = useCache ? readCache(STAFF_CACHE_KEY) : null;
  if (cached) {
    staffList.value = cached.map(mapStaff);
    if (isFresh(STAFF_CACHE_KEY, STAFF_TTL_MS)) return;
    updatingStaff.value = true;
  } else {
    loadingStaff.value = true;
  }
  staffError.value = false;
  try {
    const { data } = await api.get("/owner/staff/", { params: { stats_days: selectedDays.value } });
    const list = (data.results ?? []).map(mapStaff);
    staffList.value = list;
    if (typeof data.stats_days === "number") statsDays.value = data.stats_days;
    if (data.currency) statsCurrency.value = data.currency;
    if (selectedDays.value === 7) writeCache(STAFF_CACHE_KEY, data.results ?? []);
  } catch {
    if (!cached) staffError.value = true;
  } finally {
    loadingStaff.value = false;
    updatingStaff.value = false;
  }
};

onMounted(fetchStaff);

// Kept alive — silently revalidate on revisit (cached view shows instantly).
let _activatedOnce = false;
onActivated(() => {
  if (!_activatedOnce) { _activatedOnce = true; return; }
  fetchStaff();
});

// ── Expand / collapse ──────────────────────────────────────────────────────────
const toggleExpanded = (id) => {
  const next = new Set(expandedIds.value);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  expandedIds.value = next;
};

// ── Toggle permission ─────────────────────────────────────────────────────────
const togglePerm = async (member, permKey) => {
  if (savingId.value === member.id) return;
  const newVal = !member.permissions[permKey];
  // Optimistic update
  member.permissions[permKey] = newVal;
  savingId.value = member.id;
  delete saveError[member.id];
  try {
    await api.patch(`/owner/staff/${member.id}/`, {
      permissions: { [permKey]: newVal },
    });
    writeCache(STAFF_CACHE_KEY, staffList.value);
  } catch {
    // Roll back on error
    member.permissions[permKey] = !newVal;
    saveError[member.id] = t("ownerStaff.savePermFailed");
    toast.show(t("ownerStaff.savePermFailed"), "error");
  } finally {
    savingId.value = null;
  }
};

// ── Create staff ───────────────────────────────────────────────────────────────
const createStaff = async () => {
  formError.value = "";
  const name = form.value.name.trim();
  const email = form.value.email.trim().toLowerCase();

  if (!name || name.length < 2) {
    formError.value = t("ownerStaff.errorName");
    return;
  }
  if (!email || !email.includes("@")) {
    formError.value = t("ownerStaff.errorEmail");
    return;
  }

  creating.value = true;
  try {
    const { data } = await api.post("/owner/staff/", { name, email });
    newCredentials.value = data;
    const newMember = {
      id: data.id,
      name: data.name,
      email: data.email,
      username: data.username,
      permissions: { manage_orders: true, view_revenue: false, edit_menu: false },
    };
    staffList.value = [...staffList.value, newMember];
    writeCache(STAFF_CACHE_KEY, staffList.value);
    form.value = { name: "", email: "" };
  } catch (err) {
    const code = err?.response?.data?.code;
    if (code === "email_taken") {
      formError.value = t("ownerStaff.errorEmailTaken");
    } else if (code === "email_required" || code === "email_invalid") {
      formError.value = t("ownerStaff.errorEmail");
    } else if (code === "name_required") {
      formError.value = t("ownerStaff.errorName");
    } else if (code === "staff_limit_reached") {
      formError.value = t("ownerStaff.errorStaffLimit", { limit: err?.response?.data?.limit ?? "" });
    } else {
      formError.value = t("ownerStaff.errorGeneric");
    }
  } finally {
    creating.value = false;
  }
};

// ── Remove staff ───────────────────────────────────────────────────────────────
const removeStaff = async (member) => {
  const ok = await confirm({
    title: t("ownerStaff.confirmRemove"),
    body: t("confirmModal.defaultBody"),
    confirmLabel: t("ownerStaff.remove"),
  });
  if (!ok) return;
  removingId.value = member.id;
  try {
    await api.delete(`/owner/staff/${member.id}/`);
    staffList.value = staffList.value.filter((s) => s.id !== member.id);
    writeCache(STAFF_CACHE_KEY, staffList.value);
    const next = new Set(expandedIds.value);
    next.delete(member.id);
    expandedIds.value = next;
  } catch {
    toast.show(t("ownerStaff.removeFailed"), "error");
  } finally {
    removingId.value = null;
  }
};

// ── Copy credentials ───────────────────────────────────────────────────────────
const copyCredentials = async () => {
  if (!newCredentials.value) return;
  const text = `Email: ${newCredentials.value.email}\nPassword: ${newCredentials.value.temp_password}`;
  try {
    await navigator.clipboard.writeText(text);
    copied.value = true;
    setTimeout(() => (copied.value = false), 3000);
  } catch {
    toast.show(t('ownerStaff.copyFailed'), 'error');
  }
};
</script>

<style scoped>
/* ── Toggle switch ──────────────────────────────────────────────────────────── */
.staff-toggle {
  position: relative;
  width: 2.5rem;
  /* 44 px interactive hit area (WCAG 2.5.5) */
  min-height: 2.75rem;
  border: none;
  background: transparent;
  cursor: pointer;
  transition: opacity 0.2s;
  flex-shrink: 0;
}
.staff-toggle:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
/* Visual track rendered as a pseudo-element, centred in the 44 px button */
.staff-toggle::before {
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  top: 50%;
  transform: translateY(-50%);
  height: 1.375rem;
  border-radius: 9999px;
  transition: background-color 0.2s;
}
.staff-toggle-on::before  { background: #10b981; } /* emerald — matches the on-state used across the app */
.staff-toggle-off::before { background: #334155; }

.staff-toggle-thumb {
  position: absolute;
  /* Vertically centred relative to the 44 px button, then offset by the same
     margin as before (0.1875 rem from the track edge = track-top offset).
     track-top = 50% - 0.6875rem; thumb = track-top + 0.1875rem */
  top: calc(50% - 0.5rem); /* centres 1rem thumb in track */
  width: 1rem;
  height: 1rem;
  border-radius: 50%;
  background: white;
  transition: left 0.2s;
  pointer-events: none;
}
.staff-toggle-on  .staff-toggle-thumb { left: calc(100% - 1.1875rem); }
.staff-toggle-off .staff-toggle-thumb { left: 0.1875rem; }

/* ── Expand transition ─────────────────────────────────────────────────────── */
.staff-expand-enter-active,
.staff-expand-leave-active {
  transition: max-height 0.22s ease, opacity 0.18s ease;
  max-height: 600px;
  overflow: hidden;
}
.staff-expand-enter-from,
.staff-expand-leave-to {
  max-height: 0;
  opacity: 0;
}
@media (prefers-reduced-motion: reduce) {
  .staff-expand-enter-active,
  .staff-expand-leave-active {
    transition: none;
  }
}
/* ── Toggle switch — reduced-motion: disable thumb slide ────────────────────── */
@media (prefers-reduced-motion: reduce) {
  .staff-toggle,
  .staff-toggle-thumb {
    transition: none;
  }
}
</style>
