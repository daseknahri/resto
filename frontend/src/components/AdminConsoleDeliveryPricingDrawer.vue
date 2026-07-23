<template>
  <!-- Delivery pricing modal -->
  <Teleport to="body">
    <Transition
      enter-active-class="transition-all duration-200"
      enter-from-class="opacity-0"
      leave-active-class="transition-all duration-150"
      leave-to-class="opacity-0"
    >
      <div
        v-if="open"
        tabindex="-1"
        class="fixed inset-0 z-[2100] flex items-center justify-center bg-slate-950/80 p-4 backdrop-blur-sm"
        @click.self="emit('close')"
        @keydown.esc="emit('close')"
      >
        <div
          ref="dialogRef"
          role="dialog"
          aria-modal="true"
          aria-labelledby="admin-delivery-dialog-title"
          class="w-full max-w-lg rounded-2xl border border-slate-700 bg-slate-950 shadow-2xl"
        >
          <div class="flex items-center justify-between border-b border-slate-800 px-5 py-4">
            <div>
              <p class="text-xs font-semibold uppercase tracking-wider text-slate-400">{{ tenant?.name }}</p>
              <h3 id="admin-delivery-dialog-title" class="mt-0.5 text-base font-semibold text-white">{{ t("adminConsole.delivery.title") }}</h3>
              <p class="mt-0.5 text-xs text-slate-400">{{ t("adminConsole.delivery.subtitle") }}</p>
            </div>
            <button
              class="ui-btn-outline ui-press px-3 py-1.5 text-xs"
              @click="emit('close')"
            >{{ t("adminConsole.delivery.close") }}</button>
          </div>
          <div v-if="loading" class="space-y-3 px-5 py-4">
            <div v-for="n in 6" :key="`dl-sk-${n}`" class="ui-skeleton h-8 rounded-lg"></div>
          </div>
          <div v-else class="max-h-[70vh] space-y-4 overflow-y-auto px-5 py-4">
            <div v-if="error" role="alert" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5">
              <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
              <p class="flex-1 text-sm text-red-300">{{ error }}</p>
            </div>
            <label class="block space-y-1">
              <span class="text-xs font-medium text-slate-300">{{ t("adminConsole.delivery.fee") }}</span>
              <input
                v-model.number="form.delivery_fee"
                type="number"
                min="0"
                step="0.01"
                class="ui-input w-full px-3 py-2 text-sm"
              />
            </label>
            <label class="block space-y-1">
              <span class="text-xs font-medium text-slate-300">{{ t("adminConsole.delivery.baseFee") }}</span>
              <input
                v-model.number="form.delivery_base_fee"
                type="number"
                min="0"
                step="0.01"
                class="ui-input w-full px-3 py-2 text-sm"
              />
            </label>
            <label class="block space-y-1">
              <span class="text-xs font-medium text-slate-300">{{ t("adminConsole.delivery.perKm") }}</span>
              <input
                v-model.number="form.delivery_per_km"
                type="number"
                min="0"
                step="0.01"
                class="ui-input w-full px-3 py-2 text-sm"
              />
            </label>
            <label class="block space-y-1">
              <span class="text-xs font-medium text-slate-300">{{ t("adminConsole.delivery.freeOver") }}</span>
              <input
                v-model.number="form.delivery_free_over"
                type="number"
                min="0"
                step="0.01"
                class="ui-input w-full px-3 py-2 text-sm"
              />
            </label>
            <label class="block space-y-1">
              <span class="text-xs font-medium text-slate-300">{{ t("adminConsole.delivery.minimumOrder") }}</span>
              <input
                v-model.number="form.delivery_minimum_order"
                type="number"
                min="0"
                step="0.01"
                class="ui-input w-full px-3 py-2 text-sm"
              />
            </label>
            <label class="block space-y-1">
              <span class="text-xs font-medium text-slate-300">{{ t("adminConsole.delivery.radiusKm") }}</span>
              <input
                v-model="form.delivery_radius_km_raw"
                type="number"
                min="0"
                step="0.5"
                class="ui-input w-full px-3 py-2 text-sm"
                placeholder="—"
              />
            </label>
            <label class="block space-y-1">
              <span class="text-xs font-medium text-slate-300">{{ t("adminConsole.delivery.zoneDescription") }}</span>
              <input
                v-model="form.delivery_zone_description"
                type="text"
                maxlength="200"
                class="ui-input w-full px-3 py-2 text-sm"
              />
            </label>
            <label class="block space-y-1">
              <span class="text-xs font-medium text-slate-300">{{ t("adminConsole.delivery.commissionPct") }}</span>
              <input
                v-model.number="form.delivery_commission_pct"
                type="number"
                min="0"
                max="100"
                step="0.5"
                class="ui-input w-full px-3 py-2 text-sm"
              />
              <span class="block text-xs text-slate-500">{{ t("adminConsole.delivery.commissionHint") }}</span>
            </label>
            <label class="flex cursor-pointer items-start gap-3">
              <input
                v-model="form.platform_delivery_enabled"
                type="checkbox"
                class="mt-0.5 h-4 w-4 shrink-0 rounded border-slate-600 bg-slate-800 accent-[var(--color-primary)]"
              />
              <span class="space-y-0.5">
                <span class="block text-xs font-medium text-slate-300">{{ t("adminConsole.delivery.platformDelivery") }}</span>
                <span class="block text-xs text-slate-500">{{ t("adminConsole.delivery.platformDeliveryHint") }}</span>
              </span>
            </label>
          </div>
          <div class="flex items-center justify-end gap-3 border-t border-slate-800 px-5 py-4">
            <button
              class="ui-btn-outline ui-press px-4 py-2 text-sm"
              @click="emit('close')"
            >{{ t("adminConsole.delivery.close") }}</button>
            <button
              class="ui-btn-primary ui-press inline-flex items-center gap-1.5 px-4 py-2 text-sm disabled:opacity-50"
              :disabled="saving || loading"
              :aria-busy="saving"
              @click="emit('submit')"
            >
              <svg v-if="saving" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-4 w-4 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
              {{ saving ? t('common.loading') : t("adminConsole.delivery.save") }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
// The tenant delivery-pricing modal of AdminConsole.vue, extracted as a fully
// self-contained drawer (RISK FE-2), matching the OwnerHappyHourFormDrawer pattern.
//
// The form STATE stays owned by the parent: `deliveryForm` is a ref object the
// parent keeps and passes here via `v-model:form` (defineModel). Passed by
// reference, the field bindings below mutate the SAME object the parent holds —
// behaviour-identical to the original inline modal, and (unlike v-model on a plain
// prop) lint-clean because `form` is a model, not a prop. The parent keeps the
// modal open/tenant/loading/saving state, the delivery fetch (openDeliveryModal),
// validation + the save API call (saveDeliveryPricing), the close guard
// (closeDeliveryModal ignores clicks while saving), and the error flag — the drawer
// forwards close/submit via emits and reflects `error` / `saving` / `loading` back.
//
// The a11y focus trap moved in self-contained (own dialog ref + keydown listener +
// open watch + onBeforeUnmount cleanup), mirroring the other extracted modals.
import { nextTick, onBeforeUnmount, ref, watch } from 'vue';
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();

const form = defineModel('form', { type: Object, required: true });

const props = defineProps({
  /** Whether the modal is open (parent-owned deliveryModal.open). */
  open: { type: Boolean, default: false },
  /** The tenant being configured ({ name } shown in the header). */
  tenant: { type: Object, default: null },
  /** True while the current pricing is being fetched (deliveryModal.loading). */
  loading: { type: Boolean, default: false },
  /** True while the save request is in flight (deliveryModal.saving). */
  saving: { type: Boolean, default: false },
  /** Validation / save error message from the parent, or empty (deliveryFormError). */
  error: { type: String, default: '' },
});

const emit = defineEmits(['close', 'submit']);

// Focus trap (mirrors the parent's original delivery trap).
const dialogRef = ref(null);

const FOCUSABLE = [
  'a[href]', 'button:not([disabled])', 'input:not([disabled])',
  'select:not([disabled])', 'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(', ');

const trapFocus = (e) => {
  if (!dialogRef.value || e.key !== 'Tab') return;
  const focusable = Array.from(dialogRef.value.querySelectorAll(FOCUSABLE));
  if (!focusable.length) return;
  const first = focusable[0];
  const last  = focusable[focusable.length - 1];
  if (e.shiftKey) {
    if (document.activeElement === first) { e.preventDefault(); last.focus(); }
  } else {
    if (document.activeElement === last)  { e.preventDefault(); first.focus(); }
  }
};

watch(() => props.open, async (open) => {
  if (open) {
    await nextTick();
    dialogRef.value?.querySelector(FOCUSABLE)?.focus();
    document.addEventListener('keydown', trapFocus);
  } else {
    document.removeEventListener('keydown', trapFocus);
  }
});

onBeforeUnmount(() => document.removeEventListener('keydown', trapFocus));
</script>
