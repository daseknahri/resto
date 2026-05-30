<template>
  <div class="space-y-6 max-w-2xl">
    <!-- Header -->
    <div class="flex items-start justify-between gap-3">
      <div>
        <p class="ui-kicker">{{ t("ownerStaff.kicker") }}</p>
        <h2 class="text-xl font-bold text-white">{{ t("ownerStaff.title") }}</h2>
        <p class="mt-1 text-sm text-slate-400">{{ t("ownerStaff.subtitle") }}</p>
      </div>
      <svg v-if="updatingStaff" class="mt-1 h-4 w-4 shrink-0 animate-spin text-slate-500" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
        <path d="M13.5 8a5.5 5.5 0 1 1-1.1-3.3M13.5 2v3.5H10"/>
      </svg>
    </div>

    <!-- Create form -->
    <div class="rounded-2xl border border-slate-700/50 bg-slate-800/40 p-5 space-y-4">
      <p class="text-sm font-semibold text-slate-200">{{ t("ownerStaff.inviteSection") }}</p>
      <div class="grid gap-3 sm:grid-cols-2">
        <input
          v-model="form.name"
          type="text"
          :placeholder="t('ownerStaff.namePlaceholder')"
          class="ui-input"
          :disabled="creating"
          @keyup.enter="createStaff"
        />
        <input
          v-model="form.email"
          type="email"
          :placeholder="t('ownerStaff.emailPlaceholder')"
          class="ui-input"
          :disabled="creating"
          @keyup.enter="createStaff"
        />
      </div>
      <div v-if="formError" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5">
        <svg viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
        <p class="flex-1 text-sm text-red-300">{{ formError }}</p>
      </div>
      <button
        class="ui-btn-primary"
        :disabled="creating || !form.name.trim() || !form.email.trim()"
        @click="createStaff"
      >
        {{ creating ? t("ownerStaff.inviting") : t("ownerStaff.inviteBtn") }}
      </button>
    </div>

    <!-- Created credentials (shown once) -->
    <div
      v-if="newCredentials"
      class="rounded-2xl border border-emerald-500/30 bg-emerald-500/8 p-5 space-y-3"
    >
      <p class="text-sm font-semibold text-emerald-300">{{ t("ownerStaff.credentialsTitle") }}</p>
      <p class="text-xs text-slate-400">{{ t("ownerStaff.credentialsHint") }}</p>
      <div class="rounded-xl border border-slate-700/50 bg-slate-900/60 p-4 space-y-2 font-mono text-sm">
        <div class="flex items-center justify-between gap-3">
          <span class="text-slate-400">{{ t("common.email") }}:</span>
          <span class="text-slate-100 truncate">{{ newCredentials.email }}</span>
        </div>
        <div class="flex items-center justify-between gap-3">
          <span class="text-slate-400">{{ t("ownerStaff.credentialsPasswordLabel") }}:</span>
          <span class="text-emerald-300 font-bold tracking-wider">{{ newCredentials.temp_password }}</span>
        </div>
      </div>
      <div class="flex gap-2">
        <button
          class="rounded-xl border border-slate-600 bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-300 hover:border-slate-500 transition-colors"
          @click="copyCredentials"
        >
          {{ copied ? t("ownerStaff.credentialsCopied") : t("ownerStaff.credentialsCopy") }}
        </button>
        <button
          class="rounded-xl border border-slate-700 bg-slate-800/60 px-4 py-2 text-xs font-semibold text-slate-400 hover:border-slate-600 transition-colors"
          @click="newCredentials = null; copied = false"
        >
          {{ t("ownerStaff.credentialsDone") }}
        </button>
      </div>
    </div>

    <!-- Staff list -->
    <div class="space-y-3">
      <p class="text-sm font-semibold text-slate-300">{{ t("ownerStaff.teamSection") }}</p>

      <div v-if="loadingStaff" class="space-y-2">
        <div v-for="i in 2" :key="i" class="h-14 animate-pulse rounded-2xl border border-slate-700/40 bg-slate-800/40" />
      </div>

      <div
        v-else-if="staffError"
        class="flex items-start gap-3 rounded-2xl border border-red-500/30 bg-red-500/8 px-4 py-3"
      >
        <svg viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor">
          <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm-.75-9.25a.75.75 0 011.5 0v3.5a.75.75 0 01-1.5 0v-3.5zm.75 6a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd" />
        </svg>
        <p class="flex-1 text-sm text-red-300">{{ t("ownerStaff.fetchError") }}</p>
        <button
          class="shrink-0 rounded-lg border border-red-500/40 px-3 py-1 text-xs font-semibold text-red-300 transition hover:bg-red-500/10"
          @click="fetchStaff"
        >{{ t("common.retry") }}</button>
      </div>

      <div
        v-else-if="staffList.length === 0"
        class="rounded-2xl border border-slate-700/30 bg-slate-800/20 px-6 py-8 text-center"
      >
        <p class="text-sm text-slate-500">{{ t("ownerStaff.noStaff") }}</p>
      </div>

      <div
        v-for="member in staffList"
        :key="member.id"
        class="rounded-2xl border border-slate-700/40 bg-slate-800/30 overflow-hidden transition-all"
      >
        <!-- Staff card header -->
        <div class="flex items-center justify-between gap-3 px-4 py-3">
          <div class="min-w-0">
            <p class="text-sm font-semibold text-slate-100 truncate">{{ member.name }}</p>
            <p class="text-xs text-slate-500 truncate">{{ member.email }}</p>
          </div>
          <button
            class="shrink-0 flex items-center gap-1.5 rounded-xl border border-slate-700/60 bg-slate-800/60 px-3 py-1.5 text-xs text-slate-400 hover:border-slate-600 hover:text-slate-200 transition-colors"
            @click="toggleExpanded(member.id)"
          >
            {{ t("ownerStaff.manage") }}
            <svg
              class="h-3 w-3 transition-transform duration-200"
              :class="{ 'rotate-180': expandedIds.has(member.id) }"
              viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"
            >
              <path d="M2 4l4 4 4-4"/>
            </svg>
          </button>
        </div>

        <!-- Permissions panel (expandable) -->
        <Transition name="staff-expand">
          <div
            v-if="expandedIds.has(member.id)"
            class="border-t border-slate-700/40 bg-slate-900/40 px-4 py-4 space-y-4"
          >
            <p class="text-xs uppercase tracking-[0.18em] text-slate-500">{{ t("ownerStaff.permissionsTitle") }}</p>

            <!-- Permission toggles -->
            <div class="space-y-3">
              <div
                v-for="perm in permDefs"
                :key="perm.key"
                class="flex items-start justify-between gap-4"
              >
                <div class="min-w-0">
                  <p class="text-sm font-medium text-slate-200">{{ t(perm.labelKey) }}</p>
                  <p class="text-xs text-slate-500">{{ t(perm.descKey) }}</p>
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

            <!-- Saving indicator -->
            <p v-if="savingId === member.id" class="text-xs text-slate-500 italic">
              {{ t("ownerStaff.saving") }}
            </p>
            <p v-if="saveError[member.id]" class="text-xs text-red-400">
              {{ saveError[member.id] }}
            </p>

            <!-- Remove -->
            <div class="flex items-center justify-end gap-2 border-t border-slate-800/60 pt-3">
              <template v-if="confirmRemoveId === member.id">
                <span class="text-[11px] text-red-300 mr-1">{{ t("ownerStaff.confirmRemove") }}?</span>
                <button
                  class="rounded-xl border border-red-500/50 bg-red-500/15 px-3 py-1.5 text-xs font-semibold text-red-300 hover:bg-red-500/25 transition-colors disabled:opacity-50"
                  :disabled="removingId === member.id"
                  @click="removeStaff(member)"
                >{{ removingId === member.id ? t("ownerStaff.removing") : t("common.confirm") }}</button>
                <button
                  class="rounded-xl border border-slate-700/50 bg-slate-800/50 px-3 py-1.5 text-xs text-slate-400 hover:text-slate-200 transition-colors"
                  @click="confirmRemoveId = null"
                >{{ t("common.cancel") }}</button>
              </template>
              <button
                v-else
                class="rounded-xl border border-red-500/30 bg-red-500/8 px-4 py-1.5 text-xs font-medium text-red-400 hover:border-red-500/60 hover:text-red-300 transition-colors"
                @click="confirmRemoveId = member.id"
              >{{ t("ownerStaff.remove") }}</button>
            </div>
          </div>
        </Transition>
      </div>
    </div>

    <!-- Permissions legend -->
    <div class="rounded-xl border border-slate-800/60 bg-slate-900/30 p-4 space-y-1.5">
      <p class="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">{{ t("ownerStaff.legendTitle") }}</p>
      <p class="text-xs text-slate-500">{{ t("ownerStaff.legendOwner") }}</p>
      <p class="text-xs text-slate-500">{{ t("ownerStaff.legendStaff") }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, reactive } from "vue";
