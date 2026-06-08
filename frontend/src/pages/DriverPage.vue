<template>
  <main class="ui-page-shell space-y-4">
    <!-- Header -->
    <header class="ui-hero-ribbon ui-reveal px-4 py-3.5">
      <p class="ui-kicker">{{ t('driver.kicker') }}</p>
      <h1 class="ui-display text-2xl font-semibold leading-tight text-white">{{ t('driver.title') }}</h1>
    </header>

    <!-- Loading -->
    <div v-if="!customerStore.loaded" class="ui-skeleton h-28" aria-busy="true" :aria-label="t('common.loading')" />

    <!-- Not signed in — public rider acquisition + install-first PWA -->
    <div v-else-if="!customerStore.isAuthenticated" class="space-y-4 ui-reveal">
      <div class="ui-panel p-5 space-y-4">
        <div class="flex items-center gap-3">
          <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border border-emerald-500/30 bg-emerald-500/10">
            <AppIcon name="truck" class="h-5 w-5 text-emerald-300" aria-hidden="true" />
          </div>
          <p class="text-base font-semibold text-slate-100">{{ t('driver.earnTitle') }}</p>
        </div>
        <p class="ui-subtle">{{ t('driver.earnSubtitle') }}</p>
        <ul class="space-y-2 text-sm text-slate-300">
          <li class="flex items-start gap-2.5">
            <AppIcon name="check" class="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" aria-hidden="true" />
            <span>{{ t('driver.benefit1') }}</span>
          </li>
          <li class="flex items-start gap-2.5">
            <AppIcon name="check" class="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" aria-hidden="true" />
            <span>{{ t('driver.benefit2') }}</span>
          </li>
          <li class="flex items-start gap-2.5">
            <AppIcon name="check" class="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" aria-hidden="true" />
            <span>{{ t('driver.benefit3') }}</span>
          </li>
        </ul>
      </div>

      <!-- Install the app (riders work from the installed app) -->
      <div v-if="!isStandalone && !continueInBrowser" class="rounded-2xl border border-emerald-500/30 bg-emerald-500/8 p-4 space-y-3">
        <p class="text-sm font-semibold text-emerald-200">{{ t('driver.installTitle') }}</p>
        <p class="text-xs text-slate-300">{{ t('driver.installDesc') }}</p>
        <button v-if="canInstall" class="ui-btn-primary ui-touch-target w-full text-sm" @click="promptInstall">
          {{ t('driver.installCta') }}
        </button>
        <p v-else class="text-xs text-slate-400">{{ t('driver.installManual') }}</p>
        <button class="ui-touch-target text-[11px] text-slate-500 underline hover:text-slate-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-400" @click="continueInBrowser = true">
          {{ t('driver.continueInBrowser') }}
        </button>
      </div>

      <!-- Sign in to apply -->
      <div class="ui-panel p-5 text-center space-y-3">
        <p class="text-sm text-slate-300">{{ t('driver.signInPrompt') }}</p>
        <RouterLink :to="{ name: 'customer-account' }" class="ui-btn-primary inline-flex px-6 py-2.5 text-sm">
          {{ t('driver.signInCta') }}
        </RouterLink>
      </div>
    </div>

    <!-- Signed in but not yet a driver -->
    <div v-else-if="!isDriver" class="ui-panel p-5 space-y-4 ui-reveal">
      <div class="flex items-center gap-3">
        <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border border-emerald-500/30 bg-emerald-500/10">
          <AppIcon name="truck" class="h-5 w-5 text-emerald-300" aria-hidden="true" />
        </div>
        <p class="text-base font-semibold text-slate-100">{{ t('driver.becomeTitle') }}</p>
      </div>
      <p class="ui-subtle">{{ t('driver.becomeDesc') }}</p>

      <!-- Install the app first (drivers work from the installed app) -->
      <div v-if="!isStandalone && !continueInBrowser" class="rounded-2xl border border-emerald-500/30 bg-emerald-500/8 p-4 space-y-3">
        <p class="text-sm font-semibold text-emerald-200">{{ t('driver.installTitle') }}</p>
        <p class="text-xs text-slate-300">{{ t('driver.installDesc') }}</p>
        <button v-if="canInstall" class="ui-btn-primary ui-touch-target w-full text-sm" @click="promptInstall">
          {{ t('driver.installCta') }}
        </button>
        <p v-else class="text-xs text-slate-400">{{ t('driver.installManual') }}</p>
        <button class="ui-touch-target text-[11px] text-slate-500 underline hover:text-slate-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-400" @click="continueInBrowser = true">
          {{ t('driver.continueInBrowser') }}
        </button>
      </div>

      <!-- Apply (after install, or after explicitly continuing in the browser) -->
      <template v-else>
        <div class="space-y-1.5">
          <label class="text-xs font-medium text-slate-400" for="driver-vehicle">{{ t('driver.vehicleLabel') }}</label>
          <input
            id="driver-vehicle"
            v-model.trim="vehicle"
            type="text"
            class="ui-input"
            :placeholder="t('driver.vehiclePlaceholder')"
          />
        </div>
        <div v-if="errorMsg" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
          <AppIcon name="info" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" aria-hidden="true" />
          <p class="flex-1 text-sm text-red-300">{{ errorMsg }}</p>
        </div>
        <button
          class="ui-btn-primary ui-touch-target w-full text-sm"
          :disabled="busy"
          :aria-busy="busy"
          :aria-label="busy ? t('common.loading') : undefined"
          @click="becomeDriver"
        >{{ busy ? '…' : t('driver.becomeCta') }}</button>
      </template>
    </div>

    <!-- Applied, awaiting admin approval -->
    <div v-else-if="!approved" class="ui-panel p-6 space-y-4 text-center ui-reveal">
      <div class="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl border border-amber-500/30 bg-amber-500/10">
        <AppIcon name="info" class="h-6 w-6 text-amber-300" aria-hidden="true" />
      </div>
      <div class="space-y-1.5">
        <p class="text-base font-semibold text-slate-100">{{ t('driver.pendingTitle2') }}</p>
        <p class="ui-subtle">{{ t('driver.pendingDesc') }}</p>
      </div>
      <button
        class="ui-btn-outline ui-press px-5 py-2 text-sm"
        :disabled="busy"
        @click="fetchStatus"
      >
        {{ t('driver.refresh') }}
      </button>
    </div>

    <!-- Driver dashboard (approved) -->
    <template v-else>
      <!-- Online toggle — high prominence, the most critical driver control -->
      <div
        class="ui-panel flex items-center justify-between gap-3 p-4 ui-reveal"
        :class="online ? 'border-emerald-500/30 bg-emerald-900/10' : ''"
      >
        <div class="min-w-0">
          <div class="flex items-center gap-2">
            <span
              class="ui-live-dot"
              :class="online ? 'bg-emerald-400' : 'bg-slate-600'"
              aria-hidden="true"
            />
            <p class="text-base font-semibold" :class="online ? 'text-emerald-300' : 'text-slate-300'">
              {{ online ? t('driver.online') : t('driver.offline') }}
            </p>
          </div>
          <p class="mt-0.5 text-xs text-slate-500">{{ online ? t('driver.onlineHint') : t('driver.offlineHint') }}</p>
          <p v-if="geoError" class="mt-1 text-xs text-amber-300" role="status">{{ geoError }}</p>
        </div>
        <button
          class="ui-press shrink-0 rounded-full px-5 py-2.5 text-sm font-semibold transition-colors disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
          :class="online
            ? 'border border-slate-600 text-slate-300 hover:border-slate-400 focus-visible:outline-slate-400'
            : 'bg-emerald-600 text-white hover:bg-emerald-500 focus-visible:outline-emerald-400 shadow-lg shadow-emerald-900/40'"
          :disabled="busy"
          role="switch"
          :aria-checked="online"
          :aria-label="online ? t('driver.online') : t('driver.offline')"
          @click="toggleOnline"
        >
          {{ online ? t('driver.goOffline') : t('driver.goOnline') }}
        </button>
      </div>

      <div v-if="errorMsg" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
        <AppIcon name="info" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" aria-hidden="true" />
        <p class="flex-1 text-sm text-red-300">{{ errorMsg }}</p>
      </div>

      <!-- Earnings summary -->
      <div v-if="earnings" class="ui-panel overflow-hidden p-0 ui-reveal">
        <div class="grid grid-cols-3 divide-x divide-slate-700/40">
          <div class="flex flex-col items-center justify-center px-3 py-4 text-center">
            <p class="ui-stat-label">{{ t('driver.earned') }}</p>
            <p class="mt-1 text-base font-bold tabular-nums text-slate-200">{{ fmtMoney(earnings.earned) }}</p>
          </div>
          <div class="flex flex-col items-center justify-center px-3 py-4 text-center">
            <p class="ui-stat-label">{{ t('driver.paidOut') }}</p>
            <p class="mt-1 text-base font-bold tabular-nums text-slate-400">{{ fmtMoney(earnings.paid) }}</p>
          </div>
          <div class="flex flex-col items-center justify-center px-3 py-4 text-center">
            <p class="ui-stat-label">{{ t('driver.owed') }}</p>
            <p class="mt-1 text-base font-bold tabular-nums text-emerald-400">{{ fmtMoney(earnings.owed) }}</p>
          </div>
        </div>
      </div>

      <!-- Cash-out: available wallet balance + redeem at a restaurant -->
      <div v-if="earnings" class="ui-panel p-4 space-y-3 ui-reveal">
        <div class="flex items-center justify-between gap-3">
          <div class="min-w-0">
            <p class="ui-stat-label">{{ t('driver.available') }}</p>
            <p class="mt-1 text-xl font-bold tabular-nums text-white">{{ fmtMoney(earnings.available) }}</p>
          </div>
          <button
            v-if="!cashout"
            class="ui-btn-primary ui-press shrink-0 px-4 py-2 text-sm disabled:opacity-50"
            :disabled="!earnings.can_cash_out || busy"
            @click="requestCashout"
          >{{ t('driver.cashOut') }}</button>
        </div>
        <p v-if="!earnings.can_cash_out && !cashout" class="text-[11px] text-slate-500">
          {{ t('driver.cashOutMin', { amount: fmtMoney(earnings.cashout_min) }) }}
        </p>
        <!-- Active cash-out request: show the code to read to a restaurant -->
        <div v-if="cashout" class="rounded-2xl border border-emerald-500/30 bg-emerald-500/8 p-4 text-center space-y-2.5">
          <p class="text-xs font-medium text-emerald-200">{{ t('driver.cashOutShowCode', { amount: fmtMoney(cashout.amount) }) }}</p>
          <p class="my-1 text-4xl font-bold tracking-[0.35em] text-white tabular-nums">
            <span class="sr-only">{{ t('driver.cashOutCode') }}: </span>{{ cashout.code }}
          </p>
          <button
            class="ui-btn-outline ui-press px-5 py-2 text-sm"
            :disabled="busy"
            @click="cancelCashout"
          >
            {{ t('driver.cashOutCancel') }}
          </button>
        </div>
      </div>

      <!-- Active job -->
      <div v-if="activeJob" class="ui-panel p-0 overflow-hidden ui-reveal">
        <!-- Job header -->
        <div class="flex items-center justify-between gap-2 border-b border-slate-700/40 px-4 py-3">
          <p class="text-sm font-semibold text-slate-200">{{ t('driver.activeTitle') }}</p>
          <span class="ui-status-pill">
            {{ statusLabel(activeJob.status) }}
          </span>
        </div>

        <div class="p-4 space-y-3">
          <!-- Restaurant + order meta -->
          <div class="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <p v-if="activeJob.restaurant_name" class="text-sm font-semibold text-slate-100">{{ activeJob.restaurant_name }}</p>
            <p class="text-xs text-slate-500">{{ t('driver.order') }} #{{ activeJob.order_number }}</p>
          </div>

          <!-- Distance + items chips -->
          <div class="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-400">
            <span v-if="activeJob.distance_km != null" class="inline-flex items-center gap-1">
              <AppIcon name="location" class="h-3 w-3" aria-hidden="true" />{{ t('driver.distanceKm', { km: activeJob.distance_km }) }}
            </span>
            <span v-if="activeJob.items_count">{{ t('driver.itemsCount', { n: activeJob.items_count }) }}</span>
          </div>

          <!-- Food-ready ETA (owner's prep estimate) — when to be at the restaurant -->
          <div
            v-if="activeReadyEta"
            class="inline-flex items-center gap-1.5 rounded-lg border border-emerald-600/30 bg-emerald-900/15 px-2.5 py-1 text-xs font-semibold text-emerald-300"
          >
            <span aria-hidden="true">⏱</span>
            <span>{{ t('driver.foodReady', { time: activeReadyEta.clock }) }}</span>
            <span v-if="activeReadyEta.mins > 0" class="font-normal text-emerald-400/70">· {{ t('driver.foodReadyIn', { minutes: activeReadyEta.mins }) }}</span>
          </div>

          <!-- Cash to collect (COD) vs already paid — the driver must know -->
          <div
            v-if="activeJob.collect_cash"
            class="flex items-center justify-between rounded-xl border border-amber-500/40 bg-amber-500/10 px-3 py-2.5"
          >
            <span class="text-xs font-semibold text-amber-200">{{ t('driver.collectCash') }}</span>
            <span class="text-lg font-bold tabular-nums text-amber-200">{{ fmtMoney(activeJob.order_total) }}</span>
          </div>
          <div
            v-else-if="activeJob.order_total"
            class="flex items-center gap-1.5 rounded-xl border border-emerald-600/30 bg-emerald-900/15 px-3 py-2.5 text-xs font-semibold text-emerald-300"
          >
            <AppIcon name="check" class="h-3.5 w-3.5" aria-hidden="true" />{{ t('driver.prepaid', { amount: fmtMoney(activeJob.order_total) }) }}
          </div>

          <!-- Pickup / dropoff / call -->
          <div class="space-y-2">
            <a
              v-if="activeJob.pickup_address || activeJob.pickup_lat"
              :href="mapsLink(activeJob.pickup_lat, activeJob.pickup_lng, activeJob.pickup_address)"
              target="_blank" rel="noopener"
              class="flex items-center gap-3 rounded-xl border border-slate-700/60 bg-slate-900/40 px-3 py-3 transition-colors hover:border-slate-600/80 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-400"
              :aria-label="t('driver.pickup')"
            >
              <span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-amber-500/15">
                <AppIcon name="location" class="h-4 w-4 text-amber-300" aria-hidden="true" />
              </span>
              <div class="min-w-0 flex-1">
                <p class="text-[11px] uppercase tracking-wider text-slate-500">{{ t('driver.pickup') }}</p>
                <p class="truncate text-sm text-slate-200">{{ activeJob.pickup_address || t('driver.openMaps') }}</p>
              </div>
              <AppIcon name="chevronRight" class="h-4 w-4 shrink-0 text-slate-600 rtl:scale-x-[-1]" aria-hidden="true" />
            </a>
            <a
              v-if="activeJob.delivery_address || activeJob.delivery_lat"
              :href="mapsLink(activeJob.delivery_lat, activeJob.delivery_lng, activeJob.delivery_address)"
              target="_blank" rel="noopener"
              class="flex items-center gap-3 rounded-xl border border-slate-700/60 bg-slate-900/40 px-3 py-3 transition-colors hover:border-slate-600/80 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-400"
              :aria-label="t('driver.dropoff')"
            >
              <span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-emerald-500/15">
                <AppIcon name="location" class="h-4 w-4 text-emerald-300" aria-hidden="true" />
              </span>
              <div class="min-w-0 flex-1">
                <p class="text-[11px] uppercase tracking-wider text-slate-500">{{ t('driver.dropoff') }}</p>
                <p class="truncate text-sm text-slate-200">{{ activeJob.delivery_address || t('driver.openMaps') }}</p>
              </div>
              <AppIcon name="chevronRight" class="h-4 w-4 shrink-0 text-slate-600 rtl:scale-x-[-1]" aria-hidden="true" />
            </a>

            <!-- Call the customer (only the assigned driver sees the phone) -->
            <a
              v-if="activeJob.customer_phone"
              :href="`tel:${activeJob.customer_phone}`"
              class="flex items-center gap-3 rounded-xl border border-sky-700/50 bg-sky-900/20 px-3 py-3 transition-colors hover:border-sky-600/60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-400"
              :aria-label="`${t('driver.callCustomer')}: ${activeJob.customer_name || activeJob.customer_phone}`"
            >
              <span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-sky-500/15">
                <AppIcon name="phone" class="h-4 w-4 text-sky-300" aria-hidden="true" />
              </span>
              <div class="min-w-0 flex-1">
                <p class="text-[11px] uppercase tracking-wider text-slate-500">{{ t('driver.callCustomer') }}</p>
                <p class="truncate text-sm text-slate-200">{{ activeJob.customer_name || activeJob.customer_phone }}</p>
              </div>
              <span class="shrink-0 text-xs font-semibold text-sky-300">{{ t('driver.call') }}</span>
            </a>
          </div>

          <!-- What's in the order -->
          <div v-if="activeJob.items && activeJob.items.length" class="rounded-xl border border-slate-700/60 bg-slate-900/40 px-3 py-3">
            <p class="mb-2 text-[11px] uppercase tracking-wider text-slate-500">{{ t('driver.itemsTitle') }}</p>
            <ul class="space-y-1">
              <li v-for="(it, idx) in activeJob.items" :key="idx" class="flex justify-between gap-2 text-sm text-slate-300">
                <span class="truncate">{{ it.name }}</span>
                <span class="shrink-0 tabular-nums text-slate-400">×{{ it.qty }}</span>
              </li>
            </ul>
          </div>

          <!-- Payout row -->
          <div class="flex items-center justify-between rounded-xl border border-emerald-700/30 bg-emerald-900/10 px-3 py-2.5">
            <span class="text-xs font-medium text-slate-400">{{ t('driver.payout') }}</span>
            <span class="text-base font-bold tabular-nums text-emerald-300">{{ fmtMoney(activeJob.driver_payout) }}</span>
          </div>

          <!-- Reminder: confirm delivery with the customer's code -->
          <div
            v-if="nextAction && nextAction.to === 'delivered'"
            class="flex items-start gap-1.5 rounded-xl border border-sky-700/30 bg-sky-900/15 px-3 py-2.5 text-xs text-sky-300"
            role="status"
            aria-live="polite"
            aria-atomic="true"
          >
            <AppIcon name="info" class="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            <span>{{ t('driver.codeReminder') }}</span>
          </div>

          <!-- Advance status -->
          <button
            v-if="nextAction"
            class="ui-btn-primary ui-touch-target w-full text-sm"
            :disabled="busy"
            :aria-busy="busy"
            :aria-label="busy ? t('common.loading') : undefined"
            @click="advance(nextAction.to)"
          >{{ busy ? '…' : nextAction.label }}</button>
          <button
            v-if="!failingOpen"
            class="ui-touch-target w-full rounded-xl border border-red-500/40 px-4 py-2 text-xs text-red-300 hover:border-red-400/70 hover:text-red-200 transition-colors disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-400"
            :disabled="busy"
            @click="openFail"
          >
            {{ t('driver.actionFailed') }}
          </button>
          <!-- Failure-reason picker (the restaurant decides what happens next) -->
          <div v-else class="space-y-2 rounded-xl border border-red-500/40 bg-red-900/10 p-3">
            <p class="text-xs font-semibold text-red-200">{{ t('driver.failReasonTitle') }}</p>
            <button
              v-for="r in FAIL_REASONS"
              :key="r"
              class="ui-touch-target w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-start text-sm text-slate-200 hover:border-slate-500 disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-400"
              :disabled="busy"
              @click="submitFail(r)"
            >
              {{ t(`driver.failReason_${r}`) }}
            </button>
            <input
              v-model="failNote"
              :placeholder="t('driver.failNotePlaceholder')"
              :aria-label="t('driver.failNotePlaceholder')"
              class="ui-input"
            />
            <button
              class="ui-touch-target w-full py-1 text-xs text-slate-400 hover:text-slate-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-400"
              :disabled="busy"
              @click="failingOpen = false"
            >
              {{ t('driver.failCancel') }}
            </button>
          </div>
        </div>
      </div>

      <!-- Pending jobs (only when online and free) -->
      <div v-else-if="online" class="ui-panel p-4 space-y-3 ui-reveal">
        <div class="flex items-center justify-between gap-2">
          <p class="text-sm font-semibold text-slate-200">{{ t('driver.pendingTitle') }}</p>
          <button
            class="ui-press text-xs text-slate-400 hover:text-slate-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-400"
            :disabled="loadingJobs"
            @click="fetchJobs"
          >
            {{ t('driver.refresh') }}
          </button>
        </div>
        <div v-if="loadingJobs && !pendingJobs.length" class="space-y-2" aria-busy="true">
          <div v-for="i in 2" :key="i" class="ui-skeleton h-24" />
        </div>
        <div v-else-if="!pendingJobs.length" class="ui-empty-state text-center py-5 space-y-2">
          <AppIcon name="truck" class="mx-auto h-7 w-7 text-slate-600" aria-hidden="true" />
          <p class="text-sm font-semibold text-slate-100">{{ t('driver.noPending') }}</p>
        </div>
        <ul v-else class="space-y-2">
          <li
            v-for="(job, index) in pendingJobs"
            :key="job.id"
            class="ui-reveal rounded-2xl border border-slate-700/60 bg-slate-900/40 p-3 space-y-2.5"
            :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
          >
            <!-- Job header row -->
            <div class="flex items-start justify-between gap-2">
              <div class="min-w-0">
                <p class="truncate text-sm font-semibold text-slate-100">{{ job.restaurant_name || ('#' + job.order_number) }}</p>
                <p class="text-[11px] text-slate-500">{{ t('driver.order') }} #{{ job.order_number }}</p>
              </div>
              <span class="shrink-0 text-base font-bold tabular-nums text-emerald-300">{{ fmtMoney(job.driver_payout) }}</span>
            </div>
            <!-- Meta: distance, items, payment type -->
            <div class="flex flex-wrap items-center gap-x-2.5 gap-y-1.5 text-xs text-slate-400">
              <span v-if="job.offered_to_me" class="rounded-full bg-sky-500/15 px-2.5 py-0.5 font-semibold text-sky-300">
                {{ t('driver.offeredToYou') }}
              </span>
              <span v-if="job.distance_km != null" class="inline-flex items-center gap-1">
                <AppIcon name="location" class="h-3 w-3" aria-hidden="true" />{{ t('driver.distanceKm', { km: job.distance_km }) }}
              </span>
              <span v-if="job.items_count">{{ t('driver.itemsCount', { n: job.items_count }) }}</span>
              <span v-if="job.collect_cash" class="rounded-full bg-amber-500/15 px-2.5 py-0.5 font-semibold text-amber-300">
                {{ t('driver.cashShort', { amount: fmtMoney(job.order_total) }) }}
              </span>
              <span v-else-if="job.order_total" class="rounded-full bg-emerald-500/12 px-2.5 py-0.5 font-semibold text-emerald-300">
                {{ t('driver.prepaidShort') }}
              </span>
            </div>
            <!-- Delivery address -->
            <p v-if="job.delivery_address" class="flex items-start gap-1.5 truncate text-sm text-slate-300">
              <AppIcon name="location" class="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-300" aria-hidden="true" />
              <span class="truncate">{{ job.delivery_address }}</span>
            </p>
            <div v-if="job.offered_to_me" class="flex gap-2">
              <button class="ui-btn-primary ui-touch-target flex-1 text-sm" :disabled="busy" @click="accept(job.id)">
                {{ t('driver.accept') }}
              </button>
              <button class="ui-btn-outline ui-touch-target flex-1 text-sm" :disabled="busy" @click="decline(job.id)">
                {{ t('driver.decline') }}
              </button>
            </div>
            <button v-else class="ui-btn-primary ui-touch-target w-full text-sm" :disabled="busy" @click="accept(job.id)">
              {{ t('driver.accept') }}
            </button>
          </li>
        </ul>
      </div>

      <!-- Offline + no job -->
      <div v-else class="ui-empty-state text-center space-y-2.5 ui-reveal">
        <AppIcon name="truck" class="mx-auto h-9 w-9 text-slate-600" aria-hidden="true" />
        <p class="text-sm font-medium text-slate-400">{{ t('driver.offlineEmpty') }}</p>
      </div>

      <!-- Recent deliveries (history) -->
      <div class="ui-panel p-4 space-y-3 ui-reveal">
        <button
          class="flex w-full items-center justify-between gap-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-400"
          :aria-expanded="showHistory"
          aria-controls="driver-history-panel"
          @click="toggleHistory"
        >
          <p class="text-sm font-semibold text-slate-200">{{ t('driver.historyTitle') }}</p>
          <AppIcon :name="showHistory ? 'chevronUp' : 'chevronDown'" class="h-4 w-4 shrink-0 text-slate-500" aria-hidden="true" />
        </button>
        <div id="driver-history-panel">
          <template v-if="showHistory">
            <div v-if="loadingHistory && !history.length" class="space-y-2" aria-busy="true">
              <div v-for="i in 3" :key="i" class="ui-skeleton h-12" />
            </div>
            <div v-else-if="!history.length" class="ui-empty-state text-center py-4 space-y-1">
              <p class="text-sm font-semibold text-slate-100">{{ t('driver.historyEmpty') }}</p>
            </div>
            <ul v-else class="space-y-2">
              <li
                v-for="(d, index) in history"
                :key="d.id"
                class="ui-reveal flex items-center justify-between gap-3 rounded-xl border border-slate-700/60 bg-slate-900/40 px-3 py-2.5"
                :style="{ '--ui-delay': `${Math.min(index, 9) * 20}ms` }"
              >
                <div class="min-w-0">
                  <p class="truncate text-sm text-slate-200">{{ d.restaurant_name || ('#' + d.order_number) }}</p>
                  <p class="text-[11px] text-slate-500">{{ statusLabel(d.status) }} · {{ fmtDate(d.delivered_at || d.failed_at || d.created_at) }}</p>
                </div>
                <span class="shrink-0 text-sm font-semibold tabular-nums" :class="d.status === 'delivered' ? 'text-emerald-300' : 'text-slate-500'">{{ fmtMoney(d.driver_payout) }}</span>
              </li>
            </ul>
          </template>
        </div>
      </div>
    </template>
  </main>

  <!-- Rate the customer after delivery (driver → customer, private) -->
  <Teleport to="body">
    <div
      v-if="ratingJob"
      class="fixed inset-0 z-[2000] flex items-end justify-center bg-black/60 p-3 backdrop-blur-sm sm:items-center"
      @click.self="ratingJob = null"
      @keydown.esc="ratingJob = null"
    >
      <div ref="ratingDialogFirstFocus" class="w-full max-w-sm space-y-4 rounded-2xl border border-slate-700 bg-slate-900 p-5 shadow-2xl" role="dialog" aria-modal="true" :aria-label="t('driver.rateCustomerTitle')" tabindex="-1">
        <div>
          <p class="text-sm font-semibold text-white">{{ t('driver.rateCustomerTitle') }}</p>
          <p class="mt-0.5 text-xs text-slate-400">{{ t('driver.order') }} #{{ ratingJob.order_number }}</p>
          <p class="mt-1 text-[11px] text-slate-500">{{ t('driver.rateCustomerHint') }}</p>
        </div>
        <div class="flex items-center gap-2" role="group" :aria-label="t('driver.rateCustomerTitle')">
          <button
            v-for="n in 5" :key="n" type="button"
            class="ui-press text-3xl leading-none transition-transform hover:scale-110 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-400"
            :class="n <= custRatingScore ? 'text-amber-400' : 'text-slate-600'"
            :aria-label="t('common.rateNStars', { n })"
            @click="custRatingScore = n"
          >★</button>
        </div>
        <input
          v-model="custRatingNote" type="text" maxlength="200"
          class="ui-input"
          :aria-label="t('driver.rateCustomerNote')"
          :placeholder="t('driver.rateCustomerNote')"
        />
        <div class="flex items-center justify-end gap-2 pt-1">
          <button class="ui-btn-outline ui-press px-3 py-2 text-xs" @click="ratingJob = null">
            {{ t('driver.rateSkip') }}
          </button>
          <button
            class="ui-btn-primary ui-press px-4 py-2 text-sm disabled:opacity-50"
            :disabled="!custRatingScore || submittingRating"
            :aria-busy="submittingRating"
            :aria-label="submittingRating ? t('common.loading') : undefined"
            @click="submitCustomerRating"
          >{{ submittingRating ? '…' : t('driver.rateSubmit') }}</button>
        </div>
      </div>
    </div>
  </Teleport>

  <!-- Delivery code modal -->
  <Teleport to="body">
    <div
      v-if="codeModalOpen"
      class="fixed inset-0 z-[2000] flex items-end justify-center bg-black/60 p-3 backdrop-blur-sm sm:items-center"
      @click.self="closeCodeModal"
      @keydown.esc="closeCodeModal"
    >
      <div
        role="dialog"
        aria-modal="true"
        :aria-label="t('driver.enterDeliveryCode')"
        class="w-full max-w-sm space-y-4 rounded-2xl border border-slate-700 bg-slate-900 p-5 shadow-2xl"
      >
        <div>
          <p class="text-sm font-semibold text-white">{{ t('driver.enterDeliveryCode') }}</p>
          <p class="mt-0.5 text-xs text-slate-400">{{ t('driver.codeReminder') }}</p>
        </div>
        <input
          ref="codeFirstRef"
          v-model="codeInput"
          type="text"
          class="ui-input text-center text-lg tracking-[0.3em] font-bold uppercase"
          :placeholder="t('driver.enterDeliveryCode')"
          :aria-label="t('driver.enterDeliveryCode')"
          autocomplete="one-time-code"
          maxlength="10"
          @keydown.enter="submitDeliveryCode"
        />
        <div v-if="codeError" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
          <p class="text-sm text-red-300">{{ codeError }}</p>
        </div>
        <div class="flex items-center justify-end gap-2 pt-1">
          <button class="ui-btn-outline ui-press px-3 py-2 text-xs" @click="closeCodeModal">
            {{ t('common.cancel') }}
          </button>
          <button
            class="ui-btn-primary ui-press px-4 py-2 text-sm disabled:opacity-50"
            :disabled="!codeInput.trim() || codeSubmitting"
            :aria-busy="codeSubmitting"
            :aria-label="codeSubmitting ? t('common.loading') : undefined"
            @click="submitDeliveryCode"
          >{{ codeSubmitting ? '…' : t('common.confirm') }}</button>
        </div>
      </div>
    </div>
  </Teleport>

  <!-- Cash-out amount modal -->
  <Teleport to="body">
    <div
      v-if="cashoutModalOpen"
      class="fixed inset-0 z-[2000] flex items-end justify-center bg-black/60 p-3 backdrop-blur-sm sm:items-center"
      @click.self="closeCashoutModal"
      @keydown.esc="closeCashoutModal"
    >
      <div
        role="dialog"
        aria-modal="true"
        :aria-label="t('driver.cashOut')"
        class="w-full max-w-sm space-y-4 rounded-2xl border border-slate-700 bg-slate-900 p-5 shadow-2xl"
      >
        <div>
          <p class="text-sm font-semibold text-white">{{ t('driver.cashOut') }}</p>
          <p class="mt-0.5 text-xs text-slate-400">{{ t('driver.cashOutAmountPrompt', { max: fmtMoney(earnings ? earnings.available : 0) }) }}</p>
        </div>
        <input
          ref="cashoutFirstRef"
          v-model="cashoutInput"
          type="number"
          min="1"
          :max="earnings ? earnings.available : undefined"
          step="0.01"
          class="ui-input text-lg font-bold tabular-nums"
          :aria-label="t('driver.cashOut')"
          @keydown.enter="submitCashout"
        />
        <div v-if="cashoutModalError" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
          <p class="text-sm text-red-300">{{ cashoutModalError }}</p>
        </div>
        <div class="flex items-center justify-end gap-2 pt-1">
          <button class="ui-btn-outline ui-press px-3 py-2 text-xs" @click="closeCashoutModal">
            {{ t('common.cancel') }}
          </button>
          <button
            class="ui-btn-primary ui-press px-4 py-2 text-sm disabled:opacity-50"
            :disabled="busy"
            :aria-busy="busy"
            :aria-label="busy ? t('common.loading') : undefined"
            @click="submitCashout"
          >{{ busy ? '…' : t('driver.cashOut') }}</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, onMounted, onBeforeUnmount, ref, watch } from 'vue';
