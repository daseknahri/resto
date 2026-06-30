<template>
  <div class="ui-safe-bottom min-h-screen bg-slate-950">

    <!-- ══════════════════════════ LOADING ══════════════════════════ -->
    <div v-if="!customerStore.loaded" class="flex min-h-[65vh] flex-col items-center justify-center gap-5 px-4" aria-busy="true" :aria-label="t('common.loading')">
      <div class="h-16 w-16 animate-pulse rounded-3xl border border-slate-700/60 bg-slate-900/60" />
      <div class="space-y-2 text-center">
        <div class="mx-auto h-4 w-32 animate-pulse rounded-lg bg-slate-800" />
        <div class="mx-auto h-3 w-48 animate-pulse rounded-lg bg-slate-800/60" />
      </div>
      <div class="h-9 w-36 animate-pulse rounded-full bg-slate-800" />
    </div>

    <!-- ══════════════════════════ NOT SIGNED IN ══════════════════════════ -->
    <template v-else-if="!customerStore.isAuthenticated">

      <!-- Sign-in hero -->
      <div class="relative overflow-hidden bg-slate-950 ui-reveal">
        <div class="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_50%_-10%,rgba(245,158,11,0.13),transparent_65%)]" />
        <div class="relative px-4 pb-8 pt-10 text-center space-y-5">
          <div class="mx-auto flex h-20 w-20 items-center justify-center rounded-[22px] border border-slate-700/60 bg-gradient-to-br from-slate-800/80 to-slate-900/80 shadow-xl">
            <AppIcon name="user" class="h-9 w-9 text-slate-400" aria-hidden="true" />
          </div>
          <div class="space-y-2">
            <h1 class="ui-page-title">{{ t('customerAccount.title') }}</h1>
            <p class="ui-subtle mx-auto max-w-xs leading-relaxed">{{ t('customerAccount.crossRestaurantNote') }}</p>
          </div>
          <button class="ui-btn-primary ui-touch-target mx-auto gap-2 px-6" @click="showAuthModal = true">
            <AppIcon name="user" class="h-3.5 w-3.5" aria-hidden="true" />
            {{ t('customerAccount.signIn') }}
          </button>
        </div>
      </div>

      <!-- Benefits grid -->
      <div class="px-3 pb-28 space-y-3">
        <div class="grid grid-cols-2 gap-2">
          <div
            v-for="(b, idx) in benefits"
            :key="b.key"
            class="ui-panel ui-reveal flex items-start gap-2.5 p-3"
            :style="{ '--ui-delay': `${idx * 40}ms` }"
          >
            <div class="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-xl border border-[var(--color-secondary)]/25 bg-[var(--color-secondary)]/8">
              <AppIcon :name="b.icon" class="h-3.5 w-3.5 text-[var(--color-secondary)]" aria-hidden="true" />
            </div>
            <p class="mt-0.5 text-[11px] leading-snug text-slate-400">{{ b.label }}</p>
          </div>
        </div>

        <!-- Local orders this device -->
        <section v-if="cart.recentOrders?.length" class="ui-panel p-4 space-y-3">
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
              >{{ t('customerAccount.orderNumber', { number: order.order_number }) }}</RouterLink>
              <span v-if="order.total" class="tabular-nums text-slate-400">{{ formatPrice(order.total) }}</span>
            </li>
          </ul>
        </section>

        <!-- Find order by phone (guest lookup) -->
        <RouterLink
          :to="{ name: 'find-my-order' }"
          class="flex items-center justify-between rounded-2xl border border-slate-700/60 bg-slate-900/40 px-4 py-3 text-sm text-slate-300 hover:border-slate-600 hover:text-white transition-colors"
        >
          <span class="flex items-center gap-2.5">
            <AppIcon name="search" class="h-4 w-4 text-slate-400" aria-hidden="true" />
            {{ t('customerLayout.findMyOrder') }}
          </span>
          <AppIcon name="arrowRight" class="h-3.5 w-3.5 text-slate-500 rtl:scale-x-[-1]" aria-hidden="true" />
        </RouterLink>
      </div>
    </template>

    <!-- ══════════════════════════ SIGNED IN ══════════════════════════ -->
    <template v-else>

      <!-- ──────────────── Account hero header ──────────────── -->
      <header class="relative overflow-hidden bg-slate-950 pb-4 pt-5 ui-reveal">
        <!-- Ambient glow -->
        <div class="pointer-events-none absolute inset-0 bg-gradient-to-b from-[var(--color-secondary)]/7 via-transparent to-transparent" />
        <div class="pointer-events-none absolute -top-10 start-[-2.5rem] h-48 w-48 rounded-full bg-[var(--color-secondary)]/5 blur-3xl" />

        <div class="relative px-4">
          <!-- Avatar + name row -->
          <div class="flex items-start gap-3.5">
            <!-- Avatar -->
            <div class="relative shrink-0">
              <div
                class="flex h-[58px] w-[58px] items-center justify-center rounded-[18px] border-2 shadow-lg shadow-black/30"
                style="border-color:rgba(var(--color-secondary-rgb,245,158,11),0.35);background:linear-gradient(135deg,rgba(var(--color-secondary-rgb,245,158,11),0.18),rgba(var(--color-secondary-rgb,245,158,11),0.04))"
              >
                <span class="text-lg font-black tracking-tight text-[var(--color-secondary)] select-none">{{ initials }}</span>
              </div>
              <!-- Online dot -->
              <span class="absolute -bottom-0.5 end-[-2px] h-3 w-3 rounded-full border-2 border-slate-950 bg-emerald-400" aria-hidden="true" />
            </div>

            <!-- Name + contact + badges -->
            <div class="min-w-0 flex-1 pt-1">
              <h1 class="truncate text-[17px] font-bold leading-tight text-white">
                {{ customerStore.customer?.name || t('customerAccount.title') }}
              </h1>
              <p class="mt-0.5 truncate text-xs text-slate-400">
                {{ customerStore.customer?.phone || customerStore.customer?.email || '—' }}
              </p>
              <div class="mt-1.5 flex flex-wrap gap-1">
                <span
                  v-if="customerStore.customer?.phone_verified"
                  class="inline-flex items-center gap-0.5 rounded-full bg-emerald-500/12 px-1.5 py-0.5 text-[10px] font-medium text-emerald-400"
                >
                  <AppIcon name="check" class="h-2.5 w-2.5" />{{ t('customerAccount.verifiedPhone') }}
                </span>
                <span
                  v-if="customerStore.customer?.email_verified"
                  class="inline-flex items-center gap-0.5 rounded-full bg-sky-500/12 px-1.5 py-0.5 text-[10px] font-medium text-sky-400"
                >
                  <AppIcon name="check" class="h-2.5 w-2.5" />{{ t('customerAccount.verifiedEmail') }}
                </span>
              </div>
            </div>

            <!-- Sign out -->
            <button
              class="shrink-0 rounded-xl border border-slate-700/50 bg-slate-900/50 px-2.5 py-1.5 text-[11px] font-medium text-slate-400 transition-colors hover:border-red-500/40 hover:bg-red-500/8 hover:text-red-300"
              :aria-label="t('common.signOut')"
              @click="handleLogout"
            >
              <AppIcon name="logout" class="inline h-3.5 w-3.5 -mt-0.5" aria-hidden="true" />
            </button>
          </div>

          <!-- Stats row — 2×2 tappable tiles -->
          <div class="mt-4 grid grid-cols-2 gap-2">
            <!-- Wallet -->
            <button
              class="group flex flex-col items-center gap-0.5 rounded-2xl border border-slate-800/70 bg-slate-900/50 px-2 py-3 transition-colors active:scale-[0.97] hover:border-[var(--color-secondary)]/30 hover:bg-[var(--color-secondary)]/5 ui-touch-target"
              :aria-label="t('customerAccount.walletTitle')"
              @click="activeTab = 'wallet'"
            >
              <p class="text-sm font-bold tabular-nums leading-tight" :class="walletBalance > 0 ? 'text-[var(--color-secondary)]' : 'text-slate-500'">
                {{ formatPrice(walletBalance) }}
              </p>
              <p class="text-[10px] uppercase tracking-wider text-slate-500" aria-hidden="true">{{ t('customerAccount.walletTitle') }}</p>
            </button>

            <!-- Loyalty -->
            <button
              class="group flex flex-col items-center gap-0.5 rounded-2xl border border-slate-800/70 bg-slate-900/50 px-2 py-3 transition-colors active:scale-[0.97] hover:border-indigo-500/30 hover:bg-indigo-500/5 ui-touch-target"
              :aria-label="t('customerAccount.loyaltyTitle')"
              @click="activeTab = 'wallet'"
            >
              <p class="text-sm font-bold tabular-nums leading-tight" :class="loyaltyPoints > 0 ? 'text-indigo-300' : 'text-slate-500'">
                {{ loyaltyPoints }}
              </p>
              <p class="text-[10px] uppercase tracking-wider text-slate-500" aria-hidden="true">{{ t('customerAccount.loyaltyPts') }}</p>
            </button>

            <!-- Orders -->
            <button
              class="group flex flex-col items-center gap-0.5 rounded-2xl border border-slate-800/70 bg-slate-900/50 px-2 py-3 transition-colors active:scale-[0.97] hover:border-sky-500/30 hover:bg-sky-500/5 ui-touch-target"
              :aria-label="t('customerAccount.ordersTitle')"
              @click="activeTab = 'orders'"
            >
              <p class="text-sm font-bold tabular-nums leading-tight" :class="loadingOrders ? '' : (apiOrders.length > 0 ? 'text-sky-300' : 'text-slate-500')">
                <span v-if="loadingOrders" class="inline-block h-3.5 w-5 animate-pulse rounded bg-slate-700/70" aria-hidden="true" />
                <template v-else>{{ apiOrders.length }}</template>
              </p>
              <p class="text-[10px] uppercase tracking-wider text-slate-500" aria-hidden="true">{{ t('customerAccount.ordersTitle') }}</p>
            </button>

            <!-- Reviews -->
            <button
              class="group relative flex flex-col items-center gap-0.5 rounded-2xl border border-slate-800/70 bg-slate-900/50 px-2 py-3 transition-colors active:scale-[0.97] hover:border-amber-500/30 hover:bg-amber-500/5 ui-touch-target"
              :aria-label="t('customerAccount.reviewsTabLabel')"
              @click="activeTab = 'reviews'"
            >
              <!-- Pending dot -->
              <span
                v-if="!loadingOrders && pendingReviews.length"
                class="absolute end-2 top-2 h-1.5 w-1.5 rounded-full bg-amber-400"
                aria-hidden="true"
              />
              <p
                class="text-sm font-bold leading-tight"
                :class="submittedReviews.length ? 'text-amber-400' : pendingReviews.length ? 'text-amber-400/60' : 'text-slate-500'"
              >
                <template v-if="loadingOrders">…</template>
                <template v-else-if="submittedReviews.length">{{ reviewsAvgScore.toFixed(1) }}<span class="text-xs">★</span></template>
                <template v-else-if="pendingReviews.length">{{ pendingReviews.length }}</template>
                <template v-else>—</template>
              </p>
              <p class="text-[10px] uppercase tracking-wider text-slate-500">{{ t('customerAccount.reviewsTabLabel') }}</p>
            </button>
          </div>
        </div>
      </header>

      <!-- ──────────────── Live order banner (always visible) ──────────────── -->
      <div v-if="!loadingOrders && activeOrders.length" class="px-3 pb-2 space-y-2 bg-slate-950" aria-live="polite" aria-atomic="false">
        <div
          v-for="order in activeOrders"
          :key="order.order_number"
          class="ui-reveal relative overflow-hidden rounded-2xl border border-[var(--color-secondary)]/35 bg-[var(--color-secondary)]/7 p-3"
        >
          <div class="pointer-events-none absolute inset-0 rounded-2xl ring-1 ring-inset ring-[var(--color-secondary)]/12 motion-safe:animate-pulse" aria-hidden="true" />
          <div class="relative flex items-center gap-3">
            <span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-[var(--color-secondary)]/40 bg-[var(--color-secondary)]/12" aria-hidden="true">
              <span class="block h-2 w-2 motion-safe:animate-ping rounded-full bg-[var(--color-secondary)]" />
            </span>
            <div class="min-w-0 flex-1">
              <p class="truncate text-sm font-semibold text-[var(--color-secondary)]">
                {{ t('customerAccount.orderNumber', { number: order.order_number }) }}
              </p>
              <p class="text-[11px] text-slate-400">{{ statusLabel(order.status) }}</p>
            </div>
            <RouterLink
              :to="{ name: 'order-status', params: { orderNumber: order.order_number } }"
              class="shrink-0 inline-flex items-center gap-1 rounded-xl border border-[var(--color-secondary)]/40 bg-[var(--color-secondary)]/10 px-3 py-1.5 text-xs font-semibold text-[var(--color-secondary)] transition hover:bg-[var(--color-secondary)]/20 ui-touch-target"
            >
              {{ t('customerAccount.trackOrder') }}
              <AppIcon name="arrowRight" class="h-3 w-3 rtl:scale-x-[-1]" aria-hidden="true" />
            </RouterLink>
          </div>
        </div>
      </div>

      <!-- ──────────────── Tab navigation bar ──────────────── -->
      <div class="sticky top-0 z-20 border-b border-slate-800/70 bg-slate-950/96 backdrop-blur-md">
        <nav class="flex" role="tablist" :aria-label="t('customerAccount.tabNav')">
          <button
            v-for="tab in TABS"
            :id="'tab-' + tab.id"
            :key="tab.id"
            role="tab"
            :aria-selected="activeTab === tab.id"
            aria-controls="customer-account-tabpanel"
            class="relative flex flex-1 flex-col items-center gap-0.5 py-2.5 transition-colors"
            :class="activeTab === tab.id ? 'text-[var(--color-secondary)]' : 'text-slate-500 hover:text-slate-300'"
            @click="activeTab = tab.id"
          >
            <AppIcon :name="tab.icon" class="h-4 w-4" />
            <span class="text-[10px] font-semibold leading-none tracking-wide">{{ tab.label }}</span>
            <!-- Active underline -->
            <span
              v-if="activeTab === tab.id"
              class="absolute bottom-0 start-3 end-3 h-[2px] rounded-full bg-[var(--color-secondary)]"
              aria-hidden="true"
            />
            <!-- Live order dot on Orders tab -->
            <span
              v-if="tab.id === 'orders' && activeOrders.length && activeTab !== 'orders'"
              class="absolute end-[calc(50%-10px)] top-1.5 h-1.5 w-1.5 rounded-full bg-[var(--color-secondary)]"
              aria-hidden="true"
            />
            <!-- Pending reviews dot on Reviews tab -->
            <span
              v-if="tab.id === 'reviews' && pendingReviews.length && activeTab !== 'reviews'"
              class="absolute end-[calc(50%-10px)] top-1.5 h-1.5 w-1.5 rounded-full bg-amber-400"
              aria-hidden="true"
            />
          </button>
        </nav>
      </div>

      <!-- ──────────────── Tab content ──────────────── -->
      <div id="customer-account-tabpanel" class="px-3 py-3 pb-28 space-y-3" role="tabpanel" :aria-labelledby="'tab-' + activeTab">

        <!-- ════════════ OVERVIEW TAB ════════════ -->
        <template v-if="activeTab === 'overview'">

          <!-- Quick-nav tiles 2×2 -->
          <div class="grid grid-cols-2 gap-2">
            <!-- Orders tile -->
            <button
              class="group ui-panel ui-surface-lift ui-reveal flex items-center gap-3 p-3.5 text-left hover:border-sky-500/30"
              style="--ui-delay: 0ms"
              @click="activeTab = 'orders'"
            >
              <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl border border-sky-500/25 bg-sky-500/8 transition group-hover:bg-sky-500/15">
                <AppIcon name="calendar" class="h-4 w-4 text-sky-400" aria-hidden="true" />
              </div>
              <div class="min-w-0 flex-1">
                <p class="text-xs font-semibold leading-tight text-slate-200">{{ t('customerAccount.ordersTitle') }}</p>
                <p class="mt-0.5 text-[10px] text-slate-500">{{ t('customerAccount.ordersCount', { count: apiOrders.length }) }}</p>
              </div>
              <AppIcon name="arrowRight" class="h-3.5 w-3.5 shrink-0 text-slate-600 transition group-hover:translate-x-0.5 group-hover:text-sky-400 rtl:scale-x-[-1]" aria-hidden="true" />
            </button>

            <!-- Wallet tile -->
            <button
              class="group ui-panel ui-surface-lift ui-reveal flex items-center gap-3 p-3.5 text-left hover:border-[var(--color-secondary)]/30"
              style="--ui-delay: 40ms"
              @click="activeTab = 'wallet'"
            >
              <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl border border-[var(--color-secondary)]/25 bg-[var(--color-secondary)]/8 transition group-hover:bg-[var(--color-secondary)]/15">
                <AppIcon name="tag" class="h-4 w-4 text-[var(--color-secondary)]" aria-hidden="true" />
              </div>
              <div class="min-w-0 flex-1">
                <p class="text-xs font-semibold leading-tight text-slate-200">{{ t('customerAccount.walletTitle') }}</p>
                <p class="mt-0.5 text-[10px] tabular-nums" :class="walletBalance > 0 ? 'text-[var(--color-secondary)]' : 'text-slate-500'">
                  {{ formatPrice(walletBalance) }}
                </p>
              </div>
              <AppIcon name="arrowRight" class="h-3.5 w-3.5 shrink-0 text-slate-600 transition group-hover:translate-x-0.5 group-hover:text-[var(--color-secondary)] rtl:scale-x-[-1]" aria-hidden="true" />
            </button>

            <!-- Rewards tile -->
            <button
              class="group ui-panel ui-surface-lift ui-reveal flex items-center gap-3 p-3.5 text-left hover:border-indigo-500/30"
              style="--ui-delay: 80ms"
              @click="activeTab = 'wallet'"
            >
              <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl border border-indigo-500/25 bg-indigo-500/8 transition group-hover:bg-indigo-500/15">
                <AppIcon name="star" class="h-4 w-4 text-indigo-400" aria-hidden="true" />
              </div>
              <div class="min-w-0 flex-1">
                <p class="text-xs font-semibold leading-tight text-slate-200">{{ t('customerAccount.loyaltyTitle') }}</p>
                <p v-if="loyaltyConfig?.enabled && loyaltyConfig.redeem_threshold > 0 && loyaltyPoints >= loyaltyConfig.redeem_threshold" class="mt-0.5 text-[10px] font-semibold text-emerald-400">
                  {{ t('customerAccount.loyaltyTileReady') }}
                </p>
                <p v-else-if="loyaltyConfig?.enabled && loyaltyConfig.redeem_threshold > 0" class="mt-0.5 text-[10px] text-indigo-400">
                  {{ loyaltyPoints }} / {{ loyaltyConfig.redeem_threshold }} {{ t('customerAccount.loyaltyPts') }}
                </p>
                <p v-else class="mt-0.5 text-[10px]" :class="loyaltyPoints > 0 ? 'text-indigo-400' : 'text-slate-500'">
                  {{ loyaltyPoints }} {{ t('customerAccount.loyaltyPts') }}
                </p>
              </div>
              <AppIcon name="arrowRight" class="h-3.5 w-3.5 shrink-0 text-slate-600 transition group-hover:translate-x-0.5 group-hover:text-indigo-400 rtl:scale-x-[-1]" aria-hidden="true" />
            </button>

            <!-- Profile tile -->
            <button
              class="group ui-panel ui-surface-lift ui-reveal flex items-center gap-3 p-3.5 text-left hover:border-slate-600/60"
              style="--ui-delay: 120ms"
              @click="activeTab = 'profile'"
            >
              <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl border border-slate-700/50 bg-slate-800/50 transition group-hover:bg-slate-700/60">
                <AppIcon name="settings" class="h-4 w-4 text-slate-400 transition group-hover:text-slate-200" aria-hidden="true" />
              </div>
              <div class="min-w-0 flex-1">
                <p class="text-xs font-semibold leading-tight text-slate-200">{{ t('customerAccount.profileTitle') }}</p>
                <p class="mt-0.5 text-[10px] text-slate-500">{{ t('customerAccount.overviewProfileSubtitle') }}</p>
              </div>
              <AppIcon name="arrowRight" class="h-3.5 w-3.5 shrink-0 text-slate-600 transition group-hover:translate-x-0.5 group-hover:text-slate-300 rtl:scale-x-[-1]" aria-hidden="true" />
            </button>
          </div>

          <!-- Reviews tile (full-width) -->
          <button
            class="group ui-panel ui-surface-lift ui-reveal flex items-center gap-3 p-3.5 text-left hover:border-amber-500/30"
            style="--ui-delay: 160ms"
            @click="activeTab = 'reviews'"
          >
            <div class="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl border border-amber-500/25 bg-amber-500/8 transition group-hover:bg-amber-500/15">
              <AppIcon name="chat" class="h-4 w-4 text-amber-400" aria-hidden="true" />
              <span v-if="pendingReviews.length" class="absolute -end-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-amber-500 text-[9px] font-bold text-white" aria-hidden="true">{{ pendingReviews.length }}</span>
            </div>
            <div class="min-w-0 flex-1">
              <p class="text-xs font-semibold leading-tight text-slate-200">{{ t('customerAccount.reviewsTabLabel') }}</p>
              <p class="mt-0.5 text-[10px]" :class="pendingReviews.length ? 'text-amber-400' : 'text-slate-500'">
                <span v-if="loadingOrders">{{ t('customerAccount.loading') }}</span>
                <template v-else>
                  <span>{{ t('customerAccount.reviewsSubmittedCount', { count: submittedReviews.length }) }}</span>
                  <span v-if="pendingReviews.length" class="ms-1.5 font-semibold">{{ t('customerAccount.reviewsPending', { count: pendingReviews.length }) }}</span>
                </template>
              </p>
            </div>
            <AppIcon name="arrowRight" class="h-3.5 w-3.5 shrink-0 text-slate-600 transition group-hover:translate-x-0.5 group-hover:text-amber-400 rtl:scale-x-[-1]" aria-hidden="true" />
          </button>

          <!-- Book a ride CTA (full-width) -->
          <RouterLink
            :to="{ name: 'ride' }"
            class="group ui-panel ui-surface-lift ui-reveal flex items-center gap-3 p-3.5 text-left hover:border-indigo-500/30"
            style="--ui-delay: 200ms"
          >
            <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl border border-indigo-500/25 bg-indigo-500/8 transition group-hover:bg-indigo-500/15">
              <AppIcon name="truck" class="h-4 w-4 text-indigo-400" aria-hidden="true" />
            </div>
            <div class="min-w-0 flex-1">
              <p class="text-xs font-semibold leading-tight text-slate-200">{{ t('ridePage.title') }}</p>
              <p class="mt-0.5 text-[10px] text-slate-500">{{ t('ridePage.kicker') }}</p>
            </div>
            <AppIcon name="arrowRight" class="h-3.5 w-3.5 shrink-0 text-slate-600 transition group-hover:translate-x-0.5 group-hover:text-indigo-400 rtl:scale-x-[-1]" aria-hidden="true" />
          </RouterLink>

          <!-- Most recent ride -->
          <RouterLink
            v-if="lastRide"
            :to="{ name: 'ride' }"
            class="group ui-panel ui-reveal block p-4 space-y-3 hover:border-teal-500/30"
            style="--ui-delay: 260ms"
          >
            <div class="flex items-center justify-between gap-2">
              <p class="ui-kicker">{{ t('customerAccount.overviewLastRide') }}</p>
              <AppIcon name="arrowRight" class="h-3 w-3 shrink-0 text-slate-600 transition group-hover:translate-x-0.5 group-hover:text-teal-400 rtl:scale-x-[-1]" aria-hidden="true" />
            </div>
            <div class="flex items-start gap-2.5 rounded-xl border border-slate-700/60 bg-slate-900/40 px-3 py-2.5 text-xs">
              <span
                class="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full"
                :class="{
                  'bg-emerald-400': lastRide.status === 'completed',
                  'bg-red-400': lastRide.status === 'cancelled',
                  'bg-slate-500': lastRide.status !== 'completed' && lastRide.status !== 'cancelled',
                }"
                aria-hidden="true"
              />
              <div class="min-w-0 flex-1 space-y-1">
                <p class="truncate font-semibold text-slate-200" :title="lastRide.dropoff_address">{{ lastRide.dropoff_address }}</p>
                <div class="flex flex-wrap items-center gap-2 text-slate-500">
                  <span v-if="lastRide.fare" class="tabular-nums text-slate-400">{{ formatPrice(lastRide.fare) }}</span>
                  <span v-if="lastRide.created_at">{{ formatDate(lastRide.created_at) }}</span>
                  <span class="rounded-full border border-slate-700/60 bg-slate-900/50 px-1.5 py-0.5 text-[10px] text-slate-400">{{ rideStatusLabel(lastRide.status) }}</span>
                </div>
              </div>
            </div>
          </RouterLink>

          <div v-else-if="lastRideChecked" class="ui-panel ui-reveal p-4 space-y-2" style="--ui-delay: 260ms">
            <p class="ui-kicker">{{ t('customerAccount.overviewLastRide') }}</p>
            <p class="text-xs text-slate-400">{{ t('customerAccount.overviewNoRides') }}</p>
            <RouterLink
              :to="{ name: 'ride' }"
              class="ui-press inline-flex items-center gap-1.5 rounded-full border border-teal-500/40 bg-teal-500/8 px-3 py-1.5 text-[11px] font-semibold text-teal-300 transition hover:border-teal-500/70 hover:bg-teal-500/15"
            >{{ t('customerAccount.overviewBookRide') }}<AppIcon name="arrowRight" class="h-3 w-3 rtl:scale-x-[-1]" aria-hidden="true" /></RouterLink>
          </div>

          <!-- Re-order rail (last 3 orders) -->
          <div v-if="apiOrders.length" class="ui-panel ui-reveal p-4 space-y-2.5" style="--ui-delay: 240ms">
            <div class="flex items-center justify-between gap-2">
              <p class="ui-kicker">{{ t('customerAccount.overviewRecentOrders') }}</p>
              <button class="ui-press inline-flex items-center gap-1 text-[11px] font-medium text-[var(--color-secondary)] transition hover:opacity-75" @click="activeTab = 'orders'">
                {{ t('customerAccount.overviewViewAll') }}
                <AppIcon name="arrowRight" class="h-3 w-3 rtl:scale-x-[-1]" aria-hidden="true" />
              </button>
            </div>
            <div
              v-for="ord in apiOrders.slice(0, 3)"
              :key="ord.order_number"
              class="flex items-center gap-2.5 rounded-xl border border-slate-700/60 bg-slate-900/40 px-3 py-2.5 text-xs"
            >
              <span
                class="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full"
                :class="{
                  'animate-pulse bg-amber-400': ACTIVE_STATUSES.has(ord.status),
                  'bg-emerald-400': ord.status === 'completed',
                  'bg-red-400': ord.status === 'cancelled',
                  'bg-slate-500': !ACTIVE_STATUSES.has(ord.status) && ord.status !== 'completed' && ord.status !== 'cancelled',
                }"
              />
              <div class="min-w-0 flex-1 space-y-0.5">
                <div class="flex flex-wrap items-center gap-1.5">
                  <RouterLink
                    :to="{ name: 'order-status', params: { orderNumber: ord.order_number } }"
                    class="font-semibold text-[var(--color-secondary)] hover:opacity-80"
                  >{{ t('customerAccount.orderNumber', { number: ord.order_number }) }}</RouterLink>
                  <span class="rounded-full border border-slate-700/60 bg-slate-900/50 px-1.5 py-0.5 text-[10px] text-slate-400">{{ statusLabel(ord.status) }}</span>
                </div>
                <div class="flex flex-wrap items-center gap-2 text-slate-500">
                  <span v-if="ord.total" class="tabular-nums text-slate-400">{{ formatPrice(ord.total) }}</span>
                  <span v-if="ord.created_at">{{ formatDate(ord.created_at) }}</span>
                </div>
              </div>
              <button
                v-if="ord.items?.length"
                class="ui-press shrink-0 inline-flex items-center gap-1 rounded-lg border border-[var(--color-secondary)]/40 bg-[var(--color-secondary)]/8 px-2.5 py-1.5 text-[11px] font-semibold text-[var(--color-secondary)] transition hover:bg-[var(--color-secondary)]/18"
                @click="reorder(ord)"
              >
                <AppIcon name="refresh" class="h-3 w-3" aria-hidden="true" />
                {{ t('customerAccount.reorder') }}
              </button>
            </div>
          </div>

          <!-- Referral programme card (only when the tenant has it enabled) -->
          <div
            v-if="referralEnabled && customerStore.customer?.referral_code"
            class="ui-panel ui-reveal p-4 space-y-3"
            style="--ui-delay: 280ms"
          >
            <div class="flex items-center justify-between gap-2">
              <p class="ui-kicker">{{ t('customerAccount.referralTitle') }}</p>
              <span v-if="customerStore.customer?.referral_reward_given" class="rounded-full border border-emerald-500/40 bg-emerald-500/8 px-2 py-0.5 text-[10px] font-semibold text-emerald-300">
                {{ t('customerAccount.referralRewarded') }}
              </span>
            </div>
            <p class="text-xs text-slate-400">{{ t('customerAccount.referralHint', { points: referralRewardPoints }) }}</p>
            <div class="flex items-center gap-2 rounded-xl border border-slate-700/60 bg-slate-900/40 px-3 py-2.5">
              <code class="flex-1 font-mono text-sm font-bold tracking-widest text-[var(--color-secondary)]">{{ customerStore.customer.referral_code }}</code>
              <button
                v-if="typeof navigator !== 'undefined' && 'share' in navigator"
                class="ui-press shrink-0 rounded-lg border border-slate-700/60 bg-slate-800/60 px-2.5 py-1.5 text-[11px] font-semibold text-slate-300 transition hover:border-slate-600 hover:text-white"
                :aria-label="t('customerAccount.referralShare')"
                @click="shareReferralLink"
              >
                {{ t('customerAccount.referralShare') }}
              </button>
              <button
                class="ui-press shrink-0 rounded-lg border border-slate-700/60 bg-slate-800/60 px-2.5 py-1.5 text-[11px] font-semibold text-slate-300 transition hover:border-slate-600 hover:text-white"
                :class="referralCopied ? 'border-emerald-500/50 bg-emerald-500/10 !text-emerald-300' : ''"
                @click="copyReferralLink"
              >
                {{ referralCopied ? t('customerAccount.referralCopied') : t('customerAccount.referralCopy') }}
              </button>
            </div>
          </div>

          <!-- Profile completeness nudge -->
          <div
            v-if="!customerStore.customer?.phone && !customerStore.customer?.email"
            class="flex items-center gap-3 rounded-2xl border border-amber-500/25 bg-amber-500/6 px-3.5 py-3"
          >
            <div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border border-amber-500/30 bg-amber-500/10">
              <AppIcon name="info" class="h-4 w-4 text-amber-400" />
            </div>
            <div class="min-w-0 flex-1">
              <p class="text-xs font-semibold text-amber-200">{{ t('customerAccount.completeProfile') }}</p>
              <p class="mt-0.5 text-[11px] text-slate-400">{{ t('customerAccount.completeProfileHint') }}</p>
            </div>
            <button
              class="shrink-0 rounded-xl bg-amber-500/18 px-2.5 py-1.5 text-[11px] font-semibold text-amber-300 transition hover:bg-amber-500/28"
              @click="activeTab = 'profile'"
            >{{ t('customerAccount.completeProfileAdd') }}</button>
          </div>
        </template>


        <!-- ════════════ ORDERS TAB ════════════ -->
        <template v-else-if="activeTab === 'orders'">
          <!-- Vertical filter chips -->
          <div v-if="VERTICAL_FILTER_OPTIONS.length > 1" class="flex gap-2 overflow-x-auto pb-1 scrollbar-none">
            <button
              v-for="opt in VERTICAL_FILTER_OPTIONS"
              :key="opt.id"
              type="button"
              class="shrink-0 rounded-full border px-3 py-1 text-xs font-medium transition-colors"
              :class="selectedVertical === opt.id
                ? 'border-[var(--color-secondary)] bg-[var(--color-secondary)]/15 text-[var(--color-secondary)]'
                : 'border-slate-700 text-slate-400 hover:border-slate-500 hover:text-slate-200'"
              @click="selectVertical(opt.id)"
            >{{ opt.label }}</button>
          </div>

          <!-- Order search -->
          <div class="relative">
            <svg class="pointer-events-none absolute start-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
              <path fill-rule="evenodd" d="M9 3.5a5.5 5.5 0 1 0 0 11 5.5 5.5 0 0 0 0-11ZM2 9a7 7 0 1 1 12.452 4.391l3.328 3.329a.75.75 0 1 1-1.06 1.06l-3.329-3.328A7 7 0 0 1 2 9Z" clip-rule="evenodd"/>
            </svg>
            <input
              v-model.trim="orderSearch"
              type="search"
              class="w-full rounded-xl border border-slate-700/60 bg-slate-800/50 py-2 ps-9 pe-3 text-sm text-slate-200 placeholder-slate-500 focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
              :placeholder="t('customerAccount.orderSearchPlaceholder')"
            />
          </div>

          <!-- Order history across all restaurants (marketplace index) -->
          <div v-if="marketplaceOrders.length" class="ui-panel ui-reveal overflow-hidden p-0">
            <div class="border-b border-slate-800/70 px-4 py-3">
              <p class="ui-kicker">{{ t('customerAccount.allOrdersTitle') }}</p>
              <p class="mt-0.5 text-[10px] text-slate-500">{{ t('customerAccount.allOrdersHint') }}</p>
            </div>
            <div v-if="!filteredMarketplaceOrders.length" class="px-4 py-6 text-center text-sm text-slate-500">
              {{ t('customerAccount.orderSearchNoResults') }}
            </div>
            <ul v-else class="divide-y divide-slate-800/60">
              <li v-for="o in filteredMarketplaceOrders" :key="o.restaurant_slug + o.order_number">
                <div class="flex items-center gap-3 px-4 py-3">
                  <!-- Status dot -->
                  <span
                    class="mt-0.5 h-1.5 w-1.5 shrink-0 self-start rounded-full"
                    :class="{
                      'animate-pulse bg-amber-400': ACTIVE_STATUSES.has(o.status),
                      'bg-emerald-400': o.status === 'completed',
                      'bg-red-400': o.status === 'cancelled',
                      'bg-slate-500': !ACTIVE_STATUSES.has(o.status) && o.status !== 'completed' && o.status !== 'cancelled',
                    }"
                    aria-hidden="true"
                  />
                  <RouterLink
                    v-if="o.restaurant_slug"
                    :to="{ name: 'marketplace-order-status', params: { slug: o.restaurant_slug, orderNumber: o.order_number } }"
                    class="min-w-0 flex-1"
                  >
                    <p class="truncate text-sm font-medium text-slate-200" :title="o.restaurant_name || o.restaurant_slug">{{ o.restaurant_name || o.restaurant_slug }}</p>
                    <div class="mt-0.5 flex flex-wrap items-center gap-1.5">
                      <span class="font-mono text-[11px] text-slate-500">#{{ o.order_number }}</span>
                      <span
                        class="rounded-full border border-slate-700/60 bg-slate-900/50 px-1.5 py-0.5 text-[10px]"
                        :class="{
                          'text-amber-400': ACTIVE_STATUSES.has(o.status),
                          'text-emerald-400': o.status === 'completed',
                          'text-red-400': o.status === 'cancelled',
                          'text-slate-400': !ACTIVE_STATUSES.has(o.status) && o.status !== 'completed' && o.status !== 'cancelled',
                        }"
                      >{{ mktOrderStatus(o.status) }}</span>
                      <span v-if="o.vertical" class="rounded-full border border-slate-700/40 bg-slate-800/50 px-1.5 py-0.5 text-[10px] text-slate-500">{{ VERTICAL_SVC_LABELS[o.vertical] || o.vertical }}</span>
                      <span class="text-[11px] text-slate-500">{{ formatDate(o.created_at) }}</span>
                    </div>
                  </RouterLink>
                  <div v-else class="min-w-0 flex-1">
                    <p class="truncate text-sm font-medium text-slate-200" :title="o.restaurant_name">{{ o.restaurant_name }}</p>
                    <p class="text-[11px] text-slate-500"><span class="font-mono">#{{ o.order_number }}</span> · {{ formatDate(o.created_at) }}</p>
                  </div>
                  <div class="flex shrink-0 items-center gap-2">
                    <span class="text-sm font-semibold tabular-nums text-slate-300">{{ formatPrice(o.total) }}</span>
                    <button
                      v-if="o.restaurant_slug && o.items_snapshot?.length"
                      class="rounded-full border border-slate-700 px-2.5 py-1 text-[11px] font-semibold text-slate-300 hover:border-[var(--color-secondary,#f59e0b)] hover:text-[var(--color-secondary,#f59e0b)] transition-colors"
                      @click="reorderMarketplace(o)"
                    >{{ t('customerAccount.reorder') }}</button>
                    <button
                      v-if="o.can_cancel && o.restaurant_slug"
                      :disabled="cancellingOrderNumber === o.order_number"
                      class="text-[11px] text-red-400/70 transition-colors hover:text-red-300 disabled:opacity-40"
                      @click.stop="cancelMarketplaceOrder(o)"
                    >{{ cancellingOrderNumber === o.order_number ? t('common.loading') : t('customerAccount.cancelOrder') }}</button>
                  </div>
                </div>
              </li>
            </ul>
          </div>

          <!-- Unfiltered-empty: no marketplace orders at all -->
          <div
            v-else-if="!selectedVertical && !loadingMarketplaceOrders && customerStore.isAuthenticated"
            class="ui-panel ui-reveal p-5 text-center space-y-2"
          >
            <div class="flex h-10 w-10 items-center justify-center rounded-full bg-slate-800/80 mx-auto">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" class="h-5 w-5 text-slate-500" aria-hidden="true"><path d="M6 2 3 6v14a2 2 0 002 2h14a2 2 0 002-2V6l-3-4zM3 6h18M16 10a4 4 0 01-8 0"/></svg>
            </div>
            <p class="text-sm text-slate-400">{{ t('customerAccount.noOrdersYet') }}</p>
          </div>

          <!-- Filtered-empty: a service filter is active but returned no orders -->
          <div
            v-else-if="selectedVertical && !loadingMarketplaceOrders"
            class="ui-panel ui-reveal p-5 text-center space-y-2"
          >
            <div class="flex h-10 w-10 items-center justify-center rounded-full bg-slate-800/80 mx-auto">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" class="h-5 w-5 text-slate-500" aria-hidden="true"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
            </div>
            <p class="text-sm text-slate-400">{{ t('customerAccount.noOrdersInService') }}</p>
          </div>

          <div class="ui-panel overflow-hidden p-0">
            <!-- Header -->
            <div class="flex items-center justify-between gap-2 border-b border-slate-800/70 px-4 py-3">
              <div>
                <p class="ui-kicker">{{ t('customerAccount.ordersTitle') }}</p>
                <p v-if="tenantName" class="mt-0.5 text-[10px] text-slate-500">{{ t('customerAccount.atRestaurant', { name: tenantName }) }}</p>
              </div>
              <span v-if="apiOrders.length" class="rounded-full border border-slate-700/60 bg-slate-900/50 px-2 py-0.5 text-[11px] tabular-nums text-slate-400">{{ apiOrders.length }}</span>
            </div>

            <!-- Content -->
            <div class="p-4 space-y-2">
              <div v-if="loadingOrders" class="space-y-2">
                <div v-for="i in 3" :key="i" class="h-14 animate-pulse rounded-xl bg-slate-800/50" />
              </div>
              <div v-else-if="ordersError" class="flex items-start gap-3 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
                <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-3.5 w-3.5 shrink-0 text-red-400" fill="currentColor">
                  <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm-.75-9.25a.75.75 0 011.5 0v3.5a.75.75 0 01-1.5 0v-3.5zm.75 6a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd" />
                </svg>
                <p class="flex-1 text-xs text-red-300">{{ t('customerAccount.fetchError') }}</p>
                <button
                  class="shrink-0 rounded-lg border border-red-500/40 px-2.5 py-1 text-[10px] font-semibold text-red-300 transition hover:bg-red-500/10"
                  @click="fetchOrders"
                >{{ t('common.retry') }}</button>
              </div>

              <div
                v-else-if="!apiOrders.length && !cart.recentOrders.length"
                class="ui-empty-state text-center p-6 space-y-2"
              >
                <AppIcon name="calendar" class="mx-auto h-8 w-8 text-slate-600" aria-hidden="true" />
                <p class="text-sm font-semibold text-slate-300">{{ t('customerAccount.ordersEmpty') }}</p>
              </div>

              <ul v-else-if="apiOrders.length" class="space-y-2">
                <li
                  v-for="(order, idx) in apiOrders"
                  :key="order.order_number"
                  class="ui-reveal rounded-xl border border-slate-700/60 bg-slate-900/40 text-xs overflow-hidden"
                  :style="{ '--ui-delay': `${Math.min(idx, 9) * 28}ms` }"
                >
                  <div class="flex items-start gap-2.5 px-3 py-2.5">
                    <span
                      class="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full"
                      :class="{
                        'animate-pulse bg-amber-400': ACTIVE_STATUSES.has(order.status),
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
                        >{{ t('customerAccount.orderNumber', { number: order.order_number }) }}</RouterLink>
                        <span class="rounded-full border border-slate-700/60 bg-slate-900/50 px-1.5 py-0.5 text-[10px] text-slate-400">{{ statusLabel(order.status) }}</span>
                      </div>
                      <div class="flex flex-wrap items-center gap-2 text-slate-500">
                        <span v-if="order.fulfillment_type">{{
                          order.fulfillment_type === 'pickup'   ? t('orderStatus.fulfillmentPickup')   :
                          order.fulfillment_type === 'delivery' ? t('orderStatus.fulfillmentDelivery') :
                          t('orderStatus.fulfillmentTable', { table: order.table_label || '' })
                        }}</span>
                        <span v-if="order.total" class="font-medium tabular-nums text-slate-400">{{ formatPrice(order.total) }}</span>
                        <span v-if="order.created_at">{{ formatDate(order.created_at) }}</span>
                      </div>
                      <div v-if="order.has_rating" class="flex items-center gap-1 text-[11px] text-amber-400">
                        <span class="tracking-tight">{{ '★'.repeat(order.rating_score) }}{{ '☆'.repeat(5 - order.rating_score) }}</span>
                        <span class="text-slate-600">·</span>
                        <span class="text-slate-500">{{ t('customerAccount.reviewsReviewed') }}</span>
                      </div>
                      <button
                        v-else-if="order.status === 'completed'"
                        class="text-[11px] text-slate-500 transition-colors hover:text-amber-400"
                        @click="activeTab = 'reviews'"
                      >{{ t('customerAccount.reviewsRateNudge') }}</button>
                      <button
                        v-if="order.can_cancel"
                        :disabled="cancellingOrderNumber === order.order_number"
                        class="mt-0.5 text-[11px] text-red-400/70 transition-colors hover:text-red-300 disabled:opacity-40"
                        @click.stop="cancelOrder(order)"
                      >{{ cancellingOrderNumber === order.order_number ? t('common.loading') : t('customerAccount.cancelOrder') }}</button>
                    </div>
                    <div class="mt-0.5 flex shrink-0 flex-col items-end gap-1">
                      <button
                        v-if="order.items?.length"
                        class="rounded-lg border border-slate-700/50 bg-slate-800/50 px-2 py-1 text-[10px] font-medium text-slate-400 transition hover:border-slate-600 hover:text-slate-200"
                        :aria-expanded="expandedOrders.has(order.order_number)"
                        @click="toggleOrder(order.order_number)"
                      >{{ expandedOrders.has(order.order_number) ? t('customerAccount.orderHideItems') : t('customerAccount.orderShowItems') }}</button>
                      <button
                        v-if="order.status === 'completed' && order.items?.length"
                        class="rounded-lg border border-slate-700/50 bg-slate-800/50 px-2 py-1 text-[10px] font-medium text-slate-400 transition hover:border-slate-600 hover:text-slate-200"
                        @click="receiptOrder = order"
                      >{{ t('customerAccount.viewReceipt') }}</button>
                    </div>
                  </div>
                  <Transition name="ui-expand">
                    <div
                      v-if="expandedOrders.has(order.order_number) && order.items?.length"
                      class="border-t border-slate-700/50 px-3 pb-3 pt-2.5 space-y-2"
                    >
                      <ul class="space-y-1.5">
                        <li v-for="(item, itemIdx) in order.items" :key="itemIdx" class="flex items-start gap-2 text-slate-300">
                          <span class="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-slate-700/80 bg-slate-800/70 text-[10px] font-bold text-slate-100 tabular-nums">{{ item.qty }}</span>
                          <span class="min-w-0 flex-1 leading-snug">
                            {{ item.dish_name }}
                            <span v-if="item.options?.length" class="ms-1 text-slate-500">({{ item.options.map(o => o.name).join(', ') }})</span>
                          </span>
                          <span class="shrink-0 tabular-nums font-semibold text-[var(--color-secondary)]">{{ formatPrice(item.subtotal) }}</span>
                        </li>
                      </ul>
                      <!-- Fee/discount breakdown -->
                      <div v-if="order.delivery_fee > 0 || order.tip_amount > 0 || order.promotion_discount > 0 || order.loyalty_discount > 0" class="mt-1.5 space-y-0.5 border-t border-slate-700/40 pt-1.5 text-[11px] text-slate-500">
                        <div v-if="order.promotion_discount > 0" class="flex items-center justify-between gap-2">
                          <span>{{ t('customerAccount.receiptPromoDiscount') }}</span>
                          <span class="tabular-nums text-emerald-400">-{{ formatPrice(order.promotion_discount) }}</span>
                        </div>
                        <div v-if="order.loyalty_discount > 0" class="flex items-center justify-between gap-2">
                          <span>{{ t('customerAccount.receiptLoyaltyDiscount') }}</span>
                          <span class="tabular-nums text-emerald-400">-{{ formatPrice(order.loyalty_discount) }}</span>
                        </div>
                        <div v-if="order.delivery_fee > 0" class="flex items-center justify-between gap-2">
                          <span>{{ t('customerAccount.receiptDeliveryFee') }}</span>
                          <span class="tabular-nums">+{{ formatPrice(order.delivery_fee) }}</span>
                        </div>
                        <div v-if="order.tip_amount > 0" class="flex items-center justify-between gap-2">
                          <span>{{ t('customerAccount.receiptTip') }}</span>
                          <span class="tabular-nums">+{{ formatPrice(order.tip_amount) }}</span>
                        </div>
                      </div>
                      <button
                        class="ui-press mt-1 inline-flex items-center gap-1.5 rounded-lg border border-[var(--color-secondary)]/40 bg-[var(--color-secondary)]/8 px-3 py-1.5 text-[11px] font-semibold text-[var(--color-secondary)] transition hover:bg-[var(--color-secondary)]/18"
                        @click="reorder(order)"
                      >
                        <AppIcon name="refresh" class="h-3 w-3" aria-hidden="true" />
                        {{ t('customerAccount.reorder') }}
                      </button>
                    </div>
                  </Transition>
                </li>
              </ul>

              <!-- Load more button -->
              <div v-if="ordersHasMore || loadingMoreOrders" class="pt-1 text-center">
                <button
                  type="button"
                  class="inline-flex items-center gap-1.5 rounded-xl border border-slate-700/60 bg-slate-900/40 px-4 py-2 text-xs font-medium text-slate-400 transition hover:border-slate-600 hover:text-slate-200 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-slate-500"
                  :disabled="loadingMoreOrders"
                  @click="loadMoreOrders"
                >
                  <svg v-if="loadingMoreOrders" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
                  <AppIcon v-else name="chevronDown" class="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                  {{ loadingMoreOrders ? t('common.loading') : t('customerAccount.loadMoreOrders') }}
                </button>
              </div>

              <!-- Local-only orders (pre-login) -->
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
            </div>
          </div>
        </template>


        <!-- ════════════ RESERVATIONS TAB ════════════ -->
        <template v-else-if="activeTab === 'reservations'">
          <div class="ui-panel overflow-hidden p-0">
            <!-- Header -->
            <div class="flex items-center justify-between gap-2 border-b border-slate-800/70 px-4 py-3">
              <div>
                <p class="ui-kicker">{{ t('customerAccount.reservationsTitle') }}</p>
                <p class="mt-0.5 text-[10px] text-slate-500">{{ t('customerAccount.reservationsHint') }}</p>
              </div>
              <span v-if="apiReservations.length" class="rounded-full border border-slate-700/60 bg-slate-900/50 px-2 py-0.5 text-[11px] tabular-nums text-slate-400">{{ apiReservations.length }}</span>
            </div>

            <!-- Content -->
            <div class="p-4 space-y-2">
              <!-- Loading skeleton -->
              <div v-if="loadingReservations" class="space-y-2">
                <div v-for="i in 3" :key="i" class="h-14 animate-pulse rounded-xl bg-slate-800/50" />
              </div>

              <!-- Error -->
              <div v-else-if="reservationsError" class="flex items-start gap-3 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
                <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-3.5 w-3.5 shrink-0 text-red-400" fill="currentColor">
                  <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm-.75-9.25a.75.75 0 011.5 0v3.5a.75.75 0 01-1.5 0v-3.5zm.75 6a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd" />
                </svg>
                <p class="flex-1 text-xs text-red-300">{{ t('customerAccount.fetchError') }}</p>
                <button
                  class="shrink-0 rounded-lg border border-red-500/40 px-2.5 py-1 text-[10px] font-semibold text-red-300 transition hover:bg-red-500/10"
                  @click="fetchReservations"
                >{{ t('common.retry') }}</button>
              </div>

              <!-- Empty state -->
              <div v-else-if="!apiReservations.length" class="py-6 text-center">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" class="mx-auto mb-3 h-8 w-8 text-slate-700" aria-hidden="true">
                  <path d="M7 3v4M17 3v4M4 8h16M5 5h14a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1" /><path d="M9 15l2 2 4-4" />
                </svg>
                <p class="text-sm font-medium text-slate-500">{{ t('customerAccount.reservationsEmpty') }}</p>
                <p class="mt-1 text-[11px] text-slate-600">{{ t('customerAccount.reservationsEmptyHint') }}</p>
              </div>

              <!-- Reservation list -->
              <ul v-else class="divide-y divide-slate-800/60 -mx-4 -mb-4">
                <li
                  v-for="res in apiReservations"
                  :key="res.id"
                  class="flex items-start justify-between gap-3 px-4 py-3"
                >
                  <div class="min-w-0 flex-1">
                    <p class="truncate text-sm font-semibold text-slate-200">{{ res.restaurant_name || res.restaurant_slug }}</p>
                    <p class="mt-0.5 text-[11px] text-slate-400">{{ formatReservationDateTime(res.booked_for) }}</p>
                    <p class="mt-0.5 text-[10px] text-slate-500">
                      {{ res.party_size === 1 ? t('customerAccount.reservationPartySizeSingle') : t('customerAccount.reservationPartySize', { n: res.party_size }) }}
                      <template v-if="res.notes"> · <span class="italic">{{ res.notes }}</span></template>
                    </p>
                  </div>
                  <div class="flex shrink-0 flex-col items-end gap-1.5">
                    <span
                      class="rounded-full border px-2 py-0.5 text-[10px] font-semibold"
                      :class="reservationStatusClass(res.status)"
                    >{{ reservationStatusLabel(res.status) }}</span>
                    <RouterLink
                      v-if="res.cancel_token && res.restaurant_slug"
                      :to="{ name: 'reservation-manage', params: { token: res.cancel_token } }"
                      class="text-[10px] text-[var(--color-secondary)]/70 hover:text-[var(--color-secondary)] transition-colors"
                    >{{ t('customerAccount.reservationManageLink') }} →</RouterLink>
                  </div>
                </li>
              </ul>
            </div>
          </div>
        </template>


        <!-- ════════════ WALLET TAB ════════════ -->
        <template v-else-if="activeTab === 'wallet'">

          <!-- Verify-phone gate: no verified phone → no usable wallet -->
          <div v-if="!walletVerified" class="ui-panel flex items-start gap-3 border-amber-500/30 bg-amber-500/8 p-4" role="status">
            <div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border border-amber-500/30 bg-amber-500/10">
              <AppIcon name="wallet" class="h-4 w-4 text-amber-300" />
            </div>
            <div class="min-w-0 space-y-0.5">
              <p class="text-sm font-semibold text-amber-200">{{ t('customerAccount.walletVerifyTitle') }}</p>
              <p class="text-xs text-amber-200/70">{{ t('customerAccount.walletVerifySubtitle') }}</p>
            </div>
          </div>

          <!-- Balance hero card -->
          <div class="relative overflow-hidden rounded-3xl border border-[var(--color-secondary)]/20 bg-gradient-to-br from-[var(--color-secondary)]/10 via-slate-900/95 to-slate-950 p-5">
            <div class="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,rgba(245,158,11,0.08),transparent_65%)]" />
            <div class="relative flex items-center justify-between gap-4">
              <div>
                <p class="text-[11px] font-semibold uppercase tracking-widest text-slate-400">{{ t('customerAccount.walletTitle') }}</p>
                <p class="mt-1.5 text-3xl font-black tabular-nums leading-none" :class="walletBalance > 0 ? 'text-[var(--color-secondary)]' : 'text-slate-500'">
                  {{ formatPrice(walletBalance) }}
                </p>
                <p class="mt-1 text-[11px] text-slate-500">{{ walletBalance > 0 ? t('customerAccount.walletBalance') : t('customerAccount.walletNoBalance') }}</p>
              </div>
              <div class="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl border border-[var(--color-secondary)]/20 bg-[var(--color-secondary)]/8">
                <AppIcon name="wallet" class="h-6 w-6 text-[var(--color-secondary)]/70" />
              </div>
            </div>
            <button
              v-if="walletVerified"
              class="relative mt-4 inline-flex w-full items-center justify-center gap-2 rounded-xl border border-[var(--color-secondary)]/30 bg-[var(--color-secondary)]/8 py-2.5 text-sm font-semibold text-[var(--color-secondary)] transition-colors hover:bg-[var(--color-secondary)]/15"
              @click="togglePayCode"
            >
              <AppIcon name="qr" class="h-4 w-4" />
              {{ showPayCode ? t('customerAccount.payCodeHide') : t('customerAccount.payCodeShow') }}
            </button>
          </div>

          <!-- PSP top-up (Stripe Checkout, visible only when platform flag is on) -->
          <div
            v-if="walletVerified && customerStore.platform?.psp_topup_enabled"
            class="ui-panel space-y-3 p-4"
          >
            <p class="text-sm font-semibold text-slate-200">{{ t('customerAccount.topUpTitle') }}</p>
            <p
              v-if="topUpQueryMsg"
              class="rounded-lg px-3 py-2 text-xs font-medium"
              :class="route.query.topup === 'success' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-amber-500/10 text-amber-400'"
              role="status"
            >{{ topUpQueryMsg }}</p>
            <label class="flex flex-col gap-1 text-xs text-slate-400">
              <span>{{ t('customerAccount.topUpAmountLabel') }}</span>
              <input
                v-model.number="topUpAmount"
                type="number"
                min="10"
                max="2000"
                step="10"
                class="ui-input w-full"
                :placeholder="t('customerAccount.topUpAmountHint')"
                :disabled="topUpLoading"
              />
            </label>
            <p v-if="topUpError" class="text-xs text-red-400" role="alert">{{ topUpError }}</p>
            <button
              class="w-full rounded-xl border border-[var(--color-secondary)]/30 bg-[var(--color-secondary)]/8 py-2.5 text-sm font-semibold text-[var(--color-secondary)] transition-colors hover:bg-[var(--color-secondary)]/15 disabled:opacity-50"
              :disabled="topUpLoading || !topUpAmount"
              @click="initTopUp"
            >
              <span v-if="topUpLoading">{{ t('customerAccount.topUpLoading') }}</span>
              <span v-else>{{ t('customerAccount.topUpBtn') }}</span>
            </button>
          </div>

          <!-- Empty-wallet onboarding guide — shown only until first top-up -->
          <div
            v-if="walletVerified && walletBalance <= 0 && !loadingWallet"
            class="ui-panel space-y-4 p-4"
          >
            <div class="flex items-center gap-2">
              <div class="flex h-7 w-7 shrink-0 items-center justify-center rounded-xl border border-[var(--color-secondary)]/20 bg-[var(--color-secondary)]/8">
                <svg viewBox="0 0 20 20" fill="currentColor" class="h-4 w-4 text-[var(--color-secondary)]/70" aria-hidden="true">
                  <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a.75.75 0 000 1.5h.253a.25.25 0 01.244.304l-.459 2.066A1.75 1.75 0 0010.747 15H11a.75.75 0 000-1.5h-.253a.25.25 0 01-.244-.304l.459-2.066A1.75 1.75 0 009.253 9H9z" clip-rule="evenodd" />
                </svg>
              </div>
              <p class="text-sm font-semibold text-slate-200">{{ t('customerAccount.walletHowTitle') }}</p>
            </div>
            <ol class="space-y-3">
              <li class="flex items-start gap-3">
                <span class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[var(--color-secondary)]/15 text-[10px] font-bold text-[var(--color-secondary)]" aria-hidden="true">1</span>
                <p class="text-xs leading-relaxed text-slate-400">{{ t('customerAccount.walletHowStep1') }}</p>
              </li>
              <li class="flex items-start gap-3">
                <span class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[var(--color-secondary)]/15 text-[10px] font-bold text-[var(--color-secondary)]" aria-hidden="true">2</span>
                <p class="text-xs leading-relaxed text-slate-400">{{ t('customerAccount.walletHowStep2') }}</p>
              </li>
              <li class="flex items-start gap-3">
                <span class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[var(--color-secondary)]/15 text-[10px] font-bold text-[var(--color-secondary)]" aria-hidden="true">3</span>
                <p class="text-xs leading-relaxed text-slate-400">{{ t('customerAccount.walletHowStep3') }}</p>
              </li>
            </ol>
            <button
              class="w-full rounded-xl border border-[var(--color-secondary)]/25 bg-[var(--color-secondary)]/8 py-2.5 text-xs font-semibold text-[var(--color-secondary)] transition-colors hover:bg-[var(--color-secondary)]/15"
              @click="togglePayCode"
            >{{ t('customerAccount.walletShowQr') }}</button>
          </div>

          <!-- Pay code (QR) — restaurant scans this to top up the wallet -->
          <div v-if="showPayCode" class="ui-panel flex flex-col items-center gap-3 p-5">
            <p class="text-sm font-semibold text-slate-200">{{ t('customerAccount.payCodeTitle') }}</p>
            <div class="rounded-2xl bg-white p-3">
              <img v-if="payCodeImg" :src="payCodeImg" :alt="t('customerAccount.payCodeTitle')" class="h-44 w-44" />
              <div v-else class="flex h-44 w-44 items-center justify-center" role="status" :aria-label="t('common.loading')">
                <div class="h-8 w-8 animate-spin rounded-full border-2 border-slate-300 border-t-slate-600" aria-hidden="true" />
              </div>
            </div>
            <p class="text-center text-[11px] text-slate-500">{{ t('customerAccount.payCodeHint') }}</p>
            <button class="text-xs text-[var(--color-secondary)] hover:underline" @click="refreshPayCode">{{ t('customerAccount.payCodeRefresh') }}</button>
            <div v-if="pushSupported && pushEnabled" class="w-full border-t border-slate-700/50 pt-3 text-center">
              <button
                v-if="!pushSubscribed"
                class="ui-press text-xs font-semibold text-[var(--color-secondary)] hover:underline disabled:opacity-50"
                :disabled="pushLoading"
                @click="pushSubscribe"
              >{{ t('customerAccount.notifyEnable') }}</button>
              <p v-else class="text-[11px] text-emerald-400">{{ t('customerAccount.notifyOn') }}</p>
            </div>
          </div>

          <!-- Voucher redemption -->
          <div v-if="walletVerified" class="ui-panel p-4 space-y-3">
            <div class="flex items-center gap-2">
              <div class="flex h-7 w-7 shrink-0 items-center justify-center rounded-xl border border-[var(--color-secondary)]/20 bg-[var(--color-secondary)]/8">
                <AppIcon name="tag" class="h-3.5 w-3.5 text-[var(--color-secondary)]/70" />
              </div>
              <p class="text-sm font-semibold text-slate-200">{{ t('customerAccount.voucherTitle') }}</p>
            </div>
            <div class="flex gap-2">
              <input
                v-model="voucherCode"
                type="text"
                maxlength="32"
                autocomplete="off"
                class="ui-input flex-1 text-sm uppercase tracking-wider"
                :placeholder="t('customerAccount.voucherPlaceholder')"
                :disabled="voucherLoading"
                @keyup.enter="redeemVoucher"
              />
              <button
                class="inline-flex shrink-0 items-center gap-1.5 rounded-xl bg-[var(--color-secondary)] px-4 py-2 text-sm font-semibold text-slate-950 disabled:opacity-50 transition-opacity"
                :disabled="!voucherCode.trim() || voucherLoading"
                :aria-busy="voucherLoading"
                @click="redeemVoucher"
              >
                <svg v-if="voucherLoading" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-4 w-4 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
                {{ voucherLoading ? t('common.loading') : t('customerAccount.voucherRedeem') }}
              </button>
            </div>
            <div v-if="voucherError" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
              <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
              <p class="flex-1 text-sm text-red-300">{{ voucherError }}</p>
            </div>
            <p v-if="voucherSuccess" role="status" class="text-xs text-emerald-300">{{ voucherSuccess }}</p>
          </div>

          <!-- Send credit (P2P gifting) — only when enabled AND the sender is verified -->
          <div v-if="p2pEnabled && walletVerified" class="ui-panel p-4 space-y-3">
            <div class="flex items-center gap-2">
              <div class="flex h-7 w-7 shrink-0 items-center justify-center rounded-xl border border-[var(--color-secondary)]/20 bg-[var(--color-secondary)]/8">
                <AppIcon name="wallet" class="h-3.5 w-3.5 text-[var(--color-secondary)]/70" />
              </div>
              <p class="text-sm font-semibold text-slate-200">{{ t('customerAccount.sendTitle') }}</p>
            </div>
            <p class="text-[11px] text-slate-500">{{ t('customerAccount.sendSubtitle') }}</p>
            <input
              v-model="sendPhone"
              type="tel"
              autocomplete="off"
              class="ui-input w-full text-sm"
              :placeholder="t('customerAccount.sendPhonePlaceholder')"
              :disabled="sending"
            />
            <div class="flex gap-2">
              <input
                v-model="sendAmount"
                type="number"
                step="0.01"
                min="0.01"
                class="ui-input flex-1 text-sm"
                :placeholder="t('customerAccount.sendAmountPlaceholder')"
                :disabled="sending"
              />
              <button
                class="inline-flex shrink-0 items-center gap-1.5 rounded-xl bg-[var(--color-secondary)] px-4 py-2 text-sm font-semibold text-slate-950 transition-opacity disabled:opacity-50"
                :disabled="!sendPhone.trim() || !sendAmount || sending"
                :aria-busy="sending"
                @click="sendCredit"
              >
                <svg v-if="sending" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
                {{ sending ? t('common.loading') : t('customerAccount.sendBtn') }}
              </button>
            </div>
            <input
              v-model="sendNote"
              type="text"
              maxlength="200"
              class="ui-input w-full text-sm"
              :placeholder="t('customerAccount.sendNotePlaceholder')"
              :disabled="sending"
            />
            <div v-if="sendError" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
              <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
              <p class="flex-1 text-sm text-red-300">{{ sendError }}</p>
            </div>
            <p v-if="sendSuccess" role="status" class="text-xs text-emerald-300">{{ sendSuccess }}</p>
          </div>

          <!-- Transactions -->
          <div class="ui-panel overflow-hidden p-0">
            <div class="border-b border-slate-800/70 px-4 py-3">
              <p class="ui-kicker">{{ t('customerAccount.walletTransactions') }}</p>
            </div>
            <!-- Per-vertical filter chips (server-side ?vertical= filter) -->
            <div
              v-if="WALLET_FILTER_OPTIONS.length > 1"
              class="flex gap-2 overflow-x-auto border-b border-slate-800/70 px-4 py-2.5 scrollbar-none"
            >
              <button
                v-for="opt in WALLET_FILTER_OPTIONS"
                :key="opt.id"
                type="button"
                class="shrink-0 rounded-full border px-3 py-1 text-xs font-medium transition-colors"
                :class="walletVertical === opt.id
                  ? 'border-[var(--color-secondary)] bg-[var(--color-secondary)]/15 text-[var(--color-secondary)]'
                  : 'border-slate-700 text-slate-400 hover:border-slate-500 hover:text-slate-200'"
                :aria-pressed="walletVertical === opt.id"
                @click="selectWalletVertical(opt.id)"
              >{{ opt.label }}</button>
            </div>
            <div class="p-4 space-y-2">
              <div v-if="loadingWallet" class="space-y-2">
                <div v-for="i in 3" :key="i" class="h-10 animate-pulse rounded-xl bg-slate-800/50" />
              </div>
              <div
                v-else-if="walletError"
                class="flex items-center justify-between gap-2 rounded-xl border border-red-500/25 bg-red-500/8 px-4 py-3 text-xs text-red-300"
                role="alert"
              >
                <span>{{ t('customerAccount.walletLoadFailed') }}</span>
                <button
                  type="button"
                  class="shrink-0 rounded-lg border border-red-500/35 px-2.5 py-1 text-[11px] font-semibold text-red-300 transition hover:bg-red-500/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400/50"
                  @click="fetchWallet"
                >{{ t('common.retry') }}</button>
              </div>
              <div v-else-if="!walletTransactions.length" class="ui-empty-state text-center p-5 space-y-2">
                <AppIcon name="tag" class="mx-auto h-7 w-7 text-slate-600" aria-hidden="true" />
                <p class="text-sm font-semibold text-slate-300">{{ walletVertical ? t('customerAccount.walletNoTransactionsFiltered') : t('customerAccount.walletNoTransactions') }}</p>
              </div>
              <ul v-else class="space-y-1.5">
                <template v-for="(group, gi) in walletTransactionGroups" :key="group.key">
                  <!-- Date group header -->
                  <li
                    :class="gi > 0 ? 'pt-2' : ''"
                    class="px-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500"
                  >{{ group.label }}</li>
                  <li
                    v-for="tx in group.items"
                    :key="tx.id"
                    role="button"
                    tabindex="0"
                    :aria-label="t('customerAccount.walletViewReceipt')"
                    class="flex cursor-pointer items-center justify-between gap-2 rounded-xl border border-slate-700/60 bg-slate-900/40 px-3 py-2.5 text-xs transition-colors hover:border-slate-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/40"
                    @click="openWalletReceipt(tx)"
                    @keyup.enter="openWalletReceipt(tx)"
                    @keyup.space.prevent="openWalletReceipt(tx)"
                  >
                    <div class="flex items-center gap-2.5">
                      <div
                        class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full"
                        :class="tx.type === 'loyalty' ? 'bg-indigo-500/12' : tx.type === 'bonus' ? 'bg-violet-500/12' : isOutflow(tx) ? 'bg-red-500/12' : 'bg-emerald-500/12'"
                      >
                        <!-- Loyalty / bonus: star icon -->
                        <svg v-if="tx.type === 'loyalty' || tx.type === 'bonus'" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true" class="h-3.5 w-3.5" :class="tx.type === 'loyalty' ? 'text-indigo-400' : 'text-violet-400'"><path d="M8 1.25 9.618 4.528l3.617.526-2.617 2.551.618 3.602L8 9.47l-3.236 1.737.618-3.602-2.617-2.551 3.617-.526z"/></svg>
                        <!-- Outflow: arrow up -->
                        <svg v-else-if="isOutflow(tx)" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" class="h-3.5 w-3.5 text-red-400"><path d="M8 13V3M5 6l3-3 3 3"/></svg>
                        <!-- Inflow: arrow down -->
                        <svg v-else viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" class="h-3.5 w-3.5 text-emerald-400"><path d="M8 3v10M5 10l3 3 3-3"/></svg>
                      </div>
                      <div class="min-w-0 space-y-0.5">
                        <p class="font-medium text-slate-200">{{ txLabel(tx) }}</p>
                        <p class="text-[11px] text-slate-500">
                          <span v-if="tx.vertical" class="me-1 text-slate-400">{{ VERTICAL_SVC_LABELS[tx.vertical] || tx.vertical }} ·</span><span v-if="tx.note" class="me-1 text-slate-400">{{ tx.note }} ·</span>{{ formatDate(tx.created_at) }}
                        </p>
                      </div>
                    </div>
                    <span
                      class="shrink-0 font-semibold tabular-nums"
                      :class="isOutflow(tx) ? 'text-red-300' : 'text-emerald-300'"
                    >{{ formatPrice(tx.amount) }}</span>
                  </li>
                </template>
              </ul>
            </div>
          </div>

          <!-- Transaction receipt / detail sheet -->
          <Teleport to="body">
            <div
              v-if="walletReceipt"
              class="fixed inset-0 z-[60] flex items-end justify-center bg-black/60 p-0 sm:items-center sm:p-4"
              role="dialog"
              aria-modal="true"
              :aria-label="t('customerAccount.walletReceiptTitle')"
              @click.self="walletReceipt = null"
            >
              <div class="ui-panel w-full max-w-sm space-y-4 rounded-b-none rounded-t-2xl p-5 sm:rounded-2xl">
                <div class="flex items-center justify-between gap-2">
                  <p class="text-sm font-semibold text-slate-200">{{ t('customerAccount.walletReceiptTitle') }}</p>
                  <button
                    type="button"
                    class="rounded-lg p-1 text-slate-400 transition-colors hover:text-slate-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/40"
                    :aria-label="t('common.close')"
                    @click="walletReceipt = null"
                  >
                    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" aria-hidden="true" class="h-4 w-4"><path d="M4 4l8 8M12 4l-8 8"/></svg>
                  </button>
                </div>
                <div class="flex flex-col items-center gap-1 py-1">
                  <span
                    class="text-2xl font-black tabular-nums"
                    :class="isOutflow(walletReceipt) ? 'text-red-300' : 'text-emerald-300'"
                  >{{ isOutflow(walletReceipt) ? '−' : '+' }}{{ formatPrice(walletReceipt.amount) }}</span>
                  <span class="text-xs font-medium text-slate-400">{{ txLabel(walletReceipt) }}</span>
                </div>
                <dl class="space-y-2 border-t border-slate-800/70 pt-3 text-xs">
                  <div class="flex items-center justify-between gap-3">
                    <dt class="text-slate-500">{{ t('customerAccount.walletReceiptType') }}</dt>
                    <dd class="font-medium text-slate-300">{{ t(TX_LABEL_MAP[walletReceipt.type] || 'customerAccount.walletTxFallback') }}</dd>
                  </div>
                  <div v-if="walletReceipt.vertical" class="flex items-center justify-between gap-3">
                    <dt class="text-slate-500">{{ t('customerAccount.walletReceiptService') }}</dt>
                    <dd class="font-medium text-slate-300">{{ VERTICAL_SVC_LABELS[walletReceipt.vertical] || walletReceipt.vertical }}</dd>
                  </div>
                  <div v-if="walletReceipt.reference" class="flex items-center justify-between gap-3">
                    <dt class="text-slate-500">{{ t('customerAccount.walletReceiptReference') }}</dt>
                    <dd class="font-mono text-slate-300">{{ walletReceipt.reference }}</dd>
                  </div>
                  <div v-if="walletReceipt.note" class="flex items-start justify-between gap-3">
                    <dt class="shrink-0 text-slate-500">{{ t('customerAccount.walletReceiptNote') }}</dt>
                    <dd class="text-end text-slate-300">{{ walletReceipt.note }}</dd>
                  </div>
                  <div class="flex items-center justify-between gap-3">
                    <dt class="text-slate-500">{{ t('customerAccount.walletReceiptDate') }}</dt>
                    <dd class="text-slate-300">{{ formatDateTime(walletReceipt.created_at) }}</dd>
                  </div>
                </dl>
                <button
                  type="button"
                  class="w-full rounded-xl border border-slate-700 py-2.5 text-sm font-semibold text-slate-300 transition-colors hover:border-slate-500 hover:text-slate-100"
                  @click="walletReceipt = null"
                >{{ t('common.close') }}</button>
              </div>
            </div>
          </Teleport>

          <!-- Spend by vertical breakdown -->
          <div
            v-if="!loadingWallet && Object.keys(walletSpendByVertical).filter(v => parseFloat(walletSpendByVertical[v]) > 0).length"
            class="ui-panel overflow-hidden p-0"
          >
            <div class="border-b border-slate-800/70 px-4 py-3">
              <p class="ui-kicker">{{ t('customerAccount.spendByService') }}</p>
            </div>
            <ul class="divide-y divide-slate-800/60">
              <li
                v-for="(amount, vertical) in walletSpendByVertical"
                v-show="parseFloat(amount) > 0"
                :key="vertical"
                class="flex items-center justify-between gap-3 px-4 py-2.5 text-sm"
              >
                <span class="text-slate-300">{{ VERTICAL_SVC_LABELS[vertical] || vertical }}</span>
                <span class="tabular-nums font-semibold text-slate-200">{{ formatPrice(parseFloat(amount)) }}</span>
              </li>
            </ul>
          </div>

          <!-- Loyalty / Rewards -->
          <div v-if="loyaltyPoints > 0 || loyaltyConfig" class="ui-panel overflow-hidden p-0">
            <div class="flex items-center justify-between gap-2 border-b border-slate-800/70 px-4 py-3">
              <p class="ui-kicker">{{ t('customerAccount.loyaltyTitle') }}</p>
              <div class="flex items-center gap-1.5">
                <AppIcon name="star" class="h-3.5 w-3.5 text-indigo-400" />
                <p class="text-lg font-bold tabular-nums text-indigo-300">{{ loyaltyPoints }}</p>
                <span class="text-xs text-slate-500">{{ t('customerAccount.loyaltyPts') }}</span>
                <span
                  v-if="loyaltyEquivCredit"
                  class="ms-0.5 rounded-full border border-indigo-500/20 bg-indigo-500/10 px-2 py-0.5 text-[10px] font-medium tabular-nums text-indigo-400"
                  :title="t('customerAccount.loyaltyEquivHint')"
                >≈ {{ loyaltyEquivCredit }}</span>
                <span
                  v-if="tierName"
                  class="ms-0.5 rounded-full px-2 py-0.5 text-[10px] font-semibold"
                  :class="{
                    'border border-amber-700/40 bg-amber-900/20 text-amber-600': tierName === t('customerAccount.tierBronze'),
                    'border border-slate-400/30 bg-slate-500/10 text-slate-300': tierName === t('customerAccount.tierSilver'),
                    'border border-yellow-500/40 bg-yellow-500/10 text-yellow-300': tierName === t('customerAccount.tierGold'),
                  }"
                >{{ tierName }}</span>
              </div>
            </div>
            <div class="p-4 space-y-3">
              <template v-if="loyaltyConfig?.enabled">
                <!-- Tier progress bar (shown when tiers enabled and not yet at max) -->
                <div v-if="tierProgress" class="space-y-1">
                  <div class="flex items-center justify-between text-[11px]">
                    <span class="text-slate-400">{{ t('customerAccount.tierProgressLabel') }}</span>
                    <span class="tabular-nums text-slate-500">{{ t('customerAccount.tierProgressPts', { current: tierProgress.current, next: tierProgress.next, tier: tierProgress.tier }) }}</span>
                  </div>
                  <div class="h-1.5 overflow-hidden rounded-full bg-slate-800/80">
                    <div
                      class="h-full rounded-full bg-gradient-to-r from-amber-500 to-yellow-400 transition-all duration-700"
                      :style="{ width: Math.min((tierProgress.current / tierProgress.next) * 100, 100) + '%' }"
                    />
                  </div>
                </div>
                <div v-if="loyaltyConfig.redeem_threshold > 0" class="space-y-1.5">
                  <div class="flex items-center justify-between text-[11px]">
                    <span class="text-slate-400">{{ t('customerAccount.loyaltyEarnRate', { pts: loyaltyConfig.points_per_unit }) }}</span>
                    <span class="tabular-nums text-slate-500">{{ Math.min(loyaltyPoints, loyaltyConfig.redeem_threshold) }} / {{ loyaltyConfig.redeem_threshold }}</span>
                  </div>
                  <div class="h-1.5 overflow-hidden rounded-full bg-slate-800/80">
                    <div
                      class="h-full rounded-full bg-gradient-to-r from-indigo-500 to-violet-400 transition-all duration-700"
                      :style="{ width: Math.min((loyaltyPoints / loyaltyConfig.redeem_threshold) * 100, 100) + '%' }"
                    />
                  </div>
                </div>

                <p v-if="loyaltyPoints >= loyaltyConfig.redeem_threshold" class="text-xs text-emerald-300">
                  {{ t('customerAccount.loyaltyCanRedeem', { threshold: loyaltyConfig.redeem_threshold, credit: redeemableCredit }) }}
                </p>
                <p v-else class="text-xs text-slate-500">
                  {{ t('customerAccount.loyaltyNeedMore', { need: loyaltyConfig.redeem_threshold - loyaltyPoints, credit: loyaltyUnlockCredit ?? '?' }) }}
                </p>

                <div v-if="loyaltyPoints >= loyaltyConfig.redeem_threshold && walletVerified" class="flex flex-wrap items-center gap-3 pt-1">
                  <div class="flex items-center gap-2">
                    <label class="text-xs text-slate-400">{{ t('customerAccount.loyaltyRedeemLabel') }}</label>
                    <input
                      v-model.number="redeemAmount"
                      type="number"
                      :min="loyaltyConfig.redeem_threshold"
                      :max="loyaltyPoints"
                      :step="loyaltyConfig.redeem_threshold"
                      :aria-label="t('customerAccount.loyaltyRedeemLabel')"
                      class="ui-input w-24 text-sm"
                    />
                  </div>
                  <button
                    class="ui-btn-primary inline-flex items-center gap-1.5 px-3 py-1.5 text-xs"
                    :disabled="redeeming || redeemAmount < loyaltyConfig.redeem_threshold"
                    :aria-busy="redeeming"
                    @click="redeemPoints"
                  >
                    <svg v-if="redeeming" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
                    {{ redeeming ? t('customerAccount.loyaltyRedeeming') : t('customerAccount.loyaltyRedeem') }}
                  </button>
                </div>
                <div v-if="redeemError" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
                  <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
                  <p class="flex-1 text-sm text-red-300">{{ redeemError }}</p>
                </div>
                <p v-if="redeemSuccess" role="status" class="text-xs text-emerald-300">{{ redeemSuccess }}</p>
              </template>
              <p v-else class="text-xs text-slate-500">{{ t('customerAccount.loyaltyNotActive') }}</p>
            </div>
          </div>

          <!-- Loyalty history -->
          <div v-if="loyaltyHistory && loyaltyHistory.events && loyaltyHistory.events.length" class="ui-panel overflow-hidden p-0">
            <div class="border-b border-slate-800/70 px-4 py-3">
              <p class="ui-kicker">{{ t('customerAccount.loyaltyHistoryTitle') }}</p>
            </div>
            <ul class="divide-y divide-slate-800/50">
              <li
                v-for="(ev, idx) in loyaltyHistory.events"
                :key="idx"
                class="flex items-center justify-between gap-3 px-4 py-2.5 text-sm"
              >
                <div class="min-w-0">
                  <p class="truncate text-sm text-slate-300">
                    <span v-if="ev.type === 'earn'">{{ t('customerAccount.loyaltyHistoryEarn', { ref: ev.ref }) }}</span>
                    <span v-else>{{ t('customerAccount.loyaltyHistoryRedeem', { credit: ev.credit }) }}</span>
                  </p>
                  <p class="text-[11px] text-slate-500 tabular-nums">{{ formatDate(ev.date) }}</p>
                </div>
                <span
                  class="shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold tabular-nums"
                  :class="ev.type === 'earn' ? 'bg-indigo-500/12 text-indigo-300 border border-indigo-500/20' : 'bg-amber-500/12 text-amber-300 border border-amber-500/20'"
                >
                  {{ ev.type === 'earn' ? '+' : '-' }}{{ ev.points }} {{ t('customerAccount.loyaltyPts') }}
                </span>
              </li>
            </ul>
          </div>
        </template>


        <!-- ════════════ REVIEWS TAB ════════════ -->
        <template v-else-if="activeTab === 'reviews'">

          <!-- Loading -->
          <div v-if="loadingOrders" class="ui-panel p-4 space-y-2">
            <div v-for="i in 2" :key="i" class="h-24 animate-pulse rounded-xl bg-slate-800/50" />
          </div>

          <!-- No completed orders at all -->
          <div v-else-if="!completedOrders.length" class="ui-empty-state text-center p-8 space-y-2">
            <AppIcon name="star" class="mx-auto h-8 w-8 text-slate-600" aria-hidden="true" />
            <p class="text-sm font-semibold text-slate-300">{{ t('customerAccount.reviewsEmpty') }}</p>
            <p class="text-xs text-slate-500">{{ t('customerAccount.reviewsEmptyHint') }}</p>
          </div>

          <template v-else>

            <!-- Average score card -->
            <div v-if="submittedReviews.length" class="relative overflow-hidden rounded-3xl border border-amber-500/20 bg-gradient-to-br from-amber-500/8 via-slate-900/95 to-slate-950 p-4">
              <div class="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,rgba(245,158,11,0.07),transparent_65%)]" />
              <div class="relative flex items-center gap-4">
                <div class="text-center">
                  <p class="text-4xl font-black tabular-nums leading-none text-amber-400">{{ reviewsAvgScore.toFixed(1) }}</p>
                  <p class="mt-0.5 text-[10px] text-slate-500">{{ t('customerAccount.reviewsOutOf5') }}</p>
                </div>
                <div class="flex-1 space-y-1">
                  <div class="flex gap-0.5">
                    <span
                      v-for="s in 5"
                      :key="s"
                      class="text-xl leading-none"
                      :class="s <= Math.round(reviewsAvgScore) ? 'text-amber-400' : 'text-slate-700'"
                    >★</span>
                  </div>
                  <p class="text-[11px] text-slate-400">
                    {{ t('customerAccount.reviewsSubmittedCount', { count: submittedReviews.length }) }}
                    <span v-if="pendingReviews.length" class="ms-1.5 text-amber-400">{{ t('customerAccount.reviewsPending', { count: pendingReviews.length }) }}</span>
                  </p>
                </div>
              </div>
            </div>

            <!-- ── Pending reviews ── -->
            <div v-if="pendingReviews.length" class="ui-panel overflow-hidden p-0">
              <div class="flex items-center justify-between gap-2 border-b border-slate-800/70 px-4 py-3">
                <div>
                  <p class="ui-kicker">{{ t('customerAccount.reviewsWriteSection') }}</p>
                  <p class="mt-0.5 text-[10px] text-slate-500">{{ t('customerAccount.reviewsWriteSubtitle') }}</p>
                </div>
                <span class="rounded-full border border-amber-500/40 bg-amber-500/12 px-2 py-0.5 text-[11px] font-semibold tabular-nums text-amber-400">{{ pendingReviews.length }}</span>
              </div>
              <div class="p-4 space-y-4">
                <div
                  v-for="(order, idx) in pendingReviews"
                  :key="order.order_number"
                  class="ui-reveal rounded-2xl border border-slate-700/60 bg-slate-900/40 p-3.5 space-y-3"
                  :style="{ '--ui-delay': `${Math.min(idx, 9) * 40}ms` }"
                >
                  <!-- Order info -->
                  <div class="flex items-center gap-2 text-[11px]">
                    <RouterLink
                      :to="{ name: 'order-status', params: { orderNumber: order.order_number } }"
                      class="font-bold text-[var(--color-secondary)] hover:opacity-80"
                    >#{{ order.order_number }}</RouterLink>
                    <span class="text-slate-600">·</span>
                    <span class="text-slate-500">{{ formatDate(order.created_at) }}</span>
                    <span v-if="order.total" class="ms-auto tabular-nums text-slate-400">{{ formatPrice(order.total) }}</span>
                  </div>

                  <!-- Interactive star selector -->
                  <div class="space-y-1">
                    <p class="text-[11px] text-slate-400">{{ t('customerAccount.reviewsYourRating') }}</p>
                    <div class="flex items-center gap-0.5">
                      <button
                        v-for="s in 5"
                        :key="s"
                        type="button"
                        class="select-none text-[26px] leading-none transition-all active:scale-90"
                        :class="s <= (reviewHover[order.order_number] || getDraft(order.order_number).score)
                          ? 'text-amber-400'
                          : 'text-slate-700 hover:text-slate-500'"
                        :aria-label="t('common.rateNStars', { n: s })"
                        :aria-pressed="s <= getDraft(order.order_number).score"
                        @mouseenter="setHover(order.order_number, s)"
                        @mouseleave="setHover(order.order_number, 0)"
                        @click="setDraftScore(order.order_number, s)"
                      >★</button>
                      <span
                        v-if="getDraft(order.order_number).score || reviewHover[order.order_number]"
                        class="ms-2.5 text-xs font-semibold"
                        :class="getDraft(order.order_number).score ? 'text-amber-400' : 'text-slate-500'"
                        aria-live="polite"
                        role="status"
                      >{{ reviewScoreLabels[reviewHover[order.order_number] || getDraft(order.order_number).score] }}</span>
                    </div>
                  </div>

                  <!-- Optional comment (shown after a score is set) -->
                  <Transition name="ui-expand">
                    <div v-if="getDraft(order.order_number).score" class="space-y-1.5">
                      <p class="text-[11px] text-slate-400">{{ t('customerAccount.reviewsComment') }} <span class="text-slate-600">{{ t('customerAccount.reviewsCommentOptional') }}</span></p>
                      <textarea
                        :value="getDraft(order.order_number).comment"
                        rows="2"
                        maxlength="500"
                        class="ui-textarea w-full resize-none text-xs leading-relaxed"
                        :aria-label="t('customerAccount.reviewsComment')"
                        :placeholder="t('customerAccount.reviewsCommentPlaceholder')"
                        @input="setDraftComment(order.order_number, $event.target.value)"
                      />
                      <p class="mt-1 text-end text-xs tabular-nums" :class="(getDraft(order.order_number).comment || '').length >= 480 ? 'text-amber-400' : 'text-slate-600'" aria-live="polite">{{ (getDraft(order.order_number).comment || '').length }}/500</p>
                    </div>
                  </Transition>

                  <!-- Submit button -->
                  <button
                    class="ui-btn-primary w-full justify-center py-2 text-xs"
                    :disabled="!getDraft(order.order_number).score || submittingReview.has(order.order_number)"
                    @click="submitReview(order)"
                  >
                    <AppIcon
                      v-if="submittingReview.has(order.order_number)"
                      name="refresh"
                      class="h-3.5 w-3.5 animate-spin"
                    />
                    {{ submittingReview.has(order.order_number) ? t('customerAccount.reviewsSubmitting') : t('customerAccount.reviewsSubmit') }}
                  </button>
                </div>
              </div>
            </div>

            <!-- ── Submitted reviews ── -->
            <div v-if="submittedReviews.length" class="ui-panel overflow-hidden p-0">
              <div class="border-b border-slate-800/70 px-4 py-3">
                <p class="ui-kicker">{{ t('customerAccount.reviewsSubmittedSection') }}</p>
              </div>
              <div class="p-4 space-y-3">
                <div
                  v-for="order in submittedReviews"
                  :key="order.order_number"
                  class="rounded-2xl border border-slate-700/60 bg-slate-900/40 p-3.5 space-y-2"
                >
                  <div class="flex items-start justify-between gap-3">
                    <div class="space-y-0.5">
                      <RouterLink
                        :to="{ name: 'order-status', params: { orderNumber: order.order_number } }"
                        class="text-xs font-bold text-[var(--color-secondary)] hover:opacity-80"
                      >#{{ order.order_number }}</RouterLink>
                      <p class="text-[10px] text-slate-500">{{ formatDate(order.created_at) }}</p>
                    </div>
                    <div class="flex flex-col items-end gap-0.5">
                      <div class="flex gap-0.5">
                        <span
                          v-for="s in 5"
                          :key="s"
                          class="text-base leading-none"
                          :class="s <= order.rating_score ? 'text-amber-400' : 'text-slate-700'"
                        >★</span>
                      </div>
                      <p class="text-[10px] text-slate-500">{{ order.rating_score }}/5</p>
                    </div>
                  </div>
                  <p v-if="order.rating?.comment" class="rounded-xl border border-slate-700/50 bg-slate-950/40 px-3 py-2 text-xs italic leading-relaxed text-slate-300">
                    "{{ order.rating.comment }}"
                  </p>
                </div>
              </div>
            </div>

          </template>
        </template>


        <!-- ════════════ PROFILE TAB ════════════ -->
        <template v-else-if="activeTab === 'profile'">

          <!-- Driver mode entry -->
          <RouterLink
            :to="{ name: 'driver' }"
            class="ui-panel ui-surface-lift ui-reveal flex items-center justify-between gap-3 p-4 hover:border-emerald-500/40"
            style="--ui-delay: 0ms"
          >
            <div class="flex items-center gap-3">
              <div class="flex h-9 w-9 items-center justify-center rounded-xl border border-emerald-500/30 bg-emerald-500/10">
                <AppIcon name="truck" class="h-4 w-4 text-emerald-300" />
              </div>
              <div>
                <p class="text-sm font-semibold text-slate-100">{{ t('customerAccount.driverMode') }}</p>
                <p class="text-xs text-slate-500">
                  {{ customerStore.customer?.is_driver ? t('customerAccount.driverModeOpen') : t('customerAccount.driverModeJoin') }}
                </p>
              </div>
            </div>
            <AppIcon name="chevronRight" class="h-4 w-4 text-slate-600 rtl:scale-x-[-1]" aria-hidden="true" />
          </RouterLink>

          <!-- Personal info panel (grouped rows) -->
          <div class="ui-panel ui-reveal divide-y divide-slate-800/70 overflow-hidden p-0" style="--ui-delay: 40ms">
            <div class="px-4 py-3">
              <p class="ui-kicker">{{ t('customerAccount.profilePersonalInfo') }}</p>
            </div>

            <!-- Name -->
            <div class="px-4 py-3 space-y-1.5">
              <p class="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{{ t('common.name') }}</p>
              <div class="flex items-center gap-2">
                <input
                  v-model.trim="editableName"
                  type="text"
                  maxlength="80"
                  autocomplete="name"
                  class="ui-input flex-1 py-1.5 text-sm"
                  :placeholder="t('customerAccount.namePlaceholder')"
                  :disabled="savingName"
                />
                <button
                  v-if="editableName !== (customerStore.customer?.name || '')"
                  class="ui-btn-primary inline-flex shrink-0 items-center gap-1.5 px-3 py-1.5 text-xs"
                  :disabled="savingName"
                  :aria-busy="savingName"
                  @click="saveName"
                >
                  <svg v-if="savingName" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
                  {{ savingName ? t('customerAccount.saving') : t('customerAccount.saveName') }}
                </button>
              </div>
            </div>

            <!-- Phone -->
            <div class="px-4 py-3 space-y-1.5">
              <p class="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{{ t('common.phone') }}</p>
              <div class="flex flex-wrap items-center gap-2">
                <span v-if="customerStore.customer?.phone" class="text-sm text-slate-200">{{ customerStore.customer.phone }}</span>
                <button
                  v-else
                  class="inline-flex items-center gap-1 rounded-lg border border-amber-500/40 bg-amber-500/8 px-2.5 py-1 text-[11px] font-medium text-amber-300 transition hover:border-amber-500/70"
                  @click="showAddPhone = true"
                >
                  <AppIcon name="plus" class="h-3 w-3" />
                  {{ t('customerAccount.addPhone') }}
                </button>
                <span
                  v-if="customerStore.customer?.phone_verified"
                  class="inline-flex items-center gap-0.5 rounded-full bg-emerald-500/12 px-1.5 py-0.5 text-[10px] font-medium text-emerald-400"
                >
                  <AppIcon name="check" class="h-2.5 w-2.5" />{{ t('customerAccount.verifiedPhone') }}
                </span>
              </div>
            </div>

            <!-- Email -->
            <div class="px-4 py-3 space-y-1.5">
              <p class="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{{ t('common.email') }}</p>
              <div>
                <div class="flex flex-wrap items-center gap-2">
                  <template v-if="!showEmailInput">
                    <span v-if="customerStore.customer?.email" class="text-sm text-slate-200">{{ customerStore.customer.email }}</span>
                    <button
                      class="inline-flex items-center gap-1 text-[11px] transition-colors"
                      :class="customerStore.customer?.email ? 'text-slate-500 hover:text-slate-300' : 'text-sky-400 hover:text-sky-300'"
                      @click="openEmailInput"
                    >
                      <AppIcon name="plus" class="h-3 w-3" />
                      {{ customerStore.customer?.email ? t('customerAccount.editEmail') : t('customerAccount.addEmail') }}
                    </button>
                    <span
                      v-if="customerStore.customer?.email_verified"
                      class="inline-flex items-center gap-0.5 rounded-full bg-sky-500/12 px-1.5 py-0.5 text-[10px] font-medium text-sky-400"
                    >
                      <AppIcon name="check" class="h-2.5 w-2.5" />{{ t('customerAccount.verifiedEmail') }}
                    </span>
                  </template>
                  <template v-else>
                    <input
                      ref="emailInputRef"
                      v-model.trim="editableEmail"
                      type="email"
                      autocomplete="email"
                      maxlength="254"
                      spellcheck="false"
                      class="ui-input min-w-0 flex-1 py-1.5 text-xs"
                      :placeholder="t('customerAccount.emailPlaceholder')"
                      :aria-label="t('customerAccount.emailPlaceholder')"
                      :aria-invalid="emailError ? 'true' : undefined"
                      aria-describedby="customer-account-email-error"
                      :disabled="savingEmail"
                      @keydown.enter.prevent="saveEmail"
                      @keydown.escape.prevent="cancelEmailInput"
                    />
                    <button class="ui-btn-primary inline-flex shrink-0 items-center gap-1.5 px-2.5 py-1.5 text-xs" :disabled="savingEmail || !editableEmail" :aria-busy="savingEmail" @click="saveEmail">
                      <svg v-if="savingEmail" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
                      {{ savingEmail ? t('customerAccount.saving') : t('common.save') }}
                    </button>
                    <button class="text-xs text-slate-500 transition hover:text-slate-300" @click="cancelEmailInput">{{ t('common.cancel') }}</button>
                  </template>
                </div>
                <p v-if="emailError" id="customer-account-email-error" role="alert" class="mt-1 text-xs text-red-300">{{ emailError }}</p>
              </div>
            </div>

            <!-- Birthday -->
            <div class="px-4 py-3 space-y-1.5">
              <p class="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{{ t('customerAccount.birthdayLabel') }}</p>
              <div class="flex items-center gap-2">
                <input
                  v-model="editableBirthday"
                  type="date"
                  max="2099-12-31"
                  class="ui-input py-1.5 text-sm"
                  :aria-label="t('customerAccount.birthdayLabel')"
                  :disabled="savingBirthday"
                />
                <button
                  v-if="editableBirthday !== (customerStore.customer?.birthday || '')"
                  class="ui-btn-primary inline-flex shrink-0 items-center gap-1.5 px-3 py-1.5 text-xs"
                  :disabled="savingBirthday"
                  :aria-busy="savingBirthday"
                  @click="saveBirthday"
                >
                  <svg v-if="savingBirthday" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
                  {{ savingBirthday ? t('customerAccount.saving') : t('common.save') }}
                </button>
              </div>
              <p class="text-[11px] leading-relaxed text-slate-500">{{ t('customerAccount.birthdayHint') }}</p>
            </div>
          </div>

          <!-- Saved addresses -->
          <div class="ui-panel ui-reveal overflow-hidden p-0" style="--ui-delay: 80ms">
            <div class="flex items-center justify-between gap-2 border-b border-slate-800/70 px-4 py-3">
              <div>
                <p class="ui-kicker">{{ t('customerAccount.savedAddressesTitle') }}</p>
                <p class="mt-0.5 text-[10px] text-slate-500">{{ t('customerAccount.savedAddressesNote') }}</p>
              </div>
              <div class="flex items-center gap-2">
                <span class="text-[10px] text-slate-500">{{ savedAddresses.length }}/10</span>
                <button
                  v-if="!addingAddress && savedAddresses.length < 10"
                  class="ui-press ui-touch-target inline-flex items-center gap-1 rounded-lg border border-slate-700/60 bg-slate-800/50 px-2.5 py-1 text-[11px] font-medium text-slate-300 transition-colors hover:border-slate-600 hover:text-white"
                  @click="addingAddress = true"
                >
                  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" class="h-3 w-3 shrink-0" aria-hidden="true"><path d="M8 3v10M3 8h10"/></svg>
                  {{ t('customerAccount.savedAddressAdd') }}
                </button>
              </div>
            </div>
            <div class="p-4 space-y-2">
              <!-- Add address inline form -->
              <Transition name="ui-fade">
                <form v-if="addingAddress" class="space-y-2 rounded-xl border border-sky-500/25 bg-sky-500/5 p-3" @submit.prevent="addAddress">
                  <label class="block text-[11px] font-medium text-slate-300">
                    {{ t('customerAccount.savedAddressLabelField') }}
                    <input
                      v-model="addrForm.label"
                      type="text"
                      maxlength="60"
                      class="ui-input mt-1 w-full text-xs"
                      :placeholder="t('customerAccount.savedAddressLabelPlaceholder')"
                    />
                  </label>
                  <label class="block text-[11px] font-medium text-slate-300">
                    {{ t('customerAccount.savedAddressField') }}
                    <textarea
                      v-model="addrForm.address"
                      rows="2"
                      maxlength="300"
                      class="ui-textarea mt-1 w-full resize-none text-xs"
                      :placeholder="t('customerAccount.savedAddressAddressPlaceholder')"
                      required
                    />
                  </label>
                  <p v-if="addrError" class="text-[11px] text-red-300" role="alert">{{ addrError }}</p>
                  <div class="flex gap-2">
                    <button
                      type="submit"
                      class="ui-btn-primary ui-press inline-flex items-center gap-1.5 px-4 py-1.5 text-[11px] font-semibold disabled:opacity-50"
                      :disabled="savingAddress"
                    >
                      <svg v-if="savingAddress" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3 w-3 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
                      {{ savingAddress ? t('common.loading') : t('customerAccount.savedAddressSave') }}
                    </button>
                    <button
                      type="button"
                      class="rounded-lg border border-slate-700/60 px-4 py-1.5 text-[11px] font-medium text-slate-400 transition hover:border-slate-600 hover:text-slate-200"
                      :disabled="savingAddress"
                      @click="addingAddress = false; addrForm.label = ''; addrForm.address = ''; addrError = ''"
                    >{{ t('common.cancel') }}</button>
                  </div>
                </form>
              </Transition>
              <div v-if="loadingAddresses" class="space-y-1.5">
                <div v-for="i in 2" :key="i" class="h-12 animate-pulse rounded-xl border border-slate-700/40 bg-slate-800/30" />
              </div>
              <div v-else-if="!savedAddresses.length && !addingAddress" class="rounded-xl border border-dashed border-slate-700/50 px-4 py-4 text-center text-xs text-slate-500">
                {{ t('customerAccount.savedAddressesEmpty') }}
              </div>
              <ul class="space-y-1.5">
                <li
                  v-for="addr in savedAddresses"
                  :key="addr.id"
                  class="rounded-xl border bg-slate-900/40 px-3 py-2.5 text-xs transition-colors"
                  :class="deletingAddressId === addr.id ? 'border-red-500/30' : 'border-slate-700/60'"
                >
                  <div class="flex items-start gap-3">
                    <AppIcon name="location" class="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-500" />
                    <div class="min-w-0 flex-1 space-y-0.5">
                      <p v-if="addr.label" class="font-semibold text-slate-200">{{ addr.label }}</p>
                      <p class="text-slate-400" :title="addr.address">{{ addr.address }}</p>
                    </div>
                    <div class="flex shrink-0 gap-0.5">
                      <!-- Edit toggle -->
                      <button
                        class="ui-touch-target ui-press flex items-center justify-center transition"
                        :class="editingAddressId === addr.id ? 'text-sky-400' : 'text-slate-500 hover:text-sky-400'"
                        :aria-label="t('common.edit')"
                        @click="editingAddressId === addr.id ? editingAddressId = null : startEdit(addr)"
                      >
                        <AppIcon name="pencil" class="h-3.5 w-3.5" aria-hidden="true" />
                      </button>
                      <!-- Delete toggle -->
                      <button
                        class="ui-touch-target ui-press flex items-center justify-center transition"
                        :class="deletingAddressId === addr.id ? 'text-red-400' : 'text-slate-500 hover:text-red-400'"
                        :aria-label="t('common.remove')"
                        @click="deletingAddressId = addr.id; editingAddressId = null; addrDeleteError = ''"
                      >
                        <AppIcon name="close" class="h-3.5 w-3.5" aria-hidden="true" />
                      </button>
                    </div>
                  </div>
                  <!-- Inline edit form -->
                  <Transition name="ui-fade">
                    <form v-if="editingAddressId === addr.id" class="mt-2 space-y-2 border-t border-sky-500/15 pt-2" @submit.prevent="saveEdit">
                      <label class="block text-[11px] font-medium text-slate-300">
                        {{ t('customerAccount.savedAddressLabelField') }}
                        <input v-model="editForm.label" type="text" maxlength="60" class="ui-input mt-1 w-full text-xs" :placeholder="t('customerAccount.savedAddressLabelPlaceholder')" />
                      </label>
                      <label class="block text-[11px] font-medium text-slate-300">
                        {{ t('customerAccount.savedAddressField') }}
                        <textarea v-model="editForm.address" rows="2" maxlength="300" class="ui-textarea mt-1 w-full resize-none text-xs" required />
                      </label>
                      <p v-if="editError" class="text-[11px] text-red-300" role="alert">{{ editError }}</p>
                      <div class="flex gap-2">
                        <button type="submit" class="ui-btn-primary ui-press inline-flex items-center gap-1.5 px-4 py-1.5 text-[11px] font-semibold disabled:opacity-50" :disabled="savingEdit">
                          <svg v-if="savingEdit" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3 w-3 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
                          {{ savingEdit ? t('common.loading') : t('common.save') }}
                        </button>
                        <button type="button" class="rounded-lg border border-slate-700/60 px-4 py-1.5 text-[11px] font-medium text-slate-400 transition hover:border-slate-600 hover:text-slate-200" :disabled="savingEdit" @click="editingAddressId = null">{{ t('common.cancel') }}</button>
                      </div>
                    </form>
                  </Transition>
                  <!-- Inline delete confirmation -->
                  <Transition name="ui-fade">
                    <div v-if="deletingAddressId === addr.id" class="mt-2 border-t border-red-500/15 pt-2 space-y-2">
                      <p v-if="addrDeleteError" class="text-[11px] text-red-300" role="alert">{{ addrDeleteError }}</p>
                      <div class="flex items-center gap-3">
                        <span class="flex-1 text-red-300/80">{{ t('customerAccount.savedAddressConfirmDelete') }}</span>
                        <button class="text-slate-400 transition hover:text-slate-200" @click.stop="deletingAddressId = null; addrDeleteError = ''">{{ t('common.back') }}</button>
                        <button class="font-semibold text-red-300 transition hover:text-red-200" @click.stop="deleteAddress(addr.id)">{{ t('common.remove') }}</button>
                      </div>
                    </div>
                  </Transition>
                </li>
              </ul>
            </div>
          </div>

          <!-- Preferences panel -->
          <div class="ui-panel ui-reveal divide-y divide-slate-800/70 overflow-hidden p-0" style="--ui-delay: 120ms">
            <div class="px-4 py-3">
              <p class="ui-kicker">{{ t('customerAccount.preferencesTitle') }}</p>
            </div>

            <!-- Language -->
            <div class="px-4 py-3 space-y-2">
              <p class="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{{ t('customerAccount.localeTitle') }}</p>
              <div v-if="!localeConfigured" class="flex flex-wrap gap-2">
                <button
                  v-for="lang in [{ code: 'en', label: 'English' }, { code: 'fr', label: 'Français' }, { code: 'ar', label: 'العربية' }]"
                  :key="lang.code"
                  :aria-pressed="selectedLocale === lang.code"
                  class="rounded-full border px-3 py-1 text-xs transition-colors"
                  :class="selectedLocale === lang.code
                    ? 'border-[var(--color-secondary)] bg-[var(--color-secondary)]/15 text-[var(--color-secondary)]'
                    : 'border-slate-700 text-slate-400 hover:border-slate-500 hover:text-slate-200'"
                  :disabled="savingLocale"
                  @click="setLocale(lang.code)"
                >{{ lang.label }}</button>
              </div>
              <div v-else class="flex items-center justify-between gap-2">
                <span class="text-sm text-slate-300">{{ localeLabelCurrent }}</span>
                <button class="text-[11px] text-slate-500 transition hover:text-slate-300" @click="localeConfigured = false">{{ t('common.change') }}</button>
              </div>
            </div>

            <!-- Display currency -->
            <div class="px-4 py-3 space-y-2">
              <p class="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{{ t('customerAccount.displayCurrency') }}</p>
              <div class="flex flex-wrap gap-2">
                <button
                  v-for="r in currencyStore.available"
                  :key="r.code"
                  :aria-pressed="currencyStore.selected === r.code"
                  class="rounded-full border px-3 py-1 text-xs transition-colors"
                  :class="currencyStore.selected === r.code
                    ? 'border-[var(--color-secondary)] bg-[var(--color-secondary)]/15 text-[var(--color-secondary)]'
                    : 'border-slate-700 text-slate-400 hover:border-slate-500 hover:text-slate-200'"
                  @click="currencyStore.setCode(r.code)"
                >{{ r.code }} <span class="opacity-60">{{ r.symbol }}</span></button>
              </div>
            </div>

            <!-- Notifications -->
            <div id="notifications-section" class="px-4 py-3 space-y-2.5">
              <p class="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{{ t('customerAccount.notificationsTitle') }}</p>
              <label class="flex items-center justify-between gap-3">
                <span class="text-sm text-slate-300">{{ t('customerAccount.notifyOrderUpdates') }}</span>
                <input
                  type="checkbox"
                  class="h-4 w-4 rounded border-slate-600 bg-slate-900 text-[var(--color-secondary)] focus:ring-[var(--color-secondary)]/40"
                  :checked="!!customerStore.customer?.notify_order_updates"
                  :disabled="savingPrefs"
                  @change="savePref('notify_order_updates', $event.target.checked)"
                />
              </label>
              <label class="flex items-center justify-between gap-3">
                <span class="text-sm text-slate-300">{{ t('customerAccount.notifyReviewPrompts') }}</span>
                <input
                  type="checkbox"
                  class="h-4 w-4 rounded border-slate-600 bg-slate-900 text-[var(--color-secondary)] focus:ring-[var(--color-secondary)]/40"
                  :checked="!!customerStore.customer?.notify_review_prompts"
                  :disabled="savingPrefs"
                  @change="savePref('notify_review_prompts', $event.target.checked)"
                />
              </label>
              <label class="flex items-center justify-between gap-3">
                <span class="text-sm text-slate-300">{{ t('customerAccount.notifyPromotions') }}</span>
                <input
                  type="checkbox"
                  class="h-4 w-4 rounded border-slate-600 bg-slate-900 text-[var(--color-secondary)] focus:ring-[var(--color-secondary)]/40"
                  :checked="!!customerStore.customer?.notify_promotions"
                  :disabled="savingPrefs"
                  @change="savePref('notify_promotions', $event.target.checked)"
                />
              </label>
              <!-- Browser push notifications opt-in -->
              <div v-if="pushSupported && pushEnabled" class="flex items-start justify-between gap-3 pt-0.5">
                <div class="min-w-0 flex-1">
                  <p class="text-sm text-slate-300">{{ t('customerAccount.notifyBrowserPush') }}</p>
                  <p v-if="!pushSubscribed" class="mt-0.5 text-[10px] text-slate-500">{{ t('customerAccount.notifyBrowserPushHint') }}</p>
                </div>
                <button
                  v-if="!pushSubscribed"
                  class="shrink-0 rounded-full border border-[var(--color-secondary)]/50 bg-[var(--color-secondary)]/10 px-3 py-1 text-[11px] font-semibold text-[var(--color-secondary)] transition hover:bg-[var(--color-secondary)]/20 disabled:opacity-50 ui-press"
                  :disabled="pushLoading"
                  @click="pushSubscribe"
                >{{ t('customerAccount.notifyEnable') }}</button>
                <span v-else class="shrink-0 text-[11px] font-semibold text-emerald-400">{{ t('customerAccount.notifyOn') }}</span>
              </div>
            </div>
          </div>

          <!-- Per-service notification preferences -->
          <div class="ui-panel ui-reveal overflow-hidden p-0" style="--ui-delay: 80ms">
            <button
              type="button"
              class="flex w-full items-center justify-between gap-3 border-b border-slate-800/70 px-4 py-3 text-start"
              :aria-expanded="serviceProfilesOpen"
              @click="serviceProfilesOpen = !serviceProfilesOpen; !serviceProfiles || Object.keys(serviceProfiles).length === 0 ? fetchServiceProfiles() : null"
            >
              <p class="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{{ t('customerAccount.perServiceNotifs') }}</p>
              <svg
                viewBox="0 0 16 16"
                fill="none"
                stroke="currentColor"
                stroke-width="1.75"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
                class="h-3.5 w-3.5 shrink-0 text-slate-500 transition-transform"
                :class="serviceProfilesOpen ? 'rotate-180' : ''"
              ><path d="M4 6l4 4 4-4"/></svg>
            </button>
            <Transition name="ui-expand">
              <div v-if="serviceProfilesOpen" class="p-4 space-y-4">
                <p class="text-[11px] leading-relaxed text-slate-500">{{ t('customerAccount.perServiceNotifsHint') }}</p>

                <!-- Loading -->
                <div v-if="loadingServiceProfiles" class="space-y-2">
                  <div v-for="i in 3" :key="i" class="h-10 animate-pulse rounded-xl bg-slate-800/50" />
                </div>

                <!-- Error -->
                <p v-else-if="serviceProfilesError" class="text-xs text-red-400" role="alert">{{ t('customerAccount.perServiceLoadError') }}</p>

                <!-- Per-vertical toggles -->
                <div v-else class="space-y-4">
                  <div
                    v-for="vertical in customerStore.enabledVerticals.filter(v => v !== 'driver')"
                    :key="vertical"
                    class="rounded-xl border border-slate-700/60 bg-slate-900/40 p-3 space-y-2"
                  >
                    <p class="text-xs font-semibold text-slate-300">{{ VERTICAL_SVC_LABELS[vertical] || vertical }}</p>
                    <label class="flex items-center justify-between gap-3">
                      <span class="text-xs text-slate-400">{{ t('customerAccount.notifOrderUpdates') }}</span>
                      <input
                        type="checkbox"
                        class="h-4 w-4 rounded border-slate-600 bg-slate-900 text-[var(--color-secondary)] focus:ring-[var(--color-secondary)]/40"
                        :checked="serviceProfiles[vertical]?.notify_updates !== false"
                        :disabled="savingServiceProfile === vertical"
                        @change="saveServicePref(vertical, 'notify_updates', $event.target.checked)"
                      />
                    </label>
                    <label class="flex items-center justify-between gap-3">
                      <span class="text-xs text-slate-400">{{ t('customerAccount.notifPromotions') }}</span>
                      <input
                        type="checkbox"
                        class="h-4 w-4 rounded border-slate-600 bg-slate-900 text-[var(--color-secondary)] focus:ring-[var(--color-secondary)]/40"
                        :checked="serviceProfiles[vertical]?.notify_promotions !== false"
                        :disabled="savingServiceProfile === vertical"
                        @change="saveServicePref(vertical, 'notify_promotions', $event.target.checked)"
                      />
                    </label>
                  </div>
                </div>
              </div>
            </Transition>
          </div>

          <!-- Privacy & data section -->
          <div class="ui-panel ui-reveal overflow-hidden p-0" style="--ui-delay: 120ms">
            <div class="border-b border-slate-800/70 px-4 py-3">
              <p class="ui-kicker">{{ t('customerAccount.privacyTitle') }}</p>
            </div>

            <!-- Export row -->
            <div class="px-4 py-3 space-y-1.5">
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0 flex-1">
                  <p class="text-sm font-semibold text-slate-200">{{ t('customerAccount.privacyExportTitle') }}</p>
                  <p class="mt-0.5 text-[11px] leading-relaxed text-slate-500">{{ t('customerAccount.privacyExportHint') }}</p>
                </div>
                <button
                  class="shrink-0 inline-flex items-center gap-1.5 rounded-xl border border-slate-700/60 bg-slate-800/50 px-3 py-1.5 text-[11px] font-semibold text-slate-300 transition hover:border-slate-600 hover:text-white disabled:opacity-50 ui-press"
                  :disabled="exportingData"
                  @click="downloadMyData"
                >
                  <svg v-if="exportingData" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
                  <svg v-else aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" class="h-3.5 w-3.5 shrink-0"><path d="M8 2v8M5 7l3 3 3-3M3 12h10"/></svg>
                  {{ t('customerAccount.privacyExportBtn') }}
                </button>
              </div>
            </div>

            <!-- Delete row -->
            <div class="border-t border-slate-800/70 px-4 py-3 space-y-2.5">
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0 flex-1">
                  <p class="text-sm font-semibold text-red-300">{{ t('customerAccount.privacyDeleteTitle') }}</p>
                  <p class="mt-0.5 text-[11px] leading-relaxed text-slate-500">{{ t('customerAccount.privacyDeleteHint') }}</p>
                </div>
                <button
                  v-if="!erasureConfirmVisible"
                  class="shrink-0 inline-flex items-center gap-1.5 rounded-xl border border-red-500/40 bg-red-500/8 px-3 py-1.5 text-[11px] font-semibold text-red-300 transition hover:border-red-500/60 hover:bg-red-500/15 ui-press"
                  @click="erasureConfirmVisible = true"
                >
                  {{ t('customerAccount.privacyDeleteBtn') }}
                </button>
              </div>

              <!-- Guard-blocked error -->
              <p
                v-if="erasureBlockedMsg"
                class="text-[11px] leading-relaxed text-amber-400"
                role="alert"
              >{{ erasureBlockedMsg }}</p>

              <!-- Inline confirm -->
              <Transition name="ui-fade">
                <div
                  v-if="erasureConfirmVisible"
                  class="rounded-xl border border-red-500/30 bg-red-500/6 p-3 space-y-2.5"
                >
                  <p class="text-[11px] leading-relaxed text-red-200">{{ t('customerAccount.privacyDeleteConfirmText') }}</p>
                  <div class="flex gap-2">
                    <button
                      class="inline-flex items-center gap-1.5 rounded-lg border border-red-500/50 bg-red-500/12 px-3 py-1.5 text-[11px] font-semibold text-red-300 transition hover:bg-red-500/20 disabled:opacity-50 ui-press"
                      :disabled="requestingErasure"
                      @click="requestErasure"
                    >
                      <svg v-if="requestingErasure" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
                      {{ t('customerAccount.privacyDeleteConfirmBtn') }}
                    </button>
                    <button
                      class="rounded-lg border border-slate-700/60 px-3 py-1.5 text-[11px] font-medium text-slate-400 transition hover:border-slate-600 hover:text-slate-200"
                      :disabled="requestingErasure"
                      @click="erasureConfirmVisible = false; erasureBlockedMsg = ''"
                    >{{ t('common.cancel') }}</button>
                  </div>
                </div>
              </Transition>
            </div>
          </div>

        </template>

      </div>
    </template>

    <CustomerAuthModal v-if="showAuthModal" @close="showAuthModal = false" @authenticated="onAuthenticated" />
    <CustomerAuthModal v-if="showAddPhone" :initial-tab="'phone'" @close="showAddPhone = false" @authenticated="onPhoneAdded" />

    <!-- Receipt modal -->
    <Teleport to="body">
      <Transition name="ui-fade">
        <div
          v-if="receiptOrder"
          class="fixed inset-0 z-[200] flex items-end justify-center bg-slate-950/80 backdrop-blur-sm sm:items-center print:bg-white print:backdrop-blur-none"
          role="dialog"
          :aria-label="t('customerAccount.viewReceipt')"
          @click.self="receiptOrder = null"
        >
          <div class="receipt-modal w-full max-w-sm rounded-t-2xl border border-slate-700/60 bg-slate-900 p-5 shadow-2xl sm:rounded-2xl print:border-none print:shadow-none print:bg-white print:text-slate-900">
            <div class="mb-4 flex items-start justify-between gap-3 print:hidden">
              <p class="text-sm font-semibold text-slate-100">{{ t('customerAccount.viewReceipt') }}</p>
              <button class="text-slate-500 hover:text-slate-300" :aria-label="t('common.close')" @click="receiptOrder = null">
                <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" class="h-4 w-4" aria-hidden="true"><path d="M3 3l10 10M13 3 3 13"/></svg>
              </button>
            </div>
            <div class="space-y-3 text-[12px]">
              <div class="text-center print:block">
                <p class="font-bold text-slate-100 print:text-slate-900">{{ tenantName }}</p>
                <p class="text-[10px] text-slate-500 print:text-slate-600">{{ t('customerAccount.orderNumber', { number: receiptOrder.order_number }) }}</p>
                <p class="text-[10px] text-slate-500 print:text-slate-600">{{ formatDate(receiptOrder.created_at) }}</p>
              </div>
              <div class="border-t border-dashed border-slate-700/60 pt-3 print:border-slate-300">
                <ul class="space-y-1">
                  <li v-for="(item, idx) in receiptOrder.items" :key="idx" class="flex items-start gap-1.5">
                    <span class="shrink-0 text-slate-500 tabular-nums">{{ item.qty }}×</span>
                    <span class="min-w-0 flex-1 text-slate-200 print:text-slate-800">{{ item.dish_name }}</span>
                    <span class="shrink-0 tabular-nums text-slate-300 print:text-slate-800">{{ formatPrice(item.subtotal) }}</span>
                  </li>
                </ul>
              </div>
              <div class="border-t border-dashed border-slate-700/60 pt-2 space-y-1 print:border-slate-300">
                <div v-if="receiptOrder.promotion_discount > 0" class="flex items-center justify-between gap-2 text-emerald-400">
                  <span>{{ t('customerAccount.receiptPromoDiscount') }}</span>
                  <span class="tabular-nums">-{{ formatPrice(receiptOrder.promotion_discount) }}</span>
                </div>
                <div v-if="receiptOrder.loyalty_discount > 0" class="flex items-center justify-between gap-2 text-emerald-400">
                  <span>{{ t('customerAccount.receiptLoyaltyDiscount') }}</span>
                  <span class="tabular-nums">-{{ formatPrice(receiptOrder.loyalty_discount) }}</span>
                </div>
                <div v-if="receiptOrder.delivery_fee > 0" class="flex items-center justify-between gap-2 text-slate-400">
                  <span>{{ t('customerAccount.receiptDeliveryFee') }}</span>
                  <span class="tabular-nums">{{ formatPrice(receiptOrder.delivery_fee) }}</span>
                </div>
                <div v-if="receiptOrder.tip_amount > 0" class="flex items-center justify-between gap-2 text-slate-400">
                  <span>{{ t('customerAccount.receiptTip') }}</span>
                  <span class="tabular-nums">{{ formatPrice(receiptOrder.tip_amount) }}</span>
                </div>
                <div v-if="receiptOrder.wallet_amount_paid > 0" class="flex items-center justify-between gap-2 text-indigo-300">
                  <span>{{ t('customerAccount.receiptWallet') }}</span>
                  <span class="tabular-nums">-{{ formatPrice(receiptOrder.wallet_amount_paid) }}</span>
                </div>
                <div class="flex items-center justify-between gap-2 border-t border-slate-700/60 pt-1.5 font-bold text-slate-100 print:border-slate-300 print:text-slate-900">
                  <span>{{ t('customerAccount.receiptTotal') }}</span>
                  <span class="tabular-nums">{{ formatPrice(receiptOrder.total) }}</span>
                </div>
              </div>
            </div>
            <button
              class="mt-4 w-full rounded-xl border border-slate-700/60 bg-slate-800/60 py-2.5 text-xs font-medium text-slate-300 transition hover:bg-slate-800 print:hidden"
              @click="printReceipt()"
            >{{ t('customerAccount.printReceipt') }}</button>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue';
