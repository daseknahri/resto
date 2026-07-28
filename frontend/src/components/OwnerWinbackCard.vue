<template>
  <!-- ── Win-back automation card ──────────────────────────────────────────── -->
  <section class="space-y-2 pb-2">
    <div class="px-1">
      <p class="ui-kicker">{{ t('winback.kicker') }}</p>
    </div>
    <div class="ui-panel ui-surface-lift p-4 space-y-4">
      <!-- Explainer + toggle row -->
      <div class="flex items-start justify-between gap-4">
        <div class="flex-1 min-w-0 space-y-1">
          <p class="text-sm font-semibold text-white leading-snug">{{ t('winback.title') }}</p>
          <p class="text-xs text-slate-400">
            {{ t('winback.explainer', { weeks: form.inactive_weeks }) }}
          </p>
        </div>
        <!-- Enabled toggle -->
        <label class="relative inline-flex shrink-0 cursor-pointer items-center" :aria-label="t('winback.enabledLabel')">
          <input
            v-model="form.enabled"
            type="checkbox"
            class="sr-only peer"
            @change="emit('save')"
          />
          <div class="h-5 w-9 rounded-full border border-slate-600 bg-slate-700 transition peer-checked:border-[var(--color-secondary)] peer-checked:bg-[var(--color-secondary)] peer-focus-visible:ring-2 peer-focus-visible:ring-[var(--color-secondary)]/60 after:absolute after:left-[2px] after:top-[2px] after:h-4 after:w-4 after:rounded-full after:bg-white after:transition peer-checked:after:translate-x-4" />
        </label>
      </div>

      <!-- Fields (collapsed when disabled) -->
      <template v-if="form.enabled">
        <div class="border-t border-slate-700/40" />

        <!-- Inactive weeks -->
        <div class="space-y-1.5">
          <label for="winback-weeks" class="block text-xs font-semibold text-slate-300">{{ t('winback.weeksLabel') }}</label>
          <div class="flex items-center gap-2">
            <input
              id="winback-weeks"
              v-model.number="form.inactive_weeks"
              type="number"
              min="1"
              max="52"
              step="1"
              class="ui-input w-24"
              @change="emit('save')"
            />
            <span class="text-xs text-slate-500">{{ t('winback.weeksUnit') }}</span>
          </div>
          <p class="text-[11px] text-slate-500">{{ t('winback.weeksHint') }}</p>
        </div>

        <!-- Custom message -->
        <div class="space-y-1.5">
          <label for="winback-msg" class="block text-xs font-semibold text-slate-300">{{ t('winback.messageLabel') }}</label>
          <textarea
            id="winback-msg"
            v-model="form.message"
            rows="2"
            maxlength="200"
            class="ui-input w-full resize-none text-sm"
            :placeholder="t('winback.messagePlaceholder')"
            @change="emit('save')"
          />
          <p class="text-[11px] text-slate-500 text-end tabular-nums">{{ form.message.length }}/200</p>
        </div>

        <!-- Save error -->
        <div v-if="error" class="flex items-center gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2 text-xs text-red-300" role="alert">
          {{ error }}
        </div>

        <!-- Save button -->
        <button
          class="ui-btn-primary w-full justify-center text-sm"
          :disabled="saving"
          @click="emit('save')"
        >
          {{ saving ? t('winback.saving') : t('winback.save') }}
        </button>
      </template>
    </div>
  </section>
</template>

<script setup>
// Win-back automation config card of OwnerPromotions.vue, extracted as a
// standalone child (RISK FE-2 supervised v-model slice). The `winbackForm`
// reactive object stays owned by the parent and is passed via `v-model:form`
// (defineModel); the toggle / weeks / message bindings mutate the parent's SAME
// object by reference — behaviour-identical, lint-clean. The parent keeps the
// save API call (saveWinback) + the saving/error flags; every field's @change
// and the save button forward a single `save` emit (matching the original
// save-on-change behaviour). No focus trap (this is an inline card, not a modal).
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
