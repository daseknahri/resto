<template>
  <div class="mx-auto max-w-2xl space-y-4 px-3 py-4 pb-28 sm:px-4 ui-safe-bottom">
    <!-- Screen-reader live region: announces status changes as they arrive -->
    <div
      v-if="orderData"
      role="status"
      aria-live="polite"
      aria-atomic="true"
      class="sr-only"
    >{{ statusLabel(orderData?.status) }}</div>

    <!-- Loading skeleton -->
    <div v-if="loading && !orderData" class="space-y-3" aria-busy="true" aria-label="Loading order status">
      <div class="ui-skeleton animate-pulse p-5 space-y-3">
        <div class="h-2.5 w-16 rounded bg-slate-700/60" />
        <div class="flex items-start justify-between gap-3">
          <div class="space-y-2">
            <div class="h-6 w-44 rounded bg-slate-700/60" />
            <div class="h-5 w-28 rounded-full bg-slate-800/60" />
          </div>
          <div class="h-8 w-20 rounded bg-slate-700/50" />
        </div>
      </div>
      <div class="ui-skeleton animate-pulse p-5 space-y-4">
        <div class="flex items-center justify-between gap-2">
          <div v-for="i in 4" :key="i" class="flex flex-1 flex-col items-center gap-2">
            <div class="h-9 w-9 rounded-full bg-slate-700/60" />
            <div class="h-2 w-10 rounded bg-slate-800/50" />
          </div>
        </div>
        <div class="h-1.5 w-full rounded-full bg-slate-800/60" />
      </div>
      <div class="ui-skeleton animate-pulse p-5 space-y-3">
        <div class="h-2.5 w-20 rounded bg-slate-700/60" />
        <div v-for="i in 3" :key="i" class="flex items-center justify-between gap-3">
          <div class="h-3 w-36 rounded bg-slate-800/60" />
          <div class="h-3 w-14 rounded bg-slate-800/50" />
        </div>
      </div>
    </div>

    <!-- Not found -->
    <div v-else-if="notFound" class="ui-empty-state p-10 text-center space-y-4">
      <AppIcon name="info" class="mx-auto h-10 w-10 text-slate-500" aria-hidden="true" />
      <p class="text-base font-semibold text-slate-100">{{ t("orderStatus.notFound") }}</p>
      <RouterLink :to="{ name: 'menu' }" class="ui-btn-outline inline-flex px-5 py-2.5 text-sm">
        {{ t("orderStatus.backToMenu") }}
      </RouterLink>
    </div>

    <template v-else-if="orderData">
      <!-- 🎉 Just-placed celebration banner — shown for ~5s right after order placement -->
      <Transition name="ui-fade">
        <div
          v-if="showJustPlacedBanner"
          class="ui-reveal flex items-center gap-3 rounded-2xl border border-emerald-400/40 bg-emerald-500/10 px-4 py-3.5"
          role="status"
          :style="{ '--ui-delay': '0ms' }"
        >
          <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl border border-emerald-400/30 bg-emerald-500/15">
            <svg viewBox="0 0 20 20" fill="currentColor" class="h-5 w-5 text-emerald-400" aria-hidden="true">
              <path fill-rule="evenodd" d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z" clip-rule="evenodd" />
            </svg>
          </div>
          <div class="min-w-0 flex-1">
            <p class="text-sm font-bold text-emerald-200">{{ t('orderStatus.justPlacedTitle') }}</p>
            <p class="mt-0.5 text-xs text-emerald-200/70">{{ t('orderStatus.justPlacedSubtitle') }}</p>
          </div>
          <button
            class="shrink-0 rounded-full p-1 text-emerald-400/60 transition hover:text-emerald-300"
            :aria-label="t('common.dismiss')"
            @click="showJustPlacedBanner = false"
          >
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" class="h-4 w-4" aria-hidden="true"><path d="M4 4l8 8M12 4l-8 8"/></svg>
          </button>
        </div>
      </Transition>

      <!-- Poll-failure warning — shown after 2+ consecutive refresh failures -->
      <div
        v-if="pollFailures > 1 && isLiveStatus && !loading"
        role="alert"
        class="flex items-center gap-2.5 rounded-xl border border-amber-500/25 bg-amber-500/8 px-3.5 py-2.5"
      >
        <svg aria-hidden="true" viewBox="0 0 16 16" fill="currentColor" class="h-3.5 w-3.5 shrink-0 text-amber-400"><path fill-rule="evenodd" d="M8.485 2.495c-.673-1.167-2.357-1.167-3.03 0L1.166 8.741C.473 9.938 1.324 11.5 2.712 11.5h10.576c1.388 0 2.239-1.562 1.546-2.759L8.485 2.495ZM8 5a.75.75 0 0 1 .75.75V8a.75.75 0 1 1-1.5 0V5.75A.75.75 0 0 1 8 5Zm0 6a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z" clip-rule="evenodd"/></svg>
        <p class="flex-1 text-xs text-amber-300">{{ t('orderStatus.pollFailed') }}</p>
        <button
          type="button"
          class="shrink-0 text-xs font-semibold text-amber-300 underline underline-offset-2 hover:text-amber-200 focus-visible:outline-none"
          @click="fetchStatus"
        >{{ t('common.retry') }}</button>
      </div>

      <!-- Proof-of-delivery code (give it to your driver) -->
      <div
        v-if="orderData.delivery_code"
        class="ui-reveal rounded-2xl border border-indigo-400/50 bg-indigo-500/12 p-5 text-center"
        :style="{ '--ui-delay': '28ms' }"
      >
        <p class="ui-kicker text-indigo-300">{{ t("orderStatus.deliveryCodeTitle") }}</p>
        <p class="mt-2 text-4xl font-bold tracking-[0.35em] text-white tabular-nums">{{ orderData.delivery_code }}</p>
        <p class="mt-1.5 text-xs text-indigo-100/75">{{ t("orderStatus.deliveryCodeHint") }}</p>
        <button
          class="mt-3 inline-flex items-center gap-1.5 rounded-full border px-4 py-1.5 text-xs font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400/50"
          :class="codeCopied
            ? 'border-emerald-400/50 bg-emerald-500/10 text-emerald-300'
            : 'border-indigo-400/40 text-indigo-300 hover:border-indigo-400/70 hover:bg-indigo-500/10'"
          :aria-label="codeCopied ? t('orderStatus.deliveryCodeCopied') : t('orderStatus.deliveryCodeCopy')"
          @click="copyDeliveryCode(orderData.delivery_code)"
        >
          <svg v-if="codeCopied" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="h-3.5 w-3.5 shrink-0" aria-hidden="true"><path d="M2.5 8L6 11.5 13.5 4"/></svg>
          <svg v-else viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" class="h-3.5 w-3.5 shrink-0" aria-hidden="true"><rect x="5" y="3" width="9" height="11" rx="1.5"/><path d="M11 3V2a1 1 0 0 0-1-1H3a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h1"/></svg>
          {{ codeCopied ? t("orderStatus.deliveryCodeCopied") : t("orderStatus.deliveryCodeCopy") }}
        </button>
      </div>

      <!-- Order-ready banner -->
      <div
        v-if="orderData.status === 'ready'"
        class="ui-reveal relative overflow-hidden rounded-2xl border border-emerald-400/50 bg-emerald-500/12 p-5 text-center shadow-xl shadow-emerald-900/25 sm:p-6"
        :style="{ '--ui-delay': '28ms' }"
      >
        <!-- background glow -->
        <div class="pointer-events-none absolute inset-0 rounded-2xl bg-[radial-gradient(ellipse_at_top,rgba(52,211,153,0.18),transparent_60%)]" />
        <div class="relative space-y-2">
          <p class="text-3xl" aria-hidden="true">🎉</p>
          <p class="text-2xl font-bold text-emerald-200">{{ t("orderStatus.orderReadyTitle") }}</p>
          <p class="text-sm text-emerald-100/75">
            {{ fulfillmentLabel(orderData) === t("orderStatus.fulfillmentDelivery") ? t("orderStatus.readyBodyDelivery") : t("orderStatus.readyBodyPickup") }}
          </p>
        </div>
      </div>

      <!-- Scheduled (advance order) banner -->
      <div
        v-if="orderData.status === 'scheduled' && orderData.scheduled_for"
        class="ui-reveal rounded-2xl border border-violet-400/50 bg-violet-500/12 p-5 text-center shadow-lg shadow-violet-900/20"
        :style="{ '--ui-delay': '28ms' }"
      >
        <p class="text-2xl" aria-hidden="true">🗓️</p>
        <p class="mt-1.5 text-lg font-bold text-violet-100">{{ t("orderStatus.scheduledTitle") }}</p>
        <p class="mt-1 text-sm text-violet-100/80">
          {{ t("orderStatus.scheduledBody", { time: formatScheduledFor(orderData.scheduled_for) }) }}
        </p>
      </div>

      <!-- Order-cancelled banner -->
      <div
        v-if="orderData.status === 'cancelled'"
        class="ui-reveal rounded-2xl border border-red-400/60 bg-red-500/15 p-5 text-center shadow-lg shadow-red-900/20"
        :style="{ '--ui-delay': '28ms' }"
        role="alert"
      >
        <p class="text-2xl font-bold text-red-200">{{ t("orderStatus.cancelledTitle") }}</p>
        <p class="mt-1.5 text-sm text-red-100/80">{{ t("orderStatus.cancelledBody") }}</p>
        <RouterLink :to="{ name: 'menu' }" class="mt-4 ui-btn-primary inline-flex items-center justify-center px-5 py-2 text-sm">
          {{ t("orderStatus.backToMenu") }}
        </RouterLink>
      </div>

      <!-- Header -->
      <div class="ui-hero-ribbon ui-reveal p-5 sm:p-6" :style="{ '--ui-delay': '42ms' }">
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div class="space-y-1.5">
            <p class="ui-kicker">{{ t("orderStatus.kicker") }}</p>
            <h1 class="ui-display text-2xl font-semibold text-white sm:text-3xl">
              {{ t("orderStatus.orderNumber", { number: orderData.order_number }) }}
            </h1>
            <div class="flex flex-wrap items-center gap-2 mt-1.5">
              <span class="ui-status-pill" :class="statusClass(orderData.status)">
                {{ statusLabel(orderData.status) }}
              </span>
              <ConnectionDot v-if="isLiveStatus" :state="realtimeState" show-label />
              <span v-if="orderData.fulfillment_type" class="ui-chip">{{ fulfillmentLabel(orderData) }}</span>
              <span v-if="orderData.can_cancel" class="ui-chip border-red-400/30 bg-red-500/8 text-red-300 text-[11px]">{{ t('orderStatus.cancelAvailable') }}</span>
            </div>
          </div>
          <div class="text-end space-y-1 shrink-0">
            <p class="text-2xl font-bold tabular-nums text-[var(--color-secondary)]">{{ formatCurrency(orderData.total, orderData.currency) }}</p>
            <p class="text-[10px] text-slate-500 tracking-wide">{{ t("orderStatus.items") }}: {{ orderData.items_count }}</p>
          </div>
        </div>
      </div>

      <!-- Table order banner -->
      <div
        v-if="orderData.fulfillment_type === 'table'"
        class="ui-reveal rounded-2xl border border-emerald-500/40 bg-emerald-500/12 p-5 text-center"
        :style="{ '--ui-delay': '56ms' }"
      >
        <p class="ui-kicker text-emerald-400">
          {{ t("orderStatus.tableOrderLabel") }}
        </p>
        <p class="mt-2 text-5xl font-bold text-white tracking-tight">
          {{ orderData.table_label || t("orderStatus.tableUnknown") }}
        </p>
        <p v-if="orderData.customer_name" class="mt-2 text-sm font-medium text-slate-300">
          {{ orderData.customer_name }}
        </p>
        <p class="mt-2 text-sm text-emerald-300/75">
          {{ t("orderStatus.tableOrderHint") }}
        </p>
      </div>

      <!-- Delivery address confirmation -->
      <div
        v-if="orderData.fulfillment_type === 'delivery' && orderData.delivery_address"
        class="ui-reveal rounded-2xl border border-slate-700/60 bg-slate-900/40 p-4 sm:p-5"
        :style="{ '--ui-delay': '56ms' }"
      >
        <p class="ui-kicker">
          {{ t("orderStatus.deliveryAddress") }}
        </p>
        <p class="mt-2 text-sm text-slate-200 leading-relaxed">{{ orderData.delivery_address }}</p>
        <a
          v-if="orderData.delivery_location_url &&
                (orderData.delivery_location_url.startsWith('http://') ||
                 orderData.delivery_location_url.startsWith('https://'))"
          :href="orderData.delivery_location_url"
          target="_blank"
          rel="noopener noreferrer"
          class="mt-2.5 inline-flex items-center gap-1.5 text-xs font-medium text-sky-400 hover:text-sky-300 transition-colors"
        >
          <AppIcon name="location" class="h-3.5 w-3.5" aria-hidden="true" />
          {{ t("orderStatus.openMap") }}
          <span class="sr-only">{{ t('common.opensInNewTab') }}</span>
        </a>
      </div>

      <!-- Live driver tracking (driver card + call + map) -->
      <DeliveryTracker v-if="orderData.delivery" :delivery="orderData.delivery" />
      <!-- Self-delivery (restaurant delivers itself — no platform driver to track) -->
      <div
        v-else-if="orderData.fulfillment_type === 'delivery' && orderData.status === 'out_for_delivery'"
        class="ui-reveal rounded-2xl border border-slate-700/60 bg-slate-900/40 p-4"
        :style="{ '--ui-delay': '56ms' }"
      >
        <div class="flex items-center gap-2.5 text-sm text-slate-300">
          <AppIcon name="location" class="h-4 w-4 shrink-0 text-slate-400" aria-hidden="true" />
          {{ t("orderStatus.selfDelivery") }}
        </div>
      </div>

      <!-- Status timeline -->
      <div class="ui-journey-rail ui-reveal p-4 sm:p-5" :style="{ '--ui-delay': '70ms' }">
        <ol class="flex items-center justify-between gap-1">
          <li
            v-for="(step, idx) in statusSteps"
            :key="step.value"
            class="flex flex-1 flex-col items-center gap-1.5"
          >
            <!-- step circle with optional pulse ring on the active step -->
            <div class="relative flex items-center justify-center">
              <div
                v-if="idx === currentStepIndex && currentStepIndex >= 0 && orderData.status !== 'completed'"
                class="absolute -inset-1.5 motion-safe:animate-ping rounded-full border border-[var(--color-secondary)]/35"
                aria-hidden="true"
              />
              <div
                class="relative flex h-9 w-9 items-center justify-center rounded-full border-2 text-xs font-bold transition-all duration-500"
                :class="stepClass(step.value)"
                :aria-current="idx === currentStepIndex ? 'step' : undefined"
              >
                <span v-if="isStepDone(step.value) && idx !== currentStepIndex">✓</span>
                <span v-else-if="idx === currentStepIndex">
                  <!-- pulsing dot for current step -->
                  <span class="block h-2.5 w-2.5 rounded-full bg-current motion-safe:animate-pulse" aria-hidden="true" />
                  <span class="sr-only">{{ step.label }}</span>
                </span>
                <span v-else>{{ idx + 1 }}</span>
              </div>
            </div>
            <p class="text-center text-[10px] leading-tight text-slate-400 sm:text-xs">{{ step.label }}</p>
            <!-- Timestamp under reached steps (task 5) -->
            <p
              v-if="stepTimestamp(step.value, idx)"
              class="text-center text-[9px] leading-none tabular-nums text-slate-600"
              :aria-label="stepTimestamp(step.value, idx) || ''"
            >{{ stepTimestamp(step.value, idx) }}</p>
          </li>
        </ol>
        <!-- Progress bar -->
        <div
          class="mt-4 ui-journey-progress"
          role="progressbar"
          :aria-valuenow="progressPercent"
          aria-valuemin="0"
          aria-valuemax="100"
          :aria-label="statusLabel(orderData?.status)"
          :aria-valuetext="statusLabel(orderData?.status)"
        >
          <span
            class="absolute inset-y-0 start-0 rounded-full transition-all duration-500"
            :style="{ width: `${progressPercent}%` }"
          />
        </div>
      </div>

      <!-- Status context hint (pending / confirmed / preparing) -->
      <p
        v-if="statusHint"
        class="ui-reveal text-center text-sm text-slate-400 leading-relaxed px-1"
        :style="{ '--ui-delay': '84ms' }"
        role="status"
      >{{ statusHint }}</p>

      <!-- Contact restaurant escape hatch — shown any time order is active and phone is known -->
      <div
        v-if="!['completed','cancelled'].includes(orderData.status) && orderData.tenant_phone"
        class="ui-reveal flex justify-center"
        :style="{ '--ui-delay': '92ms' }"
      >
        <a
          :href="`tel:${orderData.tenant_phone}`"
          class="inline-flex items-center gap-2 rounded-full border border-slate-700 bg-slate-800/60 px-4 py-2 text-xs font-medium text-slate-300 transition hover:border-slate-600 hover:bg-slate-800 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/50"
          :aria-label="`${t('orderStatus.contactRestaurant')}: ${orderData.tenant_phone}`"
        >
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" class="h-3.5 w-3.5 shrink-0" aria-hidden="true"><path d="M2.3 2.3c.3-.3.8-.3 1.1 0l2 2c.3.3.3.8 0 1.1L4.2 6.6A9.5 9.5 0 0 0 9.4 11.8l1.2-1.2c.3-.3.8-.3 1.1 0l2 2c.3.3.3.8 0 1.1l-1 1c-1.2 1.2-6-1.2-8.4-3.6C2 8.7-.5 3.8.7 2.5l1-.3.6.1Z"/></svg>
          {{ t('orderStatus.contactRestaurant') }}
        </a>
      </div>

      <!-- Restaurant message -->
      <div
        v-if="orderData.owner_note || orderData.estimated_ready_minutes"
        class="ui-panel ui-reveal border-emerald-500/30 bg-emerald-500/5 p-4 sm:p-5 space-y-2"
        :style="{ '--ui-delay': '84ms' }"
      >
        <!-- ETA countdown ring + text -->
        <div v-if="orderData.estimated_ready_minutes" class="flex items-center gap-3">
          <!-- SVG ring: stroke-dashoffset encodes time-left visually -->
          <svg
            v-if="countdownSeconds !== null"
            viewBox="0 0 40 40"
            class="h-10 w-10 shrink-0 -rotate-90"
            aria-hidden="true"
          >
            <!-- track -->
            <circle cx="20" cy="20" r="16" fill="none" stroke="currentColor" stroke-width="3" class="text-emerald-900/60" />
            <!-- progress arc — dasharray = circumference ≈ 100.53, dashoffset = remaining fraction -->
            <circle
              cx="20" cy="20" r="16" fill="none"
              stroke="currentColor" stroke-width="3"
              stroke-linecap="round"
              class="text-emerald-400 transition-all duration-1000"
              :style="{
                strokeDasharray: '100.53',
                strokeDashoffset: etaRingOffset,
              }"
            />
          </svg>
          <p class="text-sm font-semibold text-emerald-200">
            <template v-if="countdownSeconds !== null && countdownSeconds > 0">
              ⏱ {{ t("orderStatus.estimatedReady", { minutes: Math.ceil(countdownSeconds / 60) }) }}
              <span class="ms-1 font-mono text-xs font-normal text-emerald-300/70 tabular-nums">
                ({{ Math.floor(countdownSeconds / 60) }}:{{ String(countdownSeconds % 60).padStart(2, "0") }})
              </span>
            </template>
            <template v-else-if="countdownSeconds !== null && countdownSeconds <= 0">
              ⏱ {{ t("orderStatus.readyAnyMoment") }}
            </template>
            <template v-else>
              ⏱ {{ t("orderStatus.estimatedReady", { minutes: orderData.estimated_ready_minutes }) }}
            </template>
          </p>
        </div>
        <p v-if="orderData.owner_note" class="text-sm text-slate-200 leading-relaxed">
          <span class="ui-kicker block mb-1">{{ t("orderStatus.ownerNote") }}</span>
          {{ orderData.owner_note }}
        </p>
      </div>

      <!-- Items -->
      <div class="ui-panel ui-reveal p-4 sm:p-5 space-y-3" :style="{ '--ui-delay': '98ms' }">
        <h2 class="ui-kicker">{{ t("orderStatus.items") }}</h2>
        <div
          v-for="(item, idx) in orderData.items"
          :key="item.dish_name + item.note"
          class="ui-reveal flex items-start justify-between gap-3 rounded-xl border border-slate-800/70 bg-slate-950/40 px-3 py-2.5 text-sm transition-colors hover:border-slate-700/60"
          :class="item.is_voided ? 'opacity-60' : ''"
          :style="{ '--ui-delay': `${Math.min(idx, 9) * 20}ms` }"
        >
          <div class="flex items-start gap-2.5 min-w-0">
            <span
              class="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-slate-700 bg-slate-800/60 text-[10px] font-bold tabular-nums"
              :class="item.is_voided ? 'text-slate-500' : 'text-slate-300'"
              :aria-label="`${item.qty}x`"
            >{{ item.qty }}</span>
            <div class="min-w-0 space-y-0.5">
              <p class="truncate" :class="item.is_voided ? 'line-through text-slate-500' : 'font-semibold text-slate-100'" :title="item.dish_name">
                {{ item.dish_name }}
                <span
                  v-if="item.is_voided"
                  class="ms-1 rounded-full border border-red-500/30 bg-red-500/10 px-1.5 py-0.5 text-[9px] font-semibold text-red-400 leading-none"
                  style="text-decoration:none"
                >{{ t('waiterPage.voidedBadge') }}</span>
              </p>
              <p v-if="item.options?.length" class="text-xs text-slate-400">
                {{ item.options.map(o => o.name).join(" · ") }}
              </p>
              <p v-if="item.note" class="text-xs italic text-slate-500">{{ item.note }}</p>
            </div>
          </div>
          <p class="shrink-0 font-semibold tabular-nums" :class="item.is_voided ? 'line-through text-slate-500' : 'text-[var(--color-secondary)]'">{{ formatCurrency(item.subtotal, orderData.currency) }}</p>
        </div>

        <!-- Delivery fee breakdown — only shown for delivery orders with a fee -->
        <template v-if="orderData.fulfillment_type === 'delivery' && Number(orderData.delivery_fee) > 0">
          <div class="flex justify-between border-t border-slate-800 pt-3 text-sm text-slate-400">
            <span>{{ t("orderStatus.subtotal") }}</span>
            <span>{{ formatCurrency(Number(orderData.total) - Number(orderData.delivery_fee), orderData.currency) }}</span>
          </div>
          <div class="flex justify-between text-sm text-slate-400">
            <span>{{ t("orderStatus.deliveryFee") }}</span>
            <span>{{ formatCurrency(orderData.delivery_fee, orderData.currency) }}</span>
          </div>
          <div v-if="Number(orderData.vat_amount) > 0" class="flex justify-between text-sm text-slate-400">
            <span>{{ t("orderStatus.vatIncluded", { label: orderData.vat_label, rate: Number(orderData.vat_rate) }) }}</span>
            <span>{{ formatCurrency(orderData.vat_amount, orderData.currency) }}</span>
          </div>
          <div class="flex justify-between border-t border-slate-700 pt-2.5">
            <span class="text-sm font-semibold text-slate-300">{{ t("orderStatus.total") }}</span>
            <span class="text-base font-bold text-white">{{ formatCurrency(orderData.total, orderData.currency) }}</span>
          </div>
        </template>
        <template v-else>
          <div v-if="Number(orderData.vat_amount) > 0" class="flex justify-between border-t border-slate-800 pt-3 text-sm text-slate-400">
            <span>{{ t("orderStatus.vatIncluded", { label: orderData.vat_label, rate: Number(orderData.vat_rate) }) }}</span>
            <span>{{ formatCurrency(orderData.vat_amount, orderData.currency) }}</span>
          </div>
          <div class="flex justify-between border-slate-800 pt-3" :class="{ 'border-t': !(Number(orderData.vat_amount) > 0) }">
            <span class="text-sm font-semibold text-slate-300">{{ t("orderStatus.total") }}</span>
            <span class="text-base font-bold text-white">{{ formatCurrency(orderData.total, orderData.currency) }}</span>
          </div>
        </template>
        <!-- Loyalty discount applied -->
        <div
          v-if="Number(orderData.loyalty_discount) > 0"
          class="flex items-center justify-between rounded-xl border border-amber-500/30 bg-amber-500/8 px-3 py-2 text-xs"
        >
          <span class="text-amber-300">{{ t('orderStatus.loyaltyDiscount') }}</span>
          <span class="font-semibold text-amber-200">−{{ formatCurrency(orderData.loyalty_discount, orderData.currency) }}</span>
        </div>
        <!-- Wallet credits applied -->
        <div
          v-if="Number(orderData.wallet_amount_paid) > 0"
          class="flex items-center justify-between rounded-xl border border-emerald-500/30 bg-emerald-500/8 px-3 py-2 text-xs"
        >
          <span class="text-emerald-300">{{ t("orderStatus.walletPaid", { amount: formatCurrency(orderData.wallet_amount_paid) }) }}</span>
          <span class="font-semibold text-emerald-200">💰 {{ formatCurrency(orderData.wallet_amount_paid) }}</span>
        </div>

        <!-- Payment status — Paid, or what's expected (pay-now vs pay-at-table) -->
        <div
          v-if="orderData.status !== 'cancelled'"
          class="flex items-center justify-between rounded-xl border px-3 py-2 text-xs"
          :class="orderData.payment_status === 'paid'
            ? 'border-emerald-500/30 bg-emerald-500/8 text-emerald-300'
            : 'border-amber-500/30 bg-amber-500/8 text-amber-200'"
        >
          <span v-if="orderData.payment_status === 'paid'">{{ t('orderStatus.paid') }}</span>
          <span v-else-if="orderData.requires_prepayment">{{ t('orderStatus.paymentDue') }}</span>
          <span v-else>{{ t('orderStatus.payAtTable') }}</span>
          <span v-if="orderData.payment_status === 'paid'" class="font-semibold">✓</span>
        </div>

        <!-- Pay this open bill from wallet — only the signed-in order owner sees this -->
        <template v-if="orderData.can_pay_with_wallet">
          <button
            class="ui-btn-primary inline-flex w-full items-center justify-center gap-2 py-3 text-sm font-semibold disabled:opacity-50"
            :disabled="payingWallet"
            :aria-busy="payingWallet"
            @click="payWithWallet"
          >
            <svg v-if="payingWallet" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-4 w-4 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
            <AppIcon v-else name="wallet" class="h-4 w-4 shrink-0" aria-hidden="true" />
            {{ payingWallet ? t('orderStatus.payingWallet') : t('orderStatus.payWithWallet', { amount: formatCurrency(orderData.amount_due, orderData.currency) }) }}
          </button>
          <p class="text-center text-[11px] text-slate-500">
            {{ t('orderStatus.walletBalanceLine', { balance: formatCurrency(orderData.wallet_balance, orderData.currency) }) }}
          </p>
        </template>

        <!-- Dine-in: cash is always an option — the server settles it at the table -->
        <p
          v-if="orderData.fulfillment_type === 'table' && orderData.payment_status !== 'paid' && orderData.status !== 'cancelled'"
          class="flex items-center justify-center gap-1.5 text-center text-[11px] text-slate-500"
        >
          <AppIcon name="info" class="h-3 w-3 shrink-0" aria-hidden="true" />
          {{ t('orderStatus.payCashHint') }}
        </p>

        <!-- Self-cancel — early pickup/delivery orders, signed-in owner only (server-gated) -->
        <template v-if="orderData.can_cancel">
          <Transition name="ui-fade" mode="out-in">
            <div v-if="!cancelConfirming" key="init">
              <button
                class="ui-btn-outline w-full justify-center py-2.5 text-sm font-semibold border-red-400/30 text-red-300 hover:border-red-400/60 hover:text-red-200 disabled:opacity-50"
                :disabled="cancelling"
                @click="cancelConfirming = true"
              >
                {{ t('orderStatus.cancelOrder') }}
              </button>
            </div>
            <div
              v-else
              key="confirm"
              class="space-y-3 rounded-2xl border border-rose-500/25 bg-rose-500/8 p-4"
            >
              <div class="flex items-start gap-3">
                <svg class="mt-0.5 h-5 w-5 shrink-0 text-rose-400" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                  <path fill-rule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/>
                </svg>
                <div class="space-y-0.5">
                  <p class="text-sm font-semibold text-rose-100">{{ t('orderStatus.cancelConfirm') }}</p>
                  <p class="text-xs leading-relaxed text-rose-200/75">{{ t('orderStatus.cancelConfirmBody') }}</p>
                </div>
              </div>
              <div class="flex gap-2.5">
                <button
                  class="ui-btn-primary inline-flex flex-1 items-center justify-center gap-2 py-2.5 text-sm"
                  style="--color-secondary: #f43f5e; --color-secondary-rgb: 244,63,94"
                  :disabled="cancelling"
                  :aria-busy="cancelling"
                  @click="cancelOrder"
                >
                  <svg v-if="cancelling" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
                  <span aria-live="polite" aria-atomic="true">
                    {{ cancelling ? t('orderStatus.cancelling') : t('orderStatus.cancelConfirmYes') }}
                  </span>
                </button>
                <button
                  class="ui-btn-outline px-4 py-2.5 text-sm"
                  :disabled="cancelling"
                  @click="cancelConfirming = false"
                >{{ t('common.back') }}</button>
              </div>
            </div>
          </Transition>
          <p class="text-center text-[11px] text-slate-500">{{ t('orderStatus.cancelHint') }}</p>
        </template>
      </div>

      <!-- Loyalty points earned — celebration (completed) or pending (in-progress) -->
      <div
        v-if="Number(orderData.points_earned) > 0"
        class="ui-panel ui-reveal flex items-center justify-between p-4"
        :class="orderData.status === 'completed'
          ? 'border-violet-500/25 bg-violet-500/8'
          : 'border-slate-700/60 bg-slate-900/40'"
        :style="{ '--ui-delay': '100ms' }"
      >
        <div class="flex items-center gap-2.5">
          <div
            class="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border"
            :class="orderData.status === 'completed' ? 'border-violet-500/25 bg-violet-500/12' : 'border-slate-700/50 bg-slate-800/60'"
          >
            <svg viewBox="0 0 16 16" fill="currentColor" class="h-4 w-4" :class="orderData.status === 'completed' ? 'text-violet-400' : 'text-slate-400'" aria-hidden="true">
              <path d="M8 1.25 9.618 4.528l3.617.526-2.617 2.551.618 3.602L8 9.47l-3.236 1.737.618-3.602-2.617-2.551 3.617-.526z"/>
            </svg>
          </div>
          <div>
            <p class="text-sm font-semibold" :class="orderData.status === 'completed' ? 'text-violet-200' : 'text-slate-300'">
              {{ orderData.status === 'completed' ? t('orderStatus.pointsEarned') : t('orderStatus.pointsPending') }}
            </p>
            <p class="mt-0.5 text-[11px]" :class="orderData.status === 'completed' ? 'text-violet-300/60' : 'text-slate-500'">
              {{ orderData.status === 'completed' ? t('orderStatus.pointsEarnedHint') : t('orderStatus.pointsPendingHint') }}
            </p>
          </div>
        </div>
        <span class="text-base font-bold tabular-nums" :class="orderData.status === 'completed' ? 'text-violet-200' : 'text-slate-400'">
          +{{ orderData.points_earned }}
        </span>
      </div>

      <!-- Receipt message (thank-you note from the restaurant owner) -->
      <div
        v-if="orderData.receipt_message && ['confirmed', 'ready', 'completed'].includes(orderData.status)"
        class="ui-panel ui-reveal p-4 sm:p-5 space-y-2 border-[var(--color-secondary)]/25 bg-[var(--color-secondary)]/5"
        :style="{ '--ui-delay': '112ms' }"
      >
        <p class="ui-kicker text-[var(--color-secondary)]/70">
          {{ t("orderStatus.receiptMessage") }}
        </p>
        <p class="text-sm text-slate-200 leading-relaxed">{{ orderData.receipt_message }}</p>
      </div>

      <!-- Rating prompt (completed, not yet rated) -->
      <div
        v-if="orderData.status === 'completed' && !orderData.has_rating"
        class="ui-panel ui-reveal p-4 sm:p-5 space-y-4"
        :style="{ '--ui-delay': '126ms' }"
      >
        <div class="space-y-1">
          <p class="text-sm font-semibold text-slate-200">{{ t("orderStatus.rateTitle") }}</p>
          <p class="text-xs text-slate-400">{{ t("orderStatus.rateSubtitle") }}</p>
        </div>
        <!-- Star picker -->
        <div class="flex gap-2" role="radiogroup" :aria-label="t('orderStatus.rateTitle')">
          <button
            v-for="star in 5"
            :key="star"
            type="button"
            role="radio"
            class="ui-touch-target ui-press flex items-center justify-center text-3xl leading-none transition-transform hover:scale-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/60 focus-visible:rounded-lg"
            :aria-label="t('orderStatus.ratingLabel', { score: star })"
            :aria-checked="star <= ratingScore"
            @click="ratingScore = star"
          >
            <span :class="star <= ratingScore ? 'text-amber-400' : 'text-slate-700'">★</span>
          </button>
        </div>
        <!-- Comment -->
        <textarea
          v-model="ratingComment"
          rows="2"
          :aria-label="t('orderStatus.commentPlaceholder')"
          :placeholder="t('orderStatus.commentPlaceholder')"
          class="ui-textarea w-full resize-none"
        />
        <button
          :disabled="ratingScore === 0 || ratingSubmitting"
          :aria-busy="ratingSubmitting"
          class="ui-btn-primary inline-flex items-center gap-2 px-5 py-2.5 text-sm disabled:opacity-40"
          @click="submitRating"
        >
          <svg v-if="ratingSubmitting" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-4 w-4 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
          {{ ratingSubmitting ? t("orderStatus.rateSubmitting") : t("orderStatus.rateSubmit") }}
        </button>
      </div>

      <!-- Already rated — confirmation + owner reply (if any) -->
      <div
        v-else-if="orderData.status === 'completed' && orderData.has_rating"
        class="ui-panel ui-reveal p-4 space-y-3"
        :style="{ '--ui-delay': '126ms' }"
      >
        <!-- Submitted confirmation row -->
        <div class="flex items-center gap-2.5 text-sm font-medium text-emerald-300">
          <AppIcon name="check" class="h-4 w-4 shrink-0" />
          {{ t("orderStatus.rateSubmitted") }}
        </div>
        <!-- Owner reply block (shown only when the restaurant has replied) -->
        <div
          v-if="orderData.rating?.owner_reply"
          class="rounded-xl border border-[var(--color-secondary)]/20 bg-[var(--color-secondary)]/5 p-3.5 space-y-1.5"
        >
          <p class="text-[11px] font-semibold uppercase tracking-wide text-[var(--color-secondary)]/70">{{ t("orderStatus.ownerReplyTitle") }}</p>
          <p class="text-sm leading-relaxed text-slate-200">{{ orderData.rating.owner_reply }}</p>
          <p v-if="orderData.rating.owner_reply_at" class="text-[11px] text-slate-500">
            {{ t("orderStatus.ownerReplyPostedAt", { date: formatReplyDate(orderData.rating.owner_reply_at) }) }}
          </p>
        </div>
      </div>

      <!-- The restaurant's feedback about this order — shown only to the signed-in
           customer who owns the order (the backend gates this to the order owner). -->
      <div
        v-if="orderData.restaurant_feedback"
        class="ui-panel ui-reveal p-4 sm:p-5 space-y-2"
        :style="{ '--ui-delay': '140ms' }"
      >
        <p class="ui-kicker">{{ t("orderStatus.restaurantFeedbackTitle") }}</p>
        <div class="flex items-center gap-2.5">
          <span class="text-2xl text-amber-400">{{ "★".repeat(orderData.restaurant_feedback.score) }}<span class="text-slate-700">{{ "★".repeat(5 - orderData.restaurant_feedback.score) }}</span></span>
          <span class="text-sm font-semibold text-slate-200">{{ orderData.restaurant_feedback.score }}/5</span>
        </div>
        <p v-if="orderData.restaurant_feedback.note" class="text-sm text-slate-400 italic leading-relaxed">{{ orderData.restaurant_feedback.note }}</p>
      </div>

      <!-- Sign-in nudge for anonymous table orders -->
      <div
        v-if="orderData.fulfillment_type === 'table' && !customerStore.isAuthenticated"
        class="ui-panel ui-reveal p-4 sm:p-5 space-y-3"
        :style="{ '--ui-delay': '154ms' }"
      >
        <div class="space-y-1">
          <p class="text-sm font-semibold text-slate-100">{{ t("orderStatus.tableSignInNudgeTitle") }}</p>
          <p class="text-xs text-slate-400">{{ t("orderStatus.tableSignInNudgeBody") }}</p>
        </div>
        <button class="ui-btn-primary inline-flex w-full justify-center py-2.5 text-sm" @click="showAuthModal = true">
          <AppIcon name="user" class="h-3.5 w-3.5" aria-hidden="true" />
          {{ t("orderStatus.tableSignInNudgeButton") }}
        </button>
      </div>

      <!-- Re-order + navigation -->
      <div class="flex flex-wrap items-center justify-between gap-3 px-1">
        <span v-if="isLiveStatus" class="text-xs text-slate-500">
          {{ t("orderStatus.autoRefresh", { seconds: POLL_INTERVAL_S }) }}
        </span>
        <div class="flex flex-wrap gap-2 ms-auto">
          <button
            v-if="orderData.status === 'completed'"
            class="ui-btn-outline inline-flex items-center gap-1.5 px-4 py-2 text-sm print:hidden"
            @click="printReceipt"
          >
            <AppIcon name="print" class="h-4 w-4" aria-hidden="true" />
            {{ t("orderStatus.printReceipt") }}
          </button>
          <button
            v-if="orderData.items?.some(i => i.dish_slug)"
            class="ui-btn-primary inline-flex px-5 py-2.5 text-sm"
            @click="reorder"
          >
            {{ t("orderStatus.reorder") }}
          </button>
          <RouterLink :to="{ name: 'menu' }" class="ui-btn-outline inline-flex px-4 py-2 text-sm">
            {{ t("orderStatus.backToMenu") }}
          </RouterLink>
        </div>
      </div>
    </template>
  </div>

  <CustomerAuthModal
    v-if="showAuthModal"
    @close="showAuthModal = false"
    @authenticated="showAuthModal = false"
  />

  <!-- Push-permission priming soft-ask (self-gated; triggered post-checkout) -->
  <PushPrimingSheet ref="pushPrimingSheet" />
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import AppIcon from "../components/AppIcon.vue";
import ConnectionDot from "../components/ConnectionDot.vue";
import CustomerAuthModal from "../components/CustomerAuthModal.vue";
import DeliveryTracker from "../components/DeliveryTracker.vue";
import PushPrimingSheet from "../components/PushPrimingSheet.vue";
import { useI18n } from "../composables/useI18n";
import { useOrderRealtime } from "../composables/useOrderRealtime";
import { useReorder } from "../composables/useReorder";
import { useCustomerStore } from "../stores/customer";
import { useOrderStore } from "../stores/order";
import { useToastStore } from "../stores/toast";
import api from "../lib/api";