import { RouterLink, useRouter, useRoute } from 'vue-router';
import AppIcon from '../components/AppIcon.vue';
import CustomerAuthModal from '../components/CustomerAuthModal.vue';
import { useI18n } from '../composables/useI18n';
import { useCartStore } from '../stores/cart';
import { useMenuStore } from '../stores/menu';
import { useCustomerStore } from '../stores/customer';
import { useCurrencyStore } from '../stores/currency';
import { useTenantStore } from '../stores/tenant';
import { useToastStore } from '../stores/toast';
import api from '../lib/api';
import { newIdempotencyKey } from '../lib/idempotency';
import { useCustomerPush } from '../composables/useCustomerPush';
import { FOOD, SHOPS, PHARMACY, RIDES, COURIER } from '../lib/verticals';
import { groupWalletTransactionsByDate } from '../lib/walletHistory';

const { t, formatPrice, currentLocale } = useI18n();
const customerStore = useCustomerStore();
const currencyStore = useCurrencyStore();
const tenantStore = useTenantStore();
const cart = useCartStore();
const toast = useToastStore();
const menuStore = useMenuStore();
const router = useRouter();
const route = useRoute();

// Show a one-time banner when Stripe redirects back with ?topup=success|cancelled
const topUpQueryMsg = computed(() => {
  const q = route.query.topup;
  if (q === 'success') return t('customerAccount.topUpSuccessMsg');
  if (q === 'cancelled') return t('customerAccount.topUpCancelledMsg');
  return '';
});