import { useI18n } from "../composables/useI18n";
import api from "../lib/api";
import { useToastStore } from "../stores/toast";
import { isFresh, readCache, writeCache } from "../lib/staleCache";

const { t } = useI18n();
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
const confirmRemoveId = ref(null); // member.id awaiting remove confirmation

const form = ref({ name: "", email: "" });
const formError = ref("");
const creating = ref(false);
const newCredentials = ref(null);
const copied = ref(false);

// ── Staff list ─────────────────────────────────────────────────────────────────
const mapStaff = (s) => ({
  ...s,
  permissions: s.permissions ?? { manage_orders: true, view_revenue: false, edit_menu: false },
});

const fetchStaff = async () => {
  const cached = readCache(STAFF_CACHE_KEY);
  if (cached) {
    staffList.value = cached.map(mapStaff);
    if (isFresh(STAFF_CACHE_KEY, STAFF_TTL_MS)) return;
    updatingStaff.value = true;
  } else {
    loadingStaff.value = true;
  }
  staffError.value = false;
  try {
    const { data } = await api.get("/owner/staff/");
    const list = (data.results ?? []).map(mapStaff);
    staffList.value = list;
    writeCache(STAFF_CACHE_KEY, data.results ?? []);
  } catch {
    if (!cached) staffError.value = true;
  } finally {
    loadingStaff.value = false;
    updatingStaff.value = false;
  }
};

