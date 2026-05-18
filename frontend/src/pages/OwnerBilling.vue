<template>
  <div class="space-y-5">

    <!-- ── Current plan ──────────────────────────────────────────────── -->
    <section class="ui-panel space-y-5 p-5">
      <div class="space-y-0.5">
        <p class="ui-section-kicker">{{ t('ownerBilling.currentPlanSection') }}</p>
        <h3 class="text-lg font-semibold text-white">{{ t('ownerBilling.yourPlan') }}</h3>
      </div>

      <div class="rounded-2xl border border-[var(--color-secondary)]/30 bg-gradient-to-br from-[var(--color-secondary)]/8 to-transparent p-5">
        <div class="flex flex-wrap items-start justify-between gap-4">
          <div class="space-y-3">
            <div class="flex items-center gap-3">
              <span class="rounded-full border border-[var(--color-secondary)]/50 bg-[var(--color-secondary)]/15 px-3 py-1 text-xs font-bold uppercase tracking-widest text-[var(--color-secondary)]">
                {{ currentTierName }}
              </span>
              <span class="rounded-full border border-emerald-500/40 bg-emerald-500/10 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-300">
                {{ t('ownerBilling.active') }}
              </span>
            </div>
            <ul class="grid grid-cols-1 gap-y-1.5 gap-x-6 sm:grid-cols-2">
              <li
                v-for="f in currentPlanFeatures"
                :key="f.label"
                class="flex items-center gap-2 text-sm"
              >
                <svg v-if="f.ok" viewBox="0 0 16 16" class="h-3.5 w-3.5 shrink-0 text-emerald-400" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M3 8l4 4 6-7"/>
                </svg>
                <svg v-else viewBox="0 0 16 16" class="h-3.5 w-3.5 shrink-0 text-slate-600" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M4 12l8-8M12 12L4 4"/>
                </svg>
                <span :class="f.ok ? 'text-slate-200' : 'text-slate-500'">{{ f.label }}</span>
              </li>
            </ul>
          </div>
        </div>
      </div>

      <!-- Usage limits (only shown when plan has limits set) -->
      <div v-if="usageLimits.length" class="space-y-3">
        <p class="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">{{ t('ownerBilling.usageTitle') }}</p>
        <div class="space-y-3">
          <div v-for="u in usageLimits" :key="u.key" class="space-y-1.5">
            <div class="flex items-center justify-between text-sm">
              <span class="text-slate-300">{{ u.label }}</span>
              <span class="tabular-nums" :class="u.pct >= 100 ? 'font-semibold text-red-400' : u.pct >= 80 ? 'text-amber-300' : 'text-slate-400'">
                {{ u.current }} / {{ u.limit }}
              </span>
            </div>
            <div class="h-1.5 w-full rounded-full bg-slate-800">
              <div
                class="h-1.5 rounded-full transition-all duration-500"
                :class="u.pct >= 100 ? 'bg-red-500' : u.pct >= 80 ? 'bg-amber-400' : 'bg-emerald-500/80'"
                :style="{ width: Math.min(u.pct, 100) + '%' }"
              />
            </div>
            <p v-if="u.pct >= 100" class="text-xs text-red-400">
              {{ t('ownerBilling.limitReached', { label: u.label }) }}
            </p>
          </div>
        </div>
      </div>

      <div
        v-if="hasPendingRequest"
        class="flex items-start gap-3 rounded-xl border border-amber-500/30 bg-amber-500/8 px-4 py-3"
      >
        <svg viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-amber-400" fill="currentColor">
          <path fill-rule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/>
        </svg>
        <p class="text-sm text-amber-200">{{ t('ownerBilling.pendingRequestNote') }}</p>
      </div>
    </section>

    <!-- ── Available upgrades ─────────────────────────────────────────── -->
    <section v-if="loading" class="ui-panel p-5">
      <div class="py-4 text-center text-sm text-slate-500">{{ t('common.loading') }}</div>
    </section>

    <section v-else-if="targets.length" class="ui-panel space-y-5 p-5">
      <div class="space-y-0.5">
        <p class="ui-section-kicker">{{ t('ownerBilling.upgradeSection') }}</p>
        <h3 class="text-lg font-semibold text-white">{{ t('ownerBilling.upgradeTitle') }}</h3>
        <p class="text-sm text-slate-400">{{ t('ownerBilling.upgradeHint') }}</p>
      </div>

      <div
        class="grid gap-4"
        :class="targets.length === 1 ? 'max-w-sm' : targets.length === 2 ? 'sm:grid-cols-2' : 'sm:grid-cols-2 xl:grid-cols-3'"
      >
        <button
          v-for="target in targets"
          :key="target.code"
          type="button"
          class="relative rounded-2xl border p-5 text-left transition-all duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/50 disabled:cursor-not-allowed disabled:opacity-40"
          :class="selectedCode === target.code
            ? 'border-[var(--color-secondary)] ring-2 ring-[var(--color-secondary)]/20 bg-[var(--color-secondary)]/6'
            : 'border-slate-700 bg-slate-900/50 hover:border-slate-500 hover:bg-slate-900/80'"
          :disabled="!target.can_request || hasPendingRequest"
          @click="selectedCode === target.code ? (selectedCode = '') : (selectedCode = target.code)"
        >
          <!-- Selected badge -->
          <div
            v-if="selectedCode === target.code"
            class="absolute right-3 top-3 flex h-5 w-5 items-center justify-center rounded-full bg-[var(--color-secondary)] text-slate-950"
          >
            <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" class="h-3 w-3">
              <path d="M2 6l3 3 5-5"/>
            </svg>
          </div>

          <!-- Coming soon badge -->
          <span
            v-if="!target.is_active"
            class="absolute left-3 top-3 rounded-full border border-sky-700/50 bg-sky-900/30 px-2 py-0.5 text-[10px] font-semibold text-sky-400"
          >
            {{ t('common.soon') }}
          </span>

          <div class="space-y-4 pr-6">
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
                <svg v-if="f.ok" viewBox="0 0 16 16" class="h-3.5 w-3.5 shrink-0 text-emerald-400" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M3 8l4 4 6-7"/>
                </svg>
                <svg v-else viewBox="0 0 16 16" class="h-3.5 w-3.5 shrink-0 text-slate-700" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M4 12l8-8M12 12L4 4"/>
                </svg>
                <span :class="f.ok ? 'text-slate-200' : 'text-slate-600'">{{ f.label }}</span>
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
          <div class="space-y-4 p-5">
            <div class="space-y-0.5">
              <p class="text-sm font-semibold text-white">
                {{ t('ownerBilling.requestFormTitle', { plan: selectedPlanName }) }}
              </p>
              <p class="text-xs text-slate-500">{{ t('ownerBilling.requestFormHint') }}</p>
            </div>
            <textarea
              v-model="note"
              rows="3"
              :placeholder="t('ownerBilling.notePlaceholder')"
              class="w-full resize-none rounded-xl border border-slate-700 bg-slate-900 px-3 py-2.5 text-sm text-slate-200 placeholder-slate-600 focus:border-[var(--color-secondary)] focus:outline-none"
            />
            <p v-if="submitError" class="text-xs text-red-300">{{ submitError }}</p>
            <div class="flex flex-wrap gap-3">
              <button
                class="ui-btn-primary px-6 py-2 text-sm disabled:opacity-60"
                :disabled="submitting"
                @click="submitRequest"
              >
                {{ submitting ? t('ownerBilling.sending') : t('ownerBilling.submitRequest') }}
              </button>
              <button class="ui-btn-outline px-4 py-2 text-sm" @click="selectedCode = ''">
                {{ t('common.cancel') }}
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </section>

    <section v-else-if="!loading" class="ui-panel p-5">
      <p class="py-4 text-center text-sm text-slate-400">{{ t('ownerBilling.highestTier') }}</p>
    </section>

    <!-- ── Request history ────────────────────────────────────────────── -->
    <section class="ui-panel space-y-5 p-5">
      <div class="flex items-center justify-between gap-3">
        <div class="space-y-0.5">
          <p class="ui-section-kicker">{{ t('ownerBilling.historySection') }}</p>
          <h3 class="text-lg font-semibold text-white">{{ t('ownerBilling.historyTitle') }}</h3>
        </div>
        <button
          class="flex h-8 w-8 items-center justify-center rounded-lg border border-slate-700 text-slate-400 hover:border-slate-500 hover:text-slate-200 disabled:opacity-50 transition-colors"
          :disabled="loading"
          :aria-label="t('common.refresh')"
          @click="fetchAll"
        >
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" class="h-4 w-4" :class="loading ? 'animate-spin' : ''">
            <path d="M4 10a6 6 0 1 0 1.5-4M4 6v4h4"/>
          </svg>
        </button>
      </div>

      <div v-if="loading" class="py-4 text-center text-sm text-slate-500">{{ t('common.loading') }}</div>

      <div
        v-else-if="!requests.length"
        class="rounded-2xl border border-dashed border-slate-700 py-10 text-center"
      >
        <svg viewBox="0 0 40 40" class="mx-auto h-10 w-10 text-slate-700" fill="none" stroke="currentColor" stroke-width="1.25">
          <rect x="8" y="6" width="24" height="28" rx="3"/>
          <path d="M14 14h12M14 19h12M14 24h8" stroke-linecap="round"/>
        </svg>
        <p class="mt-3 text-sm text-slate-500">{{ t('ownerBilling.noRequests') }}</p>
      </div>

      <ul v-else class="space-y-3">
        <li
          v-for="req in requests"
          :key="req.id"
          class="rounded-xl border border-slate-800 bg-slate-900/50 p-4"
        >
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div class="space-y-1.5">
              <div class="flex flex-wrap items-center gap-2">
                <span class="text-sm font-medium text-slate-200">{{ req.current_plan_name }}</span>
                <svg viewBox="0 0 20 12" class="h-3 w-4 text-slate-500" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
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
          <div v-if="req.customer_note" class="mt-3 rounded-lg border border-slate-800 bg-slate-950/50 px-3 py-2 text-xs text-slate-400">
            "{{ req.customer_note }}"
          </div>
          <!-- Admin note -->
          <div v-if="req.admin_note" class="mt-2 flex items-start gap-2 rounded-lg border border-slate-700/60 bg-slate-950/50 px-3 py-2 text-xs">
            <svg viewBox="0 0 16 16" class="mt-0.5 h-3 w-3 shrink-0 text-slate-400" fill="none" stroke="currentColor" stroke-width="1.5">
              <rect x="2" y="2" width="12" height="12" rx="2"/>
              <path d="M5 6h6M5 9h4" stroke-linecap="round"/>
            </svg>
            <span class="text-slate-300">{{ req.admin_note }}</span>
          </div>
          <!-- Invoice download -->
          <div v-if="req.status === 'approved'" class="mt-3">
            <button
              v-if="req.invoice_amount"
              class="flex items-center gap-1.5 rounded-full border border-emerald-500/40 bg-emerald-500/10 px-3 py-1.5 text-xs font-medium text-emerald-300 transition-colors hover:bg-emerald-500/20 disabled:opacity-60"
              :disabled="downloadingInvoice === req.id"
              @click="downloadInvoice(req.id)"
            >
              <svg v-if="downloadingInvoice !== req.id" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" class="h-3.5 w-3.5">
                <path d="M8 3v7M5 7l3 3 3-3"/>
                <path d="M3 13h10"/>
              </svg>
              <svg v-else viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin">
                <path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/>
              </svg>
              {{ downloadingInvoice === req.id ? t('ownerBilling.invoiceDownloading') : t('ownerBilling.invoiceDownload') }}
            </button>
            <p v-else class="text-[11px] text-slate-500 italic">{{ t('ownerBilling.invoiceNotReady') }}</p>
          </div>
        </li>
      </ul>
    </section>

    <!-- ── Data & privacy ──────────────────────────────────────────────── -->
    <section class="ui-panel space-y-4 p-5">
      <div class="space-y-0.5">
        <p class="ui-section-kicker">{{ t('ownerBilling.dataExportSection') }}</p>
        <h3 class="text-lg font-semibold text-white">{{ t('ownerBilling.dataExportTitle') }}</h3>
        <p class="text-sm text-slate-400">{{ t('ownerBilling.dataExportHint') }}</p>
      </div>

      <button
        class="rounded-full border border-slate-700 px-4 py-2 text-sm text-slate-50 disabled:opacity-60 flex items-center gap-2"
        :disabled="exporting"
        @click="downloadDataExport"
      >
        <svg v-if="!exporting" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" class="h-4 w-4">
          <path d="M10 3v10M6 9l4 4 4-4"/>
          <path d="M4 17h12"/>
        </svg>
        <svg v-else viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-4 w-4 animate-spin">
          <path d="M4 10a6 6 0 1 0 1.5-4M4 6v4h4"/>
        </svg>
        {{ exporting ? t('ownerBilling.dataExporting') : t('ownerBilling.dataExportButton') }}
      </button>
    </section>

    <!-- ── Close account ────────────────────────────────────────────────── -->
    <section class="ui-panel space-y-4 p-5">
      <div class="space-y-0.5">
        <p class="ui-section-kicker">{{ t('ownerBilling.deletionSection') }}</p>
        <h3 class="text-lg font-semibold text-white">{{ t('ownerBilling.deletionTitle') }}</h3>
        <p class="text-sm text-slate-400">{{ t('ownerBilling.deletionHint') }}</p>
      </div>

      <!-- Already requested -->
      <div v-if="deletionAlreadyRequested" class="rounded-xl border border-amber-500/40 bg-amber-500/10 p-3 text-xs text-amber-200">
        {{ t('ownerBilling.deletionAlreadyRequested') }}
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
              class="w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:border-red-400 focus:outline-none"
              :placeholder="t('ownerBilling.deletionReasonPlaceholder')"
            ></textarea>
            <div class="flex flex-wrap gap-2">
              <button
                class="rounded-full border border-red-500/50 bg-red-500/15 px-4 py-2 text-sm text-red-200 disabled:opacity-60 hover:bg-red-500/25 transition-colors"
                :disabled="requestingDeletion"
                @click="submitDeletionRequest"
              >
                {{ requestingDeletion ? t('ownerBilling.deletionRequesting') : t('ownerBilling.deletionButton') }}
              </button>
              <button
                class="rounded-full border border-slate-700 px-4 py-2 text-sm text-slate-400 hover:text-slate-200 transition-colors"
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
          class="rounded-full border border-red-500/40 px-4 py-2 text-sm text-red-300 hover:border-red-400/70 hover:text-red-200 transition-colors"
          @click="showDeletionConfirm = true"
        >
          {{ t('ownerBilling.deletionButton') }}
        </button>
      </template>
    </section>

  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import api from '../lib/api'
