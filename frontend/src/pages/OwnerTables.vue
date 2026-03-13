<template>
  <section class="space-y-6 ui-safe-bottom pb-24 sm:pb-0">
    <header class="no-print rounded-2xl border border-slate-800/80 bg-slate-950/70 p-4 md:p-5">
      <div class="flex flex-wrap items-end justify-between gap-4">
        <div class="space-y-1.5">
          <p class="ui-kicker">{{ t("ownerTables.kicker") }}</p>
          <h2 class="ui-display text-2xl font-semibold text-white md:text-3xl">{{ t("ownerTables.title") }}</h2>
          <p class="text-sm text-slate-300">{{ t("ownerTables.description") }}</p>
        </div>
        <div class="flex flex-wrap gap-2">
          <button class="ui-btn-primary" @click="openSetup('create')">
            {{ t("ownerTables.create") }}
          </button>
          <button class="ui-btn-outline" @click="openSetup('bulk')">
            {{ t("ownerTables.bulk") }}
          </button>
          <button class="ui-btn-outline" :disabled="loading" @click="fetchTables">
            {{ loading ? t("ownerTables.refreshing") : t("common.refresh") }}
          </button>
        </div>
      </div>
      <div class="mt-4 flex flex-wrap gap-2">
        <span class="ui-data-strip">{{ t("ownerTables.tableLinksCount", { count: tables.length }) }}</span>
        <span class="ui-data-strip">{{ t("ownerTables.activeTables") }}: {{ activeTablesCount }}</span>
        <span class="ui-data-strip">{{ t("ownerTables.disabledTables") }}: {{ disabledTablesCount }}</span>
      </div>
    </header>

    <div v-if="setupOpen" class="no-print rounded-2xl border border-slate-800/80 bg-slate-950/70 p-4 md:p-5">
      <div class="mb-4 flex flex-wrap items-center justify-between gap-2">
        <p class="ui-kicker">{{ formMode === "create" ? t("ownerTables.createTable") : t("ownerTables.bulkGenerate") }}</p>
        <button class="ui-btn-outline px-3 py-1.5 text-xs" @click="setupOpen = false">{{ t("common.close") }}</button>
      </div>
      <div class="grid gap-4 lg:grid-cols-[220px_minmax(0,1fr)]">
        <aside class="rounded-xl border border-slate-800 bg-slate-900/60 p-3">
          <p class="ui-kicker mb-2">{{ t("common.apply") }}</p>
          <ul class="space-y-2">
            <li>
              <button
                class="w-full rounded-lg border px-3 py-2 text-left text-sm font-semibold transition"
                :class="formMode === 'create' ? 'border-brand-secondary bg-brand-secondary/10 text-brand-secondary' : 'border-slate-700 text-slate-200 hover:border-brand-secondary/60'"
                @click="formMode = 'create'"
              >
                {{ t("ownerTables.createTable") }}
              </button>
            </li>
            <li>
              <button
                class="w-full rounded-lg border px-3 py-2 text-left text-sm font-semibold transition"
                :class="formMode === 'bulk' ? 'border-brand-secondary bg-brand-secondary/10 text-brand-secondary' : 'border-slate-700 text-slate-200 hover:border-brand-secondary/60'"
                @click="formMode = 'bulk'"
              >
                {{ t("ownerTables.bulkGenerate") }}
              </button>
            </li>
          </ul>
        </aside>

        <article class="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
          <template v-if="formMode === 'create'">
            <div class="space-y-1">
              <p class="ui-kicker">{{ t("ownerTables.create") }}</p>
              <h3 class="text-base font-semibold text-slate-100">{{ t("ownerTables.createTable") }}</h3>
            </div>
            <div class="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-[1.5fr,120px,120px,auto] lg:items-end">
              <label class="text-sm text-slate-300">
                {{ t("ownerTables.tableLabel") }}
                <input
                  v-model.trim="newTable.label"
                  maxlength="40"
                  class="ui-input mt-1"
                  :placeholder="t('ownerTables.tableLabelPlaceholder')"
                />
              </label>
              <label class="text-sm text-slate-300">
                {{ t("ownerTables.position") }}
                <input
                  v-model.number="newTable.position"
                  type="number"
                  min="0"
                  class="ui-input mt-1"
                />
              </label>
              <label class="text-sm text-slate-300">
                {{ t("ownerTables.active") }}
                <select v-model="newTable.is_active" class="ui-input mt-1">
                  <option :value="true">{{ t("ownerTables.yes") }}</option>
                  <option :value="false">{{ t("ownerTables.no") }}</option>
                </select>
              </label>
              <button class="ui-btn-primary px-4 py-2 text-sm disabled:opacity-60" :disabled="creating" @click="createTable">
                {{ creating ? t("ownerTables.adding") : t("ownerTables.addTable") }}
              </button>
            </div>
          </template>

          <template v-else>
            <div class="space-y-1">
              <p class="ui-kicker">{{ t("ownerTables.bulk") }}</p>
              <h3 class="text-base font-semibold text-slate-100">{{ t("ownerTables.bulkGenerate") }}</h3>
              <p class="text-sm text-slate-400">{{ t("ownerTables.bulkHint") }}</p>
            </div>
            <div class="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-[1fr,90px,90px,120px,120px,auto] xl:items-end">
              <label class="text-sm text-slate-300">
                {{ t("ownerTables.prefix") }}
                <input
                  v-model.trim="bulk.prefix"
                  maxlength="20"
                  class="ui-input mt-1"
                  :placeholder="t('ownerTables.prefixPlaceholder')"
                />
              </label>
              <label class="text-sm text-slate-300">
                {{ t("ownerTables.startNumber") }}
                <input v-model.number="bulk.start" type="number" min="1" class="ui-input mt-1" />
              </label>
              <label class="text-sm text-slate-300">
                {{ t("ownerTables.count") }}
                <input v-model.number="bulk.count" type="number" min="1" max="120" class="ui-input mt-1" />
              </label>
              <label class="text-sm text-slate-300">
                {{ t("ownerTables.positionFrom") }}
                <input v-model.number="bulk.position_start" type="number" min="0" class="ui-input mt-1" />
              </label>
              <label class="text-sm text-slate-300">
                {{ t("ownerTables.active") }}
                <select v-model="bulk.is_active" class="ui-input mt-1">
                  <option :value="true">{{ t("ownerTables.yes") }}</option>
                  <option :value="false">{{ t("ownerTables.no") }}</option>
                </select>
              </label>
              <button class="ui-btn-outline px-4 py-2 text-sm disabled:opacity-60" :disabled="generating" @click="generateTables">
                {{ generating ? t("ownerTables.generating") : t("ownerTables.generate") }}
              </button>
            </div>
          </template>
        </article>
      </div>
      <p v-if="error" class="mt-4 rounded-2xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">{{ error }}</p>
    </div>
    <div
      v-else
      class="no-print rounded-2xl border border-dashed border-slate-700/80 bg-slate-950/40 p-4 text-sm text-slate-300 md:p-5"
    >
      <div class="flex flex-wrap items-center justify-between gap-3">
        <p>{{ t("ownerTables.description") }}</p>
        <div class="flex flex-wrap gap-2">
          <button class="ui-btn-primary px-3 py-1.5 text-xs" @click="openSetup('create')">{{ t("ownerTables.createTable") }}</button>
          <button class="ui-btn-outline px-3 py-1.5 text-xs" @click="openSetup('bulk')">{{ t("ownerTables.bulkGenerate") }}</button>
        </div>
      </div>
    </div>

    <div class="no-print ui-toolbar-band p-4">
      <div class="ui-toolbar-grid">
        <div class="grid gap-3 md:grid-cols-[minmax(0,1fr),220px] md:items-center">
          <label class="text-sm text-slate-300">
            <span class="sr-only">{{ t("common.search") }}</span>
            <input
              v-model.trim="searchQuery"
              class="ui-input"
              :placeholder="t('common.search')"
            />
          </label>
          <label class="text-sm text-slate-300">
            <span class="sr-only">{{ t("ownerTables.statusFilter") }}</span>
            <select v-model="statusFilter" class="ui-input">
              <option value="all">{{ t("ownerTables.cardsTitle") }}</option>
              <option value="active">{{ t("ownerTables.activeTables") }}</option>
              <option value="disabled">{{ t("ownerTables.disabledTables") }}</option>
            </select>
          </label>
        </div>
        <div class="ui-scroll-row">
          <button class="ui-btn-outline px-3 py-1.5 text-xs" :disabled="loading" @click="fetchTables">
            {{ loading ? t("ownerTables.refreshing") : t("common.refresh") }}
          </button>
          <button class="ui-btn-outline px-3 py-1.5 text-xs" :disabled="!tables.length" @click="exportCsv">{{ t("ownerTables.exportCsv") }}</button>
          <button class="ui-btn-outline px-3 py-1.5 text-xs" :disabled="!tables.length" @click="downloadHtmlPack">{{ t("ownerTables.htmlPack") }}</button>
          <button class="ui-btn-outline px-3 py-1.5 text-xs" :disabled="!tables.length" @click="printCards">{{ t("ownerTables.printCards") }}</button>
        </div>
      </div>
      <div class="mt-3 flex flex-wrap gap-2">
        <span class="ui-data-strip">{{ t("ownerTables.tableLinksCount", { count: filteredTables.length }) }}</span>
        <span v-if="searchQuery" class="ui-data-strip">{{ t("common.search") }}: {{ searchQuery }}</span>
        <span v-if="statusFilter !== 'all'" class="ui-data-strip">
          {{ statusFilter === 'active' ? t("ownerTables.activeTables") : t("ownerTables.disabledTables") }}
        </span>
      </div>
    </div>

    <header class="print-only rounded-xl border border-slate-300 bg-white p-4 text-slate-900">
      <p class="text-xs uppercase tracking-[0.2em] text-slate-500">{{ t("ownerTables.cardsTitle") }}</p>
      <h3 class="mt-1 text-2xl font-semibold">{{ tenantName }}</h3>
      <p class="mt-1 text-xs text-slate-500">{{ t("ownerTables.generatedAt", { date: generatedAt }) }}</p>
    </header>

    <p v-if="!tables.length && !loading" class="rounded-xl border border-dashed border-slate-700 p-4 text-sm text-slate-400">
      {{ t("ownerTables.noLinks") }}
    </p>

    <div v-else-if="!filteredTables.length && !loading" class="rounded-2xl border border-dashed border-slate-700/80 bg-slate-950/30 p-5 text-sm text-slate-400">
      {{ t("common.search") }} · 0 / {{ tables.length }}
    </div>

    <div class="grid gap-4 sm:grid-cols-2 2xl:grid-cols-3">
      <article
        v-for="table in filteredTables"
        :key="table.id"
        class="table-card ui-spotlight-card space-y-3 p-4 ui-press cursor-pointer"
        :class="selectedTableId === table.id ? 'border-brand-secondary/60 shadow-brand-secondary/10' : ''"
        @click="selectedTableId = table.id"
      >
        <div class="rounded-xl border border-slate-800/80 bg-slate-950/55 p-3">
          <div class="flex items-center gap-2">
            <img
              v-if="logoUrl"
              :src="logoUrl"
              :alt="t('ownerTables.logoAlt')"
              class="h-7 w-7 rounded-full border border-slate-700 object-cover"
              loading="lazy"
            />
            <p class="truncate text-xs font-semibold uppercase tracking-[0.18em] text-slate-300">{{ tenantName }}</p>
          </div>
          <p class="mt-2 truncate text-xl font-semibold text-slate-100">{{ table.label }}</p>
          <p class="text-xs text-slate-400">{{ t("ownerTables.slug") }}: {{ table.slug }}</p>
        </div>

        <div class="mx-auto w-fit rounded-xl border border-slate-700 bg-white p-2">
          <img
            v-if="tableQrSrc(table)"
            :src="tableQrSrc(table)"
            :alt="t('ownerTables.qrAlt', { label: table.label })"
            class="h-40 w-40"
            loading="lazy"
          />
          <div
            v-else
            class="flex h-40 w-40 items-center justify-center bg-slate-100 text-center text-[11px] font-medium text-slate-500"
          >
            {{ t("ownerTables.generating") }}
          </div>
        </div>

        <div class="space-y-1 text-xs">
          <p class="text-slate-300">{{ t("ownerTables.scanHint", { table: table.label }) }}</p>
          <a :href="tableShortUrl(table)" target="_blank" rel="noopener noreferrer" class="block break-all text-brand-secondary hover:underline">
            {{ tableShortUrl(table) }}
          </a>
          <a :href="tableFullMenuUrl(table)" target="_blank" rel="noopener noreferrer" class="no-print block break-all text-slate-400 hover:underline">
            {{ t("ownerTables.fullLinkPrefix") }}: {{ tableFullMenuUrl(table) }}
          </a>
        </div>

        <div class="flex items-start justify-between gap-2">
          <span
            class="rounded-full border px-2 py-1 text-[11px] font-semibold"
            :class="table.is_active ? 'bg-emerald-500/20 text-emerald-200' : 'bg-slate-700 text-slate-300'"
          >
            {{ table.is_active ? t("ownerTables.active") : t("ownerTables.disabledState") }}
          </span>
          <p class="print-only text-[10px] uppercase tracking-[0.15em] text-slate-600">{{ t("ownerTables.poweredBy", { name: tenantName }) }}</p>
        </div>

        <div class="no-print grid grid-cols-2 gap-2 lg:grid-cols-3">
          <button class="ui-btn-outline px-3 py-1.5 text-xs" @click.stop="copyShortUrl(table)">{{ t("ownerTables.copyShort") }}</button>
          <button class="ui-btn-outline px-3 py-1.5 text-xs" @click.stop="copyTableUrl(table)">{{ t("ownerTables.copyFull") }}</button>
          <button class="ui-btn-outline px-3 py-1.5 text-xs" @click.stop="copyQrUrl(table)">{{ t("ownerTables.copyQr") }}</button>
          <button class="ui-btn-outline px-3 py-1.5 text-xs" @click.stop="downloadQrPng(table)">{{ t("ownerTables.downloadQr") }}</button>
          <button class="ui-btn-outline px-3 py-1.5 text-xs" @click.stop="toggleTable(table)">
            {{ table.is_active ? t("ownerTables.disable") : t("ownerTables.enable") }}
          </button>
          <button class="ui-btn-outline px-3 py-1.5 text-xs text-red-200 hover:border-red-400/60" @click.stop="removeTable(table)">
            {{ t("ownerTables.delete") }}
          </button>
        </div>
      </article>
    </div>

    <div class="no-print fixed bottom-4 left-3 right-3 z-20 grid grid-cols-3 gap-2 sm:hidden">
      <button class="ui-btn-primary justify-center" @click="openSetup('create')">{{ t("ownerTables.create") }}</button>
      <button class="ui-btn-outline justify-center" @click="openSetup('bulk')">{{ t("ownerTables.bulk") }}</button>
      <button class="ui-btn-outline justify-center" :disabled="loading" @click="fetchTables">
        {{ loading ? t("ownerTables.loading") : t("common.refresh") }}
      </button>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import QRCode from "qrcode";
