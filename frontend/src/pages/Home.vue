<template>
  <section class="space-y-8 px-4 py-8 md:space-y-10 md:py-12">
    <div v-if="leadSuccess" class="ui-panel flex items-center justify-between border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-emerald-100">
      <span>{{ t("home.leadSuccess") }}</span>
      <button class="text-sm underline" @click="dismiss">{{ t("home.dismiss") }}</button>
    </div>

    <div class="ui-hero-stage">
      <div class="pointer-events-none absolute -right-16 -top-16 h-64 w-64 rounded-full bg-amber-400/12 blur-3xl"></div>
      <div class="pointer-events-none absolute -left-16 bottom-0 h-64 w-64 rounded-full bg-teal-400/14 blur-3xl"></div>
      <div class="pointer-events-none absolute inset-x-10 top-24 h-px bg-gradient-to-r from-transparent via-white/10 to-transparent"></div>
      <div class="relative grid gap-8 p-5 sm:p-6 md:grid-cols-[1.22fr,0.98fr] md:p-10">
        <div class="space-y-6">
          <div class="ui-chip-strong w-fit">
            <span class="h-1.5 w-1.5 rounded-full bg-emerald-400"></span>
            {{ t("home.heroBadge") }}
            <span class="text-emerald-300">{{ t("home.heroLive") }}</span>
          </div>

          <div class="space-y-3">
            <h1 class="ui-display max-w-2xl text-4xl font-semibold leading-tight text-white md:text-5xl">
              {{ t("home.heroTitle") }}
            </h1>
            <p class="max-w-2xl text-slate-300 md:text-lg">
              {{ t("home.heroSubtitle") }}
            </p>
          </div>

          <div class="flex flex-wrap gap-2 pt-1 sm:gap-3">
            <RouterLink to="/get-started" class="ui-btn-primary ui-touch-target">{{ t("home.getMyMenu") }}</RouterLink>
            <RouterLink to="/demo" class="ui-btn-outline ui-touch-target">{{ t("home.viewLiveDemo") }}</RouterLink>
            <RouterLink v-if="session.canEditTenantMenu" to="/owner" class="ui-btn-outline ui-touch-target">{{ t("home.openWorkspace") }}</RouterLink>
          </div>

          <div class="grid gap-3 pt-2 sm:grid-cols-3">
            <article class="ui-metric-card">
              <p class="text-xs uppercase tracking-[0.2em] text-slate-500">{{ t("home.stats.launchTime") }}</p>
              <p class="mt-1 text-xl font-semibold text-white">{{ t("home.stats.launchTimeValue") }}</p>
            </article>
            <article class="ui-metric-card">
              <p class="text-xs uppercase tracking-[0.2em] text-slate-500">{{ t("home.stats.interfaces") }}</p>
              <p class="mt-1 text-xl font-semibold text-white">{{ t("home.stats.interfacesValue") }}</p>
            </article>
            <article class="ui-metric-card">
              <p class="text-xs uppercase tracking-[0.2em] text-slate-500">{{ t("home.stats.tierReady") }}</p>
              <p class="mt-1 text-xl font-semibold text-white">{{ t("home.stats.tierReadyValue") }}</p>
            </article>
          </div>

          <div class="ui-section-band space-y-4 p-4 md:p-5">
            <div class="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p class="ui-kicker">{{ t("home.readyEyebrow") }}</p>
                <p class="mt-2 text-lg font-semibold text-white">{{ t("home.readyTitle") }}</p>
              </div>
              <div class="ui-chip-strong">
                <AppIcon name="check" class="h-3.5 w-3.5" />
                <span>{{ t("common.available") }}</span>
              </div>
            </div>
            <div class="grid gap-3 md:grid-cols-3">
              <article class="ui-admin-subcard space-y-2 p-3">
                <div class="ui-chip w-fit">
                  <AppIcon name="home" class="h-3.5 w-3.5" />
                  <span>{{ t("home.interfaces.landing") }}</span>
                </div>
                <p class="text-sm font-semibold text-white">{{ t("home.interfaces.landingTitle") }}</p>
                <p class="text-sm text-slate-400">{{ t("home.interfaces.landingText") }}</p>
              </article>
              <article class="ui-admin-subcard space-y-2 p-3">
                <div class="ui-chip w-fit">
                  <AppIcon name="settings" class="h-3.5 w-3.5" />
                  <span>{{ t("home.interfaces.owner") }}</span>
                </div>
                <p class="text-sm font-semibold text-white">{{ t("home.interfaces.ownerTitle") }}</p>
                <p class="text-sm text-slate-400">{{ t("home.interfaces.ownerText") }}</p>
              </article>
              <article class="ui-admin-subcard space-y-2 p-3">
                <div class="ui-chip w-fit">
                  <AppIcon name="menu" class="h-3.5 w-3.5" />
                  <span>{{ t("home.interfaces.customer") }}</span>
                </div>
                <p class="text-sm font-semibold text-white">{{ t("home.interfaces.customerTitle") }}</p>
                <p class="text-sm text-slate-400">{{ t("home.interfaces.customerText") }}</p>
              </article>
            </div>
          </div>
        </div>

        <div class="grid gap-3 self-end">
          <article class="ui-spotlight-card p-5">
            <div class="flex items-center justify-between gap-3">
              <div>
                <p class="ui-kicker">{{ t("common.demo") }}</p>
                <p class="mt-2 text-lg font-semibold text-white">doro.menu.kepoli.com</p>
              </div>
              <span class="ui-chip-strong shrink-0">{{ t("home.heroLive") }}</span>
            </div>
            <p class="mt-3 text-sm text-slate-300">{{ t("home.interfaces.customerText") }}</p>
            <div class="mt-4 flex flex-wrap gap-2">
              <a :href="demoUrl" target="_blank" rel="noopener noreferrer" class="ui-btn-primary inline-flex items-center gap-2 ui-touch-target">
                <AppIcon name="menu" class="h-4 w-4" />
                <span>{{ t("home.viewLiveDemo") }}</span>
              </a>
              <RouterLink to="/demo" class="ui-btn-outline inline-flex items-center gap-2 ui-touch-target">
                <AppIcon name="eye" class="h-4 w-4" />
                <span>{{ t("common.demo") }}</span>
              </RouterLink>
            </div>
            <div class="mt-4 grid gap-2 sm:grid-cols-2">
              <div class="ui-admin-subcard p-3">
                <p class="ui-stat-label">{{ t("home.stats.launchTime") }}</p>
                <p class="mt-2 text-sm font-semibold text-white">{{ t("home.stats.launchTimeValue") }}</p>
              </div>
              <div class="ui-admin-subcard p-3">
                <p class="ui-stat-label">{{ t("home.stats.interfaces") }}</p>
                <p class="mt-2 text-sm font-semibold text-white">{{ t("home.stats.interfacesValue") }}</p>
              </div>
            </div>
          </article>
          <article class="ui-command-deck p-5">
            <div class="flex items-start justify-between gap-3">
              <div class="space-y-2">
                <p class="ui-kicker">{{ t("home.plansTitle") }}</p>
                <p class="text-lg font-semibold text-white">{{ t("home.plans.basic.name") }}</p>
                <p class="text-sm text-slate-300">{{ t("home.plans.basic.description") }}</p>
              </div>
              <div class="ui-chip-strong shrink-0">{{ t("common.available") }}</div>
            </div>
            <div class="mt-4 space-y-2">
              <div class="ui-admin-subcard p-3 text-sm text-slate-300">{{ t("home.plans.basic.feature1") }}</div>
              <div class="ui-admin-subcard p-3 text-sm text-slate-300">{{ t("home.plans.basic.feature2") }}</div>
              <div class="ui-admin-subcard p-3 text-sm text-slate-300">{{ t("home.plans.basic.feature3") }}</div>
            </div>
          </article>
        </div>
      </div>
    </div>

    <section class="grid gap-4 lg:grid-cols-[1.15fr,0.85fr]">
      <article class="ui-glass p-5 md:p-6">
        <div class="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div class="space-y-2">
            <p class="ui-kicker">{{ t("home.readyEyebrow") }}</p>
            <h2 class="ui-display text-2xl font-semibold text-white md:text-3xl">{{ t("home.readyTitle") }}</h2>
            <p class="max-w-2xl text-sm text-slate-300 md:text-base">{{ t("home.readyText") }}</p>
          </div>
          <div class="flex flex-wrap gap-2">
            <span class="ui-chip">
              <AppIcon name="phone" class="h-3.5 w-3.5" />
              <span>{{ t("home.stats.launchTimeValue") }}</span>
            </span>
            <span class="ui-chip">
              <AppIcon name="settings" class="h-3.5 w-3.5" />
              <span>{{ t("home.stats.interfacesValue") }}</span>
            </span>
            <span class="ui-chip">
              <AppIcon name="check" class="h-3.5 w-3.5" />
              <span>{{ t("home.stats.tierReadyValue") }}</span>
            </span>
          </div>
        </div>

        <div class="mt-5 grid gap-3 md:grid-cols-3">
          <article class="ui-admin-subcard space-y-2">
            <div class="ui-chip w-fit">
              <AppIcon name="home" class="h-3.5 w-3.5" />
              <span>{{ t("home.phases.phase1") }}</span>
            </div>
            <p class="mt-2 text-lg font-semibold text-white">{{ t("home.phases.phase1Title") }}</p>
            <p class="mt-1 text-sm text-slate-300">{{ t("home.phases.phase1Text") }}</p>
          </article>
          <article class="ui-admin-subcard space-y-2">
            <div class="ui-chip w-fit">
              <AppIcon name="settings" class="h-3.5 w-3.5" />
              <span>{{ t("home.phases.phase2") }}</span>
            </div>
            <p class="mt-2 text-lg font-semibold text-white">{{ t("home.phases.phase2Title") }}</p>
            <p class="mt-1 text-sm text-slate-300">{{ t("home.phases.phase2Text") }}</p>
          </article>
          <article class="ui-admin-subcard space-y-2">
            <div class="ui-chip w-fit">
              <AppIcon name="menu" class="h-3.5 w-3.5" />
              <span>{{ t("home.phases.phase3") }}</span>
            </div>
            <p class="mt-2 text-lg font-semibold text-white">{{ t("home.phases.phase3Title") }}</p>
            <p class="mt-1 text-sm text-slate-300">{{ t("home.phases.phase3Text") }}</p>
          </article>
        </div>
      </article>

      <article class="ui-command-deck p-5 md:p-6">
        <div class="space-y-2">
          <p class="ui-kicker">{{ t("home.plansTitle") }}</p>
          <h3 class="ui-display text-2xl font-semibold text-white">{{ t("home.plans.basic.name") }}</h3>
          <p class="text-sm text-slate-300">{{ t("home.plans.basic.description") }}</p>
        </div>

        <div class="mt-4 grid gap-3 sm:grid-cols-3">
          <article class="ui-admin-subcard p-3">
            <p class="ui-stat-label">{{ t("home.stats.launchTime") }}</p>
            <p class="mt-2 text-sm font-semibold text-white">{{ t("home.stats.launchTimeValue") }}</p>
          </article>
          <article class="ui-admin-subcard p-3">
            <p class="ui-stat-label">{{ t("home.stats.interfaces") }}</p>
            <p class="mt-2 text-sm font-semibold text-white">{{ t("home.stats.interfacesValue") }}</p>
          </article>
          <article class="ui-admin-subcard p-3">
            <p class="ui-stat-label">{{ t("home.stats.tierReady") }}</p>
            <p class="mt-2 text-sm font-semibold text-white">{{ t("home.stats.tierReadyValue") }}</p>
          </article>
        </div>

        <div class="mt-5 flex flex-wrap gap-2">
          <RouterLink to="/get-started" class="ui-btn-primary ui-touch-target">{{ t("home.getMyMenu") }}</RouterLink>
          <RouterLink to="/contact" class="ui-btn-outline ui-touch-target">{{ t("home.talkSupport") }}</RouterLink>
        </div>
      </article>
    </section>

    <section id="plans" class="space-y-4">
      <div class="ui-section-band flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div class="space-y-2">
          <p class="ui-kicker">{{ t("home.heroBadge") }}</p>
          <h2 class="ui-display text-2xl font-semibold text-white md:text-3xl">{{ t("home.plansTitle") }}</h2>
          <p class="max-w-2xl text-sm text-slate-300 md:text-base">{{ t("home.heroSubtitle") }}</p>
        </div>
        <div class="grid gap-3 sm:grid-cols-3 md:min-w-[360px]">
          <article class="ui-admin-subcard">
            <p class="ui-stat-label">{{ t("home.stats.tierReady") }}</p>
            <p class="mt-2 text-lg font-semibold text-white">{{ t("home.stats.tierReadyValue") }}</p>
          </article>
          <article class="ui-admin-subcard">
            <p class="ui-stat-label">{{ t("home.stats.launchTime") }}</p>
            <p class="mt-2 text-lg font-semibold text-white">{{ t("home.stats.launchTimeValue") }}</p>
          </article>
          <article class="ui-admin-subcard">
            <p class="ui-stat-label">{{ t("home.stats.interfaces") }}</p>
            <p class="mt-2 text-lg font-semibold text-white">{{ t("home.stats.interfacesValue") }}</p>
          </article>
        </div>
      </div>
      <div class="grid gap-4 md:grid-cols-3">
        <article
          v-for="plan in plans"
          :key="plan.code"
          class="relative overflow-hidden rounded-[1.8rem] border p-5 shadow-lg shadow-black/20 transition duration-300"
          :class="plan.recommended ? 'border-[var(--color-secondary)] bg-[var(--color-secondary)]/12' : 'border-slate-700/60 bg-slate-900/55'"
        >
          <div class="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/20 to-transparent"></div>
          <div v-if="plan.recommended" class="pointer-events-none absolute right-5 top-5 rounded-full border border-[var(--color-secondary)]/40 bg-[var(--color-secondary)]/15 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--color-secondary)]">
            {{ t("common.available") }}
          </div>
          <div class="flex items-center justify-between">
            <div>
              <p class="ui-kicker">{{ t("common.plan") }}</p>
              <p class="mt-2 text-lg font-semibold text-white">{{ plan.name }}</p>
            </div>
            <span
              class="rounded-full px-2 py-1 text-[11px] font-semibold"
              :class="plan.available ? 'bg-emerald-400/90 text-emerald-950' : 'bg-slate-700 text-slate-200'"
            >
              {{ plan.available ? t("common.available") : t("common.soon") }}
            </span>
          </div>
          <p class="mt-3 text-sm text-slate-300">{{ plan.description }}</p>
          <ul class="mt-5 space-y-2 text-sm text-slate-300">
            <li v-for="(line, featureIndex) in plan.features" :key="line" class="flex items-start gap-2">
              <span class="mt-1 inline-block h-1.5 w-1.5 rounded-full bg-[var(--color-secondary)]"></span>
              <span class="flex-1">{{ line }}</span>
              <span class="text-[10px] uppercase tracking-[0.14em] text-slate-500">{{ String(featureIndex + 1).padStart(2, "0") }}</span>
            </li>
          </ul>
          <RouterLink
            :to="{ name: 'lead', query: { plan: plan.code } }"
            class="mt-6 inline-flex rounded-full border px-4 py-2 text-sm font-semibold transition-colors ui-touch-target"
            :class="plan.recommended ? 'border-[var(--color-secondary)] text-[var(--color-secondary)]' : 'border-slate-700 text-slate-100'"
          >
            {{ plan.cta }}
          </RouterLink>
        </article>
      </div>
    </section>

    <section class="ui-glass p-6 md:p-8">
      <div class="grid gap-6 md:grid-cols-[1.18fr,0.82fr] md:items-center">
        <div class="space-y-4">
          <div class="space-y-2">
            <p class="ui-kicker">{{ t("home.readyEyebrow") }}</p>
            <h3 class="ui-display text-3xl font-semibold text-white">{{ t("home.readyTitle") }}</h3>
            <p class="text-slate-300">{{ t("home.readyText") }}</p>
          </div>
          <div class="grid gap-3 sm:grid-cols-3">
            <article class="ui-metric-card">
              <p class="ui-stat-label">{{ t("home.stats.launchTime") }}</p>
              <p class="mt-2 text-lg font-semibold text-white">{{ t("home.stats.launchTimeValue") }}</p>
            </article>
            <article class="ui-metric-card">
              <p class="ui-stat-label">{{ t("home.stats.interfaces") }}</p>
              <p class="mt-2 text-lg font-semibold text-white">{{ t("home.stats.interfacesValue") }}</p>
            </article>
            <article class="ui-metric-card">
              <p class="ui-stat-label">{{ t("home.stats.tierReady") }}</p>
              <p class="mt-2 text-lg font-semibold text-white">{{ t("home.stats.tierReadyValue") }}</p>
            </article>
          </div>
        </div>
        <div class="ui-command-deck p-5">
          <div class="space-y-2">
            <p class="ui-kicker">{{ t("common.demo") }}</p>
            <p class="text-lg font-semibold text-white">doro.menu.kepoli.com</p>
            <p class="text-sm text-slate-300">{{ t("home.interfaces.customerText") }}</p>
          </div>
          <div class="mt-4 flex flex-wrap gap-3">
            <RouterLink to="/get-started" class="ui-btn-primary ui-touch-target">{{ t("home.submitLead") }}</RouterLink>
            <RouterLink to="/contact" class="ui-btn-outline ui-touch-target">{{ t("home.talkSupport") }}</RouterLink>
            <a :href="demoUrl" target="_blank" rel="noopener noreferrer" class="ui-btn-outline ui-touch-target inline-flex items-center gap-2">
              <AppIcon name="eye" class="h-4 w-4" />
              <span>{{ t("home.viewLiveDemo") }}</span>
            </a>
          </div>
        </div>
      </div>
    </section>
  </section>
