<template>
  <div class="space-y-3">
    <!-- Week navigation -->
    <nav :aria-label="t('reservationCalendar.weekNav')" class="flex items-center justify-between gap-3">
      <button
        class="ui-btn-outline ui-press ui-touch-target inline-flex items-center gap-1 px-3 text-xs"
        :aria-label="t('reservationCalendar.prevWeek')"
        @click="prevWeek"
      >
        <span class="rtl:scale-x-[-1] inline-block" aria-hidden="true">&#8249;</span>
        {{ t("reservationCalendar.prevWeek") }}
      </button>
      <p class="text-sm font-semibold tabular-nums text-slate-100">{{ weekLabel }}</p>
      <button
        class="ui-btn-outline ui-press ui-touch-target inline-flex items-center gap-1 px-3 text-xs"
        :aria-label="t('reservationCalendar.nextWeek')"
        @click="nextWeek"
      >
        {{ t("reservationCalendar.nextWeek") }}
        <span class="rtl:scale-x-[-1] inline-block" aria-hidden="true">&#8250;</span>
      </button>
    </nav>

    <!-- Live region for drag-and-drop announcements -->
    <div role="status" aria-live="polite" aria-atomic="true" class="sr-only">{{ dropAnnouncement }}</div>

    <!-- Loading -->
    <div v-if="loading" class="flex gap-2 overflow-x-auto pb-1">
      <div
        v-for="i in 7"
        :key="i"
        class="ui-skeleton h-40 shrink-0 w-[90px] sm:w-[calc((100%-6*0.375rem)/7)]"
      />
    </div>

    <!-- Week grid -->
    <div
      v-else
      class="flex gap-1.5 overflow-x-auto pb-1 -mx-0.5 px-0.5"
      role="region"
      :aria-label="t('reservationCalendar.weekGrid')"
    >
      <div
        v-for="(day, dayIndex) in weekDays"
        :key="day.iso"
        class="shrink-0 w-[90px] sm:w-[calc((100%-6*0.375rem)/7)] min-h-[140px] rounded-2xl border transition-colors ui-reveal"
        :style="{ '--ui-delay': `${Math.min(dayIndex, 6) * 30}ms` }"
        :class="[
          isToday(day.iso) ? 'border-[var(--color-primary)]/40 bg-[var(--color-primary)]/10' : 'border-slate-700/40 bg-slate-800/20',
          dragOverDay === day.iso ? 'ring-2 ring-[var(--color-primary)]/50' : '',
        ]"
        role="group"
        :aria-label="day.dayName"
        @dragover.prevent="dragOverDay = day.iso"
        @dragleave="dragOverDay = null"
        @drop.prevent="onDrop(day.iso)"
      >
        <!-- Day header -->
        <div
          :id="'cal-day-' + day.iso"
          class="rounded-t-2xl px-2 py-1.5 text-center"
          :class="isToday(day.iso) ? 'bg-[var(--color-primary)]/20' : 'bg-slate-800/40'"
        >
          <p class="text-[10px] font-semibold uppercase tracking-widest text-slate-400">{{ day.dayName }}</p>
          <p
            class="text-lg font-bold tabular-nums"
            :class="isToday(day.iso) ? 'text-[var(--color-primary)]' : 'text-slate-100'"
          >
            {{ day.dayNum }}
          </p>
        </div>

        <!-- Reservation chips -->
        <ul :aria-labelledby="'cal-day-' + day.iso" class="space-y-1 p-1.5">
          <li
            v-for="(res, resIndex) in reservationsByDay[day.iso] || []"
            :key="res.id"
          >
            <button
              type="button"
              class="w-full text-left ui-press cursor-grab rounded-xl border px-2 py-1.5 text-[11px] transition-all active:cursor-grabbing focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)] focus-visible:ring-offset-1 focus-visible:ring-offset-slate-900 ui-reveal"
              :style="{ '--ui-delay': `${Math.min(resIndex, 5) * 20}ms` }"
              :class="statusChipClass(res.status)"
              :aria-label="[res.name, res.booked_for ? timeLabel(res.booked_for) : '', res.party_size ? t('reservationCalendar.guests', { n: res.party_size }) : '', t('reservationCalendar.moveHint')].filter(Boolean).join(', ')"
              aria-roledescription="draggable"
              aria-keyshortcuts="ArrowLeft ArrowRight"
              draggable="true"
              @dragstart="onDragStart(res)"
              @click="$emit('select', res)"
              @keydown.left.right.up.down.prevent="onChipKeydown($event, res, day.iso)"
            >
              <p class="min-w-0 truncate font-semibold text-slate-100">{{ res.name }}</p>
              <p v-if="res.booked_for" class="tabular-nums text-slate-400">{{ timeLabel(res.booked_for) }}</p>
              <p v-if="res.party_size" class="text-slate-500">{{ t("reservationCalendar.guests", { n: res.party_size }) }}</p>
              <span
                class="mt-1 inline-block rounded-full px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide"
                :class="statusBadgeClass(res.status)"
              >
                {{ statusLabelShort(res.status) }}
              </span>
            </button>
          </li>

          <!-- Empty day hint -->
          <li
            v-if="!(reservationsByDay[day.iso] || []).length"
            role="note"
          >
            <p class="px-1 py-2 text-center text-[10px] text-slate-600">
              {{ t("reservationCalendar.emptyDay") }}
            </p>
          </li>
        </ul>
      </div>
    </div>

    <!-- No-date reservations note -->
    <p v-if="undatedCount > 0" class="ui-subtle text-center text-xs tabular-nums">
      {{ t("reservationCalendar.undatedNote", { count: undatedCount }) }}
    </p>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from "vue";