import api from "../lib/api";
import { useI18n } from "../composables/useI18n";
import { useToastStore } from "../stores/toast";
import { useTenantStore } from "../stores/tenant";

const toast = useToastStore();
const tenant = useTenantStore();
const { t } = useI18n();
const loading = ref(false);
const creating = ref(false);
const generating = ref(false);
const tables = ref([]);
const qrDataUrls = ref({});
const error = ref("");
const setupOpen = ref(false);
const formMode = ref("create");
const searchQuery = ref("");
const statusFilter = ref("all");
const selectedTableId = ref(null);
const newTable = reactive({
  label: "",
  position: 0,
  is_active: true,
});
const bulk = reactive({
  prefix: t("ownerTables.defaultPrefix"),
  start: 1,
  count: 12,
  position_start: 0,
  is_active: true,
});

const tenantName = computed(() => {
  const profileName = String(tenant.meta?.profile?.restaurant_name || "").trim();
  if (profileName) return profileName;
  const brandName = String(tenant.meta?.name || "").trim();
  if (brandName) return brandName;
  return t("ownerTables.defaultRestaurantName");
});
const logoUrl = computed(() => String(tenant.meta?.profile?.logo_url || "").trim());
const generatedAt = computed(() => new Date().toLocaleString());
const activeTablesCount = computed(() => tables.value.filter((table) => table.is_active).length);
const disabledTablesCount = computed(() => Math.max(0, tables.value.length - activeTablesCount.value));
const filteredTables = computed(() => {
  const query = searchQuery.value.trim().toLowerCase();
  return tables.value.filter((table) => {
    if (statusFilter.value === "active" && !table.is_active) return false;
    if (statusFilter.value === "disabled" && table.is_active) return false;
    if (!query) return true;
    return [table.label, table.slug]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(query));
  });
});
const parseError = (err, fallback = t("ownerTables.requestFailed")) => {
  const data = err?.response?.data;
  if (typeof data?.detail === "string") return data.detail;
  if (data && typeof data === "object") {
    const first = Object.values(data).find((v) => Array.isArray(v) && v.length);
    if (first) return String(first[0]);
  }
  return fallback;
};

