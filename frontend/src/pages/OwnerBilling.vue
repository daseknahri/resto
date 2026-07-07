<template>
  <div class="space-y-4 sm:space-y-5">

    <!-- ── Current plan ──────────────────────────────────────────────── -->
    <section class="ui-panel ui-reveal space-y-4 p-4">
      <div class="space-y-0.5">
        <p class="ui-section-kicker">{{ t('ownerBilling.currentPlanSection') }}</p>
        <h2 class="ui-display text-lg font-semibold text-white">{{ t('ownerBilling.yourPlan') }}</h2>
      </div>

      <div class="ui-glass p-4">
        <div class="flex flex-wrap items-start justify-between gap-4">
          <div class="space-y-3">
            <div class="flex flex-wrap items-center gap-3">
              <span class="ui-chip-strong">
                {{ currentTierName }}
              </span>
              <span class="ui-status-pill">
                {{ t('ownerBilling.active') }}
              </span>
            </div>
            <ul class="grid grid-cols-1 gap-x-6 gap-y-1.5 sm:grid-cols-2">
              <li
                v-for="f in currentPlanFeatures"
                :key="f.label"
                class="flex items-center gap-2 text-sm"
              >
                <svg v-if="f.ok" aria-hidden="true" viewBox="0 0 16 16" class="h-3.5 w-3.5 shrink-0 text-emerald-400" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M3 8l4 4 6-7"/>
                </svg>
                <svg v-else aria-hidden="true" viewBox="0 0 16 16" class="h-3.5 w-3.5 shrink-0 text-slate-600" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M4 12l8-8M12 12L4 4"/>
                </svg>
                <span :class="f.ok ? 'text-slate-200' : 'text-slate-500'">{{ f.label }}</span>
                <span class="sr-only">{{ f.ok ? t('common.included') : t('common.notIncluded') }}</span>
              </li>
            </ul>
          </div>
        </div>
      </div>

      <!-- Usage limits (only shown when plan has limits set) -->
      <div v-if="usageLimits.length" class="space-y-3">
        <p class="ui-section-kicker">{{ t('ownerBilling.usageTitle') }}</p>
        <div class="space-y-3">
          <div v-for="u in usageLimits" :key="u.key" class="space-y-1.5">
            <div class="flex items-center justify-between text-sm">
              <span class="text-slate-300">{{ u.label }}</span>
              <span class="tabular-nums" :class="u.pct >= 100 ? 'font-semibold text-red-400' : u.pct >= 80 ? 'text-amber-300' : 'text-slate-400'">
                {{ u.current }} / {{ u.limit }}
              </span>
            </div>
            <div
              class="h-1.5 w-full rounded-full bg-slate-800"
              role="progressbar"
              :aria-valuenow="u.current"
              :aria-valuemin="0"
              :aria-valuemax="u.limit"
              :aria-label="u.label"
            >
              <div
                class="h-1.5 rounded-full transition-all duration-500"
                :class="u.pct >= 100 ? 'bg-red-500' : u.pct >= 80 ? 'bg-amber-400' : 'bg-emerald-500/80'"
                :style="{ width: Math.min(u.pct, 100) + '%' }"
              />
            </div>
            <p v-if="u.pct >= 100" class="text-xs text-red-400" role="alert">
              {{ t('ownerBilling.limitReached', { label: u.label }) }}
            </p>
          </div>
        </div>
      </div>

      <div
        v-if="hasPendingRequest"
        class="flex items-start gap-3 rounded-xl border border-amber-500/30 bg-amber-500/8 px-4 py-3"
        role="status"
      >
        <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-amber-400" fill="currentColor">
          <path fill-rule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/>
        </svg>
        <p class="text-sm text-amber-200">{{ t('ownerBilling.pendingRequestNote') }}</p>
      </div>
    </section>

    <!-- ── Available upgrades ─────────────────────────────────────────── -->
    <section v-if="loading" class="ui-panel p-4 ui-reveal" style="--ui-delay: 56ms">
      <div class="mb-3 space-y-1">
        <div class="h-2.5 w-20 animate-pulse rounded bg-slate-700/50" />
        <div class="h-5 w-40 animate-pulse rounded bg-slate-700/60" />
      </div>
      <div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <div v-for="i in 2" :key="i" class="animate-pulse space-y-3 rounded-2xl border border-slate-700/40 bg-slate-900/40 p-4">
          <div class="h-5 w-24 rounded-full bg-slate-700/60" />
          <div class="space-y-2">
            <div v-for="j in 4" :key="j" class="flex items-center gap-2">
              <div class="h-3.5 w-3.5 rounded-full bg-slate-700/50" />
              <div class="h-3 rounded bg-slate-800/60" :style="`width: ${80 + j * 20}px`" />
            </div>
          </div>
          <div class="h-9 rounded-xl bg-slate-700/40" />
        </div>
      </div>
    </section>

    <section v-else-if="targets.length" class="ui-panel ui-reveal space-y-4 p-4" style="--ui-delay: 56ms">
      <div class="space-y-0.5">
        <p class="ui-section-kicker">{{ t('ownerBilling.upgradeSection') }}</p>
        <h2 class="ui-display text-lg font-semibold text-white">{{ t('ownerBilling.upgradeTitle') }}</h2>
        <p class="ui-subtle">{{ t('ownerBilling.upgradeHint') }}</p>
      </div>

      <div
        class="grid gap-4"
        :class="targets.length === 1 ? 'max-w-sm' : targets.length === 2 ? 'sm:grid-cols-2' : 'sm:grid-cols-2 xl:grid-cols-3'"
      >
        <button
          v-for="target in targets"
          :key="target.code"
          type="button"
          class="relative rounded-2xl border p-4 text-start transition-all duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/50 disabled:cursor-not-allowed disabled:opacity-40 ui-press"
          :class="selectedCode === target.code
            ? 'border-[var(--color-secondary)] ring-2 ring-[var(--color-secondary)]/20 bg-[var(--color-secondary)]/6'
            : 'border-slate-700 bg-slate-900/50 hover:border-slate-500 hover:bg-slate-900/80'"
          :disabled="!target.can_request || hasPendingRequest"
          :aria-pressed="selectedCode === target.code"
          :aria-label="target.name"
          @click="selectedCode === target.code ? (selectedCode = '') : (selectedCode = target.code)"
        >
          <!-- Selected badge -->
          <div
            v-if="selectedCode === target.code"
            class="absolute end-3 top-3 flex h-5 w-5 items-center justify-center rounded-full bg-[var(--color-secondary)] text-slate-950"
            aria-hidden="true"
          >
            <svg aria-hidden="true" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" class="h-3 w-3">
              <path d="M2 6l3 3 5-5"/>
            </svg>
          </div>

          <!-- Coming soon badge -->
          <span
            v-if="!target.is_active"
            class="absolute start-3 top-3 rounded-full border border-sky-700/50 bg-sky-900/30 px-2 py-0.5 text-[10px] font-semibold text-sky-400"
          >
            {{ t('common.soon') }}
          </span>

          <div class="space-y-4 pe-6">
            <div>
              <span class="rounded-full border border-slate-600 bg-slate-800 px-3 py-1 text-[11px] font-bold uppercase tracking-widest text-slate-200">
                {{ target.name }}
              </span>
            </div>
            <ul class="space-y-2">
              <li
                v-for="f in targetFeatures(target)"
                :key="f.label"
                class="flex items-center gap-2.5 text-xs"
              >
                <svg v-if="f.ok" aria-hidden="true" viewBox="0 0 16 16" class="h-3.5 w-3.5 shrink-0 text-emerald-400" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M3 8l4 4 6-7"/>
                </svg>
                <svg v-else aria-hidden="true" viewBox="0 0 16 16" class="h-3.5 w-3.5 shrink-0 text-slate-700" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M4 12l8-8M12 12L4 4"/>
                </svg>
                <span :class="f.ok ? 'text-slate-200' : 'text-slate-600'">{{ f.label }}</span>
                <span class="sr-only">{{ f.ok ? t('common.included') : t('common.notIncluded') }}</span>
              </li>
            </ul>
          </div>
        </button>
      </div>

      <!-- Upgrade request form -->
      <Transition name="billing-form">
        <div
          v-if="selectedCode && !hasPendingRequest"
          class="overflow-hidden rounded-2xl border border-slate-700 bg-slate-900/70"
        >
          <div class="space-y-4 p-4">
            <div class="space-y-0.5">
              <p class="text-sm font-semibold text-white">
                {{ t('ownerBilling.requestFormTitle', { plan: selectedPlanName }) }}
              </p>
              <p class="ui-subtle text-xs">{{ t('ownerBilling.requestFormHint') }}</p>
            </div>
            <textarea
              v-model="note"
              rows="3"
              maxlength="500"
              :aria-label="t('ownerBilling.notePlaceholder')"
              :placeholder="t('ownerBilling.notePlaceholder')"
              class="ui-textarea w-full resize-none text-sm"
            />
            <p class="mt-1 text-end text-xs tabular-nums" :class="note.length >= 480 ? 'text-amber-400' : 'text-slate-600'" aria-live="polite">{{ note.length }}/500</p>
            <div v-if="submitError" role="alert" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5">
              <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
              <p class="flex-1 text-sm text-red-300">{{ submitError }}</p>
            </div>
            <div class="flex flex-wrap gap-3">
              <button
                type="button"
                class="ui-btn-primary inline-flex items-center gap-2 px-6 py-2 text-sm disabled:opacity-60"
                :disabled="submitting"
                :aria-busy="submitting"
                @click="submitRequest"
              >
                <svg v-if="submitting" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
                {{ submitting ? t('ownerBilling.sending') : t('ownerBilling.submitRequest') }}
              </button>
              <button type="button" class="ui-btn-outline px-4 py-2 text-sm" @click="selectedCode = ''">
                {{ t('common.cancel') }}
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </section>

    <section v-else-if="!loading" class="ui-panel ui-reveal p-4" style="--ui-delay: 56ms">
      <div class="ui-empty-state space-y-3 py-6 text-center">
        <div class="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl border border-amber-500/30 bg-amber-500/10 text-amber-400">
          <span class="text-xl leading-none" aria-hidden="true">★</span>
        </div>
        <p class="text-sm font-semibold text-slate-100">{{ t('ownerBilling.highestTier') }}</p>
      </div>
    </section>

    <!-- ── Request history ────────────────────────────────────────────── -->
    <section class="ui-panel ui-reveal space-y-4 p-4" style="--ui-delay: 84ms">
      <div class="flex items-center justify-between gap-3">
        <div class="space-y-0.5">
          <p class="ui-section-kicker">{{ t('ownerBilling.historySection') }}</p>
          <h2 class="ui-display text-lg font-semibold text-white">{{ t('ownerBilling.historyTitle') }}</h2>
        </div>
        <button
          type="button"
          class="ui-touch-target flex items-center justify-center rounded-lg border border-slate-700 text-slate-400 transition-colors hover:border-slate-500 hover:text-slate-200 disabled:opacity-50"
          :disabled="loading || updating"
          :aria-label="t('common.refresh')"
          :aria-busy="loading || updating"
          @click="fetchAll(true)"
        >
          <svg aria-hidden="true" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" class="h-4 w-4" :class="(loading || updating) ? 'animate-spin' : ''">
            <path d="M4 10a6 6 0 1 0 1.5-4M4 6v4h4"/>
          </svg>
        </button>
      </div>

      <div v-if="loading" class="space-y-2" aria-busy="true">
        <div v-for="i in 2" :key="i" class="animate-pulse rounded-xl border border-slate-800 bg-slate-900/40 p-4 min-h-[72px]">
          <div class="flex items-center justify-between gap-3">
            <div class="space-y-1.5">
              <div class="h-3.5 w-24 rounded bg-slate-700/60" />
              <div class="h-3 w-16 rounded bg-slate-800/50" />
            </div>
            <div class="h-5 w-16 rounded-full bg-slate-800/60" />
          </div>
        </div>
      </div>

      <div
        v-else-if="!requests.length"
        class="ui-empty-state py-10 text-center"
      >
        <svg aria-hidden="true" viewBox="0 0 40 40" class="mx-auto h-10 w-10 text-slate-600" fill="none" stroke="currentColor" stroke-width="1.25">
          <rect x="8" y="6" width="24" height="28" rx="3"/>
          <path d="M14 14h12M14 19h12M14 24h8" stroke-linecap="round"/>
        </svg>
        <p class="mt-3 text-sm text-slate-400">{{ t('ownerBilling.noRequests') }}</p>
      </div>

      <ul v-else class="space-y-2">
        <li
          v-for="(req, index) in requests"
          :key="req.id"
          class="ui-reveal rounded-xl border border-slate-800 bg-slate-900/50 p-3"
          :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
        >
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div class="min-w-0 flex-1 space-y-1.5">
              <div class="flex flex-wrap items-center gap-2">
                <span class="truncate text-sm font-medium text-slate-200">{{ req.current_plan_name }}</span>
                <svg aria-hidden="true" viewBox="0 0 20 12" class="h-3 w-4 shrink-0 text-slate-500 rtl:scale-x-[-1]" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M1 6h18M13 1l5 5-5 5"/>
                </svg>
                <span class="text-sm font-semibold text-[var(--color-secondary)]">{{ req.target_plan_name }}</span>
              </div>
              <p class="text-xs text-slate-500">{{ formatDateTime(req.requested_at) }}</p>
            </div>
            <span
              class="shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold"
              :class="requestStatusClass(req.status)"
            >
              {{ requestStatusLabel(req.status) }}
            </span>
          </div>
          <!-- Customer note -->
          <blockquote v-if="req.customer_note" class="mt-3 rounded-lg border border-slate-800 bg-slate-950/50 px-3 py-2 text-xs text-slate-400">
            "{{ req.customer_note }}"
          </blockquote>
          <!-- Admin note -->
          <div v-if="req.admin_note" class="mt-2 flex items-start gap-2 rounded-lg border border-slate-700/60 bg-slate-950/50 px-3 py-2 text-xs">
            <svg aria-hidden="true" viewBox="0 0 16 16" class="mt-0.5 h-3 w-3 shrink-0 text-slate-400" fill="none" stroke="currentColor" stroke-width="1.5">
              <rect x="2" y="2" width="12" height="12" rx="2"/>
              <path d="M5 6h6M5 9h4" stroke-linecap="round"/>
            </svg>
            <span class="text-slate-300">{{ req.admin_note }}</span>
          </div>
          <!-- Invoice download -->
          <div v-if="req.status === 'approved'" class="mt-3">
            <button
              v-if="req.invoice_amount"
              type="button"
              class="flex items-center gap-1.5 rounded-full border border-emerald-500/40 bg-emerald-500/10 px-3 py-1.5 text-xs font-medium text-emerald-300 transition-colors hover:bg-emerald-500/20 disabled:opacity-60"
              :disabled="downloadingInvoice === req.id"
              @click="downloadInvoice(req.id)"
            >
              <svg v-if="downloadingInvoice !== req.id" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" class="h-3.5 w-3.5">
                <path d="M8 3v7M5 7l3 3 3-3"/>
                <path d="M3 13h10"/>
              </svg>
              <svg v-else aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin">
                <path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/>
              </svg>
              {{ downloadingInvoice === req.id ? t('ownerBilling.invoiceDownloading') : t('ownerBilling.invoiceDownload') }}
            </button>
            <p v-else class="text-[11px] italic text-slate-500">{{ t('ownerBilling.invoiceNotReady') }}</p>
          </div>
        </li>
      </ul>
    </section>

    <!-- ── Data & privacy ──────────────────────────────────────────────── -->
    <section class="ui-panel ui-reveal space-y-4 p-4" style="--ui-delay: 112ms">
      <div class="space-y-0.5">
        <p class="ui-section-kicker">{{ t('ownerBilling.dataExportSection') }}</p>
        <h2 class="ui-display text-lg font-semibold text-white">{{ t('ownerBilling.dataExportTitle') }}</h2>
        <p class="ui-subtle">{{ t('ownerBilling.dataExportHint') }}</p>
      </div>

      <button
        type="button"
        class="ui-btn-outline inline-flex gap-2 px-4 py-2 text-sm disabled:opacity-60"
        :disabled="exporting"
        @click="downloadDataExport"
      >
        <svg v-if="!exporting" aria-hidden="true" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" class="h-4 w-4">
          <path d="M10 3v10M6 9l4 4 4-4"/>
          <path d="M4 17h12"/>
        </svg>
        <svg v-else aria-hidden="true" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-4 w-4 animate-spin">
          <path d="M4 10a6 6 0 1 0 1.5-4M4 6v4h4"/>
        </svg>
        {{ exporting ? t('ownerBilling.dataExporting') : t('ownerBilling.dataExportButton') }}
      </button>
    </section>

    <!-- ── Commission statement ─────────────────────────────────────────── -->
    <section class="ui-panel ui-reveal space-y-4 p-4" style="--ui-delay: 140ms">
      <div class="space-y-0.5">
        <p class="ui-section-kicker">{{ t('ownerBilling.commissionSection') }}</p>
        <h2 class="ui-display text-lg font-semibold text-white">{{ t('ownerBilling.commissionTitle') }}</h2>
        <p class="ui-subtle">{{ t('ownerBilling.commissionHint') }}</p>
      </div>
      <div class="flex flex-wrap items-end gap-3">
        <div class="space-y-1">
          <label for="commission-year" class="block text-xs font-medium text-slate-400">{{ t('ownerBilling.commissionYear') }}</label>
          <select id="commission-year" v-model="commissionYear" class="ui-input text-sm">
            <option v-for="y in commissionYears" :key="y" :value="y">{{ y }}</option>
          </select>
        </div>
        <div class="space-y-1">
          <label for="commission-month" class="block text-xs font-medium text-slate-400">{{ t('ownerBilling.commissionMonth') }}</label>
          <select id="commission-month" v-model="commissionMonth" class="ui-input text-sm">
            <option v-for="m in 12" :key="m" :value="m" :disabled="isFutureCommissionMonth(m)">{{ commissionMonthName(m) }}</option>
          </select>
        </div>
        <button
          type="button"
          class="ui-btn-outline inline-flex gap-2 px-4 py-2 text-sm disabled:opacity-60"
          :disabled="commissionDownloading"
          @click="downloadCommissionPdf"
        >
          <svg v-if="!commissionDownloading" aria-hidden="true" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" class="h-4 w-4">
            <path d="M10 3v10M6 9l4 4 4-4"/>
            <path d="M4 17h12"/>
          </svg>
          <svg v-else aria-hidden="true" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-4 w-4 animate-spin">
            <path d="M4 10a6 6 0 1 0 1.5-4M4 6v4h4"/>
          </svg>
          {{ commissionDownloading ? t('ownerBilling.commissionDownloading') : t('ownerBilling.commissionDownload') }}
        </button>
      </div>
    </section>

    <!-- ── Close account ────────────────────────────────────────────────── -->
    <section class="ui-panel ui-reveal space-y-4 p-4" style="--ui-delay: 168ms">
      <div class="space-y-0.5">
        <p class="ui-section-kicker">{{ t('ownerBilling.deletionSection') }}</p>
        <h2 class="ui-display text-lg font-semibold text-white">{{ t('ownerBilling.deletionTitle') }}</h2>
        <p class="ui-subtle">{{ t('ownerBilling.deletionHint') }}</p>
      </div>

      <!-- Already requested -->
      <div v-if="deletionAlreadyRequested" class="flex items-start gap-3 rounded-xl border border-amber-500/40 bg-amber-500/10 p-3 text-xs text-amber-200" role="status">
        <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-amber-400" fill="currentColor">
          <path fill-rule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/>
        </svg>
        <span>{{ t('ownerBilling.deletionAlreadyRequested') }}</span>
      </div>

      <!-- Request form -->
      <template v-else>
        <Transition name="billing-form">
          <div v-if="showDeletionConfirm" class="space-y-3 rounded-xl border border-red-500/30 bg-red-500/8 p-4">
            <p class="text-sm font-medium text-red-200">{{ t('ownerBilling.deletionConfirmPrompt') }}</p>
            <textarea
              v-model="deletionReason"
              rows="2"
              maxlength="500"
              class="ui-textarea w-full text-sm focus:border-red-400"
              :aria-label="t('ownerBilling.deletionReasonPlaceholder')"
              :placeholder="t('ownerBilling.deletionReasonPlaceholder')"
            ></textarea>
            <p class="mt-1 text-end text-xs tabular-nums" :class="deletionReason.length >= 480 ? 'text-amber-400' : 'text-slate-600'" aria-live="polite">{{ deletionReason.length }}/500</p>
            <div class="flex flex-wrap gap-2">
              <button
                type="button"
                class="rounded-full border border-red-500/50 bg-red-500/15 px-4 py-2 text-sm text-red-200 transition-colors hover:bg-red-500/25 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-400/60 disabled:opacity-60"
                :disabled="requestingDeletion"
                @click="submitDeletionRequest"
              >
                {{ requestingDeletion ? t('ownerBilling.deletionRequesting') : t('ownerBilling.deletionButton') }}
              </button>
              <button
                type="button"
                class="ui-btn-outline px-4 py-2 text-sm disabled:opacity-60"
                :disabled="requestingDeletion"
                @click="showDeletionConfirm = false"
              >
                {{ t('common.cancel') }}
              </button>
            </div>
          </div>
        </Transition>

        <button
          v-if="!showDeletionConfirm"
          type="button"
          class="rounded-full border border-red-500/40 px-4 py-2 text-sm text-red-300 transition-colors hover:border-red-400/70 hover:text-red-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-400/50"
          @click="showDeletionConfirm = true"
        >
          {{ t('ownerBilling.deletionButton') }}
        </button>
      </template>
    </section>

  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import api from '../lib/api'
