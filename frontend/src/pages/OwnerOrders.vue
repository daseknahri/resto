<template>
  <div class="space-y-4">
    <!-- Header -->
    <div class="ui-panel space-y-3 p-4 sm:p-5">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div class="space-y-1">
          <p class="ui-section-kicker">{{ t("ownerOrders.kicker") }}</p>
          <h1 class="text-2xl font-semibold text-white">{{ t("ownerOrders.title") }}</h1>
          <p class="text-sm text-slate-400">{{ t("ownerOrders.description") }}</p>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <button
            class="ui-btn-outline px-3 py-1.5 text-sm"
            :class="soundEnabled ? '' : 'opacity-50'"
            :title="soundEnabled ? t('ownerOrders.muteAlerts') : t('ownerOrders.unmuteAlerts')"
            @click="soundEnabled = !soundEnabled"
          >
            {{ soundEnabled ? "🔔" : "🔕" }}
          </button>
          <button class="ui-btn-outline px-3 py-1.5 text-sm" :disabled="exporting || !order.orders.length" @click="exportCsv">
            ⬇ {{ exporting ? t("ownerOrders.exporting") : t("ownerOrders.exportCsv") }}
          </button>
          <button class="ui-btn-outline px-3 py-1.5 text-sm" :disabled="order.ordersLoading" @click="refresh">
            <AppIcon name="refresh" class="h-3.5 w-3.5" />
            {{ t("ownerOrders.refreshOrders") }}
          </button>
        </div>
      </div>

      <!-- Today's stats bar -->
      <div class="grid grid-cols-3 gap-2 rounded-xl border border-slate-800 bg-slate-950/50 px-3 py-3">
        <div class="text-center">
          <p class="text-xl font-bold text-white tabular-nums">{{ todayStats.count }}</p>
          <p class="mt-0.5 text-[10px] uppercase tracking-wider text-slate-500">{{ t("ownerOrders.todayOrders") }}</p>
        </div>
        <div class="border-x border-slate-800 text-center">
          <p class="text-xl font-bold text-[var(--color-secondary)] tabular-nums">{{ formatCurrency(todayStats.revenue, todayStats.currency) }}</p>
          <p class="mt-0.5 text-[10px] uppercase tracking-wider text-slate-500">{{ t("ownerOrders.todayRevenue") }}</p>
        </div>
        <div class="text-center">
          <p
            class="text-xl font-bold tabular-nums transition-colors"
            :class="todayStats.pending > 0 ? 'text-amber-400' : 'text-white'"
          >{{ todayStats.pending }}</p>
          <p class="mt-0.5 text-[10px] uppercase tracking-wider text-slate-500">{{ t("ownerOrders.todayPending") }}</p>
        </div>
      </div>

      <!-- Search + date filter row -->
      <div class="flex flex-wrap items-center gap-2">
        <input
          v-model.trim="searchQuery"
          class="ui-input min-w-0 flex-1 text-sm"
          :placeholder="t('ownerOrders.searchPlaceholder')"
          @input="searchQuery = $event.target.value"
        />
        <div class="flex flex-wrap gap-1">
          <button
            v-for="d in dateTabs"
            :key="d.value"
            type="button"
            class="rounded-full border px-3 py-1 text-xs font-semibold transition-colors"
            :class="activeDateFilter === d.value
              ? 'border-[var(--color-secondary)] bg-[var(--color-secondary)]/10 text-[var(--color-secondary)]'
              : 'border-slate-700 text-slate-300 hover:border-slate-600'"
            @click="activeDateFilter = d.value"
          >
            {{ d.label }}
          </button>
        </div>
        <button
          v-if="searchQuery || activeDateFilter !== 'all'"
          class="rounded-full border border-slate-700 px-2.5 py-1 text-xs text-slate-400 hover:text-slate-200"
          @click="searchQuery = ''; activeDateFilter = 'all'"
        >✕</button>
      </div>

      <!-- Status filter tabs -->
      <div class="flex flex-wrap gap-1.5">
        <button
          v-for="tab in statusTabs"
          :key="tab.value"
          type="button"
          class="rounded-full border px-3 py-1 text-xs font-semibold transition-colors"
          :class="activeStatus === tab.value
            ? 'border-[var(--color-secondary)] bg-[var(--color-secondary)]/10 text-[var(--color-secondary)]'
            : 'border-slate-700 text-slate-300 hover:border-slate-600'"
          @click="setFilter(tab.value)"
        >
          {{ tab.label }}
          <span v-if="tab.count > 0" class="ml-1 rounded-full bg-slate-700 px-1.5 py-0.5 text-[10px]">{{ tab.count }}</span>
        </button>
      </div>

      <!-- Active filter summary -->
      <p v-if="filteredOrders.length !== order.orders.length" class="text-xs text-slate-500">
        {{ t("ownerOrders.showingFiltered", { shown: filteredOrders.length, total: order.orders.length }) }}
      </p>
      <!-- Truncation notice when server has more orders than the 200-row display cap -->
      <p v-if="order.ordersHasMore" class="text-xs text-amber-400/80">
        {{ t("ownerOrders.hasMore", { total: order.ordersTotal }) }}
      </p>
    </div>

    <!-- Loading -->
    <div v-if="order.ordersLoading" class="ui-panel p-8 text-center text-slate-400 text-sm">
      {{ t("common.loading") }}
    </div>

    <!-- Error -->
    <div v-else-if="order.ordersError" class="ui-panel border-red-500/30 p-5 text-sm text-red-300">
      {{ order.ordersError }}
    </div>

    <!-- Empty -->
    <div v-else-if="!filteredOrders.length" class="ui-panel p-8 text-center text-slate-400 text-sm">
      {{ t("ownerOrders.noOrders") }}
    </div>

    <!-- Order list -->
    <div v-else class="space-y-3">
      <article
        v-for="o in filteredOrders"
        :key="o.id"
        class="ui-panel space-y-4 p-4 sm:p-5 transition-colors"
        :class="orderCardClass(o)"
      >
        <!-- Order header -->
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div class="space-y-1.5">
            <div class="flex flex-wrap items-center gap-2">
              <span class="font-mono text-base font-bold text-white">{{ o.order_number }}</span>
              <span class="rounded-full px-2.5 py-0.5 text-xs font-semibold" :class="statusClass(o.status)">
                {{ statusLabel(o.status) }}
              </span>
              <span class="ui-data-strip">{{ fulfillmentLabel(o) }}</span>
              <!-- Marketplace source badge -->
              <span
                v-if="o.source === 'marketplace'"
                class="rounded-full bg-violet-500/15 border border-violet-500/30 px-2 py-0.5 text-[10px] font-semibold text-violet-300"
              >
                🛒 {{ t('ownerOrders.sourceMarketplace') }}
              </span>
              <!-- Age warning badge -->
              <span
                v-if="orderAgeMin(o) >= 5 && ['pending', 'confirmed'].includes(o.status)"
                class="rounded-full px-2 py-0.5 text-[10px] font-bold"
                :class="orderAgeMin(o) >= 10
                  ? 'bg-red-500/25 text-red-300'
                  : 'bg-amber-500/25 text-amber-300'"
              >
                ⏱ {{ orderAgeMin(o) }}m
              </span>
            </div>
            <p class="text-xs text-slate-400">{{ formatTime(o.created_at) }}</p>
          </div>
          <div class="text-right">
            <p class="text-lg font-bold text-[var(--color-secondary)]">{{ formatCurrency(o.total, o.currency) }}</p>
            <p v-if="o.promotion_discount && Number(o.promotion_discount) > 0" class="text-[10px] text-emerald-400">
              {{ t('ownerOrders.promoDiscount') }} −{{ formatCurrency(o.promotion_discount, o.currency) }}
            </p>
            <p v-if="o.tip_amount && Number(o.tip_amount) > 0" class="text-[10px] text-sky-400">
              {{ t('ownerOrders.tip') }} +{{ formatCurrency(o.tip_amount, o.currency) }}
            </p>
            <p v-if="o.wallet_amount_paid && Number(o.wallet_amount_paid) > 0" class="text-[10px] text-emerald-300">
              💰 {{ t('ownerOrders.walletPaid') }} {{ formatCurrency(o.wallet_amount_paid, o.currency) }}
            </p>
            <p class="text-xs text-slate-400">{{ itemCountLabel(o.items_count) }}</p>
          </div>
        </div>

        <!-- Customer info -->
        <div v-if="o.customer_name || o.customer_phone || o.customer_email" class="grid gap-2 rounded-xl border border-slate-800 bg-slate-950/40 px-3 py-2 text-xs sm:grid-cols-2">
          <div v-if="o.customer_name" class="flex flex-wrap items-center gap-2">
            <div>
              <span class="text-slate-500">{{ t("ownerOrders.customer") }}</span>
              <span class="ml-1.5 font-medium text-slate-100">{{ o.customer_name }}</span>
            </div>
            <!-- Customer trust badge -->
            <template v-if="o.customer_trust?.rating_count">
              <span
                class="rounded-full px-2 py-0.5 text-[10px] font-semibold"
                :class="o.customer_trust.avg_score >= 4
                  ? 'bg-emerald-500/15 text-emerald-300'
                  : o.customer_trust.avg_score >= 3
                    ? 'bg-amber-500/15 text-amber-300'
                    : 'bg-red-500/15 text-red-300'"
              >
                ★ {{ o.customer_trust.avg_score }}
                <span class="opacity-70">({{ o.customer_trust.rating_count }})</span>
              </span>
            </template>
          </div>
          <!-- When no name but trust exists (phone/email-only orders) -->
          <template v-else-if="o.customer_trust?.rating_count">
            <div class="flex items-center gap-2">
              <span class="text-slate-500">{{ t("ownerOrders.customerTrustScore") }}</span>
              <span
                class="rounded-full px-2 py-0.5 text-[10px] font-semibold"
                :class="o.customer_trust.avg_score >= 4
                  ? 'bg-emerald-500/15 text-emerald-300'
                  : o.customer_trust.avg_score >= 3
                    ? 'bg-amber-500/15 text-amber-300'
                    : 'bg-red-500/15 text-red-300'"
              >
                ★ {{ o.customer_trust.avg_score }}
                <span class="opacity-70">({{ o.customer_trust.rating_count }})</span>
              </span>
            </div>
          </template>
          <div v-if="o.customer_phone" class="flex flex-wrap items-center gap-2">
            <a :href="`tel:${o.customer_phone}`" class="font-medium text-sky-300 hover:text-sky-200">{{ o.customer_phone }}</a>
            <a
              :href="orderWhatsappUrl(o.customer_phone)"
              target="_blank"
              rel="noopener noreferrer"
              class="inline-flex items-center gap-1 rounded-full border border-emerald-500/40 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold text-emerald-300 hover:border-emerald-400/60 hover:bg-emerald-500/20"
            >
              💬 {{ t("ownerOrders.whatsapp") }}
            </a>
          </div>
          <div v-if="o.customer_email">
            <a :href="`mailto:${o.customer_email}`" class="font-medium text-sky-300 hover:text-sky-200">{{ o.customer_email }}</a>
          </div>
          <div v-if="o.delivery_fee && Number(o.delivery_fee) > 0" class="sm:col-span-2">
            <span class="text-slate-500">{{ t("ownerOrders.deliveryFee") }}</span>
            <span class="ml-1.5 font-medium text-slate-200">{{ formatCurrency(o.delivery_fee, o.currency) }}</span>
          </div>
          <div v-if="o.tip_amount && Number(o.tip_amount) > 0" class="sm:col-span-2">
            <span class="text-slate-500">{{ t("ownerOrders.tip") }}</span>
            <span class="ml-1.5 font-medium text-emerald-300">{{ formatCurrency(o.tip_amount, o.currency) }}</span>
          </div>
          <div v-if="o.wallet_amount_paid && Number(o.wallet_amount_paid) > 0" class="sm:col-span-2">
            <span class="text-slate-500">💰 {{ t("ownerOrders.walletPaid") }}</span>
            <span class="ml-1.5 font-medium text-emerald-300">{{ formatCurrency(o.wallet_amount_paid, o.currency) }}</span>
          </div>
          <div v-if="o.delivery_address" class="sm:col-span-2">
            <span class="text-slate-500">{{ t("ownerOrders.delivery") }}</span>
            <span class="ml-1.5 text-slate-200">{{ o.delivery_address }}</span>
            <a
              v-if="orderMapUrl(o)"
              :href="orderMapUrl(o)"
              target="_blank"
              rel="noopener noreferrer"
              class="ml-2 inline-flex items-center gap-1 rounded-full border border-sky-500/40 bg-sky-500/10 px-2 py-0.5 text-[10px] font-semibold text-sky-300 hover:border-sky-400/60 hover:bg-sky-500/20"
            >
              📍 {{ t("ownerOrders.openMap") }}
            </a>
          </div>

          <!-- Delivery job panel -->
          <div v-if="o.delivery_job" class="sm:col-span-2 rounded-xl border border-slate-700/50 bg-slate-800/40 p-3 space-y-2 text-xs">
            <div class="flex items-center justify-between gap-2">
              <span class="font-semibold text-slate-300">🛵 {{ t('ownerOrders.deliveryJobTitle') }}</span>
              <span
                class="rounded-full px-2 py-0.5 text-[10px] font-semibold"
                :class="{
                  'bg-amber-500/15 border border-amber-500/30 text-amber-300': o.delivery_job.status === 'searching',
                  'bg-sky-500/15 border border-sky-500/30 text-sky-300': ['assigned','at_restaurant'].includes(o.delivery_job.status),
                  'bg-violet-500/15 border border-violet-500/30 text-violet-300': o.delivery_job.status === 'picked_up',
                  'bg-emerald-500/15 border border-emerald-500/30 text-emerald-300': o.delivery_job.status === 'delivered',
                  'bg-red-500/15 border border-red-500/30 text-red-300': o.delivery_job.status === 'failed',
                }"
              >{{ t(`ownerOrders.djStatus_${o.delivery_job.status}`) }}</span>
            </div>
            <div v-if="o.delivery_job.driver" class="flex items-center justify-between gap-2">
              <div class="flex items-center gap-2">
                <span>{{ o.delivery_job.driver.name || t('ownerOrders.djDriverUnnamed') }}</span>
                <span v-if="o.delivery_job.driver.is_online" class="text-emerald-400">● {{ t('ownerOrders.djOnline') }}</span>
              </div>
              <a
                v-if="o.delivery_job.driver.phone"
                :href="`tel:${o.delivery_job.driver.phone}`"
                class="text-sky-400 hover:text-sky-300"
              >{{ o.delivery_job.driver.phone }}</a>
            </div>
            <p v-else class="text-slate-500">{{ t('ownerOrders.djSearching') }}</p>

            <!-- Rate driver button (only when delivered and not yet rated) -->
            <div v-if="o.delivery_job.status === 'delivered' && !o.delivery_job.restaurant_driver_rating">
              <div v-if="ratingJobId === o.id" class="space-y-1.5">
                <div class="flex gap-1">
                  <button
                    v-for="n in 5"
                    :key="n"
                    class="text-lg transition-transform hover:scale-110"
                    :class="ratingScore >= n ? 'text-amber-400' : 'text-slate-600'"
                    @click="ratingScore = n"
                  >★</button>
                </div>
                <input
                  v-model="ratingNote"
                  class="w-full rounded-lg border border-slate-700 bg-slate-900 px-2 py-1 text-slate-200 placeholder-slate-500 focus:outline-none text-[11px]"
                  :placeholder="t('ownerOrders.djRatingNotePlaceholder')"
                />
                <div class="flex gap-2">
                  <button
                    class="rounded-full bg-[var(--color-secondary,#f59e0b)] px-3 py-1 text-[11px] font-semibold text-slate-950 disabled:opacity-50"
                    :disabled="!ratingScore || submittingRating"
                    @click="submitJobRating(o)"
                  >{{ submittingRating ? '…' : t('ownerOrders.djSubmitRating') }}</button>
                  <button class="text-slate-500 hover:text-slate-300 text-[11px]" @click="ratingJobId = null; ratingScore = 0; ratingNote = ''">{{ t('common.cancel') }}</button>
                </div>
              </div>
              <button
                v-else
                class="rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold text-amber-300 hover:bg-amber-500/20"
                @click="ratingJobId = o.id; ratingScore = 0; ratingNote = ''"
              >★ {{ t('ownerOrders.djRateDriver') }}</button>
            </div>
            <div v-else-if="o.delivery_job.restaurant_driver_rating" class="text-slate-500">
              {{ t('ownerOrders.djRated', { score: o.delivery_job.restaurant_driver_rating }) }}
            </div>
          </div>
        </div>

        <!-- Items -->
        <div class="space-y-1.5">
          <div
            v-for="item in o.items"
            :key="item.dish_slug + item.note"
            class="flex items-start justify-between gap-2 rounded-xl border border-slate-800 bg-slate-950/30 px-3 py-2 text-xs"
          >
            <div class="space-y-0.5">
              <p class="font-semibold text-slate-100">{{ item.qty }}× {{ item.dish_name }}</p>
              <p v-if="item.options?.length" class="text-slate-400">
                {{ t("ownerOrders.options") }}: {{ item.options.map(o => o.name).join(", ") }}
              </p>
              <p v-if="item.note" class="text-slate-400">{{ item.note }}</p>
            </div>
            <p class="shrink-0 font-medium text-slate-200">{{ formatCurrency(item.subtotal, o.currency) }}</p>
          </div>
          <p v-if="o.customer_note" class="rounded-xl border border-slate-800 bg-slate-950/30 px-3 py-2 text-xs text-slate-300">
            <span class="font-semibold text-slate-400">{{ t("ownerOrders.note") }}:</span> {{ o.customer_note }}
          </p>
        </div>

        <!-- Owner note + estimate -->
        <div v-if="editingId === o.id" class="space-y-2 rounded-xl border border-slate-700 bg-slate-900/60 p-3">
          <label class="block space-y-1 text-xs text-slate-400">
            {{ t("ownerOrders.ownerNote") }}
            <input v-model="editNote" maxlength="300" class="ui-input mt-1 text-sm" />
          </label>
          <label class="block space-y-1 text-xs text-slate-400">
            {{ t("ownerOrders.setEstimate") }}
            <input v-model.number="editMinutes" type="number" min="0" max="180" class="ui-input mt-1 w-32 text-sm" :placeholder="t('ownerOrders.minutesPlaceholder')" />
          </label>
          <div class="flex gap-2">
            <button class="ui-btn-primary px-3 py-1.5 text-xs" :disabled="order.updatingOrderId === o.id" @click="saveNote(o)">
              {{ order.updatingOrderId === o.id ? t("common.saving") : t("ownerOrders.saveNote") }}
            </button>
            <button class="ui-btn-outline px-3 py-1.5 text-xs" @click="editingId = null">{{ t("common.close") }}</button>
          </div>
          <p v-if="noteError" class="text-xs text-red-400">{{ noteError }}</p>
        </div>

        <div v-else class="flex flex-wrap items-center gap-2">
          <span v-if="o.owner_note" class="text-xs text-slate-400">
            <span class="font-semibold">{{ t("ownerOrders.ownerNote") }}:</span> {{ o.owner_note }}
          </span>
          <span v-if="o.estimated_ready_minutes" class="ui-data-strip text-emerald-200">
            {{ t("ownerOrders.estimatedReady", { minutes: o.estimated_ready_minutes }) }}
          </span>
        </div>

        <!-- Action buttons -->
        <div class="flex flex-wrap items-center gap-2">
          <template v-if="o.status === 'pending'">
            <button class="ui-btn-primary px-3 py-1.5 text-xs" :disabled="order.updatingOrderId === o.id" @click="updateStatus(o, 'confirmed')">
              {{ t("ownerOrders.confirm") }}
            </button>
            <button class="ui-btn-outline border-red-500/40 px-3 py-1.5 text-xs text-red-300 hover:border-red-400" :disabled="order.updatingOrderId === o.id" @click="updateStatus(o, 'cancelled')">
              {{ t("ownerOrders.cancel") }}
            </button>
          </template>
          <template v-else-if="o.status === 'confirmed'">
            <button class="ui-btn-primary px-3 py-1.5 text-xs" :disabled="order.updatingOrderId === o.id" @click="updateStatus(o, 'preparing')">
              {{ t("ownerOrders.startPreparing") }}
            </button>
            <button class="ui-btn-outline border-red-500/40 px-3 py-1.5 text-xs text-red-300 hover:border-red-400" :disabled="order.updatingOrderId === o.id" @click="updateStatus(o, 'cancelled')">
              {{ t("ownerOrders.cancel") }}
            </button>
          </template>
          <template v-else-if="o.status === 'preparing'">
            <button class="ui-btn-primary px-3 py-1.5 text-xs" :disabled="order.updatingOrderId === o.id" @click="updateStatus(o, 'ready')">
              {{ t("ownerOrders.markReady") }}
            </button>
          </template>
          <template v-else-if="o.status === 'ready'">
            <button class="ui-btn-primary px-3 py-1.5 text-xs" :disabled="order.updatingOrderId === o.id" @click="updateStatus(o, 'completed')">
              {{ t("ownerOrders.complete") }}
            </button>
          </template>

          <button
            v-if="['pending','confirmed','preparing','ready'].includes(o.status)"
            class="ui-btn-outline px-3 py-1.5 text-xs"
            @click="openEdit(o)"
          >
            {{ t("ownerOrders.ownerNote") }}
          </button>

          <!-- Print ticket -->
          <button
            class="ui-btn-outline px-3 py-1.5 text-xs"
            @click="printTicket(o)"
          >
            🖨 {{ t("ownerOrders.printTicket") }}
          </button>

          <!-- Rate customer (only for linked customer accounts) -->
          <button
            v-if="o.customer_id && ['completed', 'cancelled'].includes(o.status)"
            class="ui-btn-outline px-3 py-1.5 text-xs"
            :class="o.my_customer_rating ? 'border-amber-500/40 text-amber-300' : ''"
            @click="openRating(o)"
          >
            ★ {{ o.my_customer_rating ? t("ownerOrders.updateCustomerRating") : t("ownerOrders.rateCustomer") }}
          </button>
        </div>

        <!-- Customer trust rating panel -->
        <div v-if="ratingOrderId === o.id" class="space-y-3 rounded-xl border border-slate-700 bg-slate-900/60 p-3">
          <div class="flex items-start justify-between gap-2">
            <div class="space-y-0.5">
              <p class="text-xs font-semibold text-slate-200">{{ t("ownerOrders.customerRatingTitle") }}</p>
              <p class="text-[10px] text-slate-500">{{ t("ownerOrders.customerRatingHint") }}</p>
            </div>
          </div>

          <!-- Star selector -->
          <div class="flex items-center gap-1">
            <button
              v-for="star in 5"
              :key="star"
              type="button"
              class="text-xl transition-transform hover:scale-110 focus:outline-none"
              :class="star <= ratingScore ? 'text-amber-400' : 'text-slate-600'"
              @click="ratingScore = star"
            >★</button>
            <span class="ml-2 text-xs text-slate-400">{{ ratingScore }}/5</span>
          </div>

          <!-- Note field -->
          <label class="block space-y-1 text-xs text-slate-400">
            {{ t("ownerOrders.customerRatingNote") }}
            <input v-model="ratingNote" maxlength="200" class="ui-input mt-1 text-sm" />
          </label>

          <div class="flex gap-2">
            <button
              class="ui-btn-primary px-3 py-1.5 text-xs"
              :disabled="submittingRating"
              @click="submitCustomerRating(o)"
            >
              {{ submittingRating ? t("common.saving") : t("ownerOrders.customerRatingSubmit") }}
            </button>
            <button class="ui-btn-outline px-3 py-1.5 text-xs" @click="ratingOrderId = null">{{ t("common.close") }}</button>
          </div>
          <p v-if="ratingError" class="text-xs text-red-400">{{ ratingError }}</p>
        </div>
      </article>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import AppIcon from "../components/AppIcon.vue";