import { useI18n } from '../composables/useI18n'
import { useTenantStore } from '../stores/tenant'
import { useToastStore } from '../stores/toast'

const { t, formatDateTime } = useI18n()
const tenant = useTenantStore()
const toast = useToastStore()

const loading = ref(false)
const exporting = ref(false)
const downloadingInvoice = ref(null)
const requestingDeletion = ref(false)
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
      label: t('ownerBilling.usageDishes'),
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

const fetchAll = async () => {
  loading.value = true
  try {
    const [targetsRes, requestsRes, dishesRes, staffRes] = await Promise.allSettled([
      api.get('/tier-upgrade-targets/'),
      api.get('/tier-upgrade-requests/'),
      api.get('/dishes/', { params: { page_size: 1 } }),
      api.get('/owner/staff/'),
    ])
    if (targetsRes.status === 'fulfilled') {
      const d = targetsRes.value.data
      targets.value = Array.isArray(d?.targets) ? d.targets : []
      upgradeMeta.value = {
        current_tier_code:    d?.current_tier_code    || currentTierCode.value,
        current_tier_name:    d?.current_tier_name    || currentTierName.value,
        has_pending_request:  d?.has_pending_request  === true,
      }
    }
    if (requestsRes.status === 'fulfilled') {
      requests.value = Array.isArray(requestsRes.value.data) ? requestsRes.value.data : []
      upgradeMeta.value = {
        ...upgradeMeta.value,
        has_pending_request: requests.value.some((r) => r.status === 'pending'),
      }
    }
    if (dishesRes.status === 'fulfilled') {
      const d = dishesRes.value.data
      // Paginated response has `count`; flat array has `length`
      usageDishes.value = d?.count ?? (Array.isArray(d) ? d.length : null)
    }
    if (staffRes.status === 'fulfilled') {
      usageStaff.value = staffRes.value.data?.count ?? null
    }
  } catch {
    toast.show(t('ownerBilling.loadFailed'), 'error')
  } finally {
    loading.value = false
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
  } catch {
    toast.show(t('ownerBilling.dataExportFailed'), 'error')
  } finally {
    exporting.value = false
  }
}

onMounted(fetchAll)
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
</style>
