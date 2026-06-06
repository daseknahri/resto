<template>
  <section class="space-y-4 ui-safe-bottom pb-24 sm:space-y-5 sm:pb-6">
    <header class="ui-hero-ribbon ui-reveal px-4 py-3.5 md:px-5 md:py-4">
      <div class="flex flex-wrap items-start justify-between gap-4">
        <div class="min-w-0 space-y-1.5">
          <p class="ui-kicker">{{ t("ownerReservations.kicker") }}</p>
          <h1 class="ui-display text-xl font-semibold leading-tight tracking-tight text-white sm:text-2xl">{{ t("ownerReservations.title") }}</h1>
          <div class="ui-scroll-row min-w-0">
            <span class="ui-data-strip tabular-nums">{{ t("ownerReservations.total") }}: {{ statusCounts.total }}</span>
            <span class="ui-data-strip tabular-nums">{{ t("ownerReservations.new") }}: {{ statusCounts.new }}</span>
            <span class="ui-data-strip tabular-nums">{{ t("ownerReservations.contacted") }}: {{ statusCounts.contacted }}</span>
            <span class="ui-data-strip tabular-nums">{{ t("ownerReservations.confirmed") }}: {{ statusCounts.won }}</span>
            <span class="ui-data-strip tabular-nums">{{ t("ownerReservations.overdue") }}: {{ statusCounts.overdue }}</span>
          </div>
        </div>
        <div class="flex shrink-0 flex-wrap items-center gap-2">
          <!-- View toggle -->
          <div class="ui-segmented col-span-2 sm:col-span-1" role="group" :aria-label="t('ownerReservations.viewToggleLabel')">
            <button
              class="ui-segmented-button"
              :data-active="viewMode === 'list' ? 'true' : 'false'"
              :aria-pressed="viewMode === 'list'"
              @click="viewMode = 'list'"
            >{{ t("ownerReservations.viewList") }}</button>
            <button
              class="ui-segmented-button"
              :data-active="viewMode === 'calendar' ? 'true' : 'false'"
              :aria-pressed="viewMode === 'calendar'"
              @click="viewMode = 'calendar'"
            >{{ t("ownerReservations.viewCalendar") }}</button>
          </div>
          <button class="ui-btn-primary ui-press justify-center px-4 py-2 text-sm" :disabled="loading" @click="fetchReservations">
            <AppIcon name="refresh" class="owner-res-icon" />
            {{ loading ? t("common.loading") : t("common.refresh") }}
          </button>
          <button class="ui-btn-outline ui-press justify-center px-4 py-2 text-sm" :disabled="exporting" @click="exportCsv">
            <AppIcon name="download" class="owner-res-icon" />
            {{ exporting ? t("ownerReservations.exporting") : t("ownerReservations.exportCsv") }}
          </button>
          <button class="ui-btn-outline ui-press hidden justify-center px-4 py-2 text-sm sm:inline-flex" :disabled="loading" @click="applyFilters">
            <AppIcon name="filter" class="owner-res-icon" />
            {{ t("common.apply") }}
          </button>
        </div>
      </div>
    </header>

    <section class="ui-command-deck space-y-3 sm:space-y-4">
      <div class="ui-toolbar-band grid gap-3 p-3 sm:p-4 md:grid-cols-[minmax(0,1fr)_220px_96px_auto]">
        <input
          v-model.trim="searchQuery"
          type="search"
          class="ui-input"
          enterkeyhint="search"
          :aria-label="t('ownerReservations.searchPlaceholder')"
          :placeholder="t('ownerReservations.searchPlaceholder')"
          @keyup.enter="applyFilters"
        />
        <label class="text-xs text-slate-400">
          {{ t("ownerReservations.statusFilter") }}
          <select v-model="statusFilter" class="ui-input mt-1" @change="applyFilters">
            <option v-for="option in statusOptions" :key="option.value || 'all'" :value="option.value">{{ option.label }}</option>
          </select>
        </label>
        <label class="hidden text-xs text-slate-400 md:block">
          {{ t("adminConsole.pageSize") }}
          <select v-model.number="pageSize" class="ui-input mt-1 w-24" @change="onPageSizeChange">
            <option :value="10">10</option>
            <option :value="20">20</option>
            <option :value="50">50</option>
          </select>
        </label>
        <div class="hidden flex-wrap items-end gap-2 md:flex md:justify-end">
          <button class="ui-btn-outline px-4 py-2 text-sm" :disabled="loading" @click="clearFilters">
            <AppIcon name="close" class="owner-res-icon" />
            {{ t("common.clear") }}
          </button>
          <button class="ui-btn-primary px-4 py-2 text-sm" :disabled="loading" @click="applyFilters">
            <AppIcon name="filter" class="owner-res-icon" />
            {{ t("common.apply") }}
          </button>
        </div>
        <div class="flex items-center gap-2 md:hidden">
          <button class="ui-btn-outline flex-1 justify-center px-4 py-2 text-sm" :disabled="loading" @click="clearFilters">
            <AppIcon name="close" class="owner-res-icon" />
            {{ t("common.clear") }}
          </button>
          <button class="ui-btn-primary flex-1 justify-center px-4 py-2 text-sm" :disabled="loading" @click="applyFilters">
            <AppIcon name="filter" class="owner-res-icon" />
            {{ t("common.apply") }}
          </button>
        </div>
      </div>

      <details class="rounded-xl border border-slate-800/80 bg-slate-950/40 p-3">
        <summary class="cursor-pointer text-xs font-semibold uppercase tracking-[0.16em] text-slate-300">
          {{ t("ownerReservations.reminderDateFilter") }}
        </summary>
        <div class="mt-3 grid gap-3 md:grid-cols-[220px_150px_150px_auto]">
          <label class="text-xs text-slate-400">
            {{ t("ownerReservations.reminders") }}
            <select v-model="reminderFilter" class="ui-input mt-1" @change="applyFilters">
              <option v-for="option in reminderOptions" :key="option.value || 'all-reminders'" :value="option.value">{{ option.label }}</option>
            </select>
          </label>
          <label class="text-xs text-slate-400">
            {{ t("ownerHome.from") }}
            <input v-model="dateFrom" type="date" class="ui-input mt-1" />
          </label>
          <label class="text-xs text-slate-400">
            {{ t("ownerHome.to") }}
            <input v-model="dateTo" type="date" class="ui-input mt-1" />
          </label>
          <div class="flex flex-wrap items-end gap-2 md:justify-end">
            <button
              class="ui-btn-outline px-3 py-1.5 text-xs"
              :class="reminderFilter === 'failed' ? 'border-rose-400 text-rose-200' : ''"
              @click="toggleFailedRetryQueue"
            >
              <AppIcon name="refresh" class="owner-res-icon" />
              {{ reminderFilter === "failed" ? t("ownerReservations.exitRetryQueue") : t("ownerReservations.retryQueue") }}
            </button>
            <button class="ui-btn-primary px-4 py-2 text-sm" :disabled="loading" @click="applyFilters">
              <AppIcon name="filter" class="owner-res-icon" />
              {{ t("common.apply") }}
            </button>
          </div>
        </div>
      </details>

      <div class="ui-toolbar-band hidden md:block">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div class="flex flex-wrap items-center gap-3">
            <label class="inline-flex items-center gap-2 text-xs text-slate-300">
              <input type="checkbox" :checked="allSelectedOnPage" @change="toggleSelectAllOnPage" />
              {{ t("ownerReservations.selectPage") }}
            </label>
            <p class="text-xs text-slate-400">{{ t("ownerReservations.selectedCount", { count: selectedCount }) }}</p>
            <span class="ui-data-strip">{{ activeFilterSummary }}</span>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <select v-model="bulkAction" :aria-label="t('ownerReservations.bulkActionSelect')" class="ui-input w-[160px] text-xs">
              <option value="contacted">{{ t("ownerReservations.markContacted") }}</option>
              <option value="won">{{ t("ownerReservations.markConfirmed") }}</option>
              <option value="lost">{{ t("ownerReservations.markUnavailable") }}</option>
              <option value="no_show">{{ t("ownerReservations.markNoShow") }}</option>
              <option value="new">{{ t("ownerReservations.resetNew") }}</option>
            </select>
            <button class="ui-btn-outline owner-action-btn px-3 py-1.5 text-xs" :disabled="!selectedCount || bulkUpdating" @click="runBulkAction">
              <AppIcon name="filter" class="owner-res-icon" />
              {{ t("common.apply") }}
            </button>
            <button
              class="ui-btn-outline owner-action-btn px-3 py-1.5 text-xs"
              :class="reminderFilter === 'failed' ? 'border-rose-400 text-rose-200' : ''"
              :disabled="!selectedCount || bulkReminderLoading"
              @click="bulkRetryReminders"
            >
              <AppIcon name="refresh" class="owner-res-icon" />
              {{ bulkReminderLoading ? t("ownerReservations.preparing") : t("ownerReservations.bulkRetryReminders") }}
            </button>
          </div>
        </div>
        <div v-if="pendingReminderReconciliation.length" class="mt-3 rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-xs space-y-2">
          <p class="text-amber-200">
            {{ t("ownerReservations.pendingReminderCount", { count: pendingReminderReconciliation.length }) }}
          </p>
          <p class="text-amber-100/80">{{ t("ownerReservations.pendingReminderHelp") }}</p>
          <div class="flex flex-wrap gap-2">
            <button
              class="owner-action-btn rounded-full border border-emerald-500/70 px-3 py-1.5 text-xs font-semibold text-emerald-200 disabled:opacity-60"
              :disabled="bulkReconcileLoading"
              @click="reconcilePendingReminders('opened')"
            >
              {{ bulkReconcileLoading ? t("ownerReservations.saving") : t("ownerReservations.markOpened") }}
            </button>
            <button
              class="owner-action-btn rounded-full border border-rose-500/70 px-3 py-1.5 text-xs font-semibold text-rose-200 disabled:opacity-60"
              :disabled="bulkReconcileLoading"
              @click="reconcilePendingReminders('failed')"
            >
              {{ bulkReconcileLoading ? t("ownerReservations.saving") : t("ownerReservations.markFailed") }}
            </button>
            <button
              class="owner-action-btn rounded-full border border-slate-600 px-3 py-1.5 text-xs font-semibold text-slate-300 disabled:opacity-60"
              :disabled="bulkReconcileLoading"
              @click="clearPendingReminderReconciliation"
            >
              {{ t("ownerReservations.clearPending") }}
            </button>
          </div>
        </div>
      </div>

      <details class="ui-toolbar-band md:hidden">
        <summary class="cursor-pointer text-xs font-semibold uppercase tracking-[0.16em] text-slate-300">
          {{ t("ownerReservations.selectedCount", { count: selectedCount }) }}
        </summary>
        <div class="mt-3 space-y-3">
          <div class="flex flex-wrap items-center gap-3">
            <label class="inline-flex items-center gap-2 text-xs text-slate-300">
              <input type="checkbox" :checked="allSelectedOnPage" @change="toggleSelectAllOnPage" />
              {{ t("ownerReservations.selectPage") }}
            </label>
            <span class="ui-data-strip">{{ activeFilterSummary }}</span>
          </div>
          <div class="grid grid-cols-2 gap-2">
            <select v-model="bulkAction" :aria-label="t('ownerReservations.bulkActionSelect')" class="ui-input col-span-2 text-xs">
              <option value="contacted">{{ t("ownerReservations.markContacted") }}</option>
              <option value="won">{{ t("ownerReservations.markConfirmed") }}</option>
              <option value="lost">{{ t("ownerReservations.markUnavailable") }}</option>
              <option value="no_show">{{ t("ownerReservations.markNoShow") }}</option>
              <option value="new">{{ t("ownerReservations.resetNew") }}</option>
            </select>
            <button class="ui-btn-outline owner-action-btn px-3 py-1.5 text-xs" :disabled="!selectedCount || bulkUpdating" @click="runBulkAction">
              <AppIcon name="filter" class="owner-res-icon" />
              {{ t("common.apply") }}
            </button>
            <button
              class="ui-btn-outline owner-action-btn px-3 py-1.5 text-xs"
              :class="reminderFilter === 'failed' ? 'border-rose-400 text-rose-200' : ''"
              :disabled="!selectedCount || bulkReminderLoading"
              @click="bulkRetryReminders"
            >
              <AppIcon name="refresh" class="owner-res-icon" />
              {{ bulkReminderLoading ? t("ownerReservations.preparing") : t("ownerReservations.bulkRetryReminders") }}
            </button>
          </div>
        </div>
      </details>

      <!-- Calendar view -->
      <ReservationCalendar
        v-if="viewMode === 'calendar'"
        @select="selectedCalendarRes = $event"
        @rescheduled="toast.show(t('ownerReservations.rescheduled'), 'success')"
      />

      <!-- Selected calendar reservation detail (quick panel) -->
      <div
        v-if="viewMode === 'calendar' && selectedCalendarRes"
        class="ui-panel ui-reveal p-4 space-y-2 text-sm"
      >
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0">
            <p class="truncate font-semibold text-white">{{ selectedCalendarRes.name }}</p>
            <p class="truncate text-xs text-slate-400">{{ selectedCalendarRes.phone }} · {{ selectedCalendarRes.email }}</p>
          </div>
          <button
            class="ui-press shrink-0 rounded-lg p-1 text-slate-500 transition hover:bg-slate-800/60 hover:text-slate-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500/60"
            :aria-label="t('common.close')"
            @click="selectedCalendarRes = null"
          >
            <AppIcon name="close" class="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
        <p v-if="selectedCalendarRes.booked_for" class="text-xs text-slate-300">
          {{ t("ownerReservations.bookedFor") }}: {{ formatDateTime(selectedCalendarRes.booked_for) }}
          <span v-if="selectedCalendarRes.party_size"> · {{ selectedCalendarRes.party_size }} {{ t("ownerReservations.guests") }}</span>
        </p>
        <p v-if="selectedCalendarRes.notes" class="rounded-xl border border-slate-800 bg-slate-950/50 p-2 text-xs text-slate-300 whitespace-pre-line">{{ selectedCalendarRes.notes }}</p>
      </div>

      <template v-if="viewMode === 'list'">
      <div v-if="error" role="alert" class="ui-reveal flex items-start gap-3 rounded-2xl border border-red-500/30 bg-red-500/8 px-4 py-3">
        <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor">
          <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm-.75-9.25a.75.75 0 011.5 0v3.5a.75.75 0 01-1.5 0v-3.5zm.75 6a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd" />
        </svg>
        <p id="res-list-error-msg" class="flex-1 text-sm text-red-300">{{ error }}</p>
        <button
          class="ui-press shrink-0 rounded-lg border border-red-500/40 px-3 py-1 text-xs font-semibold text-red-300 transition hover:bg-red-500/10"
          aria-describedby="res-list-error-msg"
          @click="fetchReservations"
        >{{ t('common.retry') }}</button>
      </div>
      <div v-else-if="loading" class="grid gap-3 lg:grid-cols-2" role="status" aria-live="polite" :aria-label="t('ownerReservations.loadingList')">
        <div v-for="n in 4" :key="`reservation-skeleton-${n}`" class="ui-skeleton h-72 rounded-[1.5rem]" aria-hidden="true"></div>
      </div>
      <article v-else-if="!reservations.length" class="ui-empty-state ui-reveal space-y-3 text-center text-sm">
        <div class="mx-auto flex h-11 w-11 items-center justify-center rounded-2xl border border-slate-700/80 bg-slate-950/70 text-slate-200">
          <AppIcon name="calendar" class="h-5 w-5" />
        </div>
        <div class="space-y-1">
          <p class="ui-kicker">{{ activeFilterSummary }}</p>
          <h3 class="text-lg font-semibold text-white">{{ t("ownerReservations.noReservations") }}</h3>
          <p class="text-slate-400">{{ t("ownerReservations.pageSummary", { page: pagination.page, pages: pagination.pages, total: pagination.total }) }}</p>
        </div>
        <div class="flex flex-wrap justify-center gap-2">
          <button class="ui-btn-outline ui-press px-4 py-2 text-sm" @click="clearFilters">
            <AppIcon name="close" class="owner-res-icon" aria-hidden="true" />
            {{ t("common.clear") }}
          </button>
          <button class="ui-btn-outline ui-press px-4 py-2 text-sm" @click="fetchReservations">
            <AppIcon name="refresh" class="owner-res-icon" aria-hidden="true" />
            {{ t("common.refresh") }}
          </button>
        </div>
      </article>

      <div class="grid gap-3 lg:grid-cols-2">
        <article
          v-for="(reservation, index) in reservations"
          :key="reservation.id"
          class="ui-reservation-card ui-surface-lift ui-reveal space-y-3 sm:space-y-3.5"
          :class="reservationCardClass(reservation)"
          :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms`, 'content-visibility': 'auto', 'contain-intrinsic-size': 'auto 240px' }"
        >
          <div class="flex items-start justify-between gap-3">
            <label class="inline-flex items-center gap-2">
              <input
                type="checkbox"
                :checked="isSelected(reservation.id)"
                :aria-label="reservation.name || t('ownerReservations.fallbackReservationName', { id: reservation.id })"
                @change="toggleSelection(reservation.id)"
              />
              <span class="text-base font-semibold text-slate-100">{{ reservation.name || t("ownerReservations.fallbackReservationName", { id: reservation.id }) }}</span>
            </label>
            <span class="rounded-full px-2 py-1 text-[11px] font-semibold" :class="statusClass(reservation.status)">
              {{ statusLabel(reservation.status) }}
            </span>
          </div>
          <ul role="list" class="flex flex-wrap gap-2">
            <li><span class="ui-state-chip" data-active="true">{{ formatDate(reservation.created_at) }}</span></li>
            <li
              v-if="reservation.sla_state && reservation.sla_state !== 'not_applicable'"
            ><span
              class="rounded-full px-2 py-1 text-[11px] font-semibold"
              :class="slaClass(reservation.sla_state)"
            >
              {{ slaLabel(reservation) }}
            </span></li>
            <li v-if="reservation.follow_up_due_at"><span class="ui-state-chip" :data-active="reservation.sla_state === 'warning' || reservation.sla_state === 'overdue'">
              {{ t("ownerReservations.dueLabel", { date: formatDate(reservation.follow_up_due_at) }) }}
            </span></li>
          </ul>

          <div class="grid gap-1.5 text-sm text-start sm:grid-cols-2">
            <p class="rounded-lg border border-slate-800/70 bg-slate-950/35 px-2.5 py-2 text-slate-200 break-all">
              {{ reservation.phone || "-" }}
            </p>
            <p class="rounded-lg border border-slate-800/70 bg-slate-950/35 px-2.5 py-2 text-slate-400 break-all">
              {{ reservation.email || "-" }}
            </p>
          </div>

          <p class="rounded-xl border border-slate-800 bg-slate-950/50 p-2.5 text-xs text-slate-300 whitespace-pre-line">
            {{ reservation.notes || t("ownerReservations.noCustomerNote") }}
          </p>

          <div class="flex flex-wrap items-center gap-1.5">
            <span class="ui-data-strip tabular-nums">
              {{ t("ownerReservations.reminders") }} {{ reservation.reminder_count || 0 }}
            </span>
            <span class="ui-data-strip tabular-nums">
              {{ t("ownerReservations.opened") }} {{ reservation.reminder_opened_count || 0 }}
            </span>
            <span class="ui-data-strip tabular-nums">
              {{ t("ownerReservations.failed") }} {{ reservation.reminder_failed_count || 0 }}
            </span>
            <span
              v-if="reservation.last_reminder_status"
              class="inline-flex items-center rounded-full px-2 py-1 text-[11px] font-semibold"
              :class="reminderStatusClass(reservation.last_reminder_status)"
            >
              {{ t("ownerReservations.last") }} {{ reminderStatusLabel(reservation.last_reminder_status) }}
            </span>
            <span v-if="reservation.last_reminder_at" class="text-[11px] text-slate-500">
              {{ formatDate(reservation.last_reminder_at) }}
            </span>
          </div>

          <div class="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap sm:items-center">
            <a
              v-if="telHref(reservation)"
              :href="telHref(reservation)"
              class="ui-btn-outline justify-center px-3 py-1.5 text-xs"
            >
              <AppIcon name="phone" class="owner-res-icon" />
              {{ t("common.call") }}
            </a>
            <a
              v-if="whatsappHref(reservation)"
              :href="whatsappHref(reservation)"
              target="_blank"
              rel="noopener noreferrer"
              class="ui-btn-outline justify-center px-3 py-1.5 text-xs"
            >
              <AppIcon name="chat" class="owner-res-icon" />
              {{ t("ownerReservations.quickChat") }}
            </a>
          </div>

          <div class="grid grid-cols-2 gap-2 sm:hidden">
            <button
              class="owner-action-btn rounded-full border border-emerald-500/70 px-3 py-1.5 text-xs font-semibold text-emerald-200 disabled:opacity-60"
              :disabled="isReminderSending(reservation.id) || !canSendReminder(reservation)"
              @click="sendReminder(reservation)"
            >
              {{ isReminderSending(reservation.id) ? t("ownerReservations.opening") : t("ownerReservations.reminder") }}
            </button>
            <button
              class="owner-action-btn rounded-full bg-sky-500/90 px-3 py-1.5 text-xs font-semibold text-slate-950 disabled:opacity-60"
              :disabled="isUpdating(reservation.id)"
              @click="updateStatus(reservation, 'contacted')"
            >
              {{ t("ownerReservations.contacted") }}
            </button>
            <button
              class="owner-action-btn rounded-full bg-emerald-500/90 px-3 py-1.5 text-xs font-semibold text-slate-950 disabled:opacity-60"
              :disabled="isUpdating(reservation.id)"
              @click="updateStatus(reservation, 'won')"
            >
              {{ t("ownerReservations.confirmed") }}
            </button>
          </div>

          <details class="rounded-xl border border-slate-800/80 bg-slate-950/40 p-2.5 sm:hidden">
            <summary class="cursor-pointer text-xs font-semibold uppercase tracking-[0.14em] text-slate-300">
              {{ t("common.more") }}
            </summary>
            <div class="mt-2 grid grid-cols-2 gap-2">
              <button
                class="owner-action-btn rounded-full border border-rose-500/70 px-3 py-1.5 text-xs font-semibold text-rose-200 disabled:opacity-60"
                :disabled="isUpdating(reservation.id)"
                @click="updateStatus(reservation, 'lost')"
              >
                {{ t("ownerReservations.unavailable") }}
              </button>
              <button
                class="owner-action-btn rounded-full border border-slate-700 px-3 py-1.5 text-xs font-semibold text-slate-200 disabled:opacity-60"
                :disabled="isUpdating(reservation.id)"
                @click="updateStatus(reservation, 'new')"
              >
                {{ t("ownerReservations.resetNew") }}
              </button>
              <button
                class="owner-action-btn col-span-2 rounded-full border border-slate-700 px-3 py-1.5 text-xs font-semibold text-slate-200 disabled:opacity-60"
                :disabled="isTimelineLoading(reservation.id)"
                :aria-expanded="isTimelineOpen(reservation.id)"
                @click="toggleTimeline(reservation.id)"
              >
                <AppIcon name="calendar" class="owner-res-icon" />
                {{ isTimelineOpen(reservation.id) ? t("ownerReservations.hideTimeline") : t("ownerReservations.timeline") }}
              </button>
            </div>
          </details>

          <div class="hidden gap-2 sm:grid sm:grid-cols-3">
            <button
              class="owner-action-btn rounded-full border border-emerald-500/70 px-3 py-1.5 text-xs font-semibold text-emerald-200 disabled:opacity-60"
              :disabled="isReminderSending(reservation.id) || !canSendReminder(reservation)"
              @click="sendReminder(reservation)"
            >
              {{ isReminderSending(reservation.id) ? t("ownerReservations.opening") : t("ownerReservations.reminder") }}
            </button>
            <button
              class="owner-action-btn rounded-full bg-sky-500/90 px-3 py-1.5 text-xs font-semibold text-slate-950 disabled:opacity-60"
              :disabled="isUpdating(reservation.id)"
              @click="updateStatus(reservation, 'contacted')"
            >
              {{ t("ownerReservations.contacted") }}
            </button>
            <button
              class="owner-action-btn rounded-full bg-emerald-500/90 px-3 py-1.5 text-xs font-semibold text-slate-950 disabled:opacity-60"
              :disabled="isUpdating(reservation.id)"
              @click="updateStatus(reservation, 'won')"
            >
              {{ t("ownerReservations.confirmed") }}
            </button>
            <button
              class="owner-action-btn rounded-full border border-rose-500/70 px-3 py-1.5 text-xs font-semibold text-rose-200 disabled:opacity-60"
              :disabled="isUpdating(reservation.id)"
              @click="updateStatus(reservation, 'lost')"
            >
              {{ t("ownerReservations.unavailable") }}
            </button>
            <button
              class="owner-action-btn rounded-full border border-violet-500/70 px-3 py-1.5 text-xs font-semibold text-violet-200 disabled:opacity-60"
              :disabled="isUpdating(reservation.id)"
              @click="updateStatus(reservation, 'no_show')"
            >
              {{ t("ownerReservations.markNoShow") }}
            </button>
            <button
              class="owner-action-btn rounded-full border border-slate-700 px-3 py-1.5 text-xs font-semibold text-slate-200 disabled:opacity-60"
              :disabled="isUpdating(reservation.id)"
              @click="updateStatus(reservation, 'new')"
            >
              {{ t("ownerReservations.resetNew") }}
            </button>
            <button
              class="owner-action-btn rounded-full border border-slate-700 px-3 py-1.5 text-xs font-semibold text-slate-200 disabled:opacity-60"
              :disabled="isTimelineLoading(reservation.id)"
              :aria-expanded="isTimelineOpen(reservation.id)"
              @click="toggleTimeline(reservation.id)"
            >
              <AppIcon name="calendar" class="owner-res-icon" />
              {{ isTimelineOpen(reservation.id) ? t("ownerReservations.hideTimeline") : t("ownerReservations.timeline") }}
            </button>
          </div>

          <div v-if="isTimelineOpen(reservation.id)" class="rounded-xl border border-slate-800 bg-slate-950/40 p-3 space-y-3">
            <p class="text-xs uppercase tracking-[0.18em] text-slate-400">{{ t("ownerReservations.timelineTitle") }}</p>
            <div v-if="isTimelineLoading(reservation.id)" class="space-y-2" role="status" :aria-label="t('ownerReservations.loadingTimeline')">
              <div v-for="s in 2" :key="s" class="h-10 animate-pulse rounded-lg bg-slate-800/50" />
            </div>
            <ul v-else class="space-y-2 text-xs">
              <li
                v-for="entry in timelineFor(reservation.id)"
                :key="entry.id"
                class="rounded-lg border border-slate-800 bg-slate-900/70 p-2"
              >
                <div class="flex items-center justify-between gap-2">
                  <span class="font-semibold text-slate-200">{{ timelineActionLabel(entry.action) }}</span>
                  <span class="text-slate-500">{{ formatDate(entry.created_at) }}</span>
                </div>
                <p v-if="entry.note" class="mt-1 whitespace-pre-line text-slate-300">{{ entry.note }}</p>
                <p v-if="entry.previous_status || entry.new_status" class="mt-1 text-slate-400">
                  {{ statusLabel(entry.previous_status) || "-" }}<span aria-hidden="true"> -&gt; </span><span class="sr-only"> {{ t("ownerReservations.statusTransitionTo") }} </span>{{ statusLabel(entry.new_status) || "-" }}
                </p>
                <p v-if="entry.actor_username" class="mt-1 text-slate-500">{{ t("ownerReservations.byActor", { actor: entry.actor_username }) }}</p>
              </li>
              <li v-if="!timelineFor(reservation.id).length" class="text-slate-500">{{ t("ownerReservations.noTimelineEntries") }}</li>
            </ul>

            <div class="space-y-1.5">
              <div class="flex flex-wrap items-start gap-2">
                <textarea
                  v-model.trim="timelineNote[reservation.id]"
                  rows="2"
                  class="ui-textarea min-w-[220px] flex-1"
                  :class="timelineNoteError[reservation.id] ? 'border-red-400' : ''"
                  :aria-label="t('ownerReservations.addFollowUpNote')"
                  :aria-invalid="timelineNoteError[reservation.id] ? 'true' : undefined"
                  :aria-describedby="`res-timeline-note-error-${reservation.id}`"
                  :placeholder="t('ownerReservations.addFollowUpNote')"
                  @input="timelineNoteError[reservation.id] = ''"
                ></textarea>
                <button
                  class="ui-btn-outline px-3 py-2 text-xs disabled:opacity-60"
                  :disabled="isTimelineSubmitting(reservation.id)"
                  @click="addTimelineNote(reservation.id)"
                >
                  {{ isTimelineSubmitting(reservation.id) ? t("ownerReservations.saving") : t("ownerReservations.addNote") }}
                </button>
              </div>
              <p v-if="timelineNoteError[reservation.id]" :id="`res-timeline-note-error-${reservation.id}`" class="text-xs text-red-300">{{ timelineNoteError[reservation.id] }}</p>
            </div>
          </div>
        </article>
      </div>

      <div class="flex flex-wrap items-center justify-between gap-2 border-t border-slate-800 pt-3">
        <p class="text-xs text-slate-400">
          {{ t("ownerReservations.pageSummary", { page: pagination.page, pages: pagination.pages, total: pagination.total }) }}
        </p>
        <div class="flex items-center gap-2">
          <button class="ui-btn-outline px-3 py-1.5 text-xs" :disabled="!pagination.has_prev || loading" @click="goPrevPage">
            {{ t("common.previous") }}
          </button>
          <button class="ui-btn-outline px-3 py-1.5 text-xs" :disabled="!pagination.has_next || loading" @click="goNextPage">
            {{ t("common.next") }}
          </button>
        </div>
      </div>
      </template>
    </section>

    <!-- ── Waitlist ─────────────────────────────────────────────────────────── -->
    <section class="ui-command-deck ui-reveal space-y-3 sm:space-y-4">
      <!-- Header -->
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div class="space-y-0.5">
          <p class="ui-kicker">{{ t("ownerReservations.waitlistKicker") }}</p>
          <h2 class="text-base font-bold text-white">{{ t("ownerReservations.waitlistTitle") }}</h2>
          <p class="text-xs text-slate-400">{{ t("ownerReservations.waitlistSubtitle") }}</p>
        </div>
        <label class="shrink-0 text-xs text-slate-400">
          <span class="sr-only">{{ t("ownerReservations.waitlistDate") }}</span>
          <input
            v-model="waitlistDate"
            type="date"
            class="ui-input mt-0.5 text-sm"
            :aria-label="t('ownerReservations.waitlistDate')"
            @change="fetchWaitlist"
          />
        </label>
      </div>

      <!-- Loading -->
      <div v-if="waitlistLoading" class="space-y-2 py-2">
        <div v-for="i in 3" :key="i" class="h-10 animate-pulse rounded-xl bg-slate-800/50" />
      </div>

      <!-- Error -->
      <div v-else-if="waitlistError" class="flex items-start gap-3 rounded-xl border border-red-500/30 bg-red-500/8 px-4 py-3" role="alert">
        <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor">
          <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm-.75-9.25a.75.75 0 011.5 0v3.5a.75.75 0 01-1.5 0v-3.5zm.75 6a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd" />
        </svg>
        <p class="flex-1 text-sm text-red-300">{{ t("ownerReservations.waitlistLoadError") }}</p>
        <button
          class="ui-press shrink-0 rounded-lg border border-red-500/40 px-3 py-1 text-xs font-semibold text-red-300 transition hover:bg-red-500/10"
          @click="fetchWaitlist"
        >{{ t('common.retry') }}</button>
      </div>

      <!-- Empty -->
      <div v-else-if="!waitlistEntries.length" class="ui-empty-state space-y-2 py-6 text-center">
        <div class="mx-auto flex h-10 w-10 items-center justify-center rounded-xl border border-slate-700/80 bg-slate-950/70 text-slate-400">
          <AppIcon name="calendar" class="h-5 w-5" aria-hidden="true" />
        </div>
        <p class="text-sm text-slate-400">{{ waitlistDate ? t("ownerReservations.waitlistEmpty") : t("ownerReservations.waitlistEmptyAll") }}</p>
      </div>

      <!-- Table -->
      <div v-else class="ui-table-wrap rounded-xl border border-slate-700/50">
        <table class="w-full min-w-[560px] text-sm">
          <thead>
            <tr class="border-b border-slate-700/50 bg-slate-900/60 text-xs text-slate-400">
              <th scope="col" class="px-4 py-2.5 text-start font-medium">{{ t("ownerReservations.bookedFor") }}</th>
              <th scope="col" class="px-4 py-2.5 text-start font-medium">{{ t("common.name") }}</th>
              <th scope="col" class="px-4 py-2.5 text-start font-medium">{{ t("ownerReservations.guests") }}</th>
              <th scope="col" class="px-4 py-2.5 text-start font-medium">{{ t("common.status") }}</th>
              <th scope="col" class="px-4 py-2.5 text-start font-medium">{{ t("ownerReservations.notes") }}</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="entry in waitlistEntries"
              :key="entry.id"
              class="border-b border-slate-800/60 transition hover:bg-slate-800/30"
            >
              <td class="px-4 py-3 text-slate-200 tabular-nums text-xs">{{ formatDate(entry.booked_for) }}</td>
              <td class="px-4 py-3">
                <p class="font-medium text-slate-100">{{ entry.name }}</p>
                <p v-if="entry.phone" class="text-xs text-slate-500">{{ entry.phone }}</p>
                <p v-if="entry.email" class="text-xs text-slate-500">{{ entry.email }}</p>
              </td>
              <td class="px-4 py-3 text-slate-300">{{ t("ownerReservations.waitlistParty", { n: entry.party_size }) }}</td>
              <td class="px-4 py-3">
                <span class="rounded-full px-2.5 py-0.5 text-[10px] font-semibold" :class="waitlistStatusClass(entry.status)">
                  {{ waitlistStatusLabel(entry.status) }}
                </span>
              </td>
              <td class="px-4 py-3 text-xs text-slate-400 max-w-[12rem] truncate">{{ entry.notes || '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </section>
</template>

<script setup>
import { computed, onActivated, onMounted, ref } from "vue";
import AppIcon from "../components/AppIcon.vue";
import ReservationCalendar from "../components/ReservationCalendar.vue";
import { useI18n } from "../composables/useI18n";
import api from "../lib/api";
import { safeExternalUrl } from "../lib/escape";
import { readCache, writeCache } from "../lib/staleCache";
import { useToastStore } from "../stores/toast";

// SWR cache for the default (unfiltered, page 1) list — read only on initial
// mount for an instant first paint, then revalidated silently. fetchReservations
// itself always hits the network, so the many post-mutation refetches never serve
// a stale status; they just refresh this cache when the default view is active.
const RES_CACHE = "owner.reservations";

const toast = useToastStore();
const { t, formatDateTime } = useI18n();
const viewMode = ref("list"); // "list" | "calendar"
const selectedCalendarRes = ref(null);
const reservations = ref([]);
const loading = ref(false);
const error = ref("");
const statusFilter = ref("");
const reminderFilter = ref("");
const searchQuery = ref("");
const dateFrom = ref("");
const dateTo = ref("");
const exporting = ref(false);
const bulkUpdating = ref(false);
const bulkReminderLoading = ref(false);
const bulkReconcileLoading = ref(false);
const updating = ref({});
const reminderLoading = ref({});
const pendingReminderReconciliation = ref([]);
const selectedIds = ref([]);
const timelineOpen = ref({});
const timelineLoading = ref({});
const timelineItems = ref({});
const timelineNote = ref({});
const timelineNoteError = ref({});
const timelineSubmitting = ref({});
const page = ref(1);
const pageSize = ref(20);
const bulkAction = ref("contacted");
const pagination = ref({
  page: 1,
  page_size: 20,
  total: 0,
  pages: 1,
  has_next: false,
  has_prev: false,
});

// Server-reported counts across all pages — populated by fetchReservations.
const serverCounts = ref({ total: 0, new: 0, overdue_new: 0, contacted: 0, won: 0, lost: 0 });

const statusOptions = computed(() => [
  { value: "", label: t("ownerReservations.allStatuses") },
  { value: "new", label: t("ownerReservations.new") },
  { value: "contacted", label: t("ownerReservations.contacted") },
  { value: "won", label: t("ownerReservations.confirmed") },
  { value: "lost", label: t("ownerReservations.unavailable") },
  { value: "no_show", label: t("ownerReservations.noShow") },
]);

const reminderOptions = computed(() => [
  { value: "", label: t("ownerReservations.allReminders") },
  { value: "failed", label: t("ownerReservations.failed") },
  { value: "sent", label: t("ownerReservations.sent") },
  { value: "opened", label: t("ownerReservations.opened") },
  { value: "none", label: t("ownerReservations.noReminders") },
]);
const statusCounts = computed(() => ({
  // All figures come from the server-side counts dict so they reflect the full
  // dataset, not just the current page.  Falls back to pagination.total before
  // the first successful API response.
  total: serverCounts.value.total || pagination.value.total,
  new: serverCounts.value.new,
  contacted: serverCounts.value.contacted,
  won: serverCounts.value.won,
  overdue: serverCounts.value.overdue_new,
}));
const activeStatusLabel = computed(() => statusOptions.value.find((option) => option.value === statusFilter.value)?.label || t("ownerReservations.allStatuses"));
const activeReminderLabel = computed(() => reminderOptions.value.find((option) => option.value === reminderFilter.value)?.label || t("ownerReservations.allReminders"));
const activeFilterSummary = computed(() => `${activeStatusLabel.value} / ${activeReminderLabel.value}`);

const selectedCount = computed(() => selectedIds.value.length);
const allSelectedOnPage = computed(() => {
  if (!reservations.value.length) return false;
  const pageIds = reservations.value.map((row) => row.id);
  return pageIds.every((id) => selectedIds.value.includes(id));
});

const parseApiError = (err, fallback) => {
  const data = err?.response?.data;
  if (typeof data?.detail === "string") return data.detail;
  if (typeof data === "string" && data.trim()) return data;
  return fallback;
};

const formatDate = (value) => formatDateTime(value) || "-";

const sanitizePhone = (value) => String(value || "").replace(/\D/g, "");
const sanitizeTel = (value) =>
  String(value || "")
    .replace(/[^\d+]/g, "")
    .replace(/(?!^)\+/g, "");

const telHref = (reservation) => {
  const tel = sanitizeTel(reservation?.phone || "");
  return tel ? `tel:${tel}` : "";
};

const whatsappHref = (reservation) => {
  const phone = sanitizePhone(reservation?.phone || "");
  if (!phone) return "";
  const name = String(reservation?.name || t("ownerReservations.guestFallback")).trim();
  const text = encodeURIComponent(t("ownerReservations.whatsappTemplate", { name }));
  return `https://wa.me/${phone}?text=${text}`;
};