import { useI18n } from "../composables/useI18n";
import api from "../lib/api";
import { useOrderStore } from "../stores/order";
import { useToastStore } from "../stores/toast";

const { t, itemCountLabel, formatNumber, currentLocale } = useI18n();
const order = useOrderStore();
const toast = useToastStore();
const route = useRoute();

const activeStatus = ref("");
const activeDateFilter = ref("all");
const searchQuery = ref("");
const exporting = ref(false);
const editingId = ref(null);
const editNote = ref("");
const editMinutes = ref(null);
const noteError = ref("");

// Customer trust rating
const ratingOrderId = ref(null);
// Driver rating (from restaurant side — shared score/note refs)
const ratingJobId = ref(null);
const ratingScore = ref(5);
const ratingNote = ref("");
const submittingRating = ref(false);
const ratingError = ref("");

// Sound preference — persisted in localStorage per hostname
const SOUND_KEY = typeof window === "undefined" ? "orders:sound" : `orders:sound:${window.location.hostname}`;
const soundEnabled = ref((() => {
  try { return localStorage.getItem(SOUND_KEY) !== "off"; } catch { return true; }
})());
watch(soundEnabled, (val) => {
  try { localStorage.setItem(SOUND_KEY, val ? "on" : "off"); } catch { /* ignore */ }
});

