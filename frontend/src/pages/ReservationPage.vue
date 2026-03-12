<template>
  <div class="space-y-4 px-4 py-4 pb-32 sm:pb-8 ui-safe-bottom">
    <div class="grid gap-4 xl:grid-cols-[minmax(0,1fr),340px]">
      <div class="space-y-4">
        <header class="ui-hero-stage ui-reveal overflow-hidden p-0">
          <div class="relative min-h-[224px] overflow-hidden">
            <div class="absolute inset-0 bg-gradient-to-br from-amber-500/12 via-slate-950/60 to-teal-500/14"></div>
            <div class="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(245,158,11,0.18),transparent_24%),radial-gradient(circle_at_top_right,rgba(20,184,166,0.14),transparent_22%)]"></div>

            <div class="relative flex min-h-[224px] flex-col justify-end gap-3 p-4 md:p-5">
              <div class="flex flex-wrap gap-2">
                <span class="ui-chip-strong">{{ cart.tableLabel ? t("common.reserve") : t("reservationPage.directBooking") }}</span>
                <span class="ui-chip">{{ t("reservationPage.partySize") }} / {{ form.party_size }}</span>
                <span v-if="form.date" class="ui-chip">{{ form.date }}</span>
              </div>

              <div class="space-y-1.5">
                <p class="ui-kicker">{{ t("reservationPage.kicker") }}</p>
                <h1 class="ui-display text-3xl font-semibold tracking-tight text-white md:text-4xl">{{ t("reservationPage.title") }}</h1>
                <p class="max-w-2xl text-sm text-slate-200 md:text-base">{{ t("reservationPage.description") }}</p>
              </div>

              <p class="text-xs text-slate-300/90">
                {{
                  cart.tableLabel
                    ? t("reservationPage.tableDetected", { table: cart.tableLabel })
                    : t("reservationPage.tableMissing")
                }}
              </p>
            </div>
          </div>
        </header>

        <section class="grid gap-3 sm:grid-cols-3">
          <article
            v-for="(item, index) in reservationJourney"
            :key="item.label"
            class="ui-story-card ui-surface-lift ui-reveal p-4"
            :style="{ '--ui-delay': item.delay }"
          >
            <div class="flex items-start justify-between gap-3">
              <div>
                <p class="ui-kicker">{{ item.label }}</p>
                <p class="mt-1 text-lg font-semibold text-white">{{ item.title }}</p>
              </div>
              <span class="ui-step-badge">{{ String(index + 1).padStart(2, "0") }}</span>
            </div>
            <p class="mt-3 text-sm text-slate-300">{{ item.text }}</p>
          </article>
        </section>

        <section class="ui-state-strip ui-reveal" style="--ui-delay: 115ms">
          <div class="relative z-[1] grid gap-2 md:grid-cols-[minmax(0,1fr),auto,auto,auto] md:items-center">
            <div class="min-w-0">
              <p class="ui-kicker">{{ t("reservationPage.submitReservation") }}</p>
              <p class="truncate text-sm font-medium text-white">{{ reservationStateLabel }}</p>
              <p class="mt-1 text-xs text-slate-400">{{ reservationModeLabel }}</p>
            </div>
            <span class="ui-state-chip" :data-active="reservationReadyCount === reservationChecklist.length">
              {{ reservationReadyCount }}/{{ reservationChecklist.length }}
            </span>
            <span class="ui-state-chip" :data-active="Boolean(cart.tableLabel)">
              {{ cart.tableLabel ? `${t("common.table")} / ${cart.tableLabel}` : t("reservationPage.tableMissing") }}
            </span>
            <span class="ui-state-chip" :data-active="Boolean(form.date && form.time)">
              {{ form.date && form.time ? `${form.date} / ${form.time}` : t("reservationPage.quickConfirm") }}
            </span>
          </div>
        </section>

        <section class="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <article
            v-for="item in reservationChecklist"
            :key="item.key"
            class="ui-readiness-item ui-reveal"
            :style="{ '--ui-delay': item.delay }"
            :data-complete="item.complete"
            :data-warning="!item.complete"
          >
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0">
                <div class="flex items-center gap-2">
                  <span class="ui-readiness-dot"></span>
                  <p class="ui-kicker">{{ item.label }}</p>
                </div>
                <p class="mt-2 text-sm font-medium text-white">{{ item.value }}</p>
              </div>
              <span class="ui-chip text-[10px]">{{ item.complete ? 'OK' : '...' }}</span>
            </div>
          </article>
        </section>

        <section class="ui-glass ui-reveal p-4 md:p-5" style="--ui-delay: 130ms">
          <div class="mb-4 flex flex-wrap gap-2">
            <span class="ui-data-strip">{{ t("reservationPage.partySize") }}: {{ form.party_size }}</span>
            <span v-if="form.date" class="ui-data-strip">{{ form.date }}</span>
            <span v-if="form.time" class="ui-data-strip">{{ form.time }}</span>
            <span class="ui-data-strip">{{ reservationModeLabel }}</span>
            <span class="ui-status-pill">
              <span class="ui-live-dot" :class="reservationStateDotClass"></span>
              {{ reservationStateLabel }}
            </span>
          </div>

          <div class="grid gap-4 md:grid-cols-2">
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
              {{ t("reservationPage.partySize") }}
              <input
                v-model.number="form.party_size"
                type="number"
                min="1"
                class="ui-input"
                :class="fieldClass('party_size')"
                inputmode="numeric"
                @input="clearError('party_size')"
              />
              <p v-if="errors.party_size" class="text-xs text-red-300">{{ errors.party_size }}</p>
            </label>
          </div>

          <div class="mt-5 space-y-2">
            <p class="text-xs uppercase tracking-[0.18em] text-slate-500">{{ t("reservationPage.quickSize") }}</p>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="size in [2, 4, 6, 8]"
                :key="size"
                class="ui-pill-nav"
                :class="Number(form.party_size) === size ? 'border-[var(--color-secondary)] bg-[var(--color-secondary)]/10 text-[var(--color-secondary)]' : ''"
                @click="setPartySize(size)"
              >
                {{ t("reservationPage.guestCount", { count: size }) }}
              </button>
            </div>
          </div>

          <div class="mt-5 grid gap-4 lg:grid-cols-[minmax(0,1fr),220px]">
            <div class="grid gap-4 md:grid-cols-2">
              <label class="space-y-1 text-sm text-slate-200">
                {{ t("reservationPage.preferredDate") }}
                <input v-model="form.date" type="date" class="ui-input" />
              </label>
              <label class="space-y-1 text-sm text-slate-200">
                {{ t("reservationPage.preferredTime") }}
                <input v-model="form.time" type="time" class="ui-input" />
              </label>
            </div>

            <div class="rounded-[1.35rem] border border-slate-800/80 bg-slate-950/45 p-3">
              <p class="ui-kicker">{{ t("reservationPage.preferredTime") }}</p>
              <div class="mt-3 flex flex-wrap gap-2">
                <button
                  v-for="slot in quickTimes"
                  :key="slot"
                  class="ui-pill-nav"
                  :class="form.time === slot ? 'border-[var(--color-secondary)] bg-[var(--color-secondary)]/10 text-[var(--color-secondary)]' : ''"
                  @click="form.time = slot"
                >
                  {{ slot }}
                </button>
              </div>
            </div>
          </div>

          <label class="mt-5 block space-y-1 text-sm text-slate-200">
            {{ t("common.notes") }}
            <textarea
              v-model.trim="form.note"
              rows="3"
              class="ui-textarea"
              :placeholder="t('reservationPage.notesPlaceholder')"
            ></textarea>
          </label>

          <input v-model="form.hp" type="text" class="hidden" autocomplete="off" tabindex="-1" aria-hidden="true" />

          <div class="mt-5 flex flex-wrap items-center gap-3">
            <button
              type="button"
              class="ui-btn-primary ui-touch-target disabled:cursor-not-allowed disabled:opacity-65"
              :disabled="lead.submitting || submitted"
              @click="submitReservation"
            >
              {{ lead.submitting ? t("reservationPage.sending") : submitted ? t("reservationPage.requestSent") : t("reservationPage.submitReservation") }}
            </button>
            <p v-if="lead.error" class="text-sm text-red-300">{{ lead.error }}</p>
          </div>

          <div
            v-if="submitted"
            class="mt-4 rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-100"
          >
            {{ t("reservationPage.reservationReceived") }}
          </div>
          <button
            v-if="submitted"
            type="button"
            class="ui-btn-primary mt-3 w-full justify-center opacity-90 sm:w-auto"
            disabled
          >
            {{ t("reservationPage.contactSoon") }}
          </button>

          <div class="mt-5 grid gap-3 md:grid-cols-3">
            <article class="ui-admin-subcard">
              <p class="ui-kicker">{{ t("customerLeadPage.response") }}</p>
              <p class="mt-2 text-sm font-medium text-white">{{ t("customerLeadPage.responseValue") }}</p>
            </article>
            <article class="ui-admin-subcard">
              <p class="ui-kicker">{{ t("reservationPage.quickConfirm") }}</p>
              <p class="mt-2 text-sm font-medium text-white">{{ form.time || "--" }}</p>
            </article>
            <article class="ui-admin-subcard">
              <p class="ui-kicker">{{ t("reservationPage.partySize") }}</p>
              <p class="mt-2 text-sm font-medium text-white">{{ form.party_size }}</p>
            </article>
          </div>
        </section>
      </div>

      <aside class="space-y-4">
        <section class="ui-command-deck ui-reveal p-4 lg:sticky lg:top-24" style="--ui-delay: 80ms">
          <div class="space-y-1.5">
            <p class="ui-kicker">{{ t("customerLeadPage.response") }}</p>
            <h2 class="text-xl font-semibold text-white">{{ t("customerLeadPage.responseValue") }}</h2>
            <p class="text-sm text-slate-300">{{ t("reservationPage.description") }}</p>
          </div>

          <div class="mt-4 space-y-2">
            <div class="ui-admin-subcard flex items-center justify-between gap-3">
              <span class="ui-stat-label">{{ t("common.reserve") }}</span>
              <span class="text-sm font-medium text-white">{{ cart.tableLabel || t("reservationPage.directBooking") }}</span>
            </div>
            <div class="ui-admin-subcard flex items-center justify-between gap-3">
              <span class="ui-stat-label">{{ t("reservationPage.partySize") }}</span>
              <span class="text-sm font-medium text-white">{{ form.party_size }}</span>
            </div>
            <div class="ui-admin-subcard flex items-center justify-between gap-3">
              <span class="ui-stat-label">{{ t("customerLayout.navCart") }}</span>
              <span class="text-sm font-medium text-white">{{ cart.count }}</span>
            </div>
          </div>

          <div class="mt-4 rounded-[1.35rem] border border-slate-800/80 bg-slate-950/45 p-3">
            <p class="ui-kicker">{{ t("reservationPage.quickConfirm") }}</p>
            <div class="mt-3 space-y-2 text-sm text-slate-300">
              <p>{{ t("reservationPage.preferredDate") }}: <span class="font-medium text-slate-100">{{ form.date || "--" }}</span></p>
              <p>{{ t("reservationPage.preferredTime") }}: <span class="font-medium text-slate-100">{{ form.time || "--" }}</span></p>
              <p>{{ t("reservationPage.partySize") }}: <span class="font-medium text-slate-100">{{ form.party_size }}</span></p>
            </div>
          </div>

          <div class="mt-4 space-y-2">
            <article class="ui-focus-card space-y-3 p-3">
              <div class="flex items-start justify-between gap-3">
                <div class="space-y-1">
                  <p class="ui-kicker">{{ t("reservationPage.submitReservation") }}</p>
                  <h3 class="text-base font-semibold text-white">{{ reservationStateLabel }}</h3>
                </div>
                <span class="ui-chip-strong">{{ reservationReadyCount }}/{{ reservationChecklist.length }}</span>
              </div>
              <div class="grid gap-2">
                <article
                  v-for="item in reservationChecklist"
                  :key="`aside-${item.key}`"
                  class="ui-readiness-item"
                  :data-complete="item.complete"
                  :data-warning="!item.complete"
                >
                  <div class="flex items-start justify-between gap-3">
                    <div class="min-w-0">
                      <div class="flex items-center gap-2">
                        <span class="ui-readiness-dot"></span>
                        <p class="ui-kicker">{{ item.label }}</p>
                      </div>
                      <p class="mt-2 text-sm font-medium text-white">{{ item.value }}</p>
                    </div>
                    <span class="ui-chip text-[10px]">{{ item.complete ? 'OK' : '...' }}</span>
                  </div>
                </article>
              </div>
            </article>
            <article
              v-for="(item, index) in reservationJourney"
              :key="`aside-${item.label}`"
              class="ui-story-card"
            >
              <div class="flex items-start justify-between gap-3">
                <div>
                  <p class="ui-kicker">{{ item.label }}</p>
                  <p class="mt-1 text-sm font-semibold text-white">{{ item.title }}</p>
                </div>
                <span class="ui-step-badge">{{ String(index + 1).padStart(2, "0") }}</span>
              </div>
              <p class="mt-2 text-sm text-slate-300">{{ item.text }}</p>
            </article>
          </div>

          <div class="mt-4 grid gap-3">
            <a
              v-if="phoneHref"
              :href="phoneHref"
              class="ui-orbit-card ui-surface-lift p-4 transition hover:border-[var(--color-secondary)]/70"
              @click="trackContactClick('phone_call')"
            >
              <p class="ui-kicker">{{ t("reservationPage.phoneSupport") }}</p>
              <p class="mt-1 text-lg font-semibold text-white">{{ t("reservationPage.callNow") }}</p>
            </a>
            <a
              v-if="whatsappHref"
              :href="whatsappHref"
              target="_blank"
              rel="noopener noreferrer"
              class="ui-orbit-card ui-surface-lift p-4 transition hover:border-[var(--color-secondary)]/70"
              @click="trackContactClick('whatsapp_contact')"
            >
              <p class="ui-kicker">{{ t("reservationPage.quickConfirm") }}</p>
              <p class="mt-1 text-lg font-semibold text-white">{{ t("reservationPage.whatsappMessage") }}</p>
            </a>
            <a
              v-if="reservationUrl"
              :href="reservationUrl"
              target="_blank"
              rel="noopener noreferrer"
              class="ui-btn-outline justify-center"
              @click="trackContactClick('reservation_url')"
            >
              {{ t("reservationPage.directBooking") }}
            </a>
          </div>
        </section>
      </aside>
    </div>

    <section class="grid gap-3 lg:grid-cols-[0.96fr,1.04fr]">
      <article class="ui-focus-card ui-reveal p-4 md:p-5" style="--ui-delay: 150ms">
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div class="space-y-1">
            <p class="ui-kicker">{{ t("customerLayout.navReserve") }}</p>
            <h2 class="text-xl font-semibold text-white">{{ t("reservationPage.quickConfirm") }}</h2>
          </div>
          <span class="ui-chip-strong">{{ reservationModeLabel }}</span>
        </div>

        <div class="mt-4 grid gap-3 sm:grid-cols-3">
          <RouterLink :to="{ name: 'customer-home' }" class="ui-admin-subcard transition hover:border-[var(--color-secondary)]/70">
            <p class="ui-kicker">{{ t("customerLayout.navInfo") }}</p>
            <p class="mt-1 text-sm font-semibold text-white">{{ t("customerLeadPage.helpTitle") }}</p>
          </RouterLink>
          <RouterLink :to="{ name: 'menu' }" class="ui-admin-subcard transition hover:border-[var(--color-secondary)]/70">
            <p class="ui-kicker">{{ t("customerLayout.navMenu") }}</p>
            <p class="mt-1 text-sm font-semibold text-white">{{ t("customerLeadPage.browseTitle") }}</p>
          </RouterLink>
          <RouterLink :to="{ name: 'cart' }" class="ui-admin-subcard transition hover:border-[var(--color-secondary)]/70">
            <p class="ui-kicker">{{ t("customerLayout.navCart") }}</p>
            <p class="mt-1 text-sm font-semibold text-white">{{ t("cartPage.kicker") }}</p>
          </RouterLink>
        </div>
      </article>

      <article class="ui-section-band ui-reveal p-4 md:p-5" style="--ui-delay: 180ms">
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div class="space-y-1">
            <p class="ui-kicker">{{ t("reservationPage.submitReservation") }}</p>
            <h2 class="text-xl font-semibold text-white">{{ t("customerLeadPage.responseValue") }}</h2>
          </div>
          <span class="ui-data-strip">{{ form.party_size }} {{ t("reservationPage.guestCount", { count: form.party_size }) }}</span>
        </div>

        <div class="mt-4 grid gap-3 md:grid-cols-3">
          <article class="ui-admin-subcard">
            <p class="ui-kicker">{{ t("reservationPage.preferredDate") }}</p>
            <p class="mt-2 text-sm text-slate-300">{{ form.date || "--" }}</p>
          </article>
          <article class="ui-admin-subcard">
            <p class="ui-kicker">{{ t("reservationPage.preferredTime") }}</p>
            <p class="mt-2 text-sm text-slate-300">{{ form.time || "--" }}</p>
          </article>
          <article class="ui-admin-subcard">
            <p class="ui-kicker">{{ t("reservationPage.partySize") }}</p>
            <p class="mt-2 text-sm text-slate-300">{{ form.party_size }}</p>
          </article>
        </div>
      </article>
    </section>

    <div
      v-if="!submitted"
      class="fixed bottom-20 left-3 right-3 z-20 rounded-2xl border border-slate-700/80 bg-slate-950/92 p-3 shadow-xl shadow-black/40 backdrop-blur sm:hidden"
    >
      <div class="mb-3 flex items-center justify-between gap-3 text-xs text-slate-300">
        <span class="ui-state-chip" :data-active="reservationReadyCount === reservationChecklist.length">
          {{ reservationReadyCount }}/{{ reservationChecklist.length }}
        </span>
        <span class="truncate text-right">{{ reservationStateLabel }}</span>
      </div>
      <button
        type="button"
        class="ui-btn-primary w-full justify-center"
        :disabled="lead.submitting"
        @click="submitReservation"
      >
        {{ lead.submitting ? t("reservationPage.sending") : t("reservationPage.submitReservation") }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useI18n } from "../composables/useI18n";
