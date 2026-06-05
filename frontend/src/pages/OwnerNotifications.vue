<template>
  <div class="mx-auto max-w-4xl space-y-4 p-4">
    <!-- Header -->
    <div class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 class="ui-display text-xl font-semibold text-white">{{ t('ownerNotifications.title') }}</h1>
        <p class="text-xs text-slate-400">{{ t('ownerNotifications.subtitle') }}</p>
      </div>
      <button class="ui-btn-outline px-3 py-1.5 text-xs" :disabled="loading" @click="fetchLog">
        {{ loading ? t('common.loading') : t('ownerNotifications.refresh') }}
      </button>
    </div>

    <!-- Summary chips -->
    <div class="flex flex-wrap gap-2">
      <span class="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs text-emerald-300">
        {{ t('ownerNotifications.statusSent') }}: {{ summary.sent || 0 }}
      </span>
      <span class="rounded-full border border-red-500/30 bg-red-500/10 px-3 py-1 text-xs text-red-300">
        {{ t('ownerNotifications.statusFailed') }}: {{ summary.failed || 0 }}
      </span>
      <span class="rounded-full border border-slate-600/40 bg-slate-700/30 px-3 py-1 text-xs text-slate-300">
        {{ t('ownerNotifications.statusSkipped') }}: {{ summary.skipped || 0 }}
      </span>
    </div>

    <!-- Filters -->
    <div class="flex flex-wrap gap-2">
      <select v-model="channel" class="rounded-xl border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs text-slate-200" @change="fetchLog">
        <option value="">{{ t('ownerNotifications.allChannels') }}</option>
        <option value="push">{{ t('ownerNotifications.channelPush') }}</option>
        <option value="sms">{{ t('ownerNotifications.channelSms') }}</option>
        <option value="email">{{ t('ownerNotifications.channelEmail') }}</option>
        <option value="whatsapp">{{ t('ownerNotifications.channelWhatsapp') }}</option>
      </select>
      <select v-model="statusFilter" class="rounded-xl border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs text-slate-200" @change="fetchLog">
        <option value="">{{ t('ownerNotifications.allStatuses') }}</option>
        <option value="sent">{{ t('ownerNotifications.statusSent') }}</option>
        <option value="failed">{{ t('ownerNotifications.statusFailed') }}</option>
        <option value="skipped">{{ t('ownerNotifications.statusSkipped') }}</option>
      </select>
    </div>

    <!-- List -->
    <div v-if="loadError" class="rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5 text-sm text-red-300">
      {{ t('ownerNotifications.loadError') }}
    </div>
    <div v-else-if="!loading && !rows.length" class="rounded-xl border border-slate-800 bg-slate-900/40 px-3 py-8 text-center text-sm text-slate-500">
      {{ t('ownerNotifications.empty') }}
    </div>
    <ul v-else class="space-y-1.5">
      <li
        v-for="n in rows"
        :key="n.id"
        class="flex flex-wrap items-center gap-2 rounded-xl border border-slate-800 bg-slate-900/40 px-3 py-2 text-xs"
      >
        <span class="rounded-full px-2 py-0.5 font-semibold" :class="channelClass(n.channel)">{{ channelLabel(n.channel) }}</span>
        <span class="rounded-full px-2 py-0.5 font-semibold" :class="statusClass(n.status)">{{ statusLabel(n.status) }}</span>
        <span class="text-slate-300">{{ n.event || '—' }}</span>
        <span v-if="n.reference" class="font-mono text-slate-500">{{ n.reference }}</span>
        <span v-if="n.detail" class="truncate text-slate-500">{{ n.detail }}</span>
        <span v-if="n.recipient" class="text-slate-600">→ {{ n.recipient }}</span>
        <span v-if="n.error" class="text-red-400/80">{{ n.error }}</span>
        <span class="ml-auto whitespace-nowrap text-slate-600">{{ fmtTime(n.created_at) }}</span>
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