import AppIcon from '../components/AppIcon.vue';
import { useI18n } from '../composables/useI18n';
import { useCustomerStore } from '../stores/customer';
import { useToastStore } from '../stores/toast';
import { useCustomerPush } from '../composables/useCustomerPush';
import api from '../lib/api';

const { t, currentLocale } = useI18n();
const customerStore = useCustomerStore();
const toast = useToastStore();
const driverPush = useCustomerPush();

const isDriver = ref(false);
const approved = ref(false);
const vehicle = ref('');
const online = ref(false);
const activeJob = ref(null);
const pendingJobs = ref([]);

// ── Install-first PWA — drivers work from the installed app ──────────────────────
const isStandalone = ref(
  typeof window !== 'undefined' && (
    window.matchMedia?.('(display-mode: standalone)').matches || window.navigator.standalone === true
  )
);
const continueInBrowser = ref(false);
const canInstall = ref(false);
let deferredInstallPrompt = null;
const onBeforeInstallPrompt = (e) => {
  e.preventDefault();           // stash it so we can trigger our own button
  deferredInstallPrompt = e;
  canInstall.value = true;
};
const onAppInstalled = () => {
  canInstall.value = false;
  isStandalone.value = true;
};
const promptInstall = async () => {
  if (!deferredInstallPrompt) return;
  deferredInstallPrompt.prompt();
  try { await deferredInstallPrompt.userChoice; } catch { /* ignore */ }
  deferredInstallPrompt = null;
  canInstall.value = false;
};
const busy = ref(false);
const loadingJobs = ref(false);
const errorMsg = ref('');
const geoError = ref('');

