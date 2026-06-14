<template>
  <div
    class="kitchen-shell"
    :class="{ 'kitchen-fullscreen': isFullscreen }"
  >
    <!-- Top bar -->
    <div class="kitchen-topbar" role="region" :aria-label="t('kitchen.displayHeader')">
      <div class="flex items-center gap-3">
        <span class="ui-kicker">{{ t("kitchen.title") }}</span>
        <!-- Offline / syncing indicator -->
        <span
          v-if="!waiter.isOnline"
          class="rounded-full border border-red-500/40 bg-red-500/10 px-2.5 py-1 text-[11px] font-semibold tracking-wide text-red-400"
          role="status"
          aria-live="polite"
        >{{ t("kitchen.offline") }}</span>
        <span
          v-else-if="waiter.isSyncing || waiter.queueLength > 0"
          class="rounded-full border border-amber-500/40 bg-amber-500/10 px-2.5 py-1 text-[11px] font-semibold tracking-wide text-amber-400"
          role="status"
          aria-live="polite"
        >{{ t("kitchen.syncing") }}</span>
      </div>

      <div class="flex items-center gap-4">
        <!-- WS live / polling indicator (contract 6c) -->
        <span
          v-if="wsState === 'live'"
          class="rounded-full border border-emerald-500/40 bg-emerald-500/10 px-2.5 py-1 text-[11px] font-semibold tracking-wide text-emerald-400"
          role="status"
          aria-live="polite"
        >{{ t("kitchen.live") }}</span>
        <span
          v-else-if="wsState === 'polling'"
          class="rounded-full border border-slate-600/40 bg-slate-700/30 px-2.5 py-1 text-[11px] font-semibold tracking-wide text-slate-400"
          role="status"
          aria-live="polite"
        >{{ t("kitchen.pollingMode") }}</span>
        <!-- 86 board button (contract 7) -->
        <button
          class="kitchen-fs-btn ui-press focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
          :aria-label="t('kitchen.eightySixOpen')"
          @click="open86Board"
        >
          <span aria-hidden="true" class="text-sm font-bold">86</span>
        </button>
        <!-- Active order count -->
        <span class="rounded-full border border-slate-600/60 bg-slate-700/50 px-3 py-1 text-sm font-bold tabular-nums text-slate-100" aria-live="polite" aria-atomic="true">
          {{ t("kitchen.activeCount", { n: activeOrders.length }) }}
        </span>
        <!-- Clock -->
        <span class="font-mono text-base tabular-nums text-slate-300" aria-hidden="true">{{ clockDisplay }}</span>
        <!-- Sound toggle (task 4) -->
        <button
          class="kitchen-fs-btn ui-press focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
          :class="kitchenSoundOn ? '' : 'opacity-50'"
          :aria-label="kitchenSoundOn ? t('orderFlow.soundOff') : t('orderFlow.soundOn')"
          :aria-pressed="kitchenSoundOn"
          @click="toggleKitchenSound"
        >
          <span aria-hidden="true" class="text-sm">{{ kitchenSoundOn ? '🔔' : '🔕' }}</span>
        </button>
        <!-- Fullscreen toggle -->
        <button
          class="kitchen-fs-btn ui-press focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
          :aria-label="isFullscreen ? t('kitchen.exitFullscreen') : t('kitchen.enterFullscreen')"
          :aria-pressed="isFullscreen"
          @click="toggleFullscreen"
        >
          <svg v-if="isFullscreen" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="h-4 w-4" aria-hidden="true">
            <path fill-rule="evenodd" d="M5 10a.75.75 0 01.75-.75h8.5a.75.75 0 010 1.5h-8.5A.75.75 0 015 10z" clip-rule="evenodd"/>
            <path d="M3 3.75A.75.75 0 013.75 3h3.5a.75.75 0 010 1.5h-2v2a.75.75 0 01-1.5 0v-2.75zm10 0a.75.75 0 01.75-.75h3.5a.75.75 0 01.75.75v2.75a.75.75 0 01-1.5 0v-2h-2a.75.75 0 01-.75-.75zM3 16.25A.75.75 0 013.75 17h3.5a.75.75 0 000-1.5h-2v-2a.75.75 0 00-1.5 0v2.75zm10.75.75a.75.75 0 01-.75-.75v-2.75a.75.75 0 011.5 0v2h2a.75.75 0 010 1.5h-2.75z"/>
          </svg>
          <svg v-else xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="h-4 w-4" aria-hidden="true">
            <path d="M13.28 7.78l3.22-3.22v2.69a.75.75 0 001.5 0v-4.5a.75.75 0 00-.75-.75h-4.5a.75.75 0 000 1.5h2.69l-3.22 3.22a.75.75 0 001.06 1.06zM2 17.25v-4.5a.75.75 0 011.5 0v2.69l3.22-3.22a.75.75 0 011.06 1.06L4.56 16.5h2.69a.75.75 0 010 1.5h-4.5a.75.75 0 01-.75-.75zM12.22 13.28l3.22 3.22h-2.69a.75.75 0 000 1.5h4.5a.75.75 0 00.75-.75v-4.5a.75.75 0 00-1.5 0v2.69l-3.22-3.22a.75.75 0 10-1.06 1.06zM3.5 4.56l3.22 3.22a.75.75 0 001.06-1.06L4.56 3.5h2.69a.75.75 0 000-1.5h-4.5a.75.75 0 00-.75.75v4.5a.75.75 0 001.5 0V4.56z"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- New-order flash banner (supplements audio alert in noisy kitchens) -->
    <Transition name="kitchen-flash">
      <div
        v-if="newOrderFlash"
        class="kitchen-new-order-banner"
        role="status"
        aria-live="polite"
        aria-atomic="true"
      >
        <span class="h-2.5 w-2.5 rounded-full bg-amber-300 animate-ping" aria-hidden="true" />
        {{ t('kitchen.newOrderAlert') }}
      </div>
    </Transition>

    <!-- Station filter bar -->
    <nav class="kitchen-filter-bar" :aria-label="t('kitchen.stationFilterNav')">
      <button
        v-for="f in stationFilters"
        :key="f.value"
        class="kitchen-filter-btn ui-press focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
        :class="stationFilter === f.value ? 'kitchen-filter-btn--active' : ''"
        :aria-pressed="stationFilter === f.value"
        @click="stationFilter = f.value"
      >
        {{ f.label }}
        <span v-if="f.count > 0" class="kitchen-filter-count" aria-hidden="true">{{ f.count }}</span>
      </button>
    </nav>

    <!-- Search -->
    <div class="px-3 pb-1 pt-0.5 sm:px-4">
      <div class="relative">
        <input
          v-model="kitchenSearch"
          type="search"
          class="w-full rounded-xl border border-slate-700 bg-slate-800/70 py-2 ps-9 pe-4 text-sm text-slate-200 placeholder-slate-500 transition focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
          :placeholder="t('kitchen.search')"
          :aria-label="t('kitchen.search')"
        />
        <svg class="absolute start-3 top-2.5 h-4 w-4 text-slate-500 pointer-events-none" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
          <path fill-rule="evenodd" d="M9 3.5a5.5 5.5 0 1 0 0 11 5.5 5.5 0 0 0 0-11ZM2 9a7 7 0 1 1 12.452 4.391l3.328 3.329a.75.75 0 1 1-1.06 1.06l-3.329-3.328A7 7 0 0 1 2 9Z" clip-rule="evenodd"/>
        </svg>
      </div>
    </div>

    <!-- Loading: skeleton cards matching the kitchen-grid layout -->
    <div v-if="waiter.loading" class="kitchen-grid" aria-busy="true" :aria-label="t('kitchen.activeCount', { n: 0 })">
      <div v-for="i in 3" :key="i" class="kitchen-card animate-pulse border-slate-700/40 bg-slate-800/20">
        <div class="h-1.5 w-full rounded-t-xl bg-slate-700/60" />
        <div class="flex items-start justify-between gap-2 px-4 pt-5">
          <div class="flex-1 space-y-2.5">
            <div class="h-8 w-28 rounded-lg bg-slate-700/60" />
            <div class="h-3 w-40 rounded bg-slate-800/60" />
          </div>
          <div class="flex flex-col items-end gap-2 shrink-0">
            <div class="h-6 w-14 rounded-full bg-slate-700/60" />
            <div class="h-5 w-16 rounded-full bg-slate-800/50" />
          </div>
        </div>
        <div class="mt-5 flex-1 space-y-3 px-4">
          <div v-for="j in 3" :key="j" class="flex items-center gap-3">
            <div class="h-5 w-7 rounded bg-slate-700/50" />
            <div class="h-4 rounded-md bg-slate-800/50" :style="`width: ${60 + j * 20}px`" />
          </div>
        </div>
        <div class="m-4 mt-auto h-10 rounded-xl bg-slate-700/40" />
      </div>
    </div>

    <!-- All-clear -->
    <div v-else-if="!activeOrders.length" class="kitchen-empty" role="status" aria-live="polite">
      <!-- Checkmark icon -->
      <div class="flex h-24 w-24 items-center justify-center rounded-full border border-emerald-500/20 bg-emerald-500/10">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="h-12 w-12 text-emerald-400" aria-hidden="true">
          <path d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z"/>
        </svg>
      </div>
      <p class="mt-5 text-2xl font-bold tracking-tight text-slate-100">{{ t("kitchen.allClear") }}</p>
      <p class="mt-1.5 text-sm text-slate-500">{{ t("kitchen.allClearBody") }}</p>
    </div>

    <!-- Order grid -->
    <div v-else class="kitchen-grid" role="list" :aria-label="t('kitchen.activeCount', { n: activeOrders.length })">
      <article
        v-for="(order, index) in activeOrders"
        :key="order.id"
        class="kitchen-card ui-reveal"
        :class="cardClass(order.status)"
        :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
        role="listitem"
      >
        <!-- Status strip at top -->
        <div class="kitchen-strip" :class="stripClass(order.status)" />

        <!-- Order headline -->
        <div class="flex items-start justify-between gap-3 px-4 pt-4">
          <div class="min-w-0 flex-1">
            <p class="kitchen-headline truncate" :class="headlineColorClass(order.status)" :title="orderHeadline(order)">
              {{ orderHeadline(order) }}
            </p>
            <p class="mt-1 text-xs font-medium text-slate-500 tabular-nums">
              #{{ order.order_number }} · {{ timeAgo(order.created_at) }}<span v-if="order.customer_name"> · {{ order.customer_name }}</span>
            </p>
            <!-- Advance-order scheduled badge -->
            <span
              v-if="order.scheduled_for"
              class="mt-1 inline-flex items-center gap-1 rounded-full border border-violet-500/30 bg-violet-500/15 px-2 py-0.5 text-[10px] font-semibold text-violet-300"
            >
              <span aria-hidden="true">🗓️</span> {{ formatScheduledFor(order.scheduled_for) }}
            </span>
            <!-- Delivery job status chip — kitchen staff visibility -->
            <span
              v-if="order.fulfillment_type === 'delivery' && order.delivery_job"
              class="mt-1 inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] font-semibold"
              :class="djChipClass(order.delivery_job.status)"
            >
              <span
                v-if="order.delivery_job.status === 'searching'"
                class="block h-1.5 w-1.5 shrink-0 rounded-full bg-amber-400 motion-safe:animate-pulse"
                aria-hidden="true"
              />
              <span v-else aria-hidden="true">🛵</span>
              {{ djChipLabel(order.delivery_job) }}
            </span>
          </div>
          <div class="flex shrink-0 flex-col items-end gap-2">
            <!-- Elapsed timer badge -->
            <span
              class="rounded-full border px-2.5 py-0.5 text-xs font-bold tabular-nums"
              :class="elapsedBadgeClass(elapsedMinutes(order), order.status)"
              :aria-label="elapsedLabel(order)"
            >{{ elapsedLabel(order) }}</span>
            <!-- Status chip -->
            <span
              class="rounded-full border px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-widest"
              :class="chipClass(order.status)"
            >{{ t(`kitchen.status_${order.status}`) }}</span>
          </div>
        </div>

        <!-- Items header: ready progress pill -->
        <p class="sr-only">{{ t('kitchen.tapItemReady') }}</p>
        <div v-if="orderReadyCount(order).total > 0" class="mt-4 flex items-center justify-between px-4 mb-1">
          <span class="text-[11px] font-medium text-slate-500">{{ t('kitchen.tapItemReady') }}</span>
          <span
            class="rounded-full border px-2 py-0.5 text-[11px] tabular-nums font-semibold transition-colors"
            :class="orderReadyCount(order).done === orderReadyCount(order).total
              ? 'text-emerald-300 bg-emerald-500/10 border-emerald-500/25'
              : 'text-slate-400 bg-slate-800/60 border-slate-700/40'"
          >{{ orderReadyCount(order).done }}/{{ orderReadyCount(order).total }}</span>
        </div>
        <ul class="mt-2 flex-1 divide-y divide-slate-700/30 overflow-y-auto px-4" :aria-label="t('kitchen.orderItems')">
          <li
            v-for="(item, idx) in order.items"
            :key="item.id ?? idx"
            class="kitchen-item select-none"
          >
            <!-- Voided items: show struck-out label only, no toggle interaction -->
            <div
              v-if="item.is_voided"
              class="flex items-baseline gap-2.5 px-2 py-2 opacity-30 line-through"
              :aria-label="t('kitchen.itemVoided', { name: item.dish_name })"
            >
              <span class="kitchen-qty" :class="headlineColorClass(order.status)" aria-hidden="true">{{ item.qty }}×</span>
              <span class="kitchen-name font-medium">{{ item.dish_name }}</span>
            </div>
            <button
              v-else-if="item.id != null"
              type="button"
              class="flex w-full items-baseline gap-2.5 cursor-pointer ui-press text-start rounded-lg px-2 py-2 -mx-2 transition-colors hover:bg-slate-700/30"
              :class="[item.is_ready ? 'opacity-40 line-through' : '', isItemHeld(item, order) ? 'opacity-50' : '']"
              :title="t('kitchen.tapItemReady')"
              :aria-pressed="item.is_ready"
              @click="toggleItem(order, item)"
            >
              <span class="kitchen-qty" :class="headlineColorClass(order.status)" aria-hidden="true">{{ item.qty }}×</span>
              <span class="kitchen-name font-medium">{{ item.dish_name }}</span>
              <span v-if="item.note" class="ms-1 shrink-0 text-[11px] italic text-slate-500">({{ item.note }})</span>
              <!-- Course chip for kitchen -->
              <span
                v-if="(item.course ?? 0) > 0 && !item.is_ready"
                class="ms-auto shrink-0 rounded-full border px-1.5 py-0.5 text-[9px] font-bold leading-none"
                :class="isItemHeld(item, order)
                  ? 'border-amber-500/50 bg-amber-500/10 text-amber-400'
                  : 'border-slate-600/50 bg-slate-700/30 text-slate-400'"
              >{{ isItemHeld(item, order) ? `${t('waiterPage.heldChip')} · ${t('waiterPage.courseChip', { n: item.course })}` : t('waiterPage.courseChip', { n: item.course }) }}</span>
              <span v-else-if="item.is_ready" class="ms-auto shrink-0 text-emerald-400" aria-hidden="true">
                <!-- Checkmark icon -->
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="h-4 w-4" aria-hidden="true">
                  <path fill-rule="evenodd" d="M12.416 3.376a.75.75 0 0 1 .208 1.04l-5 7.5a.75.75 0 0 1-1.154.114l-3-3a.75.75 0 0 1 1.06-1.06l2.353 2.353 4.493-6.74a.75.75 0 0 1 1.04-.207Z" clip-rule="evenodd"/>
                </svg>
              </span>
            </button>
            <template v-else>
              <span class="kitchen-qty px-2 py-2" :class="headlineColorClass(order.status)" aria-hidden="true">{{ item.qty }}×</span>
              <span class="kitchen-name font-medium py-2">{{ item.dish_name }}</span>
              <span v-if="item.note" class="ms-1 shrink-0 text-[11px] italic text-slate-500">({{ item.note }})</span>
            </template>
            <!-- Combo sub-lines -->
            <template v-if="item.combo_components?.length">
              <div
                v-for="comp in item.combo_components"
                :key="comp.dish_id"
                class="flex items-baseline gap-1.5 ps-6 py-0.5 text-[11px] text-slate-500"
              >
                <span aria-hidden="true">↳</span>
                <span>{{ comp.name }} ×{{ comp.qty * item.qty }}</span>
              </div>
            </template>
          </li>
        </ul>

        <!-- Notes -->
        <div v-if="order.customer_note || order.owner_note" class="mt-3 space-y-1.5 border-t border-slate-700/40 px-4 pt-3 text-xs">
          <p v-if="order.customer_note" class="flex items-start gap-1.5 text-slate-400">
            <span class="mt-px shrink-0 font-semibold text-slate-300">{{ t("kitchen.noteCustomer") }}:</span>
            <span>{{ order.customer_note }}</span>
          </p>
          <p v-if="order.owner_note" class="flex items-start gap-1.5 text-amber-300/80">
            <span class="mt-px shrink-0 font-semibold">{{ t("kitchen.noteStaff") }}:</span>
            <span>{{ order.owner_note }}</span>
          </p>
        </div>

        <!-- Action button -->
        <div class="mt-auto space-y-2 px-4 pb-4 pt-4">
          <!-- Fire course button (owner/expediter) -->
          <button
            v-if="lowestHeldCourse(order) !== null"
            type="button"
            class="ui-btn-outline ui-press w-full gap-1.5 border-amber-500/30 text-amber-300/90 hover:border-amber-400/50 hover:text-amber-200 text-xs"
            :disabled="firingCourseOrderId === order.id"
            @click="fireCourse(order)"
          >{{ firingCourseOrderId === order.id ? t('waiterPage.firingCourse') : t('waiterPage.fireCourse', { n: lowestHeldCourse(order) }) }}</button>
          <!-- Mark all items ready at once -->
          <button
            v-if="hasUnreadyItems(order)"
            type="button"
            class="ui-btn-outline ui-press w-full gap-1.5 border-emerald-500/30 text-emerald-300/90 hover:border-emerald-400/50 hover:text-emerald-200 text-xs"
            :aria-label="`${t('kitchen.markAllReady')} — #${order.order_number}`"
            @click="markAllReady(order)"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="h-3.5 w-3.5 shrink-0" aria-hidden="true">
              <path fill-rule="evenodd" d="M12.416 3.376a.75.75 0 0 1 .208 1.04l-5 7.5a.75.75 0 0 1-1.154.114l-3-3a.75.75 0 0 1 1.06-1.06l2.353 2.353 4.493-6.74a.75.75 0 0 1 1.04-.207Z" clip-rule="evenodd"/>
            </svg>
            {{ t('kitchen.markAllReady') }}
          </button>
          <button
            v-if="waiter.nextStatus(order)"
            class="ui-btn-primary ui-touch-target w-full rounded-xl py-3 text-sm font-bold tracking-wide focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
            :class="[actionBtnClass(order.status), waiter.updatingOrderIds.has(order.id) ? 'opacity-50 pointer-events-none' : '', allItemsReady(order) && !waiter.updatingOrderIds.has(order.id) ? 'ring-2 ring-emerald-300/40 shadow-md shadow-emerald-500/20' : '']"
            :disabled="waiter.updatingOrderIds.has(order.id)"
            :aria-busy="waiter.updatingOrderIds.has(order.id)"
            :aria-label="`${actionLabel(order)} — #${order.order_number}`"
            @click="advance(order.id)"
          >
            <span v-if="waiter.updatingOrderIds.has(order.id)" class="animate-pulse" aria-hidden="true">…</span>
            <span v-else>{{ actionLabel(order) }}</span>
          </button>
          <p v-else class="text-center text-xs italic text-slate-500">{{ t("kitchen.handedOff") }}</p>
          <button
            class="ui-btn-outline ui-press w-full gap-1.5"
            :aria-label="`${t('ownerOrders.printTicket')} — #${order.order_number}`"
            @click="printTicket(order)"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="h-3.5 w-3.5 shrink-0" aria-hidden="true">
              <path fill-rule="evenodd" d="M4 2a1.5 1.5 0 0 0-1.5 1.5v2.879a2.25 2.25 0 0 0-.659 1.591v3.158A2.25 2.25 0 0 0 4.09 13.5H4.5v.5A1.5 1.5 0 0 0 6 15.5h4a1.5 1.5 0 0 0 1.5-1.5v-.5h.41a2.25 2.25 0 0 0 2.249-2.372l-.21-3.158A2.25 2.25 0 0 0 13.5 6.379V3.5A1.5 1.5 0 0 0 12 2H4Zm8.5 4.379-.097-.172A.75.75 0 0 0 11.75 6h-7.5a.75.75 0 0 0-.653.207L3.5 6.379V3.5a.5.5 0 0 1 .5-.5h8a.5.5 0 0 1 .5.5v2.879ZM10 8.5a.5.5 0 0 1 .5.5v4.5a.5.5 0 0 1-.5.5H6a.5.5 0 0 1-.5-.5V9a.5.5 0 0 1 .5-.5h4Z" clip-rule="evenodd"/>
            </svg>
            {{ t("ownerOrders.printTicket") }}
          </button>
        </div>
      </article>
    </div>
  </div>

  <!-- 86 Board modal (contract 7) — Teleported to body so it sits above fullscreen -->
  <Teleport to="body">
    <Transition name="ui-fade">
      <div
        v-if="eightySixOpen"
        class="fixed inset-0 z-[9998] flex items-end justify-center sm:items-center"
        role="dialog"
        aria-modal="true"
        :aria-label="t('kitchen.eightySixTitle')"
        @keydown.esc="eightySixOpen = false"
      >
        <!-- Backdrop -->
        <div class="absolute inset-0 bg-slate-950/70 backdrop-blur-sm" @click="eightySixOpen = false" />
        <!-- Panel -->
        <div class="relative z-10 w-full max-w-md rounded-t-2xl sm:rounded-2xl bg-slate-900 border border-slate-700/60 shadow-2xl flex flex-col max-h-[85dvh]">
          <!-- Header -->
          <div class="flex items-center justify-between gap-3 border-b border-slate-800 px-4 py-3 shrink-0">
            <h2 class="text-base font-bold text-white">{{ t('kitchen.eightySixTitle') }}</h2>
            <button
              class="ui-press flex h-9 w-9 items-center justify-center rounded-full text-slate-400 hover:text-slate-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
              :aria-label="t('common.close')"
              @click="eightySixOpen = false"
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="h-5 w-5" aria-hidden="true">
                <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z"/>
              </svg>
            </button>
          </div>
          <!-- Search -->
          <div class="px-4 pt-3 pb-2 shrink-0">
            <div class="relative">
              <svg class="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500 pointer-events-none" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                <path fill-rule="evenodd" d="M9 3.5a5.5 5.5 0 1 0 0 11 5.5 5.5 0 0 0 0-11ZM2 9a7 7 0 1 1 12.452 4.391l3.328 3.329a.75.75 0 1 1-1.06 1.06l-3.329-3.328A7 7 0 0 1 2 9Z" clip-rule="evenodd"/>
              </svg>
              <input
                v-model.trim="eightySixSearch"
                type="search"
                autofocus
                class="w-full rounded-xl border border-slate-700 bg-slate-800/70 py-2.5 ps-9 pe-4 text-sm text-slate-200 placeholder-slate-500 focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                :placeholder="t('kitchen.eightySixSearch')"
                :aria-label="t('kitchen.eightySixSearch')"
              />
            </div>
          </div>
          <!-- List -->
          <div class="overflow-y-auto flex-1 px-4 pb-4">
            <!-- Loading skeleton -->
            <div v-if="eightySixFetching" class="space-y-2 pt-1">
              <div v-for="i in 6" :key="i" class="flex animate-pulse items-center justify-between gap-2 rounded-xl px-2 py-3">
                <div class="h-4 w-36 rounded bg-slate-700/60" />
                <div class="h-9 w-24 rounded-xl bg-slate-700/40" />
              </div>
            </div>
            <div v-else-if="!eightySixFiltered.length" class="py-8 text-center text-sm text-slate-500">{{ t('kitchen.eightySixEmpty') }}</div>
            <ul v-else role="list" class="list-none space-y-1 pt-1">
              <li
                v-for="dish in eightySixFiltered"
                :key="dish.id"
                class="flex items-center justify-between gap-3 rounded-xl px-2 py-2 transition-colors hover:bg-slate-800/50"
                :class="!dish.is_available ? 'opacity-70' : ''"
              >
                <div class="min-w-0 flex-1">
                  <p class="truncate text-sm font-medium text-slate-100">{{ dish.name }}</p>
                  <p class="truncate text-[11px] text-slate-500">{{ dish.category_name || dish.category_slug }}</p>
                </div>
                <!-- Big touch target toggle — usable with greasy thumbs -->
                <button
                  role="switch"
                  class="ui-press shrink-0 rounded-xl border px-4 py-2.5 text-sm font-semibold transition-colors disabled:opacity-50 min-w-[5.5rem] text-center"
                  :class="dish.is_available
                    ? 'border-emerald-500/40 text-emerald-300 hover:border-red-400/50 hover:bg-red-500/10 hover:text-red-300'
                    : 'border-red-500/40 bg-red-500/10 text-red-300 hover:border-emerald-400/50 hover:bg-emerald-500/10 hover:text-emerald-300'"
                  :disabled="eightySixTogglingId === dish.id"
                  :aria-checked="dish.is_available"
                  :aria-busy="eightySixTogglingId === dish.id"
                  :aria-label="`${dish.name} — ${dish.is_available ? t('kitchen.eightySixAvailable') : t('kitchen.eightySixSoldOut')}`"
                  @click="toggle86Dish(dish)"
                >
                  {{ eightySixTogglingId === dish.id ? '…' : (dish.is_available ? t('kitchen.eightySixAvailable') : t('kitchen.eightySixSoldOut')) }}
                </button>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { computed, onActivated, onDeactivated, onMounted, onUnmounted, ref, watch } from "vue";