const props = defineProps({
  orderNumber: { type: String, required: true },
});

const router = useRouter();
const customerStore = useCustomerStore();
const orderStore = useOrderStore();
const toast = useToastStore();
const { t, formatPrice, formatDateTime, currentLocale } = useI18n();
const { reorderFromOrder } = useReorder();

const showAuthModal = ref(false);
// Push-permission priming soft-ask — triggered post-checkout (high-intent moment).
const pushPrimingSheet = ref(null);

// ── Just-placed celebration banner ────────────────────────────────────────────
const showJustPlacedBanner = ref(false);
let _justPlacedTimer = null;

const POLL_INTERVAL_S = 15;
const orderData = ref(null);
const loading = ref(false);
const notFound = ref(false);
const pollFailures = ref(0);  // consecutive refresh failures → warn the user
const readyAlertShown = ref(false);

// ── Owner reply date format ───────────────────────────────────────────────────
const formatReplyDate = (iso) => {
  if (!iso) return "";
  try {
    return new Intl.DateTimeFormat(currentLocale.value, { dateStyle: "medium" }).format(new Date(iso));
  } catch {
    return iso;
  }
};

// ── Delivery-code copy ────────────────────────────────────────────────────────
const codeCopied = ref(false);
let _codeCopiedTimer = null;
const copyDeliveryCode = (code) => {
  if (!code) return;
  navigator.clipboard.writeText(String(code)).then(() => {
    codeCopied.value = true;
    clearTimeout(_codeCopiedTimer);
    _codeCopiedTimer = setTimeout(() => { codeCopied.value = false; }, 2000);
  }).catch(() => {
    toast.show(t('orderStatus.codeCopyFailed'), 'error');
  });
};

