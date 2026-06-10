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
      <p class="text-sm font-semibold text-slate-100">{{ t('adminDrivers.empty') }}</p>
      <p class="text-xs text-slate-400">{{ t('adminDrivers.emptyHint') }}</p>
    </div>

    <template v-else>
      <!-- Stats bar -->
      <div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div class="ui-panel p-4 text-center">
          <p class="text-2xl font-bold tabular-nums text-white">{{ drivers.length }}</p>
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
          <p class="text-2xl font-bold tabular-nums text-white">{{ totalDeliveries }}</p>
          <p class="ui-stat-label mt-0.5">{{ t('adminDrivers.totalDeliveries') }}</p>
        </div>
      </div>

      <!-- Desktop table (hidden on mobile) -->
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
              <th scope="col" class="px-4 py-3 text-end">{{ t('adminDrivers.colOwed') }}</th>
              <th scope="col" class="px-4 py-3 text-end">{{ t('adminDrivers.colSince') }}</th>
              <th scope="col" class="px-4 py-3 text-end" :aria-label="t('adminDrivers.colActions')"></th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-700/40">
            <tr
              v-for="(d, index) in sortedDrivers"
              :key="d.id"
              class="ui-reveal cursor-pointer hover:bg-slate-800/30 transition-colors"
              :class="{ 'bg-amber-500/5': !d.approved }"
              :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
              tabindex="0"
              @click="openDriver(d)"
              @keydown.enter.space="openDriver(d)"
            >
              <td class="px-4 py-3 text-slate-200 font-medium">
                <span class="truncate block">{{ d.name || t('adminDrivers.unnamed') }}</span>
                <span v-if="d.email" class="block text-[10px] text-slate-500 truncate">{{ d.email }}</span>
              </td>
              <td class="px-4 py-3 text-slate-400">
                <a :href="`tel:${d.phone}`" class="hover:text-sky-400">{{ d.phone }}</a>
              </td>
              <td class="px-4 py-3 text-center">
                <span
                  v-if="!d.approved"
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
                  v-if="d.is_online && d.driver_lat && d.driver_lng"
                  :href="`https://www.google.com/maps/search/?api=1&query=${d.driver_lat},${d.driver_lng}`"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="ms-1 text-[10px] text-sky-400 hover:text-sky-300"
                  :aria-label="t('adminDrivers.viewOnMap')"
                ><span aria-hidden="true">📍</span></a>
              </td>
              <td class="px-4 py-3 text-end tabular-nums text-slate-300">{{ d.total_jobs }}</td>
              <td class="px-4 py-3 text-end tabular-nums text-emerald-400">{{ d.completed_jobs }}</td>
              <td class="px-4 py-3 text-end">
                <span v-if="d.avg_rating" class="text-amber-300 tabular-nums" :aria-label="t('adminDrivers.ratingLabel', { value: d.avg_rating })"><span aria-hidden="true">★</span> {{ d.avg_rating }}</span>
                <span v-else class="text-slate-600">—</span>
              </td>
              <td class="px-4 py-3 text-end tabular-nums" :class="Number(d.owed) > 0 ? 'text-emerald-400 font-semibold' : 'text-slate-500'">
                {{ fmtMoney(d.owed) }}
              </td>
              <td class="px-4 py-3 text-end text-slate-500 text-xs tabular-nums">{{ formatDate(d.created_at) }}</td>
              <td class="px-4 py-3 text-end text-slate-600 rtl:scale-x-[-1]" aria-hidden="true">›</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Mobile card list (hidden on md+) -->
      <ul class="md:hidden space-y-2">
        <li
          v-for="(d, index) in sortedDrivers"
          :key="d.id"
          class="ui-admin-card ui-reveal ui-surface-lift cursor-pointer"
          :class="{ 'border-amber-500/30 bg-amber-500/5': !d.approved }"
          :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
          tabindex="0"
          @click="openDriver(d)"
          @keydown.enter.space="openDriver(d)"
        >
          <div class="flex items-start justify-between gap-2">
            <div class="min-w-0">
              <div class="flex items-center gap-1.5 flex-wrap">
                <span class="font-medium text-slate-200 truncate">{{ d.name || t('adminDrivers.unnamed') }}</span>
                <span
                  v-if="!d.approved"
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
            <aside v-if="selected" class="absolute end-0 top-0 h-full w-full max-w-md overflow-y-auto border-s border-slate-700 bg-slate-900 p-5 space-y-5" role="dialog" :aria-label="selected.name || t('adminDrivers.unnamed')" aria-modal="true" @keydown.esc="selected = null">
              <!-- Header -->
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <p class="ui-kicker">{{ t('adminDrivers.detailKicker') }}</p>
                  <h2 class="text-lg font-semibold text-white truncate">{{ selected.name || t('adminDrivers.unnamed') }}</h2>
                  <p class="text-xs text-slate-500 truncate">{{ selected.phone }}</p>
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

                <!-- Payout form -->
                <div v-if="Number(detail.owed) > 0" class="rounded-xl border border-slate-700/60 bg-slate-800/30 p-3 space-y-2.5">
                  <p class="text-sm font-semibold text-slate-200">{{ t('adminDrivers.recordPayout') }}</p>
                  <div class="flex gap-2">
                    <input v-model="payAmount" type="number" step="0.01" min="0.01" :max="detail.owed" class="ui-input flex-1 text-sm" :placeholder="t('adminDrivers.amount')" :aria-label="t('adminDrivers.amount')" />
                    <select v-model="payMethod" class="ui-input text-sm" :aria-label="t('adminDrivers.payMethod')">
                      <option value="cash">{{ t('adminDrivers.methodCash') }}</option>
                      <option value="transfer">{{ t('adminDrivers.methodTransfer') }}</option>
                    </select>
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
                  <p v-if="!detail.payouts.length" class="py-2 text-center text-xs text-slate-600 italic">{{ t('adminDrivers.noneYet') }}</p>
                  <ul v-else class="space-y-1.5">
                    <li v-for="p in detail.payouts" :key="p.id" class="flex items-center justify-between gap-2 rounded-lg bg-slate-800/30 px-3 py-2 text-xs">
                      <span class="text-slate-400">{{ p.method === 'cash' ? t('adminDrivers.methodCash') : t('adminDrivers.methodTransfer') }} · {{ formatDate(p.created_at) }}</span>
                      <span class="font-semibold tabular-nums text-slate-300">−{{ fmtMoney(p.amount) }}</span>
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
import api from '../lib/api';
import { useToastStore } from '../stores/toast';
import { newIdempotencyKey } from '../lib/idempotency';

