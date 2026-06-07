<template>
  <div class="ui-page-shell space-y-3 ui-safe-bottom">
    <section class="ui-workspace-stage ui-reveal overflow-hidden p-4 sm:p-5">
      <div class="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div class="min-w-0 space-y-1">
          <p class="ui-section-kicker">{{ t("common.profile") }}</p>
          <h2 class="ui-display truncate text-xl font-semibold text-white sm:text-2xl">{{ tenantName }}</h2>
        </div>
        <!-- TODO: requires logic change — after tab switch, focus the panel wrapper via nextTick + ref for WCAG 2.1 SC 2.4.3 -->
        <nav role="tablist" class="ui-segmented min-w-0" :aria-label="t('ownerProfile.sectionsNav')">
          <button
            v-for="tab in tabs"
            :id="'owner-profile-tab-' + tab.key"
            :key="tab.key"
            type="button"
            role="tab"
            class="ui-segmented-button ui-press"
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
      role="tabpanel"
      :aria-labelledby="'owner-profile-tab-' + activeTab"
    >
      <component
        :is="activeComponent"
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
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import AppIcon from "../components/AppIcon.vue";
import { useI18n } from "../composables/useI18n";
import StepBrand from "../onboarding/StepBrand.vue";
import StepPublish from "../onboarding/StepPublish.vue";
import StepTheme from "../onboarding/StepTheme.vue";
import OwnerBilling from "./OwnerBilling.vue";
import { useTenantStore } from "../stores/tenant";

const route = useRoute();
const router = useRouter();
const tenant = useTenantStore();
const { t } = useI18n();

const tabs = computed(() => [
  {
    key: "profile",
    label: t("common.profile"),
    icon: "settings",
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
</script>
