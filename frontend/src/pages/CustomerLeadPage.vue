<template>
  <div class="ui-safe-bottom pb-24 sm:pb-8">

    <!-- ══ Platform demo banner ══ -->
    <section v-if="showPlatformDemo" class="ui-hero-ribbon ui-reveal mx-3 mt-3 mb-3 p-4 text-center">
      <p class="ui-kicker">{{ t("common.demo") }}</p>
      <h2 class="ui-display text-2xl font-semibold text-white sm:text-3xl">{{ t("home.heroTitle") }}</h2>
      <p class="mt-2 text-sm text-slate-300">{{ t("home.heroSubtitle") }}</p>
      <div class="mt-4 flex flex-wrap justify-center gap-2">
        <a :href="demoMenuUrl" class="ui-btn-primary inline-flex items-center gap-2 px-4 py-2 text-sm" target="_blank" rel="noopener noreferrer">
          <AppIcon name="menu" class="h-4 w-4" />
          <span>{{ t("home.viewLiveDemo") }}</span>
        </a>
      </div>
    </section>

    <!-- ══ Hero panel ══ -->
    <section
      data-theme-dark
      class="relative overflow-hidden"
      style="height: calc(100svh - 9.5rem); min-height: 460px; max-height: 840px"
    >
      <!-- Background image / fallback -->
      <div class="absolute inset-0 bg-slate-950">
        <img
          v-if="heroImage"
          :src="heroImage"
          :alt="tenantName"
          class="h-full w-full object-cover"
          loading="eager"
          fetchpriority="high"
          decoding="async"
          @error="$event.target.style.display='none'"
        />
      </div>

      <!-- Dark gradient (bottom heavy so text is always readable) -->
      <div class="pointer-events-none absolute inset-0 bg-gradient-to-t from-black/97 via-black/50 to-black/18" />
      <!-- Subtle amber warmth at bottom-left -->
      <div class="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_20%_100%,rgba(245,158,11,0.09),transparent_42%)]" />
      <!-- Top vignette for readability near header -->
      <div class="pointer-events-none absolute inset-x-0 top-0 h-20 bg-gradient-to-b from-black/35 to-transparent" />

      <!-- Bottom accent line -->
      <div class="pointer-events-none absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-[var(--color-secondary)]/40 to-transparent" />

      <!-- Content — pinned to the bottom -->
      <div class="relative flex h-full flex-col justify-end px-4 pb-5 sm:px-6 sm:pb-7">

        <!-- Logo + name block -->
        <div class="flex items-end gap-4 mb-4">
          <img
            v-if="logoImage"
            :src="logoImage"
            :alt="`${tenantName} logo`"
            class="h-[4.5rem] w-[4.5rem] shrink-0 rounded-[1.1rem] border-2 border-white/16 object-cover shadow-2xl shadow-black/55"
            loading="eager"
            decoding="async"
            @error="$event.target.style.display='none'"
          />
          <div class="min-w-0 pb-0.5">
            <h1 class="ui-display text-[1.9rem] font-semibold leading-[1.1] text-white sm:text-4xl">{{ tenantName }}</h1>
            <p v-if="tenantDescription" class="mt-1.5 line-clamp-2 text-[13px] leading-snug text-slate-300/85" :title="tenantDescription">{{ tenantDescription }}</p>
          </div>
        </div>

        <!-- Status + location pills -->
        <div class="mb-4 flex flex-wrap items-center gap-2">
          <span class="inline-flex items-center gap-1.5 rounded-full border border-white/14 bg-black/52 px-3 py-1 text-xs font-medium text-white backdrop-blur-md">
            <span v-if="isOpen" aria-hidden="true" class="relative flex h-1.5 w-1.5 shrink-0">
              <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-70" />
              <span class="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-400" />
            </span>
            <span v-else aria-hidden="true" class="h-1.5 w-1.5 shrink-0 rounded-full bg-rose-400" />
            {{ statusLabel }}
          </span>
          <span v-if="locationLine" class="inline-flex items-center gap-1.5 rounded-full border border-white/12 bg-black/45 px-3 py-1 text-xs text-slate-300 backdrop-blur-md">
            <AppIcon name="home" class="h-3 w-3 shrink-0" />
            {{ locationLine }}
          </span>
        </div>

        <!-- CTAs — Browse Menu (primary) + Share (secondary) -->
        <div class="flex gap-2.5">
          <RouterLink
            :to="{ name: 'menu' }"
            class="ui-btn-primary flex flex-1 items-center justify-center gap-2"
            @click="trackContactClick('hero_menu_cta')"
          >
            <AppIcon name="menu" class="h-4 w-4 shrink-0" aria-hidden="true" />
            {{ t("customerLayout.navMenu") }}
          </RouterLink>
          <!-- Share — Web Share API with clipboard fallback -->
          <button
            type="button"
            class="ui-btn-outline ui-press flex shrink-0 items-center justify-center gap-1.5 px-3.5"
            :aria-label="t('customerLeadPage.shareRestaurant')"
            @click="shareRestaurant"
          >
            <AppIcon name="share" class="h-4 w-4 shrink-0" aria-hidden="true" />
            <span class="hidden sm:inline text-sm">{{ t('customerLeadPage.shareRestaurant') }}</span>
          </button>
        </div>

      </div>
    </section>

    <!-- ══ Quick actions strip ══ -->
    <div v-if="quickActions.length" class="mx-3 mt-3 sm:mx-4">
      <div class="ui-panel overflow-hidden p-2.5">
        <ul role="list" class="flex min-w-0 gap-2">
          <template v-for="(action, index) in quickActions" :key="action.key">
            <!-- Internal route actions -->
            <li v-if="action.to" class="flex flex-1 min-w-0">
              <RouterLink
                :to="action.to"
                class="ui-press ui-reveal flex flex-1 flex-col items-center justify-center gap-1.5 rounded-xl border border-slate-800/70 bg-slate-950/50 px-2 py-3 text-center transition hover:border-[var(--color-secondary)]/40 hover:bg-[var(--color-secondary)]/8 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/50"
                :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
                :aria-label="action.label"
                @click="trackContactClick(action.key)"
              >
                <span class="flex h-8 w-8 items-center justify-center rounded-full bg-[var(--color-secondary)]/12 text-[var(--color-secondary)]" aria-hidden="true">
                  <AppIcon name="calendar" class="h-4 w-4" />
                </span>
                <span class="text-[10px] font-medium leading-tight text-slate-400">{{ action.label }}</span>
              </RouterLink>
            </li>
            <!-- External link actions -->
            <li v-else-if="action.href" class="flex flex-1 min-w-0">
              <a
                :href="action.href"
                target="_blank"
                rel="noopener noreferrer"
                class="ui-press ui-reveal flex flex-1 flex-col items-center justify-center gap-1.5 rounded-xl border border-slate-800/70 bg-slate-950/50 px-2 py-3 text-center transition hover:border-[var(--color-secondary)]/40 hover:bg-[var(--color-secondary)]/8 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/50"
                :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
                :aria-label="action.label"
                @click="trackContactClick(action.key)"
              >
                <span class="flex h-8 w-8 items-center justify-center rounded-full bg-[var(--color-secondary)]/12 text-[var(--color-secondary)]" aria-hidden="true">
                  <!-- WhatsApp -->
                  <svg v-if="action.key === 'whatsapp'" viewBox="0 0 24 24" class="h-4 w-4" fill="currentColor" aria-hidden="true">
                    <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/>
                  </svg>
                  <!-- Phone -->
                  <AppIcon v-else-if="action.key === 'phone'" name="phone" class="h-4 w-4" />
                  <!-- Maps -->
                  <svg v-else-if="action.key === 'maps'" viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                    <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z"/><circle cx="12" cy="9" r="2.5"/>
                  </svg>
                  <!-- Reserve -->
                  <AppIcon v-else-if="action.key === 'reserve'" name="calendar" class="h-4 w-4" />
                </span>
                <span class="text-[10px] font-medium leading-tight text-slate-400">{{ action.label }}</span>
              </a>
            </li>
          </template>
        </ul>
      </div>
    </div>

    <!-- ══ Info cards ══ -->
    <div class="mx-3 mt-3 space-y-3 sm:mx-4">

      <!-- About -->
      <div v-if="hasAboutContent" class="ui-panel ui-reveal p-4 space-y-3" style="--ui-delay: 28ms">
        <p class="ui-kicker">{{ t('customerLeadPage.about') }}</p>
        <p class="text-sm leading-relaxed text-slate-300">{{ tenantDescription }}</p>
        <!-- Social links -->
        <ul v-if="socialLinks.length" role="list" class="flex flex-wrap gap-2 pt-1">
          <li v-for="social in socialLinks" :key="social.key">
            <a
              :href="social.url"
              target="_blank"
              rel="noopener noreferrer"
              class="ui-press inline-flex items-center gap-2 rounded-full border border-slate-700/60 bg-slate-900/60 px-3 py-1.5 text-xs text-slate-300 transition hover:border-[var(--color-secondary)]/40 hover:text-[var(--color-secondary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/50"
              @click="trackContactClick(`social_${social.key}`)"
            >
              <svg v-if="social.key === 'instagram'" viewBox="0 0 24 24" class="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r="1" fill="currentColor" stroke="none"/></svg>
              <svg v-else-if="social.key === 'facebook'" viewBox="0 0 24 24" class="h-3.5 w-3.5 shrink-0" fill="currentColor" aria-hidden="true"><path d="M13.5 22v-8h2.7l.5-3h-3.2V9.1c0-.87.3-1.46 1.56-1.46H17V5a15 15 0 00-2.38-.18C12.28 4.82 10.68 6.25 10.68 8.88V11H8v3h2.68v8H13.5z"/></svg>
              <svg v-else viewBox="0 0 24 24" class="h-3.5 w-3.5 shrink-0" fill="currentColor" aria-hidden="true"><path d="M19.59 6.69A4.83 4.83 0 0122 10.4V18a4 4 0 01-4 4h-6.2a6 6 0 01-6-6V9.5a4 4 0 014-4h5.9a4.83 4.83 0 013.89 1.19zM14 10a1 1 0 101 1 1 1 0 00-1-1zm-5 3.2a3 3 0 103 3 3 3 0 00-3-3z"/></svg>
              <span>{{ social.label }}</span>
            </a>
          </li>
        </ul>
      </div>

      <!-- Business hours -->
      <div v-if="businessHoursRows.length || businessHoursSummary" class="ui-panel ui-reveal p-4 space-y-3" style="--ui-delay: 56ms">
        <div class="flex items-center justify-between gap-2">
          <p class="ui-kicker">{{ t('customerLeadPage.businessHours') }}</p>
          <span
            class="inline-flex items-center gap-1.5 rounded-full border border-slate-700/60 bg-slate-900/60 px-2.5 py-0.5 text-[10px] font-medium"
            :class="isOpen ? 'text-emerald-400' : 'text-rose-400'"
          >
            <span
              class="h-1.5 w-1.5 rounded-full"
              :class="isOpen ? 'bg-emerald-400' : 'bg-rose-400'"
            />
            {{ statusLabel }}
          </span>
        </div>
        <!-- Structured rows (when schedule configured) -->
        <dl v-if="businessHoursRows.length" class="divide-y divide-slate-800/50">
          <div
            v-for="row in businessHoursRows"
            :key="row.key"
            class="flex items-center justify-between gap-3 py-2 text-sm first:pt-0 last:pb-0"
            :class="row.key === todayKey ? 'font-semibold' : ''"
          >
            <dt :class="row.key === todayKey ? 'text-[var(--color-secondary)]' : 'text-slate-300'">{{ row.label }}</dt>
            <dd class="tabular-nums" :class="row.key === todayKey ? 'text-[var(--color-secondary)]' : 'text-slate-500'">
              {{ row.value || '—' }}
            </dd>
          </div>
        </dl>
        <!-- Summary fallback -->
        <p v-else-if="businessHoursSummary" class="text-sm text-slate-300">{{ businessHoursSummary }}</p>
      </div>

      <!-- External reservation link (only when restaurant has a direct booking platform) -->
      <div v-if="reservationUrl" class="ui-panel ui-reveal overflow-hidden p-4" style="--ui-delay: 84ms">
        <div class="flex items-center justify-between gap-4">
          <div class="min-w-0">
            <p class="text-sm font-semibold text-slate-100">{{ t('customerLeadPage.bookOnPlatform') }}</p>
            <p class="mt-0.5 text-xs text-slate-400">{{ t('customerLeadPage.bookOnPlatformBody') }}</p>
          </div>
          <a
            :href="reservationUrl"
            target="_blank"
            rel="noopener noreferrer"
            class="ui-btn-outline shrink-0 gap-2 px-4 py-2.5 text-sm"
            @click="trackContactClick('reservation_url')"
          >
            <AppIcon name="link" class="h-4 w-4" />
            {{ t('reservationPage.bookDirectly') }}
          </a>
        </div>
      </div>

      <!-- Send a message card -->
      <div class="ui-panel ui-reveal overflow-hidden p-4" style="--ui-delay: 112ms">
        <div class="flex items-start justify-between gap-4">
          <div class="min-w-0">
            <p class="text-sm font-semibold text-slate-100">{{ t('customerLeadPage.helpTitle') }}</p>
            <p class="mt-0.5 text-xs text-slate-400">{{ t('customerLeadPage.helpText') }}</p>
          </div>
          <button
            type="button"
            class="ui-btn-primary shrink-0 gap-2 px-4 py-2.5 text-sm"
            @click="openLeadModal"
          >
            <AppIcon name="chat" class="h-4 w-4" />
            {{ t('customerLeadPage.contactMe') }}
          </button>
        </div>
        <!-- Google reviews link (if available) -->
        <a
          v-if="googleMapsUrl"
          :href="googleMapsUrl"
          target="_blank"
          rel="noopener noreferrer"
          class="mt-3 flex items-center gap-2 rounded-xl border border-slate-800/70 bg-slate-950/50 px-3 py-2.5 text-xs text-slate-400 transition hover:border-[var(--color-secondary)]/30 hover:text-slate-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/50"
          @click="trackContactClick('google_reviews')"
        >
          <!-- Google "G" icon -->
          <svg viewBox="0 0 24 24" class="h-4 w-4 shrink-0" aria-hidden="true">
            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
            <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z"/>
            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
          </svg>
          <span class="flex-1">{{ t('customerLeadPage.googleReviews') }}</span>
          <AppIcon name="arrowRight" class="h-3.5 w-3.5 shrink-0 opacity-50 rtl:scale-x-[-1]" />
        </a>
      </div>

    </div>

    <!-- ══ Contact modal ══ -->
    <Teleport to="body">
      <div
        v-if="showLeadModal"
        class="fixed inset-0 z-[90] flex items-end justify-center bg-slate-950/85 sm:items-center sm:p-5"
        @click.self="closeLeadModal"
      >
        <div ref="leadDialogRef" role="dialog" aria-modal="true" aria-labelledby="customer-lead-contact-dialog-title" class="max-h-[92vh] w-full max-w-lg overflow-y-auto rounded-t-3xl border border-slate-700/80 bg-slate-950 p-4 shadow-2xl shadow-black/50 sm:rounded-2xl sm:p-5">
          <div class="mb-4 flex items-start justify-between gap-3">
            <div>
              <p class="ui-kicker">{{ t("customerLeadPage.message") }}</p>
              <h2 id="customer-lead-contact-dialog-title" class="text-xl font-semibold text-slate-100">{{ t("customerLeadPage.contactMe") }}</h2>
              <p class="mt-1 text-sm text-slate-400">{{ t("customerLeadPage.helpText") }}</p>
            </div>
            <button type="button" class="ui-btn-outline ui-touch-target shrink-0 px-3 text-xs" @click="closeLeadModal">{{ t("common.close") }}</button>
          </div>

          <form class="space-y-3" novalidate @submit.prevent="submitLead">
            <div class="grid gap-3 sm:grid-cols-2">
              <label class="space-y-1 text-sm text-slate-200">
                {{ t("common.name") }}
                <input v-model.trim="form.name" type="text" class="ui-input" :class="fieldClass('name')" autocomplete="name" :aria-invalid="errors.name ? 'true' : undefined" :aria-describedby="errors.name ? 'lead-name-error' : undefined" aria-required="true" @input="clearError('name')" />
                <p v-if="errors.name" id="lead-name-error" class="text-xs text-red-300">{{ errors.name }}</p>
              </label>
              <label class="space-y-1 text-sm text-slate-200">
                {{ t("common.phone") }}
                <input v-model.trim="form.phone" type="tel" class="ui-input" :class="fieldClass('phone')" placeholder="+212..." inputmode="tel" autocomplete="tel" :aria-invalid="errors.phone ? 'true' : undefined" :aria-describedby="errors.phone ? 'lead-phone-error' : undefined" aria-required="true" @input="clearError('phone')" />
                <p v-if="errors.phone" id="lead-phone-error" class="text-xs text-red-300">{{ errors.phone }}</p>
              </label>
            </div>
            <label class="space-y-1 text-sm text-slate-200">
              {{ t("common.email") }}
              <input v-model.trim="form.email" type="email" class="ui-input" :class="fieldClass('email')" inputmode="email" autocomplete="email" spellcheck="false" :aria-invalid="errors.email ? 'true' : undefined" :aria-describedby="errors.email ? 'lead-email-error' : undefined" @input="clearError('email')" />
              <p v-if="errors.email" id="lead-email-error" class="text-xs text-red-300">{{ errors.email }}</p>
            </label>
            <label class="space-y-1 text-sm text-slate-200">
              {{ t("customerLeadPage.message") }}
              <textarea v-model.trim="form.note" rows="3" class="ui-textarea" :placeholder="t('customerLeadPage.messagePlaceholder')"></textarea>
            </label>
            <input v-model="form.hp" type="text" class="hidden" autocomplete="off" tabindex="-1" aria-hidden="true" />
            <div class="space-y-2">
              <button
                type="submit"
                class="ui-btn-primary ui-touch-target w-full justify-center disabled:cursor-not-allowed disabled:opacity-65 sm:w-auto"
                :disabled="lead.submitting || lead.success"
              >
                {{ lead.submitting ? t("customerLeadPage.sending") : lead.success ? t("customerLeadPage.sent") : t("customerLeadPage.contactMe") }}
              </button>
              <div v-if="lead.error" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
                <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
                <p class="flex-1 text-sm text-red-300">{{ lead.error }}</p>
              </div>
            </div>
            <div v-if="lead.success" role="status" class="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-100">
              {{ t("customerLeadPage.leadSuccess") }}
            </div>
          </form>
        </div>
      </div>
    </Teleport>

  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import AppIcon from "../components/AppIcon.vue";