import { useI18n } from "../composables/useI18n";
import { useWaiterStore } from "../stores/waiter";
import { useToastStore } from "../stores/toast";
import { usePrintTicket } from "../composables/usePrintTicket";
import { useNowTicker } from "../composables/useNowTicker";
import { chipClass as statusChipClass } from "../lib/orderStatusMeta";
import { useWakeLock } from "../composables/useWakeLock";
import { useOwnerRealtime } from "../composables/useOwnerRealtime";
import api from "../lib/api";
import { bustCache } from "../lib/staleCache";

// Under KeepAlive the kitchen page stays alive across navigation — poll timer,
// wake lock and WS handlers start on activated, stop on deactivated.
defineOptions({ name: "OwnerKitchen" });

const { t, formatDateTime, currentLocale } = useI18n();
const waiter = useWaiterStore();
const toast = useToastStore();
const { printTicket } = usePrintTicket();

// ── Wake lock (contract 3) ────────────────────────────────────────────────────
// useWakeLock manages its own onMounted/onUnmounted — no return value needed.
useWakeLock();

// ── Realtime channel (contract 6c — kitchen-local WS for instant updates) ────
// The kitchen has its own WS subscription so it reacts to order events even
// when the OwnerLayout WS is also running. Connecting in onActivated.
const kitchenRealtime = useOwnerRealtime((event) => {
  if (typeof event === "string" && event.startsWith("order.")) {
    doPoll();
  }
});