// ── Tab navigation ────────────────────────────────────────────────────────────
const VALID_TABS = ['overview', 'orders', 'reservations', 'wallet', 'loyalty', 'reviews', 'referral'];
const activeTab = ref(VALID_TABS.includes(route.query.tab) ? route.query.tab : 'overview');
const TABS = computed(() => [
  { id: 'overview',      icon: 'home',     label: t('customerAccount.tabOverview')      },
  { id: 'orders',        icon: 'calendar', label: t('customerAccount.tabOrders')        },
  { id: 'reservations',  icon: 'booking',  label: t('customerAccount.tabReservations')  },
  { id: 'reviews',       icon: 'chat',     label: t('customerAccount.reviewsTabLabel')  },
  { id: 'wallet',        icon: 'star',     label: t('customerAccount.tabWallet')        },
  { id: 'profile',       icon: 'settings', label: t('customerAccount.tabProfile')       },
]);

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

// ── Sign-in benefit tiles ─────────────────────────────────────────────────────
const benefits = computed(() => [
  { key: 'orders',    icon: 'calendar', label: t('customerAccount.benefitOrders') },
  { key: 'addresses', icon: 'location', label: t('customerAccount.benefitAddresses') },
  { key: 'loyalty',   icon: 'star',     label: t('customerAccount.benefitLoyalty') },
  { key: 'speed',     icon: 'check',    label: t('customerAccount.benefitSpeed') },
]);

