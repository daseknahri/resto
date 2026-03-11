<template>
  <div class="min-h-screen bg-slate-950 text-slate-50 px-4 py-6 ui-safe-bottom">
    <div class="mx-auto max-w-6xl space-y-6">
      <header class="ui-panel-soft flex flex-wrap items-center justify-between gap-3 p-4 ui-fade-up">
        <div>
          <p class="ui-kicker">{{ t("onboardingWizard.kicker") }}</p>
          <h1 class="ui-display text-2xl font-semibold text-white">{{ t("onboardingWizard.title") }}</h1>
        </div>
        <div class="flex items-center gap-2 text-sm text-slate-300">
          <span class="h-2 w-2 rounded-full" :class="published ? 'bg-emerald-400' : 'bg-amber-300'"></span>
          {{ published ? t("onboardingWizard.published") : t("onboardingWizard.draft") }}
        </div>
        <div class="w-full space-y-1">
          <div class="h-1.5 overflow-hidden rounded-full bg-slate-800">
            <div class="h-full rounded-full bg-[var(--color-secondary)] transition-all duration-300" :style="{ width: `${progressPct}%` }"></div>
          </div>
          <p class="text-xs text-slate-500">{{ t("onboardingWizard.stepProgress", { current, total: steps.length, pct: progressPct }) }}</p>
        </div>
      </header>

      <div class="grid min-w-0 gap-6 lg:grid-cols-[320px,1fr]">
        <aside class="min-w-0 rounded-2xl border border-slate-800 bg-slate-900/70 p-4">
          <div v-if="showResumeHint" class="rounded-xl border border-emerald-500/40 bg-emerald-500/10 p-3 text-xs text-emerald-200">
            <p>{{ t("onboardingWizard.resumedFromStep", { current }) }}</p>
            <button class="mt-2 text-emerald-300 underline underline-offset-2 hover:text-emerald-200" @click="restartWizard">
              {{ t("onboardingWizard.startFromStepOne") }}
            </button>
          </div>

          <div class="ui-scroll-row mt-4 max-w-full lg:mt-0 lg:flex lg:flex-col lg:gap-3 lg:overflow-visible lg:pb-0">
            <div
              v-for="step in steps"
              :key="step.id"
              class="flex min-w-[190px] items-start gap-3 rounded-xl border border-slate-800 bg-slate-950/35 p-3 lg:min-w-0"
            >
              <div
                class="h-8 w-8 shrink-0 flex items-center justify-center rounded-full border"
                :class="current === step.id ? 'border-[var(--color-secondary)] bg-[var(--color-secondary)]/20 text-[var(--color-secondary)]' : 'border-slate-700 text-slate-400'"
              >
                {{ step.id }}
              </div>
              <div>
                <p class="font-semibold" :class="current === step.id ? 'text-white' : 'text-slate-300'">{{ t(step.titleKey) }}</p>
                <p class="text-xs text-slate-400">{{ t(step.descriptionKey) }}</p>
              </div>
            </div>
          </div>
        </aside>

        <main class="min-w-0 space-y-4">
          <KeepAlive>
            <component :is="currentComponent" @next="next" @back="back" @publish="publish" />
          </KeepAlive>
          <p class="text-xs text-slate-500">{{ t("onboardingWizard.footerHint") }}</p>
        </main>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "../composables/useI18n";
import { steps } from "../onboarding/steps";
import StepBrand from "./StepBrand.vue";
import StepCategories from "./StepCategories.vue";
import StepDishes from "./StepDishes.vue";
import StepTheme from "./StepTheme.vue";
import StepPublish from "./StepPublish.vue";
import { useTenantStore } from "../stores/tenant";

const current = ref(1);
const published = ref(false);
const showResumeHint = ref(false);
const tenant = useTenantStore();
const router = useRouter();
const { t } = useI18n();
const mapping = {
  1: StepBrand,
  2: StepCategories,
  3: StepDishes,
  4: StepTheme,
  5: StepPublish,
};
const currentComponent = computed(() => mapping[current.value]);
const progressPct = computed(() => Math.round((current.value / steps.length) * 100));
const stepStorageKey = computed(() => {
  const slug = tenant.meta?.slug || "tenant";
  return `resto:onboarding-step:${slug}`;
});

const next = () => {
  if (current.value < steps.length) current.value += 1;
};
const back = () => {
  if (current.value > 1) current.value -= 1;
};

const publish = async () => {
  published.value = true;
  current.value = steps.length;
  persistStep();
  await router.push({ name: "owner-launch" });
};

const restartWizard = () => {
  current.value = 1;
  showResumeHint.value = false;
  persistStep();
};

const restoreStep = () => {
  if (typeof window === "undefined") return;
  const raw = window.localStorage.getItem(stepStorageKey.value);
  const parsed = Number.parseInt(raw || "1", 10);
  if (!Number.isFinite(parsed)) return;
  if (parsed >= 1 && parsed <= steps.length) {
    current.value = parsed;
    showResumeHint.value = parsed > 1;
  }
};

const persistStep = () => {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(stepStorageKey.value, String(current.value));
};

onMounted(async () => {
  if (!tenant.meta) await tenant.fetchMeta();
  published.value = tenant.meta?.profile?.is_menu_published === true;
  restoreStep();
});

watch(current, persistStep);
watch(stepStorageKey, () => {
  restoreStep();
  persistStep();
});
</script>
