# Generated by Django 5.1.1 on 2024-09-28 19:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('market', '0015_alter_requested_withdraw_operator'),
    ]

    operations = [
        migrations.AlterField(
            model_name='game',
            name='created_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]