const showAuthModal = ref(false);
const showAddPhone = ref(false);

// ── Order expand / reorder ────────────────────────────────────────────────────
const expandedOrders = ref(new Set());
const receiptOrder = ref(null);
const printReceipt = () => { window.print(); };

const toggleOrder = (orderNumber) => {
  const s = new Set(expandedOrders.value);
  if (s.has(orderNumber)) s.delete(orderNumber);
  else s.add(orderNumber);
  expandedOrders.value = s;
};

const reorder = async (order) => {
  const items = order.items || [];
  if (!items.length) {
    toast.show(t('customerAccount.reorderEmpty'), 'info');
    return;
  }
  // Ensure live menu data is loaded so we can resolve current prices.
  if (!menuStore.categories.length) {
    await menuStore.fetchCategories().catch(() => {});
  }
  // Build slug → live dish map from all loaded categories.
  const dishMap = new Map();
  for (const dishes of Object.values(menuStore.dishes || {})) {
    for (const dish of dishes) {
      if (dish.slug) dishMap.set(dish.slug, dish);
    }
  }
  let priceChanged = false;
  let dropped = false;
  let added = 0;
  for (const item of items) {
    if (!item.dish_slug) continue;
    const live = dishMap.get(item.dish_slug);
    if (!live) { dropped = true; continue; }
    const snapshotPrice = parseFloat(item.unit_price) || 0;
    const livePrice = Number(live.price) || 0;
    if (snapshotPrice !== livePrice) priceChanged = true;
    cart.add({
      slug: live.slug,
      name: live.name || item.dish_name,
      price: livePrice,
      currency: order.currency || 'MAD',
      qty: item.qty,
      note: item.note || '',
      option_ids: (item.options || []).map((o) => o.id).filter(Boolean),
      option_labels: (item.options || []).map((o) => o.name).filter(Boolean),
    });
    added += 1;
  }
  // Nothing made it into the cart (menu changed entirely or fetch failed) —
  // navigating to an empty cart with a "prices updated" toast would mislead.
  if (!added) {
    toast.show(t('customerAccount.reorderUnavailable'), 'error');
    return;
  }
  if (priceChanged || dropped) {
    toast.show(t('cartPage.reorderPriceNote'), 'info');
  } else {
    toast.show(t('customerAccount.reorderAdded'), 'success');
  }
  // Wallet pre-flight: warn if balance won't cover the cart total.
  const cartTotal = cart.items.reduce((s, i) => s + (i.unitPrice ?? i.price) * i.qty, 0);
  if (cartTotal > 0 && walletBalance.value < cartTotal) {
    toast.show(t('customerAccount.reorderWalletShort'), 'warning');
  }
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
  const emailRe = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRe.test(editableEmail.value.trim())) {
    emailError.value = t('customerAccount.emailInvalid');
    return;
  }
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