import { trackEvent } from "../lib/analytics";
import { useCartStore } from "../stores/cart";
import { useLeadStore } from "../stores/lead";
import { useTenantStore } from "../stores/tenant";

const tenant = useTenantStore();
const lead = useLeadStore();
const cart = useCartStore();
const submitted = ref(false);
const meta = computed(() => tenant.resolvedMeta || null);
const { t } = useI18n();
const quickTimes = ["12:30", "14:00", "19:30", "21:00"];

const form = reactive({
  name: "",
  phone: "",
  email: "",
  party_size: 2,
  date: "",
  time: "",
  note: "",
  hp: "",
});

const errors = reactive({
  name: "",
  phone: "",
  email: "",
  party_size: "",
});

const profile = computed(() => meta.value?.profile || {});
const reservationUrl = computed(() => String(profile.value?.reservation_url || "").trim());
const reservationModeLabel = computed(() => (reservationUrl.value ? t("reservationPage.directBooking") : t("customerLeadPage.responseValue")));
const reservationJourney = computed(() => [
  {
    label: "01",
    title: t("reservationPage.submitReservation"),
    text: t("reservationPage.description"),
    delay: "70ms",
  },
  {
    label: "02",
    title: t("reservationPage.quickConfirm"),
    text: cart.tableLabel ? t("reservationPage.tableDetected", { table: cart.tableLabel }) : t("reservationPage.tableMissing"),
    delay: "100ms",
  },
  {
    label: "03",
    title: t("customerLeadPage.responseValue"),
    text: t("reservationPage.contactSoon"),
    delay: "130ms",
  },
]);
const hasReservationContact = computed(() => Boolean(form.phone || form.email));
const reservationChecklist = computed(() => [
  {
    key: "name",
    label: t("common.name"),
    value: form.name || t("reservationPage.nameError"),
    complete: Boolean(form.name && form.name.trim().length >= 2),
    delay: "120ms",
  },
  {
    key: "contact",
    label: t("common.phone"),
    value: form.phone || form.email || t("reservationPage.contactRequired"),
    complete: hasReservationContact.value,
    delay: "140ms",
  },
  {
    key: "party",
    label: t("reservationPage.partySize"),
    value: t("reservationPage.guestCount", { count: form.party_size || 0 }),
    complete: Number(form.party_size || 0) >= 1,
    delay: "160ms",
  },
  {
    key: "slot",
    label: t("reservationPage.quickConfirm"),
    value:
      form.date && form.time
        ? `${form.date} - ${form.time}`
        : form.date || form.time || t("reservationPage.directBooking"),
    complete: Boolean(form.date && form.time),
    delay: "180ms",
  },
]);
const reservationReadyCount = computed(
  () => reservationChecklist.value.filter((item) => item.complete).length
);
const reservationStateLabel = computed(() => {
  if (submitted.value) return t("reservationPage.requestSent");
  if (reservationReadyCount.value === reservationChecklist.value.length)
    return t("reservationPage.submitReservation");
  return t("reservationPage.contactRequired");
});
const reservationStateDotClass = computed(() => {
  if (submitted.value) return "bg-emerald-400";
  if (reservationReadyCount.value === reservationChecklist.value.length)
    return "bg-[var(--color-secondary)]";
  return "bg-amber-400";
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
  const text = encodeURIComponent(
    t("reservationPage.whatsappTemplate", {
      tenant: meta.value?.name || t("customerLayout.fallbackTenantName"),
    })
  );
  return `https://wa.me/${normalized}?text=${text}`;
});