const tableFullMenuUrl = (table) => {
  const origin = typeof window === "undefined" ? "" : window.location.origin;
  const tableLabel = encodeURIComponent(table.label || "");
  return `${origin}/browse?table=${tableLabel}`;
};
const tableShortUrl = (table) => `${typeof window === "undefined" ? "" : window.location.origin}/t/${encodeURIComponent(table.slug)}`;
const tableQrSrc = (table) => qrDataUrls.value[table.id] || "";

const generateQrForTable = async (table) => {
  if (!table?.id) return;
  const url = tableShortUrl(table);
  const dataUrl = await QRCode.toDataURL(url, {
    width: 240,
    margin: 1,
    errorCorrectionLevel: "M",
    color: {
      dark: "#0f172a",
      light: "#ffffff",
    },
  });
  qrDataUrls.value = {
    ...qrDataUrls.value,
    [table.id]: dataUrl,
  };
};

const generateQrBatch = async () => {
  const rows = Array.isArray(tables.value) ? tables.value : [];
  const nextQrs = {};
  for (const table of rows) {
    try {
      const dataUrl = await QRCode.toDataURL(tableShortUrl(table), {
        width: 240,
        margin: 1,
        errorCorrectionLevel: "M",
        color: {
          dark: "#0f172a",
          light: "#ffffff",
        },
      });
      nextQrs[table.id] = dataUrl;
    } catch {
      // Keep card usable even if one QR render fails.
    }
  }
  qrDataUrls.value = nextQrs;
};