import { useI18n } from '../composables/useI18n'
import { useVocabulary } from '../composables/useVocabulary'
import { useTenantStore } from '../stores/tenant'
import { useToastStore } from '../stores/toast'
import { bustCache, isFresh, readCache, writeCache } from '../lib/staleCache'

const { t, formatDateTime, currentLocale } = useI18n()
const { itemPlural } = useVocabulary()
const tenant = useTenantStore()
const toast = useToastStore()

const BILLING_CACHE_KEY = 'owner.billing'
const BILLING_TTL_MS = 5 * 60 * 1000 // 5 min

const loading = ref(false)
const updating = ref(false)
const exporting = ref(false)
const downloadingInvoice = ref(null)
const requestingDeletion = ref(false)
const commissionDownloading = ref(false)
const commissionYear = ref(new Date().getFullYear())
const commissionMonth = ref(new Date().getMonth() + 1)
const showDeletionConfirm = ref(false)
const deletionReason = ref('')
const targets = ref([])
const requests = ref([])
const upgradeMeta = ref({ current_tier_code: '', current_tier_name: '', has_pending_request: false })
const selectedCode = ref('')
const note = ref('')
const submitting = ref(false)
const submitError = ref('')

// ── Usage tracking ───────────────────────────────────────────────────────────
const usageDishes = ref(null)   // current dish count
const usageStaff = ref(null)    // current staff count

