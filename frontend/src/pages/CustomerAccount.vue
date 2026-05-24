<template>
  <div class="space-y-3 px-3 py-2 pb-28 sm:space-y-4 sm:px-4 sm:py-4 sm:pb-6 ui-safe-bottom">

    <!-- ── Header ─────────────────────────────────────────────────────────────── -->
    <header class="ui-hero-ribbon ui-reveal p-3 md:p-5">
      <div class="flex items-center gap-3.5">
        <div
          class="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl"
          :class="customerStore.isAuthenticated
            ? 'border border-[var(--color-secondary)]/35 bg-[var(--color-secondary)]/12 text-[var(--color-secondary)]'
            : 'border border-slate-700/70 bg-slate-900/60 text-slate-400'"
        >
          <span v-if="customerStore.isAuthenticated && initials" class="text-sm font-bold tracking-tight select-none">{{ initials }}</span>
          <AppIcon v-else name="user" class="h-6 w-6" />
        </div>
        <div class="min-w-0 space-y-0.5">
          <p class="ui-kicker">{{ t('customerAccount.kicker') }}</p>
          <h1 class="ui-display text-xl font-semibold tracking-tight text-white md:text-2xl leading-tight truncate">
            {{ customerStore.isAuthenticated && customerStore.customer?.name
              ? customerStore.customer.name
              : t('customerAccount.title') }}
          </h1>
          <p v-if="customerStore.isAuthenticated && (customerStore.customer?.phone || customerStore.customer?.email)" class="text-xs text-slate-400 truncate">
            {{ customerStore.customer?.phone || customerStore.customer?.email }}
          </p>
        </div>
      </div>
    </header>

    <!-- ── Loading skeleton ──────────────────────────────────────────────────── -->
    <div v-if="!customerStore.loaded" class="ui-panel ui-reveal p-6 space-y-4 text-center">
      <div class="flex justify-center">
        <span class="flex h-14 w-14 animate-pulse items-center justify-center rounded-full border border-slate-700/70 bg-slate-900/60" />
      </div>
      <div class="space-y-2">
        <div class="mx-auto h-4 w-32 animate-pulse rounded bg-slate-800" />
        <div class="mx-auto h-3 w-48 animate-pulse rounded bg-slate-800/70" />
      </div>
      <div class="mx-auto h-9 w-44 animate-pulse rounded-full bg-slate-800" />
    </div>

    <!-- ── Not signed in ─────────────────────────────────────────────────────── -->
    <template v-else-if="!customerStore.isAuthenticated">

      <div class="ui-panel ui-reveal p-5 space-y-5">
        <div class="text-center space-y-3">
          <p class="text-sm font-semibold text-slate-100">{{ t('customerAccount.notSignedInTitle') }}</p>
          <p class="text-xs text-slate-400 max-w-xs mx-auto">{{ t('customerAccount.crossRestaurantNote') }}</p>
          <button class="ui-btn-primary mx-auto justify-center" @click="showAuthModal = true">
            <AppIcon name="user" class="h-3.5 w-3.5" />
            {{ t('customerAccount.signIn') }}
          </button>
        </div>

        <!-- Benefits grid -->
        <div class="grid grid-cols-2 gap-2 border-t border-slate-800/60 pt-4">
          <div v-for="b in benefits" :key="b.key" class="flex items-start gap-2 rounded-xl border border-slate-800/60 bg-slate-900/40 p-2.5">
            <AppIcon :name="b.icon" class="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--color-secondary)]" />
            <p class="text-[11px] leading-snug text-slate-400">{{ b.label }}</p>
          </div>
        </div>
      </div>

      <!-- Local orders from this device -->
      <section v-if="cart.recentOrders?.length" class="ui-panel ui-reveal p-4 space-y-3">
        <p class="ui-kicker">{{ t('customerAccount.localOrdersTitle') }}</p>
        <ul class="space-y-2">
          <li
            v-for="order in cart.recentOrders"
            :key="order.order_number"
            class="flex items-center justify-between gap-2 rounded-xl border border-slate-700/60 bg-slate-900/40 px-3 py-2.5 text-xs"
          >
            <RouterLink
              :to="{ name: 'order-status', params: { orderNumber: order.order_number } }"
              class="font-semibold text-[var(--color-secondary)] hover:opacity-80"
            >
              {{ t('customerAccount.orderNumber', { number: order.order_number }) }}
            </RouterLink>
            <span v-if="order.total" class="tabular-nums text-slate-400">{{ formatPrice(order.total) }}</span>
          </li>
        </ul>
      </section>
    </template>

    <!-- ── Signed in ─────────────────────────────────────────────────────────── -->
    <template v-else>

      <!-- Active (in-flight) orders -->
      <template v-if="!loadingOrders && activeOrders.length">
        <section
          v-for="order in activeOrders"
          :key="order.order_number"
          class="ui-reveal relative overflow-hidden rounded-2xl border border-[var(--color-secondary)]/40 bg-[var(--color-secondary)]/8 p-4"
        >
          <div class="pointer-events-none absolute inset-0 rounded-2xl ring-1 ring-inset ring-[var(--color-secondary)]/20 animate-pulse" />
          <div class="relative flex items-center gap-3">
            <span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-[var(--color-secondary)]/40 bg-[var(--color-secondary)]/15">
              <span class="block h-2.5 w-2.5 animate-ping rounded-full bg-[var(--color-secondary)]" />
            </span>
            <div class="min-w-0 flex-1 space-y-0.5">
              <p class="text-sm font-semibold text-[var(--color-secondary)]">
                {{ t('customerAccount.orderNumber', { number: order.order_number }) }}
              </p>
              <p class="text-xs text-slate-400">
                {{ statusLabel(order.status) }}
                <span v-if="order.fulfillment_type"> · {{
                  order.fulfillment_type === 'pickup' ? t('orderStatus.fulfillmentPickup') :
                  order.fulfillment_type === 'delivery' ? t('orderStatus.fulfillmentDelivery') :
                  t('orderStatus.fulfillmentTable', { table: order.table_label || '' })
                }}</span>
              </p>
            </div>
            <RouterLink
              :to="{ name: 'order-status', params: { orderNumber: order.order_number } }"
              class="shrink-0 inline-flex items-center gap-1.5 rounded-xl border border-[var(--color-secondary)]/40 bg-[var(--color-secondary)]/15 px-3 py-1.5 text-xs font-semibold text-[var(--color-secondary)] hover:bg-[var(--color-secondary)]/25 transition-colors"
            >
              {{ t('customerAccount.trackOrder') }}
              <AppIcon name="arrowRight" class="h-3 w-3" />
            </RouterLink>
          </div>
        </section>
      </template>

      <!-- ── Profile card ─────────────────────────────────────────────────────── -->
      <section class="ui-panel ui-reveal p-4 space-y-3.5">

        <!-- Name + sign out row -->
        <div class="flex items-center gap-3">
          <div class="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl border border-[var(--color-secondary)]/35 bg-[var(--color-secondary)]/12">
            <span class="text-sm font-bold tracking-tight text-[var(--color-secondary)] select-none">{{ initials }}</span>
          </div>
          <div class="min-w-0 flex-1 flex items-center gap-2">
            <input
              v-model.trim="editableName"
              type="text"
              maxlength="80"
              class="ui-input flex-1 text-sm py-1"
              :placeholder="t('customerAccount.namePlaceholder')"
              :disabled="savingName"
            />
            <button
              v-if="editableName !== (customerStore.customer?.name || '')"
              class="ui-btn-primary shrink-0 px-3 py-1 text-xs"
              :disabled="savingName"
              @click="saveName"
            >{{ savingName ? t('customerAccount.saving') : t('customerAccount.saveName') }}</button>
          </div>
          <button class="shrink-0 px-1 text-xs text-slate-500 hover:text-red-300 transition" @click="handleLogout">
            {{ t('customerAccount.signOut') }}
          </button>
        </div>

        <!-- Phone -->
        <div class="flex flex-wrap items-center gap-2 text-xs">
          <span v-if="customerStore.customer?.phone" class="text-slate-300">{{ customerStore.customer.phone }}</span>
          <button
            v-else
            class="inline-flex items-center gap-1 rounded-lg border border-amber-500/40 bg-amber-500/10 px-2.5 py-1 text-[11px] font-medium text-amber-300 hover:border-amber-500/70 transition-colors"
            @click="showAddPhone = true"
          >
            <AppIcon name="plus" class="h-3 w-3" />
            {{ t('customerAccount.addPhone') }}
          </button>
          <span v-if="customerStore.customer?.phone_verified" class="ui-chip border-emerald-500/40 bg-emerald-500/10 text-emerald-300 text-[10px]">
            <AppIcon name="check" class="h-3 w-3" />{{ t('customerAccount.verifiedPhone') }}
          </span>
        </div>

        <!-- Email -->
        <div>
          <div class="flex flex-wrap items-center gap-2 text-xs">
            <template v-if="!showEmailInput">
              <span v-if="customerStore.customer?.email" class="text-slate-300">{{ customerStore.customer.email }}</span>
              <button
                class="inline-flex items-center gap-1 text-[11px] transition-colors"
                :class="customerStore.customer?.email ? 'text-slate-500 hover:text-slate-300' : 'text-sky-400 hover:text-sky-300'"
                @click="openEmailInput"
              >
                <AppIcon name="plus" class="h-3 w-3" />
                {{ customerStore.customer?.email ? t('customerAccount.editEmail') : t('customerAccount.addEmail') }}
              </button>
              <span v-if="customerStore.customer?.email_verified" class="ui-chip border-emerald-500/40 bg-emerald-500/10 text-emerald-300 text-[10px]">
                <AppIcon name="check" class="h-3 w-3" />{{ t('customerAccount.verifiedEmail') }}
              </span>
            </template>
            <template v-else>
              <input
                ref="emailInputRef"
                v-model.trim="editableEmail"
                type="email"
                autocomplete="email"
                maxlength="254"
                class="ui-input flex-1 min-w-0 text-xs py-1"
                :placeholder="t('customerAccount.emailPlaceholder')"
                :disabled="savingEmail"
                @keydown.enter.prevent="saveEmail"
                @keydown.escape.prevent="cancelEmailInput"
              />
              <button class="ui-btn-primary shrink-0 px-2.5 py-1 text-xs" :disabled="savingEmail || !editableEmail" @click="saveEmail">
                {{ savingEmail ? t('customerAccount.saving') : t('common.save') }}
              </button>
              <button class="text-xs text-slate-500 hover:text-slate-300 transition" @click="cancelEmailInput">{{ t('common.cancel') }}</button>
            </template>
          </div>
          <p v-if="emailError" class="mt-1 text-xs text-red-300">{{ emailError }}</p>
        </div>

        <!-- Wallet inline badge -->
        <div v-if="walletBalance > 0" class="inline-flex items-center gap-1.5 rounded-lg border border-[var(--color-secondary)]/35 bg-[var(--color-secondary)]/10 px-2.5 py-1 text-[11px] text-[var(--color-secondary)]">
          💰 {{ formatPrice(walletBalance) }} {{ t('customerAccount.walletTitle') }}
        </div>
      </section>

      <!-- ── Preferences (language + display currency) ──────────────────────── -->
      <section class="ui-panel ui-reveal p-4 space-y-4">
        <p class="ui-kicker">{{ t('customerAccount.preferencesTitle') }}</p>

        <!-- Language -->
        <div class="space-y-1.5">
          <p class="text-[11px] font-medium text-slate-400 uppercase tracking-wider">{{ t('customerAccount.localeTitle') }}</p>
          <div v-if="!localeConfigured" class="flex flex-wrap gap-2">
            <button
              v-for="lang in [{ code: 'en', label: 'English' }, { code: 'fr', label: 'Français' }, { code: 'ar', label: 'العربية' }]"
              :key="lang.code"
              class="rounded-full border px-3 py-1 text-xs transition-colors"
              :class="selectedLocale === lang.code
                ? 'border-[var(--color-secondary)] bg-[var(--color-secondary)]/15 text-[var(--color-secondary)]'
                : 'border-slate-700 text-slate-400 hover:border-slate-500 hover:text-slate-200'"
              :disabled="savingLocale"
              @click="setLocale(lang.code)"
            >{{ lang.label }}</button>
          </div>
          <div v-else class="flex items-center justify-between gap-2">
            <span class="text-xs text-slate-300">{{ localeLabelCurrent }}</span>
            <button class="text-[11px] text-slate-500 hover:text-slate-300 transition" @click="localeConfigured = false">{{ t('common.change') }}</button>
          </div>
        </div>

        <!-- Display currency -->
        <div class="space-y-1.5">
          <p class="text-[11px] font-medium text-slate-400 uppercase tracking-wider">{{ t('customerAccount.displayCurrency') }}</p>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="r in currencyStore.available"
              :key="r.code"
              class="rounded-full border px-3 py-1 text-xs transition-colors"
              :class="currencyStore.selected === r.code
                ? 'border-[var(--color-secondary)] bg-[var(--color-secondary)]/15 text-[var(--color-secondary)]'
                : 'border-slate-700 text-slate-400 hover:border-slate-500 hover:text-slate-200'"
              @click="currencyStore.setCode(r.code)"
            >{{ r.code }} <span class="opacity-60">{{ r.symbol }}</span></button>
          </div>
        </div>
      </section>

      <!-- ── Order history ──────────────────────────────────────────────────── -->
      <section class="ui-panel ui-reveal p-4 space-y-3">
        <div class="flex items-center justify-between gap-2">
          <div>
            <p class="ui-kicker">{{ t('customerAccount.ordersTitle') }}</p>
            <p v-if="tenantName" class="mt-0.5 text-[10px] text-slate-500">{{ t('customerAccount.atRestaurant', { name: tenantName }) }}</p>
          </div>
          <span v-if="apiOrders.length" class="rounded-full border border-slate-700/60 bg-slate-900/50 px-2 py-0.5 text-[11px] tabular-nums text-slate-400">{{ apiOrders.length }}</span>
        </div>

        <div v-if="loadingOrders" class="space-y-2">
          <div v-for="i in 2" :key="i" class="h-12 animate-pulse rounded-xl bg-slate-800/60" />
        </div>
        <div v-else-if="ordersError" class="text-xs text-red-300">{{ t('customerAccount.fetchError') }}</div>
        <div v-else-if="!apiOrders.length && !cart.recentOrders.length" class="rounded-xl border border-dashed border-slate-700/50 px-4 py-6 text-center text-xs text-slate-500">
          {{ t('customerAccount.ordersEmpty') }}
        </div>

        <ul v-else-if="apiOrders.length" class="space-y-2">
          <li
            v-for="order in apiOrders"
            :key="order.order_number"
            class="rounded-xl border border-slate-700/60 bg-slate-900/40 text-xs"
          >
            <div class="flex items-start gap-2.5 px-3 py-2.5">
              <!-- Status dot -->
              <span
                class="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full"
                :class="{
                  'bg-amber-400 animate-pulse': ACTIVE_STATUSES.has(order.status),
                  'bg-emerald-400': order.status === 'completed',
                  'bg-red-400': order.status === 'cancelled',
                  'bg-slate-500': !ACTIVE_STATUSES.has(order.status) && order.status !== 'completed' && order.status !== 'cancelled',
                }"
              />
              <div class="min-w-0 flex-1 space-y-1">
                <div class="flex flex-wrap items-center gap-1.5">
                  <RouterLink
                    :to="{ name: 'order-status', params: { orderNumber: order.order_number } }"
                    class="font-semibold text-[var(--color-secondary)] hover:opacity-80"
                  >
                    {{ t('customerAccount.orderNumber', { number: order.order_number }) }}
                  </RouterLink>
                  <span class="rounded-full border border-slate-700/60 bg-slate-900/50 px-1.5 py-0.5 text-[10px] text-slate-400">{{ statusLabel(order.status) }}</span>
                </div>
                <div class="flex flex-wrap items-center gap-2 text-slate-500">
                  <span v-if="order.fulfillment_type">{{
                    order.fulfillment_type === 'pickup' ? t('orderStatus.fulfillmentPickup') :
                    order.fulfillment_type === 'delivery' ? t('orderStatus.fulfillmentDelivery') :
                    t('orderStatus.fulfillmentTable', { table: order.table_label || '' })
                  }}</span>
                  <span v-if="order.total" class="font-medium tabular-nums text-slate-400">{{ formatPrice(order.total) }}</span>
                  <span v-if="order.created_at">{{ formatDate(order.created_at) }}</span>
                </div>
                <div v-if="order.has_rating" class="text-[11px] tracking-tight text-amber-400">
                  {{ '★'.repeat(order.rating_score) }}{{ '☆'.repeat(5 - order.rating_score) }}
                </div>
              </div>
              <button
                v-if="order.items?.length"
                class="mt-0.5 shrink-0 rounded-lg border border-slate-700/50 bg-slate-800/50 px-2 py-1 text-[10px] font-medium text-slate-400 transition-colors hover:border-slate-600 hover:text-slate-200"
                @click="toggleOrder(order.order_number)"
              >
                {{ expandedOrders.has(order.order_number) ? t('customerAccount.orderHideItems') : t('customerAccount.orderShowItems') }}
              </button>
            </div>
            <Transition name="ui-expand">
              <div v-if="expandedOrders.has(order.order_number) && order.items?.length"
                class="border-t border-slate-700/50 px-3 pb-3 pt-2.5 space-y-2"
              >
                <ul class="space-y-1">
                  <li v-for="(item, idx) in order.items" :key="idx" class="flex items-start justify-between gap-2 text-slate-300">
                    <span class="min-w-0 flex-1">
                      <span class="text-slate-400">{{ item.qty }}×</span> {{ item.dish_name }}
                      <span v-if="item.options?.length" class="ml-1 text-slate-500">({{ item.options.map(o => o.name).join(', ') }})</span>
                    </span>
                    <span class="shrink-0 tabular-nums text-slate-400">{{ formatPrice(item.subtotal) }}</span>
                  </li>
                </ul>
                <button
                  class="mt-1 inline-flex items-center gap-1.5 rounded-lg border border-[var(--color-secondary)]/40 bg-[var(--color-secondary)]/10 px-3 py-1.5 text-[11px] font-semibold text-[var(--color-secondary)] transition-colors hover:bg-[var(--color-secondary)]/20"
                  @click="reorder(order)"
                >
                  <AppIcon name="cart" class="h-3 w-3" />
                  {{ t('customerAccount.reorder') }}
                </button>
              </div>
            </Transition>
          </li>
        </ul>

        <!-- Local-only orders (not yet signed in at time of order) -->
        <template v-else-if="cart.recentOrders.length">
          <ul class="space-y-2">
            <li
              v-for="order in cart.recentOrders"
              :key="order.order_number"
              class="flex items-center justify-between gap-2 rounded-xl border border-slate-700/60 bg-slate-900/40 px-3 py-2.5 text-xs"
            >
              <RouterLink
                :to="{ name: 'order-status', params: { orderNumber: order.order_number } }"
                class="font-semibold text-[var(--color-secondary)] hover:opacity-80"
              >{{ t('customerAccount.orderNumber', { number: order.order_number }) }}</RouterLink>
              <span v-if="order.total" class="tabular-nums text-slate-400">{{ formatPrice(order.total) }}</span>
            </li>
          </ul>
        </template>
      </section>

      <!-- ── Wallet ─────────────────────────────────────────────────────────── -->
      <section class="ui-panel ui-reveal p-4 space-y-3">
        <div class="flex items-center justify-between gap-2">
          <p class="ui-kicker">{{ t('customerAccount.walletTitle') }}</p>
          <p class="text-lg font-bold tabular-nums" :class="walletBalance > 0 ? 'text-[var(--color-secondary)]' : 'text-slate-500'">
            {{ formatPrice(walletBalance) }}
          </p>
        </div>

        <div v-if="loadingWallet" class="text-xs text-slate-400">{{ t('customerAccount.loading') }}</div>
        <div v-else-if="!walletTransactions.length" class="rounded-xl border border-dashed border-slate-700/50 px-4 py-4 text-center text-xs text-slate-500">
          {{ t('customerAccount.walletNoTransactions') }}
        </div>
        <ul v-else class="space-y-1.5">
          <li
            v-for="tx in walletTransactions"
            :key="tx.id"
            class="flex items-center justify-between gap-2 rounded-xl border border-slate-700/60 bg-slate-900/40 px-3 py-2 text-xs"
          >
            <div class="min-w-0 space-y-0.5">
              <p class="font-medium text-slate-200">{{ txLabel(tx) }}</p>
              <p class="text-slate-500">{{ formatDate(tx.created_at) }}</p>
            </div>
            <span
              class="shrink-0 font-semibold tabular-nums"
              :class="tx.type === 'payment' ? 'text-red-300' : 'text-emerald-300'"
            >
              {{ tx.type === 'payment' ? '−' : '+' }}{{ formatPrice(tx.amount) }}
            </span>
          </li>
        </ul>
      </section>

      <!-- ── Loyalty Points ─────────────────────────────────────────────────── -->
      <section v-if="loyaltyPoints > 0 || loyaltyConfig" class="ui-panel ui-reveal p-4 space-y-3">
        <div class="flex items-center justify-between gap-2">
          <p class="ui-kicker">{{ t('customerAccount.loyaltyTitle') }}</p>
          <p class="text-lg font-bold tabular-nums text-indigo-300">
            {{ loyaltyPoints }} <span class="text-xs font-normal text-slate-400">{{ t('customerAccount.loyaltyPts') }}</span>
          </p>
        </div>

        <div v-if="loyaltyConfig && loyaltyConfig.enabled">
          <!-- Progress bar toward threshold -->
          <div v-if="loyaltyConfig.redeem_threshold > 0" class="mb-3 space-y-1.5">
            <div class="flex items-center justify-between text-[11px]">
              <span class="text-slate-400">{{ t('customerAccount.loyaltyEarnRate', { pts: loyaltyConfig.points_per_unit }) }}</span>
              <span class="tabular-nums text-slate-500">{{ Math.min(loyaltyPoints, loyaltyConfig.redeem_threshold) }} / {{ loyaltyConfig.redeem_threshold }}</span>
            </div>
            <div class="h-1.5 overflow-hidden rounded-full bg-slate-800">
              <div
                class="h-full rounded-full bg-indigo-400 transition-all duration-500"
                :style="{ width: Math.min((loyaltyPoints / loyaltyConfig.redeem_threshold) * 100, 100) + '%' }"
              />
            </div>
          </div>

          <p v-if="loyaltyPoints >= loyaltyConfig.redeem_threshold" class="text-xs text-emerald-300">
            {{ t('customerAccount.loyaltyCanRedeem', { threshold: loyaltyConfig.redeem_threshold, credit: redeemableCredit }) }}
          </p>
          <p v-else class="text-xs text-slate-500">
            {{ t('customerAccount.loyaltyNeedMore', { need: loyaltyConfig.redeem_threshold - loyaltyPoints }) }}
          </p>

          <div v-if="loyaltyPoints >= loyaltyConfig.redeem_threshold" class="mt-3 flex flex-wrap items-center gap-3">
            <div class="flex items-center gap-2">
              <label class="text-xs text-slate-400">{{ t('customerAccount.loyaltyRedeemLabel') }}</label>
              <input
                v-model.number="redeemAmount"
                type="number"
                :min="loyaltyConfig.redeem_threshold"
                :max="loyaltyPoints"
                :step="loyaltyConfig.redeem_threshold"
                class="ui-input w-24 text-sm"
              />
            </div>
            <button
              class="ui-btn-primary px-3 py-1.5 text-xs"
              :disabled="redeeming || redeemAmount < loyaltyConfig.redeem_threshold"
              @click="redeemPoints"
            >
              {{ redeeming ? t('customerAccount.loyaltyRedeeming') : t('customerAccount.loyaltyRedeem') }}
            </button>
          </div>
          <p v-if="redeemError" class="mt-1 text-xs text-red-300">{{ redeemError }}</p>
          <p v-if="redeemSuccess" class="mt-1 text-xs text-emerald-300">{{ redeemSuccess }}</p>
        </div>
        <p v-else class="text-xs text-slate-500">{{ t('customerAccount.loyaltyNotActive') }}</p>
      </section>

      <!-- ── Saved Delivery Addresses ──────────────────────────────────────── -->
      <section v-if="customerStore.isAuthenticated" class="ui-panel ui-reveal p-4 space-y-3">
        <div class="flex items-center justify-between gap-2">
          <div>
            <p class="ui-kicker">{{ t('customerAccount.savedAddressesTitle') }}</p>
            <p class="mt-0.5 text-[10px] text-slate-500">{{ t('customerAccount.savedAddressesNote') }}</p>
          </div>
          <span class="text-[10px] text-slate-500">{{ t('customerAccount.savedAddressesMax') }}</span>
        </div>
        <div v-if="loadingAddresses" class="text-xs text-slate-400">{{ t('customerAccount.loading') }}</div>
        <div v-else-if="!savedAddresses.length" class="rounded-xl border border-dashed border-slate-700/50 px-4 py-4 text-center text-xs text-slate-500">
          {{ t('customerAccount.savedAddressesEmpty') }}
        </div>
        <ul v-else class="space-y-1.5">
          <li
            v-for="addr in savedAddresses"
            :key="addr.id"
            class="flex items-start gap-3 rounded-xl border border-slate-700/60 bg-slate-900/40 px-3 py-2 text-xs"
          >
            <div class="min-w-0 flex-1 space-y-0.5">
              <p v-if="addr.label" class="font-semibold text-slate-200">{{ addr.label }}</p>
              <p class="text-slate-400">{{ addr.address }}</p>
            </div>
            <button class="mt-0.5 shrink-0 text-slate-500 transition-colors hover:text-red-400" @click="deleteAddress(addr.id)">
              <AppIcon name="close" class="h-3.5 w-3.5" />
            </button>
          </li>
        </ul>
      </section>

    </template>

    <CustomerAuthModal v-if="showAuthModal" @close="showAuthModal = false" @authenticated="onAuthenticated" />
    <CustomerAuthModal v-if="showAddPhone" :initial-tab="'phone'" @close="showAddPhone = false" @authenticated="onPhoneAdded" />
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue';
import { RouterLink, useRouter } from 'vue-router';
import AppIcon from '../components/AppIcon.vue';
import CustomerAuthModal from '../components/CustomerAuthModal.vue';
import { useI18n } from '../composables/useI18n';
import { useCartStore } from '../stores/cart';
import { useCustomerStore } from '../stores/customer';
import { useCurrencyStore } from '../stores/currency';
import { useTenantStore } from '../stores/tenant';
import { useToastStore } from '../stores/toast';
import api from '../lib/api';

