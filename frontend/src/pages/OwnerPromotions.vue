<template>
  <div class="space-y-4 pb-6">
    <!-- Page header -->
    <header class="ui-hero-ribbon ui-reveal px-4 py-3.5 md:px-5 md:py-4">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div class="min-w-0 space-y-0.5">
          <p class="ui-kicker">{{ t('ownerPromotions.kicker') }}</p>
          <h1 class="ui-display text-xl font-bold tracking-tight text-white sm:text-2xl leading-tight">{{ t('ownerPromotions.title') }}</h1>
          <p class="ui-subtle text-xs">{{ t('ownerPromotions.subtitle') }}</p>
        </div>
        <div class="mt-1 flex shrink-0 items-center gap-2">
          <svg v-if="updating" class="h-4 w-4 animate-spin text-slate-500" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true">
            <path d="M13.5 8a5.5 5.5 0 1 1-1.1-3.3M13.5 2v3.5H10"/>
          </svg>
          <span class="sr-only" aria-live="polite" aria-atomic="true">{{ updating ? t('common.updating') : '' }}</span>
          <button class="ui-btn-primary ui-press" @click="openCreate">{{ t('ownerPromotions.newPromotion') }}</button>
        </div>
      </div>
    </header>

    <!-- Loading: skeleton cards -->
    <div v-if="loading" class="space-y-3" aria-busy="true">
      <div v-for="i in 3" :key="i" class="ui-panel animate-pulse p-4">
        <div class="flex items-start justify-between gap-4">
          <div class="flex-1 space-y-2.5">
            <div class="flex items-center gap-2">
              <div class="h-4 w-36 rounded-full bg-slate-700/60" />
              <div class="h-5 w-16 rounded-full bg-slate-800/60" />
            </div>
            <div class="h-3 w-28 rounded bg-slate-800/50" />
            <div class="h-3 w-52 rounded bg-slate-800/40" />
            <div class="h-3 w-40 rounded bg-slate-800/30" />
          </div>
          <div class="flex shrink-0 gap-2">
            <div class="h-7 w-14 rounded-lg bg-slate-800/60" />
            <div class="h-7 w-16 rounded-lg bg-slate-800/50" />
          </div>
        </div>
      </div>
    </div>

    <!-- Error -->
    <div v-else-if="fetchError" class="flex items-start gap-3 rounded-2xl border border-red-500/30 bg-red-500/8 px-4 py-3" role="alert">
      <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor">
        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm-.75-9.25a.75.75 0 011.5 0v3.5a.75.75 0 01-1.5 0v-3.5zm.75 6a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd" />
      </svg>
      <p class="flex-1 text-sm text-red-300">{{ t('ownerPromotions.fetchError') }}</p>
      <button
        class="shrink-0 rounded-lg border border-red-500/40 px-3 py-1 text-xs font-semibold text-red-300 transition hover:bg-red-500/10"
        @click="fetchPromotions"
      >{{ t('ownerPromotions.retry') }}</button>
    </div>

    <!-- Empty -->
    <OwnerPromotionsEmptyState v-else-if="!promotions.length" @create="openCreate" />

    <!-- List -->
    <div v-else class="space-y-2">
      <OwnerPromotionCard
        v-for="(promo, index) in promotions"
        :key="promo.id"
        :promo="promo"
        :index="index"
        :promo-label="promoLabel"
        :toggling="togglingId === promo.id"
        :deleting="deletingId === promo.id"
        @toggle="togglePromoActive"
        @clone="clonePromo"
        @edit="openEdit"
        @delete="deletePromo"
      />
    </div>

    <!-- Platform flash sales opt-in ─────────────────────────────────────── -->
    <section v-if="flashSalesLoaded && (flashSales.length || flashSalesError)" class="space-y-2 pb-2">
      <div class="px-1 flex items-center gap-2">
        <p class="ui-kicker">⚡ {{ t('ownerPromotions.flashKicker') }}</p>
      </div>
      <!-- Fetch error -->
      <div v-if="flashSalesError" class="flex items-center gap-2 rounded-xl border border-amber-500/30 bg-amber-500/8 px-4 py-2.5 text-xs text-amber-300">
        <span class="flex-1">{{ t('ownerPromotions.flashFetchError') }}</span>
        <button
          type="button"
          class="shrink-0 rounded-lg border border-amber-500/40 px-2.5 py-1 text-[11px] font-semibold text-amber-300 transition hover:bg-amber-500/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
          @click="fetchFlashSales"
        >{{ t('ownerPromotions.retry') }}</button>
      </div>
      <!-- Sale cards -->
      <OwnerFlashSaleOptInCard
        v-for="(fs, index) in flashSales"
        :key="fs.id"
        :sale="fs"
        :index="index"
        :fmt-flash-date="fmtFlashDate"
        :busy="flashBusyId === fs.id"
        @toggle="toggleFlashOptIn"
      />
    </section>

    <!-- ── Happy Hours section ─────────────────────────────────────────────── -->
    <section class="space-y-2 pb-2">
      <div class="px-1 flex items-center justify-between gap-3">
        <p class="ui-kicker">{{ t('happyHour.kicker') }}</p>
        <button
          class="ui-btn-outline ui-press shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold"
          :disabled="hhRules.length >= 8"
          @click="openCreateHH"
        >
          <svg aria-hidden="true" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" class="h-3 w-3 shrink-0"><path d="M6 1v10M1 6h10"/></svg>
          {{ t('happyHour.add') }}
        </button>
      </div>
      <!-- Loading -->
      <div v-if="hhLoading" class="space-y-2" aria-busy="true">
        <div v-for="i in 2" :key="i" class="ui-panel animate-pulse p-4">
          <div class="flex items-center justify-between gap-4">
            <div class="flex-1 space-y-2">
              <div class="h-4 w-40 rounded-full bg-slate-700/60" />
              <div class="h-3 w-28 rounded bg-slate-800/50" />
            </div>
            <div class="flex gap-2">
              <div class="h-7 w-14 rounded-lg bg-slate-800/60" />
              <div class="h-7 w-16 rounded-lg bg-slate-800/50" />
            </div>
          </div>
        </div>
      </div>
      <!-- Fetch error -->
      <div v-else-if="hhFetchError" class="flex items-center gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-4 py-2.5 text-xs text-red-300">
        <span class="flex-1">{{ t('happyHour.fetchError') }}</span>
        <button type="button" class="shrink-0 rounded-lg border border-red-500/40 px-2.5 py-1 text-[11px] font-semibold text-red-300 transition hover:bg-red-500/10" @click="fetchHHRules">{{ t('ownerPromotions.retry') }}</button>
      </div>
      <!-- Limit notice -->
      <div v-if="hhRules.length >= 8" class="flex items-center gap-2 rounded-xl border border-amber-500/30 bg-amber-500/8 px-4 py-2.5 text-xs text-amber-300">
        {{ t('happyHour.limitReached') }}
      </div>
      <!-- Empty -->
      <div v-if="!hhLoading && !hhFetchError && !hhRules.length" class="ui-panel text-center px-6 py-8 space-y-1">
        <p class="text-sm font-semibold text-slate-100">{{ t('happyHour.noRules') }}</p>
        <p class="text-xs text-slate-400 max-w-xs mx-auto">{{ t('happyHour.noRulesHint') }}</p>
      </div>
      <!-- Rules list -->
      <OwnerHappyHourRuleCard
        v-for="(rule, index) in hhRules"
        :key="rule.id"
        :rule="rule"
        :index="index"
        :is-overnight="isOvernightRule"
        :day-labels="hhDayLabels"
        :deleting="hhDeletingId === rule.id"
        @edit="openEditHH"
        @delete="deleteHHRule"
      />
    </section>

    <!-- ── Win-back automation card ──────────────────────────────────────────── -->
    <section class="space-y-2 pb-2">
      <div class="px-1">
        <p class="ui-kicker">{{ t('winback.kicker') }}</p>
      </div>
      <div class="ui-panel ui-surface-lift p-4 space-y-4">
        <!-- Explainer + toggle row -->
        <div class="flex items-start justify-between gap-4">
          <div class="flex-1 min-w-0 space-y-1">
            <p class="text-sm font-semibold text-white leading-snug">{{ t('winback.title') }}</p>
            <p class="text-xs text-slate-400">
              {{ t('winback.explainer', { weeks: winbackForm.inactive_weeks }) }}
            </p>
          </div>
          <!-- Enabled toggle -->
          <label class="relative inline-flex shrink-0 cursor-pointer items-center" :aria-label="t('winback.enabledLabel')">
            <input
              v-model="winbackForm.enabled"
              type="checkbox"
              class="sr-only peer"
              @change="saveWinback"
            />
            <div class="h-5 w-9 rounded-full border border-slate-600 bg-slate-700 transition peer-checked:border-[var(--color-secondary)] peer-checked:bg-[var(--color-secondary)] peer-focus-visible:ring-2 peer-focus-visible:ring-[var(--color-secondary)]/60 after:absolute after:left-[2px] after:top-[2px] after:h-4 after:w-4 after:rounded-full after:bg-white after:transition peer-checked:after:translate-x-4" />
          </label>
        </div>

        <!-- Fields (collapsed when disabled) -->
        <template v-if="winbackForm.enabled">
          <div class="border-t border-slate-700/40" />

          <!-- Inactive weeks -->
          <div class="space-y-1.5">
            <label for="winback-weeks" class="block text-xs font-semibold text-slate-300">{{ t('winback.weeksLabel') }}</label>
            <div class="flex items-center gap-2">
              <input
                id="winback-weeks"
                v-model.number="winbackForm.inactive_weeks"
                type="number"
                min="1"
                max="52"
                step="1"
                class="ui-input w-24"
                @change="saveWinback"
              />
              <span class="text-xs text-slate-500">{{ t('winback.weeksUnit') }}</span>
            </div>
            <p class="text-[11px] text-slate-500">{{ t('winback.weeksHint') }}</p>
          </div>

          <!-- Custom message -->
          <div class="space-y-1.5">
            <label for="winback-msg" class="block text-xs font-semibold text-slate-300">{{ t('winback.messageLabel') }}</label>
            <textarea
              id="winback-msg"
              v-model="winbackForm.message"
              rows="2"
              maxlength="200"
              class="ui-input w-full resize-none text-sm"
              :placeholder="t('winback.messagePlaceholder')"
              @change="saveWinback"
            />
            <p class="text-[11px] text-slate-500 text-end tabular-nums">{{ winbackForm.message.length }}/200</p>
          </div>

          <!-- Save error -->
          <div v-if="winbackSaveError" class="flex items-center gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2 text-xs text-red-300" role="alert">
            {{ winbackSaveError }}
          </div>

          <!-- Save button -->
          <button
            class="ui-btn-primary w-full justify-center text-sm"
            :disabled="winbackSaving"
            @click="saveWinback"
          >
            {{ winbackSaving ? t('winback.saving') : t('winback.save') }}
          </button>
        </template>
      </div>
    </section>

    <!-- ── Referral programme card ──────────────────────────────────────────── -->
    <section class="space-y-2 pb-2">
      <div class="px-1">
        <p class="ui-kicker">{{ t('referral.kicker') }}</p>
      </div>
      <div class="ui-panel ui-surface-lift p-4 space-y-4">
        <div class="flex items-start justify-between gap-4">
          <div class="min-w-0 flex-1">
            <p class="text-sm font-semibold text-white leading-snug">{{ t('referral.title') }}</p>
            <p class="mt-1 text-xs leading-relaxed text-slate-400">{{ t('referral.explainer') }}</p>
          </div>
          <label class="relative inline-flex shrink-0 cursor-pointer items-center" :aria-label="t('referral.toggleLabel')">
            <input
              v-model="referralForm.enabled"
              type="checkbox"
              class="peer sr-only"
              @change="saveReferral"
            />
            <div class="h-5 w-9 rounded-full border border-slate-600 bg-slate-800 transition peer-checked:border-[var(--color-secondary)] peer-checked:bg-[var(--color-secondary)]"></div>
            <div class="absolute start-0.5 top-0.5 h-4 w-4 rounded-full bg-slate-400 shadow transition peer-checked:translate-x-4 rtl:peer-checked:-translate-x-4 peer-checked:bg-white"></div>
          </label>
        </div>

        <template v-if="referralForm.enabled">
          <div>
            <label for="referral-points" class="block text-xs font-semibold text-slate-300">{{ t('referral.pointsLabel') }}</label>
            <div class="mt-1.5 flex items-center gap-2">
              <input
                id="referral-points"
                v-model.number="referralForm.reward_points"
                type="number"
                min="1"
                max="9999"
                class="w-24 rounded-lg border border-slate-700/60 bg-slate-900/50 px-3 py-1.5 text-sm text-slate-200 placeholder-slate-600 focus:border-[var(--color-secondary)] focus:outline-none"
                @change="saveReferral"
              />
              <span class="text-xs text-slate-500">{{ t('referral.pointsUnit') }}</span>
            </div>
            <p class="mt-1.5 text-[11px] text-slate-500">{{ t('referral.pointsHint') }}</p>
          </div>
        </template>

        <div v-if="referralSaveError" class="flex items-center gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2 text-xs text-red-300" role="alert">
          {{ referralSaveError }}
        </div>

        <button
          class="ui-btn-primary w-full justify-center text-sm"
          :disabled="referralSaving"
          @click="saveReferral"
        >
          {{ referralSaving ? t('referral.saving') : t('referral.save') }}
        </button>
      </div>
    </section>

    <!-- Happy Hour create/edit drawer (RISK FE-2) -->
    <OwnerHappyHourFormDrawer
      v-model:form="hhForm"
      :open="hhDrawerOpen"
      :is-edit="!!hhEditing"
      :error="hhDrawerError"
      :submitting="hhSubmitting"
      :day-options="HH_DAYS"
      :categories="hhCategories"
      @close="hhDrawerOpen = false"
      @submit="submitHHForm"
    />

    <!-- Create / Edit drawer -->
    <Teleport to="body">
      <div v-if="drawerOpen" class="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/60 backdrop-blur-sm px-3 pb-3 sm:pb-0" @keydown.esc="drawerOpen = false" @click.self="drawerOpen = false">
        <div ref="drawerDialogRef" role="dialog" aria-modal="true" aria-labelledby="owner-promotions-form-dialog-title" class="ui-panel-soft w-full max-w-md max-h-[92vh] overflow-y-auto">

          <!-- Dialog header -->
          <div class="sticky top-0 z-10 flex items-center justify-between border-b border-slate-700/50 bg-[var(--color-elevated)] px-5 py-4">
            <h2 id="owner-promotions-form-dialog-title" class="text-base font-bold tracking-tight text-white">
              {{ editingPromo ? t('common.edit') : t('ownerPromotions.newPromotion') }}
            </h2>
            <button
              class="ui-press rounded-lg border border-slate-700/50 bg-slate-800/50 p-1.5 text-slate-400 hover:border-slate-600 hover:text-white transition-colors ui-touch-target"
              :aria-label="t('common.close')"
              @click="drawerOpen = false"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" class="h-4 w-4" aria-hidden="true">
                <path d="M6 6l12 12M18 6 6 18" />
              </svg>
            </button>
          </div>

          <!-- Form body -->
          <div class="space-y-5 px-5 py-5">

            <!-- Section: Basic info -->
            <div class="space-y-4">
              <!-- Name -->
              <div class="space-y-1.5">
                <label for="promo-name" class="block text-xs font-semibold text-slate-300">{{ t('ownerPromotions.nameLabel') }}</label>
                <input
                  id="promo-name"
                  v-model="form.name"
                  type="text"
                  :placeholder="t('ownerPromotions.namePlaceholder')"
                  class="ui-input w-full"
                />
              </div>

              <!-- Description -->
              <div class="space-y-1.5">
                <label for="promo-description" class="block text-xs font-semibold text-slate-300">{{ t('ownerPromotions.descriptionLabel') }}</label>
                <input id="promo-description" v-model="form.description" type="text" class="ui-input w-full" />
              </div>

              <!-- Promo code -->
              <div class="space-y-1.5">
                <label for="promo-code" class="block text-xs font-semibold text-slate-300">{{ t('ownerPromotions.codeLabel') }}</label>
                <input
                  id="promo-code"
                  v-model="form.code"
                  type="text"
                  maxlength="20"
                  autocomplete="off"
                  class="ui-input w-full uppercase font-mono tracking-widest"
                  :placeholder="t('ownerPromotions.codePlaceholder')"
                  @input="form.code = form.code.toUpperCase()"
                />
                <p class="text-[11px] text-slate-500">{{ t('ownerPromotions.codeHint') }}</p>
              </div>
            </div>

            <div class="border-t border-slate-700/40" />

            <!-- Section: Discount -->
            <div class="space-y-4">
              <!-- Type -->
              <div class="space-y-1.5">
                <p id="promo-type-label" class="block text-xs font-semibold text-slate-300">{{ t('ownerPromotions.typeLabel') }}</p>
                <div role="group" aria-labelledby="promo-type-label" class="flex gap-2 flex-wrap">
                  <button
                    v-for="opt in promoTypes"
                    :key="opt.value"
                    type="button"
                    :aria-pressed="form.promo_type === opt.value"
                    class="rounded-xl border px-3 py-1.5 text-xs font-medium transition-colors"
                    :class="form.promo_type === opt.value
                      ? 'border-[var(--color-secondary)]/60 bg-[var(--color-secondary)]/10 text-[var(--color-secondary)]'
                      : 'border-slate-700 text-slate-400 hover:border-slate-500'"
                    @click="form.promo_type = opt.value"
                  >{{ opt.label }}</button>
                </div>
              </div>

              <!-- Discount value -->
              <div v-if="form.promo_type !== 'free_delivery'" class="space-y-1.5">
                <label for="promo-discount-value" class="block text-xs font-semibold text-slate-300">
                  {{ t('ownerPromotions.discountValueLabel') }}
                  <span class="text-slate-500 font-normal ms-1">{{ form.promo_type === 'percentage' ? '%' : '' }}</span>
                </label>
                <input id="promo-discount-value" v-model="form.discount_value" type="number" min="0" step="0.01" class="ui-input w-full" />
                <p class="text-[11px] text-slate-500">{{ t('ownerPromotions.discountValueHint') }}</p>
              </div>

              <!-- Min order -->
              <div class="space-y-1.5">
                <label for="promo-min-order" class="block text-xs font-semibold text-slate-300">{{ t('ownerPromotions.minOrderLabel') }}</label>
                <input id="promo-min-order" v-model="form.min_order_amount" type="number" min="0" step="0.01" class="ui-input w-full" />
              </div>

              <!-- Live preview of what the customer sees -->
              <div class="rounded-xl border border-indigo-500/25 bg-indigo-500/8 px-4 py-3 space-y-1">
                <p class="text-[11px] font-semibold uppercase tracking-wider text-indigo-300">{{ t('ownerPromotions.previewTitle') }}</p>
                <p class="text-sm text-slate-200">{{ promoPreview }}</p>
              </div>
            </div>

            <div class="border-t border-slate-700/40" />

            <!-- Section: Scheduling -->
            <div class="space-y-4">
              <!-- Days checkboxes -->
              <div class="space-y-1.5">
                <p id="promo-days-label" class="block text-xs font-semibold text-slate-300">{{ t('ownerPromotions.daysLabel') }}</p>
                <div role="group" aria-labelledby="promo-days-label" class="flex flex-wrap gap-1.5">
                  <button
                    v-for="d in DAYS"
                    :key="d.key"
                    type="button"
                    :aria-pressed="form.days.includes(d.key)"
                    class="inline-flex min-h-[36px] items-center rounded-full border px-2.5 py-1.5 text-[11px] font-medium transition-colors"
                    :class="form.days.includes(d.key)
                      ? 'border-[var(--color-secondary)]/60 bg-[var(--color-secondary)]/10 text-[var(--color-secondary)]'
                      : 'border-slate-700 text-slate-400 hover:border-slate-500'"
                    @click="toggleDay(d.key)"
                  >{{ d.label }}</button>
                </div>
                <p class="text-[11px] text-slate-500">{{ t('ownerPromotions.daysHint') }}</p>
              </div>

              <!-- Time window -->
              <div class="space-y-1.5">
                <p id="promo-time-label" class="block text-xs font-semibold text-slate-300">{{ t('ownerPromotions.timeLabel') }}</p>
                <div role="group" aria-labelledby="promo-time-label" class="flex items-center gap-2">
                  <input v-model="form.time_start" type="time" class="ui-input flex-1" :aria-label="t('ownerPromotions.timeStart')" />
                  <span class="text-slate-500 shrink-0" aria-hidden="true">—</span>
                  <input v-model="form.time_end" type="time" class="ui-input flex-1" :aria-label="t('ownerPromotions.timeEnd')" />
                </div>
              </div>

              <!-- Date range -->
              <div class="space-y-1.5">
                <p id="promo-daterange-label" class="block text-xs font-semibold text-slate-300">{{ t('ownerPromotions.dateRangeLabel') }}</p>
                <div role="group" aria-labelledby="promo-daterange-label" class="flex items-center gap-2">
                  <input v-model="form.active_from" type="date" class="ui-input flex-1" :aria-label="t('ownerPromotions.dateFrom')" />
                  <span class="text-slate-500 shrink-0" aria-hidden="true">—</span>
                  <input v-model="form.active_until" type="date" class="ui-input flex-1" :aria-label="t('ownerPromotions.dateUntil')" :min="form.active_from || undefined" />
                </div>
              </div>
            </div>

            <div class="border-t border-slate-700/40" />

            <!-- Section: Limits & activation -->
            <div class="space-y-4">
              <!-- Max uses -->
              <div class="space-y-1.5">
                <label for="promo-max-uses" class="block text-xs font-semibold text-slate-300">{{ t('ownerPromotions.maxUsesLabel') }}</label>
                <input id="promo-max-uses" v-model="form.max_uses" type="number" min="1" step="1" class="ui-input w-full" placeholder="∞" />
                <p class="text-[11px] text-slate-500">{{ t('ownerPromotions.maxUsesHint') }}</p>
              </div>

              <!-- Active toggle -->
              <label class="flex items-center gap-3 cursor-pointer rounded-xl border border-slate-700/50 bg-slate-800/40 px-4 py-3 ui-touch-target transition-colors hover:border-slate-600/60">
                <input
                  v-model="form.is_active"
                  type="checkbox"
                  class="rounded"
                />
                <span class="text-sm font-medium text-slate-300">{{ t('ownerPromotions.isActiveLabel') }}</span>
              </label>
            </div>

            <!-- Error -->
            <div v-if="drawerError" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
              <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
              <p class="flex-1 text-sm text-red-300">{{ drawerError }}</p>
            </div>

            <!-- Submit -->
            <button
              class="ui-btn-primary w-full justify-center"
              :disabled="submitting"
              @click="submitForm"
            >
              {{ submitting
                ? (editingPromo ? t('ownerPromotions.saving') : t('ownerPromotions.creating'))
                : (editingPromo ? t('ownerPromotions.save') : t('ownerPromotions.create'))
              }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { nextTick, onBeforeUnmount, onMounted, reactive, ref, computed, watch } from 'vue';
import OwnerFlashSaleOptInCard from '../components/OwnerFlashSaleOptInCard.vue';
import OwnerHappyHourFormDrawer from '../components/OwnerHappyHourFormDrawer.vue';
import OwnerHappyHourRuleCard from '../components/OwnerHappyHourRuleCard.vue';
import OwnerPromotionCard from '../components/OwnerPromotionCard.vue';
import OwnerPromotionsEmptyState from '../components/OwnerPromotionsEmptyState.vue';
import { useConfirmModal } from '../composables/useConfirmModal';
import { useI18n } from '../composables/useI18n';
import { useToastStore } from '../stores/toast';
import { useTenantStore } from '../stores/tenant';
import api from '../lib/api';
import { isFresh, readCache, writeCache } from '../lib/staleCache';

// Explicit name so <KeepAlive :exclude> in OwnerLayout reliably skips this page
// (has event-listener cleanup that must run on unmount).
defineOptions({ name: "OwnerPromotions" });

const { t, currentLocale } = useI18n();
const toast = useToastStore();
const tenant = useTenantStore();

// ── Constants ─────────────────────────────────────────────────────────────────
// Day keys — labels resolved via i18n (reuses stepDishes.weekday_* keys)
const DAY_KEYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];
const DAYS = computed(() => DAY_KEYS.map((key) => ({ key, label: t(`stepDishes.weekday_${key}`) })));

