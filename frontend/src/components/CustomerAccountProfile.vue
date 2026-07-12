<template>

  <!-- Driver mode entry -->
  <RouterLink
    :to="{ name: 'driver' }"
    class="ui-panel ui-surface-lift ui-reveal flex items-center justify-between gap-3 p-4 hover:border-emerald-500/40"
    style="--ui-delay: 0ms"
  >
    <div class="flex items-center gap-3">
      <div class="flex h-9 w-9 items-center justify-center rounded-xl border border-emerald-500/30 bg-emerald-500/10">
        <AppIcon name="truck" class="h-4 w-4 text-emerald-300" />
      </div>
      <div>
        <p class="text-sm font-semibold text-slate-100">{{ t('customerAccount.driverMode') }}</p>
        <p class="text-xs text-slate-500">
          {{ customer?.is_driver ? t('customerAccount.driverModeOpen') : t('customerAccount.driverModeJoin') }}
        </p>
      </div>
    </div>
    <AppIcon name="chevronRight" class="h-4 w-4 text-slate-600 rtl:scale-x-[-1]" aria-hidden="true" />
  </RouterLink>

  <!-- Personal info panel (grouped rows) -->
  <div class="ui-panel ui-reveal divide-y divide-slate-800/70 overflow-hidden p-0" style="--ui-delay: 40ms">
    <div class="px-4 py-3">
      <p class="ui-kicker">{{ t('customerAccount.profilePersonalInfo') }}</p>
    </div>

    <!-- Name -->
    <div class="px-4 py-3 space-y-1.5">
      <p class="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{{ t('common.name') }}</p>
      <div class="flex items-center gap-2">
        <input
          v-model.trim="nameDraft"
          type="text"
          maxlength="80"
          autocomplete="name"
          class="ui-input flex-1 py-1.5 text-sm"
          :placeholder="t('customerAccount.namePlaceholder')"
          :disabled="savingName"
        />
        <button
          v-if="editableName !== (customer?.name || '')"
          class="ui-btn-primary inline-flex shrink-0 items-center gap-1.5 px-3 py-1.5 text-xs"
          :disabled="savingName"
          :aria-busy="savingName"
          @click="emit('save-name')"
        >
          <svg v-if="savingName" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
          {{ savingName ? t('customerAccount.saving') : t('customerAccount.saveName') }}
        </button>
      </div>
    </div>

    <!-- Phone -->
    <div class="px-4 py-3 space-y-1.5">
      <p class="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{{ t('common.phone') }}</p>
      <div class="flex flex-wrap items-center gap-2">
        <span v-if="customer?.phone" class="text-sm text-slate-200">{{ customer.phone }}</span>
        <button
          v-else
          class="inline-flex items-center gap-1 rounded-lg border border-amber-500/40 bg-amber-500/8 px-2.5 py-1 text-[11px] font-medium text-amber-300 transition hover:border-amber-500/70"
          @click="emit('add-phone')"
        >
          <AppIcon name="plus" class="h-3 w-3" />
          {{ t('customerAccount.addPhone') }}
        </button>
        <span
          v-if="customer?.phone_verified"
          class="inline-flex items-center gap-0.5 rounded-full bg-emerald-500/12 px-1.5 py-0.5 text-[10px] font-medium text-emerald-400"
        >
          <AppIcon name="check" class="h-2.5 w-2.5" />{{ t('customerAccount.verifiedPhone') }}
        </span>
      </div>
    </div>

    <!-- Email -->
    <div class="px-4 py-3 space-y-1.5">
      <p class="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{{ t('common.email') }}</p>
      <div>
        <div class="flex flex-wrap items-center gap-2">
          <template v-if="!showEmailInput">
            <span v-if="customer?.email" class="text-sm text-slate-200">{{ customer.email }}</span>
            <button
              class="inline-flex items-center gap-1 text-[11px] transition-colors"
              :class="customer?.email ? 'text-slate-500 hover:text-slate-300' : 'text-sky-400 hover:text-sky-300'"
              @click="emit('open-email-input')"
            >
              <AppIcon name="plus" class="h-3 w-3" />
              {{ customer?.email ? t('customerAccount.editEmail') : t('customerAccount.addEmail') }}
            </button>
            <span
              v-if="customer?.email_verified"
              class="inline-flex items-center gap-0.5 rounded-full bg-sky-500/12 px-1.5 py-0.5 text-[10px] font-medium text-sky-400"
            >
              <AppIcon name="check" class="h-2.5 w-2.5" />{{ t('customerAccount.verifiedEmail') }}
            </span>
          </template>
          <template v-else>
            <input
              ref="emailInputRef"
              v-model.trim="emailDraft"
              type="email"
              autocomplete="email"
              maxlength="254"
              spellcheck="false"
              class="ui-input min-w-0 flex-1 py-1.5 text-xs"
              :placeholder="t('customerAccount.emailPlaceholder')"
              :aria-label="t('customerAccount.emailPlaceholder')"
              :aria-invalid="emailError ? 'true' : undefined"
              aria-describedby="customer-account-email-error"
              :disabled="savingEmail"
              @keydown.enter.prevent="emit('save-email')"
              @keydown.escape.prevent="emit('cancel-email-input')"
            />
            <button class="ui-btn-primary inline-flex shrink-0 items-center gap-1.5 px-2.5 py-1.5 text-xs" :disabled="savingEmail || !editableEmail" :aria-busy="savingEmail" @click="emit('save-email')">
              <svg v-if="savingEmail" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
              {{ savingEmail ? t('customerAccount.saving') : t('common.save') }}
            </button>
            <button class="text-xs text-slate-500 transition hover:text-slate-300" @click="emit('cancel-email-input')">{{ t('common.cancel') }}</button>
          </template>
        </div>
        <p v-if="emailError" id="customer-account-email-error" role="alert" class="mt-1 text-xs text-red-300">{{ emailError }}</p>
      </div>
    </div>

    <!-- Birthday -->
    <div class="px-4 py-3 space-y-1.5">
      <p class="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{{ t('customerAccount.birthdayLabel') }}</p>
      <div class="flex items-center gap-2">
        <input
          v-model="birthdayDraft"
          type="date"
          max="2099-12-31"
          class="ui-input py-1.5 text-sm"
          :aria-label="t('customerAccount.birthdayLabel')"
          :disabled="savingBirthday"
        />
        <button
          v-if="editableBirthday !== (customer?.birthday || '')"
          class="ui-btn-primary inline-flex shrink-0 items-center gap-1.5 px-3 py-1.5 text-xs"
          :disabled="savingBirthday"
          :aria-busy="savingBirthday"
          @click="emit('save-birthday')"
        >
          <svg v-if="savingBirthday" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
          {{ savingBirthday ? t('customerAccount.saving') : t('common.save') }}
        </button>
      </div>
      <p class="text-[11px] leading-relaxed text-slate-500">{{ t('customerAccount.birthdayHint') }}</p>
    </div>
  </div>

  <!-- Saved addresses -->
  <div class="ui-panel ui-reveal overflow-hidden p-0" style="--ui-delay: 80ms">
    <div class="flex items-center justify-between gap-2 border-b border-slate-800/70 px-4 py-3">
      <div>
        <p class="ui-kicker">{{ t('customerAccount.savedAddressesTitle') }}</p>
        <p class="mt-0.5 text-[10px] text-slate-500">{{ t('customerAccount.savedAddressesNote') }}</p>
      </div>
      <div class="flex items-center gap-2">
        <span class="text-[10px] text-slate-500">{{ savedAddresses.length }}/10</span>
        <button
          v-if="!addingAddress && savedAddresses.length < 10"
          class="ui-press ui-touch-target inline-flex items-center gap-1 rounded-lg border border-slate-700/60 bg-slate-800/50 px-2.5 py-1 text-[11px] font-medium text-slate-300 transition-colors hover:border-slate-600 hover:text-white"
          @click="emit('start-adding-address')"
        >
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" class="h-3 w-3 shrink-0" aria-hidden="true"><path d="M8 3v10M3 8h10"/></svg>
          {{ t('customerAccount.savedAddressAdd') }}
        </button>
      </div>
    </div>
    <div class="p-4 space-y-2">
      <!-- Add address inline form -->
      <Transition name="ui-fade">
        <form v-if="addingAddress" class="space-y-2 rounded-xl border border-sky-500/25 bg-sky-500/5 p-3" @submit.prevent="emit('add-address')">
          <label class="block text-[11px] font-medium text-slate-300">
            {{ t('customerAccount.savedAddressLabelField') }}
            <input
              :value="addrForm.label"
              type="text"
              maxlength="60"
              class="ui-input mt-1 w-full text-xs"
              :placeholder="t('customerAccount.savedAddressLabelPlaceholder')"
              @input="emit('addr-label-input', $event.target.value)"
            />
          </label>
          <label class="block text-[11px] font-medium text-slate-300">
            {{ t('customerAccount.savedAddressField') }}
            <textarea
              :value="addrForm.address"
              rows="2"
              maxlength="300"
              class="ui-textarea mt-1 w-full resize-none text-xs"
              :placeholder="t('customerAccount.savedAddressAddressPlaceholder')"
              required
              @input="emit('addr-address-input', $event.target.value)"
            />
          </label>
          <p v-if="addrError" class="text-[11px] text-red-300" role="alert">{{ addrError }}</p>
          <div class="flex gap-2">
            <button
              type="submit"
              class="ui-btn-primary ui-press inline-flex items-center gap-1.5 px-4 py-1.5 text-[11px] font-semibold disabled:opacity-50"
              :disabled="savingAddress"
            >
              <svg v-if="savingAddress" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3 w-3 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
              {{ savingAddress ? t('common.loading') : t('customerAccount.savedAddressSave') }}
            </button>
            <button
              type="button"
              class="rounded-lg border border-slate-700/60 px-4 py-1.5 text-[11px] font-medium text-slate-400 transition hover:border-slate-600 hover:text-slate-200"
              :disabled="savingAddress"
              @click="emit('cancel-adding-address')"
            >{{ t('common.cancel') }}</button>
          </div>
        </form>
      </Transition>
      <div v-if="loadingAddresses" class="space-y-1.5">
        <div v-for="i in 2" :key="i" class="h-12 animate-pulse rounded-xl border border-slate-700/40 bg-slate-800/30" />
      </div>
      <div v-else-if="!savedAddresses.length && !addingAddress" class="rounded-xl border border-dashed border-slate-700/50 px-4 py-4 text-center text-xs text-slate-500">
        {{ t('customerAccount.savedAddressesEmpty') }}
      </div>
      <ul class="space-y-1.5">
        <li
          v-for="addr in savedAddresses"
          :key="addr.id"
          class="rounded-xl border bg-slate-900/40 px-3 py-2.5 text-xs transition-colors"
          :class="deletingAddressId === addr.id ? 'border-red-500/30' : 'border-slate-700/60'"
        >
          <div class="flex items-start gap-3">
            <AppIcon name="location" class="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-500" />
            <div class="min-w-0 flex-1 space-y-0.5">
              <p v-if="addr.label" class="font-semibold text-slate-200">{{ addr.label }}</p>
              <p class="text-slate-400" :title="addr.address">{{ addr.address }}</p>
            </div>
            <div class="flex shrink-0 gap-0.5">
              <!-- Edit toggle -->
              <button
                class="ui-touch-target ui-press flex items-center justify-center transition"
                :class="editingAddressId === addr.id ? 'text-sky-400' : 'text-slate-500 hover:text-sky-400'"
                :aria-label="t('common.edit')"
                @click="emit('toggle-edit-address', addr)"
              >
                <AppIcon name="pencil" class="h-3.5 w-3.5" aria-hidden="true" />
              </button>
              <!-- Delete toggle -->
              <button
                class="ui-touch-target ui-press flex items-center justify-center transition"
                :class="deletingAddressId === addr.id ? 'text-red-400' : 'text-slate-500 hover:text-red-400'"
                :aria-label="t('common.remove')"
                @click="emit('start-delete-address', addr.id)"
              >
                <AppIcon name="close" class="h-3.5 w-3.5" aria-hidden="true" />
              </button>
            </div>
          </div>
          <!-- Inline edit form -->
          <Transition name="ui-fade">
            <form v-if="editingAddressId === addr.id" class="mt-2 space-y-2 border-t border-sky-500/15 pt-2" @submit.prevent="emit('save-edit-address')">
              <label class="block text-[11px] font-medium text-slate-300">
                {{ t('customerAccount.savedAddressLabelField') }}
                <input
                  :value="editForm.label"
                  type="text"
                  maxlength="60"
                  class="ui-input mt-1 w-full text-xs"
                  :placeholder="t('customerAccount.savedAddressLabelPlaceholder')"
                  @input="emit('edit-label-input', $event.target.value)"
                />
              </label>
              <label class="block text-[11px] font-medium text-slate-300">
                {{ t('customerAccount.savedAddressField') }}
                <textarea
                  :value="editForm.address"
                  rows="2"
                  maxlength="300"
                  class="ui-textarea mt-1 w-full resize-none text-xs"
                  required
                  @input="emit('edit-address-input', $event.target.value)"
                />
              </label>
              <p v-if="editError" class="text-[11px] text-red-300" role="alert">{{ editError }}</p>
              <div class="flex gap-2">
                <button type="submit" class="ui-btn-primary ui-press inline-flex items-center gap-1.5 px-4 py-1.5 text-[11px] font-semibold disabled:opacity-50" :disabled="savingEdit">
                  <svg v-if="savingEdit" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3 w-3 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
                  {{ savingEdit ? t('common.loading') : t('common.save') }}
                </button>
                <button type="button" class="rounded-lg border border-slate-700/60 px-4 py-1.5 text-[11px] font-medium text-slate-400 transition hover:border-slate-600 hover:text-slate-200" :disabled="savingEdit" @click="emit('cancel-edit-address')">{{ t('common.cancel') }}</button>
              </div>
            </form>
          </Transition>
          <!-- Inline delete confirmation -->
          <Transition name="ui-fade">
            <div v-if="deletingAddressId === addr.id" class="mt-2 border-t border-red-500/15 pt-2 space-y-2">
              <p v-if="addrDeleteError" class="text-[11px] text-red-300" role="alert">{{ addrDeleteError }}</p>
              <div class="flex items-center gap-3">
                <span class="flex-1 text-red-300/80">{{ t('customerAccount.savedAddressConfirmDelete') }}</span>
                <button class="text-slate-400 transition hover:text-slate-200" @click.stop="emit('cancel-delete-address')">{{ t('common.back') }}</button>
                <button class="font-semibold text-red-300 transition hover:text-red-200" @click.stop="emit('delete-address', addr.id)">{{ t('common.remove') }}</button>
              </div>
            </div>
          </Transition>
        </li>
      </ul>
    </div>
  </div>

  <!-- Preferences panel -->
  <div class="ui-panel ui-reveal divide-y divide-slate-800/70 overflow-hidden p-0" style="--ui-delay: 120ms">
    <div class="px-4 py-3">
      <p class="ui-kicker">{{ t('customerAccount.preferencesTitle') }}</p>
    </div>

    <!-- Language -->
    <div class="px-4 py-3 space-y-2">
      <p class="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{{ t('customerAccount.localeTitle') }}</p>
      <div v-if="!localeConfigured" class="flex flex-wrap gap-2">
        <button
          v-for="lang in [{ code: 'en', label: 'English' }, { code: 'fr', label: 'Français' }, { code: 'ar', label: 'العربية' }]"
          :key="lang.code"
          :aria-pressed="selectedLocale === lang.code"
          class="rounded-full border px-3 py-1 text-xs transition-colors"
          :class="selectedLocale === lang.code
            ? 'border-[var(--color-secondary)] bg-[var(--color-secondary)]/15 text-[var(--color-secondary)]'
            : 'border-slate-700 text-slate-400 hover:border-slate-500 hover:text-slate-200'"
          :disabled="savingLocale"
          @click="emit('set-locale', lang.code)"
        >{{ lang.label }}</button>
      </div>
      <div v-else class="flex items-center justify-between gap-2">
        <span class="text-sm text-slate-300">{{ localeLabelCurrent }}</span>
        <button class="text-[11px] text-slate-500 transition hover:text-slate-300" @click="emit('edit-locale')">{{ t('common.change') }}</button>
      </div>
    </div>

    <!-- Display currency -->
    <div class="px-4 py-3 space-y-2">
      <p class="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{{ t('customerAccount.displayCurrency') }}</p>
      <div class="flex flex-wrap gap-2">
        <button
          v-for="r in currencyOptions"
          :key="r.code"
          :aria-pressed="selectedCurrency === r.code"
          class="rounded-full border px-3 py-1 text-xs transition-colors"
          :class="selectedCurrency === r.code
            ? 'border-[var(--color-secondary)] bg-[var(--color-secondary)]/15 text-[var(--color-secondary)]'
            : 'border-slate-700 text-slate-400 hover:border-slate-500 hover:text-slate-200'"
          @click="emit('set-currency', r.code)"
        >{{ r.code }} <span class="opacity-60">{{ r.symbol }}</span></button>
      </div>
    </div>

    <!-- Notifications -->
    <div id="notifications-section" class="px-4 py-3 space-y-2.5">
      <p class="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{{ t('customerAccount.notificationsTitle') }}</p>
      <label class="flex items-center justify-between gap-3">
        <span class="text-sm text-slate-300">{{ t('customerAccount.notifyOrderUpdates') }}</span>
        <input
          type="checkbox"
          class="h-4 w-4 rounded border-slate-600 bg-slate-900 text-[var(--color-secondary)] focus:ring-[var(--color-secondary)]/40"
          :checked="!!customer?.notify_order_updates"
          :disabled="savingPrefs"
          @change="emit('save-pref', 'notify_order_updates', $event.target.checked)"
        />
      </label>
      <label class="flex items-center justify-between gap-3">
        <span class="text-sm text-slate-300">{{ t('customerAccount.notifyReviewPrompts') }}</span>
        <input
          type="checkbox"
          class="h-4 w-4 rounded border-slate-600 bg-slate-900 text-[var(--color-secondary)] focus:ring-[var(--color-secondary)]/40"
          :checked="!!customer?.notify_review_prompts"
          :disabled="savingPrefs"
          @change="emit('save-pref', 'notify_review_prompts', $event.target.checked)"
        />
      </label>
      <label class="flex items-center justify-between gap-3">
        <span class="text-sm text-slate-300">{{ t('customerAccount.notifyPromotions') }}</span>
        <input
          type="checkbox"
          class="h-4 w-4 rounded border-slate-600 bg-slate-900 text-[var(--color-secondary)] focus:ring-[var(--color-secondary)]/40"
          :checked="!!customer?.notify_promotions"
          :disabled="savingPrefs"
          @change="emit('save-pref', 'notify_promotions', $event.target.checked)"
        />
      </label>
      <!-- Browser push notifications opt-in -->
      <div v-if="pushSupported && pushEnabled" class="flex items-start justify-between gap-3 pt-0.5">
        <div class="min-w-0 flex-1">
          <p class="text-sm text-slate-300">{{ t('customerAccount.notifyBrowserPush') }}</p>
          <p v-if="!pushSubscribed" class="mt-0.5 text-[10px] text-slate-500">{{ t('customerAccount.notifyBrowserPushHint') }}</p>
        </div>
        <button
          v-if="!pushSubscribed"
          class="shrink-0 rounded-full border border-[var(--color-secondary)]/50 bg-[var(--color-secondary)]/10 px-3 py-1 text-[11px] font-semibold text-[var(--color-secondary)] transition hover:bg-[var(--color-secondary)]/20 disabled:opacity-50 ui-press"
          :disabled="pushLoading"
          @click="emit('push-subscribe')"
        >{{ t('customerAccount.notifyEnable') }}</button>
        <span v-else class="shrink-0 text-[11px] font-semibold text-emerald-400">{{ t('customerAccount.notifyOn') }}</span>
      </div>
    </div>
  </div>

  <!-- Per-service notification preferences -->
  <div class="ui-panel ui-reveal overflow-hidden p-0" style="--ui-delay: 80ms">
    <button
      type="button"
      class="flex w-full items-center justify-between gap-3 border-b border-slate-800/70 px-4 py-3 text-start"
      :aria-expanded="serviceProfilesOpen"
      @click="emit('toggle-service-profiles')"
    >
      <p class="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{{ t('customerAccount.perServiceNotifs') }}</p>
      <svg
        viewBox="0 0 16 16"
        fill="none"
        stroke="currentColor"
        stroke-width="1.75"
        stroke-linecap="round"
        stroke-linejoin="round"
        aria-hidden="true"
        class="h-3.5 w-3.5 shrink-0 text-slate-500 transition-transform"
        :class="serviceProfilesOpen ? 'rotate-180' : ''"
      ><path d="M4 6l4 4 4-4"/></svg>
    </button>
    <Transition name="ui-expand">
      <div v-if="serviceProfilesOpen" class="p-4 space-y-4">
        <p class="text-[11px] leading-relaxed text-slate-500">{{ t('customerAccount.perServiceNotifsHint') }}</p>

        <!-- Loading -->
        <div v-if="loadingServiceProfiles" class="space-y-2">
          <div v-for="i in 3" :key="i" class="h-10 animate-pulse rounded-xl bg-slate-800/50" />
        </div>

        <!-- Error -->
        <p v-else-if="serviceProfilesError" class="text-xs text-red-400" role="alert">{{ t('customerAccount.perServiceLoadError') }}</p>

        <!-- Per-vertical toggles -->
        <div v-else class="space-y-4">
          <div
            v-for="vertical in nonDriverVerticals"
            :key="vertical"
            class="rounded-xl border border-slate-700/60 bg-slate-900/40 p-3 space-y-2"
          >
            <p class="text-xs font-semibold text-slate-300">{{ verticalSvcLabels[vertical] || vertical }}</p>
            <label class="flex items-center justify-between gap-3">
              <span class="text-xs text-slate-400">{{ t('customerAccount.notifOrderUpdates') }}</span>
              <input
                type="checkbox"
                class="h-4 w-4 rounded border-slate-600 bg-slate-900 text-[var(--color-secondary)] focus:ring-[var(--color-secondary)]/40"
                :checked="serviceProfiles[vertical]?.notify_updates !== false"
                :disabled="savingServiceProfile === vertical"
                @change="emit('save-service-pref', vertical, 'notify_updates', $event.target.checked)"
              />
            </label>
            <label class="flex items-center justify-between gap-3">
              <span class="text-xs text-slate-400">{{ t('customerAccount.notifPromotions') }}</span>
              <input
                type="checkbox"
                class="h-4 w-4 rounded border-slate-600 bg-slate-900 text-[var(--color-secondary)] focus:ring-[var(--color-secondary)]/40"
                :checked="serviceProfiles[vertical]?.notify_promotions !== false"
                :disabled="savingServiceProfile === vertical"
                @change="emit('save-service-pref', vertical, 'notify_promotions', $event.target.checked)"
              />
            </label>
          </div>
        </div>
      </div>
    </Transition>
  </div>

  <!-- Privacy & data section -->
  <div class="ui-panel ui-reveal overflow-hidden p-0" style="--ui-delay: 120ms">
    <div class="border-b border-slate-800/70 px-4 py-3">
      <p class="ui-kicker">{{ t('customerAccount.privacyTitle') }}</p>
    </div>

    <!-- Export row -->
    <div class="px-4 py-3 space-y-1.5">
      <div class="flex items-start justify-between gap-3">
        <div class="min-w-0 flex-1">
          <p class="text-sm font-semibold text-slate-200">{{ t('customerAccount.privacyExportTitle') }}</p>
          <p class="mt-0.5 text-[11px] leading-relaxed text-slate-500">{{ t('customerAccount.privacyExportHint') }}</p>
        </div>
        <button
          class="shrink-0 inline-flex items-center gap-1.5 rounded-xl border border-slate-700/60 bg-slate-800/50 px-3 py-1.5 text-[11px] font-semibold text-slate-300 transition hover:border-slate-600 hover:text-white disabled:opacity-50 ui-press"
          :disabled="exportingData"
          @click="emit('download-my-data')"
        >
          <svg v-if="exportingData" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
          <svg v-else aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" class="h-3.5 w-3.5 shrink-0"><path d="M8 2v8M5 7l3 3 3-3M3 12h10"/></svg>
          {{ t('customerAccount.privacyExportBtn') }}
        </button>
      </div>
    </div>

    <!-- Delete row -->
    <div class="border-t border-slate-800/70 px-4 py-3 space-y-2.5">
      <div class="flex items-start justify-between gap-3">
        <div class="min-w-0 flex-1">
          <p class="text-sm font-semibold text-red-300">{{ t('customerAccount.privacyDeleteTitle') }}</p>
          <p class="mt-0.5 text-[11px] leading-relaxed text-slate-500">{{ t('customerAccount.privacyDeleteHint') }}</p>
        </div>
        <button
          v-if="!erasureConfirmVisible"
          class="shrink-0 inline-flex items-center gap-1.5 rounded-xl border border-red-500/40 bg-red-500/8 px-3 py-1.5 text-[11px] font-semibold text-red-300 transition hover:border-red-500/60 hover:bg-red-500/15 ui-press"
          @click="emit('start-erasure')"
        >
          {{ t('customerAccount.privacyDeleteBtn') }}
        </button>
      </div>

      <!-- Guard-blocked error -->
      <p
        v-if="erasureBlockedMsg"
        class="text-[11px] leading-relaxed text-amber-400"
        role="alert"
      >{{ erasureBlockedMsg }}</p>

      <!-- Inline confirm -->
      <Transition name="ui-fade">
        <div
          v-if="erasureConfirmVisible"
          class="rounded-xl border border-red-500/30 bg-red-500/6 p-3 space-y-2.5"
        >
          <p class="text-[11px] leading-relaxed text-red-200">{{ t('customerAccount.privacyDeleteConfirmText') }}</p>
          <div class="flex gap-2">
            <button
              class="inline-flex items-center gap-1.5 rounded-lg border border-red-500/50 bg-red-500/12 px-3 py-1.5 text-[11px] font-semibold text-red-300 transition hover:bg-red-500/20 disabled:opacity-50 ui-press"
              :disabled="requestingErasure"
              @click="emit('request-erasure')"
            >
              <svg v-if="requestingErasure" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
              {{ t('customerAccount.privacyDeleteConfirmBtn') }}
            </button>
            <button
              class="rounded-lg border border-slate-700/60 px-3 py-1.5 text-[11px] font-medium text-slate-400 transition hover:border-slate-600 hover:text-slate-200"
              :disabled="requestingErasure"
              @click="emit('cancel-erasure')"
            >{{ t('common.cancel') }}</button>
          </div>
        </div>
      </Transition>
    </div>
  </div>

