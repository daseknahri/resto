<template>
  <section class="space-y-8 px-4 py-8 md:space-y-10 md:py-12">
    <div v-if="leadSuccess" class="ui-panel flex items-center justify-between border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-emerald-100">
      <span>{{ t("home.leadSuccess") }}</span>
      <button class="text-sm underline" @click="dismiss">{{ t("home.dismiss") }}</button>
    </div>

    <div class="ui-glass relative overflow-hidden">
      <div class="pointer-events-none absolute -right-12 -top-12 h-56 w-56 rounded-full bg-amber-400/10 blur-3xl"></div>
      <div class="pointer-events-none absolute -left-10 bottom-0 h-56 w-56 rounded-full bg-teal-400/10 blur-3xl"></div>
      <div class="relative grid gap-8 p-5 sm:p-6 md:grid-cols-[1.3fr,1fr] md:p-10">
        <div class="space-y-6">
          <div class="ui-chip w-fit">
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
            <RouterLink to="/menu" class="ui-btn-outline ui-touch-target">{{ t("home.viewLiveDemo") }}</RouterLink>
            <RouterLink v-if="session.canEditTenantMenu" to="/owner" class="ui-btn-outline ui-touch-target">{{ t("home.openWorkspace") }}</RouterLink>
          </div>

          <div class="grid gap-3 pt-2 sm:grid-cols-3">
            <article class="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-3">
              <p class="text-xs uppercase tracking-[0.2em] text-slate-500">{{ t("home.stats.launchTime") }}</p>
              <p class="mt-1 text-xl font-semibold text-white">{{ t("home.stats.launchTimeValue") }}</p>
            </article>
            <article class="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-3">
              <p class="text-xs uppercase tracking-[0.2em] text-slate-500">{{ t("home.stats.interfaces") }}</p>
              <p class="mt-1 text-xl font-semibold text-white">{{ t("home.stats.interfacesValue") }}</p>
            </article>
            <article class="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-3">
              <p class="text-xs uppercase tracking-[0.2em] text-slate-500">{{ t("home.stats.tierReady") }}</p>
              <p class="mt-1 text-xl font-semibold text-white">{{ t("home.stats.tierReadyValue") }}</p>
            </article>
          </div>
        </div>

        <div class="grid gap-3 self-end">
          <article class="ui-panel bg-slate-950/65 p-4">
            <p class="ui-kicker">{{ t("home.interfaces.landing") }}</p>
            <p class="mt-2 text-lg font-semibold text-white">{{ t("home.interfaces.landingTitle") }}</p>
            <p class="mt-1 text-sm text-slate-400">{{ t("home.interfaces.landingText") }}</p>
          </article>
          <article class="ui-panel bg-slate-950/65 p-4">
            <p class="ui-kicker">{{ t("home.interfaces.owner") }}</p>
            <p class="mt-2 text-lg font-semibold text-white">{{ t("home.interfaces.ownerTitle") }}</p>
            <p class="mt-1 text-sm text-slate-400">{{ t("home.interfaces.ownerText") }}</p>
          </article>
          <article class="ui-panel bg-slate-950/65 p-4">
            <p class="ui-kicker">{{ t("home.interfaces.customer") }}</p>
            <p class="mt-2 text-lg font-semibold text-white">{{ t("home.interfaces.customerTitle") }}</p>
            <p class="mt-1 text-sm text-slate-400">{{ t("home.interfaces.customerText") }}</p>
          </article>
        </div>
      </div>
    </div>

    <section class="grid gap-3 md:gap-4 md:grid-cols-3">
      <article class="ui-panel p-5">
        <p class="ui-kicker">{{ t("home.phases.phase1") }}</p>
        <p class="mt-2 text-xl font-semibold text-white">{{ t("home.phases.phase1Title") }}</p>
        <p class="mt-1 text-sm text-slate-300">{{ t("home.phases.phase1Text") }}</p>
      </article>
      <article class="ui-panel p-5">
        <p class="ui-kicker">{{ t("home.phases.phase2") }}</p>
        <p class="mt-2 text-xl font-semibold text-white">{{ t("home.phases.phase2Title") }}</p>
        <p class="mt-1 text-sm text-slate-300">{{ t("home.phases.phase2Text") }}</p>
      </article>
      <article class="ui-panel p-5">
        <p class="ui-kicker">{{ t("home.phases.phase3") }}</p>
        <p class="mt-2 text-xl font-semibold text-white">{{ t("home.phases.phase3Title") }}</p>
        <p class="mt-1 text-sm text-slate-300">{{ t("home.phases.phase3Text") }}</p>
      </article>
    </section>

    <section id="plans" class="space-y-4">
      <div class="flex items-center justify-between gap-2">
        <h2 class="ui-display text-2xl font-semibold text-white">{{ t("home.plansTitle") }}</h2>
      </div>
      <div class="grid gap-4 md:grid-cols-3">
        <article
          v-for="plan in plans"
          :key="plan.code"
          class="rounded-2xl border p-5 shadow-lg shadow-black/20"
          :class="plan.recommended ? 'border-[var(--color-secondary)] bg-[var(--color-secondary)]/12' : 'border-slate-700/60 bg-slate-900/55'"
        >
          <div class="flex items-center justify-between">
            <p class="text-lg font-semibold text-white">{{ plan.name }}</p>
            <span
              class="rounded-full px-2 py-1 text-[11px] font-semibold"
              :class="plan.available ? 'bg-emerald-400/90 text-emerald-950' : 'bg-slate-700 text-slate-200'"
            >
              {{ plan.available ? t("common.available") : t("common.soon") }}
            </span>
          </div>
          <p class="mt-1 text-sm text-slate-300">{{ plan.description }}</p>
          <ul class="mt-4 space-y-1 text-sm text-slate-300">
            <li v-for="line in plan.features" :key="line">- {{ line }}</li>
          </ul>
          <RouterLink
            :to="{ name: 'lead', query: { plan: plan.code } }"
            class="mt-5 inline-flex rounded-full border px-4 py-2 text-sm font-semibold transition-colors ui-touch-target"
            :class="plan.recommended ? 'border-[var(--color-secondary)] text-[var(--color-secondary)]' : 'border-slate-700 text-slate-100'"
          >
            {{ plan.cta }}
          </RouterLink>
        </article>
      </div>
    </section>

    <section class="ui-glass p-6 md:p-8">
      <div class="grid gap-6 md:grid-cols-[1.2fr,1fr] md:items-center">
        <div class="space-y-2">
          <p class="text-sm text-slate-400">{{ t("home.readyEyebrow") }}</p>
          <h3 class="ui-display text-3xl font-semibold text-white">{{ t("home.readyTitle") }}</h3>
          <p class="text-slate-300">{{ t("home.readyText") }}</p>
        </div>
        <div class="flex flex-wrap gap-3">
          <RouterLink to="/get-started" class="ui-btn-primary ui-touch-target">{{ t("home.submitLead") }}</RouterLink>
          <RouterLink to="/contact" class="ui-btn-outline ui-touch-target">{{ t("home.talkSupport") }}</RouterLink>
        </div>
      </div>
    </section>
  </section>
</template>

<script setup>
import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "../composables/useI18n";
import { useSessionStore } from "../stores/session";

const route = useRoute();
const router = useRouter();
const session = useSessionStore();
const { t } = useI18n();
const leadSuccess = ref(route.query.lead === "success");

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
