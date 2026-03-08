from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import schema_context

from tenancy.models import Tenant
from menu.models import Category, Dish, DishOption


class Command(BaseCommand):
    help = "Seed demo menu data into a tenant (default demo)."

    def add_arguments(self, parser):
        parser.add_argument("slug", nargs="?", default="demo", help="Tenant slug to seed")

    def handle(self, *args, **options):
        slug = options["slug"]
        try:
            tenant = Tenant.objects.get(slug=slug)
        except Tenant.DoesNotExist:
            raise CommandError(f"Tenant {slug} not found")

        self.stdout.write(f"Using tenant {tenant.slug} ({tenant.name})")

        with schema_context(tenant.schema_name):
            Category.objects.all().delete()
            Dish.objects.all().delete()
            DishOption.objects.all().delete()

            breakfast = Category.objects.create(
                name="Breakfast & Brunch",
                slug="breakfast",
                description="Morning classics and brunch favorites",
                image_url="https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=800&q=80",
                position=1,
                is_published=True,
            )
            sushi = Category.objects.create(
                name="Sushi & Bowls",
                slug="sushi",
                description="Fresh rolls and poke bowls",
                image_url="https://images.unsplash.com/photo-1540189549336-e6e99c3679fe?auto=format&fit=crop&w=800&q=80",
                position=2,
                is_published=True,
            )
            desserts = Category.objects.create(
                name="Desserts",
                slug="desserts",
                description="Sweet endings",
                image_url="https://images.unsplash.com/photo-1505250469679-203ad9ced0cb?auto=format&fit=crop&w=800&q=80",
                position=3,
                is_published=True,
            )

            california = Dish.objects.create(
                category=sushi,
                name="California Classic Sushi",
                slug="california-classic",
                description="8-piece roll with crab, avocado, toasted sesame and house soy.",
                price=12.00,
                currency="USD",
                image_url="https://images.unsplash.com/photo-1546069901-ba9599a7e63c?auto=format&fit=crop&w=800&q=80",
                position=1,
                is_published=True,
            )
            royal = Dish.objects.create(
                category=breakfast,
                name="Royal Box Petit Déjeuner",
                slug="royal-box",
                description="Pancakes, eggs, seasonal fruit, maple drizzle.",
                price=14.50,
                currency="USD",
                image_url="https://images.unsplash.com/photo-1540189549336-e6e99c3679fe?auto=format&fit=crop&w=800&q=80",
                position=1,
                is_published=True,
            )
            cheesecake = Dish.objects.create(
                category=desserts,
                name="New York Cheesecake",
                slug="cheesecake",
                description="Classic baked cheesecake with berry compote.",
                price=8.00,
                currency="USD",
                image_url="https://images.unsplash.com/photo-1505250469679-203ad9ced0cb?auto=format&fit=crop&w=800&q=80",
                position=1,
                is_published=True,
            )

            DishOption.objects.bulk_create(
                [
                    DishOption(dish=california, name="Extra ginger", price_delta=0, is_required=False, max_select=1),
                    DishOption(dish=california, name="Double avocado", price_delta=2.0, is_required=False, max_select=1),
                    DishOption(dish=royal, name="Add bacon", price_delta=3.0, is_required=False, max_select=1),
                    DishOption(dish=cheesecake, name="Extra compote", price_delta=1.5, is_required=False, max_select=1),
                ]
            )

        self.stdout.write(self.style.SUCCESS("Demo menu seeded."))
