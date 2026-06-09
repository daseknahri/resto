<template>
  <div class="min-w-0 space-y-3 px-3 py-2 pb-28 sm:space-y-4 sm:px-4 sm:py-4 sm:pb-8 ui-safe-bottom">
    <div class="grid gap-3 xl:grid-cols-[minmax(0,1fr),340px]">
      <div class="min-w-0 space-y-3 sm:space-y-4">
        <header class="ui-hero-stage ui-reveal overflow-hidden p-0">
          <div class="relative min-h-[188px] overflow-hidden md:min-h-[224px]">
            <div class="absolute inset-0 bg-gradient-to-br from-amber-500/12 via-slate-950/60 to-teal-500/14"></div>
            <div class="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(245,158,11,0.18),transparent_24%),radial-gradient(circle_at_top_right,rgba(20,184,166,0.14),transparent_22%)]"></div>

            <div class="relative flex min-h-[188px] flex-col justify-end gap-2.5 p-3 md:min-h-[224px] md:gap-3 md:p-5">
              <div class="space-y-1.5">
                <p class="ui-kicker">{{ t("reservationPage.kicker") }}</p>
                <h1 class="ui-display text-2xl font-semibold tracking-tight text-white md:text-4xl">{{ t("reservationPage.title") }}</h1>
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

        <section class="ui-glass ui-reveal p-3 md:p-5" style="--ui-delay: 130ms">
          <div class="grid gap-3 md:grid-cols-2 md:gap-4">
            <label class="space-y-1 text-sm text-slate-200">
              {{ t("common.name") }}
              <input
                v-model.trim="form.name"
                type="text"
                class="ui-input"
                :class="fieldClass('name')"
                autocomplete="name"
                :aria-invalid="errors.name ? 'true' : undefined"
                aria-describedby="res-name-error"
                aria-required="true"
                @input="clearError('name')"
              />
              <p v-if="errors.name" id="res-name-error" role="alert" class="text-xs text-red-300">{{ errors.name }}</p>
            </label>
            <label class="space-y-1 text-sm text-slate-200">
              {{ t("common.phone") }}
              <input
                v-model.trim="form.phone"
                type="tel"
                class="ui-input"
                :class="fieldClass('phone')"
                placeholder="+212..."
                inputmode="tel"
                autocomplete="tel"
                :aria-invalid="errors.phone ? 'true' : undefined"
                aria-describedby="res-phone-error"
                aria-required="true"
                @input="clearError('phone')"
              />
              <p v-if="errors.phone" id="res-phone-error" role="alert" class="text-xs text-red-300">{{ errors.phone }}</p>
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
                spellcheck="false"
                :aria-invalid="errors.email ? 'true' : undefined"
                aria-describedby="res-email-error"
                @input="clearError('email')"
              />
              <p v-if="errors.email" id="res-email-error" role="alert" class="text-xs text-red-300">{{ errors.email }}</p>
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
                :aria-invalid="errors.party_size ? 'true' : undefined"
                aria-describedby="res-party-error"
                aria-required="true"
                @input="clearError('party_size')"
              />
              <p v-if="errors.party_size" id="res-party-error" role="alert" class="text-xs text-red-300">{{ errors.party_size }}</p>
            </label>
          </div>

          <div class="mt-4 space-y-2">
            <p class="ui-kicker">{{ t("reservationPage.quickSize") }}</p>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="size in [2, 4, 6, 8]"
                :key="size"
                class="ui-pill-nav"
                :class="Number(form.party_size) === size ? 'border-[var(--color-secondary)] bg-[var(--color-secondary)]/10 text-[var(--color-secondary)]' : ''"
                :aria-pressed="Number(form.party_size) === size"
                @click="setPartySize(size)"
              >
                {{ t("reservationPage.guestCount", { count: size }) }}
              </button>
            </div>
          </div>

          <div class="mt-4 grid gap-3 lg:grid-cols-[minmax(0,1fr),220px] lg:gap-4">
            <div class="grid gap-3 md:grid-cols-2 md:gap-4">
              <label class="space-y-1 text-sm text-slate-200">
                {{ t("reservationPage.preferredDate") }}
                <input v-model="form.date" type="date" class="ui-input" @change="onDateChange" />
              </label>
              <label class="space-y-1 text-sm text-slate-200">
                {{ t("reservationPage.preferredTime") }}
                <input v-model="form.time" type="time" class="ui-input" />
              </label>
            </div>

            <div class="ui-panel p-3">
              <div class="flex items-center justify-between gap-2">
                <p class="ui-kicker">{{ t("reservationPage.quickTimesKicker") }}</p>
                <span
                  v-if="availabilityLoading"
                  role="status"
                  :aria-label="t('reservationPage.slotAvailabilityTitle')"
                  class="animate-pulse text-[10px] text-slate-500"
                >…</span>
              </div>
              <div class="mt-3 flex flex-wrap gap-2">
                <button
                  v-for="slot in quickTimes"
                  :key="slot"
                  class="ui-press relative flex flex-col items-center rounded-xl border px-2.5 py-2 text-xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/60 disabled:cursor-not-allowed"
                  :class="slotButtonClass(slot)"
                  :aria-pressed="form.time === slot"
                  :disabled="isSlotFull(slot)"
                  :aria-disabled="isSlotFull(slot) || undefined"
                  @click="!isSlotFull(slot) && (form.time = slot)"
                >
                  <span class="font-medium">{{ slot }}</span>
                  <span v-if="capacityEnabled && form.date" class="mt-0.5 text-[10px] leading-none" :class="isSlotFull(slot) ? 'text-red-400' : 'text-emerald-400/80'">
                    {{ slotAvailabilityLabel(slot) }}
                  </span>
                </button>
              </div>
            </div>
          </div>

          <label class="mt-4 block space-y-1 text-sm text-slate-200">
            {{ t("common.notes") }}
            <textarea
              v-model.trim="form.note"
              rows="3"
              class="ui-textarea"
              :placeholder="t('reservationPage.notesPlaceholder')"
            ></textarea>
          </label>

          <input v-model="form.hp" type="text" class="hidden" autocomplete="off" tabindex="-1" aria-hidden="true" />

          <!-- Fully-booked state with waitlist offer -->
          <div
            v-if="lead.fullyBooked && !waitlistSubmitted"
            class="ui-reveal mt-4 space-y-3 rounded-2xl border border-amber-500/30 bg-amber-500/8 p-4"
            style="--ui-delay: 60ms"
          >
            <div class="space-y-1">
              <p class="text-sm font-semibold text-amber-200">{{ t("reservationPage.fullyBookedTitle") }}</p>
              <p class="text-xs text-amber-300/80">{{ t("reservationPage.fullyBookedHint") }}</p>
            </div>
            <div v-if="!showWaitlistForm" class="flex flex-wrap gap-2">
              <button
                class="ui-press inline-flex items-center rounded-full border border-amber-500/50 bg-amber-500/15 px-4 py-2 text-xs font-medium text-amber-200 transition-colors hover:bg-amber-500/25 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/50 ui-touch-target"
                @click="showWaitlistForm = true"
              >
                {{ t("reservationPage.joinWaitlist") }}
              </button>
              <button
                class="ui-btn-outline ui-press px-4 py-2 text-xs"
                @click="lead.$patch({ fullyBooked: false })"
              >
                {{ t("reservationPage.backToForm") }}
              </button>
            </div>
            <div v-else class="space-y-3">
              <p class="text-xs font-medium text-amber-100">{{ t("reservationPage.waitlistFormHint") }}</p>
              <div class="grid gap-2 sm:grid-cols-2">
                <input v-model.trim="waitlistForm.name" type="text" autocomplete="name" :placeholder="t('common.name')" :aria-label="t('common.name')" class="ui-input text-sm" />
                <input v-model.trim="waitlistForm.phone" type="tel" inputmode="tel" autocomplete="tel" :placeholder="t('common.phone')" :aria-label="t('common.phone')" class="ui-input text-sm" />
              </div>
              <input v-model.trim="waitlistForm.email" type="email" autocomplete="email" inputmode="email" spellcheck="false" :placeholder="t('common.email')" :aria-label="t('common.email')" class="ui-input text-sm" />
              <div class="flex flex-wrap gap-2">
                <button
                  class="ui-press inline-flex items-center gap-1.5 rounded-full border border-amber-500/50 bg-amber-500/15 px-4 py-2 text-xs font-medium text-amber-200 transition-colors hover:bg-amber-500/25 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/50 disabled:opacity-60 ui-touch-target"
                  :disabled="joiningWaitlist"
                  :aria-busy="joiningWaitlist"
                  @click="joinWaitlist"
                >
                  <svg v-if="joiningWaitlist" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3 w-3 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
                  {{ joiningWaitlist ? t("reservationPage.waitlistSubmitting") : t("reservationPage.waitlistSubmit") }}
                </button>
                <button class="ui-btn-outline ui-press px-4 py-2 text-xs" @click="showWaitlistForm = false">
                  {{ t("common.cancel") }}
                </button>
              </div>
            </div>
          </div>

          <!-- Waitlist success -->
          <div
            v-if="waitlistSubmitted"
            role="status"
            class="ui-reveal mt-4 flex items-start gap-2 rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-100"
          >
            <AppIcon name="check" class="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" aria-hidden="true" />
            <span>{{ t("reservationPage.waitlistSuccess") }}</span>
          </div>

          <div v-if="!lead.fullyBooked" class="mt-4 flex flex-wrap items-center gap-3">
            <button
              type="button"
              class="ui-btn-primary ui-touch-target inline-flex items-center gap-2 disabled:cursor-not-allowed disabled:opacity-65"
              :disabled="lead.submitting || submitted"
              :aria-busy="lead.submitting"
              @click="submitReservation"
            >
              <svg v-if="lead.submitting" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-4 w-4 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
              <AppIcon v-else name="calendar" class="h-4 w-4 shrink-0" aria-hidden="true" />
              {{ lead.submitting ? t("reservationPage.sending") : submitted ? t("reservationPage.requestSent") : t("reservationPage.submitReservation") }}
            </button>
            <div v-if="lead.error" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
              <AppIcon name="info" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" aria-hidden="true" />
              <p class="flex-1 text-sm text-red-300">{{ lead.error }}</p>
            </div>
          </div>

          <div
            v-if="submitted"
            role="status"
            class="ui-reveal mt-4 flex items-start gap-2 rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-100"
          >
            <AppIcon name="check" class="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" aria-hidden="true" />
            <span>{{ t("reservationPage.reservationReceived") }}</span>
          </div>
        </section>
      </div>

      <aside class="min-w-0 space-y-3 sm:space-y-4">
        <section class="ui-command-deck ui-reveal space-y-4 p-3 lg:sticky lg:top-24 lg:p-4" style="--ui-delay: 80ms">

          <!-- Live booking summary -->
          <div class="space-y-1.5">
            <p class="ui-kicker">{{ t("reservationPage.bookingSummary") }}</p>
            <div class="mt-2 space-y-1.5 text-sm">
              <div class="flex items-center gap-2 text-slate-300">
                <AppIcon name="user" class="h-3.5 w-3.5 shrink-0 text-slate-500" aria-hidden="true" />
                <span class="min-w-0 truncate">{{ form.name || '—' }}</span>
              </div>
              <div class="flex items-center gap-2 text-slate-300">
                <AppIcon name="menu" class="h-3.5 w-3.5 shrink-0 text-slate-500" aria-hidden="true" />
                <span>{{ form.party_size ? t("reservationPage.guestCount", { count: form.party_size }) : '—' }}</span>
              </div>
              <div class="flex items-center gap-2 text-slate-300">
                <AppIcon name="calendar" class="h-3.5 w-3.5 shrink-0 text-slate-500" aria-hidden="true" />
                <span class="min-w-0 truncate tabular-nums">{{ form.date || '—' }}{{ form.time ? ' · ' + form.time : '' }}</span>
              </div>
            </div>
          </div>

          <div class="border-t border-slate-800/60" />

          <!-- Contact options -->
          <div v-if="phoneHref || whatsappHref" class="space-y-2">
            <p class="ui-kicker">{{ t("reservationPage.contactSupport") }}</p>
            <div class="grid gap-2 sm:grid-cols-2 xl:grid-cols-1">
              <a
                v-if="phoneHref"
                :href="phoneHref"
                :aria-label="t('reservationPage.callNow') + (phoneRaw ? ' ' + phoneRaw : '')"
                class="ui-orbit-card ui-surface-lift block p-3 transition hover:border-[var(--color-secondary)]/70"
                @click="trackContactClick('phone_call')"
              >
                <AppIcon name="phone" class="h-4 w-4 text-slate-200" aria-hidden="true" />
                <p class="ui-kicker mt-1">{{ t("reservationPage.phoneSupport") }}</p>
                <p class="text-sm font-semibold text-white">{{ t("reservationPage.callNow") }}</p>
              </a>
              <a
                v-if="whatsappHref"
                :href="whatsappHref"
                target="_blank"
                rel="noopener noreferrer"
                :aria-label="t('reservationPage.whatsappMessage') + (whatsappRaw ? ' ' + whatsappRaw : '')"
                class="ui-orbit-card ui-surface-lift block p-3 transition hover:border-[var(--color-secondary)]/70"
                @click="trackContactClick('whatsapp_contact')"
              >
                <AppIcon name="chat" class="h-4 w-4 text-slate-200" aria-hidden="true" />
                <p class="ui-kicker mt-1">{{ t("reservationPage.quickConfirm") }}</p>
                <p class="text-sm font-semibold text-white">{{ t("reservationPage.whatsappMessage") }}</p>
              </a>
            </div>
          </div>

          <!-- External booking platform (shown once, only when set) -->
          <div v-if="reservationUrl" class="ui-panel space-y-2 p-3">
            <p class="text-xs text-slate-400">{{ t("reservationPage.directBookingHint") }}</p>
            <a
              :href="reservationUrl"
              target="_blank"
              rel="noopener noreferrer"
              class="ui-btn-outline w-full justify-center text-sm"
              @click="trackContactClick('reservation_url')"
            >
              <AppIcon name="link" class="h-3.5 w-3.5" />
              {{ t("reservationPage.bookDirectly") }}
            </a>
          </div>
        </section>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import AppIcon from "../components/AppIcon.vue";
