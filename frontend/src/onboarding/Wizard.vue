<template>
  <div class="min-h-screen bg-slate-950 px-4 py-6 text-slate-50 ui-safe-bottom">
    <div class="mx-auto max-w-6xl space-y-6">
      <!-- Page header -->
      <header class="ui-hero-ribbon ui-reveal px-4 py-3.5 md:px-5 md:py-4">
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div class="min-w-0">
            <p class="ui-kicker">{{ t("onboardingWizard.kicker") }}</p>
            <h1 class="ui-display text-2xl font-semibold leading-tight text-white md:text-3xl">
              {{ t("onboardingWizard.title") }}
            </h1>
          </div>
          <div class="flex shrink-0 flex-wrap items-center gap-1.5">
            <span class="ui-data-strip tabular-nums">
              {{ t("onboardingWizard.stepProgress", { current, total: steps.length, pct: progressPct }) }}
            </span>
            <span class="ui-data-strip">
              {{ published ? t("onboardingWizard.published") : t("onboardingWizard.draft") }}
            </span>
          </div>
        </div>
        <!-- Progress bar -->
        <div class="ui-journey-progress mt-3" role="progressbar" :aria-valuenow="progressPct" aria-valuemin="0" aria-valuemax="100" :aria-label="t('onboardingWizard.stepProgress', { current, total: steps.length, pct: progressPct })">
          <span :style="{ width: `${progressPct}%` }" />
        </div>
      </header>

      <div class="grid min-w-0 gap-6 lg:grid-cols-[320px,1fr]">
        <!-- Step navigation -->
        <aside class="min-w-0">
          <nav class="ui-journey-rail" :aria-label="t('onboardingWizard.kicker')">
            <!-- Mobile: horizontal scroll; desktop: vertical flex -->
            <div class="ui-scroll-row max-w-full lg:flex lg:flex-col lg:gap-2.5 lg:overflow-visible lg:pb-0">
              <button
                v-for="(step, index) in steps"
                :key="step.id"
                type="button"
                class="ui-journey-step ui-reveal flex min-w-[200px] items-start gap-3 lg:min-w-0"
                :data-active="current === step.id ? 'true' : undefined"
                :data-complete="(step.id < current || (published && step.id === steps.length)) ? 'true' : undefined"
                :aria-pressed="current === step.id"
                :aria-label="`${step.id}. ${t(step.titleKey)}`"
                :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
                @click="current = step.id"
              >
                <!-- Step number badge -->
                <span
                  class="ui-step-badge shrink-0"
                  :class="step.id < current || (published && step.id === steps.length) ? 'border-emerald-500/40 bg-emerald-500/15 !text-emerald-300' : ''"
                  aria-hidden="true"
                >
                  {{ step.id }}
                </span>
                <!-- Step label + description -->
                <div class="min-w-0 space-y-0.5 text-start">
                  <div class="flex flex-wrap items-center gap-1.5">
                    <p
                      class="truncate font-semibold"
                      :class="current === step.id ? 'text-white' : 'text-slate-300'"
                    >
                      {{ t(step.titleKey) }}
                    </p>
                    <span
                      v-if="step.id < current || (published && step.id === steps.length)"
                      class="shrink-0 rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-emerald-300"
                    >
                      {{ t("common.saved") }}
                    </span>
                  </div>
                  <p class="truncate text-xs text-slate-500">{{ t(step.descriptionKey) }}</p>
                </div>
              </button>
            </div>
          </nav>
        </aside>

        <!-- Active step content -->
        <main class="min-w-0 space-y-3">
          <div class="ui-section-band p-1.5 md:p-2">
            <KeepAlive>
              <component :is="currentComponent" @next="next" @back="back" @publish="publish" />
            </KeepAlive>
          </div>
          <!-- Footer hint -->
          <p class="ui-subtle px-1 text-xs text-slate-500">
            {{ t("onboardingWizard.footerHint") }}
          </p>
        </main>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { onBeforeRouteLeave, useRouter } from "vue-router";
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

// ── Unsaved-changes guard ────────────────────────────────────────────────────
// Warn before browser tab close / hard navigation.
const beforeUnloadHandler = (e) => {
  if (published.value) return; // wizard completed — no need to warn
  e.preventDefault();
  e.returnValue = ""; // required for Chrome
};

onMounted(() => window.addEventListener("beforeunload", beforeUnloadHandler));
onUnmounted(() => window.removeEventListener("beforeunload", beforeUnloadHandler));

// Warn before in-app (Vue Router) navigation away from the wizard.
onBeforeRouteLeave(() => {
  if (published.value) return true;
  return window.confirm(t("onboardingWizard.leaveConfirm"));
});
</script>
