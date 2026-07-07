<template>
  <section class="ui-page-shell space-y-3 pb-24 sm:pb-6">
    <!-- ── Header ──────────────────────────────────────────────────────────── -->
    <article class="ui-workspace-stage ui-reveal p-4 sm:p-5">
      <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div class="min-w-0 space-y-1">
          <p class="ui-kicker">{{ t("ownerCustomers.kicker") }}</p>
          <h1 class="ui-page-title">{{ t("ownerCustomers.title") }}</h1>
          <p class="text-xs text-slate-400 leading-relaxed">{{ t("ownerCustomers.subtitle") }}</p>
        </div>
        <!-- Summary stat chips (show once loaded) -->
        <div v-if="!loading && summary" class="flex shrink-0 flex-wrap gap-2" role="list" :aria-label="t('ownerCustomers.summaryLabel')">
          <div role="listitem" class="rounded-xl border border-slate-700/60 bg-slate-900/60 px-3 py-1.5 text-center min-w-[70px]">
            <p class="text-lg font-bold tabular-nums leading-none text-white">{{ summary.total }}</p>
            <p class="mt-0.5 text-[10px] uppercase tracking-wider text-slate-500">{{ t("ownerCustomers.statTotal") }}</p>
          </div>
          <div role="listitem" class="rounded-xl border border-emerald-500/30 bg-emerald-500/5 px-3 py-1.5 text-center min-w-[70px]">
            <p class="text-lg font-bold tabular-nums leading-none text-emerald-300">{{ summary.new }}</p>
            <p class="mt-0.5 text-[10px] uppercase tracking-wider text-emerald-600">{{ t("ownerCustomers.segmentNew") }}</p>
          </div>
          <div role="listitem" class="rounded-xl border border-sky-500/30 bg-sky-500/5 px-3 py-1.5 text-center min-w-[70px]">
            <p class="text-lg font-bold tabular-nums leading-none text-sky-300">{{ summary.returning }}</p>
            <p class="mt-0.5 text-[10px] uppercase tracking-wider text-sky-600">{{ t("ownerCustomers.segmentReturning") }}</p>
          </div>
          <div role="listitem" class="rounded-xl border border-amber-500/30 bg-amber-500/5 px-3 py-1.5 text-center min-w-[70px]">
            <p class="text-lg font-bold tabular-nums leading-none text-amber-300">{{ summary.at_risk }}</p>
            <p class="mt-0.5 text-[10px] uppercase tracking-wider text-amber-600">{{ t("ownerCustomers.segmentAtRisk") }}</p>
          </div>
        </div>
      </div>
    </article>

    <!-- ── Controls ────────────────────────────────────────────────────────── -->
    <div class="ui-reveal flex flex-col gap-2 sm:flex-row sm:items-center" style="--ui-delay: 50ms">
      <!-- Search -->
      <div class="relative flex-1 min-w-0">
        <AppIcon name="search" class="pointer-events-none absolute start-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" aria-hidden="true" />
        <input
          v-model="searchQuery"
          type="search"
          :placeholder="t('ownerCustomers.searchPlaceholder')"
          class="w-full rounded-xl border border-slate-700/60 bg-slate-900/60 py-2 ps-9 pe-8 text-sm text-slate-200 placeholder-slate-500 outline-none transition-colors focus:border-[color:var(--color-secondary)]/50 focus:ring-1 focus:ring-[color:var(--color-secondary)]/25 [&::-webkit-search-cancel-button]:hidden"
          :aria-label="t('ownerCustomers.searchPlaceholder')"
        />
        <button
          v-if="searchQuery"
          type="button"
          class="ui-touch-target absolute end-2 top-1/2 -translate-y-1/2 rounded-md p-1 text-slate-500 hover:text-slate-300 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[color:var(--color-secondary)]/60"
          :aria-label="t('ownerCustomers.searchClear')"
          @click="searchQuery = ''"
        >
          <AppIcon name="close" class="h-3.5 w-3.5" aria-hidden="true" />
        </button>
      </div>

      <!-- Sort -->
      <div class="flex shrink-0 items-center gap-2">
        <label for="customer-sort" class="text-xs text-slate-400 whitespace-nowrap">{{ t("ownerCustomers.sortByLabel") }}</label>
        <select
          id="customer-sort"
          v-model="sortKey"
          class="ui-input py-1.5 text-sm"
          :aria-label="t('ownerCustomers.sortByLabel')"
        >
          <option value="last_order">{{ t("ownerCustomers.sortLastOrder") }}</option>
          <option value="total_spend">{{ t("ownerCustomers.sortTotalSpend") }}</option>
          <option value="order_count">{{ t("ownerCustomers.sortOrderCount") }}</option>
        </select>
      </div>

      <!-- CSV export -->
      <button
        type="button"
        class="ui-btn-outline ui-press shrink-0 inline-flex items-center gap-1.5 px-3 py-2 text-sm"
        :disabled="exporting || loading"
        @click="exportCsv"
      >
        <AppIcon name="download" class="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
        {{ exporting ? t("ownerCustomers.exporting") : t("ownerCustomers.exportCsv") }}
      </button>
    </div>

    <!-- ── Tier filter chips ──────────────────────────────────────────────────── -->
    <div class="ui-reveal flex flex-wrap items-center gap-1.5" style="--ui-delay: 60ms">
      <span class="shrink-0 text-[11px] uppercase tracking-wider text-slate-500 me-0.5" aria-hidden="true">{{ t('ownerCustomers.tierFilterLabel') }}</span>
      <button
        v-for="tier in tierTabs"
        :key="tier.value"
        type="button"
        class="inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--color-secondary)]/60"
        :class="activeTier === tier.value
          ? 'border-[var(--color-secondary)]/60 bg-[var(--color-secondary)]/15 text-[var(--color-secondary)]'
          : 'border-slate-700/60 bg-slate-900/40 text-slate-400 hover:border-slate-600 hover:text-slate-200'"
        :aria-pressed="activeTier === tier.value"
        @click="activeTier = tier.value"
      >
        {{ tier.label }}
        <span
          v-if="tier.count !== null"
          class="tabular-nums"
          :class="activeTier === tier.value ? 'text-[var(--color-secondary)]/70' : 'text-slate-600'"
        >({{ tier.count }})</span>
      </button>
    </div>

    <!-- ── Segment filter chips ─────────────────────────────────────────────── -->
    <div class="ui-reveal flex flex-wrap gap-1.5" role="group" :aria-label="t('ownerCustomers.segmentFilterLabel')" style="--ui-delay: 80ms">
      <button
        v-for="seg in segments"
        :key="seg.value"
        type="button"
        class="inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--color-secondary)]/60"
        :class="activeSegment === seg.value
          ? 'border-[var(--color-secondary)]/60 bg-[var(--color-secondary)]/15 text-[var(--color-secondary)]'
          : 'border-slate-700/60 bg-slate-900/40 text-slate-400 hover:border-slate-600 hover:text-slate-200'"
        :aria-pressed="activeSegment === seg.value"
        @click="activeSegment = seg.value"
      >
        {{ seg.label }}
        <span
          v-if="seg.count !== null"
          class="tabular-nums"
          :class="activeSegment === seg.value ? 'text-[var(--color-secondary)]/70' : 'text-slate-600'"
        >({{ seg.count }})</span>
      </button>
    </div>

    <!-- ── Loading skeletons ────────────────────────────────────────────────── -->
    <div v-if="loading" class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3" aria-hidden="true">
      <div
        v-for="i in 6"
        :key="i"
        class="animate-pulse space-y-3 rounded-2xl border border-slate-800 bg-slate-900/60 p-4"
      >
        <div class="flex items-center gap-3">
          <div class="h-10 w-10 shrink-0 rounded-xl bg-slate-700/50" />
          <div class="min-w-0 flex-1 space-y-2">
            <div class="h-3 w-3/4 rounded bg-slate-700/50" />
            <div class="h-2.5 w-1/2 rounded bg-slate-700/30" />
          </div>
        </div>
        <div class="grid grid-cols-3 gap-2">
          <div v-for="j in 3" :key="j" class="space-y-1.5">
            <div class="h-4 rounded bg-slate-700/40" />
            <div class="h-2.5 rounded bg-slate-700/25" />
          </div>
        </div>
      </div>
    </div>

    <!-- ── Error ────────────────────────────────────────────────────────────── -->
    <div
      v-else-if="fetchError"
      class="ui-reveal rounded-2xl border border-red-500/30 bg-red-500/10 p-6 text-center"
      role="alert"
    >
      <p class="text-sm font-semibold text-red-300">{{ t("ownerCustomers.loadError") }}</p>
      <button type="button" class="mt-3 ui-btn-outline ui-press inline-flex items-center gap-1.5 px-4 py-2 text-sm" @click="loadCustomers">
        <AppIcon name="refresh" class="h-3.5 w-3.5" aria-hidden="true" />
        {{ t("common.retry") }}
      </button>
    </div>

    <!-- ── Empty state ──────────────────────────────────────────────────────── -->
    <div
      v-else-if="!loading && filteredCustomers.length === 0"
      class="ui-reveal ui-empty-state text-center space-y-2"
    >
      <div class="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-800/60">
        <AppIcon name="users" class="h-6 w-6 text-slate-500" aria-hidden="true" />
      </div>
      <p class="text-sm font-semibold text-slate-300">
        {{ searchQuery || activeSegment || activeTier ? t("ownerCustomers.noResults") : t("ownerCustomers.emptyState") }}
      </p>
      <p v-if="!searchQuery && !activeSegment && !activeTier" class="text-xs text-slate-500">{{ t("ownerCustomers.emptyStateHint") }}</p>
    </div>

    <!-- ── Customer cards ───────────────────────────────────────────────────── -->
    <ul v-else class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3" role="list">
      <li
        v-for="c in filteredCustomers"
        :key="c.id"
        class="ui-command-deck ui-reveal rounded-2xl border border-slate-800/80 bg-slate-950/60 p-4 space-y-3"
      >
        <!-- Card header: avatar + name + badges -->
        <div class="flex items-start gap-3">
          <!-- Avatar (initials) -->
          <div
            class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-sm font-bold uppercase leading-none select-none"
            :class="segmentAvatarClass(c.segment)"
            aria-hidden="true"
          >
            {{ initials(c.name) }}
          </div>

          <div class="min-w-0 flex-1 space-y-1">
            <p class="truncate text-sm font-semibold text-slate-100" :title="c.name">{{ c.name }}</p>
            <div class="flex flex-wrap items-center gap-1.5">
              <!-- Type badge -->
              <span
                class="rounded-full border px-1.5 py-0.5 text-[10px] font-medium leading-none"
                :class="c.type === 'account'
                  ? 'border-sky-500/40 bg-sky-500/10 text-sky-400'
                  : 'border-slate-600/50 bg-slate-800/40 text-slate-400'"
              >
                {{ c.type === 'account' ? t("ownerCustomers.typeAccount") : t("ownerCustomers.typeAnonymous") }}
              </span>
              <!-- Segment badge -->
              <span
                class="rounded-full border px-1.5 py-0.5 text-[10px] font-medium leading-none"
                :class="segmentBadgeClass(c.segment)"
              >
                {{ segmentLabel(c.segment) }}
              </span>
              <!-- Tier badge -->
              <span
                v-if="c.order_count > 0"
                class="rounded-full border px-1.5 py-0.5 text-[10px] font-semibold leading-none"
                :class="customerTierClass(c)"
              >
                {{ customerTierLabel(c) }}
              </span>
            </div>
          </div>
        </div>

        <!-- Contact row -->
        <div v-if="c.phone || c.email" class="flex flex-wrap items-center gap-2 text-xs">
          <!-- Phone -->
          <div v-if="c.phone" class="flex items-center gap-1">
            <a :href="`tel:${c.phone}`" class="flex items-center gap-1 text-sky-400 hover:text-sky-300 transition-colors" :title="t('ownerCustomers.callLabel')">
              <AppIcon name="phone" class="h-3 w-3 shrink-0" aria-hidden="true" />
              <span class="tabular-nums">{{ c.phone }}</span>
            </a>
            <!-- WhatsApp -->
            <a
              :href="whatsappUrl(c.phone)"
              target="_blank"
              rel="noopener noreferrer"
              class="ml-1 flex items-center rounded-full border border-emerald-500/30 bg-emerald-500/10 px-1.5 py-0.5 text-[10px] font-medium text-emerald-400 hover:bg-emerald-500/20 transition-colors"
              :aria-label="t('ownerCustomers.whatsappLabel')"
            >WA</a>
          </div>
          <!-- Email -->
          <a
            v-if="c.email"
            :href="`mailto:${c.email}`"
            class="truncate text-slate-400 hover:text-slate-200 transition-colors max-w-[160px]"
            :title="c.email"
          >{{ c.email }}</a>
        </div>

        <!-- Stats grid -->
        <div class="grid grid-cols-3 gap-2 rounded-xl border border-slate-800/60 bg-slate-900/40 px-3 py-2.5">
          <div class="space-y-0.5 text-center">
            <p class="text-base font-bold tabular-nums text-slate-100 leading-none">{{ c.order_count }}</p>
            <p class="text-[10px] uppercase tracking-wide text-slate-500">{{ t("ownerCustomers.colOrders") }}</p>
          </div>
          <div class="space-y-0.5 text-center">
            <p class="text-base font-bold tabular-nums text-slate-100 leading-none">{{ formatAmount(c.total_spend, c.currency) }}</p>
            <p class="text-[10px] uppercase tracking-wide text-slate-500">{{ t("ownerCustomers.colSpend") }}</p>
          </div>
          <div class="space-y-0.5 text-center">
            <p class="text-base font-bold tabular-nums text-slate-100 leading-none">{{ formatAmount(c.avg_order_value, c.currency) }}</p>
            <p class="text-[10px] uppercase tracking-wide text-slate-500">{{ t("ownerCustomers.colAvg") }}</p>
          </div>
        </div>

        <!-- Secondary stats row: wallet, review, trust, last order -->
        <div class="flex flex-wrap items-center gap-2 text-[11px] text-slate-400">
          <!-- Wallet (account type only) -->
          <span
            v-if="c.type === 'account' && c.wallet_balance !== undefined"
            class="flex items-center gap-1 rounded-full border border-emerald-500/25 bg-emerald-500/8 px-2 py-0.5"
            :class="parseFloat(c.wallet_balance) > 0 ? 'text-emerald-400' : 'text-slate-500'"
          >
            <AppIcon name="wallet" class="h-3 w-3 shrink-0" aria-hidden="true" />
            {{ formatAmount(parseFloat(c.wallet_balance || 0), c.currency) }}
          </span>
          <!-- Loyalty points (account type only) -->
          <span
            v-if="c.type === 'account' && c.loyalty_points > 0"
            class="flex items-center gap-0.5 rounded-full border border-indigo-500/30 bg-indigo-500/8 px-2 py-0.5 text-indigo-300"
            :title="t('ownerCustomers.loyaltyBadge')"
          >
            <svg viewBox="0 0 16 16" fill="currentColor" class="h-3 w-3 shrink-0" aria-hidden="true">
              <path d="M8 1l1.6 3.2L13 5l-2.5 2.4.6 3.6L8 9.4l-3.1 1.6.6-3.6L3 5l3.4-.8z"/>
            </svg>
            <span class="tabular-nums font-medium">{{ c.loyalty_points }}</span>
            <span class="text-indigo-400/60">{{ t('ownerCustomers.loyaltyBadge') }}</span>
          </span>
          <!-- Avg review -->
          <span v-if="c.avg_review !== null && c.avg_review !== undefined" class="flex items-center gap-0.5">
            <AppIcon name="star" class="h-3 w-3 shrink-0 text-amber-400" aria-hidden="true" />
            <span class="tabular-nums font-medium text-amber-300">{{ c.avg_review.toFixed(1) }}</span>
            <span class="text-slate-600">({{ c.review_count }})</span>
          </span>
          <!-- Trust score -->
          <span v-if="c.trust_score !== null && c.trust_score !== undefined" class="flex items-center gap-0.5 text-slate-500" :title="t('ownerCustomers.trustHint')">
            <svg viewBox="0 0 16 16" fill="currentColor" class="h-3 w-3 shrink-0 text-slate-500" aria-hidden="true">
              <path d="M8 1l1.8 3.6L14 5.2l-3 2.9.7 4.1L8 10.2l-3.7 2 .7-4.1-3-2.9 4.2-.6z"/>
            </svg>
            <span class="tabular-nums">{{ c.trust_score.toFixed(1) }}</span>
          </span>
          <!-- Last order date -->
          <span class="ms-auto shrink-0 text-slate-600" :title="c.last_order_at ? formatDate(c.last_order_at, true) : ''">
            {{ c.last_order_at ? formatDate(c.last_order_at) : t("ownerCustomers.lastOrderNever") }}
          </span>
        </div>

        <!-- Private notes row -->
        <div class="space-y-1.5">
          <!-- Notes display / edit toggle -->
          <div v-if="!notesEditingId || notesEditingId !== c.id" class="flex items-start gap-1.5">
            <p
              v-if="c.owner_notes"
              class="flex-1 rounded-lg border border-slate-700/40 bg-slate-800/30 px-2.5 py-1.5 text-[11px] leading-relaxed text-slate-400 whitespace-pre-line"
            >{{ c.owner_notes }}</p>
            <button
              type="button"
              class="shrink-0 rounded-md border border-slate-700/50 px-2 py-1 text-[10px] font-medium text-slate-500 hover:border-slate-600 hover:text-slate-300 transition-colors"
              @click="startEditingNotes(c)"
            >
              {{ c.owner_notes ? t("ownerCustomers.notesEdit") : t("ownerCustomers.notesAdd") }}
            </button>
          </div>
          <!-- Inline editor -->
          <div v-else class="space-y-1.5">
            <textarea
              v-model="notesDraft"
              rows="2"
              class="ui-input w-full resize-none text-[11px]"
              :placeholder="t('ownerCustomers.notesPlaceholder')"
              @keydown.esc="cancelNotesEdit"
            />
            <div class="flex items-center justify-end gap-2">
              <button
                type="button"
                class="px-2.5 py-1 text-[10px] font-medium text-slate-500 hover:text-slate-300 transition-colors"
                @click="cancelNotesEdit"
              >{{ t("common.cancel") }}</button>
              <button
                type="button"
                class="rounded-md border border-[var(--color-secondary)]/50 bg-[var(--color-secondary)]/10 px-2.5 py-1 text-[10px] font-semibold text-[var(--color-secondary)] hover:bg-[var(--color-secondary)]/20 transition-colors disabled:opacity-50"
                :disabled="notesSaving"
                @click="saveNotes(c)"
              >{{ notesSaving ? t("common.loading") : t("ownerCustomers.notesSave") }}</button>
            </div>
          </div>
        </div>

        <!-- Action row: loyalty grant (account-type only) -->
        <div v-if="c.type === 'account'" class="flex items-center justify-end">
          <button
            type="button"
            class="inline-flex items-center gap-1.5 rounded-lg border border-indigo-500/30 bg-indigo-500/8 px-2.5 py-1 text-[10px] font-semibold text-indigo-400 hover:border-indigo-500/50 hover:bg-indigo-500/15 transition-colors"
            @click="openGrantPoints(c)"
          >
            <svg aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" class="h-3 w-3">
              <circle cx="8" cy="8" r="6.5" />
              <path d="M8 5v6M5.5 7.5l2.5-2.5 2.5 2.5" />
            </svg>
            {{ t("ownerCustomers.grantPointsBtn") }}
          </button>
        </div>
      </li>
    </ul>

    <!-- Grant points modal -->
    <Teleport to="body">
      <div v-if="grantModal.open" class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm px-4" @click.self="closeGrantModal" @keydown.esc="closeGrantModal">
        <div class="ui-panel-soft w-full max-w-xs space-y-4 p-5" role="dialog" aria-modal="true" :aria-labelledby="`grant-modal-title-${grantModal.customerId}`">
          <div class="flex items-center justify-between">
            <h2 :id="`grant-modal-title-${grantModal.customerId}`" class="text-sm font-bold text-white">{{ t("ownerCustomers.grantPointsTitle") }}</h2>
            <button type="button" class="ui-icon-btn" :aria-label="t('common.close')" @click="closeGrantModal">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" class="h-4 w-4" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18"/></svg>
            </button>
          </div>
          <p class="text-xs text-slate-400">{{ grantModal.customerName }}</p>
          <div class="space-y-3">
            <div class="space-y-1">
              <label :for="`grant-delta-${grantModal.customerId}`" class="block text-xs font-semibold text-slate-300">{{ t("ownerCustomers.grantPointsDeltaLabel") }}</label>
              <input
                :id="`grant-delta-${grantModal.customerId}`"
                v-model="grantModal.delta"
                type="number"
                step="1"
                class="ui-input w-full"
              />
            </div>
            <div class="space-y-1">
              <label :for="`grant-reason-${grantModal.customerId}`" class="block text-xs font-semibold text-slate-300">{{ t("ownerCustomers.grantPointsReasonLabel") }}</label>
              <input
                :id="`grant-reason-${grantModal.customerId}`"
                v-model="grantModal.reason"
                type="text"
                class="ui-input w-full"
              />
            </div>
            <div v-if="grantModal.error" class="rounded-lg border border-red-500/30 bg-red-500/8 px-3 py-2 text-xs text-red-300" role="alert">{{ grantModal.error }}</div>
          </div>
          <div class="flex gap-2">
            <button type="button" class="flex-1 rounded-xl border border-slate-700/60 px-3 py-2 text-xs font-medium text-slate-400 hover:text-slate-200 transition-colors" @click="closeGrantModal">{{ t("common.cancel") }}</button>
            <button
              type="button"
              class="flex-1 ui-btn-primary justify-center text-xs disabled:opacity-50"
              :disabled="grantModal.loading"
              @click="submitGrantPoints"
            >{{ grantModal.loading ? t("common.loading") : t("ownerCustomers.grantPointsSubmit") }}</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Load more / end-of-list -->
    <div v-if="!loading && !fetchError && customers.length" class="py-2 text-center space-y-2">
      <button
        v-if="hasMore"
        type="button"
        class="ui-btn-outline ui-press inline-flex items-center gap-2 px-5 py-2 text-sm"
        :disabled="loadingMore"
        :aria-busy="loadingMore"
        @click="loadMore"
      >
        <span v-if="loadingMore" class="inline-block h-3.5 w-3.5 animate-spin rounded-full border border-current border-t-transparent" aria-hidden="true" />
        {{ loadingMore ? t("ownerCustomers.loadingMore") : t("ownerCustomers.loadMore") }}
      </button>
      <p v-else class="text-xs text-slate-600">
        {{ t("ownerCustomers.resultCount", { n: filteredCustomers.length }) }}
        <span v-if="!hasMore && currentOffset > filteredCustomers.length" class="ms-1">· {{ t("ownerCustomers.noMore") }}</span>
      </p>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import AppIcon from "../components/AppIcon.vue";
