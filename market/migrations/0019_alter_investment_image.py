# Generated by Django 5.1.1 on 2024-09-29 15:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('market', '0018_game_today'),
    ]

    operations = [
        migrations.AlterField(
            model_name='investment',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to='investment/'),
        ),
    ]
