<template>
  <div class="fixed inset-0 z-[3000] flex items-end justify-center bg-black/60 sm:items-center" @click.self="$emit('close')">
    <div class="flex max-h-[85vh] w-full max-w-md flex-col rounded-t-3xl border border-slate-700 bg-slate-900 sm:rounded-2xl">
      <!-- Header -->
      <div class="flex items-start justify-between gap-3 border-b border-slate-800 p-4">
        <div class="min-w-0">
          <h2 class="truncate text-base font-semibold text-white">{{ dish.name }}</h2>
          <p v-if="dish.description" class="mt-0.5 line-clamp-2 text-xs text-slate-400">{{ dish.description }}</p>
        </div>
        <button class="shrink-0 rounded-full p-1.5 text-slate-500 hover:text-slate-300" :aria-label="t('common.close')" @click="$emit('close')">✕</button>
      </div>

      <!-- Options (scrollable) -->
      <div class="flex-1 space-y-4 overflow-y-auto p-4">
        <!-- Option groups -->
        <div v-for="group in (dish.option_groups || [])" :key="group.id" class="space-y-2">
          <div class="flex items-center justify-between gap-2">
            <p class="text-sm font-semibold text-slate-200">
              {{ group.name }}
              <span v-if="group.min_select > 0" class="ml-1.5 rounded-full bg-amber-400/15 px-2 py-0.5 text-[10px] font-semibold text-amber-300">{{ t('dishPage.required') }}</span>
            </p>
            <span class="text-[11px] text-slate-500">{{ group.max_select > 1 ? t('dishPage.pickUpTo', { n: group.max_select }) : t('dishPage.pickOne') }}</span>
          </div>
          <ul class="grid gap-2 text-sm">
            <li
              v-for="opt in group.options" :key="opt.id"
              class="ui-selection-card"
              :data-active="groupIsSelected(group.id, opt.id)"
              :data-warning="group.min_select > 0 && groupSelectedCount(group.id) < group.min_select"
            >
              <label class="flex w-full cursor-pointer items-center gap-2.5">
                <input
                  v-if="group.max_select === 1"
                  type="radio"
                  :name="`qa-group-${group.id}`"
                  :checked="groupIsSelected(group.id, opt.id)"
                  class="h-4 w-4 accent-[var(--color-secondary)]"
                  @change="toggleInGroup(group.id, opt.id, group.max_select, group.min_select)"
                />
                <input
                  v-else
                  type="checkbox"
                  :checked="groupIsSelected(group.id, opt.id)"
                  class="h-4 w-4 rounded accent-[var(--color-secondary)]"
                  @change="toggleInGroup(group.id, opt.id, group.max_select, group.min_select)"
                />
                <p class="min-w-0 flex-1 font-medium text-slate-100">{{ opt.name }}</p>
                <span v-if="Number(opt.price_delta) > 0" class="shrink-0 text-xs font-semibold text-[var(--color-secondary)]">+{{ formatPrice(opt.price_delta) }}</span>
              </label>
            </li>
          </ul>
        </div>

        <!-- Flat (legacy) options -->
        <div v-if="dish.options?.length" class="space-y-2">
          <p class="text-sm font-semibold text-slate-200">{{ t('dishPage.options') }}</p>
          <ul class="grid gap-2 text-sm">
            <li
              v-for="opt in dish.options" :key="opt.id"
              class="ui-selection-card"
              :data-active="selectedOptionIds.includes(opt.id)"
              :data-warning="opt.is_required && !selectedOptionIds.includes(opt.id)"
            >
              <label class="flex w-full cursor-pointer items-center gap-2.5">
                <input v-model="selectedOptionIds" type="checkbox" :value="opt.id" class="h-4 w-4 rounded accent-[var(--color-secondary)]" />
                <div class="min-w-0 flex-1">
                  <p class="font-medium text-slate-100">{{ opt.name }}</p>
                  <p v-if="opt.is_required" class="text-[10px] text-amber-300">{{ t('dishPage.required') }}</p>
                </div>
                <span class="shrink-0 text-xs font-semibold text-[var(--color-secondary)]">+{{ formatPrice(opt.price_delta) }}</span>
              </label>
            </li>
          </ul>
        </div>

        <p v-if="hasRequiredMissing" class="text-xs text-amber-300">{{ t('dishPage.selectRequiredOptions') }}</p>
      </div>

      <!-- Footer: quantity + add -->
      <div class="flex items-center gap-3 border-t border-slate-800 p-4">
        <div class="flex shrink-0 items-center gap-0.5 rounded-full border border-slate-700 px-1">
          <button class="flex h-8 w-8 items-center justify-center" style="color:var(--color-secondary)" :aria-label="t('dishPage.decreaseQuantity')" @click="qty = Math.max(1, qty - 1)"><AppIcon name="minus" class="h-3.5 w-3.5" /></button>
          <span class="w-6 text-center text-sm font-bold tabular-nums text-slate-100">{{ qty }}</span>
          <button class="flex h-8 w-8 items-center justify-center" style="color:var(--color-secondary)" :aria-label="t('dishPage.increaseQuantity')" @click="qty = Math.min(99, qty + 1)"><AppIcon name="plus" class="h-3.5 w-3.5" /></button>
        </div>
        <button
          class="ui-btn-primary flex-1 justify-center py-2.5 text-sm font-semibold disabled:opacity-50"
          :disabled="hasRequiredMissing"
          @click="add"
        >
          {{ t('dishPage.addToCart') }} · {{ formatPrice(totalWithOptions) }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';
import AppIcon from './AppIcon.vue';
import { useI18n } from '../composables/useI18n';
import { useCartStore } from '../stores/cart';
import { useToastStore } from '../stores/toast';

const props = defineProps({
  dish: { type: Object, required: true },
  currency: { type: String, default: '' },
});
const emit = defineEmits(['close']);

const { t, formatPrice } = useI18n();
const cart = useCartStore();
const toast = useToastStore();

// Selection state — mirrors DishPage exactly so the cart payload is identical.
const groupSelections = ref({});   // { [groupId]: optionId | optionId[] }
const selectedOptionIds = ref([]); // ungrouped/legacy options
const qty = ref(1);

const groupIsSelected = (groupId, optionId) => {
  const sel = groupSelections.value[groupId];
  return Array.isArray(sel) ? sel.includes(optionId) : sel === optionId;
};

const toggleInGroup = (groupId, optionId, maxSelect, minSelect = 0) => {
  const current = Array.isArray(groupSelections.value[groupId])
    ? [...groupSelections.value[groupId]]
    : groupSelections.value[groupId] != null ? [groupSelections.value[groupId]] : [];
  const idx = current.indexOf(optionId);
  if (idx >= 0) {
    if (current.length > Math.max(minSelect, 0)) current.splice(idx, 1);
  } else {
    if (current.length >= maxSelect) current.shift();
    current.push(optionId);
  }
  groupSelections.value = { ...groupSelections.value, [groupId]: current };
};

const groupSelectedCount = (groupId) => {
  const sel = groupSelections.value[groupId];
  return Array.isArray(sel) ? sel.length : sel != null ? 1 : 0;
};

// Pre-select required defaults exactly like DishPage: all required flat options, plus the
// first option of each required group — so the diner can add in one tap, then change.
(props.dish.options || []).forEach((opt) => {
  if (opt.is_required && !selectedOptionIds.value.includes(opt.id)) selectedOptionIds.value.push(opt.id);
});
(props.dish.option_groups || []).forEach((group) => {
  if (group.min_select > 0 && group.options?.length && groupSelectedCount(group.id) === 0) {
    groupSelections.value = { ...groupSelections.value, [group.id]: [group.options[0].id] };
  }
});

const allSelectedOptionIdsSorted = computed(() => {
  const grouped = Object.values(groupSelections.value)
    .flatMap((sel) => (Array.isArray(sel) ? sel : sel != null ? [sel] : []))
    .filter((id) => id != null);
  return [...selectedOptionIds.value, ...grouped]
    .map((x) => Number(x))
    .filter((x) => Number.isInteger(x) && x > 0)
    .sort((a, b) => a - b);
});

const selectedOptionObjects = computed(() => {
  const allOptions = [...(props.dish.options || []), ...(props.dish.option_groups || []).flatMap((g) => g.options || [])];
  const byId = new Map(allOptions.map((o) => [o.id, o]));
  return allSelectedOptionIdsSorted.value.map((id) => byId.get(id)).filter(Boolean);
});

const selectedOptionNote = computed(() => {
  if (!selectedOptionObjects.value.length) return '';
  const bits = selectedOptionObjects.value.map((opt) => `${opt.name} (+${formatPrice(opt.price_delta)})`);
  return `${t('dishPage.options')}: ${bits.join(', ')}`;
});

const unitOptionTotal = computed(() => selectedOptionObjects.value.reduce((s, o) => s + Number(o.price_delta || 0), 0));
const unitPriceWithOptions = computed(() => (Number(props.dish.price) || 0) + unitOptionTotal.value);
const totalWithOptions = computed(() => unitPriceWithOptions.value * (qty.value || 1));

const hasUngroupedRequiredMissing = computed(() =>
  (props.dish.options || []).some((o) => o.is_required && !selectedOptionIds.value.includes(o.id)));
const hasGroupMissing = computed(() =>
  (props.dish.option_groups || []).some((g) => g.min_select > 0 && groupSelectedCount(g.id) < g.min_select));
const hasRequiredMissing = computed(() => hasUngroupedRequiredMissing.value || hasGroupMissing.value);

const add = () => {
  if (hasRequiredMissing.value) { toast.show(t('dishPage.selectRequiredOptionsFirst'), 'error'); return; }
  const optionSig = allSelectedOptionIdsSorted.value.join(',');
  cart.add({
    key: `${props.dish.slug}::${optionSig}`,
    slug: props.dish.slug,
    name: props.dish.name,
    price: Number(unitPriceWithOptions.value),
    currency: props.dish.currency || props.currency,
    qty: qty.value > 0 ? qty.value : 1,
    note: selectedOptionNote.value,
    option_ids: allSelectedOptionIdsSorted.value,
    option_labels: selectedOptionObjects.value.map((o) => o.name),
  });
  try { navigator.vibrate?.(12); } catch { /* not supported */ }
  toast.show(t('dishPage.addedToCart'), 'success');
  emit('close');
};
</script>
