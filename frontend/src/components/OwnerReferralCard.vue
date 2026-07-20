<template>
  <!-- ── Referral programme card ──────────────────────────────────────────── -->
  <section class="space-y-2 pb-2">
    <div class="px-1">
      <p class="ui-kicker">{{ t('referral.kicker') }}</p>
    </div>
    <div class="ui-panel ui-surface-lift p-4 space-y-4">
      <div class="flex items-start justify-between gap-4">
        <div class="min-w-0 flex-1">
          <p class="text-sm font-semibold text-white leading-snug">{{ t('referral.title') }}</p>
          <p class="mt-1 text-xs leading-relaxed text-slate-400">{{ t('referral.explainer') }}</p>
        </div>
        <label class="relative inline-flex shrink-0 cursor-pointer items-center" :aria-label="t('referral.toggleLabel')">
          <input
            v-model="form.enabled"
            type="checkbox"
            class="peer sr-only"
            @change="emit('save')"
          />
          <div class="h-5 w-9 rounded-full border border-slate-600 bg-slate-800 transition peer-checked:border-[var(--color-secondary)] peer-checked:bg-[var(--color-secondary)]"></div>
          <div class="absolute start-0.5 top-0.5 h-4 w-4 rounded-full bg-slate-400 shadow transition peer-checked:translate-x-4 rtl:peer-checked:-translate-x-4 peer-checked:bg-white"></div>
        </label>
      </div>

      <template v-if="form.enabled">
        <div>
          <label for="referral-points" class="block text-xs font-semibold text-slate-300">{{ t('referral.pointsLabel') }}</label>
          <div class="mt-1.5 flex items-center gap-2">
            <input
              id="referral-points"
              v-model.number="form.reward_points"
              type="number"
              min="1"
              max="9999"
              class="w-24 rounded-lg border border-slate-700/60 bg-slate-900/50 px-3 py-1.5 text-sm text-slate-200 placeholder-slate-600 focus:border-[var(--color-secondary)] focus:outline-none"
              @change="emit('save')"
            />
            <span class="text-xs text-slate-500">{{ t('referral.pointsUnit') }}</span>
          </div>
          <p class="mt-1.5 text-[11px] text-slate-500">{{ t('referral.pointsHint') }}</p>
        </div>
      </template>

      <div v-if="error" class="flex items-center gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2 text-xs text-red-300" role="alert">
        {{ error }}
      </div>

      <button
        class="ui-btn-primary w-full justify-center text-sm"
        :disabled="saving"
        @click="emit('save')"
      >
        {{ saving ? t('referral.saving') : t('referral.save') }}
      </button>
    </div>
  </section>
</template>

<script setup>
// Referral-programme config card of OwnerPromotions.vue, extracted as a
// standalone child (RISK FE-2 supervised v-model slice, mirrors OwnerWinbackCard).
// The `referralForm` reactive object stays owned by the parent and is passed via
// `v-model:form` (defineModel); the toggle / reward-points bindings mutate the
// parent's SAME object by reference. The parent keeps the save API call
// (saveReferral) + the saving/error flags; every field @change and the save
// button forward a single `save` emit (matching the save-on-change original).
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();

const form = defineModel('form', { type: Object, required: true });

defineProps({
  /** True while the parent's save request is in flight. */
  saving: { type: Boolean, default: false },
  /** Save error message from the parent, or empty. */
  error: { type: String, default: '' },
});

const emit = defineEmits(['save']);
</script>