let pollTimer = null;
let geoWatchId = null;
let lastPositionSent = 0;

const fmtMoney = (v) => {
  try {
    return new Intl.NumberFormat(currentLocale.value, { style: 'currency', currency: 'MAD', maximumFractionDigits: 2 })
      .format(parseFloat(v || 0));
  } catch {
    return `${parseFloat(v || 0).toFixed(2)}`;
  }
};

const fmtDate = (iso) => {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleDateString(currentLocale.value || undefined, { month: 'short', day: 'numeric' });
  } catch {
    return '';
  }
};

// Owner's food-ready ETA for the active job → { clock: "14:30", mins: 12 }, so the
// driver can time their arrival at the restaurant. Null when no estimate is set.
const activeReadyEta = computed(() => {
  const iso = activeJob.value?.food_ready_at;
  if (!iso) return null;
  const ts = new Date(iso).getTime();
  if (Number.isNaN(ts)) return null;
  let clock = '';
  try {
    clock = new Date(ts).toLocaleTimeString(currentLocale.value || undefined, { hour: '2-digit', minute: '2-digit' });
  } catch {
    clock = '';
  }
  return { clock, mins: Math.round((ts - Date.now()) / 60000) };
});

// Recent deliveries (history) — lazy-loaded the first time the driver expands it.
const showHistory = ref(false);
const history = ref([]);
const loadingHistory = ref(false);
const fetchHistory = async () => {
  loadingHistory.value = true;
  try {
    const { data } = await api.get('/driver/deliveries/');
    history.value = Array.isArray(data.results) ? data.results : [];
  } catch {
    /* keep last */
  } finally {
    loadingHistory.value = false;
  }
};
const toggleHistory = () => {
  showHistory.value = !showHistory.value;
  if (showHistory.value && !history.value.length) fetchHistory();
};

