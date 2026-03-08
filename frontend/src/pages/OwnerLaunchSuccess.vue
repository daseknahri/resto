<template>
  <section class="space-y-6 ui-safe-bottom">
    <header
      class="rounded-3xl border p-6"
      :class="isPublished ? 'border-emerald-500/40 bg-emerald-500/10' : 'border-amber-500/40 bg-amber-500/10'"
    >
      <p class="text-sm" :class="isPublished ? 'text-emerald-200' : 'text-amber-200'">Menu launch</p>
      <h2 class="ui-display mt-1 text-3xl font-semibold" :class="isPublished ? 'text-emerald-100' : 'text-amber-100'">
        {{ isPublished ? "Your menu is live" : "Your menu is still draft" }}
      </h2>
      <p class="mt-2 text-sm" :class="isPublished ? 'text-emerald-100/90' : 'text-amber-100/90'">
        {{
          isPublished
            ? "You can now share your public link and start receiving orders or WhatsApp handoffs."
            : "Publish from step 5 in onboarding to make the menu publicly accessible."
        }}
      </p>
    </header>

    <article class="ui-panel space-y-3 p-5" v-if="isPublished">
      <p class="text-sm text-slate-300">Public menu URL</p>
      <p class="break-all text-base font-semibold text-slate-100">{{ menuUrl }}</p>
      <div class="grid gap-2 sm:flex sm:flex-wrap">
        <button class="ui-btn-outline w-full justify-center sm:w-auto" @click="copyMenuUrl">
          Copy URL
        </button>
        <a
          :href="menuUrl"
          target="_blank"
          rel="noopener noreferrer"
          class="ui-btn-outline w-full justify-center sm:w-auto"
        >
          Open menu
        </a>
      </div>
    </article>

    <article class="ui-panel space-y-3 p-5" v-if="isPublished">
      <p class="text-sm text-slate-300">Ready-to-share message</p>
      <pre class="whitespace-pre-wrap rounded-xl border border-slate-800 bg-slate-900/70 p-3 text-xs text-slate-200">{{ shareMessage }}</pre>
      <button class="ui-btn-outline w-full justify-center sm:w-auto" @click="copyShareMessage">
        Copy message
      </button>
    </article>

    <article class="ui-panel space-y-3 p-5">
      <p class="text-sm text-slate-300">Next actions</p>
      <div class="grid gap-2 sm:flex sm:flex-wrap">
        <RouterLink to="/owner" class="ui-btn-primary w-full justify-center sm:w-auto">
          Go to dashboard
        </RouterLink>
        <RouterLink to="/owner/onboarding" class="ui-btn-outline w-full justify-center sm:w-auto">
          Edit menu
        </RouterLink>
      </div>
    </article>
  </section>
</template>

<script setup>
import { computed } from "vue";
import { useTenantStore } from "../stores/tenant";
import { useToastStore } from "../stores/toast";

const tenant = useTenantStore();
const toast = useToastStore();
const isPublished = computed(() => tenant.meta?.profile?.is_menu_published === true);

const menuUrl = computed(() => (typeof window === "undefined" ? "/menu" : `${window.location.origin}/menu`));
const shareMessage = computed(() => {
  const name = tenant.meta?.name || "Our Restaurant";
  return `Hello! ${name} is now live online.\nBrowse our menu here: ${menuUrl.value}\nThank you.`;
});

const copyMenuUrl = async () => {
  try {
    await navigator.clipboard.writeText(menuUrl.value);
    toast.show("Menu URL copied", "success");
  } catch (err) {
    toast.show("Copy failed", "error");
  }
};

const copyShareMessage = async () => {
  try {
    await navigator.clipboard.writeText(shareMessage.value);
    toast.show("Share message copied", "success");
  } catch (err) {
    toast.show("Copy failed", "error");
  }
};
</script>
