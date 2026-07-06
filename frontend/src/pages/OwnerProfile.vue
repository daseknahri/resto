<template>
  <div class="ui-page-shell space-y-4 ui-safe-bottom">
    <section class="ui-workspace-stage ui-reveal overflow-hidden p-4 sm:p-5 sm:pb-5">
      <div class="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div class="min-w-0 space-y-1.5">
          <p class="ui-section-kicker">{{ t("common.profile") }}</p>
          <h2 class="ui-display truncate text-xl font-semibold leading-tight tracking-tight text-white sm:text-2xl">{{ tenantName }}</h2>
        </div>
        <nav role="tablist" class="ui-segmented min-w-0 sm:shrink-0" :aria-label="t('ownerProfile.sectionsNav')">
          <button
            v-for="tab in tabs"
            :id="'owner-profile-tab-' + tab.key"
            :key="tab.key"
            type="button"
            role="tab"
            class="ui-segmented-button ui-press flex-1 gap-1.5"
            :data-active="activeTab === tab.key"
            :aria-selected="activeTab === tab.key"
            @click="setTab(tab.key)"
          >
            <AppIcon :name="tab.icon" class="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            <span>{{ tab.label }}</span>
          </button>
        </nav>
      </div>
    </section>

    <div
      :id="'owner-profile-panel-' + activeTab"
      ref="panelRef"
      role="tabpanel"
      tabindex="-1"
      :aria-labelledby="'owner-profile-tab-' + activeTab"
      class="focus-visible:outline-none"
    >
      <section
        v-if="activeTab === 'orders'"
        class="ui-workspace-stage ui-reveal space-y-5 p-4 sm:p-5"
      >
        <header class="space-y-1">
          <h3 class="text-lg font-semibold text-white">{{ t("orderHandling.title") }}</h3>
          <p class="text-sm text-white/60">{{ t("orderHandling.subtitle") }}</p>
        </header>

        <div class="ui-panel-soft flex items-start justify-between gap-4 p-4">
          <div class="min-w-0 space-y-1">
            <p class="text-sm font-medium text-white">{{ t("orderHandling.autoAcceptLabel") }}</p>
            <p class="text-xs text-white/55">{{ t("orderHandling.autoAcceptHint") }}</p>
          </div>
          <button
            type="button"
            role="switch"
            :aria-checked="autoAccept"
            :aria-label="t('orderHandling.autoAcceptLabel')"
            class="ui-touch-target shrink-0 rounded-full border px-3 text-[11px] font-semibold transition-colors"
            :class="autoAccept ? 'border-emerald-500/50 bg-emerald-500/10 text-emerald-200' : 'border-slate-700 bg-slate-900 text-slate-300'"
            :disabled="ohSaving"
            @click="autoAccept = !autoAccept"
          >
            {{ autoAccept ? t("orderHandling.on") : t("orderHandling.off") }}
          </button>
        </div>

        <div class="ui-panel-soft space-y-2 p-4">
          <label for="oh-prep" class="block text-sm font-medium text-white">{{ t("orderHandling.prepLabel") }}</label>
          <p class="text-xs text-white/55">{{ t("orderHandling.prepHint") }}</p>
          <div class="flex items-center gap-3">
            <button
              type="button"
              class="ui-touch-target rounded-full border border-slate-700 bg-slate-900 px-3 text-base font-semibold text-white ui-press focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/60"
              :disabled="ohSaving || prepMinutes <= 5"
              :aria-label="t('orderHandling.prepDecrease')"
              @click="prepMinutes = Math.max(5, prepMinutes - 5)"
            >−</button>
            <input
              id="oh-prep"
              v-model.number="prepMinutes"
              type="number"
              inputmode="numeric"
              min="5"
              max="180"
              class="ui-input w-20 text-center"
            />
            <span class="text-sm text-white/70">{{ t("orderHandling.minutesUnit") }}</span>
            <button
              type="button"
              class="ui-touch-target rounded-full border border-slate-700 bg-slate-900 px-3 text-base font-semibold text-white ui-press focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/60"
              :disabled="ohSaving || prepMinutes >= 180"
              :aria-label="t('orderHandling.prepIncrease')"
              @click="prepMinutes = Math.min(180, prepMinutes + 5)"
            >+</button>
          </div>
        </div>

        <div class="flex items-center justify-between gap-3">
          <p v-if="ohStatus" class="text-sm text-white/70" role="status">{{ ohStatus }}</p>
          <button
            type="button"
            class="ui-btn-primary ui-press ms-auto"
            :disabled="ohSaving"
            @click="saveOrderHandling"
          >
            {{ ohSaving ? t("common.saving") : t("common.save") }}
          </button>
        </div>

        <!-- ── Business hours editor ── -->
        <header class="space-y-1 border-t border-white/10 pt-5">
          <h3 class="text-base font-semibold text-white">{{ t("orderHandling.hoursTitle") }}</h3>
          <p class="text-xs text-white/55">{{ t("orderHandling.hoursHint") }}</p>
        </header>

        <div class="ui-panel-soft space-y-1.5 p-4">
          <div
            v-for="(day, idx) in scheduleLocal"
            :key="day.key"
            class="flex flex-wrap items-center gap-2 py-1.5"
            :class="idx < scheduleLocal.length - 1 ? 'border-b border-white/8' : ''"
          >
            <!-- Day label + enabled toggle -->
            <button
              type="button"
              role="switch"
              :aria-checked="day.enabled"
              :aria-label="day.label"
              class="ui-touch-target w-20 shrink-0 rounded-full border px-2 text-left text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/60"
              :class="day.enabled
                ? 'border-emerald-500/50 bg-emerald-500/10 text-emerald-200'
                : 'border-slate-700 bg-slate-900 text-slate-400'"
              @click="day.enabled = !day.enabled"
            >{{ day.label }}</button>
            <!-- Time inputs (only active when day is enabled) -->
            <template v-if="day.enabled">
              <input
                v-model="day.open"
                type="time"
                class="rounded-lg border border-slate-600 bg-slate-800 px-2 py-1 text-xs tabular-nums text-slate-100 focus:border-[var(--color-secondary)] focus:outline-none disabled:opacity-40"
                :aria-label="t('orderHandling.hoursOpen', { day: day.label })"
              />
              <span class="text-slate-500">–</span>
              <input
                v-model="day.close"
                type="time"
                class="rounded-lg border border-slate-600 bg-slate-800 px-2 py-1 text-xs tabular-nums text-slate-100 focus:border-[var(--color-secondary)] focus:outline-none disabled:opacity-40"
                :aria-label="t('orderHandling.hoursClose', { day: day.label })"
              />
            </template>
            <span v-else class="text-xs text-slate-500">{{ t("orderHandling.hoursClosed") }}</span>
          </div>
        </div>

        <div class="flex items-center justify-between gap-3">
          <p v-if="scheduleStatus" class="text-sm text-white/70" role="status">{{ scheduleStatus }}</p>
          <button
            type="button"
            class="ui-btn-primary ui-press ms-auto"
            :disabled="scheduleSaving"
            @click="saveSchedule"
          >
            {{ scheduleSaving ? t("common.saving") : t("common.save") }}
          </button>
        </div>
      </section>

      <component
        :is="activeComponent"
        v-else
        class="ui-reveal"
        v-bind="activeComponentProps"
        @next="goNext"
        @back="goPrevious"
        @publish="handlePublish"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, ref, nextTick, watch, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import AppIcon from "../components/AppIcon.vue";