// ── Connection state chip (contract 6c) ───────────────────────────────────────
const wsState = computed(() => kitchenRealtime.connectionState?.value ?? "connecting");

// ── 86 board state (contract 7) ───────────────────────────────────────────────
const eightySixOpen = ref(false);
const eightySixDishes = ref([]);
const eightySixFetching = ref(false);
const eightySixSearch = ref("");
const eightySixTogglingId = ref(null);

const eightySixFiltered = computed(() => {
  const q = eightySixSearch.value.toLowerCase();
  const list = [...eightySixDishes.value]
    .filter((d) => d.is_published)
    .sort((a, b) => {
      // 86'd (unavailable) pinned on top
      if (!a.is_available && b.is_available) return -1;
      if (a.is_available && !b.is_available) return 1;
      return 0;
    });
  if (!q) return list;
  return list.filter(
    (d) =>
      (d.name || "").toLowerCase().includes(q) ||
      (d.category_name || "").toLowerCase().includes(q)
  );
});

// Always refetch on open: another device (owner panel, second kitchen tablet)
// may have 86'd a dish since the board was last shown. The existing list stays
// visible while the refetch is in flight so the board never flashes empty.
const fetch86Dishes = async () => {
  if (eightySixFetching.value) return;
  eightySixFetching.value = true;
  try {
    const { data } = await api.get("/dishes/", { timeout: 6000 });
    eightySixDishes.value = Array.isArray(data) ? data : [];
  } catch {
    toast.show(t("ownerHome.noDishesLoaded"), "error");
  } finally {
    eightySixFetching.value = false;
  }
};