import { useI18n } from "../composables/useI18n";
import { useToastStore } from "../stores/toast";
import api from "../lib/api";

const { t } = useI18n();
const toast = useToastStore();

// ── State ────────────────────────────────────────────────────────────────────
const loading = ref(true);          // initial / reset load
const loadingMore = ref(false);     // "Load more" spinner
const fetchError = ref(false);
const exporting = ref(false);
const customers = ref([]);
const summary = ref(null);
const hasMore = ref(false);
const currentOffset = ref(0);
const PAGE_LIMIT = 100;

// Filters — changes trigger a server reload (not a JS filter)
const searchQuery = ref("");
const activeSegment = ref("");
const activeTier = ref("");
const sortKey = ref("last_order");

// ── Debounced search ──────────────────────────────────────────────────────────
let _searchTimer = null;
watch(searchQuery, () => {
  clearTimeout(_searchTimer);
  _searchTimer = setTimeout(() => {
    loadCustomers(true);
  }, 350);
});

// ── Params builder ────────────────────────────────────────────────────────────
const _buildParams = (offset = 0) => {
  const params = { limit: PAGE_LIMIT, offset };
  if (searchQuery.value.trim()) params.search = searchQuery.value.trim();
  if (activeSegment.value) params.segment = activeSegment.value;
  if (sortKey.value) params.sort = sortKey.value;
  return params;
};

