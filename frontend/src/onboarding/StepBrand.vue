<template>
  <div class="ui-panel space-y-4 p-5">
    <h2 class="text-xl font-semibold">{{ t("stepBrand.title") }}</h2>
    <p class="text-sm text-slate-400">{{ introText }}</p>
    <div v-if="isBrowseOnlyPlan" class="rounded-xl border border-sky-500/40 bg-sky-500/10 p-3 text-xs text-sky-100">
      {{ t("stepBrand.warning") }}
    </div>

    <div class="grid sm:grid-cols-2 gap-3">
      <label class="space-y-1 text-sm text-slate-200">
        {{ t("stepBrand.tagline") }}
        <input v-model="form.tagline" :class="inputClass('tagline')" @input="clearField('tagline')" />
        <p v-if="fieldError('tagline')" class="text-xs text-red-300">{{ fieldError("tagline") }}</p>
      </label>
      <label class="space-y-1 text-sm text-slate-200">
        {{ t("stepBrand.phone") }}
        <input v-model="form.phone" :class="inputClass('phone')" @input="clearField('phone')" />
        <p v-if="fieldError('phone')" class="text-xs text-red-300">{{ fieldError("phone") }}</p>
      </label>
      <label class="space-y-1 text-sm text-slate-200">
        {{ whatsappLabel }}
        <input v-model="form.whatsapp" :class="inputClass('whatsapp')" @input="clearField('whatsapp')" />
        <p v-if="fieldError('whatsapp')" class="text-xs text-red-300">{{ fieldError("whatsapp") }}</p>
        <p v-if="isBrowseOnlyPlan" class="text-xs text-slate-500">{{ t("stepBrand.whatsappHint") }}</p>
      </label>
      <label class="space-y-1 text-sm text-slate-200">
        {{ t("common.address") }}
        <input v-model="form.address" :class="inputClass('address')" @input="clearField('address')" />
        <p v-if="fieldError('address')" class="text-xs text-red-300">{{ fieldError("address") }}</p>
      </label>
    </div>

    <label class="space-y-1 text-sm text-slate-200">
      {{ t("common.description") }}
      <textarea
        v-model="form.description"
        rows="3"
        :class="inputClass('description')"
        @input="clearField('description')"
      ></textarea>
      <p v-if="fieldError('description')" class="text-xs text-red-300">{{ fieldError("description") }}</p>
    </label>

    <div class="grid sm:grid-cols-2 gap-3">
      <label class="space-y-1 text-sm text-slate-200">
        {{ t("stepBrand.googleMapsUrl") }}
        <input v-model="form.google_maps_url" :class="inputClass('google_maps_url')" @input="clearField('google_maps_url')" />
        <p v-if="fieldError('google_maps_url')" class="text-xs text-red-300">{{ fieldError("google_maps_url") }}</p>
      </label>
      <label class="space-y-1 text-sm text-slate-200">
        {{ t("stepBrand.reservationUrl") }}
        <input
          v-model="form.reservation_url"
          :class="inputClass('reservation_url')"
          placeholder="https://..."
          @input="clearField('reservation_url')"
        />
        <p v-if="fieldError('reservation_url')" class="text-xs text-red-300">{{ fieldError("reservation_url") }}</p>
      </label>
      <label class="space-y-1 text-sm text-slate-200">
        {{ t("stepBrand.facebookUrl") }}
        <input v-model="form.facebook_url" :class="inputClass('facebook_url')" @input="clearField('facebook_url')" />
        <p v-if="fieldError('facebook_url')" class="text-xs text-red-300">{{ fieldError("facebook_url") }}</p>
      </label>
      <label class="space-y-1 text-sm text-slate-200">
        {{ t("stepBrand.instagramUrl") }}
        <input v-model="form.instagram_url" :class="inputClass('instagram_url')" @input="clearField('instagram_url')" />
        <p v-if="fieldError('instagram_url')" class="text-xs text-red-300">{{ fieldError("instagram_url") }}</p>
      </label>
      <label class="space-y-1 text-sm text-slate-200">
        {{ t("stepBrand.tiktokUrl") }}
        <input v-model="form.tiktok_url" :class="inputClass('tiktok_url')" @input="clearField('tiktok_url')" />
        <p v-if="fieldError('tiktok_url')" class="text-xs text-red-300">{{ fieldError("tiktok_url") }}</p>
      </label>
      <label class="space-y-1 text-sm text-slate-200">
        {{ t("stepBrand.defaultLanguage") }}
        <select v-model="form.language" :class="inputClass('language')" @change="clearField('language')">
          <option v-for="option in localeOptions" :key="option.code" :value="option.code">
            {{ option.label }}
          </option>
        </select>
        <p class="text-xs text-slate-500">{{ t("stepBrand.defaultLanguageHint") }}</p>
        <p v-if="fieldError('language')" class="text-xs text-red-300">{{ fieldError("language") }}</p>
      </label>
    </div>

    <p v-if="fieldError('non_field_errors')" class="text-sm text-red-300">{{ fieldError("non_field_errors") }}</p>

    <div class="flex flex-wrap items-center gap-3">
      <button class="ui-btn-primary px-4 py-2" :disabled="saving" @click="saveAndNext">
        {{ saving ? t("common.saving") : t("common.saveAndNext") }}
      </button>
      <p class="text-sm text-slate-400">{{ status }}</p>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useI18n } from "../composables/useI18n";
