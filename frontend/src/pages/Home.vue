<template>
  <main id="main-content" class="space-y-10 px-4 py-10 md:space-y-14 md:py-14">
    <Transition name="ui-fade">
      <div v-if="leadSuccess" role="status" class="ui-panel flex items-center justify-between border-emerald-500/30 bg-emerald-500/10 px-5 py-3.5 text-emerald-100">
        <span class="text-sm font-medium">{{ t("home.leadSuccess") }}</span>
        <button class="ui-press ui-touch-target inline-flex items-center px-2 text-sm font-semibold underline underline-offset-2 opacity-80 hover:opacity-100" :aria-label="t('home.dismissAriaLabel')" @click="dismiss">{{ t("home.dismiss") }}</button>
      </div>
    </Transition>

    <div class="ui-hero-stage ui-reveal">
      <div class="pointer-events-none absolute -right-16 -top-16 h-72 w-72 rounded-full bg-amber-400/12 blur-3xl" aria-hidden="true"></div>
      <div class="pointer-events-none absolute -left-16 bottom-0 h-72 w-72 rounded-full bg-teal-400/14 blur-3xl" aria-hidden="true"></div>
      <div class="pointer-events-none absolute inset-x-10 top-24 h-px bg-gradient-to-r from-transparent via-white/10 to-transparent" aria-hidden="true"></div>
      <div class="relative grid gap-10 p-6 sm:p-8 md:grid-cols-[1.22fr,0.98fr] md:gap-8 md:p-12">
        <div class="space-y-7">
          <div class="ui-chip-strong w-fit">
            <span class="h-1.5 w-1.5 rounded-full bg-emerald-400"></span>
            {{ t("home.heroBadge") }}
            <span class="text-emerald-300">{{ t("home.heroLive") }}</span>
          </div>

          <div class="space-y-4">
            <h1 class="ui-display max-w-2xl text-4xl font-bold leading-[1.1] tracking-tight text-white md:text-5xl lg:text-6xl">
              {{ t("home.heroTitle") }}
            </h1>
            <p class="max-w-xl text-base leading-relaxed text-slate-300 md:text-lg">
              {{ t("home.heroSubtitle") }}
            </p>
          </div>

          <div class="flex flex-wrap gap-3 pt-1">
            <RouterLink to="/get-started" class="ui-btn-primary ui-touch-target">{{ t("home.getMyMenu") }}</RouterLink>
            <RouterLink to="/demo" class="ui-btn-outline ui-touch-target">{{ t("home.viewLiveDemo") }}</RouterLink>
            <RouterLink v-if="session.canEditTenantMenu" to="/owner" class="ui-btn-outline ui-touch-target">{{ t("home.openWorkspace") }}</RouterLink>
          </div>

          <!-- Customer / marketplace entry point -->
          <div class="space-y-3 pt-1">
            <div class="flex items-center gap-3" aria-hidden="true">
              <div class="h-px flex-1 bg-slate-800" />
              <span class="text-xs font-medium tracking-wide text-slate-500">{{ t("home.customerDivider") }}</span>
              <div class="h-px flex-1 bg-slate-800" />
            </div>
            <RouterLink
              to="/order"
              class="ui-press inline-flex w-full items-center justify-center gap-2.5 rounded-full border border-[var(--color-secondary)]/40 bg-[var(--color-secondary)]/8 px-5 py-3 text-sm font-semibold text-[var(--color-secondary)] transition-colors hover:border-[var(--color-secondary)]/70 hover:bg-[var(--color-secondary)]/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/60 sm:w-auto"
            >
              <span aria-hidden="true">🍽️</span>
              <span>{{ t("home.browseRestaurants") }}</span>
            </RouterLink>
          </div>

          <div class="grid gap-3 pt-1 sm:grid-cols-3">
            <article class="ui-metric-card ui-reveal" :style="{ '--ui-delay': '0ms' }">
              <p class="ui-stat-label">{{ t("home.stats.launchTime") }}</p>
              <p class="mt-1.5 text-2xl font-bold tabular-nums text-white">{{ t("home.stats.launchTimeValue") }}</p>
            </article>
            <article class="ui-metric-card ui-reveal" :style="{ '--ui-delay': '56ms' }">
              <p class="ui-stat-label">{{ t("home.stats.interfaces") }}</p>
              <p class="mt-1.5 text-2xl font-bold tabular-nums text-white">{{ t("home.stats.interfacesValue") }}</p>
            </article>
            <article class="ui-metric-card ui-reveal" :style="{ '--ui-delay': '112ms' }">
              <p class="ui-stat-label">{{ t("home.stats.tierReady") }}</p>
              <p class="mt-1.5 text-2xl font-bold tabular-nums text-white">{{ t("home.stats.tierReadyValue") }}</p>
            </article>
          </div>

          <div class="ui-section-band space-y-5 p-5 md:p-6">
            <div class="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p class="ui-kicker">{{ t("home.readyEyebrow") }}</p>
                <p class="mt-2 text-lg font-semibold tracking-tight text-white">{{ t("home.readyTitle") }}</p>
              </div>
              <div class="ui-chip-strong">
                <AppIcon name="check" class="h-3.5 w-3.5" aria-hidden="true" />
                <span>{{ t("common.available") }}</span>
              </div>
            </div>
            <div class="grid gap-3 md:grid-cols-3">
              <article class="ui-admin-subcard space-y-2.5 p-4">
                <div class="ui-chip w-fit">
                  <AppIcon name="home" class="h-3.5 w-3.5" aria-hidden="true" />
                  <span>{{ t("home.interfaces.landing") }}</span>
                </div>
                <p class="text-sm font-semibold leading-snug text-white">{{ t("home.interfaces.landingTitle") }}</p>
                <p class="text-sm leading-relaxed text-slate-400">{{ t("home.interfaces.landingText") }}</p>
              </article>
              <article class="ui-admin-subcard space-y-2.5 p-4">
                <div class="ui-chip w-fit">
                  <AppIcon name="settings" class="h-3.5 w-3.5" aria-hidden="true" />
                  <span>{{ t("home.interfaces.owner") }}</span>
                </div>
                <p class="text-sm font-semibold leading-snug text-white">{{ t("home.interfaces.ownerTitle") }}</p>
                <p class="text-sm leading-relaxed text-slate-400">{{ t("home.interfaces.ownerText") }}</p>
              </article>
              <article class="ui-admin-subcard space-y-2.5 p-4">
                <div class="ui-chip w-fit">
                  <AppIcon name="menu" class="h-3.5 w-3.5" aria-hidden="true" />
                  <span>{{ t("home.interfaces.customer") }}</span>
                </div>
                <p class="text-sm font-semibold leading-snug text-white">{{ t("home.interfaces.customerTitle") }}</p>
                <p class="text-sm leading-relaxed text-slate-400">{{ t("home.interfaces.customerText") }}</p>
              </article>
            </div>
          </div>
        </div>

        <div class="grid gap-4 self-end">
          <article class="ui-spotlight-card p-6 ui-reveal" :style="{ '--ui-delay': '84ms' }">
            <div class="flex items-start justify-between gap-3">
              <div>
                <p class="ui-kicker">{{ t("common.demo") }}</p>
                <p class="mt-2 text-lg font-semibold tracking-tight text-white">{{ brandDomain }}</p>
              </div>
              <span class="ui-chip-strong shrink-0">{{ t("home.heroLive") }}</span>
            </div>
            <p class="mt-3 text-sm leading-relaxed text-slate-300">{{ t("home.interfaces.customerText") }}</p>
            <div class="mt-5 flex flex-wrap gap-2">
              <a :href="demoUrl" target="_blank" rel="noopener noreferrer" class="ui-btn-primary inline-flex items-center gap-2 ui-touch-target">
                <AppIcon name="menu" class="h-4 w-4" aria-hidden="true" />
                <span>{{ t("home.viewLiveDemo") }}</span>
              </a>
              <RouterLink to="/demo" class="ui-btn-outline inline-flex items-center gap-2 ui-touch-target">
                <AppIcon name="eye" class="h-4 w-4" aria-hidden="true" />
                <span>{{ t("common.demo") }}</span>
              </RouterLink>
            </div>
            <div class="mt-5 grid gap-2 sm:grid-cols-2">
              <div class="ui-admin-subcard p-3.5">
                <p class="ui-stat-label">{{ t("home.stats.launchTime") }}</p>
                <p class="mt-2 text-base font-bold tabular-nums text-white">{{ t("home.stats.launchTimeValue") }}</p>
              </div>
              <div class="ui-admin-subcard p-3.5">
                <p class="ui-stat-label">{{ t("home.stats.interfaces") }}</p>
                <p class="mt-2 text-base font-bold tabular-nums text-white">{{ t("home.stats.interfacesValue") }}</p>
              </div>
            </div>
          </article>
          <article class="ui-command-deck p-6 ui-reveal" :style="{ '--ui-delay': '140ms' }">
            <div class="flex items-start justify-between gap-3">
              <div class="space-y-1.5">
                <p class="ui-kicker">{{ t("home.plansTitle") }}</p>
                <p class="text-lg font-semibold tracking-tight text-white">{{ t("home.plans.basic.name") }}</p>
                <p class="text-sm leading-relaxed text-slate-300">{{ t("home.plans.basic.description") }}</p>
              </div>
              <div class="ui-chip-strong shrink-0">{{ t("common.available") }}</div>
            </div>
            <div class="mt-5 space-y-2">
              <div class="ui-admin-subcard px-4 py-3 text-sm leading-relaxed text-slate-300">{{ t("home.plans.basic.feature1") }}</div>
              <div class="ui-admin-subcard px-4 py-3 text-sm leading-relaxed text-slate-300">{{ t("home.plans.basic.feature2") }}</div>
              <div class="ui-admin-subcard px-4 py-3 text-sm leading-relaxed text-slate-300">{{ t("home.plans.basic.feature3") }}</div>
            </div>
          </article>
        </div>
      </div>
    </div>

    <!-- ── Customer verticals (driven by SERVICES registry) ─────────────── -->
    <section aria-labelledby="verticals-heading">
      <div class="mb-6 space-y-1.5">
        <p class="ui-kicker">{{ t('home.verticalsKicker') }}</p>
        <h2 id="verticals-heading" class="ui-display text-2xl font-bold tracking-tight text-white md:text-3xl">{{ t('home.verticalsTitle') }}</h2>
        <p class="max-w-2xl text-sm leading-relaxed text-slate-300 md:text-base">{{ t('home.verticalsSubtitle') }}</p>
      </div>
      <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <template v-for="(svc, idx) in SERVICES" :key="svc.id">
          <!-- Live service — links to marketplace lens or named route -->
          <component
            :is="svc.status === 'live' ? 'RouterLink' : 'article'"
            v-bind="svc.status === 'live'
              ? { to: svc.kind === 'lens'
                    ? { name: 'marketplace', query: svc.subtype ? { type: svc.lens, sub: svc.subtype } : { type: svc.lens } }
                    : { name: svc.routeName } }
              : {}"
            class="ui-glass ui-reveal flex flex-col gap-4 p-5 md:p-6 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/40"
            :class="svc.status === 'coming_soon' ? 'opacity-60' : 'ui-press'"
            :style="{ '--ui-delay': (idx * 56) + 'ms' }"
            :aria-label="svc.status === 'live' ? t('services.' + svc.id + 'Title') : undefined"
          >
            <!-- Icon tile -->
            <div
              class="flex h-10 w-10 items-center justify-center rounded-2xl text-xl"
              :class="ACCENT_CLASSES[svc.accent].tile"
              aria-hidden="true"
            >{{ svc.icon }}</div>

            <!-- Text -->
            <div class="flex-1 space-y-1.5">
              <div class="flex items-center gap-2">
                <p class="text-sm font-semibold text-white">{{ t('services.' + svc.id + 'Title') }}</p>
                <span
                  v-if="svc.status === 'coming_soon'"
                  class="rounded-full border border-slate-600/60 bg-slate-800/60 px-2 py-0.5 text-[10px] font-medium text-slate-400"
                >{{ t('services.comingSoon') }}</span>
              </div>
              <p class="text-sm leading-relaxed text-slate-400">{{ t('services.' + svc.id + 'Desc') }}</p>
            </div>

            <!-- CTA pill — live only -->
            <span
              v-if="svc.status === 'live'"
              class="inline-flex w-fit items-center gap-1.5 rounded-full border px-3.5 py-1.5 text-xs font-semibold transition-colors"
              :class="ACCENT_CLASSES[svc.accent].pill"
              aria-hidden="true"
            >{{ t('home.verticalCta') }}<AppIcon name="arrowRight" class="h-3 w-3 rtl:scale-x-[-1]" aria-hidden="true" /></span>
          </component>
        </template>
      </div>
    </section>

    <section class="grid gap-5 lg:grid-cols-[1.15fr,0.85fr]" aria-labelledby="phases-heading">
      <article class="ui-glass p-6 md:p-8 ui-reveal">
        <div class="flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
          <div class="space-y-2">
            <p class="ui-kicker">{{ t("home.readyEyebrow") }}</p>
            <h2 id="phases-heading" class="ui-display text-2xl font-bold tracking-tight text-white md:text-3xl">{{ t("home.readyTitle") }}</h2>
            <p class="max-w-2xl text-sm leading-relaxed text-slate-300 md:text-base">{{ t("home.readyText") }}</p>
          </div>
          <div class="flex flex-wrap gap-2">
            <span class="ui-chip">
              <AppIcon name="phone" class="h-3.5 w-3.5" aria-hidden="true" />
              <span>{{ t("home.stats.launchTimeValue") }}</span>
            </span>
            <span class="ui-chip">
              <AppIcon name="settings" class="h-3.5 w-3.5" aria-hidden="true" />
              <span>{{ t("home.stats.interfacesValue") }}</span>
            </span>
            <span class="ui-chip">
              <AppIcon name="check" class="h-3.5 w-3.5" aria-hidden="true" />
              <span>{{ t("home.stats.tierReadyValue") }}</span>
            </span>
          </div>
        </div>

        <div class="mt-6 grid gap-4 md:grid-cols-3">
          <article class="ui-admin-subcard space-y-2.5 p-4">
            <div class="ui-chip w-fit">
              <AppIcon name="home" class="h-3.5 w-3.5" aria-hidden="true" />
              <span>{{ t("home.phases.phase1") }}</span>
            </div>
            <p class="mt-2 text-base font-semibold leading-snug text-white">{{ t("home.phases.phase1Title") }}</p>
            <p class="mt-1 text-sm leading-relaxed text-slate-300">{{ t("home.phases.phase1Text") }}</p>
          </article>
          <article class="ui-admin-subcard space-y-2.5 p-4">
            <div class="ui-chip w-fit">
              <AppIcon name="settings" class="h-3.5 w-3.5" aria-hidden="true" />
              <span>{{ t("home.phases.phase2") }}</span>
            </div>
            <p class="mt-2 text-base font-semibold leading-snug text-white">{{ t("home.phases.phase2Title") }}</p>
            <p class="mt-1 text-sm leading-relaxed text-slate-300">{{ t("home.phases.phase2Text") }}</p>
          </article>
          <article class="ui-admin-subcard space-y-2.5 p-4">
            <div class="ui-chip w-fit">
              <AppIcon name="menu" class="h-3.5 w-3.5" aria-hidden="true" />
              <span>{{ t("home.phases.phase3") }}</span>
            </div>
            <p class="mt-2 text-base font-semibold leading-snug text-white">{{ t("home.phases.phase3Title") }}</p>
            <p class="mt-1 text-sm leading-relaxed text-slate-300">{{ t("home.phases.phase3Text") }}</p>
          </article>
        </div>
      </article>

      <article class="ui-command-deck p-6 md:p-8 ui-reveal" :style="{ '--ui-delay': '56ms' }">
        <div class="space-y-2">
          <p class="ui-kicker">{{ t("home.plansTitle") }}</p>
          <h3 class="ui-display text-2xl font-bold tracking-tight text-white">{{ t("home.plans.basic.name") }}</h3>
          <p class="text-sm leading-relaxed text-slate-300">{{ t("home.plans.basic.description") }}</p>
        </div>

        <div class="mt-5 grid gap-3 sm:grid-cols-3">
          <article class="ui-admin-subcard p-3.5">
            <p class="ui-stat-label">{{ t("home.stats.launchTime") }}</p>
            <p class="mt-2 text-sm font-bold tabular-nums text-white">{{ t("home.stats.launchTimeValue") }}</p>
          </article>
          <article class="ui-admin-subcard p-3.5">
            <p class="ui-stat-label">{{ t("home.stats.interfaces") }}</p>
            <p class="mt-2 text-sm font-bold tabular-nums text-white">{{ t("home.stats.interfacesValue") }}</p>
          </article>
          <article class="ui-admin-subcard p-3.5">
            <p class="ui-stat-label">{{ t("home.stats.tierReady") }}</p>
            <p class="mt-2 text-sm font-bold tabular-nums text-white">{{ t("home.stats.tierReadyValue") }}</p>
          </article>
        </div>

        <div class="mt-6 flex flex-wrap gap-3">
          <RouterLink to="/get-started" class="ui-btn-primary ui-touch-target">{{ t("home.getMyMenu") }}</RouterLink>
          <RouterLink to="/contact" class="ui-btn-outline ui-touch-target">{{ t("home.talkSupport") }}</RouterLink>
        </div>
      </article>
    </section>

    <section id="plans" class="space-y-5" aria-labelledby="plans-heading">
      <div class="ui-section-band flex flex-col gap-5 p-6 md:flex-row md:items-end md:justify-between md:p-8">
        <div class="space-y-2">
          <p class="ui-kicker">{{ t("home.heroBadge") }}</p>
          <h2 id="plans-heading" class="ui-display text-2xl font-bold tracking-tight text-white md:text-3xl">{{ t("home.plansTitle") }}</h2>
          <p class="max-w-2xl text-sm leading-relaxed text-slate-300 md:text-base">{{ t("home.heroSubtitle") }}</p>
        </div>
        <div class="grid gap-3 sm:grid-cols-3 md:min-w-[360px]">
          <article class="ui-admin-subcard p-3.5">
            <p class="ui-stat-label">{{ t("home.stats.tierReady") }}</p>
            <p class="mt-2 text-lg font-bold tabular-nums text-white">{{ t("home.stats.tierReadyValue") }}</p>
          </article>
          <article class="ui-admin-subcard p-3.5">
            <p class="ui-stat-label">{{ t("home.stats.launchTime") }}</p>
            <p class="mt-2 text-lg font-bold tabular-nums text-white">{{ t("home.stats.launchTimeValue") }}</p>
          </article>
          <article class="ui-admin-subcard p-3.5">
            <p class="ui-stat-label">{{ t("home.stats.interfaces") }}</p>
            <p class="mt-2 text-lg font-bold tabular-nums text-white">{{ t("home.stats.interfacesValue") }}</p>
          </article>
        </div>
      </div>
      <div class="grid gap-5 md:grid-cols-3">
        <article
          v-for="(plan, planIndex) in plans"
          :key="plan.code"
          class="ui-reveal relative overflow-hidden rounded-[1.8rem] border p-6 shadow-lg shadow-black/20 transition duration-300"
          :class="plan.recommended ? 'border-[var(--color-secondary)] bg-[var(--color-secondary)]/12' : 'border-slate-700/60 bg-slate-900/55'"
          :style="{ '--ui-delay': `${planIndex * 56}ms` }"
          :aria-label="plan.name + ' — ' + (plan.available ? t('home.plans.planAvailable') : t('common.soon'))"
        >
          <div class="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/20 to-transparent" aria-hidden="true"></div>
          <div v-if="plan.recommended" class="pointer-events-none absolute end-5 top-5 rounded-full border border-[var(--color-secondary)]/40 bg-[var(--color-secondary)]/15 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--color-secondary)]" aria-hidden="true">
            {{ t("home.plans.planRecommended") }}
          </div>
          <span v-if="plan.recommended" class="sr-only">{{ t("home.recommended") }}</span>
          <div class="flex items-center justify-between gap-3">
            <div class="min-w-0">
              <p class="ui-kicker">{{ t("common.plan") }}</p>
              <p class="mt-2 truncate text-xl font-bold tracking-tight text-white">{{ plan.name }}</p>
            </div>
            <span
              class="shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold"
              :class="plan.available ? 'bg-emerald-400/90 text-emerald-950' : 'bg-slate-700 text-slate-200'"
            >
              {{ plan.available ? t("home.plans.planAvailable") : t("common.soon") }}
            </span>
          </div>
          <!-- Pricing (config-driven from lib/pricing.js — owner sets real amounts there) -->
          <div class="mt-3 flex flex-wrap items-baseline gap-1.5">
            <span v-if="plan.price" class="text-2xl font-bold tabular-nums text-white">{{ plan.price }}</span>
            <span v-else class="rounded-full border border-amber-500/40 bg-amber-500/8 px-2.5 py-0.5 text-[11px] font-semibold text-amber-300">{{ t("pricing.priceTodo") }}</span>
            <span v-if="plan.price" class="text-xs text-slate-500">/ {{ t("pricing.period." + plan.period) }}</span>
          </div>
          <p class="mt-2 text-sm leading-relaxed text-slate-300">{{ plan.description }}</p>
          <ul class="mt-5 space-y-2.5 text-sm text-slate-300">
            <li v-for="(line, featureIndex) in plan.features" :key="line" class="flex items-start gap-2.5">
              <span class="mt-[0.3rem] inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--color-secondary)]" aria-hidden="true"></span>
              <span class="min-w-0 flex-1 leading-snug">{{ line }}</span>
              <span class="shrink-0 text-[10px] uppercase tracking-[0.14em] text-slate-500" aria-hidden="true">{{ String(featureIndex + 1).padStart(2, "0") }}</span>
            </li>
          </ul>
          <RouterLink
            :to="{ name: 'lead', query: { plan: plan.code } }"
            class="ui-press mt-7 inline-flex w-full items-center justify-center rounded-full border px-4 py-2.5 text-sm font-semibold transition-colors ui-touch-target focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/60"
            :class="plan.recommended ? 'border-[var(--color-secondary)] bg-[var(--color-secondary)]/10 text-[var(--color-secondary)] hover:bg-[var(--color-secondary)]/20' : 'border-slate-700 text-slate-100 hover:border-slate-500 hover:bg-slate-800/50'"
          >
            {{ plan.cta }}
          </RouterLink>
        </article>
      </div>
    </section>

    <section class="ui-glass p-7 md:p-10 ui-reveal" aria-labelledby="cta-heading">
      <div class="grid gap-8 md:grid-cols-[1.18fr,0.82fr] md:items-center">
        <div class="space-y-5">
          <div class="space-y-2">
            <p class="ui-kicker">{{ t("home.readyEyebrow") }}</p>
            <h2 id="cta-heading" class="ui-display text-3xl font-bold tracking-tight text-white">{{ t("home.readyTitle") }}</h2>
            <p class="leading-relaxed text-slate-300">{{ t("home.readyText") }}</p>
          </div>
          <div class="grid gap-3 sm:grid-cols-3">
            <article class="ui-metric-card">
              <p class="ui-stat-label">{{ t("home.stats.launchTime") }}</p>
              <p class="mt-2 text-lg font-bold tabular-nums text-white">{{ t("home.stats.launchTimeValue") }}</p>
            </article>
            <article class="ui-metric-card">
              <p class="ui-stat-label">{{ t("home.stats.interfaces") }}</p>
              <p class="mt-2 text-lg font-bold tabular-nums text-white">{{ t("home.stats.interfacesValue") }}</p>
            </article>
            <article class="ui-metric-card">
              <p class="ui-stat-label">{{ t("home.stats.tierReady") }}</p>
              <p class="mt-2 text-lg font-bold tabular-nums text-white">{{ t("home.stats.tierReadyValue") }}</p>
            </article>
          </div>
        </div>
        <div class="ui-command-deck p-6">
          <div class="space-y-1.5">
            <p class="ui-kicker">{{ t("common.demo") }}</p>
            <p class="text-lg font-semibold tracking-tight text-white">{{ brandDomain }}</p>
            <p class="text-sm leading-relaxed text-slate-300">{{ t("home.interfaces.customerText") }}</p>
          </div>
          <div class="mt-5 flex flex-wrap gap-3">
            <RouterLink to="/get-started" class="ui-btn-primary ui-touch-target">{{ t("home.submitLead") }}</RouterLink>
            <RouterLink to="/contact" class="ui-btn-outline ui-touch-target">{{ t("home.talkSupport") }}</RouterLink>
            <a :href="demoUrl" target="_blank" rel="noopener noreferrer" class="ui-btn-outline ui-touch-target inline-flex items-center gap-2">
              <AppIcon name="eye" class="h-4 w-4" aria-hidden="true" />
              <span>{{ t("home.viewLiveDemo") }}</span>
            </a>
          </div>
        </div>
      </div>
    </section>
  </main>
