<template>
  <div class="space-y-3 px-3 py-2 pb-24 sm:space-y-4 sm:px-4 sm:py-4 sm:pb-8 ui-safe-bottom">
    <header class="ui-hero-stage ui-reveal overflow-hidden p-0">
      <div class="relative min-h-[168px] overflow-hidden rounded-[1.2rem] border border-slate-800/60 bg-slate-950/60 md:min-h-[220px]">
        <img
          v-if="heroImage"
          :src="heroImage"
          :alt="`${tenantName} hero`"
          class="absolute inset-0 h-full w-full object-cover"
          loading="lazy"
        />
        <div class="absolute inset-0 bg-slate-950/72"></div>
        <div class="absolute inset-0 bg-gradient-to-br from-black/10 via-slate-950/60 to-black/80"></div>

        <div class="relative flex min-h-[168px] flex-col justify-end gap-2.5 p-3 md:min-h-[220px] md:gap-3 md:p-5">
          <div class="flex flex-wrap items-center gap-2">
            <span class="ui-chip-strong">{{ statusLabel }}</span>
            <span v-if="locationLine" class="ui-chip">{{ locationLine }}</span>
          </div>

          <div class="space-y-1.5">
            <h1 class="ui-display text-2xl font-semibold tracking-tight text-white md:text-4xl">{{ tenantName }}</h1>
            <p class="max-w-2xl text-sm text-slate-200 md:text-base">{{ tenantDescription }}</p>
          </div>

          <div class="flex flex-wrap gap-2">
            <RouterLink :to="{ name: 'menu' }" class="ui-btn-primary px-4 py-2 text-sm">
              {{ t("customerLayout.navMenu") }}
            </RouterLink>
            <a
              v-if="whatsappHref"
              :href="whatsappHref"
              target="_blank"
              rel="noopener noreferrer"
              class="ui-btn-outline px-4 py-2 text-sm"
              @click="trackContactClick('whatsapp_contact')"
            >
              {{ t("customerLeadPage.whatsappNow") }}
            </a>
          </div>
        </div>
      </div>
    </header>

    <section class="ui-glass ui-reveal p-3 md:p-5" style="--ui-delay: 120ms">
      <div class="grid gap-4 md:grid-cols-[0.92fr,1.08fr]">
        <div class="space-y-3">
          <h2 class="text-xl font-semibold text-white">{{ t("customerLeadPage.helpTitle") }}</h2>
          <p class="text-sm text-slate-300">{{ t("customerLeadPage.helpText") }}</p>
          <div class="flex flex-wrap gap-2">
            <a
              v-if="whatsappHref"
              :href="whatsappHref"
              target="_blank"
              rel="noopener noreferrer"
              class="ui-chip text-[11px]"
              @click="trackContactClick('whatsapp_contact')"
            >
              {{ t("customerLeadPage.whatsappNow") }}
            </a>
            <a
              v-if="phoneHref"
              :href="phoneHref"
              class="ui-chip text-[11px]"
              @click="trackContactClick('phone_call')"
            >
              {{ t("customerLeadPage.callNow") }}
            </a>
            <a
              v-if="googleMapsUrl"
              :href="googleMapsUrl"
              target="_blank"
              rel="noopener noreferrer"
              class="ui-chip text-[11px]"
              @click="trackContactClick('google_reviews')"
            >
              {{ t("customerLeadPage.googleReviews") }}
            </a>
            <a
              v-for="social in socialLinks"
              :key="`social-${social.key}`"
              :href="social.url"
              target="_blank"
              rel="noopener noreferrer"
              class="ui-chip text-[11px]"
              @click="trackContactClick(`social_${social.key}`)"
            >
              {{ social.label }}
            </a>
          </div>
          <div v-if="lead.success" class="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-100">
            {{ t("customerLeadPage.leadSuccess") }}
          </div>
          <button
            v-if="lead.success"
            type="button"
            class="ui-btn-primary ui-touch-target w-full justify-center opacity-90 sm:w-auto"
            disabled
          >
            {{ t("customerLeadPage.leadSuccessCta") }}
          </button>
          <a v-if="reservationUrl" :href="reservationUrl" target="_blank" rel="noopener noreferrer" class="inline-flex text-sm text-[var(--color-secondary)] hover:underline" @click="trackContactClick('reservation_url')">{{ t("customerLeadPage.directBooking") }}</a>
        </div>

        <form class="space-y-3 rounded-[1.2rem] border border-slate-800/70 bg-slate-950/35 p-3 md:rounded-[1.4rem] md:p-4" @submit.prevent="submitLead">
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
            <button type="submit" class="ui-btn-primary ui-touch-target disabled:cursor-not-allowed disabled:opacity-65" :disabled="lead.submitting || lead.success">
              {{ lead.submitting ? t("customerLeadPage.sending") : lead.success ? t("customerLeadPage.sent") : t("customerLeadPage.contactMe") }}
            </button>
          </div>
          <p v-if="lead.error" class="text-sm text-red-300">{{ lead.error }}</p>
        </form>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive } from "vue";
import { useI18n } from "../composables/useI18n";
import { trackEvent } from "../lib/analytics";
import { useLeadStore } from "../stores/lead";
import { useTenantStore } from "../stores/tenant";

const tenant = useTenantStore();
const lead = useLeadStore();
const { t } = useI18n();
const meta = computed(() => tenant.resolvedMeta || null);

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
});
</script>
