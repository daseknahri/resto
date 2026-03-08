<template>
  <div class="mx-auto max-w-6xl px-4 py-6 space-y-6 ui-safe-bottom">
    <div class="ui-panel flex flex-wrap items-center justify-between gap-3 p-4">
      <div>
        <p class="ui-kicker">Super Admin</p>
        <h1 class="ui-display text-3xl font-semibold text-white">Provisioning and operations</h1>
        <p class="mt-1 text-xs text-slate-400">Review incoming leads, provision tenants, and manage upgrade operations.</p>
      </div>
      <div class="ui-scroll-row">
        <a
          :href="djangoAdminUrl"
          target="_blank"
          rel="noopener noreferrer"
          class="ui-btn-outline px-4 py-2 text-sm"
        >
          Django admin
        </a>
        <input v-model="domainSuffix" class="ui-input w-36 px-2 py-1 text-sm" placeholder="suffix (localhost)" />
        <button @click="refreshAll" class="ui-btn-outline px-4 py-2 text-sm">Refresh</button>
      </div>
    </div>

    <p v-if="error" class="text-sm text-red-400">{{ error }}</p>

    <section class="ui-panel p-4 space-y-3">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p class="text-sm text-slate-300">Incoming leads</p>
          <h2 class="text-xl font-semibold">Awaiting provisioning</h2>
        </div>
        <button @click="fetchLeads" class="ui-btn-outline px-3 py-1.5 text-xs">Refresh leads</button>
      </div>
      <p v-if="leadsLoading" class="text-sm text-slate-400">Loading leads...</p>
      <p v-if="!leads.length && !leadsLoading" class="text-sm text-slate-400">No leads pending.</p>
      <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <div
          v-for="lead in leads"
          :key="lead.id"
          class="rounded-xl border border-slate-800 bg-slate-900/80 p-3 space-y-2"
        >
          <div class="flex items-center justify-between">
            <p class="font-semibold text-slate-100">{{ lead.name || 'Lead #' + lead.id }}</p>
            <div class="flex items-center gap-2">
              <span class="text-xs text-slate-500">{{ lead.status }}</span>
              <span class="text-xs text-slate-400">{{ lead.plan_code?.toUpperCase() }}</span>
            </div>
          </div>
          <p class="text-xs text-slate-400">{{ lead.email }} / {{ lead.phone }}</p>
          <p class="text-[11px] text-slate-500">
            Source: {{ lead.source || "-" }}
            <span v-if="lead.tenant_slug"> | Tenant: {{ lead.tenant_slug }}</span>
          </p>
          <p class="text-xs text-slate-500 line-clamp-2">{{ lead.notes }}</p>
          <p v-if="lead.onboarded_at" class="text-xs text-emerald-300">
            Onboarded: {{ new Date(lead.onboarded_at).toLocaleString() }}
          </p>
          <div class="rounded-lg border border-slate-800 bg-slate-950/50 p-2 text-xs space-y-1">
            <p class="text-slate-400">Tenant URL preview</p>
            <p v-if="previewLoading[lead.id]" class="text-slate-500">Checking availability...</p>
            <template v-else-if="previewFor(lead.id)">
              <p class="text-slate-200">{{ previewFor(lead.id).input_domain }}</p>
              <p v-if="previewFor(lead.id).collision" class="text-amber-300">
                Collision detected. Will use {{ previewFor(lead.id).resolved_domain }}
              </p>
              <p v-else class="text-emerald-300">Available</p>
            </template>
            <p v-else class="text-slate-500">Not checked yet</p>
          </div>
          <div class="grid grid-cols-2 gap-2">
            <button
              class="flex-1 rounded-full bg-brand-secondary px-3 py-2 text-sm font-semibold text-slate-950 disabled:opacity-60"
              :disabled="provLoading[lead.id]"
              @click="provision(lead)"
            >
              {{ provLoading[lead.id] ? 'Provisioning...' : 'Provision' }}
            </button>
            <button
              class="rounded-full border border-slate-700 px-3 py-2 text-xs text-slate-200 hover:border-brand-primary"
              :disabled="previewLoading[lead.id]"
              @click="checkPreview(lead, true)"
            >
              Check
            </button>
            <button
              class="rounded-full border border-slate-700 px-3 py-2 text-xs text-slate-200 hover:border-brand-primary disabled:opacity-50"
              :disabled="resendLoading[lead.id] || lead.status !== 'live'"
              @click="resendActivation(lead)"
            >
              {{ resendLoading[lead.id] ? 'Sending...' : 'Resend activation' }}
            </button>
            <button
              class="rounded-full border border-slate-700 px-3 py-2 text-xs text-slate-200 hover:border-brand-primary disabled:opacity-50"
              :disabled="packageLoading[lead.id] || lead.status !== 'live'"
              @click="loadOnboardingPackage(lead, false)"
            >
              {{ packageLoading[lead.id] ? 'Loading...' : 'Load package' }}
            </button>
            <button
              class="rounded-full border border-slate-700 px-3 py-2 text-xs text-slate-300 hover:border-red-400/60 hover:text-red-200 disabled:opacity-50"
              :disabled="removeLoading[lead.id]"
              @click="removeLead(lead)"
            >
              {{ removeLoading[lead.id] ? 'Archiving...' : 'Archive' }}
            </button>
          </div>
        </div>
      </div>
    </section>

    <section class="ui-panel p-4 space-y-3">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p class="text-sm text-slate-300">Reservation follow-up SLA</p>
          <h2 class="text-xl font-semibold">Overdue reservation alerts</h2>
        </div>
        <button @click="fetchReservationAlerts" class="ui-btn-outline px-3 py-1.5 text-xs">Refresh alerts</button>
      </div>
      <div class="ui-scroll-row">
        <button
          class="ui-pill-nav text-xs"
          :class="alertState === 'all' ? 'border-brand-secondary bg-brand-secondary/10 text-brand-secondary' : ''"
          @click="setAlertState('all')"
        >
          All alerts
        </button>
        <button
          class="ui-pill-nav text-xs"
          :class="alertState === 'overdue' ? 'border-rose-400 bg-rose-500/10 text-rose-200' : ''"
          @click="setAlertState('overdue')"
        >
          Overdue only
        </button>
        <button
          class="ui-pill-nav text-xs"
          :class="alertState === 'due_soon' ? 'border-amber-400 bg-amber-500/10 text-amber-200' : ''"
          @click="setAlertState('due_soon')"
        >
          Due soon only
        </button>
      </div>
      <div class="grid gap-2 sm:grid-cols-3">
        <div class="rounded-lg border border-slate-800 bg-slate-950/50 px-3 py-2 text-xs">
          <p class="text-slate-500">Overdue</p>
          <p class="mt-1 text-base font-semibold text-rose-200">{{ alertCounts.overdue }}</p>
        </div>
        <div class="rounded-lg border border-slate-800 bg-slate-950/50 px-3 py-2 text-xs">
          <p class="text-slate-500">Due soon</p>
          <p class="mt-1 text-base font-semibold text-amber-200">{{ alertCounts.due_soon }}</p>
        </div>
        <div class="rounded-lg border border-slate-800 bg-slate-950/50 px-3 py-2 text-xs">
          <p class="text-slate-500">Total alerts</p>
          <p class="mt-1 text-base font-semibold text-slate-100">{{ alertCounts.total_alerts }}</p>
        </div>
      </div>
      <p class="text-xs text-slate-500">
        Tracks reservation leads still marked <span class="font-semibold text-amber-300">new</span>. Priority should be
        highest for overdue follow-ups. SLA target: {{ alertThresholds.overdue_minutes }}m (due soon window:
        last {{ alertThresholds.due_soon_minutes }}m before breach).
      </p>
      <p v-if="alertsLoading" class="text-sm text-slate-400">Loading alerts...</p>
      <p v-else-if="!reservationAlerts.length" class="text-sm text-slate-400">
        No overdue or due-soon reservation leads right now.
      </p>
      <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        <article
          v-for="lead in reservationAlerts"
          :key="`alert-${lead.id}`"
          class="rounded-xl border border-slate-800 bg-slate-900/80 p-3 space-y-2"
        >
          <div class="flex items-center justify-between gap-2">
            <p class="font-semibold text-slate-100">{{ lead.name || `Lead #${lead.id}` }}</p>
            <span class="rounded-full px-2 py-1 text-xs font-semibold" :class="slaBadgeClass(lead.sla_state)">
              {{ slaLabel(lead) }}
            </span>
          </div>
          <p class="text-xs text-slate-400">
            Tenant: <span class="text-slate-200">{{ lead.tenant_slug || "-" }}</span>
          </p>
          <p class="text-xs text-slate-400">{{ lead.phone || "-" }} {{ lead.email ? `| ${lead.email}` : "" }}</p>
          <p class="text-xs text-slate-500">
            Reminders: {{ lead.reminder_count || 0 }}
            <span v-if="lead.last_reminder_status"> | Last: {{ lead.last_reminder_status }}</span>
          </p>
          <p class="text-xs text-slate-500">Created: {{ formatDate(lead.created_at) }}</p>
          <p class="text-xs text-slate-500">Due: {{ formatDate(lead.follow_up_due_at) }}</p>
          <a
            v-if="lead.tenant_slug"
            :href="ownerReservationUrl(lead)"
            target="_blank"
            rel="noopener noreferrer"
            class="inline-flex rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-200 hover:border-brand-primary"
          >
            Open owner inbox
          </a>
        </article>
      </div>
    </section>

    <section class="ui-panel p-4 space-y-3">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p class="text-sm text-slate-300">Cash-first upgrades</p>
          <h2 class="ui-display text-2xl font-semibold">Tier upgrade requests</h2>
        </div>
        <button @click="fetchUpgradeRequests" class="ui-btn-outline px-4 py-2 text-sm">
          Refresh
        </button>
      </div>
      <p v-if="upgradeLoading" class="text-sm text-slate-400">Loading upgrade requests...</p>
      <div class="space-y-2 md:hidden">
        <article
          v-for="request in upgradeRequests"
          :key="`upgrade-mobile-${request.id}`"
          class="rounded-xl border border-slate-800 bg-slate-900/80 p-3 space-y-2"
        >
          <div class="flex items-center justify-between gap-2">
            <p class="text-xs text-slate-400">{{ new Date(request.requested_at).toLocaleString() }}</p>
            <span class="rounded-full px-2 py-1 text-xs font-semibold" :class="upgradeStatusClass(request.status)">
              {{ request.status }}
            </span>
          </div>
          <p class="text-sm font-semibold text-slate-100">{{ request.tenant_slug }}</p>
          <p class="text-xs text-slate-400">{{ request.current_plan_name }} -> {{ request.target_plan_name }}</p>
          <p class="text-xs text-slate-500">
            Payment: {{ request.payment_method }}{{ request.payment_reference ? ` / ${request.payment_reference}` : "" }}
          </p>
          <p v-if="request.target_plan_is_active === false" class="text-xs text-amber-300">Target plan is inactive.</p>
          <div class="grid grid-cols-2 gap-2">
            <button
              class="rounded-full bg-emerald-500/90 px-3 py-1.5 text-xs font-semibold text-slate-950 disabled:opacity-50"
              :disabled="request.status !== 'pending' || request.target_plan_is_active === false || !!decisionLoading[request.id]"
              @click="decideUpgradeRequest(request, 'approve')"
            >
              Approve
            </button>
            <button
              class="rounded-full border border-rose-500/70 px-3 py-1.5 text-xs font-semibold text-rose-200 disabled:opacity-50"
              :disabled="request.status !== 'pending' || !!decisionLoading[request.id]"
              @click="decideUpgradeRequest(request, 'reject')"
            >
              Reject
            </button>
          </div>
        </article>
        <p v-if="!upgradeRequests.length && !upgradeLoading" class="text-sm text-slate-400">No upgrade requests yet.</p>
      </div>
      <div class="ui-table-wrap hidden md:block">
        <table class="w-full min-w-[860px] text-sm">
          <thead class="bg-slate-900/70 text-slate-300">
            <tr>
              <th class="px-4 py-3 text-left">When</th>
              <th class="px-4 py-3 text-left">Tenant</th>
              <th class="px-4 py-3 text-left">From</th>
              <th class="px-4 py-3 text-left">To</th>
              <th class="px-4 py-3 text-left">Payment</th>
              <th class="px-4 py-3 text-left">Status</th>
              <th class="px-4 py-3 text-left">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="request in upgradeRequests" :key="request.id" class="border-t border-slate-800">
              <td class="px-4 py-3 text-slate-300">{{ new Date(request.requested_at).toLocaleString() }}</td>
              <td class="px-4 py-3 text-slate-100">{{ request.tenant_slug }}</td>
              <td class="px-4 py-3 text-slate-300">{{ request.current_plan_name }}</td>
              <td class="px-4 py-3 text-slate-300">
                <span>{{ request.target_plan_name }}</span>
                <span v-if="request.target_plan_is_active === false" class="ml-2 text-xs text-amber-300">(inactive)</span>
              </td>
              <td class="px-4 py-3 text-slate-300">{{ request.payment_method }}{{ request.payment_reference ? ` / ${request.payment_reference}` : "" }}</td>
              <td class="px-4 py-3">
                <span class="rounded-full px-2 py-1 text-xs font-semibold" :class="upgradeStatusClass(request.status)">
                  {{ request.status }}
                </span>
              </td>
              <td class="px-4 py-3">
                <div class="flex items-center gap-2">
                  <button
                    class="rounded-full bg-emerald-500/90 px-3 py-1 text-xs font-semibold text-slate-950 disabled:opacity-50"
                    :disabled="request.status !== 'pending' || request.target_plan_is_active === false || !!decisionLoading[request.id]"
                    @click="decideUpgradeRequest(request, 'approve')"
                  >
                    Approve
                  </button>
                  <button
                    class="rounded-full border border-rose-500/70 px-3 py-1 text-xs font-semibold text-rose-200 disabled:opacity-50"
                    :disabled="request.status !== 'pending' || !!decisionLoading[request.id]"
                    @click="decideUpgradeRequest(request, 'reject')"
                  >
                    Reject
                  </button>
                </div>
              </td>
            </tr>
            <tr v-if="!upgradeRequests.length && !upgradeLoading">
              <td colspan="7" class="px-4 py-3 text-slate-400">No upgrade requests yet.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="ui-panel p-4 space-y-3">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <h2 class="ui-display text-2xl font-semibold">Provisioning jobs</h2>
        <button @click="fetchJobs" class="ui-btn-outline px-4 py-2 text-sm">Refresh</button>
      </div>

      <p v-if="loading" class="text-sm text-slate-400">Loading jobs...</p>
      <div class="space-y-2 md:hidden">
        <article
          v-for="job in jobs"
          :key="`job-mobile-${job.id}`"
          class="rounded-xl border border-slate-800 bg-slate-900/80 p-3 space-y-2"
        >
          <div class="flex items-center justify-between gap-2">
            <p class="text-sm font-semibold text-slate-100">#{{ job.id }} - {{ job.lead_name }}</p>
            <span class="rounded-full px-2 py-1 text-xs font-semibold" :class="statusClass(job.status)">{{ job.status }}</span>
          </div>
          <p class="text-xs text-slate-400">Tenant: {{ job.tenant_slug || '-' }}</p>
          <p class="text-xs text-slate-400">Updated: {{ new Date(job.updated_at).toLocaleString() }}</p>
          <p class="rounded-lg border border-slate-800 bg-slate-950/50 p-2 text-xs text-slate-300 whitespace-pre-wrap">{{ job.log || "-" }}</p>
        </article>
        <p v-if="!jobs.length && !loading" class="text-sm text-slate-400">No jobs yet.</p>
      </div>

      <div class="ui-table-wrap hidden md:block">
        <table class="w-full min-w-[920px] text-sm">
          <thead class="bg-slate-900/70 text-slate-300">
            <tr>
              <th class="px-4 py-3 text-left">ID</th>
              <th class="px-4 py-3 text-left">Lead</th>
              <th class="px-4 py-3 text-left">Tenant</th>
              <th class="px-4 py-3 text-left">Status</th>
              <th class="px-4 py-3 text-left">Log</th>
              <th class="px-4 py-3 text-left">Updated</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="job in jobs" :key="job.id" class="border-t border-slate-800">
              <td class="px-4 py-3 text-slate-100">#{{ job.id }}</td>
              <td class="px-4 py-3 text-slate-200">{{ job.lead_name }}</td>
              <td class="px-4 py-3 text-slate-200">{{ job.tenant_slug || '-' }}</td>
              <td class="px-4 py-3">
                <span class="rounded-full px-2 py-1 text-xs font-semibold" :class="statusClass(job.status)">{{ job.status }}</span>
              </td>
              <td class="px-4 py-3 text-slate-300 whitespace-pre-line text-xs leading-snug max-w-[320px]">{{ job.log }}</td>
              <td class="px-4 py-3 text-slate-400">{{ new Date(job.updated_at).toLocaleString() }}</td>
            </tr>
            <tr v-if="!jobs.length && !loading">
              <td colspan="6" class="px-4 py-3 text-slate-400">No jobs yet.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="ui-panel p-4 space-y-3">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <h2 class="ui-display text-2xl font-semibold">Security audit log</h2>
        <button @click="fetchAuditLogs" class="ui-btn-outline px-4 py-2 text-sm">Refresh</button>
      </div>
      <p v-if="auditLoading" class="text-sm text-slate-400">Loading audit logs...</p>
      <div class="space-y-2 md:hidden">
        <article
          v-for="entry in auditLogs"
          :key="`audit-mobile-${entry.id}`"
          class="rounded-xl border border-slate-800 bg-slate-900/80 p-3 space-y-2"
        >
          <div class="flex items-center justify-between gap-2">
            <p class="text-sm font-semibold text-slate-100">{{ entry.action }}</p>
            <p class="text-[11px] text-slate-500">{{ new Date(entry.created_at).toLocaleString() }}</p>
          </div>
          <p class="text-xs text-slate-400">Actor: {{ entry.actor_username || "system" }}</p>
          <p class="text-xs text-slate-400">Target: {{ entry.target_repr || entry.tenant_slug || entry.lead_name || "-" }}</p>
          <p class="rounded-lg border border-slate-800 bg-slate-950/50 p-2 text-xs text-slate-300 whitespace-pre-wrap">{{ formatAuditMetadata(entry.metadata) }}</p>
        </article>
        <p v-if="!auditLogs.length && !auditLoading" class="text-sm text-slate-400">No audit entries yet.</p>
      </div>
      <div class="ui-table-wrap hidden md:block">
        <table class="w-full min-w-[860px] text-sm">
          <thead class="bg-slate-900/70 text-slate-300">
            <tr>
              <th class="px-4 py-3 text-left">When</th>
              <th class="px-4 py-3 text-left">Action</th>
              <th class="px-4 py-3 text-left">Actor</th>
              <th class="px-4 py-3 text-left">Target</th>
              <th class="px-4 py-3 text-left">Details</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="entry in auditLogs" :key="entry.id" class="border-t border-slate-800">
              <td class="px-4 py-3 text-slate-300">{{ new Date(entry.created_at).toLocaleString() }}</td>
              <td class="px-4 py-3 text-slate-100">{{ entry.action }}</td>
              <td class="px-4 py-3 text-slate-300">{{ entry.actor_username || "system" }}</td>
              <td class="px-4 py-3 text-slate-300">{{ entry.target_repr || entry.tenant_slug || entry.lead_name || "-" }}</td>
              <td class="px-4 py-3 text-slate-400 max-w-[360px] whitespace-pre-wrap text-xs">{{ formatAuditMetadata(entry.metadata) }}</td>
            </tr>
            <tr v-if="!auditLogs.length && !auditLoading">
              <td colspan="5" class="px-4 py-3 text-slate-400">No audit entries yet.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section v-if="lastProvision" class="ui-panel p-4 space-y-2 text-sm text-slate-200">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <h3 class="font-semibold">Latest provisioning package</h3>
        <div class="flex items-center gap-3">
          <button class="text-xs text-brand-secondary hover:underline" @click="copyOnboardingPackage">Copy package</button>
          <button class="text-xs text-brand-secondary hover:underline" @click="lastProvision = null">Clear</button>
        </div>
      </div>
      <p><span class="text-slate-400">Tenant:</span> {{ lastProvision.tenant || '-' }}</p>
      <div class="flex items-center gap-2">
        <span class="text-slate-400">Tenant URL:</span>
        <span class="truncate">{{ lastProvision.tenant_url || '-' }}</span>
        <button v-if="lastProvision.tenant_url" class="text-xs text-brand-secondary hover:underline" @click="copyText(lastProvision.tenant_url)">Copy</button>
      </div>
      <div class="flex items-center gap-2">
        <span class="text-slate-400">Admin URL:</span>
        <span class="truncate">{{ lastProvision.admin_url || '-' }}</span>
        <button v-if="lastProvision.admin_url" class="text-xs text-brand-secondary hover:underline" @click="copyText(lastProvision.admin_url)">Copy</button>
      </div>
      <div class="flex items-center gap-2">
        <span class="text-slate-400">Activation token:</span>
        <span class="truncate">{{ lastProvision.activation_token || '-' }}</span>
        <button v-if="lastProvision.activation_token" class="text-xs text-brand-secondary hover:underline" @click="copyText(lastProvision.activation_token)">Copy</button>
      </div>
      <div class="flex items-center gap-2">
        <span class="text-slate-400">WhatsApp link:</span>
        <span class="truncate">{{ lastProvision.whatsapp_link || '-' }}</span>
        <button v-if="lastProvision.whatsapp_link" class="text-xs text-brand-secondary hover:underline" @click="copyText(lastProvision.whatsapp_link)">Copy</button>
      </div>
      <div class="flex items-center gap-2">
        <span class="text-slate-400">Activation URL:</span>
        <span class="truncate">{{ lastProvision.activation_url || '-' }}</span>
        <button v-if="lastProvision.activation_url" class="text-xs text-brand-secondary hover:underline" @click="copyText(lastProvision.activation_url)">Copy</button>
      </div>
      <div class="space-y-1">
        <span class="text-slate-400">WhatsApp message template:</span>
        <pre class="rounded-lg border border-slate-800 bg-slate-950/50 p-2 text-xs whitespace-pre-wrap">{{ lastProvision.whatsapp_message_template || '-' }}</pre>
        <button
          v-if="lastProvision.whatsapp_message_template"
          class="text-xs text-brand-secondary hover:underline"
          @click="copyText(lastProvision.whatsapp_message_template)"
        >
          Copy message
        </button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import adminApi from "../lib/adminApi";
