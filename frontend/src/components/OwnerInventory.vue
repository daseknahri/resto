<template>
  <div class="space-y-3">
    <!-- Sub-tab bar -->
    <div class="flex overflow-x-auto gap-1 rounded-2xl border border-slate-800 bg-slate-950/40 p-1 no-scrollbar">
      <button
        v-for="st in subtabs"
        :key="st.key"
        class="flex-1 shrink-0 whitespace-nowrap rounded-xl px-3 py-1.5 text-xs font-medium transition-colors"
        :class="activeSubtab === st.key
          ? 'bg-slate-700/70 text-white'
          : 'text-slate-400 hover:text-slate-200'"
        @click="switchSubtab(st.key)"
      >
        {{ t(st.labelKey) }}
      </button>
    </div>

    <!-- ═══════════════════════════════════════════════════════════════════════
         DISH STOCK
    ════════════════════════════════════════════════════════════════════════ -->
    <template v-if="activeSubtab === 'dishStock'">
      <!-- Header band: auto-reset toggle + search + low-stock filter -->
      <div class="ui-panel space-y-3 p-3 sm:p-4">
        <!-- Auto-reset row -->
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0 leading-snug">
            <p class="text-xs font-semibold text-slate-200">{{ t("inventory.autoResetTitle") }}</p>
            <p class="mt-0.5 text-[11px] text-slate-500">{{ t("inventory.autoResetHint") }}</p>
          </div>
          <button
            role="switch"
            class="ui-press ui-touch-target shrink-0 rounded-full border px-3 py-1 text-[11px] font-semibold transition-colors disabled:opacity-50"
            :class="autoReset
              ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300'
              : 'border-slate-700/60 text-slate-400 hover:border-slate-600 hover:text-slate-300'"
            :disabled="savingReset"
            :aria-checked="autoReset"
            :aria-busy="savingReset"
            @click="toggleAutoReset"
          >
            <svg v-if="savingReset" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="me-1 inline h-3 w-3 animate-spin"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
            {{ autoReset ? t("common.open") : t("common.closed") }}
          </button>
        </div>

        <!-- Search + low-stock filter -->
        <div class="flex flex-wrap items-center gap-2">
          <div class="relative min-w-0 flex-1">
            <AppIcon name="search" class="pointer-events-none absolute start-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" aria-hidden="true" />
            <input
              v-model.trim="search"
              type="search"
              class="ui-input w-full ps-8 text-xs"
              :placeholder="t('inventory.searchPlaceholder')"
              :aria-label="t('inventory.searchPlaceholder')"
              enterkeyhint="search"
            />
          </div>
          <button
            class="ui-press ui-touch-target shrink-0 rounded-full border px-3 py-1 text-[11px] font-semibold transition-colors"
            :class="filterLowOnly
              ? 'border-amber-500/50 bg-amber-500/10 text-amber-300'
              : 'border-slate-700/60 text-slate-400 hover:border-slate-600 hover:text-slate-300'"
            :aria-pressed="filterLowOnly"
            @click="filterLowOnly = !filterLowOnly"
          >
            {{ t("inventory.lowOnly") }}
          </button>
        </div>
      </div>

      <!-- Loading skeleton -->
      <template v-if="fetching">
        <div v-for="i in 6" :key="i" class="ui-panel animate-pulse px-3 py-3">
          <div class="flex items-center justify-between gap-3">
            <div class="space-y-1.5">
              <div class="h-3 w-36 rounded bg-slate-700/60" />
              <div class="h-2.5 w-24 rounded bg-slate-800/60" />
            </div>
            <div class="flex gap-2">
              <div class="h-7 w-16 rounded-lg bg-slate-700/40" />
              <div class="h-7 w-16 rounded-lg bg-slate-700/40" />
            </div>
          </div>
        </div>
      </template>

      <!-- Empty state -->
      <div v-else-if="!dishes.length" class="ui-empty-state py-12 text-center">
        <AppIcon name="menu" class="mx-auto mb-3 h-8 w-8 text-slate-600" aria-hidden="true" />
        <p class="text-sm font-medium text-slate-400">{{ t("inventory.empty") }}</p>
      </div>

      <!-- No matches -->
      <div v-else-if="!filtered.length" class="ui-empty-state py-10 text-center">
        <p class="text-xs text-slate-500">{{ t("inventory.empty") }}</p>
      </div>

      <!-- Dish rows -->
      <ul v-else role="list" class="space-y-1.5">
        <li
          v-for="(dish, index) in filtered"
          :key="dish.id"
          class="ui-panel ui-reveal px-3 py-3"
          :class="!dish.is_available ? 'opacity-70' : ''"
          :style="{ '--ui-delay': `${Math.min(index, 14) * 15}ms` }"
        >
          <div class="flex flex-wrap items-center gap-2 sm:flex-nowrap">
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-1.5">
                <p class="truncate text-xs font-semibold text-slate-100">{{ dish.name }}</p>
                <span
                  v-if="!dish.is_available"
                  class="shrink-0 rounded-full border border-red-500/40 bg-red-500/10 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-red-300"
                >{{ t("inventory.soldOut") }}</span>
                <span
                  v-else-if="isLow(dish)"
                  class="shrink-0 rounded-full border border-amber-500/40 bg-amber-500/10 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-amber-300"
                >{{ t("ownerHome.lowStockLeft", { n: dish.stock_qty }) }}</span>
              </div>
              <p class="mt-0.5 truncate text-[10px] text-slate-500">{{ dish.category_name || dish.category_slug }}</p>
            </div>

            <div class="flex shrink-0 flex-wrap items-end gap-2 sm:flex-nowrap">
              <!-- Stock qty input -->
              <div class="flex flex-col items-center gap-0.5">
                <label :for="`inv-stock-${dish.id}`" class="text-[9px] uppercase tracking-wider text-slate-500">
                  {{ t("inventory.stockLabel") }}
                </label>
                <div class="flex items-center gap-0.5">
                  <button
                    class="ui-press flex h-6 w-6 items-center justify-center rounded-md border border-slate-700/60 text-slate-400 transition hover:border-slate-600 hover:text-slate-200 disabled:opacity-40"
                    :disabled="savingId === dish.id || (dish.stock_qty !== null && dish.stock_qty <= 0)"
                    :aria-label="`-1 ${dish.name}`"
                    @click="adjustStock(dish, -1)"
                  >
                    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" class="h-3 w-3" aria-hidden="true"><path d="M3 8h10"/></svg>
                  </button>
                  <input
                    :id="`inv-stock-${dish.id}`"
                    type="number"
                    min="0"
                    step="1"
                    :value="dish.stock_qty ?? ''"
                    :placeholder="t('inventory.unlimited')"
                    :disabled="savingId === dish.id"
                    class="ui-input w-16 py-0.5 text-center text-[11px] tabular-nums placeholder-slate-600 disabled:opacity-40"
                    :class="
                      dish.stock_qty === 0
                        ? 'border-red-500/50 text-red-300'
                        : dish.stock_qty !== null && isLow(dish)
                        ? 'border-amber-500/40 text-amber-200'
                        : dish.stock_qty !== null
                        ? 'border-slate-600 text-slate-100'
                        : ''
                    "
                    @change="commitStock(dish, $event.target.value)"
                    @keydown.enter="$event.target.blur()"
                  />
                  <button
                    class="ui-press flex h-6 w-7 items-center justify-center rounded-md border border-slate-700/60 text-[10px] font-semibold text-slate-400 transition hover:border-slate-600 hover:text-slate-200 disabled:opacity-40"
                    :disabled="savingId === dish.id"
                    :aria-label="`+10 ${dish.name}`"
                    @click="adjustStock(dish, 10)"
                  >
                    +10
                  </button>
                </div>
              </div>

              <!-- Threshold input -->
              <div class="flex flex-col items-center gap-0.5">
                <label :for="`inv-thresh-${dish.id}`" class="text-[9px] uppercase tracking-wider text-slate-500">
                  {{ t("inventory.thresholdLabel") }}
                </label>
                <input
                  :id="`inv-thresh-${dish.id}`"
                  type="number"
                  min="0"
                  step="1"
                  :value="dish.low_stock_threshold ?? ''"
                  :placeholder="t('inventory.unlimited')"
                  :disabled="savingId === dish.id"
                  class="ui-input w-16 py-0.5 text-center text-[11px] tabular-nums placeholder-slate-600 disabled:opacity-40"
                  @change="commitThreshold(dish, $event.target.value)"
                  @keydown.enter="$event.target.blur()"
                />
              </div>

              <!-- Saving spinner -->
              <div class="flex h-7 w-5 items-center justify-center">
                <svg
                  v-if="savingId === dish.id"
                  aria-hidden="true"
                  class="h-3.5 w-3.5 animate-spin text-slate-500"
                  viewBox="0 0 16 16"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                >
                  <circle cx="8" cy="8" r="6" stroke-dasharray="28" stroke-dashoffset="10" />
                </svg>
              </div>
            </div>
          </div>
        </li>
      </ul>
    </template>

    <!-- ═══════════════════════════════════════════════════════════════════════
         INGREDIENTS
    ════════════════════════════════════════════════════════════════════════ -->
    <template v-else-if="activeSubtab === 'ingredients'">
      <!-- Toolbar -->
      <div class="ui-panel space-y-3 p-3 sm:p-4">
        <div class="flex items-center justify-between gap-3">
          <p class="text-xs font-semibold text-slate-200">{{ t("inventory.ingTitle") }}</p>
          <button
            class="ui-press ui-touch-target shrink-0 inline-flex items-center gap-1.5 rounded-xl border border-slate-700/60 px-3 py-1.5 text-xs text-slate-300 transition hover:border-slate-600 hover:text-white"
            @click="ingStartCreate"
          >
            <AppIcon name="plus" class="h-3.5 w-3.5" aria-hidden="true" />
            {{ t("inventory.ingAddBtn") }}
          </button>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <div class="relative min-w-0 flex-1">
            <AppIcon name="search" class="pointer-events-none absolute start-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" aria-hidden="true" />
            <input
              v-model.trim="ingSearch"
              type="search"
              class="ui-input w-full ps-8 text-xs"
              :placeholder="t('inventory.searchPlaceholder')"
              :aria-label="t('inventory.searchPlaceholder')"
              enterkeyhint="search"
            />
          </div>
          <button
            class="ui-press ui-touch-target shrink-0 rounded-full border px-3 py-1 text-[11px] font-semibold transition-colors"
            :class="ingLowOnly
              ? 'border-amber-500/50 bg-amber-500/10 text-amber-300'
              : 'border-slate-700/60 text-slate-400 hover:border-slate-600 hover:text-slate-300'"
            :aria-pressed="ingLowOnly"
            @click="ingLowOnly = !ingLowOnly"
          >
            {{ t("inventory.lowOnly") }}
          </button>
        </div>
      </div>

      <!-- Inline create form -->
      <Transition name="ui-fade">
        <div
          v-if="ingCreating"
          class="ui-panel space-y-3 p-3 sm:p-4"
          role="group"
          :aria-label="t('inventory.ingAddBtn')"
        >
          <p class="text-xs font-semibold text-slate-300">{{ t("inventory.ingAddBtn") }}</p>
          <div class="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <div class="col-span-2 flex flex-col gap-1">
              <label class="text-[9px] uppercase tracking-wider text-slate-500">{{ t("inventory.ingNameLabel") }}</label>
              <input
                ref="ingNameInputRef"
                v-model.trim="newIng.name"
                type="text"
                class="ui-input text-xs"
                :placeholder="t('inventory.ingNameLabel')"
                :aria-label="t('inventory.ingNameLabel')"
                @keyup.enter="ingCreate"
              />
            </div>
            <div class="flex flex-col gap-1">
              <label class="text-[9px] uppercase tracking-wider text-slate-500">{{ t("inventory.ingUnitLabel") }}</label>
              <input
                v-model.trim="newIng.unit"
                type="text"
                class="ui-input text-xs"
                :placeholder="t('inventory.ingUnitHint')"
                :aria-label="t('inventory.ingUnitLabel')"
                @keyup.enter="ingCreate"
              />
            </div>
            <div class="flex flex-col gap-1">
              <label class="text-[9px] uppercase tracking-wider text-slate-500">{{ t("inventory.ingStockLabel") }}</label>
              <input
                v-model="newIng.stock_quantity"
                type="number"
                min="0"
                step="0.001"
                class="ui-input text-xs tabular-nums"
                placeholder="0"
                :aria-label="t('inventory.ingStockLabel')"
              />
            </div>
            <div class="flex flex-col gap-1">
              <label class="text-[9px] uppercase tracking-wider text-slate-500">{{ t("inventory.ingThresholdLabel") }}</label>
              <input
                v-model="newIng.low_stock_threshold"
                type="number"
                min="0"
                step="0.001"
                class="ui-input text-xs tabular-nums"
                :placeholder="t('inventory.unlimited')"
                :aria-label="t('inventory.ingThresholdLabel')"
              />
            </div>
            <div class="flex flex-col gap-1">
              <label class="text-[9px] uppercase tracking-wider text-slate-500">{{ t("inventory.ingCostLabel") }}</label>
              <input
                v-model="newIng.cost_per_unit"
                type="number"
                min="0"
                step="0.0001"
                class="ui-input text-xs tabular-nums"
                :placeholder="t('inventory.unlimited')"
                :aria-label="t('inventory.ingCostLabel')"
              />
            </div>
          </div>
          <div class="flex items-center gap-2">
            <button
              class="ui-btn-primary ui-press inline-flex items-center gap-1.5 px-4 py-1.5 text-xs disabled:opacity-50"
              :disabled="!newIng.name || !newIng.unit || ingSavingNew"
              @click="ingCreate"
            >
              <svg v-if="ingSavingNew" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="me-1 inline h-3 w-3 animate-spin"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
              <AppIcon v-else name="check" class="h-3.5 w-3.5" aria-hidden="true" />
              {{ t("common.save") }}
            </button>
            <button
              class="ui-btn-outline ui-press inline-flex items-center gap-1 px-3 py-1.5 text-xs"
              @click="ingCancelCreate"
            >
              {{ t("common.cancel") }}
            </button>
          </div>
        </div>
      </Transition>

      <!-- Loading -->
      <template v-if="ingFetching">
        <div v-for="i in 4" :key="i" class="ui-panel animate-pulse px-3 py-3">
          <div class="flex items-center justify-between gap-3">
            <div class="space-y-1.5">
              <div class="h-3 w-32 rounded bg-slate-700/60" />
              <div class="h-2.5 w-20 rounded bg-slate-800/60" />
            </div>
            <div class="h-7 w-24 rounded-lg bg-slate-700/40" />
          </div>
        </div>
      </template>

      <!-- Empty -->
      <div v-else-if="!ingredients.length && !ingCreating" class="ui-empty-state py-12 text-center">
        <AppIcon name="chart" class="mx-auto mb-3 h-8 w-8 text-slate-600" aria-hidden="true" />
        <p class="text-sm font-medium text-slate-400">{{ t("inventory.ingEmpty") }}</p>
        <button
          class="mt-3 inline-flex items-center gap-1.5 rounded-xl border border-slate-700/60 px-4 py-2 text-xs text-slate-300 transition hover:border-slate-600 hover:text-white ui-press"
          @click="ingStartCreate"
        >
          <AppIcon name="plus" class="h-3.5 w-3.5" aria-hidden="true" />
          {{ t("inventory.ingAddBtn") }}
        </button>
      </div>

      <!-- No matches -->
      <div v-else-if="!filteredIngredients.length && !ingFetching" class="ui-empty-state py-10 text-center">
        <p class="text-xs text-slate-500">{{ t("inventory.ingEmpty") }}</p>
      </div>

      <!-- Ingredient rows -->
      <ul v-else role="list" class="space-y-1.5">
        <li
          v-for="(ing, index) in filteredIngredients"
          :key="ing.id"
          class="ui-panel ui-reveal"
          :style="{ '--ui-delay': `${Math.min(index, 14) * 15}ms` }"
        >
          <!-- Main row -->
          <div class="flex flex-wrap items-center gap-2 px-3 py-3 sm:flex-nowrap">
            <!-- Name + unit + badge -->
            <div class="min-w-0 flex-1">
              <div class="flex flex-wrap items-center gap-1.5">
                <p class="text-xs font-semibold text-slate-100">{{ ing.name }}</p>
                <span class="rounded bg-slate-700/60 px-1.5 py-0.5 text-[9px] font-medium text-slate-400">{{ ing.unit }}</span>
                <span
                  v-if="ing.is_low_stock"
                  class="rounded-full border border-amber-500/40 bg-amber-500/10 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-amber-300"
                >{{ t("inventory.lowOnly") }}</span>
              </div>
              <p v-if="ing.cost_per_unit" class="mt-0.5 text-[10px] text-slate-500">
                {{ ing.cost_per_unit }} / {{ ing.unit }}
              </p>
            </div>

            <!-- Stock adjust -->
            <div class="flex shrink-0 items-center gap-1">
              <button
                class="ui-press flex h-6 w-6 items-center justify-center rounded-md border border-slate-700/60 text-slate-400 transition hover:border-slate-600 hover:text-slate-200 disabled:opacity-40"
                :disabled="ingSavingId === ing.id"
                :aria-label="`-1 ${ing.name}`"
                @click="ingAdjust(ing, -1)"
              >
                <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" class="h-3 w-3" aria-hidden="true"><path d="M3 8h10"/></svg>
              </button>
              <span
                class="w-14 text-center text-[11px] tabular-nums font-medium"
                :class="ing.is_low_stock ? 'text-amber-300' : 'text-slate-200'"
              >
                {{ Number(ing.stock_quantity).toFixed(ing.stock_quantity % 1 === 0 ? 0 : 2) }}
              </span>
              <button
                class="ui-press flex h-6 w-7 items-center justify-center rounded-md border border-slate-700/60 text-[10px] font-semibold text-slate-400 transition hover:border-slate-600 hover:text-slate-200 disabled:opacity-40"
                :disabled="ingSavingId === ing.id"
                :aria-label="`+10 ${ing.name}`"
                @click="ingAdjust(ing, 10)"
              >
                +10
              </button>
            </div>

            <!-- Threshold chip -->
            <div v-if="ing.low_stock_threshold != null" class="flex shrink-0 items-center gap-1 text-[10px] text-slate-500">
              <AppIcon name="alert" class="h-3 w-3" aria-hidden="true" />
              {{ ing.low_stock_threshold }}
            </div>

            <!-- Saving spinner / action buttons -->
            <div class="flex shrink-0 items-center gap-1">
              <svg
                v-if="ingSavingId === ing.id"
                aria-hidden="true"
                class="h-3.5 w-3.5 animate-spin text-slate-500"
                viewBox="0 0 16 16"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
              >
                <circle cx="8" cy="8" r="6" stroke-dasharray="28" stroke-dashoffset="10" />
              </svg>
              <template v-else>
                <button
                  class="ui-press flex h-7 w-7 items-center justify-center rounded-lg border border-slate-700/60 text-slate-400 transition hover:border-slate-600 hover:text-white"
                  :aria-label="`${t('common.edit')} ${ing.name}`"
                  @click="ingToggleEdit(ing)"
                >
                  <AppIcon name="edit" class="h-3.5 w-3.5" aria-hidden="true" />
                </button>
                <button
                  class="ui-press flex h-7 w-7 items-center justify-center rounded-lg border border-red-500/30 text-red-400/70 transition hover:border-red-500/50 hover:text-red-400"
                  :aria-label="`${t('common.delete')} ${ing.name}`"
                  @click="ingDelete(ing)"
                >
                  <AppIcon name="trash" class="h-3.5 w-3.5" aria-hidden="true" />
                </button>
              </template>
            </div>
          </div>

          <!-- Inline edit row -->
          <Transition name="ui-fade">
            <div
              v-if="ingEditId === ing.id"
              class="border-t border-slate-800 px-3 pb-3 pt-2 space-y-2"
              role="group"
              :aria-label="`${t('common.edit')} ${ing.name}`"
            >
              <div class="grid grid-cols-2 gap-2 sm:grid-cols-4">
                <div class="col-span-2 flex flex-col gap-1">
                  <label class="text-[9px] uppercase tracking-wider text-slate-500">{{ t("inventory.ingNameLabel") }}</label>
                  <input
                    v-model.trim="ingEditForm.name"
                    type="text"
                    class="ui-input text-xs"
                    :aria-label="t('inventory.ingNameLabel')"
                  />
                </div>
                <div class="flex flex-col gap-1">
                  <label class="text-[9px] uppercase tracking-wider text-slate-500">{{ t("inventory.ingUnitLabel") }}</label>
                  <input
                    v-model.trim="ingEditForm.unit"
                    type="text"
                    class="ui-input text-xs"
                    :placeholder="t('inventory.ingUnitHint')"
                    :aria-label="t('inventory.ingUnitLabel')"
                  />
                </div>
                <div class="flex flex-col gap-1">
                  <label class="text-[9px] uppercase tracking-wider text-slate-500">{{ t("inventory.ingStockLabel") }}</label>
                  <input
                    v-model="ingEditForm.stock_quantity"
                    type="number"
                    min="0"
                    step="0.001"
                    class="ui-input text-xs tabular-nums"
                    :aria-label="t('inventory.ingStockLabel')"
                  />
                </div>
                <div class="flex flex-col gap-1">
                  <label class="text-[9px] uppercase tracking-wider text-slate-500">{{ t("inventory.ingThresholdLabel") }}</label>
                  <input
                    v-model="ingEditForm.low_stock_threshold"
                    type="number"
                    min="0"
                    step="0.001"
                    class="ui-input text-xs tabular-nums"
                    :placeholder="t('inventory.unlimited')"
                    :aria-label="t('inventory.ingThresholdLabel')"
                  />
                </div>
                <div class="flex flex-col gap-1">
                  <label class="text-[9px] uppercase tracking-wider text-slate-500">{{ t("inventory.ingCostLabel") }}</label>
                  <input
                    v-model="ingEditForm.cost_per_unit"
                    type="number"
                    min="0"
                    step="0.0001"
                    class="ui-input text-xs tabular-nums"
                    :placeholder="t('inventory.unlimited')"
                    :aria-label="t('inventory.ingCostLabel')"
                  />
                </div>
              </div>
              <div class="flex items-center gap-2">
                <button
                  class="ui-btn-primary ui-press inline-flex items-center gap-1.5 px-4 py-1.5 text-xs disabled:opacity-50"
                  :disabled="!ingEditForm.name || !ingEditForm.unit || ingSavingId === ing.id"
                  @click="ingSaveEdit(ing)"
                >
                  <AppIcon name="check" class="h-3.5 w-3.5" aria-hidden="true" />
                  {{ t("common.save") }}
                </button>
                <button
                  class="ui-btn-outline ui-press inline-flex items-center gap-1 px-3 py-1.5 text-xs"
                  @click="ingEditId = null"
                >
                  {{ t("common.cancel") }}
                </button>
              </div>
            </div>
          </Transition>
        </li>
      </ul>
    </template>

    <!-- ═══════════════════════════════════════════════════════════════════════
         RECIPES
    ════════════════════════════════════════════════════════════════════════ -->
    <template v-else-if="activeSubtab === 'recipes'">
      <!-- Dish picker -->
      <div class="ui-panel space-y-3 p-3 sm:p-4">
        <p class="text-xs font-semibold text-slate-200">{{ t("inventory.recPickDish") }}</p>
        <div class="relative">
          <select
            v-model="recSelectedDishId"
            class="ui-input w-full appearance-none pe-8 text-xs"
            :aria-label="t('inventory.recPickDish')"
          >
            <option value="">— {{ t("inventory.recPickDish") }} —</option>
            <option
              v-for="d in recDishes"
              :key="d.id"
              :value="d.id"
            >
              {{ d.name }}
            </option>
          </select>
          <AppIcon name="chevron-down" class="pointer-events-none absolute end-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" aria-hidden="true" />
        </div>
        <svg
          v-if="recDishFetching"
          aria-hidden="true"
          class="h-4 w-4 animate-spin text-slate-500"
          viewBox="0 0 16 16"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
        >
          <circle cx="8" cy="8" r="6" stroke-dasharray="28" stroke-dashoffset="10" />
        </svg>
      </div>

      <template v-if="recSelectedDishId">
        <!-- Recipe lines -->
        <div class="ui-panel p-3 sm:p-4 space-y-3">
          <p class="text-xs font-semibold text-slate-200">{{ t("inventory.recLinesTitle") }}</p>

          <!-- Loading -->
          <div v-if="recLinesFetching" class="flex items-center gap-2 text-xs text-slate-500">
            <svg aria-hidden="true" class="h-3.5 w-3.5 animate-spin" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
              <circle cx="8" cy="8" r="6" stroke-dasharray="28" stroke-dashoffset="10" />
            </svg>
            {{ t("common.loading") }}
          </div>

          <!-- Empty -->
          <p v-else-if="!recLines.length" class="text-xs text-slate-500">{{ t("inventory.recEmpty") }}</p>

          <!-- Lines -->
          <ul v-else role="list" class="space-y-1">
            <li
              v-for="line in recLines"
              :key="line.id"
              class="flex items-center justify-between gap-3 rounded-xl border border-slate-800 px-3 py-2"
            >
              <div class="min-w-0 flex-1">
                <span class="text-xs font-medium text-slate-200">{{ line.ingredient_name }}</span>
                <span class="ms-1.5 text-[10px] text-slate-500">{{ line.ingredient_unit }}</span>
              </div>
              <div class="flex items-center gap-2">
                <span class="text-xs tabular-nums text-slate-300">× {{ Number(line.quantity) }}</span>
                <button
                  class="ui-press flex h-6 w-6 items-center justify-center rounded-lg border border-red-500/30 text-red-400/70 transition hover:border-red-500/50 hover:text-red-400 disabled:opacity-40"
                  :disabled="recDeletingLineId === line.id"
                  :aria-label="`${t('common.delete')} ${line.ingredient_name}`"
                  @click="recDeleteLine(line)"
                >
                  <svg v-if="recDeletingLineId === line.id" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3 w-3 animate-spin"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
                  <AppIcon v-else name="trash" class="h-3 w-3" aria-hidden="true" />
                </button>
              </div>
            </li>
          </ul>
        </div>

        <!-- Add line form -->
        <div class="ui-panel p-3 sm:p-4 space-y-2">
          <p class="text-xs font-semibold text-slate-200">{{ t("inventory.recAddLine") }}</p>
          <div v-if="!ingredients.length" class="text-xs text-slate-500">
            {{ t("inventory.recNoIngredients") }}
          </div>
          <template v-else>
            <div class="flex flex-wrap items-end gap-2">
              <div class="min-w-0 flex-1 flex flex-col gap-1">
                <label class="text-[9px] uppercase tracking-wider text-slate-500">{{ t("inventory.ingNameLabel") }}</label>
                <div class="relative">
                  <select
                    v-model="recNewIngId"
                    class="ui-input w-full appearance-none pe-8 text-xs"
                    :aria-label="t('inventory.ingNameLabel')"
                  >
                    <option value="">— {{ t("inventory.ingNameLabel") }} —</option>
                    <option v-for="ing in ingredients" :key="ing.id" :value="ing.id">
                      {{ ing.name }} ({{ ing.unit }})
                    </option>
                  </select>
                  <AppIcon name="chevron-down" class="pointer-events-none absolute end-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" aria-hidden="true" />
                </div>
              </div>
              <div class="w-24 flex flex-col gap-1">
                <label class="text-[9px] uppercase tracking-wider text-slate-500">{{ t("inventory.recQtyLabel") }}</label>
                <input
                  v-model="recNewQty"
                  type="number"
                  min="0.001"
                  step="0.001"
                  class="ui-input text-xs tabular-nums"
                  placeholder="0"
                  :aria-label="t('inventory.recQtyLabel')"
                />
              </div>
              <button
                class="ui-btn-primary ui-press inline-flex shrink-0 items-center gap-1.5 self-end px-4 py-2 text-xs disabled:opacity-50"
                :disabled="!recNewIngId || !recNewQty || recAddingLine"
                @click="recAddLine"
              >
                <svg v-if="recAddingLine" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="me-1 inline h-3 w-3 animate-spin"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
                <AppIcon v-else name="plus" class="h-3.5 w-3.5" aria-hidden="true" />
                {{ t("inventory.recAddLine") }}
              </button>
            </div>
          </template>
        </div>
      </template>
    </template>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from "vue";
