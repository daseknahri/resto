<template>
  <!--
    NotificationInbox — the persistent in-app notification feed (the inbox / notification
    center). Rendered as a dropdown panel anchored under the header bell. Cross-vertical:
    order updates, ride/courier milestones, wallet/charge events, review prompts. Each row
    deep-links via its stored url. Opening the inbox marks the unread rows read (the
    Careem/Grab pattern: push is just the delivery channel, this is the source of truth).
  -->
  <div
    class="ui-panel flex max-h-[70vh] w-[20rem] flex-col overflow-hidden rounded-2xl border border-slate-700/70 bg-slate-900/95 shadow-2xl shadow-black/40 backdrop-blur sm:w-[22rem]"
    role="dialog"
    :aria-label="t('notifications.title')"
  >
    <header class="flex items-center justify-between gap-2 border-b border-slate-700/60 px-4 py-3">
      <h2 class="text-sm font-semibold text-slate-100">{{ t('notifications.title') }}</h2>
      <button
        v-if="unreadCount > 0"
        type="button"
        class="ui-press rounded-full px-2 py-1 text-[11px] font-medium text-[var(--color-secondary)] transition-colors hover:opacity-80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/40"
        @click="markAllRead"
      >
        {{ t('notifications.markAllRead') }}
      </button>
    </header>

    <div class="min-h-0 flex-1 overflow-y-auto">
      <p v-if="loading && !items.length" class="px-4 py-8 text-center text-sm text-slate-400">
        {{ t('notifications.loading') }}
      </p>
      <p v-else-if="error" class="px-4 py-8 text-center text-sm text-red-300">
        {{ t('notifications.error') }}
      </p>
      <p v-else-if="!items.length" class="px-4 py-10 text-center text-sm text-slate-400">
        {{ t('notifications.empty') }}
      </p>

      <ul v-else class="divide-y divide-slate-800/70">
        <li v-for="n in items" :key="n.id">
          <component
            :is="n.url ? 'RouterLink' : 'div'"
            v-bind="n.url ? { to: n.url } : {}"
            class="flex gap-3 px-4 py-3 transition-colors"
            :class="[
              n.url ? 'cursor-pointer hover:bg-slate-800/50' : '',
              n.is_read ? 'opacity-70' : 'bg-[var(--color-secondary)]/[0.06]',
            ]"
            @click="onRowClick(n)"
          >
            <span
              aria-hidden="true"
              class="mt-1 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-sm"
              :class="verticalBadgeClass(n.vertical)"
            >{{ verticalIcon(n.vertical) }}</span>
            <div class="min-w-0 flex-1">
              <p class="truncate text-sm font-semibold text-slate-100">{{ n.title }}</p>
              <p v-if="n.body" class="mt-0.5 line-clamp-2 text-xs text-slate-400">{{ n.body }}</p>
              <p class="mt-1 text-[10px] uppercase tracking-wide text-slate-500">{{ relativeTime(n.created_at) }}</p>
            </div>
            <span
              v-if="!n.is_read"
              aria-hidden="true"
              class="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-[var(--color-secondary)]"
            />
          </component>
        </li>
      </ul>

      <div v-if="hasMore" class="px-4 py-3 text-center">
        <button
          type="button"
          class="ui-press rounded-full border border-slate-700/60 px-4 py-1.5 text-xs font-medium text-slate-300 transition-colors hover:border-[var(--color-secondary)] hover:text-[var(--color-secondary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/40"
          :disabled="loading"
          @click="loadMore"
        >
          {{ t('notifications.loadMore') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import api from "../lib/api";
import { useI18n } from "../composables/useI18n";

const emit = defineEmits(["update-unread", "close"]);

const { t } = useI18n();

const items = ref([]);
const unreadCount = ref(0);
const hasMore = ref(false);
const nextBefore = ref(null);
const loading = ref(false);
const error = ref(false);

const VERTICAL_ICONS = {
  food: "🍔",
  shops: "🛍️",
  pharmacy: "💊",
  ride: "🚗",
  courier: "📦",
  wallet: "💳",
  general: "🔔",
};

const verticalIcon = (v) => VERTICAL_ICONS[v] || VERTICAL_ICONS.general;

const verticalBadgeClass = (v) => {
  switch (v) {
    case "wallet":
      return "bg-emerald-500/15";
    case "ride":
    case "courier":
      return "bg-sky-500/15";
    case "food":
    case "shops":
    case "pharmacy":
      return "bg-amber-500/15";
    default:
      return "bg-slate-700/40";
  }
};

// Locale-light relative time. Buckets to i18n strings with a {n} placeholder.
const relativeTime = (iso) => {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const diffSec = Math.max(0, Math.floor((Date.now() - then) / 1000));
  if (diffSec < 60) return t("notifications.timeNow");
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return t("notifications.timeMinutes", { n: diffMin });
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return t("notifications.timeHours", { n: diffHr });
  const diffDay = Math.floor(diffHr / 24);
  return t("notifications.timeDays", { n: diffDay });
};

const fetchPage = async (before = null) => {
  loading.value = true;
  error.value = false;
  try {
    const params = {};
    if (before) params.before = before;
    const { data } = await api.get("/customer/notifications/", { params });
    const rows = Array.isArray(data?.notifications) ? data.notifications : [];
    if (before) items.value = items.value.concat(rows);
    else items.value = rows;
    unreadCount.value = Number(data?.unread_count || 0);
    hasMore.value = !!data?.has_more;
    nextBefore.value = data?.next_before ?? null;
    emit("update-unread", unreadCount.value);
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
};

const loadMore = () => {
  if (nextBefore.value != null) fetchPage(nextBefore.value);
};

const markAllRead = async () => {
  try {
    const { data } = await api.post("/customer/notifications/mark-read/", { ids: [] });
    items.value = items.value.map((n) => ({ ...n, is_read: true }));
    unreadCount.value = Number(data?.unread_count || 0);
    emit("update-unread", unreadCount.value);
  } catch {
    /* best-effort: badge will reconcile on next poll */
  }
};

const onRowClick = (n) => {
  // A tapped row counts as read; deep-link navigation is handled by RouterLink.
  if (!n.is_read) {
    n.is_read = true;
    unreadCount.value = Math.max(0, unreadCount.value - 1);
    emit("update-unread", unreadCount.value);
    api.post("/customer/notifications/mark-read/", { ids: [n.id] }).catch(() => {});
  }
  if (n.url) emit("close");
};

onMounted(() => {
  // Opening the inbox loads the list AND marks everything read (open = acknowledged).
  fetchPage().then(() => {
    if (unreadCount.value > 0) markAllRead();
  });
});

defineExpose({ unreadCount: computed(() => unreadCount.value), refresh: () => fetchPage() });
</script>