import { useToastStore } from "../stores/toast";

const jobs = ref([]);
const leads = ref([]);
const loading = ref(false);
const leadsLoading = ref(false);
const auditLoading = ref(false);
const error = ref(null);
const provLoading = ref({});
const resendLoading = ref({});
const packageLoading = ref({});
const removeLoading = ref({});
const previewLoading = ref({});
const previews = ref({});
const domainSuffix = ref("localhost");
const upgradeRequests = ref([]);
const upgradeLoading = ref(false);
const decisionLoading = ref({});
const reservationAlerts = ref([]);
const alertsLoading = ref(false);
const alertState = ref("all");
const alertCounts = ref({
  overdue: 0,
  due_soon: 0,
  total_alerts: 0,
});
const alertThresholds = ref({
  overdue_minutes: 30,
  due_soon_minutes: 10,
});
const toast = useToastStore();
const lastProvision = ref(null);
const auditLogs = ref([]);
const parseApiError = (err, fallback) => {
  const data = err?.response?.data;
  if (typeof data?.detail === "string") return data.detail;
  if (Array.isArray(data?.non_field_errors) && data.non_field_errors.length) return String(data.non_field_errors[0]);
  if (data && typeof data === "object") {
    const firstList = Object.values(data).find((v) => Array.isArray(v) && v.length);
    if (firstList) return String(firstList[0]);
  }
  if (typeof data === "string" && data.trim()) return data;
  return fallback;
};
const normalizeSuffix = (value) => (value || "localhost").replace(/^\.+/, "");
const djangoAdminUrl = computed(() => {
  if (typeof window === "undefined") return "/admin/";
  const host = window.location.hostname;
  const isLocal = host === "localhost" || host.endsWith(".localhost");
  if (isLocal) return `http://${host}:8000/admin/`;
  return `https://${host}/admin/`;
});
const packageText = computed(() => {
  if (!lastProvision.value) return "";
  const p = lastProvision.value;
  return [
    `Tenant: ${p.tenant || "-"}`,
    `Tenant URL: ${p.tenant_url || "-"}`,
    `Admin URL: ${p.admin_url || "-"}`,
    `Activation URL: ${p.activation_url || "-"}`,
    `Activation Token: ${p.activation_token || "-"}`,
    `WhatsApp Link: ${p.whatsapp_link || "-"}`,
    "",
    "WhatsApp Message Template:",
    p.whatsapp_message_template || "-",
  ].join("\n");
});

