<template>
  <div class="ui-shell ui-safe-bottom">
    <div class="mx-auto max-w-6xl space-y-6 px-4 py-6">
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
                class="ui-journey-step ui-reveal shrink-0 flex min-w-[200px] items-start gap-3 lg:min-w-0 disabled:cursor-not-allowed disabled:opacity-50"
                :data-active="current === step.id ? 'true' : undefined"
                :data-complete="(step.id < current || (published && step.id === steps.length)) ? 'true' : undefined"
                :data-locked="!canNavigateTo(step.id) ? 'true' : undefined"
                :aria-current="current === step.id ? 'step' : undefined"
                :aria-disabled="!canNavigateTo(step.id) ? 'true' : undefined"
                :disabled="!canNavigateTo(step.id)"
                :aria-label="`${step.id}. ${t(step.titleKey)}`"
                :title="!canNavigateTo(step.id) ? t('onboardingWizard.stepLockedHint') : undefined"
                :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
                @click="goToStep(step.id)"
              >
                <!-- Step number badge -->
                <span
                  class="ui-step-badge shrink-0"
                  :data-complete="(step.id < current || (published && step.id === steps.length)) ? 'true' : undefined"
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
                      class="ui-chip shrink-0 text-emerald-300"
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
        <section class="min-w-0 space-y-3">
          <!-- Terse SR announcement on step change; the broad aria-live was
               removed so the whole step isn't re-read on every navigation. -->
          <span class="sr-only" role="status" aria-live="polite" aria-atomic="true">{{ stepAnnouncement }}</span>
          <div ref="stepPanelRef" tabindex="-1" class="ui-panel p-4 focus:outline-none">
            <KeepAlive>
              <component :is="currentComponent" @next="next" @back="back" @publish="publish" @can-publish="onCanPublish" />
            </KeepAlive>
          </div>
          <!-- Footer hint -->
          <p class="ui-subtle px-1 text-xs text-slate-500">
            {{ t("onboardingWizard.footerHint") }}
          </p>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { onBeforeRouteLeave, useRouter } from "vue-router";
import { useI18n } from "../composables/useI18n";
import { steps } from "../onboarding/steps";
import StepStart from "./StepStart.vue";
import StepBrand from "./StepBrand.vue";
import StepCategories from "./StepCategories.vue";
import StepDishes from "./StepDishes.vue";
import StepTheme from "./StepTheme.vue";
import StepPublish from "./StepPublish.vue";
import { useTenantStore } from "../stores/tenant";

const current = ref(1);
// Highest step the user has legitimately reached (advanced into via `next` or a
// restored session). Forward jumps past `highestCompleted + 1` are blocked; going
// back to any already-reached step stays free.
const highestCompleted = ref(1);
// Mirrors StepPublish's canPublish (menu non-empty + brand/profile essentials);
// gates the final Publish step so an unfinished setup can't be reached via the nav.
const canPublishStep = ref(false);
const published = ref(false);
const tenant = useTenantStore();
const router = useRouter();
const { t } = useI18n();
const mapping = {
  1: StepStart,
  2: StepBrand,
  3: StepCategories,
  4: StepDishes,
  5: StepTheme,
  6: StepPublish,
};
const currentComponent = computed(() => mapping[current.value]);
const progressPct = computed(() => Math.round((current.value / steps.length) * 100));

// ── Step-change a11y: terse SR announcement + move focus to the new step ──────
// Replaces the old broad aria-live on the step <main>, which re-read the entire
// step (heading + every field) on each navigation.
const stepPanelRef = ref(null);
const stepAnnouncement = computed(() => {
  const step = steps[current.value - 1];
  if (!step) return "";
  return t("onboardingWizard.stepAnnounce", { n: current.value, total: steps.length, title: t(step.titleKey) });
});
const stepStorageKey = computed(() => {
  const slug = tenant.meta?.slug || "tenant";
  return `resto:onboarding-step:v2:${slug}`;
});

// A step is reachable if it has already been completed, is the next one in line,
// or is an earlier (backward) step. The final Publish step additionally requires
// the menu to be publish-ready so an empty setup can't be jumped to via the nav.
const canNavigateTo = (stepId) => {
  if (stepId <= highestCompleted.value) return true;
  if (stepId > highestCompleted.value + 1) return false;
  if (stepId === steps.length && !canPublishStep.value) return false;
  return true;
};

const goToStep = (stepId) => {
  if (!canNavigateTo(stepId)) return;
  current.value = stepId;
};

const next = () => {
  if (current.value < steps.length) {
    current.value += 1;
    if (current.value > highestCompleted.value) highestCompleted.value = current.value;
  }
};
const back = () => {
  if (current.value > 1) current.value -= 1;
};

const onCanPublish = (value) => {
  canPublishStep.value = value === true;
};

const publish = async () => {
  published.value = true;
  current.value = steps.length;
  highestCompleted.value = steps.length;
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
    // A previously-reached step is legitimately reachable again on resume.
    if (parsed > highestCompleted.value) highestCompleted.value = parsed;
  }
};

const persistStep = () => {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(stepStorageKey.value, String(current.value));
};

onMounted(async () => {
  if (!tenant.meta) await tenant.fetchMeta();
  published.value = tenant.meta?.profile?.is_menu_published === true;
  // An already-published tenant has legitimately completed every step.
  if (published.value) {
    highestCompleted.value = steps.length;
    canPublishStep.value = true;
  }
  restoreStep();
});

watch(current, persistStep);
// Move keyboard/SR focus to the new step's panel so navigation lands the user
// at the start of the new content (WCAG 2.4.3) instead of leaving focus behind.
watch(current, () => {
  nextTick(() => stepPanelRef.value?.focus());
});
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