// ── Last ride (overview) ──────────────────────────────────────────────────────
const lastRide = ref(null);
const lastRideChecked = ref(false);

// Reuses the adminRides.status* keys — already translated in all three locales.
const RIDE_STATUS_LABELS = {
  searching: 'adminRides.statusSearching',
  accepted: 'adminRides.statusAccepted',
  arrived: 'adminRides.statusArrived',
  in_progress: 'adminRides.statusInProgress',
  completed: 'adminRides.statusCompleted',
  cancelled: 'adminRides.statusCancelled',
  scheduled: 'tripSchedule.statusScheduled',
};
const rideStatusLabel = (s) => (RIDE_STATUS_LABELS[s] ? t(RIDE_STATUS_LABELS[s]) : s);

const fetchLastRide = async () => {
  if (!customerStore.isAuthenticated) return;
  try {
    const res = await api.get('/rides/history/');
    const rides = Array.isArray(res.data) ? res.data : [];
    lastRide.value = rides[0] || null;
  } catch {
    // silent-fail
  } finally {
    lastRideChecked.value = true;
  }
};

const loadingOrders = ref(false);
const loadingMoreOrders = ref(false);
const ordersError = ref(false);
const ordersHasMore = ref(false);
const ordersCurrentPage = ref(1);
const apiOrders = ref([]);

