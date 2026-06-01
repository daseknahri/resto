<template>
  <div class="space-y-3 px-3 py-2 pb-28 sm:space-y-4 sm:px-4 sm:py-4 sm:pb-6 ui-safe-bottom">

    <!-- ── Header ──────────────────────────────────────────────────────────── -->
    <header class="ui-hero-ribbon ui-reveal px-4 py-3.5 md:px-5 md:py-4">
      <div class="flex items-center justify-between gap-3">
        <div class="flex flex-wrap items-center gap-x-3 gap-y-1.5">
          <div>
            <p class="ui-kicker">{{ t('cartPage.kicker') }}</p>
            <h1 class="ui-display text-xl font-semibold tracking-tight text-white md:text-2xl leading-tight">
              {{ t('common.cart') }}
            </h1>
          </div>
          <div v-if="cart.items.length" class="flex items-center gap-1.5">
            <span class="ui-chip">{{ itemCountLabel(cart.count) }}</span>
            <span class="ui-chip">{{ planLabel }}</span>
            <span v-if="tableLabelModel" class="ui-chip">{{ t('cartPage.table', { table: tableLabelModel }) }}</span>
          </div>
        </div>
        <button
          v-if="cart.items.length"
          class="shrink-0 ui-btn-outline px-2.5 py-1.5 text-xs text-red-200 hover:border-red-400/50"
          @click="clearCart"
        >
          <AppIcon name="close" class="h-3.5 w-3.5" />
          {{ t('common.clear') }}
        </button>
      </div>
    </header>

    <!-- ── Browse-only notice ───────────────────────────────────────────────── -->
    <div
      v-if="isBrowseOnlyPlan"
      class="ui-section-band border-sky-500/40 bg-sky-500/10 px-4 py-3 text-sky-100 space-y-0.5"
    >
      <p class="text-sm font-semibold">{{ t('cartPage.orderingDisabled') }}</p>
      <p class="text-xs text-sky-200/75">{{ t('cartPage.browseOnlyBody') }}</p>
    </div>

    <!-- ── Empty state ──────────────────────────────────────────────────────── -->
    <div
      v-else-if="!cart.items.length"
      class="ui-section-band border-dashed border-slate-700 px-5 py-8 text-center space-y-1"
    >
      <p class="text-sm font-semibold text-slate-100">{{ t('cartPage.cartEmpty') }}</p>
      <p class="text-xs text-slate-400">{{ t('cartPage.cartEmptyBody') }}</p>
    </div>

    <!-- ── Main ─────────────────────────────────────────────────────────────── -->
    <div
      v-else
      class="grid gap-3 xl:grid-cols-[minmax(0,1.15fr),minmax(21rem,0.85fr)] xl:items-start"
    >

      <!-- ── Left: item list ─────────────────────────────────────────────── -->
      <div class="space-y-2">
        <article
          v-for="(item, index) in cart.items"
          :key="item.key"
          class="ui-panel ui-surface-lift ui-reveal relative overflow-hidden pl-4 pr-3.5 py-3"
          :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
        >
          <!-- left accent bar -->
          <div
            class="pointer-events-none absolute inset-y-0 left-0 w-[3px] rounded-l-xl"
            style="background: linear-gradient(to bottom, rgba(245,158,11,0.55), rgba(245,158,11,0.10))"
          />
          <div class="flex items-center gap-3">
            <!-- Name + meta -->
            <div class="min-w-0 flex-1">
              <p class="truncate text-sm font-semibold leading-snug text-slate-100">{{ item.name }}</p>
              <p v-if="item.note" class="mt-0.5 text-[11px] text-slate-500 truncate">{{ item.note }}</p>
              <p v-else-if="item.option_labels?.length" class="mt-0.5 text-[11px] text-slate-500 truncate">{{ item.option_labels.join(' · ') }}</p>
              <p class="mt-0.5 text-[11px] text-slate-500">{{ formatPrice(item.price) }} {{ t('cartPage.each') }}</p>
            </div>
            <!-- Stepper pill -->
            <div class="inline-flex shrink-0 items-center rounded-full border border-slate-700/60 bg-slate-900/60">
              <button
                class="h-7 w-7 flex items-center justify-center rounded-full text-slate-300 hover:bg-slate-800 transition-colors select-none"
                :aria-label="t('cartPage.decreaseQuantity')"
                @click="cart.decrement(item.key)"
              >
                <span class="text-base leading-none">−</span>
              </button>
              <span class="w-6 text-center text-xs font-semibold text-slate-100 select-none tabular-nums">{{ item.qty }}</span>
              <button
                class="h-7 w-7 flex items-center justify-center rounded-full text-slate-300 hover:bg-slate-800 transition-colors select-none"
                :aria-label="t('cartPage.increaseQuantity')"
                @click="cart.increment(item.key)"
              >
                <span class="text-base leading-none">+</span>
              </button>
            </div>
            <!-- Subtotal + remove -->
            <div class="shrink-0 min-w-[4rem] text-right">
              <p class="text-sm font-semibold tabular-nums text-[var(--color-secondary)]">{{ formatPrice(item.price * item.qty) }}</p>
              <button
                class="mt-0.5 text-[10px] text-slate-600 hover:text-red-400 transition-colors"
                @click="cart.remove(item.key)"
              >{{ t('cartPage.remove') }}</button>
            </div>
          </div>
        </article>

        <!-- Unavailable items warning -->
        <div
          v-if="unavailableSlugs.length"
          class="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-amber-500/40 bg-amber-500/10 px-3 py-2.5 text-xs text-amber-100"
        >
          <p class="min-w-0 flex-1">{{ t('cartPage.unavailableItemsDetected', { items: unavailableNames.join(', ') }) }}</p>
          <button class="shrink-0 ui-btn-outline px-2.5 py-1 text-xs" @click="removeUnavailable">
            <AppIcon name="close" class="h-3 w-3" />
            {{ t('cartPage.removeUnavailableItems') }}
          </button>
        </div>
      </div>

      <!-- ── Right: order panel ──────────────────────────────────────────── -->
      <aside
        v-if="!isBrowseOnlyPlan"
        class="xl:sticky xl:top-[calc(var(--safe-top)+5.75rem)] xl:self-start"
      >
        <section class="ui-glass p-4 sm:p-5 space-y-4">

          <!-- Compact total header -->
          <div class="flex items-center justify-between gap-3 rounded-xl bg-slate-900/50 px-4 py-3">
            <div>
              <p class="text-[10px] uppercase tracking-widest text-slate-500">{{ t('cartPage.total') }}</p>
              <p class="text-2xl font-bold tabular-nums leading-tight text-[var(--color-secondary)]">
                {{ formatPrice(orderGrandTotal) }}
              </p>
            </div>
            <div class="text-right text-[11px] text-slate-500 space-y-0.5">
              <p>{{ itemCountLabel(cart.count) }}</p>
              <p v-if="fulfillmentType" class="capitalize text-slate-400">
                {{ fulfillmentType === 'delivery' ? t('cartPage.delivery') : t('cartPage.pickup') }}
              </p>
            </div>
          </div>

          <div class="border-t border-slate-800/50" />

          <!-- ── Table QR context ── -->
          <div
            v-if="isTableContextOrder"
            class="rounded-xl border border-emerald-500/35 bg-emerald-500/10 p-3 space-y-2"
          >
            <div>
              <p class="text-sm font-semibold text-emerald-100">{{ t('cartPage.tableQrOrder') }}</p>
              <p class="text-xs text-emerald-200/75 mt-0.5">
                {{ t('cartPage.tableContextDetected', { table: cart.tableLabel || '-' }) }}
                {{ t('cartPage.optionalNoteOnly') }}
              </p>
            </div>
            <label class="block space-y-1">
              <span class="text-[11px] text-emerald-200/75">{{ t('cartPage.tableCustomerNameOptional') }}</span>
              <input
                v-model.trim="customerNameModel"
                type="text"
                maxlength="80"
                class="ui-input"
                autocomplete="name"
                :placeholder="t('cartPage.tableCustomerNamePlaceholder')"
                @input="clearFieldError('customer_name')"
              />
            </label>
          </div>

          <!-- ── Fulfillment selector ── -->
          <div v-else class="space-y-3">
            <div :class="['grid gap-2', deliveryEnabled ? 'grid-cols-2' : 'grid-cols-1']">
              <!-- Pickup pill -->
              <button
                class="relative flex items-center gap-2 rounded-xl border px-3 py-2 text-xs font-semibold transition-all focus:outline-none"
                :aria-pressed="fulfillmentType === 'pickup'"
                :class="fulfillmentType === 'pickup'
                  ? 'border-[var(--color-secondary)]/55 bg-[var(--color-secondary)]/10 text-[var(--color-secondary)]'
                  : 'border-slate-700/60 bg-slate-900/40 text-slate-400 hover:border-slate-600 hover:text-slate-200'"
                @click="fulfillmentType = 'pickup'"
              >
                <AppIcon name="menu" class="h-3.5 w-3.5 shrink-0" />
                {{ t('cartPage.pickup') }}
                <span v-if="fulfillmentType === 'pickup'" class="ml-auto h-1.5 w-1.5 rounded-full bg-[var(--color-secondary)]" />
              </button>
              <!-- Delivery pill -->
              <button
                v-if="deliveryEnabled"
                class="relative flex items-center gap-2 rounded-xl border px-3 py-2 text-xs font-semibold transition-all focus:outline-none"
                :aria-pressed="fulfillmentType === 'delivery'"
                :class="fulfillmentType === 'delivery'
                  ? 'border-[var(--color-secondary)]/55 bg-[var(--color-secondary)]/10 text-[var(--color-secondary)]'
                  : 'border-slate-700/60 bg-slate-900/40 text-slate-400 hover:border-slate-600 hover:text-slate-200'"
                @click="fulfillmentType = 'delivery'"
              >
                <AppIcon name="table" class="h-3.5 w-3.5 shrink-0" />
                {{ t('cartPage.delivery') }}
                <span v-if="fulfillmentType === 'delivery'" class="ml-auto h-1.5 w-1.5 rounded-full bg-[var(--color-secondary)]" />
              </button>
            </div>
            <p v-if="fieldErrors.fulfillment_type" id="cart-fulfillment-error" class="text-xs text-red-300">{{ fieldErrors.fulfillment_type }}</p>

            <!-- ── Delivery form ── -->
            <div v-if="isDelivery" class="space-y-3 rounded-xl border border-slate-700/50 bg-slate-950/40 p-3">

              <!-- Saved addresses -->
              <div v-if="customerStore.isAuthenticated && savedAddresses.length" class="space-y-1.5">
                <p class="text-[10px] font-semibold uppercase tracking-widest text-slate-500">{{ t('cartPage.savedAddresses') }}</p>
                <div class="space-y-1">
                  <div
                    v-for="addr in savedAddresses"
                    :key="addr.id"
                    class="flex items-center gap-2 rounded-xl border border-slate-700/60 bg-slate-900/40 px-3 py-2 text-xs"
                  >
                    <button class="min-w-0 flex-1 text-left hover:text-indigo-300 transition-colors" @click="applySavedAddress(addr)">
                      <span v-if="addr.label" class="font-medium text-slate-200 mr-1.5">{{ addr.label }}</span>
                      <span class="text-slate-400 truncate">{{ addr.address }}</span>
                    </button>
                    <button class="shrink-0 text-slate-600 hover:text-red-400 transition-colors" :aria-label="t('common.remove')" @click="deleteSavedAddress(addr.id)">
                      <AppIcon name="close" class="h-3 w-3" />
                    </button>
                  </div>
                </div>
              </div>

              <!-- Zone info chips -->
              <div v-if="deliveryZoneDesc || deliveryMinOrder > 0" class="flex flex-wrap gap-1.5">
                <span v-if="deliveryZoneDesc" class="inline-flex items-center gap-1 rounded-full border border-slate-700/60 bg-slate-900/60 px-2.5 py-1 text-[11px] text-slate-300">
                  <AppIcon name="info" class="h-3 w-3 shrink-0 text-slate-400" />
                  {{ t('cartPage.deliveryZoneInfo', { desc: deliveryZoneDesc }) }}
                </span>
                <span
                  v-if="deliveryMinOrder > 0"
                  class="inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px]"
                  :class="Number(cart.total) >= deliveryMinOrder
                    ? 'border-emerald-500/40 bg-emerald-500/8 text-emerald-300'
                    : 'border-amber-500/40 bg-amber-500/8 text-amber-300'"
                >
                  {{ t('cartPage.deliveryMinOrderLabel', { amount: formatPrice(deliveryMinOrder) }) }}
                </span>
              </div>

              <!-- Delivery fee note -->
              <div v-if="deliveryFeeAmount === 0" class="flex items-center gap-1.5 text-[11px] text-emerald-400">
                <AppIcon name="check" class="h-3 w-3 shrink-0" />
                {{ t('cartPage.deliveryFee') }}: {{ t('cartPage.free') }}
              </div>

              <!-- ── Location (FIRST) ── -->
              <div class="space-y-2">
                <!-- Action chips -->
                <div class="flex flex-wrap gap-1.5">
                  <button
                    class="inline-flex items-center gap-1 rounded-full border border-slate-700/60 bg-slate-800/50 px-2.5 py-1 text-[11px] text-slate-300 hover:border-slate-500 hover:text-slate-100 transition-colors disabled:opacity-50"
                    :disabled="locating"
                    @click="useCurrentLocation"
                  >
                    <AppIcon name="info" class="h-3 w-3 shrink-0" />
                    {{ locating ? t('cartPage.locating') : t('cartPage.useCurrentLocation') }}
                  </button>
                  <button
                    class="inline-flex items-center gap-1 rounded-full border border-slate-700/60 bg-slate-800/50 px-2.5 py-1 text-[11px] text-slate-300 hover:border-slate-500 hover:text-slate-100 transition-colors"
                    @click="openInAppMapPicker"
                  >
                    <AppIcon name="table" class="h-3 w-3 shrink-0" />
                    {{ t('cartPage.pickPinInApp') }}
                  </button>
                  <button
                    class="inline-flex items-center gap-1 rounded-full border border-slate-700/60 bg-slate-800/50 px-2.5 py-1 text-[11px] text-slate-300 hover:border-slate-500 hover:text-slate-100 transition-colors"
                    @click="openExternalMap"
                  >
                    <AppIcon name="link" class="h-3 w-3 shrink-0" />
                    {{ t('cartPage.openExternalMap') }}
                  </button>
                  <button
                    v-if="hasLocationCoords || deliveryLocationUrl"
                    class="inline-flex items-center gap-1 rounded-full border border-red-500/30 bg-red-500/8 px-2.5 py-1 text-[11px] text-red-300 hover:bg-red-500/15 transition-colors"
                    @click="clearLocation"
                  >
                    <AppIcon name="close" class="h-3 w-3 shrink-0" />
                    {{ t('cartPage.clearLocation') }}
                  </button>
                </div>
                <!-- GPS status -->
                <p class="text-[11px]" :class="hasLocationCoords ? 'text-emerald-400/80' : 'text-slate-600'">
                  {{ hasLocationCoords
                    ? t('cartPage.locationReady', { lat: formatCoordinate(deliveryLat), lng: formatCoordinate(deliveryLng) })
                    : t('cartPage.noCoordinatesYet') }}
                </p>
                <p v-if="locationError" id="cart-location-error" class="text-xs text-red-300">{{ locationError }}</p>

                <!-- Map URL + Paste button inline -->
                <div class="space-y-1">
                  <span class="text-[11px] text-slate-400">{{ t('cartPage.mapPinUrlOptional') }}</span>
                  <div class="flex gap-1.5">
                    <input
                      ref="deliveryUrlInputRef"
                      v-model.trim="deliveryLocationUrl"
                      type="text"
                      maxlength="500"
                      class="ui-input flex-1 min-w-0"
                      :class="waitingForPaste ? 'ring-2 ring-[var(--color-secondary)]/40' : ''"
                      inputmode="url"
                      placeholder="https://maps.google.com/..."
                      :aria-label="t('cartPage.mapPinUrlOptional')"
                      :aria-invalid="fieldErrors.delivery_location_url ? 'true' : undefined"
                      aria-describedby="cart-map-url-error"
                      @input="clearFieldError('delivery_location_url')"
                    />
                    <button
                      type="button"
                      class="shrink-0 rounded-xl border px-3 py-2 text-xs font-semibold transition-all focus:outline-none"
                      :class="waitingForPaste
                        ? 'border-[var(--color-secondary)]/70 bg-[var(--color-secondary)]/15 text-[var(--color-secondary)]'
                        : 'border-slate-600 bg-slate-800/60 text-slate-400 hover:border-slate-500 hover:text-slate-200'"
                      @click="pasteMapLink"
                    >{{ t('cartPage.pasteLink') }}</button>
                  </div>
                  <p v-if="fieldErrors.delivery_location_url" id="cart-map-url-error" class="text-xs text-red-300">{{ fieldErrors.delivery_location_url }}</p>
                </div>
              </div>

              <!-- Address (SECOND — optional when map link filled) -->
              <label class="block space-y-1">
                <span class="text-[11px]" :class="deliveryLocationUrl ? 'text-slate-500' : 'text-slate-400'">
                  {{ deliveryLocationUrl ? t('cartPage.deliveryAddressOptionalWhenPin') : t('cartPage.deliveryAddressRequired') }}
                </span>
                <textarea
                  v-model.trim="deliveryAddress"
                  rows="2"
                  maxlength="180"
                  class="ui-textarea"
                  autocomplete="street-address"
                  :placeholder="t('cartPage.deliveryAddressPlaceholder')"
                  :aria-invalid="fieldErrors.delivery_address ? 'true' : undefined"
                  aria-describedby="cart-address-error"
                  @input="clearFieldError('delivery_address')"
                ></textarea>
                <p v-if="fieldErrors.delivery_address" id="cart-address-error" class="text-xs text-red-300">{{ fieldErrors.delivery_address }}</p>
              </label>

              <!-- Save address -->
              <div v-if="customerStore.isAuthenticated && deliveryAddress" class="space-y-1.5">
                <label class="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" v-model="saveAddressAfterOrder" class="rounded" />
                  <span class="text-xs text-slate-400">{{ t('cartPage.saveAddress') }}</span>
                </label>
                <input
                  v-if="saveAddressAfterOrder"
                  v-model.trim="saveAddressLabel"
                  type="text"
                  maxlength="60"
                  class="ui-input text-xs"
                  :placeholder="t('cartPage.saveAddressLabelPlaceholder')"
                  :aria-label="t('cartPage.saveAddressLabelPlaceholder')"
                />
              </div>

              <!-- Advanced: lat / lng (collapsed) -->
              <div>
                <button
                  type="button"
                  class="flex items-center gap-1 text-[11px] text-slate-500 hover:text-slate-300 transition-colors"
                  @click="locationAdvancedOpen = !locationAdvancedOpen"
                >
                  <span aria-hidden="true">{{ locationAdvancedOpen ? '▾' : '▸' }}</span>
                  {{ t('cartPage.latitudeOptional') }} / {{ t('cartPage.longitudeOptional') }}
                </button>
                <div v-if="locationAdvancedOpen" class="mt-2 grid grid-cols-2 gap-2">
                  <label class="block space-y-1">
                    <span class="text-[11px] text-slate-400">{{ t('cartPage.latitudeOptional') }}</span>
                    <input
                      v-model.number="deliveryLat"
                      type="number"
                      step="any"
                      class="ui-input"
                      inputmode="decimal"
                      placeholder="33.5731"
                      :aria-invalid="fieldErrors.delivery_lat ? 'true' : undefined"
                      aria-describedby="cart-lat-error"
                      @input="clearFieldError('delivery_lat')"
                    />
                    <p v-if="fieldErrors.delivery_lat" id="cart-lat-error" class="text-xs text-red-300">{{ fieldErrors.delivery_lat }}</p>
                  </label>
                  <label class="block space-y-1">
                    <span class="text-[11px] text-slate-400">{{ t('cartPage.longitudeOptional') }}</span>
                    <input
                      v-model.number="deliveryLng"
                      type="number"
                      step="any"
                      class="ui-input"
                      inputmode="decimal"
                      placeholder="-7.5898"
                      :aria-invalid="fieldErrors.delivery_lng ? 'true' : undefined"
                      aria-describedby="cart-lng-error"
                      @input="clearFieldError('delivery_lng')"
                    />
                    <p v-if="fieldErrors.delivery_lng" id="cart-lng-error" class="text-xs text-red-300">{{ fieldErrors.delivery_lng }}</p>
                  </label>
                </div>
              </div>

            </div><!-- /delivery form -->
          </div><!-- /fulfillment -->

          <!-- ── Note ── -->
          <label class="block space-y-1">
            <span class="text-[11px] text-slate-400">{{ t('cartPage.optionalNoteForRestaurant') }}</span>
            <textarea
              v-model.trim="customerNote"
              rows="2"
              maxlength="300"
              class="ui-textarea"
              :placeholder="isTableContextOrder ? t('cartPage.tableNotePlaceholder') : t('cartPage.generalNotePlaceholder')"
            ></textarea>
          </label>

          <!-- ── Tip (compact row) ── -->
          <div class="space-y-2">
            <div class="flex items-center gap-2">
              <span class="shrink-0 text-xs text-slate-400">{{ t('cartPage.tipLabel') }}</span>
              <div class="flex flex-1 gap-1">
                <button
                  v-for="opt in TIP_OPTIONS"
                  :key="opt.value"
                  type="button"
                  class="flex-1 rounded-lg border py-1 text-[11px] font-semibold transition-colors"
                  :class="tipPercent === opt.value
                    ? 'border-[var(--color-secondary)]/70 bg-[var(--color-secondary)]/15 text-[var(--color-secondary)]'
                    : 'border-slate-700 bg-slate-800/50 text-slate-400 hover:border-slate-600 hover:text-slate-200'"
                  @click="setTipPercent(opt.value)"
                >{{ opt.label }}</button>
              </div>
              <span
                v-if="tipAmount > 0"
                class="shrink-0 text-xs font-semibold tabular-nums text-[var(--color-secondary)]"
              >+{{ formatPrice(tipAmount) }}</span>
            </div>
            <!-- Custom tip input -->
            <div v-if="tipPercent === 'custom'" class="flex items-center gap-2">
              <span class="text-xs text-slate-400 shrink-0">{{ currencyStore.selected }}</span>
              <input
                v-model="customTipInput"
                type="number"
                min="0"
                step="0.01"
                class="ui-input flex-1 text-sm"
                :aria-label="t('cartPage.tipCustomPlaceholder')"
                :placeholder="t('cartPage.tipCustomPlaceholder')"
                @blur="clampCustomTip"
              />
            </div>
          </div>

          <!-- ── Promo code (collapsible) ── -->
          <div>
            <!-- Applied state -->
            <div
              v-if="promoApplied"
              class="flex items-center justify-between gap-2 rounded-xl border border-emerald-500/40 bg-emerald-500/8 px-3 py-2"
            >
              <div class="min-w-0">
                <p class="text-xs font-semibold text-emerald-300">{{ promoApplied.name }}</p>
                <p class="text-[10px] text-emerald-400/70">
                  {{ promoApplied.promo_type === 'percentage'
                    ? t('ownerPromotions.labelPercentage', { value: promoApplied.discount_value })
                    : promoApplied.promo_type === 'fixed'
                      ? t('ownerPromotions.labelFixed', { value: promoApplied.discount_value })
                      : t('ownerPromotions.typeFreeDelivery') }}
                </p>
              </div>
              <button class="shrink-0 text-[10px] text-slate-400 hover:text-red-300 transition-colors" @click="removePromoCode">
                {{ t('cartPage.promoRemove') }}
              </button>
            </div>
            <!-- Collapsed toggle -->
            <template v-else>
              <button
                type="button"
                class="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-300 transition-colors"
                @click="promoOpen = !promoOpen"
              >
                <span aria-hidden="true" class="text-slate-600 text-[11px]">{{ promoOpen ? '▾' : '▸' }}</span>
                {{ t('cartPage.promoCodeLabel') }}
              </button>
              <div v-show="promoOpen" class="mt-2 flex gap-2">
                <input
                  v-model="promoCode"
                  type="text"
                  maxlength="20"
                  autocomplete="off"
                  class="ui-input flex-1 uppercase text-sm"
                  :aria-label="t('cartPage.promoCodeLabel')"
                  :placeholder="t('cartPage.promoPlaceholder')"
                  :aria-invalid="promoError ? 'true' : undefined"
                  aria-describedby="cart-promo-error"
                  @keyup.enter="applyPromoCode"
                  @input="promoCode = promoCode.toUpperCase(); promoError = ''"
                />
                <button
                  class="shrink-0 rounded-xl border border-slate-600 bg-slate-800/60 px-3 py-2 text-xs font-semibold text-slate-300 hover:border-indigo-500/60 hover:text-indigo-300 transition-colors disabled:opacity-50"
                  :disabled="promoChecking || !promoCode.trim()"
                  @click="applyPromoCode"
                >{{ promoChecking ? '…' : t('cartPage.promoApply') }}</button>
              </div>
              <p v-if="promoError" id="cart-promo-error" class="mt-1 text-[10px] text-red-300">{{ promoError }}</p>
            </template>
          </div>

          <!-- ── Wallet credits ── -->
          <div
            v-if="canPayWithCredits"
            class="rounded-xl border p-3 transition-colors"
            :class="useWallet
              ? 'border-[var(--color-secondary)]/50 bg-[var(--color-secondary)]/8'
              : 'border-slate-700/60 bg-slate-900/30'"
          >
            <label class="flex cursor-pointer items-center justify-between gap-3">
              <div>
                <p class="text-xs font-semibold" :class="useWallet ? 'text-[var(--color-secondary)]' : 'text-slate-300'">
                  {{ t('cartPage.payWithCredits') }}
                </p>
                <p class="text-[11px] text-slate-400">{{ t('cartPage.payWithCreditsBalance', { balance: walletBalance }) }}</p>
              </div>
              <button
                type="button"
                role="switch"
                :aria-checked="useWallet"
                :aria-label="t('cartPage.payWithCredits')"
                class="relative h-5 w-9 shrink-0 rounded-full border transition-colors focus:outline-none"
                :class="useWallet ? 'border-[var(--color-secondary)]/60 bg-[var(--color-secondary)]/30' : 'border-slate-600 bg-slate-800'"
                @click="useWallet = !useWallet"
              >
                <span
                  class="absolute top-0.5 h-4 w-4 rounded-full transition-transform"
                  :class="useWallet ? 'translate-x-4 bg-[var(--color-secondary)]' : 'translate-x-0.5 bg-slate-500'"
                />
              </button>
            </label>
            <p v-if="useWallet" class="mt-1 text-[11px] text-emerald-300">
              {{ t('cartPage.creditsApplied', { amount: formatPrice(walletDeduction) }) }}
            </p>
          </div>

          <!-- ── Sign-in nudge (table orders) ── -->
          <div
            v-if="isTableContextOrder && !customerStore.isAuthenticated && !tableNudgeDismissed"
            class="rounded-xl border border-slate-700/60 bg-slate-900/60 p-3 space-y-2"
          >
            <div class="flex items-start justify-between gap-2">
              <p class="text-xs font-semibold text-slate-200">{{ t('cartPage.tableNudgeTitle') }}</p>
              <button class="shrink-0 text-slate-500 hover:text-slate-300 transition" :aria-label="t('common.close')" @click="tableNudgeDismissed = true">
                <AppIcon name="close" class="h-3.5 w-3.5" />
              </button>
            </div>
            <ul class="space-y-1">
              <li class="flex items-center gap-1.5 text-[11px] text-slate-400">
                <AppIcon name="check" class="h-3 w-3 shrink-0 text-emerald-400" />{{ t('cartPage.tableNudgeBenefit1') }}
              </li>
              <li class="flex items-center gap-1.5 text-[11px] text-slate-400">
                <AppIcon name="check" class="h-3 w-3 shrink-0 text-emerald-400" />{{ t('cartPage.tableNudgeBenefit2') }}
              </li>
              <li class="flex items-center gap-1.5 text-[11px] text-slate-400">
                <AppIcon name="check" class="h-3 w-3 shrink-0 text-emerald-400" />{{ t('cartPage.tableNudgeBenefit3') }}
              </li>
            </ul>
            <button class="ui-btn-outline w-full justify-center text-xs py-1.5" @click="showAuthModal = true">
              <AppIcon name="user" class="h-3.5 w-3.5" />
              {{ t('cartPage.tableNudgeButton') }}
            </button>
          </div>

          <!-- ── Auth gate (non-table orders) ── -->
          <template v-if="!isTableContextOrder">
            <div v-if="!customerStore.isAuthenticated" class="rounded-xl border border-amber-500/40 bg-amber-500/8 p-3 space-y-2">
              <p class="text-xs font-semibold text-amber-300">{{ t('cartPage.orderAuthRequired') }}</p>
              <p class="text-[11px] text-slate-400">{{ t('cartPage.orderAuthBody') }}</p>
              <button class="ui-btn-primary w-full justify-center" @click="showAuthModal = true">
                <AppIcon name="user" class="h-3.5 w-3.5" />
                {{ t('cartPage.deliveryAuthButton') }}
              </button>
            </div>
            <template v-else>
              <div v-if="isDelivery && !customerStore.isVerified" class="rounded-xl border border-amber-500/40 bg-amber-500/8 px-3 py-2 space-y-1">
                <p class="text-xs font-semibold text-amber-300">{{ t('cartPage.deliveryNotVerified') }}</p>
                <button class="text-[11px] text-slate-400 hover:text-slate-200 underline" @click="showAuthModal = true">{{ t('cartPage.deliveryAuthButton') }}</button>
              </div>
              <div v-else class="flex items-center gap-1.5 rounded-xl border border-emerald-500/30 bg-emerald-500/8 px-3 py-2 text-xs text-emerald-300">
                <AppIcon name="check" class="h-3.5 w-3.5 shrink-0" />
                {{ t('cartPage.signedInAs', { name: customerStore.displayName }) }}
              </div>
            </template>
          </template>

          <!-- ── Order summary breakdown ── -->
          <div class="border-t border-slate-800/50 pt-3 space-y-1.5 text-xs">
            <div v-if="fulfillmentType === 'delivery' && deliveryFeeAmount > 0" class="flex items-center justify-between text-slate-400">
              <span>{{ t('cartPage.subtotal') }}</span>
              <span class="tabular-nums">{{ formatPrice(cart.total) }}</span>
            </div>
            <div v-if="fulfillmentType === 'delivery' && deliveryFeeAmount > 0" class="flex items-center justify-between text-slate-300">
              <span>{{ t('cartPage.deliveryFee') }}</span>
              <span class="tabular-nums font-medium">{{ formatPrice(deliveryFeeAmount) }}</span>
            </div>
            <div v-if="fulfillmentType === 'delivery' && deliveryFeeAmount === 0" class="flex items-center justify-between text-emerald-400">
              <span>{{ t('cartPage.deliveryFee') }}</span>
              <span class="font-medium">{{ t('cartPage.free') }}</span>
            </div>
            <div v-if="tipAmount > 0" class="flex items-center justify-between text-[var(--color-secondary)]/75">
              <span>{{ t('cartPage.tipLabel') }}</span>
              <span class="tabular-nums">+{{ formatPrice(tipAmount) }}</span>
            </div>
            <div v-if="useWallet && walletDeduction > 0" class="flex items-center justify-between text-emerald-400">
              <span>{{ t('cartPage.payWithCredits') }}</span>
              <span class="tabular-nums font-medium">-{{ formatPrice(walletDeduction) }}</span>
            </div>
            <div class="flex items-center justify-between pt-1.5 border-t border-slate-800/40">
              <span class="text-sm font-semibold text-slate-200">{{ t('cartPage.total') }}</span>
              <span class="text-lg font-bold tabular-nums text-[var(--color-secondary)]">{{ formatPrice(orderGrandTotal) }}</span>
            </div>
          </div>

          <!-- ── CTA buttons ── -->
          <div class="space-y-2">
            <button
              v-if="!isBrowseOnlyPlan"
              class="ui-btn-primary w-full justify-center py-3.5 text-base font-semibold shadow-lg shadow-[var(--color-secondary)]/15"
              :disabled="placingOrder"
              @click="placeInAppOrder"
            >
              <AppIcon name="cart" class="h-3.5 w-3.5" />
              {{ placingOrder ? t('cartPage_order.placing') : t('cartPage_order.placeOrder') }}
            </button>
            <button
              v-if="cart.canWhatsapp"
              class="ui-btn-outline w-full justify-center"
              :disabled="sendingWhatsapp"
              @click="openWhatsApp"
            >
              <AppIcon name="chat" class="h-3.5 w-3.5" />
              {{ sendingWhatsapp ? t('cartPage.preparingWhatsApp') : t('cartPage.sendViaWhatsApp') }}
            </button>
            <button
              v-if="cart.canCheckout"
              class="ui-btn-outline w-full justify-center"
              :disabled="processingCheckout"
              @click="startCheckout"
            >
              <AppIcon name="cart" class="h-3.5 w-3.5" />
              {{ processingCheckout ? t('cartPage.preparingCheckout') : t('cartPage.proceedCheckout') }}
            </button>
            <button
              v-if="isBrowseOnlyPlan"
              class="w-full inline-flex items-center justify-center rounded-full border border-slate-700 px-5 py-3 text-slate-50 opacity-60 cursor-not-allowed"
              disabled
            >{{ t('cartPage.orderingDisabledPlan') }}</button>
            <p v-if="isBrowseOnlyPlan" class="text-[11px] text-slate-500 text-center">{{ t('cartPage.orderingDisabledCurrentPlan') }}</p>
          </div>

          <!-- Errors -->
          <div v-if="placeOrderError" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
            <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
            <p class="flex-1 text-sm text-red-300">{{ placeOrderError }}</p>
          </div>
          <div v-if="checkoutError" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
            <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
            <p class="flex-1 text-sm text-red-300">{{ checkoutError }}</p>
          </div>
          <div v-if="handoffError" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
            <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
            <p class="flex-1 text-sm text-red-300">{{ handoffError }}</p>
          </div>

        </section>
      </aside>
    </div>

    <!-- ── Modals ─────────────────────────────────────────────────────────── -->
    <CustomerAuthModal
      v-if="showAuthModal"
      @close="showAuthModal = false"
      @authenticated="onCustomerAuthenticated"
    />

    <Teleport to="body">
      <div
        v-if="showMapModal"
        class="fixed inset-0 z-50 flex items-end justify-center bg-slate-950/85 p-3 sm:items-center sm:p-5"
        @click.self="closeMapModal"
        @keydown.esc.window="closeMapModal"
      >
        <div ref="mapDialogRef" role="dialog" aria-modal="true" aria-labelledby="cart-map-dialog-title" class="w-full max-w-2xl rounded-2xl border border-slate-700/70 bg-slate-950 shadow-2xl shadow-black/50">
          <header class="flex items-center justify-between gap-3 border-b border-slate-800 px-4 py-3">
            <div>
              <p class="ui-kicker">{{ t('cartPage.mapPicker') }}</p>
              <h2 id="cart-map-dialog-title" class="text-base font-semibold text-slate-100">{{ t('cartPage.tapMapToChoosePin') }}</h2>
            </div>
            <button class="ui-btn-outline px-3 py-1.5 text-xs" @click="closeMapModal">
              <AppIcon name="close" class="h-3.5 w-3.5" />
              {{ t('common.close') }}
            </button>
          </header>
          <div class="space-y-3 p-3">
            <p class="text-xs text-slate-400">
              {{ t('cartPage.selected') }}:
              {{
                hasTemporaryMapSelection
                  ? `${formatCoordinate(temporaryMapLat)}, ${formatCoordinate(temporaryMapLng)}`
                  : t('cartPage.noPinSelectedYet')
              }}
            </p>
            <div
              ref="mapContainerRef"
              class="h-[52vh] min-h-[280px] w-full overflow-hidden rounded-xl border border-slate-700/80"
            ></div>
            <div class="flex flex-wrap items-center justify-end gap-2">
              <button class="ui-btn-outline px-3 py-1.5 text-xs" @click="closeMapModal">
                <AppIcon name="close" class="h-3.5 w-3.5" />
                {{ t('cartPage.cancel') }}
              </button>
              <button
                class="ui-btn-primary px-4 py-2 text-sm"
                :disabled="!hasTemporaryMapSelection"
                @click="applyMapSelection"
              >
                <AppIcon name="check" class="h-3.5 w-3.5" />
                {{ t('cartPage.useSelectedPin') }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from 'vue';
import { useRouter } from 'vue-router';
import AppIcon from '../components/AppIcon.vue';
import CustomerAuthModal from '../components/CustomerAuthModal.vue';
import { useI18n } from '../composables/useI18n';
import { useCartStore } from '../stores/cart';
import { useCustomerStore } from '../stores/customer';
import { useOrderStore } from '../stores/order';
import { useTenantStore } from '../stores/tenant';
import { useToastStore } from '../stores/toast';
import { useCurrencyStore } from '../stores/currency';
import api from '../lib/api';
import { trackEvent } from '../lib/analytics';
import { safeExternalUrl } from '../lib/escape';

const router = useRouter();
const cart = useCartStore();
const customerStore = useCustomerStore();
const order = useOrderStore();
const tenant = useTenantStore();
const toast = useToastStore();
const { formatCurrency, formatPrice, itemCountLabel, t } = useI18n();
const currencyStore = useCurrencyStore();

const showAuthModal = ref(false);
const tableNudgeDismissed = ref(false);
const useWallet = ref(false);

// ── Tip ──────────────────────────────────────────────────────────────────────
const TIP_OPTIONS = [
  { value: 0,        label: '0%' },
  { value: 5,        label: '5%' },
  { value: 10,       label: '10%' },
  { value: 15,       label: '15%' },
  { value: 20,       label: '20%' },
  { value: 'custom', label: '…' },
];
const tipPercent    = ref(0);
const customTipInput = ref('');

const tipAmount = computed(() => {
  if (tipPercent.value === 'custom') {
    const v = parseFloat(customTipInput.value);
    if (!Number.isFinite(v) || v <= 0) return 0;
    // If user has a display currency selected, convert their input → MAD
    const sel = currencyStore.selected;
    if (sel && sel !== 'MAD') {
      const rate = currencyStore.rates[sel];
      const madPerUnit = Number(rate?.mad_per_unit ?? 1);
      if (madPerUnit > 0) return Math.round(v * madPerUnit * 100) / 100;
    }
    return Math.round(v * 100) / 100;
  }
  const pct = Number(tipPercent.value) || 0;
  if (pct === 0) return 0;
  const base = Number(cart.total) || 0;
  return Math.round(base * pct) / 100;
});

const setTipPercent = (val) => {
  tipPercent.value = val;
  if (val !== 'custom') customTipInput.value = '';
};

const clampCustomTip = () => {
  const v = parseFloat(customTipInput.value);
  if (!Number.isFinite(v) || v < 0) customTipInput.value = '';
};

// Promo code
const promoCode = ref('');
const promoChecking = ref(false);
const promoApplied = ref(null);   // { name, promo_type, discount_value, min_order_amount }
const promoError = ref('');
const promoOpen = ref(false);

// Saved addresses
const savedAddresses = ref([]);
const saveAddressAfterOrder = ref(false);
const saveAddressLabel = ref('');

const fetchSavedAddresses = async () => {
  if (!customerStore.isAuthenticated) return;
  try {
    const res = await api.get('/customer/addresses/');
    savedAddresses.value = res.data || [];
  } catch {
    // silent
  }
};

const applySavedAddress = (addr) => {
  deliveryAddress.value = addr.address;
  deliveryLocationUrl.value = addr.location_url || '';
  deliveryLat.value = addr.lat ?? null;
  deliveryLng.value = addr.lng ?? null;
  clearFieldError('delivery_address');
  clearFieldError('delivery_location_url');
};

const deleteSavedAddress = async (id) => {
  try {
    await api.delete(`/customer/addresses/${id}/`);
    savedAddresses.value = savedAddresses.value.filter((a) => a.id !== id);
  } catch {
    toast.show(t('cartPage.addressDeleteFailed'), 'error');
  }
};

const sendingWhatsapp = ref(false);
const processingCheckout = ref(false);
const placingOrder = ref(false);
const handoffError = ref('');
const checkoutError = ref('');
const placeOrderError = ref('');
const customerNote = ref('');
const unavailableSlugs = ref([]);
const unavailableNames = computed(() =>
  unavailableSlugs.value.map((slug) => cart.items.find((i) => i.slug === slug)?.name || slug)
);

const fulfillmentType = ref('');
const deliveryAddress = ref('');
const deliveryLocationUrl = ref('');
const deliveryLat = ref(null);
const deliveryLng = ref(null);
const locating = ref(false);
const locationError = ref('');
const locationAdvancedOpen = ref(false);
const waitingForPaste = ref(false);
const deliveryUrlInputRef = ref(null);
let waitingForPasteTimer = null;
const fieldErrors = ref({});
const showMapModal = ref(false);
const mapContainerRef = ref(null);
const mapDialogRef = ref(null);

const FOCUSABLE_MAP = [
  'a[href]', 'button:not([disabled])', 'input:not([disabled])',
  'select:not([disabled])', 'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(', ');

const trapMapFocus = (e) => {
  if (!mapDialogRef.value || e.key !== 'Tab') return;
  const focusable = Array.from(mapDialogRef.value.querySelectorAll(FOCUSABLE_MAP));
  if (!focusable.length) return;
  const first = focusable[0];
  const last  = focusable[focusable.length - 1];
  if (e.shiftKey) {
    if (document.activeElement === first) { e.preventDefault(); last.focus(); }
  } else {
    if (document.activeElement === last)  { e.preventDefault(); first.focus(); }
  }
};
const leafletMap = ref(null);
const leafletMarker = ref(null);
const leafletModuleRef = ref(null);
const leafletAssetsReady = ref(false);
const temporaryMapLat = ref(null);
const temporaryMapLng = ref(null);
const meta = computed(() => tenant.resolvedMeta || null);

// Delivery settings from restaurant profile
const deliveryEnabled = computed(() => meta.value?.profile?.delivery_enabled !== false);

// Delivery fee from restaurant profile (0 means free delivery)
const deliveryFeeAmount = computed(() => {
  const raw = meta.value?.profile?.delivery_fee;
  const n = Number(raw);
  return Number.isFinite(n) && n > 0 ? n : 0;
});

// Minimum order total required for delivery (0 = no minimum)
const deliveryMinOrder = computed(() => {
  const raw = meta.value?.profile?.delivery_minimum_order;
  const n = Number(raw);
  return Number.isFinite(n) && n > 0 ? n : 0;
});

// Short zone description shown to customers (empty = not set)
const deliveryZoneDesc = computed(() => String(meta.value?.profile?.delivery_zone_description || '').trim());

// Grand total = items subtotal + delivery fee (when applicable)
const orderGrandTotal = computed(() => {
  const subtotal = Number(cart.total) || 0;
  const base = fulfillmentType.value === 'delivery'
    ? subtotal + deliveryFeeAmount.value
    : subtotal;
  return base + tipAmount.value;
});

// Wallet credits
const walletBalance = computed(() => {
  const raw = customerStore.customer?.wallet_balance;
  const n = Number(raw);
  return Number.isFinite(n) && n > 0 ? n : 0;
});
const canPayWithCredits = computed(() =>
  customerStore.isAuthenticated && walletBalance.value > 0 && !isBrowseOnlyPlan.value
);
const walletDeduction = computed(() => Math.min(walletBalance.value, orderGrandTotal.value));

const parseCoordinateValue = (value) => {
  if (value === null || value === undefined) return null;
  const raw = String(value).trim();
  if (!raw) return null;
  const number = Number(raw);
  return Number.isFinite(number) ? number : null;
};

const currency = computed(() => {
  const firstItemCurrency = cart.items.find((item) => item.currency)?.currency;
  return firstItemCurrency || meta.value?.plan?.currency || 'MAD';
});
const planLabel = computed(
  () => meta.value?.plan?.tier_name || meta.value?.plan?.name || 'Basic'
);
const isBrowseOnlyPlan = computed(() => tenant.isBrowseOnlyPlan === true);
const tableLabelModel = computed(() => cart.tableLabel || '');
const isTableContextOrder = computed(() =>
  Boolean(cart.tableSlug || cart.tableLabel)
);
const isDelivery = computed(
  () => !isTableContextOrder.value && fulfillmentType.value === 'delivery'
);
const hasLocationCoords = computed(() => {
  const lat = parseCoordinateValue(deliveryLat.value);
  const lng = parseCoordinateValue(deliveryLng.value);
  return lat !== null && lng !== null;
});
const hasTemporaryMapSelection = computed(() => {
  const lat = parseCoordinateValue(temporaryMapLat.value);
  const lng = parseCoordinateValue(temporaryMapLng.value);
  return lat !== null && lng !== null;
});

const customerNameModel = computed({
  get: () => cart.customerName || '',
  set: (value) => cart.setCustomerName(value),
});
const customerPhoneModel = computed({
  get: () => cart.customerPhone || '',
  set: (value) => cart.setCustomerPhone(value),
});

const formatCoordinate = (value) => {
  const number = Number(value);
  if (!Number.isFinite(number)) return '-';
  return number.toFixed(6);
};

const clearFieldError = (field) => {
  if (!fieldErrors.value?.[field]) return;
  const next = { ...fieldErrors.value };
  delete next[field];
  fieldErrors.value = next;
};

const setLineQty = (item, event) => {
  const next = Number(event?.target?.value || item.qty);
  cart.setQty(item.key, next);
};

const clearCart = () => {
  cart.clear();
  unavailableSlugs.value = [];
  toast.show(t('cartPage.cartCleared'), 'info');
};

const parseCoordinatesFromMapUrl = (value) => {
  const raw = String(value || '').trim();
  if (!raw) return null;
  let match = raw.match(/@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/);
  if (!match) {
    match = raw.match(
      /[?&](?:q|query|ll|destination)=(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/i
    );
  }
  if (!match) {
    match = raw.match(/#map=\d+\/(-?\d+(?:\.\d+)?)\/(-?\d+(?:\.\d+)?)/i);
  }
  if (!match) return null;
  const lat = Number(match[1]);
  const lng = Number(match[2]);
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
  if (lat < -90 || lat > 90 || lng < -180 || lng > 180) return null;
  return { lat: Number(lat.toFixed(6)), lng: Number(lng.toFixed(6)) };
};

const setLocationCoordinates = (lat, lng) => {
  deliveryLat.value = Number(Number(lat).toFixed(6));
  deliveryLng.value = Number(Number(lng).toFixed(6));
  clearFieldError('delivery_lat');
  clearFieldError('delivery_lng');
  clearFieldError('delivery_location_url');
};

const resolveMapCenter = () => {
  const lat = parseCoordinateValue(deliveryLat.value);
  const lng = parseCoordinateValue(deliveryLng.value);
  if (lat !== null && lng !== null) {
    return { lat, lng, zoom: 16, hasMarker: true };
  }
  const parsedFromUrl = parseCoordinatesFromMapUrl(deliveryLocationUrl.value);
  if (parsedFromUrl) {
    return {
      lat: parsedFromUrl.lat,
      lng: parsedFromUrl.lng,
      zoom: 16,
      hasMarker: true,
    };
  }
  return { lat: 33.5731, lng: -7.5898, zoom: 12, hasMarker: false };
};

const ensureLeafletLoaded = async () => {
  if (leafletModuleRef.value) return leafletModuleRef.value;

  const [{ default: Leaflet }, marker2x, marker, shadow] = await Promise.all([
    import('leaflet'),
    import('leaflet/dist/images/marker-icon-2x.png'),
    import('leaflet/dist/images/marker-icon.png'),
    import('leaflet/dist/images/marker-shadow.png'),
  ]);

  if (!leafletAssetsReady.value) {
    await import('leaflet/dist/leaflet.css');
    delete Leaflet.Icon.Default.prototype._getIconUrl;
    Leaflet.Icon.Default.mergeOptions({
      iconRetinaUrl: marker2x.default,
      iconUrl: marker.default,
      shadowUrl: shadow.default,
    });
    leafletAssetsReady.value = true;
  }

  leafletModuleRef.value = Leaflet;
  return Leaflet;
};

const updateLeafletMarker = (lat, lng) => {
  if (!leafletMap.value) return;
  if (!leafletMarker.value) {
    const Leaflet = leafletModuleRef.value;
    leafletMarker.value = Leaflet.marker([lat, lng]).addTo(leafletMap.value);
    return;
  }
  leafletMarker.value.setLatLng([lat, lng]);
};

const removeLeafletMarker = () => {
  if (!leafletMap.value || !leafletMarker.value) return;
  leafletMap.value.removeLayer(leafletMarker.value);
  leafletMarker.value = null;
};

const initLeafletMap = async () => {
  if (!mapContainerRef.value) return;
  const Leaflet = await ensureLeafletLoaded();
  const center = resolveMapCenter();

  if (!leafletMap.value) {
    leafletMap.value = Leaflet.map(mapContainerRef.value, {
      zoomControl: true,
      attributionControl: true,
    });
    Leaflet.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap contributors',
    }).addTo(leafletMap.value);
    leafletMap.value.on('click', (event) => {
      const lat = Number(event?.latlng?.lat);
      const lng = Number(event?.latlng?.lng);
      if (!Number.isFinite(lat) || !Number.isFinite(lng)) return;
      temporaryMapLat.value = Number(lat.toFixed(6));
      temporaryMapLng.value = Number(lng.toFixed(6));
      updateLeafletMarker(temporaryMapLat.value, temporaryMapLng.value);
    });
  }

  leafletMap.value.setView([center.lat, center.lng], center.zoom);
  leafletMap.value.invalidateSize();

  if (center.hasMarker) {
    temporaryMapLat.value = Number(center.lat.toFixed(6));
    temporaryMapLng.value = Number(center.lng.toFixed(6));
    updateLeafletMarker(temporaryMapLat.value, temporaryMapLng.value);
  } else {
    temporaryMapLat.value = null;
    temporaryMapLng.value = null;
    removeLeafletMarker();
  }
};

const openInAppMapPicker = () => {
  showMapModal.value = true;
  trackEvent('contact_click', {
    source: 'cart_delivery_location',
    metadata: { action: 'open_in_app_map_picker' },
  });
};

const closeMapModal = () => {
  showMapModal.value = false;
};

const applyMapSelection = () => {
  const lat = parseCoordinateValue(temporaryMapLat.value);
  const lng = parseCoordinateValue(temporaryMapLng.value);
  if (lat === null || lng === null) {
    toast.show(t('cartPage.selectPinFirst'), 'error');
    return;
  }
  setLocationCoordinates(lat, lng);
  deliveryLocationUrl.value = `https://maps.google.com/?q=${deliveryLat.value},${deliveryLng.value}`;
  clearFieldError('delivery_location_url');
  locationError.value = '';
  closeMapModal();
  trackEvent('contact_click', {
    source: 'cart_delivery_location',
    metadata: { action: 'map_pin_selected' },
  });
  toast.show(t('cartPage.deliveryPinSelected'), 'success');
};

const clearLocation = () => {
  deliveryLocationUrl.value = '';
  deliveryLat.value = null;
  deliveryLng.value = null;
  temporaryMapLat.value = null;
  temporaryMapLng.value = null;
  removeLeafletMarker();
  locationError.value = '';
  clearFieldError('delivery_location_url');
  clearFieldError('delivery_lat');
  clearFieldError('delivery_lng');
};

watch(deliveryLocationUrl, (value) => {
  if (value) {
    waitingForPaste.value = false;
    clearTimeout(waitingForPasteTimer);
  }
  const parsed = parseCoordinatesFromMapUrl(value);
  if (parsed) {
    setLocationCoordinates(parsed.lat, parsed.lng);
  }
});

watch(isTableContextOrder, (value) => {
  if (!value) return;
  fieldErrors.value = {};
  locationError.value = '';
});

// If delivery gets disabled server-side, reset to pickup automatically
watch(deliveryEnabled, (enabled) => {
  if (!enabled && fulfillmentType.value === 'delivery') {
    fulfillmentType.value = 'pickup';
  }
});

watch(canPayWithCredits, (val) => {
  if (!val) useWallet.value = false;
});

watch(fulfillmentType, (value) => {
  clearFieldError('fulfillment_type');
  if (value && !isTableContextOrder.value && !customerStore.isAuthenticated) {
    showAuthModal.value = true;
  }
  if (value !== 'delivery') {
    closeMapModal();
    deliveryAddress.value = '';
    deliveryLocationUrl.value = '';
    deliveryLat.value = null;
    deliveryLng.value = null;
    temporaryMapLat.value = null;
    temporaryMapLng.value = null;
    removeLeafletMarker();
    locationError.value = '';
    clearFieldError('delivery_address');
    clearFieldError('delivery_location_url');
    clearFieldError('delivery_lat');
    clearFieldError('delivery_lng');
  }
});

watch(showMapModal, async (value) => {
  if (!value) {
    // Destroy the map instance when the modal closes to free memory
    if (leafletMap.value) {
      leafletMap.value.remove();
      leafletMap.value = null;
      leafletMarker.value = null;
    }
    document.removeEventListener('keydown', trapMapFocus);
    return;
  }
  await nextTick();
  mapDialogRef.value?.querySelector(FOCUSABLE_MAP)?.focus();
  document.addEventListener('keydown', trapMapFocus);
  try {
    await initLeafletMap();
  } catch {
    toast.show(t('cartPage.unableToLoadMapPicker'), 'error');
    showMapModal.value = false;
  }
});

const useCurrentLocation = () => {
  locationError.value = '';
  if (typeof navigator === 'undefined' || !navigator.geolocation) {
    locationError.value = t('cartPage.locationNotSupported');
    return;
  }
  locating.value = true;
  navigator.geolocation.getCurrentPosition(
    (position) => {
      const lat = position?.coords?.latitude;
      const lng = position?.coords?.longitude;
      if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
        locationError.value = t('cartPage.unableToReadGps');
        locating.value = false;
        return;
      }
      setLocationCoordinates(lat, lng);
      // Always replace the URL with the fresh GPS coordinates
      deliveryLocationUrl.value = `https://maps.google.com/?q=${deliveryLat.value},${deliveryLng.value}`;
      clearFieldError('delivery_location_url');
      waitingForPaste.value = false;
      clearTimeout(waitingForPasteTimer);
      trackEvent('contact_click', {
        source: 'cart_delivery_location',
        metadata: { action: 'use_current_location' },
      });
      locationError.value = '';
      locating.value = false;
    },
    (err) => {
      if (err?.code === 1) {
        locationError.value = t('cartPage.locationPermissionDenied');
      } else if (err?.code === 3) {
        locationError.value = t('cartPage.locationRequestTimedOut');
      } else {
        locationError.value = t('cartPage.unableToCaptureLocation');
      }
      locating.value = false;
    },
    {
      enableHighAccuracy: true,
      timeout: 12000,
      maximumAge: 60000,
    }
  );
};

const openExternalMap = () => {
  const lat = parseCoordinateValue(deliveryLat.value);
  const lng = parseCoordinateValue(deliveryLng.value);
  const url =
    lat !== null && lng !== null
      ? `https://www.google.com/maps/search/?api=1&query=${lat},${lng}`
      : 'https://www.google.com/maps';
  window.open(url, '_blank', 'noopener,noreferrer');
  trackEvent('contact_click', {
    source: 'cart_delivery_location',
    metadata: { action: 'open_external_map' },
  });
  // Highlight the paste button for 30 s so user knows what to do next
  waitingForPaste.value = true;
  clearTimeout(waitingForPasteTimer);
  waitingForPasteTimer = setTimeout(() => { waitingForPaste.value = false; }, 30000);
  toast.show(t('cartPage.openMapsInstruction'), 'info');
};

const pasteMapLink = async () => {
  waitingForPaste.value = false;
  clearTimeout(waitingForPasteTimer);
  try {
    if (navigator.clipboard?.readText) {
      const text = await navigator.clipboard.readText();
      if (!text?.trim()) {
        deliveryUrlInputRef.value?.focus();
        toast.show(t('cartPage.clipboardEmpty'), 'info');
        return;
      }
      deliveryLocationUrl.value = text.trim();
      clearFieldError('delivery_location_url');
      toast.show(t('cartPage.mapLinkPasted'), 'success');
    } else {
      // Clipboard API unavailable — focus field for manual Ctrl+V
      deliveryUrlInputRef.value?.focus();
      toast.show(t('cartPage.pasteMapLinkManually'), 'info');
    }
  } catch {
    // Permission denied — focus field for manual paste
    deliveryUrlInputRef.value?.focus();
    toast.show(t('cartPage.pasteMapLinkManually'), 'info');
  }
};

const validateForm = () => {
  if (isTableContextOrder.value) {
    fieldErrors.value = {};
    return true;
  }

  // Delivery minimum order check
  if (fulfillmentType.value === 'delivery' && deliveryMinOrder.value > 0 && Number(cart.total) < deliveryMinOrder.value) {
    toast.show(t('cartPage.deliveryMinOrderNotMet', {
      amount: formatPrice(deliveryMinOrder.value),
    }), 'error');
    return false;
  }

  // All non-table orders require a signed-in customer
  if (!customerStore.isAuthenticated) {
    showAuthModal.value = true;
    return false;
  }
  // Delivery also requires a verified account
  if (fulfillmentType.value === 'delivery' && !customerStore.isVerified) {
    toast.show(t('cartPage.deliveryNotVerified'), 'error');
    return false;
  }
  // Delivery requires a phone number so the driver can reach the customer
  if (fulfillmentType.value === 'delivery' && !customerStore.customer?.phone) {
    toast.show(t('cartPage.deliveryPhoneRequired'), 'error');
    return false;
  }

  const errors = {};
  if (!fulfillmentType.value) {
    errors.fulfillment_type = t('cartPage.selectPickupOrDelivery');
  }
  if (fulfillmentType.value === 'delivery') {
    if (!deliveryAddress.value && !deliveryLocationUrl.value.trim()) {
      errors.delivery_address = t('cartPage.deliveryAddressRequiredError');
    }
    const latValue = parseCoordinateValue(deliveryLat.value);
    const lngValue = parseCoordinateValue(deliveryLng.value);
    const hasLat = latValue !== null;
    const hasLng = lngValue !== null;
    if (hasLat && (latValue < -90 || latValue > 90)) {
      errors.delivery_lat = t('cartPage.latitudeRangeError');
    }
    if (hasLng && (lngValue < -180 || lngValue > 180)) {
      errors.delivery_lng = t('cartPage.longitudeRangeError');
    }
    if (hasLat !== hasLng) {
      errors.delivery_lat = t('cartPage.latLngTogetherError');
      errors.delivery_lng = t('cartPage.latLngTogetherError');
    }
    if (!hasLocationCoords.value && !deliveryLocationUrl.value.trim()) {
      errors.delivery_location_url = t(
        'cartPage.provideMapLinkOrCurrentLocation'
      );
    }
  }

  fieldErrors.value = errors;
  if (Object.keys(errors).length) {
    toast.show(t('cartPage.completeRequiredOrderDetails'), 'error');
    return false;
  }
  return true;
};

const applyPromoCode = async () => {
  const code = promoCode.value.trim().toUpperCase();
  if (!code) return;
  promoError.value = '';
  promoChecking.value = true;
  try {
    const res = await api.get(`/promo-code-check/?code=${encodeURIComponent(code)}`);
    if (res.data?.valid) {
      promoApplied.value = res.data;
      promoError.value = '';
    } else {
      promoApplied.value = null;
      promoError.value = res.data?.detail || t('cartPage.promoInvalid');
    }
  } catch {
    promoApplied.value = null;
    promoError.value = t('cartPage.promoCheckFailed');
  } finally {
    promoChecking.value = false;
  }
};

const removePromoCode = () => {
  promoApplied.value = null;
  promoCode.value = '';
  promoError.value = '';
};

const buildPayload = () => {
  const payload = {
    items: cart.items.map((item) => ({
      slug: item.slug,
      qty: item.qty,
      ...(Array.isArray(item.option_ids) && item.option_ids.length
        ? { option_ids: item.option_ids }
        : {}),
      ...(item.note ? { note: item.note } : {}),
    })),
  };

  if (customerNote.value) payload.customer_note = customerNote.value;
  if (useWallet.value && canPayWithCredits.value) payload.use_wallet = true;
  if (promoApplied.value) payload.promo_code = promoCode.value.trim().toUpperCase();
  if (tipAmount.value > 0) payload.tip_amount = tipAmount.value;
  if (cart.tableLabel) payload.table_label = cart.tableLabel;
  if (cart.tableSlug) payload.table_slug = cart.tableSlug;
  // customer_name: only for table context (optional)
  if (isTableContextOrder.value && cart.customerName) payload.customer_name = cart.customerName;
  // customer_phone no longer sent (anonymous pickup, delivery uses customer profile)

  if (!isTableContextOrder.value) {
    if (fulfillmentType.value) payload.fulfillment_type = fulfillmentType.value;
    if (isDelivery.value) {
      const latValue = parseCoordinateValue(deliveryLat.value);
      const lngValue = parseCoordinateValue(deliveryLng.value);
      if (deliveryAddress.value)
        payload.delivery_address = deliveryAddress.value;
      if (deliveryLocationUrl.value)
        payload.delivery_location_url = deliveryLocationUrl.value;
      if (latValue !== null && lngValue !== null) {
        payload.delivery_lat = Number(latValue.toFixed(6));
        payload.delivery_lng = Number(lngValue.toFixed(6));
      }
    }
  }
  return payload;
};

const assignFieldErrors = (data) => {
  if (!data || typeof data !== 'object') return;
  const mapped = {};
  const keys = [
    'fulfillment_type',
    'customer_name',
    'customer_phone',
    'delivery_address',
    'delivery_location_url',
    'delivery_lat',
    'delivery_lng',
  ];
  keys.forEach((key) => {
    const value = data[key];
    if (Array.isArray(value) && value.length) {
      mapped[key] = String(value[0]);
    } else if (typeof value === 'string' && value.trim()) {
      mapped[key] = value.trim();
    }
  });
  if (Object.keys(mapped).length) {
    fieldErrors.value = { ...fieldErrors.value, ...mapped };
  }
};

const mapOrderApiError = (err, fallback) => {
  const data = err?.response?.data || {};
  const code = data?.code || '';
  const unavailable = Array.isArray(data?.unavailable_slugs)
    ? data.unavailable_slugs
    : [];
  unavailableSlugs.value = unavailable;
  const note =
    typeof data?.note === 'string' && data.note.trim() ? data.note.trim() : '';

  assignFieldErrors(data);

  if (code === 'promo_not_found' || code === 'promo_invalid') {
    promoApplied.value = null;
    return data?.detail || t('cartPage.promoInvalid');
  }
  if (code === 'auth_required') {
    showAuthModal.value = true;
    return t('cartPage.deliveryAuthRequired');
  }
  if (code === 'not_verified') {
    return t('cartPage.deliveryNotVerified');
  }
  if (code === 'phone_required') {
    return t('cartPage.deliveryPhoneRequired');
  }
  if (code === 'items_unavailable' && unavailable.length) {
    return t('cartPage.itemsUnavailable', { items: unavailable.join(', ') });
  }
  if (code === 'plan_forbidden' || code === 'plan_forbidden_checkout') {
    return t('cartPage.actionNotAvailableOnPlan');
  }
  if (code === 'menu_unpublished') {
    return t('cartPage.menuNotPublishedYet');
  }
  if (code === 'restaurant_closed') {
    return t('cartPage.restaurantCurrentlyClosed');
  }
  if (code === 'contact_missing') {
    return t('cartPage.restaurantContactNotConfigured');
  }
  if (code === 'table_unavailable') {
    return t('cartPage.tableQrUnavailable');
  }
  if (code === 'mixed_currency') {
    return t('cartPage.mixedCurrency');
  }
  if (code === 'menu_temporarily_disabled') {
    return note
      ? t('cartPage.menuTemporarilyUnavailableWithNote', { note })
      : t('cartPage.menuTemporarilyUnavailable');
  }
  if (data && typeof data === 'object') {
    const firstList = Object.values(data).find(
      (v) => Array.isArray(v) && v.length
    );
    if (firstList) return String(firstList[0]);
  }
  if (typeof data?.detail === 'string' && data.detail.trim()) {
    return data.detail;
  }
  return fallback;
};

const removeUnavailable = () => {
  if (!unavailableSlugs.value.length) return;
  const blocked = new Set(unavailableSlugs.value);
  const toRemove = cart.items
    .filter((item) => blocked.has(item.slug))
    .map((item) => item.key);
  toRemove.forEach((key) => cart.remove(key));
  unavailableSlugs.value = [];
  toast.show(t('cartPage.unavailableItemsRemoved'), 'success');
};

const startCheckout = async () => {
  checkoutError.value = '';
  handoffError.value = '';
  unavailableSlugs.value = [];
  fieldErrors.value = {};
  if (!cart.canCheckout) return;
  if (!cart.items.length) {
    toast.show(t('cartPage.cartEmpty'), 'error');
    return;
  }
  if (!validateForm()) return;

  processingCheckout.value = true;
  try {
    trackEvent('checkout_click', {
      source: 'cart_checkout',
      metadata: {
        items_count: cart.count,
        total: cart.total,
        currency: currency.value,
      },
    });
    const res = await api.post('/checkout-intent/', buildPayload());
    const data = res?.data || {};
    if (safeExternalUrl(data.checkout_url)) {
      window.open(safeExternalUrl(data.checkout_url), '_blank', 'noopener,noreferrer');
      toast.show(t('cartPage.openingCheckout'), 'success');
      return;
    }
    const detail = data.detail || t('cartPage.checkoutNotConfigured');
    checkoutError.value = detail;
    toast.show(detail, 'info');
  } catch (err) {
    const detail = mapOrderApiError(err, t('cartPage.unableToStartCheckout'));
    checkoutError.value = detail;
    toast.show(detail, 'error');
  } finally {
    processingCheckout.value = false;
  }
};

const openWhatsApp = async () => {
  handoffError.value = '';
  checkoutError.value = '';
  unavailableSlugs.value = [];
  fieldErrors.value = {};
  if (!cart.canWhatsapp) return;
  if (!cart.items.length) {
    toast.show(t('cartPage.cartEmpty'), 'error');
    return;
  }
  if (!validateForm()) return;

  sendingWhatsapp.value = true;
  try {
    trackEvent('order_handoff_click', {
      source: 'cart_whatsapp',
      metadata: {
        items_count: cart.count,
        total: cart.total,
        currency: currency.value,
      },
    });
    const res = await api.post('/order-handoff/', buildPayload());
    const url = safeExternalUrl(res?.data?.url);
    if (!url) throw new Error(t('cartPage.missingWhatsappHandoffUrl'));
    window.open(url, '_blank', 'noopener,noreferrer');
    toast.show(t('cartPage.openingWhatsApp'), 'success');
  } catch (err) {
    const detail = mapOrderApiError(
      err,
      t('cartPage.unableToPrepareWhatsAppOrder')
    );
    handoffError.value = detail;
    toast.show(detail, 'error');
  } finally {
    sendingWhatsapp.value = false;
  }
};

const placeInAppOrder = async () => {
  placeOrderError.value = '';
  handoffError.value = '';
  checkoutError.value = '';
  unavailableSlugs.value = [];
  fieldErrors.value = {};
  if (isBrowseOnlyPlan.value) return;
  if (!cart.items.length) {
    toast.show(t('cartPage.cartEmpty'), 'error');
    return;
  }
  if (!validateForm()) return;

  placingOrder.value = true;
  try {
    trackEvent('place_order_click', {
      source: 'cart_in_app',
      metadata: {
        items_count: cart.count,
        total: cart.total,
        currency: currency.value,
      },
    });
    const result = await order.placeOrder(buildPayload());
    // Save to recent orders BEFORE clearing the cart so we still have item data
    cart.pushRecentOrder({
      order_number: result.order_number,
      total: result.total ?? cart.total,
      currency: result.currency ?? currency.value,
      created_at: result.created_at ?? new Date().toISOString(),
      items: cart.items,
    });
    cart.clear();
    // Persist the order number so the layout can show a "track order" banner
    try {
      localStorage.setItem('lastOrderNumber', result.order_number);
      localStorage.setItem('lastOrderAt', String(Date.now()));
    } catch {}
    // Optionally save the delivery address for future use
    if (isDelivery.value && saveAddressAfterOrder.value && deliveryAddress.value) {
      try {
        await api.post('/customer/addresses/', {
          label: saveAddressLabel.value.trim() || '',
          address: deliveryAddress.value,
          location_url: deliveryLocationUrl.value || '',
          lat: deliveryLat.value,
          lng: deliveryLng.value,
        });
      } catch { /* non-critical */ }
    }
    toast.show(t('cartPage_order.placeOrderSuccess'), 'success');
    router.push({ name: 'order-status', params: { orderNumber: result.order_number } });
  } catch (err) {
    const detail = mapOrderApiError(err, t('cartPage_order.placeOrderError'));
    placeOrderError.value = detail;
    toast.show(detail, 'error');
  } finally {
    placingOrder.value = false;
  }
};

const onCustomerAuthenticated = (customer) => {
  customerStore.setCustomer(customer);
  toast.show(t('cartPage.signedIn'), 'success');
};

const handleEscapeKey = (event) => {
  if (showAuthModal.value) {
    if (event?.key === 'Escape') showAuthModal.value = false;
    return;
  }
  if (!showMapModal.value) return;
  if (event?.key !== 'Escape') return;
  closeMapModal();
};

onMounted(() => {
  customerStore.fetchCustomer(); // no-op if layout already fetched it
  fetchSavedAddresses();
  trackEvent(
    'cart_view',
    { source: 'customer_cart' },
    { onceKey: 'cart:view' }
  );
  if (typeof window !== 'undefined') {
    window.addEventListener('keydown', handleEscapeKey);
  }
});

onBeforeUnmount(() => {
  if (typeof window !== 'undefined') {
    window.removeEventListener('keydown', handleEscapeKey);
  }
  document.removeEventListener('keydown', trapMapFocus);
  clearTimeout(waitingForPasteTimer);
  if (leafletMap.value) {
    leafletMap.value.remove();
    leafletMap.value = null;
    leafletMarker.value = null;
  }
  leafletModuleRef.value = null;
});
</script>
