# Generated by Django 5.1.1 on 2024-09-15 12:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_remove_customer_referred_users_customer_referred_by'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='referal_code',
            field=models.CharField(blank=True, max_length=10, null=True),
        ),
    ]
