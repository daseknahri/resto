<template>
  <div class="ui-shell">

    <!-- Screen-reader live region: announces status transitions only (not every poll cycle). -->
    <div
      v-if="liveStatus"
      role="status"
      aria-live="polite"
      aria-atomic="true"
      class="sr-only"
    >{{ t(`mktOrderStatus.${liveStatus}`) }}</div>

    <div class="mx-auto max-w-md space-y-4 px-4 py-6 pb-16 sm:py-8">
      <!-- Back -->
      <router-link to="/order" class="ui-top-link inline-flex items-center gap-1 text-xs">
        <svg aria-hidden="true" viewBox="0 0 16 16" class="h-3.5 w-3.5 rtl:scale-x-[-1]" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M10 12L6 8l4-4" />
        </svg>
        {{ t('mktOrderStatus.backToMarketplace') }}
      </router-link>

      <!-- Loading skeleton -->
      <div v-if="loading && !order" class="space-y-4 animate-pulse">
        <div class="space-y-2 text-center">
          <div class="mx-auto h-2.5 w-32 rounded bg-slate-700/60" />
          <div class="mx-auto h-5 w-48 rounded bg-slate-700/50" />
        </div>
        <!-- Status stepper skeleton -->
        <div class="ui-panel p-5">
          <div class="flex items-center justify-between gap-1">
            <div v-for="i in 4" :key="i" class="flex flex-1 flex-col items-center gap-1">
              <div class="h-8 w-8 rounded-full bg-slate-700/60" />
              <div class="h-2 w-10 rounded bg-slate-800/50" />
            </div>
          </div>
        </div>
        <!-- Summary card skeleton -->
        <div class="ui-panel space-y-3 p-5">
          <div v-for="i in 3" :key="i" class="flex justify-between">
            <div class="h-3 w-24 rounded bg-slate-700/60" />
            <div class="h-3 w-14 rounded bg-slate-800/50" />
          </div>
        </div>
      </div>

      <!-- Error -->
      <div
        v-else-if="fetchError && !order"
        role="alert"
        class="flex items-start gap-3 rounded-2xl border border-red-500/30 bg-red-500/8 px-4 py-3"
      >
        <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor">
          <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm-.75-9.25a.75.75 0 011.5 0v3.5a.75.75 0 01-1.5 0v-3.5zm.75 6a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd" />
        </svg>
        <p class="flex-1 text-sm text-red-300">{{ t('mktOrderStatus.loadError') }}</p>
        <button
          class="ui-press shrink-0 rounded-lg border border-red-500/40 px-3 py-1 text-xs font-semibold text-red-300 transition hover:bg-red-500/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400/50"
          @click="fetchStatus"
        >{{ t('common.retry') }}</button>
      </div>

      <template v-else-if="order">
        <!-- Just-placed celebration banner — auto-dismisses after 5 s -->
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
              <p class="text-sm font-bold text-emerald-200">{{ t('mktOrderStatus.justPlacedTitle') }}</p>
              <p class="mt-0.5 text-xs text-emerald-200/70">{{ t('mktOrderStatus.justPlacedSubtitle') }}</p>
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

        <!-- Header -->
        <header class="ui-hero-ribbon ui-reveal px-4 py-4 text-center">
          <p class="ui-kicker">{{ t('mktOrderStatus.restaurant', { name: order.restaurant_name }) }}</p>
          <h1 class="ui-display mt-1 text-xl text-white">{{ t('mktOrderStatus.title', { number: order.order_number }) }}</h1>
          <p class="mt-1 text-xs text-slate-400">{{ t('mktOrderStatus.trackingHint') }}</p>
        </header>

        <!-- Order-ready celebration banner -->
        <div
          v-if="order.status === 'ready'"
          class="ui-reveal relative overflow-hidden rounded-2xl border border-emerald-400/50 bg-emerald-500/12 p-5 text-center shadow-xl shadow-emerald-900/25"
          :style="{ '--ui-delay': '28ms' }"
          role="alert"
        >
          <div class="pointer-events-none absolute inset-0 rounded-2xl bg-[radial-gradient(ellipse_at_top,rgba(52,211,153,0.18),transparent_60%)]" />
          <div class="relative space-y-1.5">
            <p class="text-3xl" aria-hidden="true">🎉</p>
            <p class="text-xl font-bold text-emerald-200">{{ t('mktOrderStatus.ready') }}</p>
          </div>
        </div>

        <!-- Order-cancelled banner -->
        <div
          v-if="order.status === 'cancelled'"
          class="ui-reveal rounded-2xl border border-red-400/60 bg-red-500/15 p-5 text-center"
          :style="{ '--ui-delay': '28ms' }"
          role="alert"
        >
          <p class="text-lg font-bold text-red-200">{{ t('mktOrderStatus.cancelled') }}</p>
          <router-link
            to="/order"
            class="mt-3 inline-flex items-center gap-1.5 rounded-full border border-red-400/30 px-5 py-2 text-sm font-medium text-red-300 transition-colors hover:border-red-400/60 hover:text-red-200"
          >
            {{ t('mktOrderStatus.backToMarketplace') }}
          </router-link>
        </div>

        <!-- Proof-of-delivery code (give it to your driver) -->
        <div
          v-if="order.delivery_code"
          class="ui-reveal rounded-2xl border border-indigo-400/50 bg-indigo-500/12 p-4 text-center"
          :style="{ '--ui-delay': '56ms' }"
        >
          <p class="text-xs font-semibold uppercase tracking-wider text-indigo-300">{{ t('mktOrderStatus.deliveryCodeTitle') }}</p>
          <p class="mt-1 tabular-nums text-3xl font-bold tracking-[0.3em] text-white">{{ order.delivery_code }}</p>
          <p class="mt-1 text-xs text-indigo-100/75">{{ t('mktOrderStatus.deliveryCodeHint') }}</p>
          <button
            class="mt-3 inline-flex items-center gap-1.5 rounded-full border px-4 py-1.5 text-xs font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400/50"
            :class="codeCopied
              ? 'border-emerald-400/50 bg-emerald-500/10 text-emerald-300'
              : 'border-indigo-400/40 text-indigo-300 hover:border-indigo-400/70 hover:bg-indigo-500/10'"
            :aria-label="codeCopied ? t('mktOrderStatus.deliveryCodeCopied') : t('mktOrderStatus.deliveryCodeCopy')"
            @click="copyDeliveryCode(order.delivery_code)"
          >
            <svg v-if="codeCopied" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="h-3.5 w-3.5 shrink-0" aria-hidden="true"><path d="M2.5 8L6 11.5 13.5 4"/></svg>
            <svg v-else viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" class="h-3.5 w-3.5 shrink-0" aria-hidden="true"><rect x="5" y="3" width="9" height="11" rx="1.5"/><path d="M11 3V2a1 1 0 0 0-1-1H3a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h1"/></svg>
            {{ codeCopied ? t('mktOrderStatus.deliveryCodeCopied') : t('mktOrderStatus.deliveryCodeCopy') }}
          </button>
        </div>

        <!-- Scheduled (advance order) banner -->
        <div
          v-if="order.status === 'scheduled' && order.scheduled_for"
          class="ui-reveal rounded-2xl border border-violet-400/40 bg-violet-500/10 p-4 text-center"
          :style="{ '--ui-delay': '56ms' }"
        >
          <p class="text-2xl" aria-hidden="true">🗓️</p>
          <p class="mt-1 text-sm font-semibold text-violet-100">{{ t('mktOrderStatus.scheduledFor', { time: formatScheduledFor(order.scheduled_for) }) }}</p>
        </div>

        <!-- Status stepper -->
        <div class="ui-panel ui-reveal p-5" :style="{ '--ui-delay': '84ms' }">
          <div class="flex items-center justify-between gap-1" role="list" :aria-label="t('mktOrderStatus.statusStepperLabel')">
            <template v-for="(step, idx) in statusSteps" :key="step.key">
              <div class="relative flex flex-1 flex-col items-center gap-1.5" role="listitem">
                <!-- Bubble + pulse ring -->
                <div class="relative flex items-center justify-center">
                  <div
                    v-if="isCurrentStep(step.key) && order.status !== 'cancelled'"
                    class="absolute -inset-1.5 motion-safe:animate-ping rounded-full border border-[var(--color-secondary)]/30"
                    aria-hidden="true"
                  />
                  <div
                    class="relative flex h-10 w-10 items-center justify-center rounded-full border-2 text-sm font-bold transition-all duration-500"
                    :class="stepClass(step.key)"
                    :aria-current="isCurrentStep(step.key) ? 'step' : undefined"
                    :aria-label="t(`mktOrderStatus.${step.key}`) + (isCurrentStep(step.key) ? ' — ' + t('mktOrderStatus.currentStep') : isStepDone(step.key) ? ' — ' + t('mktOrderStatus.stepDone') : '')"
                  >
                    <span v-if="isStepDone(step.key)" aria-hidden="true">✓</span>
                    <span v-else-if="isCurrentStep(step.key)" aria-hidden="true">
                      <span class="block h-2.5 w-2.5 rounded-full bg-current" />
                    </span>
                    <span v-else aria-hidden="true">{{ idx + 1 }}</span>
                  </div>
                </div>
                <span
                  class="text-center text-[10px] leading-tight transition-colors duration-300"
                  :class="isCurrentStep(step.key) ? 'font-semibold text-[var(--color-secondary)]' : isStepDone(step.key) ? 'text-emerald-500/70' : 'text-slate-500'"
                >
                  {{ t(`mktOrderStatus.${step.key}`) }}
                </span>
                <!-- Connector line — sits inside the listitem, bridging to the next step -->
                <div
                  v-if="idx < statusSteps.length - 1"
                  class="absolute top-5 start-1/2 h-0.5 w-full rounded transition-colors duration-500"
                  :class="isStepDone(statusSteps[idx + 1].key) || isCurrentStep(statusSteps[idx + 1].key) ? 'bg-[var(--color-secondary)]/50' : 'bg-slate-700'"
                  aria-hidden="true"
                />
              </div>
            </template>
          </div>

          <!-- Progress bar -->
          <div
            v-if="order.status !== 'cancelled'"
            class="mt-4 relative h-1.5 overflow-hidden rounded-full bg-slate-800"
            role="progressbar"
            :aria-valuenow="progressPercent"
            aria-valuemin="0"
            aria-valuemax="100"
          >
            <span
              class="absolute inset-y-0 start-0 rounded-full bg-[var(--color-secondary)] transition-all duration-700"
              :style="{ width: `${progressPercent}%` }"
            />
          </div>

          <!-- Self-cancel (early pickup/delivery orders only) -->
          <div v-if="order.can_cancel" class="mt-3">
            <Transition name="ui-fade" mode="out-in">
              <div v-if="!cancelConfirming" key="init" class="text-center">
                <button
                  class="ui-press ui-touch-target inline-flex items-center rounded-full border border-red-500/40 px-4 py-1.5 text-xs font-semibold text-red-300 transition-colors hover:bg-red-500/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400/50 disabled:opacity-50"
                  :disabled="cancelling"
                  @click="cancelConfirming = true"
                >
                  {{ t('mktOrderStatus.cancelOrder') }}
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
                    <p class="text-sm font-semibold text-rose-100">{{ t('mktOrderStatus.cancelConfirm') }}</p>
                    <p class="text-xs leading-relaxed text-rose-200/75">{{ t('mktOrderStatus.cancelConfirmBody') }}</p>
                  </div>
                </div>
                <div class="flex gap-2.5">
                  <button
                    class="ui-btn-primary ui-press flex-1 py-2.5 text-sm"
                    style="--color-secondary: #f43f5e; --color-secondary-rgb: 244,63,94"
                    :disabled="cancelling"
                    @click="cancelOrder"
                  >
                    <span aria-live="polite" aria-atomic="true">
                      {{ cancelling ? t('common.saving') : t('mktOrderStatus.cancelConfirmYes') }}
                    </span>
                  </button>
                  <button
                    class="ui-btn-outline ui-press px-4 py-2.5 text-sm"
                    :disabled="cancelling"
                    @click="cancelConfirming = false"
                  >{{ t('common.back') }}</button>
                </div>
              </div>
            </Transition>
          </div>
        </div>

        <!-- Driver tracking panel (shared component) -->
        <DeliveryTracker :delivery="delivery" />

        <!-- Self-delivery (restaurant delivers itself — no platform driver to track) -->
        <div
          v-if="!delivery && order && order.fulfillment_type === 'delivery' && order.status === 'out_for_delivery'"
          class="ui-panel ui-reveal flex items-start gap-3 p-4 text-sm text-slate-300"
          :style="{ '--ui-delay': '112ms' }"
        >
          <span aria-hidden="true" class="shrink-0 text-base">🛵</span>
          <span>{{ t('mktOrderStatus.selfDelivery') }}</span>
        </div>

        <!-- Order items -->
        <div class="ui-panel ui-reveal space-y-3 p-4" :style="{ '--ui-delay': '140ms' }">
          <h2 class="ui-kicker">{{ t('mktOrderStatus.yourItems') }}</h2>
          <ul class="space-y-1.5">
            <li
              v-for="(item, idx) in order.items"
              :key="idx"
              class="flex items-start gap-2.5 rounded-xl border border-slate-800/70 bg-slate-950/40 px-3 py-2.5 text-sm"
            >
              <span class="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-slate-700 bg-slate-800/60 text-[10px] font-bold text-slate-300 tabular-nums">
                {{ item.qty }}
              </span>
              <div class="min-w-0 flex-1">
                <p class="text-slate-200 leading-snug">{{ item.dish_name }}</p>
                <!-- Selected option modifiers (from snapshot) -->
                <p
                  v-if="item.options?.length"
                  class="mt-0.5 text-[11px] text-slate-500 leading-snug"
                >{{ item.options.map(o => o.name).join(' · ') }}</p>
                <!-- Customer note on this item -->
                <p
                  v-if="item.note"
                  class="mt-0.5 text-[11px] italic text-slate-500 leading-snug"
                >{{ item.note }}</p>
              </div>
              <span class="shrink-0 tabular-nums font-semibold text-[var(--color-secondary)]">{{ formatCurrency(item.subtotal, order.currency) }}</span>
            </li>
          </ul>

          <!-- Totals -->
          <div class="space-y-1 border-t border-slate-800/80 pt-2 text-sm">
            <div v-if="Number(order.delivery_fee) > 0" class="flex justify-between text-slate-500">
              <span>{{ t('mktOrderStatus.deliveryFee') }}</span>
              <span class="tabular-nums">{{ formatCurrency(order.delivery_fee, order.currency) }}</span>
            </div>
            <div v-if="Number(order.promotion_discount) > 0" class="flex justify-between text-amber-300">
              <span>{{ order.applied_promotion_name || t('mktOrderStatus.promoDiscount') }}</span>
              <span class="tabular-nums">−{{ formatCurrency(order.promotion_discount, order.currency) }}</span>
            </div>
            <div v-if="Number(order.loyalty_discount) > 0" class="flex justify-between text-amber-400/90">
              <span>{{ t('mktOrderStatus.loyaltyDiscount') }}</span>
              <span class="tabular-nums">−{{ formatCurrency(order.loyalty_discount, order.currency) }}</span>
            </div>
            <div v-if="Number(order.wallet_amount_paid) > 0" class="flex justify-between text-emerald-400/80">
              <span>{{ t('mktOrderStatus.walletPaid') }}</span>
              <span class="tabular-nums">−{{ formatCurrency(order.wallet_amount_paid, order.currency) }}</span>
            </div>
            <div class="flex justify-between font-bold text-white">
              <span>{{ t('mktOrderStatus.total') }}</span>
              <span class="tabular-nums">{{ formatCurrency(order.total, order.currency) }}</span>
            </div>
            <!-- Points earned celebration — visible on completed orders with loyalty earn -->
            <div
              v-if="order.status === 'completed' && order.points_earned > 0"
              class="mt-1.5 flex items-center justify-between rounded-lg border border-violet-500/20 bg-violet-500/8 px-3 py-1.5"
            >
              <span class="flex items-center gap-1.5 text-[11px] text-violet-300">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="h-3 w-3 shrink-0 text-violet-400" aria-hidden="true">
                  <path d="M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 2.97.719 4.192a.75.75 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79l.72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25Z" />
                </svg>
                {{ t('mktOrderStatus.pointsEarned') }}
              </span>
              <span class="text-[12px] font-bold tabular-nums text-violet-200">+{{ order.points_earned }} pts</span>
            </div>
          </div>
        </div>

        <!-- Terminal-state actions -->
        <div v-if="order.status === 'completed' || order.status === 'cancelled'" class="mt-2 flex gap-2">
          <button
            v-if="order.status === 'completed'"
            type="button"
            class="ui-press ui-reveal inline-flex flex-1 items-center justify-center gap-1.5 rounded-2xl border border-slate-700/60 bg-slate-800/50 py-3 text-sm font-semibold text-slate-300 transition-colors hover:bg-slate-800 print:hidden"
            :style="{ '--ui-delay': '160ms' }"
            @click="printReceipt"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" class="h-4 w-4 shrink-0" aria-hidden="true">
              <path d="M6 9V2h12v7M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/>
              <rect x="6" y="14" width="12" height="8"/>
            </svg>
            {{ t('mktOrderStatus.printReceipt') }}
          </button>
          <button
            type="button"
            class="ui-press ui-reveal inline-flex flex-1 items-center justify-center gap-2 rounded-2xl border border-[var(--color-secondary)]/40 bg-[var(--color-secondary)]/8 py-3 text-sm font-semibold text-[var(--color-secondary)] transition-colors hover:bg-[var(--color-secondary)]/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/40"
            :style="{ '--ui-delay': '180ms' }"
            @click="reorder"
          >
            <svg viewBox="0 0 16 16" class="h-4 w-4 shrink-0" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/>
            </svg>
            {{ t('mktOrderStatus.orderAgain') }}
          </button>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useI18n } from '../composables/useI18n';
