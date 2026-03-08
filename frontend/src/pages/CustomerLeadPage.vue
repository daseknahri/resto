<template>
  <div class="space-y-4 px-4 py-4 pb-32 sm:pb-8 ui-safe-bottom">
    <header class="ui-glass ui-reveal overflow-hidden p-0">
      <div class="relative min-h-[240px] overflow-hidden md:min-h-[260px]">
        <img
          v-if="heroImage"
          :src="heroImage"
          :alt="`${tenantName} hero`"
          class="absolute inset-0 h-full w-full object-cover"
          loading="lazy"
        />
        <div class="absolute inset-0 bg-slate-950/76"></div>
        <div class="absolute inset-0 bg-gradient-to-br from-black/10 via-slate-950/60 to-black/80"></div>

        <div class="relative flex min-h-[240px] flex-col justify-end gap-3 p-4 md:min-h-[260px] md:p-5">
          <div class="flex flex-wrap items-center gap-2">
            <span class="ui-chip">{{ statusLabel }}</span>
            <span v-if="locationLine" class="ui-chip">{{ locationLine }}</span>
            <span class="ui-chip">Mode: {{ orderingModeLabel }}</span>
          </div>

          <div class="space-y-1.5">
            <p class="ui-kicker">Restaurant landing</p>
            <h1 class="ui-display text-2xl font-semibold tracking-tight text-white md:text-3xl">{{ tenantName }}</h1>
            <p class="max-w-2xl text-sm text-slate-200">{{ tenantDescription }}</p>
            <div v-if="socialLinks.length" class="flex flex-wrap gap-2 pt-1">
              <a
                v-for="social in socialLinks"
                :key="`hero-${social.key}`"
                :href="social.url"
                target="_blank"
                rel="noopener noreferrer"
                class="ui-chip text-[11px]"
                @click="trackContactClick(`social_${social.key}`)"
              >
                {{ social.label }}
              </a>
            </div>
          </div>
        </div>
      </div>
    </header>

    <section class="grid gap-3 sm:grid-cols-2">
      <article class="ui-panel ui-surface-lift ui-reveal p-4" style="--ui-delay: 40ms">
        <p class="ui-kicker">Step 1</p>
        <p class="mt-1 text-lg font-semibold text-white">Browse menu</p>
        <p class="mt-1 text-sm text-slate-300">Explore categories and dishes before placing an order.</p>
      </article>

      <article class="ui-panel ui-surface-lift ui-reveal p-4" style="--ui-delay: 70ms">
        <p class="ui-kicker">Step 2</p>
        <p class="mt-1 text-lg font-semibold text-white">Reserve table</p>
        <p class="mt-1 text-sm text-slate-300">Send your reservation request directly from mobile.</p>
      </article>

      <a
        v-if="googleMapsUrl"
        :href="googleMapsUrl"
        target="_blank"
        rel="noopener noreferrer"
        class="ui-panel ui-surface-lift ui-reveal group p-4 transition hover:border-[var(--color-secondary)]/70"
        style="--ui-delay: 100ms"
        @click="trackContactClick('google_reviews')"
      >
        <p class="ui-kicker">Trust</p>
        <p class="mt-1 text-lg font-semibold text-white">Google reviews</p>
        <p class="mt-1 text-sm text-slate-300">Check ratings and real customer feedback.</p>
      </a>

      <a
        v-if="whatsappHref || phoneHref"
        :href="whatsappHref || phoneHref || '#'"
        target="_blank"
        rel="noopener noreferrer"
        class="ui-panel ui-surface-lift ui-reveal group p-4 transition hover:border-[var(--color-secondary)]/70"
        style="--ui-delay: 130ms"
        @click="trackContactClick(whatsappHref ? 'whatsapp_contact' : 'phone_call')"
      >
        <p class="ui-kicker">Contact</p>
        <p class="mt-1 text-lg font-semibold text-white">{{ whatsappHref ? "WhatsApp now" : "Call now" }}</p>
        <p class="mt-1 text-sm text-slate-300">Get quick support before ordering.</p>
      </a>
    </section>

    <section class="grid gap-3 sm:grid-cols-3">
      <article class="ui-panel ui-surface-lift ui-reveal p-4" style="--ui-delay: 80ms">
        <p class="ui-kicker">Categories</p>
        <p class="mt-1 text-2xl font-semibold text-white">{{ categoriesCount }}</p>
      </article>
      <article class="ui-panel ui-surface-lift ui-reveal p-4" style="--ui-delay: 110ms">
        <p class="ui-kicker">Dishes</p>
        <p class="mt-1 text-2xl font-semibold text-white">{{ dishesCount }}</p>
      </article>
      <article class="ui-panel ui-surface-lift ui-reveal p-4" style="--ui-delay: 140ms">
        <p class="ui-kicker">Response</p>
        <p class="mt-1 text-base font-semibold text-white">Fast confirmation</p>
      </article>
    </section>

    <section class="ui-panel ui-reveal p-4 md:p-5" style="--ui-delay: 120ms">
      <div class="grid gap-5 md:grid-cols-[1fr,1.2fr]">
        <div class="space-y-2">
          <h2 class="text-xl font-semibold text-white">Need help before ordering?</h2>
          <p class="text-sm text-slate-300">
            Share your contact details and we will reach out with availability and recommendations.
          </p>
          <div v-if="lead.success" class="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-100">
            Thank you. We received your request and will contact you soon.
          </div>
          <button
            v-if="lead.success"
            type="button"
            class="ui-btn-primary ui-touch-target w-full justify-center opacity-90 sm:w-auto"
            disabled
          >
            We will contact you shortly
          </button>
          <a
            v-if="reservationUrl"
            :href="reservationUrl"
            target="_blank"
            rel="noopener noreferrer"
            class="inline-flex text-sm text-[var(--color-secondary)] hover:underline"
            @click="trackContactClick('reservation_url')"
          >
            Prefer direct booking? Open reservation link
          </a>
        </div>

        <form class="space-y-3" @submit.prevent="submitLead">
          <div class="grid gap-3 sm:grid-cols-2">
            <label class="space-y-1 text-sm text-slate-200">
              Name
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
              Phone
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
            Email
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
            Message
            <textarea
              v-model.trim="form.note"
              rows="3"
              class="ui-textarea"
              placeholder="Any dietary needs, preferred time, or questions..."
            ></textarea>
          </label>

          <input v-model="form.hp" type="text" class="hidden" autocomplete="off" tabindex="-1" aria-hidden="true" />

          <div class="flex flex-wrap items-center gap-3">
            <button type="submit" class="ui-btn-primary ui-touch-target disabled:cursor-not-allowed disabled:opacity-65" :disabled="lead.submitting || lead.success">
              {{ lead.submitting ? "Sending..." : lead.success ? "Sent" : "Contact me" }}
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
import { trackEvent } from "../lib/analytics";
import { useLeadStore } from "../stores/lead";
import { useMenuStore } from "../stores/menu";
import { useTenantStore } from "../stores/tenant";