const fetchTables = async () => {
  loading.value = true;
  error.value = "";
  try {
    const { data } = await api.get("/tables/");
    tables.value = Array.isArray(data) ? data : [];
    if (!tables.value.some((table) => table.id === selectedTableId.value)) {
      selectedTableId.value = tables.value[0]?.id ?? null;
    }
    await generateQrBatch();
  } catch (err) {
    error.value = parseError(err, t("ownerTables.loadFailed"));
  } finally {
    loading.value = false;
  }
};

const createTable = async () => {
  if (!newTable.label.trim()) {
    toast.show(t("ownerTables.labelRequired"), "error");
    return;
  }
  creating.value = true;
  error.value = "";
  try {
    const payload = {
      label: newTable.label.trim(),
      position: Number(newTable.position) || 0,
      is_active: newTable.is_active === true,
    };
    await api.post("/tables/", payload);
    newTable.label = "";
    newTable.position = 0;
    newTable.is_active = true;
    toast.show(t("ownerTables.created"), "success");
    await fetchTables();
    setupOpen.value = false;
  } catch (err) {
    error.value = parseError(err, t("ownerTables.createFailed"));
    toast.show(error.value, "error");
  } finally {
    creating.value = false;
  }
};

const generateTables = async () => {
  if (!bulk.prefix.trim()) {
    toast.show(t("ownerTables.prefixRequired"), "error");
    return;
  }
  generating.value = true;
  error.value = "";
  try {
    const payload = {
      prefix: bulk.prefix.trim(),
      start: Number(bulk.start) || 1,
      count: Number(bulk.count) || 1,
      position_start: Number(bulk.position_start) || 0,
      is_active: bulk.is_active === true,
    };
    const { data } = await api.post("/tables/bulk-generate/", payload);
    toast.show(data?.detail || t("ownerTables.generated"), "success");
    await fetchTables();
    setupOpen.value = false;
  } catch (err) {
    error.value = parseError(err, t("ownerTables.generateFailed"));
    toast.show(error.value, "error");
  } finally {
    generating.value = false;
  }
};

