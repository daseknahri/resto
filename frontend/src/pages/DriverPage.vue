<template>
  <div class="ui-page-shell space-y-4">
    <!-- Header -->
    <header class="ui-hero-ribbon ui-reveal flex items-start justify-between gap-3 px-4 py-3.5">
      <div class="min-w-0">
        <p class="ui-kicker">{{ t('driver.kicker') }}</p>
        <h1 class="ui-display text-2xl font-semibold leading-tight text-white">{{ t('driver.title') }}</h1>
      </div>
      <!-- Persistent driver⇄client switch: returns the rider to the consumer hub. -->
      <RouterLink
        v-if="customerStore.isAuthenticated"
        :to="{ name: 'super-app-hub' }"
        class="ui-btn-outline ui-touch-target inline-flex shrink-0 items-center gap-1.5 px-3 py-2 text-[11px] sm:text-sm"
      >
        <AppIcon name="home" class="h-3.5 w-3.5" aria-hidden="true" />
        <span>{{ t('driver.switchToOrdering') }}</span>
      </RouterLink>
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
          class="ui-btn-primary ui-touch-target inline-flex w-full items-center justify-center gap-2 text-sm"
          :disabled="busy"
          :aria-busy="busy"
          @click="becomeDriver"
        >
          <svg v-if="busy" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
          {{ busy ? t('common.loading') : t('driver.becomeCta') }}
        </button>
      </template>
    </div>

    <!-- Applied, awaiting admin approval -->
    <div v-else-if="!approved" class="ui-panel p-6 space-y-4 text-center ui-reveal">
      <div class="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl border border-amber-500/30 bg-amber-500/10">
        <AppIcon name="info" class="h-6 w-6 text-amber-300" aria-hidden="true" />
      </div>
      <div class="space-y-1.5">
        <p class="text-base font-semibold text-slate-100">{{ t('driver.pendingTitle') }}</p>
        <p class="ui-subtle">{{ t('driver.pendingBody') }}</p>
      </div>
      <button
        class="ui-btn-outline ui-press px-5 py-2 text-sm"
        :disabled="busy"
        @click="fetchStatus"
      >
        {{ t('driver.pendingRefresh') }}
      </button>
    </div>

    <!-- Driver dashboard (approved) -->
    <template v-else>
      <!-- First-approved welcome (one-time, dismissible) -->
      <div v-if="!driverWelcomed" class="ui-panel space-y-3 border border-emerald-500/30 bg-emerald-900/10 p-4 ui-reveal">
        <div class="space-y-1">
          <p class="text-base font-semibold text-emerald-200">{{ t('driver.welcomeTitle') }}</p>
          <p class="ui-subtle text-sm">{{ t('driver.welcomeBody') }}</p>
        </div>
        <button class="ui-btn-outline ui-press w-full px-4 py-2 text-sm" @click="dismissDriverWelcome">
          {{ t('driver.welcomeDismiss') }}
        </button>
      </div>
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

      <!-- Vehicle-type picker -->
      <div class="ui-panel p-4 space-y-2.5 ui-reveal">
        <div class="flex items-center justify-between gap-2">
          <p class="text-xs font-medium text-slate-400">{{ t('driverRides.vehicleTypeLabel') }}</p>
          <p class="text-[11px]" :class="driverVehicleType === 'car' ? 'text-emerald-400' : 'text-amber-400'">{{ t('driverRides.vehicleTypeHint') }}</p>
        </div>
        <div class="flex gap-2" role="group" :aria-label="t('driverRides.vehicleTypeLabel')">
          <button
            v-for="vt in VEHICLE_TYPES"
            :key="vt.value"
            class="ui-press flex-1 rounded-xl border px-3 py-2 text-sm font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-400"
            :class="driverVehicleType === vt.value
              ? 'border-emerald-500/50 bg-emerald-600/20 text-emerald-300'
              : 'border-slate-700 bg-slate-900/40 text-slate-400 hover:border-slate-600 hover:text-slate-200'"
            :aria-pressed="driverVehicleType === vt.value"
            :disabled="busy"
            @click="setVehicleType(vt.value)"
          >
            {{ t(vt.label) }}
          </button>
        </div>
      </div>

      <!-- Car-docs card: only for car drivers, only when not approved -->
      <div
        v-if="driverVehicleType === 'car'"
        class="ui-panel p-4 space-y-3 ui-reveal"
      >
        <!-- Approved chip -->
        <template v-if="driverCarApproved">
          <div class="flex items-center gap-2">
            <span class="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/15 px-3 py-1 text-xs font-semibold text-emerald-300">
              <AppIcon name="check" class="h-3.5 w-3.5" aria-hidden="true" />
              {{ t('driverDocs.approved') }}
            </span>
          </div>
        </template>
        <!-- Upload UI -->
        <template v-else>
          <div class="space-y-1">
            <p class="text-sm font-semibold text-slate-100">{{ t('driverDocs.title') }}</p>
            <p class="text-xs text-slate-400">{{ t('driverDocs.hint') }}</p>
          </div>
          <!-- Licence row -->
          <div class="flex items-center justify-between gap-3">
            <span class="text-sm text-slate-300">{{ t('driverDocs.licence') }}</span>
            <div class="flex items-center gap-2 shrink-0">
              <span
                v-if="driverLicenceUrl"
                class="rounded-full bg-amber-500/15 px-2.5 py-0.5 text-[11px] font-semibold text-amber-300"
              >{{ t('driverDocs.submitted') }}</span>
              <span
                v-else
                class="rounded-full bg-slate-700/60 px-2.5 py-0.5 text-[11px] text-slate-400"
              >—</span>
              <label class="ui-btn-outline ui-press cursor-pointer px-3 py-1.5 text-xs disabled:opacity-50">
                {{ driverLicenceUrl ? t('driverDocs.replace') : t('driverDocs.upload') }}
                <input
                  type="file"
                  accept="image/*"
                  class="sr-only"
                  :disabled="uploadingDoc"
                  @change="uploadDoc('licence', $event)"
                />
              </label>
            </div>
          </div>
          <!-- Insurance row -->
          <div class="flex items-center justify-between gap-3">
            <span class="text-sm text-slate-300">{{ t('driverDocs.insurance') }}</span>
            <div class="flex items-center gap-2 shrink-0">
              <span
                v-if="driverInsuranceUrl"
                class="rounded-full bg-amber-500/15 px-2.5 py-0.5 text-[11px] font-semibold text-amber-300"
              >{{ t('driverDocs.submitted') }}</span>
              <span
                v-else
                class="rounded-full bg-slate-700/60 px-2.5 py-0.5 text-[11px] text-slate-400"
              >—</span>
              <label class="ui-btn-outline ui-press cursor-pointer px-3 py-1.5 text-xs disabled:opacity-50">
                {{ driverInsuranceUrl ? t('driverDocs.replace') : t('driverDocs.upload') }}
                <input
                  type="file"
                  accept="image/*"
                  class="sr-only"
                  :disabled="uploadingDoc"
                  @change="uploadDoc('insurance', $event)"
                />
              </label>
            </div>
          </div>
        </template>
      </div>

      <div v-if="errorMsg" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
        <AppIcon name="info" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" aria-hidden="true" />
        <p class="flex-1 text-sm text-red-300">{{ errorMsg }}</p>
      </div>

      <!-- Today earnings strip — compact summary for a driver doing multiple drops in a day -->
      <div
        v-if="earnings && (online || earnings.deliveries_today > 0)"
        class="ui-panel flex items-center gap-3 px-4 py-2.5 ui-reveal"
      >
        <span class="flex-1 text-xs font-medium text-slate-300">
          {{ t('driver.todayStrip', { deliveries_today: earnings.deliveries_today, earned_today: fmtMoney(earnings.earned_today) }) }}
        </span>
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
        <!-- Ride earnings row — only shown when driver has completed rides -->
        <div v-if="earnings.rides_completed > 0" class="border-t border-slate-700/40 flex items-center justify-between px-4 py-3">
          <p class="ui-stat-label">{{ t('driverRides.earningsLabel') }}</p>
          <div class="text-right">
            <p class="text-sm font-bold tabular-nums text-sky-300">{{ fmtMoney(earnings.ride_earned) }}</p>
            <p class="text-[11px] text-slate-400">{{ t('driverRides.earningsCount', { n: earnings.rides_completed }) }}</p>
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
            {{ statusLabel(activeJob.status, activeJob.business_type) }}
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
                <p class="truncate text-sm text-slate-200" :title="activeJob.pickup_address || undefined">{{ activeJob.pickup_address || t('driver.openMaps') }}</p>
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
                <p class="truncate text-sm text-slate-200" :title="activeJob.delivery_address || undefined">{{ activeJob.delivery_address || t('driver.openMaps') }}</p>
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
                <p class="truncate text-sm text-slate-200" :title="activeJob.customer_name || activeJob.customer_phone || undefined">{{ activeJob.customer_name || activeJob.customer_phone }}</p>
              </div>
              <span class="shrink-0 text-xs font-semibold text-sky-300">{{ t('driver.call') }}</span>
            </a>
            <!-- Call the restaurant / merchant — lets the driver check if food is ready -->
            <a
              v-if="activeJob.restaurant_phone"
              :href="`tel:${activeJob.restaurant_phone}`"
              class="flex items-center gap-3 rounded-xl border border-amber-700/50 bg-amber-900/15 px-3 py-3 transition-colors hover:border-amber-600/60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-400"
              :aria-label="`${t('driver.callRestaurant')}: ${activeJob.restaurant_name || activeJob.restaurant_phone}`"
            >
              <span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-amber-500/15">
                <AppIcon name="phone" class="h-4 w-4 text-amber-300" aria-hidden="true" />
              </span>
              <div class="min-w-0 flex-1">
                <p class="text-[11px] uppercase tracking-wider text-slate-500">{{ t('driver.callRestaurant') }}</p>
                <p class="truncate text-sm text-slate-200" :title="activeJob.restaurant_name || activeJob.restaurant_phone || undefined">{{ activeJob.restaurant_name || activeJob.restaurant_phone }}</p>
              </div>
              <span class="shrink-0 text-xs font-semibold text-amber-300">{{ t('driver.call') }}</span>
            </a>
          </div>

          <!-- What's in the order -->
          <div v-if="activeJob.items && activeJob.items.length" class="rounded-xl border border-slate-700/60 bg-slate-900/40 px-3 py-3">
            <p class="mb-2 text-[11px] uppercase tracking-wider text-slate-500">{{ t('driver.itemsTitle') }}</p>
            <ul class="space-y-1">
              <li v-for="(it, idx) in activeJob.items" :key="idx" class="flex justify-between gap-2 text-sm text-slate-300">
                <span class="truncate" :title="it.name">{{ it.name }}</span>
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
            class="ui-btn-primary ui-touch-target inline-flex w-full items-center justify-center gap-2 text-sm"
            :disabled="busy"
            :aria-busy="busy"
            @click="advance(nextAction.to)"
          >
            <svg v-if="busy" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
            {{ busy ? t('common.loading') : nextAction.label }}
          </button>
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
              maxlength="500"
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
                <p class="truncate text-sm font-semibold text-slate-100" :title="job.restaurant_name || ('#' + job.order_number)">{{ job.restaurant_name || ('#' + job.order_number) }}</p>
                <p class="text-[11px] text-slate-500">{{ t('driver.order') }} #{{ job.order_number }}</p>
              </div>
              <span class="shrink-0 text-base font-bold tabular-nums text-emerald-300">{{ fmtMoney(job.driver_payout) }}</span>
            </div>
            <!-- Meta: distance, items, payment type, offer countdown -->
            <div class="flex flex-wrap items-center gap-x-2.5 gap-y-1.5 text-xs text-slate-400">
              <span v-if="job.offered_to_me" class="rounded-full bg-sky-500/15 px-2.5 py-0.5 font-semibold text-sky-300">
                {{ t('driver.offeredToYou') }}
              </span>
              <!-- Offer countdown — amber when time is low, red when near zero -->
              <span
                v-if="job.offer_expires_at && offerSecondsLeft(job.offer_expires_at) > 0"
                class="rounded-full px-2.5 py-0.5 font-semibold tabular-nums"
                :class="offerSecondsLeft(job.offer_expires_at) <= 5 ? 'bg-red-500/20 text-red-300' : offerSecondsLeft(job.offer_expires_at) <= 10 ? 'bg-amber-500/20 text-amber-300' : 'bg-slate-700/60 text-slate-300'"
              >
                {{ t('driver.offerSecondsLeft', { n: offerSecondsLeft(job.offer_expires_at) }) }}
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
            <p v-if="job.delivery_address" class="flex items-start gap-1.5 truncate text-sm text-slate-300" :title="job.delivery_address">
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

      <!-- ── Rides section (car drivers only, while online and no active delivery) ── -->
      <template v-if="online && !activeJob && driverVehicleType === 'car'">
        <!-- Waiting-for-car-approval notice -->
        <div
          v-if="!driverCarApproved && (driverLicenceUrl || driverInsuranceUrl)"
          class="ui-panel p-4 flex items-start gap-3 ui-reveal"
        >
          <AppIcon name="info" class="mt-0.5 h-4 w-4 shrink-0 text-amber-300" aria-hidden="true" />
          <p class="text-sm text-amber-200">{{ t('driverRides.waitingCarApproval') }}</p>
        </div>

        <!-- Rate last passenger inline card -->
        <div
          v-if="lastCompleted && lastCompleted.driver_rider_rating == null && !riderRateDone"
          class="ui-panel p-4 space-y-3 ui-reveal"
        >
          <p class="text-sm font-semibold text-slate-100">{{ t('driverRides.lastRideTitle') }}</p>
          <p class="text-xs text-slate-400">{{ t('driverRides.rateRider') }}</p>
          <div class="flex items-center gap-1" role="group" :aria-label="t('driverRides.rateRider')">
            <button
              v-for="n in 5" :key="n" type="button"
              class="ui-press text-3xl leading-none transition-transform hover:scale-110 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-400"
              :class="n <= riderRatingScore ? 'text-amber-400' : 'text-slate-600'"
              :aria-label="t('common.rateNStars', { n })"
              @click="riderRatingScore = n"
            >★</button>
          </div>
          <button
            class="ui-btn-primary ui-press inline-flex items-center gap-2 px-4 py-2 text-sm disabled:opacity-50"
            :disabled="!riderRatingScore || submittingRiderRating"
            :aria-busy="submittingRiderRating"
            @click="submitRiderRating"
          >
            <svg v-if="submittingRiderRating" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
            {{ submittingRiderRating ? t('common.loading') : t('driver.rateSubmit') }}
          </button>
        </div>

        <!-- Active ride card -->
        <div v-if="activeRide" class="ui-panel p-0 overflow-hidden ui-reveal">
          <div class="flex items-center justify-between gap-2 border-b border-slate-700/40 px-4 py-3">
            <p class="text-sm font-semibold text-slate-200">{{ t('driverRides.offersTitle') }}</p>
            <span class="ui-status-pill">{{ rideStatusLabel(activeRide.status) }}</span>
          </div>
          <div class="p-4 space-y-3">
            <!-- Pickup / dropoff addresses -->
            <div class="space-y-2">
              <a
                v-if="activeRide.pickup_address"
                :href="mapsLink(null, null, activeRide.pickup_address)"
                target="_blank" rel="noopener"
                class="flex items-center gap-3 rounded-xl border border-slate-700/60 bg-slate-900/40 px-3 py-3 transition-colors hover:border-slate-600/80 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-400"
              >
                <span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-amber-500/15">
                  <AppIcon name="location" class="h-4 w-4 text-amber-300" aria-hidden="true" />
                </span>
                <div class="min-w-0 flex-1">
                  <p class="text-[11px] uppercase tracking-wider text-slate-500">{{ t('ridePage.pickupLabel') }}</p>
                  <p class="truncate text-sm text-slate-200" :title="activeRide.pickup_address">{{ activeRide.pickup_address }}</p>
                </div>
                <AppIcon name="chevronRight" class="h-4 w-4 shrink-0 text-slate-600 rtl:scale-x-[-1]" aria-hidden="true" />
              </a>
              <a
                v-if="activeRide.dropoff_address"
                :href="mapsLink(null, null, activeRide.dropoff_address)"
                target="_blank" rel="noopener"
                class="flex items-center gap-3 rounded-xl border border-slate-700/60 bg-slate-900/40 px-3 py-3 transition-colors hover:border-slate-600/80 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-400"
              >
                <span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-emerald-500/15">
                  <AppIcon name="location" class="h-4 w-4 text-emerald-300" aria-hidden="true" />
                </span>
                <div class="min-w-0 flex-1">
                  <p class="text-[11px] uppercase tracking-wider text-slate-500">{{ t('ridePage.dropoffLabel') }}</p>
                  <p class="truncate text-sm text-slate-200" :title="activeRide.dropoff_address">{{ activeRide.dropoff_address }}</p>
                </div>
                <AppIcon name="chevronRight" class="h-4 w-4 shrink-0 text-slate-600 rtl:scale-x-[-1]" aria-hidden="true" />
              </a>
            </div>
            <!-- Fare + payment -->
            <div class="flex items-center justify-between rounded-xl border border-emerald-700/30 bg-emerald-900/10 px-3 py-2.5">
              <span class="text-xs font-medium text-slate-400">{{ t('driverRides.fareLabel') }}</span>
              <div class="flex items-center gap-2">
                <span class="text-base font-bold tabular-nums text-emerald-300">{{ fmtMoney(activeRide.fare) }}</span>
                <span
                  v-if="activeRide.payment_method === 'cash'"
                  class="rounded-full bg-amber-500/15 px-2 py-0.5 text-[11px] font-semibold text-amber-300"
                >{{ t('driverRides.collectCash', { amount: fmtMoney(activeRide.fare) }) }}</span>
                <span
                  v-else
                  class="rounded-full bg-emerald-500/12 px-2 py-0.5 text-[11px] font-semibold text-emerald-300"
                >{{ t('driverRides.paidWallet') }}</span>
              </div>
            </div>
            <!-- Call recipient (packages only — PII gated to own active trip) -->
            <a
              v-if="activeRide.kind === 'package' && activeRide.recipient_phone"
              :href="`tel:${activeRide.recipient_phone}`"
              class="flex items-center gap-3 rounded-xl border border-sky-700/50 bg-sky-900/20 px-3 py-3 transition-colors hover:border-sky-600/60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-400"
              :aria-label="`${t('driverRides.callRecipient')}: ${activeRide.recipient_phone}`"
            >
              <span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-sky-500/15">
                <AppIcon name="phone" class="h-4 w-4 text-sky-300" aria-hidden="true" />
              </span>
              <div class="min-w-0 flex-1">
                <p class="text-[11px] uppercase tracking-wider text-slate-500">{{ t('driverRides.callRecipient') }}</p>
                <p class="truncate text-sm text-slate-200">{{ activeRide.recipient_phone }}</p>
              </div>
              <span class="shrink-0 text-xs font-semibold text-sky-300">{{ t('driver.call') }}</span>
            </a>
            <!-- Action buttons -->
            <button
              v-if="activeRide.status === 'accepted'"
              class="ui-btn-primary ui-touch-target inline-flex w-full items-center justify-center gap-2 text-sm"
              :disabled="busy"
              :aria-busy="busy"
              @click="advanceRide(activeRide.id, 'arrived')"
            >
              <svg v-if="busy" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
              {{ busy ? t('common.loading') : t('driverRides.arrivedCta') }}
            </button>
            <button
              v-else-if="activeRide.status === 'arrived'"
              class="ui-btn-primary ui-touch-target inline-flex w-full items-center justify-center gap-2 text-sm"
              :disabled="busy"
              :aria-busy="busy"
              @click="advanceRide(activeRide.id, 'in_progress')"
            >
              <svg v-if="busy" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
              {{ busy ? t('common.loading') : t('driverRides.startCta') }}
            </button>
            <!-- Package in_progress: inline code entry -->
            <template v-else-if="activeRide.status === 'in_progress' && activeRide.kind === 'package'">
              <div class="space-y-2">
                <label class="block text-xs font-medium text-slate-400" :for="`pkg-code-${activeRide.id}`">
                  {{ t('driverRides.enterCode') }}
                </label>
                <input
                  :id="`pkg-code-${activeRide.id}`"
                  v-model="packageCodeInput"
                  type="text"
                  inputmode="numeric"
                  maxlength="6"
                  autocomplete="one-time-code"
                  class="ui-input text-center text-lg tracking-[0.35em] font-bold tabular-nums"
                  :placeholder="t('driverRides.enterCode')"
                  :aria-label="t('driverRides.enterCode')"
                  @keydown.enter="submitPackageCode(activeRide.id)"
                />
                <div v-if="packageCodeError" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
                  <p class="text-sm text-red-300">{{ packageCodeError }}</p>
                </div>
                <button
                  class="ui-btn-primary ui-touch-target inline-flex w-full items-center justify-center gap-2 text-sm disabled:opacity-50"
                  :disabled="busy || !packageCodeInput.trim()"
                  :aria-busy="busy"
                  @click="submitPackageCode(activeRide.id)"
                >
                  <svg v-if="busy" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
                  {{ busy ? t('common.loading') : t('driverRides.codeCta') }}
                </button>
              </div>
            </template>
            <!-- Non-package in_progress: normal complete button -->
            <button
              v-else-if="activeRide.status === 'in_progress'"
              class="ui-btn-primary ui-touch-target inline-flex w-full items-center justify-center gap-2 text-sm"
              :disabled="busy"
              :aria-busy="busy"
              @click="advanceRide(activeRide.id, 'completed')"
            >
              <svg v-if="busy" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
              {{ busy ? t('common.loading') : t('driverRides.completeCta') }}
            </button>
            <!-- Release / abandon -->
            <button
              v-if="activeRide.status !== 'completed'"
              class="ui-touch-target w-full rounded-xl border border-red-500/40 px-4 py-2 text-xs text-red-300 hover:border-red-400/70 hover:text-red-200 transition-colors disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-400"
              :disabled="busy"
              @click="confirmReleaseRide"
            >
              {{ t('driverRides.abandonCta') }}
            </button>
          </div>
        </div>

        <!-- Ride offer cards -->
        <div v-else class="ui-panel p-4 space-y-3 ui-reveal">
          <div class="flex items-center justify-between gap-2">
            <p class="text-sm font-semibold text-slate-200">{{ t('driverRides.offersTitle') }}</p>
            <button
              class="ui-press text-xs text-slate-400 hover:text-slate-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-400"
              :disabled="loadingRides"
              @click="fetchRides"
            >
              {{ t('driver.refresh') }}
            </button>
          </div>
          <div v-if="loadingRides && !rideOffers.length" class="space-y-2" aria-busy="true">
            <div v-for="i in 2" :key="i" class="ui-skeleton h-24" />
          </div>
          <div v-else-if="!rideOffers.length" class="ui-empty-state text-center py-5 space-y-2">
            <AppIcon name="location" class="mx-auto h-7 w-7 text-slate-600" aria-hidden="true" />
            <p class="text-sm font-semibold text-slate-100">{{ t('driverRides.noOffers') }}</p>
          </div>
          <ul v-else class="space-y-2">
            <li
              v-for="(ride, index) in rideOffers"
              :key="ride.id"
              class="ui-reveal rounded-2xl border border-slate-700/60 bg-slate-900/40 p-3 space-y-2.5"
              :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
            >
              <!-- Pickup / dropoff row -->
              <div class="space-y-1.5">
                <p class="flex items-start gap-1.5 text-sm text-slate-200" :title="ride.pickup_address">
                  <span class="mt-0.5 inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-amber-500/20 text-[10px] font-bold text-amber-300">A</span>
                  <span class="truncate">{{ ride.pickup_address }}</span>
                </p>
                <p class="flex items-start gap-1.5 text-sm text-slate-300" :title="ride.dropoff_address">
                  <span class="mt-0.5 inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-emerald-500/20 text-[10px] font-bold text-emerald-300">B</span>
                  <span class="truncate">{{ ride.dropoff_address }}</span>
                </p>
              </div>
              <!-- Package badge + recipient info -->
              <template v-if="ride.kind === 'package'">
                <div class="flex flex-wrap items-center gap-2">
                  <span class="inline-flex items-center gap-1 rounded-full bg-sky-500/15 px-2.5 py-0.5 text-[11px] font-semibold text-sky-300">
                    <span aria-hidden="true">📦</span>{{ t('driverRides.packageBadge') }}
                  </span>
                  <span v-if="ride.recipient_name" class="text-xs text-slate-300">
                    <span class="text-slate-500">{{ t('driverRides.recipientLabel') }}:</span> {{ ride.recipient_name }}
                  </span>
                </div>
                <p v-if="ride.package_note" class="text-xs text-slate-500 leading-snug">{{ ride.package_note }}</p>
              </template>
              <!-- Meta chips: fare, distance, to-pickup, payment -->
              <div class="flex flex-wrap items-center gap-x-2.5 gap-y-1.5 text-xs text-slate-400">
                <span class="text-base font-bold tabular-nums text-emerald-300">{{ fmtMoney(ride.fare) }}</span>
                <span v-if="ride.distance_km != null" class="inline-flex items-center gap-1">
                  <AppIcon name="location" class="h-3 w-3" aria-hidden="true" />{{ t('driver.distanceKm', { km: ride.distance_km }) }}
                </span>
                <span v-if="ride.distance_to_pickup_km != null" class="inline-flex items-center gap-1 text-sky-300">
                  <AppIcon name="location" class="h-3 w-3" aria-hidden="true" />{{ t('driverRides.toPickup', { km: ride.distance_to_pickup_km }) }}
                </span>
                <span
                  v-if="ride.payment_method === 'cash'"
                  class="rounded-full bg-amber-500/15 px-2.5 py-0.5 font-semibold text-amber-300"
                >{{ t('driverRides.collectCash', { amount: fmtMoney(ride.fare) }) }}</span>
                <span
                  v-else
                  class="rounded-full bg-emerald-500/12 px-2.5 py-0.5 font-semibold text-emerald-300"
                >{{ t('driverRides.paidWallet') }}</span>
              </div>
              <!-- Accept button -->
              <button
                class="ui-btn-primary ui-touch-target w-full text-sm"
                :disabled="busy"
                @click="acceptRide(ride.id)"
              >
                {{ t('driverRides.acceptCta') }}
              </button>
            </li>
          </ul>
        </div>
      </template>

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
                  <p class="truncate text-sm text-slate-200" :title="d.restaurant_name || ('#' + d.order_number)">{{ d.restaurant_name || ('#' + d.order_number) }}</p>
                  <p class="text-[11px] text-slate-500">{{ statusLabel(d.status) }} · {{ fmtDate(d.delivered_at || d.failed_at || d.created_at) }}</p>
                </div>
                <span class="shrink-0 text-sm font-semibold tabular-nums" :class="d.status === 'delivered' ? 'text-emerald-300' : 'text-slate-500'">{{ fmtMoney(d.driver_payout) }}</span>
              </li>
            </ul>
          </template>
        </div>
      </div>

      <!-- Ride history (car drivers only) -->
      <div v-if="driverVehicleType === 'car'" class="ui-panel p-4 space-y-3 ui-reveal">
        <button
          class="flex w-full items-center justify-between gap-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-400"
          :aria-expanded="showRideHistory"
          aria-controls="driver-ride-history-panel"
          @click="toggleRideHistory"
        >
          <p class="text-sm font-semibold text-slate-200">{{ t('driverRides.historyTitle') }}</p>
          <AppIcon :name="showRideHistory ? 'chevronUp' : 'chevronDown'" class="h-4 w-4 shrink-0 text-slate-500" aria-hidden="true" />
        </button>
        <div id="driver-ride-history-panel">
          <template v-if="showRideHistory">
            <div v-if="loadingRideHistory && !rideHistory.length" class="space-y-2" aria-busy="true">
              <div v-for="i in 3" :key="i" class="ui-skeleton h-12" />
            </div>
            <div v-else-if="!rideHistory.length" class="ui-empty-state text-center py-4 space-y-1">
              <p class="text-sm font-semibold text-slate-100">{{ t('driverRides.historyEmpty') }}</p>
            </div>
            <ul v-else class="space-y-2">
              <li
                v-for="(r, index) in rideHistory"
                :key="r.id"
                class="ui-reveal rounded-xl border border-slate-700/60 bg-slate-900/40 px-3 py-2.5 space-y-1"
                :style="{ '--ui-delay': `${Math.min(index, 9) * 20}ms` }"
              >
                <div class="flex items-start justify-between gap-3">
                  <p class="truncate text-sm text-slate-200" :title="r.dropoff_address"><span v-if="r.kind === 'package'" aria-hidden="true">📦 </span>{{ r.dropoff_address }}</p>
                  <div class="flex shrink-0 items-center gap-1.5">
                    <span
                      v-if="r.payment_method === 'cash'"
                      class="rounded-full bg-amber-500/15 px-2 py-0.5 text-[11px] font-semibold text-amber-300"
                    >{{ t('driverRides.collectCash', { amount: fmtMoney(r.fare) }) }}</span>
                    <span
                      v-else
                      class="rounded-full bg-emerald-500/12 px-2 py-0.5 text-[11px] font-semibold text-emerald-300"
                    >{{ t('driverRides.paidWallet') }}</span>
                    <span class="text-sm font-bold tabular-nums text-emerald-300">{{ fmtMoney(r.fare) }}</span>
                  </div>
                </div>
                <div class="flex items-center gap-3 text-[11px] text-slate-500">
                  <span>{{ fmtDate(r.completed_at) }}</span>
                  <span v-if="r.driver_rider_rating != null" class="flex items-center gap-0.5 text-amber-400">
                    <span aria-hidden="true">★</span>
                    <span>{{ r.driver_rider_rating }}</span>
                  </span>
                </div>
              </li>
            </ul>
          </template>
        </div>
      </div>
    </template>
  </div>

  <!-- Post-delivery "Go online for the next drop" sticky CTA.
       Only shown when the driver just completed a delivery, is now offline,
       and has no active job. Dismissable. Does NOT change backend behaviour. -->
  <Teleport to="body">
    <div
      v-if="showGoOnlineCta"
      class="fixed bottom-0 inset-x-0 z-[1500] flex items-center gap-3 border-t border-emerald-500/30 bg-slate-950/95 px-4 py-3 backdrop-blur-sm safe-b"
      role="status"
      aria-live="polite"
    >
      <button
        class="ui-btn-primary ui-touch-target flex-1 text-sm font-semibold shadow-lg shadow-emerald-900/40"
        @click="handleGoOnlineCta"
      >
        {{ t('driver.goOnlineNextDrop') }}
      </button>
      <button
        class="ui-press shrink-0 rounded-full p-2 text-slate-400 hover:text-slate-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-400"
        :aria-label="t('driver.goOnlineNextDropDismiss')"
        @click="showGoOnlineCta = false"
      >
        <AppIcon name="close" class="h-5 w-5" aria-hidden="true" />
      </button>
    </div>
  </Teleport>

  <!-- Release-ride confirm modal -->
  <Teleport to="body">
    <div
      v-if="releaseRideConfirmOpen"
      class="fixed inset-0 z-[2000] flex items-end justify-center bg-black/60 p-3 backdrop-blur-sm sm:items-center"
      @click.self="releaseRideConfirmOpen = false"
      @keydown.esc="releaseRideConfirmOpen = false"
    >
      <div
        role="dialog"
        aria-modal="true"
        :aria-label="t('driverRides.abandonCta')"
        class="w-full max-w-sm space-y-4 rounded-2xl border border-slate-700 bg-slate-900 p-5 shadow-2xl"
      >
        <p class="text-sm font-semibold text-white">{{ t('driverRides.abandonCta') }}?</p>
        <div class="flex items-center justify-end gap-2 pt-1">
          <button class="ui-btn-outline ui-press px-3 py-2 text-xs" @click="releaseRideConfirmOpen = false">
            {{ t('common.cancel') }}
          </button>
          <button
            class="ui-press inline-flex items-center gap-2 rounded-xl border border-red-500/60 px-4 py-2 text-sm font-semibold text-red-300 hover:border-red-400 disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-400"
            :disabled="busy"
            :aria-busy="busy"
            @click="releaseRide"
          >
            <svg v-if="busy" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
            {{ busy ? t('common.loading') : t('driverRides.abandonCta') }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>

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
            class="ui-btn-primary ui-press inline-flex items-center gap-2 px-4 py-2 text-sm disabled:opacity-50"
            :disabled="!custRatingScore || submittingRating"
            :aria-busy="submittingRating"
            @click="submitCustomerRating"
          >
            <svg v-if="submittingRating" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
            {{ submittingRating ? t('common.loading') : t('driver.rateSubmit') }}
          </button>
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
          inputmode="numeric"
          pattern="[0-9]*"
          class="ui-input text-center text-lg tracking-[0.3em] font-bold"
          :placeholder="t('driver.enterDeliveryCode')"
          :aria-label="t('driver.enterDeliveryCode')"
          autocomplete="one-time-code"
          maxlength="6"
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
            class="ui-btn-primary ui-press inline-flex items-center gap-1.5 px-4 py-2 text-sm disabled:opacity-50"
            :disabled="!codeInput.trim() || codeSubmitting"
            :aria-busy="codeSubmitting"
            @click="submitDeliveryCode"
          >
            <svg v-if="codeSubmitting" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-4 w-4 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
            {{ codeSubmitting ? t('common.loading') : t('common.confirm') }}
          </button>
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
            class="ui-btn-primary ui-press inline-flex items-center gap-2 px-4 py-2 text-sm disabled:opacity-50"
            :disabled="busy"
            :aria-busy="busy"
            @click="submitCashout"
          >
            <svg v-if="busy" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
            {{ busy ? t('common.loading') : t('driver.cashOut') }}
          </button>
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
import { pickupLabelKey } from '../lib/deliveryVocab';

const { t, currentLocale } = useI18n();
const customerStore = useCustomerStore();
const toast = useToastStore();
const driverPush = useCustomerPush();

const isDriver = ref(false);
const approved = ref(false);

// First-approved welcome (one-time, dismissible). Shows once after a driver is
// approved; a localStorage flag suppresses it thereafter.
const DRIVER_WELCOMED_KEY = 'kepoli.driver.welcomed';
const driverWelcomed = ref(false);
try { driverWelcomed.value = localStorage.getItem(DRIVER_WELCOMED_KEY) === '1'; } catch (e) { void e; driverWelcomed.value = true; }
const dismissDriverWelcome = () => {
  driverWelcomed.value = true;
  try { localStorage.setItem(DRIVER_WELCOMED_KEY, '1'); } catch (e) { void e; }
};
const vehicle = ref('');
const online = ref(false);
const activeJob = ref(null);
const pendingJobs = ref([]);

// ── Rides (ride-hailing) ─────────────────────────────────────────────────────
const driverVehicleType = ref('motorbike'); // populated from /driver/status/
const rideOffers = ref([]);
const activeRide = ref(null);
const loadingRides = ref(false);
const releaseRideConfirmOpen = ref(false);

// ── Package handover code (inline on ride completion) ─────────────────────────
const packageCodeInput = ref('');
const packageCodeError = ref('');

// ── Car documents ─────────────────────────────────────────────────────────────
const driverCarApproved = ref(false);
const driverLicenceUrl = ref('');
const driverInsuranceUrl = ref('');
const uploadingDoc = ref(false);

// ── Rate last passenger (from last_completed window) ──────────────────────────
const lastCompleted = ref(null);
const riderRatingScore = ref(0);
const riderRateDone = ref(false);
const submittingRiderRating = ref(false);

const VEHICLE_TYPES = [
  { value: 'car', label: 'driverRides.vehicleCar' },
  { value: 'motorbike', label: 'driverRides.vehicleMotorbike' },
  { value: 'bicycle', label: 'driverRides.vehicleBicycle' },
];

const rideStatusLabel = (s) => {
  if (s === 'searching') return t('driver.online'); // "on the way"
  if (s === 'arrived') return t('driverRides.arrivedCta');
  if (s === 'in_progress') return t('driverRides.startCta');
  return s;
};

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

// ── Item B: shared countdown clock for offer expiry chips ─────────────────────
// A single 1-second interval keeps all chips in sync without N timers.
const offerNow = ref(Date.now());
let offerCountdownTimer = null;
// Remaining seconds for an offer — computed against the shared clock.
const offerSecondsLeft = (isoExpiry) => {
  if (!isoExpiry) return 0;
  return Math.max(0, Math.round((Date.parse(isoExpiry) - offerNow.value) / 1000));
};

// ── Item D: post-delivery "go online for next drop" sticky CTA ────────────────
const showGoOnlineCta = ref(false);
const handleGoOnlineCta = async () => {
  showGoOnlineCta.value = false;
  await toggleOnline();
};

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

// Ride history (driver's completed/cancelled rides) — lazy-loaded on first expand.
const showRideHistory = ref(false);
const rideHistory = ref([]);
const loadingRideHistory = ref(false);
const fetchRideHistory = async () => {
  loadingRideHistory.value = true;
  try {
    const { data } = await api.get('/driver/rides/history/');
    rideHistory.value = Array.isArray(data) ? data : [];
  } catch {
    /* keep last */
  } finally {
    loadingRideHistory.value = false;
  }
};
const toggleRideHistory = () => {
  showRideHistory.value = !showRideHistory.value;
  if (showRideHistory.value && !rideHistory.value.length) fetchRideHistory();
};

const STATUS_LABELS = {
  assigned: 'driver.statusAssigned',
  at_restaurant: 'driver.statusAtRestaurant',
  picked_up: 'driver.statusPickedUp',
  delivered: 'driver.statusDelivered',
  failed: 'driver.statusFailed',
};
// at_restaurant label branches on the active job's business_type via deliveryVocab.
const statusLabel = (s, businessType) => {
  if (s === 'at_restaurant') return t(pickupLabelKey(businessType, 'at'));
  return t(STATUS_LABELS[s] || 'driver.statusAssigned');
};

// Next forward transition for the active job's current status.
// The button label for "go to at_restaurant" also branches on business_type.
const nextAction = computed(() => {
  const job = activeJob.value;
  if (!job) return null;
  const bt = job.business_type;
  const NEXT = {
    assigned: { to: 'at_restaurant', label: pickupLabelKey(bt, 'collect') },
    at_restaurant: { to: 'picked_up', label: 'driver.actionPickedUp' },
    picked_up: { to: 'delivered', label: 'driver.actionDelivered' },
  };
  const n = NEXT[job.status];
  return n ? { to: n.to, label: t(n.label) } : null;
});

const mapsLink = (lat, lng, address) => {
  // Turn-by-turn navigation (dir/?destination=…) — opens the native Maps app on
  // mobile and routes from the driver's current location. Coordinates beat the
  // address string for accuracy when present.
  if (lat != null && lng != null) return `https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}`;
  return `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(address || '')}`;
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
      showGoOnlineCta.value = true; // Item D: prompt the driver to go back online
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
    if (data.driver_vehicle_type) driverVehicleType.value = data.driver_vehicle_type;
    driverCarApproved.value = Boolean(data.driver_car_approved);
    driverLicenceUrl.value = data.driver_licence_url || '';
    driverInsuranceUrl.value = data.driver_insurance_url || '';
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
const pollTick = () => {
  fetchJobs();
  if (driverVehicleType.value === 'car') fetchRides();
};
const ensurePoll = () => {
  if (!pollTimer) pollTimer = setInterval(pollTick, 15000);
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
      showGoOnlineCta.value = false; // dismiss the CTA once truly online
      startGeo();
      // Subscribe to web push so new jobs reach the driver even when backgrounded.
      driverPush.subscribe().catch(() => {});
      await fetchJobs();
      if (driverVehicleType.value === 'car') fetchRides();
    } else {
      stopGeo();
      rideOffers.value = [];
      activeRide.value = null;
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
    errorMsg.value = t('driver.errorGeneric');
    await fetchJobs();
  } finally {
    busy.value = false;
  }
};

// ── Ride-hailing functions ────────────────────────────────────────────────────
const fetchRides = async () => {
  if (!isDriver.value) return;
  loadingRides.value = true;
  try {
    const { data } = await api.get('/driver/rides/');
    rideOffers.value = data.open_rides || [];
    const prevRideId = activeRide.value?.id;
    activeRide.value = data.active_ride || null;
    // Reset package code state when the ride changes
    if (activeRide.value?.id !== prevRideId) {
      packageCodeInput.value = '';
      packageCodeError.value = '';
    }
    if (data.last_completed) {
      lastCompleted.value = data.last_completed;
      // Reset the rating UI if a new last_completed arrived with no rating yet
      if (data.last_completed.driver_rider_rating == null) {
        riderRateDone.value = false;
        riderRatingScore.value = 0;
      }
    } else {
      lastCompleted.value = null;
    }
  } catch {
    /* keep last */
  } finally {
    loadingRides.value = false;
  }
};

const setVehicleType = async (vt) => {
  if (driverVehicleType.value === vt) return;
  busy.value = true;
  try {
    await api.patch('/driver/status/', { driver_vehicle_type: vt });
    driverVehicleType.value = vt;
    // Refresh rides — car gets offers, others won't
    if (vt === 'car') fetchRides();
    else { rideOffers.value = []; activeRide.value = null; }
  } catch (err) {
    errorMsg.value = err?.response?.data?.detail || t('driver.errorGeneric');
  } finally {
    busy.value = false;
  }
};

const acceptRide = async (rideId) => {
  errorMsg.value = '';
  busy.value = true;
  try {
    const { data } = await api.post(`/driver/rides/${rideId}/accept/`, {});
    activeRide.value = data;
    rideOffers.value = [];
  } catch (err) {
    if (err?.response?.status === 409) {
      toast.show(t('driver.errorGeneric'), 'error');
    } else {
      errorMsg.value = err?.response?.data?.detail || t('driver.errorGeneric');
    }
    await fetchRides();
  } finally {
    busy.value = false;
  }
};

const advanceRide = async (rideId, status) => {
  errorMsg.value = '';
  busy.value = true;
  try {
    const { data } = await api.post(`/driver/rides/${rideId}/status/`, { status });
    if (data.status === 'completed') {
      activeRide.value = null;
      toast.show(t('driver.deliveredToast'), 'success');
      fetchEarnings();
      fetchRides();
    } else {
      activeRide.value = data;
    }
  } catch (err) {
    errorMsg.value = err?.response?.data?.detail || t('driver.errorGeneric');
  } finally {
    busy.value = false;
  }
};

// Package handover code submission — sends {status: 'completed', code} to the ride endpoint.
const submitPackageCode = async (rideId) => {
  const code = packageCodeInput.value.trim();
  if (!code) return;
  packageCodeError.value = '';
  busy.value = true;
  try {
    await api.post(`/driver/rides/${rideId}/status/`, { status: 'completed', code });
    packageCodeInput.value = '';
    activeRide.value = null;
    toast.show(t('driver.deliveredToast'), 'success');
    fetchEarnings();
    fetchRides();
  } catch (err) {
    const errCode = err?.response?.data?.code;
    if (errCode === 'bad_code') {
      packageCodeError.value = t('driverRides.badCode');
    } else if (errCode === 'code_locked') {
      packageCodeError.value = t('driverRides.codeLocked');
    } else {
      packageCodeError.value = err?.response?.data?.detail || t('driver.errorGeneric');
    }
  } finally {
    busy.value = false;
  }
};

const confirmReleaseRide = () => {
  releaseRideConfirmOpen.value = true;
};

const releaseRide = async () => {
  if (!activeRide.value) return;
  busy.value = true;
  try {
    await api.post(`/driver/rides/${activeRide.value.id}/status/`, { status: 'searching' });
    activeRide.value = null;
    releaseRideConfirmOpen.value = false;
    await fetchRides();
  } catch (err) {
    errorMsg.value = err?.response?.data?.detail || t('driver.errorGeneric');
  } finally {
    busy.value = false;
  }
};

// ── Car-document upload ───────────────────────────────────────────────────────
const uploadDoc = async (kind, event) => {
  const file = event.target.files?.[0];
  if (!file) return;
  uploadingDoc.value = true;
  try {
    const fd = new FormData();
    fd.append('kind', kind);
    fd.append('image', file);
    const { data } = await api.post('/driver/docs/', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    // Reflect returned urls immediately
    driverCarApproved.value = Boolean(data.driver_car_approved);
    driverLicenceUrl.value = data.driver_licence_url || '';
    driverInsuranceUrl.value = data.driver_insurance_url || '';
    toast.show(t('driverDocs.uploaded'), 'success');
  } catch {
    toast.show(t('driverDocs.uploadFailed'), 'error');
  } finally {
    uploadingDoc.value = false;
    // Reset the file input so the same file can be re-selected after Replace
    event.target.value = '';
  }
};

// ── Rate last passenger ───────────────────────────────────────────────────────
const submitRiderRating = async () => {
  if (!lastCompleted.value || !riderRatingScore.value || submittingRiderRating.value) return;
  submittingRiderRating.value = true;
  try {
    await api.post(`/driver/rides/${lastCompleted.value.id}/rate/`, { rating: riderRatingScore.value });
    riderRateDone.value = true;
    toast.show(t('driverRides.rateThanks'), 'success');
  } catch {
    toast.show(t('driver.ratingFailed'), 'error');
  } finally {
    submittingRiderRating.value = false;
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
      showGoOnlineCta.value = true; // Item D: prompt the driver to go back online
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
  // Item B: start the shared 1-second countdown clock for offer expiry chips.
  offerCountdownTimer = setInterval(() => {
    offerNow.value = Date.now();
    // Auto-remove offers whose countdown has elapsed so stale cards don't linger.
    if (pendingJobs.value.length) {
      pendingJobs.value = pendingJobs.value.filter(
        (j) => !j.offer_expires_at || Date.parse(j.offer_expires_at) > Date.now(),
      );
    }
  }, 1000);

  await customerStore.fetchCustomer();
  if (!customerStore.isAuthenticated) return;
  await fetchStatus();
  if (isDriver.value && approved.value) {
    await fetchJobs();
    fetchEarnings();
    fetchCashout();
    if (driverVehicleType.value === 'car') fetchRides();
    if (online.value) {
      startGeo();
      driverPush.autoRestore().catch(() => {}); // re-arm push if previously opted in
    }
    ensurePoll();
  }
});

onBeforeUnmount(() => {
  if (pollTimer) clearInterval(pollTimer);
  if (offerCountdownTimer) clearInterval(offerCountdownTimer); // Item B cleanup
  stopGeo();
  if (typeof window !== 'undefined') {
    window.removeEventListener('beforeinstallprompt', onBeforeInstallPrompt);
    window.removeEventListener('appinstalled', onAppInstalled);
  }
});
</script>
