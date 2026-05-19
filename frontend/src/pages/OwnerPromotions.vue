<template>
  <div class="owner-page-root">
    <div class="owner-page-header">
      <div>
        <h1 class="owner-page-title">{{ t('ownerPromotions.title') }}</h1>
        <p class="owner-page-subtitle">{{ t('ownerPromotions.subtitle') }}</p>
      </div>
      <button class="btn-primary" @click="openCreate">{{ t('ownerPromotions.newPromotion') }}</button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="owner-section-card py-10 text-center text-sm text-slate-400">
      {{ t('common.loading') }}
    </div>

    <!-- Empty -->
    <div v-else-if="!promotions.length" class="owner-section-card py-12 text-center space-y-1">
      <p class="text-sm font-semibold text-slate-300">{{ t('ownerPromotions.noPromotions') }}</p>
      <p class="text-xs text-slate-500">{{ t('ownerPromotions.noPromotionsHint') }}</p>
    </div>

    <!-- List -->
    <div v-else class="space-y-3">
      <div
        v-for="promo in promotions"
        :key="promo.id"
        class="owner-section-card flex items-start justify-between gap-4"
      >
        <div class="flex-1 min-w-0 space-y-1">
          <div class="flex items-center gap-2 flex-wrap">
            <span class="text-sm font-semibold text-white">{{ promo.name }}</span>
            <span
              class="rounded-full px-2 py-0.5 text-[10px] font-semibold"
              :class="promo.is_active ? 'bg-emerald-500/15 text-emerald-300' : 'bg-slate-700 text-slate-400'"
            >
              {{ promo.is_active ? t('ownerPromotions.activeNow') : t('ownerPromotions.inactive') }}
            </span>
          </div>
          <p class="text-xs text-slate-400">{{ promoLabel(promo) }}</p>
          <p v-if="promo.code" class="inline-flex items-center gap-1 rounded-md border border-indigo-500/30 bg-indigo-500/10 px-1.5 py-0.5 text-[10px] font-mono font-semibold text-indigo-300">
            <span class="opacity-60 font-sans font-normal">{{ t('ownerPromotions.codeLabel') }}:</span> {{ promo.code }}
          </p>
          <p v-if="promo.description" class="text-xs text-slate-500">{{ promo.description }}</p>
          <div class="flex flex-wrap gap-3 text-[11px] text-slate-500 mt-1">
            <span v-if="promo.min_order_amount && Number(promo.min_order_amount) > 0">
              Min {{ promo.min_order_amount }}
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
          <button class="btn-sm-ghost" @click="openEdit(promo)">{{ t('common.edit') }}</button>
          <button class="btn-sm-danger" @click="deletePromo(promo)">{{ t('common.delete') }}</button>
        </div>
      </div>
    </div>

    <!-- Create / Edit drawer -->
    <Teleport to="body">
      <div v-if="drawerOpen" class="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/60 backdrop-blur-sm px-4 pb-4 sm:pb-0">
        <div class="w-full max-w-md bg-slate-900 rounded-2xl border border-slate-700 p-6 space-y-4 max-h-[90vh] overflow-y-auto">
          <div class="flex items-center justify-between">
            <h2 class="text-base font-bold text-white">
              {{ editingPromo ? t('common.edit') : t('ownerPromotions.newPromotion') }}
            </h2>
            <button class="text-slate-400 hover:text-white text-xl leading-none" @click="drawerOpen = false">✕</button>
          </div>

          <!-- Name -->
          <div>
            <label class="block text-xs font-medium text-slate-400 mb-1">{{ t('ownerPromotions.nameLabel') }}</label>
            <input
              v-model="form.name"
              type="text"
              :placeholder="t('ownerPromotions.namePlaceholder')"
              class="owner-input"
            />
          </div>

          <!-- Description -->
          <div>
            <label class="block text-xs font-medium text-slate-400 mb-1">{{ t('ownerPromotions.descriptionLabel') }}</label>
            <input v-model="form.description" type="text" class="owner-input" />
          </div>

          <!-- Promo code (optional) -->
          <div>
            <label class="block text-xs font-medium text-slate-400 mb-1">{{ t('ownerPromotions.codeLabel') }}</label>
            <input
              v-model="form.code"
              type="text"
              maxlength="20"
              class="owner-input uppercase"
              :placeholder="t('ownerPromotions.codePlaceholder')"
              @input="form.code = form.code.toUpperCase()"
            />
            <p class="mt-0.5 text-[10px] text-slate-600">{{ t('ownerPromotions.codeHint') }}</p>
          </div>

          <!-- Type -->
          <div>
            <label class="block text-xs font-medium text-slate-400 mb-1.5">{{ t('ownerPromotions.typeLabel') }}</label>
            <div class="flex gap-2 flex-wrap">
              <button
                v-for="opt in promoTypes"
                :key="opt.value"
                type="button"
                class="rounded-xl border px-3 py-1.5 text-xs font-medium transition-colors"
                :class="form.promo_type === opt.value
                  ? 'border-[var(--color-secondary,#f59e0b)]/60 bg-[var(--color-secondary,#f59e0b)]/10 text-[var(--color-secondary,#f59e0b)]'
                  : 'border-slate-700 text-slate-400 hover:border-slate-500'"
                @click="form.promo_type = opt.value"
              >{{ opt.label }}</button>
            </div>
          </div>

          <!-- Discount value (not shown for free_delivery) -->
          <div v-if="form.promo_type !== 'free_delivery'">
            <label class="block text-xs font-medium text-slate-400 mb-1">
              {{ t('ownerPromotions.discountValueLabel') }}
              <span class="text-slate-600 font-normal ml-1">{{ form.promo_type === 'percentage' ? '%' : '' }}</span>
            </label>
            <input v-model="form.discount_value" type="number" min="0" step="0.01" class="owner-input" />
            <p class="mt-0.5 text-[10px] text-slate-600">{{ t('ownerPromotions.discountValueHint') }}</p>
          </div>

          <!-- Min order -->
          <div>
            <label class="block text-xs font-medium text-slate-400 mb-1">{{ t('ownerPromotions.minOrderLabel') }}</label>
            <input v-model="form.min_order_amount" type="number" min="0" step="0.01" class="owner-input" />
          </div>

          <!-- Days checkboxes -->
          <div>
            <label class="block text-xs font-medium text-slate-400 mb-1.5">{{ t('ownerPromotions.daysLabel') }}</label>
            <div class="flex flex-wrap gap-1.5">
              <button
                v-for="d in DAYS"
                :key="d.key"
                type="button"
                class="rounded-full border px-2.5 py-0.5 text-[11px] font-medium transition-colors"
                :class="form.days.includes(d.key)
                  ? 'border-[var(--color-secondary,#f59e0b)]/60 bg-[var(--color-secondary,#f59e0b)]/10 text-[var(--color-secondary,#f59e0b)]'
                  : 'border-slate-700 text-slate-400 hover:border-slate-500'"
                @click="toggleDay(d.key)"
              >{{ d.label }}</button>
            </div>
            <p class="mt-0.5 text-[10px] text-slate-600">{{ t('ownerPromotions.daysHint') }}</p>
          </div>

          <!-- Time window -->
          <div>
            <label class="block text-xs font-medium text-slate-400 mb-1.5">{{ t('ownerPromotions.timeLabel') }}</label>
            <div class="flex items-center gap-2">
              <input v-model="form.time_start" type="time" class="owner-input flex-1" />
              <span class="text-slate-500 text-sm">—</span>
              <input v-model="form.time_end" type="time" class="owner-input flex-1" />
            </div>
          </div>

          <!-- Date range -->
          <div>
            <label class="block text-xs font-medium text-slate-400 mb-1.5">{{ t('ownerPromotions.dateRangeLabel') }}</label>
            <div class="flex items-center gap-2">
              <input v-model="form.active_from" type="date" class="owner-input flex-1" />
              <span class="text-slate-500 text-sm">—</span>
              <input v-model="form.active_until" type="date" class="owner-input flex-1" />
            </div>
          </div>

          <!-- Max uses -->
          <div>
            <label class="block text-xs font-medium text-slate-400 mb-1">{{ t('ownerPromotions.maxUsesLabel') }}</label>
            <input v-model="form.max_uses" type="number" min="1" step="1" class="owner-input" placeholder="∞" />
            <p class="mt-0.5 text-[10px] text-slate-600">{{ t('ownerPromotions.maxUsesHint') }}</p>
          </div>

          <!-- Active toggle -->
          <label class="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" v-model="form.is_active" class="rounded" />
            <span class="text-sm text-slate-300">{{ t('ownerPromotions.isActiveLabel') }}</span>
          </label>

          <!-- Error -->
          <p v-if="drawerError" class="text-xs text-red-400">{{ drawerError }}</p>

          <!-- Submit -->
          <button
            class="btn-primary w-full"
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