const toggle86Dish = async (dish) => {
  if (eightySixTogglingId.value === dish.id) return;
  eightySixTogglingId.value = dish.id;
  const newVal = !dish.is_available;
  try {
    await api.patch(`/dishes/${dish.id}/`, { is_available: newVal });
    dish.is_available = newVal;
    bustCache("menu.categories");
  } catch (err) {
    const status = err?.response?.status;
    if (status === 403) {
      toast.show(t("kitchen.eightySixToggleFailed403"), "error");
    } else {
      toast.show(t("kitchen.eightySixToggleFailed"), "error");
    }
  } finally {
    eightySixTogglingId.value = null;
  }
};

const open86Board = () => {
  eightySixOpen.value = true;
  fetch86Dishes();
};

const isFullscreen = ref(false);
const stationFilter = ref("all");

// ── Sound toggle (task 4) ─────────────────────────────────────────────────────
const KITCHEN_SOUND_KEY = "kitchen:sound";
const kitchenSoundOn = ref((() => {
  try { return localStorage.getItem(KITCHEN_SOUND_KEY) !== "off"; } catch { return true; }
})());
watch(kitchenSoundOn, (val) => {
  try { localStorage.setItem(KITCHEN_SOUND_KEY, val ? "on" : "off"); } catch { /* ignore */ }
});