import AppIcon from "./AppIcon.vue";
import { useI18n } from "../composables/useI18n";
import { useTenantStore } from "../stores/tenant";
import { useToastStore } from "../stores/toast";
import api from "../lib/api";
import { bustCache } from "../lib/staleCache";

const { t } = useI18n();
const tenant = useTenantStore();
const toast = useToastStore();

// ── Sub-tabs ──────────────────────────────────────────────────────────────────
const subtabs = [
  { key: "dishStock", labelKey: "inventory.subtabDishStock" },
  { key: "ingredients", labelKey: "inventory.subtabIngredients" },
  { key: "recipes", labelKey: "inventory.subtabRecipes" },
];
const activeSubtab = ref("dishStock");

const switchSubtab = (key) => {
  activeSubtab.value = key;
  if (key === "ingredients" && !ingredients.value.length && !ingFetching.value) {
    fetchIngredients();
  }
  if (key === "recipes") {
    if (!recDishes.value.length && !recDishFetching.value) fetchDishesForRecipe();
    if (!ingredients.value.length && !ingFetching.value) fetchIngredients();
  }
};

// ─────────────────────────────────────────────────────────────────────────────
// DISH STOCK
// ─────────────────────────────────────────────────────────────────────────────

const dishes = ref([]);
const fetching = ref(false);
const savingId = ref(null);
const savingReset = ref(false);
const search = ref("");
const filterLowOnly = ref(false);