const currentTierCode = computed(
  () => upgradeMeta.value.current_tier_code || tenant.entitlements?.tier_code || 'basic'
)
const currentTierName = computed(
  () => upgradeMeta.value.current_tier_name || tenant.entitlements?.tier_name || 'Basic'
)
const hasPendingRequest = computed(
  () =>
    upgradeMeta.value.has_pending_request ||
    requests.value.some((r) => r.status === 'pending')
)
const selectedPlanName = computed(
  () => targets.value.find((t) => t.code === selectedCode.value)?.name || selectedCode.value
)

// ── Feature helpers ─────────────────────────────────────────────────────────

const buildFeatures = (plan) => [
  { label: t('ownerBilling.featureMenu'),         ok: true },
  { label: t('ownerBilling.featureReservations'), ok: true },
  { label: t('ownerBilling.featureBranding'),     ok: true },
  { label: t('ownerBilling.featureOrdering'),     ok: Boolean(plan?.can_checkout) },
  { label: t('ownerBilling.featureWhatsApp'),     ok: Boolean(plan?.can_whatsapp_order) },
  {
    label:
      (plan?.max_languages || 1) > 1
        ? t('ownerBilling.featureLanguages', { count: plan.max_languages })
        : t('ownerBilling.featureOneLanguage'),
    ok: (plan?.max_languages || 1) > 1,
  },
]

