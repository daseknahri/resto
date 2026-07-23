<template>
  <article
    class="ui-panel ui-surface-lift ui-reveal relative overflow-hidden ps-4 pe-3.5 py-3.5"
    :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
  >
    <!-- left accent bar -->
    <div
      class="pointer-events-none absolute inset-y-0 start-0 w-[3px] ltr:rounded-l-xl rtl:rounded-r-xl"
      style="background: linear-gradient(to bottom, rgba(245,158,11,0.55), rgba(245,158,11,0.10))"
    />
    <div class="flex items-center gap-3">
      <!-- Name + meta -->
      <div class="min-w-0 flex-1">
        <p class="truncate text-sm font-semibold leading-snug text-slate-100 tracking-tight" :title="item.name">{{ item.name }}</p>
        <p v-if="item.note" class="mt-1 text-[11px] text-slate-400 truncate" :title="item.note">{{ item.note }}</p>
        <p v-else-if="item.option_labels?.length" class="mt-1 text-[11px] text-slate-400 truncate" :title="item.option_labels.join(' · ')">{{ item.option_labels.join(' · ') }}</p>
        <p class="mt-1 text-[11px] text-slate-500">{{ formatPrice(item.price) }} {{ t('cartPage.each') }}</p>
      </div>
      <!-- Stepper pill -->
      <div class="inline-flex shrink-0 items-center rounded-full border border-slate-700/60 bg-slate-900/60">
        <QtyStepperButton :aria-label="t('cartPage.decreaseQuantity')" @click="emit('decrement')">
          <span class="text-base leading-none" aria-hidden="true">−</span>
        </QtyStepperButton>
        <span class="w-7 text-center text-sm font-bold text-slate-100 select-none tabular-nums" aria-live="polite">{{ item.qty }}</span>
        <QtyStepperButton :aria-label="t('cartPage.increaseQuantity')" @click="emit('increment')">
          <span class="text-base leading-none" aria-hidden="true">+</span>
        </QtyStepperButton>
      </div>
      <!-- Subtotal + edit/remove -->
      <div class="shrink-0 min-w-[4.5rem] text-end">
        <p class="text-sm font-bold tabular-nums text-[var(--color-secondary)]">{{ formatPrice(item.price * item.qty) }}</p>
        <div class="mt-1 flex items-center justify-end gap-1.5">
          <button
            v-if="editable"
            class="px-2 py-1 text-[11px] text-slate-500 hover:text-[var(--color-secondary)] transition-colors focus-visible:text-[var(--color-secondary)] focus:outline-none rounded-md"
            :aria-label="`${t('cartPage.editItem')} ${item.name}`"
            @click="emit('edit')"
          >{{ t('cartPage.editItem') }}</button>
          <button
            class="px-2 py-1 text-[11px] text-slate-500 hover:text-red-400 transition-colors focus-visible:text-red-400 focus:outline-none rounded-md"
            :aria-label="`${t('cartPage.remove')} ${item.name}`"
            @click="emit('remove')"
          >{{ t('cartPage.remove') }}</button>
        </div>
      </div>
    </div>
  </article>
</template>

<script setup>
// A single cart line-item card of Cart.vue, extracted as a standalone
// presentational child (RISK FE-2). Display only: the item name + note/options,
// the price-each, the quantity stepper, the line subtotal, and edit/remove
// affordances. It mutates NOTHING — the cart store mutations stay in the parent
// (Cart.vue keeps cart.decrement / cart.increment / cart.remove and openEditLine);
// this card forwards intent via the decrement / increment / remove / edit emits
// (the parent supplies `item` from its v-for). `formatPrice` is a function prop so
// pricing stays single-sourced in the parent; `editable` is isLineEditable(item),
// computed in the parent. No pricing, payment or checkout logic lives here.
import QtyStepperButton from './QtyStepperButton.vue';
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();

defineProps({
  /** The cart line item ({ name, note, option_labels, price, qty, key, ... }). */
  item: { type: Object, required: true },
  /** Row index within the cart (staggered --ui-delay reveal). */
  index: { type: Number, default: 0 },
  /** Whether this line can be edited (isLineEditable(item)). */
  editable: { type: Boolean, default: false },
  /** Currency formatter (amount) => string, owned by the parent. */
  formatPrice: { type: Function, required: true },
});

const emit = defineEmits(['decrement', 'increment', 'remove', 'edit']);
</script>
