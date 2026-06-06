<template>
  <main class="ui-page-shell max-w-4xl space-y-4">
    <!-- Header -->
    <header class="ui-hero-ribbon ui-reveal px-4 py-3.5 md:px-5 md:py-4">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div class="min-w-0">
          <p class="ui-kicker">{{ t('ownerNotifications.kicker') }}</p>
          <h1 class="ui-display text-xl font-semibold leading-tight tracking-tight text-white md:text-2xl">
            {{ t('ownerNotifications.title') }}
          </h1>
          <p class="ui-subtle mt-0.5 hidden text-xs sm:block">{{ t('ownerNotifications.subtitle') }}</p>
        </div>
        <div class="flex shrink-0 flex-wrap items-center gap-1.5">
          <span class="ui-chip tabular-nums">
            <span class="h-2 w-2 rounded-full bg-emerald-400/80"></span>
            {{ summary.sent || 0 }} {{ t('ownerNotifications.statusSent') }}
          </span>
          <span class="ui-chip tabular-nums">
            <span class="h-2 w-2 rounded-full bg-red-400/80"></span>
            {{ summary.failed || 0 }} {{ t('ownerNotifications.statusFailed') }}
          </span>
          <span class="ui-chip tabular-nums">
            <span class="h-2 w-2 rounded-full bg-slate-500/80"></span>
            {{ summary.skipped || 0 }} {{ t('ownerNotifications.statusSkipped') }}
          </span>
        </div>
      </div>
    </header>

    <!-- Filters toolbar -->
    <div class="ui-toolbar-band">
      <div class="flex flex-wrap items-center gap-2">
        <label class="sr-only" for="notif-channel-filter">{{ t('ownerNotifications.allChannels') }}</label>
        <select
          id="notif-channel-filter"
          v-model="channel"
          class="ui-input ui-touch-target max-w-[180px] py-1.5 text-xs"
          @change="fetchLog"
        >
          <option value="">{{ t('ownerNotifications.allChannels') }}</option>
          <option value="push">{{ t('ownerNotifications.channelPush') }}</option>
          <option value="sms">{{ t('ownerNotifications.channelSms') }}</option>
          <option value="email">{{ t('ownerNotifications.channelEmail') }}</option>
          <option value="whatsapp">{{ t('ownerNotifications.channelWhatsapp') }}</option>
        </select>
        <label class="sr-only" for="notif-status-filter">{{ t('ownerNotifications.allStatuses') }}</label>
        <select
          id="notif-status-filter"
          v-model="statusFilter"
          class="ui-input ui-touch-target max-w-[180px] py-1.5 text-xs"
          @change="fetchLog"
        >
          <option value="">{{ t('ownerNotifications.allStatuses') }}</option>
          <option value="sent">{{ t('ownerNotifications.statusSent') }}</option>
          <option value="failed">{{ t('ownerNotifications.statusFailed') }}</option>
          <option value="skipped">{{ t('ownerNotifications.statusSkipped') }}</option>
        </select>
        <button
          class="ui-btn-outline ui-press ui-touch-target ms-auto px-4 py-1.5 text-xs"
          :disabled="loading"
          :aria-label="t('ownerNotifications.refresh')"
          @click="fetchLog"
        >
          {{ loading ? t('common.loading') : t('ownerNotifications.refresh') }}
        </button>
      </div>
    </div>

    <!-- Error -->
    <div
      v-if="loadError"
      class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5"
      role="alert"
    >
      <svg class="mt-0.5 h-4 w-4 shrink-0 text-red-400" aria-hidden="true" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
      </svg>
      <p class="flex-1 text-sm text-red-300">{{ t('ownerNotifications.loadError') }}</p>
      <button class="ui-press shrink-0 text-xs text-red-400 underline underline-offset-2" @click="fetchLog">
        {{ t('common.retry') }}
      </button>
    </div>

    <!-- Loading skeletons -->
    <div v-else-if="loading" class="space-y-1.5" aria-busy="true" :aria-label="t('common.loading')">
      <div v-for="i in 6" :key="i" class="ui-skeleton h-10 rounded-xl" />
    </div>

    <!-- Empty -->
    <div v-else-if="!rows.length" class="ui-empty-state text-center">
      <p class="text-sm font-semibold text-slate-100">{{ t('ownerNotifications.empty') }}</p>
      <p class="mt-1 text-xs text-slate-400">{{ t('ownerNotifications.emptyHint') }}</p>
    </div>

    <!-- List -->
    <ul v-else class="space-y-1.5">
      <li
        v-for="(n, index) in rows"
        :key="n.id"
        class="ui-panel ui-reveal flex min-w-0 flex-wrap items-center gap-2 px-3 py-2.5 text-xs"
        :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
      >
        <span class="shrink-0 rounded-full px-2 py-0.5 font-semibold" :class="channelClass(n.channel)">{{ channelLabel(n.channel) }}</span>
        <span class="shrink-0 rounded-full px-2 py-0.5 font-semibold" :class="statusClass(n.status)">{{ statusLabel(n.status) }}</span>
        <span class="min-w-0 truncate text-slate-300">{{ n.event || '—' }}</span>
        <span v-if="n.reference" class="shrink-0 font-mono text-slate-500">{{ n.reference }}</span>
        <span v-if="n.detail" class="min-w-0 truncate text-slate-500">{{ n.detail }}</span>
        <span v-if="n.recipient" class="shrink-0 text-slate-500">
          <span aria-hidden="true" class="ltr:me-0.5 rtl:scale-x-[-1] rtl:inline-block">→</span>{{ n.recipient }}
        </span>
        <span v-if="n.error" class="min-w-0 truncate text-red-400/80">{{ n.error }}</span>
        <time class="ms-auto shrink-0 whitespace-nowrap tabular-nums text-slate-500" :datetime="n.created_at">{{ fmtTime(n.created_at) }}</time>
      </li>
    </ul>
  </main>
