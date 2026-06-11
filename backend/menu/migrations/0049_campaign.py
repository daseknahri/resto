from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('menu', '0048_orderpayment'),
    ]

    operations = [
        migrations.CreateModel(
            name='Campaign',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=80)),
                ('message', models.CharField(max_length=200)),
                ('created_by_user_id', models.IntegerField(null=True)),
                ('audience_count', models.IntegerField(default=0)),
                ('sent_count', models.IntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ('-created_at',),
            },
        ),
    ]