import { useI18n } from "../composables/useI18n";
import { formatBusinessHoursRows, formatBusinessHoursSummary, getCurrentDayKey, getTodayClosingTime, getNextOpenInfo, isCurrentlyOpenBySchedule, normalizeBusinessHoursSchedule } from "../lib/businessHours";
import { trackEvent } from "../lib/analytics";
import { safeExternalUrl } from "../lib/escape";
import { useLeadStore } from "../stores/lead";
import { useCustomerStore } from "../stores/customer";
import { useToastStore } from "../stores/toast";
import { isPublicDemoHost } from "../lib/runtimeHost";
import { useTenantStore } from "../stores/tenant";

const tenant = useTenantStore();
const lead = useLeadStore();
const customerStore = useCustomerStore();
const toast = useToastStore();
const { currentLocale, t } = useI18n();
const meta = computed(() => tenant.resolvedMeta || null);
const showLeadModal = ref(false);
const leadDialogRef = ref(null);

const FOCUSABLE_LEAD = [
  'a[href]', 'button:not([disabled])', 'input:not([disabled])',
  'select:not([disabled])', 'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(', ');

const trapLeadFocus = (e) => {
  if (!leadDialogRef.value || e.key !== 'Tab') return;
  const focusable = Array.from(leadDialogRef.value.querySelectorAll(FOCUSABLE_LEAD));
  if (!focusable.length) return;
  const first = focusable[0];
  const last  = focusable[focusable.length - 1];
  if (e.shiftKey) {
    if (document.activeElement === first) { e.preventDefault(); last.focus(); }
  } else {
    if (document.activeElement === last)  { e.preventDefault(); first.focus(); }
  }
};

let _leadReturnFocus = null;
watch(showLeadModal, async (open) => {
  if (open) {
    _leadReturnFocus = document.activeElement;
    await nextTick();
    leadDialogRef.value?.querySelector(FOCUSABLE_LEAD)?.focus();
    document.addEventListener('keydown', trapLeadFocus);
  } else {
    document.removeEventListener('keydown', trapLeadFocus);
    _leadReturnFocus?.focus();
    _leadReturnFocus = null;
  }
});
const showPlatformDemo = computed(() => isPublicDemoHost());
const demoMenuUrl = computed(() => import.meta.env.VITE_PUBLIC_DEMO_URL || "https://doro.menu.ibnbatoutaweb.com/menu");

const form = reactive({ name: "", phone: "", email: "", note: "", hp: "" });
const errors = reactive({ name: "", phone: "", email: "" });

const profile = computed(() => meta.value?.profile || {});
const tenantName = computed(() => meta.value?.name || t("customerLayout.fallbackTenantName"));
const isOpen = computed(() => profile.value?.is_open !== false);
const statusLabel = computed(() => {
  if (!isOpen.value) return t("customerLeadPage.closedNow");
  const schedule = profile.value?.business_hours_schedule;
  if (schedule && Object.keys(schedule).length) {
    const openBySchedule = isCurrentlyOpenBySchedule(schedule);
    if (openBySchedule === true) {
      const closeTime = getTodayClosingTime(schedule);
      return closeTime ? t("menu.opensUntil", { time: closeTime }) : t("customerLeadPage.openNow");
    }
    if (openBySchedule === false) {
      const next = getNextOpenInfo(schedule, currentLocale.value);
      if (next) {
        const dayPart = next.isTomorrow ? t("menu.tomorrow") : next.dayLabel;
        return t("menu.opensAt", { day: dayPart, time: next.openTime });
      }
    }
  }
  return t("customerLeadPage.openNow");
});
const locationLine = computed(() => String(profile.value?.address || profile.value?.city || "").trim());
const tenantDescription = computed(() => {
  const tagline = String(profile.value?.tagline || "").trim();
  const desc = String(profile.value?.description || "").trim();
  if (tagline && desc) return `${tagline} — ${desc}`;
  if (tagline) return tagline;
  if (desc) return desc;
  return t("customerLeadPage.fallbackDescription");
});
const heroImage = computed(() => String(profile.value?.hero_url || "").trim());
const logoImage = computed(() => String(profile.value?.logo_url || "").trim());
const googleMapsUrl = computed(() => safeExternalUrl(profile.value?.google_maps_url));
const reservationUrl = computed(() => safeExternalUrl(profile.value?.reservation_url));
const businessHoursSchedule = computed(() => normalizeBusinessHoursSchedule(profile.value?.business_hours_schedule));
const todayKey = getCurrentDayKey();
const businessHoursRows = computed(() =>
  formatBusinessHoursRows(businessHoursSchedule.value, currentLocale.value).filter((row) => row.enabled)
);
const businessHoursSummary = computed(() => {
  const summary = formatBusinessHoursSummary(businessHoursSchedule.value, currentLocale.value);
  if (summary) return summary;
  return String(profile.value?.business_hours || "").trim();
});

const sanitizePhoneForTel = (value) => String(value || "").replace(/[^\d+]/g, "").replace(/(?!^)\+/g, "");
const sanitizePhoneForWhatsapp = (value) => String(value || "").replace(/\D/g, "");
const phoneRaw = computed(() => String(profile.value?.phone || profile.value?.whatsapp || "").trim());
const whatsappRaw = computed(() => String(profile.value?.whatsapp || profile.value?.phone || "").trim());
const phoneHref = computed(() => { const n = sanitizePhoneForTel(phoneRaw.value); return n ? `tel:${n}` : ""; });
const whatsappHref = computed(() => {
  const n = sanitizePhoneForWhatsapp(whatsappRaw.value);
  if (!n) return "";
  const text = encodeURIComponent(t("customerLeadPage.moreInfoMessage", { tenant: tenantName.value }));
  return `https://wa.me/${n}?text=${text}`;
});
const socialLinks = computed(() =>
  [
    { key: "instagram", label: "Instagram", url: safeExternalUrl(profile.value?.instagram_url) },
    { key: "facebook", label: "Facebook", url: safeExternalUrl(profile.value?.facebook_url) },
    { key: "tiktok", label: "TikTok", url: safeExternalUrl(profile.value?.tiktok_url) },
  ].filter((item) => Boolean(item.url))
);

// Quick action buttons shown below the hero (deduplicated, no repeating CTAs)
const quickActions = computed(() => {
  const actions = [];
  if (whatsappHref.value) actions.push({ key: "whatsapp", href: whatsappHref.value, label: t("customerLeadPage.whatsappNow") });
  if (phoneHref.value) actions.push({ key: "phone", href: phoneHref.value, label: t("customerLeadPage.callNow") });
  if (googleMapsUrl.value) actions.push({ key: "maps", href: googleMapsUrl.value, label: t("common.location") });
  // Reserve always links to the internal reservation page (external link shown separately below)
  actions.push({ key: "reserve", to: { name: "reserve" }, label: t("customerLayout.navReserve") });
  return actions;
});

const hasAboutContent = computed(() => Boolean(tenantDescription.value || socialLinks.value.length));

const openLeadModal = () => {
  lead.reset();
  Object.assign(form, { name: "", phone: "", email: "", note: "", hp: "" });
  Object.assign(errors, { name: "", phone: "", email: "" });
  showLeadModal.value = true;
};
const closeLeadModal = () => { showLeadModal.value = false; };
const onEscape = (e) => { if (e?.key === "Escape" && showLeadModal.value) closeLeadModal(); };
const fieldClass = (field) => (errors[field] ? "border-red-400" : "border-slate-700");
const clearError = (field) => { if (errors[field]) errors[field] = ""; };

const validate = () => {
  errors.name = ""; errors.phone = ""; errors.email = "";
  let valid = true;
  if (!form.name || form.name.length < 2) { errors.name = t("customerLeadPage.nameError"); valid = false; }
  if (!form.phone && !form.email) { errors.phone = t("customerLeadPage.contactRequired"); errors.email = t("customerLeadPage.contactRequired"); valid = false; }
  if (form.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) { errors.email = t("customerLeadPage.invalidEmail"); valid = false; }
  return valid;
};

const buildNotes = () => {
  const pageUrl = typeof window !== "undefined" ? window.location.href : "";
  return [t("customerLeadPage.leadNoteIntro"), form.note ? `Message: ${form.note}` : "", pageUrl ? `Page URL: ${pageUrl}` : ""].filter(Boolean).join("\n");
};

const submitLead = async () => {
  if (lead.success) return;
  lead.$patch({ error: null });
  if (!validate()) return;
  await lead.submitLead({ name: form.name, phone: form.phone, email: form.email, source: "customer_landing", notes: buildNotes(), hp: form.hp });
  if (lead.success) trackEvent("customer_info_lead_submit", { source: "customer_landing_form" });
};

const trackContactClick = (target) => {
  trackEvent("contact_click", { source: "customer_landing", metadata: { target: String(target || "").slice(0, 60) } });
};

// ── Share restaurant ──────────────────────────────────────────────────────────
const shareRestaurant = async () => {
  const url = window.location.origin;
  const title = tenantName.value;
  const text = tenantDescription.value || title;
  trackContactClick('share');
  if (typeof navigator.share === 'function') {
    try { await navigator.share({ title, text, url }); return; } catch { /* user cancelled or not supported */ }
  }
  try {
    await navigator.clipboard.writeText(url);
    toast.show(t('customerLeadPage.shareRestaurantCopied'), 'success');
  } catch { /* clipboard blocked — silently ignore */ }
};

onMounted(async () => {
  lead.reset();
  trackEvent("customer_info_view", { source: "customer_landing_info" }, { onceKey: "customer:landing" });
  const c = customerStore.customer;
  if (c?.name && !form.name) form.name = c.name;
  if (c?.phone && !form.phone) form.phone = c.phone;
  if (c?.email && !form.email) form.email = c.email;
  if (typeof window !== "undefined") window.addEventListener("keydown", onEscape);
});
onBeforeUnmount(() => {
  if (typeof window !== "undefined") window.removeEventListener("keydown", onEscape);
  document.removeEventListener('keydown', trapLeadFocus);
});
</script>
