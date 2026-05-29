<template>
  <div class="space-y-4 pb-6">
    <!-- Page header -->
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div class="space-y-0.5">
        <p class="ui-kicker">{{ t('ownerPromotions.kicker') }}</p>
        <h1 class="ui-display text-2xl font-semibold text-white sm:text-3xl">{{ t('ownerPromotions.title') }}</h1>
        <p class="text-sm text-slate-400">{{ t('ownerPromotions.subtitle') }}</p>
      </div>
      <div class="flex items-center gap-2">
        <svg v-if="updating" class="h-4 w-4 animate-spin text-slate-500" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <path d="M13.5 8a5.5 5.5 0 1 1-1.1-3.3M13.5 2v3.5H10"/>
        </svg>
        <button class="ui-btn-primary" @click="openCreate">{{ t('ownerPromotions.newPromotion') }}</button>
      </div>
    </div>

    <!-- Loading: skeleton cards -->
    <div v-if="loading" class="space-y-3">
      <div v-for="i in 3" :key="i" class="animate-pulse rounded-2xl border border-slate-700/40 bg-slate-900/60 p-4">
        <div class="flex items-start justify-between gap-4">
          <div class="flex-1 space-y-2">
            <div class="flex items-center gap-2">
              <div class="h-4 w-32 rounded-full bg-slate-700/60" />
              <div class="h-4 w-14 rounded-full bg-slate-800/60" />
            </div>
            <div class="h-3 w-24 rounded bg-slate-800/50" />
            <div class="h-3 w-48 rounded bg-slate-800/40" />
          </div>
          <div class="flex gap-2 shrink-0">
            <div class="h-7 w-12 rounded-lg bg-slate-800/60" />
            <div class="h-7 w-14 rounded-lg bg-slate-800/50" />
          </div>
        </div>
      </div>
    </div>

    <!-- Error -->
    <div v-else-if="fetchError" class="flex items-start gap-3 rounded-2xl border border-red-500/30 bg-red-500/8 px-4 py-3">
      <svg viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor">
        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm-.75-9.25a.75.75 0 011.5 0v3.5a.75.75 0 01-1.5 0v-3.5zm.75 6a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd" />
      </svg>
      <p class="flex-1 text-sm text-red-300">{{ t('ownerPromotions.fetchError') }}</p>
      <button
        class="shrink-0 rounded-lg border border-red-500/40 px-3 py-1 text-xs font-semibold text-red-300 transition hover:bg-red-500/10"
        @click="fetchPromotions"
      >{{ t('ownerPromotions.retry') }}</button>
    </div>

    <!-- Empty -->
    <div v-else-if="!promotions.length" class="rounded-2xl border border-slate-700/40 bg-slate-900/40 py-12 text-center space-y-1.5">
      <p class="text-2xl">🏷️</p>
      <p class="text-sm font-semibold text-slate-300">{{ t('ownerPromotions.noPromotions') }}</p>
      <p class="text-xs text-slate-500">{{ t('ownerPromotions.noPromotionsHint') }}</p>
    </div>

    <!-- List -->
    <div v-else class="space-y-3">
      <div
        v-for="promo in promotions"
        :key="promo.id"
        class="rounded-2xl border border-slate-700/60 bg-slate-900/60 p-4 flex items-start justify-between gap-4 transition-colors hover:border-slate-600"
      >
        <div class="flex-1 min-w-0 space-y-1.5">
          <div class="flex items-center gap-2 flex-wrap">
            <span class="text-sm font-semibold text-white">{{ promo.name }}</span>
            <span
              class="rounded-full px-2 py-0.5 text-[10px] font-semibold"
              :class="promo.is_active
                ? 'bg-emerald-500/15 border border-emerald-500/30 text-emerald-300'
                : 'bg-slate-700/50 border border-slate-600 text-slate-400'"
            >
              {{ promo.is_active ? t('ownerPromotions.activeNow') : t('ownerPromotions.inactive') }}
            </span>
          </div>
          <p class="text-xs text-slate-400">{{ promoLabel(promo) }}</p>
          <p v-if="promo.code" class="inline-flex items-center gap-1 rounded-md border border-indigo-500/30 bg-indigo-500/10 px-1.5 py-0.5 text-[10px] font-mono font-semibold text-indigo-300">
            <span class="opacity-60 font-sans font-normal">{{ t('ownerPromotions.codeLabel') }}:</span> {{ promo.code }}
          </p>
          <p v-if="promo.description" class="text-xs text-slate-500">{{ promo.description }}</p>
          <div class="flex flex-wrap gap-3 text-[11px] text-slate-500">
            <span v-if="promo.min_order_amount && Number(promo.min_order_amount) > 0">
              {{ t('ownerPromotions.minOrderShort', { amount: promo.min_order_amount }) }}
            </span>
            <span v-if="promo.days && promo.days.length">{{ promo.days.join(', ') }}</span>
            <span v-if="promo.time_start && promo.time_end">{{ promo.time_start }}–{{ promo.time_end }}</span>
            <span v-if="promo.active_from || promo.active_until">
              {{ promo.active_from || '∞' }} → {{ promo.active_until || '∞' }}
            </span>
            <span>{{ t('ownerPromotions.useCount_other', { count: promo.use_count }) }}</span>
          </div>
        </div>
        <div class="flex gap-2 shrink-0">
          <button
            class="rounded-lg border border-slate-700/50 bg-slate-800/50 px-2.5 py-1 text-xs text-slate-300 hover:border-slate-600 hover:text-white transition-colors"
            @click="openEdit(promo)"
          >{{ t('common.edit') }}</button>
          <button
            class="rounded-lg border border-red-500/30 bg-red-500/10 px-2.5 py-1 text-xs text-red-400 hover:border-red-500/50 hover:text-red-300 transition-colors"
            @click="deletePromo(promo)"
          >{{ t('common.delete') }}</button>
        </div>
      </div>
    </div>

    <!-- Create / Edit drawer -->
    <Teleport to="body">
      <div v-if="drawerOpen" class="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/60 backdrop-blur-sm px-3 pb-3 sm:pb-0">
        <div class="w-full max-w-md rounded-2xl border border-slate-700/70 bg-slate-900 p-5 space-y-4 max-h-[92vh] overflow-y-auto shadow-2xl">
          <div class="flex items-center justify-between">
            <h2 class="text-base font-bold text-white">
              {{ editingPromo ? t('common.edit') : t('ownerPromotions.newPromotion') }}
            </h2>
            <button
              class="rounded-lg border border-slate-700/50 bg-slate-800/50 p-1.5 text-slate-400 hover:border-slate-600 hover:text-white transition-colors"
              @click="drawerOpen = false"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" class="h-4 w-4">
                <path d="M6 6l12 12M18 6 6 18" />
              </svg>
            </button>
          </div>

          <!-- Name -->
          <div class="space-y-1.5">
            <label class="block text-xs font-semibold text-slate-300">{{ t('ownerPromotions.nameLabel') }}</label>
            <input
              v-model="form.name"
              type="text"
              :placeholder="t('ownerPromotions.namePlaceholder')"
              class="ui-input w-full"
            />
          </div>

          <!-- Description -->
          <div class="space-y-1.5">
            <label class="block text-xs font-semibold text-slate-300">{{ t('ownerPromotions.descriptionLabel') }}</label>
            <input v-model="form.description" type="text" class="ui-input w-full" />
          </div>

          <!-- Promo code -->
          <div class="space-y-1.5">
            <label class="block text-xs font-semibold text-slate-300">{{ t('ownerPromotions.codeLabel') }}</label>
            <input
              v-model="form.code"
              type="text"
              maxlength="20"
              class="ui-input w-full uppercase"
              :placeholder="t('ownerPromotions.codePlaceholder')"
              @input="form.code = form.code.toUpperCase()"
            />
            <p class="text-[11px] text-slate-500">{{ t('ownerPromotions.codeHint') }}</p>
          </div>

          <!-- Type -->
          <div class="space-y-1.5">
            <label class="block text-xs font-semibold text-slate-300">{{ t('ownerPromotions.typeLabel') }}</label>
            <div class="flex gap-2 flex-wrap">
              <button
                v-for="opt in promoTypes"
                :key="opt.value"
                type="button"
                class="rounded-xl border px-3 py-1.5 text-xs font-medium transition-colors"
                :class="form.promo_type === opt.value
                  ? 'border-[var(--color-secondary)]/60 bg-[var(--color-secondary)]/10 text-[var(--color-secondary)]'
                  : 'border-slate-700 text-slate-400 hover:border-slate-500'"
                @click="form.promo_type = opt.value"
              >{{ opt.label }}</button>
            </div>
          </div>

          <!-- Discount value -->
          <div v-if="form.promo_type !== 'free_delivery'" class="space-y-1.5">
            <label class="block text-xs font-semibold text-slate-300">
              {{ t('ownerPromotions.discountValueLabel') }}
              <span class="text-slate-500 font-normal ml-1">{{ form.promo_type === 'percentage' ? '%' : '' }}</span>
            </label>
            <input v-model="form.discount_value" type="number" min="0" step="0.01" class="ui-input w-full" />
            <p class="text-[11px] text-slate-500">{{ t('ownerPromotions.discountValueHint') }}</p>
          </div>

          <!-- Min order -->
          <div class="space-y-1.5">
            <label class="block text-xs font-semibold text-slate-300">{{ t('ownerPromotions.minOrderLabel') }}</label>
            <input v-model="form.min_order_amount" type="number" min="0" step="0.01" class="ui-input w-full" />
          </div>

          <!-- Days checkboxes -->
          <div class="space-y-1.5">
            <label class="block text-xs font-semibold text-slate-300">{{ t('ownerPromotions.daysLabel') }}</label>
            <div class="flex flex-wrap gap-1.5">
              <button
                v-for="d in DAYS"
                :key="d.key"
                type="button"
                class="rounded-full border px-2.5 py-0.5 text-[11px] font-medium transition-colors"
                :class="form.days.includes(d.key)
                  ? 'border-[var(--color-secondary)]/60 bg-[var(--color-secondary)]/10 text-[var(--color-secondary)]'
                  : 'border-slate-700 text-slate-400 hover:border-slate-500'"
                @click="toggleDay(d.key)"
              >{{ d.label }}</button>
            </div>
            <p class="text-[11px] text-slate-500">{{ t('ownerPromotions.daysHint') }}</p>
          </div>

          <!-- Time window -->
          <div class="space-y-1.5">
            <label class="block text-xs font-semibold text-slate-300">{{ t('ownerPromotions.timeLabel') }}</label>
            <div class="flex items-center gap-2">
              <input v-model="form.time_start" type="time" class="ui-input flex-1" />
              <span class="text-slate-500">—</span>
              <input v-model="form.time_end" type="time" class="ui-input flex-1" />
            </div>
          </div>

          <!-- Date range -->
          <div class="space-y-1.5">
            <label class="block text-xs font-semibold text-slate-300">{{ t('ownerPromotions.dateRangeLabel') }}</label>
            <div class="flex items-center gap-2">
              <input v-model="form.active_from" type="date" class="ui-input flex-1" />
              <span class="text-slate-500">—</span>
              <input v-model="form.active_until" type="date" class="ui-input flex-1" />
            </div>
          </div>

          <!-- Max uses -->
          <div class="space-y-1.5">
            <label class="block text-xs font-semibold text-slate-300">{{ t('ownerPromotions.maxUsesLabel') }}</label>
            <input v-model="form.max_uses" type="number" min="1" step="1" class="ui-input w-full" placeholder="∞" />
            <p class="text-[11px] text-slate-500">{{ t('ownerPromotions.maxUsesHint') }}</p>
          </div>

          <!-- Active toggle -->
          <label class="flex items-center gap-2.5 cursor-pointer rounded-xl border border-slate-700/50 bg-slate-800/40 px-3 py-2.5">
            <input type="checkbox" v-model="form.is_active" class="rounded" />
            <span class="text-sm text-slate-300">{{ t('ownerPromotions.isActiveLabel') }}</span>
          </label>

          <!-- Error -->
          <p v-if="drawerError" class="text-xs text-red-400">{{ drawerError }}</p>

          <!-- Submit -->
          <button
            class="ui-btn-primary w-full justify-center"
            :disabled="submitting"
            @click="submitForm"
          >
            {{ submitting
              ? (editingPromo ? t('ownerPromotions.saving') : t('ownerPromotions.creating'))
              : (editingPromo ? t('ownerPromotions.save') : t('ownerPromotions.create'))
            }}
          </button>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref, computed } from 'vue';