const { t, formatPrice, formatCurrency } = useI18n();
const customerStore = useCustomerStore();
const currencyStore = useCurrencyStore();
const tenantStore = useTenantStore();
const cart = useCartStore();
const toast = useToastStore();
const router = useRouter();

// ── Cross-restaurant context ──────────────────────────────────────────────────
const tenantName = computed(() => tenantStore.resolvedMeta?.name || '');

// ── Initials avatar ───────────────────────────────────────────────────────────
const initials = computed(() => {
  const name = (customerStore.customer?.name || '').trim();
  if (!name) return '?';
  const parts = name.split(/\s+/).filter(Boolean);
  if (parts.length === 1) return parts[0][0].toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
});

// ── Sign-in benefit tiles ────────────────────────────────────────────────────
const benefits = computed(() => [
  { key: 'orders',    icon: 'menu',     label: t('customerAccount.benefitOrders') },
  { key: 'addresses', icon: 'info',     label: t('customerAccount.benefitAddresses') },
  { key: 'loyalty',   icon: 'calendar', label: t('customerAccount.benefitLoyalty') },
  { key: 'speed',     icon: 'check',    label: t('customerAccount.benefitSpeed') },
]);

const showAuthModal = ref(false);
const showAddPhone = ref(false);

// ── Order expand / reorder ────────────────────────────────────────────────────
const expandedOrders = ref(new Set());

