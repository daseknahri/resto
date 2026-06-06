<template>
  <div class="space-y-4">
    <section v-if="!standalone" class="ui-panel space-y-3 p-5 ui-reveal">
      <p class="ui-kicker">{{ t("stepPublish.title") }}</p>
      <h2 class="text-xl font-semibold text-white leading-tight">{{ t("stepPublish.readinessSection") }}</h2>
      <p class="ui-subtle">{{ t("stepPublish.description") }}</p>
    </section>

    <section :class="sectionPanelClass" class="ui-reveal" :style="{ '--ui-delay': '28ms' }">
      <div class="space-y-1">
        <p class="ui-section-kicker">{{ t("stepPublish.title") }}</p>
        <h3 class="text-lg font-semibold text-white leading-tight">{{ t("stepPublish.readinessSection") }}</h3>
      </div>

      <div class="flex flex-wrap gap-2">
        <span class="ui-chip tabular-nums">
          {{ categoriesCount }} {{ t("common.categories").toLowerCase() }}
        </span>
        <span class="ui-chip tabular-nums">
          {{ dishesCount }} {{ t("common.dishes").toLowerCase() }}
        </span>
        <span
          class="ui-chip"
          :class="published ? 'border-emerald-500/35 bg-emerald-500/10 text-emerald-200' : ''"
        >
          {{ published ? t("stepPublish.liveBadge") : t("stepPublish.draftBadge") }}
        </span>
        <span
          class="ui-chip"
          :class="form.is_open ? 'border-emerald-500/35 bg-emerald-500/10 text-emerald-200' : ''"
        >
          {{ form.is_open ? t("stepPublish.restaurantOpen") : t("common.closed") }}
        </span>
      </div>

      <div v-if="isBrowseOnlyPlan" class="rounded-xl border border-sky-500/40 bg-sky-500/10 p-3 text-xs text-sky-100">
        {{ t("stepPublish.browseOnlyWarning") }}
      </div>

      <div class="grid gap-4 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)]">
        <ul class="space-y-2 text-sm" role="list">
          <li
            v-for="(item, index) in checks"
            :key="item.key"
            class="ui-readiness-item flex items-center justify-between gap-3 ui-reveal"
            :data-complete="item.ok || undefined"
            :data-warning="!item.ok || undefined"
            :style="{ '--ui-delay': `${index * 28}ms` }"
          >
            <div class="flex items-center gap-2.5 min-w-0">
              <span class="ui-readiness-dot shrink-0" aria-hidden="true"></span>
              <span class="min-w-0 truncate text-slate-200">{{ item.label }}</span>
            </div>
            <span
              class="shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold"
              :class="item.ok ? 'bg-emerald-500/10 text-emerald-200' : 'bg-amber-500/10 text-amber-200'"
            >
              {{ item.ok ? t("stepPublish.ok") : t("stepPublish.missing") }}
            </span>
          </li>
        </ul>

        <div class="space-y-3">
          <div class="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 space-y-2 text-sm">
            <p class="ui-section-kicker">{{ t("stepPublish.menuUrl") }}</p>
            <p class="break-all text-slate-100 text-sm tabular-nums">{{ menuUrl }}</p>
            <p v-if="publishedAt" class="text-xs text-slate-400">{{ t("stepPublish.publishedAt", { date: formattedPublishedAt }) }}</p>
          </div>

          <div class="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 space-y-3">
            <div class="flex items-center justify-between gap-3">
              <div class="min-w-0">
                <p class="ui-section-kicker">{{ t("stepPublish.publishStatus") }}</p>
                <p class="text-lg font-semibold text-white leading-tight">
                  {{ published ? t("stepPublish.published") : t("stepPublish.draft") }}
                </p>
              </div>
              <span
                class="shrink-0 rounded-full px-3 py-1 text-xs font-semibold"
                :class="published ? 'bg-emerald-500/10 text-emerald-200' : 'bg-slate-800 text-slate-300'"
              >
                {{ published ? t("stepPublish.liveBadge") : t("stepPublish.draftBadge") }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section :class="sectionPanelClass" class="ui-reveal" :style="{ '--ui-delay': '56ms' }">
      <div class="space-y-1">
        <p class="ui-section-kicker">{{ t("stepPublish.availabilityControls") }}</p>
        <h3 class="text-lg font-semibold text-white leading-tight">{{ t("stepPublish.availabilitySectionTitle") }}</h3>
      </div>

      <div class="space-y-3 rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
        <label class="ui-touch-target flex cursor-pointer items-center justify-between gap-3 rounded-xl border border-slate-800 bg-slate-900/70 px-3">
          <div class="space-y-0.5">
            <span class="text-sm font-medium text-slate-100">{{ t("stepPublish.restaurantOpen") }}</span>
            <p class="text-xs text-slate-500">{{ t("stepPublish.restaurantOpenHint") }}</p>
          </div>
          <input v-model="form.is_open" type="checkbox" class="h-4 w-4 shrink-0 rounded border-slate-600 bg-slate-900 text-brand-secondary" />
        </label>

        <label class="ui-touch-target flex cursor-pointer items-center justify-between gap-3 rounded-xl border border-slate-800 bg-slate-900/70 px-3">
          <div class="space-y-0.5">
            <span class="text-sm font-medium text-slate-100">{{ t("stepPublish.disablePublicMenu") }}</span>
            <p class="text-xs text-slate-500">{{ t("stepPublish.disablePublicMenuHint") }}</p>
          </div>
          <input
            v-model="form.is_menu_temporarily_disabled"
            type="checkbox"
            class="h-4 w-4 shrink-0 rounded border-slate-600 bg-slate-900 text-brand-secondary"
            @change="clearError('is_menu_temporarily_disabled')"
          />
        </label>

        <div v-if="form.is_menu_temporarily_disabled" class="space-y-2 rounded-xl border border-slate-800 bg-slate-950/45 p-3">
          <label for="sp-disabled-note" class="text-sm font-medium text-slate-200">{{ t("stepPublish.disableMessage") }}</label>
          <textarea
            id="sp-disabled-note"
            v-model="form.menu_disabled_note"
            rows="2"
            class="ui-textarea"
            :class="errors.menu_disabled_note ? 'border-red-400' : ''"
            :aria-label="t('stepPublish.disableMessage')"
            :aria-invalid="errors.menu_disabled_note ? 'true' : undefined"
            aria-describedby="step-publish-disabled-note-error"
            :placeholder="t('stepPublish.disableMessagePlaceholder')"
            @input="clearError('menu_disabled_note')"
          ></textarea>
          <p v-if="errors.menu_disabled_note" id="step-publish-disabled-note-error" class="text-xs text-red-300" role="alert">{{ errors.menu_disabled_note }}</p>
        </div>

        <!-- Receipt message -->
        <div class="space-y-2 rounded-xl border border-slate-800 bg-slate-950/45 p-3">
          <div class="space-y-0.5">
            <label for="sp-receipt-message" class="text-sm font-medium text-slate-200">{{ t("stepPublish.receiptMessage") }}</label>
            <p class="text-xs text-slate-500">{{ t("stepPublish.receiptMessageHint") }}</p>
          </div>
          <textarea
            id="sp-receipt-message"
            v-model="form.receipt_message"
            rows="2"
            maxlength="300"
            class="ui-textarea"
            :aria-label="t('stepPublish.receiptMessage')"
            :placeholder="t('stepPublish.receiptMessagePlaceholder')"
          ></textarea>
          <p class="text-end text-[11px] text-slate-600 tabular-nums">{{ (form.receipt_message || "").length }}/300</p>
        </div>

        <!-- SMS notifications -->
        <label class="ui-touch-target flex cursor-pointer items-center justify-between gap-3 rounded-xl border border-slate-800 bg-slate-900/70 px-3">
          <div class="space-y-0.5">
            <span class="text-sm font-medium text-slate-100">{{ t("stepPublish.smsNotifications") }}</span>
            <p class="text-xs text-slate-500">{{ t("stepPublish.smsNotificationsHint") }}</p>
          </div>
          <input v-model="form.sms_notifications_enabled" type="checkbox" class="h-4 w-4 shrink-0 rounded border-slate-600 bg-slate-900 text-brand-secondary" />
        </label>

        <!-- Cash on handover for trusted customers -->
        <label class="ui-touch-target flex cursor-pointer items-center justify-between gap-3 rounded-xl border border-slate-800 bg-slate-900/70 px-3">
          <div class="space-y-0.5">
            <span class="text-sm font-medium text-slate-100">{{ t("stepPublish.codEnabled") }}</span>
            <p class="text-xs text-slate-500">{{ t("stepPublish.codEnabledHint") }}</p>
          </div>
          <input v-model="form.cod_enabled" type="checkbox" class="h-4 w-4 shrink-0 rounded border-slate-600 bg-slate-900 text-brand-secondary" />
        </label>
        <div v-if="form.cod_enabled" class="space-y-1.5 rounded-xl border border-slate-800 bg-slate-950/45 px-3 py-3">
          <label for="sp-cod-min-orders" class="text-xs font-medium text-slate-300">{{ t("stepPublish.codMinOrders") }}</label>
          <div class="flex items-center gap-2">
            <input
              id="sp-cod-min-orders"
              v-model.number="form.cod_min_paid_orders"
              type="number"
              min="1"
              max="100"
              :aria-label="t('stepPublish.codMinOrders')"
              class="w-24 ui-input tabular-nums"
            />
            <span class="text-xs text-slate-500">{{ t("stepPublish.codMinOrdersUnit") }}</span>
          </div>
        </div>

        <!-- Auto-confirm reservations -->
        <label class="ui-touch-target flex cursor-pointer items-center justify-between gap-3 rounded-xl border border-slate-800 bg-slate-900/70 px-3">
          <div class="space-y-0.5">
            <span class="text-sm font-medium text-slate-100">{{ t("stepPublish.autoConfirmReservations") }}</span>
            <p class="text-xs text-slate-500">{{ t("stepPublish.autoConfirmReservationsHint") }}</p>
          </div>
          <input v-model="form.auto_confirm_reservations" type="checkbox" class="h-4 w-4 shrink-0 rounded border-slate-600 bg-slate-900 text-brand-secondary" />
        </label>
        <div v-if="form.auto_confirm_reservations" class="space-y-1.5 rounded-xl border border-slate-800 bg-slate-950/45 px-3 py-3">
          <label for="sp-auto-confirm-min-hours" class="text-xs font-medium text-slate-300">{{ t("stepPublish.autoConfirmMinHours") }}</label>
          <div class="flex items-center gap-2">
            <input
              id="sp-auto-confirm-min-hours"
              v-model.number="form.auto_confirm_min_hours"
              type="number"
              min="0"
              max="168"
              :aria-label="t('stepPublish.autoConfirmMinHours')"
              class="w-24 ui-input tabular-nums"
            />
            <span class="text-xs text-slate-500">{{ t("stepPublish.autoConfirmMinHoursUnit") }}</span>
          </div>
          <p class="text-xs text-slate-500">{{ t("stepPublish.autoConfirmMinHoursHint") }}</p>
        </div>

        <!-- Reservation reminders -->
        <label class="ui-touch-target flex cursor-pointer items-center justify-between gap-3 rounded-xl border border-slate-800 bg-slate-900/70 px-3">
          <div class="space-y-0.5">
            <span class="text-sm font-medium text-slate-100">{{ t("stepPublish.reservationReminders") }}</span>
            <p class="text-xs text-slate-500">{{ t("stepPublish.reservationRemindersHint") }}</p>
          </div>
          <input v-model="form.reservation_reminders_enabled" type="checkbox" class="h-4 w-4 shrink-0 rounded border-slate-600 bg-slate-900 text-brand-secondary" />
        </label>

        <!-- Delivery settings -->
        <div class="space-y-3 rounded-xl border border-slate-800 bg-slate-950/45 p-3">
          <div class="space-y-0.5">
            <p class="ui-section-kicker">{{ t("stepPublish.deliverySettings") }}</p>
            <p class="text-xs text-slate-500">{{ t("stepPublish.deliverySettingsHint") }}</p>
          </div>

          <label class="ui-touch-target flex cursor-pointer items-center justify-between gap-3 rounded-xl border border-slate-800 bg-slate-900/70 px-3">
            <div class="space-y-0.5 min-w-0">
              <span class="text-sm font-medium text-slate-200">{{ t("stepPublish.deliveryEnabled") }}</span>
              <p class="text-xs text-slate-500">{{ t("stepPublish.deliveryEnabledHint") }}</p>
            </div>
            <input v-model="form.delivery_enabled" type="checkbox" class="h-4 w-4 shrink-0 rounded border-slate-600 bg-slate-900 text-brand-secondary" />
          </label>

          <template v-if="form.delivery_enabled">
            <div class="grid gap-3 sm:grid-cols-2">
              <div class="space-y-1">
                <label for="sp-delivery-fee" class="text-xs font-medium text-slate-300">{{ t("stepPublish.deliveryFee") }}</label>
                <p class="text-[11px] text-slate-500">{{ t("stepPublish.deliveryFeeHint") }}</p>
                <input
                  id="sp-delivery-fee"
                  v-model.number="form.delivery_fee"
                  type="number"
                  min="0"
                  step="0.01"
                  :aria-label="t('stepPublish.deliveryFee')"
                  class="w-28 ui-input tabular-nums"
                />
              </div>

              <div class="space-y-1">
                <label for="sp-delivery-min-order" class="text-xs font-medium text-slate-300">{{ t("stepPublish.deliveryMinimumOrder") }}</label>
                <p class="text-[11px] text-slate-500">{{ t("stepPublish.deliveryMinimumOrderHint") }}</p>
                <input
                  id="sp-delivery-min-order"
                  v-model.number="form.delivery_minimum_order"
                  type="number"
                  min="0"
                  step="0.01"
                  :aria-label="t('stepPublish.deliveryMinimumOrder')"
                  class="w-28 ui-input tabular-nums"
                />
              </div>
            </div>

            <!-- Distance-based pricing (base + per-km). Per-km > 0 turns it on. -->
            <div class="space-y-2.5 rounded-xl border border-slate-800 bg-slate-900/40 p-3">
              <div class="space-y-0.5">
                <p class="text-sm font-medium text-slate-200">{{ t("stepPublish.distancePricingTitle") }}</p>
                <p class="text-[11px] text-slate-500">{{ t("stepPublish.distancePricingHint") }}</p>
              </div>
              <div class="grid gap-3 sm:grid-cols-2">
                <div class="space-y-1">
                  <label for="sp-delivery-base-fee" class="text-xs font-medium text-slate-300">{{ t("stepPublish.deliveryBaseFee") }}</label>
                  <input
                    id="sp-delivery-base-fee"
                    v-model.number="form.delivery_base_fee"
                    type="number" min="0" step="0.01"
                    :aria-label="t('stepPublish.deliveryBaseFee')"
                    class="w-28 ui-input tabular-nums"
                  />
                </div>
                <div class="space-y-1">
                  <label for="sp-delivery-per-km" class="text-xs font-medium text-slate-300">{{ t("stepPublish.deliveryPerKm") }}</label>
                  <input
                    id="sp-delivery-per-km"
                    v-model.number="form.delivery_per_km"
                    type="number" min="0" step="0.01"
                    :aria-label="t('stepPublish.deliveryPerKm')"
                    class="w-28 ui-input tabular-nums"
                  />
                </div>
                <div class="space-y-1">
                  <label for="sp-delivery-radius-km" class="text-xs font-medium text-slate-300">{{ t("stepPublish.deliveryRadiusKm") }}</label>
                  <input
                    id="sp-delivery-radius-km"
                    v-model.number="form.delivery_radius_km"
                    type="number" min="0" step="0.5"
                    :aria-label="t('stepPublish.deliveryRadiusKm')"
                    class="w-28 ui-input tabular-nums"
                  />
                </div>
                <div class="space-y-1">
                  <label for="sp-delivery-free-over" class="text-xs font-medium text-slate-300">{{ t("stepPublish.deliveryFreeOver") }}</label>
                  <input
                    id="sp-delivery-free-over"
                    v-model.number="form.delivery_free_over"
                    type="number" min="0" step="0.01"
                    :aria-label="t('stepPublish.deliveryFreeOver')"
                    class="w-28 ui-input tabular-nums"
                  />
                </div>
              </div>
              <p class="text-[11px] text-slate-500">{{ t("stepPublish.distancePricingExample") }}</p>
              <p
                v-if="Number(form.delivery_per_km) > 0 && !Number(form.delivery_base_fee) && !Number(form.delivery_fee)"
                class="text-[11px] text-amber-400"
              >{{ t("stepPublish.distancePricingZeroWarn") }}</p>
            </div>

            <div class="space-y-1">
              <label for="sp-delivery-zone-desc" class="text-xs font-medium text-slate-300">{{ t("stepPublish.deliveryZoneDescription") }}</label>
              <p class="text-[11px] text-slate-500">{{ t("stepPublish.deliveryZoneDescriptionHint") }}</p>
              <input
                id="sp-delivery-zone-desc"
                v-model="form.delivery_zone_description"
                type="text"
                maxlength="200"
                :aria-label="t('stepPublish.deliveryZoneDescription')"
                :placeholder="t('stepPublish.deliveryZoneDescriptionPlaceholder')"
                class="w-full ui-input"
              />
              <p class="text-end text-[11px] text-slate-600 tabular-nums">{{ (form.delivery_zone_description || "").length }}/200</p>
            </div>

            <label class="ui-touch-target flex cursor-pointer items-center justify-between gap-3 rounded-xl border-t border-slate-800 px-0 pt-3">
              <div class="space-y-0.5 min-w-0">
                <span class="text-sm font-medium text-slate-200">{{ t("stepPublish.platformDelivery") }}</span>
                <p class="text-xs text-slate-500">{{ t("stepPublish.platformDeliveryHint") }}</p>
              </div>
              <input v-model="form.platform_delivery_enabled" type="checkbox" class="h-4 w-4 shrink-0 rounded border-slate-600 bg-slate-900 text-brand-secondary" />
            </label>
          </template>
        </div>

        <!-- Reservation capacity settings -->
        <div class="space-y-3 rounded-xl border border-slate-800 bg-slate-950/45 p-3">
          <div class="space-y-0.5">
            <p class="ui-section-kicker">{{ t("stepPublish.capacitySettings") }}</p>
            <p class="text-xs text-slate-500">{{ t("stepPublish.capacitySettingsHint") }}</p>
          </div>

          <div class="grid gap-3 sm:grid-cols-2">
            <div class="space-y-1">
              <label for="sp-max-covers" class="text-xs font-medium text-slate-300">{{ t("stepPublish.maxCoversPerSlot") }}</label>
              <p class="text-[11px] text-slate-500">{{ t("stepPublish.maxCoversPerSlotHint") }}</p>
              <input
                id="sp-max-covers"
                v-model.number="form.max_covers_per_slot"
                type="number"
                min="0"
                step="1"
                :aria-label="t('stepPublish.maxCoversPerSlot')"
                class="w-full ui-input tabular-nums"
              />
            </div>
            <div class="space-y-1">
              <label for="sp-slot-duration" class="text-xs font-medium text-slate-300">{{ t("stepPublish.slotDuration") }}</label>
              <p class="text-[11px] text-slate-500">{{ t("stepPublish.slotDurationHint") }}</p>
              <select
                id="sp-slot-duration"
                v-model.number="form.slot_duration_minutes"
                :aria-label="t('stepPublish.slotDuration')"
                class="w-full ui-input"
              >
                <option :value="30">30 {{ t("stepPublish.minuteUnit") }}</option>
                <option :value="60">1 {{ t("stepPublish.hour") }}</option>
                <option :value="90">1.5 {{ t("stepPublish.hours") }}</option>
                <option :value="120">2 {{ t("stepPublish.hours") }}</option>
              </select>
            </div>
          </div>
        </div>

        <div class="flex flex-wrap gap-3">
          <button
            class="ui-btn-outline ui-press disabled:opacity-60"
            :disabled="savingStatus"
            @click="saveStatus"
          >
            {{ savingStatus ? t("stepPublish.savingStatus") : t("stepPublish.saveStatus") }}
          </button>
        </div>
      </div>
    </section>

    <!-- Platform directory -->
    <section :class="sectionPanelClass" class="ui-reveal" :style="{ '--ui-delay': '84ms' }">
      <div class="space-y-1">
        <p class="ui-section-kicker">{{ t("stepPublish.directoryControls") }}</p>
        <h3 class="text-lg font-semibold text-white leading-tight">{{ t("stepPublish.directoryTitle") }}</h3>
        <p class="ui-subtle">{{ t("stepPublish.directoryHint") }}</p>
      </div>
      <div class="space-y-3 rounded-xl border border-slate-800 bg-slate-950/45 p-3">
        <!-- Opt-in toggle -->
        <label class="ui-touch-target flex cursor-pointer items-center justify-between gap-3 rounded-xl border border-slate-800 bg-slate-900/70 px-3">
          <div class="space-y-0.5">
            <p class="text-sm font-medium text-slate-100">{{ t("stepPublish.directoryOptIn") }}</p>
          </div>
          <input v-model="form.directory_opt_in" type="checkbox" class="h-4 w-4 shrink-0 rounded border-slate-600 bg-slate-900 text-brand-secondary" />
        </label>

        <template v-if="form.directory_opt_in">
          <div class="grid gap-3 sm:grid-cols-2">
            <div class="space-y-1">
              <label for="sp-cuisine-type" class="text-xs font-medium text-slate-300">{{ t("stepPublish.cuisineType") }}</label>
              <input
                id="sp-cuisine-type"
                v-model="form.cuisine_type"
                type="text"
                maxlength="60"
                :aria-label="t('stepPublish.cuisineType')"
                :placeholder="t('stepPublish.cuisineTypePlaceholder')"
                class="w-full ui-input"
              />
            </div>
            <div class="space-y-1">
              <label for="sp-city" class="text-xs font-medium text-slate-300">{{ t("stepPublish.cityLabel") }}</label>
              <input
                id="sp-city"
                v-model="form.city"
                type="text"
                maxlength="80"
                :aria-label="t('stepPublish.cityLabel')"
                :placeholder="t('stepPublish.cityPlaceholder')"
                class="w-full ui-input"
              />
            </div>
          </div>

          <!-- Price tier -->
          <div class="space-y-1.5">
            <p class="text-xs font-medium text-slate-300">{{ t("stepPublish.priceTierLabel") }}</p>
            <p class="text-[11px] text-slate-500">{{ t("stepPublish.priceTierHint") }}</p>
            <div class="flex gap-2">
              <button
                v-for="tier in [1, 2, 3]"
                :key="tier"
                type="button"
                class="ui-touch-target rounded-full border px-4 text-sm font-semibold transition-colors"
                :class="form.price_tier === tier
                  ? 'border-[var(--color-secondary)] bg-[var(--color-secondary)]/10 text-[var(--color-secondary)]'
                  : 'border-slate-700 text-slate-300 hover:border-slate-500'"
                :aria-pressed="form.price_tier === tier"
                @click="form.price_tier = tier"
              >
                {{ '€'.repeat(tier) }}
              </button>
            </div>
          </div>

          <!-- Tags -->
          <div class="space-y-1.5">
            <p class="text-xs font-medium text-slate-300">{{ t("stepPublish.tagsLabel") }}</p>
            <p class="text-[11px] text-slate-500">{{ t("stepPublish.tagsHint") }}</p>
            <div class="flex flex-wrap gap-2">
              <label
                v-for="tag in MARKETPLACE_TAGS"
                :key="tag"
                class="flex cursor-pointer items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition-colors has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-[var(--color-secondary)]/60 has-[:focus-visible]:outline-none"
                :class="form.tags.includes(tag)
                  ? 'border-[var(--color-secondary)]/60 bg-[var(--color-secondary)]/10 text-[var(--color-secondary)]'
                  : 'border-slate-700 text-slate-400 hover:border-slate-500'"
              >
                <input
                  type="checkbox"
                  class="sr-only"
                  :checked="form.tags.includes(tag)"
                  @change="toggleTag(tag)"
                />
                {{ tag }}
              </label>
            </div>
          </div>

          <!-- Location -->
          <div class="space-y-2 rounded-xl border border-slate-800 bg-slate-950/40 p-3">
            <p class="text-xs font-medium text-slate-300">{{ t("stepPublish.locationTitle") }}</p>
            <p class="text-[11px] text-slate-500">{{ t("stepPublish.locationHint") }}</p>
            <button
              type="button"
              class="ui-btn-outline ui-press px-3 py-1 text-xs disabled:opacity-50"
              :disabled="gettingLocation"
              @click="useMyLocation"
            >
              <template v-if="gettingLocation">…</template>
              <template v-else><span aria-hidden="true">📍 </span>{{ t("stepPublish.useMyLocation") }}</template>
            </button>
            <div class="grid gap-2 sm:grid-cols-2">
              <div class="space-y-0.5">
                <label for="sp-lat" class="text-[10px] text-slate-500">{{ t("stepPublish.latLabel") }}</label>
                <input
                  id="sp-lat"
                  v-model.number="form.lat"
                  type="number"
                  step="0.0001"
                  :aria-label="t('stepPublish.latLabel')"
                  placeholder="e.g. 48.8566"
                  class="w-full ui-input tabular-nums"
                />
              </div>
              <div class="space-y-0.5">
                <label for="sp-lng" class="text-[10px] text-slate-500">{{ t("stepPublish.lngLabel") }}</label>
                <input
                  id="sp-lng"
                  v-model.number="form.lng"
                  type="number"
                  step="0.0001"
                  :aria-label="t('stepPublish.lngLabel')"
                  placeholder="e.g. 2.3522"
                  class="w-full ui-input tabular-nums"
                />
              </div>
            </div>
          </div>
        </template>
      </div>
      <div class="flex flex-wrap gap-3">
        <button
          class="ui-btn-outline ui-press disabled:opacity-60"
          :disabled="savingDirectory"
          @click="saveDirectory"
        >
          {{ savingDirectory ? t("stepPublish.savingStatus") : t("common.save") }}
        </button>
      </div>
    </section>

    <!-- Menu visual theme -->
    <section :class="sectionPanelClass" class="ui-reveal" :style="{ '--ui-delay': '112ms' }">
      <div class="space-y-1">
        <p class="ui-section-kicker">{{ t("stepPublish.menuThemeControls") }}</p>
        <h3 class="text-lg font-semibold text-white leading-tight">{{ t("stepPublish.menuThemeSectionTitle") }}</h3>
        <p class="ui-subtle">{{ t("stepPublish.menuThemeHint") }}</p>
      </div>

      <div class="grid grid-cols-3 gap-3">
        <button
          v-for="theme in MENU_THEMES"
          :key="theme.value"
          type="button"
          class="relative overflow-hidden rounded-2xl border p-0 transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/60"
          :class="form.menu_theme === theme.value
            ? 'border-[var(--color-secondary)] ring-2 ring-[var(--color-secondary)]/30'
            : 'border-slate-700 hover:border-slate-500'"
          :aria-pressed="form.menu_theme === theme.value"
          :aria-label="t(theme.labelKey)"
          @click="form.menu_theme = theme.value"
        >
          <!-- Swatch preview -->
          <div class="h-16 w-full" :style="{ background: theme.preview }"></div>
          <div class="space-y-0.5 px-3 py-2 text-start bg-slate-900/80">
            <p class="text-xs font-semibold text-slate-100">{{ t(theme.labelKey) }}</p>
          </div>
          <!-- Active checkmark -->
          <div
            v-if="form.menu_theme === theme.value"
            class="absolute end-2 top-2 flex h-5 w-5 items-center justify-center rounded-full bg-[var(--color-secondary)] text-slate-950"
            aria-hidden="true"
          >
            <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="h-3 w-3">
              <path d="M2 6l3 3 5-5" />
            </svg>
          </div>
        </button>
      </div>

      <div class="flex flex-wrap gap-3">
        <button
          class="ui-btn-outline ui-press disabled:opacity-60"
          :disabled="savingTheme"
          @click="saveTheme"
        >
          {{ savingTheme ? t("stepPublish.savingStatus") : t("stepPublish.saveTheme") }}
        </button>
      </div>
    </section>

    <!-- Menu card layout picker -->
    <section :class="sectionPanelClass" class="ui-reveal" :style="{ '--ui-delay': '140ms' }">
      <div class="space-y-1">
        <p class="ui-section-kicker">{{ t("stepPublish.cardLayoutControls") }}</p>
        <h3 class="text-lg font-semibold text-white leading-tight">{{ t("stepPublish.cardLayoutSectionTitle") }}</h3>
        <p class="ui-subtle">{{ t("stepPublish.cardLayoutHint") }}</p>
      </div>

      <div class="grid grid-cols-3 gap-3">
        <button
          v-for="layout in CARD_LAYOUTS"
          :key="layout.value"
          type="button"
          class="relative overflow-hidden rounded-2xl border p-0 transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/60"
          :class="form.menu_card_layout === layout.value
            ? 'border-[var(--color-secondary)] ring-2 ring-[var(--color-secondary)]/30'
            : 'border-slate-700 hover:border-slate-500'"
          :aria-pressed="form.menu_card_layout === layout.value"
          :aria-label="t(layout.labelKey)"
          @click="form.menu_card_layout = layout.value"
        >
          <!-- Visual preview mockup -->
          <div class="h-16 w-full overflow-hidden bg-slate-950/60" :style="{ background: layout.preview }"></div>
          <div class="space-y-0.5 bg-slate-900/80 px-3 py-2 text-start">
            <p class="text-xs font-semibold text-slate-100">{{ t(layout.labelKey) }}</p>
          </div>
          <div
            v-if="form.menu_card_layout === layout.value"
            class="absolute end-2 top-2 flex h-5 w-5 items-center justify-center rounded-full bg-[var(--color-secondary)] text-slate-950"
            aria-hidden="true"
          >
            <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="h-3 w-3">
              <path d="M2 6l3 3 5-5" />
            </svg>
          </div>
        </button>
      </div>

      <div class="flex flex-wrap gap-3">
        <button
          class="ui-btn-outline ui-press disabled:opacity-60"
          :disabled="savingTheme"
          @click="saveCardLayout"
        >
          {{ savingTheme ? t("stepPublish.savingStatus") : t("stepPublish.saveCardLayout") }}
        </button>
      </div>
    </section>

    <!-- Closure dates / holiday closures -->
    <section :class="sectionPanelClass" class="ui-reveal" :style="{ '--ui-delay': '168ms' }">
      <div class="space-y-1">
        <p class="ui-section-kicker">{{ t("stepPublish.closureDatesControls") }}</p>
        <h3 class="text-lg font-semibold text-white leading-tight">{{ t("stepPublish.closureDatesSectionTitle") }}</h3>
        <p class="ui-subtle">{{ t("stepPublish.closureDatesHint") }}</p>
      </div>
      <ClosureDates />
    </section>

    <section :class="sectionPanelClass" class="ui-reveal" :style="{ '--ui-delay': '196ms' }">
      <div class="space-y-1">
        <p class="ui-section-kicker">{{ t("stepPublish.publishActions") }}</p>
        <h3 class="text-lg font-semibold text-white leading-tight">{{ t("stepPublish.publishSectionTitle") }}</h3>
      </div>

      <div v-if="!canAttemptPublish" role="alert" class="flex items-start gap-2 rounded-xl border border-amber-500/30 bg-amber-500/8 px-3 py-2.5">
        <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-amber-400" fill="currentColor"><path fill-rule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
        <p class="flex-1 text-xs text-amber-200">{{ t("stepPublish.publishRequirement") }}</p>
      </div>
      <div v-if="errors.is_menu_published" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
        <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
        <p class="flex-1 text-sm text-red-300">{{ errors.is_menu_published }}</p>
      </div>
      <div v-if="errors.non_field_errors" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
        <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
        <p class="flex-1 text-sm text-red-300">{{ errors.non_field_errors }}</p>
      </div>

      <div class="grid gap-2 sm:flex sm:flex-wrap">
        <button
          class="ui-btn-primary w-full justify-center sm:w-auto disabled:opacity-60"
          :disabled="publishing || !canAttemptPublish"
          @click="publish"
        >
          {{ publishing ? t("stepPublish.publishing") : published ? t("stepPublish.published") : t("stepPublish.publishMenu") }}
        </button>
        <button class="ui-btn-outline w-full justify-center sm:w-auto disabled:opacity-60" :disabled="loadingChecks" @click="refreshChecks">
          {{ loadingChecks ? t("stepPublish.refreshingChecks") : t("stepPublish.refreshChecks") }}
        </button>
        <RouterLink v-if="published" to="/owner/launch" class="ui-btn-outline w-full justify-center sm:w-auto">
          {{ t("stepPublish.launchSummary") }}
        </RouterLink>
        <RouterLink to="/menu" class="ui-btn-outline w-full justify-center sm:w-auto">{{ t("stepPublish.previewMenu") }}</RouterLink>
        <button class="ui-btn-outline w-full justify-center sm:w-auto" @click="copyMenuUrl">{{ t("stepPublish.copyMenuUrl") }}</button>
        <RouterLink to="/" class="ui-btn-outline w-full justify-center sm:w-auto">{{ t("stepPublish.backToLanding") }}</RouterLink>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useToastStore } from "../stores/toast";