const currentPlanFeatures = computed(() =>
  buildFeatures({
    can_checkout:       tenant.entitlements?.can_checkout,
    can_whatsapp_order: tenant.entitlements?.can_whatsapp_order,
    max_languages:      tenant.entitlements?.max_languages,
  })
)
const targetFeatures = (plan) => buildFeatures(plan)

// Usage vs limit rows — only shown when plan imposes a limit (limit > 0)
const usageLimits = computed(() => {
  const rows = []
  const maxDishes = tenant.entitlements?.max_dishes ?? 0
  const maxStaff = tenant.entitlements?.max_staff_accounts ?? 0

  if (maxDishes > 0 && usageDishes.value !== null) {
    rows.push({
      key: 'dishes',
      label: t('ownerBilling.usageDishes', { items: itemPlural.value }),
      current: usageDishes.value,
      limit: maxDishes,
      pct: Math.round((usageDishes.value / maxDishes) * 100),
    })
  }
  if (maxStaff > 0 && usageStaff.value !== null) {
    rows.push({
      key: 'staff',
      label: t('ownerBilling.usageStaff'),
      current: usageStaff.value,
      limit: maxStaff,
      pct: Math.round((usageStaff.value / maxStaff) * 100),
    })
  }
  return rows
})

// ── Status helpers ──────────────────────────────────────────────────────────