// Shared AudioContext — created once on first user gesture so Chrome's autoplay
// policy is satisfied. Any click on the page (including the mute toggle) will
// initialise it; subsequent calls from setInterval simply reuse the same ctx.
let _audioCtx = null;
const _getAudioCtx = () => {
  if (!_audioCtx) {
    try { _audioCtx = new (window.AudioContext || window.webkitAudioContext)(); } catch { /* not supported */ }
  }
  return _audioCtx;
};
// Prime the context on the first user interaction on this page
if (typeof window !== "undefined") {
  const _prime = () => { _getAudioCtx(); window.removeEventListener("click", _prime, true); };
  window.addEventListener("click", _prime, { capture: true, once: true });
}

// ── Date filter tabs ──────────────────────────────────────────────────────────
const dateTabs = computed(() => [
  { value: "all",       label: t("ownerOrders.dateAll") },
  { value: "today",     label: t("ownerOrders.dateToday") },
  { value: "yesterday", label: t("ownerOrders.dateYesterday") },
  { value: "week",      label: t("ownerOrders.dateLast7") },
]);

// ── Status tabs ───────────────────────────────────────────────────────────────
const statusTabs = computed(() => {
  const counts = {};
  order.orders.forEach((o) => { counts[o.status] = (counts[o.status] || 0) + 1; });
  return [
    { value: "", label: t("ownerOrders.allStatuses"), count: 0 },
    { value: "pending", label: t("ownerOrders.statusPending"), count: counts.pending || 0 },
    { value: "confirmed", label: t("ownerOrders.statusConfirmed"), count: counts.confirmed || 0 },
    { value: "preparing", label: t("ownerOrders.statusPreparing"), count: counts.preparing || 0 },
    { value: "ready", label: t("ownerOrders.statusReady"), count: counts.ready || 0 },
    { value: "completed", label: t("ownerOrders.statusCompleted"), count: counts.completed || 0 },
    { value: "cancelled", label: t("ownerOrders.statusCancelled"), count: counts.cancelled || 0 },
  ];
});

