<template>
  <div class="mx-auto max-w-md px-4 py-10">
    <div class="rounded-2xl border border-slate-800 bg-slate-900 p-6">
      <h1 class="text-lg font-semibold text-slate-100">{{ t('reservationManage.title') }}</h1>

      <p v-if="loading" class="mt-4 text-sm text-slate-400">{{ t('reservationManage.loading') }}</p>

      <p v-else-if="notFound" class="mt-4 text-sm text-rose-300">{{ t('reservationManage.notFound') }}</p>

      <div v-else class="mt-4 space-y-4">
        <dl class="space-y-2 text-sm">
          <div class="flex justify-between gap-3">
            <dt class="text-slate-500">{{ t('reservationManage.restaurant') }}</dt>
            <dd class="font-medium text-slate-200">{{ data.restaurant || '—' }}</dd>
          </div>
          <div v-if="data.booked_for" class="flex justify-between gap-3">
            <dt class="text-slate-500">{{ t('reservationManage.when') }}</dt>
            <dd class="font-medium text-slate-200">{{ formatWhen(data.booked_for) }}</dd>
          </div>
          <div v-if="data.party_size" class="flex justify-between gap-3">
            <dt class="text-slate-500">{{ t('reservationManage.partySize') }}</dt>
            <dd class="font-medium text-slate-200">{{ data.party_size }}</dd>
          </div>
        </dl>

        <!-- Cancelled state -->
        <div v-if="data.cancelled" class="rounded-xl border border-slate-700/60 bg-slate-800/40 p-3 text-center text-sm text-slate-300">
          ✓ {{ t('reservationManage.cancelledState') }}
        </div>

        <!-- Cancellable -->
        <div v-else-if="data.can_cancel" class="space-y-2">
          <p v-if="errorMsg" class="text-sm text-rose-300">{{ errorMsg }}</p>
          <button
            class="w-full rounded-xl border border-rose-500/50 bg-rose-500/10 px-4 py-2.5 text-sm font-semibold text-rose-200 hover:bg-rose-500/20 disabled:opacity-50"
            :disabled="cancelling"
            @click="cancel"
          >
            {{ cancelling ? t('reservationManage.cancelling') : t('reservationManage.cancelButton') }}
          </button>
        </div>

        <!-- Past / not cancellable -->
        <p v-else class="rounded-xl border border-slate-700/60 bg-slate-800/40 p-3 text-center text-sm text-slate-400">
          {{ data.is_past ? t('reservationManage.tooLate') : t('reservationManage.notCancellable') }}
        </p>
      </div>
    </div>
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