import { categoryApi, dishApi, profileApi } from "../lib/onboardingApi";
import { useI18n } from "../composables/useI18n";
import { useTenantStore } from "../stores/tenant";
import { trackEvent } from "../lib/analytics";
import ClosureDates from "../components/ClosureDates.vue";

const props = defineProps({
  standalone: {
    type: Boolean,
    default: false,
  },
});
const emit = defineEmits(["publish"]);
const toast = useToastStore();
const tenant = useTenantStore();
const { t, formatDateTime } = useI18n();
const publishing = ref(false);
const savingStatus = ref(false);
const savingTheme = ref(false);
const loadingChecks = ref(false);
const published = ref(false);
const publishedAt = ref(null);
const profileSnapshot = ref({});
const categoriesCount = ref(0);
const dishesCount = ref(0);

const MENU_THEMES = [
  {
    value: "dark",
    labelKey: "stepPublish.menuThemeDark",
    preview: "linear-gradient(135deg, #060b12 0%, #0d1722 50%, #0f1d2b 100%)",
  },
  {
    value: "light",
    labelKey: "stepPublish.menuThemeLight",
    preview: "linear-gradient(135deg, #f0f4f8 0%, #e2e8f0 50%, #f8fafc 100%)",
  },
  {
    value: "warm",
    labelKey: "stepPublish.menuThemeWarm",
    preview: "linear-gradient(135deg, #fdf6ef 0%, #fef3e2 50%, #fdf8f2 100%)",
  },
];

