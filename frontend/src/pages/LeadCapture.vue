<template>
  <section class="space-y-6 px-4 py-6 md:space-y-8 md:py-8">
    <header class="ui-hero-ribbon ui-fade-up overflow-hidden p-0">
      <div class="grid gap-6 p-5 md:grid-cols-[1.15fr,0.85fr] md:p-6">
        <div class="space-y-4">
          <span class="ui-chip-strong w-fit">{{ t("leadCapture.kicker") }}</span>
          <div class="space-y-2">
            <h2 class="ui-display max-w-3xl text-3xl font-semibold text-white md:text-4xl">{{ t("leadCapture.title") }}</h2>
            <p class="max-w-2xl text-sm leading-7 text-slate-300 md:text-base">{{ t("leadCapture.description") }}</p>
          </div>
          <div class="flex flex-wrap gap-2 text-xs text-slate-300">
            <span class="ui-data-strip">{{ t("leadCapture.planBasic") }}</span>
            <span class="ui-data-strip">{{ t("leadCapture.planGrowth") }}</span>
            <span class="ui-data-strip">{{ t("leadCapture.planPro") }}</span>
          </div>
        </div>

        <div class="grid gap-3 sm:grid-cols-3 md:grid-cols-1">
          <article class="ui-stat-tile">
            <p class="ui-stat-label">{{ t("common.plan") }}</p>
            <p class="ui-stat-value text-2xl">{{ selectedPlanLabel }}</p>
            <p class="ui-stat-note">{{ selectedPlanDescription }}</p>
          </article>
          <article class="ui-stat-tile">
            <p class="ui-stat-label">{{ t("leadCapture.whatHappensNext") }}</p>
            <p class="ui-stat-value text-2xl">4</p>
            <p class="ui-stat-note">{{ t("leadCapture.step4") }}</p>
          </article>
          <article class="ui-stat-tile">
            <p class="ui-stat-label">{{ t("common.workspace") }}</p>
            <p class="ui-stat-value text-2xl">Owner</p>
            <p class="ui-stat-note">{{ t("leadCapture.qualityRule") }}</p>
          </article>
        </div>
      </div>
    </header>

    <div class="grid gap-6 xl:grid-cols-[1.12fr,0.88fr]">
      <form class="ui-command-deck space-y-4 p-5 md:p-6" @submit.prevent="submit">
        <div class="flex flex-wrap items-start justify-between gap-3 rounded-2xl border border-slate-800/80 bg-slate-950/45 px-4 py-3 text-sm text-slate-300">
          <div>
            <p class="font-medium text-white">{{ t("leadCapture.whatHappensNext") }}</p>
            <p class="mt-1 text-xs text-slate-400">{{ t("leadCapture.qualityRule") }}</p>
          </div>
          <span class="ui-chip-strong">{{ t("common.getStarted") }}</span>
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

        <div class="flex flex-wrap items-center gap-3">
          <button type="submit" :disabled="lead.submitting" class="ui-btn-primary ui-touch-target disabled:opacity-60">
            {{ lead.submitting ? t("leadCapture.submitting") : lead.success ? t("leadCapture.submitted") : t("leadCapture.submitLead") }}
          </button>
          <span class="text-xs text-slate-500">{{ t("leadCapture.step1") }}</span>
        </div>
      </form>

      <aside class="space-y-4">
        <article class="ui-command-deck p-5">
          <p class="ui-kicker">{{ t("common.plan") }}</p>
          <div class="mt-4 grid gap-3">
            <button
              type="button"
              class="rounded-[1.35rem] border p-4 text-left transition"
              :class="form.plan_code === 'basic' ? 'border-[var(--color-secondary)] bg-[rgba(245,158,11,0.12)]' : 'border-slate-800/80 bg-slate-950/45'"
              @click="form.plan_code = 'basic'"
            >
              <p class="text-sm font-semibold text-white">Basic</p>
              <p class="mt-1 text-xs text-slate-400">{{ t("leadCapture.planBasic") }}</p>
            </button>
            <button
              type="button"
              class="rounded-[1.35rem] border p-4 text-left transition"
              :class="form.plan_code === 'growth' ? 'border-[var(--color-secondary)] bg-[rgba(245,158,11,0.12)]' : 'border-slate-800/80 bg-slate-950/45'"
              @click="form.plan_code = 'growth'"
            >
              <p class="text-sm font-semibold text-white">Growth</p>
              <p class="mt-1 text-xs text-slate-400">{{ t("leadCapture.planGrowth") }}</p>
            </button>
            <button
              type="button"
              class="rounded-[1.35rem] border p-4 text-left transition"
              :class="form.plan_code === 'pro' ? 'border-[var(--color-secondary)] bg-[rgba(245,158,11,0.12)]' : 'border-slate-800/80 bg-slate-950/45'"
              @click="form.plan_code = 'pro'"
            >
              <p class="text-sm font-semibold text-white">Pro</p>
              <p class="mt-1 text-xs text-slate-400">{{ t("leadCapture.planPro") }}</p>
            </button>
          </div>
        </article>

        <article class="ui-spotlight-card p-5">
          <p class="ui-kicker">{{ t("leadCapture.whatHappensNext") }}</p>
          <ol class="mt-4 space-y-3 text-sm text-slate-200">
            <li class="flex gap-3"><span class="ui-chip-strong min-w-[2rem] justify-center">1</span><span>{{ t("leadCapture.step1") }}</span></li>
            <li class="flex gap-3"><span class="ui-chip-strong min-w-[2rem] justify-center">2</span><span>{{ t("leadCapture.step2") }}</span></li>
            <li class="flex gap-3"><span class="ui-chip-strong min-w-[2rem] justify-center">3</span><span>{{ t("leadCapture.step3") }}</span></li>
            <li class="flex gap-3"><span class="ui-chip-strong min-w-[2rem] justify-center">4</span><span>{{ t("leadCapture.step4") }}</span></li>
          </ol>
        </article>

        <article class="ui-panel-soft p-5">
          <p class="ui-kicker">{{ t("leadCapture.planGuidance") }}</p>
          <div class="mt-4 space-y-3 text-sm text-slate-200">
            <div class="rounded-2xl border border-slate-800/80 bg-slate-950/45 p-3" :class="form.plan_code === 'basic' ? 'border-[var(--color-secondary)]/50' : ''">
              <p class="font-semibold text-white">Basic</p>
              <p class="mt-1 text-slate-400">{{ t("leadCapture.planBasic") }}</p>
            </div>
            <div class="rounded-2xl border border-slate-800/80 bg-slate-950/45 p-3" :class="form.plan_code === 'growth' ? 'border-[var(--color-secondary)]/50' : ''">
              <p class="font-semibold text-white">Growth</p>
              <p class="mt-1 text-slate-400">{{ t("leadCapture.planGrowth") }}</p>
            </div>
            <div class="rounded-2xl border border-slate-800/80 bg-slate-950/45 p-3" :class="form.plan_code === 'pro' ? 'border-[var(--color-secondary)]/50' : ''">
              <p class="font-semibold text-white">Pro</p>
              <p class="mt-1 text-slate-400">{{ t("leadCapture.planPro") }}</p>
            </div>
          </div>
        </article>
      </aside>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, watch } from "vue";
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

const selectedPlanLabel = computed(() => {
  if (form.plan_code === "growth") return "Growth";
  if (form.plan_code === "pro") return "Pro";
  return "Basic";
});

const selectedPlanDescription = computed(() => {
  if (form.plan_code === "growth") return t("leadCapture.planGrowth");
  if (form.plan_code === "pro") return t("leadCapture.planPro");
  return t("leadCapture.planBasic");
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