import SecuritySettings from "../components/SecuritySettings.vue";
import { useI18n } from "../composables/useI18n";
import { useToastStore } from "../stores/toast";
import { profileApi } from "../lib/onboardingApi";
import {
  isAutoAcceptOn,
  clampPrepMinutes,
  PREP_MINUTES_DEFAULT,
} from "../lib/orderHandling";
import StepBrand from "../onboarding/StepBrand.vue";
import StepPublish from "../onboarding/StepPublish.vue";
import StepTheme from "../onboarding/StepTheme.vue";
import OwnerBilling from "./OwnerBilling.vue";
import { useTenantStore } from "../stores/tenant";

const route = useRoute();
const router = useRouter();
const tenant = useTenantStore();
const { t } = useI18n();
const toast = useToastStore();

const tabs = computed(() => [
  {
    key: "profile",
    label: t("common.profile"),
    icon: "settings",
    component: StepBrand,
  },
  {
    key: "orders",
    label: t("orderHandling.tabLabel"),
    icon: "bell",
    component: StepBrand,
  },
  {
    key: "theme",
    label: t("stepTheme.title"),
    icon: "sparkles",
    component: StepTheme,
  },
  {
    key: "publish",
    label: t("stepPublish.title"),
    icon: "check-circle",
    component: StepPublish,
  },
  {
    key: "billing",
    label: t("ownerBilling.tabLabel"),
    icon: "card",
    component: OwnerBilling,
  },
  {
    key: "security",
    label: t("mfa.securityTabLabel"),
    icon: "shield",
    component: SecuritySettings,
  },
]);

const validTabKeys = computed(() => tabs.value.map((tab) => tab.key));

const activeTab = computed(() => {
  const tab = String(route.query.tab || "profile").toLowerCase();
  return validTabKeys.value.includes(tab) ? tab : "profile";
});

const activeTabConfig = computed(() => tabs.value.find((tab) => tab.key === activeTab.value) || tabs.value[0]);
const activeComponent = computed(() => activeTabConfig.value.component);
const activeComponentProps = computed(() => ({ standalone: true }));
const tenantName = computed(() => tenant.meta?.name || t("ownerLayout.fallbackTenantName"));

const panelRef = ref(null);