// ── Data loading ─────────────────────────────────────────────────────────────
// reset=true: start from page 0, clear the list (used when filters change).
// reset=false: append the next page (Load more).
const loadCustomers = async (reset = false) => {
  if (reset) {
    loading.value = true;
    fetchError.value = false;
    currentOffset.value = 0;
    customers.value = [];
    hasMore.value = false;
  } else {
    loadingMore.value = true;
  }
  try {
    const { data } = await api.get("/owner/customers/", {
      params: _buildParams(currentOffset.value),
    });
    // Backend returns { results, has_more, limit, offset } plus optional summary
    const page = Array.isArray(data.results) ? data.results : [];
    if (reset) {
      customers.value = page;
      // Summary is returned on first page only (it's a global aggregate)
      if (data.summary !== undefined) summary.value = data.summary;
    } else {
      customers.value = [...customers.value, ...page];
    }
    hasMore.value = Boolean(data.has_more);
    currentOffset.value += page.length;
  } catch {
    if (!customers.value.length) fetchError.value = true;
  } finally {
    loading.value = false;
    loadingMore.value = false;
  }
};

const loadMore = () => {
  if (loadingMore.value || !hasMore.value) return;
  loadCustomers(false);
};

onMounted(() => loadCustomers(true));

// Reload when segment, tier, or sort changes
watch([activeSegment, sortKey], () => loadCustomers(true));
// Tier filter is client-side only (no backend param), don't reload for it

