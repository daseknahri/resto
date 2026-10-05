/**
 * Client mirror of the public menu's customer-visibility predicate
 * (backend/menu/visibility.py — the CategoryViewSet/DishViewSet customer filter):
 *   - a super-category (menu section) is visible when published and not paused;
 *   - a category is visible when published, not paused, AND its section is visible;
 *   - a dish is visible when published AND its category is visible.
 *
 * The owner's menu lists are served in preview mode (every row, hidden ones included),
 * so counting them raw overstates what customers actually see. Used by the onboarding
 * publish readiness check, which the backend publish gate enforces with the same rule.
 */
const isShown = (row) => row?.is_published !== false && row?.is_temporarily_disabled !== true;

const idSet = (rows) => new Set(rows.map((row) => String(row?.id)));

export const countCustomerVisible = ({ superCategories = [], categories = [], dishes = [] } = {}) => {
  const asList = (value) => (Array.isArray(value) ? value : []);
  const visibleSections = idSet(asList(superCategories).filter(isShown));
  const visibleCategories = asList(categories).filter(
    (category) => isShown(category) && visibleSections.has(String(category?.super_category))
  );
  const visibleCategoryIds = idSet(visibleCategories);
  const visibleDishes = asList(dishes).filter(
    (dish) => dish?.is_published !== false && visibleCategoryIds.has(String(dish?.category))
  );
  return { categories: visibleCategories.length, dishes: visibleDishes.length };
};
