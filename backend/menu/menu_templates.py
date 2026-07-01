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
    "patisserie_fine": {
        "label": "Pâtisserie fine / French patisserie",
        "business_type": "bakery",
        "theme": {
            "primary_color": "#4A2C2A",
            "secondary_color": "#E9B7C4",
            "menu_theme": "light",
            "menu_card_layout": "grid",
        },
        "super_category": "Catalog",
        "categories": [
            {
                "name": "Signature Cakes",
                "dishes": [
                    {"name": "Opéra", "price": "38", "description": "Almond sponge, coffee buttercream, chocolate ganache."},
                    {"name": "Fraisier", "price": "42", "description": "Génoise, crème mousseline, fresh strawberries."},
                    {"name": "Paris-Brest", "price": "40", "description": "Choux pastry, praline cream, toasted almonds."},
                    {"name": "Saint-Honoré", "price": "45", "description": "Puff pastry, caramel choux, Chantilly cream."},
                ],
            },
            {
                "name": "Tarts",
                "dishes": [
                    {"name": "Tarte au Citron Meringuée", "price": "35", "description": "Zesty lemon curd, torched meringue."},
                    {"name": "Tarte aux Fraises", "price": "38", "description": "Crème pâtissière, glazed fresh strawberries."},
                    {"name": "Tarte au Chocolat", "price": "36", "description": "Dark chocolate ganache, buttery sablé crust."},
                ],
            },
            {
                "name": "Petits Fours",
                "dishes": [
                    {"name": "Éclair au Café", "price": "22", "description": "Choux pastry, coffee cream, coffee fondant."},
                    {"name": "Religieuse au Chocolat", "price": "24", "description": "Stacked choux, chocolate cream and glaze."},
                    {"name": "Macarons (12)", "price": "110", "description": "Assorted premium flavours, gift box."},
                    {"name": "Cannelé (4)", "price": "40", "description": "Caramelised crust, tender vanilla-rum centre."},
                ],
            },
        ],
    },
    "viennoiserie": {
        "label": "Viennoiserie / Morning bakery",
        "business_type": "bakery",
        "theme": {
            "primary_color": "#7C4A21",
            "secondary_color": "#F0CE9A",
            "menu_theme": "light",
            "menu_card_layout": "grid",
        },
        "super_category": "Catalog",
        "categories": [
            {
                "name": "Viennoiseries",
                "dishes": [
                    {"name": "Croissant au Beurre", "price": "8", "description": "Flaky all-butter croissant, baked fresh."},
                    {"name": "Pain au Chocolat", "price": "10", "description": "Buttery pastry, two dark chocolate batons."},
                    {"name": "Pain aux Raisins", "price": "12", "description": "Spiral pastry, crème pâtissière, plump raisins."},
                    {"name": "Chausson aux Pommes", "price": "12", "description": "Puff pastry turnover, spiced apple compote."},
                ],
            },
            {
                "name": "Breakfast Breads",
                "dishes": [
                    {"name": "Brioche Tressée", "price": "25", "description": "Soft braided brioche, golden egg wash."},
                    {"name": "Pain de Mie", "price": "20", "description": "Soft sandwich loaf, thin tender crust."},
                    {"name": "Baguette Tradition", "price": "12", "description": "Crusty crust, open airy crumb."},
                ],
            },
            {
                "name": "Cookies & Muffins",
                "dishes": [
                    {"name": "Cookie Chocolat", "price": "12", "description": "Chewy centre, dark chocolate chunks."},
                    {"name": "Muffin Myrtille", "price": "15", "description": "Moist muffin loaded with blueberries."},
                    {"name": "Financier", "price": "10", "description": "Almond-brown-butter cake, moist and nutty."},
                ],
            },
        ],
    },
    "bakery_traditional": {
        "label": "Boulangerie traditionnelle / Moroccan bakery",
        "business_type": "bakery",
        "theme": {
            "primary_color": "#6B4226",
            "secondary_color": "#D9B382",
            "menu_theme": "light",
            "menu_card_layout": "grid",
        },
        "super_category": "Catalog",
        "categories": [
            {
                "name": "Moroccan Breads",
                "dishes": [
                    {"name": "Khobz (Pain Rond)", "price": "3", "description": "Round semolina bread, baked fresh daily."},
                    {"name": "Batbout", "price": "5", "description": "Soft pan-cooked pocket bread."},
                    {"name": "Harcha", "price": "6", "description": "Pan-fried semolina flatbread, buttery and crumbly."},
                    {"name": "Msemen (2)", "price": "10", "description": "Layered square flatbread, crisp and flaky."},
                ],
            },
            {
                "name": "Savoury",
                "dishes": [
                    {"name": "Batbout Farci Kefta", "price": "18", "description": "Stuffed pocket bread, spiced minced beef."},
                    {"name": "Msemen Farci", "price": "15", "description": "Flatbread stuffed with onion and herbs."},
                    {"name": "Meloui", "price": "8", "description": "Coiled layered pancake, tender and rich."},
                ],
            },
            {
                "name": "Sweet Treats",
                "dishes": [
                    {"name": "Sfenj (3)", "price": "10", "description": "Moroccan doughnuts, light and airy."},
                    {"name": "Ghriba aux Amandes", "price": "8", "description": "Crackled almond shortbread cookie."},
                    {"name": "Baghrir", "price": "10", "description": "Thousand-hole pancake, honey and butter."},
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
    "epicerie_fine": {
        "label": "Épicerie fine / Gourmet deli",
        "business_type": "grocery",
        "theme": {
            "primary_color": "#4E342E",
            "secondary_color": "#C8A96A",
            "menu_theme": "light",
            "menu_card_layout": "grid",
        },
        "super_category": "Catalog",
        "categories": [
            {
                "name": "Cheese & Charcuterie",
                "dishes": [
                    {"name": "Aged Gouda (200g)", "price": "55", "description": "Matured, nutty and firm."},
                    {"name": "Brie de Meaux (250g)", "price": "70", "description": "Soft, creamy, bloomy rind."},
                    {"name": "Sliced Prosciutto (100g)", "price": "80", "description": "Dry-cured, thinly sliced."},
                    {"name": "Green Olive Tapenade", "price": "35", "description": "Olives, capers, olive oil."},
                ],
            },
            {
                "name": "Oils & Condiments",
                "dishes": [
                    {"name": "Extra Virgin Olive Oil 500ml", "price": "75", "description": "First cold press, single origin."},
                    {"name": "Argan Oil 250ml", "price": "90", "description": "Culinary Moroccan argan oil."},
                    {"name": "Balsamic Vinegar 250ml", "price": "60", "description": "Aged, rich and syrupy."},
                    {"name": "Wildflower Honey 500g", "price": "70", "description": "Raw, unfiltered, local."},
                ],
            },
            {
                "name": "Pantry Delicacies",
                "dishes": [
                    {"name": "Sun-Dried Tomatoes (200g)", "price": "40", "description": "In olive oil with herbs."},
                    {"name": "Dark Chocolate 70% (100g)", "price": "35", "description": "Single-origin cocoa bar."},
                    {"name": "Assorted Nuts (300g)", "price": "55", "description": "Roasted almonds, cashews, pistachios."},
                ],
            },
        ],
    },
    "organic_market": {
        "label": "Organic market / Bio store",
        "business_type": "grocery",
        "theme": {
            "primary_color": "#33691E",
            "secondary_color": "#C5E1A5",
            "menu_theme": "light",
            "menu_card_layout": "grid",
        },
        "super_category": "Catalog",
        "categories": [
            {
                "name": "Organic Produce",
                "dishes": [
                    {"name": "Organic Carrots (per kg)", "price": "18", "description": "Pesticide-free, freshly harvested."},
                    {"name": "Organic Spinach (250g)", "price": "15", "description": "Tender leaves, triple washed."},
                    {"name": "Organic Avocado (each)", "price": "12", "description": "Ripe and ready to eat."},
                    {"name": "Organic Lemons (per kg)", "price": "20", "description": "Unwaxed, thin-skinned."},
                ],
            },
            {
                "name": "Grains & Superfoods",
                "dishes": [
                    {"name": "Organic Quinoa 500g", "price": "45", "description": "Protein-rich whole grain."},
                    {"name": "Chia Seeds 250g", "price": "38", "description": "Rich in omega-3 and fibre."},
                    {"name": "Rolled Oats 1kg", "price": "30", "description": "Whole-grain, no additives."},
                    {"name": "Raw Almonds 500g", "price": "70", "description": "Unroasted, unsalted."},
                ],
            },
            {
                "name": "Plant-Based",
                "dishes": [
                    {"name": "Almond Milk 1L", "price": "28", "description": "Unsweetened, no additives."},
                    {"name": "Tofu Nature 400g", "price": "25", "description": "Organic firm tofu."},
                    {"name": "Coconut Yogurt 400g", "price": "35", "description": "Dairy-free, live cultures."},
                ],
            },
        ],
    },
    "convenience_store": {
        "label": "Convenience store / Hanout",
        "business_type": "grocery",
        "theme": {
            "primary_color": "#0D47A1",
            "secondary_color": "#FFCA28",
            "menu_theme": "light",
            "menu_card_layout": "grid",
        },
        "super_category": "Catalog",
        "categories": [
            {
                "name": "Snacks",
                "dishes": [
                    {"name": "Potato Chips 45g", "price": "8", "description": "Salted, crispy."},
                    {"name": "Chocolate Bar", "price": "10", "description": "Milk chocolate, single bar."},
                    {"name": "Biscuits Pack", "price": "12", "description": "Assorted sweet biscuits."},
                    {"name": "Salted Peanuts 100g", "price": "10", "description": "Roasted and salted."},
                ],
            },
            {
                "name": "Drinks",
                "dishes": [
                    {"name": "Cola 1.5L", "price": "12", "description": "Chilled, family size."},
                    {"name": "Still Water 1.5L", "price": "6", "description": "Single bottle."},
                    {"name": "Energy Drink 25cl", "price": "15", "description": "Chilled can."},
                    {"name": "Fruit Juice 25cl", "price": "8", "description": "Orange or apple."},
                ],
            },
            {
                "name": "Essentials",
                "dishes": [
                    {"name": "Fresh Milk 1L", "price": "10", "description": "Pasteurised, chilled."},
                    {"name": "Sliced Bread", "price": "12", "description": "Soft sandwich loaf."},
                    {"name": "Eggs (6)", "price": "14", "description": "Half-dozen, fresh."},
                    {"name": "Table Salt 1kg", "price": "6", "description": "Fine iodised salt."},
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
    "mexican": {
        "label": "Mexican / Tacos",
        "business_type": "restaurant",
        "theme": {
            "primary_color": "#7C1C0A",
            "secondary_color": "#F5A623",
            "menu_theme": "dark",
            "menu_card_layout": "grid",
        },
        "super_category": "Menu",
        "categories": [
            {
                "name": "Tacos",
                "dishes": [
                    {"name": "Taco al Pastor", "price": "30", "description": "Porc mariné, ananas, coriandre, salsa rouge."},
                    {"name": "Taco de Poulet Grillé", "price": "28", "description": "Poulet épicé, guacamole, pico de gallo."},
                    {"name": "Taco Veggie", "price": "25", "description": "Haricots noirs, maïs, poivrons, salsa verde."},
                    {"name": "Taco Boeuf", "price": "32", "description": "Boeuf haché assaisonné, fromage, jalapeño."},
                ],
            },
            {
                "name": "Burritos",
                "dishes": [
                    {"name": "Burrito Classic", "price": "55", "description": "Riz, haricots, boeuf, crème, fromage."},
                    {"name": "Burrito Poulet", "price": "52", "description": "Poulet grillé, riz, guacamole, salsa."},
                    {"name": "Burrito Végétarien", "price": "48", "description": "Légumes rôtis, haricots, riz, salsa verde."},
                ],
            },
            {
                "name": "Sides",
                "dishes": [
                    {"name": "Guacamole & Nachos", "price": "35", "description": "Avocat frais, tomate, citron vert, chips de maïs."},
                    {"name": "Quesadilla", "price": "40", "description": "Tortilla grillée, fromage fondant, jalapeño."},
                    {"name": "Elotes (Maïs grillé)", "price": "22", "description": "Maïs grillé, mayonnaise, fromage, paprika."},
                    {"name": "Frites de Patate Douce", "price": "25", "description": "Croustillantes, sauce chipotle."},
                ],
            },
            {
                "name": "Drinks",
                "dishes": [
                    {"name": "Horchata", "price": "22", "description": "Boisson de riz crémeuse, cannelle, vanille."},
                    {"name": "Agua de Jamaica", "price": "20", "description": "Infusion d'hibiscus fraîche, légèrement sucrée."},
                    {"name": "Limonade Citron Vert", "price": "18", "description": "Pressée minute, piment doux."},
                ],
            },
        ],
    },
    "snack_shawarma": {
        "label": "Snack / Shawarma",
        "business_type": "restaurant",
        "theme": {
            "primary_color": "#2C1A0E",
            "secondary_color": "#E8A020",
            "menu_theme": "dark",
            "menu_card_layout": "grid",
        },
        "super_category": "Menu",
        "categories": [
            {
                "name": "Shawarma & Tacos",
                "dishes": [
                    {"name": "Shawarma Poulet", "price": "28", "description": "Poulet mariné, sauce blanche, chou, cornichon."},
                    {"name": "Shawarma Viande", "price": "35", "description": "Viande de veau, tahini, légumes croquants."},
                    {"name": "Taco Viande", "price": "22", "description": "Galette fine, viande assaisonnée, sauce harissa."},
                    {"name": "Taco Poulet Crispy", "price": "22", "description": "Poulet frit croustillant, mayonnaise, salade."},
                    {"name": "Mix Shawarma (Poulet + Viande)", "price": "40", "description": "Moitié poulet, moitié viande, double sauce."},
                ],
            },
            {
                "name": "Paninis & Burgers",
                "dishes": [
                    {"name": "Panini Poulet", "price": "30", "description": "Pain ciabatta grillé, poulet, fromage, tomate."},
                    {"name": "Panini Viande Hachée", "price": "32", "description": "Viande épicée, fromage fondu, salade, ketchup."},
                    {"name": "Burger Smash", "price": "45", "description": "Deux steaks smashés, cheddar, pickles, sauce maison."},
                    {"name": "Burger Poulet Crispy", "price": "42", "description": "Poulet frit, coleslaw, mayo épicée, pain brioché."},
                ],
            },
            {
                "name": "Frites & Sides",
                "dishes": [
                    {"name": "Frites Classiques", "price": "15", "description": "Dorées et croustillantes, sel fin."},
                    {"name": "Frites Chargées", "price": "30", "description": "Frites, fromage fondu, viande hachée, sauce."},
                    {"name": "Frites Épicées", "price": "18", "description": "Assaisonnées paprika-cumin, sauce harissa."},
                    {"name": "Salade Maison", "price": "20", "description": "Laitue, tomate, oignon, vinaigrette citron."},
                ],
            },
            {
                "name": "Boissons",
                "dishes": [
                    {"name": "Soda (cannette)", "price": "10", "description": "Coca, Fanta ou Sprite, servi frais."},
                    {"name": "Jus d'Orange Pressé", "price": "18", "description": "Oranges fraîches du Maroc, pressées minute."},
                    {"name": "Eau Minérale", "price": "8", "description": "50cl, servie fraîche."},
                ],
            },
        ],
    },
    "breakfast_brunch": {
        "label": "Breakfast / Brunch",
        "business_type": "cafe",
        "theme": {
            "primary_color": "#A0522D",
            "secondary_color": "#FDE68A",
            "menu_theme": "light",
            "menu_card_layout": "grid",
        },
        "super_category": "Menu",
        "categories": [
            {
                "name": "Breakfasts",
                "dishes": [
                    {"name": "Full Moroccan Breakfast", "price": "65", "description": "Msemen, beghrir, amlou, olive oil, honey, olives, cheese."},
                    {"name": "Continental Breakfast", "price": "55", "description": "Croissant, butter, jam, orange juice, coffee."},
                    {"name": "Avocado Toast", "price": "50", "description": "Sourdough, smashed avocado, lemon, chilli flakes."},
                    {"name": "Granola Bowl", "price": "45", "description": "Homemade granola, yogurt, fresh fruit, honey."},
                ],
            },
            {
                "name": "Pancakes & Sweets",
                "dishes": [
                    {"name": "Fluffy Pancakes", "price": "50", "description": "Stack of three, maple syrup, fresh berries."},
                    {"name": "French Toast", "price": "48", "description": "Brioche dipped in vanilla custard, powdered sugar."},
                    {"name": "Msemen au Miel & Argan", "price": "30", "description": "Crêpes feuilletées marocaines, miel, huile d'argan."},
                    {"name": "Crêpe Sucrée", "price": "28", "description": "Nutella, banane ou confiture au choix."},
                ],
            },
            {
                "name": "Egg Dishes",
                "dishes": [
                    {"name": "Eggs Benedict", "price": "65", "description": "Poached eggs, Canadian ham, hollandaise, English muffin."},
                    {"name": "Shakshuka", "price": "55", "description": "Eggs poached in spiced tomato sauce, fresh herbs."},
                    {"name": "Omelette Maison", "price": "45", "description": "Three eggs, choice of fillings: cheese / veggies / merguez."},
                    {"name": "Scrambled Eggs & Toast", "price": "40", "description": "Creamy soft-scrambled eggs, buttered toast."},
                ],
            },
            {
                "name": "Coffee & Juice",
                "dishes": [
                    {"name": "Cappuccino", "price": "25", "description": "Double shot espresso, steamed milk foam."},
                    {"name": "Café au Lait", "price": "22", "description": "Strong coffee, hot milk, light and smooth."},
                    {"name": "Fresh Orange Juice", "price": "22", "description": "Pressed to order, 100% Moroccan oranges."},
                    {"name": "Green Detox Juice", "price": "30", "description": "Spinach, cucumber, ginger, apple, lemon."},
                    {"name": "Moroccan Mint Tea", "price": "18", "description": "Fresh mint, green tea, light sugar."},
                ],
            },
        ],
    },
    "vegan": {
        "label": "Vegan / Plant-based",
        "business_type": "restaurant",
        "theme": {
            "primary_color": "#1F3D1A",
            "secondary_color": "#7EC850",
            "menu_theme": "light",
            "menu_card_layout": "grid",
        },
        "super_category": "Menu",
        "categories": [
            {
                "name": "Bowls",
                "dishes": [
                    {"name": "Buddha Bowl", "price": "65", "description": "Quinoa, roasted veggies, chickpeas, tahini dressing."},
                    {"name": "Falafel Bowl", "price": "60", "description": "Crispy falafels, hummus, tabbouleh, pita chips."},
                    {"name": "Moroccan Couscous Bowl", "price": "58", "description": "Steamed couscous, seven vegetables, harissa."},
                    {"name": "Poke Bowl", "price": "70", "description": "Brown rice, avocado, edamame, mango, sesame."},
                ],
            },
            {
                "name": "Burgers & Wraps",
                "dishes": [
                    {"name": "Black Bean Burger", "price": "55", "description": "Smoky black-bean patty, avocado, pickles, vegan mayo."},
                    {"name": "Falafel Wrap", "price": "45", "description": "Whole-wheat wrap, falafel, hummus, veggies."},
                    {"name": "Mushroom & Lentil Burger", "price": "58", "description": "Earthy mushroom-lentil patty, tomato, rocket, tahini."},
                ],
            },
            {
                "name": "Salads",
                "dishes": [
                    {"name": "Salade de Quinoa", "price": "48", "description": "Quinoa, tomates cerises, concombre, herbes fraîches."},
                    {"name": "Salade Marocaine", "price": "35", "description": "Tomates, poivrons, cumin, coriandre, huile d'olive."},
                    {"name": "Salade de Pois Chiches", "price": "42", "description": "Pois chiches rôtis, épinards, citron, sumac."},
                    {"name": "Salade d'Avocat & Mangue", "price": "50", "description": "Avocat, mangue, roquette, vinaigrette agrumes."},
                ],
            },
            {
                "name": "Smoothies",
                "dishes": [
                    {"name": "Green Power Smoothie", "price": "35", "description": "Spinach, banana, almond milk, chia seeds."},
                    {"name": "Berry Blast", "price": "38", "description": "Mixed berries, coconut milk, flaxseed."},
                    {"name": "Mango Sunshine", "price": "35", "description": "Mango, orange, turmeric, ginger."},
                    {"name": "Chocolate Protein Shake", "price": "40", "description": "Plant protein, cacao, oat milk, almond butter."},
                ],
            },
        ],
    },
    "fried_chicken": {
        "label": "Fried Chicken",
        "business_type": "restaurant",
        "theme": {
            "primary_color": "#3D1A00",
            "secondary_color": "#FF6B00",
            "menu_theme": "dark",
            "menu_card_layout": "grid",
        },
        "super_category": "Menu",
        "categories": [
            {
                "name": "Buckets",
                "dishes": [
                    {"name": "Bucket 6 pcs", "price": "85", "description": "6 morceaux de poulet frit croustillant, sauce au choix."},
                    {"name": "Bucket 10 pcs", "price": "130", "description": "10 morceaux, 2 sauces, idéal à partager."},
                    {"name": "Bucket Family 15 pcs", "price": "190", "description": "15 morceaux assortis, 3 sauces, 4 frites."},
                ],
            },
            {
                "name": "Burgers",
                "dishes": [
                    {"name": "Crispy Chicken Burger", "price": "50", "description": "Filet de poulet frit, coleslaw, mayo épicée, pain brioché."},
                    {"name": "Double Crispy Burger", "price": "68", "description": "Double filet frit, cheddar, pickles, sauce barbecue."},
                    {"name": "Spicy Hot Burger", "price": "55", "description": "Poulet mariné piment, sauce ranch, jalapeño."},
                    {"name": "Chicken Cheese Burger", "price": "58", "description": "Poulet frit, fromage fondu, tomate, laitue."},
                ],
            },
            {
                "name": "Tenders & Wings",
                "dishes": [
                    {"name": "Tenders 4 pcs", "price": "45", "description": "Filets de poulet panés, sauce BBQ ou ranch."},
                    {"name": "Wings Buffalo 6 pcs", "price": "50", "description": "Ailes marinées sauce buffalo, céleri, bleu cheese."},
                    {"name": "Wings Honey Garlic 6 pcs", "price": "52", "description": "Ailes glacées miel-ail, sésame, oignon vert."},
                    {"name": "Combo Tenders & Wings", "price": "75", "description": "3 tenders + 4 wings, 2 sauces, frites."},
                ],
            },
            {
                "name": "Sides",
                "dishes": [
                    {"name": "Frites Croustillantes", "price": "18", "description": "Frites maison dorées, sel et épices."},
                    {"name": "Coleslaw Maison", "price": "15", "description": "Chou blanc et rouge, carottes, mayo légère."},
                    {"name": "Corn on the Cob", "price": "15", "description": "Épis de maïs grillés, beurre et herbes."},
                    {"name": "Mac & Cheese", "price": "28", "description": "Macaroni crémeux au cheddar fondu."},
                    {"name": "Biscuit Maison", "price": "12", "description": "Biscuit feuilleté chaud, beurre et miel."},
                ],
            },
        ],
    },
    "tea_house": {
        "label": "Tea house / Moroccan pastries",
        "business_type": "cafe",
        "theme": {
            "primary_color": "#4A2C17",
            "secondary_color": "#D4AC6E",
            "menu_theme": "light",
            "menu_card_layout": "grid",
        },
        "super_category": "Menu",
        "categories": [
            {
                "name": "Teas",
                "dishes": [
                    {"name": "Atay bil Nana (Thé à la Menthe)", "price": "18", "description": "Thé vert, menthe fraîche, sucre, servi en théière."},
                    {"name": "Thé à l'Absinthe", "price": "18", "description": "Thé vert marocain, chiba, saveur légèrement amère."},
                    {"name": "Thé aux Roses", "price": "20", "description": "Thé vert, pétales de rose, cardamome."},
                    {"name": "Thé Khmira (Épicé)", "price": "22", "description": "Mélange de 7 épices marocaines, gingembre, cannelle."},
                    {"name": "Thé au Lait d'Amande", "price": "25", "description": "Thé vert, lait d'amande maison, fleur d'oranger."},
                ],
            },
            {
                "name": "Moroccan Pastries",
                "dishes": [
                    {"name": "Cornes de Gazelle", "price": "12", "description": "Pâtisseries à la pâte d'amande, eau de fleur d'oranger."},
                    {"name": "Briouates aux Amandes", "price": "15", "description": "Feuilleté croustillant, farce amande-cannelle, miel."},
                    {"name": "Sellou", "price": "20", "description": "Mélange de farine grillée, amandes, sésame, miel."},
                    {"name": "Fekkas", "price": "14", "description": "Biscuits secs aux amandes et raisins secs."},
                    {"name": "Chebakia", "price": "15", "description": "Fleurs de sésame frites, miel, eau de rose."},
                ],
            },
            {
                "name": "Crepes & Msemen",
                "dishes": [
                    {"name": "Msemen Nature", "price": "12", "description": "Crêpe feuilletée marocaine, beurre et miel."},
                    {"name": "Msemen Farci", "price": "22", "description": "Msemen garni viande hachée et oignons caramélisés."},
                    {"name": "Beghrir (Crêpe aux Mille Trous)", "price": "18", "description": "Crêpe spongieuse, beurre fondu, miel."},
                    {"name": "Crêpe Sucrée", "price": "20", "description": "Fine crêpe, miel d'argan ou confiture de figues."},
                ],
            },
            {
                "name": "Cold Drinks",
                "dishes": [
                    {"name": "Jus d'Orange Pressé", "price": "20", "description": "Oranges du Maroc pressées minute, frais."},
                    {"name": "Citronnade à la Menthe", "price": "22", "description": "Citrons, menthe fraîche, eau gazeuse."},
                    {"name": "Smoothie Avocat-Lait", "price": "30", "description": "Avocat frais, lait, sucre — classique marocain."},
                    {"name": "Eau Infusée Hibiscus", "price": "18", "description": "Fleurs de karkadé, citron vert, menthe."},
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
    "fashion_boutique": {
        "label": "Fashion boutique / Prêt-à-porter",
        "business_type": "retail",
        "theme": {
            "primary_color": "#212121",
            "secondary_color": "#D4AF37",
            "menu_theme": "light",
            "menu_card_layout": "grid",
        },
        "super_category": "Catalog",
        "categories": [
            {
                "name": "Women",
                "dishes": [
                    {"name": "Silk Blouse", "price": "390", "description": "Flowing silk, mother-of-pearl buttons."},
                    {"name": "Tailored Blazer", "price": "690", "description": "Structured shoulders, lined."},
                    {"name": "Midi Dress", "price": "520", "description": "Elegant cut, breathable fabric."},
                    {"name": "High-Waist Trousers", "price": "420", "description": "Tapered leg, crease-front."},
                ],
            },
            {
                "name": "Men",
                "dishes": [
                    {"name": "Oxford Shirt", "price": "290", "description": "Crisp cotton, button-down collar."},
                    {"name": "Chino Trousers", "price": "360", "description": "Slim fit, stretch cotton."},
                    {"name": "Wool Sweater", "price": "480", "description": "Merino wool, ribbed trim."},
                    {"name": "Slim Blazer", "price": "790", "description": "Half-lined, notch lapel."},
                ],
            },
            {
                "name": "Accessories",
                "dishes": [
                    {"name": "Silk Scarf", "price": "220", "description": "Hand-rolled edges, printed."},
                    {"name": "Leather Wallet", "price": "260", "description": "Full-grain, card slots."},
                    {"name": "Statement Necklace", "price": "180", "description": "Gold-tone, adjustable."},
                ],
            },
        ],
    },
    "electronics_store": {
        "label": "Electronics store / High-tech",
        "business_type": "retail",
        "theme": {
            "primary_color": "#0B1E3B",
            "secondary_color": "#00B0FF",
            "menu_theme": "dark",
            "menu_card_layout": "grid",
        },
        "super_category": "Catalog",
        "categories": [
            {
                "name": "Audio",
                "dishes": [
                    {"name": "Wireless Earbuds", "price": "450", "description": "Active noise cancellation, 24h battery."},
                    {"name": "Bluetooth Speaker", "price": "390", "description": "Waterproof, deep bass."},
                    {"name": "Over-Ear Headphones", "price": "690", "description": "Studio sound, foldable."},
                ],
            },
            {
                "name": "Accessories",
                "dishes": [
                    {"name": "Fast Charger 20W", "price": "120", "description": "USB-C, quick charge."},
                    {"name": "Power Bank 10000mAh", "price": "180", "description": "Slim, dual-port."},
                    {"name": "Phone Case", "price": "90", "description": "Shockproof, slim profile."},
                    {"name": "Braided USB-C Cable 2m", "price": "60", "description": "Durable, fast data."},
                ],
            },
            {
                "name": "Smart Devices",
                "dishes": [
                    {"name": "Smartwatch", "price": "1200", "description": "Heart-rate, GPS, notifications."},
                    {"name": "Wireless Mouse", "price": "160", "description": "Ergonomic, silent click."},
                    {"name": "Mechanical Keyboard", "price": "420", "description": "Backlit, tactile switches."},
                ],
            },
        ],
    },
    "home_decor": {
        "label": "Home & decor store",
        "business_type": "retail",
        "theme": {
            "primary_color": "#5D4037",
            "secondary_color": "#BCAAA4",
            "menu_theme": "light",
            "menu_card_layout": "grid",
        },
        "super_category": "Catalog",
        "categories": [
            {
                "name": "Living Room",
                "dishes": [
                    {"name": "Woven Throw Blanket", "price": "220", "description": "Soft cotton blend, fringed."},
                    {"name": "Decorative Cushion", "price": "120", "description": "Removable cover, plush filling."},
                    {"name": "Ceramic Vase", "price": "180", "description": "Hand-glazed, matte finish."},
                    {"name": "Scented Candle", "price": "90", "description": "Soy wax, 40h burn time."},
                ],
            },
            {
                "name": "Kitchen & Dining",
                "dishes": [
                    {"name": "Stoneware Dinner Set (4)", "price": "390", "description": "Reactive glaze, dishwasher safe."},
                    {"name": "Wooden Serving Board", "price": "150", "description": "Acacia wood, oiled finish."},
                    {"name": "Glass Storage Jars (3)", "price": "130", "description": "Airtight bamboo lids."},
                ],
            },
            {
                "name": "Textiles & Rugs",
                "dishes": [
                    {"name": "Handwoven Berber Rug", "price": "890", "description": "Wool, traditional pattern."},
                    {"name": "Cotton Bath Towel Set", "price": "260", "description": "Absorbent, quick-dry."},
                    {"name": "Linen Table Runner", "price": "140", "description": "Natural weave, fringed ends."},
                ],
            },
        ],
    },
    "pharmacy": {
        "label": "Pharmacy / Parapharmacie",
        "business_type": "pharmacy",
        "theme": {
            "primary_color": "#005B72",
            "secondary_color": "#80CBC4",
            "menu_theme": "light",
            "menu_card_layout": "list",
        },
        "super_category": "Catalog",
        "categories": [
            {
                "name": "Vitamins & Supplements",
                "dishes": [
                    {"name": "Vitamin C 1000mg (30 tabs)", "price": "55", "description": "High-dose vitamin C for daily immune support."},
                    {"name": "Vitamin D3 2000 IU (60 caps)", "price": "75", "description": "Supports bone health and immune function."},
                    {"name": "Omega-3 Fish Oil (90 caps)", "price": "120", "description": "Purified EPA & DHA for cardiovascular wellness."},
                    {"name": "Magnesium 300mg (60 tabs)", "price": "65", "description": "Helps reduce fatigue and muscle cramps."},
                ],
            },
            {
                "name": "Hygiene & Care",
                "dishes": [
                    {"name": "Micellar Water 400ml", "price": "85", "description": "Gentle facial cleanser for all skin types."},
                    {"name": "SPF 50+ Sunscreen 50ml", "price": "110", "description": "Broad-spectrum UVA/UVB protection, non-greasy."},
                    {"name": "Moisturising Hand Cream 75ml", "price": "45", "description": "Fast-absorbing, fragrance-free formula."},
                    {"name": "Antiseptic Gel 100ml", "price": "30", "description": "70% alcohol hand sanitiser."},
                ],
            },
            {
                "name": "Baby & Mother",
                "dishes": [
                    {"name": "Baby Physiological Saline (18 units)", "price": "40", "description": "Sterile saline unidoses for nasal hygiene."},
                    {"name": "Baby Moisturising Lotion 200ml", "price": "70", "description": "Dermatologically tested, hypoallergenic."},
                    {"name": "Folic Acid 400mcg (90 tabs)", "price": "60", "description": "Essential B-vitamin for pregnancy preparation."},
                    {"name": "Nipple Cream 30ml", "price": "80", "description": "Lanolin-based, safe for breastfeeding."},
                ],
            },
            {
                "name": "First Aid",
                "dishes": [
                    {"name": "Sterile Gauze Pads (10 pcs)", "price": "25", "description": "Non-woven, individually wrapped."},
                    {"name": "Adhesive Bandages Assorted (30 pcs)", "price": "35", "description": "Waterproof, hypoallergenic."},
                    {"name": "Elastic Bandage 7.5cm×4.5m", "price": "28", "description": "Cohesive, reusable compression bandage."},
                    {"name": "Digital Thermometer", "price": "90", "description": "Fast 10-second oral/axillary reading."},
                ],
            },
        ],
    },
    "parapharmacie": {
        "label": "Parapharmacie / Beauty & derma",
        "business_type": "pharmacy",
        "theme": {
            "primary_color": "#00695C",
            "secondary_color": "#B2DFDB",
            "menu_theme": "light",
            "menu_card_layout": "grid",
        },
        "super_category": "Catalog",
        "categories": [
            {
                "name": "Face Care",
                "dishes": [
                    {"name": "Hyaluronic Serum 30ml", "price": "180", "description": "Deep hydration, plumps fine lines."},
                    {"name": "Vitamin C Cream 50ml", "price": "160", "description": "Brightening antioxidant day cream."},
                    {"name": "Cleansing Foam 150ml", "price": "95", "description": "Gentle daily face wash, non-drying."},
                    {"name": "Eye Contour Gel 15ml", "price": "120", "description": "Reduces puffiness and dark circles."},
                ],
            },
            {
                "name": "Body & Sun",
                "dishes": [
                    {"name": "Nourishing Body Milk 400ml", "price": "90", "description": "24h hydration, fast absorbing."},
                    {"name": "SPF 50+ Face Fluid 40ml", "price": "130", "description": "Anti-ageing, non-greasy sun protection."},
                    {"name": "Repair Cica Balm 40ml", "price": "75", "description": "Soothes and repairs irritated skin."},
                ],
            },
            {
                "name": "Hair Care",
                "dishes": [
                    {"name": "Anti-Hair-Loss Shampoo 200ml", "price": "110", "description": "Strengthens roots, stimulates growth."},
                    {"name": "Argan Hair Oil 100ml", "price": "85", "description": "Nourishing, adds shine and softness."},
                    {"name": "Anti-Dandruff Treatment 125ml", "price": "95", "description": "Soothes scalp, reduces flaking."},
                ],
            },
        ],
    },
    "herbalist": {
        "label": "Herbalist / Herboristerie",
        "business_type": "pharmacy",
        "theme": {
            "primary_color": "#4E5D2A",
            "secondary_color": "#CDDC39",
            "menu_theme": "light",
            "menu_card_layout": "list",
        },
        "super_category": "Catalog",
        "categories": [
            {
                "name": "Herbs & Teas",
                "dishes": [
                    {"name": "Verbena Loose Leaf 100g", "price": "35", "description": "Calming herbal infusion."},
                    {"name": "Chamomile Flowers 100g", "price": "30", "description": "Soothing before-sleep tea."},
                    {"name": "Green Tea Gunpowder 200g", "price": "45", "description": "Classic Moroccan mint-tea base."},
                    {"name": "Sage Leaves 100g", "price": "28", "description": "Digestive and warming infusion."},
                ],
            },
            {
                "name": "Natural Oils",
                "dishes": [
                    {"name": "Pure Argan Oil 100ml", "price": "120", "description": "Cosmetic-grade, cold-pressed."},
                    {"name": "Black Seed Oil 100ml", "price": "90", "description": "Nigella sativa, traditional tonic."},
                    {"name": "Eucalyptus Essential Oil 30ml", "price": "60", "description": "Respiratory comfort, aromatherapy."},
                    {"name": "Prickly Pear Seed Oil 30ml", "price": "220", "description": "Rich in vitamin E, anti-ageing."},
                ],
            },
            {
                "name": "Spices & Remedies",
                "dishes": [
                    {"name": "Ras el Hanout 100g", "price": "40", "description": "Blend of 20+ traditional spices."},
                    {"name": "Ground Turmeric 100g", "price": "25", "description": "Anti-inflammatory golden spice."},
                    {"name": "Raw Honey with Nigella 250g", "price": "95", "description": "Immune-supporting daily tonic."},
                    {"name": "Ginger Root Powder 100g", "price": "30", "description": "Warming digestive aid."},
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
