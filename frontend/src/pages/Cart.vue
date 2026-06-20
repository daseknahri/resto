<template>
  <div class="space-y-3 px-3 py-2 pb-28 sm:space-y-4 sm:px-4 sm:py-4 sm:pb-6 ui-safe-bottom">

    <!-- ── Header ──────────────────────────────────────────────────────────── -->
    <header class="ui-hero-ribbon ui-reveal px-4 py-4 md:px-5 md:py-5">
      <div class="flex items-center justify-between gap-3">
        <div class="flex flex-wrap items-center gap-x-3 gap-y-2">
          <div>
            <p class="ui-kicker">{{ t('cartPage.kicker') }}</p>
            <h1 class="ui-display text-2xl font-bold tracking-tight text-white md:text-3xl leading-tight">
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
          <AppIcon name="close" class="h-3.5 w-3.5" aria-hidden="true" />
          {{ t('common.clear') }}
        </button>
      </div>
    </header>

    <!-- ── Restaurant closed notice ─────────────────────────────────────────── -->
    <div
      v-if="!isRestaurantOpen && !isBrowseOnlyPlan"
      class="ui-section-band border-amber-500/40 bg-amber-500/10 px-4 py-3 text-amber-100 space-y-0.5"
      role="status"
    >
      <p class="text-sm font-semibold">{{ t('cartPage.restaurantClosed') }}</p>
      <p class="text-xs text-amber-200/75">{{ t('cartPage.restaurantClosedBody') }}</p>
    </div>

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
      class="ui-empty-state ui-reveal text-center space-y-2"
    >
      <p class="text-base font-semibold text-slate-100">{{ t('cartPage.cartEmpty') }}</p>
      <p class="text-sm text-slate-400">{{ t('cartPage.cartEmptyBody') }}</p>
      <RouterLink :to="{ name: 'menu' }" class="ui-btn-primary mt-4 inline-flex items-center gap-1.5 px-6 py-2.5 text-sm font-semibold tracking-wide">
        <AppIcon name="menu" class="h-4 w-4" />{{ t('cartPage.browseMenu') }}
      </RouterLink>
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
          class="ui-panel ui-surface-lift ui-reveal relative overflow-hidden pl-4 pr-3.5 py-3.5"
          :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
        >
          <!-- left accent bar -->
          <div
            class="pointer-events-none absolute inset-y-0 start-0 w-[3px] ltr:rounded-l-xl rtl:rounded-r-xl"
            style="background: linear-gradient(to bottom, rgba(245,158,11,0.55), rgba(245,158,11,0.10))"
          />
          <div class="flex items-center gap-3">
            <!-- Name + meta -->
            <div class="min-w-0 flex-1">
              <p class="truncate text-sm font-semibold leading-snug text-slate-100 tracking-tight" :title="item.name">{{ item.name }}</p>
              <p v-if="item.note" class="mt-1 text-[11px] text-slate-400 truncate" :title="item.note">{{ item.note }}</p>
              <p v-else-if="item.option_labels?.length" class="mt-1 text-[11px] text-slate-400 truncate" :title="item.option_labels.join(' · ')">{{ item.option_labels.join(' · ') }}</p>
              <p class="mt-1 text-[11px] text-slate-500">{{ formatPrice(item.price) }} {{ t('cartPage.each') }}</p>
            </div>
            <!-- Stepper pill -->
            <div class="inline-flex shrink-0 items-center rounded-full border border-slate-700/60 bg-slate-900/60">
              <button
                class="ui-press flex h-10 w-10 items-center justify-center rounded-full text-slate-300 transition-colors select-none hover:bg-slate-800 focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/40 focus:outline-none"
                :aria-label="t('cartPage.decreaseQuantity')"
                @click="cart.decrement(item.key)"
              >
                <span class="text-base leading-none" aria-hidden="true">−</span>
              </button>
              <span class="w-7 text-center text-sm font-bold text-slate-100 select-none tabular-nums" aria-live="polite">{{ item.qty }}</span>
              <button
                class="ui-press flex h-10 w-10 items-center justify-center rounded-full text-slate-300 transition-colors select-none hover:bg-slate-800 focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/40 focus:outline-none"
                :aria-label="t('cartPage.increaseQuantity')"
                @click="cart.increment(item.key)"
              >
                <span class="text-base leading-none" aria-hidden="true">+</span>
              </button>
            </div>
            <!-- Subtotal + remove -->
            <div class="shrink-0 min-w-[4.5rem] text-right">
              <p class="text-sm font-bold tabular-nums text-[var(--color-secondary)]">{{ formatPrice(item.price * item.qty) }}</p>
              <button
                class="mt-1 px-2 py-1 text-[11px] text-slate-500 hover:text-red-400 transition-colors focus-visible:text-red-400 focus:outline-none rounded-md"
                :aria-label="`${t('cartPage.remove')} ${item.name}`"
                @click="cart.remove(item.key)"
              >{{ t('cartPage.remove') }}</button>
            </div>
          </div>
        </article>

        <!-- Unavailable items warning -->
        <div
          v-if="unavailableSlugs.length"
          role="alert"
          class="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-amber-500/40 bg-amber-500/10 px-3 py-2.5 text-xs text-amber-100"
        >
          <p class="min-w-0 flex-1">{{ t('cartPage.unavailableItemsDetected', { items: unavailableNames.join(', ') }) }}</p>
          <button class="shrink-0 ui-btn-outline px-2.5 py-1 text-xs" @click="removeUnavailable">
            <AppIcon name="close" class="h-3 w-3" aria-hidden="true" />
            {{ t('cartPage.removeUnavailableItems') }}
          </button>
        </div>
      </div>

      <!-- ── Right: order panel ──────────────────────────────────────────── -->
      <aside
        v-if="!isBrowseOnlyPlan"
        class="ui-reveal xl:sticky xl:top-[calc(var(--safe-top)+5.75rem)] xl:self-start"
        :style="{ '--ui-delay': '84ms' }"
      >
        <section class="ui-glass p-4 sm:p-5 space-y-4">

          <!-- Compact total header -->
          <div class="flex items-center justify-between gap-3 rounded-xl bg-slate-900/60 px-4 py-3.5 border border-slate-800/60">
            <div>
              <p class="text-[10px] font-medium uppercase tracking-widest text-slate-500">{{ t('cartPage.total') }}</p>
              <p class="text-3xl font-bold tabular-nums leading-tight text-[var(--color-secondary)]">
                {{ formatPrice(orderGrandTotal) }}
              </p>
            </div>
            <div class="text-right text-[11px] text-slate-500 space-y-0.5">
              <p class="font-medium text-slate-400">{{ itemCountLabel(cart.count) }}</p>
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
                class="relative flex items-center gap-2 rounded-xl border px-3 py-2 text-xs font-semibold transition-all focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/40 focus:outline-none"
                :aria-pressed="fulfillmentType === 'pickup'"
                :class="fulfillmentType === 'pickup'
                  ? 'border-[var(--color-secondary)]/55 bg-[var(--color-secondary)]/10 text-[var(--color-secondary)]'
                  : 'border-slate-700/60 bg-slate-900/40 text-slate-400 hover:border-slate-600 hover:text-slate-200'"
                @click="fulfillmentType = 'pickup'"
              >
                <AppIcon name="menu" class="h-3.5 w-3.5 shrink-0" />
                {{ t('cartPage.pickup') }}
                <span v-if="fulfillmentType === 'pickup'" class="ms-auto h-1.5 w-1.5 rounded-full bg-[var(--color-secondary)]" />
              </button>
              <!-- Delivery pill -->
              <button
                v-if="deliveryEnabled"
                class="relative flex items-center gap-2 rounded-xl border px-3 py-2 text-xs font-semibold transition-all focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/40 focus:outline-none"
                :aria-pressed="fulfillmentType === 'delivery'"
                :class="fulfillmentType === 'delivery'
                  ? 'border-[var(--color-secondary)]/55 bg-[var(--color-secondary)]/10 text-[var(--color-secondary)]'
                  : 'border-slate-700/60 bg-slate-900/40 text-slate-400 hover:border-slate-600 hover:text-slate-200'"
                @click="fulfillmentType = 'delivery'"
              >
                <AppIcon name="table" class="h-3.5 w-3.5 shrink-0" />
                {{ t('cartPage.delivery') }}
                <span v-if="fulfillmentType === 'delivery'" class="ms-auto h-1.5 w-1.5 rounded-full bg-[var(--color-secondary)]" />
              </button>
            </div>
            <p v-if="fieldErrors.fulfillment_type" id="cart-fulfillment-error" role="alert" class="text-xs text-red-300">{{ fieldErrors.fulfillment_type }}</p>

            <!-- ── When: ASAP vs scheduled (pickup/delivery only) ── -->
            <div v-if="canSchedule" class="space-y-2 rounded-xl border border-slate-700/50 bg-slate-950/40 p-3">
              <p class="text-xs font-semibold text-slate-300">{{ t('cartPage.whenTitle') }}</p>
              <div class="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  class="rounded-xl border px-3 py-2 text-xs font-semibold transition-all focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/40 focus:outline-none"
                  :aria-pressed="!scheduleEnabled"
                  :class="!scheduleEnabled
                    ? 'border-[var(--color-secondary)]/55 bg-[var(--color-secondary)]/10 text-[var(--color-secondary)]'
                    : 'border-slate-700/60 bg-slate-900/40 text-slate-400 hover:border-slate-600 hover:text-slate-200'"
                  @click="scheduleEnabled = false"
                >
                  {{ t('cartPage.scheduleAsap') }}
                </button>
                <button
                  type="button"
                  class="rounded-xl border px-3 py-2 text-xs font-semibold transition-all focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/40 focus:outline-none"
                  :aria-pressed="scheduleEnabled"
                  :class="scheduleEnabled
                    ? 'border-[var(--color-secondary)]/55 bg-[var(--color-secondary)]/10 text-[var(--color-secondary)]'
                    : 'border-slate-700/60 bg-slate-900/40 text-slate-400 hover:border-slate-600 hover:text-slate-200'"
                  @click="scheduleEnabled = true"
                >
                  {{ t('cartPage.scheduleLater') }}
                </button>
              </div>
              <div v-if="scheduleEnabled" class="space-y-1">
                <input
                  v-model="scheduledFor"
                  type="datetime-local"
                  :min="minScheduleDatetime"
                  :aria-label="t('cartPage.scheduleLater')"
                  class="w-full rounded-xl border border-slate-700/60 bg-slate-900/40 px-3 py-2 text-sm text-slate-100 focus:border-[var(--color-secondary)]/55 focus:outline-none"
                />
                <p class="text-[11px] text-slate-500">{{ t('cartPage.scheduleHint') }}</p>
                <p v-if="fieldErrors.scheduled_for" class="text-xs text-red-300">{{ fieldErrors.scheduled_for }}</p>
              </div>
            </div>

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
                    <button class="min-w-0 flex-1 text-start hover:text-indigo-300 transition-colors focus-visible:underline focus:outline-none" @click="applySavedAddress(addr)">
                      <span v-if="addr.label" class="font-medium text-slate-200 me-1.5">{{ addr.label }}</span>
                      <span class="text-slate-400 truncate" :title="addr.address">{{ addr.address }}</span>
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
                  {{ deliveryMinGap > 0
                    ? t('cartPage.deliveryMinAddMore', { amount: formatPrice(deliveryMinGap) })
                    : t('cartPage.deliveryMinOrderLabel', { amount: formatPrice(deliveryMinOrder) }) }}
                </span>
              </div>

              <!-- Delivery fee note (distance-aware) -->
              <div v-if="deliveryOutOfRange" class="flex items-start gap-1.5 text-[11px] text-rose-300">
                <AppIcon name="info" class="h-3 w-3 shrink-0 mt-px" />
                {{ t('cartPage.deliveryOutOfRange', { km: deliveryPricing.radiusKm }) }}
              </div>
              <div v-else-if="deliveryIsFree" class="flex items-center gap-1.5 text-[11px] text-emerald-400">
                <AppIcon name="check" class="h-3 w-3 shrink-0" />
                {{ t('cartPage.deliveryFee') }}: {{ t('cartPage.free') }}
              </div>
              <div v-else-if="deliveryFeeIsDistance" class="flex items-center gap-1.5 text-[11px] text-slate-400">
                <AppIcon name="location" class="h-3 w-3 shrink-0" />
                {{ t('cartPage.deliveryFeeDistance', { fee: formatPrice(deliveryFeeAmount), km: deliveryDistanceKm }) }}
              </div>
              <div v-else-if="deliveryPricing.perKm > 0" class="flex items-center gap-1.5 text-[11px] text-slate-400">
                <AppIcon name="location" class="h-3 w-3 shrink-0" />
                {{ t('cartPage.deliveryFeeByDistance') }}
              </div>
              <div v-else-if="deliveryFeeAmount === 0" class="flex items-center gap-1.5 text-[11px] text-emerald-400">
                <AppIcon name="check" class="h-3 w-3 shrink-0" />
                {{ t('cartPage.deliveryFee') }}: {{ t('cartPage.free') }}
              </div>
              <div v-else class="flex items-center gap-1.5 text-[11px] text-slate-400">
                <AppIcon name="truck" class="h-3 w-3 shrink-0" />
                {{ t('cartPage.deliveryFee') }}: {{ formatPrice(deliveryFeeAmount) }}
              </div>

              <!-- ── Delivery location ── -->
              <div class="space-y-2">
                <p class="text-xs font-semibold text-slate-300">{{ t('cartPage.deliveryLocationTitle') }}</p>

                <!-- Primary: use current location (fastest path) -->
                <button
                  class="ui-btn-primary w-full justify-center py-2.5 text-sm disabled:opacity-50"
                  :disabled="locating"
                  aria-describedby="cart-location-error"
                  @click="useCurrentLocation"
                >
                  <AppIcon name="location" class="h-4 w-4" />
                  {{ locating ? t('cartPage.locating') : t('cartPage.useCurrentLocation') }}
                </button>

                <!-- Secondary actions -->
                <div class="flex flex-wrap gap-1.5">
                  <button
                    class="inline-flex items-center gap-1 rounded-full border border-slate-700/60 bg-slate-800/50 px-2.5 py-1 text-[11px] text-slate-300 hover:border-slate-500 hover:text-slate-100 transition-colors"
                    @click="openInAppMapPicker"
                  >
                    <AppIcon name="table" class="h-3 w-3 shrink-0" />
                    {{ t('cartPage.pickPinInApp') }}
                  </button>
                  <button
                    class="inline-flex items-center gap-1 rounded-full border border-slate-700/60 bg-slate-800/50 px-2.5 py-1 text-[11px] text-slate-400 hover:border-slate-500 hover:text-slate-200 transition-colors"
                    :aria-expanded="showMoreLocationOptions || !!deliveryLocationUrl"
                    @click="showMoreLocationOptions = !showMoreLocationOptions"
                  >
                    {{ t('cartPage.moreLocationOptions') }}
                    <span aria-hidden="true" class="text-[10px]">{{ (showMoreLocationOptions || deliveryLocationUrl) ? '▾' : '▸' }}</span>
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
                <p v-if="locationError" id="cart-location-error" role="alert" class="text-xs text-red-300">{{ locationError }}</p>

                <!-- More options: paste a map link (collapsed by default) -->
                <div v-show="showMoreLocationOptions || deliveryLocationUrl" class="space-y-1 pt-1">
                  <button
                    type="button"
                    class="inline-flex items-center gap-1 text-[11px] text-slate-400 hover:text-slate-200 transition-colors"
                    @click="openExternalMap"
                  >
                    <AppIcon name="link" class="h-3 w-3 shrink-0" />
                    {{ t('cartPage.openExternalMap') }}
                  </button>
                  <span class="block text-[11px] text-slate-400">{{ t('cartPage.mapPinUrlOptional') }}</span>
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
                      class="shrink-0 rounded-xl border px-3 py-2 text-xs font-semibold transition-all focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/40 focus:outline-none"
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
                  <input v-model="saveAddressAfterOrder" type="checkbox" class="rounded" />
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
                  :aria-expanded="locationAdvancedOpen"
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
                  class="ui-press flex-1 rounded-lg border py-1 text-[11px] font-semibold transition-colors focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/40 focus:outline-none"
                  :class="tipPercent === opt.value
                    ? 'border-[var(--color-secondary)]/70 bg-[var(--color-secondary)]/15 text-[var(--color-secondary)]'
                    : 'border-slate-700 bg-slate-800/50 text-slate-400 hover:border-slate-600 hover:text-slate-200'"
                  :aria-pressed="tipPercent === opt.value"
                  @click="setTipPercent(opt.value)"
                >{{ opt.label }}</button>
              </div>
              <span
                v-if="tipAmount > 0"
                class="shrink-0 text-xs font-semibold tabular-nums text-[var(--color-secondary)]"
              >+{{ formatPrice(tipAmount) }}</span>
            </div>
            <!-- Custom tip input -->
            <div v-if="tipPercent === 'custom'" class="space-y-1.5">
              <div class="flex items-center gap-2">
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
              <p v-if="tipHighWarning" class="text-[10px] text-amber-400/80 ps-0.5">
                ⚠ {{ t('cartPage.tipHighWarning') }}
              </p>
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
                class="flex items-center gap-1.5 text-xs font-medium text-slate-400 hover:text-[var(--color-secondary)] transition-colors"
                :aria-expanded="promoOpen"
                @click="promoOpen = !promoOpen"
              >
                <AppIcon name="tag" class="h-3.5 w-3.5" aria-hidden="true" />
                {{ t('cartPage.promoCodeCta') }}
                <span aria-hidden="true" class="text-slate-600 text-[11px]">{{ promoOpen ? '▾' : '▸' }}</span>
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
                  class="inline-flex shrink-0 items-center gap-1 rounded-xl border border-slate-600 bg-slate-800/60 px-3 py-2 text-xs font-semibold text-slate-300 hover:border-indigo-500/60 hover:text-indigo-300 transition-colors disabled:opacity-50"
                  :disabled="promoChecking || !promoCode.trim()"
                  :aria-busy="promoChecking"
                  @click="applyPromoCode"
                >
                  <svg v-if="promoChecking" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3 w-3 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
                  {{ promoChecking ? t('common.loading') : t('cartPage.promoApply') }}
                </button>
              </div>
              <p v-if="promoError" id="cart-promo-error" class="mt-1 text-[10px] text-red-300">{{ promoError }}</p>
            </template>
          </div>

          <!-- ── Pay now (pickup/delivery) ── -->
          <div v-if="requiresPrepay && customerStore.isAuthenticated && orderGrandTotal > 0" class="space-y-2">
            <!-- Trusted customers: choose wallet or cash on handover -->
            <div v-if="codEligible" class="grid grid-cols-2 gap-2">
              <button
                type="button"
                class="rounded-xl border px-3 py-2 text-xs font-semibold transition-colors focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/40 focus:outline-none"
                :class="paymentMethod === 'wallet' ? 'border-[var(--color-secondary)] bg-[var(--color-secondary)]/10 text-[var(--color-secondary)]' : 'border-slate-700 text-slate-300 hover:border-slate-500'"
                :aria-pressed="paymentMethod === 'wallet'"
                @click="paymentMethod = 'wallet'"
              >{{ t('cartPage.payMethodWallet') }}</button>
              <button
                type="button"
                class="rounded-xl border px-3 py-2 text-xs font-semibold transition-colors focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/40 focus:outline-none"
                :class="paymentMethod === 'cash' ? 'border-[var(--color-secondary)] bg-[var(--color-secondary)]/10 text-[var(--color-secondary)]' : 'border-slate-700 text-slate-300 hover:border-slate-500'"
                :aria-pressed="paymentMethod === 'cash'"
                @click="paymentMethod = 'cash'"
              >{{ t('cartPage.payMethodCash') }}</button>
            </div>

            <!-- Cash on handover panel -->
            <div v-if="codChosen" class="rounded-xl border border-emerald-500/30 bg-emerald-500/8 p-3">
              <p class="text-xs font-semibold text-emerald-300">{{ t('cartPage.payCashOnHandoverTitle') }}</p>
              <p class="mt-0.5 text-[11px] text-slate-400">{{ t('cartPage.payCashOnHandoverNote') }}</p>
            </div>

            <!-- Wallet panel -->
            <div
              v-else
              class="rounded-xl border p-3"
              :class="walletCoversTotal ? 'border-emerald-500/30 bg-emerald-500/8' : 'border-amber-500/40 bg-amber-500/8'"
            >
              <div class="flex items-center justify-between gap-3">
                <div>
                  <p class="text-xs font-semibold" :class="walletCoversTotal ? 'text-emerald-300' : 'text-amber-300'">
                    {{ t('cartPage.payFromWalletTitle') }}
                  </p>
                  <p class="text-[11px] text-slate-400">{{ t('cartPage.payWithCreditsBalance', { balance: walletBalance }) }}</p>
                </div>
                <AppIcon :name="walletCoversTotal ? 'check' : 'info'" class="h-4 w-4 shrink-0" :class="walletCoversTotal ? 'text-emerald-400' : 'text-amber-400'" />
              </div>
              <p v-if="!walletCoversTotal" class="mt-1.5 text-[11px] text-amber-200">
                {{ t('cartPage.walletShortNotice', { amount: formatPrice(orderGrandTotal - walletBalance) }) }}
              </p>
              <RouterLink
                v-if="prepayShortfall"
                :to="{ name: 'customer-account' }"
                class="mt-2 inline-flex items-center gap-1 text-[11px] font-semibold text-amber-300 underline decoration-amber-300/40 underline-offset-2 hover:text-amber-200 transition-colors"
              >
                {{ t('cartPage.topUpWallet') }}
                <AppIcon name="arrowRight" class="h-3 w-3 rtl:scale-x-[-1]" aria-hidden="true" />
              </RouterLink>
            </div>
          </div>

          <!-- ── Wallet credits (opt-in for dine-in tabs) ── -->
          <div
            v-else-if="canPayWithCredits"
            class="rounded-xl border p-3 transition-colors"
            :class="useWallet
              ? 'border-[var(--color-secondary)]/50 bg-[var(--color-secondary)]/8'
              : 'border-slate-700/60 bg-slate-900/30'"
          >
            <div class="flex cursor-pointer items-center justify-between gap-3">
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
            </div>
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
                <AppIcon name="close" class="h-3.5 w-3.5" aria-hidden="true" />
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

          <!-- ── Loyalty redemption ── -->
          <label
            v-if="loyaltyAvailable"
            class="flex cursor-pointer items-center gap-2.5 rounded-xl border border-amber-500/30 bg-amber-500/5 px-3 py-2.5"
          >
            <input v-model="useLoyalty" type="checkbox" class="h-4 w-4 rounded border-slate-600 bg-slate-900 text-amber-500 focus:ring-amber-500/40" />
            <span class="flex-1 text-xs text-amber-200">{{ t('cartPage.loyaltyRedeem', { points: loyaltyPoints }) }}</span>
            <span v-if="useLoyalty && loyaltyDiscount > 0" class="text-xs font-semibold tabular-nums text-amber-300">-{{ formatPrice(loyaltyDiscount) }}</span>
          </label>

          <!-- ── Order summary breakdown ── -->
          <div class="border-t border-slate-800/50 pt-3 space-y-2 text-xs">
            <div v-if="fulfillmentType === 'delivery' && deliveryFeeAmount > 0" class="flex items-center justify-between text-slate-400">
              <span>{{ t('cartPage.subtotal') }}</span>
              <span class="tabular-nums font-medium">{{ formatPrice(cart.total) }}</span>
            </div>
            <div v-if="loyaltyDiscount > 0" class="flex items-center justify-between text-amber-300">
              <span>{{ t('cartPage.loyaltyDiscount') }}</span>
              <span class="tabular-nums font-semibold">-{{ formatPrice(loyaltyDiscount) }}</span>
            </div>
            <div v-if="fulfillmentType === 'delivery' && deliveryFeeAmount > 0" class="flex items-center justify-between text-slate-300">
              <span>
                {{ t('cartPage.deliveryFee') }}
                <span v-if="deliveryFeeIsDistance" class="text-[11px] text-slate-500">· {{ deliveryDistanceKm }} km</span>
              </span>
              <span class="tabular-nums font-medium">{{ formatPrice(deliveryFeeAmount) }}</span>
            </div>
            <div v-if="fulfillmentType === 'delivery' && deliveryFeePending" class="flex items-center justify-between text-slate-400">
              <span>{{ t('cartPage.deliveryFee') }}</span>
              <span class="text-[11px]">{{ t('cartPage.deliveryFeeByDistanceShort') }}</span>
            </div>
            <div v-else-if="fulfillmentType === 'delivery' && !deliveryOutOfRange && deliveryFeeAmount === 0" class="flex items-center justify-between text-emerald-400">
              <span>{{ t('cartPage.deliveryFee') }}</span>
              <span class="font-semibold">{{ t('cartPage.free') }}</span>
            </div>
            <div v-if="tipAmount > 0" class="flex items-center justify-between text-[var(--color-secondary)]/75">
              <span>{{ t('cartPage.tipLabel') }}</span>
              <span class="tabular-nums font-medium">+{{ formatPrice(tipAmount) }}</span>
            </div>
            <div v-if="walletApplied && walletDeduction > 0" class="flex items-center justify-between text-emerald-400">
              <span>{{ t('cartPage.payWithCredits') }}</span>
              <span class="tabular-nums font-semibold">-{{ formatPrice(walletDeduction) }}</span>
            </div>
            <div class="flex items-center justify-between pt-2 border-t border-slate-700/50">
              <span class="text-sm font-bold text-slate-200 tracking-tight">{{ t('cartPage.total') }}</span>
              <span class="text-xl font-bold tabular-nums text-[var(--color-secondary)]">{{ formatPrice(orderGrandTotal) }}</span>
            </div>
          </div>

          <!-- Payment-timing note: pickup/delivery pay now, dine-in pays at the table -->
          <p
            v-if="!isBrowseOnlyPlan"
            class="flex items-start gap-2 rounded-xl border border-slate-700/50 bg-slate-900/40 px-3 py-2.5 text-[11px] text-slate-400 leading-relaxed"
          >
            <AppIcon name="info" class="h-3.5 w-3.5 mt-0.5 shrink-0 text-slate-500" />
            <span v-if="isTableContextOrder">{{ t('cartPage.payAtEndNote') }}</span>
            <span v-else>{{ t('cartPage.payNowNote') }}</span>
          </p>

          <!-- ── CTA buttons ── -->
          <div class="space-y-2.5">
            <button
              v-if="!isBrowseOnlyPlan"
              class="ui-btn-primary w-full justify-center py-4 text-base font-bold tracking-wide shadow-lg shadow-[var(--color-secondary)]/20"
              :disabled="placingOrder || prepayShortfall || deliveryBlocked || deliveryMinGap > 0 || closedBlocksOrder || closedNeedsSchedule"
              :aria-busy="placingOrder"
              @click="placeInAppOrder"
            >
              <svg v-if="placingOrder" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-4 w-4 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
              <AppIcon v-else name="cart" class="h-4 w-4 shrink-0" aria-hidden="true" />
              {{ placingOrder ? t('cartPage_order.placing') : (closedBlocksOrder ? t('cartPage.restaurantCurrentlyClosed') : (closedNeedsSchedule ? t('cartPage.closedScheduleToOrder') : (deliveryBlocked ? t('cartPage.deliveryOutOfRangeShort') : (prepayShortfall ? t('cartPage.walletTopUpRequiredShort') : (deliveryMinGap > 0 ? t('cartPage.deliveryMinAddMore', { amount: formatPrice(deliveryMinGap) }) : t('cartPage_order.placeOrder')))))) }}
            </button>
            <button
              v-if="cart.canWhatsapp"
              class="ui-btn-outline w-full justify-center py-2.5 text-sm font-semibold"
              :disabled="sendingWhatsapp"
              :aria-busy="sendingWhatsapp"
              @click="openWhatsApp"
            >
              <svg v-if="sendingWhatsapp" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-4 w-4 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
              <AppIcon v-else name="chat" class="h-4 w-4" />
              {{ sendingWhatsapp ? t('cartPage.preparingWhatsApp') : t('cartPage.sendViaWhatsApp') }}
            </button>
            <button
              v-if="cart.canCheckout"
              class="ui-btn-outline w-full justify-center py-2.5 text-sm font-semibold"
              :disabled="processingCheckout"
              :aria-busy="processingCheckout"
              @click="startCheckout"
            >
              <svg v-if="processingCheckout" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-4 w-4 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
              <AppIcon v-else name="card" class="h-4 w-4" />
              {{ processingCheckout ? t('cartPage.preparingCheckout') : t('cartPage.proceedCheckout') }}
            </button>
            <button
              v-if="isBrowseOnlyPlan"
              class="ui-btn-outline w-full justify-center opacity-50 cursor-not-allowed"
              disabled
              aria-disabled="true"
            >{{ t('cartPage.orderingDisabledPlan') }}</button>
            <p v-if="isBrowseOnlyPlan" class="text-[11px] text-slate-500 text-center">{{ t('cartPage.orderingDisabledCurrentPlan') }}</p>

            <!-- Closed-now: dine-in can't order (no scheduling) -->
            <div
              v-if="!isBrowseOnlyPlan && closedBlocksOrder"
              class="flex items-start gap-2 rounded-xl border border-amber-500/30 bg-amber-500/8 px-3 py-2.5"
              role="status"
            >
              <AppIcon name="info" aria-hidden="true" class="mt-0.5 h-4 w-4 shrink-0 text-amber-400" />
              <p class="flex-1 text-[12px] leading-relaxed text-amber-200">{{ t('cartPage.closedDineInNotice') }}</p>
            </div>

            <!-- Closed-now: pickup/delivery can still order ahead — steer to schedule -->
            <div
              v-else-if="!isBrowseOnlyPlan && closedNeedsSchedule"
              class="space-y-2 rounded-xl border border-amber-500/30 bg-amber-500/8 px-3 py-2.5"
              role="status"
            >
              <p class="flex items-start gap-2 text-[12px] leading-relaxed text-amber-200">
                <AppIcon name="info" aria-hidden="true" class="mt-0.5 h-4 w-4 shrink-0 text-amber-400" />
                <span class="flex-1">{{ t('cartPage.closedScheduleNotice') }}</span>
              </p>
              <button
                type="button"
                class="ui-btn-outline w-full justify-center py-2 text-xs font-semibold"
                @click="scheduleEnabled = true"
              >{{ t('cartPage.scheduleLater') }}</button>
            </div>
          </div>

          <!-- Errors -->
          <div v-if="placeOrderError" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
            <AppIcon name="info" aria-hidden="true" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" />
            <p class="flex-1 text-sm text-red-300">{{ placeOrderError }}</p>
          </div>
          <div v-if="checkoutError" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
            <AppIcon name="info" aria-hidden="true" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" />
            <p class="flex-1 text-sm text-red-300">{{ checkoutError }}</p>
          </div>
          <div v-if="handoffError" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
            <AppIcon name="info" aria-hidden="true" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" />
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
        @keydown.esc="closeMapModal"
      >
        <div ref="mapDialogRef" role="dialog" aria-modal="true" aria-labelledby="cart-map-dialog-title" class="w-full max-w-2xl rounded-2xl border border-slate-700/70 bg-slate-950 shadow-2xl shadow-black/50">
          <header class="flex items-center justify-between gap-3 border-b border-slate-800 px-4 py-3">
            <div>
              <p class="ui-kicker">{{ t('cartPage.mapPicker') }}</p>
              <h2 id="cart-map-dialog-title" class="text-base font-semibold text-slate-100">{{ t('cartPage.tapMapToChoosePin') }}</h2>
            </div>
            <button class="ui-btn-outline px-3 py-1.5 text-xs" @click="closeMapModal">
              <AppIcon name="close" class="h-3.5 w-3.5" aria-hidden="true" />
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
                <AppIcon name="close" class="h-3.5 w-3.5" aria-hidden="true" />
                {{ t('cartPage.cancel') }}
              </button>
              <button
                class="ui-btn-primary px-4 py-2 text-sm"
                :disabled="!hasTemporaryMapSelection"
                @click="applyMapSelection"
              >
                <AppIcon name="check" class="h-3.5 w-3.5" aria-hidden="true" />
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
import { useMenuStore } from '../stores/menu';
import { useOrderStore } from '../stores/order';
import { useTenantStore } from '../stores/tenant';
import { useToastStore } from '../stores/toast';
import { useCurrencyStore } from '../stores/currency';
import api from '../lib/api';
import { trackEvent } from '../lib/analytics';
import { safeExternalUrl } from '../lib/escape';
import { addTileLayer } from '../lib/mapTiles';
import { isRestaurantOpenNow, classifyClosedOrderState } from '../lib/businessHours';