</template>

<script setup>
import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import AppIcon from "../components/AppIcon.vue";
import { useI18n } from "../composables/useI18n";
import { useSessionStore } from "../stores/session";
import { SERVICES } from "../lib/services";
import { BRAND_DOMAIN, DEMO_MENU_URL } from "../lib/brand";
import { PRICING_PLANS } from "../lib/pricing";

// Full literal Tailwind class strings per accent — never compute by string concat
// so that the Tailwind scanner can reliably detect these classes.
const ACCENT_CLASSES = {
  amber:   { tile: 'border border-amber-500/30 bg-amber-500/10',   pill: 'border-amber-500/40 bg-amber-500/8 text-amber-300 hover:border-amber-500/70 hover:bg-amber-500/15 focus-visible:ring-amber-500/50'   },
  indigo:  { tile: 'border border-indigo-500/30 bg-indigo-500/10', pill: 'border-indigo-500/40 bg-indigo-500/8 text-indigo-300 hover:border-indigo-500/70 hover:bg-indigo-500/15 focus-visible:ring-indigo-500/50' },
  emerald: { tile: 'border border-emerald-500/30 bg-emerald-500/10', pill: 'border-emerald-500/40 bg-emerald-500/8 text-emerald-300 hover:border-emerald-500/70 hover:bg-emerald-500/15 focus-visible:ring-emerald-500/50' },
  rose:    { tile: 'border border-rose-500/30 bg-rose-500/10',     pill: 'border-rose-500/40 bg-rose-500/8 text-rose-300 hover:border-rose-500/70 hover:bg-rose-500/15 focus-visible:ring-rose-500/50'     },
  sky:     { tile: 'border border-sky-500/30 bg-sky-500/10',       pill: 'border-sky-500/40 bg-sky-500/8 text-sky-300 hover:border-sky-500/70 hover:bg-sky-500/15 focus-visible:ring-sky-500/50'       },
};