const toggleTable = async (table) => {
  try {
    await api.put(`/tables/${table.id}/`, {
      ...table,
      is_active: !table.is_active,
    });
    table.is_active = !table.is_active;
    toast.show(table.is_active ? t("ownerTables.enabledToast") : t("ownerTables.disabledToast"), "success");
  } catch (err) {
    toast.show(parseError(err, t("ownerTables.updateFailed")), "error");
  }
};

const removeTable = async (table) => {
  const confirmed = typeof window === "undefined" ? true : window.confirm(t("ownerTables.deleteConfirm", { label: table.label }));
  if (!confirmed) return;
  try {
    await api.delete(`/tables/${table.id}/`);
    tables.value = tables.value.filter((item) => item.id !== table.id);
    if (selectedTableId.value === table.id) {
      selectedTableId.value = tables.value[0]?.id ?? null;
    }
    toast.show(t("ownerTables.deleted"), "success");
  } catch (err) {
    toast.show(parseError(err, t("ownerTables.deleteFailed")), "error");
  }
};

const copyText = async (value, successText) => {
  try {
    await navigator.clipboard.writeText(value);
    toast.show(successText, "success");
  } catch {
    toast.show(t("ownerTables.copyFailed"), "error");
  }
};

const copyShortUrl = (table) => copyText(tableShortUrl(table), t("ownerTables.shortCopied"));
const copyTableUrl = (table) => copyText(tableFullMenuUrl(table), t("ownerTables.fullCopied"));
const copyQrUrl = async (table) => {
  if (!tableQrSrc(table)) {
    await generateQrForTable(table);
  }
  const src = tableQrSrc(table);
  if (!src) {
    toast.show(t("ownerTables.qrNotReady"), "error");
    return;
  }
  copyText(src, t("ownerTables.qrCopied"));
};