const router = useRouter();
const cart = useCartStore();
const customerStore = useCustomerStore();
const menu = useMenuStore();
const order = useOrderStore();
const tenant = useTenantStore();
const toast = useToastStore();
const { formatPrice, itemCountLabel, t } = useI18n();
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

// Warn if custom tip exceeds the order total (generous but probably a typo)
const tipHighWarning = computed(() => {
  if (tipPercent.value !== 'custom') return false;
  const tip = tipAmount.value;
  const base = Number(cart.total) || 0;
  return tip > 0 && base > 0 && tip > base;
});

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
// Advance/scheduled order — pickup & delivery may be placed now for a future time.
const scheduleEnabled = ref(false);
const scheduledFor = ref(''); // <input type="datetime-local"> value: "YYYY-MM-DDTHH:mm" (local)
const deliveryAddress = ref('');
const deliveryLocationUrl = ref('');
const deliveryLat = ref(null);
const deliveryLng = ref(null);
const locating = ref(false);
const locationError = ref('');
const locationAdvancedOpen = ref(false);
const showMoreLocationOptions = ref(false);
const waitingForPaste = ref(false);
const deliveryUrlInputRef = ref(null);
let waitingForPasteTimer = null;
const fieldErrors = ref({});
const showMapModal = ref(false);
const mapContainerRef = ref(null);
const mapDialogRef = ref(null);
// APG dialog pattern: remember the control that opened the map dialog so focus
// can be restored to it when the dialog closes.
const mapTriggerEl = ref(null);

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

