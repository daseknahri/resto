"""Starter templates for new restaurants.

Each template bundles a professional theme (colours + menu presentation) and a
ready-to-edit sample menu (categories + dishes), so a new owner can pick their
kind of place and instantly have a polished, populated app.

Templates are presentation + content presets — they set Profile.business_type
too, but several kinds (hotel / fine dining / fast casual) all map to the
"restaurant" business_type and differ only in look + sample menu.

Prices are in the platform default currency (MAD) and are illustrative; owners
edit everything after applying.
"""

# Each template:
#   label          — human label (English; UI localizes its own labels)
#   business_type  — Profile.business_type to set
#   theme          — primary_color, secondary_color, menu_theme, menu_card_layout
#   super_category — name of the top-level menu to attach categories to
#   categories     — [{ name, dishes: [{ name, price, description }] }]

TEMPLATES = {
    "cafe": {
        "label": "Café / Coffee shop",
        "business_type": "cafe",
        "theme": {
            "primary_color": "#6F4E37",
            "secondary_color": "#C8A27C",
            "menu_theme": "light",
            "menu_card_layout": "grid",
        },
        "super_category": "Menu",
        "categories": [
            {
                "name": "Coffee",
                "dishes": [
                    {"name": "Espresso", "price": "18", "description": "Rich single shot, freshly pulled."},
                    {"name": "Cappuccino", "price": "25", "description": "Espresso with steamed milk and foam."},
                    {"name": "Caffè Latte", "price": "28", "description": "Smooth espresso with steamed milk."},
                    {"name": "Flat White", "price": "28", "description": "Velvety microfoam over a double shot."},
                ],
            },
            {
                "name": "Pastries",
                "dishes": [
                    {"name": "Butter Croissant", "price": "15", "description": "Flaky, all-butter, baked fresh daily."},
                    {"name": "Pain au Chocolat", "price": "18", "description": "Buttery pastry with dark chocolate."},
                    {"name": "Blueberry Muffin", "price": "20", "description": "Moist muffin loaded with blueberries."},
                ],
            },
            {
                "name": "Cold Drinks",
                "dishes": [
                    {"name": "Iced Latte", "price": "30", "description": "Chilled espresso over milk and ice."},
                    {"name": "Fresh Lemonade", "price": "25", "description": "Hand-squeezed lemons, lightly sweet."},
                    {"name": "Mango Smoothie", "price": "35", "description": "Blended mango with yogurt."},
                ],
            },
        ],
    },
    "hotel": {
        "label": "Hotel",
        "business_type": "restaurant",
        "theme": {
            "primary_color": "#14304A",
            "secondary_color": "#C9A227",
            "menu_theme": "dark",
            "menu_card_layout": "grid",
        },
        "super_category": "Menu",
        "categories": [
            {
                "name": "Breakfast",
                "dishes": [
                    {"name": "Continental Breakfast", "price": "85", "description": "Pastries, fruit, juice and coffee."},
                    {"name": "English Breakfast", "price": "110", "description": "Eggs, sausage, beans, toast and grilled tomato."},
                    {"name": "Pancake Stack", "price": "70", "description": "Fluffy pancakes with maple syrup."},
                ],
            },
            {
                "name": "Room Service",
                "dishes": [
                    {"name": "Club Sandwich", "price": "95", "description": "Triple-decker with fries."},
                    {"name": "Caesar Salad", "price": "80", "description": "Crisp romaine, parmesan, croutons."},
                    {"name": "Gourmet Burger", "price": "120", "description": "Prime beef, cheddar, brioche bun."},
                ],
            },
            {
                "name": "Dinner",
                "dishes": [
                    {"name": "Grilled Salmon", "price": "180", "description": "With seasonal vegetables."},
                    {"name": "Ribeye Steak", "price": "220", "description": "Char-grilled, peppercorn sauce."},
                    {"name": "Penne Arrabbiata", "price": "110", "description": "Spicy tomato, garlic, basil."},
                ],
            },
        ],
    },
    "fine_dining": {
        "label": "Fine dining / big restaurant",
        "business_type": "restaurant",
        "theme": {
            "primary_color": "#171717",
            "secondary_color": "#B08D57",
            "menu_theme": "dark",
            "menu_card_layout": "row",
        },
        "super_category": "Menu",
        "categories": [
            {
                "name": "Starters",
                "dishes": [
                    {"name": "Seared Foie Gras", "price": "190", "description": "Brioche, fig compote."},
                    {"name": "Burrata & Heirloom Tomato", "price": "140", "description": "Basil oil, aged balsamic."},
                    {"name": "Beef Tartare", "price": "160", "description": "Hand-cut, capers, quail egg."},
                ],
            },
            {
                "name": "Main Courses",
                "dishes": [
                    {"name": "Beef Wellington", "price": "320", "description": "Mushroom duxelles, red wine jus."},
                    {"name": "Pan-Seared Sea Bass", "price": "260", "description": "Saffron beurre blanc."},
                    {"name": "Duck Confit", "price": "240", "description": "Crispy leg, orange reduction."},
                ],
            },
            {
                "name": "Desserts",
                "dishes": [
                    {"name": "Crème Brûlée", "price": "90", "description": "Vanilla custard, caramelised sugar."},
                    {"name": "Chocolate Fondant", "price": "95", "description": "Molten centre, vanilla ice cream."},
                ],
            },
        ],
    },
    "fast_casual": {
        "label": "Fast casual / QSR",
        "business_type": "restaurant",
        "theme": {
            "primary_color": "#E23744",
            "secondary_color": "#FFB400",
            "menu_theme": "light",
            "menu_card_layout": "grid",
        },
        "super_category": "Menu",
        "categories": [
            {
                "name": "Burgers",
                "dishes": [
                    {"name": "Classic Burger", "price": "45", "description": "Beef patty, lettuce, tomato, house sauce."},
                    {"name": "Cheeseburger", "price": "50", "description": "Double cheddar, pickles, onions."},
                    {"name": "Double Smash", "price": "65", "description": "Two smashed patties, special sauce."},
                ],
            },
            {
                "name": "Combos",
                "dishes": [
                    {"name": "Burger Combo", "price": "75", "description": "Burger + fries + drink."},
                    {"name": "Chicken Combo", "price": "70", "description": "Crispy chicken + fries + drink."},
                ],
            },
            {
                "name": "Sides & Drinks",
                "dishes": [
                    {"name": "French Fries", "price": "20", "description": "Crispy, lightly salted."},
                    {"name": "Onion Rings", "price": "25", "description": "Golden, crunchy."},
                    {"name": "Soft Drink", "price": "12", "description": "Choice of cola, lemon-lime or orange."},
                ],
            },
        ],
    },
}


def template_summaries():
    """Lightweight metadata for the picker UI (no full dish list payload)."""
    out = []
    for key, tpl in TEMPLATES.items():
        out.append({
            "key": key,
            "label": tpl["label"],
            "business_type": tpl["business_type"],
            "theme": tpl["theme"],
            "categories": [c["name"] for c in tpl["categories"]],
            "dish_count": sum(len(c["dishes"]) for c in tpl["categories"]),
        })
    return out