const statusClass = (status) => {
  if (status === "new") return "bg-amber-500/20 text-amber-200";
  if (status === "contacted") return "bg-sky-500/20 text-sky-200";
  if (status === "won") return "bg-emerald-500/20 text-emerald-200";
  if (status === "lost") return "bg-rose-500/20 text-rose-200";
  if (status === "no_show") return "bg-violet-500/20 text-violet-200";
  return "bg-slate-700 text-slate-200";
};

const statusLabel = (status) => {
  if (status === "new") return t("ownerReservations.new");
  if (status === "contacted") return t("ownerReservations.contacted");
  if (status === "won") return t("ownerReservations.confirmed");
  if (status === "lost") return t("ownerReservations.unavailable");
  if (status === "no_show") return t("ownerReservations.noShow");
  return status ? String(status) : "";
};

const slaClass = (slaState) => {
  if (slaState === "overdue") return "bg-rose-500/20 text-rose-200";
  if (slaState === "due_soon") return "bg-amber-500/20 text-amber-200";
  if (slaState === "on_track") return "bg-emerald-500/20 text-emerald-200";
  if (slaState === "resolved") return "bg-slate-700/60 text-slate-300";
  return "bg-slate-800 text-slate-400";
};

const slaLabel = (reservation) => {
  const state = String(reservation?.sla_state || "");
  if (state === "overdue") {
    const minutes = Number(reservation?.sla_minutes_overdue || 0);
    return minutes > 0 ? `${t("ownerReservations.statusOverdue")} ${minutes}m` : t("ownerReservations.statusOverdue");
  }
  if (state === "due_soon") return t("ownerReservations.statusDueSoon");
  if (state === "on_track") return t("ownerReservations.statusOnTrack");
  if (state === "resolved") return t("ownerReservations.statusResolved");
  return t("ownerReservations.noSla");
};