// ── Distance-based delivery pricing ─────────────────────────────────────────
// Mirrors backend tenancy/delivery_pricing.compute_delivery_fee so the customer
// sees the same fee before placing. The backend recomputes authoritatively.
// Straight-line→road multiplier, mirrors backend tenancy/routing road factor
// (DELIVERY_ROAD_FACTOR, default 1.3). When the server uses a real OSRM route
// the preview is a close estimate; the server's figure is authoritative.
const ROAD_FACTOR = 1.3;
function haversineKm(lat1, lng1, lat2, lng2) {
  const toNum = (v) => (v === null || v === undefined || v === '' ? NaN : Number(v));
  const a1 = toNum(lat1), o1 = toNum(lng1), a2 = toNum(lat2), o2 = toNum(lng2);
  if (![a1, o1, a2, o2].every((n) => Number.isFinite(n))) return null;
  const R = 6371.0088;
  const rad = (d) => (d * Math.PI) / 180;
  const dLat = rad(a2 - a1);
  const dLng = rad(o2 - o1);
  const s =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(rad(a1)) * Math.cos(rad(a2)) * Math.sin(dLng / 2) ** 2;
  return R * 2 * Math.asin(Math.min(1, Math.sqrt(s)));
}

const deliveryPricing = computed(() => {
  const p = meta.value?.profile || {};
  return {
    flat: Number(p.delivery_fee) || 0,
    base: Number(p.delivery_base_fee) || 0,
    perKm: Number(p.delivery_per_km) || 0,
    freeOver: Number(p.delivery_free_over) || 0,
    radiusKm: p.delivery_radius_km == null ? null : Number(p.delivery_radius_km),
    lat: p.lat,
    lng: p.lng,
  };
});

