<template>
  <div class="ui-safe-bottom min-h-screen bg-slate-950">

    <!-- ══════════════════════════ LOADING ══════════════════════════ -->
    <div
      v-if="!customerStore.loaded"
      class="flex min-h-[65vh] flex-col items-center justify-center gap-5 px-4"
      aria-busy="true"
      :aria-label="t('common.loading')"
    >
      <div class="h-16 w-16 animate-pulse rounded-3xl border border-slate-700/60 bg-slate-900/60" />
      <div class="mx-auto h-4 w-32 animate-pulse rounded-lg bg-slate-800" />
    </div>

    <!-- ══════════════════════════ NOT SIGNED IN ══════════════════════════ -->
    <template v-else-if="!customerStore.isAuthenticated">
      <div class="relative overflow-hidden bg-slate-950 ui-reveal">
        <div class="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_50%_-10%,rgba(99,102,241,0.13),transparent_65%)]" />
        <div class="relative px-4 pb-10 pt-12 text-center space-y-5">
          <div class="mx-auto flex h-20 w-20 items-center justify-center rounded-[22px] border border-slate-700/60 bg-gradient-to-br from-slate-800/80 to-slate-900/80 shadow-xl">
            <AppIcon name="truck" class="h-9 w-9 text-indigo-400" aria-hidden="true" />
          </div>
          <div class="space-y-2">
            <p class="ui-kicker">{{ t('ridePage.kicker') }}</p>
            <h1 class="ui-page-title">{{ t('ridePage.title') }}</h1>
            <p class="ui-subtle mx-auto max-w-xs leading-relaxed">{{ t('ridePage.signInFirst') }}</p>
          </div>
          <button
            class="ui-btn-primary ui-touch-target mx-auto gap-2 px-6"
            @click="showAuthModal = true"
          >
            <AppIcon name="user" class="h-3.5 w-3.5" aria-hidden="true" />
            {{ t('customerAccount.signIn') }}
          </button>
        </div>
      </div>
      <CustomerAuthModal
        v-if="showAuthModal"
        @close="showAuthModal = false"
        @authenticated="showAuthModal = false"
      />
    </template>

    <!-- ══════════════════════════ SIGNED IN ══════════════════════════ -->
    <template v-else>

      <!-- ── Page header ── -->
      <header class="relative overflow-hidden bg-slate-950 pb-4 pt-6 ui-reveal">
        <div class="pointer-events-none absolute inset-0 bg-gradient-to-b from-indigo-500/7 via-transparent to-transparent" />
        <div class="relative px-4">
          <p class="ui-kicker">{{ t('ridePage.kicker') }}</p>
          <h1 class="ui-page-title flex items-center gap-2">
            <AppIcon name="truck" class="h-5 w-5 text-indigo-400" aria-hidden="true" />
            {{ t('ridePage.title') }}
          </h1>
        </div>
      </header>

      <!-- ══════════════════════════ ACTIVE RIDE TRACKING ══════════════════════════ -->
      <div
        v-if="activeRide && activeRide.status !== 'completed' && activeRide.status !== 'cancelled'"
        class="px-3 pb-6 space-y-3"
        aria-live="polite"
        aria-atomic="false"
      >
        <!-- Status banner -->
        <div
          class="ui-panel ui-reveal relative overflow-hidden p-4 space-y-3"
          :class="{
            'border-amber-500/30 bg-amber-500/6': activeRide.status === 'searching',
            'border-sky-500/30 bg-sky-500/6': activeRide.status === 'accepted',
            'border-violet-500/30 bg-violet-500/6': activeRide.status === 'arrived',
            'border-emerald-500/30 bg-emerald-500/6': activeRide.status === 'in_progress',
          }"
        >
          <!-- Pulse ring for active states -->
          <div
            class="pointer-events-none absolute inset-0 rounded-2xl ring-1 ring-inset motion-safe:animate-pulse"
            :class="{
              'ring-amber-500/15': activeRide.status === 'searching',
              'ring-sky-500/15': activeRide.status === 'accepted',
              'ring-violet-500/15': activeRide.status === 'arrived',
              'ring-emerald-500/15': activeRide.status === 'in_progress',
            }"
            aria-hidden="true"
          />

          <!-- Status label -->
          <div class="relative flex items-center gap-3">
            <span
              class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border"
              :class="{
                'border-amber-500/40 bg-amber-500/12 text-amber-300': activeRide.status === 'searching',
                'border-sky-500/40 bg-sky-500/12 text-sky-300': activeRide.status === 'accepted',
                'border-violet-500/40 bg-violet-500/12 text-violet-300': activeRide.status === 'arrived',
                'border-emerald-500/40 bg-emerald-500/12 text-emerald-300': activeRide.status === 'in_progress',
              }"
              aria-hidden="true"
            >
              <AppIcon name="truck" class="h-4 w-4" aria-hidden="true" />
            </span>
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2">
                <p
                  class="text-sm font-semibold"
                  :class="{
                    'text-amber-300': activeRide.status === 'searching',
                    'text-sky-300': activeRide.status === 'accepted',
                    'text-violet-300': activeRide.status === 'arrived',
                    'text-emerald-300': activeRide.status === 'in_progress',
                  }"
                >
                  {{ rideStatusLabel }}
                </p>
                <ConnectionDot :state="connectionState" />
              </div>
              <p v-if="activeRide.driver" class="mt-0.5 text-xs text-slate-400">
                {{ activeRide.driver.name }}
                <span v-if="activeRide.driver.driver_vehicle" class="ms-1 text-slate-500">· {{ activeRide.driver.driver_vehicle }}</span>
              </p>
            </div>
            <!-- Phone link once driver assigned -->
            <a
              v-if="activeRide.driver?.phone"
              :href="`tel:${activeRide.driver.phone}`"
              class="ui-btn-outline ui-touch-target ui-press shrink-0 gap-1.5 px-3 py-2 text-xs"
              :aria-label="t('deliveryTracker.call')"
            >
              <AppIcon name="phone" class="h-4 w-4" aria-hidden="true" />
            </a>
          </div>

          <!-- Addresses -->
          <dl class="ui-admin-subcard space-y-1 px-3 py-2 relative">
            <div class="flex items-baseline gap-1.5 text-xs">
              <dt class="shrink-0 text-slate-500">{{ t('ridePage.pickupLabel') }}</dt>
              <dd class="min-w-0 truncate text-slate-300">{{ activeRide.pickup_address }}</dd>
            </div>
            <div class="flex items-baseline gap-1.5 text-xs">
              <dt class="shrink-0 text-slate-500">{{ t('ridePage.dropoffLabel') }}</dt>
              <dd class="min-w-0 truncate text-slate-300">{{ activeRide.dropoff_address }}</dd>
            </div>
          </dl>
        </div>

        <!-- Live map (driver position) -->
        <div
          v-show="hasDriverPos"
          ref="trackingMapEl"
          class="h-52 w-full overflow-hidden rounded-2xl border border-slate-800"
          role="img"
          :aria-label="t('ridePage.driverAssigned')"
        />

        <!-- Cancel button (searching / accepted) — two-tap guard -->
        <button
          v-if="activeRide.status === 'searching' || activeRide.status === 'accepted'"
          type="button"
          class="w-full rounded-2xl border py-3 text-sm font-semibold transition ui-press disabled:opacity-50"
          :class="cancelConfirming
            ? 'border-red-500/60 bg-red-500/18 text-red-200'
            : 'border-red-500/30 bg-red-500/8 text-red-300 hover:bg-red-500/15'"
          :disabled="cancelling"
          @click="cancelRide"
        >
          {{ cancelling ? t('common.loading') : (cancelConfirming ? t('ridePage.cancelConfirmCta') : t('ridePage.cancelCta')) }}
        </button>
      </div>

      <!-- ══════════════════════════ COMPLETED — RATE ══════════════════════════ -->
      <div
        v-else-if="activeRide && activeRide.status === 'completed'"
        class="px-3 pb-6 space-y-3"
      >
        <div class="ui-panel ui-reveal p-4 space-y-3 border-emerald-500/30 bg-emerald-500/6">
          <p class="ui-kicker">{{ t('ridePage.completed') }}</p>
          <dl class="space-y-1">
            <div class="flex items-baseline gap-1.5 text-xs">
              <dt class="shrink-0 text-slate-500">{{ t('ridePage.pickupLabel') }}</dt>
              <dd class="min-w-0 truncate text-slate-300">{{ activeRide.pickup_address }}</dd>
            </div>
            <div class="flex items-baseline gap-1.5 text-xs">
              <dt class="shrink-0 text-slate-500">{{ t('ridePage.dropoffLabel') }}</dt>
              <dd class="min-w-0 truncate text-slate-300">{{ activeRide.dropoff_address }}</dd>
            </div>
          </dl>
        </div>

        <!-- Rating UI -->
        <div v-if="!ratingDone" class="ui-panel ui-reveal p-4 space-y-3">
          <p class="ui-kicker">{{ t('ridePage.rateTitle') }}</p>
          <div class="flex justify-center gap-1" role="radiogroup" :aria-label="t('ridePage.rateTitle')">
            <button
              v-for="n in 5"
              :key="n"
              type="button"
              role="radio"
              class="ui-touch-target ui-press flex items-center justify-center rounded-xl transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
              :class="ratingScore >= n ? 'text-amber-400' : 'text-slate-600 hover:text-slate-400'"
              :aria-label="`${n} star${n > 1 ? 's' : ''}`"
              :aria-checked="ratingScore === n"
              @click="ratingScore = n"
            >
              <AppIcon name="star" class="h-8 w-8" aria-hidden="true" />
            </button>
          </div>
          <button
            type="button"
            class="ui-btn-primary ui-press w-full py-3 text-sm font-semibold disabled:opacity-50"
            :disabled="!ratingScore || submittingRating"
            @click="submitRating"
          >
            {{ submittingRating ? t('common.saving') : t('ridePage.rateCta') }}
          </button>
        </div>
        <p
          v-else
          role="status"
          class="flex items-center justify-center gap-2 rounded-2xl border border-emerald-500/25 bg-emerald-500/8 py-4 text-sm font-semibold text-emerald-300"
        >
          <AppIcon name="check" class="h-4 w-4 shrink-0" aria-hidden="true" />
          {{ t('ridePage.rated') }}
        </p>

        <!-- Book another -->
        <button
          type="button"
          class="ui-btn-primary ui-press w-full py-3 text-sm font-semibold"
          @click="resetForm"
        >
          {{ t('ridePage.title') }}
        </button>
      </div>

      <!-- ══════════════════════════ CANCELLED ══════════════════════════ -->
      <div
        v-else-if="showCancelled"
        class="px-3 pb-6 space-y-3"
      >
        <div class="ui-panel ui-reveal p-4 border-red-500/25 bg-red-500/6 space-y-3">
          <p class="text-sm font-semibold text-red-300">{{ t('ridePage.cancelled') }}</p>
        </div>
        <button
          type="button"
          class="ui-btn-primary ui-press w-full py-3 text-sm font-semibold"
          @click="resetForm"
        >
          {{ t('ridePage.title') }}
        </button>
      </div>

      <!-- ══════════════════════════ BOOKING FORM ══════════════════════════ -->
      <div
        v-else
        ref="formTopEl"
        class="px-3 pb-28 space-y-3"
      >
        <!-- No-driver-found notice (system cancel detected by polling) -->
        <div
          v-if="noDriverFound"
          role="alert"
          class="flex items-start gap-3 rounded-2xl border border-amber-500/30 bg-amber-500/8 px-4 py-3"
        >
          <AppIcon name="info" class="mt-0.5 h-4 w-4 shrink-0 text-amber-400" aria-hidden="true" />
          <p class="flex-1 text-sm text-amber-200">{{ t('ridePage.noDriverFound') }}</p>
          <button
            type="button"
            class="shrink-0 text-amber-400 hover:text-amber-300"
            :aria-label="t('common.close')"
            @click="noDriverFound = false"
          >
            <AppIcon name="close" class="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        <!-- Error banners -->
        <div
          v-if="errorMsg"
          role="alert"
          class="flex items-start gap-3 rounded-2xl border border-red-500/30 bg-red-500/8 px-4 py-3"
        >
          <AppIcon name="info" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" aria-hidden="true" />
          <p class="flex-1 text-sm text-red-300">{{ errorMsg }}</p>
          <button
            type="button"
            class="shrink-0 text-red-400 hover:text-red-300"
            :aria-label="t('common.close')"
            @click="errorMsg = ''"
          >
            <AppIcon name="close" class="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        <!-- ── Pickup ── -->
        <section class="ui-panel ui-reveal p-4 space-y-3">
          <p class="ui-kicker flex items-center gap-1.5">
            <AppIcon name="location" class="h-3.5 w-3.5 text-[var(--color-secondary)]" aria-hidden="true" />
            {{ t('ridePage.pickupLabel') }}
          </p>
          <!-- Saved-address chips (reuse food-checkout saved addresses) -->
          <div v-if="savedAddresses.length" class="space-y-1.5">
            <p class="text-[10px] font-semibold uppercase tracking-widest text-slate-500">{{ t('sendPackage.savedAddresses') }}</p>
            <div class="flex flex-wrap gap-1.5">
              <button
                v-for="addr in savedAddresses"
                :key="`pickup-${addr.id}`"
                type="button"
                class="inline-flex max-w-full items-center gap-1.5 rounded-full border border-slate-700/60 bg-slate-900/40 px-3 py-1.5 text-xs text-slate-300 transition hover:border-[var(--color-secondary)]/40 hover:bg-[var(--color-secondary)]/5 ui-press"
                :aria-label="t('sendPackage.fillForPickup')"
                @click="applySavedAddress(addr, 'pickup')"
              >
                <AppIcon name="location" class="h-3 w-3 shrink-0 text-[var(--color-secondary)]" aria-hidden="true" />
                <span v-if="addr.label" class="font-medium text-slate-200">{{ addr.label }}</span>
                <span class="truncate text-slate-400" :title="addr.address">{{ addr.label ? '' : addr.address }}</span>
              </button>
            </div>
          </div>
          <button
            type="button"
            class="w-full inline-flex items-center gap-2 rounded-xl border border-slate-700/60 bg-slate-900/40 px-3 py-2.5 text-sm text-slate-300 transition hover:border-[var(--color-secondary)]/40 hover:bg-[var(--color-secondary)]/5 ui-press"
            :class="locating ? 'opacity-60' : ''"
            :disabled="locating"
            @click="useMyLocation"
          >
            <AppIcon name="location" class="h-4 w-4 shrink-0 text-[var(--color-secondary)]" aria-hidden="true" />
            <span class="flex-1 text-left text-sm">{{ locating ? t('common.loading') : t('ridePage.useMyLocation') }}</span>
          </button>
          <input
            v-model="pickupAddress"
            type="text"
            class="ui-input w-full"
            :placeholder="t('ridePage.addressPlaceholder')"
            :aria-label="t('ridePage.pickupLabel')"
          />
          <p v-if="pickupLatLng" class="text-[11px] text-emerald-400 flex items-center gap-1">
            <AppIcon name="check" class="h-3 w-3" aria-hidden="true" />
            {{ pickupLatLng.lat.toFixed(5) }}, {{ pickupLatLng.lng.toFixed(5) }}
          </p>
        </section>

        <!-- ── Drop-off + map ── -->
        <section class="ui-panel ui-reveal p-4 space-y-3">
          <p class="ui-kicker flex items-center gap-1.5">
            <AppIcon name="location" class="h-3.5 w-3.5 text-indigo-400" aria-hidden="true" />
            {{ t('ridePage.dropoffLabel') }}
          </p>
          <!-- Saved-address chips for drop-off -->
          <div v-if="savedAddresses.length" class="space-y-1.5">
            <p class="text-[10px] font-semibold uppercase tracking-widest text-slate-500">{{ t('sendPackage.savedAddresses') }}</p>
            <div class="flex flex-wrap gap-1.5">
              <button
                v-for="addr in savedAddresses"
                :key="`dropoff-${addr.id}`"
                type="button"
                class="inline-flex max-w-full items-center gap-1.5 rounded-full border border-slate-700/60 bg-slate-900/40 px-3 py-1.5 text-xs text-slate-300 transition hover:border-indigo-400/40 hover:bg-indigo-400/5 ui-press"
                :aria-label="t('sendPackage.fillForDropoff')"
                @click="applySavedAddress(addr, 'dropoff')"
              >
                <AppIcon name="location" class="h-3 w-3 shrink-0 text-indigo-400" aria-hidden="true" />
                <span v-if="addr.label" class="font-medium text-slate-200">{{ addr.label }}</span>
                <span class="truncate text-slate-400" :title="addr.address">{{ addr.label ? '' : addr.address }}</span>
              </button>
            </div>
          </div>
          <input
            v-model="dropoffAddress"
            type="text"
            class="ui-input w-full"
            :placeholder="t('ridePage.addressPlaceholder')"
            :aria-label="t('ridePage.dropoffLabel')"
          />
          <!-- Leaflet map — tap to place drop-off pin -->
          <div
            ref="pickMapEl"
            class="h-48 w-full overflow-hidden rounded-xl border border-slate-800"
            role="img"
            :aria-label="t('ridePage.dropoffLabel')"
          />
          <p v-if="dropoffLatLng" class="text-[11px] text-indigo-300 flex items-center gap-1">
            <AppIcon name="check" class="h-3 w-3" aria-hidden="true" />
            {{ dropoffLatLng.lat.toFixed(5) }}, {{ dropoffLatLng.lng.toFixed(5) }}
          </p>
          <p v-else class="text-[11px] text-slate-500">{{ t("ridePage.dropoffMapHint") }}</p>
        </section>

        <!-- ── Fare estimate (auto-computed) + payment + request ── -->
        <div class="ui-panel ui-reveal p-4 space-y-3">
          <!-- Inline fare row — shown once estimate resolves; skeleton while loading -->
          <div class="flex items-center justify-between gap-4 min-h-[48px]">
            <template v-if="estimating">
              <!-- Loading skeleton -->
              <div class="flex-1 space-y-1">
                <div class="h-2.5 w-16 animate-pulse rounded bg-slate-800" />
                <div class="h-5 w-10 animate-pulse rounded bg-slate-800" />
              </div>
              <div class="space-y-1">
                <div class="h-2.5 w-14 animate-pulse rounded bg-slate-800" />
                <div class="h-5 w-12 animate-pulse rounded bg-slate-800" />
              </div>
              <div class="space-y-1 text-end">
                <div class="h-2.5 w-16 animate-pulse rounded bg-slate-800" />
                <div class="h-6 w-16 animate-pulse rounded bg-slate-800" />
              </div>
            </template>
            <template v-else-if="estimate">
              <div>
                <p class="text-[10px] uppercase tracking-wider text-slate-500">{{ t('ridePage.distanceLabel') }}</p>
                <p class="mt-0.5 text-lg font-bold tabular-nums text-slate-200">{{ estimate.distance_km }} km</p>
              </div>
              <div v-if="estimate.duration_min" class="text-center">
                <p class="text-[10px] uppercase tracking-wider text-slate-500">{{ t('ridePage.durationLabel') }}</p>
                <p class="mt-0.5 text-lg font-bold tabular-nums text-slate-200">{{ t('ridePage.durationValue', { min: estimate.duration_min }) }}</p>
              </div>
              <div class="text-end">
                <p class="text-[10px] uppercase tracking-wider text-slate-500">{{ t('ridePage.fareLabel') }}</p>
                <p class="mt-0.5 text-lg font-bold tabular-nums text-[var(--color-secondary)]">{{ formatPrice(estimate.fare) }}</p>
              </div>
            </template>
            <template v-else>
              <p class="text-xs text-slate-500">{{ canEstimate ? t('ridePage.estimatingHint') : t('ridePage.pickBothHint') }}</p>
            </template>
          </div>

          <!-- Payment toggle — only visible once estimate resolved -->
          <template v-if="estimate">
            <div class="flex rounded-xl border border-slate-700/60 overflow-hidden text-sm font-semibold" role="group" :aria-label="`${t('ridePage.payWallet')} / ${t('ridePage.payCash')}`">
              <button
                type="button"
                class="flex-1 py-2.5 transition-colors"
                :class="paymentMethod === 'wallet' ? 'bg-[var(--color-secondary)] text-slate-950' : 'bg-slate-900/40 text-slate-400 hover:text-slate-200'"
                :disabled="walletInsufficient"
                @click="paymentMethod = 'wallet'"
              >
                {{ t('ridePage.walletShort') }}
              </button>
              <button
                type="button"
                class="flex-1 py-2.5 transition-colors"
                :class="paymentMethod === 'cash' ? 'bg-slate-200 text-slate-950' : 'bg-slate-900/40 text-slate-400 hover:text-slate-200'"
                @click="paymentMethod = 'cash'"
              >
                {{ t('ridePage.cashShort') }}
              </button>
            </div>

            <p
              v-if="walletInsufficient && paymentMethod === 'wallet'"
              role="alert"
              class="flex items-center gap-1.5 text-xs text-amber-300"
            >
              <AppIcon name="info" class="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              {{ t('ridePage.insufficientWallet') }}
            </p>

            <!-- ── Schedule for later ── -->
            <div class="space-y-2 rounded-xl border border-slate-700/50 bg-slate-950/40 p-3">
              <div class="flex items-center justify-between gap-3">
                <p class="text-xs font-semibold text-slate-300">{{ t('tripSchedule.toggle') }}</p>
                <button
                  type="button"
                  class="relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/50"
                  :class="scheduleEnabled ? 'bg-[var(--color-secondary)]' : 'bg-slate-700'"
                  :aria-pressed="scheduleEnabled"
                  :aria-label="t('tripSchedule.toggle')"
                  @click="scheduleEnabled = !scheduleEnabled"
                >
                  <span
                    class="pointer-events-none inline-block h-4 w-4 rounded-full bg-white shadow ring-0 transition-transform duration-200"
                    :class="scheduleEnabled ? 'translate-x-4' : 'translate-x-0'"
                  />
                </button>
              </div>
              <template v-if="scheduleEnabled">
                <p class="text-[11px] text-slate-500">{{ t('tripSchedule.hint') }}</p>
                <div class="grid grid-cols-2 gap-2">
                  <div class="space-y-0.5">
                    <label class="block text-[10px] text-slate-500">{{ t('tripSchedule.dateLabel') }}</label>
                    <input
                      v-model="scheduleDate"
                      type="date"
                      :min="minScheduleDate"
                      class="w-full rounded-xl border border-slate-700/60 bg-slate-900/40 px-3 py-2 text-sm text-slate-100 focus:border-[var(--color-secondary)]/55 focus:outline-none"
                      :aria-label="t('tripSchedule.dateLabel')"
                    />
                  </div>
                  <div class="space-y-0.5">
                    <label class="block text-[10px] text-slate-500">{{ t('tripSchedule.timeLabel') }}</label>
                    <input
                      v-model="scheduleTime"
                      type="time"
                      class="w-full rounded-xl border border-slate-700/60 bg-slate-900/40 px-3 py-2 text-sm text-slate-100 focus:border-[var(--color-secondary)]/55 focus:outline-none"
                      :aria-label="t('tripSchedule.timeLabel')"
                    />
                  </div>
                </div>
              </template>
            </div>
          </template>

          <!-- Single request CTA — disabled until estimate resolves -->
          <button
            type="button"
            class="ui-btn-primary ui-press w-full py-3 text-sm font-semibold disabled:opacity-50"
            :disabled="!canEstimate || estimating || !estimate || requesting || (paymentMethod === 'wallet' && walletInsufficient)"
            @click="requestRide"
          >
            <span v-if="requesting">{{ t('common.loading') }}</span>
            <span v-else-if="estimating">{{ t('ridePage.estimatingHint') }}</span>
            <span v-else-if="!estimate">{{ canEstimate ? t('ridePage.estimatingHint') : t('ridePage.requestCta') }}</span>
            <span v-else>{{ scheduleEnabled ? t('tripSchedule.scheduledBadge') : t('ridePage.requestCta') }}</span>
          </button>
        </div>

        <!-- ══════════════════════════ UPCOMING SCHEDULED RIDES ══════════════════════════ -->
        <section v-if="scheduledTrips.length > 0" class="space-y-2 pt-1">
          <p class="ui-kicker px-1">{{ t('tripSchedule.upcomingTitle') }}</p>
          <ul class="space-y-1.5">
            <li
              v-for="trip in scheduledTrips"
              :key="trip.id"
              class="ui-panel flex items-center gap-3 px-3 py-2.5"
            >
              <AppIcon name="truck" class="h-4 w-4 shrink-0 text-indigo-400" aria-hidden="true" />
              <div class="min-w-0 flex-1">
                <p class="truncate text-sm text-slate-200">{{ trip.dropoff_address || trip.pickup_address }}</p>
                <p class="mt-0.5 text-[11px] text-slate-500">
                  {{ t('tripSchedule.forTime', { time: fmtScheduledFor(trip.scheduled_for) }) }}
                </p>
              </div>
              <span class="shrink-0 rounded-full border border-indigo-500/30 bg-indigo-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-indigo-300">
                {{ t('tripSchedule.scheduledBadge') }}
              </span>
              <button
                type="button"
                class="shrink-0 rounded-xl border border-red-500/30 bg-red-500/8 px-2.5 py-1.5 text-xs font-semibold text-red-300 transition hover:bg-red-500/15 disabled:opacity-50"
                :disabled="cancellingSchId === trip.id"
                @click="cancelScheduled(trip.id)"
              >
                {{ cancellingSchId === trip.id ? t('common.loading') : t('tripSchedule.cancelCta') }}
              </button>
            </li>
          </ul>
        </section>

        <!-- ══════════════════════════ PAST RIDES ══════════════════════════ -->
        <RidePageHistory
          :history="rideHistory"
          :loading="historyLoading"
          :is-authenticated="customerStore.isAuthenticated"
          @rebook="rebookRide"
        />
      </div>

    </template>

  <!-- Push-permission priming (self-gated; triggered post-request) -->
  <PushPrimingSheet ref="pushPrimingSheet" />
