<template>
  <!-- Create / Edit drawer -->
  <Teleport to="body">
    <div v-if="open" class="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/60 backdrop-blur-sm px-3 pb-3 sm:pb-0" @keydown.esc="emit('close')" @click.self="emit('close')">
      <div ref="dialogRef" role="dialog" aria-modal="true" aria-labelledby="owner-promotions-form-dialog-title" class="ui-panel-soft w-full max-w-md max-h-[92vh] overflow-y-auto">

        <!-- Dialog header -->
        <div class="sticky top-0 z-10 flex items-center justify-between border-b border-slate-700/50 bg-[var(--color-elevated)] px-5 py-4">
          <h2 id="owner-promotions-form-dialog-title" class="text-base font-bold tracking-tight text-white">
            {{ isEdit ? t('common.edit') : t('ownerPromotions.newPromotion') }}
          </h2>
          <button
            class="ui-press rounded-lg border border-slate-700/50 bg-slate-800/50 p-1.5 text-slate-400 hover:border-slate-600 hover:text-white transition-colors ui-touch-target"
            :aria-label="t('common.close')"
            @click="emit('close')"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" class="h-4 w-4" aria-hidden="true">
              <path d="M6 6l12 12M18 6 6 18" />
            </svg>
          </button>
        </div>

        <!-- Form body -->
        <div class="space-y-5 px-5 py-5">

          <!-- Section: Basic info -->
          <div class="space-y-4">
            <!-- Name -->
            <div class="space-y-1.5">
              <label for="promo-name" class="block text-xs font-semibold text-slate-300">{{ t('ownerPromotions.nameLabel') }}</label>
              <input
                id="promo-name"
                v-model="form.name"
                type="text"
                :placeholder="t('ownerPromotions.namePlaceholder')"
                class="ui-input w-full"
              />
            </div>

            <!-- Description -->
            <div class="space-y-1.5">
              <label for="promo-description" class="block text-xs font-semibold text-slate-300">{{ t('ownerPromotions.descriptionLabel') }}</label>
              <input id="promo-description" v-model="form.description" type="text" class="ui-input w-full" />
            </div>

            <!-- Promo code -->
            <div class="space-y-1.5">
              <label for="promo-code" class="block text-xs font-semibold text-slate-300">{{ t('ownerPromotions.codeLabel') }}</label>
              <input
                id="promo-code"
                v-model="form.code"
                type="text"
                maxlength="20"
                autocomplete="off"
                class="ui-input w-full uppercase font-mono tracking-widest"
                :placeholder="t('ownerPromotions.codePlaceholder')"
                @input="form.code = form.code.toUpperCase()"
              />
              <p class="text-[11px] text-slate-500">{{ t('ownerPromotions.codeHint') }}</p>
            </div>
          </div>

          <div class="border-t border-slate-700/40" />

          <!-- Section: Discount -->
          <div class="space-y-4">
            <!-- Type -->
            <div class="space-y-1.5">
              <p id="promo-type-label" class="block text-xs font-semibold text-slate-300">{{ t('ownerPromotions.typeLabel') }}</p>
              <div role="group" aria-labelledby="promo-type-label" class="flex gap-2 flex-wrap">
                <button
                  v-for="opt in promoTypes"
                  :key="opt.value"
                  type="button"
                  :aria-pressed="form.promo_type === opt.value"
                  class="rounded-xl border px-3 py-1.5 text-xs font-medium transition-colors"
                  :class="form.promo_type === opt.value
                    ? 'border-[var(--color-secondary)]/60 bg-[var(--color-secondary)]/10 text-[var(--color-secondary)]'
                    : 'border-slate-700 text-slate-400 hover:border-slate-500'"
                  @click="form.promo_type = opt.value"
                >{{ opt.label }}</button>
              </div>
            </div>

            <!-- Discount value -->
            <div v-if="form.promo_type !== 'free_delivery'" class="space-y-1.5">
              <label for="promo-discount-value" class="block text-xs font-semibold text-slate-300">
                {{ t('ownerPromotions.discountValueLabel') }}
                <span class="text-slate-500 font-normal ms-1">{{ form.promo_type === 'percentage' ? '%' : '' }}</span>
              </label>
              <input id="promo-discount-value" v-model="form.discount_value" type="number" min="0" step="0.01" class="ui-input w-full" />
              <p class="text-[11px] text-slate-500">{{ t('ownerPromotions.discountValueHint') }}</p>
            </div>

            <!-- Min order -->
            <div class="space-y-1.5">
              <label for="promo-min-order" class="block text-xs font-semibold text-slate-300">{{ t('ownerPromotions.minOrderLabel') }}</label>
              <input id="promo-min-order" v-model="form.min_order_amount" type="number" min="0" step="0.01" class="ui-input w-full" />
            </div>

            <!-- Live preview of what the customer sees -->
            <div class="rounded-xl border border-indigo-500/25 bg-indigo-500/8 px-4 py-3 space-y-1">
              <p class="text-[11px] font-semibold uppercase tracking-wider text-indigo-300">{{ t('ownerPromotions.previewTitle') }}</p>
              <p class="text-sm text-slate-200">{{ promoPreview }}</p>
            </div>
          </div>

          <div class="border-t border-slate-700/40" />

          <!-- Section: Scheduling -->
          <div class="space-y-4">
            <!-- Days checkboxes -->
            <div class="space-y-1.5">
              <p id="promo-days-label" class="block text-xs font-semibold text-slate-300">{{ t('ownerPromotions.daysLabel') }}</p>
              <div role="group" aria-labelledby="promo-days-label" class="flex flex-wrap gap-1.5">
                <button
                  v-for="d in dayOptions"
                  :key="d.key"
                  type="button"
                  :aria-pressed="form.days.includes(d.key)"
                  class="inline-flex min-h-[36px] items-center rounded-full border px-2.5 py-1.5 text-[11px] font-medium transition-colors"
                  :class="form.days.includes(d.key)
                    ? 'border-[var(--color-secondary)]/60 bg-[var(--color-secondary)]/10 text-[var(--color-secondary)]'
                    : 'border-slate-700 text-slate-400 hover:border-slate-500'"
                  @click="toggleDay(d.key)"
                >{{ d.label }}</button>
              </div>
              <p class="text-[11px] text-slate-500">{{ t('ownerPromotions.daysHint') }}</p>
            </div>

            <!-- Time window -->
            <div class="space-y-1.5">
              <p id="promo-time-label" class="block text-xs font-semibold text-slate-300">{{ t('ownerPromotions.timeLabel') }}</p>
              <div role="group" aria-labelledby="promo-time-label" class="flex items-center gap-2">
                <input v-model="form.time_start" type="time" class="ui-input flex-1" :aria-label="t('ownerPromotions.timeStart')" />
                <span class="text-slate-500 shrink-0" aria-hidden="true">—</span>
                <input v-model="form.time_end" type="time" class="ui-input flex-1" :aria-label="t('ownerPromotions.timeEnd')" />
              </div>
            </div>

            <!-- Date range -->
            <div class="space-y-1.5">
              <p id="promo-daterange-label" class="block text-xs font-semibold text-slate-300">{{ t('ownerPromotions.dateRangeLabel') }}</p>
              <div role="group" aria-labelledby="promo-daterange-label" class="flex items-center gap-2">
                <input v-model="form.active_from" type="date" class="ui-input flex-1" :aria-label="t('ownerPromotions.dateFrom')" />
                <span class="text-slate-500 shrink-0" aria-hidden="true">—</span>
                <input v-model="form.active_until" type="date" class="ui-input flex-1" :aria-label="t('ownerPromotions.dateUntil')" :min="form.active_from || undefined" />
              </div>
            </div>
          </div>

          <div class="border-t border-slate-700/40" />

          <!-- Section: Limits & activation -->
          <div class="space-y-4">
            <!-- Max uses -->
            <div class="space-y-1.5">
              <label for="promo-max-uses" class="block text-xs font-semibold text-slate-300">{{ t('ownerPromotions.maxUsesLabel') }}</label>
              <input id="promo-max-uses" v-model="form.max_uses" type="number" min="1" step="1" class="ui-input w-full" placeholder="∞" />
              <p class="text-[11px] text-slate-500">{{ t('ownerPromotions.maxUsesHint') }}</p>
            </div>

            <!-- Active toggle -->
            <label class="flex items-center gap-3 cursor-pointer rounded-xl border border-slate-700/50 bg-slate-800/40 px-4 py-3 ui-touch-target transition-colors hover:border-slate-600/60">
              <input
                v-model="form.is_active"
                type="checkbox"
                class="rounded"
              />
              <span class="text-sm font-medium text-slate-300">{{ t('ownerPromotions.isActiveLabel') }}</span>
            </label>
          </div>

          <!-- Error -->
          <div v-if="error" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
            <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
            <p class="flex-1 text-sm text-red-300">{{ error }}</p>
          </div>

          <!-- Submit -->
          <button
            class="ui-btn-primary w-full justify-center"
            :disabled="submitting"
            @click="emit('submit')"
          >
            {{ submitting
              ? (isEdit ? t('ownerPromotions.saving') : t('ownerPromotions.creating'))
              : (isEdit ? t('ownerPromotions.save') : t('ownerPromotions.create'))
            }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
// Promotion create/edit form drawer of OwnerPromotions.vue, extracted as a
// standalone child (RISK FE-2 supervised v-model slice, mirroring
// OwnerHappyHourFormDrawer).
//
// The `form` reactive object stays owned by the parent and is passed via
// `v-model:form` (defineModel); the field bindings + the day toggle + the
// uppercase-code @input mutate the SAME object by reference — behaviour-identical
// to the inline drawer, and lint-clean (a model isn't a prop). The parent keeps
// open/edit state, validation + the save API call (submitForm), and the error/
// submitting flags — reached via close/submit emits. `promoPreview` (a pure
// form-derived computed) and `toggleDay` (mutates form.days) live here; the a11y
// focus-trap moved in self-contained. `promoTypes` and `dayOptions` are passed
// as props so they stay single-sourced in the parent.
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();

const form = defineModel('form', { type: Object, required: true });

const props = defineProps({
  /** Whether the drawer is open (parent-owned). */
  open: { type: Boolean, default: false },
  /** True when editing an existing promotion (drives the title + button labels). */
  isEdit: { type: Boolean, default: false },
  /** Validation / save error message from the parent, or empty. */
  error: { type: String, default: '' },
  /** True while the parent's save request is in flight. */
  submitting: { type: Boolean, default: false },
  /** Promo-type option list ({ value, label }) — the parent's promoTypes. */
  promoTypes: { type: Array, default: () => [] },
  /** Weekday option list ({ key, label }) — the parent's DAYS. */
  dayOptions: { type: Array, default: () => [] },
});

const emit = defineEmits(['close', 'submit']);

// Live, human-readable preview of what a customer sees as the owner fills the
// form (pure derivation of the shared form object).
const promoPreview = computed(() => {
  const v = parseFloat(form.value.discount_value) || 0;
  let base;
  if (form.value.promo_type === 'percentage') base = t('ownerPromotions.labelPercentage', { value: v });
  else if (form.value.promo_type === 'fixed') base = t('ownerPromotions.labelFixed', { value: v });
  else base = t('ownerPromotions.typeFreeDelivery');
  const min = parseFloat(form.value.min_order_amount) || 0;
  if (min > 0) base += ' ' + t('ownerPromotions.previewMinClause', { min });
  return base;
});

const toggleDay = (key) => {
  const idx = form.value.days.indexOf(key);
  if (idx >= 0) form.value.days.splice(idx, 1);
  else form.value.days.push(key);
};

// Focus trap (mirrors the parent's original promotions-drawer trap).
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
