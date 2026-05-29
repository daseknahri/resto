<template>
  <div class="space-y-6 max-w-2xl">
    <!-- Header -->
    <div>
      <p class="ui-kicker">{{ t("ownerStaff.kicker") }}</p>
      <h2 class="text-xl font-bold text-white">{{ t("ownerStaff.title") }}</h2>
      <p class="mt-1 text-sm text-slate-400">{{ t("ownerStaff.subtitle") }}</p>
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
      <p v-if="formError" class="text-xs text-red-400">{{ formError }}</p>
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

// ── State ──────────────────────────────────────────────────────────────────────
const staffList = ref([]);
const loadingStaff = ref(false);
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
const fetchStaff = async () => {
  loadingStaff.value = true;
  try {
    const { data } = await api.get("/owner/staff/");
    staffList.value = (data.results ?? []).map((s) => ({
      ...s,
      permissions: s.permissions ?? { manage_orders: true, view_revenue: false, edit_menu: false },
    }));
  } catch {
    // silent — user will see empty list
  } finally {
    loadingStaff.value = false;
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
    staffList.value = [
      ...staffList.value,
      {
        id: data.id,
        name: data.name,
        email: data.email,
        username: data.username,
        permissions: { manage_orders: true, view_revenue: false, edit_menu: false },
      },
    ];
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
