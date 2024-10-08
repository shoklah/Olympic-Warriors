# Generated by Django 4.2.14 on 2024-08-29 21:48

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("olympic_warriors", "0014_alter_dodgeballevent_event_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="dodgeballevent",
            name="event_type",
            field=models.CharField(
                choices=[
                    ("STA", "Start"),
                    ("END", "End"),
                    ("HIT", "Hit"),
                    ("CAT", "Catch"),
                    ("FOL", "Foul"),
                    ("OUT", "Out"),
                    ("NEW", "New Round"),
                ],
                max_length=3,
            ),
        ),
    ]