// ── Rating ────────────────────────────────────────────────────────────────────
const ratingScore = ref(0);
const ratingComment = ref("");
const ratingSubmitting = ref(false);

const submitRating = async () => {
  if (ratingScore.value === 0 || ratingSubmitting.value) return;
  ratingSubmitting.value = true;
  try {
    await api.post(`/orders/${props.orderNumber}/rate/`, {
      score: ratingScore.value,
      comment: ratingComment.value.trim(),
    });
    toast.show(t("orderStatus.rateSubmitted"), "success");
    // Refresh so has_rating flips to true and the prompt hides
    await fetchStatus();
  } catch {
    toast.show(t("orderStatus.rateError"), "error");
  } finally {
    ratingSubmitting.value = false;
  }
};

const isLiveStatus = computed(() =>
  orderData.value && !["completed", "cancelled"].includes(orderData.value.status)
);

// ── Countdown timer ───────────────────────────────────────────────────────────
const countdownSeconds = ref(null);
let countdownTimer = null;

const updateCountdown = () => {
  const d = orderData.value;
  if (!d?.estimated_ready_minutes || !d?.created_at || !isLiveStatus.value) {
    countdownSeconds.value = null;
    return;
  }
  const readyAt = new Date(d.created_at).getTime() + d.estimated_ready_minutes * 60_000;
  countdownSeconds.value = Math.floor((readyAt - Date.now()) / 1000);
};