const fetchJobs = async () => {
  loading.value = true;
  error.value = null;
  try {
    const res = await adminApi.get("/provision-jobs/");
    jobs.value = res.data;
  } catch (err) {
    error.value = parseApiError(err, "Unable to load jobs (login as admin)");
  } finally {
    loading.value = false;
  }
};

const fetchUpgradeRequests = async () => {
  upgradeLoading.value = true;
  try {
    const res = await adminApi.get("/admin-tier-upgrade-requests/");
    upgradeRequests.value = Array.isArray(res.data) ? res.data : [];
  } catch (err) {
    const msg = parseApiError(err, "Unable to load upgrade requests");
    error.value = msg;
    toast.show(msg, "error");
  } finally {
    upgradeLoading.value = false;
  }
};

const fetchAuditLogs = async () => {
  auditLoading.value = true;
  try {
    const res = await adminApi.get("/admin-audit-logs/");
    auditLogs.value = Array.isArray(res.data) ? res.data.slice(0, 100) : [];
  } catch (err) {
    const msg = parseApiError(err, "Unable to load audit logs");
    error.value = msg;
    toast.show(msg, "error");
  } finally {
    auditLoading.value = false;
  }
};

const fetchLeads = async () => {
  leadsLoading.value = true;
  try {
    const res = await adminApi.get("/leads/");
    leads.value = res.data;
    previews.value = {};
    previewLoading.value = {};
    await Promise.all(leads.value.map((lead) => checkPreview(lead, false)));
  } catch (err) {
    const msg = parseApiError(err, "Unable to load leads (admin only)");
    error.value = msg;
    toast.show(msg, "error");
  } finally {
    leadsLoading.value = false;
  }
};

