<!-- eslint-disable vue/html-indent -->
<template>
  <div class="mx-auto max-w-7xl px-4 py-6 pb-28 md:pb-6 space-y-6 ui-safe-bottom">
    <div class="ui-workspace-stage space-y-4 p-4 md:p-5">
      <div class="ui-workspace-grid items-start">
        <div class="space-y-2">
          <p class="ui-kicker">{{ t("adminConsole.superAdmin") }}</p>
          <h1 class="ui-display text-3xl font-semibold text-white">{{ activeAdminViewTitle }}</h1>
          <p class="mt-1 text-xs text-slate-400">{{ t("adminConsole.reviewIncomingLeads") }}</p>
          <div class="flex flex-wrap gap-2">
            <span class="ui-chip text-[10px] uppercase tracking-[0.18em] text-slate-300">{{ activeAdminViewLabel }}</span>
            <span class="ui-chip text-[10px] uppercase tracking-[0.18em] text-slate-300">{{ currentDomainSuffixLabel }}</span>
          </div>
        </div>
        <div class="grid gap-3 self-start">
          <article class="ui-action-tile space-y-3">
            <div class="space-y-1">
              <p class="ui-kicker">{{ t("adminConsole.tenantLifecycleControls") }}</p>
              <p class="text-sm text-slate-400">{{ t("adminConsole.suffixOptional") }}</p>
            </div>
            <input
              v-model="domainSuffix"
              class="ui-input w-full px-3 py-2 text-sm"
              :placeholder="`${t('adminConsole.suffixOptional')} (${inferredDomainSuffix})`"
            />
            <div class="grid grid-cols-2 gap-2">
              <button class="ui-btn-outline w-full px-4 py-2 text-sm disabled:opacity-50" :disabled="activeAdminViewLoading" @click="refreshCurrentView">{{ t("common.refresh") }}</button>
              <a
                :href="djangoAdminUrl"
                target="_blank"
                rel="noopener noreferrer"
                class="ui-btn-outline w-full px-4 py-2 text-sm"
              >
                {{ t("adminConsole.djangoAdmin") }}
              </a>
            </div>
          </article>
          <article class="ui-orbit-card space-y-2">
            <p class="ui-kicker">{{ activeAdminViewLabel }}</p>
            <p class="text-lg font-semibold text-white">{{ currentDomainSuffixLabel }}</p>
            <p class="text-sm text-slate-400">{{ activeAdminViewLoading ? t("common.loading") : t("common.available") }}</p>
          </article>
        </div>
      </div>

      <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <article v-for="metric in activeAdminMetrics" :key="metric.label" class="ui-stat-tile">
          <p class="ui-stat-label">{{ metric.label }}</p>
          <p class="ui-stat-value" :class="metric.valueClass">{{ metric.value }}</p>
          <p class="ui-stat-note">{{ metric.note }}</p>
        </article>
      </div>

      <div class="ui-scroll-row md:hidden">
        <button
          class="ui-pill-nav text-xs"
          :class="activeAdminView === 'operations' ? 'border-brand-secondary bg-brand-secondary/10 text-brand-secondary' : ''"
          @click="selectAdminView('operations')"
        >
          {{ t("adminConsole.provisioningOperations") }}
        </button>
        <button
          class="ui-pill-nav text-xs"
          :class="activeAdminView === 'tenants' ? 'border-brand-secondary bg-brand-secondary/10 text-brand-secondary' : ''"
          @click="selectAdminView('tenants')"
        >
          {{ t("adminConsole.tenantLifecycleControls") }}
        </button>
        <button
          class="ui-pill-nav text-xs"
          :class="activeAdminView === 'monitoring' ? 'border-brand-secondary bg-brand-secondary/10 text-brand-secondary' : ''"
          @click="selectAdminView('monitoring')"
        >
          {{ t("adminConsole.reservationFollowUpSla") }}
        </button>
        <button
          class="ui-pill-nav text-xs"
          :class="activeAdminView === 'plans' ? 'border-brand-secondary bg-brand-secondary/10 text-brand-secondary' : ''"
          @click="selectAdminView('plans')"
        >
          {{ t("adminConsole.planFeatureFlags") }}
        </button>
      </div>
    </div>

    <div class="ui-segmented hidden md:flex">
      <button
        class="ui-segmented-button"
        :data-active="activeAdminView === 'operations'"
        @click="selectAdminView('operations')"
      >
        {{ t("adminConsole.provisioningOperations") }}
      </button>
      <button
        class="ui-segmented-button"
        :data-active="activeAdminView === 'tenants'"
        @click="selectAdminView('tenants')"
      >
        {{ t("adminConsole.tenantLifecycleControls") }}
      </button>
      <button
        class="ui-segmented-button"
        :data-active="activeAdminView === 'monitoring'"
        @click="selectAdminView('monitoring')"
      >
        {{ t("adminConsole.reservationFollowUpSla") }}
      </button>
      <button
        class="ui-segmented-button"
        :data-active="activeAdminView === 'plans'"
        @click="selectAdminView('plans')"
      >
        {{ t("adminConsole.planFeatureFlags") }}
      </button>
    </div>

    <p v-if="error" class="text-sm text-red-400">{{ error }}</p>

    <section v-if="activeAdminView === 'operations'" class="ui-workspace-stage p-4 space-y-3">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p class="text-sm text-slate-300">{{ t("adminConsole.incomingLeads") }}</p>
          <h2 class="text-xl font-semibold">{{ t("adminConsole.awaitingProvisioning") }}</h2>
        </div>
        <button class="ui-btn-outline px-3 py-1.5 text-xs disabled:opacity-50" :disabled="leadsLoading" @click="fetchLeads">{{ t("adminConsole.refreshLeads") }}</button>
      </div>
      <p v-if="leadsLoading" class="text-sm text-slate-400">{{ t("adminConsole.loadingLeads") }}</p>
      <p v-if="!leads.length && !leadsLoading" class="text-sm text-slate-400">{{ t("adminConsole.noLeadsPending") }}</p>
      <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <div
          v-for="lead in leads"
          :key="lead.id"
          class="ui-admin-card space-y-2"
        >
          <div class="flex items-center justify-between">
            <p class="font-semibold text-slate-100">{{ lead.name || t("adminConsole.leadLabel", { id: lead.id }) }}</p>
            <div class="flex items-center gap-2">
              <span class="text-xs text-slate-500">{{ lead.status }}</span>
              <span class="text-xs text-slate-400">{{ lead.plan_code?.toUpperCase() }}</span>
            </div>
          </div>
          <p class="text-xs text-slate-400">{{ lead.email }} / {{ lead.phone }}</p>
          <p class="text-[11px] text-slate-500">
            {{ t("adminConsole.source") }}: {{ lead.source || "-" }}
            <span v-if="lead.tenant_slug"> | {{ t("adminConsole.tenant") }}: {{ lead.tenant_slug }}</span>
          </p>
          <p class="text-xs text-slate-500 line-clamp-2">{{ lead.notes }}</p>
          <p v-if="lead.onboarded_at" class="text-xs text-emerald-300">
            {{ t("adminConsole.onboarded") }}: {{ new Date(lead.onboarded_at).toLocaleString() }}
          </p>
          <div class="ui-admin-subcard text-xs space-y-1">
            <p class="text-slate-400">{{ t("adminConsole.tenantUrlPreview") }}</p>
            <p v-if="previewLoading[lead.id]" class="text-slate-500">{{ t("adminConsole.checkingAvailability") }}</p>
            <template v-else-if="previewFor(lead.id)">
              <p class="text-slate-200">{{ previewFor(lead.id).input_domain }}</p>
              <p v-if="previewFor(lead.id).collision" class="text-amber-300">
                {{ t("adminConsole.collisionDetectedWillUse", { domain: previewFor(lead.id).resolved_domain }) }}
              </p>
              <p v-else class="text-emerald-300">{{ t("common.available") }}</p>
            </template>
            <p v-else class="text-slate-500">{{ t("adminConsole.notCheckedYet") }}</p>
          </div>
          <div class="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <button
              class="flex-1 rounded-full bg-brand-secondary px-3 py-2 text-sm font-semibold text-slate-950 disabled:opacity-60"
              :disabled="provLoading[lead.id]"
              @click="provision(lead)"
            >
              {{ provLoading[lead.id] ? t("adminConsole.provisioning") : t("adminConsole.provision") }}
            </button>
            <button
              class="rounded-full border border-slate-700 px-3 py-2 text-xs text-slate-200 hover:border-brand-primary"
              :disabled="previewLoading[lead.id]"
              @click="checkPreview(lead, true)"
            >
              {{ t("adminConsole.check") }}
            </button>
            <button
              class="rounded-full border border-slate-700 px-3 py-2 text-xs text-slate-200 hover:border-brand-primary disabled:opacity-50"
              :disabled="resendLoading[lead.id] || lead.status !== 'live'"
              @click="resendActivation(lead)"
            >
              {{ resendLoading[lead.id] ? t("adminConsole.sending") : t("adminConsole.resendActivation") }}
            </button>
            <button
              class="rounded-full border border-slate-700 px-3 py-2 text-xs text-slate-200 hover:border-brand-primary disabled:opacity-50"
              :disabled="packageLoading[lead.id] || lead.status !== 'live'"
              @click="loadOnboardingPackage(lead, false)"
            >
              {{ packageLoading[lead.id] ? t("common.loading") : t("adminConsole.loadPackage") }}
            </button>
            <button
              class="rounded-full border border-slate-700 px-3 py-2 text-xs text-slate-300 hover:border-red-400/60 hover:text-red-200 disabled:opacity-50 sm:col-span-2"
              :disabled="removeLoading[lead.id]"
              @click="removeLead(lead)"
            >
              {{ removeLoading[lead.id] ? t("adminConsole.archiving") : t("adminConsole.archive") }}
            </button>
          </div>
        </div>
      </div>
    </section>

    <section v-if="activeAdminView === 'tenants'" class="ui-workspace-stage p-4 space-y-3">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p class="text-sm text-slate-300">{{ t("adminConsole.tenantLifecycleControls") }}</p>
          <h2 class="text-xl font-semibold">{{ t("adminConsole.suspendReactivateCancel") }}</h2>
        </div>
        <div class="ui-scroll-row">
          <label class="text-xs text-slate-400">
            {{ t("adminConsole.pageSize") }}
            <select v-model.number="tenantPageSize" class="ui-input ml-2 px-2 py-1 text-xs">
              <option :value="10">10</option>
              <option :value="25">25</option>
              <option :value="50">50</option>
            </select>
          </label>
          <button class="ui-btn-outline px-3 py-1.5 text-xs disabled:opacity-50" :disabled="!tenantHasPrev" @click="changeTenantPage(tenantPage - 1)">
            {{ t("common.previous") }}
          </button>
          <button class="ui-btn-outline px-3 py-1.5 text-xs disabled:opacity-50" :disabled="!tenantHasNext" @click="changeTenantPage(tenantPage + 1)">
            {{ t("common.next") }}
          </button>
          <button class="ui-btn-outline px-3 py-1.5 text-xs disabled:opacity-50" :disabled="tenantsLoading" @click="fetchTenants(tenantPage)">{{ t("adminConsole.refreshTenants") }}</button>
        </div>
      </div>
      <p class="text-xs text-slate-500">{{ t("adminConsole.pageSummary", { page: tenantPage, pages: tenantTotalPages, total: tenantTotal }) }}</p>
      <p v-if="tenantsLoading" class="text-sm text-slate-400">{{ t("adminConsole.loadingTenants") }}</p>
      <p v-else-if="!tenants.length" class="text-sm text-slate-400">{{ t("adminConsole.noTenantRecordsFound") }}</p>
      <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        <article
          v-for="tenant in tenants"
          :key="`tenant-${tenant.id}`"
          class="ui-admin-card space-y-2"
        >
          <div class="flex items-center justify-between gap-2">
            <p class="font-semibold text-slate-100">{{ tenant.name }}</p>
            <span class="rounded-full px-2 py-1 text-xs font-semibold" :class="tenantLifecycleStatusClass(tenant.lifecycle_status)">
              {{ tenant.lifecycle_status }}
            </span>
          </div>
          <p class="text-xs text-slate-400">{{ t("adminConsole.slug") }}: {{ tenant.slug }} | {{ t("common.plan") }}: {{ tenant.plan_name }}</p>
          <p class="text-xs text-slate-500">{{ t("adminConsole.domain") }}: {{ tenant.primary_domain || "-" }}</p>
          <p class="text-xs text-slate-500">{{ t("adminConsole.owner") }}: {{ tenant.owner_username || "-" }}</p>
          <p v-if="tenant.canceled_reason" class="text-xs text-rose-200">{{ t("adminConsole.cancelReason") }}: {{ tenant.canceled_reason }}</p>
          <div class="grid grid-cols-1 gap-2 sm:grid-cols-3">
            <button
              class="rounded-full border border-amber-400/70 px-3 py-1.5 text-xs font-semibold text-amber-200 disabled:opacity-50"
              :disabled="tenant.lifecycle_status !== 'active' || !!tenantLifecycleLoading[tenant.id]"
              @click="applyTenantLifecycle(tenant, 'suspend')"
            >
              {{ t("adminConsole.suspend") }}
            </button>
            <button
              class="rounded-full border border-emerald-400/70 px-3 py-1.5 text-xs font-semibold text-emerald-200 disabled:opacity-50"
              :disabled="tenant.lifecycle_status === 'active' || !!tenantLifecycleLoading[tenant.id]"
              @click="applyTenantLifecycle(tenant, 'reactivate')"
            >
              {{ t("adminConsole.reactivate") }}
            </button>
            <button
              class="rounded-full border border-rose-500/70 px-3 py-1.5 text-xs font-semibold text-rose-200 disabled:opacity-50"
              :disabled="tenant.lifecycle_status === 'canceled' || !!tenantLifecycleLoading[tenant.id]"
              @click="applyTenantLifecycle(tenant, 'cancel')"
            >
              {{ t("adminConsole.cancel") }}
            </button>
          </div>
          <button
            class="rounded-full border border-slate-700 px-3 py-1.5 text-xs text-slate-200 hover:border-brand-primary"
            @click="toggleTenantTools(tenant.id)"
          >
            {{ tenantToolsExpanded(tenant.id) ? `${t("adminConsole.hide")} tools` : `${t("adminConsole.show")} tools` }}
          </button>
          <div v-if="tenantToolsExpanded(tenant.id)" class="space-y-2">
            <div class="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <button
                class="rounded-full border border-slate-700 px-3 py-1.5 text-xs text-slate-200 hover:border-brand-primary disabled:opacity-50"
                :disabled="!!tenantExportLoading[tenant.id]"
                @click="exportTenantSettings(tenant)"
              >
                {{ tenantExportLoading[tenant.id] ? t("adminConsole.exporting") : t("adminConsole.exportSettings") }}
              </button>
              <button
                class="rounded-full border border-slate-700 px-3 py-1.5 text-xs text-slate-200 hover:border-brand-primary disabled:opacity-50"
                :disabled="!!tenantImportLoading[tenant.id]"
                @click="openTenantImportPicker(tenant.id)"
              >
                {{ tenantImportLoading[tenant.id] ? t("adminConsole.importing") : t("adminConsole.importSettings") }}
              </button>
              <input
                :ref="(el) => setTenantImportInputRef(tenant.id, el)"
                type="file"
                accept=".json,application/json"
                class="hidden"
                @change="handleTenantImportFile(tenant, $event)"
              />
            </div>
            <div class="ui-admin-subcard space-y-2">
              <div class="flex items-center justify-between gap-2">
                <p class="text-[11px] uppercase tracking-[0.2em] text-slate-500">{{ t("adminConsole.actionHistory") }}</p>
                <button
                  class="text-xs text-brand-secondary hover:underline disabled:opacity-50"
                  :disabled="tenantTimelineLoading(tenant.id)"
                  @click="toggleTenantTimeline(tenant)"
                >
                  {{ tenantTimelineExpanded(tenant.id) ? t("adminConsole.hide") : t("adminConsole.show") }}
                </button>
              </div>
              <template v-if="tenantTimelineExpanded(tenant.id)">
                <div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <p class="text-[11px] text-slate-500">
                    {{ t("adminConsole.pageSummary", { page: tenantTimelinePage(tenant.id), pages: tenantTimelineTotalPages(tenant.id), total: tenantTimelineTotal(tenant.id) }) }}
                  </p>
                  <div class="flex flex-wrap items-center gap-1">
                    <button
                      class="rounded-full border border-slate-700 px-2 py-1 text-[10px] text-slate-200 disabled:opacity-50"
                      :disabled="!tenantTimelineHasPrev(tenant.id) || tenantTimelineLoading(tenant.id)"
                      @click="changeTenantTimelinePage(tenant.id, tenantTimelinePage(tenant.id) - 1)"
                    >
                      {{ t("common.previous") }}
                    </button>
                    <button
                      class="rounded-full border border-slate-700 px-2 py-1 text-[10px] text-slate-200 disabled:opacity-50"
                      :disabled="!tenantTimelineHasNext(tenant.id) || tenantTimelineLoading(tenant.id)"
                      @click="changeTenantTimelinePage(tenant.id, tenantTimelinePage(tenant.id) + 1)"
                    >
                      {{ t("common.next") }}
                    </button>
                    <button
                      class="rounded-full border border-slate-700 px-2 py-1 text-[10px] text-slate-200 disabled:opacity-50"
                      :disabled="tenantTimelineLoading(tenant.id)"
                      @click="fetchTenantTimeline(tenant.id, tenantTimelinePage(tenant.id))"
                    >
                      {{ t("common.refresh") }}
                    </button>
                  </div>
                </div>
                <p v-if="tenantTimelineLoading(tenant.id)" class="text-xs text-slate-400">{{ t("adminConsole.loadingHistory") }}</p>
                <p v-else-if="!tenantTimelineEntries(tenant.id).length" class="text-xs text-slate-500">
                  {{ t("adminConsole.noAdminActionsRecordedYet") }}
                </p>
                <ul v-else class="space-y-2">
                  <li
                    v-for="entry in tenantTimelineEntries(tenant.id)"
                    :key="`tenant-timeline-${tenant.id}-${entry.id}`"
                    class="rounded-lg border border-slate-800 bg-slate-900/70 px-2 py-1.5"
                  >
                    <div class="flex items-center justify-between gap-2 text-[11px]">
                      <span class="font-semibold text-slate-200">{{ formatAuditAction(entry.action) }}</span>
                      <span class="text-slate-500">{{ formatDate(entry.created_at) }}</span>
                    </div>
                    <p class="text-[11px] text-slate-400">
                      {{ t("adminConsole.by") }} {{ entry.actor_username || t("adminConsole.system") }}
                      <span v-if="entry.metadata?.lifecycle_action">
                        | {{ entry.metadata.lifecycle_action }}
                      </span>
                    </p>
                  </li>
                </ul>
              </template>
            </div>
          </div>
        </article>
      </div>
    </section>

    <section v-if="activeAdminView === 'monitoring'" class="ui-workspace-stage p-4 space-y-3">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p class="text-sm text-slate-300">{{ t("adminConsole.reservationFollowUpSla") }}</p>
          <h2 class="text-xl font-semibold">{{ t("adminConsole.overdueReservationAlerts") }}</h2>
        </div>
        <div class="ui-scroll-row">
          <button class="ui-btn-outline px-3 py-1.5 text-xs" @click="adminPanels.alerts = !adminPanels.alerts">
            {{ adminPanels.alerts ? t("adminConsole.hide") : t("adminConsole.show") }}
          </button>
          <button class="ui-btn-outline px-3 py-1.5 text-xs disabled:opacity-50" :disabled="alertsLoading || !adminPanels.alerts" @click="fetchReservationAlerts">{{ t("adminConsole.refreshAlerts") }}</button>
        </div>
      </div>
      <template v-if="adminPanels.alerts">
      <div class="ui-scroll-row">
        <button
          class="ui-pill-nav text-xs"
          :class="alertState === 'all' ? 'border-brand-secondary bg-brand-secondary/10 text-brand-secondary' : ''"
          @click="setAlertState('all')"
        >
          {{ t("adminConsole.allAlerts") }}
        </button>
        <button
          class="ui-pill-nav text-xs"
          :class="alertState === 'overdue' ? 'border-rose-400 bg-rose-500/10 text-rose-200' : ''"
          @click="setAlertState('overdue')"
        >
          {{ t("adminConsole.overdueOnly") }}
        </button>
        <button
          class="ui-pill-nav text-xs"
          :class="alertState === 'due_soon' ? 'border-amber-400 bg-amber-500/10 text-amber-200' : ''"
          @click="setAlertState('due_soon')"
        >
          {{ t("adminConsole.dueSoonOnly") }}
        </button>
      </div>
      <div class="grid gap-2 sm:grid-cols-3">
        <div class="rounded-lg border border-slate-800 bg-slate-950/50 px-3 py-2 text-xs">
          <p class="text-slate-500">{{ t("adminConsole.overdue") }}</p>
          <p class="mt-1 text-base font-semibold text-rose-200">{{ alertCounts.overdue }}</p>
        </div>
        <div class="rounded-lg border border-slate-800 bg-slate-950/50 px-3 py-2 text-xs">
          <p class="text-slate-500">{{ t("adminConsole.dueSoon") }}</p>
          <p class="mt-1 text-base font-semibold text-amber-200">{{ alertCounts.due_soon }}</p>
        </div>
        <div class="rounded-lg border border-slate-800 bg-slate-950/50 px-3 py-2 text-xs">
          <p class="text-slate-500">{{ t("adminConsole.totalAlerts") }}</p>
          <p class="mt-1 text-base font-semibold text-slate-100">{{ alertCounts.total_alerts }}</p>
        </div>
      </div>
      <p class="text-xs text-slate-500">
        {{ t("adminConsole.reservationSlaCopy", { overdue: alertThresholds.overdue_minutes, dueSoon: alertThresholds.due_soon_minutes }) }}
      </p>
      <p v-if="alertsLoading" class="text-sm text-slate-400">{{ t("adminConsole.loadingAlerts") }}</p>
      <p v-else-if="!reservationAlerts.length" class="text-sm text-slate-400">
        {{ t("adminConsole.noReservationAlerts") }}
      </p>
      <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        <article
          v-for="lead in reservationAlerts"
          :key="`alert-${lead.id}`"
          class="ui-admin-card space-y-2"
        >
          <div class="flex items-center justify-between gap-2">
            <p class="font-semibold text-slate-100">{{ lead.name || t("adminConsole.leadLabel", { id: lead.id }) }}</p>
            <span class="rounded-full px-2 py-1 text-xs font-semibold" :class="slaBadgeClass(lead.sla_state)">
              {{ slaLabel(lead) }}
            </span>
          </div>
          <p class="text-xs text-slate-400">
            {{ t("adminConsole.tenant") }}: <span class="text-slate-200">{{ lead.tenant_slug || "-" }}</span>
          </p>
          <p class="text-xs text-slate-400">{{ lead.phone || "-" }} {{ lead.email ? `| ${lead.email}` : "" }}</p>
          <p class="text-xs text-slate-500">
            {{ t("adminConsole.reminders") }}: {{ lead.reminder_count || 0 }}
            <span v-if="lead.last_reminder_status"> | {{ t("adminConsole.last") }}: {{ lead.last_reminder_status }}</span>
          </p>
          <p class="text-xs text-slate-500">{{ t("adminConsole.created") }}: {{ formatDate(lead.created_at) }}</p>
          <p class="text-xs text-slate-500">{{ t("adminConsole.due") }}: {{ formatDate(lead.follow_up_due_at) }}</p>
          <a
            v-if="lead.tenant_slug"
            :href="ownerReservationUrl(lead)"
            target="_blank"
            rel="noopener noreferrer"
            class="inline-flex rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-200 hover:border-brand-primary"
          >
            {{ t("adminConsole.openOwnerInbox") }}
          </a>
        </article>
      </div>
      </template>
    </section>

    <section v-if="activeAdminView === 'operations'" class="ui-workspace-stage p-4 space-y-3">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p class="text-sm text-slate-300">{{ t("adminConsole.cashFirstUpgrades") }}</p>
          <h2 class="ui-display text-2xl font-semibold">{{ t("adminConsole.tierUpgradeRequests") }}</h2>
        </div>
        <button class="ui-btn-outline px-4 py-2 text-sm disabled:opacity-50" :disabled="upgradeLoading" @click="fetchUpgradeRequests">
          {{ t("common.refresh") }}
        </button>
      </div>
      <p v-if="upgradeLoading" class="text-sm text-slate-400">{{ t("adminConsole.loadingUpgradeRequests") }}</p>
      <div class="space-y-2 md:hidden">
        <article
          v-for="request in upgradeRequests"
          :key="`upgrade-mobile-${request.id}`"
          class="ui-admin-card space-y-2"
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
            {{ t("adminConsole.payment") }}: {{ request.payment_method }}{{ request.payment_reference ? ` / ${request.payment_reference}` : "" }}
          </p>
          <p v-if="request.target_plan_is_active === false" class="text-xs text-amber-300">{{ t("adminConsole.targetPlanInactive") }}</p>
          <div class="grid grid-cols-2 gap-2">
            <button
              class="rounded-full bg-emerald-500/90 px-3 py-1.5 text-xs font-semibold text-slate-950 disabled:opacity-50"
              :disabled="request.status !== 'pending' || request.target_plan_is_active === false || !!decisionLoading[request.id]"
              @click="decideUpgradeRequest(request, 'approve')"
            >
              {{ t("adminConsole.approve") }}
            </button>
            <button
              class="rounded-full border border-rose-500/70 px-3 py-1.5 text-xs font-semibold text-rose-200 disabled:opacity-50"
              :disabled="request.status !== 'pending' || !!decisionLoading[request.id]"
              @click="decideUpgradeRequest(request, 'reject')"
            >
              {{ t("adminConsole.reject") }}
            </button>
          </div>
        </article>
        <p v-if="!upgradeRequests.length && !upgradeLoading" class="text-sm text-slate-400">{{ t("adminConsole.noUpgradeRequestsYet") }}</p>
      </div>
      <div class="ui-table-wrap hidden md:block">
        <table class="w-full min-w-[860px] text-sm">
          <thead class="bg-slate-900/70 text-slate-300">
            <tr>
              <th class="px-4 py-3 text-left">{{ t("adminConsole.when") }}</th>
              <th class="px-4 py-3 text-left">{{ t("adminConsole.tenant") }}</th>
              <th class="px-4 py-3 text-left">{{ t("adminConsole.from") }}</th>
              <th class="px-4 py-3 text-left">{{ t("adminConsole.to") }}</th>
              <th class="px-4 py-3 text-left">{{ t("adminConsole.payment") }}</th>
              <th class="px-4 py-3 text-left">{{ t("common.status") }}</th>
              <th class="px-4 py-3 text-left">{{ t("adminConsole.actions") }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="request in upgradeRequests" :key="request.id" class="border-t border-slate-800">
              <td class="px-4 py-3 text-slate-300">{{ new Date(request.requested_at).toLocaleString() }}</td>
              <td class="px-4 py-3 text-slate-100">{{ request.tenant_slug }}</td>
              <td class="px-4 py-3 text-slate-300">{{ request.current_plan_name }}</td>
              <td class="px-4 py-3 text-slate-300">
                <span>{{ request.target_plan_name }}</span>
                <span v-if="request.target_plan_is_active === false" class="ml-2 text-xs text-amber-300">({{ t("adminConsole.inactive") }})</span>
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
                    {{ t("adminConsole.approve") }}
                  </button>
                  <button
                    class="rounded-full border border-rose-500/70 px-3 py-1 text-xs font-semibold text-rose-200 disabled:opacity-50"
                    :disabled="request.status !== 'pending' || !!decisionLoading[request.id]"
                    @click="decideUpgradeRequest(request, 'reject')"
                  >
                    {{ t("adminConsole.reject") }}
                  </button>
                </div>
              </td>
            </tr>
            <tr v-if="!upgradeRequests.length && !upgradeLoading">
              <td colspan="7" class="px-4 py-3 text-slate-400">{{ t("adminConsole.noUpgradeRequestsYet") }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section v-if="activeAdminView === 'plans'" class="ui-workspace-stage p-4 space-y-3">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p class="text-sm text-slate-300">{{ t("adminConsole.planFeatureFlags") }}</p>
          <h2 class="ui-display text-2xl font-semibold">{{ t("adminConsole.planFeatureControls") }}</h2>
          <p class="text-xs text-slate-500">{{ t("adminConsole.planFeatureControlsHint") }}</p>
        </div>
        <div class="ui-scroll-row">
          <button class="ui-btn-outline px-3 py-1.5 text-xs" @click="adminPanels.planFlags = !adminPanels.planFlags">
            {{ adminPanels.planFlags ? t("adminConsole.hide") : t("adminConsole.show") }}
          </button>
          <button class="ui-btn-outline px-4 py-2 text-sm disabled:opacity-50" :disabled="planFlagsLoading || !adminPanels.planFlags" @click="fetchPlanFeatureFlags">
            {{ t("common.refresh") }}
          </button>
        </div>
      </div>
      <template v-if="adminPanels.planFlags">
      <p v-if="planFlagsLoading" class="text-sm text-slate-400">{{ t("adminConsole.loadingPlanFeatureFlags") }}</p>
      <p v-else-if="!planFeatureRows.length" class="text-sm text-slate-400">{{ t("adminConsole.noPlanFeatureFlags") }}</p>
      <div v-else class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        <article
          v-for="plan in planFeatureRows"
          :key="`plan-flag-${plan.plan_code}`"
          class="rounded-xl border border-slate-800 bg-slate-900/80 p-3 space-y-3"
        >
          <div class="flex items-center justify-between gap-2">
            <div>
              <p class="font-semibold text-slate-100">{{ plan.plan_name }}</p>
              <p class="text-[11px] text-slate-500">{{ plan.plan_code?.toUpperCase() }}</p>
            </div>
            <span
              class="rounded-full px-2 py-1 text-[10px] font-semibold"
              :class="plan.plan_is_active ? 'bg-emerald-500/20 text-emerald-200' : 'bg-slate-700/60 text-slate-300'"
            >
              {{ plan.plan_is_active ? t("common.available") : t("adminConsole.inactive") }}
            </span>
          </div>
          <div class="space-y-2">
            <div
              v-for="flag in plan.feature_flags"
              :key="`${plan.plan_code}-${flag.key}`"
              class="ui-admin-subcard space-y-2"
            >
              <div class="flex items-start justify-between gap-2">
                <div class="min-w-0">
                  <p class="text-xs font-semibold text-slate-100">{{ flag.label || flag.key }}</p>
                  <p class="text-[11px] text-slate-400">{{ flag.description || "-" }}</p>
                </div>
                <label class="inline-flex items-center gap-2 text-xs text-slate-300">
                  <input v-model="flag.enabled" type="checkbox" class="h-4 w-4 rounded border-slate-600 bg-slate-900" />
                </label>
              </div>
              <textarea
                v-model="flag.configText"
                rows="3"
                class="ui-input w-full px-2 py-1 text-xs font-mono"
                :placeholder="t('adminConsole.flagConfigPlaceholder')"
              />
              <div class="flex items-center justify-between gap-2">
                <span class="text-[11px] text-slate-500">{{ flag.key }}</span>
                <button
                  class="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-100 hover:border-brand-primary disabled:opacity-50"
                  :disabled="!!planFlagSaving[planFlagStateKey(plan.plan_code, flag.key)]"
                  @click="savePlanFeatureFlag(plan, flag)"
                >
                  {{ planFlagSaving[planFlagStateKey(plan.plan_code, flag.key)] ? t("common.saving") : t("adminConsole.saveFlag") }}
                </button>
              </div>
            </div>
          </div>
        </article>
      </div>
      </template>
    </section>

    <section v-if="activeAdminView === 'monitoring'" class="ui-workspace-stage p-4 space-y-3">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <h2 class="ui-display text-2xl font-semibold">{{ t("adminConsole.provisioningJobs") }}</h2>
        <div class="ui-scroll-row">
          <button class="ui-btn-outline px-3 py-1.5 text-xs" @click="adminPanels.jobs = !adminPanels.jobs">
            {{ adminPanels.jobs ? t("adminConsole.hide") : t("adminConsole.show") }}
          </button>
          <button class="ui-btn-outline px-4 py-2 text-sm disabled:opacity-50" :disabled="loading || !adminPanels.jobs" @click="fetchJobs">{{ t("common.refresh") }}</button>
        </div>
      </div>
      <template v-if="adminPanels.jobs">
      <p v-if="loading" class="text-sm text-slate-400">{{ t("adminConsole.loadingJobs") }}</p>
      <div class="space-y-2 md:hidden">
        <article
          v-for="job in jobs"
          :key="`job-mobile-${job.id}`"
          class="ui-admin-card space-y-2"
        >
          <div class="flex items-center justify-between gap-2">
            <p class="text-sm font-semibold text-slate-100">#{{ job.id }} - {{ job.lead_name }}</p>
            <span class="rounded-full px-2 py-1 text-xs font-semibold" :class="statusClass(job.status)">{{ job.status }}</span>
          </div>
          <p class="text-xs text-slate-400">{{ t("adminConsole.tenant") }}: {{ job.tenant_slug || '-' }}</p>
          <p class="text-xs text-slate-400">{{ t("adminConsole.updated") }}: {{ new Date(job.updated_at).toLocaleString() }}</p>
          <p class="rounded-lg border border-slate-800 bg-slate-950/50 p-2 text-xs text-slate-300 whitespace-pre-wrap break-words">{{ job.log || "-" }}</p>
        </article>
        <p v-if="!jobs.length && !loading" class="text-sm text-slate-400">{{ t("adminConsole.noJobsYet") }}</p>
      </div>

      <div class="ui-table-wrap hidden md:block">
        <table class="w-full min-w-[920px] text-sm">
          <thead class="bg-slate-900/70 text-slate-300">
            <tr>
              <th class="px-4 py-3 text-left">{{ t("adminConsole.id") }}</th>
              <th class="px-4 py-3 text-left">{{ t("adminConsole.lead") }}</th>
              <th class="px-4 py-3 text-left">{{ t("adminConsole.tenant") }}</th>
              <th class="px-4 py-3 text-left">{{ t("common.status") }}</th>
              <th class="px-4 py-3 text-left">{{ t("adminConsole.log") }}</th>
              <th class="px-4 py-3 text-left">{{ t("adminConsole.updated") }}</th>
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
              <td colspan="6" class="px-4 py-3 text-slate-400">{{ t("adminConsole.noJobsYet") }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      </template>
    </section>

    <section v-if="activeAdminView === 'monitoring'" class="ui-workspace-stage p-4 space-y-3">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <h2 class="ui-display text-2xl font-semibold">{{ t("adminConsole.securityAuditLog") }}</h2>
        <div class="ui-scroll-row">
          <button class="ui-btn-outline px-3 py-1.5 text-xs" @click="adminPanels.audit = !adminPanels.audit">
            {{ adminPanels.audit ? t("adminConsole.hide") : t("adminConsole.show") }}
          </button>
          <label class="text-xs text-slate-400">
            {{ t("adminConsole.pageSize") }}
            <select v-model.number="auditPageSize" class="ui-input ml-2 px-2 py-1 text-xs">
              <option :value="25">25</option>
              <option :value="50">50</option>
              <option :value="100">100</option>
            </select>
          </label>
          <button
            class="ui-btn-outline px-3 py-1.5 text-xs disabled:opacity-50"
            :disabled="!auditHasPrev"
            @click="changeAuditPage(auditPage - 1)"
          >
            {{ t("common.previous") }}
          </button>
          <button
            class="ui-btn-outline px-3 py-1.5 text-xs disabled:opacity-50"
            :disabled="!auditHasNext"
            @click="changeAuditPage(auditPage + 1)"
          >
            {{ t("common.next") }}
          </button>
          <button class="ui-btn-outline px-4 py-2 text-sm disabled:opacity-50" :disabled="auditLoading || !adminPanels.audit" @click="fetchAuditLogs(auditPage)">{{ t("common.refresh") }}</button>
        </div>
      </div>
      <template v-if="adminPanels.audit">
      <p class="text-xs text-slate-500">
        {{ t("adminConsole.pageEntriesSummary", { page: auditPage, pages: auditTotalPages, total: auditTotal }) }}
      </p>
      <p v-if="auditLoading" class="text-sm text-slate-400">{{ t("adminConsole.loadingAuditLogs") }}</p>
      <div class="space-y-2 md:hidden">
        <article
          v-for="entry in auditLogs"
          :key="`audit-mobile-${entry.id}`"
          class="ui-admin-card space-y-2"
        >
          <div class="flex items-center justify-between gap-2">
            <p class="text-sm font-semibold text-slate-100">{{ entry.action }}</p>
            <p class="text-[11px] text-slate-500">{{ new Date(entry.created_at).toLocaleString() }}</p>
          </div>
          <p class="text-xs text-slate-400">{{ t("adminConsole.actor") }}: {{ entry.actor_username || t("adminConsole.system") }}</p>
          <p class="text-xs text-slate-400">{{ t("adminConsole.target") }}: {{ entry.target_repr || entry.tenant_slug || entry.lead_name || "-" }}</p>
          <p class="rounded-lg border border-slate-800 bg-slate-950/50 p-2 text-xs text-slate-300 whitespace-pre-wrap break-words">{{ formatAuditMetadata(entry.metadata) }}</p>
        </article>
        <p v-if="!auditLogs.length && !auditLoading" class="text-sm text-slate-400">{{ t("adminConsole.noAuditEntriesYet") }}</p>
      </div>
      <div class="ui-table-wrap hidden md:block">
        <table class="w-full min-w-[860px] text-sm">
          <thead class="bg-slate-900/70 text-slate-300">
            <tr>
              <th class="px-4 py-3 text-left">{{ t("adminConsole.when") }}</th>
              <th class="px-4 py-3 text-left">{{ t("adminConsole.action") }}</th>
              <th class="px-4 py-3 text-left">{{ t("adminConsole.actor") }}</th>
              <th class="px-4 py-3 text-left">{{ t("adminConsole.target") }}</th>
              <th class="px-4 py-3 text-left">{{ t("adminConsole.details") }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="entry in auditLogs" :key="entry.id" class="border-t border-slate-800">
              <td class="px-4 py-3 text-slate-300">{{ new Date(entry.created_at).toLocaleString() }}</td>
              <td class="px-4 py-3 text-slate-100">{{ entry.action }}</td>
              <td class="px-4 py-3 text-slate-300">{{ entry.actor_username || t("adminConsole.system") }}</td>
              <td class="px-4 py-3 text-slate-300">{{ entry.target_repr || entry.tenant_slug || entry.lead_name || "-" }}</td>
              <td class="px-4 py-3 text-slate-400 max-w-[360px] whitespace-pre-wrap text-xs">{{ formatAuditMetadata(entry.metadata) }}</td>
            </tr>
            <tr v-if="!auditLogs.length && !auditLoading">
              <td colspan="5" class="px-4 py-3 text-slate-400">{{ t("adminConsole.noAuditEntriesYet") }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      </template>
    </section>

    <section v-if="lastProvision && activeAdminView === 'operations'" class="ui-workspace-stage p-4 space-y-4 text-sm text-slate-200">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p class="ui-kicker">{{ t("adminConsole.latestProvisioningPackage") }}</p>
          <h3 class="text-xl font-semibold text-white">{{ lastProvision.tenant || "-" }}</h3>
          <p class="text-sm text-slate-400">{{ lastProvision.public_menu_url || lastProvision.tenant_url || "-" }}</p>
        </div>
        <div class="flex flex-wrap gap-2">
          <button class="ui-btn-outline px-3 py-1.5 text-xs" @click="copyOnboardingPackage">{{ t("adminConsole.copyPackage") }}</button>
          <button
            v-if="lastProvision.whatsapp_message_template"
            class="ui-btn-outline px-3 py-1.5 text-xs"
            @click="copyText(lastProvision.whatsapp_message_template)"
          >
            {{ t("adminConsole.copyMessage") }}
          </button>
          <button class="ui-btn-outline px-3 py-1.5 text-xs" @click="lastProvision = null">{{ t("common.clear") }}</button>
        </div>
      </div>

      <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <article class="ui-stat-tile">
          <p class="ui-stat-label">{{ t("adminConsole.tenantUrl") }}</p>
          <p class="mt-2 break-all text-sm font-semibold text-white">{{ lastProvision.tenant_url || "-" }}</p>
          <button v-if="lastProvision.tenant_url" class="mt-3 text-xs text-brand-secondary hover:underline" @click="copyText(lastProvision.tenant_url)">{{ t("common.copy") }}</button>
        </article>
        <article class="ui-stat-tile">
          <p class="ui-stat-label">{{ t("adminConsole.workspaceUrl") }}</p>
          <p class="mt-2 break-all text-sm font-semibold text-white">{{ lastProvision.workspace_url || "-" }}</p>
          <button v-if="lastProvision.workspace_url" class="mt-3 text-xs text-brand-secondary hover:underline" @click="copyText(lastProvision.workspace_url)">{{ t("common.copy") }}</button>
        </article>
        <article class="ui-stat-tile">
          <p class="ui-stat-label">{{ t("adminConsole.activationUrl") }}</p>
          <p class="mt-2 break-all text-sm font-semibold text-white">{{ lastProvision.activation_url || "-" }}</p>
          <button v-if="lastProvision.activation_url" class="mt-3 text-xs text-brand-secondary hover:underline" @click="copyText(lastProvision.activation_url)">{{ t("common.copy") }}</button>
        </article>
        <article class="ui-stat-tile">
          <p class="ui-stat-label">{{ t("adminConsole.activationToken") }}</p>
          <p class="mt-2 break-all text-sm font-semibold text-white">{{ lastProvision.activation_token || "-" }}</p>
          <button v-if="lastProvision.activation_token" class="mt-3 text-xs text-brand-secondary hover:underline" @click="copyText(lastProvision.activation_token)">{{ t("common.copy") }}</button>
        </article>
      </div>

      <div class="grid gap-4 xl:grid-cols-[minmax(0,1.1fr),420px]">
        <article class="ui-focus-card space-y-3">
          <div class="space-y-1">
            <p class="ui-kicker">{{ t("adminConsole.ownerNextSteps") }}</p>
            <p class="text-sm text-slate-300">{{ t("adminConsole.provisioningOperations") }}</p>
          </div>
          <ol v-if="lastProvision.owner_next_steps?.length" class="space-y-2 text-sm text-slate-200">
            <li v-for="(step, index) in lastProvision.owner_next_steps" :key="step" class="flex items-start gap-3 rounded-xl border border-slate-800/80 bg-slate-950/50 px-3 py-2.5">
              <span class="mt-0.5 inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[var(--color-secondary)]/15 text-xs font-semibold text-[var(--color-secondary)]">{{ index + 1 }}</span>
              <span class="leading-6">{{ step }}</span>
            </li>
          </ol>
          <p v-else class="text-sm text-slate-500">-</p>
        </article>

        <article class="ui-command-deck space-y-3">
          <div class="space-y-1">
            <p class="ui-kicker">{{ t("adminConsole.whatsappMessageTemplate") }}</p>
            <p class="text-sm text-slate-300">{{ t("adminConsole.whatsappLink") }}</p>
          </div>
          <div class="space-y-2">
            <div class="rounded-xl border border-slate-800/80 bg-slate-950/50 px-3 py-2.5">
              <p class="text-[11px] uppercase tracking-[0.18em] text-slate-500">{{ t("adminConsole.whatsappLink") }}</p>
              <p class="mt-2 break-all text-xs text-slate-200">{{ lastProvision.whatsapp_link || "-" }}</p>
              <button v-if="lastProvision.whatsapp_link" class="mt-2 text-xs text-brand-secondary hover:underline" @click="copyText(lastProvision.whatsapp_link)">{{ t("common.copy") }}</button>
            </div>
            <pre class="rounded-xl border border-slate-800 bg-slate-950/60 p-3 text-xs whitespace-pre-wrap break-all">{{ lastProvision.whatsapp_message_template || "-" }}</pre>
          </div>
        </article>
      </div>
    </section>

    <nav class="ui-bottom-dock md:hidden">
      <div class="ui-bottom-dock-grid grid-cols-4">
        <button
          class="ui-pill-nav ui-touch-target justify-center text-center text-[11px]"
          :class="activeAdminView === 'operations' ? 'border-brand-secondary bg-brand-secondary/10 text-brand-secondary' : ''"
          @click="selectAdminView('operations')"
        >
          {{ t("adminConsole.provisioningOperations") }}
        </button>
        <button
          class="ui-pill-nav ui-touch-target justify-center text-center text-[11px]"
          :class="activeAdminView === 'tenants' ? 'border-brand-secondary bg-brand-secondary/10 text-brand-secondary' : ''"
          @click="selectAdminView('tenants')"
        >
          {{ t("adminConsole.tenantLifecycleControls") }}
        </button>
        <button
          class="ui-pill-nav ui-touch-target justify-center text-center text-[11px]"
          :class="activeAdminView === 'monitoring' ? 'border-brand-secondary bg-brand-secondary/10 text-brand-secondary' : ''"
          @click="selectAdminView('monitoring')"
        >
          {{ t("adminConsole.reservationFollowUpSla") }}
        </button>
        <button
          class="ui-pill-nav ui-touch-target justify-center text-center text-[11px]"
          :class="activeAdminView === 'plans' ? 'border-brand-secondary bg-brand-secondary/10 text-brand-secondary' : ''"
          @click="selectAdminView('plans')"
        >
          {{ t("adminConsole.planFeatureFlags") }}
        </button>
      </div>
    </nav>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import adminApi from "../lib/adminApi";
import { useI18n } from "../composables/useI18n";
import { useToastStore } from "../stores/toast";
import { getPrimaryPublicHost } from "../lib/runtimeHost";

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
const inferDomainSuffix = () => {
  if (typeof window === "undefined") return "localhost";
  const configuredPublicHost = getPrimaryPublicHost();
  if (configuredPublicHost) return configuredPublicHost;
  const host = String(window.location.hostname || "").trim().toLowerCase().replace(/^www\./, "");
  if (!host) return "localhost";
  if (host === "localhost" || host === "127.0.0.1" || host.endsWith(".localhost")) return "localhost";
  const parts = host.split(".").filter(Boolean);
  if (parts.length >= 3 && parts[parts.length - 1].length === 2 && parts[parts.length - 2].length <= 3) {
    return parts.slice(-3).join(".");
  }
  if (parts.length >= 2) return parts.slice(-2).join(".");
  return host;
};
const inferredDomainSuffix = inferDomainSuffix();
const domainSuffix = ref("");
const upgradeRequests = ref([]);
const upgradeLoading = ref(false);
const decisionLoading = ref({});
const planFeatureRows = ref([]);
const planFlagsLoading = ref(false);
const planFlagSaving = ref({});
const adminPanels = ref({
  alerts: false,
  planFlags: false,
  jobs: false,
  audit: false,
});
const tenants = ref([]);
const tenantsLoading = ref(false);
const tenantPage = ref(1);
const tenantPageSize = ref(25);
const tenantTotal = ref(0);
const tenantTotalPages = ref(1);
const tenantHasNext = ref(false);
const tenantHasPrev = ref(false);
const tenantLifecycleLoading = ref({});
const tenantExportLoading = ref({});
const tenantImportLoading = ref({});
const tenantImportInputs = new Map();
const tenantTools = ref({});
const tenantTimeline = ref({});
const activeAdminView = ref("operations");
const loadedAdminViews = ref({
  operations: false,
  tenants: false,
  monitoring: false,
  plans: false,
});
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
const { t } = useI18n();
const lastProvision = ref(null);
const auditLogs = ref([]);
const auditPage = ref(1);
const auditPageSize = ref(50);
const auditTotal = ref(0);
const auditTotalPages = ref(1);
const auditHasNext = ref(false);
const auditHasPrev = ref(false);
let tenantsRequestController = null;
const tenantTimelineControllers = new Map();
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
const normalizeSuffix = (value) => String(value || "").trim().replace(/^\.+/, "");
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
    `${t("adminConsole.tenant")}: ${p.tenant || "-"}`,
    `${t("adminConsole.tenantUrl")}: ${p.tenant_url || "-"}`,
    `${t("adminConsole.workspaceUrl")}: ${p.workspace_url || "-"}`,
    `${t("adminConsole.onboardingUrl")}: ${p.onboarding_url || "-"}`,
    `${t("adminConsole.signInUrl")}: ${p.signin_url || "-"}`,
    `${t("adminConsole.activationUrl")}: ${p.activation_url || "-"}`,
    `${t("adminConsole.publicMenuUrl")}: ${p.public_menu_url || "-"}`,
    `${t("adminConsole.activationToken")}: ${p.activation_token || "-"}`,
    `${t("adminConsole.whatsappLink")}: ${p.whatsapp_link || "-"}`,
    "",
    `${t("adminConsole.ownerNextSteps")}:`,
    ...(Array.isArray(p.owner_next_steps) && p.owner_next_steps.length ? p.owner_next_steps.map((step, index) => `${index + 1}. ${step}`) : ["-"]),
    "",
    `${t("adminConsole.whatsappMessageTemplate")}:`,
    p.whatsapp_message_template || "-",
  ].join("\n");
});
const adminViewLabels = computed(() => ({
  operations: t("adminConsole.provisioningOperations"),
  tenants: t("adminConsole.tenantLifecycleControls"),
  monitoring: t("adminConsole.reservationFollowUpSla"),
  plans: t("adminConsole.planFeatureFlags"),
}));
const activeAdminViewLabel = computed(() => adminViewLabels.value[activeAdminView.value] || adminViewLabels.value.operations);
const activeAdminViewTitle = computed(() => {
  if (activeAdminView.value === "tenants") return t("adminConsole.suspendReactivateCancel");
  if (activeAdminView.value === "monitoring") return t("adminConsole.reservationFollowUpSla");
  if (activeAdminView.value === "plans") return t("adminConsole.planFeatureControls");
  return t("adminConsole.provisioningOperations");
});
const currentDomainSuffixLabel = computed(() => `${t("adminConsole.suffixOptional")}: ${normalizeSuffix(domainSuffix.value) || inferredDomainSuffix}`);
const activeAdminViewLoading = computed(() => {
  if (activeAdminView.value === "operations") return leadsLoading.value || upgradeLoading.value;
  if (activeAdminView.value === "tenants") return tenantsLoading.value;
  if (activeAdminView.value === "monitoring") return alertsLoading.value || loading.value || auditLoading.value;
  if (activeAdminView.value === "plans") return planFlagsLoading.value;
  return false;
});
const activeAdminMetrics = computed(() => {
  if (activeAdminView.value === "tenants") {
    const activeCount = tenants.value.filter((tenant) => tenant.lifecycle_status === "active").length;
    const pausedCount = tenants.value.filter((tenant) => tenant.lifecycle_status === "suspended").length;
    return [
      { label: t("adminConsole.tenantLifecycleControls"), value: tenantTotal.value, note: t("adminConsole.pageSummary", { page: tenantPage.value, pages: tenantTotalPages.value, total: tenantTotal.value }), valueClass: "" },
      { label: t("common.available"), value: activeCount, note: t("adminConsole.tenantLifecycleControls"), valueClass: "text-emerald-300" },
      { label: t("adminConsole.suspend"), value: pausedCount, note: t("adminConsole.suspendReactivateCancel"), valueClass: "text-amber-300" },
      { label: t("common.status"), value: activeAdminViewLoading.value ? t("common.loading") : t("common.available"), note: currentDomainSuffixLabel.value, valueClass: "text-base md:text-2xl" },
    ];
  }

  if (activeAdminView.value === "monitoring") {
    return [
      { label: t("adminConsole.totalAlerts"), value: alertCounts.value.total_alerts || reservationAlerts.value.length, note: t("adminConsole.reservationFollowUpSla"), valueClass: "text-amber-300" },
      { label: t("adminConsole.provisioningJobs"), value: jobs.value.length, note: adminPanels.value.jobs ? t("common.available") : t("adminConsole.hide"), valueClass: "" },
      { label: t("adminConsole.securityAuditLog"), value: auditTotal.value || auditLogs.value.length, note: adminPanels.value.audit ? t("common.available") : t("adminConsole.hide"), valueClass: "" },
      { label: t("common.status"), value: activeAdminViewLoading.value ? t("common.loading") : t("common.available"), note: currentDomainSuffixLabel.value, valueClass: "text-base md:text-2xl" },
    ];
  }

  if (activeAdminView.value === "plans") {
    const activePlans = planFeatureRows.value.filter((plan) => plan.plan_is_active).length;
    const enabledFlags = planFeatureRows.value.reduce(
      (count, plan) => count + plan.feature_flags.filter((flag) => flag.enabled).length,
      0
    );
    return [
      { label: t("common.plan"), value: planFeatureRows.value.length, note: t("adminConsole.planFeatureFlags"), valueClass: "" },
      { label: t("common.available"), value: activePlans, note: t("adminConsole.planFeatureControls"), valueClass: "text-emerald-300" },
      { label: t("adminConsole.planFeatureFlags"), value: enabledFlags, note: t("adminConsole.saveFlag"), valueClass: "text-brand-secondary" },
      { label: t("common.status"), value: activeAdminViewLoading.value ? t("common.loading") : t("common.available"), note: currentDomainSuffixLabel.value, valueClass: "text-base md:text-2xl" },
    ];
  }

  return [
    { label: t("adminConsole.incomingLeads"), value: leads.value.length, note: t("adminConsole.awaitingProvisioning"), valueClass: "" },
    { label: t("adminConsole.tierUpgradeRequests"), value: upgradeRequests.value.length, note: t("adminConsole.cashFirstUpgrades"), valueClass: "text-brand-secondary" },
    { label: t("adminConsole.latestProvisioningPackage"), value: lastProvision.value ? 1 : 0, note: lastProvision.value?.tenant || t("common.clear"), valueClass: lastProvision.value ? "text-emerald-300" : "text-slate-200" },
    { label: t("common.status"), value: activeAdminViewLoading.value ? t("common.loading") : t("common.available"), note: currentDomainSuffixLabel.value, valueClass: "text-base md:text-2xl" },
  ];
});

const parseFlagConfigText = (text) => {
  const raw = String(text || "").trim();
  if (!raw) return null;
  return JSON.parse(raw);
};

const toConfigText = (value) => {
  if (value === null || value === undefined || value === "") return "";
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return "";
  }
};

const normalizePlanFeatureRow = (row) => ({
  ...row,
  feature_flags: Array.isArray(row?.feature_flags)
    ? row.feature_flags.map((flag) => ({
        ...flag,
        configText: toConfigText(flag?.config),
      }))
    : [],
});

const planFlagStateKey = (planCode, key) => `${String(planCode || "").trim().toLowerCase()}:${String(key || "").trim().toLowerCase()}`;
const tenantToolsExpanded = (tenantId) => Boolean(tenantTools.value[String(tenantId || "")]);
const toggleTenantTools = (tenantId) => {
  const key = String(tenantId || "");
  if (!key) return;
  tenantTools.value = {
    ...tenantTools.value,
    [key]: !tenantToolsExpanded(key),
  };
};

const fetchPlanFeatureFlags = async () => {
  planFlagsLoading.value = true;
  try {
    const res = await adminApi.get("/admin-plan-feature-flags/");
    const rows = Array.isArray(res?.data?.plans) ? res.data.plans : [];
    planFeatureRows.value = rows.map((row) => normalizePlanFeatureRow(row));
    loadedAdminViews.value = { ...loadedAdminViews.value, plans: true };
  } catch (err) {
    const msg = parseApiError(err, t("adminConsole.loadPlanFeatureFlagsFailed"));
    error.value = msg;
    toast.show(msg, "error");
  } finally {
    planFlagsLoading.value = false;
  }
};

const savePlanFeatureFlag = async (plan, flag) => {
  const planCode = String(plan?.plan_code || "").trim();
  const key = String(flag?.key || "").trim();
  if (!planCode || !key) return;
  const stateKey = planFlagStateKey(planCode, key);
  planFlagSaving.value = { ...planFlagSaving.value, [stateKey]: true };
  try {
    let config = null;
    try {
      config = parseFlagConfigText(flag.configText);
    } catch {
      const msg = t("adminConsole.invalidFlagConfig");
      error.value = msg;
      toast.show(msg, "error");
      return;
    }

    const res = await adminApi.put(`/admin-plan-feature-flags/${planCode}/`, {
      feature_flags: [
        {
          key,
          enabled: Boolean(flag.enabled),
          config,
        },
      ],
    });
    const updatedPlan = res?.data?.plan;
    if (updatedPlan && typeof updatedPlan === "object") {
      planFeatureRows.value = planFeatureRows.value.map((row) =>
        row.plan_code === updatedPlan.plan_code ? normalizePlanFeatureRow(updatedPlan) : row
      );
    } else {
      flag.configText = toConfigText(config);
    }
    toast.show(t("adminConsole.planFeatureFlagSaved", { plan: planCode.toUpperCase(), key }), "success");
  } catch (err) {
    const msg = parseApiError(err, t("adminConsole.savePlanFeatureFlagFailed"));
    error.value = msg;
    toast.show(msg, "error");
  } finally {
    planFlagSaving.value = { ...planFlagSaving.value, [stateKey]: false };
  }
};

const fetchJobs = async () => {
  loading.value = true;
  error.value = null;
  try {
    const res = await adminApi.get("/provision-jobs/");
    jobs.value = res.data;
    loadedAdminViews.value = { ...loadedAdminViews.value, monitoring: true };
  } catch (err) {
    error.value = parseApiError(err, t("adminConsole.loadJobsFailed"));
  } finally {
    loading.value = false;
  }
};

const fetchUpgradeRequests = async () => {
  upgradeLoading.value = true;
  try {
    const res = await adminApi.get("/admin-tier-upgrade-requests/");
    upgradeRequests.value = Array.isArray(res.data) ? res.data : [];
    loadedAdminViews.value = { ...loadedAdminViews.value, operations: true };
  } catch (err) {
    const msg = parseApiError(err, t("adminConsole.loadUpgradeRequestsFailed"));
    error.value = msg;
    toast.show(msg, "error");
  } finally {
    upgradeLoading.value = false;
  }
};

const fetchAuditLogs = async (page = auditPage.value) => {
  const requestedPage = Number.isFinite(Number(page)) ? Math.max(1, Number.parseInt(page, 10)) : 1;
  auditLoading.value = true;
  try {
    const res = await adminApi.get("/admin-audit-logs/", {
      params: {
        page: requestedPage,
        page_size: auditPageSize.value,
      },
    });
    const payload = res?.data;
    if (Array.isArray(payload)) {
      auditLogs.value = payload.slice(0, auditPageSize.value);
      auditPage.value = 1;
      auditTotal.value = payload.length;
      auditTotalPages.value = 1;
      auditHasNext.value = false;
      auditHasPrev.value = false;
      return;
    }

    auditLogs.value = Array.isArray(payload?.results) ? payload.results : [];
    const pagination = payload?.pagination || {};
    auditPage.value = Number.parseInt(pagination.page, 10) || requestedPage;
    auditTotal.value = Number.parseInt(pagination.total, 10) || 0;
    auditTotalPages.value = Number.parseInt(pagination.total_pages, 10) || 1;
    auditHasNext.value = Boolean(pagination.has_next);
    auditHasPrev.value = Boolean(pagination.has_prev);
    loadedAdminViews.value = { ...loadedAdminViews.value, monitoring: true };
  } catch (err) {
    const msg = parseApiError(err, t("adminConsole.loadAuditLogsFailed"));
    error.value = msg;
    toast.show(msg, "error");
  } finally {
    auditLoading.value = false;
  }
};

const changeAuditPage = async (nextPage) => {
  const page = Number.parseInt(nextPage, 10);
  if (!Number.isFinite(page) || page < 1 || page > auditTotalPages.value) return;
  await fetchAuditLogs(page);
};

const fetchLeads = async () => {
  leadsLoading.value = true;
  try {
    const res = await adminApi.get("/leads/");
    leads.value = res.data;
    previews.value = {};
    previewLoading.value = {};
    loadedAdminViews.value = { ...loadedAdminViews.value, operations: true };
  } catch (err) {
    const msg = parseApiError(err, t("adminConsole.loadLeadsFailed"));
    error.value = msg;
    toast.show(msg, "error");
  } finally {
    leadsLoading.value = false;
  }
};

const fetchTenants = async (page = tenantPage.value) => {
  const requestedPage = Number.isFinite(Number(page)) ? Math.max(1, Number.parseInt(page, 10)) : 1;
  if (tenantsRequestController) {
    tenantsRequestController.abort();
  }
  const controller = new AbortController();
  tenantsRequestController = controller;
  tenantsLoading.value = true;
  try {
    const res = await adminApi.get("/admin-tenants/", {
      signal: controller.signal,
      params: {
        page: requestedPage,
        page_size: tenantPageSize.value,
      },
    });
    const payload = res?.data;
    if (Array.isArray(payload)) {
      tenants.value = payload;
      tenantPage.value = 1;
      tenantTotal.value = payload.length;
      tenantTotalPages.value = 1;
      tenantHasNext.value = false;
      tenantHasPrev.value = false;
      return;
    }
    tenants.value = Array.isArray(payload?.results) ? payload.results : [];
    const pagination = payload?.pagination || {};
    tenantPage.value = Number.parseInt(pagination.page, 10) || requestedPage;
    tenantTotal.value = Number.parseInt(pagination.total, 10) || 0;
    tenantTotalPages.value = Number.parseInt(pagination.total_pages, 10) || 1;
    tenantHasNext.value = Boolean(pagination.has_next);
    tenantHasPrev.value = Boolean(pagination.has_prev);
    loadedAdminViews.value = { ...loadedAdminViews.value, tenants: true };
  } catch (err) {
    if (err?.code === "ERR_CANCELED") return;
    const msg = parseApiError(err, t("adminConsole.loadTenantsFailed"));
    error.value = msg;
    toast.show(msg, "error");
  } finally {
    if (tenantsRequestController === controller) {
      tenantsRequestController = null;
    }
    tenantsLoading.value = false;
  }
};

const changeTenantPage = async (nextPage) => {
  const page = Number.parseInt(nextPage, 10);
  if (!Number.isFinite(page) || page < 1 || page > tenantTotalPages.value) return;
  await fetchTenants(page);
};

const tenantTimelineDefaults = () => ({
  expanded: false,
  loaded: false,
  loading: false,
  items: [],
  page: 1,
  total: 0,
  totalPages: 1,
  hasNext: false,
  hasPrev: false,
});

const getTenantTimelineState = (tenantId) => {
  const key = String(tenantId || "");
  if (!key) return tenantTimelineDefaults();
  return tenantTimeline.value[key] || tenantTimelineDefaults();
};

const ensureTenantTimelineState = (tenantId) => {
  const key = String(tenantId || "");
  if (!key) return tenantTimelineDefaults();
  const existing = tenantTimeline.value[key];
  if (existing) return existing;
  const created = tenantTimelineDefaults();
  tenantTimeline.value = { ...tenantTimeline.value, [key]: created };
  return created;
};

const patchTenantTimelineState = (tenantId, patch) => {
  const key = String(tenantId || "");
  if (!key) return;
  const current = ensureTenantTimelineState(key);
  tenantTimeline.value = {
    ...tenantTimeline.value,
    [key]: {
      ...current,
      ...patch,
    },
  };
};

const tenantTimelineEntries = (tenantId) => getTenantTimelineState(tenantId).items || [];
const tenantTimelineLoading = (tenantId) => Boolean(getTenantTimelineState(tenantId).loading);
const tenantTimelineExpanded = (tenantId) => Boolean(getTenantTimelineState(tenantId).expanded);
const tenantTimelinePage = (tenantId) => getTenantTimelineState(tenantId).page || 1;
const tenantTimelineTotal = (tenantId) => getTenantTimelineState(tenantId).total || 0;
const tenantTimelineTotalPages = (tenantId) => getTenantTimelineState(tenantId).totalPages || 1;
const tenantTimelineHasNext = (tenantId) => Boolean(getTenantTimelineState(tenantId).hasNext);
const tenantTimelineHasPrev = (tenantId) => Boolean(getTenantTimelineState(tenantId).hasPrev);

const fetchTenantTimeline = async (tenantId, page = 1) => {
  const requestedPage = Number.isFinite(Number(page)) ? Math.max(1, Number.parseInt(page, 10)) : 1;
  const key = String(tenantId || "");
  tenantTimelineControllers.get(key)?.abort();
  const controller = new AbortController();
  tenantTimelineControllers.set(key, controller);
  patchTenantTimelineState(tenantId, { loading: true });
  try {
    const res = await adminApi.get(`/admin-tenants/${tenantId}/timeline/`, {
      signal: controller.signal,
      params: {
        page: requestedPage,
        page_size: 10,
      },
    });
    const payload = res?.data;
    if (Array.isArray(payload)) {
      patchTenantTimelineState(tenantId, {
        items: payload.slice(0, 10),
        page: 1,
        total: payload.length,
        totalPages: 1,
        hasNext: false,
        hasPrev: false,
        loaded: true,
      });
      return;
    }
    const pagination = payload?.pagination || {};
    patchTenantTimelineState(tenantId, {
      items: Array.isArray(payload?.results) ? payload.results : [],
      page: Number.parseInt(pagination.page, 10) || requestedPage,
      total: Number.parseInt(pagination.total, 10) || 0,
      totalPages: Number.parseInt(pagination.total_pages, 10) || 1,
      hasNext: Boolean(pagination.has_next),
      hasPrev: Boolean(pagination.has_prev),
      loaded: true,
    });
  } catch (err) {
    if (err?.code === "ERR_CANCELED") return;
    const msg = parseApiError(err, t("adminConsole.loadTenantHistoryFailed"));
    error.value = msg;
    toast.show(msg, "error");
  } finally {
    if (tenantTimelineControllers.get(key) === controller) {
      tenantTimelineControllers.delete(key);
    }
    patchTenantTimelineState(tenantId, { loading: false });
  }
};

const toggleTenantTimeline = async (tenant) => {
  const tenantId = tenant?.id;
  if (!tenantId) return;
  const state = ensureTenantTimelineState(tenantId);
  const nextExpanded = !state.expanded;
  patchTenantTimelineState(tenantId, { expanded: nextExpanded });
  if (nextExpanded && !state.loaded) {
    await fetchTenantTimeline(tenantId, 1);
  }
};

const changeTenantTimelinePage = async (tenantId, nextPage) => {
  const page = Number.parseInt(nextPage, 10);
  if (!Number.isFinite(page) || page < 1 || page > tenantTimelineTotalPages(tenantId)) return;
  await fetchTenantTimeline(tenantId, page);
};

const setTenantImportInputRef = (tenantId, element) => {
  const key = String(tenantId || "");
  if (!key) return;
  if (element) {
    tenantImportInputs.set(key, element);
    return;
  }
  tenantImportInputs.delete(key);
};

const openTenantImportPicker = (tenantId) => {
  const key = String(tenantId || "");
  const input = tenantImportInputs.get(key);
  if (!input) {
    toast.show(t("adminConsole.importInputNotReady"), "error");
    return;
  }
  input.click();
};

const readFileAsText = (file) =>
  new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error(t("adminConsole.unableToReadFile")));
    reader.readAsText(file);
  });