// Straight-line km from the restaurant to the chosen delivery address (1dp), or null.
// A coordinate is usable only if it's in range AND not the null-island (0,0)
// default a failed locate/geocode leaves behind — mirrors backend valid_coord.
const validCoord = (lat, lng) => {
  const a = Number(lat), o = Number(lng);
  if (!Number.isFinite(a) || !Number.isFinite(o)) return false;
  if (a < -90 || a > 90 || o < -180 || o > 180) return false;
  return !(Math.abs(a) < 1e-6 && Math.abs(o) < 1e-6);
};

const deliveryDistanceKm = computed(() => {
  const p = deliveryPricing.value;
  // Only compute distance when BOTH the restaurant and the chosen address are real
  // points. A bogus/unset restaurant coordinate must NOT read as "outside delivery
  // area" — fall back to flat pricing instead.
  if (!validCoord(p.lat, p.lng) || !validCoord(deliveryLat.value, deliveryLng.value)) return null;
  const d = haversineKm(p.lat, p.lng, deliveryLat.value, deliveryLng.value);
  // Approximate the road distance the driver drives (× road factor), matching
  // backend tenancy/routing.road_distance_km so the previewed fee lines up.
  return d == null ? null : Math.round(d * ROAD_FACTOR * 10) / 10;
});