import { useI18n } from "../composables/useI18n";
import { trackEvent } from "../lib/analytics";
import api from "../lib/api";
import { useCartStore } from "../stores/cart";
import { useLeadStore } from "../stores/lead";
import { useCustomerStore } from "../stores/customer";
import { useTenantStore } from "../stores/tenant";
import { useToastStore } from "../stores/toast";

const tenant = useTenantStore();
const lead = useLeadStore();
const customerStore = useCustomerStore();
const cart = useCartStore();
const toast = useToastStore();
const submitted = ref(false);
const meta = computed(() => tenant.resolvedMeta || null);
const { t } = useI18n();
const quickTimes = ["12:00", "13:00", "14:00", "19:00", "20:00", "21:00"];

// ── Availability ─────────────────────────────────────────────────────────────
const availabilityLoading = ref(false);
const availabilitySlots = ref([]); // [{ time, datetime, used, max, available, full }]
const capacityEnabled = computed(() => {
  const p = meta.value?.profile;
  return Boolean(p?.max_covers_per_slot && Number(p.max_covers_per_slot) > 0);
});

const fetchAvailability = async (date) => {
  if (!date || !capacityEnabled.value) {
    availabilitySlots.value = [];
    return;
  }
  availabilityLoading.value = true;
  try {
    const res = await api.get('/availability/', { params: { date } });
    availabilitySlots.value = Array.isArray(res.data?.slots) ? res.data.slots : [];
  } catch {
    availabilitySlots.value = [];
  } finally {
    availabilityLoading.value = false;
  }
};