const promoTypes = computed(() => [
  { value: 'percentage', label: t('ownerPromotions.typePercentage') },
  { value: 'fixed', label: t('ownerPromotions.typeFixed') },
  { value: 'free_delivery', label: t('ownerPromotions.typeFreeDelivery') },
]);

const PROMOS_CACHE_KEY = 'owner.promotions';
const PROMOS_TTL_MS = 5 * 60 * 1000; // 5 min

// ── State ─────────────────────────────────────────────────────────────────────
const loading = ref(false);
const updating = ref(false);
const fetchError = ref(false);
const promotions = ref([]);
const drawerOpen = ref(false);
const drawerDialogRef = ref(null);
const editingPromo = ref(null);

const FOCUSABLE = [
  'a[href]', 'button:not([disabled])', 'input:not([disabled])',
  'select:not([disabled])', 'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(', ');

const trapDrawerFocus = (e) => {
  if (!drawerDialogRef.value || e.key !== 'Tab') return;
  const focusable = Array.from(drawerDialogRef.value.querySelectorAll(FOCUSABLE));
  if (!focusable.length) return;
  const first = focusable[0];
  const last  = focusable[focusable.length - 1];
  if (e.shiftKey) {
    if (document.activeElement === first) { e.preventDefault(); last.focus(); }
  } else {
    if (document.activeElement === last)  { e.preventDefault(); first.focus(); }
  }
};

watch(drawerOpen, async (open) => {
  if (open) {
    await nextTick();
    drawerDialogRef.value?.querySelector(FOCUSABLE)?.focus();
    document.addEventListener('keydown', trapDrawerFocus);
  } else {
    document.removeEventListener('keydown', trapDrawerFocus);
  }
});
onBeforeUnmount(() => document.removeEventListener('keydown', trapDrawerFocus));
const submitting = ref(false);
const deletingId = ref(null);
const togglingId = ref(null);
const drawerError = ref('');
const { confirm } = useConfirmModal();

const form = reactive({
  name: '',
  description: '',
  code: '',
  promo_type: 'percentage',
  discount_value: '',
  min_order_amount: '0',
  days: [],
  time_start: '',
  time_end: '',
  active_from: '',
  active_until: '',
  max_uses: '',
  is_active: true,
});

const resetForm = () => {
  form.name = '';
  form.description = '';
  form.code = '';
  form.promo_type = 'percentage';
  form.discount_value = '';
  form.min_order_amount = '0';
  form.days = [];
  form.time_start = '';
  form.time_end = '';
  form.active_from = '';
  form.active_until = '';
  form.max_uses = '';
  form.is_active = true;
};

// ── Helpers ───────────────────────────────────────────────────────────────────
const promoLabel = (promo) => {
  if (promo.promo_type === 'percentage') return t('ownerPromotions.labelPercentage', { value: promo.discount_value });
  if (promo.promo_type === 'fixed') return t('ownerPromotions.labelFixed', { value: promo.discount_value });
  return t('ownerPromotions.typeFreeDelivery');
};

// Live, human-readable preview of what a customer sees as the owner fills the form.
const promoPreview = computed(() => {
  const v = parseFloat(form.discount_value) || 0;
  let base;
  if (form.promo_type === 'percentage') base = t('ownerPromotions.labelPercentage', { value: v });
  else if (form.promo_type === 'fixed') base = t('ownerPromotions.labelFixed', { value: v });
  else base = t('ownerPromotions.typeFreeDelivery');
  const min = parseFloat(form.min_order_amount) || 0;
  if (min > 0) base += ' ' + t('ownerPromotions.previewMinClause', { min });
  return base;
});

const toggleDay = (key) => {
  const idx = form.days.indexOf(key);
  if (idx >= 0) form.days.splice(idx, 1);
  else form.days.push(key);
};

// ── Drawer ────────────────────────────────────────────────────────────────────
const openCreate = () => {
  editingPromo.value = null;
  resetForm();
  drawerError.value = '';
  drawerOpen.value = true;
};

const togglePromoActive = async (promo) => {
  if (togglingId.value === promo.id) return;
  togglingId.value = promo.id;
  // Optimistic update
  promo.is_active = !promo.is_active;
  try {
    await api.patch(`/owner/promotions/${promo.id}/`, { is_active: promo.is_active });
  } catch {
    // Revert on error
    promo.is_active = !promo.is_active;
    toast.show(t('ownerPromotions.toggleActiveFailed'), 'error');
  } finally {
    togglingId.value = null;
  }
};

const openEdit = (promo) => {
  editingPromo.value = promo;
  form.name = promo.name;
  form.description = promo.description || '';
  form.promo_type = promo.promo_type;
  form.discount_value = promo.discount_value;
  form.min_order_amount = promo.min_order_amount;
  form.days = [...(promo.days || [])];
  form.time_start = promo.time_start || '';
  form.time_end = promo.time_end || '';
  form.active_from = promo.active_from || '';
  form.active_until = promo.active_until || '';
  form.max_uses = promo.max_uses != null ? String(promo.max_uses) : '';
  form.is_active = promo.is_active;
  form.code = promo.code || '';
  drawerError.value = '';
  drawerOpen.value = true;
};

/** Open the create drawer pre-seeded with a copy of `promo`.
 *  The clone starts inactive (draft) so the owner can review before enabling.
 *  The promo code is cleared — a code must be unique; the owner sets one if needed.
 */
const clonePromo = (promo) => {
  editingPromo.value = null;
  form.name = t('ownerPromotions.clonedName', { name: promo.name });
  form.description = promo.description || '';
  form.promo_type = promo.promo_type;
  form.discount_value = promo.discount_value;
  form.min_order_amount = promo.min_order_amount;
  form.days = [...(promo.days || [])];
  form.time_start = promo.time_start || '';
  form.time_end = promo.time_end || '';
  // Do not copy date range — the user almost certainly needs new dates for the clone.
  form.active_from = '';
  form.active_until = '';
  form.max_uses = promo.max_uses != null ? String(promo.max_uses) : '';
  // Start inactive so the owner reviews before it goes live.
  form.is_active = false;
  // Clear code — promo codes must be unique; let the owner set a new one if needed.
  form.code = '';
  drawerError.value = '';
  drawerOpen.value = true;
};

// ── API ───────────────────────────────────────────────────────────────────────
const fetchPromotions = async () => {
  const cached = readCache(PROMOS_CACHE_KEY);
  if (cached) {
    promotions.value = cached;
    if (isFresh(PROMOS_CACHE_KEY, PROMOS_TTL_MS)) return;
    updating.value = true;
  } else {
    loading.value = true;
  }
  fetchError.value = false;
  try {
    const res = await api.get('/owner/promotions/');
    promotions.value = res.data;
    writeCache(PROMOS_CACHE_KEY, res.data);
  } catch {
    if (!cached) fetchError.value = true;
  } finally {
    loading.value = false;
    updating.value = false;
  }
};

const submitForm = async () => {
  drawerError.value = '';
  if (!form.name.trim()) {
    drawerError.value = t('ownerPromotions.nameRequired');
    return;
  }
  // Discount value required for non-free_delivery types
  if (form.promo_type !== 'free_delivery') {
    const dv = parseFloat(form.discount_value);
    if (!(dv > 0)) {
      drawerError.value = t('ownerPromotions.discountRequired');
      return;
    }
    if (form.promo_type === 'percentage' && dv > 100) {
      drawerError.value = t('ownerPromotions.discountMaxPercent');
      return;
    }
  }
  // Time window: both start and end must be provided together
  if ((form.time_start && !form.time_end) || (!form.time_start && form.time_end)) {
    drawerError.value = t('ownerPromotions.timeRangeIncomplete');
    return;
  }
  // Date range: end must not be before start
  if (form.active_from && form.active_until && form.active_until < form.active_from) {
    drawerError.value = t('ownerPromotions.dateRangeInvalid');
    return;
  }
  // max_uses must be ≥ 1 if provided (HTML min="1" is advisory only when typed directly)
  if (form.max_uses !== '' && form.max_uses !== null) {
    const mu = parseInt(form.max_uses);
    if (Number.isNaN(mu) || mu < 1) {
      drawerError.value = t('ownerPromotions.maxUsesInvalid');
      return;
    }
  }
  submitting.value = true;
  const payload = {
    name: form.name.trim(),
    description: form.description.trim(),
    promo_type: form.promo_type,
    discount_value: form.discount_value || '0',
    min_order_amount: form.min_order_amount || '0',
    days: form.days,
    time_start: form.time_start || '',
    time_end: form.time_end || '',
    active_from: form.active_from || null,
    active_until: form.active_until || null,
    max_uses: form.max_uses ? parseInt(form.max_uses) : null,
    is_active: form.is_active,
    code: form.code.trim().toUpperCase(),
  };
  try {
    if (editingPromo.value) {
      const res = await api.patch(`/owner/promotions/${editingPromo.value.id}/`, payload);
      const idx = promotions.value.findIndex((p) => p.id === editingPromo.value.id);
      if (idx >= 0) promotions.value[idx] = res.data;
      writeCache(PROMOS_CACHE_KEY, promotions.value); // keep cache in sync
      toast.show(t('ownerPromotions.save'), 'success');
    } else {
      const res = await api.post('/owner/promotions/', payload);
      promotions.value.unshift(res.data);
      writeCache(PROMOS_CACHE_KEY, promotions.value);
      toast.show(t('ownerPromotions.create'), 'success');
    }
    drawerOpen.value = false;
  } catch (err) {
    const detail = err?.response?.data?.detail || err?.response?.data?.non_field_errors?.[0];
    drawerError.value = editingPromo.value
      ? (detail || t('ownerPromotions.saveFailed'))
      : (detail || t('ownerPromotions.createFailed'));
  } finally {
    submitting.value = false;
  }
};

const deletePromo = async (promo) => {
  if (deletingId.value === promo.id) return;
  const ok = await confirm({
    title: t('ownerPromotions.deleteConfirm'),
    body: t('confirmModal.defaultBody'),
    confirmLabel: t('common.delete'),
  });
  if (!ok) return;
  deletingId.value = promo.id;
  try {
    await api.delete(`/owner/promotions/${promo.id}/`);
    promotions.value = promotions.value.filter((p) => p.id !== promo.id);
    writeCache(PROMOS_CACHE_KEY, promotions.value);
    toast.show(t('ownerPromotions.deleted'), 'success');
  } catch {
    toast.show(t('ownerPromotions.deleteFailed'), 'error');
  } finally {
    deletingId.value = null;
  }
};

// ── Platform flash sales opt-in ──────────────────────────────────────────────
const flashSales = ref([]);
const flashSalesLoaded = ref(false);
const flashSalesError = ref(false);
const flashBusyId = ref(null);

const fmtFlashDate = (iso) => {
  if (!iso) return '';
  try {
    return new Intl.DateTimeFormat(currentLocale.value, {
      month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
    }).format(new Date(iso));
  } catch {
    return iso.slice(0, 16);
  }
};

const fetchFlashSales = async () => {
  flashSalesError.value = false;
  try {
    const res = await api.get('/owner/flash-sales/');
    flashSales.value = Array.isArray(res.data) ? res.data : [];
  } catch {
    flashSalesError.value = true;
  } finally {
    flashSalesLoaded.value = true;
  }
};

const toggleFlashOptIn = async (fs) => {
  flashBusyId.value = fs.id;
  try {
    if (fs.opted_in) {
      await api.delete(`/owner/flash-sales/${fs.id}/opt-in/`);
      const idx = flashSales.value.findIndex((s) => s.id === fs.id);
      if (idx >= 0) flashSales.value[idx] = { ...fs, opted_in: false };
      toast.show(t('ownerPromotions.flashOptedOut'), 'info');
    } else {
      await api.post(`/owner/flash-sales/${fs.id}/opt-in/`);
      const idx = flashSales.value.findIndex((s) => s.id === fs.id);
      if (idx >= 0) flashSales.value[idx] = { ...fs, opted_in: true };
      toast.show(t('ownerPromotions.flashOptedIn'), 'success');
    }
  } catch {
    toast.show(t('ownerPromotions.flashToggleFailed'), 'error');
  } finally {
    flashBusyId.value = null;
  }
};

// ── Win-back automation ───────────────────────────────────────────────────────

const winbackForm = reactive({
  enabled: tenant.meta?.profile?.winback_enabled ?? false,
  inactive_weeks: tenant.meta?.profile?.winback_inactive_weeks ?? 4,
  message: tenant.meta?.profile?.winback_message ?? '',
});
const winbackSaving = ref(false);
const winbackSaveError = ref('');

const saveWinback = async () => {
  winbackSaveError.value = '';
  const weeks = Number(winbackForm.inactive_weeks);
  if (!Number.isInteger(weeks) || weeks < 1 || weeks > 52) {
    winbackSaveError.value = t('winback.weeksInvalid');
    return;
  }
  winbackSaving.value = true;
  try {
    await api.patch('/profile/', {
      winback_enabled: winbackForm.enabled,
      winback_inactive_weeks: weeks,
      winback_message: winbackForm.message.trim(),
    });
    tenant.mergeProfile({
      winback_enabled: winbackForm.enabled,
      winback_inactive_weeks: weeks,
      winback_message: winbackForm.message.trim(),
    });
    toast.show(t('winback.saved'), 'success');
  } catch {
    winbackSaveError.value = t('winback.saveFailed');
  } finally {
    winbackSaving.value = false;
  }
};

// ── Referral programme ─────────────────────────────────────────────────────────

const referralForm = reactive({
  enabled: tenant.meta?.profile?.referral_enabled ?? false,
  reward_points: tenant.meta?.profile?.referral_reward_points ?? 100,
});
const referralSaving = ref(false);
const referralSaveError = ref('');

const saveReferral = async () => {
  referralSaveError.value = '';
  const pts = Number(referralForm.reward_points);
  if (!Number.isInteger(pts) || pts < 1 || pts > 9999) {
    referralSaveError.value = t('referral.pointsInvalid');
    return;
  }
  referralSaving.value = true;
  try {
    await api.patch('/profile/', {
      referral_enabled: referralForm.enabled,
      referral_reward_points: pts,
    });
    tenant.mergeProfile({
      referral_enabled: referralForm.enabled,
      referral_reward_points: pts,
    });
    toast.show(t('referral.saved'), 'success');
  } catch {
    referralSaveError.value = t('referral.saveFailed');
  } finally {
    referralSaving.value = false;
  }
};

onMounted(() => {
  fetchPromotions();
  fetchFlashSales();
  fetchHHRules();
  fetchHHCategories();
});

// ── Happy Hours ───────────────────────────────────────────────────────────────

// Day definitions: 0=Monday…6=Sunday (Python weekday() convention)
const HH_DAY_KEYS = [0, 1, 2, 3, 4, 5, 6];
const HH_DAY_I18N = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];
const HH_DAYS = computed(() =>
  HH_DAY_KEYS.map((v, i) => ({ value: v, label: t(`stepDishes.weekday_${HH_DAY_I18N[i]}`) }))
);

