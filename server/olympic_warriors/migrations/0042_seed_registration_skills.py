from django.db import migrations

# (identifier, French label, English name, weight), in form order. Literals on purpose:
# a migration must not change when registration.py later does (a test keeps them equal to
# FORM_PROFILES). The English name is what PlayerRating.name stores.
SKILLS_2025 = [
    ("TEAM", "Cohésion et esprit d'équipe", "Cohesion and Team Spirit", 2),
    ("MOB", "Souplesse et coordination", "Mobility", 3),
    ("ACC", "Précision et lancer", "Accuracy and Aiming", 2),
    ("SPD", "Course et vitesse", "Running and Speed", 4),
    ("STMN", "Endurance longue durée", "Endurance", 4),
    ("CARD", "Cardio", "Cardio", 4),
    ("CULT", "Culture générale", "Cultural Knowledge", 1),
    ("STR", "Force (soulever, pousser, etc)", "Strength", 3),
    ("EXPL", "Explosivité (effort puissant en un temps court)", "Explosiveness", 4),
    ("STRT", "Stratégie et vision de jeu", "Strategy and Game Vision", 2),
]

SKILLS_2024 = [
    ("TEAM", "Cohésion et esprit d'équipe", "Cohesion and Team Spirit", 2),
    ("OBS", "Observation et orientation", "Observation and Orientation", 1),
    ("MOB", "Souplesse et coordination", "Mobility", 3),
    ("ACC", "Précision et lancer", "Accuracy and Aiming", 2),
    ("SPD", "Course et vitesse", "Running and Speed", 4),
    ("STMN", "Endurance et cardio", "Endurance and Cardio", 4),
    ("CULT", "Culture", "Cultural Knowledge", 1),
    ("STR", "Force", "Strength", 3),
    ("EXPL", "Explosivité (effort puissant en un temps court)", "Explosiveness", 4),
    ("STRT", "Stratégie et vision de jeu", "Strategy and Game Vision", 2),
]


def seed(apps, schema_editor):
    """2024 gets its own skill set, every later edition the 2025 one, earlier ones nothing;
    an edition that already has a questionnaire is left alone."""
    Edition = apps.get_model("olympic_warriors", "Edition")
    RegistrationSkill = apps.get_model("olympic_warriors", "RegistrationSkill")
    for edition in Edition.objects.filter(year__gte=2024):
        if RegistrationSkill.objects.filter(edition=edition).exists():
            continue
        skills = SKILLS_2024 if edition.year == 2024 else SKILLS_2025
        RegistrationSkill.objects.bulk_create(
            RegistrationSkill(
                edition=edition,
                identifier=identifier,
                name_fr=name_fr,
                name_en=name_en,
                weight=weight,
                order=order,
            )
            for order, (identifier, name_fr, name_en, weight) in enumerate(skills)
        )


class Migration(migrations.Migration):

    dependencies = [
        ("olympic_warriors", "0041_registration_foundations"),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