const reminderStatusClass = (status) => {
  if (status === "opened") return "bg-emerald-500/20 text-emerald-200";
  if (status === "failed") return "bg-rose-500/20 text-rose-200";
  if (status === "sent") return "bg-amber-500/20 text-amber-200";
  return "bg-slate-700/60 text-slate-300";
};

const reminderStatusLabel = (status) => {
  if (status === "opened") return t("ownerReservations.opened");
  if (status === "failed") return t("ownerReservations.failed");
  if (status === "sent") return t("ownerReservations.sent");
  return t("ownerReservations.unknown");
};

const timelineActionLabel = (action) => {
  const normalized = String(action || "").toLowerCase();
  if (normalized.includes("status")) return t("ownerReservations.timelineActionStatusChange");
  if (normalized.includes("note")) return t("ownerReservations.timelineActionNote");
  if (normalized.includes("reminder")) return t("ownerReservations.timelineActionReminder");
  return action ? String(action) : t("ownerReservations.timelineActionUnknown");
};

const reservationCardClass = (reservation) => {
  if (reservation?.last_reminder_status === "failed") return "border-rose-500/70";
  if (reservation?.last_reminder_status === "opened") return "border-emerald-500/60";
  if (reservation?.last_reminder_status === "sent") return "border-amber-500/60";
  return "border-slate-800";
};