const autoReset = computed(() => tenant.meta?.profile?.auto_reset_availability === true);

const isLow = (dish) =>
  dish.stock_qty !== null &&
  dish.stock_qty !== undefined &&
  dish.low_stock_threshold !== null &&
  dish.low_stock_threshold !== undefined &&
  dish.stock_qty <= dish.low_stock_threshold;

const filtered = computed(() => {
  let list = dishes.value.filter((d) => d.is_published);
  if (filterLowOnly.value) list = list.filter((d) => isLow(d));
  const q = search.value.toLowerCase();
  if (q) {
    list = list.filter(
      (d) =>
        (d.name || "").toLowerCase().includes(q) ||
        (d.category_name || "").toLowerCase().includes(q) ||
        (d.category_slug || "").toLowerCase().includes(q),
    );
  }
  return [...list].sort((a, b) => {
    const aWeight = !a.is_available ? 0 : isLow(a) ? 1 : 2;
    const bWeight = !b.is_available ? 0 : isLow(b) ? 1 : 2;
    if (aWeight !== bWeight) return aWeight - bWeight;
    return (a.name || "").localeCompare(b.name || "");
  });
});

const fetchDishes = async () => {
  if (fetching.value) return;
  fetching.value = true;
  try {
    const { data } = await api.get("/dishes/", { timeout: 8000 });
    dishes.value = Array.isArray(data) ? data : [];
  } catch {
    toast.show(t("ownerHome.noDishesLoaded"), "error");
  } finally {
    fetching.value = false;
  }
};