const startCountdown = () => {
  clearInterval(countdownTimer);
  updateCountdown();
  countdownTimer = setInterval(updateCountdown, 1000);
};

const stopCountdown = () => {
  clearInterval(countdownTimer);
  countdownTimer = null;
  countdownSeconds.value = null;
};

// ── Re-order ──────────────────────────────────────────────────────────────────
// Unified, availability-safe path (useReorder): re-resolves each line against the
// live menu (drops sold-out items, refreshes prices, drops stale options) and
// restores fulfillment context — identical to the Menu.vue reorder.
const printReceipt = () => window.print();

const reorder = async () => {
  if (!orderData.value?.items?.length) return;
  const result = await reorderFromOrder(orderData.value);
  // Only navigate to the cart if at least one line made it in.
  if (result.added > 0) {
    router.push({ name: "cart" });
  }
};

// The visible flow differs by fulfillment type: pickup ends at "Picked up",
// dine-in adds a final "To pay" step, delivery adds "Out for delivery → Delivered".
const statusSteps = computed(() => {
  const ft = orderData.value?.fulfillment_type;
  const base = [
    { value: "pending", label: t("orderStatus.statusPending") },
    { value: "confirmed", label: t("orderStatus.statusConfirmed") },
    { value: "preparing", label: t("orderStatus.statusPreparing") },
  ];
  if (ft === "delivery") {
    return [
      ...base,
      { value: "ready", label: t("orderStatus.stepReadyDispatch") },
      { value: "out_for_delivery", label: t("orderStatus.stepOutForDelivery") },
      { value: "completed", label: t("orderStatus.stepDelivered") },
    ];
  }
  if (ft === "table") {
    return [
      ...base,
      { value: "ready", label: t("orderStatus.stepServed") },
      { value: "pay", label: t("orderStatus.stepToPay") },
      { value: "completed", label: t("orderStatus.stepPaidClosed") },
    ];
  }
  return [
    ...base,
    { value: "ready", label: t("orderStatus.stepReadyPickup") },
    { value: "completed", label: t("orderStatus.stepPickedUp") },
  ];
});