// True when the chosen address is beyond the restaurant's max delivery radius.
const deliveryOutOfRange = computed(() => {
  const p = deliveryPricing.value;
  const d = deliveryDistanceKm.value;
  return d != null && p.radiusKm != null && p.radiusKm > 0 && d > p.radiusKm;
});

// Whether distance pricing is actually in effect (per-km set AND distance known).
const deliveryFeeIsDistance = computed(
  () => deliveryPricing.value.perKm > 0 && deliveryDistanceKm.value != null,
);

// True when delivery is free because the subtotal cleared the free-over threshold.
const deliveryIsFree = computed(() => {
  const p = deliveryPricing.value;
  const subtotal = Number(cart.total) || 0;
  return p.freeOver > 0 && subtotal >= p.freeOver && !deliveryOutOfRange.value;
});

// Delivery fee preview (0 = free / out of range). Distance pricing when configured,
// else the flat fee.
const deliveryFeeAmount = computed(() => {
  const p = deliveryPricing.value;
  const subtotal = Number(cart.total) || 0;
  if (deliveryOutOfRange.value) return 0;
  if (p.freeOver > 0 && subtotal >= p.freeOver) return 0;
  if (deliveryFeeIsDistance.value) {
    const fee = p.base + p.perKm * deliveryDistanceKm.value;
    return Math.max(0, Math.round(fee * 100) / 100);
  }
  return p.flat > 0 ? p.flat : 0;
});