const requestStatusClass = (s) => {
  if (s === 'pending')   return 'bg-amber-500/15 text-amber-300 border border-amber-500/30'
  if (s === 'approved')  return 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30'
  if (s === 'rejected')  return 'bg-red-500/15 text-red-300 border border-red-500/30'
  return 'bg-slate-800 text-slate-400 border border-slate-700'
}
const requestStatusLabel = (s) => {
  if (s === 'pending')   return t('ownerBilling.statusPending')
  if (s === 'approved')  return t('ownerBilling.statusApproved')
  if (s === 'rejected')  return t('ownerBilling.statusRejected')
  return s
}

// ── Data fetching ────────────────────────────────────────────────────────────

const applyBillingData = (d) => {
  if (d.targets !== undefined) {
    targets.value = d.targets
    upgradeMeta.value = {
      current_tier_code:   d.current_tier_code   || currentTierCode.value,
      current_tier_name:   d.current_tier_name   || currentTierName.value,
      has_pending_request: d.has_pending_request === true,
    }
  }
  if (d.requests !== undefined) {
    requests.value = d.requests
    upgradeMeta.value = {
      ...upgradeMeta.value,
      has_pending_request: d.requests.some((r) => r.status === 'pending'),
    }
  }
  if (d.usageDishes !== undefined) usageDishes.value = d.usageDishes
  if (d.usageStaff  !== undefined) usageStaff.value  = d.usageStaff
}