const currentStepIndex = computed(() => {
  const d = orderData.value;
  if (!d || d.status === "cancelled") return -1;
  const steps = statusSteps.value;
  // Dine-in: once served and still unpaid, the active step is "To pay".
  if (d.fulfillment_type === "table" && d.status === "ready" && d.payment_status !== "paid") {
    return steps.findIndex((st) => st.value === "pay");
  }
  return steps.findIndex((st) => st.value === d.status);
});

const progressPercent = computed(() => {
  const steps = statusSteps.value;
  if (currentStepIndex.value < 0 || !steps.length) return 0;
  return Math.round(((currentStepIndex.value + 1) / steps.length) * 100);
});

const statusHint = computed(() => {
  const s = orderData.value?.status;
  if (s === 'pending') return t('orderStatus.hintPending');
  if (s === 'confirmed') return t('orderStatus.hintConfirmed');
  if (s === 'preparing') return t('orderStatus.hintPreparing');
  if (s === 'out_for_delivery') return t('orderStatus.hintOutForDelivery');
  return null;
});

// ETA ring: stroke-dashoffset for a circle with r=16 (circumference ≈ 100.53).
// Offset=0 → full ring (all time left); offset=100.53 → empty (no time left).
const etaRingOffset = computed(() => {
  const d = orderData.value;
  if (!d?.estimated_ready_minutes || countdownSeconds.value == null) return 0;
  const totalSecs = d.estimated_ready_minutes * 60;
  if (totalSecs <= 0) return 100.53;
  const remaining = Math.max(0, countdownSeconds.value);
  return Math.round((1 - remaining / totalSecs) * 100.53 * 100) / 100;
});

