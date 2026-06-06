<template>
  <div class="mx-auto max-w-md px-4 py-10">
    <main>
      <!-- Loading skeleton -->
      <div v-if="loading" class="ui-panel space-y-4 p-6" aria-busy="true" :aria-label="t('reservationManage.loading')">
        <div class="space-y-1.5">
          <div class="h-2.5 w-20 animate-pulse rounded bg-slate-700/60" />
          <div class="h-5 w-36 animate-pulse rounded bg-slate-700/40" />
        </div>
        <div class="space-y-3 pt-2">
          <div v-for="i in 3" :key="i" class="flex justify-between gap-3">
            <div class="h-3.5 w-20 animate-pulse rounded bg-slate-700/50" />
            <div class="h-3.5 w-28 animate-pulse rounded bg-slate-700/35" />
          </div>
        </div>
        <div class="h-10 animate-pulse rounded-xl bg-slate-700/40" />
      </div>

      <!-- Not-found / error state -->
      <div
        v-else-if="notFound"
        class="ui-empty-state space-y-2 p-6 text-center"
        role="alert"
      >
        <p class="text-sm font-semibold text-slate-100">{{ t('reservationManage.notFoundTitle') }}</p>
        <p class="text-xs text-slate-400">{{ t('reservationManage.notFound') }}</p>
      </div>

      <!-- Main card -->
      <div v-else class="ui-glass ui-reveal p-6 space-y-5">
        <!-- Header -->
        <div class="space-y-0.5">
          <p class="ui-kicker">{{ t('reservationManage.kicker') }}</p>
          <h1 class="text-xl font-semibold tracking-tight text-white">{{ t('reservationManage.title') }}</h1>
        </div>

        <!-- Details -->
        <dl class="space-y-2.5 text-sm">
          <div class="flex items-start justify-between gap-3">
            <dt class="text-slate-400">{{ t('reservationManage.restaurant') }}</dt>
            <dd class="min-w-0 text-end font-medium text-slate-100 truncate">{{ data.restaurant || '—' }}</dd>
          </div>
          <div v-if="data.booked_for" class="flex items-start justify-between gap-3">
            <dt class="text-slate-400 shrink-0">{{ t('reservationManage.when') }}</dt>
            <dd class="min-w-0 text-end font-medium text-slate-100 truncate">{{ formatWhen(data.booked_for) }}</dd>
          </div>
          <div v-if="data.party_size" class="flex items-start justify-between gap-3">
            <dt class="text-slate-400">{{ t('reservationManage.partySize') }}</dt>
            <dd class="font-medium tabular-nums text-slate-100">{{ data.party_size }}</dd>
          </div>
        </dl>

        <div class="ui-divider" />

        <!-- Cancelled state -->
        <div
          v-if="data.cancelled"
          class="flex items-center gap-2 rounded-xl border border-emerald-500/30 bg-emerald-500/8 px-3 py-3 text-sm text-emerald-300"
          role="status"
        >
          <svg class="h-4 w-4 shrink-0" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
            <path fill-rule="evenodd" d="M16.704 4.153a.75.75 0 0 1 .143 1.052l-8 10.5a.75.75 0 0 1-1.127.075l-4.5-4.5a.75.75 0 0 1 1.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 0 1 1.05-.143Z" clip-rule="evenodd" />
          </svg>
          <span>{{ t('reservationManage.cancelledState') }}</span>
        </div>

        <!-- Cancellable -->
        <div v-else-if="data.can_cancel" class="space-y-3">
          <div
            v-if="errorMsg"
            class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5"
            role="alert"
          >
            <svg class="mt-0.5 h-4 w-4 shrink-0 text-red-400" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
              <path fill-rule="evenodd" d="M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Zm-8-5a.75.75 0 0 1 .75.75v4.5a.75.75 0 0 1-1.5 0v-4.5A.75.75 0 0 1 10 5Zm0 10a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z" clip-rule="evenodd" />
            </svg>
            <p class="flex-1 text-sm text-red-300">{{ errorMsg }}</p>
          </div>
          <button
            class="ui-touch-target ui-press w-full rounded-xl border border-rose-500/50 bg-rose-500/10 px-4 text-sm font-semibold text-rose-200 transition hover:bg-rose-500/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-500/60 disabled:opacity-50"
            :disabled="cancelling"
            @click="cancel"
          >
            {{ cancelling ? t('reservationManage.cancelling') : t('reservationManage.cancelButton') }}
          </button>
        </div>

        <!-- Past / not cancellable -->
        <p
          v-else
          class="rounded-xl border border-slate-700/50 bg-slate-800/35 px-3 py-3 text-center text-sm text-slate-400"
        >
          {{ data.is_past ? t('reservationManage.tooLate') : t('reservationManage.notCancellable') }}
        </p>
      </div>
    </main>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue';
import api from '../lib/api';
import { useI18n } from '../composables/useI18n';

const props = defineProps({ token: { type: String, required: true } });
const { t, currentLocale } = useI18n();

const loading = ref(true);
const notFound = ref(false);
const cancelling = ref(false);
const errorMsg = ref('');
const data = reactive({
  restaurant: '', name: '', booked_for: null, party_size: null,
  status: '', cancelled: false, is_past: false, can_cancel: false,
});

const _apply = (d) => {
  data.restaurant = d.restaurant || '';
  data.name = d.name || '';
  data.booked_for = d.booked_for || null;
  data.party_size = d.party_size || null;
  data.status = d.status || '';
  data.cancelled = !!d.cancelled;
  data.is_past = !!d.is_past;
  data.can_cancel = !!d.can_cancel;
};

const formatWhen = (iso) => {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  try {
    return new Intl.DateTimeFormat(currentLocale.value, {
      weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
    }).format(d);
  } catch {
    return d.toLocaleString();
  }
};

const load = async () => {
  loading.value = true;
  notFound.value = false;
  try {
    const res = await api.get(`/reservations/manage/${props.token}/`);
    _apply(res.data);
  } catch {
    notFound.value = true;
  } finally {
    loading.value = false;
  }
};

const cancel = async () => {
  if (cancelling.value) return;
  if (!window.confirm(t('reservationManage.cancelConfirm'))) return;
  cancelling.value = true;
  errorMsg.value = '';
  try {
    const res = await api.post(`/reservations/manage/${props.token}/cancel/`);
    _apply(res.data);
  } catch (err) {
    errorMsg.value = err?.response?.data?.detail || t('reservationManage.cancelFailed');
  } finally {
    cancelling.value = false;
  }
};

onMounted(load);
</script>
