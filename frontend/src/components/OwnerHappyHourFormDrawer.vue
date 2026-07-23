<template>
  <!-- Happy Hour create/edit drawer -->
  <Teleport to="body">
    <div v-if="open" class="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/60 backdrop-blur-sm px-3 pb-3 sm:pb-0" @keydown.esc="emit('close')" @click.self="emit('close')">
      <div ref="dialogRef" role="dialog" aria-modal="true" aria-labelledby="owner-hh-form-dialog-title" class="ui-panel-soft w-full max-w-md max-h-[92vh] overflow-y-auto">

        <!-- Dialog header -->
        <div class="sticky top-0 z-10 flex items-center justify-between border-b border-slate-700/50 bg-[var(--color-elevated)] px-5 py-4">
          <h2 id="owner-hh-form-dialog-title" class="text-base font-bold tracking-tight text-white">
            {{ isEdit ? t('happyHour.edit') : t('happyHour.add') }}
          </h2>
          <button
            class="ui-press rounded-lg border border-slate-700/50 bg-slate-800/50 p-1.5 text-slate-400 hover:border-slate-600 hover:text-white transition-colors ui-touch-target"
            :aria-label="t('common.close')"
            @click="emit('close')"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" class="h-4 w-4" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18" /></svg>
          </button>
        </div>

        <!-- Form body -->
        <div class="space-y-5 px-5 py-5">
          <!-- Name -->
          <div class="space-y-1.5">
            <label for="hh-name" class="block text-xs font-semibold text-slate-300">{{ t('happyHour.nameLabel') }}</label>
            <input id="hh-name" v-model="form.name" type="text" :placeholder="t('happyHour.namePlaceholder')" class="ui-input w-full" />
          </div>

          <div class="border-t border-slate-700/40" />

          <!-- Percent off -->
          <div class="space-y-1.5">
            <label for="hh-pct" class="block text-xs font-semibold text-slate-300">{{ t('happyHour.percentOffLabel') }}</label>
            <input id="hh-pct" v-model.number="form.percent_off" type="number" min="1" max="90" step="1" class="ui-input w-full" />
            <p class="text-[11px] text-slate-500">{{ t('happyHour.percentOffHint') }}</p>
          </div>

          <div class="border-t border-slate-700/40" />

          <!-- Time window -->
          <div class="space-y-1.5">
            <p id="hh-time-label" class="block text-xs font-semibold text-slate-300">{{ t('ownerPromotions.timeLabel') }}</p>
            <div role="group" aria-labelledby="hh-time-label" class="flex items-center gap-2">
              <input v-model="form.start_time" type="time" class="ui-input flex-1" :aria-label="t('happyHour.startTimeLabel')" />
              <span class="text-slate-500 shrink-0" aria-hidden="true">—</span>
              <input v-model="form.end_time" type="time" class="ui-input flex-1" :aria-label="t('happyHour.endTimeLabel')" />
            </div>
            <p v-if="form.start_time && form.end_time && form.start_time > form.end_time" class="text-[11px] text-amber-400">{{ t('happyHour.overnightHint') }}</p>
          </div>

          <div class="border-t border-slate-700/40" />

          <!-- Active days (0=Mon…6=Sun) -->
          <div class="space-y-1.5">
            <p id="hh-days-label" class="block text-xs font-semibold text-slate-300">{{ t('happyHour.daysLabel') }}</p>
            <div role="group" aria-labelledby="hh-days-label" class="flex flex-wrap gap-1.5">
              <button
                v-for="d in dayOptions"
                :key="d.value"
                type="button"
                :aria-pressed="form.days.includes(d.value)"
                class="inline-flex min-h-[36px] items-center rounded-full border px-2.5 py-1.5 text-[11px] font-medium transition-colors"
                :class="form.days.includes(d.value)
                  ? 'border-[var(--color-secondary)]/60 bg-[var(--color-secondary)]/10 text-[var(--color-secondary)]'
                  : 'border-slate-700 text-slate-400 hover:border-slate-500'"
                @click="toggleDay(d.value)"
              >{{ d.label }}</button>
            </div>
            <p class="text-[11px] text-slate-500">{{ t('happyHour.daysHint') }}</p>
          </div>

          <div class="border-t border-slate-700/40" />

          <!-- Category scope -->
          <div class="space-y-1.5">
            <p id="hh-cat-label" class="block text-xs font-semibold text-slate-300">{{ t('happyHour.categoryLabel') }}</p>
            <div role="group" aria-labelledby="hh-cat-label" class="flex flex-wrap gap-1.5">
              <button
                v-for="cat in categories"
                :key="cat.id"
                type="button"
                :aria-pressed="form.category_ids.includes(cat.id)"
                class="inline-flex min-h-[36px] items-center rounded-xl border px-3 py-1.5 text-xs font-medium transition-colors"
                :class="form.category_ids.includes(cat.id)
                  ? 'border-[var(--color-secondary)]/60 bg-[var(--color-secondary)]/10 text-[var(--color-secondary)]'
                  : 'border-slate-700 text-slate-400 hover:border-slate-500'"
                @click="toggleCategory(cat.id)"
              >{{ cat.name }}</button>
            </div>
            <p class="text-[11px] text-slate-500">{{ t('happyHour.categoryHint') }}</p>
          </div>

          <div class="border-t border-slate-700/40" />

          <!-- Active toggle -->
          <label class="flex items-center gap-3 cursor-pointer rounded-xl border border-slate-700/50 bg-slate-800/40 px-4 py-3 ui-touch-target transition-colors hover:border-slate-600/60">
            <input v-model="form.is_active" type="checkbox" class="rounded" />
            <span class="text-sm font-medium text-slate-300">{{ t('happyHour.isActiveLabel') }}</span>
          </label>

          <!-- Error -->
          <div v-if="error" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
            <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
            <p class="flex-1 text-sm text-red-300">{{ error }}</p>
          </div>

          <!-- Submit -->
          <button
            class="ui-btn-primary w-full justify-center"
            :disabled="submitting"
            @click="emit('submit')"
          >
            {{ submitting
              ? (isEdit ? t('happyHour.saving') : t('happyHour.creating'))
              : (isEdit ? t('happyHour.save') : t('happyHour.create'))
            }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
// Happy Hour create/edit form drawer of OwnerPromotions.vue, extracted as a
// standalone child (RISK FE-2 — the first supervised v-model slice).
//
// The form STATE stays owned by the parent: `hhForm` is a reactive object the
// parent keeps and passes here via `v-model:form` (defineModel). Because the
// object is passed by reference, the field bindings below mutate the SAME object
// the parent holds — behaviour-identical to the original inline drawer, and
// (unlike v-model on a plain prop) lint-clean because `form` is a model, not a
// prop. The parent also keeps open/edit state, the category fetch, validation +
// the save API call (submitHHForm), and the error/submitting flags — the drawer
// forwards close/submit intent via emits and reflects `error`/`submitting` back.
//
// The two array-toggles (day / category) only mutate the form arrays, so they
// live here. The a11y focus trap moved in self-contained (own dialog ref +
// keydown listener + open watch + onBeforeUnmount cleanup), mirroring the other
// extracted modals. `dayOptions` (the i18n-labelled weekday list, also used by
// the parent's rule cards) and `categories` are passed down as props so they
// stay single-sourced in the parent.
import { nextTick, onBeforeUnmount, ref, watch } from 'vue';
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();

const form = defineModel('form', { type: Object, required: true });

const props = defineProps({
  /** Whether the drawer is open (parent-owned). */
  open: { type: Boolean, default: false },
  /** True when editing an existing rule (drives the title + button labels). */
  isEdit: { type: Boolean, default: false },
  /** Validation / save error message from the parent, or empty. */
  error: { type: String, default: '' },
  /** True while the parent's save request is in flight. */
  submitting: { type: Boolean, default: false },
  /** Weekday option list ({ value, label }) — the parent's HH_DAYS. */
  dayOptions: { type: Array, default: () => [] },
  /** Category options ({ id, name }) for the scope picker. */
  categories: { type: Array, default: () => [] },
});

const emit = defineEmits(['close', 'submit']);

// Day / category toggles mutate the shared form arrays (same object the parent
// owns), matching the original inline handlers.
const toggleDay = (val) => {
  const idx = form.value.days.indexOf(val);
  if (idx >= 0) form.value.days.splice(idx, 1);
  else form.value.days.push(val);
};

const toggleCategory = (id) => {
  const idx = form.value.category_ids.indexOf(id);
  if (idx >= 0) form.value.category_ids.splice(idx, 1);
  else form.value.category_ids.push(id);
};

// Focus trap (mirrors the parent's original happy-hour trap).
const dialogRef = ref(null);

const FOCUSABLE = [
  'a[href]', 'button:not([disabled])', 'input:not([disabled])',
  'select:not([disabled])', 'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(', ');

const trapFocus = (e) => {
  if (!dialogRef.value || e.key !== 'Tab') return;
  const focusable = Array.from(dialogRef.value.querySelectorAll(FOCUSABLE));
  if (!focusable.length) return;
  const first = focusable[0];
  const last  = focusable[focusable.length - 1];
  if (e.shiftKey) {
    if (document.activeElement === first) { e.preventDefault(); last.focus(); }
  } else {
    if (document.activeElement === last)  { e.preventDefault(); first.focus(); }
  }
};

watch(() => props.open, async (open) => {
  if (open) {
    await nextTick();
    dialogRef.value?.querySelector(FOCUSABLE)?.focus();
    document.addEventListener('keydown', trapFocus);
  } else {
    document.removeEventListener('keydown', trapFocus);
  }
});

onBeforeUnmount(() => document.removeEventListener('keydown', trapFocus));
</script>