onMounted(fetchDishes);

let _stockTimer = null;
let _threshTimer = null;

const patchDish = async (dish, payload) => {
  if (savingId.value === dish.id) return;
  savingId.value = dish.id;
  try {
    await api.patch(`/dishes/${dish.id}/`, payload);
    Object.assign(dish, payload);
    if (payload.stock_qty != null && payload.stock_qty > 0 && !dish.is_available) {
      await api.patch(`/dishes/${dish.id}/`, { is_available: true });
      dish.is_available = true;
    }
    bustCache("menu.categories");
    toast.show(t("inventory.saved"), "success");
  } catch {
    toast.show(t("inventory.saveFailed"), "error");
  } finally {
    savingId.value = null;
  }
};

const commitStock = (dish, rawValue) => {
  const trimmed = String(rawValue ?? "").trim();
  const newQty = trimmed === "" ? null : parseInt(trimmed, 10);
  if (newQty !== null && (isNaN(newQty) || newQty < 0)) return;
  if (newQty === dish.stock_qty) return;
  clearTimeout(_stockTimer);
  _stockTimer = setTimeout(() => patchDish(dish, { stock_qty: newQty }), 600);
};

const commitThreshold = (dish, rawValue) => {
  const trimmed = String(rawValue ?? "").trim();
  const newVal = trimmed === "" ? 3 : parseInt(trimmed, 10);
  if (isNaN(newVal) || newVal < 0) return;
  if (newVal === dish.low_stock_threshold) return;
  clearTimeout(_threshTimer);
  _threshTimer = setTimeout(() => patchDish(dish, { low_stock_threshold: newVal }), 600);
};

