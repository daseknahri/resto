<template>
  <section class="space-y-8 px-4 py-8 md:py-10">
    <header class="space-y-2 ui-fade-up">
      <p class="ui-kicker">{{ t("leadCapture.kicker") }}</p>
      <h2 class="ui-page-title ui-display">{{ t("leadCapture.title") }}</h2>
      <p class="max-w-3xl text-slate-400">{{ t("leadCapture.description") }}</p>
    </header>

    <div class="grid gap-6 lg:grid-cols-[1.2fr,1fr]">
      <form class="ui-glass p-5 md:p-6 space-y-4" @submit.prevent="submit">
        <div class="rounded-2xl border border-slate-700/50 bg-slate-950/50 px-4 py-3 text-xs text-slate-300">
          {{ t("leadCapture.qualityRule") }}
        </div>

        <div class="grid gap-3 sm:grid-cols-2">
          <label class="space-y-1 text-sm text-slate-200">
            {{ t("leadCapture.ownerName") }}
            <input
              v-model.trim="form.name"
              class="ui-input"
              :class="errors.name ? 'border-red-400' : 'border-slate-700'"
              required
              autocomplete="name"
              @input="clearError('name')"
            />
            <p v-if="errors.name" class="text-xs text-red-300">{{ errors.name }}</p>
          </label>
          <label class="space-y-1 text-sm text-slate-200">
            {{ t("common.email") }}
            <input
              v-model.trim="form.email"
              type="email"
              class="ui-input"
              :class="errors.email ? 'border-red-400' : 'border-slate-700'"
              autocomplete="email"
              inputmode="email"
              @input="clearError('email')"
            />
            <p v-if="errors.email" class="text-xs text-red-300">{{ errors.email }}</p>
          </label>
          <label class="space-y-1 text-sm text-slate-200">
            {{ t("leadCapture.phoneWhatsapp") }}
            <input
              v-model.trim="form.phone"
              class="ui-input"
              :class="errors.phone ? 'border-red-400' : 'border-slate-700'"
              placeholder="+212..."
              autocomplete="tel"
              inputmode="tel"
              @input="clearError('phone')"
            />
            <p v-if="errors.phone" class="text-xs text-red-300">{{ errors.phone }}</p>
          </label>
          <label class="space-y-1 text-sm text-slate-200">
            {{ t("common.plan") }}
            <select
              v-model="form.plan_code"
              class="ui-input"
              :class="errors.plan_code ? 'border-red-400' : 'border-slate-700'"
              @change="clearError('plan_code')"
            >
              <option value="basic">{{ t("leadCapture.basicOption") }}</option>
              <option value="growth">{{ t("leadCapture.growthOption") }}</option>
              <option value="pro">{{ t("leadCapture.proOption") }}</option>
            </select>
            <p v-if="errors.plan_code" class="text-xs text-red-300">{{ errors.plan_code }}</p>
          </label>
        </div>

        <label class="space-y-1 text-sm text-slate-200">
          {{ t("common.notes") }}
          <textarea
            v-model.trim="form.notes"
            rows="4"
            class="ui-textarea"
            :class="errors.notes ? 'border-red-400' : 'border-slate-700'"
            :placeholder="t('leadCapture.notesPlaceholder')"
            @input="clearError('notes')"
          ></textarea>
          <p v-if="errors.notes" class="text-xs text-red-300">{{ errors.notes }}</p>
        </label>

        <input v-model="form.hp" type="text" class="hidden" autocomplete="off" tabindex="-1" aria-hidden="true" />

        <div class="flex flex-wrap items-center justify-between gap-3 text-sm">
          <span class="text-slate-400">{{ t("leadCapture.responseTarget") }}</span>
          <span v-if="lead.success" class="text-emerald-400">{{ t("leadCapture.submittedOk") }}</span>
          <span v-else-if="lead.error" class="text-red-400">{{ lead.error }}</span>
        </div>

        <button type="submit" :disabled="lead.submitting" class="ui-btn-primary ui-touch-target disabled:opacity-60">
          {{ lead.submitting ? t("leadCapture.submitting") : lead.success ? t("leadCapture.submitted") : t("leadCapture.submitLead") }}
        </button>
      </form>

      <aside class="space-y-4">
        <article class="ui-panel p-5">
          <p class="text-sm text-slate-300">{{ t("leadCapture.whatHappensNext") }}</p>
          <ol class="mt-3 space-y-2 text-sm text-slate-200">
            <li>{{ t("leadCapture.step1") }}</li>
            <li>{{ t("leadCapture.step2") }}</li>
            <li>{{ t("leadCapture.step3") }}</li>
            <li>{{ t("leadCapture.step4") }}</li>
          </ol>
        </article>

        <article class="ui-panel p-5">
          <p class="text-sm text-slate-300">{{ t("leadCapture.planGuidance") }}</p>
          <ul class="mt-3 space-y-2 text-sm text-slate-200">
            <li>- {{ t("leadCapture.planBasic") }}</li>
            <li>- {{ t("leadCapture.planGrowth") }}</li>
            <li>- {{ t("leadCapture.planPro") }}</li>
          </ul>
        </article>
      </aside>
    </div>
  </section>
</template>

<script setup>
import { onMounted, reactive, watch } from "vue";
import { useRoute } from "vue-router";
import { useI18n } from "../composables/useI18n";
import { useLeadStore } from "../stores/lead";

const lead = useLeadStore();
const route = useRoute();
const { t } = useI18n();

const form = reactive({
  name: "",
  email: "",
  phone: "",
  plan_code: "basic",
  notes: "",
  hp: "",
});

const errors = reactive({
  name: "",
  email: "",
  phone: "",
  plan_code: "",
  notes: "",
});

const applyPlanFromQuery = () => {
  const requested = String(route.query.plan || "").toLowerCase();
  if (requested === "starter") {
    form.plan_code = "basic";
    return;
  }
  if (["basic", "growth", "pro"].includes(requested)) {
    form.plan_code = requested;
  }
};

const clearError = (field) => {
  if (errors[field]) errors[field] = "";
};

const validate = () => {
  Object.keys(errors).forEach((k) => {
    errors[k] = "";
  });

  let valid = true;
  if (!form.name || form.name.length < 2) {
    errors.name = t("leadCapture.nameError");
    valid = false;
  }

  if (!form.email && !form.phone) {
    errors.email = t("leadCapture.contactRequired");
    errors.phone = t("leadCapture.contactRequired");
    valid = false;
  }

  if (form.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) {
    errors.email = t("leadCapture.invalidEmail");
    valid = false;
  }

  if (!["basic", "growth", "pro"].includes(form.plan_code)) {
    errors.plan_code = t("leadCapture.invalidPlan");
    valid = false;
  }

  return valid;
};

const submit = async () => {
  if (!validate()) return;
  await lead.submitLead({ ...form, source: "landing" });
};

onMounted(applyPlanFromQuery);
watch(() => route.query.plan, applyPlanFromQuery);
</script>
