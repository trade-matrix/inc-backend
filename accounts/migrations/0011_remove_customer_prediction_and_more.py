# Generated by Django 5.1.1 on 2024-09-28 15:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0010_customer_prediction_customer_prediction_correct_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='customer',
            name='prediction',
        ),
        migrations.RemoveField(
            model_name='customer',
            name='prediction_correct',
        ),
        migrations.RemoveField(
            model_name='customer',
            name='prediction_date',
        ),
        migrations.AddField(
            model_name='customer',
            name='withdrawal_reference',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]