const saveJsonFile = (filename, payload) => {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(objectUrl);
};

const exportTenantSettings = async (tenant) => {
  if (!tenant?.id) return;
  tenantExportLoading.value = { ...tenantExportLoading.value, [tenant.id]: true };
  try {
    const res = await adminApi.get(`/admin-tenants/${tenant.id}/settings-export/`);
    const payload = res?.data || {};
    const stamp = new Date().toISOString().replace(/[:.]/g, "-");
    const filename = `${tenant.slug || `tenant-${tenant.id}`}-settings-${stamp}.json`;
    saveJsonFile(filename, payload);
    toast.show(t("adminConsole.settingsExportDownloaded"), "success");
  } catch (err) {
    const msg = parseApiError(err, t("adminConsole.exportTenantSettingsFailed"));
    error.value = msg;
    toast.show(msg, "error");
  } finally {
    tenantExportLoading.value = { ...tenantExportLoading.value, [tenant.id]: false };
  }
};

const handleTenantImportFile = async (tenant, event) => {
  const input = event?.target;
  const file = input?.files?.[0];
  if (!file || !tenant?.id) return;
  tenantImportLoading.value = { ...tenantImportLoading.value, [tenant.id]: true };
  try {
    const text = await readFileAsText(file);
    let parsed;
    try {
      parsed = JSON.parse(text);
    } catch {
      throw new Error(t("adminConsole.invalidJsonFile"));
    }
    if (!parsed || typeof parsed !== "object") {
      throw new Error(t("adminConsole.importPayloadMustBeObject"));
    }

    const dryRunBody = Object.prototype.hasOwnProperty.call(parsed, "payload")
      ? { ...parsed, mode: "dry_run" }
      : { mode: "dry_run", payload: parsed };
    const dryRunRes = await adminApi.post(`/admin-tenants/${tenant.id}/settings-import/`, dryRunBody);
    const drySummary = dryRunRes?.data?.summary || {};
    const shouldApply = window.confirm(
      [
        t("adminConsole.dryRunSuccessful"),
        t("adminConsole.categoriesCount", { count: drySummary.categories || 0 }),
        t("adminConsole.dishesCount", { count: drySummary.dishes || 0 }),
        t("adminConsole.optionsCount", { count: drySummary.options || 0 }),
        t("adminConsole.tableLinksCount", { count: drySummary.table_links || 0 }),
        t("adminConsole.profileUpdated", { value: drySummary.profile_updated ? t("adminConsole.yes") : t("adminConsole.no") }),
        "",
        t("adminConsole.applyImportNow"),
      ].join("\n")
    );
    if (!shouldApply) {
      toast.show(t("adminConsole.dryRunCanceled"), "success");
      return;
    }

    const replaceBody = Object.prototype.hasOwnProperty.call(parsed, "payload")
      ? { ...parsed, mode: "replace" }
      : { mode: "replace", payload: parsed };
    const res = await adminApi.post(`/admin-tenants/${tenant.id}/settings-import/`, replaceBody);
    const summary = res?.data?.summary || {};
    toast.show(
      t("adminConsole.importComplete", {
        categories: summary.categories || 0,
        dishes: summary.dishes || 0,
        tables: summary.table_links || 0,
      }),
      "success"
    );
    await fetchTenants(tenantPage.value);
  } catch (err) {
    const msg = parseApiError(err, err instanceof Error ? err.message : t("adminConsole.importTenantSettingsFailed"));
    error.value = msg;
    toast.show(msg, "error");
  } finally {
    tenantImportLoading.value = { ...tenantImportLoading.value, [tenant.id]: false };
    if (input) input.value = "";
  }
};