const isUpdating = (id) => Boolean(updating.value[id]);
const isReminderSending = (id) => Boolean(reminderLoading.value[id]);
const isSelected = (id) => selectedIds.value.includes(id);
const isTimelineOpen = (id) => Boolean(timelineOpen.value[id]);
const isTimelineLoading = (id) => Boolean(timelineLoading.value[id]);
const isTimelineSubmitting = (id) => Boolean(timelineSubmitting.value[id]);
const timelineFor = (id) => (Array.isArray(timelineItems.value[id]) ? timelineItems.value[id] : []);
const canSendReminder = (reservation) => Boolean(whatsappHref(reservation)) && reservation?.status !== "lost";

const buildFilterParams = () => {
  const params = {};
  if (statusFilter.value) params.status = statusFilter.value;
  if (reminderFilter.value) params.reminder_status = reminderFilter.value;
  if (searchQuery.value) params.q = searchQuery.value;
  if (dateFrom.value) params.from = dateFrom.value;
  if (dateTo.value) params.to = dateTo.value;
  return params;
};

const buildListParams = () => ({
  ...buildFilterParams(),
  page: page.value,
  page_size: pageSize.value,
});

const isDefaultReservationView = () =>
  !statusFilter.value &&
  !reminderFilter.value &&
  !searchQuery.value &&
  !dateFrom.value &&
  !dateTo.value &&
  page.value === 1;