import { useToastStore } from '../stores/toast';
import api from '../lib/api';
import DeliveryTracker from '../components/DeliveryTracker.vue';

const { t, formatDateTime, formatCurrency } = useI18n();
const route = useRoute();
const router = useRouter();
const toast = useToastStore();


const slug = route.params.slug;
const orderNumber = route.params.orderNumber;

const loading = ref(true);
const fetchError = ref(false);
const order = ref(null);
// Only announce when status genuinely changes — not on every poll cycle that
// re-assigns the same order object (which would re-trigger screen readers).
const liveStatus = ref('');
watch(() => order.value?.status, (newStatus) => {
  if (newStatus && newStatus !== liveStatus.value) liveStatus.value = newStatus;
});

// ── Just-placed celebration banner ────────────────────────────────────────────
const showJustPlacedBanner = ref(false);
let _justPlacedTimer = null;

// ── Delivery-code copy ─────────────────────────────────────────────────────────
const codeCopied = ref(false);
let _codeCopiedTimer = null;
const copyDeliveryCode = (code) => {
  if (!code) return;
  navigator.clipboard.writeText(String(code)).then(() => {
    codeCopied.value = true;
    clearTimeout(_codeCopiedTimer);
    _codeCopiedTimer = setTimeout(() => { codeCopied.value = false; }, 2000);
  }).catch(() => {/* best-effort */});
};