</div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useI18n } from '../composables/useI18n';
import { useToastStore } from '../stores/toast';
import { useCustomerStore } from '../stores/customer';
import api from '../lib/api';
import { addTileLayer } from '../lib/mapTiles';
import AppIcon from '../components/AppIcon.vue';
import ConnectionDot from '../components/ConnectionDot.vue';
import CustomerAuthModal from '../components/CustomerAuthModal.vue';
import PushPrimingSheet from '../components/PushPrimingSheet.vue';
import RidePageHistory from '../components/RidePageHistory.vue';

const { t, formatPrice, currentLocale } = useI18n();
const toast = useToastStore();
const customerStore = useCustomerStore();

// ── Push priming sheet ────────────────────────────────────────────────────────
const pushPrimingSheet = ref(null);

// ── Auth modal ────────────────────────────────────────────────────────────────
const showAuthModal = ref(false);

// ── Form state ────────────────────────────────────────────────────────────────
const pickupAddress  = ref('');
const dropoffAddress = ref('');
const pickupLatLng   = ref(null);  // { lat, lng }
const dropoffLatLng  = ref(null);
const locating       = ref(false);
const estimating     = ref(false);
const requesting     = ref(false);
const cancelling     = ref(false);
const estimate       = ref(null);  // { distance_km, fare }
const paymentMethod  = ref('wallet');
const errorMsg       = ref('');