const tenant = useTenantStore();
const menu = useMenuStore();
const lead = useLeadStore();

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

const profile = computed(() => tenant.meta?.profile || {});
const tenantName = computed(() => tenant.meta?.name || "Restaurant");
const isOpen = computed(() => profile.value?.is_open !== false);
const statusLabel = computed(() => (isOpen.value ? "Open now" : "Currently closed"));
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
  return "Discover our menu, check reviews, and reserve your next table in a few taps.";
});
const heroImage = computed(() => String(profile.value?.hero_url || "").trim());
const googleMapsUrl = computed(() => String(profile.value?.google_maps_url || "").trim());
const reservationUrl = computed(() => String(profile.value?.reservation_url || "").trim());
const categoriesCount = computed(() => menu.categories.length);
const dishesCount = computed(() => menu.categories.reduce((sum, cat) => sum + Number(cat?.dishes?.length || 0), 0));
const orderingModeLabel = computed(() => {
  const mode = String(tenant.entitlements?.ordering_mode || "browse").toLowerCase();
  if (mode === "checkout") return "Checkout";
  if (mode === "whatsapp") return "WhatsApp";
  return "Browse only";
});

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
  const text = encodeURIComponent(`Hi ${tenantName.value}, I'd like more information.`);
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
    errors.name = "Name must be at least 2 characters.";
    valid = false;
  }
  if (!form.phone && !form.email) {
    errors.phone = "Provide phone or email.";
    errors.email = "Provide phone or email.";
    valid = false;
  }
  if (form.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) {
    errors.email = "Invalid email address.";
    valid = false;
  }

  return valid;
};

const buildNotes = () => {
  const pageUrl = typeof window !== "undefined" ? window.location.href : "";
  const lines = [
    "Customer lead from restaurant landing",
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
  if (!menu.categories.length) {
    await menu.fetchCategories();
  }
  trackEvent("customer_info_view", { source: "customer_landing_info" }, { onceKey: "customer:landing" });
});
</script>