const safeFileBase = (value) =>
  String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9-_]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 60) || "table";

const downloadDataUrl = (filename, dataUrl) => {
  if (typeof window === "undefined" || !dataUrl) return;
  const link = document.createElement("a");
  link.href = dataUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
};

const parseFilenameFromDisposition = (value, fallback) => {
  const raw = String(value || "");
  const utf8Match = raw.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1].trim());
    } catch {
      return utf8Match[1].trim();
    }
  }
  const basicMatch = raw.match(/filename="?([^";]+)"?/i);
  if (basicMatch?.[1]) return basicMatch[1].trim();
  return fallback;
};

const downloadBlob = (filename, blob) => {
  if (typeof window === "undefined" || !blob) return;
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
};

const downloadServerQrExport = async (format) => {
  const normalized = String(format || "zip").trim().toLowerCase();
  const ext = normalized === "pdf" ? "pdf" : "zip";
  try {
    const response = await api.get("/tables/qr-export/", {
      params: { export_format: normalized },
      responseType: "blob",
    });
    const fallback = `${safeFileBase(tenantName.value)}-qr-export.${ext}`;
    const filename = parseFilenameFromDisposition(response?.headers?.["content-disposition"], fallback);
    downloadBlob(filename, response?.data);
    toast.show(t("ownerTables.serverDownloadSuccess", { format: ext.toUpperCase() }), "success");
  } catch (err) {
    toast.show(parseError(err, t("ownerTables.serverDownloadFailed", { format: ext.toUpperCase() })), "error");
  }
};