// ── Today's stats ─────────────────────────────────────────────────────────────
const todayStats = computed(() => {
  const today = new Date().toDateString();
  const todayOrders = order.orders.filter((o) => new Date(o.created_at).toDateString() === today);
  const pending = todayOrders.filter((o) => o.status === "pending").length;
  const revenue = todayOrders.reduce((sum, o) => sum + (Number(o.total) || 0), 0);
  const currency = todayOrders.find((o) => o.currency)?.currency || "MAD";
  return { count: todayOrders.length, revenue, pending, currency };
});

// ── Filtered + sorted orders ──────────────────────────────────────────────────
const STATUS_SORT = { pending: 0, confirmed: 1, preparing: 2, ready: 3, completed: 4, cancelled: 5 };

const filteredOrders = computed(() => {
  const now = new Date();
  const todayStr = now.toDateString();
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  const yesterdayStr = yesterday.toDateString();
  const weekAgo = new Date(now);
  weekAgo.setDate(now.getDate() - 6);
  weekAgo.setHours(0, 0, 0, 0);

  const q = searchQuery.value.toLowerCase();

  let base = order.orders.filter((o) => {
    // Status filter
    if (activeStatus.value && o.status !== activeStatus.value) return false;

    // Date filter
    if (activeDateFilter.value !== "all") {
      const d = new Date(o.created_at);
      if (activeDateFilter.value === "today" && d.toDateString() !== todayStr) return false;
      if (activeDateFilter.value === "yesterday" && d.toDateString() !== yesterdayStr) return false;
      if (activeDateFilter.value === "week" && d < weekAgo) return false;
    }

    // Search filter
    if (q) {
      const haystack = [
        o.order_number,
        o.customer_name,
        o.customer_phone,
        o.customer_email,
        o.delivery_address,
        o.table_label,
      ].filter(Boolean).join(" ").toLowerCase();
      if (!haystack.includes(q)) return false;
    }

    return true;
  });

  return [...base].sort((a, b) => {
    const sd = (STATUS_SORT[a.status] ?? 9) - (STATUS_SORT[b.status] ?? 9);
    if (sd !== 0) return sd;
    // Within same status: newest first
    return new Date(b.created_at) - new Date(a.created_at);
  });
});