// Lazy AudioContext — created only after the first user click on the sound toggle
// so Chrome's autoplay policy is satisfied.
let _kitchenAudioCtx = null;
const _ensureAudioCtx = () => {
  if (!_kitchenAudioCtx) {
    try { _kitchenAudioCtx = new (window.AudioContext || window.webkitAudioContext)(); } catch { /* unsupported */ }
  }
  return _kitchenAudioCtx;
};
const toggleKitchenSound = () => {
  // Prime the AudioContext on the click that enables sound (autoplay policy).
  if (!kitchenSoundOn.value) _ensureAudioCtx();
  kitchenSoundOn.value = !kitchenSoundOn.value;
};

// ── Seen-IDs set for new-order detection (task 4) ────────────────────────────
// Populated after first load; any id not present on subsequent polls is "new".
let _seenOrderIds = null; // null = not yet initialized

// Elapsed badges use the shared 30-s ticker composable.
const { now: tickerNow } = useNowTicker();

// Visual flash when a new pending order arrives (supplements the audio alert)
const newOrderFlash = ref(false);
let flashTimer = null;

// Active orders — exclude completed/cancelled, apply station filter + search
const ACTIVE_STATUSES = new Set(["pending", "confirmed", "preparing", "ready"]);
const kitchenSearch = ref("");

const allActiveOrders = computed(() =>
  waiter.orders.filter((o) => ACTIVE_STATUSES.has(o.status))
);

const activeOrders = computed(() => {
  let orders = allActiveOrders.value;
  if (stationFilter.value !== "all") {
    orders = orders.filter((o) => o.fulfillment_type === stationFilter.value);
  }
  const q = kitchenSearch.value.trim().toLowerCase();
  if (!q) return orders;
  return orders.filter((o) =>
    (o.order_number || "").toLowerCase().includes(q) ||
    (o.customer_name || "").toLowerCase().includes(q) ||
    (o.table_label || "").toLowerCase().includes(q)
  );
});

// Station filter options with live counts.
// Non-"all" options with 0 orders are hidden (no useful filter to offer).
const stationFilters = computed(() => {
  const all = allActiveOrders.value;
  const count = (type) => all.filter((o) => o.fulfillment_type === type).length;
  const counts = {
    table: count("table"),
    pickup: count("pickup"),
    delivery: count("delivery"),
  };
  return [
    { value: "all",      label: t("kitchen.filterAll"),      count: all.length },
    ...(counts.table    > 0 ? [{ value: "table",    label: t("kitchen.filterTables"),   count: counts.table }]    : []),
    ...(counts.pickup   > 0 ? [{ value: "pickup",   label: t("kitchen.pickup"),         count: counts.pickup }]   : []),
    ...(counts.delivery > 0 ? [{ value: "delivery", label: t("kitchen.delivery"),       count: counts.delivery }] : []),
  ];
});

