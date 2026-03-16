<template>
  <div class="space-y-4">
    <section class="ui-panel overflow-hidden p-4 sm:p-5">
      <div class="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div class="space-y-2">
          <p class="ui-section-kicker">{{ t("common.profile") }}</p>
          <h2 class="ui-display text-2xl font-semibold text-white sm:text-3xl">{{ tenantName }}</h2>
        </div>
        <nav class="owner-profile-nav" aria-label="Owner profile sections">
          <button
            v-for="tab in tabs"
            :key="tab.key"
            type="button"
            class="owner-profile-nav-item"
            :data-active="activeTab === tab.key"
            @click="setTab(tab.key)"
          >
            <AppIcon :name="tab.icon" class="owner-profile-nav-icon" />
            <span>{{ tab.label }}</span>
          </button>
        </nav>
      </div>
    </section>

    <component
      :is="activeComponent"
      v-bind="activeComponentProps"
      @next="goNext"
      @back="goPrevious"
      @publish="handlePublish"
    />
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

<style scoped>
.owner-profile-nav {
  display: inline-grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.5rem;
  width: 100%;
  max-width: 32rem;
  border: 1px solid rgba(51, 65, 85, 0.72);
  border-radius: 1rem;
  background: linear-gradient(135deg, rgba(2, 6, 23, 0.86), rgba(3, 15, 35, 0.78));
  padding: 0.35rem;
}

.owner-profile-nav-item {
  min-height: 2.85rem;
  border-radius: 0.8rem;
  border: 1px solid rgba(51, 65, 85, 0.4);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.45rem;
  padding: 0.6rem 0.8rem;
  color: rgb(203, 213, 225);
  font-size: 0.86rem;
  font-weight: 600;
  transition: border-color 0.2s ease, background 0.2s ease, color 0.2s ease;
}

.owner-profile-nav-item:hover {
  border-color: rgba(245, 158, 11, 0.55);
  background: rgba(15, 23, 42, 0.72);
  color: rgb(245, 158, 11);
}

.owner-profile-nav-item[data-active="true"] {
  border-color: rgba(245, 158, 11, 0.82);
  background: linear-gradient(135deg, rgba(245, 158, 11, 0.2), rgba(245, 158, 11, 0.08));
  color: rgb(245, 158, 11);
  box-shadow: 0 0 0 1px rgba(245, 158, 11, 0.12) inset;
}

.owner-profile-nav-icon {
  width: 0.9rem;
  height: 0.9rem;
  flex-shrink: 0;
}

@media (max-width: 640px) {
  .owner-profile-nav {
    display: flex;
    max-width: none;
    gap: 0.4rem;
    overflow-x: auto;
    padding: 0.3rem;
    scrollbar-width: none;
  }

  .owner-profile-nav::-webkit-scrollbar {
    display: none;
  }

  .owner-profile-nav-item {
    min-height: 2.45rem;
    flex: 0 0 auto;
    font-size: 0.76rem;
    padding: 0.48rem 0.72rem;
  }

  .owner-profile-nav-icon {
    width: 0.8rem;
    height: 0.8rem;
  }
}
</style>
