# Generated by Django 4.2.15 on 2024-08-22 20:25

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("olympic_warriors", "0010_blindtestguess_blindtest"),
    ]

    operations = [
        migrations.AddField(
            model_name="discipline",
            name="reveal_score",
            field=models.BooleanField(default=False),
        ),
    ]