const CARD_LAYOUTS = [
  {
    value: "row",
    labelKey: "stepPublish.cardLayoutRow",
    // Mockup: text bars left, image square right
    preview: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='64'%3E%3Crect width='120' height='64' fill='%230d1722'/%3E%3Crect x='8' y='10' width='64' height='6' rx='3' fill='%23334155'/%3E%3Crect x='8' y='22' width='48' height='4' rx='2' fill='%231e293b'/%3E%3Crect x='8' y='32' width='36' height='4' rx='2' fill='%231e293b'/%3E%3Crect x='8' y='46' width='28' height='6' rx='3' fill='%23f59e0b' opacity='.7'/%3E%3Crect x='84' y='8' width='28' height='28' rx='4' fill='%23334155'/%3E%3Ccircle cx='112' cy='44' r='8' fill='%23f59e0b'/%3E%3C/svg%3E")`,
  },
  {
    value: "card",
    labelKey: "stepPublish.cardLayoutCard",
    // Mockup: full-width image top, text + button below
    preview: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='64'%3E%3Crect width='120' height='64' fill='%230d1722'/%3E%3Crect width='120' height='30' rx='0' fill='%23334155'/%3E%3Crect x='6' y='35' width='60' height='5' rx='2' fill='%23475569'/%3E%3Crect x='6' y='44' width='44' height='4' rx='2' fill='%231e293b'/%3E%3Crect x='6' y='53' width='108' height='7' rx='3' fill='%23f59e0b' opacity='.7'/%3E%3C/svg%3E")`,
  },
  {
    value: "compact",
    labelKey: "stepPublish.cardLayoutCompact",
    // Mockup: three single-line rows
    preview: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='64'%3E%3Crect width='120' height='64' fill='%230d1722'/%3E%3Crect x='6' y='8' width='120' height='14' rx='3' fill='%231e293b'/%3E%3Crect x='10' y='12' width='52' height='5' rx='2' fill='%23334155'/%3E%3Ccircle cx='108' cy='15' r='7' fill='%23f59e0b' opacity='.7'/%3E%3Crect x='6' y='26' width='120' height='14' rx='3' fill='%231e293b'/%3E%3Crect x='10' y='30' width='44' height='5' rx='2' fill='%23334155'/%3E%3Ccircle cx='108' cy='33' r='7' fill='%23f59e0b' opacity='.7'/%3E%3Crect x='6' y='44' width='120' height='14' rx='3' fill='%231e293b'/%3E%3Crect x='10' y='48' width='58' height='5' rx='2' fill='%23334155'/%3E%3Ccircle cx='108' cy='51' r='7' fill='%23f59e0b' opacity='.7'/%3E%3C/svg%3E")`,
  },
];