const fetchReservations = async ({ silent = false } = {}) => {
  if (!silent) loading.value = true;
  error.value = "";
  try {
    const res = await api.get("/owner/reservations/", { params: buildListParams() });
    const payload = res?.data || {};
    if (Array.isArray(payload)) {
      reservations.value = payload;
      pagination.value = {
        page: 1,
        page_size: payload.length,
        total: payload.length,
        pages: 1,
        has_next: false,
        has_prev: false,
      };
    } else {
      reservations.value = Array.isArray(payload.results) ? payload.results : [];
      pagination.value = payload.pagination || pagination.value;
      page.value = Number(pagination.value.page || page.value);
      if (payload.counts) serverCounts.value = { ...serverCounts.value, ...payload.counts };
    }
    selectedIds.value = [];
    // Keep the default-view cache warm with the freshest data.
    if (isDefaultReservationView()) {
      writeCache(RES_CACHE, {
        reservations: reservations.value,
        pagination: pagination.value,
        counts: serverCounts.value,
      });
    }
  } catch (err) {
    const message = parseApiError(err, t("ownerReservations.loadFailed"));
    error.value = message;
    if (!silent) toast.show(message, "error");
  } finally {
    if (!silent) loading.value = false;
  }
};

const updateStatus = async (reservation, status) => {
  const id = reservation?.id;
  if (!id) return;
  updating.value = { ...updating.value, [id]: true };
  try {
    await api.put(`/owner/reservations/${id}/`, { status });
    toast.show(t("ownerReservations.updatedReservation"), "success");
    await fetchReservations();
  } catch (err) {
    toast.show(parseApiError(err, t("ownerReservations.updateReservationFailed")), "error");
  } finally {
    const clone = { ...updating.value };
    delete clone[id];
    updating.value = clone;
  }
};

