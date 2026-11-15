<template>
  <div class="ui-page-shell space-y-5">
    <!-- Header -->
    <header class="ui-hero-ribbon ui-reveal px-4 py-3.5 md:px-5 md:py-4">
      <div class="flex items-start justify-between gap-3">
        <div>
          <p class="ui-kicker">{{ t('adminDrivers.kicker') }}</p>
          <h1 class="ui-page-title text-xl md:text-2xl leading-tight">{{ t('adminDrivers.title') }}</h1>
          <p class="mt-0.5 ui-subtle text-xs hidden sm:block">{{ t('adminDrivers.subtitle') }}</p>
        </div>
        <button
          class="ui-btn-outline ui-press inline-flex shrink-0 items-center gap-1.5 px-4 py-2 text-sm disabled:opacity-50"
          :disabled="loading"
          :aria-busy="loading"
          @click="fetchDrivers"
        >
          <svg v-if="loading" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-4 w-4 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
          {{ loading ? t('common.loading') : t('adminDrivers.refresh') }}
        </button>
      </div>
    </header>

    <!-- Active / Rejected toggle (A2-02): rejected drivers are no longer invisible -->
    <div class="flex gap-2" role="tablist" :aria-label="t('adminDrivers.title')">
      <button
        type="button"
        role="tab"
        :aria-selected="!showRejected"
        class="ui-state-chip ui-press"
        :data-active="!showRejected ? 'true' : 'false'"
        @click="setRejected(false)"
      >{{ t('adminDrivers.showActive') }}</button>
      <button
        type="button"
        role="tab"
        :aria-selected="showRejected"
        class="ui-state-chip ui-press"
        :data-active="showRejected ? 'true' : 'false'"
        @click="setRejected(true)"
      >{{ t('adminDrivers.showRejected') }}</button>
    </div>

    <!-- Loading: skeleton stats + table -->
    <template v-if="loading">
      <div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div v-for="i in 4" :key="i" class="animate-pulse rounded-2xl border border-slate-700/60 bg-slate-900 p-4 text-center space-y-2">
          <div class="mx-auto h-7 w-10 rounded bg-slate-700/60" />
          <div class="mx-auto h-2.5 w-20 rounded bg-slate-800/50" />
        </div>
      </div>
      <div class="ui-table-wrap hidden md:block">
        <table class="w-full min-w-[640px] text-sm">
          <thead class="bg-slate-800/60 text-xs text-slate-400">
            <tr>
              <th scope="col" class="px-4 py-3 text-start">{{ t('adminDrivers.colName') }}</th>
              <th scope="col" class="px-4 py-3 text-start">{{ t('adminDrivers.colPhone') }}</th>
              <th scope="col" class="px-4 py-3 text-center">{{ t('adminDrivers.colStatus') }}</th>
              <th scope="col" class="px-4 py-3 text-end">{{ t('adminDrivers.colJobs') }}</th>
              <th scope="col" class="px-4 py-3 text-end">{{ t('adminDrivers.colCompleted') }}</th>
              <th scope="col" class="px-4 py-3 text-end">{{ t('adminDrivers.colRating') }}</th>
              <th scope="col" class="px-4 py-3 text-end">{{ t('adminDrivers.colSince') }}</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-700/40">
            <tr v-for="i in 4" :key="i" class="animate-pulse">
              <td class="px-4 py-3 space-y-1.5"><div class="h-3 w-24 rounded bg-slate-700/60" /><div class="h-2 w-16 rounded bg-slate-800/40" /></td>
              <td class="px-4 py-3"><div class="h-3 w-20 rounded bg-slate-800/60" /></td>
              <td class="px-4 py-3"><div class="mx-auto h-4 w-12 rounded-full bg-slate-800/50" /></td>
              <td class="px-4 py-3"><div class="ms-auto h-3 w-6 rounded bg-slate-800/50" /></td>
              <td class="px-4 py-3"><div class="ms-auto h-3 w-8 rounded bg-slate-800/50" /></td>
              <td class="px-4 py-3"><div class="ms-auto h-3 w-8 rounded bg-slate-800/50" /></td>
              <td class="px-4 py-3"><div class="ms-auto h-3 w-16 rounded bg-slate-800/40" /></td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <!-- Error -->
    <div v-else-if="fetchError" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
      <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor">
        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm-.75-9.25a.75.75 0 011.5 0v3.5a.75.75 0 01-1.5 0v-3.5zm.75 6a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd" />
      </svg>
      <p class="flex-1 text-sm text-red-300">{{ t('adminDrivers.fetchError') }}</p>
      <button
        class="ui-press shrink-0 rounded-lg border border-red-500/40 px-3 py-1 text-xs font-semibold text-red-300 transition hover:bg-red-500/10"
        @click="fetchDrivers"
      >{{ t('common.retry') }}</button>
    </div>

    <!-- Empty -->
    <div v-else-if="!drivers.length" class="ui-empty-state text-center p-8 space-y-1">
      <p class="text-sm font-semibold text-slate-100">{{ showRejected ? t('adminDrivers.rejectedEmpty') : t('adminDrivers.empty') }}</p>
      <p v-if="!showRejected" class="text-xs text-slate-400">{{ t('adminDrivers.emptyHint') }}</p>
    </div>

    <template v-else>
      <!-- Stats bar (active drivers only; hidden for the rejected list) -->
      <div v-if="!showRejected" class="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div class="ui-panel p-4 text-center">
          <p class="text-2xl font-bold tabular-nums text-white">{{ totalDrivers }}</p>
          <p class="ui-stat-label mt-0.5">{{ t('adminDrivers.totalDrivers') }}</p>
        </div>
        <div class="ui-panel p-4 text-center">
          <p class="text-2xl font-bold tabular-nums text-emerald-400">{{ onlineCount }}</p>
          <p class="ui-stat-label mt-0.5">{{ t('adminDrivers.online') }}</p>
        </div>
        <div
          class="ui-panel p-4 text-center"
          :class="pendingCount ? 'border-amber-500/40' : ''"
        >
          <p class="text-2xl font-bold tabular-nums" :class="pendingCount ? 'text-amber-400' : 'text-white'">{{ pendingCount }}</p>
          <p class="ui-stat-label mt-0.5">{{ t('adminDrivers.pendingCount') }}</p>
        </div>
        <div class="ui-panel p-4 text-center">
          <p class="text-2xl font-bold tabular-nums text-white">{{ serverTotalDeliveries }}</p>
          <p class="ui-stat-label mt-0.5">{{ t('adminDrivers.totalDeliveries') }}</p>
        </div>
      </div>

      <!-- Cap note (A2-08): the list is capped at 200 rows -->
      <p v-if="driversTotal > 200" class="text-xs text-slate-500">{{ t('adminDrivers.showingFirst', { shown: drivers.length, total: driversTotal }) }}</p>

      <!-- A2-21: client-side search (name/phone) + status filter over the loaded
           list. Server-side search is out of scope for this P2; the 200-cap note
           (A2-08) above stays visible. -->
      <div class="flex flex-wrap items-center gap-2">
        <input
          v-model="searchQuery"
          type="search"
          class="ui-input min-w-[200px] flex-1 text-sm"
          :placeholder="t('adminDrivers.searchPlaceholder')"
          :aria-label="t('adminDrivers.searchPlaceholder')"
        />
        <select v-model="statusFilter" class="ui-input text-sm" :aria-label="t('adminDrivers.filterAll')">
          <option value="all">{{ t('adminDrivers.filterAll') }}</option>
          <option value="online">{{ t('adminDrivers.filterOnline') }}</option>
          <option value="offline">{{ t('adminDrivers.filterOffline') }}</option>
          <option value="pending">{{ t('adminDrivers.filterPending') }}</option>
        </select>
        <span v-if="isFiltering" class="text-xs text-slate-500 tabular-nums">{{ t('adminDrivers.filteredCount', { shown: filteredDrivers.length, total: drivers.length }) }}</span>
      </div>
      <div v-if="!filteredDrivers.length" class="ui-empty-state text-center p-8 space-y-1">
        <p class="text-sm font-semibold text-slate-100">{{ t('adminDrivers.noResults') }}</p>
      </div>

      <!-- Desktop table (hidden on mobile) -->
      <div v-if="filteredDrivers.length" class="ui-table-wrap hidden md:block">
        <table class="w-full min-w-[640px] text-sm">
          <thead class="bg-slate-800/60 text-xs text-slate-400">
            <tr>
              <th scope="col" class="px-4 py-3 text-start">{{ t('adminDrivers.colName') }}</th>
              <th scope="col" class="px-4 py-3 text-start">{{ t('adminDrivers.colPhone') }}</th>
              <th scope="col" class="px-4 py-3 text-center">{{ t('adminDrivers.colStatus') }}</th>
              <th scope="col" class="px-4 py-3 text-end">{{ t('adminDrivers.colJobs') }}</th>
              <th scope="col" class="px-4 py-3 text-end">{{ t('adminDrivers.colCompleted') }}</th>
              <th scope="col" class="px-4 py-3 text-end">{{ t('adminDrivers.colRating') }}</th>
              <th scope="col" class="px-4 py-3 text-end">{{ t('adminDrivers.colOwed') }}</th>
              <th scope="col" class="px-4 py-3 text-end">{{ t('adminDrivers.colSince') }}</th>
              <th scope="col" class="px-4 py-3 text-end" :aria-label="t('adminDrivers.colActions')"></th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-700/40">
            <tr
              v-for="(d, index) in filteredDrivers"
              :key="d.id"
              class="ui-reveal cursor-pointer hover:bg-slate-800/30 transition-colors"
              :class="{ 'bg-amber-500/5': !d.approved }"
              :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
              tabindex="0"
              @click="openDriver(d)"
              @keydown.enter.space.prevent="openDriver(d)"
            >
              <td class="px-4 py-3 text-slate-200 font-medium">
                <span class="truncate block">{{ d.name || t('adminDrivers.unnamed') }}</span>
                <span v-if="d.email" class="block text-[10px] text-slate-500 truncate">{{ d.email }}</span>
              </td>
              <td class="px-4 py-3 text-slate-400">
                <a v-if="d.phone" :href="`tel:${d.phone}`" class="hover:text-sky-400" @click.stop>{{ d.phone }}</a>
                <span v-else class="text-slate-600">—</span>
              </td>
              <td class="px-4 py-3 text-center">
                <span
                  v-if="showRejected"
                  class="rounded-full border border-red-500/40 bg-red-500/15 px-2 py-0.5 text-[10px] font-semibold text-red-300"
                  :title="d.driver_rejection_reason || ''"
                >
                  {{ t('adminDrivers.rejected') }}
                </span>
                <span
                  v-else-if="!d.approved"
                  class="rounded-full border border-amber-500/40 bg-amber-500/15 px-2 py-0.5 text-[10px] font-semibold text-amber-300"
                >
                  {{ t('adminDrivers.pendingCount') }}
                </span>
                <span
                  v-else
                  class="rounded-full px-2 py-0.5 text-[10px] font-semibold"
                  :class="d.is_online
                    ? 'bg-emerald-500/15 border border-emerald-500/30 text-emerald-300'
                    : 'bg-slate-700/50 border border-slate-600 text-slate-400'"
                >
                  {{ d.is_online ? t('adminDrivers.statusOnline') : t('adminDrivers.statusOffline') }}
                </span>
                <a
                  v-if="d.is_online && d.driver_lat && d.driver_lng && !isPositionStale(d)"
                  :href="`https://www.google.com/maps/search/?api=1&query=${d.driver_lat},${d.driver_lng}`"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="ms-1 text-[10px] text-sky-400 hover:text-sky-300"
                  :aria-label="t('adminDrivers.viewOnMap')"
                  @click.stop
                ><span aria-hidden="true">📍</span></a>
                <span v-if="d.approved && (d.position_updated_at || d.is_online)" class="mt-1 block text-[10px] text-slate-500 tabular-nums">{{ t('adminDrivers.lastSeen', { when: lastSeenText(d) }) }}</span>
                <span v-if="d.approved && d.is_online && isPositionStale(d)" class="mt-1 inline-block rounded-full border border-amber-500/40 bg-amber-500/15 px-1.5 py-0.5 text-[10px] font-semibold text-amber-300">{{ t('adminDrivers.staleBadge') }}</span>
              </td>
              <td class="px-4 py-3 text-end tabular-nums text-slate-300">{{ d.total_jobs }}</td>
              <td class="px-4 py-3 text-end tabular-nums text-emerald-400">{{ d.completed_jobs }}</td>
              <td class="px-4 py-3 text-end">
                <span v-if="d.avg_rating != null" class="inline-flex items-center gap-1 text-amber-300 tabular-nums" :aria-label="t('adminDrivers.ratingLabel', { value: formatRating(d.avg_rating) })"><svg aria-hidden="true" viewBox="0 0 20 20" fill="currentColor" class="h-3.5 w-3.5 shrink-0"><path d="M10 1.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8L10 14.9l-5.2 2.7 1-5.8L1.5 7.7l5.9-.9L10 1.5z" /></svg>{{ formatRating(d.avg_rating) }}</span>
                <span v-else class="text-slate-600">—</span>
              </td>
              <td class="px-4 py-3 text-end tabular-nums" :class="Number(d.owed) > 0 ? 'text-emerald-400 font-semibold' : 'text-slate-500'">
                {{ fmtMoney(d.owed) }}
              </td>
              <td class="px-4 py-3 text-end text-slate-500 text-xs tabular-nums">{{ formatDate(d.created_at) }}</td>
              <td class="px-4 py-3 text-end">
                <button
                  v-if="showRejected"
                  type="button"
                  class="rounded-lg border border-emerald-500/40 px-2.5 py-1 text-xs font-semibold text-emerald-300 hover:bg-emerald-500/10 ui-press disabled:opacity-50"
                  :disabled="reapprovingId === d.id"
                  @click.stop="reapproveDriver(d)"
                >{{ t('adminDrivers.reapprove') }}</button>
                <span v-else class="text-slate-600 rtl:scale-x-[-1]" aria-hidden="true">›</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Mobile card list (hidden on md+) -->
      <ul v-if="filteredDrivers.length" class="md:hidden space-y-2">
        <li
          v-for="(d, index) in filteredDrivers"
          :key="d.id"
          class="ui-admin-card ui-reveal ui-surface-lift cursor-pointer"
          :class="{ 'border-amber-500/30 bg-amber-500/5': !d.approved }"
          :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
          tabindex="0"
          @click="openDriver(d)"
          @keydown.enter.space.prevent="openDriver(d)"
        >
          <div class="flex items-start justify-between gap-2">
            <div class="min-w-0">
              <div class="flex items-center gap-1.5 flex-wrap">
                <span class="font-medium text-slate-200 truncate">{{ d.name || t('adminDrivers.unnamed') }}</span>
                <span
                  v-if="showRejected"
                  class="shrink-0 rounded-full border border-red-500/40 bg-red-500/15 px-1.5 py-0.5 text-[10px] font-semibold text-red-300"
                >{{ t('adminDrivers.rejected') }}</span>
                <span
                  v-else-if="!d.approved"
                  class="shrink-0 rounded-full border border-amber-500/40 bg-amber-500/15 px-1.5 py-0.5 text-[10px] font-semibold text-amber-300"
                >{{ t('adminDrivers.pendingCount') }}</span>
                <span
                  v-else
                  class="shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-semibold"
                  :class="d.is_online ? 'bg-emerald-500/15 border border-emerald-500/30 text-emerald-300' : 'bg-slate-700/50 border border-slate-600 text-slate-400'"
                >
                  {{ d.is_online ? t('adminDrivers.statusOnline') : t('adminDrivers.statusOffline') }}
                </span>
              </div>
              <p class="mt-0.5 text-xs text-slate-500 truncate">{{ d.phone || d.email || '' }}</p>
            </div>
            <div class="shrink-0 text-end">
              <p class="font-semibold tabular-nums text-sm" :class="Number(d.owed) > 0 ? 'text-emerald-400' : 'text-slate-500'">{{ fmtMoney(d.owed) }}</p>
              <p class="text-[10px] text-slate-500 tabular-nums">{{ d.completed_jobs }} / {{ d.total_jobs }}</p>
            </div>
          </div>
          <p class="mt-1.5 text-[10px] text-slate-600 tabular-nums">{{ formatDate(d.created_at) }}</p>
          <p v-if="d.approved && (d.position_updated_at || d.is_online)" class="mt-0.5 text-[10px] text-slate-500 tabular-nums">{{ t('adminDrivers.lastSeen', { when: lastSeenText(d) }) }}<span v-if="d.is_online && isPositionStale(d)" class="ms-1 rounded-full border border-amber-500/40 bg-amber-500/15 px-1.5 py-0.5 font-semibold text-amber-300">{{ t('adminDrivers.staleBadge') }}</span></p>
          <p v-if="showRejected && d.driver_rejection_reason" class="mt-1 text-[11px] text-slate-400">{{ t('adminDrivers.rejectedReason') }}: {{ d.driver_rejection_reason }}</p>
          <button
            v-if="showRejected"
            type="button"
            class="mt-2 rounded-lg border border-emerald-500/40 px-2.5 py-1 text-xs font-semibold text-emerald-300 hover:bg-emerald-500/10 ui-press disabled:opacity-50"
            :disabled="reapprovingId === d.id"
            @click.stop="reapproveDriver(d)"
          >{{ t('adminDrivers.reapprove') }}</button>
        </li>
      </ul>
    </template>

    <!-- Driver earnings detail slide-over -->
    <Teleport to="body">
      <Transition enter-active-class="transition-opacity duration-200" enter-from-class="opacity-0" leave-active-class="transition-opacity duration-150" leave-to-class="opacity-0">
        <div v-if="selected" class="fixed inset-0 z-50 bg-black/60" @click.self="selected = null">
          <Transition
            enter-active-class="transition-transform duration-200"
            enter-from-class="ltr:translate-x-full rtl:-translate-x-full"
            leave-active-class="transition-transform duration-150"
            leave-to-class="ltr:translate-x-full rtl:-translate-x-full"
          >
            <aside v-if="selected" ref="slideOverRef" class="absolute end-0 top-0 h-full w-full max-w-md overflow-y-auto border-s border-slate-700 bg-slate-900 p-5 space-y-5" role="dialog" :aria-label="selected.name || t('adminDrivers.unnamed')" aria-modal="true" @keydown.esc="selected = null">
              <!-- Header -->
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <p class="ui-kicker">{{ t('adminDrivers.detailKicker') }}</p>
                  <h2 class="text-lg font-semibold text-white truncate">{{ selected.name || t('adminDrivers.unnamed') }}</h2>
                  <p class="text-xs text-slate-500 truncate">{{ selected.phone }}</p>
                  <p v-if="selected.approved && (selected.position_updated_at || selected.is_online)" class="mt-0.5 text-[11px] text-slate-500 tabular-nums">{{ t('adminDrivers.lastSeen', { when: lastSeenText(selected) }) }}<span v-if="selected.is_online && isPositionStale(selected)" class="ms-1 rounded-full border border-amber-500/40 bg-amber-500/15 px-1.5 py-0.5 text-[10px] font-semibold text-amber-300">{{ t('adminDrivers.staleBadge') }}</span></p>
                </div>
                <button
                  class="ui-press shrink-0 rounded-full p-1.5 text-slate-500 hover:text-slate-300 ui-touch-target"
                  :aria-label="t('common.close')"
                  autofocus
                  @click="selected = null"
                >
                  <svg viewBox="0 0 20 20" fill="currentColor" class="h-4 w-4" aria-hidden="true">
                    <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
                  </svg>
                </button>
              </div>

              <div v-if="loadingDetail" class="space-y-3">
                <div v-for="i in 3" :key="i" class="h-14 animate-pulse rounded-xl bg-slate-800/50" />
              </div>

              <!-- Fetch error: don't leave the panel blank (no earnings / vetting / payout controls) -->
              <div v-else-if="detailError" class="space-y-3 py-8 text-center" role="alert">
                <p class="text-sm text-red-300">{{ detailError }}</p>
                <button class="ui-btn-outline px-4 py-1.5 text-xs" @click="openDriver(selected)">{{ t('common.retry') }}</button>
              </div>

              <template v-else-if="detail">
                <!-- Earnings tiles -->
                <div class="grid grid-cols-3 gap-2">
                  <div class="rounded-xl border border-slate-700/60 bg-slate-800/30 p-3 text-center">
                    <p class="ui-stat-label">{{ t('adminDrivers.earned') }}</p>
                    <p class="mt-0.5 text-sm font-bold tabular-nums text-slate-200">{{ fmtMoney(detail.earned) }}</p>
                  </div>
                  <div class="rounded-xl border border-slate-700/60 bg-slate-800/30 p-3 text-center">
                    <p class="ui-stat-label">{{ t('adminDrivers.paid') }}</p>
                    <p class="mt-0.5 text-sm font-bold tabular-nums text-slate-400">{{ fmtMoney(detail.paid) }}</p>
                  </div>
                  <div class="rounded-xl border border-slate-700/60 bg-slate-800/30 p-3 text-center">
                    <p class="ui-stat-label">{{ t('adminDrivers.colOwed') }}</p>
                    <p class="mt-0.5 text-sm font-bold tabular-nums text-emerald-400">{{ fmtMoney(detail.owed) }}</p>
                  </div>
                </div>

                <!-- Vetting / approval -->
                <div
                  class="rounded-xl border p-3 space-y-2.5"
                  :class="selected.approved ? 'border-emerald-500/30 bg-emerald-500/8' : 'border-amber-500/40 bg-amber-500/8'"
                >
                  <div class="min-w-0">
                    <p class="text-sm font-semibold" :class="selected.approved ? 'text-emerald-300' : 'text-amber-300'">
                      {{ selected.approved ? t('adminDrivers.approved') : t('adminDrivers.pending') }}
                    </p>
                    <p v-if="selected.vehicle" class="truncate text-xs text-slate-400">{{ selected.vehicle }}</p>
                  </div>
                  <!-- Optional reject reason — surfaced later on the driver's own status screen. -->
                  <input
                    v-if="!selected.approved"
                    v-model="rejectReason"
                    type="text"
                    maxlength="300"
                    class="ui-input text-sm"
                    :placeholder="t('adminDrivers.rejectReasonPlaceholder')"
                    :aria-label="t('adminDrivers.rejectReasonPlaceholder')"
                  />
                  <div class="flex gap-2">
                    <button
                      v-if="!selected.approved"
                      class="flex-1 rounded-xl bg-emerald-600 py-2 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-50"
                      :disabled="vetting"
                      @click="setApproval(true)"
                    >{{ t('adminDrivers.approve') }}</button>
                    <button
                      class="flex-1 rounded-xl border border-red-400/40 py-2 text-sm font-semibold text-red-300 hover:border-red-400/70 disabled:opacity-50"
                      :disabled="vetting"
                      @click="setApproval(false)"
                    >{{ t('adminDrivers.reject') }}</button>
                  </div>
                </div>

                <!-- Car documents (car vehicle type only) -->
                <div
                  v-if="selected.driver_vehicle_type === 'car'"
                  class="rounded-xl border p-3 space-y-2.5"
                  :class="selected.driver_car_approved
                    ? 'border-emerald-500/30 bg-emerald-500/8'
                    : (selected.driver_licence_url && selected.driver_insurance_url)
                      ? 'border-amber-500/40 bg-amber-500/8'
                      : 'border-slate-700/60 bg-slate-800/30'"
                >
                  <div class="flex items-center justify-between gap-2 flex-wrap">
                    <p class="text-sm font-semibold text-slate-200">{{ t('adminConsole.carDocs') }}</p>
                    <span
                      class="rounded-full px-2 py-0.5 text-[10px] font-semibold"
                      :class="selected.driver_car_approved
                        ? 'bg-emerald-500/15 border border-emerald-500/30 text-emerald-300'
                        : (selected.driver_licence_url && selected.driver_insurance_url)
                          ? 'bg-amber-500/15 border border-amber-500/40 text-amber-300'
                          : 'bg-slate-700/50 border border-slate-600 text-slate-400'"
                    >
                      {{ selected.driver_car_approved
                        ? t('adminConsole.carApproved')
                        : (selected.driver_licence_url && selected.driver_insurance_url)
                          ? t('adminConsole.carPending')
                          : t('adminConsole.carMissing') }}
                    </span>
                  </div>
                  <div v-if="selected.driver_licence_url || selected.driver_insurance_url" class="flex gap-3 flex-wrap text-xs">
                    <a
                      v-if="selected.driver_licence_url"
                      :href="selected.driver_licence_url"
                      target="_blank"
                      rel="noopener noreferrer"
                      class="text-sky-400 hover:text-sky-300 underline underline-offset-2"
                    >{{ t('adminConsole.licenceLink') }}</a>
                    <a
                      v-if="selected.driver_insurance_url"
                      :href="selected.driver_insurance_url"
                      target="_blank"
                      rel="noopener noreferrer"
                      class="text-sky-400 hover:text-sky-300 underline underline-offset-2"
                    >{{ t('adminConsole.insuranceLink') }}</a>
                  </div>
                  <!-- A2-10: show the stored expiries with expired/soon flags -->
                  <div v-if="selected.driver_licence_expiry || selected.driver_insurance_expiry" class="space-y-1 text-xs">
                    <p v-if="selected.driver_licence_expiry" class="flex items-center gap-1.5 flex-wrap">
                      <span class="text-slate-400">{{ t('adminConsole.licenceExpiry') }}: {{ formatDate(selected.driver_licence_expiry) }}</span>
                      <span v-if="expiryState(selected.driver_licence_expiry) === 'expired'" class="rounded-full bg-red-500/15 px-2 py-0.5 text-[10px] font-semibold text-red-300">{{ t('adminConsole.expiryExpired') }}</span>
                      <span v-else-if="expiryState(selected.driver_licence_expiry) === 'soon'" class="rounded-full bg-amber-500/15 px-2 py-0.5 text-[10px] font-semibold text-amber-300">{{ t('adminConsole.expirySoon') }}</span>
                    </p>
                    <p v-if="selected.driver_insurance_expiry" class="flex items-center gap-1.5 flex-wrap">
                      <span class="text-slate-400">{{ t('adminConsole.insuranceExpiry') }}: {{ formatDate(selected.driver_insurance_expiry) }}</span>
                      <span v-if="expiryState(selected.driver_insurance_expiry) === 'expired'" class="rounded-full bg-red-500/15 px-2 py-0.5 text-[10px] font-semibold text-red-300">{{ t('adminConsole.expiryExpired') }}</span>
                      <span v-else-if="expiryState(selected.driver_insurance_expiry) === 'soon'" class="rounded-full bg-amber-500/15 px-2 py-0.5 text-[10px] font-semibold text-amber-300">{{ t('adminConsole.expirySoon') }}</span>
                    </p>
                  </div>
                  <!-- A2-10: expiry date inputs on approve (prefilled from the stored values) -->
                  <div v-if="!selected.driver_car_approved && selected.driver_licence_url && selected.driver_insurance_url" class="grid grid-cols-2 gap-2">
                    <label class="space-y-1 text-xs text-slate-400">{{ t('adminConsole.licenceExpiry') }}
                      <input v-model="licenceExpiryInput" type="date" class="ui-input w-full text-sm" :aria-label="t('adminConsole.licenceExpiry')" />
                    </label>
                    <label class="space-y-1 text-xs text-slate-400">{{ t('adminConsole.insuranceExpiry') }}
                      <input v-model="insuranceExpiryInput" type="date" class="ui-input w-full text-sm" :aria-label="t('adminConsole.insuranceExpiry')" />
                    </label>
                  </div>
                  <div v-if="selected.driver_licence_url && selected.driver_insurance_url" class="flex gap-2">
                    <button
                      v-if="!selected.driver_car_approved"
                      class="flex-1 rounded-xl bg-emerald-600 py-2 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-50"
                      :disabled="vettingCar"
                      @click="setCarApproval(true)"
                    >{{ t('adminConsole.carApprove') }}</button>
                    <button
                      v-if="selected.driver_car_approved"
                      class="flex-1 rounded-xl border border-red-400/40 py-2 text-sm font-semibold text-red-300 hover:border-red-400/70 disabled:opacity-50"
                      :disabled="vettingCar"
                      @click="setCarApproval(false)"
                    >{{ t('adminConsole.carReject') }}</button>
                  </div>
                </div>

                <!-- Payout form (A2-09): prefill + cap on the DELIVERY-ledger cap
                     (earned − paid), not the wallet balance — the wallet also holds
                     ride/tip credits the ledger must not pay out. -->
                <div v-if="payoutCap > 0" class="rounded-xl border border-slate-700/60 bg-slate-800/30 p-3 space-y-2.5">
                  <p class="text-sm font-semibold text-slate-200">{{ t('adminDrivers.recordPayout') }}</p>
                  <p class="text-[11px] text-slate-500">{{ t('adminDrivers.payoutCapNote', { ledger: fmtMoney(detail.ledger_owed), cashout: fmtMoney(detail.cashout_total), wallet: fmtMoney(detail.wallet_balance) }) }}</p>
                  <div class="flex gap-2">
                    <input v-model="payAmount" type="number" step="0.01" min="0.01" :max="payoutCap" class="ui-input flex-1 text-sm" :placeholder="t('adminDrivers.amount')" :aria-label="t('adminDrivers.amount')" />
                    <select v-model="payMethod" class="ui-input text-sm" :aria-label="t('adminDrivers.payMethod')">
                      <option value="cash">{{ t('adminDrivers.methodCash') }}</option>
                      <option value="transfer">{{ t('adminDrivers.methodTransfer') }}</option>
                    </select>
                  </div>
                  <div class="grid grid-cols-2 gap-2">
                    <input v-model="payNote" type="text" maxlength="200" class="ui-input text-sm" :placeholder="t('adminDrivers.payoutNote')" :aria-label="t('adminDrivers.payoutNote')" />
                    <input v-model="payReference" type="text" maxlength="120" class="ui-input text-sm" :placeholder="t('adminDrivers.payoutReference')" :aria-label="t('adminDrivers.payoutReference')" />
                  </div>
                  <button class="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-emerald-600 py-2 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-50" :disabled="paying" :aria-busy="paying" @click="submitPayout">
                    <svg v-if="paying" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin shrink-0">
                      <path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/>
                    </svg>
                    {{ paying ? t('common.loading') : t('adminDrivers.payOut') }}
                  </button>
                  <p v-if="payError" class="text-xs text-red-300" role="alert">{{ payError }}</p>
                </div>

                <!-- Recent deliveries -->
                <div class="space-y-2">
                  <p class="ui-kicker">{{ t('adminDrivers.recentDeliveries') }}</p>
                  <p v-if="detail.deliveries.length >= historyLimit" class="text-[11px] text-slate-500">{{ t('adminDrivers.historyCapNote', { limit: historyLimit }) }}</p>
                  <p v-if="!detail.deliveries.length" class="py-2 text-center text-xs text-slate-600 italic">{{ t('adminDrivers.noneYet') }}</p>
                  <ul v-else class="space-y-1.5">
                    <li v-for="j in detail.deliveries" :key="j.order_number" class="flex items-center justify-between gap-2 rounded-lg bg-slate-800/30 px-3 py-2 text-xs">
                      <span class="font-mono text-slate-400">#{{ j.order_number }}</span>
                      <span class="flex items-center gap-2 tabular-nums"><span class="text-slate-600">{{ formatDate(j.delivered_at) }}</span><span class="font-semibold text-emerald-300">+{{ fmtMoney(j.payout) }}</span></span>
                    </li>
                  </ul>
                </div>

                <!-- Payout history -->
                <div class="space-y-2">
                  <p class="ui-kicker">{{ t('adminDrivers.payoutHistory') }}</p>
                  <p v-if="detail.payouts.length >= historyLimit" class="text-[11px] text-slate-500">{{ t('adminDrivers.historyCapNote', { limit: historyLimit }) }}</p>
                  <p v-if="!detail.payouts.length" class="py-2 text-center text-xs text-slate-600 italic">{{ t('adminDrivers.noneYet') }}</p>
                  <ul v-else class="space-y-1.5">
                    <li v-for="p in detail.payouts" :key="p.id" class="rounded-lg bg-slate-800/30 px-3 py-2 text-xs">
                      <span class="flex items-center justify-between gap-2">
                        <span class="text-slate-400">{{ p.method === 'cash' ? t('adminDrivers.methodCash') : t('adminDrivers.methodTransfer') }} · {{ formatDate(p.created_at) }}</span>
                        <span class="font-semibold tabular-nums text-slate-300">−{{ fmtMoney(p.amount) }}</span>
                      </span>
                      <span v-if="p.note || p.reference" class="mt-0.5 block text-slate-500">{{ p.reference }}<span v-if="p.reference && p.note"> · </span>{{ p.note }}</span>
                    </li>
                  </ul>
                </div>
              </template>
            </aside>
          </Transition>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { useI18n } from '../composables/useI18n';