const downloadServerQrZip = () => downloadServerQrExport("zip");
const downloadServerQrPdf = () => downloadServerQrExport("pdf");

const downloadQrPng = async (table) => {
  if (!table?.id) return;
  try {
    const response = await api.get(`/tables/${table.id}/qr-image/`, {
      responseType: "blob",
    });
    const fallback = `${safeFileBase(tenantName.value)}-${safeFileBase(table.label)}-qr.png`;
    const filename = parseFilenameFromDisposition(response?.headers?.["content-disposition"], fallback);
    downloadBlob(filename, response?.data);
    toast.show(t("ownerTables.downloadSuccess", { label: table.label }), "success");
    return;
  } catch {
    // Fallback to in-browser QR generation if server export fails.
  }

  if (!tableQrSrc(table)) {
    await generateQrForTable(table);
  }
  const src = tableQrSrc(table);
  if (!src) {
    toast.show(t("ownerTables.qrNotReady"), "error");
    return;
  }
  const fallbackName = `${safeFileBase(tenantName.value)}-${safeFileBase(table.label)}-qr.png`;
  downloadDataUrl(fallbackName, src);
  toast.show(t("ownerTables.downloadSuccess", { label: table.label }), "success");
};

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const downloadAllQrPng = async () => {
  if (!tables.value.length) return;
  if (Object.keys(qrDataUrls.value).length < tables.value.length) {
    await generateQrBatch();
  }

  let downloaded = 0;
  for (const table of tables.value) {
    const src = tableQrSrc(table);
    if (!src) continue;
    const filename = `${safeFileBase(tenantName.value)}-${safeFileBase(table.label)}-qr.png`;
    downloadDataUrl(filename, src);
    downloaded += 1;
    await sleep(120);
  }
  if (downloaded) {
    toast.show(t("ownerTables.downloadAllStarted", { count: downloaded }), "success");
  } else {
    toast.show(t("ownerTables.noQrAvailable"), "error");
  }
};

const downloadFile = (filename, content, mimeType) => {
  if (typeof window === "undefined") return;
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
};

const escapeHtml = (value) =>
  String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");

const exportCsv = () => {
  if (!tables.value.length) return;
  const rows = [
    ["label", "slug", "short_url", "full_menu_url", "is_active"],
    ...tables.value.map((table) => [
      table.label,
      table.slug,
      tableShortUrl(table),
      tableFullMenuUrl(table),
      table.is_active ? "true" : "false",
    ]),
  ];
  const csv = rows
    .map((row) => row.map((cell) => `"${String(cell || "").replace(/"/g, '""')}"`).join(","))
    .join("\n");
  const filename = `${safeFileBase(tenantName.value || t("ownerTables.defaultRestaurantName"))}-tables.csv`;
  downloadFile(filename, csv, "text/csv;charset=utf-8");
  toast.show(t("ownerTables.csvExported"), "success");
};