const adjustStock = (dish, delta) => {
  const current = dish.stock_qty ?? 0;
  const next = Math.max(0, current + delta);
  if (next === dish.stock_qty) return;
  clearTimeout(_stockTimer);
  patchDish(dish, { stock_qty: next });
};

const toggleAutoReset = async () => {
  if (savingReset.value) return;
  savingReset.value = true;
  const newValue = !autoReset.value;
  try {
    await api.patch("/profile/", { auto_reset_availability: newValue });
    tenant.mergeProfile({ auto_reset_availability: newValue });
  } catch {
    toast.show(t("inventory.saveFailed"), "error");
  } finally {
    savingReset.value = false;
  }
};

// ─────────────────────────────────────────────────────────────────────────────
// INGREDIENTS
// ─────────────────────────────────────────────────────────────────────────────

const ingredients = ref([]);
const ingFetching = ref(false);
const ingSearch = ref("");
const ingLowOnly = ref(false);
const ingCreating = ref(false);
const ingSavingNew = ref(false);
const ingEditId = ref(null);
const ingSavingId = ref(null);
const ingNameInputRef = ref(null);

const _ingEmpty = () => ({ name: "", unit: "", stock_quantity: "", low_stock_threshold: "", cost_per_unit: "" });
const newIng = ref(_ingEmpty());
const ingEditForm = ref(_ingEmpty());