const toggleOrder = (orderNumber) => {
  const s = new Set(expandedOrders.value);
  if (s.has(orderNumber)) s.delete(orderNumber);
  else s.add(orderNumber);
  expandedOrders.value = s;
};

const reorder = (order) => {
  const items = order.items || [];
  if (!items.length) {
    toast.show(t('customerAccount.reorderEmpty'), 'info');
    return;
  }
  items.forEach((item) => {
    cart.add({
      slug: item.dish_slug,
      name: item.dish_name,
      price: parseFloat(item.unit_price) || 0,
      currency: order.currency || 'MAD',
      qty: item.qty,
      note: item.note || '',
      option_ids: (item.options || []).map((o) => o.id).filter(Boolean),
      option_labels: (item.options || []).map((o) => o.name).filter(Boolean),
    });
  });
  toast.show(t('customerAccount.reorderAdded'), 'success');
  router.push({ name: 'cart' });
};

const editableName = ref('');
const savingName = ref(false);

// ── Email ─────────────────────────────────────────────────────────────────────
const showEmailInput = ref(false);
const editableEmail = ref('');
const savingEmail = ref(false);
const emailError = ref('');
const emailInputRef = ref(null);

const openEmailInput = () => {
  editableEmail.value = customerStore.customer?.email || '';
  emailError.value = '';
  showEmailInput.value = true;
  nextTick(() => emailInputRef.value?.focus());
};
const cancelEmailInput = () => {
  showEmailInput.value = false;
  emailError.value = '';
};
const saveEmail = async () => {
  emailError.value = '';
  if (!editableEmail.value) return;
  savingEmail.value = true;
  try {
    const res = await api.patch('/customer/profile/', { email: editableEmail.value });
    customerStore.setCustomer(res.data.customer);
    showEmailInput.value = false;
  } catch (err) {
    emailError.value = err?.response?.data?.detail || t('customerAccount.emailSaveFailed');
  } finally {
    savingEmail.value = false;
  }
};