const hhRules = ref([]);
const hhLoading = ref(false);
const hhFetchError = ref(false);
const hhDrawerOpen = ref(false);
const hhEditing = ref(null);
const hhSubmitting = ref(false);
const hhDeletingId = ref(null);
const hhDrawerError = ref('');
const hhCategories = ref([]);

const hhForm = reactive({
  name: '',
  percent_off: 20,
  start_time: '',
  end_time: '',
  days: [],
  category_ids: [],
  is_active: true,
});

const resetHHForm = () => {
  hhForm.name = '';
  hhForm.percent_off = 20;
  hhForm.start_time = '';
  hhForm.end_time = '';
  hhForm.days = [];
  hhForm.category_ids = [];
  hhForm.is_active = true;
};

const isOvernightRule = (rule) =>
  rule.start_time && rule.end_time && rule.start_time > rule.end_time;

const hhDayLabels = (days) => {
  if (!days?.length) return '';
  return days
    .map((d) => HH_DAYS.value.find((x) => x.value === d)?.label || String(d))
    .join(', ');
};

const openCreateHH = () => {
  hhEditing.value = null;
  resetHHForm();
  hhDrawerError.value = '';
  hhDrawerOpen.value = true;
};

const openEditHH = (rule) => {
  hhEditing.value = rule;
  hhForm.name = rule.name;
  hhForm.percent_off = rule.percent_off;
  hhForm.start_time = rule.start_time;
  hhForm.end_time = rule.end_time;
  hhForm.days = [...(rule.days || [])];
  hhForm.category_ids = [...(rule.category_ids || [])];
  hhForm.is_active = rule.is_active;
  hhDrawerError.value = '';
  hhDrawerOpen.value = true;
};

