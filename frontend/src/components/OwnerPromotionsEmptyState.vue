<template>
  <div class="ui-panel ui-reveal text-center px-6 py-12 space-y-2">
    <p class="text-sm font-semibold text-slate-100">{{ t('ownerPromotions.noPromotions') }}</p>
    <p class="text-xs text-slate-400 max-w-xs mx-auto">{{ t('ownerPromotions.noPromotionsHint') }}</p>
    <div class="pt-2">
      <button class="ui-btn-outline ui-press inline-flex items-center gap-1.5 px-5 py-2 text-sm" @click="emit('create')">
        {{ t('ownerPromotions.newPromotion') }}
      </button>
    </div>
  </div>
</template>

<script setup>
// Empty state for OwnerPromotions.vue, extracted as a standalone presentational
// child component (RISK FE-2). The parent renders this via a v-else-if branch
// (alongside its loading/error/list branches) when the promotions list is
// empty, so the loading/error/fetch/list state itself stays owned by the
// parent — this component only ever appears once that decision is already
// made. Purely static markup: the "new promotion" CTA just asks the parent to
// open the create drawer via the `create` emit; all drawer/form state and the
// fetch call stay in the parent.
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();
const emit = defineEmits(['create']);
</script>