// After a tab switch, move focus to the panel wrapper so keyboard users land in
// the new section without having to Tab through the nav again (WCAG 2.4.3).
watch(activeTab, () => {
  nextTick(() => panelRef.value?.focus());
});

const setTab = (tab) => {
  if (tab === activeTab.value) return;
  router.replace({
    name: "owner-profile",
    query: { ...route.query, tab },
  });
};

const goNext = () => {
  const currentIndex = validTabKeys.value.indexOf(activeTab.value);
  const nextTab = validTabKeys.value[currentIndex + 1];
  if (nextTab) {
    setTab(nextTab);
  }
};

const goPrevious = () => {
  const currentIndex = validTabKeys.value.indexOf(activeTab.value);
  const previousTab = validTabKeys.value[currentIndex - 1];
  if (previousTab) {
    setTab(previousTab);
  }
};

const handlePublish = () => {
  router.push({ name: "owner-launch" });
};

// ── Order handling (auto-accept + default prep time) ──────────────────────────
// Self-contained settings block for the 'orders' tab. Loads the two Profile
// fields, lets the owner toggle auto-accept and tune the default prep/quote
// time, and saves via the same /profile/ endpoint as the brand form. Default
// auto_accept_orders=false means existing tenants land here with the toggle OFF
// and see no behaviour change unless they opt in.
const autoAccept = ref(false);
const prepMinutes = ref(PREP_MINUTES_DEFAULT);
const ohSaving = ref(false);
const ohStatus = ref("");

const loadOrderHandling = () => {
  const p = tenant.meta?.profile || {};
  autoAccept.value = isAutoAcceptOn(p);
  prepMinutes.value = clampPrepMinutes(p.default_prep_minutes);
};

const saveOrderHandling = async () => {
  ohSaving.value = true;
  ohStatus.value = "";
  try {
    const minutes = clampPrepMinutes(prepMinutes.value);
    prepMinutes.value = minutes;
    const saved = await profileApi.save({
      auto_accept_orders: autoAccept.value,
      default_prep_minutes: minutes,
    });
    tenant.mergeProfile(saved);
    loadOrderHandling();
    ohStatus.value = t("common.saved");
    toast.show(t("orderHandling.saved"), "success");
  } catch (e) {
    ohStatus.value = t("common.saveFailed");
    toast.show(e?.message || t("orderHandling.saveFailed"), "error");
  } finally {
    ohSaving.value = false;
  }
};

onMounted(loadOrderHandling);
watch(
  () => tenant.meta?.profile,
  () => loadOrderHandling(),
);

// ── Business hours editor ─────────────────────────────────────────────────────
const _SCHEDULE_DAYS = [
  { key: 'mon', labelKey: 'orderHandling.dayMon' },
  { key: 'tue', labelKey: 'orderHandling.dayTue' },
  { key: 'wed', labelKey: 'orderHandling.dayWed' },
  { key: 'thu', labelKey: 'orderHandling.dayThu' },
  { key: 'fri', labelKey: 'orderHandling.dayFri' },
  { key: 'sat', labelKey: 'orderHandling.daySat' },
  { key: 'sun', labelKey: 'orderHandling.daySun' },
];

const _buildScheduleLocal = () => {
  const sched = tenant.meta?.profile?.business_hours_schedule || {};
  return _SCHEDULE_DAYS.map(({ key, labelKey }) => {
    const entry = sched[key] || {};
    return {
      key,
      label: t(labelKey),
      enabled: Boolean(entry.enabled),
      open: entry.open || '09:00',
      close: entry.close || '22:00',
    };
  });
};

const scheduleLocal = ref(_buildScheduleLocal());
const scheduleSaving = ref(false);
const scheduleStatus = ref('');

watch(
  () => tenant.meta?.profile?.business_hours_schedule,
  () => { scheduleLocal.value = _buildScheduleLocal(); },
);

const saveSchedule = async () => {
  const invalidDay = scheduleLocal.value.find(
    (d) => d.enabled && d.open && d.close && d.close <= d.open,
  );
  if (invalidDay) {
    toast.show(t('orderHandling.hoursInvalidRange', { day: invalidDay.label }), 'error');
    return;
  }
  scheduleSaving.value = true;
  scheduleStatus.value = '';
  try {
    const schedule = Object.fromEntries(
      scheduleLocal.value.map(({ key, enabled, open, close }) => [
        key,
        { enabled, open: enabled ? open : null, close: enabled ? close : null },
      ])
    );
    const saved = await profileApi.save({ business_hours_schedule: schedule });
    tenant.mergeProfile(saved);
    scheduleStatus.value = t('common.saved');
    toast.show(t('orderHandling.hoursSaved'), 'success');
  } catch (e) {
    scheduleStatus.value = t('common.saveFailed');
    toast.show(e?.message || t('common.saveFailed'), 'error');
  } finally {
    scheduleSaving.value = false;
  }
};
</script>
