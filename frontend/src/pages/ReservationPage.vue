<template>
  <div class="space-y-4 px-4 py-4 pb-32 sm:pb-8 ui-safe-bottom">
    <header class="ui-glass ui-reveal p-4 md:p-5">
      <div class="space-y-1.5">
        <p class="ui-kicker">Reservation</p>
        <h1 class="ui-display text-2xl font-semibold tracking-tight text-white md:text-3xl">Reserve your table</h1>
        <p class="max-w-2xl text-sm text-slate-300">
          Submit your reservation request and our team will confirm with you.
        </p>
      </div>
      <div class="mt-3 ui-divider"></div>
      <p class="mt-2 text-xs text-slate-400">
        {{
          cart.tableLabel
            ? `Table context detected: ${cart.tableLabel}.`
            : "No table context detected. Add it if needed."
        }}
      </p>
      <a
        v-if="reservationUrl"
        :href="reservationUrl"
        target="_blank"
        rel="noopener noreferrer"
        class="mt-2 inline-flex text-xs text-[var(--color-secondary)] hover:underline"
        @click="trackContactClick('reservation_url')"
      >
        Prefer direct booking? Open reservation link
      </a>
    </header>

    <section class="grid gap-3 sm:grid-cols-2">
      <a
        v-if="phoneHref"
        :href="phoneHref"
        class="ui-panel ui-surface-lift ui-reveal p-4 transition hover:border-[var(--color-secondary)]/70"
        style="--ui-delay: 70ms"
        @click="trackContactClick('phone_call')"
      >
        <p class="ui-kicker">Phone support</p>
        <p class="mt-1 text-lg font-semibold text-white">Call now</p>
      </a>
      <a
        v-if="whatsappHref"
        :href="whatsappHref"
        target="_blank"
        rel="noopener noreferrer"
        class="ui-panel ui-surface-lift ui-reveal p-4 transition hover:border-[var(--color-secondary)]/70"
        style="--ui-delay: 100ms"
        @click="trackContactClick('whatsapp_contact')"
      >
        <p class="ui-kicker">Quick confirm</p>
        <p class="mt-1 text-lg font-semibold text-white">WhatsApp message</p>
      </a>
    </section>

    <section class="ui-panel ui-reveal p-4 md:p-5" style="--ui-delay: 130ms">
      <div class="grid gap-4 md:grid-cols-2">
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
          Party size
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

      <div class="mt-4 space-y-2">
        <p class="text-xs uppercase tracking-[0.18em] text-slate-500">Quick size</p>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="size in [2, 4, 6, 8]"
            :key="size"
            class="ui-pill-nav"
            :class="Number(form.party_size) === size ? 'border-[var(--color-secondary)] bg-[var(--color-secondary)]/10 text-[var(--color-secondary)]' : ''"
            @click="setPartySize(size)"
          >
            {{ size }} guests
          </button>
        </div>
      </div>

      <div class="mt-4 grid gap-4 md:grid-cols-2">
        <label class="space-y-1 text-sm text-slate-200">
          Preferred date
          <input v-model="form.date" type="date" class="ui-input" />
        </label>
        <label class="space-y-1 text-sm text-slate-200">
          Preferred time
          <input v-model="form.time" type="time" class="ui-input" />
        </label>
      </div>

      <label class="mt-4 block space-y-1 text-sm text-slate-200">
        Notes
        <textarea
          v-model.trim="form.note"
          rows="3"
          class="ui-textarea"
          placeholder="Special request, seating preference..."
        ></textarea>
      </label>

      <input v-model="form.hp" type="text" class="hidden" autocomplete="off" tabindex="-1" aria-hidden="true" />

      <div class="mt-4 flex flex-wrap items-center gap-3">
        <button
          type="button"
          class="ui-btn-primary ui-touch-target disabled:cursor-not-allowed disabled:opacity-65"
          :disabled="lead.submitting || submitted"
          @click="submitReservation"
        >
          {{ lead.submitting ? "Sending..." : submitted ? "Request sent" : "Submit reservation" }}
        </button>
        <p v-if="lead.error" class="text-sm text-red-300">{{ lead.error }}</p>
      </div>

      <div
        v-if="submitted"
        class="mt-4 rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-100"
      >
        Reservation request received. We will contact you.
      </div>
      <button
        v-if="submitted"
        type="button"
        class="ui-btn-primary mt-3 w-full justify-center opacity-90 sm:w-auto"
        disabled
      >
        We will contact you shortly
      </button>
    </section>

    <div
      v-if="!submitted"
      class="fixed bottom-20 left-3 right-3 z-20 rounded-2xl border border-slate-700/80 bg-slate-950/92 p-3 shadow-xl shadow-black/40 backdrop-blur sm:hidden"
    >
      <button
        type="button"
        class="ui-btn-primary w-full justify-center"
        :disabled="lead.submitting"
        @click="submitReservation"
      >
        {{ lead.submitting ? "Sending..." : "Submit reservation" }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { trackEvent } from "../lib/analytics";
import { useCartStore } from "../stores/cart";
import { useLeadStore } from "../stores/lead";
import { useTenantStore } from "../stores/tenant";

const tenant = useTenantStore();
const lead = useLeadStore();
const cart = useCartStore();
const submitted = ref(false);

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

const profile = computed(() => tenant.meta?.profile || {});
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
  const text = encodeURIComponent(`Hi, I'd like to reserve a table at ${tenant.meta?.name || "your restaurant"}.`);
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
  if (Number(form.party_size || 0) < 1) {
    errors.party_size = "Party size must be at least 1.";
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
    `Reservation request for tenant: ${tenant.meta?.slug || "unknown"}`,
    cart.tableLabel ? `Table context: ${cart.tableLabel}` : "",
    form.party_size ? `Party size: ${form.party_size}` : "",
    form.date ? `Preferred date: ${form.date}` : "",
    form.time ? `Preferred time: ${form.time}` : "",
    form.note ? `Customer note: ${form.note}` : "",
    pageUrl ? `Page URL: ${pageUrl}` : "",
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