import { profileApi } from "../lib/onboardingApi";
import { useLocaleStore } from "../stores/locale";
import { useTenantStore } from "../stores/tenant";
import { useToastStore } from "../stores/toast";

const form = reactive({
  tagline: "",
  description: "",
  phone: "",
  whatsapp: "",
  address: "",
  google_maps_url: "",
  reservation_url: "",
  facebook_url: "",
  instagram_url: "",
  tiktok_url: "",
  language: "en",
});
const saving = ref(false);
const status = ref("");
const errors = ref({});
const tenant = useTenantStore();
const locale = useLocaleStore();
const toast = useToastStore();
const emit = defineEmits(["next"]);
const { localeOptions, t } = useI18n();
const canWhatsappOrder = computed(() => tenant.entitlements?.can_whatsapp_order === true);
const isBrowseOnlyPlan = computed(() => tenant.isBrowseOnlyPlan === true);
const introText = computed(() =>
  isBrowseOnlyPlan.value
    ? t("stepBrand.introBrowseOnly")
    : t("stepBrand.introDefault")
);
const whatsappLabel = computed(() => (canWhatsappOrder.value ? t("stepBrand.whatsappOrdering") : t("stepBrand.whatsappContact")));

const inputClass = (field) =>
  `w-full rounded-xl bg-slate-900 px-3 py-2 border ${errors.value[field] ? "border-red-400" : "border-slate-700"}`;

const fieldError = (field) => (errors.value[field] ? String(errors.value[field]) : "");
const clearField = (field) => {
  if (errors.value[field]) {
    const next = { ...errors.value };
    delete next[field];
    errors.value = next;
  }
};

const load = async () => {
  try {
    const data = await profileApi.get();
    Object.assign(form, data || {});
  } catch {
    status.value = t("stepBrand.statusLoadFailed");
  }
};

const saveAndNext = async () => {
  saving.value = true;
  status.value = "";
  errors.value = {};
  try {
    const saved = await profileApi.save(form);
    tenant.mergeProfile(saved);
    locale.setTenantDefault(saved?.language || form.language);
    status.value = t("stepBrand.statusSaved");
    toast.show(t("stepBrand.toastSaved"), "success");
    emit("next");
  } catch (e) {
    status.value = t("stepBrand.statusSaveFailed");
    errors.value = e?.fieldErrors || {};
    toast.show(e?.message || t("stepBrand.toastFailed"), "error");
  } finally {
    saving.value = false;
  }
};

onMounted(load);
</script>