const buildHtmlPack = () => {
  const htmlTitle = `${tenantName.value} - ${t("ownerTables.cardsTitle")}`;
  const generatedLabel = t("ownerTables.generatedAt", { date: generatedAt.value });
  const tableCountLabel = t("ownerTables.tableLinksCount", { count: tables.value.length });
  const cards = tables.value
    .map((table) => {
      const short = tableShortUrl(table);
      const full = tableFullMenuUrl(table);
      const qrSrc = tableQrSrc(table);
      return `
        <article class="card">
          <div class="head">
            ${logoUrl.value ? `<img src="${escapeHtml(logoUrl.value)}" alt="${escapeHtml(t("ownerTables.logoAlt"))}" class="logo" />` : ""}
            <div>
              <p class="brand">${escapeHtml(tenantName.value)}</p>
              <h2>${escapeHtml(table.label)}</h2>
            </div>
          </div>
          <div class="qr-wrap">
            ${qrSrc ? `<img src="${escapeHtml(qrSrc)}" alt="${escapeHtml(t("ownerTables.qrAlt", { label: table.label }))}" class="qr" />` : `<div class="qr-missing">${escapeHtml(t("ownerTables.qrUnavailable"))}</div>`}
          </div>
          <p class="hint">${escapeHtml(t("ownerTables.scanHintPlain"))}</p>
          <p class="url">${escapeHtml(short)}</p>
          <p class="full">${escapeHtml(t("ownerTables.fullLinkPrefix"))}: ${escapeHtml(full)}</p>
          <p class="state">${escapeHtml(table.is_active ? t("ownerTables.active") : t("ownerTables.disabledState"))}</p>
        </article>
      `;
    })
    .join("\n");

  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>${escapeHtml(htmlTitle)}</title>
  <style>
    body { margin: 0; font-family: "Segoe UI", Arial, sans-serif; background: #f8fafc; color: #0f172a; }
    .wrap { max-width: 1200px; margin: 0 auto; padding: 20px; }
    .meta { margin-bottom: 16px; }
    .meta h1 { margin: 0; font-size: 24px; }
    .meta p { margin: 6px 0 0; color: #475569; font-size: 12px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 14px; }
    .card { border: 1px solid #cbd5e1; border-radius: 14px; background: #fff; padding: 12px; break-inside: avoid; page-break-inside: avoid; }
    .head { display: flex; align-items: center; gap: 10px; }
    .logo { width: 26px; height: 26px; border-radius: 999px; object-fit: cover; border: 1px solid #cbd5e1; }
    .brand { margin: 0; color: #475569; font-size: 10px; text-transform: uppercase; letter-spacing: .12em; font-weight: 700; }
    h2 { margin: 2px 0 0; font-size: 20px; }
    .qr-wrap { margin-top: 10px; display: flex; justify-content: center; }
    .qr { width: 200px; height: 200px; border: 1px solid #e2e8f0; border-radius: 8px; }
    .qr-missing { width: 200px; height: 200px; border: 1px dashed #94a3b8; display: flex; align-items: center; justify-content: center; color: #64748b; font-size: 12px; }
    .hint { margin: 8px 0 0; font-size: 12px; color: #334155; }
    .url { margin: 4px 0 0; font-size: 11px; color: #0f172a; word-break: break-all; }
    .full { margin: 4px 0 0; font-size: 10px; color: #64748b; word-break: break-all; }
    .state { margin: 8px 0 0; font-size: 10px; color: #334155; text-transform: uppercase; letter-spacing: .12em; }
    @media print {
      @page { size: A4; margin: 10mm; }
      body { background: #fff; }
      .wrap { padding: 0; }
    }
  </style>
</head>
<body>
  <main class="wrap">
    <header class="meta">
      <h1>${escapeHtml(htmlTitle)}</h1>
      <p>${escapeHtml(generatedLabel)} | ${escapeHtml(tableCountLabel)}</p>
    </header>
    <section class="grid">
      ${cards}
    </section>
  </main>
</body>
</html>`;
};

const downloadHtmlPack = async () => {
  if (!tables.value.length) return;
  if (Object.keys(qrDataUrls.value).length < tables.value.length) {
    await generateQrBatch();
  }
  const html = buildHtmlPack();
  const filename = `${safeFileBase(tenantName.value || t("ownerTables.defaultRestaurantName"))}-qr-pack.html`;
  downloadFile(filename, html, "text/html;charset=utf-8");
  toast.show(t("ownerTables.htmlDownloaded"), "success");
};

const printCards = () => {
  if (typeof window === "undefined") return;
  window.print();
};

const openSetup = (mode = "create") => {
  formMode.value = mode;
  setupOpen.value = true;
};

onMounted(fetchTables);
</script>

<style scoped>
.print-only {
  display: none;
}

@media print {
  @page {
    size: A4;
    margin: 10mm;
  }

  .print-only {
    display: block !important;
  }

  .no-print {
    display: none !important;
  }

  .grid {
    gap: 12px !important;
  }

  .table-card {
    break-inside: avoid;
    page-break-inside: avoid;
    border-width: 1px !important;
    border-color: #cbd5e1 !important;
    background: #ffffff !important;
    color: #0f172a !important;
  }
}
</style>