</template>

<script setup>
// Profile tab of CustomerAccount.vue, extracted as a standalone child
// component (RISK FE-2). All fetch/state/API-mutation ownership stays in the
// parent (CustomerAccount.vue) — every field shown here (customer profile,
// saved addresses, locale/currency/notification prefs, per-service prefs,
// privacy export/erasure) is also reset/read by shared parent-level lifecycle
// code (auth watch, onAuthenticated, onPhoneAdded, logout), so none of it can
// safely move down without duplicating that reset logic. This component is
// purely presentational: it renders whatever data it's given and asks the
// parent to apply mutations via emits. The only local state kept here is the
// email input's autofocus-on-open behavior, which is pure DOM/UI concern for
// an element that now lives entirely inside this component.
import { computed, nextTick, ref, watch } from 'vue';
import { RouterLink } from 'vue-router';
import AppIcon from './AppIcon.vue';
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();

const props = defineProps({
  /** The signed-in customer record (name, phone, email, verification flags, prefs…). */
  customer: { type: Object, default: () => ({}) },

  /** Name field draft + in-flight save state. */
  editableName: { type: String, default: '' },
  savingName: { type: Boolean, default: false },

  /** Email edit-toggle + draft + in-flight/validation state. */
  showEmailInput: { type: Boolean, default: false },
  editableEmail: { type: String, default: '' },
  savingEmail: { type: Boolean, default: false },
  emailError: { type: String, default: '' },

  /** Birthday field draft + in-flight save state. */
  editableBirthday: { type: String, default: '' },
  savingBirthday: { type: Boolean, default: false },

  /** Saved addresses list + add/edit/delete UI state, all owned by the parent. */
  savedAddresses: { type: Array, default: () => [] },
  loadingAddresses: { type: Boolean, default: false },
  addingAddress: { type: Boolean, default: false },
  addrForm: { type: Object, default: () => ({ label: '', address: '' }) },
  addrError: { type: String, default: '' },
  savingAddress: { type: Boolean, default: false },
  editingAddressId: { type: [Number, String], default: null },
  editForm: { type: Object, default: () => ({ label: '', address: '' }) },
  editError: { type: String, default: '' },
  savingEdit: { type: Boolean, default: false },
  deletingAddressId: { type: [Number, String], default: null },
  addrDeleteError: { type: String, default: '' },

  /** Locale preference state. */
  localeConfigured: { type: Boolean, default: false },
  selectedLocale: { type: String, default: 'en' },
  savingLocale: { type: Boolean, default: false },
  localeLabelCurrent: { type: String, default: '' },

  /** Display currency options (currencyStore.available / .selected). */
  currencyOptions: { type: Array, default: () => [] },
  selectedCurrency: { type: String, default: '' },

  /** Notification checkbox in-flight state. */
  savingPrefs: { type: Boolean, default: false },

  /** Browser push opt-in (useCustomerPush composable, owned by the parent). */
  pushSupported: { type: Boolean, default: false },
  pushEnabled: { type: Boolean, default: false },
  pushSubscribed: { type: Boolean, default: false },
  pushLoading: { type: Boolean, default: false },

  /** Per-service (per-vertical) notification preferences. */
  serviceProfilesOpen: { type: Boolean, default: false },
  serviceProfiles: { type: Object, default: () => ({}) },
  loadingServiceProfiles: { type: Boolean, default: false },
  serviceProfilesError: { type: Boolean, default: false },
  savingServiceProfile: { type: String, default: '' },
  enabledVerticals: { type: Array, default: () => [] },
  verticalSvcLabels: { type: Object, default: () => ({}) },

  /** Privacy: data export + right-to-erasure state. */
  exportingData: { type: Boolean, default: false },
  requestingErasure: { type: Boolean, default: false },
  erasureConfirmVisible: { type: Boolean, default: false },
  erasureBlockedMsg: { type: String, default: '' },
});

