# Generated by Django 5.1.1 on 2024-09-18 13:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('market', '0007_wallet_active_wallet_eligible'),
    ]

    operations = [
        migrations.AddField(
            model_name='wallet',
            name='date_made_eligible',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]