const isStepDone = (stepValue) => {
  const idx = statusSteps.value.findIndex((st) => st.value === stepValue);
  return idx >= 0 && idx <= currentStepIndex.value;
};

// ── Step timestamps (task 5) ──────────────────────────────────────────────────
const _fmtStepTime = (iso) => {
  if (!iso) return null;
  try {
    return new Intl.DateTimeFormat(currentLocale.value, {
      hour: "2-digit", minute: "2-digit",
    }).format(new Date(iso));
  } catch {
    return null;
  }
};

const stepTimestamp = (stepValue, idx) => {
  const d = orderData.value;
  if (!d) return null;
  const curr = currentStepIndex.value;
  // Only show for steps that have been reached (idx <= curr)
  if (idx < 0 || idx > curr) return null;

  // First step (pending) → created_at with t('orderFlow.placedAt') prefix
  if (idx === 0) {
    const ts = _fmtStepTime(d.created_at);
    return ts ? `${t("orderFlow.placedAt")} ${ts}` : null;
  }
  // Current active step → status_updated_at with t('orderFlow.updatedAt') prefix
  if (idx === curr) {
    // If we also have paid_at and this is a terminal paid step, prefer that
    if (d.paid_at) {
      const ts = _fmtStepTime(d.paid_at);
      if (ts) return `${t("orderFlow.paidAt")} ${ts}`;
    }
    const ts = _fmtStepTime(d.status_updated_at);
    return ts ? `${t("orderFlow.updatedAt")} ${ts}` : null;
  }
  // Intermediate done steps — no timestamp (keeps it clean)
  return null;
};

