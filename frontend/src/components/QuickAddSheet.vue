<template>
  <div class="fixed inset-0 z-[3000] flex items-end justify-center bg-black/70 backdrop-blur-sm sm:items-center" @click.self="$emit('close')">
    <div
      ref="sheetRef"
      class="ui-panel ui-reveal flex max-h-[85vh] w-full max-w-md flex-col rounded-t-3xl sm:rounded-2xl"
      role="dialog"
      aria-modal="true"
      aria-labelledby="qa-sheet-title"
    >
      <!-- Hero image (4:3, object-cover) — keeps visual context when adding from a card -->
      <div v-if="dish.image_url" class="relative w-full overflow-hidden rounded-t-3xl sm:rounded-t-2xl" style="aspect-ratio:4/3">
        <img
          :src="dish.image_url"
          :alt="dish.name"
          class="h-full w-full object-cover"
          loading="lazy"
          decoding="async"
        />
      </div>

      <!-- Header -->
      <div class="flex items-start justify-between gap-3 border-b border-slate-800 p-4">
        <div class="min-w-0">
          <h2 id="qa-sheet-title" class="truncate text-base font-semibold text-white" :title="dish.name">{{ dish.name }}</h2>
          <p v-if="dish.attributes?.brand || dish.attributes?.unit" class="mt-0.5 text-[11px] text-slate-500">{{ [dish.attributes?.brand, dish.attributes?.unit].filter(Boolean).join(' · ') }}</p>
          <p v-if="dish.description" class="mt-0.5 line-clamp-2 text-xs text-slate-400" :title="dish.description">{{ dish.description }}</p>
        </div>
        <button
          class="ui-press ui-touch-target shrink-0 rounded-full p-1.5 text-slate-400 transition hover:bg-slate-800 hover:text-slate-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/50"
          :aria-label="t('common.close')"
          @click="$emit('close')"
        >
          <AppIcon name="close" class="h-4 w-4" aria-hidden="true" />
        </button>
      </div>

      <!-- Options (scrollable) -->
      <div class="flex-1 space-y-4 overflow-y-auto p-4">
        <!-- Option groups -->
        <div
          v-for="group in (dish.option_groups || [])"
          :key="group.id"
          role="group"
          :aria-labelledby="`qa-group-label-${group.id}`"
          class="space-y-2"
        >
          <div class="flex items-center justify-between gap-2">
            <div class="flex min-w-0 flex-1 items-center gap-1.5">
              <p :id="`qa-group-label-${group.id}`" class="truncate text-sm font-semibold text-slate-200">{{ group.name }}</p>
              <span v-if="group.min_select > 0" class="ui-chip-strong shrink-0">{{ t('dishPage.required') }}</span>
            </div>
            <span class="ui-stat-label shrink-0">{{ group.max_select > 1 ? t('dishPage.pickUpTo', { n: group.max_select }) : t('dishPage.pickOne') }}</span>
          </div>
          <ul
            class="grid gap-2 text-sm"
            :aria-describedby="group.min_select > 0 ? `qa-group-err-${group.id}` : undefined"
          >
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
                <span v-if="Number(opt.price_delta) > 0" class="shrink-0 tabular-nums text-xs font-semibold text-[var(--color-secondary)]">+{{ formatPrice(opt.price_delta) }}</span>
              </label>
            </li>
          </ul>
          <span
            v-if="group.min_select > 0"
            :id="`qa-group-err-${group.id}`"
            role="alert"
            aria-live="assertive"
            class="sr-only"
          >{{ groupSelectedCount(group.id) < group.min_select ? t('dishPage.selectRequiredOptions') : '' }}</span>
        </div>

        <!-- Flat (legacy) options -->
        <div v-if="dish.options?.length" class="space-y-2">
          <p class="ui-kicker">{{ t('dishPage.optionsKicker') }}</p>
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
                </div>
                <span v-if="opt.is_required" class="ui-chip-strong shrink-0">{{ t('dishPage.required') }}</span>
                <span v-if="Number(opt.price_delta) > 0" class="shrink-0 tabular-nums text-xs font-semibold text-[var(--color-secondary)]">+{{ formatPrice(opt.price_delta) }}</span>
              </label>
            </li>
          </ul>
        </div>

        <div v-if="hasRequiredMissing" class="flex items-start gap-2 rounded-xl border border-amber-500/30 bg-amber-500/8 px-3 py-2" role="alert">
          <AppIcon name="info" class="mt-0.5 h-4 w-4 shrink-0 text-amber-400" aria-hidden="true" />
          <p class="flex-1 text-xs text-amber-300">{{ t('dishPage.selectRequiredOptions') }}</p>
        </div>
      </div>

      <!-- Special instructions (per-item note carried to the kitchen) -->
      <div class="border-t border-slate-800 px-4 pt-3">
        <label class="block space-y-1">
          <span class="text-[11px] text-slate-400">{{ t('dishPage.specialInstructions') }}</span>
          <textarea
            v-model.trim="specialInstructions"
            rows="2"
            maxlength="140"
            class="ui-textarea text-sm"
            :placeholder="t('dishPage.instructionsPlaceholder')"
            :aria-label="t('dishPage.specialInstructions')"
          ></textarea>
        </label>
      </div>

      <!-- Footer: quantity + add -->
      <div class="flex items-center gap-3 px-4 pt-3" style="padding-bottom: calc(var(--safe-bottom) + 1rem)">
        <div class="ui-qty-control inline-flex shrink-0 items-center rounded-full border p-1">
          <QtyStepperButton :aria-label="t('dishPage.decreaseQuantity')" @click="qty = Math.max(1, qty - 1)">
            <AppIcon name="minus" class="h-3.5 w-3.5" aria-hidden="true" />
          </QtyStepperButton>
          <span class="w-7 text-center text-sm font-bold tabular-nums text-slate-100" aria-live="polite" :aria-label="`${t('dishPage.qty')}: ${qty}`">{{ qty }}</span>
          <QtyStepperButton :aria-label="t('dishPage.increaseQuantity')" @click="qty = Math.min(99, qty + 1)">
            <AppIcon name="plus" class="h-3.5 w-3.5" aria-hidden="true" />
          </QtyStepperButton>
        </div>
        <button
          class="ui-btn-primary flex-1 justify-center py-2.5 text-sm font-semibold disabled:opacity-50"
          :disabled="hasRequiredMissing"
          @click="add"
        >
          {{ isEditMode ? t('dishPage.saveChanges') : t('dishPage.addToCart') }} · {{ formatPrice(totalWithOptions) }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue';
import AppIcon from './AppIcon.vue';
import QtyStepperButton from './QtyStepperButton.vue';
import { useI18n } from '../composables/useI18n';
import { useCartStore } from '../stores/cart';
import { useToastStore } from '../stores/toast';

const props = defineProps({
  dish: { type: Object, required: true },
  currency: { type: String, default: '' },
  // ── Edit-in-place mode ──────────────────────────────────────────────────────
  // When `mode === 'edit'`, the sheet re-opens seeded with an existing cart
  // line's selections (initialOptionIds/initialQty/initialNote). Saving emits
  // `save` with the rebuilt line + the original key so the caller can call
  // cart.replaceLine(editKey, line) instead of add(). `editKey` is the original
  // cart line key being edited.
  mode: { type: String, default: 'add' },           // 'add' | 'edit'
  editKey: { type: String, default: '' },
  initialOptionIds: { type: Array, default: () => [] },
  initialQty: { type: Number, default: 1 },
  initialNote: { type: String, default: '' },
});
const emit = defineEmits(['close', 'save']);

const isEditMode = computed(() => props.mode === 'edit');

const { t, formatPrice } = useI18n();
const cart = useCartStore();
const toast = useToastStore();

// ── Focus trap — keeps keyboard focus inside the sheet, restores it on close ─
const sheetRef = ref(null);

const TRAP_SELECTORS = [
  'a[href]', 'button:not([disabled])', 'input:not([disabled])',
  'select:not([disabled])', 'textarea:not([disabled])', '[tabindex]:not([tabindex="-1"])',
].join(', ');

let _returnFocus = null;

const _trapKeydown = (e) => {
  if (!sheetRef.value) return;
  if (e.key === 'Escape') { e.preventDefault(); emit('close'); return; }
  if (e.key !== 'Tab') return;
  const focusable = Array.from(sheetRef.value.querySelectorAll(TRAP_SELECTORS));
  if (!focusable.length) return;
  const first = focusable[0];
  const last  = focusable[focusable.length - 1];
  if (e.shiftKey) {
    if (document.activeElement === first) { e.preventDefault(); last.focus(); }
  } else {
    if (document.activeElement === last)  { e.preventDefault(); first.focus(); }
  }
};

onMounted(async () => {
  _returnFocus = document.activeElement;
  document.addEventListener('keydown', _trapKeydown);
  await nextTick();
  if (!sheetRef.value?.contains(document.activeElement)) {
    sheetRef.value?.querySelector(TRAP_SELECTORS)?.focus();
  }
});

onBeforeUnmount(() => {
  document.removeEventListener('keydown', _trapKeydown);
  _returnFocus?.focus();
  _returnFocus = null;
});

// Selection state — mirrors DishPage exactly so the cart payload is identical.
const groupSelections = ref({});   // { [groupId]: optionId | optionId[] }
const selectedOptionIds = ref([]); // ungrouped/legacy options
const qty = ref(1);
// Per-item special instructions ("no onions"), carried onto the order line.
const specialInstructions = ref('');

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

// Set of every selectable option id on this dish, used to seed edit mode safely.
const allOptionIds = new Set([
  ...(props.dish.options || []).map((o) => o.id),
  ...(props.dish.option_groups || []).flatMap((g) => (g.options || []).map((o) => o.id)),
]);

if (isEditMode.value) {
  // ── Seed from the existing cart line ──────────────────────────────────────
  qty.value = Number(props.initialQty) > 0 ? Math.min(99, Math.floor(Number(props.initialQty))) : 1;
  const seedIds = (Array.isArray(props.initialOptionIds) ? props.initialOptionIds : [])
    .map((x) => Number(x))
    .filter((x) => Number.isInteger(x) && x > 0 && allOptionIds.has(x));
  const seedSet = new Set(seedIds);
  // Restore ungrouped/legacy options.
  (props.dish.options || []).forEach((opt) => {
    if (seedSet.has(opt.id)) selectedOptionIds.value.push(opt.id);
  });
  // Restore grouped options (respecting max_select per group).
  (props.dish.option_groups || []).forEach((group) => {
    const chosen = (group.options || []).filter((o) => seedSet.has(o.id)).map((o) => o.id);
    if (chosen.length) {
      const capped = group.max_select > 0 ? chosen.slice(0, group.max_select) : chosen;
      groupSelections.value = { ...groupSelections.value, [group.id]: capped };
    }
  });
  // The stored note may be the auto-generated options summary from a previous
  // add() ("Options: …") rather than a user instruction — don't pre-fill that.
  const note = String(props.initialNote || '').trim();
  const optionsPrefix = `${t('dishPage.options')}:`;
  if (note && !note.startsWith(optionsPrefix)) specialInstructions.value = note.slice(0, 140);
  // Backfill any required selections the seed didn't cover (defensive).
  (props.dish.options || []).forEach((opt) => {
    if (opt.is_required && !selectedOptionIds.value.includes(opt.id)) selectedOptionIds.value.push(opt.id);
  });
  (props.dish.option_groups || []).forEach((group) => {
    if (group.min_select > 0 && group.options?.length && groupSelectedCount(group.id) === 0) {
      groupSelections.value = { ...groupSelections.value, [group.id]: [group.options[0].id] };
    }
  });
} else {
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
}

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
  // The line note is the user's free-text special instructions (carried to the
  // kitchen). Options are surfaced separately via option_labels, so the note
  // stays a clean per-item instruction. Fold the instructions into the key so
  // two same-option lines with different notes remain distinct.
  const note = (specialInstructions.value || '').trim().slice(0, 140);
  const noteSig = note.toLowerCase();
  const line = {
    key: `${props.dish.slug}::${optionSig}::${noteSig}`,
    slug: props.dish.slug,
    name: props.dish.name,
    price: Number(unitPriceWithOptions.value),
    currency: props.dish.currency || props.currency,
    qty: qty.value > 0 ? qty.value : 1,
    // Keep the readable options summary appended after any user instruction so
    // the kitchen still sees the chosen options when there is no separate
    // option_labels render (back-compat with note-only surfaces).
    note: note || selectedOptionNote.value,
    option_ids: allSelectedOptionIdsSorted.value,
    option_labels: selectedOptionObjects.value.map((o) => o.name),
  };
  if (isEditMode.value) {
    emit('save', { oldKey: props.editKey, line });
    try { navigator.vibrate?.(12); } catch { /* not supported */ }
    toast.show(t('dishPage.changesSaved'), 'success');
    emit('close');
    return;
  }
  cart.add(line);
  try { navigator.vibrate?.(12); } catch { /* not supported */ }
  toast.show(t('dishPage.addedToCart'), 'success');
  emit('close');
};
</script>
