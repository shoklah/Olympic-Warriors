from django.db import migrations, models


def mark_existing_games_played(apps, schema_editor):
    """Every edition in the database is over: games that exist were played."""
    Game = apps.get_model("olympic_warriors", "Game")
    Game.objects.update(is_played=True)


class Migration(migrations.Migration):

    dependencies = [
        ('olympic_warriors', '0027_edition_photos_url_unique_year'),
    ]

    operations = [
        migrations.AddField(
            model_name='game',
            name='is_played',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(mark_existing_games_played, migrations.RunPython.noop),
    ]