import { useI18n } from '../composables/useI18n';
import { useToastStore } from '../stores/toast';
import api from '../lib/api';
import { bustCache, isFresh, readCache, writeCache } from '../lib/staleCache';

const { t } = useI18n();
const toast = useToastStore();

// ── Constants ─────────────────────────────────────────────────────────────────
// Day keys — labels resolved via i18n (reuses stepDishes.weekday_* keys)
const DAY_KEYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];
const DAYS = computed(() => DAY_KEYS.map((key) => ({ key, label: t(`stepDishes.weekday_${key}`) })));

const promoTypes = computed(() => [
  { value: 'percentage', label: t('ownerPromotions.typePercentage') },
  { value: 'fixed', label: t('ownerPromotions.typeFixed') },
  { value: 'free_delivery', label: t('ownerPromotions.typeFreeDelivery') },
]);

const PROMOS_CACHE_KEY = 'owner.promotions';
const PROMOS_TTL_MS = 5 * 60 * 1000; // 5 min

// ── State ─────────────────────────────────────────────────────────────────────
const loading = ref(false);
const updating = ref(false);
const fetchError = ref(false);
const promotions = ref([]);
const drawerOpen = ref(false);
const editingPromo = ref(null);
const submitting = ref(false);
const drawerError = ref('');

