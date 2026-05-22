from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0028_supercategory_description_image"),
    ]

    operations = [
        migrations.CreateModel(
            name="CurrencyRate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(help_text="ISO 4217 code, e.g. EUR", max_length=3, unique=True)),
                ("name", models.CharField(max_length=60)),
                ("symbol", models.CharField(help_text="Display symbol, e.g. €", max_length=10)),
                (
                    "mad_per_unit",
                    models.DecimalField(
                        decimal_places=6,
                        help_text="How many MAD equal 1 unit of this currency (1 for MAD itself).",
                        max_digits=12,
                    ),
                ),
                ("is_active", models.BooleanField(default=True, help_text="Shown to customers when active.")),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Currency Rate",
                "verbose_name_plural": "Currency Rates",
                "ordering": ["code"],
            },
        ),
        # Seed the four supported currencies with conservative starting rates.
        # The fetch_currency_rates management command will keep them current.
        migrations.RunSQL(
            sql="""
                INSERT INTO menu_currencyrate (code, name, symbol, mad_per_unit, is_active, updated_at)
                VALUES
                    ('MAD', 'Dirham marocain', 'د.م.',  1.000000, true,  NOW()),
                    ('EUR', 'Euro',            '€',    10.900000, true,  NOW()),
                    ('SAR', 'Riyal saoudien',  '﷼',    2.610000, true,  NOW()),
                    ('AED', 'Dirham émirien',  'د.إ',  2.670000, true,  NOW())
                ON CONFLICT (code) DO NOTHING;
            """,
            reverse_sql="DELETE FROM menu_currencyrate WHERE code IN ('MAD','EUR','SAR','AED');",
        ),
    ]
