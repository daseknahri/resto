<template>
  <!--
    NotificationBell — header bell + unread badge for the persistent notification inbox.
    Polls the lightweight unread-count endpoint while signed in; clicking opens the
    NotificationInbox dropdown (which marks rows read). Hidden for guests. Additive: it
    only appears next to the existing header controls and owns no layout.
  -->
  <div v-if="customerStore.isAuthenticated" ref="rootEl" class="relative">
    <button
      type="button"
      class="ui-touch-target ui-press relative inline-flex h-8 w-8 items-center justify-center rounded-full border border-slate-700/60 bg-slate-900/70 text-slate-400 transition-colors hover:border-[var(--color-secondary)] hover:text-[var(--color-secondary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)] focus-visible:ring-offset-1 focus-visible:ring-offset-slate-950"
      :aria-label="unreadCount > 0 ? t('notifications.bellAriaUnread', { n: unreadCount }) : t('notifications.bellAria')"
      :aria-expanded="open"
      @click="toggle"
    >
      <AppIcon name="bell" class="h-4 w-4" aria-hidden="true" />
      <span
        v-if="unreadCount > 0"
        aria-hidden="true"
        class="absolute -end-1 -top-1 flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-[var(--color-secondary)] px-1 text-[10px] font-semibold tabular-nums leading-none text-slate-950"
      >{{ unreadCount > 99 ? '99+' : unreadCount }}</span>
    </button>

    <div
      v-if="open"
      ref="inboxEl"
      role="dialog"
      :aria-label="t('notifications.inboxAriaLabel')"
      aria-modal="false"
      class="absolute end-0 top-full z-50 mt-2"
    >
      <NotificationInbox @update-unread="onUpdateUnread" @close="close" />
    </div>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, watch, nextTick } from "vue";
import api from "../lib/api";
import AppIcon from "./AppIcon.vue";
import NotificationInbox from "./NotificationInbox.vue";
import { useI18n } from "../composables/useI18n";
import { useCustomerStore } from "../stores/customer";
import { useFocusTrap } from "../composables/useFocusTrap";

const { t } = useI18n();
const customerStore = useCustomerStore();

const open = ref(false);
const unreadCount = ref(0);
const rootEl = ref(null);
const inboxEl = ref(null);
let pollTimer = null;
let _bellTrigger = null; // button that opened the dropdown — focus is restored on close

useFocusTrap(inboxEl, open);

const POLL_MS = 60000; // poll the cheap count-only endpoint every 60s while signed in

const fetchUnread = async () => {
  if (!customerStore.isAuthenticated) {
    unreadCount.value = 0;
    return;
  }
  try {
    const { data } = await api.get("/customer/notifications/", { params: { count_only: 1 } });
    unreadCount.value = Number(data?.unread_count || 0);
  } catch {
    /* best-effort: keep the last known count */
  }
};

const onUpdateUnread = (n) => {
  unreadCount.value = Number(n || 0);
};

const toggle = () => {
  if (!open.value) _bellTrigger = document.activeElement;
  open.value = !open.value;
  if (!open.value) {
    nextTick(() => _bellTrigger?.focus());
    _bellTrigger = null;
  }
};

const close = () => {
  open.value = false;
  nextTick(() => _bellTrigger?.focus());
  _bellTrigger = null;
};

const onDocClick = (e) => {
  if (open.value && rootEl.value && !rootEl.value.contains(e.target)) close();
};

const onKeydown = (e) => {
  if (e.key === "Escape") close();
};

const startPolling = () => {
  stopPolling();
  if (customerStore.isAuthenticated) {
    fetchUnread();
    pollTimer = setInterval(fetchUnread, POLL_MS);
  }
};

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
};

watch(
  () => customerStore.isAuthenticated,
  (auth) => {
    if (auth) startPolling();
    else {
      stopPolling();
      unreadCount.value = 0;
      open.value = false;
    }
  }
);

onMounted(() => {
  startPolling();
  document.addEventListener("click", onDocClick);
  document.addEventListener("keydown", onKeydown);
});

onBeforeUnmount(() => {
  stopPolling();
  document.removeEventListener("click", onDocClick);
  document.removeEventListener("keydown", onKeydown);
});

defineExpose({ unreadCount, open });
</script>
