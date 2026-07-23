<template>
  <!-- Live orders support modal (read-only) -->
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
          aria-labelledby="admin-live-orders-dialog-title"
          class="flex max-h-[85vh] w-full max-w-2xl flex-col rounded-2xl border border-slate-700 bg-slate-950 shadow-2xl"
        >
          <div class="flex items-start justify-between gap-3 border-b border-slate-800 px-5 py-4">
            <div class="min-w-0">
              <p class="text-xs font-semibold uppercase tracking-wider text-slate-400">{{ tenant?.name }}</p>
              <h3 id="admin-live-orders-dialog-title" class="mt-0.5 text-base font-semibold text-white">{{ t("adminConsole.liveOrders.title") }}</h3>
              <p class="mt-0.5 text-xs text-slate-400">{{ t("adminConsole.liveOrders.subtitle") }}</p>
              <span class="mt-1.5 inline-flex items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold text-amber-200">
                {{ t("adminConsole.liveOrders.readOnlyBadge") }}
              </span>
            </div>
            <div class="flex shrink-0 items-center gap-2">
              <button
                class="ui-btn-outline ui-press px-3 py-1.5 text-xs disabled:opacity-50"
                :disabled="loading"
                @click="emit('refresh')"
              >{{ t("common.refresh") }}</button>
              <button
                class="ui-btn-outline ui-press px-3 py-1.5 text-xs"
                @click="emit('close')"
              >{{ t("adminConsole.liveOrders.close") }}</button>
            </div>
          </div>
          <div class="min-h-0 flex-1 overflow-y-auto px-5 py-4">
            <div v-if="loading" class="space-y-2">
              <div v-for="n in 5" :key="`lo-sk-${n}`" class="ui-skeleton h-12 rounded-lg"></div>
            </div>
            <div v-else-if="error" role="alert" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5">
              <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
              <p class="flex-1 text-sm text-red-300">{{ error }}</p>
            </div>
            <article v-else-if="!orders.length" class="ui-empty-state">
              <p class="ui-kicker">{{ t("adminConsole.liveOrders.title") }}</p>
              <h3 class="text-lg font-semibold text-white">{{ t("adminConsole.liveOrders.empty") }}</h3>
              <p class="max-w-xl text-sm text-slate-400">{{ t("adminConsole.liveOrders.emptyHint") }}</p>
            </article>
            <template v-else>
              <p class="mb-3 text-xs text-slate-500">{{ t("adminConsole.liveOrders.activeCount", { count }) }}</p>
              <!-- Mobile: cards -->
              <div class="space-y-2 md:hidden">
                <article
                  v-for="(order, index) in orders"
                  :key="`lo-mobile-${order.order_number}-${index}`"
                  class="ui-admin-card space-y-1.5"
                >
                  <div class="flex items-center justify-between gap-2">
                    <p class="font-semibold text-slate-100">#{{ order.order_number }}</p>
                    <span class="ui-status-pill text-[10px] font-semibold" :class="liveOrderStatusClass(order.status)">{{ order.status }}</span>
                  </div>
                  <p class="text-xs text-slate-400">{{ t("adminConsole.liveOrders.type") }}: {{ order.order_type || "-" }}</p>
                  <p class="text-xs text-slate-400">{{ t("adminConsole.liveOrders.total") }}: {{ order.total }}</p>
                  <p class="text-xs text-slate-500">{{ t("adminConsole.liveOrders.age") }}: {{ formatAge(order.created_at) }}</p>
                  <p class="text-xs text-slate-500">{{ t("adminConsole.liveOrders.phone") }}: {{ order.customer_phone || "-" }}</p>
                </article>
              </div>
              <!-- Desktop: table -->
              <div class="ui-table-wrap hidden md:block">
                <table class="w-full min-w-[640px] text-sm">
                  <thead class="bg-slate-900/70 text-slate-300">
                    <tr>
                      <th scope="col" class="px-3 py-2.5 text-start">{{ t("adminConsole.liveOrders.orderNumber") }}</th>
                      <th scope="col" class="px-3 py-2.5 text-start">{{ t("common.status") }}</th>
                      <th scope="col" class="px-3 py-2.5 text-start">{{ t("adminConsole.liveOrders.type") }}</th>
                      <th scope="col" class="px-3 py-2.5 text-start">{{ t("adminConsole.liveOrders.total") }}</th>
                      <th scope="col" class="px-3 py-2.5 text-start">{{ t("adminConsole.liveOrders.age") }}</th>
                      <th scope="col" class="px-3 py-2.5 text-start">{{ t("adminConsole.liveOrders.phone") }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(order, index) in orders" :key="`lo-row-${order.order_number}-${index}`" class="border-t border-slate-800">
                      <td class="px-3 py-2.5 font-medium text-slate-100">#{{ order.order_number }}</td>
                      <td class="px-3 py-2.5">
                        <span class="ui-status-pill text-[10px] font-semibold" :class="liveOrderStatusClass(order.status)">{{ order.status }}</span>
                      </td>
                      <td class="px-3 py-2.5 text-slate-300">{{ order.order_type || "-" }}</td>
                      <td class="px-3 py-2.5 text-slate-300 tabular-nums">{{ order.total }}</td>
                      <td class="px-3 py-2.5 text-slate-400">{{ formatAge(order.created_at) }}</td>
                      <td class="px-3 py-2.5 text-slate-400">{{ order.customer_phone || "-" }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </template>
          </div>
          <div class="flex items-center justify-end gap-3 border-t border-slate-800 px-5 py-4">
            <button
              class="ui-btn-outline ui-press px-4 py-2 text-sm"
              @click="emit('close')"
            >{{ t("adminConsole.liveOrders.close") }}</button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
// "Live orders support" modal of AdminConsole.vue, extracted as a standalone
// child component (RISK FE-2). This modal is read-only: it DISPLAYS a tenant's
// live/recent orders as mobile cards + a desktop table. Data-fetching
// (fetchLiveOrders / the /admin/tenants/{id}/live-orders/ call), the open/close
// state (liveOrdersModal) and the orders/count refs all stay owned by the
// parent — this component only renders whatever it's given and asks the parent
// to close or refresh via emits. `liveOrderStatusClass` and `formatAge` are
// used only by this section, so they move here in full (same approach as
// AdminConsoleProvisioningJobs' statusClass). The dialog's focus trap is
// directly-supporting a11y logic for this modal, so it lives here
// self-contained (its own dialog ref + keydown listener, cleaned up on unmount)
// exactly like AdminConsoleDryRunImportModal.
import { nextTick, onBeforeUnmount, ref, watch } from "vue";
import { useI18n } from "../composables/useI18n";

const props = defineProps({
  /** Whether the modal is open (parent-owned open/close state). */
  open: { type: Boolean, default: false },
  /** The tenant whose live orders are shown ({ name, ... }); null before open. */
  tenant: { type: Object, default: null },
  /** True while the parent's live-orders fetch is in flight (drives the skeleton). */
  loading: { type: Boolean, default: false },
  /** Load-error message from the parent's fetch, or null. */
  error: { type: String, default: null },
  /** Live/recent order records to render (parent-owned, read-only). */
  orders: { type: Array, default: () => [] },
  /** Active order count for the header line (may exceed orders.length). */
  count: { type: Number, default: 0 },
});

const emit = defineEmits(["close", "refresh"]);

const { t } = useI18n();

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
  const last = focusable[focusable.length - 1];
  if (e.shiftKey) {
    if (document.activeElement === first) { e.preventDefault(); last.focus(); }
  } else {
    if (document.activeElement === last) { e.preventDefault(); first.focus(); }
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

onBeforeUnmount(() => {
  document.removeEventListener('keydown', trapFocus);
});

const liveOrderStatusClass = (status) => {
  if (status === "ready") return "bg-emerald-500/20 text-emerald-200";
  if (status === "out_for_delivery") return "bg-sky-500/20 text-sky-200";
  if (status === "preparing") return "bg-amber-500/20 text-amber-200";
  if (status === "confirmed") return "bg-indigo-500/20 text-indigo-200";
  if (status === "scheduled") return "bg-violet-500/20 text-violet-200";
  if (status === "pending") return "bg-slate-700/60 text-slate-200";
  return "bg-slate-700/60 text-slate-300";
};

const formatAge = (value) => {
  if (!value) return "-";
  const created = new Date(value);
  if (Number.isNaN(created.getTime())) return "-";
  const diffMs = Date.now() - created.getTime();
  if (diffMs < 0) return t("adminConsole.liveOrders.ageNow");
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return t("adminConsole.liveOrders.ageNow");
  if (minutes < 60) return t("adminConsole.liveOrders.ageMinutes", { minutes });
  const hours = Math.floor(minutes / 60);
  const remMinutes = minutes % 60;
  if (hours < 24) return t("adminConsole.liveOrders.ageHours", { hours, minutes: remMinutes });
  const days = Math.floor(hours / 24);
  return t("adminConsole.liveOrders.ageDays", { days });
};
</script>
