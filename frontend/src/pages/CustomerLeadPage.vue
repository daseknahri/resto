<template>
  <div class="space-y-3 px-4 py-3 pb-32 sm:space-y-4 sm:py-4 sm:pb-8 ui-safe-bottom">
    <header class="ui-hero-stage ui-reveal overflow-hidden p-0">
      <div class="grid gap-4 lg:grid-cols-[minmax(0,1.08fr),320px]">
        <div class="relative min-h-[228px] overflow-hidden rounded-[1.6rem] border border-slate-800/60 bg-slate-950/60 md:min-h-[300px]">
          <img
            v-if="heroImage"
            :src="heroImage"
            :alt="`${tenantName} hero`"
            class="absolute inset-0 h-full w-full object-cover"
            loading="lazy"
          />
          <div class="absolute inset-0 bg-slate-950/76"></div>
          <div class="absolute inset-0 bg-gradient-to-br from-black/10 via-slate-950/60 to-black/80"></div>

          <div class="relative flex min-h-[228px] flex-col justify-end gap-3 p-4 md:min-h-[300px] md:p-5">
            <div class="flex flex-wrap items-center gap-2">
              <span class="ui-chip-strong">{{ statusLabel }}</span>
              <span v-if="locationLine" class="ui-chip">{{ locationLine }}</span>
              <span class="ui-chip">{{ t("menu.mode") }}: {{ orderingModeLabel }}</span>
            </div>

            <div class="space-y-1.5">
              <p class="ui-kicker">{{ t("customerLeadPage.kicker") }}</p>
              <h1 class="ui-display text-3xl font-semibold tracking-tight text-white md:text-5xl">{{ tenantName }}</h1>
              <p class="max-w-2xl text-sm text-slate-200 md:text-base">{{ tenantDescription }}</p>
            </div>
          </div>
        </div>

        <aside class="ui-command-deck ui-reveal flex flex-col gap-4 p-4 lg:p-5" style="--ui-delay: 55ms">
          <div class="space-y-1.5">
            <p class="ui-kicker">{{ t("customerLeadPage.quickContact") }}</p>
            <h2 class="text-xl font-semibold text-white">{{ t("customerLeadPage.helpTitle") }}</h2>
            <p class="text-sm text-slate-300">{{ t("customerLeadPage.helpText") }}</p>
          </div>

          <div class="grid gap-2">
            <RouterLink :to="{ name: 'menu' }" class="ui-btn-primary justify-center">
              {{ t("customerLayout.navMenu") }}
            </RouterLink>
            <RouterLink :to="{ name: 'reserve' }" class="ui-btn-outline justify-center">
              {{ t("customerLayout.navReserve") }}
            </RouterLink>
            <a
              v-if="googleMapsUrl"
              :href="googleMapsUrl"
              target="_blank"
              rel="noopener noreferrer"
              class="ui-btn-outline justify-center"
              @click="trackContactClick('google_reviews')"
            >
              {{ t("customerLeadPage.googleReviews") }}
            </a>
          </div>

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
        </aside>
      </div>
    </header>

    <section class="grid gap-3 lg:grid-cols-[repeat(3,minmax(0,1fr))]">
      <article class="ui-orbit-card ui-surface-lift ui-reveal p-4" style="--ui-delay: 40ms">
        <p class="ui-kicker">{{ t("customerLeadPage.stepOne") }}</p>
        <p class="mt-1 text-lg font-semibold text-white">{{ t("customerLeadPage.browseTitle") }}</p>
        <p class="mt-1 text-sm text-slate-300">{{ t("customerLeadPage.browseText") }}</p>
      </article>

      <article class="ui-orbit-card ui-surface-lift ui-reveal p-4" style="--ui-delay: 70ms">
        <p class="ui-kicker">{{ t("customerLeadPage.stepTwo") }}</p>
        <p class="mt-1 text-lg font-semibold text-white">{{ t("customerLeadPage.reserveTitle") }}</p>
        <p class="mt-1 text-sm text-slate-300">{{ t("customerLeadPage.reserveText") }}</p>
      </article>

      <a
        v-if="googleMapsUrl"
        :href="googleMapsUrl"
        target="_blank"
        rel="noopener noreferrer"
        class="ui-spotlight-card ui-surface-lift ui-reveal group p-4 transition hover:border-[var(--color-secondary)]/70"
        style="--ui-delay: 100ms"
        @click="trackContactClick('google_reviews')"
      >
        <p class="ui-kicker">{{ t("customerLeadPage.trust") }}</p>
        <p class="mt-1 text-lg font-semibold text-white">{{ t("customerLeadPage.googleReviews") }}</p>
        <p class="mt-1 text-sm text-slate-300">{{ t("customerLeadPage.googleReviewsText") }}</p>
      </a>
    </section>

    <section class="grid gap-3 lg:grid-cols-[1.08fr,0.92fr]">
      <article class="ui-focus-card ui-reveal p-4 md:p-5" style="--ui-delay: 95ms">
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div class="space-y-1">
            <p class="ui-kicker">{{ t("customerLeadPage.quickContact") }}</p>
            <h2 class="text-xl font-semibold text-white">{{ t("customerLeadPage.helpTitle") }}</h2>
          </div>
          <span class="ui-chip-strong">{{ statusLabel }}</span>
        </div>
        <div class="mt-4 grid gap-3 sm:grid-cols-2">
          <article class="ui-admin-subcard">
            <p class="ui-stat-label">{{ t("customerLeadPage.response") }}</p>
            <p class="mt-2 text-lg font-semibold text-white">{{ t("customerLeadPage.responseValue") }}</p>
            <p class="mt-1 text-sm text-slate-400">{{ t("customerLeadPage.reserveText") }}</p>
          </article>
          <article class="ui-admin-subcard">
            <p class="ui-stat-label">{{ t("menu.mode") }}</p>
            <p class="mt-2 text-lg font-semibold text-white">{{ orderingModeLabel }}</p>
            <p class="mt-1 text-sm text-slate-400">{{ tenantDescription }}</p>
          </article>
        </div>

        <div class="mt-4 grid gap-3 md:grid-cols-3">
          <article
            v-for="item in visitJourney"
            :key="item.label"
            class="ui-orbit-card ui-surface-lift p-4"
          >
            <p class="ui-kicker">{{ item.label }}</p>
            <p class="mt-1 text-base font-semibold text-white">{{ item.title }}</p>
            <p class="mt-2 text-sm text-slate-300">{{ item.text }}</p>
          </article>
        </div>
      </article>

      <article class="ui-command-deck ui-reveal p-4 md:p-5" style="--ui-delay: 110ms">
        <p class="ui-kicker">{{ t("customerLeadPage.quickContact") }}</p>
        <div class="mt-4 grid gap-2">
          <a
            v-if="phoneHref"
            :href="phoneHref"
            class="ui-btn-outline justify-center"
            @click="trackContactClick('phone_call')"
          >
            {{ t("customerLeadPage.callNow") }}
          </a>
          <a
            v-if="whatsappHref"
            :href="whatsappHref"
            target="_blank"
            rel="noopener noreferrer"
            class="ui-btn-primary justify-center"
            @click="trackContactClick('whatsapp_contact')"
          >
            {{ t("customerLeadPage.whatsappNow") }}
          </a>
          <a
            v-if="reservationUrl"
            :href="reservationUrl"
            target="_blank"
            rel="noopener noreferrer"
            class="ui-btn-outline justify-center"
            @click="trackContactClick('reservation_url')"
          >
            {{ t("customerLeadPage.directBooking") }}
          </a>
        </div>

        <div class="mt-4 grid gap-2">
          <a
            v-for="social in socialLinks"
            :key="`deck-${social.key}`"
            :href="social.url"
            target="_blank"
            rel="noopener noreferrer"
            class="ui-admin-subcard transition hover:border-[var(--color-secondary)]/70"
            @click="trackContactClick(`social_${social.key}`)"
          >
            <p class="ui-kicker">{{ social.label }}</p>
            <p class="mt-1 text-sm font-medium text-white">{{ tenantName }}</p>
          </a>
        </div>
      </article>
    </section>

    <section class="grid gap-3 lg:grid-cols-[0.86fr,1.14fr]">
      <div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <article class="ui-metric-card ui-surface-lift ui-reveal p-4" style="--ui-delay: 80ms">
          <p class="ui-kicker">{{ t("customerLeadPage.categories") }}</p>
          <p class="mt-1 text-2xl font-semibold text-white">{{ categoriesCount }}</p>
        </article>
        <article class="ui-metric-card ui-surface-lift ui-reveal p-4" style="--ui-delay: 110ms">
          <p class="ui-kicker">{{ t("customerLeadPage.dishes") }}</p>
          <p class="mt-1 text-2xl font-semibold text-white">{{ dishesCount }}</p>
        </article>
        <article class="ui-metric-card ui-surface-lift ui-reveal p-4" style="--ui-delay: 140ms">
          <p class="ui-kicker">{{ t("customerLeadPage.response") }}</p>
          <p class="mt-1 text-base font-semibold text-white">{{ t("customerLeadPage.responseValue") }}</p>
        </article>
        <article class="ui-metric-card ui-surface-lift ui-reveal p-4" style="--ui-delay: 170ms">
          <p class="ui-kicker">{{ t("menu.mode") }}</p>
          <p class="mt-1 text-base font-semibold text-white">{{ orderingModeLabel }}</p>
        </article>
      </div>

      <article class="ui-section-band ui-reveal p-4 md:p-5" style="--ui-delay: 140ms">
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div class="space-y-1">
            <p class="ui-kicker">{{ t("customerLeadPage.googleReviews") }}</p>
            <h2 class="text-xl font-semibold text-white">{{ t("customerLeadPage.helpTitle") }}</h2>
          </div>
          <span class="ui-data-strip">{{ locationLine || tenantName }}</span>
        </div>

        <div class="mt-4 grid gap-3 md:grid-cols-3">
          <article class="ui-admin-subcard">
            <p class="ui-kicker">{{ t("customerLeadPage.browseTitle") }}</p>
            <p class="mt-2 text-sm text-slate-300">{{ t("customerLeadPage.browseText") }}</p>
          </article>
          <article class="ui-admin-subcard">
            <p class="ui-kicker">{{ t("customerLeadPage.reserveTitle") }}</p>
            <p class="mt-2 text-sm text-slate-300">{{ t("customerLeadPage.reserveText") }}</p>
          </article>
          <article class="ui-admin-subcard">
            <p class="ui-kicker">{{ t("customerLeadPage.trust") }}</p>
            <p class="mt-2 text-sm text-slate-300">{{ t("customerLeadPage.googleReviewsText") }}</p>
          </article>
        </div>
      </article>
    </section>

    <section v-if="featuredCategories.length" class="grid gap-3 lg:grid-cols-[1.08fr,0.92fr]">
      <article class="ui-section-band ui-reveal p-4 md:p-5" style="--ui-delay: 150ms">
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div class="space-y-1">
            <p class="ui-kicker">{{ t("customerLeadPage.categories") }}</p>
            <h2 class="text-xl font-semibold text-white">{{ t("customerLeadPage.browseTitle") }}</h2>
          </div>
          <span class="ui-data-strip">{{ categoriesCount }} {{ t("customerLeadPage.categories") }}</span>
        </div>

        <div class="mt-4 grid gap-3 sm:grid-cols-2">
          <RouterLink
            v-for="category in featuredCategories"
            :key="category.slug"
            :to="{ name: 'category', params: { slug: category.slug } }"
            class="ui-admin-subcard ui-press overflow-hidden transition hover:border-[var(--color-secondary)]/70"
          >
            <div class="flex items-center gap-3">
              <div
                class="h-16 w-16 overflow-hidden rounded-2xl border border-slate-800/80 bg-slate-900/70"
              >
                <img
                  v-if="category.image"
                  :src="category.image"
                  :alt="category.name"
                  class="h-full w-full object-cover"
                  loading="lazy"
                />
                <div
                  v-else
                  class="flex h-full w-full items-center justify-center bg-[radial-gradient(circle_at_top_left,rgba(245,158,11,0.18),transparent_38%),radial-gradient(circle_at_bottom_right,rgba(20,184,166,0.14),transparent_36%)] text-sm font-semibold text-slate-200"
                >
                  {{ category.name.slice(0, 1) }}
                </div>
              </div>
              <div class="min-w-0 flex-1">
                <p class="truncate text-base font-semibold text-white">{{ category.name }}</p>
                <p class="mt-1 text-sm text-slate-300">
                  {{ category.count }} {{ t("common.dishes") }}
                </p>
                <p class="mt-2 text-xs font-medium text-[var(--color-secondary)]">
                  {{ t("categoryCard.openCategory") }}
                </p>
              </div>
            </div>
          </RouterLink>
        </div>
      </article>

      <article class="ui-command-deck ui-reveal p-4 md:p-5" style="--ui-delay: 180ms">
        <div class="space-y-1">
          <p class="ui-kicker">{{ t("customerLeadPage.stepOne") }}</p>
          <h2 class="text-xl font-semibold text-white">{{ t("customerLeadPage.helpTitle") }}</h2>
          <p class="text-sm text-slate-300">{{ t("customerLeadPage.helpText") }}</p>
        </div>

        <div class="mt-4 grid gap-2">
          <RouterLink :to="{ name: 'menu' }" class="ui-btn-primary justify-center">
            {{ t("customerLayout.navMenu") }}
          </RouterLink>
          <RouterLink :to="{ name: 'cart' }" class="ui-btn-outline justify-center">
            {{ t("customerLayout.navCart") }}
          </RouterLink>
          <RouterLink :to="{ name: 'reserve' }" class="ui-btn-outline justify-center">
            {{ t("customerLayout.navReserve") }}
          </RouterLink>
        </div>

        <div class="mt-4 grid gap-2">
          <article class="ui-admin-subcard">
            <p class="ui-kicker">{{ t("customerLeadPage.stepTwo") }}</p>
            <p class="mt-1 text-sm text-slate-300">{{ t("customerLeadPage.reserveText") }}</p>
          </article>
          <article class="ui-admin-subcard">
            <p class="ui-kicker">{{ t("customerLeadPage.trust") }}</p>
            <p class="mt-1 text-sm text-slate-300">{{ t("customerLeadPage.googleReviewsText") }}</p>
          </article>
        </div>
      </article>
    </section>

    <section class="ui-glass ui-reveal p-4 md:p-5" style="--ui-delay: 120ms">
      <div class="grid gap-5 md:grid-cols-[0.92fr,1.08fr]">
        <div class="space-y-3">
          <h2 class="text-xl font-semibold text-white">{{ t("customerLeadPage.helpTitle") }}</h2>
          <p class="text-sm text-slate-300">{{ t("customerLeadPage.helpText") }}</p>
          <div class="grid gap-3 sm:grid-cols-2 md:grid-cols-1">
            <article class="ui-admin-subcard">
              <p class="ui-stat-label">{{ t("customerLeadPage.response") }}</p>
              <p class="mt-2 text-base font-semibold text-white">{{ t("customerLeadPage.responseValue") }}</p>
            </article>
            <article class="ui-admin-subcard">
              <p class="ui-stat-label">{{ t("customerLeadPage.quickContact") }}</p>
              <p class="mt-2 text-sm text-slate-200">
                {{ whatsappHref ? t("customerLeadPage.whatsappNow") : phoneHref ? t("customerLeadPage.callNow") : t("customerLeadPage.directBooking") }}
              </p>
            </article>
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
          <a
            v-if="reservationUrl"
            :href="reservationUrl"
            target="_blank"
            rel="noopener noreferrer"
            class="inline-flex text-sm text-[var(--color-secondary)] hover:underline"
            @click="trackContactClick('reservation_url')"
          >
            {{ t("customerLeadPage.directBooking") }}
          </a>
        </div>

        <form class="space-y-3 rounded-[1.4rem] border border-slate-800/70 bg-slate-950/35 p-4" @submit.prevent="submitLead">
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
import { useMenuStore } from "../stores/menu";
import { useTenantStore } from "../stores/tenant";

