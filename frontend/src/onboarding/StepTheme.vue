<template>
  <div class="space-y-4">
    <section v-if="!standalone" class="ui-panel space-y-3 p-5 ui-reveal">
      <h2 class="text-xl font-semibold text-white">{{ t("stepTheme.title") }}</h2>
      <p class="ui-subtle">{{ t("stepTheme.description") }}</p>
    </section>

    <section :class="sectionPanelClass" class="ui-reveal" :style="{ '--ui-delay': '28ms' }">
      <div class="space-y-1">
        <p class="ui-section-kicker">{{ t("stepTheme.title") }}</p>
        <component :is="standalone ? 'h2' : 'h3'" class="text-lg font-semibold text-white">{{ t("stepTheme.appearanceSection") }}</component>
      </div>

      <div class="flex flex-wrap gap-1.5">
        <span class="ui-chip">
          <span class="inline-block h-2.5 w-2.5 shrink-0 rounded-full border border-white/10" :style="{ background: form.primary_color }" aria-hidden="true"></span>
          {{ t("stepTheme.primaryColor") }}
        </span>
        <span class="ui-chip">
          <span class="inline-block h-2.5 w-2.5 shrink-0 rounded-full border border-white/10" :style="{ background: form.secondary_color }" aria-hidden="true"></span>
          {{ t("stepTheme.secondaryColor") }}
        </span>
        <span class="ui-chip">
          {{ form.logo_url ? t("stepTheme.logoUploaded") : t("stepTheme.uploadLogo") }}
        </span>
        <span class="ui-chip">
          {{ form.hero_url ? t("stepTheme.heroUploaded") : t("stepTheme.uploadHeroImage") }}
        </span>
      </div>

      <div class="grid gap-4 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)]">
        <div class="space-y-4 rounded-2xl border border-slate-800 bg-slate-950/45 p-4">
          <div class="grid gap-3 sm:grid-cols-2">
            <label class="space-y-2 text-sm text-slate-200">
              <span>{{ t("stepTheme.primaryColor") }}</span>
              <div class="flex items-center gap-3 rounded-xl border border-slate-700 bg-slate-900/80 px-3 py-2">
                <input
                  v-model="form.primary_color"
                  type="color"
                  class="ui-touch-target h-10 w-12 rounded-lg border border-slate-700 bg-slate-900 p-1"
                  :aria-invalid="errors.primary_color ? 'true' : undefined"
                  aria-describedby="step-theme-primary-error"
                  @input="clearField('primary_color')"
                />
                <span class="text-xs font-semibold uppercase tracking-[0.2em] tabular-nums text-slate-400">{{ form.primary_color }}</span>
              </div>
              <p v-if="errors.primary_color" id="step-theme-primary-error" role="alert" class="text-xs text-red-300">{{ errors.primary_color }}</p>
            </label>

            <label class="space-y-2 text-sm text-slate-200">
              <span>{{ t("stepTheme.secondaryColor") }}</span>
              <div class="flex items-center gap-3 rounded-xl border border-slate-700 bg-slate-900/80 px-3 py-2">
                <input
                  v-model="form.secondary_color"
                  type="color"
                  class="ui-touch-target h-10 w-12 rounded-lg border border-slate-700 bg-slate-900 p-1"
                  :aria-invalid="errors.secondary_color ? 'true' : undefined"
                  aria-describedby="step-theme-secondary-error"
                  @input="clearField('secondary_color')"
                />
                <span class="text-xs font-semibold uppercase tracking-[0.2em] tabular-nums text-slate-400">{{ form.secondary_color }}</span>
              </div>
              <p v-if="errors.secondary_color" id="step-theme-secondary-error" role="alert" class="text-xs text-red-300">{{ errors.secondary_color }}</p>
            </label>
          </div>

          <div class="space-y-3 rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
            <div class="space-y-1">
              <p class="text-sm font-semibold text-slate-100">{{ t("stepTheme.themePresets") }}</p>
              <p class="text-xs text-slate-500">{{ t("stepTheme.presetsHint") }}</p>
            </div>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="preset in themePresets"
                :key="preset.id"
                type="button"
                class="ui-touch-target ui-press inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-secondary)]"
                :class="isPresetActive(preset) ? 'border-brand-secondary bg-brand-secondary/10 text-brand-secondary' : 'border-slate-700 text-slate-200 hover:border-brand-secondary'"
                :aria-pressed="isPresetActive(preset)"
                @click="applyThemePreset(preset)"
              >
                <span class="inline-block h-2 w-2 shrink-0 rounded-full border border-white/10" :style="{ background: preset.primary }" aria-hidden="true"></span>
                <span class="inline-block h-2 w-2 shrink-0 rounded-full border border-white/10" :style="{ background: preset.secondary }" aria-hidden="true"></span>
                {{ preset.label }}
              </button>
            </div>
          </div>
        </div>

        <div class="rounded-2xl border border-slate-800 bg-slate-900/80 p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]" :style="previewStyle">
          <div class="space-y-5">
            <div class="space-y-1">
              <p class="ui-section-kicker text-slate-300">{{ t("stepTheme.preview") }}</p>
              <h4 class="text-xl font-semibold text-white">{{ previewTitle }}</h4>
            </div>

            <div class="flex flex-wrap items-center gap-2">
              <img
                v-if="form.logo_url"
                :src="form.logo_url"
                :alt="t('stepTheme.logoPreviewAlt')"
                loading="eager"
                decoding="async"
                class="h-14 w-14 rounded-2xl border border-white/10 object-cover shadow-lg"
                @error="$event.target.style.display='none'"
              />
              <span class="ui-chip inline-flex items-center gap-1.5">
                <span class="inline-block h-2.5 w-2.5 shrink-0 rounded-full border border-white/10" :style="{ background: form.primary_color }" aria-hidden="true"></span>
                <span class="tabular-nums">{{ form.primary_color }}</span>
              </span>
              <span class="ui-chip inline-flex items-center gap-1.5">
                <span class="inline-block h-2.5 w-2.5 shrink-0 rounded-full border border-white/10" :style="{ background: form.secondary_color }" aria-hidden="true"></span>
                <span class="tabular-nums">{{ form.secondary_color }}</span>
              </span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section :class="sectionPanelClass" class="ui-reveal" :style="{ '--ui-delay': '56ms' }">
      <div class="space-y-1">
        <p class="ui-section-kicker">{{ t("stepTheme.mediaSection") }}</p>
        <component :is="standalone ? 'h2' : 'h3'" class="text-lg font-semibold text-white">{{ t("stepTheme.mediaSectionTitle") }}</component>
      </div>

      <div class="grid gap-4 lg:grid-cols-2">
        <div class="space-y-2 text-sm text-slate-200">
          <span>{{ t("stepTheme.logoUrl") }}</span>
          <div
            class="space-y-3 rounded-2xl border border-dashed p-4 transition-colors"
            :class="draggingLogo ? 'border-brand-secondary bg-brand-secondary/10' : 'border-slate-700 bg-slate-900/40'"
            aria-describedby="step-theme-logo-hint"
            @dragenter="draggingLogo = true"
            @dragleave="draggingLogo = false"
            @dragover="preventDropDefaults"
            @drop="dropLogo"
          >
            <div class="flex flex-wrap items-center gap-2">
              <label class="ui-touch-target cursor-pointer rounded-full border border-slate-700 px-3 py-1.5 text-xs text-slate-100 transition-colors hover:border-brand-secondary focus-within:border-brand-secondary focus-within:outline focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-[var(--color-secondary)]">
                {{ uploadingLogo ? t("stepTheme.uploadingProgress", { progress: logoProgress }) : t("stepTheme.uploadLogo") }}
                <input
                  type="file"
                  accept="image/*"
                  class="hidden"
                  :disabled="uploadingLogo"
                  :aria-invalid="errors.logo_url ? 'true' : undefined"
                  aria-describedby="step-theme-logo-error"
                  @change="uploadLogo"
                />
              </label>
              <button
                v-if="form.logo_url"
                class="ui-touch-target ui-press rounded-full border border-slate-700 px-3 py-1.5 text-xs text-slate-100 transition-colors hover:border-red-400 hover:text-red-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-400"
                type="button"
                @click="clearLogo"
              >
                {{ t("stepTheme.removeLogo") }}
              </button>
            </div>

            <div class="flex items-center gap-3">
              <img
                v-if="form.logo_url"
                :src="form.logo_url"
                :alt="t('stepTheme.logoPreviewAlt')"
                loading="eager"
                decoding="async"
                class="h-14 w-14 rounded-2xl border border-slate-700 object-cover"
                @error="$event.target.style.display='none'"
              />
              <div class="space-y-1">
                <p id="step-theme-logo-hint" class="text-xs text-slate-300">{{ t("stepTheme.logoDropHint") }}</p>
                <p class="text-[11px] text-slate-500">{{ t("stepTheme.acceptedFormats") }}</p>
              </div>
            </div>

            <div
              v-if="uploadingLogo"
              class="h-1.5 w-full overflow-hidden rounded bg-slate-800"
              role="progressbar"
              :aria-valuenow="logoProgress"
              aria-valuemin="0"
              aria-valuemax="100"
              :aria-label="t('stepTheme.uploadingProgress', { progress: logoProgress })"
            >
              <div class="h-full bg-emerald-400 transition-all duration-150" :style="{ width: `${logoProgress}%` }"></div>
            </div>
          </div>
          <p v-if="errors.logo_url" id="step-theme-logo-error" role="alert" class="text-xs text-red-300">{{ errors.logo_url }}</p>
        </div>

        <div class="space-y-2 text-sm text-slate-200">
          <span>{{ t("stepTheme.heroImageUrl") }}</span>
          <div
            class="space-y-3 rounded-2xl border border-dashed p-4 transition-colors"
            :class="draggingHero ? 'border-brand-secondary bg-brand-secondary/10' : 'border-slate-700 bg-slate-900/40'"
            aria-describedby="step-theme-hero-hint"
            @dragenter="draggingHero = true"
            @dragleave="draggingHero = false"
            @dragover="preventDropDefaults"
            @drop="dropHero"
          >
            <div class="flex flex-wrap items-center gap-2">
              <label class="ui-touch-target cursor-pointer rounded-full border border-slate-700 px-3 py-1.5 text-xs text-slate-100 transition-colors hover:border-brand-secondary focus-within:border-brand-secondary focus-within:outline focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-[var(--color-secondary)]">
                {{ uploadingHero ? t("stepTheme.uploadingProgress", { progress: heroProgress }) : t("stepTheme.uploadHeroImage") }}
                <input
                  type="file"
                  accept="image/*"
                  class="hidden"
                  :disabled="uploadingHero"
                  :aria-invalid="errors.hero_url ? 'true' : undefined"
                  aria-describedby="step-theme-hero-error"
                  @change="uploadHero"
                />
              </label>
              <button
                v-if="form.hero_url"
                class="ui-touch-target ui-press rounded-full border border-slate-700 px-3 py-1.5 text-xs text-slate-100 transition-colors hover:border-red-400 hover:text-red-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-400"
                type="button"
                @click="clearHero"
              >
                {{ t("stepTheme.removeHero") }}
              </button>
            </div>

            <div class="space-y-2">
              <div v-if="form.hero_url" class="overflow-hidden rounded-2xl border border-slate-700">
                <img :src="form.hero_url" :alt="t('stepTheme.heroPreviewAlt')" loading="lazy" decoding="async" class="h-40 w-full object-cover" @error="$event.target.style.display='none'" />
              </div>
              <p id="step-theme-hero-hint" class="text-xs text-slate-300">{{ t("stepTheme.heroDropHint") }}</p>
              <p class="text-[11px] text-slate-500">{{ t("stepTheme.acceptedFormats") }}</p>
            </div>

            <div
              v-if="uploadingHero"
              class="h-1.5 w-full overflow-hidden rounded bg-slate-800"
              role="progressbar"
              :aria-valuenow="heroProgress"
              aria-valuemin="0"
              aria-valuemax="100"
              :aria-label="t('stepTheme.uploadingProgress', { progress: heroProgress })"
            >
              <div class="h-full bg-emerald-400 transition-all duration-150" :style="{ width: `${heroProgress}%` }"></div>
            </div>
          </div>
          <p v-if="errors.hero_url" id="step-theme-hero-error" role="alert" class="text-xs text-red-300">{{ errors.hero_url }}</p>
        </div>
      </div>
    </section>

    <section :class="sectionPanelClass" class="ui-reveal" :style="{ '--ui-delay': '84ms' }">
      <div v-if="errors.non_field_errors" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
        <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
        <p class="flex-1 text-sm text-red-300">{{ errors.non_field_errors }}</p>
      </div>

      <div class="flex flex-wrap items-center gap-3">
        <button class="ui-btn-primary ui-touch-target px-5 py-2.5 text-sm" :disabled="saving || uploadingHero || uploadingLogo" @click="saveAndNext">
          {{ saving ? t("common.saving") : standalone ? t("common.save") : t("common.saveAndNext") }}
        </button>
        <button v-if="!standalone" class="ui-btn-outline ui-touch-target px-5 py-2.5 text-sm" @click="$emit('back')">{{ t("common.previous") }}</button>
        <p class="text-sm text-slate-400">{{ status }}</p>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { profileApi, uploadApi } from "../lib/onboardingApi";