const sendReminder = async (reservation) => {
  const id = reservation?.id;
  if (!id || !canSendReminder(reservation)) return;
  reminderLoading.value = { ...reminderLoading.value, [id]: true };
  try {
    const res = await api.post(`/owner/reservations/${id}/reminder/`, {});
    const fallback = whatsappHref(reservation);
    const link = safeExternalUrl(res?.data?.whatsapp_link || fallback || "");
    const reminderId = Number(res?.data?.id || 0);
    let popup = null;
    if (link) {
      popup = window.open(link, "_blank", "noopener,noreferrer");
    }
    if (reminderId > 0) {
      const opened = Boolean(popup);
      await api.post(`/owner/reservations/${id}/reminder-result/`, {
        reminder_id: reminderId,
        status: opened ? "opened" : "failed",
        error: opened ? "" : t("ownerReservations.reminderBlocked"),
      });
    }
    if (popup) {
      toast.show(t("ownerReservations.reminderOpened"), "success");
    } else {
      if (link && navigator?.clipboard?.writeText) {
        try {
          await navigator.clipboard.writeText(link);
        } catch {
          // Ignore clipboard errors and still show fallback guidance.
        }
      }
      toast.show(t("ownerReservations.reminderBlocked"), "error");
    }
    await fetchReservations();
    if (isTimelineOpen(id)) {
      await fetchTimeline(id);
    }
  } catch (err) {
    toast.show(parseApiError(err, t("ownerReservations.prepareReminderFailed")), "error");
  } finally {
    const clone = { ...reminderLoading.value };
    delete clone[id];
    reminderLoading.value = clone;
  }
};

