<template>
  <div class="space-y-4">
    <div v-if="!props.standalone" class="ui-panel space-y-4 p-5">
      <h2 class="text-xl font-semibold">{{ t("stepBrand.title") }}</h2>
      <p class="text-sm text-slate-400">{{ introText }}</p>
      <div v-if="isBrowseOnlyPlan" class="rounded-xl border border-sky-500/40 bg-sky-500/10 p-3 text-xs text-sky-100">
        {{ t("stepBrand.warning") }}
      </div>
    </div>

    <section :class="sectionPanelClass">
      <div class="space-y-1">
        <p class="ui-section-kicker">{{ props.standalone ? t("common.profile") : t("stepBrand.title") }}</p>
        <h3 class="text-lg font-semibold text-white">{{ t("ownerProfileSections.brandContact") }}</h3>
      </div>

      <div class="grid gap-3 sm:grid-cols-2">
        <div class="space-y-1 text-sm text-slate-200">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <span>{{ t("stepBrand.tagline") }}</span>
          <div class="flex flex-wrap gap-1">
            <button
              v-for="localeCode in contentLocaleCodes"
              :key="`tagline-${localeCode}`"
              type="button"
              class="rounded-full border px-2.5 py-1 text-[11px] font-semibold transition-colors"
              :class="fieldLocales.tagline === localeCode ? 'border-brand-secondary bg-brand-secondary/10 text-brand-secondary' : 'border-slate-700 text-slate-200 hover:border-brand-secondary'"
              :aria-pressed="fieldLocales.tagline === localeCode"
              @click="fieldLocales.tagline = localeCode"
            >
              {{ localeChipLabel(localeCode) }}
            </button>
            <button
              v-if="fieldLocales.tagline !== defaultContentLocale && localizedFieldValue('tagline', defaultContentLocale)"
              type="button"
              class="rounded-full border border-sky-700/60 px-2.5 py-1 text-[11px] font-semibold text-sky-300 transition-colors hover:border-sky-500 hover:text-sky-200 disabled:opacity-50"
              :disabled="translating['tagline']"
              @click="runTranslate('tagline', 'tagline', fieldLocales.tagline)"
            >
              {{ translating["tagline"] ? t("common.translating") : t("common.translate") }}
            </button>
          </div>
        </div>
        <input
          type="text"
          :value="localizedFieldValue('tagline', fieldLocales.tagline)"
          :class="inputClass('tagline')"
          :aria-label="t('stepBrand.tagline')"
          :aria-invalid="fieldError('tagline') ? 'true' : undefined"
          aria-describedby="step-brand-tagline-error"
          @input="onLocalizedFieldInput('tagline', fieldLocales.tagline, $event.target.value)"
        />
        <p v-if="fieldError('tagline')" id="step-brand-tagline-error" class="text-xs text-red-300">{{ fieldError("tagline") }}</p>
      </div>
        <label class="space-y-1 text-sm text-slate-200">
          {{ t("stepBrand.phone") }}
          <input v-model="form.phone" type="tel" inputmode="tel" autocomplete="tel" :class="inputClass('phone')" :aria-invalid="fieldError('phone') ? 'true' : undefined" aria-describedby="step-brand-phone-error" @input="clearField('phone')" />
          <p v-if="fieldError('phone')" id="step-brand-phone-error" class="text-xs text-red-300">{{ fieldError("phone") }}</p>
        </label>
        <label class="space-y-1 text-sm text-slate-200">
          {{ whatsappLabel }}
          <input v-model="form.whatsapp" type="tel" inputmode="tel" autocomplete="tel" :class="inputClass('whatsapp')" :aria-invalid="fieldError('whatsapp') ? 'true' : undefined" aria-describedby="step-brand-whatsapp-error" @input="clearField('whatsapp')" />
          <p v-if="fieldError('whatsapp')" id="step-brand-whatsapp-error" class="text-xs text-red-300">{{ fieldError("whatsapp") }}</p>
          <p v-if="isBrowseOnlyPlan" class="text-xs text-slate-500">{{ t("stepBrand.whatsappHint") }}</p>
        </label>
        <label class="space-y-1 text-sm text-slate-200">
          {{ t("stepBrand.deliveryFee") }}
          <div class="relative">
            <input
              v-model="form.delivery_fee"
              type="number"
              min="0"
              step="0.01"
              :class="inputClass('delivery_fee') + ' pr-14'"
              :aria-invalid="fieldError('delivery_fee') ? 'true' : undefined"
              aria-describedby="step-brand-delivery-fee-error"
              @input="clearField('delivery_fee')"
            />
            <span class="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs text-slate-500">
              {{ t("stepBrand.deliveryFeeUnit") }}
            </span>
          </div>
          <p class="text-xs text-slate-500">{{ t("stepBrand.deliveryFeeHint") }}</p>
          <p v-if="fieldError('delivery_fee')" id="step-brand-delivery-fee-error" class="text-xs text-red-300">{{ fieldError("delivery_fee") }}</p>
        </label>
        <div class="grid grid-cols-[1fr_auto] gap-3">
          <label class="space-y-1 text-sm text-slate-200">
            {{ t("stepBrand.vatRate") }}
            <div class="relative">
              <input
                v-model="form.vat_rate"
                type="number"
                min="0"
                max="100"
                step="0.01"
                :class="inputClass('vat_rate') + ' pr-10'"
                @input="clearField('vat_rate')"
              />
              <span class="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs text-slate-500">%</span>
            </div>
            <p class="text-xs text-slate-500">{{ t("stepBrand.vatRateHint") }}</p>
          </label>
          <label class="space-y-1 text-sm text-slate-200">
            {{ t("stepBrand.vatLabel") }}
            <input
              v-model="form.vat_label"
              type="text"
              maxlength="20"
              :placeholder="t('stepBrand.vatLabelPlaceholder')"
              :class="inputClass('vat_label') + ' w-24'"
            />
          </label>
        </div>
        <div class="space-y-1 text-sm text-slate-200">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <span>{{ t("common.address") }}</span>
          <div class="flex flex-wrap gap-1">
            <button
              v-for="localeCode in contentLocaleCodes"
              :key="`address-${localeCode}`"
              type="button"
              class="rounded-full border px-2.5 py-1 text-[11px] font-semibold transition-colors"
              :class="fieldLocales.address === localeCode ? 'border-brand-secondary bg-brand-secondary/10 text-brand-secondary' : 'border-slate-700 text-slate-200 hover:border-brand-secondary'"
              :aria-pressed="fieldLocales.address === localeCode"
              @click="fieldLocales.address = localeCode"
            >
              {{ localeChipLabel(localeCode) }}
            </button>
            <button
              v-if="fieldLocales.address !== defaultContentLocale && localizedFieldValue('address', defaultContentLocale)"
              type="button"
              class="rounded-full border border-sky-700/60 px-2.5 py-1 text-[11px] font-semibold text-sky-300 transition-colors hover:border-sky-500 hover:text-sky-200 disabled:opacity-50"
              :disabled="translating['address']"
              @click="runTranslate('address', 'address', fieldLocales.address)"
            >
              {{ translating["address"] ? t("common.translating") : t("common.translate") }}
            </button>
          </div>
        </div>
        <input
          type="text"
          :value="localizedFieldValue('address', fieldLocales.address)"
          :class="inputClass('address')"
          :aria-label="t('common.address')"
          :aria-invalid="fieldError('address') ? 'true' : undefined"
          aria-describedby="step-brand-address-error"
          @input="onLocalizedFieldInput('address', fieldLocales.address, $event.target.value)"
        />
        <p v-if="fieldError('address')" id="step-brand-address-error" class="text-xs text-red-300">{{ fieldError("address") }}</p>
        </div>
      </div>

      <div class="space-y-1 text-sm text-slate-200">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <span>{{ t("common.description") }}</span>
          <div class="flex flex-wrap gap-1">
            <button
              v-for="localeCode in contentLocaleCodes"
              :key="`description-${localeCode}`"
              type="button"
              class="rounded-full border px-2.5 py-1 text-[11px] font-semibold transition-colors"
              :class="fieldLocales.description === localeCode ? 'border-brand-secondary bg-brand-secondary/10 text-brand-secondary' : 'border-slate-700 text-slate-200 hover:border-brand-secondary'"
              :aria-pressed="fieldLocales.description === localeCode"
              @click="fieldLocales.description = localeCode"
            >
              {{ localeChipLabel(localeCode) }}
            </button>
            <button
              v-if="fieldLocales.description !== defaultContentLocale && localizedFieldValue('description', defaultContentLocale)"
              type="button"
              class="rounded-full border border-sky-700/60 px-2.5 py-1 text-[11px] font-semibold text-sky-300 transition-colors hover:border-sky-500 hover:text-sky-200 disabled:opacity-50"
              :disabled="translating['description']"
              @click="runTranslate('description', 'description', fieldLocales.description)"
            >
              {{ translating["description"] ? t("common.translating") : t("common.translate") }}
            </button>
          </div>
        </div>
        <textarea
          :value="localizedFieldValue('description', fieldLocales.description)"
          rows="3"
          :class="inputClass('description')"
          :aria-label="t('common.description')"
          :aria-invalid="fieldError('description') ? 'true' : undefined"
          aria-describedby="step-brand-description-error"
          @input="onLocalizedFieldInput('description', fieldLocales.description, $event.target.value)"
        ></textarea>
        <p v-if="fieldError('description')" id="step-brand-description-error" class="text-xs text-red-300">{{ fieldError("description") }}</p>
      </div>
    </section>

    <section :class="sectionPanelClass">
      <div class="space-y-1">
        <p class="ui-section-kicker">{{ t("stepBrand.businessHours") }}</p>
        <h3 class="text-lg font-semibold text-white">{{ t("ownerProfileSections.operations") }}</h3>
      </div>

      <div class="space-y-3 text-sm text-slate-200">
      <div class="flex flex-wrap gap-2">
        <span class="rounded-full border border-slate-700 bg-slate-950/55 px-3 py-1 text-[11px] font-medium text-slate-300">
          {{ t("common.open") }} {{ openBusinessDaysCount }}/7
        </span>
        <span
          v-if="businessHoursPreview"
          class="rounded-full border border-brand-secondary/35 bg-brand-secondary/10 px-3 py-1 text-[11px] font-medium text-brand-secondary"
        >
          {{ businessHoursPreview }}
        </span>
      </div>

      <div class="space-y-2 rounded-2xl border border-slate-800 bg-slate-950/55 p-3">
        <div
          v-for="day in weekdayOptions"
          :key="day.key"
          class="rounded-2xl border border-slate-800/90 bg-slate-950/35 px-3 py-3"
        >
          <div class="grid gap-3 sm:grid-cols-[7rem_minmax(0,1fr)_auto] sm:items-center">
            <div class="space-y-1">
              <p class="font-medium text-slate-100">{{ day.label }}</p>
              <p class="text-xs text-slate-500">
                {{ form.business_hours_schedule[day.key].enabled ? t("stepBrand.openLabel") : t("stepBrand.closedAllDay") }}
              </p>
            </div>

            <div v-if="form.business_hours_schedule[day.key].enabled" class="grid gap-2 sm:grid-cols-2">
              <label class="space-y-1 text-[11px] text-slate-400">
                <span>{{ t("stepBrand.opensAt") }}</span>
                <input
                  v-model="form.business_hours_schedule[day.key].open"
                  type="time"
                  class="w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100"
                  @input="markBusinessHoursEdited"
                />
              </label>
              <label class="space-y-1 text-[11px] text-slate-400">
                <span>{{ t("stepBrand.closesAt") }}</span>
                <input
                  v-model="form.business_hours_schedule[day.key].close"
                  type="time"
                  class="w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100"
                  @input="markBusinessHoursEdited"
                />
              </label>
            </div>

            <div
              v-else
              class="rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2 text-xs text-slate-500 sm:text-right"
            >
              {{ t("stepBrand.closedAllDay") }}
            </div>

            <button
              type="button"
              :aria-pressed="form.business_hours_schedule[day.key].enabled"
              class="justify-self-start rounded-full border px-3 py-1 text-[11px] font-semibold transition-colors sm:justify-self-end"
              :class="form.business_hours_schedule[day.key].enabled ? 'border-emerald-500/50 bg-emerald-500/10 text-emerald-200' : 'border-slate-700 bg-slate-900 text-slate-300'"
              @click="toggleBusinessHoursDay(day.key)"
            >
              {{ form.business_hours_schedule[day.key].enabled ? t("common.open") : t("common.closed") }}
            </button>
          </div>
        </div>
      </div>

      <div v-if="!hasStructuredBusinessHours && localizedFieldValue('business_hours', defaultContentLocale)" class="rounded-2xl border border-slate-800 bg-slate-950/45 px-3 py-2 text-xs text-slate-400">
        {{ t("stepBrand.businessHoursLegacyNotice") }}
      </div>
      <p v-if="fieldError('business_hours')" id="step-brand-business-hours-error" class="text-xs text-red-300">{{ fieldError("business_hours") }}</p>
      <p v-if="fieldError('business_hours_schedule')" id="step-brand-business-hours-schedule-error" class="text-xs text-red-300">{{ fieldError("business_hours_schedule") }}</p>

      <div class="space-y-1">
        <label class="text-xs font-medium text-slate-400">{{ t("stepBrand.timezoneLabel") }}</label>
        <select v-model="form.timezone" :class="inputClass('timezone')">
          <option value="">{{ t("stepBrand.timezoneDefault") }}</option>
          <option v-for="tz in TIMEZONE_OPTIONS" :key="tz" :value="tz">{{ tz }}</option>
        </select>
        <p class="text-[11px] text-slate-500">{{ t("stepBrand.timezoneHint") }}</p>
      </div>
      </div>
    </section>

    <section :class="sectionPanelClass">
      <div class="space-y-1">
        <p class="ui-section-kicker">{{ t("ownerProfileSections.links") }}</p>
        <h3 class="text-lg font-semibold text-white">{{ t("ownerProfileSections.discovery") }}</h3>
      </div>

      <div class="grid gap-3 sm:grid-cols-2">
        <label class="space-y-1 text-sm text-slate-200">
          {{ t("stepBrand.googleMapsUrl") }}
          <input v-model="form.google_maps_url" type="url" inputmode="url" :class="inputClass('google_maps_url')" :aria-invalid="fieldError('google_maps_url') ? 'true' : undefined" aria-describedby="step-brand-maps-error" @input="clearField('google_maps_url')" />
          <p v-if="fieldError('google_maps_url')" id="step-brand-maps-error" class="text-xs text-red-300">{{ fieldError("google_maps_url") }}</p>
        </label>
        <label class="space-y-1 text-sm text-slate-200">
          {{ t("stepBrand.reservationUrl") }}
          <input
            v-model="form.reservation_url"
            type="url"
            inputmode="url"
            :class="inputClass('reservation_url')"
            placeholder="https://..."
            :aria-invalid="fieldError('reservation_url') ? 'true' : undefined"
            aria-describedby="step-brand-reservation-error"
            @input="clearField('reservation_url')"
          />
          <p v-if="fieldError('reservation_url')" id="step-brand-reservation-error" class="text-xs text-red-300">{{ fieldError("reservation_url") }}</p>
        </label>
        <label class="space-y-1 text-sm text-slate-200">
          {{ t("stepBrand.facebookUrl") }}
          <input v-model="form.facebook_url" type="url" inputmode="url" :class="inputClass('facebook_url')" :aria-invalid="fieldError('facebook_url') ? 'true' : undefined" aria-describedby="step-brand-facebook-error" @input="clearField('facebook_url')" />
          <p v-if="fieldError('facebook_url')" id="step-brand-facebook-error" class="text-xs text-red-300">{{ fieldError("facebook_url") }}</p>
        </label>
        <label class="space-y-1 text-sm text-slate-200">
          {{ t("stepBrand.instagramUrl") }}
          <input v-model="form.instagram_url" type="url" inputmode="url" :class="inputClass('instagram_url')" :aria-invalid="fieldError('instagram_url') ? 'true' : undefined" aria-describedby="step-brand-instagram-error" @input="clearField('instagram_url')" />
          <p v-if="fieldError('instagram_url')" id="step-brand-instagram-error" class="text-xs text-red-300">{{ fieldError("instagram_url") }}</p>
        </label>
        <label class="space-y-1 text-sm text-slate-200">
          {{ t("stepBrand.tiktokUrl") }}
          <input v-model="form.tiktok_url" type="url" inputmode="url" :class="inputClass('tiktok_url')" :aria-invalid="fieldError('tiktok_url') ? 'true' : undefined" aria-describedby="step-brand-tiktok-error" @input="clearField('tiktok_url')" />
          <p v-if="fieldError('tiktok_url')" id="step-brand-tiktok-error" class="text-xs text-red-300">{{ fieldError("tiktok_url") }}</p>
        </label>
        <label class="space-y-1 text-sm text-slate-200">
          {{ t("stepBrand.defaultLanguage") }}
          <select v-model="form.language" :class="inputClass('language')" :aria-invalid="fieldError('language') ? 'true' : undefined" aria-describedby="step-brand-language-error" @change="clearField('language')">
            <option v-for="option in localeOptions" :key="option.code" :value="option.code">
              {{ option.label }}
            </option>
          </select>
          <p class="text-xs text-slate-500">{{ t("stepBrand.defaultLanguageHint") }}</p>
          <p v-if="fieldError('language')" id="step-brand-language-error" class="text-xs text-red-300">{{ fieldError("language") }}</p>
        </label>
      </div>
    </section>

    <section :class="sectionPanelClass">
      <div v-if="fieldError('non_field_errors')" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
        <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
        <p class="flex-1 text-sm text-red-300">{{ fieldError("non_field_errors") }}</p>
      </div>

      <div class="flex flex-wrap items-center gap-3">
        <button class="ui-btn-primary px-4 py-2" :disabled="saving" @click="saveAndNext">
          {{ saving ? t("common.saving") : props.standalone ? t("common.save") : t("common.saveAndNext") }}
        </button>
        <p class="text-sm text-slate-400">{{ status }}</p>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import {
  buildBusinessHoursSummaries,
  createEmptyBusinessHoursSchedule,
  hasEnabledBusinessHours,
  normalizeBusinessHoursSchedule,
  WEEKDAY_KEYS,
} from "../lib/businessHours";
import { useI18n } from "../composables/useI18n";
import { useTranslate } from "../composables/useTranslate";
import { LOCALE_OPTIONS, normalizeLocale } from "../i18n/config";
import { profileApi } from "../lib/onboardingApi";
import { useLocaleStore } from "../stores/locale";
import { useTenantStore } from "../stores/tenant";
import { useToastStore } from "../stores/toast";