const form = reactive({
  name: '',
  description: '',
  code: '',
  promo_type: 'percentage',
  discount_value: '',
  min_order_amount: '0',
  days: [],
  time_start: '',
  time_end: '',
  active_from: '',
  active_until: '',
  max_uses: '',
  is_active: true,
});

const resetForm = () => {
  form.name = '';
  form.description = '';
  form.code = '';
  form.promo_type = 'percentage';
  form.discount_value = '';
  form.min_order_amount = '0';
  form.days = [];
  form.time_start = '';
  form.time_end = '';
  form.active_from = '';
  form.active_until = '';
  form.max_uses = '';
  form.is_active = true;
};

// ── Helpers ───────────────────────────────────────────────────────────────────
const promoLabel = (promo) => {
  if (promo.promo_type === 'percentage') return t('ownerPromotions.labelPercentage', { value: promo.discount_value });
  if (promo.promo_type === 'fixed') return t('ownerPromotions.labelFixed', { value: promo.discount_value });
  return t('ownerPromotions.typeFreeDelivery');
};

const toggleDay = (key) => {
  const idx = form.days.indexOf(key);
  if (idx >= 0) form.days.splice(idx, 1);
  else form.days.push(key);
};

// ── Drawer ────────────────────────────────────────────────────────────────────
const openCreate = () => {
  editingPromo.value = null;
  resetForm();
  drawerError.value = '';
  drawerOpen.value = true;
};

