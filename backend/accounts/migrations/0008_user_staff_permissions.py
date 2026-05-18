from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0007_customer_email_db_index"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="perm_manage_orders",
            field=models.BooleanField(
                default=True,
                help_text="Staff can view and update order statuses.",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="perm_view_revenue",
            field=models.BooleanField(
                default=False,
                help_text="Staff can view revenue analytics and financial summaries.",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="perm_edit_menu",
            field=models.BooleanField(
                default=False,
                help_text="Staff can create, edit and delete menu items.",
            ),
        ),
    ]