// Block placing a delivery order when the chosen address is out of range.
const deliveryBlocked = computed(
  () => fulfillmentType.value === 'delivery' && deliveryOutOfRange.value,
);

// Distance pricing configured but no location yet → fee not knowable (don't show "Free").
const deliveryFeePending = computed(
  () =>
    fulfillmentType.value === 'delivery' &&
    deliveryPricing.value.perKm > 0 &&
    deliveryDistanceKm.value == null &&
    !deliveryIsFree.value,
);

// Minimum order total required for delivery (0 = no minimum)
const deliveryMinOrder = computed(() => {
  const raw = meta.value?.profile?.delivery_minimum_order;
  const n = Number(raw);
  return Number.isFinite(n) && n > 0 ? n : 0;
});

// How much more is needed to reach the delivery minimum (0 = already met).
const deliveryMinGap = computed(() => Math.max(0, deliveryMinOrder.value - (Number(cart.total) || 0)));

// Short zone description shown to customers (empty = not set)
const deliveryZoneDesc = computed(() => String(meta.value?.profile?.delivery_zone_description || '').trim());

// Grand total = items subtotal + delivery fee (when applicable)
// ── Loyalty redemption at checkout ──────────────────────────────────────────
const loyaltyConfig = ref(null);
const useLoyalty = ref(false);
const loyaltyPoints = computed(() => Number(customerStore.customer?.loyalty_points) || 0);
const loyaltyAvailable = computed(() =>
  customerStore.isAuthenticated &&
  !!loyaltyConfig.value?.enabled &&
  loyaltyPoints.value >= (Number(loyaltyConfig.value?.redeem_threshold) || 0) &&
  (Number(loyaltyConfig.value?.points_value) || 0) > 0
);
// Discount preview = value of all the customer's points, capped to the pre-tip charge.
// The backend re-caps and spends only the points the order actually consumes.
const loyaltyDiscount = computed(() => {
  if (!useLoyalty.value || !loyaltyAvailable.value) return 0;
  const ptsValue = Number(loyaltyConfig.value.points_value) || 0;
  const subtotal = Number(cart.total) || 0;
  const base = fulfillmentType.value === 'delivery' ? subtotal + deliveryFeeAmount.value : subtotal;
  return Math.max(0, Math.min(loyaltyPoints.value * ptsValue, base));
});

