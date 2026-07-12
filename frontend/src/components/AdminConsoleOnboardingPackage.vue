<template>
  <section class="ui-workspace-stage p-4 space-y-4 text-sm text-slate-200">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <p class="ui-kicker">{{ t("adminConsole.latestProvisioningPackage") }}</p>
        <h3 class="text-xl font-semibold text-white">{{ lastProvision.tenant || "-" }}</h3>
        <p class="text-sm text-slate-400">{{ lastProvision.public_menu_url || lastProvision.tenant_url || "-" }}</p>
      </div>
      <div class="flex flex-wrap gap-2">
        <button class="ui-btn-outline px-3 py-1.5 text-xs" @click="copyOnboardingPackage">{{ t("adminConsole.copyPackage") }}</button>
        <button
          v-if="lastProvision.whatsapp_message_template"
          class="ui-btn-outline px-3 py-1.5 text-xs"
          @click="copyText(lastProvision.whatsapp_message_template)"
        >
          {{ t("adminConsole.copyMessage") }}
        </button>
        <button class="ui-btn-outline px-3 py-1.5 text-xs" @click="emit('clear')">{{ t("common.clear") }}</button>
      </div>
    </div>

    <div class="ui-context-band">
      <div class="grid gap-3 xl:grid-cols-[minmax(0,1.15fr),420px]">
        <div class="space-y-3">
          <div class="space-y-1">
            <p class="ui-kicker">{{ t("adminConsole.provisioningOperations") }}</p>
            <p class="text-lg font-semibold text-white">{{ lastProvision.tenant || "-" }}</p>
            <p class="text-sm text-slate-300">{{ currentDomainSuffixLabel }}</p>
          </div>
          <div class="flex flex-wrap gap-2">
            <span class="ui-route-badge">{{ t("adminConsole.latestProvisioningPackage") }}</span>
            <span class="ui-route-badge">{{ lastProvision.public_menu_url || lastProvision.tenant_url || "-" }}</span>
          </div>
        </div>
        <div class="grid gap-2 sm:grid-cols-3 xl:grid-cols-1">
          <article class="ui-context-stat">
            <p class="ui-kicker">{{ t("adminConsole.tenantUrl") }}</p>
            <p class="mt-1 break-all text-sm font-semibold text-white">{{ lastProvision.tenant_url || "-" }}</p>
            <button v-if="lastProvision.tenant_url" class="mt-2 inline-flex text-xs text-brand-secondary hover:underline" @click="copyText(lastProvision.tenant_url)">{{ t("common.copy") }}</button>
          </article>
          <article class="ui-context-stat">
            <p class="ui-kicker">{{ t("adminConsole.workspaceUrl") }}</p>
            <p class="mt-1 break-all text-sm font-semibold text-white">{{ lastProvision.workspace_url || "-" }}</p>
            <button v-if="lastProvision.workspace_url" class="mt-2 inline-flex text-xs text-brand-secondary hover:underline" @click="copyText(lastProvision.workspace_url)">{{ t("common.copy") }}</button>
          </article>
          <article class="ui-context-stat">
            <p class="ui-kicker">{{ t("adminConsole.activationToken") }}</p>
            <p class="mt-1 break-all text-sm font-semibold text-white">{{ lastProvision.activation_token || "-" }}</p>
            <button v-if="lastProvision.activation_token" class="mt-2 inline-flex text-xs text-brand-secondary hover:underline" @click="copyText(lastProvision.activation_token)">{{ t("common.copy") }}</button>
          </article>
        </div>
      </div>
    </div>

    <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <article class="ui-stat-tile ui-reveal" style="--ui-delay: 0ms">
        <p class="ui-stat-label">{{ t("adminConsole.tenantUrl") }}</p>
        <p class="mt-2 break-all text-sm font-semibold text-white">{{ lastProvision.tenant_url || "-" }}</p>
        <button v-if="lastProvision.tenant_url" class="ui-press mt-3 text-xs text-[var(--color-secondary)] underline-offset-2 hover:underline" @click="copyText(lastProvision.tenant_url)">{{ t("common.copy") }}</button>
      </article>
      <article class="ui-stat-tile ui-reveal" style="--ui-delay: 28ms">
        <p class="ui-stat-label">{{ t("adminConsole.workspaceUrl") }}</p>
        <p class="mt-2 break-all text-sm font-semibold text-white">{{ lastProvision.workspace_url || "-" }}</p>
        <button v-if="lastProvision.workspace_url" class="ui-press mt-3 text-xs text-[var(--color-secondary)] underline-offset-2 hover:underline" @click="copyText(lastProvision.workspace_url)">{{ t("common.copy") }}</button>
      </article>
      <article class="ui-stat-tile ui-reveal" style="--ui-delay: 56ms">
        <p class="ui-stat-label">{{ t("adminConsole.activationUrl") }}</p>
        <p class="mt-2 break-all text-sm font-semibold text-white">{{ lastProvision.activation_url || "-" }}</p>
        <button v-if="lastProvision.activation_url" class="ui-press mt-3 text-xs text-[var(--color-secondary)] underline-offset-2 hover:underline" @click="copyText(lastProvision.activation_url)">{{ t("common.copy") }}</button>
      </article>
      <article class="ui-stat-tile ui-reveal" style="--ui-delay: 84ms">
        <p class="ui-stat-label">{{ t("adminConsole.activationToken") }}</p>
        <p class="mt-2 break-all text-sm font-semibold text-white">{{ lastProvision.activation_token || "-" }}</p>
        <button v-if="lastProvision.activation_token" class="ui-press mt-3 text-xs text-[var(--color-secondary)] underline-offset-2 hover:underline" @click="copyText(lastProvision.activation_token)">{{ t("common.copy") }}</button>
      </article>
    </div>

    <div class="grid gap-4 xl:grid-cols-[minmax(0,1.1fr),420px]">
      <article class="ui-focus-card space-y-3">
        <div class="space-y-1">
          <p class="ui-kicker">{{ t("adminConsole.ownerNextSteps") }}</p>
          <p class="text-sm text-slate-300">{{ t("adminConsole.provisioningOperations") }}</p>
        </div>
        <ol v-if="lastProvision.owner_next_steps?.length" class="space-y-2 text-sm text-slate-200">
          <li
            v-for="(step, index) in lastProvision.owner_next_steps"
            :key="step"
            class="ui-checklist-card flex items-start gap-3"
            :data-complete="index < 1"
            :data-warning="index >= 1"
          >
            <span class="mt-0.5 inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[var(--color-secondary)]/15 text-xs font-semibold text-[var(--color-secondary)]">{{ index + 1 }}</span>
            <span class="leading-6">{{ step }}</span>
          </li>
        </ol>
        <p v-else class="text-sm text-slate-500">-</p>
      </article>

      <article class="ui-command-deck space-y-3">
        <div class="space-y-1">
          <p class="ui-kicker">{{ t("adminConsole.whatsappMessageTemplate") }}</p>
          <p class="text-sm text-slate-300">{{ t("adminConsole.whatsappLink") }}</p>
        </div>
        <div class="space-y-2">
          <div class="rounded-xl border border-slate-800/80 bg-slate-950/50 px-3 py-2.5">
            <p class="text-[11px] uppercase tracking-[0.18em] text-slate-500">{{ t("adminConsole.whatsappLink") }}</p>
            <p class="mt-2 break-all text-xs text-slate-200">{{ lastProvision.whatsapp_link || "-" }}</p>
            <button v-if="lastProvision.whatsapp_link" class="mt-2 text-xs text-brand-secondary hover:underline" @click="copyText(lastProvision.whatsapp_link)">{{ t("common.copy") }}</button>
          </div>
          <pre class="rounded-xl border border-slate-800 bg-slate-950/60 p-3 text-xs whitespace-pre-wrap break-all">{{ lastProvision.whatsapp_message_template || "-" }}</pre>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup>