import { THEME_PRESETS } from "./starterTemplates";
import { useI18n } from "../composables/useI18n";
import { useThemeStore } from "../stores/theme";
import { useToastStore } from "../stores/toast";

const form = reactive({
  primary_color: "#0F766E",
  secondary_color: "#F59E0B",
  logo_url: "",
  hero_url: "",
});
const saving = ref(false);
const uploadingHero = ref(false);
const uploadingLogo = ref(false);
const heroProgress = ref(0);
const logoProgress = ref(0);
const draggingHero = ref(false);
const draggingLogo = ref(false);
const pendingCleanup = ref([]);
const status = ref("");
const errors = reactive({});
const theme = useThemeStore();
const toast = useToastStore();
const { t } = useI18n();
const props = defineProps({
  standalone: {
    type: Boolean,
    default: false,
  },
});
const emit = defineEmits(["next", "back"]);
const themePresets = THEME_PRESETS;

const previewStyle = computed(() => ({
  backgroundImage: form.hero_url ? `linear-gradient(180deg, rgba(0,0,0,0.6), rgba(0,0,0,0.9)), url(${form.hero_url})` : undefined,
  backgroundSize: "cover",
  backgroundPosition: "center",
  borderColor: form.primary_color,
}));
const sectionPanelClass = computed(() => "ui-panel space-y-4 p-5");