const props = defineProps({
  standalone: {
    type: Boolean,
    default: false,
  },
});

// Curated IANA timezones for the business-hours schedule (owners can request more).
const TIMEZONE_OPTIONS = [
  "Africa/Casablanca", "UTC", "Europe/Paris", "Europe/Madrid", "Europe/London",
  "Africa/Cairo", "Africa/Tunis", "Africa/Algiers", "Asia/Dubai", "America/New_York",
];

const form = reactive({
  tagline: "",
  tagline_i18n: {},
  description: "",
  description_i18n: {},
  business_hours: "",
  business_hours_i18n: {},
  business_hours_schedule: createEmptyBusinessHoursSchedule(),
  timezone: "",
  phone: "",
  whatsapp: "",
  delivery_fee: "0",
  vat_rate: "0",
  vat_label: "",
  address: "",
  address_i18n: {},
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
const { translating, translateError, translateField } = useTranslate();

const runTranslate = async (fieldKey, formField, targetLocale) => {
  const sourceText = localizedFieldValue(formField, defaultContentLocale.value);
  if (!sourceText.trim()) return;
  const result = await translateField(fieldKey, sourceText, targetLocale, defaultContentLocale.value);
  if (result) {
    onLocalizedFieldInput(formField, targetLocale, result);
  } else if (translateError.value === "notConfigured") {
    toast.show(t("common.translateErrorNotConfigured"), "error");
  } else if (translateError.value) {
    toast.show(t("common.translateErrorGeneric"), "error");
  }
};

const canWhatsappOrder = computed(() => tenant.entitlements?.can_whatsapp_order === true);
const isBrowseOnlyPlan = computed(() => tenant.isBrowseOnlyPlan === true);
const introText = computed(() =>
  isBrowseOnlyPlan.value
    ? t("stepBrand.introBrowseOnly")
    : t("stepBrand.introDefault")
);
const whatsappLabel = computed(() => (canWhatsappOrder.value ? t("stepBrand.whatsappOrdering") : t("stepBrand.whatsappContact")));
const maxTranslationLocales = computed(() =>
  Math.max(0, Number(tenant.entitlements?.max_languages || 1) - 1)
);
const defaultContentLocale = computed(() => normalizeLocale(form.language || "en"));
const contentLocaleCodes = computed(() => {
  const fallback = defaultContentLocale.value;
  const secondary = LOCALE_OPTIONS.filter((option) => option.code !== fallback)
    .slice(0, maxTranslationLocales.value)
    .map((option) => option.code);
  return [fallback, ...secondary];
});
const fieldLocales = reactive({
  tagline: defaultContentLocale.value,
  address: defaultContentLocale.value,
  description: defaultContentLocale.value,
});
const businessHoursEdited = ref(false);

const inputClass = (field) =>
  `w-full rounded-xl bg-slate-900 px-3 py-2 border ${errors.value[field] ? "border-red-400" : "border-slate-700"}`;

const fieldError = (field) => (errors.value[field] ? String(errors.value[field]) : "");
const sectionPanelClass = computed(() =>
  props.standalone
    ? "ui-panel space-y-4 p-5"
    : "ui-panel space-y-4 p-5"
);
const clearField = (field) => {
  if (errors.value[field]) {
    const next = { ...errors.value };
    delete next[field];
    errors.value = next;
  }
};

const normalizeI18nMap = (value) => {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  const out = {};
  Object.entries(value).forEach(([rawLocale, rawText]) => {
    const locale = normalizeLocale(rawLocale);
    const text = String(rawText || "").trim();
    if (!locale || !text) return;
    out[locale] = text;
  });
  return out;
};

const i18nFieldName = (field) => `${field}_i18n`;

const localizedFieldValue = (field, localeCode) => {
  const localeCodeNormalized = normalizeLocale(localeCode || defaultContentLocale.value);
  if (localeCodeNormalized === defaultContentLocale.value) return String(form[field] || "");
  const map = form[i18nFieldName(field)];
  if (!map || typeof map !== "object") return "";
  return String(map[localeCodeNormalized] || "");
};

const onLocalizedFieldInput = (field, localeCode, value) => {
  const localeCodeNormalized = normalizeLocale(localeCode || defaultContentLocale.value);
  const nextValue = String(value || "");
  if (localeCodeNormalized === defaultContentLocale.value) {
    form[field] = nextValue;
  } else {
    if (!form[i18nFieldName(field)] || typeof form[i18nFieldName(field)] !== "object") {
      form[i18nFieldName(field)] = {};
    }
    if (nextValue.trim()) {
      form[i18nFieldName(field)][localeCodeNormalized] = nextValue;
    } else {
      delete form[i18nFieldName(field)][localeCodeNormalized];
    }
  }
  clearField(field);
};

const localeChipLabel = (localeCode) => {
  const locale = LOCALE_OPTIONS.find((item) => item.code === normalizeLocale(localeCode));
  return locale?.nativeLabel || String(localeCode || "").toUpperCase();
};

const weekdayOptions = computed(() =>
  WEEKDAY_KEYS.map((day) => ({
    key: day,
    label: t(`stepBrand.weekdays.${day}`),
  }))
);

const hasStructuredBusinessHours = computed(() =>
  WEEKDAY_KEYS.some((day) => Boolean(form.business_hours_schedule?.[day]?.enabled))
);

const buildLocalizedBusinessHours = () => buildBusinessHoursSummaries(form.business_hours_schedule);

const businessHoursPreview = computed(() => {
  const summaries = buildLocalizedBusinessHours();
  const summary = summaries[defaultContentLocale.value] || "";
  if (summary) return summary;
  return localizedFieldValue("business_hours", defaultContentLocale.value);
});
const openBusinessDaysCount = computed(() =>
  WEEKDAY_KEYS.filter((day) => Boolean(form.business_hours_schedule?.[day]?.enabled)).length
);

const markBusinessHoursEdited = () => {
  businessHoursEdited.value = true;
  clearField("business_hours");
  clearField("business_hours_schedule");
};

const toggleBusinessHoursDay = (day) => {
  const current = form.business_hours_schedule?.[day];
  if (!current) return;
  current.enabled = !current.enabled;
  markBusinessHoursEdited();
};

const syncFieldLocales = () => {
  const allowed = new Set(contentLocaleCodes.value);
  const fallback = defaultContentLocale.value;
  ["tagline", "address", "description"].forEach((field) => {
    if (!allowed.has(fieldLocales[field])) {
      fieldLocales[field] = fallback;
    }
  });
};

watch([contentLocaleCodes, defaultContentLocale], syncFieldLocales, { immediate: true });

const load = async () => {
  try {
    const data = await profileApi.get();
    Object.assign(form, data || {});
    form.tagline_i18n = normalizeI18nMap(data?.tagline_i18n);
    form.address_i18n = normalizeI18nMap(data?.address_i18n);
    form.description_i18n = normalizeI18nMap(data?.description_i18n);
    form.business_hours_i18n = normalizeI18nMap(data?.business_hours_i18n);
    form.business_hours_schedule = normalizeBusinessHoursSchedule(data?.business_hours_schedule);
    businessHoursEdited.value = false;
  } catch {
    status.value = t("stepBrand.statusLoadFailed");
  }
};

const saveAndNext = async () => {
  saving.value = true;
  status.value = "";
  errors.value = {};
  try {
    const normalizedSchedule = normalizeBusinessHoursSchedule(form.business_hours_schedule);
    const payload = {
      ...form,
      business_hours_schedule: hasEnabledBusinessHours(normalizedSchedule) || businessHoursEdited.value ? normalizedSchedule : {},
    };

    if (businessHoursEdited.value || hasStructuredBusinessHours.value) {
      const summaries = buildLocalizedBusinessHours();
      payload.business_hours = summaries[defaultContentLocale.value] || "";
      payload.business_hours_i18n = Object.fromEntries(
        Object.entries(summaries).filter(([localeCode, summary]) => localeCode !== defaultContentLocale.value && summary)
      );
    }

    const saved = await profileApi.save(payload);
    tenant.mergeProfile(saved);
    locale.setTenantDefault(saved?.language || form.language);
    status.value = t("stepBrand.statusSaved");
    toast.show(t("stepBrand.toastSaved"), "success");
    businessHoursEdited.value = false;
    if (!props.standalone) {
      emit("next");
    }
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