const MARKETPLACE_TAGS = [
  "Vegetarian", "Vegan", "Halal", "Kosher",
  "Gluten-Free", "Seafood", "BBQ", "Pizza", "Burgers", "Sushi",
];

const gettingLocation = ref(false);

const form = reactive({
  is_open: true,
  is_menu_temporarily_disabled: false,
  menu_disabled_note: "",
  receipt_message: "",
  menu_theme: "dark",
  sms_notifications_enabled: false,
  cod_enabled: false,
  cod_min_paid_orders: 3,
  auto_confirm_reservations: false,
  auto_confirm_min_hours: 24,
  reservation_reminders_enabled: false,
  menu_card_layout: "row",
  delivery_enabled: true,
  delivery_fee: 0,
  delivery_base_fee: 0,
  delivery_per_km: 0,
  delivery_free_over: 0,
  delivery_radius_km: null,
  delivery_minimum_order: 0,
  delivery_zone_description: "",
  platform_delivery_enabled: false,
  max_covers_per_slot: 0,
  slot_duration_minutes: 60,
  directory_opt_in: false,
  cuisine_type: "",
  city: "",
  lat: null,
  lng: null,
  price_tier: 2,
  tags: [],
});
const savingDirectory = ref(false);
const errors = reactive({});

const menuUrl = computed(() => {
  if (typeof window === "undefined") return "/menu";
  return `${window.location.origin}/menu`;
});