// ── Locale ────────────────────────────────────────────────────────────────────
const savingLocale = ref(false);
const selectedLocale = ref('en');
const localeConfigured = ref(false);

const LOCALE_LABELS = { en: 'English', fr: 'Français', ar: 'العربية' };
const localeLabelCurrent = computed(() => LOCALE_LABELS[selectedLocale.value] || selectedLocale.value);

const loadingOrders = ref(false);
const ordersError = ref(false);
const apiOrders = ref([]);

const ACTIVE_STATUSES = new Set(['pending', 'confirmed', 'preparing', 'ready']);
const activeOrders = computed(() => apiOrders.value.filter(o => ACTIVE_STATUSES.has(o.status)));

const loadingWallet = ref(false);
const walletTransactions = ref([]);
const walletBalance = computed(() => {
  const raw = customerStore.customer?.wallet_balance;
  const n = Number(raw);
  return Number.isFinite(n) ? n : 0;
});

// ── Loyalty ───────────────────────────────────────────────────────────────────
const loyaltyPoints = computed(() => customerStore.customer?.loyalty_points || 0);
const loyaltyConfig = ref(null);
const redeemAmount = ref(0);
const redeeming = ref(false);
const redeemError = ref('');
const redeemSuccess = ref('');

const redeemableCredit = computed(() => {
  if (!loyaltyConfig.value || !loyaltyPoints.value) return '0.00';
  const pts = Math.min(redeemAmount.value || loyaltyConfig.value.redeem_threshold, loyaltyPoints.value);
  return (pts * Number(loyaltyConfig.value.points_value)).toFixed(2);
});