import api from "../lib/api";
import { useI18n } from "../composables/useI18n";

const { t, currentLocale } = useI18n();

const emit = defineEmits(["select", "rescheduled"]);

// ── Week navigation ────────────────────────────────────────────────────────────
const weekOffset = ref(0); // 0 = current week, -1 = last week, etc.

const mondayOfWeek = computed(() => {
  const now = new Date();
  const day = now.getDay(); // 0=Sun
  const diff = (day === 0 ? -6 : 1 - day); // shift to Monday
  const mon = new Date(now);
  mon.setDate(now.getDate() + diff + weekOffset.value * 7);
  mon.setHours(0, 0, 0, 0);
  return mon;
});

const weekDays = computed(() => {
  const days = [];
  const fmt = new Intl.DateTimeFormat(currentLocale.value, { weekday: "short" });
  for (let i = 0; i < 7; i++) {
    const d = new Date(mondayOfWeek.value);
    d.setDate(d.getDate() + i);
    days.push({
      iso: d.toISOString().slice(0, 10),
      dayName: fmt.format(d),
      dayNum: d.getDate(),
      date: d,
    });
  }
  return days;
});

const weekLabel = computed(() => {
  const start = weekDays.value[0];
  const end = weekDays.value[6];
  const fmtDate = (d) => new Intl.DateTimeFormat(currentLocale.value, { month: "short", day: "numeric" }).format(new Date(d.iso));
  return `${fmtDate(start)} – ${fmtDate(end)}`;
});

const isToday = (iso) => iso === new Date().toISOString().slice(0, 10);

const prevWeek = () => weekOffset.value--;
const nextWeek = () => weekOffset.value++;

// ── Data fetching ──────────────────────────────────────────────────────────────
const reservations = ref([]);
const loading = ref(false);

const fetchWeek = async () => {
  loading.value = true;
  try {
    const from = weekDays.value[0].iso;
    const to = weekDays.value[6].iso;
    // Fetch reservations with booked_for in this week range
    const res = await api.get("/owner/reservations/", {
      params: { from, to, page_size: 200 },
    });
    reservations.value = Array.isArray(res.data?.results) ? res.data.results : [];
  } catch {
    reservations.value = [];
  } finally {
    loading.value = false;
  }
};

watch(weekOffset, fetchWeek);
onMounted(fetchWeek);