// ── Segments ─────────────────────────────────────────────────────────────────
// Segment counts come from the summary object (returned by backend)
const segments = computed(() => [
  { value: "",          label: t("ownerCustomers.segmentAll"),       count: summary.value?.total ?? customers.value.length },
  { value: "new",       label: t("ownerCustomers.segmentNew"),       count: summary.value?.new ?? null },
  { value: "returning", label: t("ownerCustomers.segmentReturning"), count: summary.value?.returning ?? null },
  { value: "at_risk",   label: t("ownerCustomers.segmentAtRisk"),    count: summary.value?.at_risk ?? null },
]);

// ── Tiers ─────────────────────────────────────────────────────────────────────
// Tier is still client-side — computed from order_count on loaded rows
const _tierKey = (c) => c.order_count >= 10 ? "vip" : c.order_count >= 3 ? "regular" : "new";

const customerTierLabel = (c) => {
  const k = _tierKey(c);
  if (k === "vip") return t("ownerCustomers.tierVIP");
  if (k === "regular") return t("ownerCustomers.tierRegular");
  return t("ownerCustomers.tierNew");
};

const customerTierClass = (c) => {
  const k = _tierKey(c);
  if (k === "vip") return "border-amber-500/50 bg-amber-500/10 text-amber-400";
  if (k === "regular") return "border-sky-500/40 bg-sky-500/10 text-sky-400";
  return "border-slate-600/50 bg-slate-800/40 text-slate-500";
};