const slotDataFor = (timeStr) => {
  return availabilitySlots.value.find((s) => s.time === timeStr) || null;
};

const isSlotFull = (timeStr) => {
  if (!capacityEnabled.value || !form.date) return false;
  const s = slotDataFor(timeStr);
  return s ? s.full : false;
};

const slotAvailabilityLabel = (timeStr) => {
  const s = slotDataFor(timeStr);
  if (!s) return t('reservationPage.slotUnlimited');
  if (s.full) return t('reservationPage.slotFull');
  if (s.available !== null && s.available <= 3) return t('reservationPage.slotAvailableCount', { available: s.available });
  return t('reservationPage.slotUnlimited');
};

const slotButtonClass = (slot) => {
  const full = isSlotFull(slot);
  const active = form.time === slot;
  if (full) return 'border-red-500/30 bg-red-500/8 text-red-400 opacity-70 cursor-not-allowed';
  if (active) return 'border-[var(--color-secondary)] bg-[var(--color-secondary)]/10 text-[var(--color-secondary)]';
  return 'border-slate-700 bg-slate-900/50 text-slate-300 hover:border-slate-500 hover:text-slate-200';
};

const onDateChange = () => {
  fetchAvailability(form.date);
};

// ── Waitlist ──────────────────────────────────────────────────────────────────
const showWaitlistForm = ref(false);
const joiningWaitlist = ref(false);
const waitlistSubmitted = ref(false);
const waitlistForm = reactive({ name: '', phone: '', email: '' });