const formattedPublishedAt = computed(() => {
  if (!publishedAt.value) return "";
  return formatDateTime(publishedAt.value);
});
const canCheckout = computed(() => tenant.entitlements?.can_checkout === true);
const canWhatsappOrder = computed(() => tenant.entitlements?.can_whatsapp_order === true);
const isBrowseOnlyPlan = computed(() => tenant.isBrowseOnlyPlan === true);
const sectionPanelClass = computed(() => "ui-panel space-y-4 p-5");

const checks = computed(() => {
  const p = profileSnapshot.value || {};
  const hasContact = Boolean((p.phone || "").trim() || (p.whatsapp || "").trim());
  const hasBrand = Boolean((p.tagline || "").trim() || hasContact);
  const hasTheme = Boolean((p.logo_url || "").trim() || (p.hero_url || "").trim() || p.primary_color || p.secondary_color);
  const items = [
    { key: "brand", label: t("stepPublish.checkBrandContact"), ok: hasBrand },
    { key: "categories", label: t("stepPublish.checkCategories", { count: categoriesCount.value }), ok: categoriesCount.value > 0 },
    { key: "dishes", label: t("stepPublish.checkDishes", { count: dishesCount.value }), ok: dishesCount.value > 0 },
    { key: "theme", label: t("stepPublish.checkTheme"), ok: hasTheme },
  ];
  if (isBrowseOnlyPlan.value) {
    items.push({ key: "plan_mode", label: t("stepPublish.checkPlanBrowseOnly"), ok: true });
  } else if (canCheckout.value || canWhatsappOrder.value) {
    items.push({ key: "plan_mode", label: t("stepPublish.checkPlanOrdering"), ok: true });
  }
  return items;
});

