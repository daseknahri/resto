<template>
  <section class="max-w-3xl mx-auto space-y-4 px-4 py-8 text-slate-200">
    <header class="ui-panel p-5 space-y-2 ui-fade-up">
      <p class="ui-kicker">Support</p>
      <h1 class="text-3xl font-semibold text-white">Contact support</h1>
      <p class="text-slate-300">
        Need onboarding support, account help, or privacy requests? We usually respond within one business day.
      </p>
    </header>

    <div class="grid gap-3 sm:grid-cols-3">
      <a href="mailto:support@example.com" class="ui-panel p-4 transition hover:border-[var(--color-secondary)]/70">
        <p class="ui-kicker">Email</p>
        <p class="mt-1 text-sm font-semibold text-slate-100">support@example.com</p>
      </a>
      <a href="https://wa.me/212600000000" target="_blank" rel="noopener noreferrer" class="ui-panel p-4 transition hover:border-[var(--color-secondary)]/70">
        <p class="ui-kicker">WhatsApp</p>
        <p class="mt-1 text-sm font-semibold text-slate-100">+212600000000</p>
      </a>
      <article class="ui-panel p-4">
        <p class="ui-kicker">Hours</p>
        <p class="mt-1 text-sm font-semibold text-slate-100">Monday-Friday, 09:00-18:00</p>
      </article>
    </div>

    <article class="ui-panel p-4 space-y-2 text-sm">
      <p class="text-slate-300">For faster support, include:</p>
      <ul class="space-y-1 text-slate-400">
        <li>- Tenant slug</li>
        <li>- Account email</li>
        <li>- Short issue summary</li>
      </ul>
    </article>
  </section>
</template>