const previewTitle = computed(() => t("stepTheme.previewTitle"));
const isManagedUpload = (value = "") => /\/uploads\//.test(String(value));
const cleanupManagedUpload = async (value) => {
  if (!isManagedUpload(value)) return;
  try {
    await uploadApi.removeImage(value);
  } catch {
    // Non-blocking cleanup.
  }
};

const queueCleanup = (value) => {
  if (!isManagedUpload(value)) return;
  if (pendingCleanup.value.includes(value)) return;
  pendingCleanup.value.push(value);
};

const flushPendingCleanup = async () => {
  if (!pendingCleanup.value.length) return;
  const stillReferenced = new Set([form.logo_url, form.hero_url].filter(Boolean));
  const queue = [...pendingCleanup.value];
  pendingCleanup.value = [];
  for (const value of queue) {
    if (stillReferenced.has(value)) continue;
    await cleanupManagedUpload(value);
  }
};

const clearField = (field) => {
  if (errors[field]) delete errors[field];
};

const applyThemePreset = (preset) => {
  if (!preset) return;
  form.primary_color = preset.primary;
  form.secondary_color = preset.secondary;
  clearField("primary_color");
  clearField("secondary_color");
  status.value = t("stepTheme.presetSelected", { preset: preset.label });
};

const isPresetActive = (preset) =>
  preset &&
  String(form.primary_color || "").toUpperCase() === String(preset.primary || "").toUpperCase() &&
  String(form.secondary_color || "").toUpperCase() === String(preset.secondary || "").toUpperCase();