const stepClass = (stepValue) => {
  const idx = statusSteps.value.findIndex((st) => st.value === stepValue);
  const curr = currentStepIndex.value;
  if (idx < curr) return "border-[var(--color-secondary)] bg-[var(--color-secondary)] text-black";
  if (idx === curr) return "border-[var(--color-secondary)] bg-[var(--color-secondary)]/20 text-[var(--color-secondary)]";
  return "border-slate-700 bg-slate-900 text-slate-600";
};

const statusClass = (s) => ({
  scheduled: "bg-violet-500/20 text-violet-200 border border-violet-500/30",
  pending: "bg-amber-500/20 text-amber-200 border border-amber-500/30",
  confirmed: "bg-sky-500/20 text-sky-200 border border-sky-500/30",
  preparing: "bg-orange-500/20 text-orange-200 border border-orange-500/30",
  ready: "bg-emerald-500/20 text-emerald-200 border border-emerald-500/30",
  out_for_delivery: "bg-indigo-500/20 text-indigo-200 border border-indigo-500/30",
  completed: "bg-slate-700 text-slate-300",
  cancelled: "bg-red-500/20 text-red-300 border border-red-500/30",
}[s] || "bg-slate-700 text-slate-300");

const statusLabel = (s) => ({
  scheduled: t("orderStatus.statusScheduled"),
  pending: t("orderStatus.statusPending"),
  confirmed: t("orderStatus.statusConfirmed"),
  preparing: t("orderStatus.statusPreparing"),
  ready: t("orderStatus.statusReady"),
  out_for_delivery: t("orderStatus.stepOutForDelivery"),
  completed: t("orderStatus.statusCompleted"),
  cancelled: t("orderStatus.statusCancelled"),
}[s] || s);