// ── Saved addresses (reuse food-checkout saved-address endpoint) ───────────────
const savedAddresses = ref([]);

const fetchSavedAddresses = async () => {
  if (!customerStore.isAuthenticated) return;
  try {
    const res = await api.get('/customer/addresses/');
    savedAddresses.value = Array.isArray(res.data) ? res.data : [];
  } catch {
    // best-effort; the chips simply won't render
  }
};

// Fill pickup OR drop-off from a saved address. `target` is 'pickup' | 'dropoff'.
const applySavedAddress = (addr, target) => {
  // Number(null) === 0 — guard so a coord-less saved address doesn't drop a (0,0) pin.
  const lat = addr?.lat == null || addr.lat === '' ? NaN : Number(addr.lat);
  const lng = addr?.lng == null || addr.lng === '' ? NaN : Number(addr.lng);
  const hasPos = Number.isFinite(lat) && Number.isFinite(lng);
  if (target === 'pickup') {
    pickupAddress.value = addr.address || '';
    if (hasPos) {
      pickupLatLng.value = { lat, lng };
      if (_pickMap) ensurePickupMarker(lat, lng);
    }
  } else {
    dropoffAddress.value = addr.address || '';
    if (hasPos) {
      dropoffLatLng.value = { lat, lng };
      ensureDropoffMarker(lat, lng);
    }
  }
};