const joinWaitlist = async () => {
  if (joiningWaitlist.value) return;
  if (!waitlistForm.name || waitlistForm.name.length < 2) {
    toast.show(t('reservationPage.nameError'), 'error');
    return;
  }
  if (!waitlistForm.phone && !waitlistForm.email) {
    toast.show(t('reservationPage.contactRequired'), 'error');
    return;
  }
  joiningWaitlist.value = true;
  try {
    let bookedFor = null;
    if (form.date) {
      const timeStr = form.time || '00:00';
      try { bookedFor = new Date(`${form.date}T${timeStr}`).toISOString(); } catch { bookedFor = null; }
    }
    await api.post('/waitlist/', {
      name: waitlistForm.name,
      phone: waitlistForm.phone,
      email: waitlistForm.email,
      booked_for: bookedFor,
      party_size: Number(form.party_size) || 1,
    });
    waitlistSubmitted.value = true;
    showWaitlistForm.value = false;
  } catch {
    toast.show(t('reservationPage.waitlistFailed'), 'error');
  } finally {
    joiningWaitlist.value = false;
  }
};

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
  lead.$patch({ error: null });
  if (!validate()) return;

  // Combine date + time into an ISO datetime string for booked_for field
  let bookedFor = null;
  if (form.date) {
    const timeStr = form.time || "00:00";
    try {
      bookedFor = new Date(`${form.date}T${timeStr}`).toISOString();
    } catch {
      bookedFor = null;
    }
  }

  await lead.submitLead({
    name: form.name,
    email: form.email,
    phone: form.phone,
    source: "table_reservation",
    notes: reservationNotes(),
    booked_for: bookedFor,
    party_size: Number(form.party_size) || null,
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
  waitlistSubmitted.value = false;
  showWaitlistForm.value = false;
  // Pre-fill from verified customer identity first, then fall back to cart localStorage
  const c = customerStore.customer;
  if (c?.name && !form.name) form.name = c.name;
  if (c?.phone && !form.phone) form.phone = c.phone;
  if (c?.email && !form.email) form.email = c.email;
  if (cart.customerName && !form.name) form.name = cart.customerName;
  if (cart.customerPhone && !form.phone) form.phone = cart.customerPhone;
  // Pre-fill waitlist form too
  waitlistForm.name = form.name || '';
  waitlistForm.phone = form.phone || '';
  waitlistForm.email = form.email || '';
  // Fetch availability if date is already set
  if (form.date) fetchAvailability(form.date);
});

// Pre-fill waitlist form when main form changes
watch(() => form.name, (v) => { if (v && !waitlistForm.name) waitlistForm.name = v; });
watch(() => form.phone, (v) => { if (v && !waitlistForm.phone) waitlistForm.phone = v; });
watch(() => form.email, (v) => { if (v && !waitlistForm.email) waitlistForm.email = v; });
</script>
