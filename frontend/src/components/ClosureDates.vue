<template>
  <div class="space-y-3">
    <!-- Add new closure date -->
    <div class="ui-panel p-4 space-y-3 ui-reveal">
      <p class="ui-kicker">{{ t('closureDates.addDate') }}</p>
      <div class="flex flex-col gap-2 sm:flex-row sm:items-end">
        <div class="min-w-0 flex-1 space-y-1">
          <label for="closure-date" class="text-xs text-slate-400">{{ t('closureDates.date') }}</label>
          <input
            id="closure-date"
            v-model="newDate"
            type="date"
            :min="todayStr"
            class="ui-input"
          />
        </div>
        <div class="min-w-0 flex-1 space-y-1">
          <label for="closure-label" class="text-xs text-slate-400">{{ t('closureDates.labelOptional') }}</label>
          <input
            id="closure-label"
            v-model="newLabel"
            type="text"
            maxlength="100"
            :placeholder="t('closureDates.labelPlaceholder')"
            class="ui-input"
            @keyup.enter="addDate"
          />
        </div>
        <button
          class="ui-btn-primary ui-press ui-touch-target shrink-0 gap-1.5 disabled:opacity-50"
          :disabled="!newDate || saving"
          @click="addDate"
        >
          {{ saving ? t('common.saving') : t('closureDates.add') }}
        </button>
      </div>
      <div v-if="addError" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
        <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
        <p class="flex-1 text-sm text-red-300">{{ addError }}</p>
      </div>
    </div>

    <!-- Existing closure dates list -->
    <div v-if="loading" class="space-y-2">
      <div v-for="i in 2" :key="i" class="flex animate-pulse items-center justify-between rounded-xl border border-slate-800 bg-slate-900/40 px-4 py-3">
        <div class="space-y-1.5">
          <div class="h-3.5 w-24 rounded bg-slate-700/60" />
          <div class="h-3 w-32 rounded bg-slate-800/50" />
        </div>
        <div class="h-7 w-16 rounded-lg bg-slate-700/50" />
      </div>
    </div>

    <div v-else-if="dates.length === 0" class="ui-empty-state text-center">
      <p class="text-sm font-semibold text-slate-100">{{ t('closureDates.emptyTitle') }}</p>
      <p class="mt-0.5 text-xs text-slate-400">{{ t('closureDates.emptyBody') }}</p>
    </div>

    <ul v-else class="space-y-2">
      <li
        v-for="(closure, index) in sortedDates"
        :key="closure.id"
        class="ui-panel ui-reveal flex items-center justify-between gap-3 px-4 py-3"
        :class="isPast(closure.date) ? 'opacity-50' : ''"
        :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
      >
        <div class="min-w-0 flex-1">
          <p class="text-sm font-medium text-slate-200">{{ formatDate(closure.date) }}</p>
          <p v-if="closure.label" class="mt-0.5 truncate text-xs text-slate-500">{{ closure.label }}</p>
        </div>
        <div class="flex shrink-0 items-center gap-2">
          <span
            v-if="isPast(closure.date)"
            class="ui-chip text-[10px]"
          >
            {{ t('closureDates.past') }}
          </span>
          <span
            v-else-if="isToday(closure.date)"
            class="ui-chip-strong text-[10px]"
          >
            {{ t('closureDates.today') }}
          </span>
          <button
            class="ui-press ui-touch-target flex h-8 w-8 items-center justify-center rounded-lg border border-slate-700/80 text-slate-400 transition-colors hover:border-red-500/50 hover:text-red-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500/50"
            :aria-label="t('common.remove')"
            @click="removeDate(closure.id)"
          >
            <svg aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" class="h-3.5 w-3.5">
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
