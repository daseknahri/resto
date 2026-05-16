<template>
  <div class="space-y-6 max-w-2xl">
    <!-- Header -->
    <div>
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
          class="rounded-xl border border-slate-700/60 bg-slate-900/50 px-3.5 py-2.5 text-sm text-slate-100 placeholder-slate-500 outline-none focus:border-indigo-500/60 focus:ring-1 focus:ring-indigo-500/30 transition-colors"
          :disabled="creating"
          @keyup.enter="createStaff"
        />
        <input
          v-model="form.email"
          type="email"
          :placeholder="t('ownerStaff.emailPlaceholder')"
          class="rounded-xl border border-slate-700/60 bg-slate-900/50 px-3.5 py-2.5 text-sm text-slate-100 placeholder-slate-500 outline-none focus:border-indigo-500/60 focus:ring-1 focus:ring-indigo-500/30 transition-colors"
          :disabled="creating"
          @keyup.enter="createStaff"
        />
      </div>
      <p v-if="formError" class="text-xs text-red-400">{{ formError }}</p>
      <button
        class="rounded-xl bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white transition-opacity hover:bg-indigo-500 disabled:opacity-50"
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
          <span class="text-slate-400">Email:</span>
          <span class="text-slate-100 truncate">{{ newCredentials.email }}</span>
        </div>
        <div class="flex items-center justify-between gap-3">
          <span class="text-slate-400">Password:</span>
          <span class="text-emerald-300 font-bold tracking-wider">{{ newCredentials.temp_password }}</span>
        </div>
      </div>
      <div class="flex gap-2">
        <button
          class="rounded-xl border border-slate-600 bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-300 hover:border-slate-500 transition-colors"
          @click="copyCredentials"
        >
          {{ copied ? "Copied ✓" : t("ownerStaff.credentialsCopy") }}
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
        class="flex items-center justify-between gap-3 rounded-2xl border border-slate-700/40 bg-slate-800/30 px-4 py-3"
      >
        <div class="min-w-0">
          <p class="text-sm font-semibold text-slate-100 truncate">{{ member.name }}</p>
          <p class="text-xs text-slate-500 truncate">{{ member.email }}</p>
        </div>
        <button
          class="shrink-0 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-1.5 text-xs font-medium text-red-400 hover:border-red-500/60 hover:text-red-300 transition-colors disabled:opacity-50"
          :disabled="removingId === member.id"
          @click="removeStaff(member)"
        >
          {{ removingId === member.id ? t("ownerStaff.removing") : t("ownerStaff.remove") }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { useI18n } from "../composables/useI18n";
import api from "../lib/api";

const { t } = useI18n();

// ── State ──────────────────────────────────────────────────────────────────────
const staffList = ref([]);
const loadingStaff = ref(false);

const form = ref({ name: "", email: "" });
const formError = ref("");
const creating = ref(false);
const newCredentials = ref(null);
const copied = ref(false);

const removingId = ref(null);

// ── Staff list ─────────────────────────────────────────────────────────────────
const fetchStaff = async () => {
  loadingStaff.value = true;
  try {
    const { data } = await api.get("/owner/staff/");
    staffList.value = data.results ?? [];
  } catch {
    // silent — user will see empty list
  } finally {
    loadingStaff.value = false;
  }
};

onMounted(fetchStaff);

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
      { id: data.id, name: data.name, email: data.email, username: data.username },
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
  if (!confirm(`Remove ${member.name} (${member.email})?`)) return;
  removingId.value = member.id;
  try {
    await api.delete(`/owner/staff/${member.id}/`);
    staffList.value = staffList.value.filter((s) => s.id !== member.id);
  } catch {
    // silent
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