</template>

<script setup>
import { onMounted, ref } from 'vue';
import { useI18n } from '../composables/useI18n';
import api from '../lib/api';

const { t, currentLocale } = useI18n();

const rows = ref([]);
const summary = ref({});
const loading = ref(false);
const loadError = ref(false);
const channel = ref('');
const statusFilter = ref('');

const fetchLog = async () => {
  loading.value = true;
  loadError.value = false;
  try {
    const params = {};
    if (channel.value) params.channel = channel.value;
    if (statusFilter.value) params.status = statusFilter.value;
    const res = await api.get('/owner/notifications/', { params });
    rows.value = Array.isArray(res.data?.results) ? res.data.results : [];
    summary.value = res.data?.summary || {};
  } catch {
    loadError.value = true;
  } finally {
    loading.value = false;
  }
};

const fmtTime = (iso) => {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  try {
    return d.toLocaleString(currentLocale.value, { dateStyle: 'short', timeStyle: 'short' });
  } catch {
    return d.toLocaleString();
  }
};

const channelLabel = (c) => ({
  push: t('ownerNotifications.channelPush'),
  sms: t('ownerNotifications.channelSms'),
  email: t('ownerNotifications.channelEmail'),
  whatsapp: t('ownerNotifications.channelWhatsapp'),
}[c] || c);

const channelClass = (c) => ({
  push: 'bg-indigo-500/15 text-indigo-300',
  sms: 'bg-sky-500/15 text-sky-300',
  email: 'bg-violet-500/15 text-violet-300',
  whatsapp: 'bg-emerald-500/15 text-emerald-300',
}[c] || 'bg-slate-700/40 text-slate-300');

const statusLabel = (s) => ({
  sent: t('ownerNotifications.statusSent'),
  failed: t('ownerNotifications.statusFailed'),
  skipped: t('ownerNotifications.statusSkipped'),
}[s] || s);

const statusClass = (s) => ({
  sent: 'bg-emerald-500/15 text-emerald-300',
  failed: 'bg-red-500/15 text-red-300',
  skipped: 'bg-slate-600/30 text-slate-400',
}[s] || 'bg-slate-700/40 text-slate-300');

onMounted(fetchLog);
</script>