const tierTabs = computed(() => {
  const all = customers.value;
  const counts = { vip: 0, regular: 0, new: 0 };
  all.forEach((c) => { if (c.order_count > 0) counts[_tierKey(c)]++; });
  return [
    { value: "",        label: t("ownerCustomers.segmentAll"),   count: all.length },
    { value: "vip",     label: t("ownerCustomers.tierVIP"),      count: counts.vip },
    { value: "regular", label: t("ownerCustomers.tierRegular"),  count: counts.regular },
    { value: "new",     label: t("ownerCustomers.tierNew"),      count: counts.new },
  ];
});

// ── Client-side filtering (tier only — search/segment/sort are server-side) ──
const filteredCustomers = computed(() => {
  let list = customers.value;
  // Tier filter is client-side so no extra round-trip for a simple count threshold
  if (activeTier.value) {
    list = list.filter((c) => _tierKey(c) === activeTier.value);
  }
  return list;
});

// ── CSV export ────────────────────────────────────────────────────────────────
const exportCsv = async () => {
  if (exporting.value) return;
  exporting.value = true;
  try {
    const resp = await api.get("/owner/customers/", {
      params: { format: "csv", search: searchQuery.value.trim() || undefined, segment: activeSegment.value || undefined },
      responseType: "blob",
    });
    const url = URL.createObjectURL(new Blob([resp.data]));
    const a = document.createElement("a");
    a.href = url;
    a.download = "customers.csv";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch {
    toast.show(t("ownerCustomers.exportError"), "error");
  } finally {
    exporting.value = false;
  }
};

// ── Formatting helpers ────────────────────────────────────────────────────────
const initials = (name) => {
  if (!name || name === "—") return "?";
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() || "")
    .join("");
};

