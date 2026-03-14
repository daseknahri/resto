<template>
  <div class="px-3 py-2 pb-24 sm:px-4 sm:py-4 sm:pb-8 ui-safe-bottom">
    <section class="ui-hero-stage ui-reveal relative overflow-hidden p-0">
      <div class="relative min-h-[calc(100vh-9.5rem)] overflow-hidden rounded-[1.35rem] border border-slate-800/70 bg-slate-950/90 sm:min-h-[calc(100vh-10.5rem)] md:min-h-[calc(100vh-9rem)]">
        <img
          v-if="heroImage"
          :src="heroImage"
          :alt="`${tenantName} hero`"
          class="absolute inset-0 h-full w-full object-cover"
          loading="eager"
          fetchpriority="high"
          decoding="async"
        />
        <div class="absolute inset-0 bg-slate-950/92"></div>
        <div class="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(20,184,166,0.11),transparent_30%),radial-gradient(circle_at_bottom_left,rgba(245,158,11,0.08),transparent_28%)]"></div>

        <div class="relative flex min-h-[calc(100vh-9.5rem)] flex-col justify-between gap-4 p-4 sm:min-h-[calc(100vh-10.5rem)] md:min-h-[calc(100vh-9rem)] md:p-6">
          <div class="mx-auto w-full max-w-4xl space-y-5 text-center">
            <div class="flex flex-col items-center gap-3">
              <div class="flex min-w-0 items-center justify-center gap-3">
                <img
                  v-if="logoImage"
                  :src="logoImage"
                  :alt="`${tenantName} logo`"
                  class="h-14 w-14 rounded-2xl border border-slate-700/70 object-cover shadow-xl shadow-black/35"
                  loading="eager"
                  decoding="async"
                />
                <div class="min-w-0 space-y-1">
                  <h1 class="ui-display text-3xl font-semibold tracking-tight text-white sm:text-4xl">{{ tenantName }}</h1>
                  <p class="text-sm text-slate-300">{{ tenantDescription }}</p>
                </div>
              </div>
              <span class="ui-chip-strong shrink-0">{{ statusLabel }}</span>
            </div>

            <div class="flex flex-wrap justify-center gap-2">
              <RouterLink :to="{ name: 'menu' }" class="ui-btn-primary inline-flex items-center gap-2 px-4 py-2 text-sm">
                <AppIcon name="menu" class="h-4 w-4" />
                <span>{{ t("customerLayout.navMenu") }}</span>
              </RouterLink>
              <button type="button" class="ui-btn-outline inline-flex items-center gap-2 px-4 py-2 text-sm" @click="openLeadModal">
                <AppIcon name="chat" class="h-4 w-4" />
                <span>{{ t("customerLeadPage.contactMe") }}</span>
              </button>
              <a
                v-if="reservationUrl"
                :href="reservationUrl"
                target="_blank"
                rel="noopener noreferrer"
                class="ui-btn-outline inline-flex items-center gap-2 px-4 py-2 text-sm"
                @click="trackContactClick('reservation_url')"
              >
                <AppIcon name="calendar" class="h-4 w-4" />
                <span>{{ t("customerLeadPage.directBooking") }}</span>
              </a>
            </div>

            <div class="mx-auto w-full max-w-3xl rounded-2xl border border-slate-700/80 bg-slate-950/78 p-3.5 text-center shadow-xl shadow-black/35 backdrop-blur-sm sm:p-4">
              <div class="space-y-3">
                <p class="text-sm text-slate-200">{{ t("customerLeadPage.helpText") }}</p>
                <div class="flex flex-wrap justify-center gap-2">
                  <a
                    v-if="whatsappHref"
                    :href="whatsappHref"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="ui-btn-outline inline-flex items-center gap-2 px-3 py-2 text-xs"
                    @click="trackContactClick('whatsapp_contact')"
                  >
                    <AppIcon name="chat" class="h-3.5 w-3.5" />
                    <span>{{ t("customerLeadPage.whatsappNow") }}</span>
                  </a>
                  <a
                    v-if="phoneHref"
                    :href="phoneHref"
                    class="ui-btn-outline inline-flex items-center gap-2 px-3 py-2 text-xs"
                    @click="trackContactClick('phone_call')"
                  >
                    <AppIcon name="phone" class="h-3.5 w-3.5" />
                    <span>{{ t("customerLeadPage.callNow") }}</span>
                  </a>
                  <a
                    v-if="googleMapsUrl"
                    :href="googleMapsUrl"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="ui-btn-outline inline-flex items-center gap-2 px-3 py-2 text-xs"
                    @click="trackContactClick('google_reviews')"
                  >
                    <AppIcon name="info" class="h-3.5 w-3.5" />
                    <span>{{ t("customerLeadPage.googleReviews") }}</span>
                  </a>
                </div>

                <div v-if="socialLinks.length" class="flex flex-wrap justify-center gap-2">
                  <a
                    v-for="social in socialLinks"
                    :key="`social-${social.key}`"
                    :href="social.url"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="ui-chip inline-flex items-center gap-2 text-[11px]"
                    @click="trackContactClick(`social_${social.key}`)"
                  >
                    <span aria-hidden="true">
                      <svg v-if="social.key === 'instagram'" viewBox="0 0 24 24" class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="5" /><circle cx="12" cy="12" r="4" /><circle cx="17.5" cy="6.5" r="1" /></svg>
                      <svg v-else-if="social.key === 'facebook'" viewBox="0 0 24 24" class="h-3.5 w-3.5" fill="currentColor"><path d="M13.5 22v-8h2.7l.5-3h-3.2V9.1c0-.87.3-1.46 1.56-1.46H17V4.98C16.7 4.94 15.74 4.85 14.62 4.85c-2.34 0-3.94 1.43-3.94 4.06V11H8v3h2.68v8h2.82z" /></svg>
                      <svg v-else viewBox="0 0 24 24" class="h-3.5 w-3.5" fill="currentColor"><path d="M19.59 6.69A4.83 4.83 0 0 1 22 10.4V18a4 4 0 0 1-4 4h-6.2a6 6 0 0 1-6-6V9.5a4 4 0 0 1 4-4h5.9a4.83 4.83 0 0 1 3.89 1.19zM14 10a1 1 0 1 0 1 1 1 1 0 0 0-1-1zm-5 3.2a3 3 0 1 0 3 3 3 3 0 0 0-3-3z" /></svg>
                    </span>
                    <span>{{ social.label }}</span>
                  </a>
                </div>

                <div class="flex flex-wrap justify-center gap-2 pt-1">
                  <span class="ui-chip">{{ locationLine || t("customerLeadPage.fallbackDescription") }}</span>
                  <span class="ui-chip">{{ t("customerLeadPage.responseValue") }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <Teleport to="body">
      <div v-if="showLeadModal" class="fixed inset-0 z-[90] flex items-center justify-center bg-slate-950/86 p-3 sm:p-5" @click.self="closeLeadModal">
        <div class="w-full max-w-lg rounded-2xl border border-slate-700/80 bg-slate-950 p-4 shadow-2xl shadow-black/50 sm:p-5">
          <div class="mb-4 flex items-center justify-between gap-3">
            <div>
              <p class="ui-kicker">{{ t("customerLeadPage.message") }}</p>
              <h2 class="text-xl font-semibold text-slate-100">{{ t("customerLeadPage.contactMe") }}</h2>
              <p class="mt-1 text-sm text-slate-400">{{ t("customerLeadPage.helpText") }}</p>
            </div>
            <button type="button" class="ui-btn-outline px-3 py-1.5 text-xs" @click="closeLeadModal">{{ t("common.close") }}</button>
          </div>

          <form class="space-y-3" @submit.prevent="submitLead">
            <div class="grid gap-3 sm:grid-cols-2">
              <label class="space-y-1 text-sm text-slate-200">
                {{ t("common.name") }}
                <input
                  v-model.trim="form.name"
                  class="ui-input"
                  :class="fieldClass('name')"
                  autocomplete="name"
                  @input="clearError('name')"
                />
                <p v-if="errors.name" class="text-xs text-red-300">{{ errors.name }}</p>
              </label>
              <label class="space-y-1 text-sm text-slate-200">
                {{ t("common.phone") }}
                <input
                  v-model.trim="form.phone"
                  class="ui-input"
                  :class="fieldClass('phone')"
                  placeholder="+212..."
                  inputmode="tel"
                  autocomplete="tel"
                  @input="clearError('phone')"
                />
                <p v-if="errors.phone" class="text-xs text-red-300">{{ errors.phone }}</p>
              </label>
            </div>

            <label class="space-y-1 text-sm text-slate-200">
              {{ t("common.email") }}
              <input
                v-model.trim="form.email"
                type="email"
                class="ui-input"
                :class="fieldClass('email')"
                inputmode="email"
                autocomplete="email"
                @input="clearError('email')"
              />
              <p v-if="errors.email" class="text-xs text-red-300">{{ errors.email }}</p>
            </label>

            <label class="space-y-1 text-sm text-slate-200">
              {{ t("customerLeadPage.message") }}
              <textarea
                v-model.trim="form.note"
                rows="3"
                class="ui-textarea"
                :placeholder="t('customerLeadPage.messagePlaceholder')"
              ></textarea>
            </label>

            <input v-model="form.hp" type="text" class="hidden" autocomplete="off" tabindex="-1" aria-hidden="true" />

            <div class="flex flex-wrap items-center gap-3">
              <button type="submit" class="ui-btn-primary ui-touch-target w-full justify-center disabled:cursor-not-allowed disabled:opacity-65 sm:w-auto" :disabled="lead.submitting || lead.success">
                {{ lead.submitting ? t("customerLeadPage.sending") : lead.success ? t("customerLeadPage.sent") : t("customerLeadPage.contactMe") }}
              </button>
              <p v-if="lead.error" class="text-sm text-red-300">{{ lead.error }}</p>
            </div>

            <div v-if="lead.success" class="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-100">
              {{ t("customerLeadPage.leadSuccess") }}
            </div>
          </form>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import AppIcon from "../components/AppIcon.vue";
import { useI18n } from "../composables/useI18n";
import { trackEvent } from "../lib/analytics";
import { useLeadStore } from "../stores/lead";
import { useTenantStore } from "../stores/tenant";

const tenant = useTenantStore();
const lead = useLeadStore();
const { t } = useI18n();
const meta = computed(() => tenant.resolvedMeta || null);
const showLeadModal = ref(false);

const form = reactive({
  name: "",
  phone: "",
  email: "",
  note: "",
  hp: "",
});

const errors = reactive({
  name: "",
  phone: "",
  email: "",
});

const profile = computed(() => meta.value?.profile || {});
const tenantName = computed(() => meta.value?.name || t("customerLayout.fallbackTenantName"));
const isOpen = computed(() => profile.value?.is_open !== false);
const statusLabel = computed(() => (isOpen.value ? t("customerLeadPage.openNow") : t("customerLeadPage.closedNow")));
const locationLine = computed(() => {
  const line = String(profile.value?.address || profile.value?.city || "").trim();
  return line || "";
});
const tenantDescription = computed(() => {
  const tagline = String(profile.value?.tagline || "").trim();
  const desc = String(profile.value?.description || "").trim();
  if (tagline && desc) return `${tagline} - ${desc}`;
  if (tagline) return tagline;
  if (desc) return desc;
  return t("customerLeadPage.fallbackDescription");
});
const heroImage = computed(() => String(profile.value?.hero_url || "").trim());
const logoImage = computed(() => String(profile.value?.logo_url || "").trim());
const googleMapsUrl = computed(() => String(profile.value?.google_maps_url || "").trim());
const reservationUrl = computed(() => String(profile.value?.reservation_url || "").trim());

const sanitizePhoneForTel = (value) =>
  String(value || "")
    .replace(/[^\d+]/g, "")
    .replace(/(?!^)\+/g, "");
const sanitizePhoneForWhatsapp = (value) => String(value || "").replace(/\D/g, "");
const phoneRaw = computed(() => String(profile.value?.phone || profile.value?.whatsapp || "").trim());
const whatsappRaw = computed(() => String(profile.value?.whatsapp || profile.value?.phone || "").trim());
const phoneHref = computed(() => {
  const normalized = sanitizePhoneForTel(phoneRaw.value);
  return normalized ? `tel:${normalized}` : "";
});
const whatsappHref = computed(() => {
  const normalized = sanitizePhoneForWhatsapp(whatsappRaw.value);
  if (!normalized) return "";
  const text = encodeURIComponent(t("customerLeadPage.moreInfoMessage", { tenant: tenantName.value }));
  return `https://wa.me/${normalized}?text=${text}`;
});
const socialLinks = computed(() =>
  [
    { key: "instagram", label: "Instagram", url: String(profile.value?.instagram_url || "").trim() },
    { key: "facebook", label: "Facebook", url: String(profile.value?.facebook_url || "").trim() },
    { key: "tiktok", label: "TikTok", url: String(profile.value?.tiktok_url || "").trim() },
  ].filter((item) => Boolean(item.url))
);

const openLeadModal = () => {
  showLeadModal.value = true;
};

const closeLeadModal = () => {
  showLeadModal.value = false;
};

const onEscape = (event) => {
  if (event?.key !== "Escape") return;
  if (!showLeadModal.value) return;
  closeLeadModal();
};

const fieldClass = (field) => (errors[field] ? "border-red-400" : "border-slate-700");
const clearError = (field) => {
  if (errors[field]) errors[field] = "";
};

const validate = () => {
  errors.name = "";
  errors.phone = "";
  errors.email = "";
  let valid = true;

  if (!form.name || form.name.length < 2) {
    errors.name = t("customerLeadPage.nameError");
    valid = false;
  }
  if (!form.phone && !form.email) {
    errors.phone = t("customerLeadPage.contactRequired");
    errors.email = t("customerLeadPage.contactRequired");
    valid = false;
  }
  if (form.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) {
    errors.email = t("customerLeadPage.invalidEmail");
    valid = false;
  }

  return valid;
};

const buildNotes = () => {
  const pageUrl = typeof window !== "undefined" ? window.location.href : "";
  const lines = [
    t("customerLeadPage.leadNoteIntro"),
    form.note ? `Message: ${form.note}` : "",
    pageUrl ? `Page URL: ${pageUrl}` : "",
  ].filter(Boolean);
  return lines.join("\n");
};

const submitLead = async () => {
  if (lead.success) return;
  if (!validate()) return;

  await lead.submitLead({
    name: form.name,
    phone: form.phone,
    email: form.email,
    source: "customer_landing",
    notes: buildNotes(),
    hp: form.hp,
  });

  if (lead.success) {
    trackEvent("customer_info_lead_submit", { source: "customer_landing_form" });
  }
};

const trackContactClick = (target) => {
  trackEvent("contact_click", {
    source: "customer_landing",
    metadata: { target: String(target || "").slice(0, 60) },
  });
};

onMounted(async () => {
  lead.reset();
  trackEvent("customer_info_view", { source: "customer_landing_info" }, { onceKey: "customer:landing" });
  if (typeof window !== "undefined") {
    window.addEventListener("keydown", onEscape);
  }
});

onBeforeUnmount(() => {
  if (typeof window !== "undefined") {
    window.removeEventListener("keydown", onEscape);
  }
});
</script>