const bulkRetryReminders = async () => {
  if (!selectedIds.value.length) return;
  bulkReminderLoading.value = true;
  try {
    const res = await api.post("/owner/reservations/bulk-reminder/", {
      ids: selectedIds.value,
      require_failed_last_reminder: reminderFilter.value === "failed",
    });
    const payload = res?.data || {};
    const preparedCount = Number(payload.prepared_count || 0);
    const skippedNoPhone = Array.isArray(payload.skipped_no_phone_ids) ? payload.skipped_no_phone_ids.length : 0;
    const skippedUnavailable = Array.isArray(payload.skipped_unavailable_ids) ? payload.skipped_unavailable_ids.length : 0;
    const skippedNotFailed = Array.isArray(payload.skipped_not_failed_ids) ? payload.skipped_not_failed_ids.length : 0;
    const results = Array.isArray(payload.results) ? payload.results : [];
    const links = results.map((item) => safeExternalUrl(item?.whatsapp_link || "")).filter(Boolean);
    pendingReminderReconciliation.value = results;

    let firstPopup = null;
    if (links.length) {
      firstPopup = window.open(links[0], "_blank", "noopener,noreferrer");
    }
    if (links.length && navigator?.clipboard?.writeText) {
      try {
        await navigator.clipboard.writeText(links.join("\n"));
      } catch {
        // Ignore clipboard errors and keep summary toast.
      }
    }
    if (results.length) {
      const first = results[0];
      if (first?.lead_id && first?.reminder_id) {
        try {
          const res = await api.post("/owner/reservations/bulk-reminder-result/", {
            items: [
              {
                lead_id: first.lead_id,
                reminder_id: first.reminder_id,
                status: firstPopup ? "opened" : "failed",
                error: firstPopup ? "" : t("ownerReservations.reminderBlocked"),
              },
            ],
          });
          if (Number(res?.data?.updated_count || 0) > 0) {
            pendingReminderReconciliation.value = pendingReminderReconciliation.value.slice(1);
          }
        } catch {
          // Best effort tracking; do not fail whole operation.
        }
      }
    }

    if (!preparedCount) {
      toast.show(t("ownerReservations.noRemindersPrepared"), "info");
    } else if (firstPopup) {
      toast.show(t("ownerReservations.preparedAndOpened", { count: preparedCount }), "success");
    } else {
      toast.show(t("ownerReservations.preparedAndCopied", { count: preparedCount }), "info");
    }

    if (skippedNoPhone || skippedUnavailable || skippedNotFailed) {
      toast.show(
        t("ownerReservations.skippedSummary", {
          noPhone: skippedNoPhone,
          unavailable: skippedUnavailable,
          notFailed: skippedNotFailed,
        }),
        "info"
      );
    }

    await fetchReservations();
    for (const reservationId of Object.keys(timelineOpen.value)) {
      const parsed = Number(reservationId);
      if (Number.isFinite(parsed) && parsed > 0) {
        await fetchTimeline(parsed);
      }
    }
  } catch (err) {
    toast.show(parseApiError(err, t("ownerReservations.prepareBulkReminderFailed")), "error");
  } finally {
    bulkReminderLoading.value = false;
  }
};

const clearPendingReminderReconciliation = () => {
  pendingReminderReconciliation.value = [];
};

const reconcilePendingReminders = async (status) => {
  if (!pendingReminderReconciliation.value.length) return;
  bulkReconcileLoading.value = true;
  try {
    const items = pendingReminderReconciliation.value.map((item) => ({
      lead_id: item.lead_id,
      reminder_id: item.reminder_id,
      status,
      error: status === "failed" ? t("ownerReservations.markFailed") : "",
    }));
    const res = await api.post("/owner/reservations/bulk-reminder-result/", { items });
    const updatedCount = Number(res?.data?.updated_count || 0);
    const missingCount = Number(res?.data?.missing_count || 0);
    pendingReminderReconciliation.value = [];
    toast.show(
      missingCount
        ? t("ownerReservations.reconciledWithMissing", { updated: updatedCount, missing: missingCount })
        : t("ownerReservations.reconciled", { updated: updatedCount }),
      "success"
    );
    await fetchReservations();
    for (const reservationId of Object.keys(timelineOpen.value)) {
      const parsed = Number(reservationId);
      if (Number.isFinite(parsed) && parsed > 0) {
        await fetchTimeline(parsed);
      }
    }
  } catch (err) {
    toast.show(parseApiError(err, t("ownerReservations.reconcileFailed")), "error");
  } finally {
    bulkReconcileLoading.value = false;
  }
};

const bulkUpdateStatus = async (status) => {
  if (!selectedIds.value.length) return;
  bulkUpdating.value = true;
  try {
    const res = await api.post("/owner/reservations/bulk-status/", {
      ids: selectedIds.value,
      status,
    });
    const updatedCount = Number(res?.data?.updated_count || 0);
    const missingCount = Array.isArray(res?.data?.missing_ids) ? res.data.missing_ids.length : 0;
    toast.show(
      missingCount
        ? t("ownerReservations.bulkUpdatedWithMissing", { updated: updatedCount, missing: missingCount })
        : t("ownerReservations.bulkUpdated", { updated: updatedCount }),
      "success"
    );
    await fetchReservations();
  } catch (err) {
    toast.show(parseApiError(err, t("ownerReservations.bulkUpdateFailed")), "error");
  } finally {
    bulkUpdating.value = false;
  }
};