const setFilter = (val) => { activeStatus.value = val; };
const refresh = () => order.fetchOrders();

// ── Helpers ───────────────────────────────────────────────────────────────────
const statusClass = (s) => ({
  pending: "bg-amber-500/20 text-amber-200 border border-amber-500/30",
  confirmed: "bg-sky-500/20 text-sky-200 border border-sky-500/30",
  preparing: "bg-violet-500/20 text-violet-200 border border-violet-500/30",
  ready: "bg-emerald-500/20 text-emerald-200 border border-emerald-500/30",
  completed: "bg-slate-700 text-slate-300",
  cancelled: "bg-red-500/20 text-red-300 border border-red-500/30",
}[s] || "bg-slate-700 text-slate-300");

const statusLabel = (s) => ({
  pending: t("ownerOrders.statusPending"),
  confirmed: t("ownerOrders.statusConfirmed"),
  preparing: t("ownerOrders.statusPreparing"),
  ready: t("ownerOrders.statusReady"),
  completed: t("ownerOrders.statusCompleted"),
  cancelled: t("ownerOrders.statusCancelled"),
}[s] || s);

const fulfillmentLabel = (o) => {
  if (o.fulfillment_type === "table") return t("ownerOrders.fulfillmentTable", { table: o.table_label || "?" });
  if (o.fulfillment_type === "delivery") return t("ownerOrders.fulfillmentDelivery");
  if (o.fulfillment_type === "pickup") return t("ownerOrders.fulfillmentPickup");
  return "";
};

