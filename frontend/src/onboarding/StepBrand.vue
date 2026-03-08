<template>
  <div class="ui-panel space-y-4 p-5">
    <h2 class="text-xl font-semibold">Brand & Contact</h2>
    <p class="text-sm text-slate-400">{{ introText }}</p>
    <div v-if="isBrowseOnlyPlan" class="rounded-xl border border-sky-500/40 bg-sky-500/10 p-3 text-xs text-sky-100">
      Ordering is currently disabled for this tenant plan. Update plan entitlements to enable WhatsApp or checkout.
    </div>

    <div class="grid sm:grid-cols-2 gap-3">
      <label class="space-y-1 text-sm text-slate-200">
        Tagline
        <input v-model="form.tagline" :class="inputClass('tagline')" @input="clearField('tagline')" />
        <p v-if="fieldError('tagline')" class="text-xs text-red-300">{{ fieldError("tagline") }}</p>
      </label>
      <label class="space-y-1 text-sm text-slate-200">
        Phone
        <input v-model="form.phone" :class="inputClass('phone')" @input="clearField('phone')" />
        <p v-if="fieldError('phone')" class="text-xs text-red-300">{{ fieldError("phone") }}</p>
      </label>
      <label class="space-y-1 text-sm text-slate-200">
        {{ whatsappLabel }}
        <input v-model="form.whatsapp" :class="inputClass('whatsapp')" @input="clearField('whatsapp')" />
        <p v-if="fieldError('whatsapp')" class="text-xs text-red-300">{{ fieldError("whatsapp") }}</p>
        <p v-if="isBrowseOnlyPlan" class="text-xs text-slate-500">Shown as contact only until ordering is enabled on this tenant plan.</p>
      </label>
      <label class="space-y-1 text-sm text-slate-200">
        Address
        <input v-model="form.address" :class="inputClass('address')" @input="clearField('address')" />
        <p v-if="fieldError('address')" class="text-xs text-red-300">{{ fieldError("address") }}</p>
      </label>
    </div>

    <label class="space-y-1 text-sm text-slate-200">
      Description
      <textarea
        v-model="form.description"
        rows="3"
        :class="inputClass('description')"
        @input="clearField('description')"
      ></textarea>
      <p v-if="fieldError('description')" class="text-xs text-red-300">{{ fieldError("description") }}</p>
    </label>

    <div class="grid sm:grid-cols-2 gap-3">
      <label class="space-y-1 text-sm text-slate-200">
        Google Maps URL
        <input v-model="form.google_maps_url" :class="inputClass('google_maps_url')" @input="clearField('google_maps_url')" />
        <p v-if="fieldError('google_maps_url')" class="text-xs text-red-300">{{ fieldError("google_maps_url") }}</p>
      </label>
      <label class="space-y-1 text-sm text-slate-200">
        Reservation URL
        <input
          v-model="form.reservation_url"
          :class="inputClass('reservation_url')"
          @input="clearField('reservation_url')"
          placeholder="https://..."
        />
        <p v-if="fieldError('reservation_url')" class="text-xs text-red-300">{{ fieldError("reservation_url") }}</p>
      </label>
      <label class="space-y-1 text-sm text-slate-200">
        Facebook URL
        <input v-model="form.facebook_url" :class="inputClass('facebook_url')" @input="clearField('facebook_url')" />
        <p v-if="fieldError('facebook_url')" class="text-xs text-red-300">{{ fieldError("facebook_url") }}</p>
      </label>
      <label class="space-y-1 text-sm text-slate-200">
        Instagram URL
        <input v-model="form.instagram_url" :class="inputClass('instagram_url')" @input="clearField('instagram_url')" />
        <p v-if="fieldError('instagram_url')" class="text-xs text-red-300">{{ fieldError("instagram_url") }}</p>
      </label>
      <label class="space-y-1 text-sm text-slate-200">
        TikTok URL
        <input v-model="form.tiktok_url" :class="inputClass('tiktok_url')" @input="clearField('tiktok_url')" />
        <p v-if="fieldError('tiktok_url')" class="text-xs text-red-300">{{ fieldError("tiktok_url") }}</p>
      </label>
    </div>

    <p v-if="fieldError('non_field_errors')" class="text-sm text-red-300">{{ fieldError("non_field_errors") }}</p>

    <div class="flex flex-wrap items-center gap-3">
      <button class="ui-btn-primary px-4 py-2" @click="saveAndNext" :disabled="saving">
        {{ saving ? "Saving..." : "Save & Next" }}
      </button>
      <p class="text-sm text-slate-400">{{ status }}</p>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { profileApi } from "../lib/onboardingApi";
import { useTenantStore } from "../stores/tenant";
import { useToastStore } from "../stores/toast";

const form = reactive({
  tagline: "",
  description: "",
  phone: "",
  whatsapp: "",
  address: "",
  google_maps_url: "",
  reservation_url: "",
  facebook_url: "",
  instagram_url: "",
  tiktok_url: "",
});
const saving = ref(false);
const status = ref("");
const errors = ref({});
const tenant = useTenantStore();
const toast = useToastStore();
const emit = defineEmits(["next"]);
const canCheckout = computed(() => tenant.entitlements?.can_checkout === true);
const canWhatsappOrder = computed(() => tenant.entitlements?.can_whatsapp_order === true);
const isBrowseOnlyPlan = computed(() => tenant.isBrowseOnlyPlan === true);
const introText = computed(() =>
  isBrowseOnlyPlan.value
    ? "Set your identity and customer contact details."
    : "Name, phone, WhatsApp, address, description."
);
const whatsappLabel = computed(() => (canWhatsappOrder.value ? "WhatsApp ordering number" : "WhatsApp contact"));

const inputClass = (field) =>
  `w-full rounded-xl bg-slate-900 px-3 py-2 border ${errors.value[field] ? "border-red-400" : "border-slate-700"}`;

const fieldError = (field) => (errors.value[field] ? String(errors.value[field]) : "");
const clearField = (field) => {
  if (errors.value[field]) {
    const next = { ...errors.value };
    delete next[field];
    errors.value = next;
  }
};

const load = async () => {
  try {
    const data = await profileApi.get();
    Object.assign(form, data || {});
  } catch (e) {
    status.value = "Load failed";
  }
};

const saveAndNext = async () => {
  saving.value = true;
  status.value = "";
  errors.value = {};
  try {
    await profileApi.save(form);
    status.value = "Saved";
    toast.show("Brand & contact saved", "success");
    emit("next");
  } catch (e) {
    status.value = "Save failed";
    errors.value = e?.fieldErrors || {};
    toast.show(e?.message || "Brand save failed", "error");
  } finally {
    saving.value = false;
  }
};

onMounted(load);
</script>