const runBulkAction = async () => {
  if (!selectedIds.value.length) return;
  await bulkUpdateStatus(bulkAction.value);
};

const toggleSelection = (id) => {
  if (selectedIds.value.includes(id)) {
    selectedIds.value = selectedIds.value.filter((item) => item !== id);
    return;
  }
  selectedIds.value = [...selectedIds.value, id];
};

const toggleSelectAllOnPage = () => {
  const pageIds = reservations.value.map((row) => row.id);
  if (!pageIds.length) return;
  if (allSelectedOnPage.value) {
    selectedIds.value = selectedIds.value.filter((id) => !pageIds.includes(id));
    return;
  }
  const merged = new Set([...selectedIds.value, ...pageIds]);
  selectedIds.value = Array.from(merged);
};

const toggleFailedRetryQueue = async () => {
  reminderFilter.value = reminderFilter.value === "failed" ? "" : "failed";
  page.value = 1;
  await fetchReservations();
};

const applyFilters = async () => {
  page.value = 1;
  await fetchReservations();
};

const clearFilters = async () => {
  statusFilter.value = "";
  reminderFilter.value = "";
  searchQuery.value = "";
  dateFrom.value = "";
  dateTo.value = "";
  page.value = 1;
  await fetchReservations();
};

const onPageSizeChange = async () => {
  page.value = 1;
  await fetchReservations();
};

const goPrevPage = async () => {
  if (!pagination.value.has_prev) return;
  page.value = Math.max(1, page.value - 1);
  await fetchReservations();
};

const goNextPage = async () => {
  if (!pagination.value.has_next) return;
  page.value += 1;
  await fetchReservations();
};

const fetchTimeline = async (reservationId) => {
  timelineLoading.value = { ...timelineLoading.value, [reservationId]: true };
  try {
    const res = await api.get(`/owner/reservations/${reservationId}/timeline/`, {
      params: { limit: 80 },
    });
    timelineItems.value = {
      ...timelineItems.value,
      [reservationId]: Array.isArray(res.data) ? res.data : [],
    };
  } catch (err) {
    toast.show(parseApiError(err, t("ownerReservations.loadTimelineFailed")), "error");
  } finally {
    const clone = { ...timelineLoading.value };
    delete clone[reservationId];
    timelineLoading.value = clone;
  }
};

const toggleTimeline = async (reservationId) => {
  const isOpen = isTimelineOpen(reservationId);
  if (isOpen) {
    const next = { ...timelineOpen.value };
    delete next[reservationId];
    timelineOpen.value = next;
    return;
  }
  timelineOpen.value = { ...timelineOpen.value, [reservationId]: true };
  if (!timelineItems.value[reservationId]) {
    await fetchTimeline(reservationId);
  }
};

const addTimelineNote = async (reservationId) => {
  const note = String(timelineNote.value[reservationId] || "").trim();
  if (!note) {
    timelineNoteError.value = { ...timelineNoteError.value, [reservationId]: t("ownerReservations.writeShortNote") };
    return;
  }
  timelineNoteError.value = { ...timelineNoteError.value, [reservationId]: "" };
  timelineSubmitting.value = { ...timelineSubmitting.value, [reservationId]: true };
  try {
    const res = await api.post(`/owner/reservations/${reservationId}/timeline/`, { note });
    const existing = timelineFor(reservationId);
    timelineItems.value = {
      ...timelineItems.value,
      [reservationId]: [res.data, ...existing],
    };
    timelineNote.value = { ...timelineNote.value, [reservationId]: "" };
    toast.show(t("ownerReservations.noteAdded"), "success");
  } catch (err) {
    toast.show(parseApiError(err, t("ownerReservations.addTimelineFailed")), "error");
  } finally {
    const clone = { ...timelineSubmitting.value };
    delete clone[reservationId];
    timelineSubmitting.value = clone;
  }
};

const parseFilename = (contentDisposition) => {
  const value = String(contentDisposition || "");
  const match = /filename\*?=(?:UTF-8''|")?([^";]+)/i.exec(value);
  if (!match?.[1]) return "reservations.csv";
  return decodeURIComponent(match[1]).replace(/"/g, "").trim() || "reservations.csv";
};

const exportCsv = async () => {
  exporting.value = true;
  try {
    const response = await api.get("/owner/reservations/export/", {
      params: buildFilterParams(),
      responseType: "blob",
    });
    const contentDisposition = response?.headers?.["content-disposition"];
    const filename = parseFilename(contentDisposition);
    const blob = response?.data instanceof Blob ? response.data : new Blob([response?.data || ""], { type: "text/csv" });
    const objectUrl = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = objectUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(objectUrl);
    toast.show(t("ownerReservations.exportReady"), "success");
  } catch {
    toast.show(t("ownerReservations.exportFailed"), "error");
  } finally {
    exporting.value = false;
  }
};

// ── Waitlist ──────────────────────────────────────────────────────────────────
const waitlistDate = ref("");
const waitlistLoading = ref(false);
const waitlistError = ref(false);
const waitlistEntries = ref([]);

const fetchWaitlist = async () => {
  waitlistLoading.value = true;
  waitlistError.value = false;
  try {
    const params = {};
    if (waitlistDate.value) params.date = waitlistDate.value;
    const res = await api.get("/owner/waitlist/", { params });
    waitlistEntries.value = res.data?.results ?? [];
  } catch {
    waitlistError.value = true;
  } finally {
    waitlistLoading.value = false;
  }
};

const waitlistStatusLabel = (status) => {
  const map = {
    waiting: t("ownerReservations.waitlistStatusWaiting"),
    notified: t("ownerReservations.waitlistStatusNotified"),
    converted: t("ownerReservations.waitlistStatusConverted"),
    expired: t("ownerReservations.waitlistStatusExpired"),
  };
  return map[status] ?? status;
};

const waitlistStatusClass = (status) => {
  if (status === "waiting")   return "bg-amber-500/15 border border-amber-500/30 text-amber-300";
  if (status === "notified")  return "bg-sky-500/15 border border-sky-500/30 text-sky-300";
  if (status === "converted") return "bg-emerald-500/15 border border-emerald-500/30 text-emerald-300";
  if (status === "expired")   return "bg-slate-700/50 border border-slate-600 text-slate-400";
  return "bg-slate-700/50 border border-slate-600 text-slate-400";
};

onMounted(() => {
  // Instant first paint from cache (default view only), then revalidate silently.
  const cached = isDefaultReservationView() ? readCache(RES_CACHE) : null;
  if (cached) {
    reservations.value = Array.isArray(cached.reservations) ? cached.reservations : [];
    pagination.value = cached.pagination || pagination.value;
    if (cached.counts) serverCounts.value = { ...serverCounts.value, ...cached.counts };
    fetchReservations({ silent: true });
  } else {
    fetchReservations();
  }
  fetchWaitlist();
});

// Kept alive (see OwnerLayout) — onMounted won't re-run on revisit, so silently
// revalidate the list (and waitlist) when the user navigates back to this page.
let reservationsActivatedOnce = false;
onActivated(() => {
  if (!reservationsActivatedOnce) {
    reservationsActivatedOnce = true; // first activation pairs with onMounted
    return;
  }
  fetchReservations({ silent: true });
  fetchWaitlist();
});
</script>

<style scoped>
.owner-res-icon {
  width: 0.84rem;
  height: 0.84rem;
}

@media (max-width: 640px) {
  .owner-action-btn {
    min-height: 2.35rem;
    font-size: 0.74rem;
    letter-spacing: 0.01em;
  }
}
</style>