const filteredIngredients = computed(() => {
  let list = ingredients.value;
  if (ingLowOnly.value) list = list.filter((i) => i.is_low_stock);
  const q = ingSearch.value.toLowerCase();
  if (q) list = list.filter((i) => (i.name || "").toLowerCase().includes(q));
  return list;
});

const fetchIngredients = async () => {
  if (ingFetching.value) return;
  ingFetching.value = true;
  try {
    const { data } = await api.get("/owner/ingredients/", { timeout: 8000 });
    ingredients.value = Array.isArray(data) ? data : [];
  } catch {
    toast.show(t("inventory.saveFailed"), "error");
  } finally {
    ingFetching.value = false;
  }
};

const ingStartCreate = () => {
  ingCreating.value = true;
  newIng.value = _ingEmpty();
  nextTick(() => ingNameInputRef.value?.focus());
};

const ingCancelCreate = () => {
  ingCreating.value = false;
  newIng.value = _ingEmpty();
};

const _buildIngPayload = (form) => {
  const payload = { name: form.name, unit: form.unit };
  if (form.stock_quantity !== "" && form.stock_quantity !== null)
    payload.stock_quantity = parseFloat(form.stock_quantity);
  if (form.low_stock_threshold !== "" && form.low_stock_threshold !== null)
    payload.low_stock_threshold = parseFloat(form.low_stock_threshold);
  else
    payload.low_stock_threshold = null;
  if (form.cost_per_unit !== "" && form.cost_per_unit !== null)
    payload.cost_per_unit = parseFloat(form.cost_per_unit);
  else
    payload.cost_per_unit = null;
  return payload;
};