const formatCurrency = (amount, currency = "USD") => {
  try {
    return formatNumber(Number(amount) || 0, { style: "currency", currency });
  } catch {
    return `${currency} ${Number(amount).toFixed(2)}`;
  }
};

const formatTime = (iso) => {
  if (!iso) return "";
  const d = new Date(iso);
  const now = new Date();
  const diffMin = Math.floor((now - d) / 60000);
  if (diffMin < 1) return t("ownerOrders.justNow");
  if (diffMin < 60) return `${diffMin}m`;
  if (diffMin < 1440) return `${Math.floor(diffMin / 60)}h ${diffMin % 60}m`;
  return new Intl.DateTimeFormat(currentLocale.value, { dateStyle: "short" }).format(d);
};

// ── Delivery helpers ──────────────────────────────────────────────────────────
const orderMapUrl = (o) => {
  if (o.delivery_location_url) return o.delivery_location_url;
  const lat = o.delivery_lat;
  const lng = o.delivery_lng;
  if (lat != null && lng != null) return `https://maps.google.com/?q=${lat},${lng}`;
  return null;
};

const orderWhatsappUrl = (phone) => {
  if (!phone) return "#";
  const digits = String(phone).replace(/\D/g, "");
  return `https://wa.me/${digits}`;
};

// ── Order age ─────────────────────────────────────────────────────────────────
const orderAgeMin = (o) => Math.floor((Date.now() - new Date(o.created_at)) / 60000);

const orderCardClass = (o) => {
  if (["pending", "confirmed"].includes(o.status)) {
    const age = orderAgeMin(o);
    if (age >= 10) return "border-red-500/60 bg-red-950/5";
    if (age >= 5)  return "border-amber-400/60";
    return "border-amber-500/40";
  }
  if (o.status === "cancelled") return "border-red-500/20";
  return "";
};

// ── Status actions ────────────────────────────────────────────────────────────
const updateStatus = async (o, newStatus) => {
  try {
    await order.updateOrderStatus(o.id, { status: newStatus });
    toast.show(t("ownerOrders.updated"), "success");
    // After confirming, immediately open the note/ETA panel so the owner can
    // set an estimated ready time in the same action without a second click.
    if (newStatus === "confirmed") {
      const fresh = order.orders.find((x) => x.id === o.id) || o;
      openEdit(fresh);
    }
  } catch {
    toast.show(t("ownerOrders.updateFailed"), "error");
  }
};

const openEdit = (o) => {
  editingId.value = o.id;
  editNote.value = o.owner_note || "";
  editMinutes.value = o.estimated_ready_minutes ?? null;
  noteError.value = "";
};

const saveNote = async (o) => {
  noteError.value = "";
  try {
    await order.updateOrderStatus(o.id, {
      owner_note: editNote.value,
      estimated_ready_minutes: editMinutes.value ?? null,
    });
    editingId.value = null;
    toast.show(t("ownerOrders.updated"), "success");
  } catch {
    noteError.value = t("ownerOrders.updateFailed");
  }
};

// ── Customer trust rating ─────────────────────────────────────────────────────
const openRating = (o) => {
  ratingOrderId.value = o.id;
  ratingScore.value = o.my_customer_rating?.score ?? 5;
  ratingNote.value = o.my_customer_rating?.note ?? "";
  ratingError.value = "";
  // Close the note editor if open
  if (editingId.value === o.id) editingId.value = null;
};

const submitCustomerRating = async (o) => {
  ratingError.value = "";
  submittingRating.value = true;
  try {
    const res = await api.post(`/owner/orders/${o.id}/customer-rating/`, {
      score: ratingScore.value,
      note: ratingNote.value,
    });
    // Update in-place so the badge refreshes immediately
    o.my_customer_rating = { score: ratingScore.value, note: ratingNote.value };
    o.customer_trust = {
      avg_score: res.data.avg_score,
      rating_count: res.data.rating_count,
    };
    ratingOrderId.value = null;
    toast.show(t("ownerOrders.customerRatingSubmitted"), "success");
  } catch {
    ratingError.value = t("ownerOrders.customerRatingFailed");
  } finally {
    submittingRating.value = false;
  }
};