const STATUS_LABELS = {
  assigned: 'driver.statusAssigned',
  at_restaurant: 'driver.statusAtRestaurant',
  picked_up: 'driver.statusPickedUp',
  delivered: 'driver.statusDelivered',
  failed: 'driver.statusFailed',
};
const statusLabel = (s) => t(STATUS_LABELS[s] || 'driver.statusAssigned');

// Next forward transition for the active job's current status.
const NEXT = {
  assigned: { to: 'at_restaurant', label: 'driver.actionAtRestaurant' },
  at_restaurant: { to: 'picked_up', label: 'driver.actionPickedUp' },
  picked_up: { to: 'delivered', label: 'driver.actionDelivered' },
};
const nextAction = computed(() => {
  const n = activeJob.value && NEXT[activeJob.value.status];
  return n ? { to: n.to, label: t(n.label) } : null;
});

const mapsLink = (lat, lng, address) => {
  if (lat != null && lng != null) return `https://www.google.com/maps/search/?api=1&query=${lat},${lng}`;
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(address || '')}`;
};

const earnings = ref(null);
const fetchEarnings = async () => {
  try {
    const { data } = await api.get('/driver/earnings/');
    earnings.value = data;
  } catch {
    earnings.value = null;
  }
};

// ── Delivery-code modal (replaces window.prompt) ─────────────────────────────────
const codeModalOpen = ref(false);
const codeInput = ref('');
const codeError = ref('');
const codeSubmitting = ref(false);
const codeFirstRef = ref(null);
let _codeReturnFocus = null;

const closeCodeModal = () => {
  codeModalOpen.value = false;
  _codeReturnFocus?.focus();
  _codeReturnFocus = null;
};

const submitDeliveryCode = async () => {
  const code = codeInput.value.trim();
  if (!code) { codeError.value = t('driver.enterDeliveryCode'); return; }
  codeError.value = '';
  codeSubmitting.value = true;
  const job = activeJob.value;
  try {
    const { data } = await api.patch(`/driver/jobs/${job.id}/status/`, { status: 'delivered', code });
    closeCodeModal();
    if (data.is_terminal) {
      activeJob.value = null;
      online.value = false;
      stopGeo();
      toast.show(t('driver.deliveredToast'), 'success');
      if (job && job.restaurant_slug) openCustomerRating(job);
      await fetchJobs();
      fetchEarnings();
    } else {
      activeJob.value = data;
    }
  } catch (err) {
    const errCode = err?.response?.data?.code;
    codeError.value = errCode === 'bad_delivery_code'
      ? t('driver.badDeliveryCode')
      : (err?.response?.data?.detail || t('driver.errorGeneric'));
  } finally {
    codeSubmitting.value = false;
  }
};

// ── Cash-out modal (replaces window.prompt) ───────────────────────────────────────
const cashoutModalOpen = ref(false);
const cashoutInput = ref('');
const cashoutModalError = ref('');
const cashoutFirstRef = ref(null);
let _cashoutReturnFocus = null;

const closeCashoutModal = () => {
  cashoutModalOpen.value = false;
  _cashoutReturnFocus?.focus();
  _cashoutReturnFocus = null;
};

const submitCashout = async () => {
  const amount = Number(String(cashoutInput.value).replace(',', '.'));
  if (!Number.isFinite(amount) || amount <= 0) {
    cashoutModalError.value = t('driver.errorGeneric');
    return;
  }
  cashoutModalError.value = '';
  busy.value = true;
  try {
    const { data } = await api.post('/driver/cashout/', { amount });
    cashout.value = data;
    closeCashoutModal();
  } catch (err) {
    cashoutModalError.value = err?.response?.data?.detail || t('driver.errorGeneric');
  } finally {
    busy.value = false;
  }
};

// ── Cash-out: redeem wallet balance for cash at a restaurant ─────────────────────
const cashout = ref(null); // current pending request { id, amount, code, ... }
const fetchCashout = async () => {
  try {
    const { data } = await api.get('/driver/cashout/');
    cashout.value = data.pending || null;
  } catch {
    cashout.value = null;
  }
};
const requestCashout = () => {
  _cashoutReturnFocus = document.activeElement;
  errorMsg.value = '';
  const max = Number(earnings.value?.available || 0);
  cashoutInput.value = String(max);
  cashoutModalError.value = '';
  cashoutModalOpen.value = true;
  nextTick(() => { cashoutFirstRef.value?.focus(); });
};
const cancelCashout = async () => {
  if (!cashout.value) return;
  busy.value = true;
  try {
    await api.post(`/driver/cashout/${cashout.value.id}/cancel/`);
    cashout.value = null;
  } catch {
    /* ignore */
  } finally {
    busy.value = false;
  }
};

const fetchStatus = async () => {
  try {
    const { data } = await api.get('/driver/status/');
    isDriver.value = Boolean(data.is_driver);
    approved.value = Boolean(data.driver_approved);
    online.value = Boolean(data.is_driver_online);
  } catch {
    isDriver.value = Boolean(customerStore.customer?.is_driver);
  }
};

const fetchJobs = async () => {
  if (!isDriver.value) return;
  loadingJobs.value = true;
  try {
    const { data } = await api.get('/driver/jobs/');
    activeJob.value = (data.active && data.active[0]) || null;
    pendingJobs.value = data.pending || [];
  } catch {
    /* keep last */
  } finally {
    loadingJobs.value = false;
  }
};

// Keep the job list fresh while the page is open (idempotent — never double-starts).
const ensurePoll = () => {
  if (!pollTimer) pollTimer = setInterval(fetchJobs, 15000);
};

const becomeDriver = async () => {
  errorMsg.value = '';
  busy.value = true;
  try {
    const { data } = await api.post('/driver/register/', { vehicle: vehicle.value });
    isDriver.value = Boolean(data.is_driver);
    approved.value = Boolean(data.driver_approved);
    online.value = Boolean(data.is_driver_online);
    if (customerStore.customer) customerStore.setCustomer({ ...customerStore.customer, is_driver: true });
    toast.show(approved.value ? t('driver.registered') : t('driver.applied'), 'success');
    if (approved.value) {
      await fetchJobs();
      ensurePoll();
    }
  } catch (err) {
    errorMsg.value = err?.response?.data?.detail || t('driver.errorGeneric');
  } finally {
    busy.value = false;
  }
};

const toggleOnline = async () => {
  errorMsg.value = '';
  busy.value = true;
  const next = !online.value;
  try {
    const { data } = await api.patch('/driver/status/', { online: next });
    online.value = Boolean(data.is_driver_online);
    if (online.value) {
      startGeo();
      // Subscribe to web push so new jobs reach the driver even when backgrounded.
      driverPush.subscribe().catch(() => {});
      await fetchJobs();
    } else {
      stopGeo();
    }
  } catch (err) {
    errorMsg.value = err?.response?.data?.detail || t('driver.errorGeneric');
  } finally {
    busy.value = false;
  }
};

const accept = async (jobId) => {
  errorMsg.value = '';
  busy.value = true;
  try {
    const { data } = await api.post(`/driver/jobs/${jobId}/accept/`, {});
    activeJob.value = data;
    pendingJobs.value = [];
  } catch (err) {
    errorMsg.value = err?.response?.data?.detail || t('driver.errorGeneric');
    await fetchJobs(); // someone else may have taken it
  } finally {
    busy.value = false;
  }
};

// Pass on an exclusive offer → it cascades to the next-nearest driver immediately.
const decline = async (jobId) => {
  errorMsg.value = '';
  busy.value = true;
  try {
    await api.post(`/driver/jobs/${jobId}/decline/`, {});
    // Drop it from view right away; the next poll reflects the cascade.
    pendingJobs.value = pendingJobs.value.filter((j) => j.id !== jobId);
  } catch {
    await fetchJobs();
  } finally {
    busy.value = false;
  }
};

const advance = async (toStatus, extra = {}) => {
  errorMsg.value = '';
  if (toStatus === 'delivered') {
    // Proof of delivery — open the code modal instead of window.prompt().
    _codeReturnFocus = document.activeElement;
    codeInput.value = '';
    codeError.value = '';
    codeModalOpen.value = true;
    await nextTick();
    codeFirstRef.value?.focus();
    return;
  }
  const payload = { status: toStatus, ...extra };
  busy.value = true;
  try {
    const job = activeJob.value;
    const { data } = await api.patch(`/driver/jobs/${job.id}/status/`, payload);
    if (data.is_terminal) {
      activeJob.value = null;
      online.value = false; // backend takes the driver offline after delivery
      stopGeo();
      toast.show(t('driver.deliveredToast'), 'success');
      if (job && job.restaurant_slug) openCustomerRating(job);
      await fetchJobs();
      fetchEarnings(); // a completed delivery just added to earnings
    } else {
      activeJob.value = data;
    }
  } catch (err) {
    errorMsg.value = err?.response?.data?.detail || t('driver.errorGeneric');
  } finally {
    busy.value = false;
  }
};

const FAIL_REASONS = ['customer_no_show', 'bad_address', 'driver_unable', 'other'];
const failingOpen = ref(false);
const failNote = ref('');
const openFail = () => {
  failNote.value = '';
  failingOpen.value = true;
};
const submitFail = async (reason) => {
  failingOpen.value = false;
  await advance('failed', { failure_reason: reason, failure_note: failNote.value.trim() });
};

// ── Rate the customer (driver → customer, after delivery) ──────────────────────
const ratingJob = ref(null);
const custRatingScore = ref(0);
const custRatingNote = ref('');
const submittingRating = ref(false);
const ratingDialogFirstFocus = ref(null);
let ratingTriggerEl = null;

watch(ratingJob, (val) => {
  if (val) {
    ratingTriggerEl = typeof document !== 'undefined' ? document.activeElement : null;
    nextTick(() => { ratingDialogFirstFocus.value?.focus(); });
  } else if (ratingTriggerEl) {
    ratingTriggerEl.focus();
    ratingTriggerEl = null;
  }
});

const openCustomerRating = (job) => {
  ratingJob.value = job;
  custRatingScore.value = 0;
  custRatingNote.value = '';
};

const submitCustomerRating = async () => {
  const job = ratingJob.value;
  if (!job || !custRatingScore.value || submittingRating.value) return;
  submittingRating.value = true;
  try {
    await api.post(
      `/marketplace/track/${job.order_number}/rate/?restaurant=${encodeURIComponent(job.restaurant_slug)}`,
      { role: 'driver', score: custRatingScore.value, note: custRatingNote.value },
    );
    ratingJob.value = null;
    toast.show(t('driver.ratingThanks'), 'success');
  } catch {
    toast.show(t('driver.ratingFailed'), 'error');
  } finally {
    submittingRating.value = false;
  }
};

// ── Geolocation ───────────────────────────────────────────────────────────────
const sendPosition = (lat, lng) => {
  const nowMs = Date.now();
  if (nowMs - lastPositionSent < 10000) return; // throttle to ~10s
  lastPositionSent = nowMs;
  api.post('/driver/position/', { lat, lng }).catch(() => {});
};

const startGeo = () => {
  geoError.value = '';
  if (!('geolocation' in navigator)) {
    geoError.value = t('driver.geoUnavailable');
    return;
  }
  if (geoWatchId !== null) return;
  geoWatchId = navigator.geolocation.watchPosition(
    (pos) => { geoError.value = ''; sendPosition(pos.coords.latitude, pos.coords.longitude); },
    () => { geoError.value = t('driver.locationDenied'); },
    { enableHighAccuracy: true, maximumAge: 15000, timeout: 20000 },
  );
};

const stopGeo = () => {
  if (geoWatchId !== null) {
    navigator.geolocation.clearWatch(geoWatchId);
    geoWatchId = null;
  }
};

onMounted(async () => {
  if (typeof window !== 'undefined') {
    window.addEventListener('beforeinstallprompt', onBeforeInstallPrompt);
    window.addEventListener('appinstalled', onAppInstalled);
  }
  await customerStore.fetchCustomer();
  if (!customerStore.isAuthenticated) return;
  await fetchStatus();
  if (isDriver.value && approved.value) {
    await fetchJobs();
    fetchEarnings();
    fetchCashout();
    if (online.value) {
      startGeo();
      driverPush.autoRestore().catch(() => {}); // re-arm push if previously opted in
    }
    ensurePoll();
  }
});

onBeforeUnmount(() => {
  if (pollTimer) clearInterval(pollTimer);
  stopGeo();
  if (typeof window !== 'undefined') {
    window.removeEventListener('beforeinstallprompt', onBeforeInstallPrompt);
    window.removeEventListener('appinstalled', onAppInstalled);
  }
});
</script>