</template>

<script setup>
import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import AppIcon from "../components/AppIcon.vue";
import { useI18n } from "../composables/useI18n";
import { useSessionStore } from "../stores/session";

const route = useRoute();
const router = useRouter();
const session = useSessionStore();
const { t } = useI18n();
const leadSuccess = ref(route.query.lead === "success");
const demoUrl = import.meta.env.VITE_PUBLIC_DEMO_URL || "https://doro.menu.kepoli.com/menu";

const plans = computed(() => [
  {
    code: "basic",
    name: t("home.plans.basic.name"),
    description: t("home.plans.basic.description"),
    features: [t("home.plans.basic.feature1"), t("home.plans.basic.feature2"), t("home.plans.basic.feature3")],
    available: true,
    recommended: true,
    cta: t("home.plans.basic.cta"),
  },
  {
    code: "growth",
    name: t("home.plans.growth.name"),
    description: t("home.plans.growth.description"),
    features: [t("home.plans.growth.feature1"), t("home.plans.growth.feature2"), t("home.plans.growth.feature3")],
    available: false,
    recommended: false,
    cta: t("home.plans.growth.cta"),
  },
  {
    code: "pro",
    name: t("home.plans.pro.name"),
    description: t("home.plans.pro.description"),
    features: [t("home.plans.pro.feature1"), t("home.plans.pro.feature2"), t("home.plans.pro.feature3")],
    available: false,
    recommended: false,
    cta: t("home.plans.pro.cta"),
  },
]);

const dismiss = () => {
  leadSuccess.value = false;
  const q = { ...route.query };
  delete q.lead;
  router.replace({ query: q });
};
</script>