import { useConfirmModal } from '../composables/useConfirmModal';
import { useFocusTrap } from '../composables/useFocusTrap';
import api from '../lib/api';
import { formatCurrencyString } from '../lib/intlFormatters';
import { useToastStore } from '../stores/toast';
import { newIdempotencyKey } from '../lib/idempotency';

const { t, currentLocale } = useI18n();
const { confirm } = useConfirmModal();
const toast = useToastStore();

const loading = ref(true);
const fetchError = ref(false);
const drivers = ref([]);
const showRejected = ref(false);
const reapprovingId = ref(null);

const setRejected = (value) => {
  if (showRejected.value === value) return;
  showRejected.value = value;
  fetchDrivers();
};

// A2-02: re-approve a rejected driver from the rejected list (no slide-over —
// the earnings detail 404s for a non-driver). Confirm, POST approve, drop the row.
const reapproveDriver = async (d) => {
  const ok = await confirm({
    title: t('adminDrivers.reapproveConfirmTitle', { name: d.name || t('adminDrivers.unnamed') }),
    body: t('adminDrivers.reapproveConfirmBody', { name: d.name || t('adminDrivers.unnamed') }),
    confirmLabel: t('adminDrivers.reapprove'),
    danger: false,
  });
  if (!ok) return;
  reapprovingId.value = d.id;
  try {
    await api.post(`/admin/drivers/${d.id}/approve/`, {});
    drivers.value = drivers.value.filter((x) => x.id !== d.id);
    toast.show(t('adminDrivers.reapproveDone'), 'success');
  } catch (err) {
    toast.show(err?.response?.data?.detail || t('adminDrivers.actionFailed'), 'error');
  } finally {
    reapprovingId.value = null;
  }
};