const ingCreate = async () => {
  if (!newIng.value.name || !newIng.value.unit || ingSavingNew.value) return;
  ingSavingNew.value = true;
  try {
    const { data } = await api.post("/owner/ingredients/", _buildIngPayload(newIng.value));
    ingredients.value.push(data);
    ingCancelCreate();
    toast.show(t("inventory.ingSaved"), "success");
  } catch {
    toast.show(t("inventory.ingSaveFailed"), "error");
  } finally {
    ingSavingNew.value = false;
  }
};

const ingToggleEdit = (ing) => {
  if (ingEditId.value === ing.id) {
    ingEditId.value = null;
    return;
  }
  ingEditId.value = ing.id;
  ingEditForm.value = {
    name: ing.name,
    unit: ing.unit,
    stock_quantity: ing.stock_quantity,
    low_stock_threshold: ing.low_stock_threshold ?? "",
    cost_per_unit: ing.cost_per_unit ?? "",
  };
};

const ingSaveEdit = async (ing) => {
  if (!ingEditForm.value.name || !ingEditForm.value.unit || ingSavingId.value === ing.id) return;
  ingSavingId.value = ing.id;
  try {
    const { data } = await api.patch(`/owner/ingredients/${ing.id}/`, _buildIngPayload(ingEditForm.value));
    Object.assign(ing, data);
    ingEditId.value = null;
    toast.show(t("inventory.ingSaved"), "success");
  } catch {
    toast.show(t("inventory.ingSaveFailed"), "error");
  } finally {
    ingSavingId.value = null;
  }
};