const fetchAll = async (force = false) => {
  if (force) bustCache(BILLING_CACHE_KEY)
  const cached = readCache(BILLING_CACHE_KEY)
  if (cached) {
    applyBillingData(cached)
    if (isFresh(BILLING_CACHE_KEY, BILLING_TTL_MS)) return
    updating.value = true
  } else {
    loading.value = true
  }
  try {
    const [targetsRes, requestsRes, dishesRes, staffRes] = await Promise.allSettled([
      api.get('/tier-upgrade-targets/'),
      api.get('/tier-upgrade-requests/'),
      api.get('/dishes/', { params: { page_size: 1 } }),
      api.get('/owner/staff/'),
    ])
    const snapshot = {}
    if (targetsRes.status === 'fulfilled') {
      const d = targetsRes.value.data
      snapshot.targets            = Array.isArray(d?.targets) ? d.targets : []
      snapshot.current_tier_code  = d?.current_tier_code  || ''
      snapshot.current_tier_name  = d?.current_tier_name  || ''
      snapshot.has_pending_request = d?.has_pending_request === true
    }
    if (requestsRes.status === 'fulfilled') {
      snapshot.requests = Array.isArray(requestsRes.value.data) ? requestsRes.value.data : []
    }
    if (dishesRes.status === 'fulfilled') {
      const d = dishesRes.value.data
      snapshot.usageDishes = d?.count ?? (Array.isArray(d) ? d.length : null)
    }
    if (staffRes.status === 'fulfilled') {
      snapshot.usageStaff = staffRes.value.data?.count ?? null
    }
    applyBillingData(snapshot)
    if (Object.keys(snapshot).length) writeCache(BILLING_CACHE_KEY, snapshot)
  } catch {
    if (!cached) toast.show(t('ownerBilling.loadFailed'), 'error')
  } finally {
    loading.value = false
    updating.value = false
  }
}