const { t, currentLocale } = useI18n();
const toast = useToastStore();

const loading = ref(true);
const fetchError = ref(false);
const drivers = ref([]);

const fmtMoney = (v) => {
  try {
    return new Intl.NumberFormat(currentLocale.value, { style: 'currency', currency: 'MAD', maximumFractionDigits: 2 }).format(parseFloat(v || 0));
  } catch {
    return `${parseFloat(v || 0).toFixed(2)}`;
  }
};

// ── Earnings detail slide-over + payout ─────────────────────────────────────
const selected = ref(null);
const detail = ref(null);
const loadingDetail = ref(false);
const payAmount = ref('');
const payMethod = ref('cash');
const paying = ref(false);
const payError = ref('');
const vetting = ref(false);
const vettingCar = ref(false);

const openDriver = async (d) => {
  selected.value = d;
  detail.value = null;
  payError.value = '';
  loadingDetail.value = true;
  try {
    const res = await api.get(`/admin/drivers/${d.id}/earnings/`);
    detail.value = res.data;
    payAmount.value = res.data.owed;
    payMethod.value = 'cash';
  } catch {
    payError.value = t('adminDrivers.fetchError');
  } finally {
    loadingDetail.value = false;
  }
};

const submitPayout = async () => {
  payError.value = '';
  const amount = parseFloat(payAmount.value);
  if (!amount || amount <= 0) { payError.value = t('adminDrivers.payoutInvalid'); return; }
  paying.value = true;
  try {
    const res = await api.post(`/admin/drivers/${selected.value.id}/payout/`, {
      amount: amount.toFixed(2),
      method: payMethod.value,
      idempotency_key: newIdempotencyKey(),
    });
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
  vetting.value = true;
  try {
    await api.post(`/admin/drivers/${selected.value.id}/${approve ? 'approve' : 'reject'}/`, {});
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
  vettingCar.value = true;
  try {
    await api.post(`/admin/drivers/${selected.value.id}/${approve ? 'car-approve' : 'car-reject'}/`, {});
    toast.show(approve ? t('adminConsole.carApproved') : t('adminConsole.carReject'), 'success');
    selected.value.driver_car_approved = approve;
    const row = drivers.value.find((d) => d.id === selected.value.id);
    if (row) row.driver_car_approved = approve;
  } catch (err) {
    toast.show(err?.response?.data?.detail || t('adminDrivers.actionFailed'), 'error');
  } finally {
    vettingCar.value = false;
  }
};

const onlineCount = computed(() => drivers.value.filter(d => d.is_online).length);
const pendingCount = computed(() => drivers.value.filter(d => !d.approved).length);
// Surface pending applications first so admins review them promptly.
const sortedDrivers = computed(() =>
  [...drivers.value].sort((a, b) => (a.approved === b.approved ? 0 : a.approved ? 1 : -1))
);
const totalDeliveries = computed(() => drivers.value.reduce((sum, d) => sum + d.completed_jobs, 0));

const fetchDrivers = async () => {
  loading.value = true;
  fetchError.value = false;
  try {
    const res = await api.get('/admin/drivers/');
    drivers.value = res.data;
  } catch {
    fetchError.value = true;
  } finally {
    loading.value = false;
  }
};

const formatDate = (iso) => {
  if (!iso) return '—';
  return new Intl.DateTimeFormat(currentLocale.value, { year: 'numeric', month: 'short', day: 'numeric' }).format(new Date(iso));
};

onMounted(fetchDrivers);
</script>