const { t } = useI18n();
const toast = useToastStore();

// ── Constants ─────────────────────────────────────────────────────────────────
const DAYS = [
  { key: 'mon', label: 'Mon' },
  { key: 'tue', label: 'Tue' },
  { key: 'wed', label: 'Wed' },
  { key: 'thu', label: 'Thu' },
  { key: 'fri', label: 'Fri' },
  { key: 'sat', label: 'Sat' },
  { key: 'sun', label: 'Sun' },
];

const promoTypes = computed(() => [
  { value: 'percentage', label: t('ownerPromotions.typePercentage') },
  { value: 'fixed', label: t('ownerPromotions.typeFixed') },
  { value: 'free_delivery', label: t('ownerPromotions.typeFreeDelivery') },
]);

// ── State ─────────────────────────────────────────────────────────────────────
const loading = ref(true);
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
  if (promo.promo_type === 'percentage') return `${promo.discount_value}% off`;
  if (promo.promo_type === 'fixed') return `${promo.discount_value} off`;
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
  loading.value = true;
  try {
    const res = await api.get('/owner/promotions/');
    promotions.value = res.data;
  } catch {
    // silent
  } finally {
    loading.value = false;
  }
};

const submitForm = async () => {
  drawerError.value = '';
  if (!form.name.trim()) {
    drawerError.value = t('ownerPromotions.nameLabel') + ' is required.';
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
      toast.show(t('ownerPromotions.save'));
    } else {
      const res = await api.post('/owner/promotions/', payload);
      promotions.value.unshift(res.data);
      toast.show(t('ownerPromotions.create'));
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
    toast.show(t('ownerPromotions.deleted'));
  } catch {
    toast.show(t('ownerPromotions.deleteFailed'), 'error');
  }
};

onMounted(fetchPromotions);
</script>