const fmtMoney = (v) =>
  formatCurrencyString(currentLocale.value, v, 'MAD', { maximumFractionDigits: 2 });

// ── Earnings detail slide-over + payout ─────────────────────────────────────
const selected = ref(null);
// Focus trap for the money/vetting slide-over (mirrors AdminCustomers / AdminWallet):
// Tab stays inside the drawer, focus enters on open + returns to the trigger on close.
const slideOverRef = ref(null);
useFocusTrap(slideOverRef, computed(() => !!selected.value));
const detail = ref(null);
const loadingDetail = ref(false);
const payAmount = ref('');
// A2-09: the payout cap is min(ledger_owed, wallet_balance) — the delivery
// ledger cap record_driver_payout enforces, bounded by the cash actually in
// the wallet. Falls back to `owed` when the envelope lacks the new fields.
const payoutCap = computed(() => {
  if (!detail.value) return 0;
  const ledger = Number(detail.value.ledger_owed ?? detail.value.owed);
  const wallet = Number(detail.value.wallet_balance ?? detail.value.owed);
  if (!Number.isFinite(ledger) || !Number.isFinite(wallet)) return 0;
  return Math.max(0, Math.min(ledger, wallet));
});
const payMethod = ref('cash');
// A2-26: the earnings endpoint caps each history at the latest `limit` rows
// (server-side, see AdminDriverEarningsView.get) — the cap note renders from it.
const historyLimit = computed(() => Number(detail.value?.limit) || 20);
// A2-27: note/reference recorded with the settlement (endpoint already accepts
// both; history already returns both — the form just never sent them).
const payNote = ref('');
const payReference = ref('');
const paying = ref(false);
const payError = ref('');
// Idempotency key for the payout POST. Generated once per payout intent and held
// ACROSS retries (cleared only on success / when a different driver panel opens), so
// a click after an ambiguous failure (response lost mid-flight) replays the same key
// server-side instead of committing a SECOND real payout. Mirrors AdminWallet /
// AdminCustomers. A fresh-key-per-click let a partial settlement double-pay.
let payoutKey = null;
const detailError = ref(''); // panel-level fetch error (distinct from payError = the payout error shown inside the panel)
const vetting = ref(false);
const vettingCar = ref(false);
const rejectReason = ref(''); // optional reason posted with a reject; server-truncated to 300 chars
// A2-10: expiry date inputs on car approval, prefilled from the stored values.
const licenceExpiryInput = ref('');
const insuranceExpiryInput = ref('');
// 'expired' when the date is past, 'soon' when it expires within 30 days.
const expiryState = (iso) => {
  if (!iso) return '';
  const d = new Date(String(iso).slice(0, 10) + 'T00:00:00');
  if (Number.isNaN(d.getTime())) return '';
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  if (d < today) return 'expired';
  const soon = new Date(today);
  soon.setDate(soon.getDate() + 30);
  return d <= soon ? 'soon' : '';
};