// ── Driver rating (restaurant rates driver) ───────────────────────────────────
const submitJobRating = async (o) => {
  if (!ratingScore.value || submittingRating.value) return;
  submittingRating.value = true;
  try {
    await api.post(`/marketplace/track/${o.order_number}/rate/`, {
      role: 'restaurant',
      score: ratingScore.value,
      note: ratingNote.value,
    });
    // Update in-place so the rate button disappears
    if (o.delivery_job) {
      o.delivery_job.restaurant_driver_rating = ratingScore.value;
      o.delivery_job.restaurant_driver_note = ratingNote.value;
    }
    ratingJobId.value = null;
    ratingScore.value = 0;
    ratingNote.value = '';
    toast.show(t('ownerOrders.djRatingSubmitted'), 'success');
  } catch {
    toast.show(t('ownerOrders.djRatingFailed'), 'error');
  } finally {
    submittingRating.value = false;
  }
};

// ── Print ticket ──────────────────────────────────────────────────────────────
const printTicket = (o) => {
  const itemRows = (o.items || []).map((item) => {
    const opts = item.options?.length ? `<div style="font-size:11px;color:#555">${item.options.map((x) => x.name).join(", ")}</div>` : "";
    const note = item.note ? `<div style="font-size:11px;color:#555;font-style:italic">${item.note}</div>` : "";
    return `<tr>
      <td style="padding:3px 0;vertical-align:top">
        <strong>${item.qty}×</strong> ${item.dish_name}${opts}${note}
      </td>
      <td style="padding:3px 0;text-align:right;white-space:nowrap;vertical-align:top">
        ${formatCurrency(item.subtotal, o.currency)}
      </td>
    </tr>`;
  }).join("");

  const meta = [
    fulfillmentLabel(o),
    o.customer_name ? `${t("ownerOrders.ticketCustomer")}: ${o.customer_name}` : "",
    o.customer_phone ? `${t("ownerOrders.ticketPhone")}: ${o.customer_phone}` : "",
    o.customer_email ? `${t("ownerOrders.ticketEmail")}: ${o.customer_email}` : "",
    o.delivery_address ? `${t("ownerOrders.ticketAddress")}: ${o.delivery_address}` : "",
    new Intl.DateTimeFormat(currentLocale.value, { dateStyle: "short", timeStyle: "short" }).format(new Date(o.created_at)),
  ].filter(Boolean).map((line) => `<div>${line}</div>`).join("");

  const noteLabel      = t("ownerOrders.ticketNote");
  const totalLabel     = t("ownerOrders.ticketTotal");
  const printedLabel   = t("ownerOrders.ticketPrinted");
  const feeLabel       = t("ownerOrders.deliveryFee");
  const subtotalLabel  = t("ownerOrders.ticketSubtotal");
  const walletLabel    = t("ownerOrders.walletPaid");

  const note = o.customer_note
    ? `<div style="border-top:1px dashed #000;margin-top:8px;padding-top:6px"><strong>${noteLabel}:</strong> ${o.customer_note}</div>`
    : "";

  const html = `<!DOCTYPE html><html><head>
    <meta charset="utf-8">
    <title>Order ${o.order_number}</title>
    <style>
      * { margin:0; padding:0; box-sizing:border-box; }
      body { font-family: 'Courier New', monospace; font-size: 13px; width: 300px; padding: 12px; }
      h1 { font-size: 18px; text-align: center; letter-spacing: 1px; border-bottom: 2px dashed #000; padding-bottom: 8px; margin-bottom: 8px; }
      .meta { font-size: 11px; margin-bottom: 8px; line-height: 1.6; }
      table { width: 100%; border-collapse: collapse; }
      .divider { border-top: 1px dashed #000; margin: 8px 0; }
      .total td { font-weight: bold; font-size: 15px; padding: 4px 0; }
      .footer { text-align: center; font-size: 10px; color: #666; margin-top: 12px; border-top: 1px dashed #000; padding-top: 8px; }
      @media print { @page { margin: 0; size: 80mm auto; } }
    </style>
  </head><body>
    <h1>#${o.order_number}</h1>
    <div class="meta">${meta}</div>
    <div class="divider"></div>
    <table>${itemRows}</table>
    <div class="divider"></div>
    <table>
      ${Number(o.delivery_fee) > 0 ? `
      <tr><td style="padding:2px 0;font-size:12px;color:#444">${subtotalLabel}</td><td style="text-align:right;font-size:12px;color:#444">${formatCurrency(Number(o.total) - Number(o.delivery_fee), o.currency)}</td></tr>
      <tr><td style="padding:2px 0;font-size:12px;color:#444">${feeLabel}</td><td style="text-align:right;font-size:12px;color:#444">${formatCurrency(o.delivery_fee, o.currency)}</td></tr>
      ` : ""}
      <tr class="total"><td>${totalLabel}</td><td style="text-align:right">${formatCurrency(o.total, o.currency)}</td></tr>
      ${Number(o.wallet_amount_paid) > 0 ? `
      <tr><td style="padding:2px 0;font-size:12px;color:#16a34a">💰 ${walletLabel}</td><td style="text-align:right;font-size:12px;color:#16a34a">−${formatCurrency(o.wallet_amount_paid, o.currency)}</td></tr>
      ` : ""}
    </table>
    ${note}
    <div class="footer">${printedLabel} ${new Intl.DateTimeFormat(currentLocale.value, { timeStyle: 'short' }).format(new Date())}</div>
  </body></html>`;

  const win = window.open("", "_blank", "width=420,height=620");
  if (!win) { toast.show(t("ownerOrders.printBlocked"), "error"); return; }
  win.document.write(html);
  win.document.close();
  win.focus();
  setTimeout(() => { win.print(); win.close(); }, 300);
};