const formatAmount = (val, currency) => {
  if (val === null || val === undefined || isNaN(val)) return "—";
  const code = (currency || "").toUpperCase();
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: code || "MAD",
      maximumFractionDigits: 0,
    }).format(val);
  } catch {
    return `${code} ${Number(val).toFixed(0)}`;
  }
};

const formatDate = (iso, full = false) => {
  if (!iso) return "";
  try {
    return new Intl.DateTimeFormat(undefined, full ? { dateStyle: "long" } : { dateStyle: "short" }).format(new Date(iso));
  } catch {
    return iso.slice(0, 10);
  }
};

const whatsappUrl = (phone) => {
  const digits = String(phone).replace(/\D/g, "");
  return `https://wa.me/${digits}`;
};

// ── Customer notes ────────────────────────────────────────────────────────────
const notesEditingId = ref(null);  // card id currently being edited
const notesDraft = ref("");
const notesSaving = ref(false);

const startEditingNotes = (c) => {
  notesEditingId.value = c.id;
  notesDraft.value = c.owner_notes || "";
};
const cancelNotesEdit = () => {
  notesEditingId.value = null;
  notesDraft.value = "";
};
const saveNotes = async (c) => {
  if (notesSaving.value) return;
  if (!c.customer_id) { cancelNotesEdit(); return; }
  notesSaving.value = true;
  try {
    const res = await api.patch(`/owner/customers/${c.customer_id}/notes/`, { notes: notesDraft.value });
    // update in-place so the card reflects the saved note immediately
    const idx = customers.value.findIndex((x) => x.id === c.id);
    if (idx >= 0) customers.value[idx] = { ...customers.value[idx], owner_notes: res.data.notes };
    toast.show(t("ownerCustomers.notesSaved"), "success");
    cancelNotesEdit();
  } catch {
    toast.show(t("ownerCustomers.notesError"), "error");
  } finally {
    notesSaving.value = false;
  }
};