const openEdit = (promo) => {
  editingPromo.value = promo;
  form.name = promo.name;
  form.description = promo.description || '';
  form.promo_type = promo.promo_type;
  form.discount_value = promo.discount_value;
  form.min_order_amount = promo.min_order_amount;
  form.days = [...(promo.days || [])];
  form.time_start = promo.time_start || '';
  form.time_end = promo.time_end || '';
  form.active_from = promo.active_from || '';
  form.active_until = promo.active_until || '';
  form.max_uses = promo.max_uses != null ? String(promo.max_uses) : '';
  form.is_active = promo.is_active;
  form.code = promo.code || '';
  drawerError.value = '';
  drawerOpen.value = true;
};

// ── API ───────────────────────────────────────────────────────────────────────
const fetchPromotions = async () => {
  const cached = readCache(PROMOS_CACHE_KEY);
  if (cached) {
    promotions.value = cached;
    if (isFresh(PROMOS_CACHE_KEY, PROMOS_TTL_MS)) return;
    updating.value = true;
  } else {
    loading.value = true;
  }
  fetchError.value = false;
  try {
    const res = await api.get('/owner/promotions/');
    promotions.value = res.data;
    writeCache(PROMOS_CACHE_KEY, res.data);
  } catch {
    if (!cached) fetchError.value = true;
  } finally {
    loading.value = false;
    updating.value = false;
  }
};

const submitForm = async () => {
  drawerError.value = '';
  if (!form.name.trim()) {
    drawerError.value = t('ownerPromotions.nameRequired');
    return;
  }
  submitting.value = true;
  const payload = {
    name: form.name.trim(),
    description: form.description.trim(),
    promo_type: form.promo_type,
    discount_value: form.discount_value || '0',
    min_order_amount: form.min_order_amount || '0',
    days: form.days,
    time_start: form.time_start || '',
    time_end: form.time_end || '',
    active_from: form.active_from || null,
    active_until: form.active_until || null,
    max_uses: form.max_uses ? parseInt(form.max_uses) : null,
    is_active: form.is_active,
    code: form.code.trim().toUpperCase(),
  };
  try {
    if (editingPromo.value) {
      const res = await api.patch(`/owner/promotions/${editingPromo.value.id}/`, payload);
      const idx = promotions.value.findIndex((p) => p.id === editingPromo.value.id);
      if (idx >= 0) promotions.value[idx] = res.data;
      writeCache(PROMOS_CACHE_KEY, promotions.value); // keep cache in sync
      toast.show(t('ownerPromotions.save'), 'success');
    } else {
      const res = await api.post('/owner/promotions/', payload);
      promotions.value.unshift(res.data);
      writeCache(PROMOS_CACHE_KEY, promotions.value);
      toast.show(t('ownerPromotions.create'), 'success');
    }
    drawerOpen.value = false;
  } catch {
    drawerError.value = editingPromo.value
      ? t('ownerPromotions.saveFailed')
      : t('ownerPromotions.createFailed');
  } finally {
    submitting.value = false;
  }
};

const deletePromo = async (promo) => {
  if (!confirm(t('ownerPromotions.deleteConfirm'))) return;
  try {
    await api.delete(`/owner/promotions/${promo.id}/`);
    promotions.value = promotions.value.filter((p) => p.id !== promo.id);
    writeCache(PROMOS_CACHE_KEY, promotions.value);
    toast.show(t('ownerPromotions.deleted'), 'success');
  } catch {
    toast.show(t('ownerPromotions.deleteFailed'), 'error');
  }
};

onMounted(fetchPromotions);
</script>
