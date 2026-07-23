<template>
  <!-- Rate the customer after delivery (driver → customer, private) -->
  <Teleport to="body">
    <div
      v-if="job"
      class="fixed inset-0 z-[2000] flex items-end justify-center bg-black/60 p-3 backdrop-blur-sm sm:items-center"
      @click.self="emit('close')"
      @keydown.esc="emit('close')"
    >
      <div ref="dialogRef" class="w-full max-w-sm space-y-4 rounded-2xl border border-slate-700 bg-slate-900 p-5 shadow-2xl" role="dialog" aria-modal="true" :aria-label="t('driver.rateCustomerTitle')" tabindex="-1">
        <div>
          <p class="text-sm font-semibold text-white">{{ t('driver.rateCustomerTitle') }}</p>
          <p class="mt-0.5 text-xs text-slate-400">{{ t('driver.order') }} #{{ job.order_number }}</p>
          <p class="mt-1 text-[11px] text-slate-500">{{ t('driver.rateCustomerHint') }}</p>
        </div>
        <div class="flex items-center gap-2" role="group" :aria-label="t('driver.rateCustomerTitle')">
          <button
            v-for="n in 5" :key="n" type="button"
            class="ui-press text-3xl leading-none transition-transform hover:scale-110 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-400"
            :class="n <= score ? 'text-amber-400' : 'text-slate-600'"
            :aria-label="t('common.rateNStars', { n })"
            @click="score = n"
          >★</button>
        </div>
        <input
          v-model="note" type="text" maxlength="200"
          class="ui-input"
          :aria-label="t('driver.rateCustomerNote')"
          :placeholder="t('driver.rateCustomerNote')"
        />
        <div class="flex items-center justify-end gap-2 pt-1">
          <button class="ui-btn-outline ui-press px-3 py-2 text-xs" @click="emit('close')">
            {{ t('driver.rateSkip') }}
          </button>
          <button
            class="ui-btn-primary ui-press inline-flex items-center gap-2 px-4 py-2 text-sm disabled:opacity-50"
            :disabled="!score || busy"
            :aria-busy="busy"
            @click="emit('submit')"
          >
            <svg v-if="busy" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
            {{ busy ? t('common.loading') : t('driver.rateSubmit') }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
// The driver → customer post-delivery rating modal of DriverPage.vue, extracted as
// a fully self-contained drawer (RISK FE-2). It owns the whole modal (Teleport +
// backdrop + dialog) and its a11y focus trap via the shared useFocusTrap composable
// (keyed on `job`, truthy when open — same as the parent's original call). Non-money
// (private reputation rating). The parent keeps the rating state, the open helper
// (openCustomerRating) and the submit handler (submitCustomerRating → the API); the
// star score + note are two-way models, and skip/submit are emits.
import { ref } from 'vue';
import { useI18n } from '../composables/useI18n';
import { useFocusTrap } from '../composables/useFocusTrap';

const { t } = useI18n();

const props = defineProps({
  /** The delivery job being rated (ratingJob) — drives the modal + supplies #order_number. */
  job: { type: Object, default: null },
  /** True while the rating submit is in flight (submittingRating). */
  busy: { type: Boolean, default: false },
});

/** Star score (custRatingScore), two-way. */
const score = defineModel('score', { type: Number, default: 0 });
/** Free-text note (custRatingNote), two-way. */
const note = defineModel('note', { type: String, default: '' });

const emit = defineEmits(['close', 'submit']);

// D-8: Tab focus-trap + open/return focus handling (shared helper), keyed on `job`.
const dialogRef = ref(null);
useFocusTrap(dialogRef, () => props.job);
</script>