const tenantLifecycleStatusClass = (status) => {
  if (status === "active") return "bg-emerald-500/20 text-emerald-200";
  if (status === "suspended") return "bg-amber-500/20 text-amber-200";
  if (status === "canceled") return "bg-rose-500/20 text-rose-200";
  return "bg-slate-700/60 text-slate-300";
};

const applyTenantLifecycle = async (tenant, action) => {
  if (!tenant?.id || !action) return;
  let reason = "";
  if (action === "cancel") {
    const value = window.prompt(t("adminConsole.cancellationReasonRequiredPrompt"), "");
    if (value === null) return;
    reason = value.trim();
    if (!reason) {
      toast.show(t("adminConsole.cancellationReasonRequired"), "error");
      return;
    }
  } else if (action === "suspend") {
    reason = (window.prompt(t("adminConsole.suspendReasonOptionalPrompt"), "") || "").trim();
  }

  tenantLifecycleLoading.value = { ...tenantLifecycleLoading.value, [tenant.id]: true };
  try {
    const res = await adminApi.put(`/admin-tenants/${tenant.id}/lifecycle/`, {
      action,
      reason,
    });
    const msg = res?.data?.detail || t("adminConsole.tenantActionDone", { action });
    toast.show(msg, "success");
    await fetchTenants(tenantPage.value);
  } catch (err) {
    const msg = parseApiError(err, t("adminConsole.updateTenantLifecycleFailed"));
    error.value = msg;
    toast.show(msg, "error");
  } finally {
    tenantLifecycleLoading.value = { ...tenantLifecycleLoading.value, [tenant.id]: false };
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
    loadedAdminViews.value = { ...loadedAdminViews.value, monitoring: true };
  } catch (err) {
    const msg = parseApiError(err, t("adminConsole.loadReservationAlertsFailed"));
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
    const resolvedSuffix = normalizeSuffix(domainSuffix.value);
    const params = {};
    if (resolvedSuffix) {
      params.domain_suffix = resolvedSuffix;
    }
    const res = await adminApi.get(`/lead-provision-preview/${lead.id}/`, { params });
    previews.value = { ...previews.value, [lead.id]: res.data };
    if (showToast) {
      if (res.data?.collision) {
        toast.show(t("adminConsole.collisionDetectedProvision", { slug: res.data.resolved_slug }), "error");
      } else {
        toast.show(t("adminConsole.slugDomainAvailable"), "success");
      }
    }
  } catch (err) {
    if (showToast) {
      toast.show(parseApiError(err, t("adminConsole.previewCheckFailed")), "error");
    }
  } finally {
    previewLoading.value = { ...previewLoading.value, [lead.id]: false };
  }
};