// "Latest Provisioning Package" section of AdminConsole.vue, extracted as a
// standalone child component (RISK FE-2). The provisioning/onboarding mutation
// handlers (provision, resendActivation, loadOnboardingPackage) that populate
// lastProvision stay in the parent — this component is purely presentational:
// it renders whatever provisioning result it's given and asks the parent to
// clear it via the `clear` emit. The clipboard-copy helpers below are pure UI
// actions (no server calls, no tenant mutation, not used anywhere else in the
// parent) so they're kept fully self-contained here.
import { computed } from "vue";
import { useI18n } from "../composables/useI18n";
import { useToastStore } from "../stores/toast";

const props = defineProps({
  /** The last successful provisioning/onboarding result. Only rendered by the
   * parent (v-if) when non-null, so this is never null while mounted. */
  lastProvision: { type: Object, default: null },
  /** Precomputed "suffix label: value" string shown next to the tenant name. */
  currentDomainSuffixLabel: { type: String, default: "" },
});

const emit = defineEmits(["clear"]);

const { t } = useI18n();
const toast = useToastStore();

const packageText = computed(() => {
  if (!props.lastProvision) return "";
  const p = props.lastProvision;
  return [
    `${t("adminConsole.tenant")}: ${p.tenant || "-"}`,
    `${t("adminConsole.tenantUrl")}: ${p.tenant_url || "-"}`,
    `${t("adminConsole.workspaceUrl")}: ${p.workspace_url || "-"}`,
    `${t("adminConsole.onboardingUrl")}: ${p.onboarding_url || "-"}`,
    `${t("adminConsole.signInUrl")}: ${p.signin_url || "-"}`,
    `${t("adminConsole.activationUrl")}: ${p.activation_url || "-"}`,
    `${t("adminConsole.publicMenuUrl")}: ${p.public_menu_url || "-"}`,
    `${t("adminConsole.activationToken")}: ${p.activation_token || "-"}`,
    `${t("adminConsole.whatsappLink")}: ${p.whatsapp_link || "-"}`,
    "",
    `${t("adminConsole.ownerNextSteps")}:`,
    ...(Array.isArray(p.owner_next_steps) && p.owner_next_steps.length ? p.owner_next_steps.map((step, index) => `${index + 1}. ${step}`) : ["-"]),
    "",
    `${t("adminConsole.whatsappMessageTemplate")}:`,
    p.whatsapp_message_template || "-",
  ].join("\n");
});

const copyText = async (text) => {
  try {
    await navigator.clipboard.writeText(text);
    toast.show(t("adminConsole.copied"), "success");
  } catch {
    toast.show(t("adminConsole.copyFailed"), "error");
  }
};

const copyOnboardingPackage = async () => {
  if (!packageText.value) {
    toast.show(t("adminConsole.noPackageDetails"), "error");
    return;
  }
  await copyText(packageText.value);
};
</script>