const canAttemptPublish = computed(() => categoriesCount.value > 0 && dishesCount.value > 0);
const standalone = computed(() => props.standalone);

const clearErrors = () => {
  Object.keys(errors).forEach((key) => delete errors[key]);
};
const clearError = (key) => {
  if (errors[key]) delete errors[key];
};

const load = async () => {
  try {
    const data = await profileApi.get();
    profileSnapshot.value = data || {};
    published.value = data?.is_menu_published === true;
    publishedAt.value = data?.published_at || null;
    form.is_open = data?.is_open !== false;
    form.is_menu_temporarily_disabled = data?.is_menu_temporarily_disabled === true;
    form.menu_disabled_note = data?.menu_disabled_note || "";
    form.receipt_message = data?.receipt_message || "";
    form.menu_theme = data?.menu_theme || "dark";
    form.sms_notifications_enabled = data?.sms_notifications_enabled === true;
    form.cod_enabled = data?.cod_enabled === true;
    form.cod_min_paid_orders = Number(data?.cod_min_paid_orders ?? 3) || 3;
    form.auto_confirm_reservations = data?.auto_confirm_reservations === true;
    form.auto_confirm_min_hours = Number(data?.auto_confirm_min_hours ?? 24) || 24;
    form.reservation_reminders_enabled = data?.reservation_reminders_enabled === true;
    form.menu_card_layout = data?.menu_card_layout || "row";
    form.delivery_enabled = data?.delivery_enabled !== false;
    form.delivery_fee = Number(data?.delivery_fee ?? 0);
    form.delivery_base_fee = Number(data?.delivery_base_fee ?? 0);
    form.delivery_per_km = Number(data?.delivery_per_km ?? 0);
    form.delivery_free_over = Number(data?.delivery_free_over ?? 0);
    form.delivery_radius_km = data?.delivery_radius_km ?? null;
    form.delivery_minimum_order = Number(data?.delivery_minimum_order ?? 0);
    form.delivery_zone_description = data?.delivery_zone_description || "";
    form.platform_delivery_enabled = Boolean(data?.platform_delivery_enabled);
    form.max_covers_per_slot = Number(data?.max_covers_per_slot ?? 0);
    form.slot_duration_minutes = Number(data?.slot_duration_minutes ?? 60) || 60;
    form.directory_opt_in = Boolean(data?.directory_opt_in);
    form.cuisine_type = data?.cuisine_type || "";
    form.city = data?.city || "";
    form.lat = data?.lat ?? null;
    form.lng = data?.lng ?? null;
    form.price_tier = Number(data?.price_tier ?? 2) || 2;
    form.tags = Array.isArray(data?.tags) ? [...data.tags] : [];
  } catch {
    // keep default state
  }
};