const orderGrandTotal = computed(() => {
  const subtotal = Number(cart.total) || 0;
  const base = fulfillmentType.value === 'delivery'
    ? subtotal + deliveryFeeAmount.value
    : subtotal;
  return Math.max(0, base - loyaltyDiscount.value) + tipAmount.value;
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
// Display-only "restaurant closed" notice (it does NOT gate checkout here), so it
// uses the shared server-authoritative verdict to agree with Menu/MenuSelect.
const isRestaurantOpen = computed(() => isRestaurantOpenNow(meta.value?.profile));
const tableLabelModel = computed(() => cart.tableLabel || '');
// Dine-in (table) context only applies to businesses with the dine_in
// capability. Without this gate, appending ?table= to a shop/pharmacy URL
// would activate the dine-in flow (pay-at-table, no wallet debit) — so a
// shop order could be placed with no payment collected.
const isTableContextOrder = computed(() =>
  Boolean(cart.tableSlug || cart.tableLabel) && tenant.capabilities.dine_in !== false
);
const isDelivery = computed(
  () => !isTableContextOrder.value && fulfillmentType.value === 'delivery'
);
// Advance orders apply to pickup & delivery (not dine-in). The "Schedule for later"
// toggle is offered once one of those is chosen.
const canSchedule = computed(
  () => !isTableContextOrder.value &&
    (fulfillmentType.value === 'pickup' || fulfillmentType.value === 'delivery')
);
// Earliest selectable time = now + 30 min lead, formatted for <input type="datetime-local">
// in the browser's local wall-clock (no timezone suffix).
const minScheduleDatetime = computed(() => {
  const d = new Date(Date.now() + 30 * 60 * 1000);
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
});
// Pickup & delivery are pay-now: settled in full from the wallet at checkout
// (the only online method for now). Dine-in (table) pays at the end.
const requiresPrepay = computed(
  () => !isTableContextOrder.value &&
    (fulfillmentType.value === 'pickup' || fulfillmentType.value === 'delivery')
);
const walletCoversTotal = computed(() => walletBalance.value >= orderGrandTotal.value);
// Trusted-customer cash-on-handover (COD): eligibility comes from the backend.
const codEligible = ref(false);
const codMinOrders = ref(3);
const paymentMethod = ref('wallet'); // 'wallet' | 'cash' (cash only when codEligible)
const codChosen = computed(
  () => requiresPrepay.value && codEligible.value && paymentMethod.value === 'cash'
);
// Wallet is applied for prepay orders unless the customer picked cash-on-handover.
const walletApplied = computed(
  () => (requiresPrepay.value && customerStore.isAuthenticated && !codChosen.value) ||
    (useWallet.value && canPayWithCredits.value)
);
// Block checkout when a signed-in customer's wallet can't cover a pay-now order
// (unless they chose trusted cash-on-handover).
const prepayShortfall = computed(
  () => requiresPrepay.value && orderGrandTotal.value > 0 &&
    customerStore.isAuthenticated && !walletCoversTotal.value && !codChosen.value
);

// ── Closed-now ordering gate (mirror backend, prevent the checkout-time 409) ──
// The backend lets the SCHEDULE win for an IMMEDIATE order and 409s
// "restaurant_closed"; SCHEDULED pickup/delivery bypass that gate. We mirror it
// here so the cart never silently builds an un-checkout-able immediate order.
//
// A scheduled order = the "Schedule for later" toggle is on with a chosen time
// (only offered for pickup/delivery via canSchedule). It must remain placeable
// even when closed-now — that is the whole point of order-ahead.
const isScheduledOrder = computed(
  () => canSchedule.value && scheduleEnabled.value && Boolean(scheduledFor.value)
);
// One shared classification (open | blocked | schedule) — see businessHours.js.
const closedOrderState = computed(() =>
  classifyClosedOrderState({
    profile: meta.value?.profile,
    isTableContext: isTableContextOrder.value,
    isScheduled: isScheduledOrder.value,
  })
);
// Closed-now AND placing an IMMEDIATE (non-scheduled) order (any context).
const closedNowImmediate = computed(() => closedOrderState.value !== 'open');
// Dine-in (table) has no scheduling → closed-now immediate is a hard block.
const closedBlocksOrder = computed(() => closedOrderState.value === 'blocked');
// Pickup/delivery → closed-now immediate is recoverable: steer to "Schedule for
// later" instead of letting Place Order blind-409.
const closedNeedsSchedule = computed(() => closedOrderState.value === 'schedule');

// Pull COD eligibility for the signed-in customer at this restaurant.
const fetchCodEligibility = async () => {
  if (!customerStore.isAuthenticated || isTableContextOrder.value) {
    codEligible.value = false;
    return;
  }
  try {
    const res = await api.get('/order-eligibility/');
    codEligible.value = res.data?.cod_eligible === true;
    codMinOrders.value = Number(res.data?.cod_min_paid_orders) || 3;
    if (!codEligible.value && paymentMethod.value === 'cash') paymentMethod.value = 'wallet';
  } catch {
    codEligible.value = false;
  }
};
const fetchLoyaltyConfig = async () => {
  if (!customerStore.isAuthenticated) {
    loyaltyConfig.value = null;
    return;
  }
  try {
    const res = await api.get('/customer/loyalty/config/');
    loyaltyConfig.value = res.data?.enabled ? res.data : null;
  } catch {
    loyaltyConfig.value = null;
  }
};
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
    addTileLayer(Leaflet, leafletMap.value);
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
  // Remember the trigger so focus returns here when the dialog closes (APG).
  mapTriggerEl.value =
    typeof document !== 'undefined' && document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null;
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

watch(() => customerStore.isAuthenticated, () => {
  fetchCodEligibility();
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
    // Invalidate a "free delivery" promo when switching away from delivery —
    // it would be rejected at checkout anyway since it's delivery-only.
    if (promoApplied.value?.promo_type === 'free_delivery') {
      promoApplied.value = null;
      promoCode.value = '';
      toast.show(t('cartPage.promoFreeDeliveryRemoved'), 'info');
    }
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
    // APG: restore focus to the control that opened the dialog.
    const trigger = mapTriggerEl.value;
    mapTriggerEl.value = null;
    if (trigger && typeof trigger.focus === 'function' && trigger.isConnected) {
      nextTick(() => trigger.focus());
    }
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
  // Closed-now + IMMEDIATE order: mirror the backend gate so we never blind-409.
  // Scheduled pickup/delivery (isScheduledOrder) is exempt — order-ahead is valid.
  if (closedNowImmediate.value) {
    if (isTableContextOrder.value) {
      // Dine-in has no scheduling — closed means it cannot order at all.
      toast.show(t('cartPage.restaurantCurrentlyClosed'), 'error');
    } else {
      // Pickup/delivery — point the customer at "Schedule for later".
      toast.show(t('cartPage.closedScheduleNotice'), 'error');
    }
    return false;
  }

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
  // Pickup & delivery are pay-now: the wallet must cover the full total (unless the
  // customer chose trusted cash-on-handover).
  if (requiresPrepay.value && !codChosen.value && orderGrandTotal.value > 0 && walletBalance.value < orderGrandTotal.value) {
    toast.show(t('cartPage.walletTopUpRequired', {
      balance: formatPrice(walletBalance.value),
      total: formatPrice(orderGrandTotal.value),
    }), 'error');
    return false;
  }

  const errors = {};
  if (!fulfillmentType.value) {
    errors.fulfillment_type = t('cartPage.selectPickupOrDelivery');
  }
  if (canSchedule.value && scheduleEnabled.value) {
    if (!scheduledFor.value) {
      errors.scheduled_for = t('cartPage.scheduleRequired');
    } else if (scheduledFor.value < minScheduleDatetime.value) {
      errors.scheduled_for = t('cartPage.scheduleInPast');
    }
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
      // OPS-6b: never surface raw backend detail to customers — use the localized message.
      promoError.value = t('cartPage.promoInvalid');
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
  if (codChosen.value) {
    payload.payment_method = 'cash';
  } else if (requiresPrepay.value || (useWallet.value && canPayWithCredits.value)) {
    payload.use_wallet = true;
  }
  if (promoApplied.value) payload.promo_code = promoCode.value.trim().toUpperCase();
  // Loyalty redemption — send the full balance; the backend caps the discount to the
  // order and debits only the points actually consumed.
  if (useLoyalty.value && loyaltyAvailable.value && loyaltyPoints.value > 0) {
    payload.redeem_points = loyaltyPoints.value;
  }
  if (tipAmount.value > 0) payload.tip_amount = tipAmount.value;
  if (cart.tableLabel) payload.table_label = cart.tableLabel;
  if (cart.tableSlug) payload.table_slug = cart.tableSlug;
  // customer_name: only for table context (optional)
  if (isTableContextOrder.value && cart.customerName) payload.customer_name = cart.customerName;
  // customer_phone no longer sent (anonymous pickup, delivery uses customer profile)

  if (!isTableContextOrder.value) {
    if (fulfillmentType.value) payload.fulfillment_type = fulfillmentType.value;
    // Advance/scheduled order — send the chosen local time as a UTC instant.
    if (canSchedule.value && scheduleEnabled.value && scheduledFor.value) {
      const dt = new Date(scheduledFor.value);
      if (!Number.isNaN(dt.getTime())) payload.scheduled_for = dt.toISOString();
    }
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
    'scheduled_for',
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

const mapOrderApiError = (err) => {
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
    // Never surface raw backend detail to the customer; use the localized message.
    return t('cartPage.promoInvalid');
  }
  if (code === 'auth_required') {
    showAuthModal.value = true;
    return t('cartPage.deliveryAuthRequired');
  }
  if (code === 'wallet_insufficient') {
    return t('cartPage.walletInsufficientError');
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
  if (typeof code === 'string' && code.startsWith('loyalty_')) {
    // Points balance changed under us → refresh the customer so the UI re-syncs.
    customerStore.fetchCustomer(true);
    useLoyalty.value = false;
    // Never surface raw backend detail to the customer; use the localized message.
    return t('cartPage.loyaltyRedeemFailed');
  }
  if (typeof code === 'string' && code.startsWith('schedule_')) {
    // Never surface raw backend detail to the customer; use the localized message,
    // and mirror it onto the field error so the input shows a customer-safe hint.
    const scheduleMsg = t('cartPage.scheduleInvalid');
    fieldErrors.value = { ...fieldErrors.value, scheduled_for: scheduleMsg };
    return scheduleMsg;
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
  if (code === 'stale_options') {
    // Menu changed under the cart (option prices/availability changed).
    // The toast is the primary action signal; the customer can review and retry.
    return t('cartPage.staleOptions');
  }
  if (code === 'menu_temporarily_disabled') {
    return note
      ? t('cartPage.menuTemporarilyUnavailableWithNote', { note })
      : t('cartPage.menuTemporarilyUnavailable');
  }
  return t('cartPage.genericCheckoutError');
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

  // Stale happy-hour guard: if any cart line was priced during a happy-hour
  // window that has since ended, refetch menu prices, update lines, and let the
  // user re-confirm.
  // Overnight windows (starts_at > ends_at, e.g. 22:00–02:00) are handled
  // correctly: a line with ends_at='02:00' at 23:30 is NOT stale, because the
  // gap where the window is inactive is 02:00–22:00, not 22:00–02:00.
  {
    const nowHHMM = new Date().toTimeString().slice(0, 5); // "HH:MM"
    const hasStaleHH = cart.items.some((i) => {
      const endsAt = i.happy_hour_ends_at;
      if (typeof endsAt !== 'string') return false;
      const startsAt = i.happy_hour_starts_at;
      const isOvernight = typeof startsAt === 'string' && startsAt > endsAt;
      // Overnight: stale only in the gap between end and next start (daytime).
      if (isOvernight) return nowHHMM >= endsAt && nowHHMM < startsAt;
      // Normal window: stale when current time has passed ends_at.
      return nowHHMM >= endsAt;
    });
    if (hasStaleHH) {
      await menu.fetchCategories(true);
      const allDishes = Object.values(menu.dishes).flat();
      const dishMap = new Map(allDishes.map((d) => [d.slug, d]));
      for (const line of cart.items) {
        const live = dishMap.get(line.slug);
        if (!live) continue;
        const liveEffective = (live.happy_hour && Number(live.effective_price) < Number(live.price))
          ? Number(live.effective_price)
          : Number(live.price);
        line.price = liveEffective;
        line.happy_hour_ends_at = live.happy_hour?.ends_at ?? null;
        line.happy_hour_starts_at = live.happy_hour?.starts_at ?? null;
      }
      cart.persist();
      toast.show(t('happyHour.ended'), 'info');
      return; // let user re-confirm with updated prices
    }
  }

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
    } catch { /* best-effort: ignore failures */ }
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
  fetchCodEligibility();
  fetchLoyaltyConfig();
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
  fetchCodEligibility();
  fetchLoyaltyConfig();
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