// ── Schedule state ────────────────────────────────────────────────────────────
const scheduleEnabled  = ref(false);
const scheduleDate     = ref('');   // "YYYY-MM-DD"
const scheduleTime     = ref('');   // "HH:mm"
const cancellingSchId  = ref(null); // id of the scheduled trip being cancelled
const scheduledTrips   = ref([]);   // kind==='ride' items from active endpoint

// ── Rating state ──────────────────────────────────────────────────────────────
const ratingScore     = ref(0);
const submittingRating = ref(false);
const ratingDone      = ref(false);

// ── Cancel guard ─────────────────────────────────────────────────────────────
const cancelConfirming = ref(false);
let _cancelGuardTimer = null;
const armCancelGuard = () => {
  cancelConfirming.value = true;
  clearTimeout(_cancelGuardTimer);
  _cancelGuardTimer = setTimeout(() => { cancelConfirming.value = false; }, 3000);
};
const clearCancelGuard = () => {
  cancelConfirming.value = false;
  clearTimeout(_cancelGuardTimer);
};

// ── Cancelled state ───────────────────────────────────────────────────────────
const showCancelled   = ref(false);
const noDriverFound   = ref(false);  // system-cancelled (no driver accepted)

// ── Form top anchor (used by Rebook) ──────────────────────────────────────────
const formTopEl = ref(null);