const formatScheduledFor = (iso) => {
  if (!iso) return "";
  try {
    return formatDateTime(iso, { weekday: "short", dateStyle: undefined, timeStyle: undefined, day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
  } catch {
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? "" : d.toLocaleString();
  }
};

const fulfillmentLabel = (o) => {
  if (o.fulfillment_type === "table") return t("orderStatus.fulfillmentTable", { table: o.table_label || "?" });
  if (o.fulfillment_type === "delivery") return t("orderStatus.fulfillmentDelivery");
  if (o.fulfillment_type === "pickup") return t("orderStatus.fulfillmentPickup");
  return "";
};

const formatCurrency = (amount, currency) => {
  if (!currency) return formatPrice(amount);
  try {
    return new Intl.NumberFormat(currentLocale.value, {
      style: 'currency',
      currency,
      maximumFractionDigits: 2,
    }).format(amount || 0);
  } catch {
    return formatPrice(amount);
  }
};

// ── Order-ready alert ──────────────────────────────────────────────────────────

const playReadyChime = () => {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const notes = [523.25, 659.25, 783.99]; // C5, E5, G5
    notes.forEach((freq, i) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.type = "sine";
      osc.frequency.value = freq;
      const start = ctx.currentTime + i * 0.18;
      gain.gain.setValueAtTime(0, start);
      gain.gain.linearRampToValueAtTime(0.28, start + 0.04);
      gain.gain.exponentialRampToValueAtTime(0.001, start + 0.52);
      osc.start(start);
      osc.stop(start + 0.55);
    });
  } catch {
    // AudioContext blocked or unavailable — silent fallback
  }
};

const sendReadyBrowserNotification = () => {
  try {
    if (typeof Notification === "undefined" || Notification.permission !== "granted") return;
    const n = new Notification(t("orderStatus.readyNotifTitle"), {
      body: t("orderStatus.readyNotifBody", { number: props.orderNumber }),
      tag: `order-ready-${props.orderNumber}`,
      renotify: false,
    });
    // Auto-close after 8 seconds
    setTimeout(() => n.close(), 8000);
  } catch {
    // Notification API unavailable
  }
};

const triggerReadyAlert = () => {
  if (readyAlertShown.value) return;
  readyAlertShown.value = true;
  playReadyChime();
  sendReadyBrowserNotification();
};

// Watch for status transitioning to "ready" during polling
watch(
  () => orderData.value?.status,
  (newStatus, oldStatus) => {
    if (newStatus === "ready" && oldStatus && oldStatus !== "ready") {
      triggerReadyAlert();
    }
  }
);

// Start/stop countdown whenever order data arrives or status changes
watch(
  () => [orderData.value?.estimated_ready_minutes, orderData.value?.created_at, isLiveStatus.value],
  () => {
    if (orderData.value?.estimated_ready_minutes && isLiveStatus.value) startCountdown();
    else stopCountdown();
  }
);

const fetchStatus = async () => {
  loading.value = true;
  try {
    const res = await api.get(`/order-status/${props.orderNumber}/`);
    const prev = orderData.value?.status;
    orderData.value = res.data;
    // If the order was already "ready" when the page first loaded, show alert too
    if (res.data?.status === "ready" && !prev) {
      triggerReadyAlert();
    }
    notFound.value = false;
    pollFailures.value = 0;  // reset consecutive-failure counter on success
  } catch (err) {
    if (err?.response?.status === 404) {
      notFound.value = true;
    } else {
      pollFailures.value++;  // track network / server errors so we can warn the user
    }
  } finally {
    loading.value = false;
  }
};

// Pay the open bill from the customer's wallet (e.g. settling a dine-in tab).
const payingWallet = ref(false);
const payWithWallet = async () => {
  if (payingWallet.value) return;
  payingWallet.value = true;
  try {
    await api.post(`/orders/${props.orderNumber}/pay-wallet/`);
    await fetchStatus(); // refresh → flips to Paid, hides the button
    toast.show(t("orderStatus.walletPaidOk"), "success");
  } catch (err) {
    const code = err?.response?.data?.code;
    toast.show(
      code === "insufficient" ? t("orderStatus.walletInsufficient") : t("orderStatus.walletPayError"),
      "error",
    );
  } finally {
    payingWallet.value = false;
  }
};

// Self-cancel an early pickup/delivery order (wallet auto-refunds server-side).
const cancelling = ref(false);
const cancelConfirming = ref(false);
const cancelOrder = async () => {
  if (cancelling.value) return;
  cancelling.value = true;
  try {
    await api.post(`/order-status/${props.orderNumber}/cancel/`);
    await fetchStatus(); // refresh → flips to Cancelled, hides the button
    toast.show(t("orderStatus.cancelledOk"), "success");
    cancelConfirming.value = false;
  } catch (err) {
    const code = err?.response?.data?.code;
    toast.show(
      code === "not_cancellable" ? t("orderStatus.cancelTooLate") : t("orderStatus.cancelFailed"),
      "error",
    );
    cancelConfirming.value = false;
  } finally {
    cancelling.value = false;
  }
};

let pollTimer = null;

const onStatusPageVisible = () => {
  if (typeof document !== "undefined" && document.visibilityState === "visible" && isLiveStatus.value) {
    updateCountdown(); // immediately re-sync the timer display before the fetch round-trip
    fetchStatus();
  }
};

// Live status push (guest per-order channel). On a "status" ping, refresh
// immediately; the poll below stays as the fallback when WS is unavailable.
const orderRealtime = useOrderRealtime(
  () => props.orderNumber,
  (event) => {
    if (event === "status") fetchStatus();
  }
);
// Live-connection state for the ConnectionDot indicator. 'live' = WS open;
// anything else (connecting/polling/idle) → amber "reconnecting" cue.
const { connectionState: realtimeState } = orderRealtime;

onMounted(() => {
  // Request notification permission proactively (non-blocking)
  if (typeof Notification !== "undefined" && Notification.permission === "default") {
    Notification.requestPermission().catch(() => {});
  }
  // Show celebration banner if arriving within 60s of placing this order
  try {
    const lastNum = localStorage.getItem('lastOrderNumber');
    const lastAt = parseInt(localStorage.getItem('lastOrderAt') || '0', 10);
    if (lastNum === props.orderNumber && (Date.now() - lastAt) < 60000) {
      showJustPlacedBanner.value = true;
      _justPlacedTimer = setTimeout(() => { showJustPlacedBanner.value = false; }, 5000);
      // High-intent moment: just placed this order → soft-ask for push permission.
      // The sheet self-gates (supported + permission==='default' + push enabled +
      // not recently dismissed) and only fires the real OS prompt on accept.
      pushPrimingSheet.value?.maybeShow?.();
    }
  } catch { /* storage unavailable */ }
  fetchStatus();
  orderRealtime.connect();
  if (typeof document !== "undefined") {
    document.addEventListener("visibilitychange", onStatusPageVisible);
  }
  pollTimer = setInterval(() => {
    if (typeof document !== "undefined" && document.visibilityState === "hidden") return;
    if (isLiveStatus.value) fetchStatus();
  }, POLL_INTERVAL_S * 1000);
});
onUnmounted(() => {
  if (_justPlacedTimer) clearTimeout(_justPlacedTimer);
  clearInterval(pollTimer);
  orderRealtime.disconnect();
  stopCountdown();
  orderStore.clearPlacedOrder();
  if (typeof document !== "undefined") {
    document.removeEventListener("visibilitychange", onStatusPageVisible);
  }
});
</script>