const fetchReservationAlerts = async () => {
  alertsLoading.value = true;
  try {
    const res = await adminApi.get("/admin-reservation-alerts/", {
      params: { state: alertState.value, limit: 30 },
    });
    const payload = res?.data || {};
    reservationAlerts.value = Array.isArray(payload.results) ? payload.results : [];
    alertCounts.value = {
      ...alertCounts.value,
      ...(payload.counts || {}),
    };
    alertThresholds.value = {
      ...alertThresholds.value,
      ...(payload.thresholds || {}),
    };
  } catch (err) {
    const msg = parseApiError(err, "Unable to load reservation alerts");
    error.value = msg;
    toast.show(msg, "error");
  } finally {
    alertsLoading.value = false;
  }
};

const setAlertState = async (state) => {
  if (!["all", "overdue", "due_soon"].includes(state)) return;
  if (alertState.value === state) return;
  alertState.value = state;
  await fetchReservationAlerts();
};

const previewFor = (leadId) => previews.value[leadId] || null;

const checkPreview = async (lead, showToast = true) => {
  previewLoading.value = { ...previewLoading.value, [lead.id]: true };
  try {
    const res = await adminApi.get(`/lead-provision-preview/${lead.id}/`, {
      params: { domain_suffix: normalizeSuffix(domainSuffix.value || "localhost") },
    });
    previews.value = { ...previews.value, [lead.id]: res.data };
    if (showToast) {
      if (res.data?.collision) {
        toast.show(`Collision detected. Provision will use ${res.data.resolved_slug}`, "error");
      } else {
        toast.show("Slug/domain available", "success");
      }
    }
  } catch (err) {
    if (showToast) {
      toast.show(parseApiError(err, "Preview check failed"), "error");
    }
  } finally {
    previewLoading.value = { ...previewLoading.value, [lead.id]: false };
  }
};