// ── Ride history ──────────────────────────────────────────────────────────────
const rideHistory    = ref([]);
const historyLoading = ref(false);

// ── Active ride polling ───────────────────────────────────────────────────────
const activeRide = ref(null);
let pollTimer = null;
// Poll health → ConnectionDot. 'live' while the active-ride poll is succeeding;
// 'connecting' after a failed poll or when the browser reports offline.
const pollHealthy = ref(true);
const connectionState = computed(() =>
  pollHealthy.value &&
  (typeof navigator === 'undefined' || navigator.onLine !== false)
    ? 'live'
    : 'connecting',
);

const walletBalance = computed(() => {
  const raw = customerStore.customer?.wallet_balance;
  const n = Number(raw);
  return Number.isFinite(n) ? n : 0;
});

const minScheduleDate = computed(() => {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
});

const fmtScheduledFor = (iso) => {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleString(currentLocale.value || undefined, {
      month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
    });
  } catch { return iso; }
};

const walletInsufficient = computed(
  () => estimate.value != null && walletBalance.value < Number(estimate.value.fare),
);

const canEstimate = computed(
  () =>
    (pickupLatLng.value || pickupAddress.value.trim()) &&
    (dropoffLatLng.value || dropoffAddress.value.trim()),
);

const rideStatusLabel = computed(() => {
  switch (activeRide.value?.status) {
    case 'searching':   return t('ridePage.searching');
    case 'accepted':    return t('ridePage.driverAssigned');
    case 'arrived':     return t('ridePage.driverArrived');
    case 'in_progress': return t('ridePage.inProgress');
    case 'completed':   return t('ridePage.completed');
    case 'cancelled':   return t('ridePage.cancelled');
    default:            return '';
  }
});