// ── Delivery tracking (driver card + live map rendered by <DeliveryTracker>) ─────
const delivery = ref(null);

const fetchDelivery = async () => {
  try {
    const res = await api.get(`/marketplace/track/${orderNumber}/`, {
      params: { restaurant: slug },
    });
    delivery.value = res.data;
  } catch {
    // 404 = no delivery job for this order, that's OK (pickup orders)
    delivery.value = null;
  }
};

// Driver rating now lives in <DeliveryTracker> (shared by both order pages).

const printReceipt = () => window.print();

// ── Reorder ───────────────────────────────────────────────────────────────────
const reorder = () => {
  if (!order.value?.items?.length) return;
  router.push({
    name: 'marketplace-menu',
    params: { slug },
    state: {
      reorderItems: order.value.items.map((i) => ({
        slug: i.dish_slug,
        name: i.dish_name,
        price: Number(i.unit_price),
        qty: i.qty,
      })),
    },
  });
};

const formatScheduledFor = (iso) => {
  if (!iso) return '';
  try {
    return formatDateTime(iso, { weekday: 'short', dateStyle: undefined, timeStyle: undefined, day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
  } catch {
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? '' : d.toLocaleString();
  }
};

// ── Status stepper ────────────────────────────────────────────────────────────
const STATUS_ORDER = ['pending', 'confirmed', 'preparing', 'ready', 'out_for_delivery', 'completed'];
const statusSteps = [
  { key: 'pending' },
  { key: 'confirmed' },
  { key: 'preparing' },
  { key: 'ready' },
  { key: 'out_for_delivery' },
  { key: 'completed' },
];

const currentStatusIdx = computed(() => {
  if (!order.value) return -1;
  return STATUS_ORDER.indexOf(order.value.status);
});

const isCurrentStep = (key) => order.value?.status === key;
const isStepDone = (key) => {
  const keyIdx = STATUS_ORDER.indexOf(key);
  return keyIdx >= 0 && keyIdx < currentStatusIdx.value;
};

const stepClass = (key) => {
  if (order.value?.status === 'cancelled') {
    return 'border-slate-700 bg-slate-900 text-slate-600';
  }
  if (isCurrentStep(key)) return 'border-[var(--color-secondary)] bg-[var(--color-secondary)]/20 text-[var(--color-secondary)]';
  if (isStepDone(key)) return 'border-[var(--color-secondary)] bg-[var(--color-secondary)] text-slate-950';
  return 'border-slate-700 bg-slate-900 text-slate-600';
};

const progressPercent = computed(() => {
  const idx = currentStatusIdx.value;
  if (idx < 0) return 0;
  return Math.round(((idx + 1) / statusSteps.length) * 100);
});

// ── Polling ───────────────────────────────────────────────────────────────────
let _pollTimer = null;
const TERMINAL_STATUSES = new Set(['completed', 'cancelled']);

const fetchStatus = async () => {
  fetchError.value = false;
  try {
    const res = await api.get(`/marketplace/order/${orderNumber}/`, {
      params: { restaurant: slug },
    });
    order.value = res.data;
    // Stop polling when terminal
    if (TERMINAL_STATUSES.has(res.data.status)) {
      clearInterval(_pollTimer);
      _pollTimer = null;
    }
  } catch {
    fetchError.value = true;
  } finally {
    loading.value = false;
  }
};

const cancelling = ref(false);
const cancelConfirming = ref(false);
const cancelOrder = async () => {
  if (cancelling.value) return;
  cancelling.value = true;
  try {
    await api.post(`/marketplace/order/${orderNumber}/cancel/`, { restaurant: slug });
    toast.show(t('mktOrderStatus.cancelledOk'), 'success');
    cancelConfirming.value = false;
    await fetchStatus();
  } catch (err) {
    const code = err?.response?.data?.code;
    toast.show(code === 'cancel_too_late' ? t('mktOrderStatus.cancelTooLate') : t('mktOrderStatus.cancelFailed'), 'error');
    cancelConfirming.value = false;
  } finally {
    cancelling.value = false;
  }
};

const onMktStatusVisible = () => {
  if (document.visibilityState === 'visible' && _pollTimer) {
    fetchStatus();
    fetchDelivery();
  }
};

onMounted(() => {
  // Request push notification permission proactively (best-effort; same as tenant OrderStatus)
  if (typeof Notification !== 'undefined' && Notification.permission === 'default') {
    Notification.requestPermission().catch(() => {});
  }
  // Show celebration banner if arriving within 60s of placing this order
  try {
    const lastNum = localStorage.getItem('mktLastOrderNumber');
    const lastAt = parseInt(localStorage.getItem('mktLastOrderAt') || '0', 10);
    if (lastNum === String(orderNumber) && (Date.now() - lastAt) < 60000) {
      showJustPlacedBanner.value = true;
      _justPlacedTimer = setTimeout(() => { showJustPlacedBanner.value = false; }, 5000);
    }
  } catch { /* storage unavailable */ }
  fetchStatus();
  fetchDelivery();
  document.addEventListener('visibilitychange', onMktStatusVisible);
  _pollTimer = setInterval(() => {
    if (document.visibilityState === 'hidden') return;
    fetchStatus();
    fetchDelivery();
  }, 10000);
});

onBeforeUnmount(() => {
  if (_justPlacedTimer) clearTimeout(_justPlacedTimer);
  clearInterval(_pollTimer);
  document.removeEventListener('visibilitychange', onMktStatusVisible);
});
</script>