const provision = async (lead) => {
  provLoading.value = { ...provLoading.value, [lead.id]: true };
  try {
    const preview = previewFor(lead.id);
    const res = await adminApi.put(`/lead-provision/${lead.id}/`, {
      domain_suffix: domainSuffix.value || "localhost",
      requested_slug: preview?.input_slug || undefined,
    });
    const data = res.data || {};
    toast.show(`Provisioned ${lead.name || lead.email}`, "success");
    // display quick info for copy/paste
    lastProvision.value = {
      tenant_url: data.tenant_url,
      admin_url: data.admin_url,
      activation_url: data.activation_url,
      activation_token: data.activation_token,
      tenant: data.tenant,
      whatsapp_link: data.whatsapp_link,
      whatsapp_message_template: data.whatsapp_message_template,
    };
    fetchJobs();
  } catch (err) {
    const msg = parseApiError(err, "Provision failed");
    error.value = msg;
    toast.show(msg, "error");
  } finally {
    provLoading.value = { ...provLoading.value, [lead.id]: false };
  }
};

const resendActivation = async (lead) => {
  resendLoading.value = { ...resendLoading.value, [lead.id]: true };
  try {
    const res = await adminApi.post(`/lead-resend-activation/${lead.id}/`);
    const data = res.data || {};
    toast.show(`Activation resent for ${lead.name || lead.email}`, "success");
    lastProvision.value = {
      tenant_url: data.tenant_url,
      admin_url: data.admin_url,
      activation_url: data.activation_url,
      activation_token: data.activation_token,
      tenant: data.tenant,
      whatsapp_link: data.whatsapp_link,
      whatsapp_message_template: data.whatsapp_message_template,
    };
    fetchJobs();
  } catch (err) {
    const msg = parseApiError(err, "Resend failed");
    error.value = msg;
    toast.show(msg, "error");
  } finally {
    resendLoading.value = { ...resendLoading.value, [lead.id]: false };
  }
};

