<template>
  <div class="space-y-4">
    <section class="ui-panel overflow-hidden p-4 sm:p-5">
      <div class="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div class="space-y-2">
          <p class="ui-section-kicker">{{ t("ownerLayout.menuBuilder") }}</p>
          <h2 class="ui-display text-2xl font-semibold text-white sm:text-3xl">{{ activeTabTitle }}</h2>
        </div>
        <nav class="owner-menu-builder-nav" aria-label="Menu builder sections">
          <button
            v-for="tab in tabs"
            :key="tab.key"
            type="button"
            class="owner-menu-builder-nav-item"
            :data-active="activeTab === tab.key"
            @click="setTab(tab.key)"
          >
            <AppIcon :name="tab.icon" class="owner-menu-builder-nav-icon" />
            <span>{{ tab.label }}</span>
          </button>
        </nav>
      </div>
    </section>

    <component :is="activeComponent" standalone />
  </div>
</template>

<script setup>
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import AppIcon from "../components/AppIcon.vue";
import { useI18n } from "../composables/useI18n";
import StepCategories from "../onboarding/StepCategories.vue";
import StepDishes from "../onboarding/StepDishes.vue";

const route = useRoute();
const router = useRouter();
const { t } = useI18n();

const tabs = computed(() => [
  {
    key: "categories",
    label: t("onboardingWizard.steps.categories.title"),
    description: t("onboardingWizard.steps.categories.description"),
    icon: "menu",
    component: StepCategories,
  },
  {
    key: "dishes",
    label: t("onboardingWizard.steps.dishes.title"),
    description: t("onboardingWizard.steps.dishes.description"),
    icon: "cart",
    component: StepDishes,
  },
]);

const validTabKeys = computed(() => tabs.value.map((tab) => tab.key));
const activeTab = computed(() => {
  const tab = String(route.query.tab || "categories").toLowerCase();
  return validTabKeys.value.includes(tab) ? tab : "categories";
});
const activeTabConfig = computed(() => tabs.value.find((tab) => tab.key === activeTab.value) || tabs.value[0]);
const activeComponent = computed(() => activeTabConfig.value.component);
const activeTabTitle = computed(() => activeTabConfig.value.label);

const setTab = (tab) => {
  if (tab === activeTab.value) return;
  router.replace({
    name: "owner-menu-builder",
    query: { ...route.query, tab },
  });
};
</script>

<style scoped>
.owner-menu-builder-nav {
  display: inline-grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.5rem;
  width: 100%;
  max-width: 22rem;
  border: 1px solid rgba(51, 65, 85, 0.72);
  border-radius: 1rem;
  background: linear-gradient(135deg, rgba(2, 6, 23, 0.86), rgba(3, 15, 35, 0.78));
  padding: 0.35rem;
}

.owner-menu-builder-nav-item {
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

.owner-menu-builder-nav-item:hover {
  border-color: rgba(245, 158, 11, 0.55);
  background: rgba(15, 23, 42, 0.72);
  color: rgb(245, 158, 11);
}

.owner-menu-builder-nav-item[data-active="true"] {
  border-color: rgba(245, 158, 11, 0.82);
  background: linear-gradient(135deg, rgba(245, 158, 11, 0.2), rgba(245, 158, 11, 0.08));
  color: rgb(245, 158, 11);
  box-shadow: 0 0 0 1px rgba(245, 158, 11, 0.12) inset;
}

.owner-menu-builder-nav-icon {
  width: 0.9rem;
  height: 0.9rem;
  flex-shrink: 0;
}

@media (max-width: 640px) {
  .owner-menu-builder-nav {
    display: flex;
    max-width: none;
    overflow-x: auto;
    padding: 0.3rem;
    scrollbar-width: none;
  }

  .owner-menu-builder-nav::-webkit-scrollbar {
    display: none;
  }

  .owner-menu-builder-nav-item {
    min-height: 2.45rem;
    flex: 0 0 auto;
    font-size: 0.76rem;
    padding: 0.48rem 0.72rem;
  }

  .owner-menu-builder-nav-icon {
    width: 0.8rem;
    height: 0.8rem;
  }
}
</style>