const hasDriverPos = computed(
  () => activeRide.value?.driver?.driver_lat != null && activeRide.value?.driver?.driver_lng != null,
);

// ── Geolocation ───────────────────────────────────────────────────────────────
const useMyLocation = () => {
  if (!navigator.geolocation) {
    errorMsg.value = t('driver.geoUnavailable');
    return;
  }
  locating.value = true;
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      pickupLatLng.value = { lat: pos.coords.latitude, lng: pos.coords.longitude };
      locating.value = false;
      // Centre pick-map on user position
      if (_pickMap) {
        _pickMap.setView([pos.coords.latitude, pos.coords.longitude], 14);
        ensurePickupMarker(pos.coords.latitude, pos.coords.longitude);
      }
    },
    () => {
      errorMsg.value = t('driver.locationDenied');
      locating.value = false;
    },
    { timeout: 8000 },
  );
};

// ── Estimate ──────────────────────────────────────────────────────────────────
const getEstimate = async () => {
  estimating.value = true;
  errorMsg.value = '';
  try {
    const payload = {
      pickup_lat:  pickupLatLng.value?.lat   ?? 0,
      pickup_lng:  pickupLatLng.value?.lng   ?? 0,
      dropoff_lat: dropoffLatLng.value?.lat  ?? 0,
      dropoff_lng: dropoffLatLng.value?.lng  ?? 0,
    };
    const res = await api.post('/rides/estimate/', payload);
    estimate.value = res.data;
    // Auto-switch to cash if wallet insufficient
    if (walletInsufficient.value) paymentMethod.value = 'cash';
  } catch {
    errorMsg.value = t('ridePage.errorEstimate');
  } finally {
    estimating.value = false;
  }
};

// ── Request ride ──────────────────────────────────────────────────────────────
const requestRide = async () => {
  requesting.value = true;
  errorMsg.value = '';
  try {
    const payload = {
      pickup_lat:       pickupLatLng.value?.lat   ?? 0,
      pickup_lng:       pickupLatLng.value?.lng   ?? 0,
      dropoff_lat:      dropoffLatLng.value?.lat  ?? 0,
      dropoff_lng:      dropoffLatLng.value?.lng  ?? 0,
      pickup_address:   pickupAddress.value.trim() || `${pickupLatLng.value?.lat}, ${pickupLatLng.value?.lng}`,
      dropoff_address:  dropoffAddress.value.trim() || `${dropoffLatLng.value?.lat}, ${dropoffLatLng.value?.lng}`,
      payment_method:   paymentMethod.value,
    };
    if (scheduleEnabled.value) {
      // Toggle on but date/time blank would silently book an IMMEDIATE trip —
      // block instead so the button never lies about what it does.
      if (!scheduleDate.value || !scheduleTime.value) {
        errorMsg.value = t('tripSchedule.tooSoon');
        requesting.value = false;
        return;
      }
      const dt = new Date(`${scheduleDate.value}T${scheduleTime.value}`);
      // Client-side guard: at least 20 min from now
      if (dt.getTime() - Date.now() < 20 * 60 * 1000) {
        errorMsg.value = t('tripSchedule.tooSoon');
        requesting.value = false;
        return;
      }
      payload.scheduled_for = dt.toISOString();
    }
    const res = await api.post('/rides/', payload);
    if (scheduleEnabled.value && payload.scheduled_for) {
      // Scheduled trip created — show success, reset form, refetch upcoming
      scheduleEnabled.value = false;
      scheduleDate.value = '';
      scheduleTime.value = '';
      estimate.value = null;
      await fetchActiveRide();
    } else {
      activeRide.value = res.data;
      startPolling();
      // High-intent moment — prime for push notifications
      nextTick(() => pushPrimingSheet.value?.maybeShow?.());
    }
  } catch (err) {
    const httpStatus = err?.response?.status;
    const code       = err?.response?.data?.code;
    if (code === 'vertical_disabled' || httpStatus === 503) {
      // Deep-linked to a paused vertical (the hub gates the tile, but the URL is reachable).
      errorMsg.value = t('services.comingSoon');
    } else if (code === 'too_soon') {
      errorMsg.value = t('tripSchedule.tooSoon');
    } else if (code === 'too_far') {
      errorMsg.value = t('tripSchedule.tooFar');
    } else if (code === 'too_many_scheduled') {
      errorMsg.value = t('tripSchedule.tooMany');
    } else if (httpStatus === 409) {
      errorMsg.value = t('ridePage.errorActive');
      // Try to load active ride
      fetchActiveRide();
    } else if (code === 'insufficient_wallet') {
      errorMsg.value = t('ridePage.insufficientWallet');
      paymentMethod.value = 'cash';
    } else {
      errorMsg.value = t('ridePage.errorRequest');
    }
  } finally {
    requesting.value = false;
  }
};