const openDriver = async (d) => {
  selected.value = d;
  // A2-10: prefill the expiry inputs from the stored values (date inputs take YYYY-MM-DD).
  licenceExpiryInput.value = String(d.driver_licence_expiry || '').slice(0, 10);
  insuranceExpiryInput.value = String(d.driver_insurance_expiry || '').slice(0, 10);
  detail.value = null;
  payError.value = '';
  detailError.value = '';
  rejectReason.value = '';
  payoutKey = null; // new panel → new payout intent → fresh key
  loadingDetail.value = true;
  try {
    const res = await api.get(`/admin/drivers/${d.id}/earnings/`);
    detail.value = res.data;
    // A2-09: prefill on the ledger cap (min with the wallet balance).
    const ledger = Number(res.data.ledger_owed ?? res.data.owed);
    const wallet = Number(res.data.wallet_balance ?? res.data.owed);
    payAmount.value = Math.max(0, Math.min(ledger, wallet)).toFixed(2);
    payMethod.value = 'cash';
    payNote.value = '';
    payReference.value = '';
  } catch {
    detailError.value = t('adminDrivers.fetchError');
  } finally {
    loadingDetail.value = false;
  }
};

const submitPayout = async () => {
  payError.value = '';
  const amount = parseFloat(payAmount.value);
  if (!amount || amount <= 0) { payError.value = t('adminDrivers.payoutInvalid'); return; }
  if (amount > payoutCap.value) { payError.value = t('adminDrivers.payoutInvalid'); return; }
  const okPay = await confirm({
    title: t('adminDrivers.payoutConfirmTitle'),
    body: t('adminDrivers.payoutConfirmBody', { amount: fmtMoney(amount), name: selected.value?.name || t('adminDrivers.thisDriver') }),
    confirmLabel: t('adminDrivers.payoutConfirmCta'),
    danger: true,
  });
  if (!okPay) return;
  paying.value = true;
  if (!payoutKey) payoutKey = newIdempotencyKey(); // stable across retries of THIS payout
  try {
    const res = await api.post(`/admin/drivers/${selected.value.id}/payout/`, {
      amount: amount.toFixed(2),
      method: payMethod.value,
      note: payNote.value.trim(),
      reference: payReference.value.trim(),
      idempotency_key: payoutKey,
    });
    payoutKey = null; // settled — the next payout gets a fresh key
    toast.show(t('adminDrivers.payoutDone'), 'success');
    // Refresh the detail panel + the row's owed.
    await openDriver(selected.value);
    const row = drivers.value.find((d) => d.id === selected.value.id);
    if (row) { row.owed = res.data.owed; row.paid = res.data.paid; }
  } catch (err) {
    payError.value = err?.response?.data?.detail || t('adminDrivers.payoutFailed');
  } finally {
    paying.value = false;
  }
};