const loadOnboardingPackage = async (lead, refreshToken = false) => {
  packageLoading.value = { ...packageLoading.value, [lead.id]: true };
  try {
    const res = await adminApi.get(`/lead-onboarding-package/${lead.id}/`, {
      params: { refresh_token: refreshToken ? "1" : "0" },
    });
    const data = res.data || {};
    lastProvision.value = {
      tenant: data.tenant,
      tenant_url: data.tenant_url,
      admin_url: data.admin_url,
      activation_url: data.activation_url,
      activation_token: data.activation_token,
      whatsapp_link: data.whatsapp_link,
      whatsapp_message_template: data.whatsapp_message_template,
    };
    toast.show(`Package loaded for ${lead.name || lead.email}`, "success");
  } catch (err) {
    const msg = parseApiError(err, "Unable to load onboarding package");
    error.value = msg;
    toast.show(msg, "error");
  } finally {
    packageLoading.value = { ...packageLoading.value, [lead.id]: false };
  }
};

const removeLead = async (lead) => {
  removeLoading.value = { ...removeLoading.value, [lead.id]: true };
  try {
    await adminApi.delete(`/leads/${lead.id}/`);
    leads.value = leads.value.filter((l) => l.id !== lead.id);
    const { [lead.id]: _removedPreview, ...rest } = previews.value;
    previews.value = rest;
    toast.show(`Archived ${lead.name || lead.email}`, "success");
  } catch (err) {
    const msg = parseApiError(err, "Unable to archive lead");
    error.value = msg;
    toast.show(msg, "error");
  } finally {
    removeLoading.value = { ...removeLoading.value, [lead.id]: false };
  }
};