const refreshChecks = async () => {
  loadingChecks.value = true;
  try {
    const [profile, categories, dishes] = await Promise.all([
      profileApi.get(),
      categoryApi.list(),
      dishApi.list(),
    ]);
    profileSnapshot.value = profile || {};
    categoriesCount.value = Array.isArray(categories) ? categories.length : 0;
    dishesCount.value = Array.isArray(dishes) ? dishes.length : 0;
  } catch {
    toast.show(t("stepPublish.refreshChecksFailed"), "error");
  } finally {
    loadingChecks.value = false;
  }
};

const saveProfile = async (publishFlag = null) => {
  const current = await profileApi.get();
  const payload = {
    ...(current || {}),
    is_open: form.is_open,
    is_menu_temporarily_disabled: form.is_menu_temporarily_disabled,
    menu_disabled_note: form.menu_disabled_note,
    receipt_message: form.receipt_message,
    menu_theme: form.menu_theme,
    sms_notifications_enabled: form.sms_notifications_enabled,
    cod_enabled: Boolean(form.cod_enabled),
    cod_min_paid_orders: Math.max(1, Number(form.cod_min_paid_orders) || 3),
    auto_confirm_reservations: form.auto_confirm_reservations,
    auto_confirm_min_hours: Number(form.auto_confirm_min_hours) || 24,
    reservation_reminders_enabled: form.reservation_reminders_enabled,
    menu_card_layout: form.menu_card_layout,
    delivery_enabled: form.delivery_enabled,
    delivery_fee: Number(form.delivery_fee) || 0,
    delivery_base_fee: Number(form.delivery_base_fee) || 0,
    delivery_per_km: Number(form.delivery_per_km) || 0,
    delivery_free_over: Number(form.delivery_free_over) || 0,
    delivery_radius_km:
      form.delivery_radius_km === null || form.delivery_radius_km === ""
        ? null
        : Number(form.delivery_radius_km),
    delivery_minimum_order: Number(form.delivery_minimum_order) || 0,
    delivery_zone_description: form.delivery_zone_description || "",
    platform_delivery_enabled: Boolean(form.platform_delivery_enabled),
    max_covers_per_slot: Number(form.max_covers_per_slot) || 0,
    slot_duration_minutes: Number(form.slot_duration_minutes) || 60,
  };
  if (publishFlag !== null) payload.is_menu_published = publishFlag;
  return profileApi.save(payload);
};