// When the selected station filter has no more active orders, fall back to "all"
// so the kitchen never gets stuck showing an empty filtered view.
watch(stationFilters, (filters) => {
  if (stationFilter.value === "all") return;
  const still = filters.find((f) => f.value === stationFilter.value);
  if (!still || still.count === 0) stationFilter.value = "all";
});

// Elapsed time helpers — use status_updated_at when available, else created_at
const elapsedMinutes = (order) => {
  const base = order.status_updated_at || order.created_at;
  return Math.floor((tickerNow.value - new Date(base).getTime()) / 60_000);
};

const elapsedBadgeClass = (minutes, status) => {
  if (status === "preparing" && minutes > 15) return "border-amber-500/50 bg-amber-500/15 text-amber-300";
  if (minutes >= 20) return "border-red-500/50 bg-red-500/15 text-red-300";
  if (minutes >= 10) return "border-amber-500/50 bg-amber-500/15 text-amber-300";
  return "border-slate-600/60 bg-slate-700/40 text-slate-400";
};

// Elapsed badge label — uses orderFlow.elapsed / orderFlow.overdue keys
const elapsedLabel = (order) => {
  const m = elapsedMinutes(order);
  if (order.status === "preparing" && m > 15) return t("orderFlow.overdue", { m });
  return t("orderFlow.elapsed", { m });
};

// ── Clock ─────────────────────────────────────────────────────────────────────
const clockDisplay = ref("");
let clockTimer = null;
const updateClock = () => {
  const now = new Date();
  clockDisplay.value = new Intl.DateTimeFormat(currentLocale.value, { hour: "2-digit", minute: "2-digit" }).format(now);
};

// ── Fullscreen ────────────────────────────────────────────────────────────────
let _fsReturnFocus = null;

const toggleFullscreen = () => {
  // Save the element that has focus now so we can restore it when exiting.
  _fsReturnFocus = document.activeElement;
  if (!document.fullscreenEnabled) {
    isFullscreen.value = !isFullscreen.value;
    return;
  }
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen().catch(() => {
      isFullscreen.value = !isFullscreen.value;
    });
    isFullscreen.value = true;
  } else {
    document.exitFullscreen();
    isFullscreen.value = false;
  }
};

const onFullscreenChange = () => {
  const wasFullscreen = isFullscreen.value;
  isFullscreen.value = Boolean(document.fullscreenElement);
  // When the user exits fullscreen (Esc or button), the browser moves focus to
  // <body>. Return it to whichever element launched the toggle.
  if (wasFullscreen && !isFullscreen.value && _fsReturnFocus) {
    _fsReturnFocus.focus?.();
    _fsReturnFocus = null;
  }
};

// ── Polling ───────────────────────────────────────────────────────────────────
let pollTimer = null;
let prevPendingIds = new Set();

const playAlert = () => {
  // Two-tone WebAudio beep — uses the lazy context so autoplay policy is satisfied.
  if (kitchenSoundOn.value) {
    try {
      const ctx = _ensureAudioCtx();
      if (ctx) {
        const play = () => {
          // Two tones: 620 Hz then 820 Hz, ~150 ms each
          [[620, 0], [820, 0.17]].forEach(([freq, delay]) => {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.type = "sine";
            osc.frequency.value = freq;
            gain.gain.setValueAtTime(0.4, ctx.currentTime + delay);
            gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + delay + 0.3);
            osc.start(ctx.currentTime + delay);
            osc.stop(ctx.currentTime + delay + 0.32);
          });
        };
        if (ctx.state === "suspended") { ctx.resume().then(play).catch(() => {}); }
        else { play(); }
      }
    } catch { /* AudioContext unavailable */ }
  }
  // Visual flash for 4 s (supplements audio — noisy kitchen environments)
  newOrderFlash.value = true;
  clearTimeout(flashTimer);
  flashTimer = setTimeout(() => { newOrderFlash.value = false; }, 4000);
};

const checkNewOrders = (orders) => {
  const pendingIds = new Set(orders.filter((o) => o.status === "pending").map((o) => o.id));
  if ([...pendingIds].some((id) => !prevPendingIds.has(id)) && prevPendingIds.size > 0) playAlert();
  prevPendingIds = pendingIds;
};

// Detect truly new order IDs (any status) after first load — drives the toast.
const checkNewOrderIds = (orders) => {
  if (_seenOrderIds === null) {
    // First load — seed, no toast.
    _seenOrderIds = new Set(orders.map((o) => o.id));
    return;
  }
  const newOnes = orders.filter((o) => !_seenOrderIds.has(o.id));
  orders.forEach((o) => _seenOrderIds.add(o.id));
  if (newOnes.length > 0) {
    toast.show(t("orderFlow.newOrder"), "info");
  }
};

const doPoll = async () => {
  const results = await waiter.fetchOrders({ silent: true });
  if (Array.isArray(results)) {
    checkNewOrders(results);
    checkNewOrderIds(results);
  }
};

const onKitchenPageVisible = () => {
  if (document.visibilityState === "visible") doPoll();
};

// ── Shared start/stop helpers (used by both mount and KeepAlive activate) ─────
const startKitchenPolling = () => {
  if (pollTimer) return;
  pollTimer = setInterval(() => {
    // Do NOT skip when hidden — browser throttles hidden timers which is
    // acceptable; an explicit skip means ZERO updates and no alert beep.
    doPoll();
  }, 10_000); // 10s for kitchen — faster than regular waiter view
};

const stopKitchenPolling = () => {
  clearInterval(pollTimer);
  pollTimer = null;
};

const startClock = () => {
  if (clockTimer) return; // guard against double-start across activations
  updateClock();
  clockTimer = setInterval(updateClock, 1_000);
};
const stopClock = () => {
  clearInterval(clockTimer);
  clockTimer = null;
};

// One-time setup that survives KeepAlive park/unpark. Live-loop concerns
// (clock, poll, WS, wake lock) are owned by onActivated/onDeactivated so they
// pause while the page is parked behind another. onActivated fires right after
// onMounted on first mount, so the live loop still starts on initial load.
onMounted(async () => {
  waiter.setupConnectivityListeners();
  document.addEventListener("fullscreenchange", onFullscreenChange);
  document.addEventListener("visibilitychange", onKitchenPageVisible);

  const initial = await waiter.fetchOrders();
  if (Array.isArray(initial)) {
    prevPendingIds = new Set(initial.filter((o) => o.status === "pending").map((o) => o.id));
    checkNewOrderIds(initial); // seeds _seenOrderIds on first load
  }
});

// Under KeepAlive: start the live loop when the page becomes active. This also
// fires on the first mount (after onMounted), so connect()/poll start here only
// — never duplicated in onMounted.
onActivated(() => {
  startClock();
  doPoll(); // immediate fresh state on activation
  startKitchenPolling();
  kitchenRealtime.connect();
});