const loadingReservations = ref(false);
const reservationsError = ref(false);
const apiReservations = ref([]);

const ACTIVE_STATUSES = new Set(['pending', 'confirmed', 'preparing', 'ready', 'out_for_delivery']);
const activeOrders = computed(() => apiOrders.value.filter(o => ACTIVE_STATUSES.has(o.status)));

// ── Reviews ───────────────────────────────────────────────────────────────────
const reviewDrafts     = reactive({});   // { [orderNumber]: { score: 0, comment: '' } }
const reviewHover      = reactive({});   // { [orderNumber]: 0–5 }
const submittingReview = ref(new Set());

const completedOrders  = computed(() => apiOrders.value.filter(o => o.status === 'completed'));
const pendingReviews   = computed(() => completedOrders.value.filter(o => !o.has_rating));
const submittedReviews = computed(() => completedOrders.value.filter(o => o.has_rating));
const reviewsAvgScore  = computed(() => {
  const rated = submittedReviews.value;
  if (!rated.length) return 0;
  return rated.reduce((sum, o) => sum + (o.rating_score || 0), 0) / rated.length;
});

const getDraft = (num) => reviewDrafts[num] ?? { score: 0, comment: '' };

/** Reactive score label array — re-evaluates when locale changes. */
const reviewScoreLabels = computed(() => [
  '',
  t('customerAccount.reviewsScorePoor'),
  t('customerAccount.reviewsScoreFair'),
  t('customerAccount.reviewsScoreGood'),
  t('customerAccount.reviewsScoreGreat'),
  t('customerAccount.reviewsScoreExcellent'),
]);