const saveStatus = async () => {
  savingStatus.value = true;
  clearErrors();
  try {
    const saved = await saveProfile(null);
    profileSnapshot.value = saved || {};
    form.is_open = saved?.is_open !== false;
    form.is_menu_temporarily_disabled = saved?.is_menu_temporarily_disabled === true;
    form.menu_disabled_note = saved?.menu_disabled_note || "";
    form.receipt_message = saved?.receipt_message || "";
    form.menu_theme = saved?.menu_theme || "dark";
    form.sms_notifications_enabled = saved?.sms_notifications_enabled === true;
    form.auto_confirm_reservations = saved?.auto_confirm_reservations === true;
    form.auto_confirm_min_hours = Number(saved?.auto_confirm_min_hours ?? 24) || 24;
    form.reservation_reminders_enabled = saved?.reservation_reminders_enabled === true;
    form.menu_card_layout = saved?.menu_card_layout || "row";
    form.delivery_enabled = saved?.delivery_enabled !== false;
    form.delivery_fee = Number(saved?.delivery_fee ?? 0);
    form.delivery_base_fee = Number(saved?.delivery_base_fee ?? 0);
    form.delivery_per_km = Number(saved?.delivery_per_km ?? 0);
    form.delivery_free_over = Number(saved?.delivery_free_over ?? 0);
    form.delivery_radius_km = saved?.delivery_radius_km ?? null;
    form.delivery_minimum_order = Number(saved?.delivery_minimum_order ?? 0);
    form.delivery_zone_description = saved?.delivery_zone_description || "";
    form.platform_delivery_enabled = Boolean(saved?.platform_delivery_enabled);
    form.max_covers_per_slot = Number(saved?.max_covers_per_slot ?? 0);
    form.slot_duration_minutes = Number(saved?.slot_duration_minutes ?? 60) || 60;
    await tenant.fetchMeta();
    toast.show(t("stepPublish.statusSaved"), "success");
  } catch (e) {
    Object.assign(errors, e?.fieldErrors || {});
    toast.show(e?.message || t("stepPublish.statusSaveFailed"), "error");
  } finally {
    savingStatus.value = false;
  }
};

const saveDirectory = async () => {
  savingDirectory.value = true;
  try {
    const saved = await profileApi.save({
      directory_opt_in: form.directory_opt_in,
      cuisine_type: form.cuisine_type.trim(),
      city: form.city.trim(),
      lat: form.lat || null,
      lng: form.lng || null,
      price_tier: form.price_tier,
      tags: form.tags,
    });
    form.directory_opt_in = Boolean(saved?.directory_opt_in);
    form.cuisine_type = saved?.cuisine_type || "";
    form.city = saved?.city || "";
    form.lat = saved?.lat ?? null;
    form.lng = saved?.lng ?? null;
    form.price_tier = Number(saved?.price_tier ?? 2) || 2;
    form.tags = Array.isArray(saved?.tags) ? [...saved.tags] : [];
    toast.show(t("stepPublish.directorySaved"), "success");
  } catch {
    toast.show(t("stepPublish.directorySaveFailed"), "error");
  } finally {
    savingDirectory.value = false;
  }
};

const toggleTag = (tag) => {
  const idx = form.tags.indexOf(tag);
  if (idx >= 0) {
    form.tags.splice(idx, 1);
  } else {
    form.tags.push(tag);
  }
};

const useMyLocation = () => {
  if (!navigator.geolocation) return;
  gettingLocation.value = true;
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      form.lat = Math.round(pos.coords.latitude * 10000) / 10000;
      form.lng = Math.round(pos.coords.longitude * 10000) / 10000;
      gettingLocation.value = false;
    },
    () => { gettingLocation.value = false; },
    { timeout: 8000 }
  );
};

const saveTheme = async () => {
  savingTheme.value = true;
  try {
    const current = await profileApi.get();
    const saved = await profileApi.save({ ...(current || {}), menu_theme: form.menu_theme });
    form.menu_theme = saved?.menu_theme || "dark";
    await tenant.fetchMeta();
    toast.show(t("stepPublish.themeSaved"), "success");
  } catch (e) {
    toast.show(e?.message || t("stepPublish.themeSaveFailed"), "error");
  } finally {
    savingTheme.value = false;
  }
};

const saveCardLayout = async () => {
  savingTheme.value = true;  // reuse the loading flag
  try {
    const current = await profileApi.get();
    const saved = await profileApi.save({ ...(current || {}), menu_card_layout: form.menu_card_layout });
    form.menu_card_layout = saved?.menu_card_layout || "row";
    await tenant.fetchMeta();
    toast.show(t("stepPublish.cardLayoutSaved"), "success");
  } catch (e) {
    toast.show(e?.message || t("stepPublish.cardLayoutSaveFailed"), "error");
  } finally {
    savingTheme.value = false;
  }
};

const publish = async () => {
  publishing.value = true;
  clearErrors();
  try {
    const saved = await saveProfile(true);
    profileSnapshot.value = saved || {};
    published.value = saved?.is_menu_published === true;
    publishedAt.value = saved?.published_at || null;
    form.is_open = saved?.is_open !== false;
    form.is_menu_temporarily_disabled = saved?.is_menu_temporarily_disabled === true;
    form.menu_disabled_note = saved?.menu_disabled_note || "";
    form.receipt_message = saved?.receipt_message || "";
    form.menu_theme = saved?.menu_theme || "dark";
    form.sms_notifications_enabled = saved?.sms_notifications_enabled === true;
    form.auto_confirm_reservations = saved?.auto_confirm_reservations === true;
    form.auto_confirm_min_hours = Number(saved?.auto_confirm_min_hours ?? 24) || 24;
    form.reservation_reminders_enabled = saved?.reservation_reminders_enabled === true;
    form.menu_card_layout = saved?.menu_card_layout || "row";
    form.delivery_enabled = saved?.delivery_enabled !== false;
    form.delivery_fee = Number(saved?.delivery_fee ?? 0);
    form.delivery_base_fee = Number(saved?.delivery_base_fee ?? 0);
    form.delivery_per_km = Number(saved?.delivery_per_km ?? 0);
    form.delivery_free_over = Number(saved?.delivery_free_over ?? 0);
    form.delivery_radius_km = saved?.delivery_radius_km ?? null;
    form.delivery_minimum_order = Number(saved?.delivery_minimum_order ?? 0);
    form.delivery_zone_description = saved?.delivery_zone_description || "";
    form.platform_delivery_enabled = Boolean(saved?.platform_delivery_enabled);
    form.max_covers_per_slot = Number(saved?.max_covers_per_slot ?? 0);
    form.slot_duration_minutes = Number(saved?.slot_duration_minutes ?? 60) || 60;
    await tenant.fetchMeta();
    trackEvent("owner_publish", {
      source: "owner_wizard",
      metadata: {
        categories_count: categoriesCount.value,
        dishes_count: dishesCount.value,
      },
    });
    emit("publish");
    toast.show(t("stepPublish.publishedSuccess"), "success");
  } catch (e) {
    Object.assign(errors, e?.fieldErrors || {});
    toast.show(e?.message || t("stepPublish.publishFailed"), "error");
  } finally {
    publishing.value = false;
  }
};

const copyMenuUrl = async () => {
  try {
    await navigator.clipboard.writeText(menuUrl.value);
    toast.show(t("stepPublish.menuCopied"), "success");
  } catch {
    toast.show(t("stepPublish.copyFailed"), "error");
  }
};

onMounted(async () => {
  await load();
  await refreshChecks();
});
</script>