const fetchHHRules = async () => {
  hhLoading.value = true;
  hhFetchError.value = false;
  try {
    const res = await api.get('/happy-hours/');
    hhRules.value = Array.isArray(res.data) ? res.data : (res.data?.results ?? []);
  } catch {
    hhFetchError.value = true;
  } finally {
    hhLoading.value = false;
  }
};

const fetchHHCategories = async () => {
  try {
    const res = await api.get('/categories/');
    const rows = Array.isArray(res.data) ? res.data : (res.data?.results ?? []);
    hhCategories.value = rows.map((c) => ({ id: c.id, name: c.name }));
  } catch {
    // non-critical — category scope is optional
  }
};

const submitHHForm = async () => {
  hhDrawerError.value = '';
  if (!hhForm.name.trim()) {
    hhDrawerError.value = t('happyHour.nameRequired');
    return;
  }
  const pct = Number(hhForm.percent_off);
  if (!Number.isInteger(pct) || pct < 1 || pct > 90) {
    hhDrawerError.value = t('happyHour.percentRequired');
    return;
  }
  if (!hhForm.start_time || !hhForm.end_time) {
    hhDrawerError.value = t('happyHour.timeRequired');
    return;
  }
  hhSubmitting.value = true;
  const payload = {
    name: hhForm.name.trim(),
    percent_off: pct,
    start_time: hhForm.start_time,
    end_time: hhForm.end_time,
    days: [...hhForm.days],
    category_ids: [...hhForm.category_ids],
    is_active: hhForm.is_active,
  };
  try {
    if (hhEditing.value) {
      const res = await api.patch(`/happy-hours/${hhEditing.value.id}/`, payload);
      const idx = hhRules.value.findIndex((r) => r.id === hhEditing.value.id);
      if (idx >= 0) hhRules.value[idx] = res.data;
      toast.show(t('happyHour.save'), 'success');
    } else {
      const res = await api.post('/happy-hours/', payload);
      hhRules.value.unshift(res.data);
      toast.show(t('happyHour.create'), 'success');
    }
    hhDrawerOpen.value = false;
  } catch (err) {
    const detail = err?.response?.data?.detail || err?.response?.data?.non_field_errors?.[0];
    hhDrawerError.value = hhEditing.value
      ? (detail || t('happyHour.saveFailed'))
      : (detail || t('happyHour.createFailed'));
  } finally {
    hhSubmitting.value = false;
  }
};

const deleteHHRule = async (rule) => {
  if (hhDeletingId.value === rule.id) return;
  const ok = await confirm({
    title: t('happyHour.deleteConfirm'),
    body: t('confirmModal.defaultBody'),
    confirmLabel: t('common.delete'),
  });
  if (!ok) return;
  hhDeletingId.value = rule.id;
  try {
    await api.delete(`/happy-hours/${rule.id}/`);
    hhRules.value = hhRules.value.filter((r) => r.id !== rule.id);
    toast.show(t('happyHour.deleted'), 'success');
  } catch {
    toast.show(t('happyHour.deleteFailed'), 'error');
  } finally {
    hhDeletingId.value = null;
  }
};

</script>
