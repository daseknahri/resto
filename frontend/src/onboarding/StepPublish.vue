<template>
  <div class="ui-panel space-y-4 p-5">
    <h2 class="text-xl font-semibold">Publish</h2>
    <p class="text-sm text-slate-400">Review your setup and publish your menu.</p>
    <div v-if="isBrowseOnlyPlan" class="rounded-xl border border-sky-500/40 bg-sky-500/10 p-3 text-xs text-sky-100">
      This tenant currently has browsing-only access. Publishing makes the menu public, but ordering actions remain disabled until plan entitlements are enabled.
    </div>

    <ul class="text-sm space-y-2">
      <li v-for="item in checks" :key="item.key" class="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-900/50 px-3 py-2">
        <span class="text-slate-200">{{ item.label }}</span>
        <span class="text-xs font-semibold" :class="item.ok ? 'text-emerald-300' : 'text-amber-300'">{{ item.ok ? 'OK' : 'Missing' }}</span>
      </li>
    </ul>

    <div class="rounded-xl border border-slate-800 bg-slate-900/60 p-3 space-y-1 text-sm">
      <p class="text-slate-300">Menu URL</p>
      <p class="text-slate-100 break-all">{{ menuUrl }}</p>
      <p v-if="publishedAt" class="text-xs text-slate-400">Published at: {{ formattedPublishedAt }}</p>
    </div>

    <div class="rounded-xl border border-slate-800 bg-slate-900/60 p-4 space-y-3">
      <p class="text-sm text-slate-300">Availability controls</p>
      <label class="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-900/70 px-3 py-2">
        <span class="text-sm text-slate-200">Restaurant open</span>
        <input v-model="form.is_open" type="checkbox" class="h-4 w-4 rounded border-slate-600 bg-slate-900 text-brand-secondary" />
      </label>
      <label class="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-900/70 px-3 py-2">
        <span class="text-sm text-slate-200">Temporarily disable public menu</span>
        <input
          v-model="form.is_menu_temporarily_disabled"
          type="checkbox"
          class="h-4 w-4 rounded border-slate-600 bg-slate-900 text-brand-secondary"
          @change="clearError('is_menu_temporarily_disabled')"
        />
      </label>

      <div v-if="form.is_menu_temporarily_disabled" class="space-y-1">
        <label class="text-sm text-slate-200">Disable message</label>
        <textarea
          v-model="form.menu_disabled_note"
          rows="2"
          class="w-full rounded-xl bg-slate-900 border px-3 py-2 text-sm"
          :class="errors.menu_disabled_note ? 'border-red-400' : 'border-slate-700'"
          placeholder="Example: We are updating the menu and will reopen at 6 PM."
          @input="clearError('menu_disabled_note')"
        ></textarea>
        <p v-if="errors.menu_disabled_note" class="text-xs text-red-300">{{ errors.menu_disabled_note }}</p>
      </div>

      <div class="flex flex-wrap gap-3">
        <button
          class="rounded-full border border-slate-700 px-4 py-2 text-sm text-slate-50 disabled:opacity-60"
          :disabled="savingStatus"
          @click="saveStatus"
        >
          {{ savingStatus ? "Saving status..." : "Save status" }}
        </button>
      </div>
    </div>

    <p v-if="!canAttemptPublish" class="text-xs text-amber-300">
      Add at least one category and one dish before publishing.
    </p>
    <p v-if="errors.is_menu_published" class="text-sm text-red-300">{{ errors.is_menu_published }}</p>
    <p v-if="errors.non_field_errors" class="text-sm text-red-300">{{ errors.non_field_errors }}</p>

    <div class="grid gap-2 sm:flex sm:flex-wrap">
      <button
        class="ui-btn-primary w-full justify-center sm:w-auto disabled:opacity-60"
        :disabled="publishing || !canAttemptPublish"
        @click="publish"
      >
        {{ publishing ? "Publishing..." : published ? "Published" : "Publish menu" }}
      </button>
      <button class="ui-btn-outline w-full justify-center sm:w-auto" @click="refreshChecks" :disabled="loadingChecks">
        {{ loadingChecks ? "Refreshing..." : "Refresh checks" }}
      </button>
      <RouterLink v-if="published" to="/owner/launch" class="ui-btn-outline w-full justify-center sm:w-auto">
        Launch summary
      </RouterLink>
      <RouterLink to="/menu" class="ui-btn-outline w-full justify-center sm:w-auto">Preview menu</RouterLink>
      <button class="ui-btn-outline w-full justify-center sm:w-auto" @click="copyMenuUrl">Copy menu URL</button>
      <RouterLink to="/" class="ui-btn-outline w-full justify-center sm:w-auto">Back to landing</RouterLink>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useToastStore } from "../stores/toast";
import { categoryApi, dishApi, profileApi } from "../lib/onboardingApi";
import { useTenantStore } from "../stores/tenant";
import { trackEvent } from "../lib/analytics";

const emit = defineEmits(["publish"]);
const toast = useToastStore();
const tenant = useTenantStore();
const publishing = ref(false);
const savingStatus = ref(false);
const loadingChecks = ref(false);
const published = ref(false);
const publishedAt = ref(null);
const profileSnapshot = ref({});
const categoriesCount = ref(0);
const dishesCount = ref(0);

