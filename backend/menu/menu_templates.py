"""Starter templates for new businesses.

Each template bundles a professional theme (colours + menu presentation) and a
ready-to-edit sample menu (categories + dishes), so a new owner can pick their
kind of place and instantly have a polished, populated app.

Templates are presentation + content presets — they set Profile.business_type
too, but several kinds (hotel / fine dining / fast casual / bar) all map to the
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
                "name": "Tea & Chocolate",
                "dishes": [
                    {"name": "Moroccan Mint Tea", "price": "20", "description": "Fresh mint, lightly sweet."},
                    {"name": "Earl Grey", "price": "18", "description": "Classic bergamot black tea."},
                    {"name": "Hot Chocolate", "price": "30", "description": "Rich dark chocolate, steamed milk."},
                    {"name": "Chai Latte", "price": "30", "description": "Spiced tea with steamed milk."},
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
            {
                "name": "Beverages",
                "dishes": [
                    {"name": "Fresh Orange Juice", "price": "35", "description": "Squeezed to order."},
                    {"name": "Moroccan Mint Tea", "price": "25", "description": "Served in a traditional pot."},
                    {"name": "Sparkling Water", "price": "20", "description": "Chilled, 50cl."},
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
            {
                "name": "Wine & Pairings",
                "dishes": [
                    {"name": "House Red (Glass)", "price": "70", "description": "Sommelier's selection."},
                    {"name": "House White (Glass)", "price": "70", "description": "Crisp and balanced."},
                    {"name": "Champagne Flute", "price": "120", "description": "Brut, served chilled."},
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
                "name": "Wraps & Salads",
                "dishes": [
                    {"name": "Chicken Wrap", "price": "40", "description": "Grilled chicken, garlic mayo, veggies."},
                    {"name": "Caesar Wrap", "price": "42", "description": "Chicken, romaine, parmesan, caesar."},
                    {"name": "Garden Salad", "price": "35", "description": "Mixed greens, vinaigrette."},
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
    "bakery": {
        "label": "Bakery / Patisserie",
        "business_type": "bakery",
        "theme": {
            "primary_color": "#8B5E3C",
            "secondary_color": "#E8C39E",
            "menu_theme": "light",
            "menu_card_layout": "grid",
        },
        "super_category": "Menu",
        "categories": [
            {
                "name": "Breads",
                "dishes": [
                    {"name": "Sourdough Loaf", "price": "35", "description": "Slow-fermented, crusty crust."},
                    {"name": "Baguette", "price": "12", "description": "Classic French, baked fresh."},
                    {"name": "Whole Wheat Loaf", "price": "30", "description": "Hearty and wholesome."},
                ],
            },
            {
                "name": "Pastries",
                "dishes": [
                    {"name": "Butter Croissant", "price": "15", "description": "Flaky, all-butter."},
                    {"name": "Cinnamon Roll", "price": "22", "description": "Soft, swirled, glazed."},
                    {"name": "Almond Danish", "price": "24", "description": "Almond cream, toasted flakes."},
                ],
            },
            {
                "name": "Cakes & Sweets",
                "dishes": [
                    {"name": "Chocolate Cake (slice)", "price": "30", "description": "Rich layered ganache."},
                    {"name": "Cheesecake (slice)", "price": "32", "description": "Creamy, biscuit base."},
                    {"name": "Macarons (6)", "price": "60", "description": "Assorted flavours."},
                ],
            },
        ],
    },
    "bar": {
        "label": "Bar / Lounge",
        "business_type": "restaurant",
        "theme": {
            "primary_color": "#1B1B2F",
            "secondary_color": "#C0A062",
            "menu_theme": "dark",
            "menu_card_layout": "row",
        },
        "super_category": "Menu",
        "categories": [
            {
                "name": "Cocktails",
                "dishes": [
                    {"name": "Mojito", "price": "75", "description": "White rum, mint, lime, soda."},
                    {"name": "Old Fashioned", "price": "90", "description": "Bourbon, bitters, orange."},
                    {"name": "Margarita", "price": "85", "description": "Tequila, triple sec, lime."},
                    {"name": "Negroni", "price": "90", "description": "Gin, vermouth, Campari."},
                ],
            },
            {
                "name": "Wine & Beer",
                "dishes": [
                    {"name": "House Red (Glass)", "price": "60", "description": "Smooth and easy-drinking."},
                    {"name": "House White (Glass)", "price": "60", "description": "Crisp and chilled."},
                    {"name": "Draft Beer", "price": "45", "description": "Cold, on tap."},
                    {"name": "IPA", "price": "55", "description": "Hoppy and aromatic."},
                ],
            },
            {
                "name": "Small Plates",
                "dishes": [
                    {"name": "Loaded Nachos", "price": "65", "description": "Cheese, jalapeños, salsa."},
                    {"name": "Chicken Wings", "price": "70", "description": "Spicy glaze, blue cheese dip."},
                    {"name": "Olives & Cheese", "price": "55", "description": "Marinated olives, mixed cheese."},
                ],
            },
        ],
    },
    # ── Non-restaurant verticals ───────────────────────────────────────────────
    # These set business_type=grocery/retail, so the capability seam hides
    # tables/dine-in/waiter/kitchen/reservations and the UI reads as a catalog
    # (Catalog / Products / Sections via the vocabulary layer). Sample "dishes"
    # are products; owners edit everything after applying.
    "grocery": {
        "label": "Grocery / Mini-market",
        "business_type": "grocery",
        "theme": {
            "primary_color": "#2E7D32",
            "secondary_color": "#A5D6A7",
            "menu_theme": "light",
            "menu_card_layout": "grid",
        },
        "super_category": "Catalog",
        "categories": [
            {
                "name": "Fruits & Vegetables",
                "dishes": [
                    {"name": "Bananas (per kg)", "price": "12", "description": "Fresh, ripe."},
                    {"name": "Tomatoes (per kg)", "price": "9", "description": "Vine-ripened."},
                    {"name": "Apples (per kg)", "price": "16", "description": "Crisp and sweet."},
                ],
            },
            {
                "name": "Pantry",
                "dishes": [
                    {"name": "Rice 1kg", "price": "18", "description": "Long-grain."},
                    {"name": "Pasta 500g", "price": "10", "description": "Durum wheat."},
                    {"name": "Olive Oil 1L", "price": "60", "description": "Extra virgin."},
                ],
            },
            {
                "name": "Beverages",
                "dishes": [
                    {"name": "Still Water 1.5L", "price": "6", "description": "Pack of one."},
                    {"name": "Orange Juice 1L", "price": "15", "description": "100% juice."},
                    {"name": "Cola 33cl", "price": "7", "description": "Chilled can."},
                ],
            },
            {
                "name": "Household",
                "dishes": [
                    {"name": "Dish Soap", "price": "20", "description": "Lemon scent, 750ml."},
                    {"name": "Paper Towels (2)", "price": "18", "description": "Two-roll pack."},
                    {"name": "Trash Bags (30)", "price": "22", "description": "30 bags, 30L."},
                ],
            },
        ],
    },
    "pizza": {
        "label": "Pizza / Italian",
        "business_type": "restaurant",
        "theme": {
            "primary_color": "#7B1F1F",
            "secondary_color": "#F4845F",
            "menu_theme": "dark",
            "menu_card_layout": "grid",
        },
        "super_category": "Menu",
        "categories": [
            {
                "name": "Pizzas",
                "dishes": [
                    {"name": "Margherita", "price": "45", "description": "San Marzano tomato, fresh mozzarella, basil."},
                    {"name": "Pepperoni", "price": "55", "description": "Generous pepperoni, mozzarella, tomato sauce."},
                    {"name": "BBQ Chicken", "price": "58", "description": "Grilled chicken, BBQ sauce, red onion, mozzarella."},
                    {"name": "Quattro Formaggi", "price": "60", "description": "Mozzarella, gorgonzola, parmesan, fontina."},
                    {"name": "Veggie Supreme", "price": "52", "description": "Roasted peppers, mushrooms, olives, spinach."},
                ],
            },
            {
                "name": "Pasta",
                "dishes": [
                    {"name": "Spaghetti Bolognese", "price": "48", "description": "Slow-cooked beef ragù, fresh parmesan."},
                    {"name": "Penne Arrabbiata", "price": "40", "description": "Spicy tomato, garlic, chilli, fresh basil."},
                    {"name": "Carbonara", "price": "52", "description": "Guanciale, egg yolk, pecorino, black pepper."},
                    {"name": "Fettuccine Alfredo", "price": "50", "description": "Butter, cream, parmesan, garlic."},
                ],
            },
            {
                "name": "Starters",
                "dishes": [
                    {"name": "Garlic Focaccia", "price": "18", "description": "Warm, crispy, drizzled with herb oil."},
                    {"name": "Bruschetta al Pomodoro", "price": "22", "description": "Toasted bread, diced tomato, garlic, basil."},
                    {"name": "Caprese Salad", "price": "35", "description": "Buffalo mozzarella, heirloom tomato, basil, balsamic."},
                    {"name": "Burrata", "price": "45", "description": "Creamy burrata, roasted cherry tomatoes, basil oil."},
                ],
            },
            {
                "name": "Desserts",
                "dishes": [
                    {"name": "Tiramisu", "price": "30", "description": "Mascarpone, espresso-soaked ladyfingers, cocoa."},
                    {"name": "Panna Cotta", "price": "28", "description": "Vanilla cream, berry coulis."},
                    {"name": "Gelato (2 scoops)", "price": "25", "description": "Chef's daily selection."},
                ],
            },
            {
                "name": "Drinks",
                "dishes": [
                    {"name": "Fresh Lemonade", "price": "18", "description": "Hand-squeezed, lightly sparkling."},
                    {"name": "Cola", "price": "12", "description": "Chilled can."},
                    {"name": "Sparkling Water", "price": "10", "description": "50cl bottle."},
                    {"name": "Espresso", "price": "15", "description": "Rich single shot."},
                ],
            },
        ],
    },
    "sushi": {
        "label": "Sushi / Japanese",
        "business_type": "restaurant",
        "theme": {
            "primary_color": "#1A1A2E",
            "secondary_color": "#E94B4B",
            "menu_theme": "dark",
            "menu_card_layout": "list",
        },
        "super_category": "Menu",
        "categories": [
            {
                "name": "Signature Rolls",
                "dishes": [
                    {"name": "California Roll (8 pcs)", "price": "55", "description": "Crab, avocado, cucumber, tobiko."},
                    {"name": "Dragon Roll (8 pcs)", "price": "80", "description": "Shrimp tempura inside, avocado on top, eel sauce."},
                    {"name": "Spicy Tuna Roll (8 pcs)", "price": "70", "description": "Fresh tuna, spicy mayo, cucumber, sriracha."},
                    {"name": "Rainbow Roll (8 pcs)", "price": "90", "description": "Crab inside, assorted sashimi on top."},
                    {"name": "Avocado Roll (6 pcs)", "price": "45", "description": "Fresh avocado, sesame seeds. Vegan."},
                ],
            },
            {
                "name": "Sashimi",
                "dishes": [
                    {"name": "Salmon Sashimi (6 pcs)", "price": "85", "description": "Premium Atlantic salmon, thinly sliced."},
                    {"name": "Tuna Sashimi (6 pcs)", "price": "95", "description": "Fresh bluefin tuna, delicate and rich."},
                    {"name": "Mixed Sashimi (12 pcs)", "price": "150", "description": "Chef's selection of the finest daily catches."},
                ],
            },
            {
                "name": "Hot Dishes",
                "dishes": [
                    {"name": "Edamame", "price": "20", "description": "Steamed salted soybeans."},
                    {"name": "Gyoza (6 pcs)", "price": "38", "description": "Pan-fried pork & vegetable dumplings."},
                    {"name": "Miso Soup", "price": "18", "description": "Tofu, wakame, spring onion."},
                    {"name": "Chicken Teriyaki", "price": "65", "description": "Glazed chicken thigh, steamed rice, pickled ginger."},
                    {"name": "Tempura Prawns (4 pcs)", "price": "55", "description": "Light crispy batter, dipping sauce."},
                ],
            },
            {
                "name": "Bento Boxes",
                "dishes": [
                    {"name": "Salmon Bento", "price": "110", "description": "Grilled salmon, rice, miso soup, salad, gyoza."},
                    {"name": "Teriyaki Bento", "price": "100", "description": "Chicken teriyaki, rice, miso soup, salad, edamame."},
                    {"name": "Vegetarian Bento", "price": "90", "description": "Tofu, rice, miso soup, mixed vegetable tempura."},
                ],
            },
            {
                "name": "Drinks",
                "dishes": [
                    {"name": "Japanese Green Tea", "price": "15", "description": "Warm sencha tea pot."},
                    {"name": "Yuzu Lemonade", "price": "25", "description": "Refreshing citrus, lightly sparkling."},
                    {"name": "Mango Juice", "price": "20", "description": "100% mango, no added sugar."},
                    {"name": "Sparkling Water", "price": "10", "description": "50cl."},
                ],
            },
        ],
    },
    "moroccan": {
        "label": "Moroccan / Traditional",
        "business_type": "restaurant",
        "theme": {
            "primary_color": "#5C3317",
            "secondary_color": "#D4A853",
            "menu_theme": "dark",
            "menu_card_layout": "grid",
        },
        "super_category": "Menu",
        "categories": [
            {
                "name": "Mezze & Starters",
                "dishes": [
                    {"name": "Zaalouk", "price": "25", "description": "Roasted aubergine & tomato salad, cumin, coriander."},
                    {"name": "Taktouka", "price": "25", "description": "Roasted pepper & tomato salad, garlic, olive oil."},
                    {"name": "Harira", "price": "20", "description": "Traditional tomato, lentil & chickpea soup."},
                    {"name": "Briouates au Fromage (4 pcs)", "price": "30", "description": "Crispy pastry triangles, herbed cheese filling."},
                    {"name": "Assorted Mezze Platter", "price": "70", "description": "Selection of 4 Moroccan salads for sharing."},
                ],
            },
            {
                "name": "Tagines",
                "dishes": [
                    {"name": "Chicken with Lemon & Olives", "price": "95", "description": "Slow-cooked chicken, preserved lemon, green olives."},
                    {"name": "Lamb with Prunes & Almonds", "price": "120", "description": "Tender lamb shank, honeyed prunes, toasted almonds."},
                    {"name": "Kefta & Egg", "price": "85", "description": "Spiced beef kefta in rich tomato sauce, runny egg."},
                    {"name": "Fish Chermoula", "price": "110", "description": "Sea bass in chermoula marinade, peppers, potatoes."},
                    {"name": "Vegetable Tagine", "price": "75", "description": "Seasonal vegetables, chickpeas, saffron broth."},
                ],
            },
            {
                "name": "Couscous",
                "dishes": [
                    {"name": "Royal Couscous", "price": "130", "description": "Lamb, chicken, merguez sausage, seven vegetables."},
                    {"name": "Vegetable Couscous", "price": "85", "description": "Hearty vegetables, chickpeas, herb butter."},
                    {"name": "Tfaya Couscous", "price": "110", "description": "Chicken, caramelised onion & raisin compote."},
                ],
            },
            {
                "name": "Grills & Mechoui",
                "dishes": [
                    {"name": "Mixed Grill", "price": "120", "description": "Kefta, brochette, chicken & merguez with sides."},
                    {"name": "Kefta Brochettes (2)", "price": "60", "description": "Spiced minced lamb, chargrilled to order."},
                    {"name": "Mechoui d'Agneau", "price": "160", "description": "Slow-roasted lamb shoulder, cumin salt."},
                ],
            },
            {
                "name": "Pastilla",
                "dishes": [
                    {"name": "Chicken Pastilla", "price": "80", "description": "Flaky pastry, spiced chicken, almonds, cinnamon sugar."},
                    {"name": "Seafood Pastilla", "price": "90", "description": "Shrimp, calamari, vermicelli, herbs in crispy warqa."},
                ],
            },
            {
                "name": "Desserts",
                "dishes": [
                    {"name": "Moroccan Pastry Plate", "price": "35", "description": "Chebakia, ghriba, fekkas — honey & sesame."},
                    {"name": "Crème Caramel", "price": "25", "description": "Silky vanilla custard, golden caramel."},
                    {"name": "Seasonal Fruit Plate", "price": "30", "description": "Chef's selection of fresh fruits."},
                ],
            },
            {
                "name": "Drinks",
                "dishes": [
                    {"name": "Moroccan Mint Tea", "price": "18", "description": "Fresh spearmint, green tea, served in a traditional pot."},
                    {"name": "Fresh Orange Juice", "price": "22", "description": "Hand-squeezed Marrakchi oranges."},
                    {"name": "Avocado Smoothie", "price": "30", "description": "Blended avocado, milk, honey — thick and creamy."},
                    {"name": "Sparkling Water", "price": "10", "description": "50cl."},
                ],
            },
        ],
    },
    "health": {
        "label": "Healthy / Salad bar",
        "business_type": "cafe",
        "theme": {
            "primary_color": "#1A3A2A",
            "secondary_color": "#56C271",
            "menu_theme": "dark",
            "menu_card_layout": "list",
        },
        "super_category": "Menu",
        "categories": [
            {
                "name": "Power Bowls",
                "dishes": [
                    {"name": "Quinoa Buddha Bowl", "price": "58", "description": "Quinoa, roasted veg, avocado, tahini dressing."},
                    {"name": "Chicken Protein Bowl", "price": "65", "description": "Grilled chicken, sweet potato, edamame, lemon vinaigrette."},
                    {"name": "Vegan Grain Bowl", "price": "55", "description": "Farro, roasted chickpeas, kale, miso-ginger dressing."},
                    {"name": "Salmon & Greens Bowl", "price": "72", "description": "Poached salmon, spinach, cucumber, yuzu dressing."},
                ],
            },
            {
                "name": "Salads",
                "dishes": [
                    {"name": "Classic Caesar", "price": "45", "description": "Romaine, parmesan, croutons, house caesar dressing."},
                    {"name": "Greek Salad", "price": "42", "description": "Tomato, cucumber, olives, feta, oregano vinaigrette."},
                    {"name": "Mixed Greens", "price": "35", "description": "Seasonal leaves, cherry tomatoes, balsamic."},
                    {"name": "Nicoise", "price": "55", "description": "Tuna, egg, green beans, olives, mustard dressing."},
                ],
            },
            {
                "name": "Smoothies",
                "dishes": [
                    {"name": "Green Detox", "price": "32", "description": "Spinach, cucumber, green apple, ginger, lemon."},
                    {"name": "Berry Blast", "price": "35", "description": "Strawberry, raspberry, blueberry, banana, almond milk."},
                    {"name": "Tropical Sunshine", "price": "35", "description": "Mango, pineapple, coconut milk, turmeric."},
                    {"name": "Banana Protein", "price": "38", "description": "Banana, peanut butter, oat milk, protein powder."},
                ],
            },
            {
                "name": "Cold-Pressed Juice",
                "dishes": [
                    {"name": "Immunity Shot (60ml)", "price": "18", "description": "Ginger, lemon, turmeric, black pepper."},
                    {"name": "Green Cleanser", "price": "28", "description": "Celery, cucumber, kale, lemon, ginger."},
                    {"name": "Carrot Ginger", "price": "28", "description": "Carrot, apple, ginger, orange."},
                    {"name": "Citrus Boost", "price": "28", "description": "Orange, grapefruit, lemon, mint."},
                ],
            },
            {
                "name": "Wraps & Bites",
                "dishes": [
                    {"name": "Grilled Chicken Wrap", "price": "45", "description": "Chicken, hummus, grilled veg, rocket in a whole-wheat wrap."},
                    {"name": "Falafel Wrap", "price": "38", "description": "Crispy falafel, tahini, salad, pickled cabbage. Vegan."},
                    {"name": "Avocado Toast", "price": "35", "description": "Smashed avocado, sourdough, poached egg, chilli flakes."},
                    {"name": "Energy Balls (3 pcs)", "price": "22", "description": "Oat, date, cocoa — no added sugar."},
                ],
            },
        ],
    },
    "burger": {
        "label": "Burger joint / Smashburger",
        "business_type": "restaurant",
        "theme": {
            "primary_color": "#1C1917",
            "secondary_color": "#F59E0B",
            "menu_theme": "dark",
            "menu_card_layout": "grid",
        },
        "super_category": "Menu",
        "categories": [
            {
                "name": "Burgers",
                "dishes": [
                    {"name": "Classic Smash", "price": "55", "description": "Double smash patty, american cheese, pickles, special sauce."},
                    {"name": "Crispy Chicken Burger", "price": "58", "description": "Crispy chicken thigh, coleslaw, sriracha mayo."},
                    {"name": "BBQ Bacon Burger", "price": "68", "description": "Double patty, crispy bacon, cheddar, BBQ sauce."},
                    {"name": "Veggie Burger", "price": "50", "description": "Black bean & quinoa patty, lettuce, avocado, chipotle mayo."},
                    {"name": "The Monster", "price": "80", "description": "Triple smash, triple cheese, caramelised onions, mushrooms."},
                ],
            },
            {
                "name": "Sides",
                "dishes": [
                    {"name": "Smash Fries", "price": "22", "description": "Golden crispy fries, signature seasoning."},
                    {"name": "Onion Rings", "price": "25", "description": "Beer-battered, golden and crispy."},
                    {"name": "Chicken Nuggets (6 pcs)", "price": "30", "description": "All-breast, hand-breaded, dipping sauce."},
                    {"name": "Loaded Fries", "price": "38", "description": "Fries, cheddar sauce, jalapeños, bacon bits."},
                ],
            },
            {
                "name": "Drinks",
                "dishes": [
                    {"name": "Classic Milkshake", "price": "35", "description": "Vanilla, chocolate, or strawberry — thick and creamy."},
                    {"name": "Fresh Lemonade", "price": "22", "description": "Hand-squeezed, lightly sweet."},
                    {"name": "Soft Drink", "price": "15", "description": "Pepsi, 7-Up, or water."},
                ],
            },
        ],
    },
    "bubble_tea": {
        "label": "Bubble tea / Boba bar",
        "business_type": "cafe",
        "theme": {
            "primary_color": "#3B1F5E",
            "secondary_color": "#F472B6",
            "menu_theme": "dark",
            "menu_card_layout": "grid",
        },
        "super_category": "Menu",
        "categories": [
            {
                "name": "Milk Teas",
                "dishes": [
                    {"name": "Classic Milk Tea", "price": "28", "description": "Black tea, creamy milk, tapioca pearls. Sugar level adjustable."},
                    {"name": "Taro Milk Tea", "price": "32", "description": "Purple taro, sweet milk, black pearls."},
                    {"name": "Matcha Latte Boba", "price": "35", "description": "Japanese matcha, oat milk, tapioca pearls."},
                    {"name": "Brown Sugar Boba", "price": "38", "description": "Tiger-striped brown sugar, fresh milk, black pearls."},
                    {"name": "Oolong Milk Tea", "price": "30", "description": "Fragrant oolong, creamy milk, chewy pearls."},
                ],
            },
            {
                "name": "Fruit Teas",
                "dishes": [
                    {"name": "Passion Fruit Tea", "price": "30", "description": "Passion fruit, green tea, popping boba."},
                    {"name": "Lychee Slush", "price": "32", "description": "Lychee, crushed ice, coconut jelly."},
                    {"name": "Mango Green Tea", "price": "30", "description": "Jasmine green tea, fresh mango, tapioca."},
                    {"name": "Strawberry Yogurt", "price": "35", "description": "Strawberry, yogurt base, strawberry popping boba."},
                ],
            },
            {
                "name": "Extras",
                "dishes": [
                    {"name": "Extra Pearls", "price": "5", "description": "Add another serving of tapioca pearls."},
                    {"name": "Coconut Jelly", "price": "6", "description": "Cubed coconut jelly topping."},
                    {"name": "Pudding Topping", "price": "8", "description": "Egg or taro pudding topping."},
                ],
            },
        ],
    },
    "juice_bar": {
        "label": "Juice bar / Smoothies",
        "business_type": "cafe",
        "theme": {
            "primary_color": "#1B4332",
            "secondary_color": "#F97316",
            "menu_theme": "dark",
            "menu_card_layout": "list",
        },
        "super_category": "Menu",
        "categories": [
            {
                "name": "Fresh Juices",
                "dishes": [
                    {"name": "Fresh Orange Juice", "price": "22", "description": "Hand-squeezed Moroccan oranges, 500ml."},
                    {"name": "Carrot Apple Ginger", "price": "25", "description": "Cold-pressed carrot, apple, fresh ginger."},
                    {"name": "Watermelon Mint", "price": "22", "description": "Fresh watermelon, spearmint, squeeze of lime."},
                    {"name": "Mixed Citrus", "price": "25", "description": "Orange, grapefruit, lemon — immune booster."},
                    {"name": "Beet & Apple", "price": "28", "description": "Red beet, apple, lemon, ginger."},
                ],
            },
            {
                "name": "Smoothies",
                "dishes": [
                    {"name": "Mango Paradise", "price": "35", "description": "Mango, banana, coconut milk, passion fruit."},
                    {"name": "Green Power", "price": "38", "description": "Spinach, cucumber, apple, ginger, lemon."},
                    {"name": "Strawberry Banana", "price": "32", "description": "Fresh strawberry, banana, yogurt, honey."},
                    {"name": "Avocado Smoothie", "price": "38", "description": "Avocado, banana, almond milk, maple syrup."},
                    {"name": "Peanut Butter Boost", "price": "40", "description": "Banana, peanut butter, oat milk, protein powder."},
                ],
            },
            {
                "name": "Shots & Boosters",
                "dishes": [
                    {"name": "Ginger Immunity Shot (60ml)", "price": "18", "description": "Ginger, lemon, turmeric, black pepper."},
                    {"name": "Wheatgrass Shot (60ml)", "price": "20", "description": "Pure cold-pressed wheatgrass."},
                    {"name": "Add-On: Protein Powder", "price": "10", "description": "25g scoop — vanilla or chocolate."},
                ],
            },
        ],
    },
    "ice_cream": {
        "label": "Ice cream / Gelato",
        "business_type": "cafe",
        "theme": {
            "primary_color": "#1E3A8A",
            "secondary_color": "#FB7185",
            "menu_theme": "light",
            "menu_card_layout": "grid",
        },
        "super_category": "Menu",
        "categories": [
            {
                "name": "Scoops",
                "dishes": [
                    {"name": "Single Scoop", "price": "18", "description": "Choose one flavour: vanilla, chocolate, strawberry, pistachio, caramel."},
                    {"name": "Double Scoop", "price": "30", "description": "Two flavours in a wafer cone or cup."},
                    {"name": "Triple Scoop", "price": "42", "description": "Three flavours — the full tour."},
                ],
            },
            {
                "name": "Sundaes",
                "dishes": [
                    {"name": "Classic Sundae", "price": "40", "description": "Two scoops, chocolate or caramel sauce, whipped cream, cherry."},
                    {"name": "Banana Split", "price": "55", "description": "Banana, three scoops, three sauces, whipped cream, sprinkles."},
                    {"name": "Brownie Sundae", "price": "60", "description": "Warm brownie, vanilla scoop, hot fudge, whipped cream."},
                    {"name": "Fruit Sorbet Plate", "price": "45", "description": "Three scoops of fruit sorbet, fresh seasonal fruit."},
                ],
            },
            {
                "name": "Milkshakes",
                "dishes": [
                    {"name": "Classic Milkshake", "price": "38", "description": "Thick shake — vanilla, chocolate, strawberry, or pistachio."},
                    {"name": "Oreo Milkshake", "price": "45", "description": "Vanilla, crushed Oreos, whipped cream."},
                    {"name": "Nutella Milkshake", "price": "48", "description": "Chocolate, Nutella swirl, hazelnut crumble."},
                ],
            },
        ],
    },
    "seafood": {
        "label": "Seafood restaurant",
        "business_type": "restaurant",
        "theme": {
            "primary_color": "#0A2342",
            "secondary_color": "#06B6D4",
            "menu_theme": "dark",
            "menu_card_layout": "grid",
        },
        "super_category": "Menu",
        "categories": [
            {
                "name": "Starters",
                "dishes": [
                    {"name": "Oysters (6 pcs)", "price": "90", "description": "Fresh local oysters, mignonette sauce, lemon."},
                    {"name": "Shrimp Cocktail", "price": "75", "description": "Chilled tiger prawns, house cocktail sauce."},
                    {"name": "Calamari Fritti", "price": "55", "description": "Crispy fried squid rings, aioli, lemon."},
                    {"name": "Fish Soup", "price": "45", "description": "Rich tomato-saffron broth, crusty bread, rouille."},
                ],
            },
            {
                "name": "Grills & Platters",
                "dishes": [
                    {"name": "Grilled Sea Bass", "price": "130", "description": "Whole sea bass, chargrilled, herbs, lemon butter."},
                    {"name": "Lobster Thermidor (half)", "price": "180", "description": "Half lobster, cream, mustard, gruyère."},
                    {"name": "Mixed Seafood Platter (2 pax)", "price": "250", "description": "Prawns, squid, mussels, fish fillet, fries, salad."},
                    {"name": "Grilled King Prawns (4 pcs)", "price": "110", "description": "Garlic butter, chilli, parsley."},
                ],
            },
            {
                "name": "Sides & Drinks",
                "dishes": [
                    {"name": "Hand-cut Fries", "price": "22", "description": "Fresh potatoes, seasoned salt."},
                    {"name": "Grilled Vegetables", "price": "28", "description": "Seasonal veg, olive oil, herbs."},
                    {"name": "House Salad", "price": "25", "description": "Mixed leaves, cherry tomatoes, vinaigrette."},
                    {"name": "Fresh Lemonade", "price": "22", "description": "Hand-squeezed, mint, lightly sweet."},
                ],
            },
        ],
    },
    "steakhouse": {
        "label": "Steakhouse / Grill",
        "business_type": "restaurant",
        "theme": {
            "primary_color": "#1A0A00",
            "secondary_color": "#DC2626",
            "menu_theme": "dark",
            "menu_card_layout": "list",
        },
        "super_category": "Menu",
        "categories": [
            {
                "name": "Starters",
                "dishes": [
                    {"name": "Shrimp Cocktail", "price": "65", "description": "Chilled prawns, house cocktail sauce, lemon wedge."},
                    {"name": "Bone Marrow", "price": "75", "description": "Roasted marrow bones, herb salsa, toast."},
                    {"name": "Burrata", "price": "60", "description": "Creamy burrata, heirloom tomatoes, basil, olive oil."},
                    {"name": "French Onion Soup", "price": "45", "description": "Slow-cooked, gruyère crouton."},
                ],
            },
            {
                "name": "Steaks",
                "dishes": [
                    {"name": "Entrecôte 300g", "price": "180", "description": "Grass-fed ribeye, pepper sauce or béarnaise."},
                    {"name": "Filet Mignon 250g", "price": "220", "description": "Tenderloin centre-cut, truffle butter."},
                    {"name": "Tomahawk 1kg (to share)", "price": "490", "description": "Aged 30 days, served with 3 sauces."},
                    {"name": "New York Strip 350g", "price": "200", "description": "Well-marbled, classic char."},
                ],
            },
            {
                "name": "Sides",
                "dishes": [
                    {"name": "Truffle Fries", "price": "35", "description": "Hand-cut, truffle oil, parmesan."},
                    {"name": "Creamed Spinach", "price": "28", "description": "Wilted spinach, cream, nutmeg."},
                    {"name": "Mac & Cheese", "price": "35", "description": "Three cheeses, golden breadcrumb crust."},
                    {"name": "Asparagus", "price": "30", "description": "Charred asparagus, hollandaise."},
                ],
            },
            {
                "name": "Desserts",
                "dishes": [
                    {"name": "Crème Brûlée", "price": "45", "description": "Classic vanilla, caramelised sugar."},
                    {"name": "Chocolate Lava Cake", "price": "50", "description": "Warm dark chocolate, vanilla ice cream."},
                ],
            },
        ],
    },
    "indian": {
        "label": "Indian / Curry house",
        "business_type": "restaurant",
        "theme": {
            "primary_color": "#78350F",
            "secondary_color": "#F59E0B",
            "menu_theme": "dark",
            "menu_card_layout": "list",
        },
        "super_category": "Menu",
        "categories": [
            {
                "name": "Starters",
                "dishes": [
                    {"name": "Samosa (2 pcs)", "price": "22", "description": "Crispy pastry, spiced potato & peas, tamarind chutney."},
                    {"name": "Onion Bhaji (3 pcs)", "price": "25", "description": "Crispy onion fritters, mint raita."},
                    {"name": "Chicken Tikka Starter", "price": "45", "description": "Tandoor-marinated chicken, cumin raita, salad."},
                    {"name": "Aloo Tikki", "price": "28", "description": "Spiced potato patties, coriander chutney."},
                ],
            },
            {
                "name": "Curries",
                "dishes": [
                    {"name": "Chicken Tikka Masala", "price": "70", "description": "Tender chicken, creamy tomato-spice sauce — the classic."},
                    {"name": "Lamb Rogan Josh", "price": "80", "description": "Slow-braised lamb, Kashmiri spices, rich gravy."},
                    {"name": "Palak Paneer", "price": "60", "description": "Fresh spinach, cottage cheese, garlic, garam masala. Vegetarian."},
                    {"name": "Prawn Masala", "price": "85", "description": "Tiger prawns, coastal spice gravy, coconut undertone."},
                    {"name": "Chana Dal", "price": "50", "description": "Yellow lentils, cumin, turmeric. Vegan."},
                ],
            },
            {
                "name": "Breads & Rice",
                "dishes": [
                    {"name": "Garlic Naan", "price": "18", "description": "Tandoor-baked, butter, fresh garlic."},
                    {"name": "Peshwari Naan", "price": "22", "description": "Coconut, almond, sultana stuffed naan."},
                    {"name": "Basmati Rice", "price": "15", "description": "Steamed long-grain basmati."},
                    {"name": "Vegetable Biryani", "price": "60", "description": "Aromatic rice, seasonal vegetables, fried onions, raita."},
                ],
            },
            {
                "name": "Desserts & Drinks",
                "dishes": [
                    {"name": "Gulab Jamun (2 pcs)", "price": "22", "description": "Milk dumplings, rose syrup, pistachio."},
                    {"name": "Mango Lassi", "price": "28", "description": "Chilled yogurt, Alphonso mango, cardamom."},
                    {"name": "Masala Chai", "price": "18", "description": "Spiced milk tea, ginger, cardamom, cinnamon."},
                ],
            },
        ],
    },
    "chinese": {
        "label": "Chinese / Dim sum",
        "business_type": "restaurant",
        "theme": {
            "primary_color": "#7F1D1D",
            "secondary_color": "#EAB308",
            "menu_theme": "dark",
            "menu_card_layout": "grid",
        },
        "super_category": "Menu",
        "categories": [
            {
                "name": "Dim Sum",
                "dishes": [
                    {"name": "Har Gow (4 pcs)", "price": "35", "description": "Steamed shrimp dumplings, thin translucent skin."},
                    {"name": "Siu Mai (4 pcs)", "price": "32", "description": "Open-top pork & shrimp dumplings."},
                    {"name": "Char Siu Bao (3 pcs)", "price": "30", "description": "Steamed BBQ pork buns, fluffy pillowy dough."},
                    {"name": "Cheung Fun (Shrimp)", "price": "35", "description": "Rice noodle rolls, shrimp, oyster sauce."},
                    {"name": "Turnip Cake", "price": "28", "description": "Pan-fried radish cake, XO sauce."},
                ],
            },
            {
                "name": "Mains",
                "dishes": [
                    {"name": "Peking Duck (half)", "price": "180", "description": "Crispy skin duck, pancakes, spring onion, hoisin sauce."},
                    {"name": "Sweet & Sour Pork", "price": "70", "description": "Crispy pork, bell peppers, pineapple, classic sauce."},
                    {"name": "Kung Pao Chicken", "price": "65", "description": "Wok-fried chicken, peanuts, dried chillies, Sichuan pepper."},
                    {"name": "Steamed Sea Bass", "price": "120", "description": "Whole sea bass, ginger, scallion, soy oil."},
                ],
            },
            {
                "name": "Noodles & Rice",
                "dishes": [
                    {"name": "Wonton Noodle Soup", "price": "45", "description": "Pork & shrimp wontons, egg noodles, clear broth."},
                    {"name": "Beef Chow Fun", "price": "55", "description": "Flat rice noodles, tender beef, bean sprouts, soy."},
                    {"name": "Yangzhou Fried Rice", "price": "45", "description": "Egg, BBQ pork, shrimp, spring onion."},
                ],
            },
            {
                "name": "Desserts",
                "dishes": [
                    {"name": "Mango Pudding", "price": "25", "description": "Silky mango pudding, evaporated milk."},
                    {"name": "Egg Tart", "price": "18", "description": "Flaky pastry shell, smooth egg custard."},
                    {"name": "Sesame Balls (3 pcs)", "price": "22", "description": "Fried glutinous rice balls, lotus paste, sesame crust."},
                ],
            },
        ],
    },
    "retail": {
        "label": "Retail / Shop",
        "business_type": "retail",
        "theme": {
            "primary_color": "#37474F",
            "secondary_color": "#FF7043",
            "menu_theme": "light",
            "menu_card_layout": "grid",
        },
        "super_category": "Catalog",
        "categories": [
            {
                "name": "New Arrivals",
                "dishes": [
                    {"name": "Classic T-Shirt", "price": "120", "description": "Soft cotton, unisex."},
                    {"name": "Denim Jacket", "price": "450", "description": "Mid-wash, timeless cut."},
                    {"name": "Canvas Sneakers", "price": "320", "description": "Everyday comfort."},
                ],
            },
            {
                "name": "Accessories",
                "dishes": [
                    {"name": "Leather Belt", "price": "150", "description": "Full-grain, brass buckle."},
                    {"name": "Sunglasses", "price": "180", "description": "UV400 protection."},
                    {"name": "Cotton Cap", "price": "90", "description": "Adjustable, embroidered."},
                ],
            },
            {
                "name": "Bags",
                "dishes": [
                    {"name": "Canvas Tote", "price": "110", "description": "Roomy everyday tote."},
                    {"name": "Backpack", "price": "390", "description": "Laptop sleeve, water-resistant."},
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