const fieldClass = (field) => (errors[field] ? "border-red-400" : "border-slate-700");
const clearError = (field) => {
  if (errors[field]) errors[field] = "";
};

const validate = () => {
  errors.name = "";
  errors.phone = "";
  errors.email = "";
  errors.party_size = "";
  let valid = true;

  if (!form.name || form.name.length < 2) {
    errors.name = t("reservationPage.nameError");
    valid = false;
  }
  if (!form.phone && !form.email) {
    errors.phone = t("reservationPage.contactRequired");
    errors.email = t("reservationPage.contactRequired");
    valid = false;
  }
  if (form.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) {
    errors.email = t("reservationPage.invalidEmail");
    valid = false;
  }
  if (Number(form.party_size || 0) < 1) {
    errors.party_size = t("reservationPage.partySizeError");
    valid = false;
  }

  return valid;
};

const setPartySize = (size) => {
  form.party_size = Number(size);
  clearError("party_size");
};

const reservationNotes = () => {
  const pageUrl = typeof window !== "undefined" ? window.location.href : "";
  const lines = [
    t("reservationPage.notesIntro", { tenant: meta.value?.slug || meta.value?.name || t("customerLayout.fallbackTenantName") }),
    cart.tableLabel ? t("reservationPage.tableContextLine", { table: cart.tableLabel }) : "",
    form.party_size ? t("reservationPage.partySizeLine", { count: form.party_size }) : "",
    form.date ? t("reservationPage.preferredDateLine", { date: form.date }) : "",
    form.time ? t("reservationPage.preferredTimeLine", { time: form.time }) : "",
    form.note ? t("reservationPage.customerNoteLine", { note: form.note }) : "",
    pageUrl ? t("reservationPage.pageUrlLine", { url: pageUrl }) : "",
  ].filter(Boolean);
  return lines.join("\n");
};

const submitReservation = async () => {
  if (submitted.value) return;
  if (!validate()) return;
  await lead.submitLead({
    name: form.name,
    email: form.email,
    phone: form.phone,
    source: "table_reservation",
    notes: reservationNotes(),
    hp: form.hp,
  });
  if (lead.success) {
    submitted.value = true;
    trackEvent("reservation_submit", { source: "customer_reservation_page" });
  }
};

const trackContactClick = (target) => {
  trackEvent("contact_click", {
    source: "customer_reservation",
    metadata: { target: String(target || "").slice(0, 60) },
  });
};

onMounted(() => {
  lead.reset();
  submitted.value = false;
  if (cart.customerName && !form.name) form.name = cart.customerName;
  if (cart.customerPhone && !form.phone) form.phone = cart.customerPhone;
});
</script>