const form = reactive({
  is_open: true,
  is_menu_temporarily_disabled: false,
  menu_disabled_note: "",
});
const errors = reactive({});

const menuUrl = computed(() => {
  if (typeof window === "undefined") return "/menu";
  return `${window.location.origin}/menu`;
});

const formattedPublishedAt = computed(() => {
  if (!publishedAt.value) return "";
  return new Date(publishedAt.value).toLocaleString();
});
const canCheckout = computed(() => tenant.entitlements?.can_checkout === true);
const canWhatsappOrder = computed(() => tenant.entitlements?.can_whatsapp_order === true);
const isBrowseOnlyPlan = computed(() => tenant.isBrowseOnlyPlan === true);

const checks = computed(() => {
  const p = profileSnapshot.value || {};
  const hasContact = Boolean((p.phone || "").trim() || (p.whatsapp || "").trim());
  const hasBrand = Boolean((p.tagline || "").trim() || hasContact);
  const hasTheme = Boolean((p.logo_url || "").trim() || (p.hero_url || "").trim() || p.primary_color || p.secondary_color);
  const items = [
    { key: "brand", label: "Brand and contact set", ok: hasBrand },
    { key: "categories", label: `Categories added (${categoriesCount.value})`, ok: categoriesCount.value > 0 },
    { key: "dishes", label: `Dishes added (${dishesCount.value})`, ok: dishesCount.value > 0 },
    { key: "theme", label: "Theme configured", ok: hasTheme },
  ];
  if (isBrowseOnlyPlan.value) {
    items.push({ key: "plan_mode", label: "Plan mode: Browse-only", ok: true });
  } else if (canCheckout.value || canWhatsappOrder.value) {
    items.push({ key: "plan_mode", label: "Plan mode: Ordering enabled", ok: true });
  }
  return items;
});

const canAttemptPublish = computed(() => categoriesCount.value > 0 && dishesCount.value > 0);

const clearErrors = () => {
  Object.keys(errors).forEach((key) => delete errors[key]);
};
const clearError = (key) => {
  if (errors[key]) delete errors[key];
};

const load = async () => {
  try {
    const data = await profileApi.get();
    profileSnapshot.value = data || {};
    published.value = data?.is_menu_published === true;
    publishedAt.value = data?.published_at || null;
    form.is_open = data?.is_open !== false;
    form.is_menu_temporarily_disabled = data?.is_menu_temporarily_disabled === true;
    form.menu_disabled_note = data?.menu_disabled_note || "";
  } catch (e) {
    // keep default state
  }
};

const refreshChecks = async () => {
  loadingChecks.value = true;
  try {
    const [profile, categories, dishes] = await Promise.all([
      profileApi.get(),
      categoryApi.list(),
      dishApi.list(),
    ]);
    profileSnapshot.value = profile || {};
    categoriesCount.value = Array.isArray(categories) ? categories.length : 0;
    dishesCount.value = Array.isArray(dishes) ? dishes.length : 0;
  } catch (e) {
    toast.show("Unable to refresh checks", "error");
  } finally {
    loadingChecks.value = false;
  }
};

const saveProfile = async (publishFlag = null) => {
  const current = await profileApi.get();
  const payload = {
    ...(current || {}),
    is_open: form.is_open,
    is_menu_temporarily_disabled: form.is_menu_temporarily_disabled,
    menu_disabled_note: form.menu_disabled_note,
  };
  if (publishFlag !== null) payload.is_menu_published = publishFlag;
  return profileApi.save(payload);
};

const saveStatus = async () => {
  savingStatus.value = true;
  clearErrors();
  try {
    const saved = await saveProfile(null);
    profileSnapshot.value = saved || {};
    form.is_open = saved?.is_open !== false;
    form.is_menu_temporarily_disabled = saved?.is_menu_temporarily_disabled === true;
    form.menu_disabled_note = saved?.menu_disabled_note || "";
    await tenant.fetchMeta();
    toast.show("Availability status saved", "success");
  } catch (e) {
    Object.assign(errors, e?.fieldErrors || {});
    toast.show(e?.message || "Status save failed", "error");
  } finally {
    savingStatus.value = false;
  }
};

const publish = async () => {
  publishing.value = true;
  clearErrors();
  try {
    const saved = await saveProfile(true);
    profileSnapshot.value = saved || {};
    published.value = saved?.is_menu_published === true;
    publishedAt.value = saved?.published_at || null;
    form.is_open = saved?.is_open !== false;
    form.is_menu_temporarily_disabled = saved?.is_menu_temporarily_disabled === true;
    form.menu_disabled_note = saved?.menu_disabled_note || "";
    await tenant.fetchMeta();
    trackEvent("owner_publish", {
      source: "owner_wizard",
      metadata: {
        categories_count: categoriesCount.value,
        dishes_count: dishesCount.value,
      },
    });
    emit("publish");
    toast.show("Menu published. Share your URL with customers.", "success");
  } catch (e) {
    Object.assign(errors, e?.fieldErrors || {});
    toast.show(e?.message || "Publish failed", "error");
  } finally {
    publishing.value = false;
  }
};

const copyMenuUrl = async () => {
  try {
    await navigator.clipboard.writeText(menuUrl.value);
    toast.show("Menu URL copied", "success");
  } catch (e) {
    toast.show("Copy failed", "error");
  }
};

onMounted(async () => {
  await load();
  await refreshChecks();
});
</script>
