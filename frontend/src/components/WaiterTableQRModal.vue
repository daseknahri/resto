<template>
  <!-- ── TABLE QR CODE MODAL — shows a table's ordering-page QR for guests to scan ── -->
  <Teleport to="body">
    <Transition
      enter-active-class="transition-all duration-200"
      enter-from-class="opacity-0 scale-95"
      leave-active-class="transition-all duration-150"
      leave-to-class="opacity-0 scale-95"
    >
      <div
        v-if="qrDataUrl"
        class="fixed inset-0 z-[5000] flex items-center justify-center bg-black/70 p-6 backdrop-blur-sm"
        @click.self="emit('close')"
        @keydown.esc="emit('close')"
      >
        <div
          class="flex flex-col items-center gap-4 rounded-2xl bg-slate-50 p-6 shadow-2xl"
          role="dialog"
          aria-modal="true"
          :aria-label="t('waiterPage.showQR')"
        >
          <p class="text-sm font-semibold text-slate-700">{{ qrTableLabel }}</p>
          <img :src="qrDataUrl" :alt="t('waiterPage.qrCodeAlt', { label: qrTableLabel })" class="h-56 w-56 rounded-lg" />
          <p class="text-[11px] text-slate-400">{{ t('waiterPage.qrScanHint') }}</p>
          <button
            type="button"
            class="rounded-lg bg-slate-200 px-4 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-300 focus-visible:outline-none"
            @click="emit('close')"
          >{{ t('common.close') }}</button>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
// Table QR-code modal of WaiterPage.vue, extracted as a standalone
// presentational child (RISK FE-2). QR generation (`showTableQR`, the
// dynamic `qrcode` import) and the `qrDataUrl`/`qrTableLabel` state stay
// owned by the parent — this component only renders the already-generated
// data URL + label and asks the parent to clear them via the `close` emit.
// No order-entry, cart, payment, or live-order fetch/poll logic here.
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();

defineProps({
  /** Generated QR-code image data URL. Empty string hides the modal. */
  qrDataUrl: { type: String, default: '' },
  /** Table label shown above the code and in the image's alt text. */
  qrTableLabel: { type: String, default: '' },
});

const emit = defineEmits(['close']);
</script>