// ── Loyalty point grant ───────────────────────────────────────────────────────
const grantModal = reactive({
  open: false,
  customerId: null,
  customerName: "",
  delta: "",
  reason: "",
  loading: false,
  error: "",
});

const openGrantPoints = (c) => {
  grantModal.open = true;
  grantModal.customerId = c.customer_id;
  grantModal.customerName = c.name;
  grantModal.delta = "";
  grantModal.reason = "";
  grantModal.loading = false;
  grantModal.error = "";
};
const closeGrantModal = () => {
  grantModal.open = false;
};
const submitGrantPoints = async () => {
  if (grantModal.loading) return;
  const delta = parseInt(grantModal.delta, 10);
  if (Number.isNaN(delta)) {
    grantModal.error = t("ownerCustomers.grantPointsInvalid");
    return;
  }
  grantModal.loading = true;
  grantModal.error = "";
  try {
    const res = await api.post(`/owner/customers/${grantModal.customerId}/loyalty-grant/`, {
      delta,
      reason: grantModal.reason.trim(),
    });
    // update in-place so the card reflects the new balance immediately
    const idx = customers.value.findIndex((x) => x.customer_id === grantModal.customerId);
    if (idx >= 0) customers.value[idx] = { ...customers.value[idx], loyalty_points: res.data.loyalty_points };
    toast.show(t("ownerCustomers.grantPointsSuccess"), "success");
    closeGrantModal();
  } catch {
    grantModal.error = t("ownerCustomers.grantPointsError");
    grantModal.loading = false;
  }
};

// ── Segment classes ───────────────────────────────────────────────────────────
const segmentAvatarClass = (seg) => {
  if (seg === "new") return "bg-emerald-500/15 text-emerald-300";
  if (seg === "returning") return "bg-sky-500/15 text-sky-300";
  if (seg === "at_risk") return "bg-amber-500/15 text-amber-300";
  return "bg-slate-700/50 text-slate-400";
};

const segmentBadgeClass = (seg) => {
  if (seg === "new") return "border-emerald-500/40 bg-emerald-500/10 text-emerald-400";
  if (seg === "returning") return "border-sky-500/40 bg-sky-500/10 text-sky-400";
  if (seg === "at_risk") return "border-amber-500/40 bg-amber-500/10 text-amber-400";
  return "border-slate-600/40 bg-slate-800/30 text-slate-400";
};

const segmentLabel = (seg) => {
  if (seg === "new") return t("ownerCustomers.segTagNew");
  if (seg === "returning") return t("ownerCustomers.segTagReturning");
  if (seg === "at_risk") return t("ownerCustomers.segTagAtRisk");
  return seg;
};
</script>
