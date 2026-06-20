/**
 * useVocabulary(businessTypeOverride?) — business-type-aware noun set.
 *
 * The platform began restaurant-only ("Menu", "Dish", "Category"). For shop
 * verticals (retail/grocery/bakery/pharmacy) the same screens should read as a
 * catalog ("Catalog", "Product", "Section") without renaming anything in the
 * database — the Dish/Category models stay; only the displayed nouns change.
 *
 * Two contexts:
 *   - OWNER screens call useVocabulary() with NO argument → keyed off the tenant
 *     store (the owner's own business_type).
 *   - CUSTOMER / marketplace screens that render ANOTHER tenant's menu pass that
 *     tenant's business_type (a ref, a getter, or a plain string) so the page
 *     reads in the viewed shop's vocabulary — e.g.
 *       useVocabulary(() => menu.value?.business_type)
 *
 * Falls back to the restaurant noun set whenever the type is unknown/missing, so
 * nothing breaks.
 *
 * Usage:
 *   const voc = useVocabulary();
 *   voc.itemPlural.value   // "Dishes" (restaurant) | "Products" (shop)
 */

import { computed, unref } from "vue";
import { useI18n } from "./useI18n";
import { useTenantStore } from "../stores/tenant";

const SHOP_TYPES = ["retail", "grocery", "bakery", "pharmacy"];

export function useVocabulary(businessTypeOverride = null) {
  const { t } = useI18n();
  const tenant = useTenantStore();
  // Resolve the override (getter | ref | string); fall back to the tenant store
  // when it is absent/empty so owner screens keep their existing behaviour.
  const resolvedType = computed(() => {
    const override = typeof businessTypeOverride === "function"
      ? businessTypeOverride()
      : unref(businessTypeOverride);
    return override || tenant.businessType;
  });
  const set = computed(() => (SHOP_TYPES.includes(resolvedType.value) ? "shop" : "restaurant"));
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