const ingDelete = async (ing) => {
  if (ingSavingId.value === ing.id) return;
  ingSavingId.value = ing.id;
  try {
    await api.delete(`/owner/ingredients/${ing.id}/`);
    ingredients.value = ingredients.value.filter((i) => i.id !== ing.id);
    toast.show(t("inventory.ingDeleted"), "success");
  } catch {
    toast.show(t("inventory.ingSaveFailed"), "error");
  } finally {
    ingSavingId.value = null;
  }
};

const ingAdjust = async (ing, delta) => {
  if (ingSavingId.value === ing.id) return;
  ingSavingId.value = ing.id;
  try {
    const { data } = await api.post(`/owner/ingredients/${ing.id}/adjust/`, { delta });
    Object.assign(ing, data);
    toast.show(t("inventory.ingSaved"), "success");
  } catch {
    toast.show(t("inventory.ingSaveFailed"), "error");
  } finally {
    ingSavingId.value = null;
  }
};

// ─────────────────────────────────────────────────────────────────────────────
// RECIPES
// ─────────────────────────────────────────────────────────────────────────────

const recDishes = ref([]);
const recDishFetching = ref(false);
const recSelectedDishId = ref("");
const recLines = ref([]);
const recLinesFetching = ref(false);
const recNewIngId = ref("");
const recNewQty = ref("");
const recAddingLine = ref(false);
const recDeletingLineId = ref(null);

const fetchDishesForRecipe = async () => {
  if (recDishFetching.value) return;
  recDishFetching.value = true;
  try {
    const { data } = await api.get("/dishes/", { timeout: 8000 });
    recDishes.value = (Array.isArray(data) ? data : []).filter((d) => d.is_published);
  } catch {
    toast.show(t("ownerHome.noDishesLoaded"), "error");
  } finally {
    recDishFetching.value = false;
  }
};

const fetchRecipeLines = async (dishId) => {
  if (!dishId) return;
  recLinesFetching.value = true;
  recLines.value = [];
  try {
    const { data } = await api.get(`/owner/dishes/${dishId}/recipe/`, { timeout: 8000 });
    recLines.value = Array.isArray(data) ? data : [];
  } catch {
    toast.show(t("inventory.ingSaveFailed"), "error");
  } finally {
    recLinesFetching.value = false;
  }
};

watch(recSelectedDishId, (dishId) => {
  recNewIngId.value = "";
  recNewQty.value = "";
  if (dishId) fetchRecipeLines(dishId);
  else recLines.value = [];
});

const recAddLine = async () => {
  if (!recNewIngId.value || !recNewQty.value || recAddingLine.value) return;
  recAddingLine.value = true;
  try {
    const { data } = await api.post(`/owner/dishes/${recSelectedDishId.value}/recipe/`, {
      ingredient: recNewIngId.value,
      quantity: parseFloat(recNewQty.value),
    });
    const existing = recLines.value.findIndex((l) => l.id === data.id);
    if (existing >= 0) recLines.value[existing] = data;
    else recLines.value.push(data);
    recNewIngId.value = "";
    recNewQty.value = "";
    toast.show(t("inventory.recLineSaved"), "success");
  } catch {
    toast.show(t("inventory.recLineFailed"), "error");
  } finally {
    recAddingLine.value = false;
  }
};

const recDeleteLine = async (line) => {
  if (recDeletingLineId.value === line.id) return;
  recDeletingLineId.value = line.id;
  try {
    await api.delete(`/owner/recipe-lines/${line.id}/`);
    recLines.value = recLines.value.filter((l) => l.id !== line.id);
    toast.show(t("inventory.recLineDeleted"), "success");
  } catch {
    toast.show(t("inventory.recLineFailed"), "error");
  } finally {
    recDeletingLineId.value = null;
  }
};
</script>
