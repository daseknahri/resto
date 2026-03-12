<template>
  <section class="space-y-6 ui-safe-bottom">
    <header
      class="ui-workspace-stage overflow-hidden"
      :class="isPublished ? 'border-emerald-500/30' : 'border-amber-500/30'"
    >
      <div class="relative ui-workspace-grid gap-5">
        <div class="space-y-5">
          <span class="ui-chip-strong w-fit">{{ t("ownerLaunchSuccess.launch") }}</span>
          <div class="space-y-2">
            <h2 class="ui-display text-3xl font-semibold md:text-4xl" :class="isPublished ? 'text-emerald-100' : 'text-amber-100'">
              {{ isPublished ? t("ownerLaunchSuccess.liveTitle") : t("ownerLaunchSuccess.draftTitle") }}
            </h2>
            <p class="max-w-2xl text-sm md:text-base" :class="isPublished ? 'text-emerald-100/90' : 'text-amber-100/90'">
              {{
                isPublished
                  ? t("ownerLaunchSuccess.liveText")
                  : t("ownerLaunchSuccess.draftText")
              }}
            </p>
          </div>
          <div class="grid gap-3 sm:grid-cols-3">
            <article class="ui-stat-tile">
              <p class="ui-stat-label">{{ t("ownerLaunchSuccess.publicUrl") }}</p>
              <p class="ui-stat-value text-lg md:text-2xl">{{ menuHost }}</p>
              <p class="ui-stat-note">{{ tenantName }}</p>
            </article>
            <article class="ui-stat-tile">
              <p class="ui-stat-label">{{ t("ownerLaunchSuccess.shareMessageTitle") }}</p>
              <p class="ui-stat-value text-lg md:text-2xl">{{ isPublished ? 2 : 1 }}</p>
              <p class="ui-stat-note">{{ t("ownerLaunchSuccess.nextActions") }}</p>
            </article>
            <article class="ui-stat-tile">
              <p class="ui-stat-label">{{ t("ownerLaunchSuccess.goDashboard") }}</p>
              <p class="ui-stat-value text-lg md:text-2xl">{{ isPublished ? activeActionsCount : 1 }}</p>
              <p class="ui-stat-note">{{ t("ownerLaunchSuccess.nextActions") }}</p>
            </article>
          </div>
        </div>

        <div class="grid gap-3 self-start">
          <article class="ui-command-deck space-y-3">
            <p class="ui-kicker">{{ t("ownerLaunchSuccess.publicUrl") }}</p>
            <p class="break-all text-sm font-semibold text-white md:text-base">{{ menuUrl }}</p>
            <div class="grid gap-2 sm:grid-cols-2">
              <button class="ui-btn-primary justify-center px-4 py-2 text-sm" @click="copyMenuUrl">
                {{ t("ownerLaunchSuccess.copyUrl") }}
              </button>
              <a
                :href="menuUrl"
                target="_blank"
                rel="noopener noreferrer"
                class="ui-btn-outline justify-center px-4 py-2 text-sm"
              >
                {{ t("ownerLaunchSuccess.openMenu") }}
              </a>
            </div>
          </article>
          <article class="ui-action-tile space-y-2">
            <p class="ui-kicker">{{ t("ownerLaunchSuccess.nextActions") }}</p>
            <div class="grid gap-2">
              <RouterLink to="/owner" class="ui-btn-primary justify-center">
                {{ t("ownerLaunchSuccess.goDashboard") }}
              </RouterLink>
              <RouterLink to="/owner/onboarding" class="ui-btn-outline justify-center">
                {{ t("ownerLaunchSuccess.editMenu") }}
              </RouterLink>
            </div>
          </article>
        </div>
      </div>
    </header>

    <div class="grid gap-4 xl:grid-cols-[minmax(0,1.1fr),420px]">
      <article v-if="isPublished" class="ui-spotlight-card space-y-3 p-5">
        <div class="space-y-1">
          <p class="ui-kicker">{{ t("ownerLaunchSuccess.shareMessageTitle") }}</p>
          <h3 class="text-lg font-semibold text-white">{{ tenantName }}</h3>
        </div>
        <pre class="whitespace-pre-wrap rounded-2xl border border-slate-800 bg-slate-950/70 p-4 text-xs text-slate-200">{{ shareMessage }}</pre>
        <div class="flex flex-wrap gap-2">
          <button class="ui-btn-outline justify-center px-4 py-2 text-sm" @click="copyShareMessage">
            {{ t("ownerLaunchSuccess.copyMessage") }}
          </button>
          <a
            :href="menuUrl"
            target="_blank"
            rel="noopener noreferrer"
            class="ui-btn-outline justify-center px-4 py-2 text-sm"
          >
            {{ t("ownerLaunchSuccess.openMenu") }}
          </a>
        </div>
      </article>

      <article class="ui-action-tile space-y-3 p-5">
        <p class="ui-kicker">{{ t("ownerLaunchSuccess.nextActions") }}</p>
        <div class="space-y-2 text-sm text-slate-300">
          <div class="rounded-2xl border border-slate-800/80 bg-slate-950/50 p-3">
            <p class="font-semibold text-slate-100">{{ t("ownerLaunchSuccess.goDashboard") }}</p>
            <p class="mt-1 text-slate-400">{{ t("ownerLaunchSuccess.nextActions") }}</p>
          </div>
          <div class="rounded-2xl border border-slate-800/80 bg-slate-950/50 p-3">
            <p class="font-semibold text-slate-100">{{ t("ownerLaunchSuccess.editMenu") }}</p>
            <p class="mt-1 text-slate-400">{{ t("ownerLaunchSuccess.launch") }}</p>
          </div>
          <div v-if="isPublished" class="rounded-2xl border border-slate-800/80 bg-slate-950/50 p-3">
            <p class="font-semibold text-slate-100">{{ t("ownerLaunchSuccess.copyUrl") }}</p>
            <p class="mt-1 text-slate-400">{{ t("ownerLaunchSuccess.shareMessageTitle") }}</p>
          </div>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup>
import { computed } from "vue";
import { useI18n } from "../composables/useI18n";
import { useTenantStore } from "../stores/tenant";
import { useToastStore } from "../stores/toast";

const tenant = useTenantStore();
const toast = useToastStore();
const { t } = useI18n();
const isPublished = computed(() => tenant.meta?.profile?.is_menu_published === true);
const tenantName = computed(() => tenant.meta?.profile?.restaurant_name || tenant.meta?.name || t("ownerLaunchSuccess.defaultRestaurantName"));
const activeActionsCount = computed(() => (isPublished.value ? 3 : 2));

const menuUrl = computed(() => (typeof window === "undefined" ? "/menu" : `${window.location.origin}/menu`));
const menuHost = computed(() => {
  try {
    return new URL(menuUrl.value, typeof window === "undefined" ? "https://menu.kepoli.com" : window.location.origin).host;
  } catch {
    return "menu";
  }
});
const shareMessage = computed(() => {
  return t("ownerLaunchSuccess.shareTemplate", { name: tenantName.value, url: menuUrl.value });
});

const copyMenuUrl = async () => {
  try {
    await navigator.clipboard.writeText(menuUrl.value);
    toast.show(t("ownerLaunchSuccess.menuUrlCopied"), "success");
  } catch {
    toast.show(t("ownerLaunchSuccess.copyFailed"), "error");
  }
};

const copyShareMessage = async () => {
  try {
    await navigator.clipboard.writeText(shareMessage.value);
    toast.show(t("ownerLaunchSuccess.shareCopied"), "success");
  } catch {
    toast.show(t("ownerLaunchSuccess.copyFailed"), "error");
  }
};
</script>