const load = async () => {
  try {
    const data = await profileApi.get();
    if (data) Object.assign(form, data);
  } catch {
    status.value = t("common.loadFailed");
  }
};

const saveAndNext = async () => {
  saving.value = true;
  status.value = "";
  Object.keys(errors).forEach((k) => delete errors[k]);
  try {
    await profileApi.save(form);
    await flushPendingCleanup();
    theme.apply(form);
    status.value = t("common.saved");
    toast.show(t("stepTheme.toastSaved"), "success");
    if (!props.standalone) emit("next");
  } catch (e) {
    status.value = t("common.saveFailed");
    Object.assign(errors, e?.fieldErrors || {});
    toast.show(e?.message || t("stepTheme.toastSaveFailed"), "error");
  } finally {
    saving.value = false;
  }
};

const preventDropDefaults = (event) => {
  event.preventDefault();
  event.stopPropagation();
};

const fileFromEvent = (event) => {
  if (!event) return null;
  if (event.dataTransfer?.files?.length) return event.dataTransfer.files[0];
  if (event.target?.files?.length) return event.target.files[0];
  return null;
};

const uploadLogoFile = async (file) => {
  if (!file) return;
  uploadingLogo.value = true;
  logoProgress.value = 0;
  clearField("logo_url");
  const old = form.logo_url;
  try {
    const result = await uploadApi.image(file, {
      variant: "logo",
      onProgress: (pct) => {
        logoProgress.value = pct;
      },
    });
    form.logo_url = result.url || "";
    queueCleanup(old);
    toast.show(t("stepTheme.logoUploaded"), "success");
  } catch (e) {
    Object.assign(errors, e?.fieldErrors || {});
    toast.show(e?.message || t("stepTheme.logoUploadFailed"), "error");
  } finally {
    uploadingLogo.value = false;
    draggingLogo.value = false;
  }
};