const setDraftScore = (num, score) => {
  if (!reviewDrafts[num]) reviewDrafts[num] = { score: 0, comment: '' };
  reviewDrafts[num].score = score;
};

const setDraftComment = (num, comment) => {
  if (!reviewDrafts[num]) reviewDrafts[num] = { score: 0, comment: '' };
  reviewDrafts[num].comment = comment;
};

const setHover = (num, score) => { reviewHover[num] = score; };

const submitReview = async (order) => {
  const draft = reviewDrafts[order.order_number];
  if (!draft?.score) return;
  const num = order.order_number;
  const s = new Set(submittingReview.value); s.add(num); submittingReview.value = s;
  try {
    await api.post(`/orders/${num}/rate/`, { score: draft.score, comment: draft.comment || '' });
    const idx = apiOrders.value.findIndex(o => o.order_number === num);
    if (idx !== -1) {
      const updated = [...apiOrders.value];
      updated[idx] = {
        ...updated[idx],
        has_rating: true,
        rating_score: draft.score,
        rating: { score: draft.score, comment: draft.comment || '', created_at: new Date().toISOString() },
      };
      apiOrders.value = updated;
    }
    toast.show(t('customerAccount.reviewsSuccess'), 'success');
  } catch (err) {
    toast.show(err?.response?.data?.detail || t('customerAccount.reviewsError'), 'error');
  } finally {
    const s2 = new Set(submittingReview.value); s2.delete(num); submittingReview.value = s2;
  }
};

const loadingWallet = ref(false);
const walletError = ref(false);
const walletTransactions = ref([]);
const walletBalance = computed(() => {
  const raw = customerStore.customer?.wallet_balance;
  const n = Number(raw);
  return Number.isFinite(n) ? n : 0;
});

// ── Loyalty ───────────────────────────────────────────────────────────────────
const loyaltyPoints = computed(() => customerStore.customer?.loyalty_points || 0);
const lifetimeLoyaltyPoints = computed(() => customerStore.customer?.lifetime_loyalty_points || 0);

const tierName = computed(() => {
  const cfg = loyaltyConfig.value;
  if (!cfg?.tier_enabled) return null;
  const lt = lifetimeLoyaltyPoints.value;
  if (lt >= (cfg.tier_gold_threshold || 2000)) return t('customerAccount.tierGold');
  if (lt >= (cfg.tier_silver_threshold || 500)) return t('customerAccount.tierSilver');
  return t('customerAccount.tierBronze');
});

const tierProgress = computed(() => {
  const cfg = loyaltyConfig.value;
  if (!cfg?.tier_enabled) return null;
  const lt = lifetimeLoyaltyPoints.value;
  const goldThr = cfg.tier_gold_threshold || 2000;
  const silverThr = cfg.tier_silver_threshold || 500;
  if (lt >= goldThr) return null; // already at max tier
  if (lt >= silverThr) {
    return { current: lt, next: goldThr, tier: t('customerAccount.tierGold') };
  }
  return { current: lt, next: silverThr, tier: t('customerAccount.tierSilver') };
});

// ── Birthday ──────────────────────────────────────────────────────────────────
const editableBirthday = ref(null);
const savingBirthday = ref(false);

const saveBirthday = async () => {
  savingBirthday.value = true;
  try {
    const res = await api.patch('/customer/profile/', { birthday: editableBirthday.value || '' });
    customerStore.setCustomer({ ...customerStore.customer, birthday: res.data.birthday });
    toast.show(t('customerAccount.birthdaySaved'), 'success');
  } catch {
    toast.show(t('common.saveFailed'), 'error');
  } finally {
    savingBirthday.value = false;
  }
};

// ── Referral ──────────────────────────────────────────────────────────────────
const referralEnabled = computed(() => !!tenantStore.resolvedMeta?.profile?.referral_enabled);
const referralRewardPoints = computed(() => tenantStore.resolvedMeta?.profile?.referral_reward_points || 100);
const referralCopied = ref(false);
let _referralCopyTimer = null;
const copyReferralLink = async () => {
  const code = customerStore.customer?.referral_code;
  if (!code) return;
  const link = `${window.location.origin}?ref=${code}`;
  try {
    await navigator.clipboard.writeText(link);
  } catch {
    // Fallback for non-secure contexts
    const el = document.createElement("textarea");
    el.value = link;
    el.style.position = "fixed";
    el.style.opacity = "0";
    document.body.appendChild(el);
    el.select();
    document.execCommand("copy");
    document.body.removeChild(el);
  }
  referralCopied.value = true;
  clearTimeout(_referralCopyTimer);
  _referralCopyTimer = setTimeout(() => { referralCopied.value = false; }, 2000);
};
const shareReferralLink = async () => {
  const code = customerStore.customer?.referral_code;
  if (!code) return;
  const link = `${window.location.origin}?ref=${code}`;
  try {
    await navigator.share({ url: link, text: t('customerAccount.referralShareText') });
  } catch {
    /* user cancelled or share not supported */
  }
};

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

// Total wallet-equivalent of all current points (shown in header badge)
const loyaltyEquivCredit = computed(() => {
  const pv = Number(loyaltyConfig.value?.points_value);
  const lp = Number(loyaltyPoints.value);
  if (!pv || !lp) return null;
  return (lp * pv).toFixed(2);
});

// Credit unlocked by ONE redemption (threshold × points_value) — shown in the "need more" hint
const loyaltyUnlockCredit = computed(() => {
  const pv = Number(loyaltyConfig.value?.points_value);
  const thr = Number(loyaltyConfig.value?.redeem_threshold);
  if (!pv || !thr) return null;
  return (thr * pv).toFixed(2);
});

// ── Saved addresses ───────────────────────────────────────────────────────────
const savedAddresses = ref([]);
const deletingAddressId = ref(null);
const addrDeleteError = ref(''); // inline error for the delete confirmation popover
const editingAddressId = ref(null);
const editForm = reactive({ label: '', address: '' });
const editError = ref('');
const savingEdit = ref(false);
const loadingAddresses = ref(false);

const fetchAddresses = async () => {
  if (!customerStore.isAuthenticated) return;
  loadingAddresses.value = true;
  try {
    const res = await api.get('/customer/addresses/');
    savedAddresses.value = res.data || [];
  } catch {
    toast.show(t('customerAccount.addressLoadFailed'), 'error');
  } finally {
    loadingAddresses.value = false;
  }
};

const deleteAddress = async (id) => {
  addrDeleteError.value = '';
  try {
    await api.delete(`/customer/addresses/${id}/`);
    savedAddresses.value = savedAddresses.value.filter((a) => a.id !== id);
    deletingAddressId.value = null;
    toast.show(t('customerAccount.savedAddressDeleted'), 'success');
  } catch {
    // Keep the confirm panel open so the user can see the error and retry.
    addrDeleteError.value = t('customerAccount.savedAddressDeleteFailed');
  }
};

const startEdit = (addr) => {
  editingAddressId.value = addr.id;
  editForm.label = addr.label || '';
  editForm.address = addr.address || '';
  editError.value = '';
  deletingAddressId.value = null; // close any pending delete confirm
};

const saveEdit = async () => {
  editError.value = '';
  if (!editForm.address.trim()) {
    editError.value = t('customerAccount.savedAddressRequired');
    return;
  }
  savingEdit.value = true;
  try {
    const res = await api.patch(`/customer/addresses/${editingAddressId.value}/`, {
      label: editForm.label.trim(),
      address: editForm.address.trim(),
    });
    const idx = savedAddresses.value.findIndex((a) => a.id === editingAddressId.value);
    if (idx >= 0) savedAddresses.value[idx] = res.data;
    editingAddressId.value = null;
    toast.show(t('customerAccount.savedAddressEdited'), 'success');
  } catch {
    editError.value = t('customerAccount.savedAddressEditFailed');
  } finally {
    savingEdit.value = false;
  }
};

// Add address
const addingAddress = ref(false);
const addrForm = reactive({ label: '', address: '' });
const addrError = ref('');
const savingAddress = ref(false);