const decideUpgradeRequest = async (requestItem, decision) => {
  decisionLoading.value = { ...decisionLoading.value, [requestItem.id]: true };
  try {
    let adminNote = "";
    let paymentReference = requestItem.payment_reference || "";
    if (decision === "approve") {
      paymentReference = window.prompt("Payment reference (optional)", paymentReference) ?? paymentReference;
      adminNote = window.prompt("Internal admin note (optional)", "") ?? "";
    } else {
      adminNote = window.prompt("Reason for rejection (optional)", "") ?? "";
    }
    const res = await adminApi.put(`/admin-tier-upgrade-requests/${requestItem.id}/decision/`, {
      decision,
      admin_note: adminNote,
      payment_reference: paymentReference,
    });
    const detail = res?.data?.detail || (decision === "approve" ? "Upgrade approved" : "Upgrade rejected");
    toast.show(detail, "success");
    await fetchUpgradeRequests();
    fetchAuditLogs();
  } catch (err) {
    const msg = parseApiError(err, "Unable to process upgrade request");
    error.value = msg;
    toast.show(msg, "error");
  } finally {
    decisionLoading.value = { ...decisionLoading.value, [requestItem.id]: false };
  }
};

const copyText = async (text) => {
  try {
    await navigator.clipboard.writeText(text);
    toast.show("Copied", "success");
  } catch (e) {
    toast.show("Copy failed", "error");
  }
};

