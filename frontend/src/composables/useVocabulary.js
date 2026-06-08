/**
 * useVocabulary — business-type-aware noun set.
 *
 * The platform began restaurant-only ("Menu", "Dish", "Category"). For shop
 * verticals (retail/grocery/bakery) the same screens should read as a catalog
 * ("Catalog", "Product", "Section") without renaming anything in the database —
 * the Dish/Category models stay; only the displayed nouns change.
 *
 * Keyed off the tenant's business_type (tenant store). Falls back to the
 * restaurant noun set whenever the type is unknown, so nothing breaks.
 *
 * Usage:
 *   const voc = useVocabulary();
 *   voc.itemPlural.value   // "Dishes" (restaurant) | "Products" (shop)
 */

import { computed } from "vue";
import { useI18n } from "./useI18n";
import { useTenantStore } from "../stores/tenant";

const SHOP_TYPES = ["retail", "grocery", "bakery"];

export function useVocabulary() {
  const { t } = useI18n();
  const tenant = useTenantStore();
  const set = computed(() => (SHOP_TYPES.includes(tenant.businessType) ? "shop" : "restaurant"));
  const noun = (key) => t(`vocabulary.${set.value}.${key}`);
  return {
    isShop: computed(() => set.value === "shop"),
    catalog: computed(() => noun("catalog")),
    itemSingular: computed(() => noun("itemSingular")),
    itemPlural: computed(() => noun("itemPlural")),
    groupSingular: computed(() => noun("groupSingular")),
    groupPlural: computed(() => noun("groupPlural")),
  };
}