// ── Submit upgrade request ───────────────────────────────────────────────────

const submitRequest = async () => {
  if (!selectedCode.value || submitting.value) return
  submitError.value = ''
  submitting.value = true
  try {
    const { data } = await api.post('/tier-upgrade-requests/', {
      target_plan_code: selectedCode.value,
      customer_note: note.value.trim(),
    })
    requests.value.unshift(data)
    upgradeMeta.value = { ...upgradeMeta.value, has_pending_request: true }
    bustCache(BILLING_CACHE_KEY) // force fresh load next visit
    selectedCode.value = ''
    note.value = ''
    toast.show(t('ownerBilling.requestSent'), 'success')
  } catch (err) {
    const detail = err?.response?.data?.detail || t('ownerBilling.requestFailed')
    submitError.value = detail
  } finally {
    submitting.value = false
  }
}

// ── Deletion request ──────────────────────────────────────────────────────
const deletionAlreadyRequested = computed(() => Boolean(tenant.meta?.deletion_requested_at))

const submitDeletionRequest = async () => {
  if (requestingDeletion.value) return
  requestingDeletion.value = true
  try {
    await api.post('/owner/deletion-request/', { reason: deletionReason.value.trim() })
    showDeletionConfirm.value = false
    deletionReason.value = ''
    await tenant.fetchMeta()
    toast.show(t('ownerBilling.deletionRequestSent'), 'success')
  } catch {
    toast.show(t('ownerBilling.deletionRequestFailed'), 'error')
  } finally {
    requestingDeletion.value = false
  }
}