const copyOnboardingPackage = async () => {
  if (!packageText.value) {
    toast.show("No package details yet", "error");
    return;
  }
  await copyText(packageText.value);
};

const formatAuditMetadata = (meta) => {
  if (!meta || typeof meta !== "object") return "-";
  try {
    return Object.entries(meta)
      .map(([key, value]) => `${key}: ${typeof value === "string" ? value : JSON.stringify(value)}`)
      .join("\n");
  } catch (e) {
    return "-";
  }
};

const formatDate = (value) => {
  if (!value) return "-";
  try {
    return new Date(value).toLocaleString();
  } catch (e) {
    return String(value);
  }
};

const ownerReservationUrl = (lead) => {
  const slug = String(lead?.tenant_slug || "").trim();
  if (!slug || typeof window === "undefined") return "";
  const protocol = window.location.protocol === "https:" ? "https" : "http";
  const hostname = window.location.hostname;
  if (hostname === "localhost" || hostname.endsWith(".localhost")) {
    return `${protocol}://${slug}.localhost:5173/owner/reservations`;
  }
  const hostParts = hostname.split(".");
  if (hostParts.length >= 2) {
    const baseDomain = hostParts.slice(-2).join(".");
    return `${protocol}://${slug}.${baseDomain}/owner/reservations`;
  }
  return `${protocol}://${hostname}/owner/reservations`;
};

const slaBadgeClass = (state) => {
  if (state === "overdue") return "bg-rose-500/20 text-rose-200";
  if (state === "due_soon") return "bg-amber-500/20 text-amber-200";
  if (state === "on_track") return "bg-emerald-500/20 text-emerald-200";
  return "bg-slate-700/60 text-slate-300";
};

const slaLabel = (lead) => {
  const state = String(lead?.sla_state || "");
  if (state === "overdue") {
    const minutes = Number(lead?.sla_minutes_overdue || 0);
    return minutes > 0 ? `Overdue ${minutes}m` : "Overdue";
  }
  if (state === "due_soon") return "Due soon";
  if (state === "on_track") return "On track";
  return "SLA";
};

const statusClass = (status) => {
  if (status === "success") return "bg-emerald-600/30 text-emerald-200";
  if (status === "running") return "bg-amber-500/30 text-amber-200";
  if (status === "failed") return "bg-red-600/30 text-red-200";
  return "bg-slate-700/50 text-slate-200";
};

const upgradeStatusClass = (status) => {
  if (status === "approved") return "bg-emerald-600/30 text-emerald-200";
  if (status === "rejected") return "bg-rose-500/20 text-rose-200";
  if (status === "canceled") return "bg-slate-600/40 text-slate-300";
  return "bg-amber-500/30 text-amber-200";
};

const refreshAll = () => {
  fetchLeads();
  fetchReservationAlerts();
  fetchUpgradeRequests();
  fetchJobs();
  fetchAuditLogs();
};

onMounted(refreshAll);

watch(domainSuffix, () => {
  if (!leads.value.length) return;
  Promise.all(leads.value.map((lead) => checkPreview(lead, false)));
});
</script>