const provision = async (lead) => {
  provLoading.value = { ...provLoading.value, [lead.id]: true };
  try {
    const preview = previewFor(lead.id);
    const resolvedSuffix = normalizeSuffix(domainSuffix.value);
    const payload = {
      requested_slug: preview?.input_slug || undefined,
    };
    if (resolvedSuffix) {
      payload.domain_suffix = resolvedSuffix;
    }
    const res = await adminApi.put(`/lead-provision/${lead.id}/`, payload);
    const data = res.data || {};
    toast.show(t("adminConsole.provisionedLead", { lead: lead.name || lead.email }), "success");
    // display quick info for copy/paste
    lastProvision.value = {
      tenant_url: data.tenant_url,
      workspace_url: data.workspace_url,
      onboarding_url: data.onboarding_url,
      signin_url: data.signin_url,
      admin_url: data.admin_url,
      django_admin_url: data.django_admin_url,
      activation_url: data.activation_url,
      public_menu_url: data.public_menu_url,
      activation_token: data.activation_token,
      tenant: data.tenant,
      owner_next_steps: Array.isArray(data.owner_next_steps) ? data.owner_next_steps : [],
      whatsapp_link: data.whatsapp_link,
      whatsapp_message_template: data.whatsapp_message_template,
    };
  } catch (err) {
    const msg = parseApiError(err, t("adminConsole.provisionFailed"));
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
    toast.show(t("adminConsole.activationResent", { lead: lead.name || lead.email }), "success");
    lastProvision.value = {
      tenant_url: data.tenant_url,
      workspace_url: data.workspace_url,
      onboarding_url: data.onboarding_url,
      signin_url: data.signin_url,
      admin_url: data.admin_url,
      django_admin_url: data.django_admin_url,
      activation_url: data.activation_url,
      public_menu_url: data.public_menu_url,
      activation_token: data.activation_token,
      tenant: data.tenant,
      owner_next_steps: Array.isArray(data.owner_next_steps) ? data.owner_next_steps : [],
      whatsapp_link: data.whatsapp_link,
      whatsapp_message_template: data.whatsapp_message_template,
    };
  } catch (err) {
    const msg = parseApiError(err, t("adminConsole.resendFailed"));
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
      workspace_url: data.workspace_url,
      onboarding_url: data.onboarding_url,
      signin_url: data.signin_url,
      admin_url: data.admin_url,
      django_admin_url: data.django_admin_url,
      activation_url: data.activation_url,
      public_menu_url: data.public_menu_url,
      activation_token: data.activation_token,
      owner_next_steps: Array.isArray(data.owner_next_steps) ? data.owner_next_steps : [],
      whatsapp_link: data.whatsapp_link,
      whatsapp_message_template: data.whatsapp_message_template,
    };
    toast.show(t("adminConsole.packageLoaded", { lead: lead.name || lead.email }), "success");
  } catch (err) {
    const msg = parseApiError(err, t("adminConsole.loadOnboardingPackageFailed"));
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
    const nextPreviews = { ...previews.value };
    delete nextPreviews[lead.id];
    previews.value = nextPreviews;
    toast.show(t("adminConsole.archivedLead", { lead: lead.name || lead.email }), "success");
  } catch (err) {
    const msg = parseApiError(err, t("adminConsole.archiveLeadFailed"));
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
      paymentReference = window.prompt(t("adminConsole.paymentReferenceOptionalPrompt"), paymentReference) ?? paymentReference;
      adminNote = window.prompt(t("adminConsole.internalAdminNoteOptionalPrompt"), "") ?? "";
    } else {
      adminNote = window.prompt(t("adminConsole.reasonForRejectionOptionalPrompt"), "") ?? "";
    }
    const res = await adminApi.put(`/admin-tier-upgrade-requests/${requestItem.id}/decision/`, {
      decision,
      admin_note: adminNote,
      payment_reference: paymentReference,
    });
    const detail = res?.data?.detail || (decision === "approve" ? t("adminConsole.upgradeApproved") : t("adminConsole.upgradeRejected"));
    toast.show(detail, "success");
    await fetchUpgradeRequests();
  } catch (err) {
    const msg = parseApiError(err, t("adminConsole.processUpgradeFailed"));
    error.value = msg;
    toast.show(msg, "error");
  } finally {
    decisionLoading.value = { ...decisionLoading.value, [requestItem.id]: false };
  }
};

