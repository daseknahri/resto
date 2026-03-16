<template>
  <div class="min-h-screen bg-slate-950 px-4 py-6 text-slate-50 ui-safe-bottom">
    <div class="mx-auto max-w-6xl space-y-6">
      <header class="ui-fade-up space-y-2 px-1">
        <p class="ui-kicker">{{ t("onboardingWizard.kicker") }}</p>
        <h1 class="ui-display text-3xl font-semibold text-white md:text-4xl">{{ t("onboardingWizard.title") }}</h1>
        <div class="flex flex-wrap items-center gap-2">
          <span class="ui-data-strip">{{ t("onboardingWizard.stepProgress", { current, total: steps.length, pct: progressPct }) }}</span>
          <span class="ui-data-strip">{{ published ? t("onboardingWizard.published") : t("onboardingWizard.draft") }}</span>
        </div>
      </header>

      <div class="grid min-w-0 gap-6 lg:grid-cols-[340px,1fr]">
        <aside class="ui-workspace-stage min-w-0 p-4">
          <div class="ui-scroll-row max-w-full lg:flex lg:flex-col lg:gap-3 lg:overflow-visible lg:pb-0">
            <button
              v-for="step in steps"
              :key="step.id"
              type="button"
              class="group flex min-w-[220px] items-start gap-3 rounded-[1.25rem] border p-3 text-left transition lg:min-w-0"
              :class="current === step.id ? 'border-amber-400/40 bg-amber-500/10 shadow-lg shadow-amber-500/10' : 'border-slate-800/80 bg-slate-950/45 hover:border-slate-700/80'"
              @click="current = step.id"
            >
              <div
                class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border text-sm font-semibold"
                :class="current === step.id ? 'border-amber-300/60 bg-amber-400/20 text-amber-200' : 'border-slate-700 text-slate-400 group-hover:text-slate-200'"
              >
                {{ step.id }}
              </div>
              <div class="space-y-1">
                <div class="flex items-center gap-2">
                  <p class="font-semibold" :class="current === step.id ? 'text-white' : 'text-slate-300'">{{ t(step.titleKey) }}</p>
                  <span v-if="step.id < current || (published && step.id === steps.length)" class="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-emerald-300">
                    {{ t("common.saved") }}
                  </span>
                </div>
              </div>
            </button>
          </div>
        </aside>

        <main class="min-w-0 space-y-4">
          <div class="ui-section-band p-1.5 md:p-2">
            <KeepAlive>
              <component :is="currentComponent" @next="next" @back="back" @publish="publish" />
            </KeepAlive>
          </div>
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

const restoreStep = () => {
  if (typeof window === "undefined") return;
  const raw = window.localStorage.getItem(stepStorageKey.value);
  const parsed = Number.parseInt(raw || "1", 10);
  if (!Number.isFinite(parsed)) return;
  if (parsed >= 1 && parsed <= steps.length) {
    current.value = parsed;
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