// ── Saved addresses ───────────────────────────────────────────────────────────
const savedAddresses = ref([]);
const loadingAddresses = ref(false);

const fetchAddresses = async () => {
  if (!customerStore.isAuthenticated) return;
  loadingAddresses.value = true;
  try {
    const res = await api.get('/customer/addresses/');
    savedAddresses.value = res.data || [];
  } catch { /* silent */ } finally {
    loadingAddresses.value = false;
  }
};

const deleteAddress = async (id) => {
  try {
    await api.delete(`/customer/addresses/${id}/`);
    savedAddresses.value = savedAddresses.value.filter((a) => a.id !== id);
    toast.show(t('customerAccount.savedAddressDeleted'), 'success');
  } catch {
    toast.show(t('customerAccount.savedAddressDeleteFailed'), 'error');
  }
};

const fetchLoyaltyConfig = async () => {
  try {
    const res = await api.get('/customer/loyalty/config/');
    if (res.data?.enabled) {
      loyaltyConfig.value = res.data;
      redeemAmount.value = res.data.redeem_threshold;
    }
  } catch { /* silent */ }
};

const redeemPoints = async () => {
  redeemError.value = '';
  redeemSuccess.value = '';
  redeeming.value = true;
  try {
    const res = await api.post('/customer/loyalty/redeem/', { points: redeemAmount.value });
    if (customerStore.customer) {
      customerStore.setCustomer({
        ...customerStore.customer,
        loyalty_points: res.data.new_points_balance,
        wallet_balance: res.data.new_wallet_balance,
      });
    }
    redeemSuccess.value = t('customerAccount.loyaltyRedeemSuccess', {
      pts: res.data.redeemed_points,
      credit: res.data.credit_amount,
    });
    redeemAmount.value = loyaltyConfig.value?.redeem_threshold || 100;
  } catch (err) {
    redeemError.value = err?.response?.data?.detail || t('customerAccount.loyaltyRedeemFailed');
  } finally {
    redeeming.value = false;
  }
};