const addAddress = async () => {
  addrError.value = '';
  if (!addrForm.address.trim()) {
    addrError.value = t('customerAccount.savedAddressRequired');
    return;
  }
  savingAddress.value = true;
  try {
    const res = await api.post('/customer/addresses/', {
      label: addrForm.label.trim(),
      address: addrForm.address.trim(),
    });
    savedAddresses.value.unshift(res.data);
    addrForm.label = '';
    addrForm.address = '';
    addingAddress.value = false;
    toast.show(t('customerAccount.savedAddressSaved'), 'success');
  } catch (err) {
    const code = err?.response?.data?.code;
    addrError.value = code === 'address_limit'
      ? t('customerAccount.savedAddressLimit')
      : t('customerAccount.savedAddressSaveFailed');
  } finally {
    savingAddress.value = false;
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
  fetchLoyaltyHistory();
};

const loyaltyHistory = ref(null);

const fetchLoyaltyHistory = async () => {
  if (loyaltyHistory.value) return; // already loaded
  try {
    const res = await api.get('/customer/loyalty/history/');
    loyaltyHistory.value = res.data;
  } catch { loyaltyHistory.value = { events: [] }; }
};

let redeemKey = null; // stable across retries of the same redemption; cleared on success

const redeemPoints = async () => {
  redeemError.value = '';
  redeemSuccess.value = '';
  const pts = parseInt(redeemAmount.value, 10);
  if (!Number.isFinite(pts) || pts <= 0) { redeemError.value = t('customerAccount.loyaltyRedeemFailed'); return; }
  redeeming.value = true;
  if (!redeemKey) redeemKey = newIdempotencyKey();
  try {
    const res = await api.post('/customer/loyalty/redeem/', { points: redeemAmount.value, idempotency_key: redeemKey });
    if (customerStore.customer) {
      customerStore.setCustomer({
        ...customerStore.customer,
        loyalty_points: res.data.new_points_balance,
        wallet_balance: res.data.new_wallet_balance,
      });
    }
    redeemKey = null; // confirmed — next redemption gets a fresh key
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

// ── Wallet voucher ────────────────────────────────────────────────────────────
const voucherCode = ref('');
const voucherLoading = ref(false);
const voucherError = ref('');
const voucherSuccess = ref('');

const redeemVoucher = async () => {
  const code = voucherCode.value.trim().toUpperCase();
  if (!code) return;
  voucherError.value = '';
  voucherSuccess.value = '';
  voucherLoading.value = true;
  try {
    const res = await api.post('/customer/wallet/redeem-voucher/', { code });
    voucherCode.value = '';
    if (customerStore.customer) {
      customerStore.setCustomer({
        ...customerStore.customer,
        wallet_balance: res.data.new_balance,
      });
    }
    await fetchWallet();
    voucherSuccess.value = t('customerAccount.voucherSuccess', { amount: res.data.credited });
  } catch (err) {
    voucherError.value = err?.response?.data?.detail || t('customerAccount.voucherError');
  } finally {
    voucherLoading.value = false;
  }
};

const formatDate = (iso) => {
  if (!iso) return '';
  try {
    return new Intl.DateTimeFormat(currentLocale.value, { month: 'short', day: 'numeric', year: 'numeric' }).format(new Date(iso));
  } catch { return iso; }
};

const STATUS_I18N = {
  pending: 'orderStatus.statusPending',
  confirmed: 'orderStatus.statusConfirmed',
  preparing: 'orderStatus.statusPreparing',
  ready: 'orderStatus.statusReady',
  out_for_delivery: 'orderStatus.stepOutForDelivery',
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
  transfer_out: 'customerAccount.walletTxTransferOut',
  transfer_in:  'customerAccount.walletTxTransferIn',
};
const OUTFLOW_TYPES = new Set(['payment', 'transfer_out']);
const isOutflow = (tx) => OUTFLOW_TYPES.has(tx.type);
const txLabel = (tx) => {
  const base = t(TX_LABEL_MAP[tx.type] || 'customerAccount.walletTxFallback');
  return tx.reference ? `${base} ${tx.reference}` : base;
};

// No verified phone → no usable wallet. Gates the credit actions in the wallet tab.
const walletVerified = computed(() => !!customerStore.customer?.phone_verified);

// ── Pay code (QR) — a restaurant scans this to top up the wallet ───────────────
const showPayCode = ref(false);
const payCodeImg = ref('');

// ── PSP top-up (Stripe Checkout, shown only when platform flag is on) ─────────
const topUpAmount = ref(100);
const topUpLoading = ref(false);
const topUpError = ref('');

const initTopUp = async () => {
  topUpError.value = '';
  topUpLoading.value = true;
  try {
    const { data } = await api.post('/customer/topup/intent/', { amount: String(topUpAmount.value) });
    if (data.enabled && data.url) {
      window.location.href = data.url;
    } else {
      topUpError.value = t('customerAccount.topUpError');
    }
  } catch {
    topUpError.value = t('customerAccount.topUpError');
  } finally {
    topUpLoading.value = false;
  }
};

const refreshPayCode = async () => {
  payCodeImg.value = '';
  try {
    const { data } = await api.get('/customer/wallet/pay-token/');
    const QRCode = (await import('qrcode')).default;  // lazy — keeps ~60KB out of the page chunk
    payCodeImg.value = await QRCode.toDataURL(data.token, { width: 320, margin: 1 });
  } catch {
    payCodeImg.value = '';
  }
};

const togglePayCode = () => {
  showPayCode.value = !showPayCode.value;
  if (showPayCode.value && !payCodeImg.value) refreshPayCode();
};

// Web Push opt-in so the customer is nudged to approve above-threshold charges.
const {
  supported: pushSupported,
  enabled: pushEnabled,
  subscribed: pushSubscribed,
  loading: pushLoading,
  subscribe: pushSubscribe,
  checkEnabled: pushCheckEnabled,
} = useCustomerPush();

// ── P2P gifting (only active when the platform enables it) ─────────────────────
const p2pEnabled = ref(false);
const sendPhone = ref('');
const sendAmount = ref('');
const sendNote = ref('');
const sending = ref(false);
const sendError = ref('');
const sendSuccess = ref('');
let sendKey = null; // stable across retries of the same transfer; cleared on success

const sendCredit = async () => {
  sendError.value = '';
  sendSuccess.value = '';
  const amount = parseFloat(sendAmount.value);
  if (!sendPhone.value.trim()) { sendError.value = t('customerAccount.sendPhoneRequired'); return; }
  if (!amount || amount <= 0) { sendError.value = t('customerAccount.sendAmountRequired'); return; }
  sending.value = true;
  if (!sendKey) sendKey = newIdempotencyKey();
  try {
    const res = await api.post('/customer/wallet/transfer/', {
      recipient_phone: sendPhone.value.trim(),
      amount: amount.toFixed(2),
      note: sendNote.value.trim(),
      idempotency_key: sendKey,
    });
    if (res.data.new_balance !== undefined && customerStore.customer) {
      customerStore.setCustomer({ ...customerStore.customer, wallet_balance: res.data.new_balance });
    }
    sendKey = null; // confirmed — next transfer gets a fresh key
    sendSuccess.value = t('customerAccount.sendSuccess', { amount: res.data.amount });
    sendPhone.value = '';
    sendAmount.value = '';
    sendNote.value = '';
    await fetchWallet();
  } catch (err) {
    sendError.value = err?.response?.data?.detail || t('customerAccount.sendFailed');
  } finally {
    sending.value = false;
  }
};

const fetchWallet = async () => {
  if (!customerStore.isAuthenticated) return;
  loadingWallet.value = true;
  walletError.value = false;
  try {
    // ?vertical= scopes ONLY the transaction list; balance + spend-by-vertical
    // stay global (one wallet pool). Blank/all → unfiltered list.
    const params = walletVertical.value ? `?vertical=${encodeURIComponent(walletVertical.value)}` : '';
    const res = await api.get(`/customer/wallet/${params}`);
    walletTransactions.value = res.data.transactions || [];
    p2pEnabled.value = Boolean(res.data.p2p_enabled);
    walletSpendByVertical.value = res.data.spend_by_vertical || {};
    if (res.data.balance !== undefined && customerStore.customer) {
      customerStore.setCustomer({ ...customerStore.customer, wallet_balance: res.data.balance });
    }
  } catch {
    walletError.value = true;
  } finally {
    loadingWallet.value = false;
  }
};

const fetchOrders = async (page = 1) => {
  if (!customerStore.isAuthenticated) return;
  const isFirstPage = page === 1;
  if (isFirstPage) {
    loadingOrders.value = true;
    ordersError.value = false;
    ordersCurrentPage.value = 1;
  } else {
    loadingMoreOrders.value = true;
  }
  try {
    const res = await api.get(`/customer/orders/?page=${page}`);
    const incoming = res.data.orders || [];
    if (isFirstPage) {
      apiOrders.value = incoming;
    } else {
      apiOrders.value = [...apiOrders.value, ...incoming];
    }
    ordersHasMore.value = Boolean(res.data.has_more);
    ordersCurrentPage.value = page;
  } catch {
    if (isFirstPage) ordersError.value = true;
  } finally {
    loadingOrders.value = false;
    loadingMoreOrders.value = false;
  }
};

const loadMoreOrders = () => fetchOrders(ordersCurrentPage.value + 1);

// Cross-restaurant order history (public marketplace index — works on any domain).
const marketplaceOrders = ref([]);
const loadingMarketplaceOrders = ref(false);
const MKT_ORDER_STATUS = {
  pending: 'orderStatus.statusPending',
  confirmed: 'orderStatus.statusConfirmed',
  preparing: 'orderStatus.statusPreparing',
  ready: 'orderStatus.statusReady',
  out_for_delivery: 'orderStatus.stepOutForDelivery',
  completed: 'orderStatus.statusCompleted',
  cancelled: 'orderStatus.statusCancelled',
};
const mktOrderStatus = (s) => t(MKT_ORDER_STATUS[s] || 'orderStatus.statusPending');

// ── Order self-cancel ──────────────────────────────────────────────────────────
const cancellingOrderNumber = ref(null);
const cancelOrder = async (order) => {
  if (cancellingOrderNumber.value) return;
  if (!window.confirm(t('customerAccount.cancelConfirm'))) return;
  cancellingOrderNumber.value = order.order_number;
  try {
    await api.post(`/order-status/${order.order_number}/cancel/`);
    toast.show(t('customerAccount.orderCancelled'), 'success');
    // Optimistically mark as cancelled in the list; full refetch will sync.
    const target = apiOrders.value.find((o) => o.order_number === order.order_number);
    if (target) { target.status = 'cancelled'; target.can_cancel = false; }
  } catch (err) {
    const code = err?.response?.data?.code;
    if (code === 'cannot_cancel') {
      toast.show(t('customerAccount.orderCancelFailed'), 'error');
    } else {
      toast.show(t('customerAccount.orderCancelFailed'), 'error');
    }
  } finally {
    cancellingOrderNumber.value = null;
  }
};

const cancelMarketplaceOrder = async (order) => {
  if (cancellingOrderNumber.value) return;
  if (!window.confirm(t('customerAccount.cancelConfirm'))) return;
  cancellingOrderNumber.value = order.order_number;
  try {
    await api.post(`/marketplace/order/${order.order_number}/cancel/`, { restaurant: order.restaurant_slug });
    toast.show(t('customerAccount.orderCancelled'), 'success');
    const target = marketplaceOrders.value.find((o) => o.order_number === order.order_number);
    if (target) { target.status = 'cancelled'; target.can_cancel = false; }
  } catch {
    toast.show(t('customerAccount.orderCancelFailed'), 'error');
  } finally {
    cancellingOrderNumber.value = null;
  }
};

// ── Vertical filter for marketplace orders ────────────────────────────────────
const selectedVertical = ref('');
const orderSearch = ref('');

const filteredMarketplaceOrders = computed(() => {
  const q = orderSearch.value.trim().toLowerCase();
  if (!q) return marketplaceOrders.value;
  return marketplaceOrders.value.filter(
    (o) =>
      (o.restaurant_name || '').toLowerCase().includes(q) ||
      (o.order_number || '').toLowerCase().includes(q)
  );
});

const VERTICAL_FILTER_OPTIONS = computed(() => {
  const opts = [{ id: '', label: t('customerAccount.svcAll') }];
  // Order history is CustomerOrderRef-backed, which only ever holds order verticals
  // (food/shops/pharmacy). Rides + courier live in RideRequest with their own history
  // screens, so a ?vertical=rides query here returns nothing — including them would
  // render phantom, always-empty filter tabs.
  const map = {
    [FOOD]:     t('customerAccount.svcFood'),
    [SHOPS]:    t('customerAccount.svcShops'),
    [PHARMACY]: t('customerAccount.svcPharmacy'),
  };
  for (const v of customerStore.enabledVerticals) {
    if (map[v]) opts.push({ id: v, label: map[v] });
  }
  return opts;
});

const fetchMarketplaceOrders = async (vertical = '') => {
  if (!customerStore.isAuthenticated) return;
  loadingMarketplaceOrders.value = true;
  try {
    const params = vertical ? `?vertical=${vertical}` : '';
    const res = await api.get(`/customer/orders/all/${params}`);
    marketplaceOrders.value = res.data.orders || [];
  } catch {
    marketplaceOrders.value = [];
  } finally {
    loadingMarketplaceOrders.value = false;
  }
};

const selectVertical = (v) => {
  selectedVertical.value = v;
  fetchMarketplaceOrders(v);
};

// ── Wallet spend-by-vertical ──────────────────────────────────────────────────
const walletSpendByVertical = ref({});

// ── Wallet transaction per-vertical filter + receipt sheet ────────────────────
// Selected vertical filter for the wallet tx list (''=all). Server-side ?vertical=.
const walletVertical = ref('');

// Filter chips: "All" + every enabled vertical that a WalletTransaction can carry
// (food/shops/pharmacy from orders, rides/courier from trips). Unlike the orders
// tab, wallet tx DO span rides/courier, so we include them here.
const WALLET_FILTER_OPTIONS = computed(() => {
  const opts = [{ id: '', label: t('customerAccount.svcAll') }];
  const map = {
    [FOOD]:     t('customerAccount.svcFood'),
    [SHOPS]:    t('customerAccount.svcShops'),
    [PHARMACY]: t('customerAccount.svcPharmacy'),
    [RIDES]:    t('customerAccount.svcRides'),
    [COURIER]:  t('customerAccount.svcCourier'),
  };
  for (const v of customerStore.enabledVerticals) {
    if (map[v]) opts.push({ id: v, label: map[v] });
  }
  return opts;
});

const selectWalletVertical = (v) => {
  if (walletVertical.value === v) return;
  walletVertical.value = v;
  fetchWallet();
};

// Group the (already date-sorted, newest-first) tx list into Today / Yesterday /
// month buckets so a long history reads as a dated ledger rather than a flat wall.
const walletTransactionGroups = computed(() =>
  groupWalletTransactionsByDate(walletTransactions.value, {
    t: (k) => t(k === 'today' ? 'customerAccount.walletGroupToday' : 'customerAccount.walletGroupYesterday'),
    formatMonth: (d) => {
      try {
        return new Intl.DateTimeFormat(currentLocale.value, { month: 'long', year: 'numeric' }).format(d);
      } catch { return `${d.getFullYear()}-${d.getMonth()}`; }
    },
  }),
);

// Receipt / detail sheet — the tapped transaction (or null when closed).
const walletReceipt = ref(null);
const openWalletReceipt = (tx) => { walletReceipt.value = tx; };

const formatDateTime = (iso) => {
  if (!iso) return '';
  try {
    return new Intl.DateTimeFormat(currentLocale.value, {
      month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit',
    }).format(new Date(iso));
  } catch { return iso; }
};

// ── Per-service notification preferences ─────────────────────────────────────
const serviceProfiles = ref({});
const loadingServiceProfiles = ref(false);
const serviceProfilesError = ref(false);
const serviceProfilesOpen = ref(false);
const savingServiceProfile = ref(''); // vertical currently being saved

const VERTICAL_SVC_LABELS = computed(() => ({
  [FOOD]:     t('customerAccount.svcFood'),
  [SHOPS]:    t('customerAccount.svcShops'),
  [PHARMACY]: t('customerAccount.svcPharmacy'),
  [RIDES]:    t('customerAccount.svcRides'),
  [COURIER]:  t('customerAccount.svcCourier'),
}));

const fetchServiceProfiles = async () => {
  if (!customerStore.isAuthenticated) return;
  loadingServiceProfiles.value = true;
  serviceProfilesError.value = false;
  try {
    const res = await api.get('/customer/service-profiles/');
    serviceProfiles.value = res.data.service_profiles || {};
  } catch {
    serviceProfilesError.value = true;
  } finally {
    loadingServiceProfiles.value = false;
  }
};

const saveServicePref = async (vertical, field, value) => {
  if (savingServiceProfile.value) return;
  savingServiceProfile.value = vertical;
  // Optimistic update
  if (serviceProfiles.value[vertical]) {
    serviceProfiles.value[vertical][field] = value;
  }
  try {
    const res = await api.patch('/customer/service-profiles/', { vertical, [field]: value });
    if (serviceProfiles.value[vertical]) {
      serviceProfiles.value[vertical].notify_updates = res.data.notify_updates;
      serviceProfiles.value[vertical].notify_promotions = res.data.notify_promotions;
    }
  } catch {
    // Revert optimistic update on failure
    if (serviceProfiles.value[vertical]) {
      serviceProfiles.value[vertical][field] = !value;
    }
    toast.show(t('customerAccount.prefSaveFailed'), 'error');
  } finally {
    savingServiceProfile.value = '';
  }
};

const fetchReservations = async () => {
  if (!customerStore.isAuthenticated) return;
  loadingReservations.value = true;
  reservationsError.value = false;
  try {
    const res = await api.get('/customer/reservations/');
    apiReservations.value = res.data.reservations || [];
  } catch {
    reservationsError.value = true;
  } finally {
    loadingReservations.value = false;
  }
};

// Reservation status label map
const RESERVATION_STATUS_I18N = {
  new:        'customerAccount.reservationStatusNew',
  contacted:  'customerAccount.reservationStatusContacted',
  won:        'customerAccount.reservationStatusWon',
  lost:       'customerAccount.reservationStatusLost',
  no_show:    'customerAccount.reservationStatusNoShow',
};
const reservationStatusLabel  = (s) => t(RESERVATION_STATUS_I18N[s] || 'customerAccount.reservationStatusNew');
const reservationStatusClass  = (s) => ({
  new:       'bg-sky-500/10 text-sky-300 border-sky-500/25',
  contacted: 'bg-sky-500/10 text-sky-300 border-sky-500/25',
  won:       'bg-emerald-500/10 text-emerald-300 border-emerald-500/25',
  lost:      'bg-slate-700/40 text-slate-400 border-slate-600/30',
  no_show:   'bg-amber-500/10 text-amber-300 border-amber-500/25',
}[s] || 'bg-slate-700/40 text-slate-400 border-slate-600/30');

const formatReservationDateTime = (iso) => {
  if (!iso) return '';
  try {
    return new Intl.DateTimeFormat(currentLocale.value, {
      weekday: 'short', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    }).format(new Date(iso));
  } catch { return iso; }
};

// Re-order a marketplace order: pre-fill the restaurant's menu cart and navigate there.
// (Distinct from reorder() above, which uses the hostname-scoped cart for tenant orders.)
const reorderMarketplace = (order) => {
  router.push({
    name: 'marketplace-menu',
    params: { slug: order.restaurant_slug },
    state: { reorderItems: order.items_snapshot || [] },
  });
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
    toast.show(t('customerAccount.saveNameFailed'), 'error');
  } finally {
    savingName.value = false;
  }
};

const savingPrefs = ref(false);
const savePref = async (field, value) => {
  if (savingPrefs.value) return;
  savingPrefs.value = true;
  try {
    const res = await api.patch('/customer/profile/', { [field]: value });
    customerStore.setCustomer(res.data.customer);
  } catch {
    toast.show(t('customerAccount.prefSaveFailed'), 'error');
  } finally {
    savingPrefs.value = false;
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
  apiReservations.value = [];
  for (const k in reviewDrafts) delete reviewDrafts[k];
  for (const k in reviewHover)  delete reviewHover[k];
  walletTransactions.value = [];
  editableName.value = '';
  selectedLocale.value = 'en';
  localeConfigured.value = false;
  showEmailInput.value = false;
  emailError.value = '';
  lastRide.value = null;
  lastRideChecked.value = false;
  activeTab.value = 'overview';
};

// ── Privacy & data export ─────────────────────────────────────────────────────
const exportingData = ref(false);
const requestingErasure = ref(false);
const erasureConfirmVisible = ref(false);
const erasureBlockedMsg = ref('');

const downloadMyData = async () => {
  if (exportingData.value) return;
  exportingData.value = true;
  try {
    const resp = await fetch('/api/customer/my-data/', { credentials: 'same-origin' });
    if (!resp.ok) throw new Error('export-failed');
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'kepoli-data-export.json';
    a.click();
    URL.revokeObjectURL(url);
  } catch {
    toast.show(t('customerAccount.privacyExportFailed'), 'error');
  } finally {
    exportingData.value = false;
  }
};

const requestErasure = async () => {
  if (requestingErasure.value) return;
  requestingErasure.value = true;
  erasureBlockedMsg.value = '';
  try {
    await api.post('/customer/request-erasure/');
    await customerStore.logout();
    toast.show(t('customerAccount.privacyDeleteDone'), 'success');
    router.push({ name: 'home' });
  } catch (err) {
    if (err?.response?.status === 409) {
      const errors = err.response.data?.errors || [];
      erasureBlockedMsg.value = errors.join(' · ') || t('customerAccount.privacyDeleteBlocked');
      erasureConfirmVisible.value = false;
    } else {
      toast.show(t('customerAccount.privacyDeleteFailed'), 'error');
    }
  } finally {
    requestingErasure.value = false;
    erasureConfirmVisible.value = false;
  }
};

const onAuthenticated = (customer) => {
  customerStore.setCustomer(customer);
  editableName.value = customer?.name || '';
  selectedLocale.value = customer?.locale || 'en';
  localeConfigured.value = !!(customer?.id && localStorage.getItem(`locale_set_${customer.id}`));
  fetchOrders();
  fetchMarketplaceOrders();
  fetchReservations();
  fetchWallet();
  fetchLastRide();
  fetchServiceProfiles();
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
    editableBirthday.value = val?.birthday || '';
  },
  { immediate: true }
);

onMounted(async () => {
  await customerStore.fetchCustomer();
  if (customerStore.isAuthenticated) {
    fetchOrders();
    fetchMarketplaceOrders();
    fetchReservations();
    fetchWallet();
    fetchLoyaltyConfig();
    fetchAddresses();
    pushCheckEnabled();
    fetchLastRide();
    fetchServiceProfiles();
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
@media (prefers-reduced-motion: reduce) {
  .ui-expand-enter-active,
  .ui-expand-leave-active {
    transition: none;
  }
}
</style>