const setApproval = async (approve) => {
  if (!selected.value || vetting.value) return;
  // A2-23: approve confirms like reject does — approving grants job access and
  // customer addresses, so it is no longer a one-click vetting decision.
  if (approve) {
    const okApprove = await confirm({
      title: t('adminDrivers.approveConfirmTitle'),
      body: t('adminDrivers.approveConfirmBody', { name: selected.value?.name || t('adminDrivers.thisDriver') }),
      confirmLabel: t('adminDrivers.approveConfirmCta'),
      danger: false,
    });
    if (!okApprove) return;
  } else {
    const okReject = await confirm({
      title: t('adminDrivers.rejectConfirmTitle'),
      body: t('adminDrivers.rejectConfirmBody', { name: selected.value?.name || t('adminDrivers.thisDriver') }),
      confirmLabel: t('adminDrivers.rejectConfirmCta'),
      danger: true,
    });
    if (!okReject) return;
  }
  vetting.value = true;
  try {
    const body = approve ? {} : { reason: rejectReason.value.trim() };
    await api.post(`/admin/drivers/${selected.value.id}/${approve ? 'approve' : 'reject'}/`, body);
    toast.show(approve ? t('adminDrivers.approveDone') : t('adminDrivers.rejectDone'), 'success');
    if (approve) {
      selected.value.approved = true;
      const row = drivers.value.find((d) => d.id === selected.value.id);
      if (row) row.approved = true;
    } else {
      // Rejected drivers are no longer drivers — drop from the list and close.
      drivers.value = drivers.value.filter((d) => d.id !== selected.value.id);
      selected.value = null;
    }
  } catch (err) {
    toast.show(err?.response?.data?.detail || t('adminDrivers.actionFailed'), 'error');
  } finally {
    vetting.value = false;
  }
};

