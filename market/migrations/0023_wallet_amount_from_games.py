# Generated by Django 5.1.1 on 2024-09-30 15:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('market', '0022_transaction_image'),
    ]

    operations = [
        migrations.AddField(
            model_name='wallet',
            name='amount_from_games',
            field=models.FloatField(default=0.0),
        ),
    ]