const emit = defineEmits([
  'update-editable-name',
  'save-name',
  'update-editable-email',
  'open-email-input',
  'save-email',
  'cancel-email-input',
  'update-editable-birthday',
  'save-birthday',
  'add-phone',
  'start-adding-address',
  'cancel-adding-address',
  'add-address',
  'addr-label-input',
  'addr-address-input',
  'toggle-edit-address',
  'save-edit-address',
  'cancel-edit-address',
  'edit-label-input',
  'edit-address-input',
  'start-delete-address',
  'cancel-delete-address',
  'delete-address',
  'set-locale',
  'edit-locale',
  'set-currency',
  'save-pref',
  'push-subscribe',
  'toggle-service-profiles',
  'save-service-pref',
  'download-my-data',
  'start-erasure',
  'request-erasure',
  'cancel-erasure',
]);

// Writable local drafts backed by the parent's refs — keeps the exact same
// v-model[.trim] input behavior the inline template had before extraction.
const nameDraft = computed({
  get: () => props.editableName,
  set: (v) => emit('update-editable-name', v),
});
const emailDraft = computed({
  get: () => props.editableEmail,
  set: (v) => emit('update-editable-email', v),
});
const birthdayDraft = computed({
  get: () => props.editableBirthday,
  set: (v) => emit('update-editable-birthday', v),
});

// customerStore.enabledVerticals.filter(v => v !== 'driver') — same derivation,
// just recomputed from the prop instead of a store getter.
const nonDriverVerticals = computed(() => props.enabledVerticals.filter((v) => v !== 'driver'));

// Auto-focus the email input when it appears — mirrors the previous
// nextTick(() => emailInputRef.value?.focus()) in the parent's openEmailInput().
const emailInputRef = ref(null);
watch(
  () => props.showEmailInput,
  (shown) => {
    if (shown) nextTick(() => emailInputRef.value?.focus());
  },
);
</script>
