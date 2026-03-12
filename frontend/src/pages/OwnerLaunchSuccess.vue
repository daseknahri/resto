<template>
  <section class="space-y-6 ui-safe-bottom">
    <header
      class="rounded-3xl border p-6"
      :class="isPublished ? 'border-emerald-500/40 bg-emerald-500/10' : 'border-amber-500/40 bg-amber-500/10'"
    >
      <p class="text-sm" :class="isPublished ? 'text-emerald-200' : 'text-amber-200'">{{ t("ownerLaunchSuccess.launch") }}</p>
      <h2 class="ui-display mt-1 text-3xl font-semibold" :class="isPublished ? 'text-emerald-100' : 'text-amber-100'">
        {{ isPublished ? t("ownerLaunchSuccess.liveTitle") : t("ownerLaunchSuccess.draftTitle") }}
      </h2>
      <p class="mt-2 text-sm" :class="isPublished ? 'text-emerald-100/90' : 'text-amber-100/90'">
        {{
          isPublished
            ? t("ownerLaunchSuccess.liveText")
            : t("ownerLaunchSuccess.draftText")
        }}
      </p>
    </header>

    <article v-if="isPublished" class="ui-panel space-y-3 p-5">
      <p class="text-sm text-slate-300">{{ t("ownerLaunchSuccess.publicUrl") }}</p>
      <p class="break-all text-base font-semibold text-slate-100">{{ menuUrl }}</p>
      <div class="grid gap-2 sm:flex sm:flex-wrap">
        <button class="ui-btn-outline w-full justify-center sm:w-auto" @click="copyMenuUrl">
          {{ t("ownerLaunchSuccess.copyUrl") }}
        </button>
        <a
          :href="menuUrl"
          target="_blank"
          rel="noopener noreferrer"
          class="ui-btn-outline w-full justify-center sm:w-auto"
        >
          {{ t("ownerLaunchSuccess.openMenu") }}
        </a>
      </div>
    </article>

    <article v-if="isPublished" class="ui-panel space-y-3 p-5">
      <p class="text-sm text-slate-300">{{ t("ownerLaunchSuccess.shareMessageTitle") }}</p>
      <pre class="whitespace-pre-wrap rounded-xl border border-slate-800 bg-slate-900/70 p-3 text-xs text-slate-200">{{ shareMessage }}</pre>
      <button class="ui-btn-outline w-full justify-center sm:w-auto" @click="copyShareMessage">
        {{ t("ownerLaunchSuccess.copyMessage") }}
      </button>
    </article>

    <article class="ui-panel space-y-3 p-5">
      <p class="text-sm text-slate-300">{{ t("ownerLaunchSuccess.nextActions") }}</p>
      <div class="grid gap-2 sm:flex sm:flex-wrap">
        <RouterLink to="/owner" class="ui-btn-primary w-full justify-center sm:w-auto">
          {{ t("ownerLaunchSuccess.goDashboard") }}
        </RouterLink>
        <RouterLink to="/owner/onboarding" class="ui-btn-outline w-full justify-center sm:w-auto">
          {{ t("ownerLaunchSuccess.editMenu") }}
        </RouterLink>
      </div>
    </article>
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

const menuUrl = computed(() => (typeof window === "undefined" ? "/menu" : `${window.location.origin}/menu`));
const shareMessage = computed(() => {
  const name = tenant.meta?.name || t("ownerLaunchSuccess.defaultRestaurantName");
  return t("ownerLaunchSuccess.shareTemplate", { name, url: menuUrl.value });
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