// Under KeepAlive: pause the whole live loop when navigating away (wake lock is
// released by the useWakeLock composable's own onDeactivated hook).
onDeactivated(() => {
  stopKitchenPolling();
  stopClock();
  kitchenRealtime.disconnect();
  eightySixOpen.value = false; // don't leave the 86 modal teleported over another page
});

onUnmounted(() => {
  stopKitchenPolling();
  stopClock();
  clearTimeout(flashTimer);
  document.removeEventListener("fullscreenchange", onFullscreenChange);
  document.removeEventListener("visibilitychange", onKitchenPageVisible);
  waiter.teardownConnectivityListeners();
  kitchenRealtime.disconnect();
  if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
});

// ── Course sequencing helpers ──────────────────────────────────────────────────
const firingCourseOrderId = ref(null);

const isItemHeld = (item, order) => {
  const c = item.course ?? 0;
  if (c === 0) return false;
  return c > (order.fired_course ?? 1);
};

const lowestHeldCourse = (order) => {
  if (order.fulfillment_type !== 'table') return null;
  const firedCourse = order.fired_course ?? 1;
  let lowest = null;
  for (const item of (order.items || [])) {
    const c = item.course ?? 0;
    if (c > 0 && c > firedCourse) {
      if (lowest === null || c < lowest) lowest = c;
    }
  }
  return lowest;
};

const fireCourse = async (order) => {
  const course = lowestHeldCourse(order);
  if (!course || firingCourseOrderId.value === order.id) return;
  firingCourseOrderId.value = order.id;
  try {
    const { data } = await api.post(`/staff/orders/${order.id}/fire-course/`, { course });
    const o = waiter.orders.find((x) => x.id === order.id);
    if (o) o.fired_course = data.fired_course ?? course;
  } catch (err) {
    const code = err?.response?.data?.code;
    const keyMap = {
      already_fired: 'fireCourseError_already_fired',
      not_table: 'fireCourseError_not_table',
      bad_status: 'fireCourseError_bad_status',
      invalid_course: 'fireCourseError_invalid_course',
    };
    const msgKey = keyMap[code] || 'fireCourseError_default';
    toast.show(t(`waiterPage.${msgKey}`, { n: course }), 'error');
  } finally {
    firingCourseOrderId.value = null;
  }
};

const advance = async (orderId) => {
  const ok = await waiter.advanceStatus(orderId);
  if (!ok) toast.show(t('kitchen.updateFailed'), 'error');
};
const toggleItem = async (order, item) => {
  if (item?.id == null) return; // older payloads without item ids → no-op
  const ok = await waiter.toggleItemReady(order.id, item.id, !item.is_ready);
  if (!ok) toast.show(t('kitchen.itemToggleFailed'), 'error');
};

// ── Bulk item-readiness helpers ────────────────────────────────────────────────
const orderReadyCount = (order) => {
  const trackable = order.items.filter((i) => i.id != null && !i.is_voided);
  return { done: trackable.filter((i) => i.is_ready).length, total: trackable.length };
};

const hasUnreadyItems = (order) =>
  order.items.some((i) => i.id != null && !i.is_voided && !i.is_ready);

const allItemsReady = (order) => {
  const rc = orderReadyCount(order);
  return rc.total > 0 && rc.done === rc.total;
};

const markAllReady = async (order) => {
  // Use the bulk endpoint (POST /staff/orders/<id>/items/ready-all/) which
  // marks all non-voided, not-yet-ready items in a single request.
  try {
    const { data } = await api.post(`/staff/orders/${order.id}/items/ready-all/`);
    // Merge the updated order items back into the store
    const stored = waiter.orders.find((o) => o.id === order.id);
    if (stored && Array.isArray(data.items)) {
      stored.items = data.items;
    }
  } catch (err) {
    const code = err?.response?.data?.code;
    if (code === "bad_status") {
      // Order is terminal — show a clear message
      toast.show(t("kitchen.markAllFailed"), "error");
    } else {
      toast.show(t("kitchen.markAllFailed"), "error");
    }
  }
};

// ── Display helpers ────────────────────────────────────────────────────────────
const orderHeadline = (order) => {
  if (order.fulfillment_type === "table" && order.table_label) return order.table_label;
  if (order.fulfillment_type === "pickup") return t("kitchen.pickup");
  if (order.fulfillment_type === "delivery") return t("kitchen.delivery");
  return `#${order.order_number}`;
};

const timeAgo = (iso) => {
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (diff < 60) return t("kitchen.justNow");
  if (diff < 3600) return t("kitchen.minsAgo", { n: Math.floor(diff / 60) });
  return t("kitchen.hrsAgo", { n: Math.floor(diff / 3600) });
};