// ── Group by day ───────────────────────────────────────────────────────────────
const reservationsByDay = computed(() => {
  const groups = {};
  for (const r of reservations.value) {
    if (!r.booked_for) continue;
    const dayIso = r.booked_for.slice(0, 10);
    if (!groups[dayIso]) groups[dayIso] = [];
    groups[dayIso].push(r);
  }
  // Sort each day by time
  for (const day of Object.keys(groups)) {
    groups[day].sort((a, b) => (a.booked_for || "").localeCompare(b.booked_for || ""));
  }
  return groups;
});

const undatedCount = computed(() => reservations.value.filter((r) => !r.booked_for).length);

const timeLabel = (iso) => {
  try {
    return new Intl.DateTimeFormat(currentLocale.value, { hour: "2-digit", minute: "2-digit" }).format(new Date(iso));
  } catch {
    return "";
  }
};

// ── Drag and drop ──────────────────────────────────────────────────────────────
const dragging = ref(null);
const dragOverDay = ref(null);
const dropAnnouncement = ref("");

const onDragStart = (res) => {
  dragging.value = res;
  dropAnnouncement.value = t("reservationCalendar.dragStart", { name: res.name });
};

// Shared reschedule mutation used by both drag-drop and keyboard.
const rescheduleTo = async (res, targetDayIso) => {
  if (!res) return;

  // Compute new booked_for: keep existing time if present, use noon otherwise
  let newBookedFor;
  if (res.booked_for) {
    const existingTime = res.booked_for.slice(11, 16); // HH:MM
    newBookedFor = new Date(`${targetDayIso}T${existingTime}`).toISOString();
  } else {
    newBookedFor = new Date(`${targetDayIso}T12:00`).toISOString();
  }

  try {
    const updated = await api.patch(`/owner/reservations/${res.id}/`, { booked_for: newBookedFor });
    // Update local state
    const idx = reservations.value.findIndex((r) => r.id === res.id);
    if (idx !== -1) reservations.value[idx] = { ...reservations.value[idx], booked_for: newBookedFor };
    dropAnnouncement.value = t("reservationCalendar.dropSuccess", { name: res.name, day: targetDayIso });
    emit("rescheduled", updated.data);
  } catch {
    dropAnnouncement.value = t("reservationCalendar.dropError", { name: res.name });
  }
};

const onDrop = async (targetDayIso) => {
  dragOverDay.value = null;
  const res = dragging.value;
  dragging.value = null;
  await rescheduleTo(res, targetDayIso);
};

// ── Keyboard reschedule (WCAG 2.1.1) ─────────────────────────────────────────────
// Move the focused reservation one day earlier/later without a pointer drag.
const onChipKeydown = async (event, res, currentDayIso) => {
  const week = weekDays.value;
  const idx = week.findIndex((d) => d.iso === currentDayIso);
  if (idx === -1) return;
  const delta = event.key === "ArrowRight" || event.key === "ArrowUp" ? 1 : -1;
  const target = week[idx + delta];
  if (!target) return; // stay within the visible week; navigate weeks with Prev/Next
  await rescheduleTo(res, target.iso);
};

// ── Status styling ─────────────────────────────────────────────────────────────
const statusChipClass = (s) => ({
  new: "border-amber-500/40 bg-amber-500/10",
  contacted: "border-sky-500/40 bg-sky-500/10",
  won: "border-emerald-500/40 bg-emerald-500/10",
  lost: "border-slate-600/50 bg-slate-800/40",
}[s] ?? "border-slate-600/40 bg-slate-800/30");

const statusBadgeClass = (s) => ({
  new: "bg-amber-500/20 text-amber-300",
  contacted: "bg-sky-500/20 text-sky-300",
  won: "bg-emerald-500/20 text-emerald-300",
  lost: "bg-slate-700 text-slate-400",
}[s] ?? "bg-slate-700 text-slate-400");

const statusLabelShort = (s) => {
  const key = `reservationCalendar.status.${s}`;
  return t(key);
};
</script>