const route = useRoute();
const router = useRouter();
const session = useSessionStore();
const { t } = useI18n();
const leadSuccess = ref(route.query.lead === "success");
const brandDomain = BRAND_DOMAIN;
const demoUrl = DEMO_MENU_URL;

/**
 * Merge i18n plan copy with pricing config from lib/pricing.js.
 * Price/period come from PRICING_PLANS (owner-configurable); all other copy is i18n.
 */
const plans = computed(() => [
  {
    code: "basic",
    name: t("home.plans.basic.name"),
    description: t("home.plans.basic.description"),
    features: [t("home.plans.basic.feature1"), t("home.plans.basic.feature2"), t("home.plans.basic.feature3")],
    available: true,
    recommended: true,
    cta: t("home.plans.basic.cta"),
    price: PRICING_PLANS.find((p) => p.code === "basic")?.price ?? null,
    period: PRICING_PLANS.find((p) => p.code === "basic")?.period ?? "monthly",
  },
  {
    code: "growth",
    name: t("home.plans.growth.name"),
    description: t("home.plans.growth.description"),
    features: [t("home.plans.growth.feature1"), t("home.plans.growth.feature2"), t("home.plans.growth.feature3")],
    available: false,
    recommended: false,
    cta: t("home.plans.growth.cta"),
    price: PRICING_PLANS.find((p) => p.code === "growth")?.price ?? null,
    period: PRICING_PLANS.find((p) => p.code === "growth")?.period ?? "monthly",
  },
  {
    code: "pro",
    name: t("home.plans.pro.name"),
    description: t("home.plans.pro.description"),
    features: [t("home.plans.pro.feature1"), t("home.plans.pro.feature2"), t("home.plans.pro.feature3")],
    available: false,
    recommended: false,
    cta: t("home.plans.pro.cta"),
    price: PRICING_PLANS.find((p) => p.code === "pro")?.price ?? null,
    period: PRICING_PLANS.find((p) => p.code === "pro")?.period ?? "monthly",
  },
]);

const dismiss = () => {
  leadSuccess.value = false;
  const q = { ...route.query };
  delete q.lead;
  router.replace({ query: q });
};
</script>