const setCarApproval = async (approve) => {
  if (!selected.value || vettingCar.value) return;
  // A2-10: block approval when an effective expiry (entered or stored) is past —
  // the server enforces the same check, this stops the click before the round trip.
  if (approve) {
    const todayStr = new Date().toISOString().slice(0, 10);
    const effLicence = (licenceExpiryInput.value || selected.value.driver_licence_expiry || '').slice(0, 10);
    const effInsurance = (insuranceExpiryInput.value || selected.value.driver_insurance_expiry || '').slice(0, 10);
    if ((effLicence && effLicence < todayStr) || (effInsurance && effInsurance < todayStr)) {
      toast.show(t('adminConsole.carExpiryPast'), 'error');
      return;
    }
  }
  if (!approve) {
    const okCarReject = await confirm({
      title: t('adminConsole.carRejectConfirmTitle'),
      body: t('adminConsole.carRejectConfirmBody', { name: selected.value?.name || t('adminDrivers.thisDriver') }),
      confirmLabel: t('adminConsole.carReject'),
      danger: true,
    });
    if (!okCarReject) return;
  }
  vettingCar.value = true;
  try {
    const body = approve
      ? {
          licence_expiry: licenceExpiryInput.value || undefined,
          insurance_expiry: insuranceExpiryInput.value || undefined,
        }
      : {};
    const res = await api.post(`/admin/drivers/${selected.value.id}/${approve ? 'car-approve' : 'car-reject'}/`, body);
    toast.show(approve ? t('adminConsole.carApproved') : t('adminConsole.carReject'), 'success');
    selected.value.driver_car_approved = approve;
    // The server echoes the (possibly updated) expiries — sync them.
    if (res.data?.driver_licence_expiry !== undefined) selected.value.driver_licence_expiry = res.data.driver_licence_expiry;
    if (res.data?.driver_insurance_expiry !== undefined) selected.value.driver_insurance_expiry = res.data.driver_insurance_expiry;
    const row = drivers.value.find((d) => d.id === selected.value.id);
    if (row) {
      row.driver_car_approved = approve;
      if (res.data?.driver_licence_expiry !== undefined) row.driver_licence_expiry = res.data.driver_licence_expiry;
      if (res.data?.driver_insurance_expiry !== undefined) row.driver_insurance_expiry = res.data.driver_insurance_expiry;
    }
  } catch (err) {
    toast.show(err?.response?.data?.detail || t('adminDrivers.actionFailed'), 'error');
  } finally {
    vettingCar.value = false;
  }
};