const tenant = useTenantStore();
const menu = useMenuStore();
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
const menuCategories = computed(() => (Array.isArray(menu.categories) ? menu.categories : []));
const categoriesCount = computed(() => menuCategories.value.length);
const dishesCount = computed(() => menuCategories.value.reduce((sum, cat) => sum + Number(cat?.dishes?.length || 0), 0));
const orderingModeLabel = computed(() => {
  const mode = String(tenant.entitlements?.ordering_mode || "browse").toLowerCase();
  if (mode === "checkout") return t("customerLeadPage.checkout");
  if (mode === "whatsapp") return t("customerLeadPage.whatsapp");
  return t("customerLeadPage.browseOnly");
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
  const text = encodeURIComponent(t("customerLeadPage.moreInfoMessage", { tenant: tenantName.value }));
  return `https://wa.me/${normalized}?text=${text}`;
});
const featuredCategories = computed(() =>
  menuCategories.value
    .slice()
    .sort((a, b) => Number(b?.dishes?.length || 0) - Number(a?.dishes?.length || 0))
    .slice(0, 4)
    .map((category) => ({
      slug: String(category?.slug || "").trim(),
      name: String(category?.name || "").trim() || tenantName.value,
      image: String(category?.image_url || "").trim(),
      count: Number(category?.dishes?.length || 0),
    }))
    .filter((category) => category.slug)
);
const socialLinks = computed(() =>
  [
    { key: "instagram", label: "Instagram", url: String(profile.value?.instagram_url || "").trim() },
    { key: "facebook", label: "Facebook", url: String(profile.value?.facebook_url || "").trim() },
    { key: "tiktok", label: "TikTok", url: String(profile.value?.tiktok_url || "").trim() },
  ].filter((item) => Boolean(item.url))
);
const visitJourney = computed(() => [
  {
    label: "01",
    title: t("customerLeadPage.browseTitle"),
    text: t("customerLeadPage.browseText"),
  },
  {
    label: "02",
    title: t("customerLeadPage.reserveTitle"),
    text: t("customerLeadPage.reserveText"),
  },
  {
    label: "03",
    title: t("customerLeadPage.googleReviews"),
    text: t("customerLeadPage.googleReviewsText"),
  },
]);

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
  if (!menuCategories.value.length) {
    await menu.fetchCategories();
  }
  trackEvent("customer_info_view", { source: "customer_landing_info" }, { onceKey: "customer:landing" });
});
</script>
