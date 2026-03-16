<template>
  <div class="space-y-4">
    <section v-if="!standalone" class="ui-panel space-y-4 p-5">
      <h2 class="text-xl font-semibold">{{ t("stepPublish.title") }}</h2>
      <p class="text-sm text-slate-400">{{ t("stepPublish.description") }}</p>
    </section>

    <section :class="sectionPanelClass">
      <div class="space-y-1">
        <p class="ui-section-kicker">{{ t("stepPublish.title") }}</p>
        <h3 class="text-lg font-semibold text-white">{{ t("stepPublish.readinessSection") }}</h3>
      </div>

      <div class="flex flex-wrap gap-2">
        <span class="rounded-full border border-slate-700 bg-slate-950/55 px-3 py-1 text-[11px] font-medium text-slate-300">
          {{ categoriesCount }} {{ t("common.categories").toLowerCase() }}
        </span>
        <span class="rounded-full border border-slate-700 bg-slate-950/55 px-3 py-1 text-[11px] font-medium text-slate-300">
          {{ dishesCount }} {{ t("common.dishes").toLowerCase() }}
        </span>
        <span
          class="rounded-full border px-3 py-1 text-[11px] font-medium"
          :class="published ? 'border-emerald-500/35 bg-emerald-500/10 text-emerald-200' : 'border-slate-700 bg-slate-950/55 text-slate-300'"
        >
          {{ published ? t("stepPublish.liveBadge") : t("stepPublish.draftBadge") }}
        </span>
        <span
          class="rounded-full border px-3 py-1 text-[11px] font-medium"
          :class="form.is_open ? 'border-emerald-500/35 bg-emerald-500/10 text-emerald-200' : 'border-slate-700 bg-slate-950/55 text-slate-300'"
        >
          {{ form.is_open ? t("stepPublish.restaurantOpen") : t("common.closed") }}
        </span>
      </div>

      <div v-if="isBrowseOnlyPlan" class="rounded-xl border border-sky-500/40 bg-sky-500/10 p-3 text-xs text-sky-100">
        {{ t("stepPublish.browseOnlyWarning") }}
      </div>

      <div class="grid gap-4 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)]">
        <ul class="space-y-2 text-sm">
          <li
            v-for="item in checks"
            :key="item.key"
            class="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-900/50 px-4 py-3"
          >
            <span class="text-slate-200">{{ item.label }}</span>
            <span
              class="rounded-full px-2.5 py-1 text-[11px] font-semibold"
              :class="item.ok ? 'bg-emerald-500/10 text-emerald-200' : 'bg-amber-500/10 text-amber-200'"
            >
              {{ item.ok ? t("stepPublish.ok") : t("stepPublish.missing") }}
            </span>
          </li>
        </ul>

        <div class="space-y-4">
          <div class="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 space-y-2 text-sm">
            <p class="ui-section-kicker">{{ t("stepPublish.menuUrl") }}</p>
            <p class="text-slate-100 break-all">{{ menuUrl }}</p>
            <p v-if="publishedAt" class="text-xs text-slate-400">{{ t("stepPublish.publishedAt", { date: formattedPublishedAt }) }}</p>
          </div>

          <div class="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 space-y-3">
            <div class="flex items-center justify-between gap-3">
              <div>
                <p class="ui-section-kicker">{{ t("stepPublish.publishStatus") }}</p>
                <p class="text-lg font-semibold text-white">
                  {{ published ? t("stepPublish.published") : t("stepPublish.draft") }}
                </p>
              </div>
              <span
                class="rounded-full px-3 py-1 text-xs font-semibold"
                :class="published ? 'bg-emerald-500/10 text-emerald-200' : 'bg-slate-800 text-slate-300'"
              >
                {{ published ? t("stepPublish.liveBadge") : t("stepPublish.draftBadge") }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section :class="sectionPanelClass">
      <div class="space-y-1">
        <p class="ui-section-kicker">{{ t("stepPublish.availabilityControls") }}</p>
        <h3 class="text-lg font-semibold text-white">{{ t("stepPublish.availabilitySectionTitle") }}</h3>
      </div>

      <div class="space-y-3 rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
        <label class="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-900/70 px-3 py-3">
          <div class="space-y-1">
            <span class="text-sm font-medium text-slate-100">{{ t("stepPublish.restaurantOpen") }}</span>
            <p class="text-xs text-slate-500">{{ t("stepPublish.restaurantOpenHint") }}</p>
          </div>
          <input v-model="form.is_open" type="checkbox" class="h-4 w-4 rounded border-slate-600 bg-slate-900 text-brand-secondary" />
        </label>

        <label class="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-900/70 px-3 py-3">
          <div class="space-y-1">
            <span class="text-sm font-medium text-slate-100">{{ t("stepPublish.disablePublicMenu") }}</span>
            <p class="text-xs text-slate-500">{{ t("stepPublish.disablePublicMenuHint") }}</p>
          </div>
          <input
            v-model="form.is_menu_temporarily_disabled"
            type="checkbox"
            class="h-4 w-4 rounded border-slate-600 bg-slate-900 text-brand-secondary"
            @change="clearError('is_menu_temporarily_disabled')"
          />
        </label>

        <div v-if="form.is_menu_temporarily_disabled" class="space-y-2 rounded-xl border border-slate-800 bg-slate-950/45 p-3">
          <label class="text-sm text-slate-200">{{ t("stepPublish.disableMessage") }}</label>
          <textarea
            v-model="form.menu_disabled_note"
            rows="2"
            class="w-full rounded-xl border bg-slate-900 px-3 py-2 text-sm"
            :class="errors.menu_disabled_note ? 'border-red-400' : 'border-slate-700'"
            :placeholder="t('stepPublish.disableMessagePlaceholder')"
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
            {{ savingStatus ? t("stepPublish.savingStatus") : t("stepPublish.saveStatus") }}
          </button>
        </div>
      </div>
    </section>

    <section :class="sectionPanelClass">
      <div class="space-y-1">
        <p class="ui-section-kicker">{{ t("stepPublish.publishActions") }}</p>
        <h3 class="text-lg font-semibold text-white">{{ t("stepPublish.publishSectionTitle") }}</h3>
      </div>

      <p v-if="!canAttemptPublish" class="text-xs text-amber-300">
        {{ t("stepPublish.publishRequirement") }}
      </p>
      <p v-if="errors.is_menu_published" class="text-sm text-red-300">{{ errors.is_menu_published }}</p>
      <p v-if="errors.non_field_errors" class="text-sm text-red-300">{{ errors.non_field_errors }}</p>

      <div class="grid gap-2 sm:flex sm:flex-wrap">
        <button
          class="ui-btn-primary w-full justify-center sm:w-auto disabled:opacity-60"
          :disabled="publishing || !canAttemptPublish"
          @click="publish"
        >
          {{ publishing ? t("stepPublish.publishing") : published ? t("stepPublish.published") : t("stepPublish.publishMenu") }}
        </button>
        <button class="ui-btn-outline w-full justify-center sm:w-auto" :disabled="loadingChecks" @click="refreshChecks">
          {{ loadingChecks ? t("stepPublish.refreshingChecks") : t("stepPublish.refreshChecks") }}
        </button>
        <RouterLink v-if="published" to="/owner/launch" class="ui-btn-outline w-full justify-center sm:w-auto">
          {{ t("stepPublish.launchSummary") }}
        </RouterLink>
        <RouterLink to="/menu" class="ui-btn-outline w-full justify-center sm:w-auto">{{ t("stepPublish.previewMenu") }}</RouterLink>
        <button class="ui-btn-outline w-full justify-center sm:w-auto" @click="copyMenuUrl">{{ t("stepPublish.copyMenuUrl") }}</button>
        <RouterLink to="/" class="ui-btn-outline w-full justify-center sm:w-auto">{{ t("stepPublish.backToLanding") }}</RouterLink>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useToastStore } from "../stores/toast";