// A2-08: the server returns {results, total, limit, stats} — stats are computed
// over the FULL driver set, not the capped 200 rows. Fall back to client-side
// computation when the envelope is absent (older response shape).
const serverStats = ref(null);
const driversTotal = ref(0);
const onlineCount = computed(() => serverStats.value?.online ?? drivers.value.filter(d => d.is_online).length);
const pendingCount = computed(() => serverStats.value?.pending ?? drivers.value.filter(d => !d.approved).length);
const totalDrivers = computed(() => serverStats.value?.total ?? drivers.value.length);
const serverTotalDeliveries = computed(() => serverStats.value?.total_deliveries ?? drivers.value.reduce((sum, d) => sum + d.completed_jobs, 0));
// Surface pending applications first so admins review them promptly.
const sortedDrivers = computed(() =>
  [...drivers.value].sort((a, b) => (a.approved === b.approved ? 0 : a.approved ? 1 : -1))
);

// A2-21: client-side search (name/phone/email, case-insensitive) + status
// filter over the loaded list. No pagination: the server caps at 200 rows and
// the A2-08 cap note stays visible above the table.
const searchQuery = ref('');
const statusFilter = ref('all');
const filteredDrivers = computed(() => {
  const q = searchQuery.value.trim().toLowerCase();
  return sortedDrivers.value.filter((d) => {
    if (statusFilter.value === 'online' && !d.is_online) return false;
    if (statusFilter.value === 'offline' && d.is_online) return false;
    if (statusFilter.value === 'pending' && d.approved) return false;
    if (!q) return true;
    return [d.name, d.phone, d.email].some((v) => String(v || '').toLowerCase().includes(q));
  });
});
const isFiltering = computed(() => searchQuery.value.trim() !== '' || statusFilter.value !== 'all');