const formatDate = (iso) => {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  } catch { return iso; }
};

const STATUS_I18N = {
  pending: 'orderStatus.statusPending',
  confirmed: 'orderStatus.statusConfirmed',
  preparing: 'orderStatus.statusPreparing',
  ready: 'orderStatus.statusReady',
  completed: 'orderStatus.statusCompleted',
  cancelled: 'orderStatus.statusCancelled',
};
const statusLabel = (s) => s ? t(STATUS_I18N[s] || 'orderStatus.statusPending') : '';

const TX_LABEL_MAP = {
  topup:   'customerAccount.walletTxTopup',
  payment: 'customerAccount.walletTxPayment',
  refund:  'customerAccount.walletTxRefund',
  bonus:   'customerAccount.walletTxBonus',
  loyalty: 'customerAccount.walletTxLoyalty',
};
const txLabel = (tx) => {
  const base = t(TX_LABEL_MAP[tx.type] || 'customerAccount.walletTxFallback');
  return tx.reference ? `${base} ${tx.reference}` : base;
};

const fetchWallet = async () => {
  if (!customerStore.isAuthenticated) return;
  loadingWallet.value = true;
  try {
    const res = await api.get('/customer/wallet/');
    walletTransactions.value = res.data.transactions || [];
    if (res.data.balance !== undefined && customerStore.customer) {
      customerStore.setCustomer({ ...customerStore.customer, wallet_balance: res.data.balance });
    }
  } catch { /* silent */ } finally {
    loadingWallet.value = false;
  }
};