const formatScheduledFor = (iso) => {
  if (!iso) return "";
  try {
    return formatDateTime(iso, { weekday: "short", dateStyle: undefined, timeStyle: undefined, day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
  } catch {
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? "" : d.toLocaleString();
  }
};

const actionLabel = (order) => ({
  pending: t("kitchen.actionAccept"),
  confirmed: t("kitchen.actionPreparing"),
  preparing: t("kitchen.actionReady"),
  ready: order.fulfillment_type === "delivery" ? t("kitchen.actionOutForDelivery") : t("kitchen.actionDone"),
}[order.status] ?? "");

// ── Styling ────────────────────────────────────────────────────────────────────
const cardClass = (s) => ({
  pending:   "border-amber-500/30 bg-amber-500/5",
  confirmed: "border-sky-500/30 bg-sky-500/5",
  preparing: "border-orange-500/30 bg-orange-500/5",
  ready:     "border-emerald-500/30 bg-emerald-500/5",
}[s] ?? "border-slate-700/40 bg-slate-800/20");

const stripClass = (s) => ({
  pending:   "bg-amber-500",
  confirmed: "bg-sky-500",
  preparing: "bg-orange-500",
  ready:     "bg-emerald-500",
}[s] ?? "bg-slate-600");

const headlineColorClass = (s) => ({
  pending:   "text-amber-300",
  confirmed: "text-sky-300",
  preparing: "text-orange-300",
  ready:     "text-emerald-300",
}[s] ?? "text-slate-200");

// chipClass now delegates to STATUS_META (statusChipClass imported at top).
const chipClass = (s) => statusChipClass(s);

const actionBtnClass = (s) => ({
  pending:   "bg-amber-500 hover:bg-amber-400 text-white",
  confirmed: "bg-sky-500 hover:bg-sky-400 text-white",
  preparing: "bg-orange-500 hover:bg-orange-400 text-white",
  ready:     "bg-emerald-500 hover:bg-emerald-400 text-white",
}[s] ?? "bg-slate-600 hover:bg-slate-500 text-white");

// ── Delivery job chip helpers ─────────────────────────────────────────────────
const djChipClass = (djStatus) => ({
  searching:     "border-amber-500/40 bg-amber-500/10 text-amber-300",
  assigned:      "border-sky-500/40 bg-sky-500/10 text-sky-300",
  at_restaurant: "border-sky-500/40 bg-sky-500/10 text-sky-300",
  picked_up:     "border-violet-500/40 bg-violet-500/10 text-violet-300",
  delivered:     "border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
  failed:        "border-red-500/40 bg-red-500/10 text-red-300",
  cancelled:     "border-slate-600/40 bg-slate-800/40 text-slate-400",
}[djStatus] ?? "border-slate-600/40 bg-slate-800/40 text-slate-400");

const djChipLabel = (dj) => {
  const { status, driver_name } = dj;
  if (status === "searching")     return t("kitchen.driverSearching");
  if (status === "assigned")      return driver_name ? `${t("kitchen.driverAssigned")} · ${driver_name}` : t("kitchen.driverAssigned");
  if (status === "at_restaurant") return driver_name ? `${t("kitchen.driverAtDoor")} · ${driver_name}` : t("kitchen.driverAtDoor");
  if (status === "picked_up")     return t("kitchen.driverPickedUp");
  if (status === "failed")        return t("kitchen.driverFailed");
  return status;
};
</script>

<style scoped>
/* Kitchen shell — overrides the owner layout's max-width container */
.kitchen-shell {
  position: relative;
  min-height: calc(100vh - 8rem);
  display: flex;
  flex-direction: column;
  gap: 1rem;
  background: #0b0f1a;
  border-radius: 1rem;
  padding: 0.75rem;
}

.kitchen-shell.kitchen-fullscreen {
  position: fixed;
  inset: 0;
  z-index: 9999;
  border-radius: 0;
  padding: 1rem;
  min-height: 100dvh;
}

.kitchen-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(15, 23, 42, 0.95);
  border: 1px solid rgba(51, 65, 85, 0.6);
  border-radius: 0.875rem;
  padding: 0.625rem 1rem;
  flex-shrink: 0;
}

.kitchen-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  min-height: 20rem;
  gap: 0;
  text-align: center;
  padding: 2rem 1rem;
}

/* Responsive grid: 1 col on phones, 2 on tablet, 3+ on wide kitchen displays */
.kitchen-grid {
  display: grid;
  gap: 1rem;
  grid-template-columns: 1fr;
  flex: 1;
  align-content: start;
}

@media (min-width: 640px) {
  .kitchen-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 1rem;
  }
}

@media (min-width: 1024px) {
  .kitchen-grid {
    grid-template-columns: repeat(3, 1fr);
    gap: 1.25rem;
  }
}

@media (min-width: 1400px) {
  .kitchen-grid {
    grid-template-columns: repeat(4, 1fr);
    gap: 1.25rem;
  }
}

.kitchen-card {
  display: flex;
  flex-direction: column;
  border-radius: 1rem;
  border-width: 1px;
  overflow: hidden;
  min-height: 20rem;
  background: rgba(15, 23, 42, 0.65);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3), 0 1px 2px rgba(0, 0, 0, 0.2);
}

.kitchen-strip {
  height: 0.375rem;
  width: 100%;
  flex-shrink: 0;
}

/* Very large — readable at arm's length on a tablet mounted in a kitchen */
.kitchen-headline {
  font-size: clamp(1.75rem, 5vw, 2.5rem);
  font-weight: 800;
  line-height: 1.1;
  letter-spacing: -0.01em;
}

.kitchen-item {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  font-size: 1.05rem;
  line-height: 1.5;
  color: rgb(226, 232, 240);
}

.kitchen-qty {
  flex-shrink: 0;
  font-size: 1.1rem;
  font-weight: 800;
  letter-spacing: -0.01em;
}

.kitchen-name {
  min-width: 0;
  word-break: break-word;
  font-size: 1rem;
}

/* Station filter bar */
.kitchen-filter-bar {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
  flex-shrink: 0;
}

.kitchen-filter-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  border-radius: 9999px;
  border: 1px solid rgba(51, 65, 85, 0.6);
  background: rgba(30, 41, 59, 0.5);
  padding: 0.375rem 1rem;
  font-size: 0.8rem;
  font-weight: 600;
  color: rgb(148, 163, 184);
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s, background 0.15s;
}

.kitchen-filter-btn:hover {
  border-color: rgba(100, 116, 139, 0.8);
  color: rgb(203, 213, 225);
  background: rgba(30, 41, 59, 0.7);
}

.kitchen-filter-btn--active {
  border-color: rgba(245, 158, 11, 0.5);
  background: rgba(245, 158, 11, 0.12);
  color: rgb(251, 191, 36);
  font-weight: 700;
}

.kitchen-fs-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 0.75rem;
  border: 1px solid rgba(51, 65, 85, 0.6);
  background: rgba(30, 41, 59, 0.55);
  padding: 0.4rem 0.5rem;
  color: rgb(148, 163, 184);
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s, background 0.15s;
}

.kitchen-fs-btn:hover {
  border-color: rgba(100, 116, 139, 0.8);
  color: rgb(203, 213, 225);
  background: rgba(30, 41, 59, 0.8);
}

/* New-order flash banner */
.kitchen-new-order-banner {
  position: fixed;
  top: 1.25rem;
  left: 50%;
  transform: translateX(-50%);
  z-index: 9500;
  display: inline-flex;
  align-items: center;
  gap: 0.625rem;
  background: rgba(245, 158, 11, 0.92);
  border: 1px solid rgba(251, 191, 36, 0.7);
  border-radius: 9999px;
  padding: 0.5rem 1.25rem;
  font-size: 0.9rem;
  font-weight: 800;
  color: #fff;
  letter-spacing: 0.01em;
  box-shadow: 0 4px 24px rgba(245, 158, 11, 0.55), 0 1px 4px rgba(0, 0, 0, 0.4);
  pointer-events: none;
  white-space: nowrap;
}

.kitchen-flash-enter-active,
.kitchen-flash-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}
.kitchen-flash-enter-from,
.kitchen-flash-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(-0.5rem);
}

.kitchen-filter-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 1.35rem;
  height: 1.35rem;
  border-radius: 9999px;
  background: rgba(51, 65, 85, 0.9);
  font-size: 0.7rem;
  font-weight: 700;
  color: rgb(148, 163, 184);
  padding: 0 0.3rem;
}

.kitchen-filter-btn--active .kitchen-filter-count {
  background: rgba(245, 158, 11, 0.25);
  color: rgb(251, 191, 36);
}
</style>
