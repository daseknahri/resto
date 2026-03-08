export const CATEGORY_TEMPLATE_PACKS = [
  {
    id: "restaurant",
    label: "Restaurant",
    categories: ["Starters", "Main Courses", "Sides", "Desserts", "Drinks"],
  },
  {
    id: "fastfood",
    label: "Fast Food",
    categories: ["Burgers", "Wraps", "Fried Chicken", "Fries", "Soft Drinks"],
  },
  {
    id: "cafe",
    label: "Cafe",
    categories: ["Breakfast", "Sandwiches", "Pastries", "Hot Drinks", "Cold Drinks"],
  },
];

export const THEME_PRESETS = [
  { id: "amber-teal", label: "Amber Teal", primary: "#0F766E", secondary: "#F59E0B" },
  { id: "charcoal-red", label: "Charcoal Red", primary: "#334155", secondary: "#EF4444" },
  { id: "forest-lime", label: "Forest Lime", primary: "#166534", secondary: "#84CC16" },
  { id: "ocean-coral", label: "Ocean Coral", primary: "#0C4A6E", secondary: "#FB7185" },
];

export const suggestDishNameForCategory = (categoryName = "") => {
  const key = String(categoryName || "").toLowerCase();
  if (key.includes("drink")) return "Fresh Juice";
  if (key.includes("dessert") || key.includes("pastr")) return "Chocolate Cake";
  if (key.includes("breakfast")) return "Omelette Plate";
  if (key.includes("burger")) return "Classic Burger";
  if (key.includes("wrap")) return "Chicken Wrap";
  if (key.includes("starter")) return "Soup of the Day";
  return "Chef Special";
};