const fetchOrders = async () => {
  if (!customerStore.isAuthenticated) return;
  loadingOrders.value = true;
  ordersError.value = false;
  try {
    const res = await api.get('/customer/orders/');
    apiOrders.value = res.data.orders || [];
  } catch {
    ordersError.value = true;
  } finally {
    loadingOrders.value = false;
  }
};

const saveName = async () => {
  const trimmed = editableName.value.trim();
  if (!trimmed) return;
  savingName.value = true;
  try {
    const res = await api.patch('/customer/profile/', { name: trimmed });
    customerStore.setCustomer(res.data.customer);
  } catch {
    editableName.value = customerStore.customer?.name || '';
  } finally {
    savingName.value = false;
  }
};

const setLocale = async (code) => {
  if (savingLocale.value || code === selectedLocale.value) return;
  savingLocale.value = true;
  try {
    const res = await api.patch('/customer/profile/', { locale: code });
    customerStore.setCustomer(res.data.customer);
    selectedLocale.value = code;
    localeConfigured.value = true;
    if (customerStore.customer?.id) {
      localStorage.setItem(`locale_set_${customerStore.customer.id}`, '1');
    }
    toast.show(t('customerAccount.localeSaved'), 'success');
  } catch {
    toast.show(t('customerAccount.localeSaveFailed'), 'error');
  } finally {
    savingLocale.value = false;
  }
};

