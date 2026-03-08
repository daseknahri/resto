<template>
  <div class="ui-auth-page flex items-center">
    <div class="ui-auth-card max-w-lg space-y-6">
      <div class="space-y-2 text-center">
        <p class="ui-kicker">Access control</p>
        <h1 class="text-2xl font-semibold text-white">Access denied</h1>
        <p class="text-sm text-slate-300">{{ message }}</p>
      </div>

      <div class="grid gap-3 sm:grid-cols-2">
        <RouterLink
          v-if="showSignIn"
          :to="signInLink"
          class="ui-btn-primary justify-center"
        >
          Sign in
        </RouterLink>
        <RouterLink
          v-if="showAdmin"
          to="/admin-console"
          class="ui-btn-primary justify-center"
        >
          Go to admin console
        </RouterLink>
        <RouterLink
          v-if="showOnboarding"
          to="/owner/onboarding"
          class="ui-btn-primary justify-center"
        >
          Go to onboarding
        </RouterLink>
        <button
          v-if="session.isAuthenticated"
          class="ui-btn-outline justify-center"
          @click="switchAccount"
        >
          Switch account
        </button>
        <RouterLink
          to="/"
          class="ui-btn-outline justify-center"
        >
          Back to home
        </RouterLink>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useSessionStore } from "../stores/session";

const route = useRoute();
const router = useRouter();
const session = useSessionStore();

const reason = computed(() => (typeof route.query.reason === "string" ? route.query.reason : ""));
const next = computed(() => (typeof route.query.next === "string" ? route.query.next : ""));

const message = computed(() => {
  if (reason.value === "admin") return "This page requires a platform admin account.";
  if (reason.value === "editor") return "This page requires a tenant owner or tenant staff account.";
  return "You do not have permission to access this page.";
});

const signInLink = computed(() => {
  return next.value ? { name: "signin", query: { next: next.value } } : { name: "signin" };
});

const showSignIn = computed(() => !session.isAuthenticated);
const showAdmin = computed(() => reason.value === "editor" && session.isPlatformAdmin);
const showOnboarding = computed(() => reason.value === "admin" && session.canEditTenantMenu);

const switchAccount = async () => {
  await session.signOut();
  router.push(signInLink.value);
};
</script>
