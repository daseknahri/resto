<template>
  <section class="space-y-8 px-4 py-8 md:space-y-10 md:py-12">
    <div v-if="leadSuccess" class="ui-panel flex items-center justify-between border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-emerald-100">
      <span>Your request was received. We will contact you shortly.</span>
      <button class="text-sm underline" @click="dismiss">Dismiss</button>
    </div>

    <div class="ui-glass relative overflow-hidden">
      <div class="pointer-events-none absolute -right-12 -top-12 h-56 w-56 rounded-full bg-amber-400/10 blur-3xl"></div>
      <div class="pointer-events-none absolute -left-10 bottom-0 h-56 w-56 rounded-full bg-teal-400/10 blur-3xl"></div>
      <div class="relative grid gap-8 p-5 sm:p-6 md:grid-cols-[1.3fr,1fr] md:p-10">
        <div class="space-y-6">
          <div class="ui-chip w-fit">
            <span class="h-1.5 w-1.5 rounded-full bg-emerald-400"></span>
            Restaurant SaaS platform
            <span class="text-emerald-300">Live</span>
          </div>

          <div class="space-y-3">
            <h1 class="ui-display max-w-2xl text-4xl font-semibold leading-tight text-white md:text-5xl">
              Build and sell premium restaurant menus with one strong SaaS core.
            </h1>
            <p class="max-w-2xl text-slate-300 md:text-lg">
              One product, three user interfaces: conversion landing, owner workspace, and customer menu. Launch with Basic now, then scale to Growth and Pro.
            </p>
          </div>

          <div class="flex flex-wrap gap-2 pt-1 sm:gap-3">
            <RouterLink to="/get-started" class="ui-btn-primary ui-touch-target">Get my menu</RouterLink>
            <RouterLink to="/menu" class="ui-btn-outline ui-touch-target">View live demo</RouterLink>
            <RouterLink v-if="session.canEditTenantMenu" to="/owner" class="ui-btn-outline ui-touch-target">Open owner workspace</RouterLink>
          </div>

          <div class="grid gap-3 pt-2 sm:grid-cols-3">
            <article class="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-3">
              <p class="text-xs uppercase tracking-[0.2em] text-slate-500">Launch Time</p>
              <p class="mt-1 text-xl font-semibold text-white">1 day</p>
            </article>
            <article class="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-3">
              <p class="text-xs uppercase tracking-[0.2em] text-slate-500">Interfaces</p>
              <p class="mt-1 text-xl font-semibold text-white">3 roles</p>
            </article>
            <article class="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-3">
              <p class="text-xs uppercase tracking-[0.2em] text-slate-500">Tier Ready</p>
              <p class="mt-1 text-xl font-semibold text-white">Basic first</p>
            </article>
          </div>
        </div>

        <div class="grid gap-3 self-end">
          <article class="ui-panel bg-slate-950/65 p-4">
            <p class="ui-kicker">Landing</p>
            <p class="mt-2 text-lg font-semibold text-white">Capture and qualify leads</p>
            <p class="mt-1 text-sm text-slate-400">Offer-focused copy, trust sections, and structured call booking.</p>
          </article>
          <article class="ui-panel bg-slate-950/65 p-4">
            <p class="ui-kicker">Owner</p>
            <p class="mt-2 text-lg font-semibold text-white">Setup and publish workflow</p>
            <p class="mt-1 text-sm text-slate-400">Wizard, media uploads, launch checks, and publish controls.</p>
          </article>
          <article class="ui-panel bg-slate-950/65 p-4">
            <p class="ui-kicker">Customer</p>
            <p class="mt-2 text-lg font-semibold text-white">Mobile-first menu and order handoff</p>
            <p class="mt-1 text-sm text-slate-400">Fast browsing, cart, and WhatsApp flow per plan entitlements.</p>
          </article>
        </div>
      </div>
    </div>

    <section class="grid gap-3 md:gap-4 md:grid-cols-3">
      <article class="ui-panel p-5">
        <p class="ui-kicker">Phase 1</p>
        <p class="mt-2 text-xl font-semibold text-white">Basic launch</p>
        <p class="mt-1 text-sm text-slate-300">QR menu + WhatsApp handoff + owner management foundation.</p>
      </article>
      <article class="ui-panel p-5">
        <p class="ui-kicker">Phase 2</p>
        <p class="mt-2 text-xl font-semibold text-white">Tier expansion</p>
        <p class="mt-1 text-sm text-slate-300">Unlock Growth operations once you validate demand with cash sales.</p>
      </article>
      <article class="ui-panel p-5">
        <p class="ui-kicker">Phase 3</p>
        <p class="mt-2 text-xl font-semibold text-white">Pro modules</p>
        <p class="mt-1 text-sm text-slate-300">Checkout, analytics, and premium plan expansion.</p>
      </article>
    </section>

    <section id="plans" class="space-y-4">
      <div class="flex items-center justify-between gap-2">
        <h2 class="ui-display text-2xl font-semibold text-white">Plans</h2>
      </div>
      <div class="grid gap-4 md:grid-cols-3">
        <article
          v-for="plan in plans"
          :key="plan.code"
          class="rounded-2xl border p-5 shadow-lg shadow-black/20"
          :class="plan.recommended ? 'border-[var(--color-secondary)] bg-[var(--color-secondary)]/12' : 'border-slate-700/60 bg-slate-900/55'"
        >
          <div class="flex items-center justify-between">
            <p class="text-lg font-semibold text-white">{{ plan.name }}</p>
            <span
              class="rounded-full px-2 py-1 text-[11px] font-semibold"
              :class="plan.available ? 'bg-emerald-400/90 text-emerald-950' : 'bg-slate-700 text-slate-200'"
            >
              {{ plan.available ? "Available" : "Soon" }}
            </span>
          </div>
          <p class="mt-1 text-sm text-slate-300">{{ plan.description }}</p>
          <ul class="mt-4 space-y-1 text-sm text-slate-300">
            <li v-for="line in plan.features" :key="line">- {{ line }}</li>
          </ul>
          <RouterLink
            :to="{ name: 'lead', query: { plan: plan.code } }"
            class="mt-5 inline-flex rounded-full border px-4 py-2 text-sm font-semibold transition-colors ui-touch-target"
            :class="plan.recommended ? 'border-[var(--color-secondary)] text-[var(--color-secondary)]' : 'border-slate-700 text-slate-100'"
          >
            {{ plan.available ? "Get started" : "Join waitlist" }}
          </RouterLink>
        </article>
      </div>
    </section>

    <section class="ui-glass p-6 md:p-8">
      <div class="grid gap-6 md:grid-cols-[1.2fr,1fr] md:items-center">
        <div class="space-y-2">
          <p class="text-sm text-slate-400">Ready to sell your menu?</p>
          <h3 class="ui-display text-3xl font-semibold text-white">Get live in one call and one setup flow.</h3>
          <p class="text-slate-300">You confirm the lead, provision the tenant, owner activates account, completes wizard, then publishes.</p>
        </div>
        <div class="flex flex-wrap gap-3">
          <RouterLink to="/get-started" class="ui-btn-primary ui-touch-target">Submit lead</RouterLink>
          <RouterLink to="/contact" class="ui-btn-outline ui-touch-target">Talk to support</RouterLink>
        </div>
      </div>
    </section>
  </section>
</template>

<script setup>
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useSessionStore } from "../stores/session";

const route = useRoute();
const router = useRouter();
const session = useSessionStore();
const leadSuccess = ref(route.query.lead === "success");

const plans = [
  {
    code: "basic",
    name: "Basic",
    description: "Launch fast with QR menu and WhatsApp handoff flow.",
    features: ["Restaurant landing + menu browse flow", "WhatsApp order handoff", "Owner menu builder and publish controls"],
    available: true,
    recommended: true,
  },
  {
    code: "growth",
    name: "Growth",
    description: "Enable in-platform order operations workflow.",
    features: ["Order management dashboard", "Order status workflow", "Kitchen-oriented operations"],
    available: false,
    recommended: false,
  },
  {
    code: "pro",
    name: "Pro",
    description: "Scale with analytics and premium capabilities.",
    features: ["Priority feature access", "Advanced integrations", "Enterprise-ready controls"],
    available: false,
    recommended: false,
  },
];

const dismiss = () => {
  leadSuccess.value = false;
  const q = { ...route.query };
  delete q.lead;
  router.replace({ query: q });
};
</script>
