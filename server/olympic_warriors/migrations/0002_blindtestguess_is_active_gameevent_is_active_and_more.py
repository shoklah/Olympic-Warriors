# Generated by Django 4.2.14 on 2024-08-01 15:31

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("olympic_warriors", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="blindtestguess",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="gameevent",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="teamresult",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
    ]