onMounted(fetchStaff);

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
    } else {
      formError.value = t("ownerStaff.errorGeneric");
    }
  } finally {
    creating.value = false;
  }
};

// ── Remove staff ───────────────────────────────────────────────────────────────
const removeStaff = async (member) => {
  removingId.value = member.id;
  try {
    await api.delete(`/owner/staff/${member.id}/`);
    staffList.value = staffList.value.filter((s) => s.id !== member.id);
    writeCache(STAFF_CACHE_KEY, staffList.value);
    const next = new Set(expandedIds.value);
    next.delete(member.id);
    expandedIds.value = next;
    confirmRemoveId.value = null;
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
    // clipboard blocked
  }
};
</script>

<style scoped>
/* ── Toggle switch ──────────────────────────────────────────────────────────── */
.staff-toggle {
  position: relative;
  width: 2.5rem;
  height: 1.375rem;
  border-radius: 9999px;
  border: none;
  cursor: pointer;
  transition: background-color 0.2s, opacity 0.2s;
  flex-shrink: 0;
}
.staff-toggle:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.staff-toggle-on  { background: var(--color-secondary, #f59e0b); }
.staff-toggle-off { background: #334155; }

.staff-toggle-thumb {
  position: absolute;
  top: 0.1875rem;
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
  max-height: 400px;
  overflow: hidden;
}
.staff-expand-enter-from,
.staff-expand-leave-to {
  max-height: 0;
  opacity: 0;
}
</style>