// ── Cancel a scheduled trip ───────────────────────────────────────────────────
const cancelScheduled = async (tripId) => {
  cancellingSchId.value = tripId;
  try {
    await api.post(`/rides/${tripId}/cancel/`);
    await fetchActiveRide();
    toast.show(t('tripSchedule.cancelled'), 'success');
  } catch {
    errorMsg.value = t('ridePage.errorRequest');
  } finally {
    cancellingSchId.value = null;
  }
};

// ── Cancel ────────────────────────────────────────────────────────────────────
const cancelRide = async () => {
  if (!activeRide.value?.id) return;
  if (!cancelConfirming.value) {
    armCancelGuard();
    return;
  }
  clearCancelGuard();
  cancelling.value = true;
  try {
    await api.post(`/rides/${activeRide.value.id}/cancel/`);
    stopPolling();
    activeRide.value = null;
    showCancelled.value = true;
    fetchHistory();
  } catch {
    errorMsg.value = t('ridePage.errorRequest');
  } finally {
    cancelling.value = false;
  }
};

// ── Rating ────────────────────────────────────────────────────────────────────
const submitRating = async () => {
  if (!ratingScore.value || submittingRating.value || !activeRide.value?.id) return;
  submittingRating.value = true;
  try {
    await api.post(`/rides/${activeRide.value.id}/rate/`, { rating: ratingScore.value });
    ratingDone.value = true;
  } catch {
    toast.show(t('ridePage.ratingFailed'), 'error');
  } finally {
    submittingRating.value = false;
  }
};

// ── Reset to booking form ─────────────────────────────────────────────────────
const resetForm = () => {
  activeRide.value    = null;
  estimate.value      = null;
  ratingScore.value   = 0;
  ratingDone.value    = false;
  showCancelled.value = false;
  noDriverFound.value = false;
  errorMsg.value      = '';
  pickupAddress.value  = '';
  dropoffAddress.value = '';
  pickupLatLng.value   = null;
  dropoffLatLng.value  = null;
  scheduleEnabled.value = false;
  scheduleDate.value    = '';
  scheduleTime.value    = '';
  clearCancelGuard();
  destroyTrackingMap();
  fetchHistory();
};

