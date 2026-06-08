<template>
  <main class="mx-auto max-w-md px-4 py-10" aria-labelledby="rm-heading">

    <!-- ── Loading skeleton ────────────────────────────────────────────── -->
    <div v-if="loading" class="space-y-4" aria-busy="true" :aria-label="t('reservationManage.loading')">
      <!-- Icon placeholder -->
      <div class="flex justify-center">
        <div class="h-16 w-16 animate-pulse rounded-2xl bg-slate-800/60" />
      </div>
      <!-- Card skeleton -->
      <div class="rounded-[1.35rem] border border-slate-800/60 bg-slate-900/60 p-6 space-y-4">
        <div class="space-y-1.5">
          <div class="h-2.5 w-20 animate-pulse rounded bg-slate-700/60" />
          <div class="h-6 w-44 animate-pulse rounded bg-slate-700/40" />
        </div>
        <div class="space-y-3 pt-2">
          <div v-for="i in 3" :key="i" class="flex justify-between gap-3">
            <div class="h-4 w-24 animate-pulse rounded bg-slate-700/50" />
            <div class="h-4 w-32 animate-pulse rounded bg-slate-700/35" />
          </div>
        </div>
        <div class="h-11 animate-pulse rounded-xl bg-slate-700/40" />
      </div>
    </div>

    <!-- ── Not-found / error state ─────────────────────────────────────── -->
    <div
      v-else-if="notFound"
      class="ui-empty-state ui-reveal text-center space-y-4 p-8"
      role="alert"
    >
      <div
        class="mx-auto flex h-14 w-14 items-center justify-center rounded-full border border-slate-700/50 bg-slate-900/60"
        aria-hidden="true"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" class="h-7 w-7 text-slate-500">
          <circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/>
        </svg>
      </div>
      <div class="space-y-1.5">
        <p class="text-base font-semibold text-slate-100">{{ t('reservationManage.notFoundTitle') }}</p>
        <p class="text-sm leading-relaxed text-slate-400">{{ t('reservationManage.notFound') }}</p>
      </div>
    </div>

    <!-- ── Main card ───────────────────────────────────────────────────── -->
    <template v-else>
      <!-- Icon hero -->
      <div class="mb-5 flex flex-col items-center gap-3 ui-reveal text-center" style="--ui-delay:0ms">
        <div
          class="flex h-16 w-16 items-center justify-center rounded-2xl border"
          :class="data.cancelled
            ? 'border-emerald-500/25 bg-emerald-500/10'
            : 'border-[var(--color-secondary)]/25 bg-[var(--color-secondary)]/10'"
          aria-hidden="true"
        >
          <!-- Calendar check when done, calendar when active -->
          <svg
            v-if="data.cancelled"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.75"
            stroke-linecap="round"
            stroke-linejoin="round"
            class="h-8 w-8 text-emerald-400"
          >
            <path d="M8 2v4M16 2v4M3 10h18M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z"/><path d="m9 16 2 2 4-4"/>
          </svg>
          <svg
            v-else
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.75"
            stroke-linecap="round"
            stroke-linejoin="round"
            class="h-8 w-8 text-[var(--color-secondary)]"
          >
            <path d="M8 2v4M16 2v4M3 10h18M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z"/>
          </svg>
        </div>
        <div>
          <p class="ui-kicker">{{ t('reservationManage.kicker') }}</p>
          <h1 id="rm-heading" class="ui-display mt-0.5 text-xl font-bold text-white">
            {{ data.restaurant || t('reservationManage.title') }}
          </h1>
        </div>
      </div>

      <!-- Detail card -->
      <div class="ui-glass ui-reveal space-y-5 p-5 sm:p-6" style="--ui-delay:56ms">

        <!-- Cancelled banner -->
        <div
          v-if="data.cancelled"
          class="flex items-center gap-3 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3.5"
          role="status"
        >
          <svg class="h-5 w-5 shrink-0 text-emerald-400" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z" clip-rule="evenodd"/>
          </svg>
          <p class="text-sm font-medium text-emerald-200">{{ t('reservationManage.cancelledState') }}</p>
        </div>

        <!-- Reservation details -->
        <dl class="space-y-3">
          <div v-if="data.restaurant" class="flex items-start justify-between gap-3">
            <dt class="flex min-w-0 shrink-0 items-center gap-2 text-sm text-slate-400">
              <svg class="h-3.5 w-3.5 shrink-0 text-slate-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>
              </svg>
              {{ t('reservationManage.restaurant') }}
            </dt>
            <dd class="min-w-0 text-end text-sm font-semibold text-slate-100 truncate">{{ data.restaurant }}</dd>
          </div>

          <div v-if="data.booked_for" class="flex items-start justify-between gap-3">
            <dt class="flex min-w-0 shrink-0 items-center gap-2 text-sm text-slate-400">
              <svg class="h-3.5 w-3.5 shrink-0 text-slate-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
              </svg>
              {{ t('reservationManage.when') }}
            </dt>
            <dd class="min-w-0 text-end text-sm font-semibold text-slate-100">{{ formatWhen(data.booked_for) }}</dd>
          </div>

          <div v-if="data.party_size" class="flex items-start justify-between gap-3">
            <dt class="flex min-w-0 shrink-0 items-center gap-2 text-sm text-slate-400">
              <svg class="h-3.5 w-3.5 shrink-0 text-slate-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>
              </svg>
              {{ t('reservationManage.partySize') }}
            </dt>
            <dd class="text-end text-sm font-semibold tabular-nums text-slate-100">
              {{ data.party_size }} {{ data.party_size === 1 ? t('reservationManage.person') : t('reservationManage.people') }}
            </dd>
          </div>
        </dl>

        <div class="border-t border-slate-800/60" />

        <!-- ── Cancellable: inline confirm flow ────────────────────── -->
        <div v-if="!data.cancelled && data.can_cancel" class="space-y-3">
          <!-- Error alert -->
          <div
            v-if="errorMsg"
            id="cancel-error"
            class="flex items-start gap-2.5 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-3"
            role="alert"
          >
            <svg class="mt-0.5 h-4 w-4 shrink-0 text-red-400" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
              <path fill-rule="evenodd" d="M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Zm-8-5a.75.75 0 0 1 .75.75v4.5a.75.75 0 0 1-1.5 0v-4.5A.75.75 0 0 1 10 5Zm0 10a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z" clip-rule="evenodd"/>
            </svg>
            <p class="flex-1 text-sm text-red-300">{{ errorMsg }}</p>
          </div>

          <!-- Confirmation step -->
          <Transition name="ui-fade" mode="out-in">
            <!-- Not yet confirming: single cancel button -->
            <div v-if="!confirming" key="initial">
              <button
                type="button"
                class="ui-btn-outline ui-touch-target ui-press w-full border-rose-500/40 text-rose-200 hover:border-rose-500/60 hover:bg-rose-500/10 hover:text-rose-100"
                :aria-describedby="errorMsg ? 'cancel-error' : undefined"
                :disabled="cancelling"
                @click="confirming = true"
              >
                <svg class="h-4 w-4 shrink-0" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                  <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.28 7.22a.75.75 0 00-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 101.06 1.06L10 11.06l1.72 1.72a.75.75 0 101.06-1.06L11.06 10l1.72-1.72a.75.75 0 00-1.06-1.06L10 8.94 8.28 7.22z" clip-rule="evenodd"/>
                </svg>
                {{ t('reservationManage.cancelButton') }}
              </button>
            </div>

            <!-- Confirming: two-step confirmation -->
            <div v-else key="confirm" class="space-y-3 rounded-xl border border-rose-500/25 bg-rose-500/8 p-4">
              <div class="flex items-start gap-3">
                <svg class="mt-0.5 h-5 w-5 shrink-0 text-rose-400" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                  <path fill-rule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/>
                </svg>
                <div class="space-y-0.5">
                  <p class="text-sm font-semibold text-rose-100">{{ t('reservationManage.confirmTitle') }}</p>
                  <p class="text-xs leading-relaxed text-rose-200/75">{{ t('reservationManage.confirmBody') }}</p>
                </div>
              </div>
              <div class="flex gap-2.5">
                <button
                  type="button"
                  class="ui-btn-primary ui-press flex-1 py-2.5 text-sm"
                  style="--color-secondary: #f43f5e; --color-secondary-rgb: 244,63,94"
                  :disabled="cancelling"
                  @click="cancel"
                >
                  <span aria-live="polite" aria-atomic="true">
                    {{ cancelling ? t('reservationManage.cancelling') : t('reservationManage.confirmYes') }}
                  </span>
                </button>
                <button
                  type="button"
                  class="ui-btn-outline ui-press px-4 py-2.5 text-sm"
                  :disabled="cancelling"
                  @click="confirming = false"
                >
                  {{ t('common.back') }}
                </button>
              </div>
            </div>
          </Transition>
        </div>

        <!-- ── Past / not cancellable ────────────────────────────── -->
        <p
          v-else-if="!data.cancelled"
          class="rounded-xl border border-slate-700/50 bg-slate-800/35 px-4 py-3.5 text-center text-sm text-slate-400"
        >
          {{ data.is_past ? t('reservationManage.tooLate') : t('reservationManage.notCancellable') }}
        </p>
      </div>
    </template>
  </main>
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
const confirming = ref(false);
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
      weekday: 'long', day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit',
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
  cancelling.value = true;
  errorMsg.value = '';
  try {
    const res = await api.post(`/reservations/manage/${props.token}/cancel/`);
    _apply(res.data);
    confirming.value = false;
  } catch (err) {
    errorMsg.value = err?.response?.data?.detail || t('reservationManage.cancelFailed');
    confirming.value = false;
  } finally {
    cancelling.value = false;
  }
};

onMounted(load);
</script>