import { categoryApi, dishApi, profileApi } from "../lib/onboardingApi";
import { useI18n } from "../composables/useI18n";
import { useTenantStore } from "../stores/tenant";
import { trackEvent } from "../lib/analytics";

const props = defineProps({
  standalone: {
    type: Boolean,
    default: false,
  },
});
const emit = defineEmits(["publish"]);
const toast = useToastStore();
const tenant = useTenantStore();
const { t, formatDateTime } = useI18n();
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
  return formatDateTime(publishedAt.value);
});
const canCheckout = computed(() => tenant.entitlements?.can_checkout === true);
const canWhatsappOrder = computed(() => tenant.entitlements?.can_whatsapp_order === true);
const isBrowseOnlyPlan = computed(() => tenant.isBrowseOnlyPlan === true);
const sectionPanelClass = computed(() => "ui-panel space-y-4 p-5");

const checks = computed(() => {
  const p = profileSnapshot.value || {};
  const hasContact = Boolean((p.phone || "").trim() || (p.whatsapp || "").trim());
  const hasBrand = Boolean((p.tagline || "").trim() || hasContact);
  const hasTheme = Boolean((p.logo_url || "").trim() || (p.hero_url || "").trim() || p.primary_color || p.secondary_color);
  const items = [
    { key: "brand", label: t("stepPublish.checkBrandContact"), ok: hasBrand },
    { key: "categories", label: t("stepPublish.checkCategories", { count: categoriesCount.value }), ok: categoriesCount.value > 0 },
    { key: "dishes", label: t("stepPublish.checkDishes", { count: dishesCount.value }), ok: dishesCount.value > 0 },
    { key: "theme", label: t("stepPublish.checkTheme"), ok: hasTheme },
  ];
  if (isBrowseOnlyPlan.value) {
    items.push({ key: "plan_mode", label: t("stepPublish.checkPlanBrowseOnly"), ok: true });
  } else if (canCheckout.value || canWhatsappOrder.value) {
    items.push({ key: "plan_mode", label: t("stepPublish.checkPlanOrdering"), ok: true });
  }
  return items;
});

const canAttemptPublish = computed(() => categoriesCount.value > 0 && dishesCount.value > 0);
const standalone = computed(() => props.standalone);

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
  } catch {
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
  } catch {
    toast.show(t("stepPublish.refreshChecksFailed"), "error");
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
    toast.show(t("stepPublish.statusSaved"), "success");
  } catch (e) {
    Object.assign(errors, e?.fieldErrors || {});
    toast.show(e?.message || t("stepPublish.statusSaveFailed"), "error");
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
    toast.show(t("stepPublish.publishedSuccess"), "success");
  } catch (e) {
    Object.assign(errors, e?.fieldErrors || {});
    toast.show(e?.message || t("stepPublish.publishFailed"), "error");
  } finally {
    publishing.value = false;
  }
};

const copyMenuUrl = async () => {
  try {
    await navigator.clipboard.writeText(menuUrl.value);
    toast.show(t("stepPublish.menuCopied"), "success");
  } catch {
    toast.show(t("stepPublish.copyFailed"), "error");
  }
};

onMounted(async () => {
  await load();
  await refreshChecks();
});
</script>