const fetchDrivers = async () => {
  loading.value = true;
  fetchError.value = false;
  try {
    const params = showRejected.value ? { rejected: 1 } : {};
    const res = await api.get('/admin/drivers/', { params });
    drivers.value = Array.isArray(res.data) ? res.data : (res.data?.results || []);
    driversTotal.value = typeof res.data?.total === 'number' ? res.data.total : drivers.value.length;
    serverStats.value = res.data?.stats || null;
  } catch {
    fetchError.value = true;
  } finally {
    loading.value = false;
  }
};

const formatDate = (iso) => {
  if (!iso) return '—';
  try {
    return new Intl.DateTimeFormat(currentLocale.value, { year: 'numeric', month: 'short', day: 'numeric' }).format(new Date(iso));
  } catch {
    return String(iso).slice(0, 10);
  }
};

// A2-25: 1 decimal via the shared Intl path (same as fmtMoney/formatDate).
// Returns '—' for a non-numeric value instead of throwing during render.
const formatRating = (v) => {
  const n = Number(v);
  if (!Number.isFinite(n)) return '—';
  try {
    return new Intl.NumberFormat(currentLocale.value, { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(n);
  } catch {
    return n.toFixed(1);
  }
};

// A2-22: dispatch treats a driver position as fresh for 300 s (DriverJobListView
// in accounts/views.py only shows GPS on offer cards inside that window), so the
// board uses the same window for its staleness badge. No poll: the badge +
// "last seen" are the required part; Refresh re-fetches.
const POSITION_FRESH_MS = 5 * 60 * 1000;
const positionAgeMs = (d) => {
  if (!d?.position_updated_at) return null;
  const ms = Date.now() - new Date(d.position_updated_at).getTime();
  return Number.isNaN(ms) ? null : ms;
};
const isPositionStale = (d) => {
  if (!d?.is_online) return false;
  const age = positionAgeMs(d);
  return age === null || age > POSITION_FRESH_MS;
};
const lastSeenText = (d) => {
  const age = positionAgeMs(d);
  if (age === null) return t('adminDrivers.lastSeenNever');
  if (age < 60 * 1000) return t('adminDrivers.lastSeenJustNow');
  if (age < 60 * 60 * 1000) return t('adminDrivers.lastSeenMins', { count: Math.floor(age / 60000) });
  if (age < 24 * 60 * 60 * 1000) return t('adminDrivers.lastSeenHours', { count: Math.floor(age / 3600000) });
  return formatDate(d.position_updated_at);
};

onMounted(fetchDrivers);
</script>
