<template>
  <!--
    RoleSwitcher — compact segmented control that lets one identity hop between the
    services they ACTUALLY hold: Order (everyone), Drive (drivers), Manage (tenant
    owners/staff). Modes are derived from the customer session flags, so a customer
    who is neither a driver nor an owner sees nothing (the control hides itself).
    Each segment deep-links to the right surface; the active mode is non-clickable.
  -->
  <nav
    v-if="modes.length > 1"
    class="inline-flex items-center gap-1 rounded-full border border-slate-700/60 bg-slate-900/60 p-1"
    :aria-label="t('roleSwitch.switchView')"
  >
    <template v-for="m in modes" :key="m.id">
      <span
        v-if="m.id === current"
        class="inline-flex items-center gap-1.5 rounded-full bg-[var(--color-secondary)]/15 px-3 py-1.5 text-xs font-semibold text-[var(--color-secondary)]"
        aria-current="true"
      >
        <span aria-hidden="true">{{ m.icon }}</span>
        {{ t(m.labelKey) }}
      </span>
      <RouterLink
        v-else
        :to="m.to"
        class="ui-press inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium text-slate-400 transition-colors hover:bg-slate-800/60 hover:text-slate-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/40"
      >
        <span aria-hidden="true">{{ m.icon }}</span>
        {{ t(m.labelKey) }}
      </RouterLink>
    </template>
  </nav>
</template>

<script setup>
import { computed } from 'vue';
import { RouterLink } from 'vue-router';
import { useI18n } from '../composables/useI18n';
import { useCustomerStore } from '../stores/customer';

const props = defineProps({
  /** Which mode is the surface this switcher is rendered on: 'order' | 'drive' | 'manage'. */
  current: {
    type: String,
    default: 'order',
  },
});

const { t } = useI18n();
const customerStore = useCustomerStore();

const modes = computed(() => {
  const c = customerStore.customer || {};
  const list = [
    { id: 'order', labelKey: 'roleSwitch.orderMode', icon: '🛍️', to: { name: 'super-app-hub' } },
  ];
  if (c.is_driver) {
    list.push({ id: 'drive', labelKey: 'roleSwitch.driveAndEarn', icon: '🏍️', to: { name: 'driver' } });
  }
  // has_tenant (a.k.a. is_staff) — the same identity also owns/works a tenant.
  if (c.has_tenant || c.is_staff) {
    list.push({ id: 'manage', labelKey: 'roleSwitch.manageMode', icon: '🏪', to: { name: 'owner-home' } });
  }
  return list;
});

// Exposed for the parent so it can decide whether to render a surrounding shell.
defineExpose({ modes });
const current = computed(() => props.current);
</script>