// ── Rebook from history ───────────────────────────────────────────────────────
const rebookRide = (ride) => {
  // Clear active/completed state first
  activeRide.value    = null;
  estimate.value      = null;
  ratingScore.value   = 0;
  ratingDone.value    = false;
  showCancelled.value = false;
  noDriverFound.value = false;
  errorMsg.value      = '';
  scheduleEnabled.value = false;
  clearCancelGuard();
  // Pre-fill addresses
  pickupAddress.value  = ride.pickup_address  || '';
  dropoffAddress.value = ride.dropoff_address || '';
  // Pre-fill coords if the history record carries them
  const pLat = Number(ride.pickup_lat);
  const pLng = Number(ride.pickup_lng);
  if (Number.isFinite(pLat) && Number.isFinite(pLng)) {
    pickupLatLng.value = { lat: pLat, lng: pLng };
  } else {
    pickupLatLng.value = null;
  }
  const dLat = Number(ride.dropoff_lat);
  const dLng = Number(ride.dropoff_lng);
  if (Number.isFinite(dLat) && Number.isFinite(dLng)) {
    dropoffLatLng.value = { lat: dLat, lng: dLng };
    nextTick(() => {
      if (_pickMap) ensureDropoffMarker(dLat, dLng);
    });
  } else {
    dropoffLatLng.value = null;
  }
  // Scroll to top of form
  nextTick(() => {
    formTopEl.value?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
};

// ── Polling ───────────────────────────────────────────────────────────────────
const fetchActiveRide = async () => {
  try {
    const res = await api.get('/rides/active/');
    // Endpoint returns { ride, scheduled } — handle both old and new shape
    const data = res.data;
    if (data && typeof data === 'object' && 'ride' in data) {
      activeRide.value = data.ride ?? null;
      scheduledTrips.value = (Array.isArray(data.scheduled) ? data.scheduled : [])
        .filter((r) => r.kind === 'ride');
    } else if (data && data.id) {
      // fallback: legacy flat shape
      activeRide.value = data;
    }
  } catch {
    // 404 = no active ride, ignore
  }
};

const fetchHistory = async () => {
  historyLoading.value = true;
  try {
    const res = await api.get('/rides/history/');
    rideHistory.value = Array.isArray(res.data) ? res.data : [];
  } catch {
    // best-effort; leave existing history intact
  } finally {
    historyLoading.value = false;
  }
};

const pollActiveRideOnce = async () => {
  if (!activeRide.value?.id) { stopPolling(); return; }
  const prevStatus = activeRide.value.status;
  try {
    const res = await api.get('/rides/active/');
    pollHealthy.value = true;
    const data = res.data;
    // Handle both { ride, scheduled } and legacy flat shape
    const rideData = (data && typeof data === 'object' && 'ride' in data)
      ? data.ride
      : (data?.id ? data : null);
    if (data && typeof data === 'object' && 'scheduled' in data) {
      scheduledTrips.value = (Array.isArray(data.scheduled) ? data.scheduled : [])
        .filter((r) => r.kind === 'ride');
    }
    if (rideData?.id) {
      activeRide.value = rideData;
      // Stop polling when terminal state
      if (['completed', 'cancelled'].includes(rideData.status)) {
        stopPolling();
        // System-cancelled: was searching/accepted, now cancelled (no user action)
        if (
          rideData.status === 'cancelled' &&
          ['searching', 'accepted', 'arrived'].includes(prevStatus) &&
          !cancelling.value
        ) {
          noDriverFound.value = true;
          activeRide.value = null;
          fetchHistory();
        } else if (rideData.status === 'completed') {
          fetchHistory();
        }
      }
    } else {
      // No active ride returned — likely completed/cancelled
      stopPolling();
    }
  } catch {
    // ignore transient errors, but surface them on the connection dot
    pollHealthy.value = false;
  }
};

const startPolling = () => {
  stopPolling();
  pollHealthy.value = true;
  pollTimer = setInterval(pollActiveRideOnce, 5000);
};

const stopPolling = () => {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
};

// Mobile browsers throttle/suspend background timers — resync immediately
// when the tab regains focus instead of waiting for the next 5s tick.
const handleVisibilityChange = () => {
  if (document.visibilityState === 'visible' && activeRide.value?.id) {
    pollActiveRideOnce();
  }
};

// ── Leaflet: pick-map (drop-off pin) ─────────────────────────────────────────
const pickMapEl      = ref(null);
const trackingMapEl  = ref(null);
let _leaflet         = null;
let _pickMap         = null;
let _pickupMarker    = null;
let _dropoffMarker   = null;
let _trackMap        = null;
let _trackDriverMkr  = null;

const ensureLeaflet = async () => {
  if (_leaflet) return _leaflet;
  const [{ default: L }, m2x, m, shadow] = await Promise.all([
    import('leaflet'),
    import('leaflet/dist/images/marker-icon-2x.png'),
    import('leaflet/dist/images/marker-icon.png'),
    import('leaflet/dist/images/marker-shadow.png'),
  ]);
  await import('leaflet/dist/leaflet.css');
  delete L.Icon.Default.prototype._getIconUrl;
  L.Icon.Default.mergeOptions({
    iconRetinaUrl: m2x.default,
    iconUrl: m.default,
    shadowUrl: shadow.default,
  });
  _leaflet = L;
  return L;
};

const ensurePickupMarker = (lat, lng) => {
  if (!_pickMap || !_leaflet) return;
  const pos = [lat, lng];
  if (!_pickupMarker) {
    _pickupMarker = _leaflet.marker(pos, { opacity: 0.85 }).addTo(_pickMap);
  } else {
    _pickupMarker.setLatLng(pos);
  }
};

// Place/move the drop-off pin on the pick-map and recenter (used by saved-address chips).
const ensureDropoffMarker = (lat, lng) => {
  if (!_pickMap || !_leaflet) return;
  const pos = [lat, lng];
  if (!_dropoffMarker) {
    _dropoffMarker = _leaflet.marker(pos).addTo(_pickMap);
  } else {
    _dropoffMarker.setLatLng(pos);
  }
  _pickMap.setView(pos, 14);
};

const initPickMap = async () => {
  if (!pickMapEl.value) return;
  const L = await ensureLeaflet();
  const defaultCenter = [33.5731, -7.5898]; // Casablanca fallback
  _pickMap = L.map(pickMapEl.value, { zoomControl: false, attributionControl: false }).setView(defaultCenter, 12);
  addTileLayer(L, _pickMap);

  // Tap to set drop-off
  _pickMap.on('click', (e) => {
    const { lat, lng } = e.latlng;
    dropoffLatLng.value = { lat, lng };
    if (!_dropoffMarker) {
      _dropoffMarker = L.marker([lat, lng]).addTo(_pickMap);
    } else {
      _dropoffMarker.setLatLng([lat, lng]);
    }
  });

  setTimeout(() => _pickMap && _pickMap.invalidateSize(), 0);
};

const destroyPickMap = () => {
  if (_pickMap) { _pickMap.remove(); _pickMap = null; _pickupMarker = null; _dropoffMarker = null; }
};

// ── Leaflet: tracking map ─────────────────────────────────────────────────────
const renderTrackingMap = async () => {
  const d = activeRide.value?.driver;
  if (!d || d.driver_lat == null || d.driver_lng == null || !trackingMapEl.value) return;
  const L = await ensureLeaflet();
  const driverPos = [Number(d.driver_lat), Number(d.driver_lng)];
  if (!_trackMap) {
    _trackMap = L.map(trackingMapEl.value, { zoomControl: false, attributionControl: false }).setView(driverPos, 14);
    addTileLayer(L, _trackMap);
  }
  if (!_trackDriverMkr) {
    _trackDriverMkr = L.marker(driverPos).addTo(_trackMap);
  } else {
    _trackDriverMkr.setLatLng(driverPos);
  }
  _trackMap.setView(driverPos, 14);
  setTimeout(() => _trackMap && _trackMap.invalidateSize(), 0);
};

const destroyTrackingMap = () => {
  if (_trackMap) { _trackMap.remove(); _trackMap = null; _trackDriverMkr = null; }
};

// Re-render tracking map when driver pos changes
watch(
  () => [activeRide.value?.driver?.driver_lat, activeRide.value?.driver?.driver_lng],
  () => { if (hasDriverPos.value) nextTick(renderTrackingMap); },
  { immediate: true },
);

// Re-init pick-map when the form section becomes visible
watch(
  () => customerStore.isAuthenticated,
  (auth) => { if (auth) nextTick(initPickMap); },
);

// ── Auto-estimate: fire in background when both coordinates are available ──────
watch(
  () => [pickupLatLng.value, dropoffLatLng.value],
  ([pickup, dropoff]) => {
    if (pickup && dropoff && !activeRide.value) {
      // Clear stale estimate so the request button re-disables while refreshing
      estimate.value = null;
      getEstimate();
    }
  },
);

onMounted(async () => {
  // Check for in-progress ride immediately
  if (customerStore.isAuthenticated) {
    await fetchActiveRide();
    if (activeRide.value && !['completed', 'cancelled'].includes(activeRide.value.status)) {
      startPolling();
    }
    if (!activeRide.value) {
      nextTick(initPickMap);
    }
    fetchHistory();
    fetchSavedAddresses();
  }
  document.addEventListener('visibilitychange', handleVisibilityChange);
});

onBeforeUnmount(() => {
  stopPolling();
  clearCancelGuard();
  destroyPickMap();
  destroyTrackingMap();
  document.removeEventListener('visibilitychange', handleVisibilityChange);
});
</script>