// ── Invoice download ─────────────────────────────────────────────────────────

const downloadInvoice = async (requestId) => {
  if (downloadingInvoice.value === requestId) return
  downloadingInvoice.value = requestId
  try {
    const res = await api.get('/owner/invoice/', {
      params: { request_id: requestId },
      responseType: 'blob',
    })
    const url = URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }))
    const a = document.createElement('a')
    a.href = url
    a.download = `invoice-INV-${String(requestId).padStart(5, '0')}.pdf`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    toast.show(t('ownerBilling.invoiceDownloaded'), 'success')
  } catch {
    toast.show(t('ownerBilling.invoiceDownloadFailed'), 'error')
  } finally {
    downloadingInvoice.value = null
  }
}

// ── Data export ─────────────────────────────────────────────────────────────

const downloadDataExport = async () => {
  if (exporting.value) return
  exporting.value = true
  try {
    const res = await api.get('/owner/data-export/', { responseType: 'blob' })
    const url = URL.createObjectURL(new Blob([res.data], { type: 'application/json' }))
    const a = document.createElement('a')
    const date = new Date().toISOString().slice(0, 10).replace(/-/g, '')
    a.href = url
    a.download = `restaurant-export-${date}.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    toast.show(t('ownerBilling.dataExportSuccess'), 'success')
  } catch {
    toast.show(t('ownerBilling.dataExportFailed'), 'error')
  } finally {
    exporting.value = false
  }
}

// ── Commission statement ──────────────────────────────────────────────────────

const currentYear = new Date().getFullYear()
const commissionYears = computed(() => {
  const years = []
  for (let y = currentYear; y >= currentYear - 3; y--) years.push(y)
  return years
})

const commissionMonthName = (m) => {
  try {
    return new Intl.DateTimeFormat(currentLocale.value, { month: 'long' }).format(new Date(2000, m - 1, 1))
  } catch {
    return String(m)
  }
}

const currentMonth = new Date().getMonth() + 1
const isFutureCommissionMonth = (m) => commissionYear.value === currentYear && m > currentMonth

watch(commissionYear, () => {
  if (isFutureCommissionMonth(commissionMonth.value)) commissionMonth.value = currentMonth
})

const downloadCommissionPdf = async () => {
  if (commissionDownloading.value) return
  if (isFutureCommissionMonth(commissionMonth.value)) {
    toast.show(t('ownerBilling.commissionFuturePeriod'), 'error')
    return
  }
  commissionDownloading.value = true
  try {
    const res = await api.get('/owner/commission-statement/', {
      params: { year: commissionYear.value, month: commissionMonth.value, format: 'pdf' },
      responseType: 'blob',
    })
    const url = URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }))
    const a = document.createElement('a')
    a.href = url
    a.download = `commission-${commissionYear.value}-${String(commissionMonth.value).padStart(2, '0')}.pdf`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    toast.show(t('ownerBilling.commissionDownloaded'), 'success')
  } catch {
    toast.show(t('ownerBilling.commissionDownloadFailed'), 'error')
  } finally {
    commissionDownloading.value = false
  }
}

onMounted(() => fetchAll())
</script>

<style scoped>
.billing-form-enter-active,
.billing-form-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease, max-height 0.3s ease;
  max-height: 400px;
  overflow: hidden;
}
.billing-form-enter-from,
.billing-form-leave-to {
  opacity: 0;
  transform: translateY(-6px);
  max-height: 0;
}

@media (prefers-reduced-motion: reduce) {
  .billing-form-enter-active,
  .billing-form-leave-active {
    transition: opacity 0.1s ease, max-height 0.1s ease;
  }
  .billing-form-enter-from,
  .billing-form-leave-to {
    transform: none;
  }
}
</style>