const copyText = async (text) => {
  try {
    await navigator.clipboard.writeText(text);
    toast.show(t("adminConsole.copied"), "success");
  } catch {
    toast.show(t("adminConsole.copyFailed"), "error");
  }
};

const copyOnboardingPackage = async () => {
  if (!packageText.value) {
    toast.show(t("adminConsole.noPackageDetails"), "error");
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
  } catch {
    return "-";
  }
};

const formatAuditAction = (action) => {
  const raw = String(action || "").trim();
  if (!raw) return t("adminConsole.defaultActionLabel");
  return raw
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
};

const formatDate = (value) => {
  if (!value) return "-";
  try {
    return new Date(value).toLocaleString();
  } catch {
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
    return minutes > 0 ? t("adminConsole.overdueMinutes", { minutes }) : t("adminConsole.overdue");
  }
  if (state === "due_soon") return t("adminConsole.dueSoon");
  if (state === "on_track") return t("adminConsole.onTrack");
  return t("adminConsole.sla");
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

const refreshCurrentView = async () => {
  if (activeAdminView.value === "operations") {
    await Promise.all([fetchLeads(), fetchUpgradeRequests()]);
    return;
  }
  if (activeAdminView.value === "tenants") {
    await fetchTenants(tenantPage.value);
    return;
  }
  if (activeAdminView.value === "monitoring") {
    const tasks = [];
    if (adminPanels.value.alerts) tasks.push(fetchReservationAlerts());
    if (adminPanels.value.jobs) tasks.push(fetchJobs());
    if (adminPanels.value.audit) tasks.push(fetchAuditLogs(auditPage.value));
    if (tasks.length) {
      await Promise.all(tasks);
    }
    return;
  }
  if (activeAdminView.value === "plans") {
    await fetchPlanFeatureFlags();
  }
};

const selectAdminView = async (view) => {
  activeAdminView.value = view;
  if (loadedAdminViews.value[view]) return;
  if (view === "operations") {
    await Promise.all([fetchLeads(), fetchUpgradeRequests()]);
    return;
  }
  if (view === "tenants") {
    await fetchTenants(tenantPage.value);
    return;
  }
  if (view === "plans") {
    await fetchPlanFeatureFlags();
  }
};

onMounted(() => {
  selectAdminView("operations");
});

watch(domainSuffix, () => {
  previews.value = {};
  previewLoading.value = {};
});

</script>

