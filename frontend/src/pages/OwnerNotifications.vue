<template>
  <div class="ui-page-shell max-w-4xl space-y-4">
    <!-- Header -->
    <header class="ui-hero-ribbon ui-reveal space-y-3 px-4 py-4 md:px-5">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div class="min-w-0 space-y-1">
          <p class="ui-kicker">{{ t('ownerNotifications.kicker') }}</p>
          <h1 class="ui-display text-2xl font-bold tracking-tight text-white md:text-3xl">
            {{ t('ownerNotifications.title') }}
          </h1>
          <p class="ui-subtle">{{ t('ownerNotifications.subtitle') }}</p>
        </div>
        <div class="shrink-0">
          <button
            class="ui-btn-outline ui-press ui-touch-target inline-flex items-center gap-1.5 px-3 py-1.5 text-sm disabled:opacity-50"
            :disabled="loading"
            :aria-busy="loading"
            @click="fetchLog"
          >
            <svg v-if="loading" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-4 w-4 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
            {{ loading ? t('common.loading') : t('ownerNotifications.refresh') }}
          </button>
        </div>
      </div>

      <!-- Summary stat bar -->
      <div class="grid grid-cols-3 gap-px overflow-hidden rounded-xl border border-slate-800 bg-slate-800">
        <div class="bg-slate-950/70 px-3 py-3 text-center">
          <p class="text-xl font-bold tabular-nums text-emerald-400">{{ summary.sent || 0 }}</p>
          <p class="ui-stat-label mt-0.5">{{ t('ownerNotifications.statusSent') }}</p>
        </div>
        <div class="bg-slate-950/70 px-3 py-3 text-center">
          <p class="text-xl font-bold tabular-nums text-red-400">{{ summary.failed || 0 }}</p>
          <p class="ui-stat-label mt-0.5">{{ t('ownerNotifications.statusFailed') }}</p>
        </div>
        <div class="bg-slate-950/70 px-3 py-3 text-center">
          <p class="text-xl font-bold tabular-nums text-slate-400">{{ summary.skipped || 0 }}</p>
          <p class="ui-stat-label mt-0.5">{{ t('ownerNotifications.statusSkipped') }}</p>
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
      </div>
    </div>

    <!-- Error -->
    <div
      v-if="loadError"
      class="flex items-start gap-2.5 rounded-xl border border-red-500/30 bg-red-500/8 px-4 py-3"
      role="alert"
    >
      <svg class="mt-0.5 h-4 w-4 shrink-0 text-red-400" aria-hidden="true" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
      </svg>
      <p class="flex-1 text-sm text-red-300">{{ t('ownerNotifications.loadError') }}</p>
      <button class="ui-press ui-touch-target shrink-0 rounded text-xs text-red-400 underline underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400" @click="fetchLog">
        {{ t('common.retry') }}
      </button>
    </div>

    <!-- Loading skeletons -->
    <div v-else-if="loading" class="space-y-2" aria-busy="true" aria-live="polite" :aria-label="t('common.loading')">
      <div v-for="i in 6" :key="i" class="ui-skeleton rounded-xl" :class="i % 3 === 0 ? 'h-12' : 'h-10'" />
    </div>

    <!-- Empty -->
    <div v-else-if="!rows.length" class="ui-empty-state py-12 text-center">
      <p class="text-sm font-semibold text-slate-100">{{ t('ownerNotifications.empty') }}</p>
      <p class="mt-1.5 text-xs text-slate-400">{{ t('ownerNotifications.emptyHint') }}</p>
    </div>

    <!-- List -->
    <ul v-else class="space-y-2">
      <li
        v-for="(n, index) in rows"
        :key="n.id"
        class="ui-panel ui-reveal min-w-0 px-4 py-3"
        :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
        :aria-label="`${channelLabel(n.channel)}, ${statusLabel(n.status)}, ${n.event || ''}`"
      >
        <!-- Top row: badges + time -->
        <div class="flex flex-wrap items-center gap-1.5">
          <span
            role="img"
            class="shrink-0 rounded-full px-2.5 py-0.5 text-[11px] font-semibold tracking-wide"
            :class="channelClass(n.channel)"
            :aria-label="channelLabel(n.channel)"
          >{{ channelLabel(n.channel) }}</span>
          <span
            role="img"
            class="shrink-0 rounded-full px-2.5 py-0.5 text-[11px] font-semibold tracking-wide"
            :class="statusClass(n.status)"
            :aria-label="statusLabel(n.status)"
          >{{ statusLabel(n.status) }}</span>
          <time
            class="ms-auto shrink-0 whitespace-nowrap tabular-nums text-[11px] text-slate-500"
            :datetime="n.created_at"
          >{{ fmtTime(n.created_at) }}</time>
        </div>
        <!-- Bottom row: event, recipient, reference, detail, error -->
        <div class="mt-1.5 flex min-w-0 flex-wrap items-center gap-x-3 gap-y-0.5 text-xs">
          <span class="min-w-0 truncate font-medium text-slate-200" :title="n.event || undefined">{{ n.event || '—' }}</span>
          <span v-if="n.recipient" class="shrink-0 text-slate-400">
            <span class="sr-only">{{ t('ownerNotifications.recipient') }}</span>
            <span aria-hidden="true" class="ltr:me-0.5 rtl:scale-x-[-1] rtl:inline-block">→</span>{{ n.recipient }}
          </span>
          <span v-if="n.reference" class="shrink-0 font-mono text-slate-500">{{ n.reference }}</span>
          <span v-if="n.detail" class="min-w-0 truncate text-slate-500" :title="n.detail">{{ n.detail }}</span>
          <span v-if="n.error" class="min-w-0 truncate text-red-400/80" :title="n.error">{{ n.error }}</span>
        </div>
      </li>
    </ul>
  </div>
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