const uploadHeroFile = async (file) => {
  if (!file) return;
  uploadingHero.value = true;
  heroProgress.value = 0;
  clearField("hero_url");
  const old = form.hero_url;
  try {
    const result = await uploadApi.image(file, {
      variant: "hero",
      onProgress: (pct) => {
        heroProgress.value = pct;
      },
    });
    form.hero_url = result.url || "";
    queueCleanup(old);
    toast.show(t("stepTheme.heroUploaded"), "success");
  } catch (e) {
    Object.assign(errors, e?.fieldErrors || {});
    toast.show(e?.message || t("stepTheme.heroUploadFailed"), "error");
  } finally {
    uploadingHero.value = false;
    draggingHero.value = false;
  }
};

const uploadLogo = async (event) => {
  const file = fileFromEvent(event);
  if (event?.target) event.target.value = "";
  await uploadLogoFile(file);
};

const uploadHero = async (event) => {
  const file = fileFromEvent(event);
  if (event?.target) event.target.value = "";
  await uploadHeroFile(file);
};

const dropLogo = async (event) => {
  preventDropDefaults(event);
  draggingLogo.value = false;
  await uploadLogoFile(fileFromEvent(event));
};

const dropHero = async (event) => {
  preventDropDefaults(event);
  draggingHero.value = false;
  await uploadHeroFile(fileFromEvent(event));
};

const clearHero = async () => {
  const old = form.hero_url;
  form.hero_url = "";
  queueCleanup(old);
};

const clearLogo = async () => {
  const old = form.logo_url;
  form.logo_url = "";
  queueCleanup(old);
};

onMounted(load);

const standalone = computed(() => props.standalone);
</script>