// ── CSV export ────────────────────────────────────────────────────────────────
// Calls the server export endpoint (up to 5 000 rows, BOM-prefixed for Excel)
// so owners always get the full history, not just the 200 currently in memory.
const _toIsoDate = (d) => {
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
};

const _buildExportParams = () => {
  const params = {};
  if (activeStatus.value) params.status = activeStatus.value;
  const now = new Date();
  if (activeDateFilter.value === "today") {
    params.from = params.to = _toIsoDate(now);
  } else if (activeDateFilter.value === "yesterday") {
    const y = new Date(now); y.setDate(now.getDate() - 1);
    params.from = params.to = _toIsoDate(y);
  } else if (activeDateFilter.value === "week") {
    const w = new Date(now); w.setDate(now.getDate() - 6);
    params.from = _toIsoDate(w);
  }
  return params;
};

const exportCsv = async () => {
  exporting.value = true;
  try {
    const response = await api.get("/owner/orders/export/", {
      params: _buildExportParams(),
      responseType: "blob",
      headers: { Accept: "text/csv" },
    });
    const url = URL.createObjectURL(response.data);
    const a = document.createElement("a");
    a.href = url;
    a.download = `orders-${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch {
    toast.show(t("ownerOrders.exportFailed"), "error");
  } finally {
    exporting.value = false;
  }
};

// ── New-order alert ───────────────────────────────────────────────────────────
const knownOrderIds = ref(new Set());
const lastAlertTime = ref(0);
const RECURRING_ALERT_MS = 2 * 60 * 1000; // re-ping every 2 min while pending orders sit

const playAlertSound = () => {
  if (!soundEnabled.value) return;
  try {
    const ctx = _getAudioCtx();
    if (!ctx) return;
    // Resume if suspended (e.g., tab was backgrounded and context auto-suspended)
    const play = () => {
      [0, 0.18].forEach((delay, i) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.type = "sine";
        osc.frequency.setValueAtTime(i === 0 ? 780 : 980, ctx.currentTime + delay);
        gain.gain.setValueAtTime(0.35, ctx.currentTime + delay);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + delay + 0.25);
        osc.start(ctx.currentTime + delay);
        osc.stop(ctx.currentTime + delay + 0.25);
      });
    };
    if (ctx.state === "suspended") {
      ctx.resume().then(play).catch(() => {});
    } else {
      play();
    }
  } catch {
    // AudioContext not available
  }
};

const showBrowserNotification = (count) => {
  if (typeof window === "undefined" || !("Notification" in window)) return;
  if (Notification.permission !== "granted") return;
  new Notification(t(count === 1 ? "ownerOrders.newOrderNotifTitle_one" : "ownerOrders.newOrderNotifTitle_other", { count }), {
    body: t("ownerOrders.newOrderNotifBody"),
    icon: "/favicon.ico",
    tag: "new-order",
    renotify: true,
  });
};

const checkForNewOrders = (freshOrders) => {
  if (!knownOrderIds.value.size) {
    // First load — seed known IDs, no alert
    freshOrders.forEach((o) => knownOrderIds.value.add(o.id));
    return;
  }
  const newPending = freshOrders.filter(
    (o) => o.status === "pending" && !knownOrderIds.value.has(o.id),
  );
  freshOrders.forEach((o) => knownOrderIds.value.add(o.id));
  if (newPending.length) {
    playAlertSound();
    showBrowserNotification(newPending.length);
    toast.show(t(newPending.length === 1 ? "ownerOrders.newOrderNotifTitle_one" : "ownerOrders.newOrderNotifTitle_other", { count: newPending.length }), "info");
    lastAlertTime.value = Date.now();
  }
};

const requestNotificationPermission = async () => {
  if (typeof window === "undefined" || !("Notification" in window)) return;
  if (Notification.permission === "default") await Notification.requestPermission();
};

// ── Polling (visibility-aware) ────────────────────────────────────────────────
let pollTimer = null;

const doPoll = async () => {
  // Always fetch all orders (no status filter) — filtering is client-side only.
  // Passing activeStatus to the API would replace the full list with a subset,
  // making other status groups disappear until the next manual refresh.
  const fresh = await order.fetchOrders("", { silent: true });
  const orders = Array.isArray(fresh) ? fresh : order.orders;
  checkForNewOrders(orders);

  // Recurring alert: re-ping if there are still unhandled pending orders
  const hasPending = orders.some((o) => o.status === "pending");
  const cooldownPassed = Date.now() - lastAlertTime.value > RECURRING_ALERT_MS;
  if (hasPending && knownOrderIds.value.size > 0 && cooldownPassed) {
    playAlertSound();
    lastAlertTime.value = Date.now();
  }
};

const onPageVisible = () => {
  // Immediately refresh when the owner switches back to this tab
  if (typeof document !== "undefined" && document.visibilityState === "visible") {
    doPoll();
  }
};

onMounted(async () => {
  // Pre-populate search from ?q= query param (e.g. deep-linked from Ratings page)
  if (route.query.q) searchQuery.value = String(route.query.q);

  await requestNotificationPermission();
  const initial = await order.fetchOrders();
  checkForNewOrders(Array.isArray(initial) ? initial : order.orders);

  if (typeof document !== "undefined") {
    document.addEventListener("visibilitychange", onPageVisible);
  }

  pollTimer = setInterval(() => {
    // Skip the API call when the tab is in the background — runs on resume instead
    if (typeof document !== "undefined" && document.visibilityState === "hidden") return;
    doPoll();
  }, 15000); // 15 s — faster than layout's 30 s
});

onUnmounted(() => {
  clearInterval(pollTimer);
  if (typeof document !== "undefined") {
    document.removeEventListener("visibilitychange", onPageVisible);
  }
});
</script>
