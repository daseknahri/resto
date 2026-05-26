<template>
  <div class="space-y-4">
    <!-- Add new closure date -->
    <div class="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 space-y-3">
      <p class="text-sm font-medium text-slate-200">{{ t('closureDates.addDate') }}</p>
      <div class="flex flex-col gap-2 sm:flex-row sm:items-end">
        <div class="flex-1 space-y-1">
          <label class="text-xs text-slate-400">{{ t('closureDates.date') }}</label>
          <input
            v-model="newDate"
            type="date"
            :min="todayStr"
            class="w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-200 focus:border-[var(--color-secondary)] focus:outline-none"
          />
        </div>
        <div class="flex-1 space-y-1">
          <label class="text-xs text-slate-400">{{ t('closureDates.labelOptional') }}</label>
          <input
            v-model="newLabel"
            type="text"
            maxlength="100"
            :placeholder="t('closureDates.labelPlaceholder')"
            class="w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:border-[var(--color-secondary)] focus:outline-none"
            @keyup.enter="addDate"
          />
        </div>
        <button
          class="rounded-xl bg-[var(--color-secondary)] px-4 py-2 text-sm font-semibold text-slate-950 disabled:opacity-50 sm:flex-none"
          :disabled="!newDate || saving"
          @click="addDate"
        >
          {{ saving ? t('common.saving') : t('closureDates.add') }}
        </button>
      </div>
      <p v-if="addError" class="text-xs text-red-300">{{ addError }}</p>
    </div>

    <!-- Existing closure dates list -->
    <div v-if="loading" class="py-4 text-center text-sm text-slate-500">
      {{ t('common.loading') }}
    </div>

    <div v-else-if="dates.length === 0" class="rounded-2xl border border-dashed border-slate-700 p-4 text-center text-sm text-slate-500">
      {{ t('closureDates.empty') }}
    </div>

    <ul v-else class="space-y-2">
      <li
        v-for="closure in sortedDates"
        :key="closure.id"
        class="flex items-center justify-between gap-3 rounded-xl border border-slate-800 bg-slate-900/50 px-4 py-3"
        :class="isPast(closure.date) ? 'opacity-50' : ''"
      >
        <div class="min-w-0 flex-1">
          <p class="text-sm font-medium text-slate-200">{{ formatDate(closure.date) }}</p>
          <p v-if="closure.label" class="mt-0.5 truncate text-xs text-slate-500">{{ closure.label }}</p>
        </div>
        <div class="flex items-center gap-2">
          <span
            v-if="isPast(closure.date)"
            class="rounded-full border border-slate-700 px-2 py-0.5 text-[10px] font-medium text-slate-500"
          >
            {{ t('closureDates.past') }}
          </span>
          <span
            v-else-if="isToday(closure.date)"
            class="rounded-full border border-amber-500/40 bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium text-amber-300"
          >
            {{ t('closureDates.today') }}
          </span>
          <button
            class="flex h-7 w-7 items-center justify-center rounded-lg border border-slate-700 text-slate-400 hover:border-red-500/50 hover:text-red-400 transition-colors"
            :aria-label="t('common.remove')"
            @click="removeDate(closure.id)"
          >
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" class="h-3.5 w-3.5">
              <path d="M3 3l10 10M13 3L3 13" />
            </svg>
          </button>
        </div>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import api from '../lib/api'
import { useI18n } from '../composables/useI18n'
import { useToastStore } from '../stores/toast'

const { t, currentLocale } = useI18n()
const toast = useToastStore()

const dates = ref([])
const loading = ref(false)
const saving = ref(false)
const newDate = ref('')
const newLabel = ref('')
const addError = ref('')

const todayStr = computed(() => {
  const d = new Date()
  return d.toISOString().slice(0, 10)
})

const sortedDates = computed(() =>
  [...dates.value].sort((a, b) => a.date.localeCompare(b.date))
)

const isPast = (dateStr) => dateStr < todayStr.value
const isToday = (dateStr) => dateStr === todayStr.value

const formatDate = (dateStr) => {
  try {
    return new Intl.DateTimeFormat(currentLocale.value, {
      weekday: 'short',
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    }).format(new Date(dateStr + 'T12:00:00'))
  } catch {
    return dateStr
  }
}

const fetchDates = async () => {
  loading.value = true
  try {
    const { data } = await api.get('/owner/closure-dates/')
    dates.value = Array.isArray(data) ? data : []
  } catch {
    toast.show(t('closureDates.loadFailed'), 'error')
  } finally {
    loading.value = false
  }
}

const addDate = async () => {
  if (!newDate.value || saving.value) return
  addError.value = ''
  saving.value = true
  try {
    const { data } = await api.post('/owner/closure-dates/', {
      date: newDate.value,
      label: newLabel.value.trim(),
    })
    dates.value.push(data)
    newDate.value = ''
    newLabel.value = ''
    toast.show(t('closureDates.added'), 'success')
  } catch (err) {
    const detail = err?.response?.data?.detail || t('closureDates.addFailed')
    addError.value = detail
  } finally {
    saving.value = false
  }
}

const removeDate = async (id) => {
  try {
    await api.delete(`/owner/closure-dates/${id}/`)
    dates.value = dates.value.filter((d) => d.id !== id)
    toast.show(t('closureDates.removed'), 'success')
  } catch {
    toast.show(t('closureDates.removeFailed'), 'error')
  }
}

onMounted(fetchDates)
</script>