const handleLogout = async () => {
  await customerStore.logout();
  apiOrders.value = [];
  walletTransactions.value = [];
  editableName.value = '';
  selectedLocale.value = 'en';
  localeConfigured.value = false;
  showEmailInput.value = false;
  emailError.value = '';
};

const onAuthenticated = (customer) => {
  customerStore.setCustomer(customer);
  editableName.value = customer?.name || '';
  selectedLocale.value = customer?.locale || 'en';
  localeConfigured.value = !!(customer?.id && localStorage.getItem(`locale_set_${customer.id}`));
  fetchOrders();
  fetchWallet();
};

const onPhoneAdded = (customer) => {
  customerStore.setCustomer(customer);
  editableName.value = customer?.name || '';
  selectedLocale.value = customer?.locale || 'en';
  showAddPhone.value = false;
};

watch(
  () => customerStore.customer,
  (val) => {
    editableName.value = val?.name || '';
    selectedLocale.value = val?.locale || 'en';
    if (val?.id) localeConfigured.value = !!localStorage.getItem(`locale_set_${val.id}`);
  },
  { immediate: true }
);

onMounted(async () => {
  await customerStore.fetchCustomer();
  if (customerStore.isAuthenticated) {
    fetchOrders();
    fetchWallet();
    fetchLoyaltyConfig();
    fetchAddresses();
  }
});
</script>

<style scoped>
.ui-expand-enter-active,
.ui-expand-leave-active {
  transition: opacity 0.2s ease, max-height 0.25s ease;
  overflow: hidden;
  max-height: 600px;
}
.ui-expand-enter-from,
.ui-expand-leave-to {
  opacity: 0;
  max-height: 0;
}
</style>
