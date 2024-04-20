from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator

import pandas as pd


class Player(models.Model):
    """
    A player is a user that has a rating and is part of a team.
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)])
    team = models.ForeignKey("Team", on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)


class PlayerRating(models.Model):
    """
    A player rating on a specific area, with its name and identifier.
    """

    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    identifier = models.CharField(max_length=4)
    rating = models.FloatField(validators=[MinValueValidator(1), MaxValueValidator(10)])
    is_active = models.BooleanField(default=True)


class Edition(models.Model):
    """
    An edition is a year in which the Olympic Warriors take place..
    """

    year = models.IntegerField(validators=[MinValueValidator(2020), MaxValueValidator(2030)])
    host = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    registration_form = models.FileField(upload_to="registration_forms/", null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def create_players_from_registration_form(self):
        """
        Create players from the registration form of the edition.
        """
        header_mapping = {
            "Horodateur": "Timestamp",
            "Prénom et Nom": "Name",
            "A quelle fréquence pratiques-tu du sport ? ": "Sport Frequency",
            "Quels sont les sports que tu as pratiqué (dans toute ta vie et à tout niveau) ? En précisant sur chaque ligne le sport, le nombre d'années, le niveau et ta pratique actuelle (et toute information utile, comme le poste ou la spécialité). Exemple : "
            "Foot - 6 années - Amateur - Ne pratique plus - Défenseur gauche"
            "": "Sports Practiced",
            "Sur une échelle de 1 (le plus faible) à 10 (le plus élevé), comment estimes-tu le niveau que tu auras en septembre selon les critères suivants ? [Cohésion et esprit d'équipe]": "Cohesion and Team Spirit",
            "Sur une échelle de 1 (le plus faible) à 10 (le plus élevé), comment estimes-tu le niveau que tu auras en septembre selon les critères suivants ? [Observation et orientation]": "Observation and Orientation",
            "Sur une échelle de 1 (le plus faible) à 10 (le plus élevé), comment estimes-tu le niveau que tu auras en septembre selon les critères suivants ? [Souplesse et coordination]": "Mobility",
            "Sur une échelle de 1 (le plus faible) à 10 (le plus élevé), comment estimes-tu le niveau que tu auras en septembre selon les critères suivants ? [Précision et lancer]": "Accuracy and Aiming",
            "Sur une échelle de 1 (le plus faible) à 10 (le plus élevé), comment estimes-tu le niveau que tu auras en septembre selon les critères suivants ? [Course et vitesse]": "Running and Speed",
            "Sur une échelle de 1 (le plus faible) à 10 (le plus élevé), comment estimes-tu le niveau que tu auras en septembre selon les critères suivants ? [Endurance et cardio]": "Endurance and Cardio",
            "Sur une échelle de 1 (le plus faible) à 10 (le plus élevé), comment estimes-tu le niveau que tu auras en septembre selon les critères suivants ? [Culture]": "Cultural Knowledge",
            "Sur une échelle de 1 (le plus faible) à 10 (le plus élevé), comment estimes-tu le niveau que tu auras en septembre selon les critères suivants ? [Force]": "Strength",
            "Sur une échelle de 1 (le plus faible) à 10 (le plus élevé), comment estimes-tu le niveau que tu auras en septembre selon les critères suivants ? [Explosivité (effort puissant en un temps court)]": "Explosiveness",
            "Sur une échelle de 1 (le plus faible) à 10 (le plus élevé), comment estimes-tu le niveau que tu auras en septembre selon les critères suivants ? [Stratégie et vision de jeu]": "Strategy and Game Vision",
            "As-tu déjà participé aux Olympic Warriors ? Si oui, écris le classement final de ton équipe par ligne et par année. Exemple : "
            " - 2022, 2e "
            " - 2023, 3e": "Olympic Warriors Participation",
            "Sur une échelle de 1 à 10, comment estimes-tu ton niveau global pour les Olympic Warriors de 2024 (Cache-cache, Touch Rugby, Balle au camp, Course d'orientation, Blind Test, CrossFit) ?": "Global Level Estimation for Olympic Warriors 2024",
            "Avec qui souhaiterais-tu être ou ne pas être en équipe ? (Ces demandes resteront confidentielles. Par contre, on ne pourra pas toutes les prendre en compte mais on le fera le plus possible).": "Team Preferences",
            "J'ai payé mon inscription et je confirme que je serai là.": "Paid Registration Confirmation",
        }

        rating_columns = [
            "Cohesion and Team Spirit",
            "Observation and Orientation",
            "Mobility",
            "Accuracy and Aiming",
            "Running and Speed",
            "Endurance and Cardio",
            "Cultural Knowledge",
            "Strength",
            "Explosiveness",
            "Strategy and Game Vision",
        ]

        rating_identifiers = {
            "Cohesion and Team Spirit": "TEAM",
            "Observation and Orientation": "OBS",
            "Mobility": "MOB",
            "Accuracy and Aiming": "ACC",
            "Running and Speed": "SPD",
            "Endurance and Cardio": "STMN",
            "Cultural Knowledge": "CULT",
            "Strength": "STR",
            "Explosiveness": "EXPL",
            "Strategy and Game Vision": "STRAT",
        }

        df = pd.read_csv(
            "/Users/shoklah/Work/Playground/Olympic-Warriors/Inscription-aux-Olympic-Warriors-2024.csv"
        )
        df.rename(columns=header_mapping, inplace=True)

        df["Rating"] = df[rating_columns].mean(axis=1)
        df["Rating"] = df["Rating"].apply(lambda x: 1 if x < 1 else x)
        df["Rating"] = df["Rating"].apply(lambda x: 10 if x > 10 else x)

        # multiply rating by 2.5 if rating is below 4 and global level estimation is above 5
        df["Rating"] = df.apply(
            lambda x: (
                x["Rating"] * 2.5
                if x["Rating"] < 4 and x["Global Level Estimation for Olympic Warriors 2024"] > 5
                else x["Rating"]
            ),
            axis=1,
        )

        # average_rating = df.groupby("Name")["Rating"].mean()
        # print(average_rating)

        # calculate ajusted rating, including global level estimation
        df["Adjusted Rating"] = df.apply(
            lambda x: ((x["Rating"] + x["Global Level Estimation for Olympic Warriors 2024"]) / 2),
            axis=1,
        )
        df["Adjusted Rating"] = df["Adjusted Rating"].apply(lambda x: 1 if x < 1 else x)
        df["Adjusted Rating"] = df["Adjusted Rating"].apply(lambda x: 10 if x > 10 else x)
        df["Adjusted Rating"] = df["Adjusted Rating"].astype(int)

        ## Create players from the registration form
        for index, row in df.iterrows():
            player = Player.objects.create(
                user=User.objects.create_user(
                    username=row["Name"].replace(" ", "").lower(),
                    password="password",
                    email=f"{row['Name'].replace(' ', '').lower()}@olympicwarriors.com",
                ),
                rating=row["Adjusted Rating"],
                team=None,
            )

            for column in rating_columns:
                PlayerRating.objects.create(
                    player=player,
                    name=column,
                    identifier=rating_identifiers[column],
                    rating=row[column],
                )

    def save(self, *args, **kwargs):
        # Check if the object is already in the database
        if self.pk is not None:
            # Get the original object from the database
            original_obj = Edition.objects.get(pk=self.pk)
            # Compare registration from to see if it has been updated
            if getattr(self, "registration_form") != getattr(original_obj, "registration_form"):
                print(f"registration_form has been updated.")
        elif self.registration_form:
            print(f"New edition has been created with a registration form.")

        # Call the original save method to save the object
        super().save(*args, **kwargs)


class Team(models.Model):
    """
    A team is a group of players that participate in an edition of the Olympic Warriors.
    """

    captain = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="captain")
    name = models.CharField(max_length=100)
    edition = models.ForeignKey(Edition, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)


class Registration(models.Model):
    """
    A registration is a link between a Player and an Edition. It is used to keep track of
    the teams that participate in an edition.
    """

    player = models.ForeignKey(Player, on_delete=models.CASCADE)1
    edition = models.ForeignKey(Edition, on_delete=models.CASCADE)
    confirmed = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)


class Game(models.Model):
    """
    A game is a competition between two teams that takes place in an edition of the Olympic Warriors.
    """

    team1 = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="team1")
    team2 = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="team2")
    referees = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="referees")
    edition = models.ForeignKey(Edition, on_delete=models.CASCADE)
    date = models.DateField()
    is_active = models.BooleanField(default=True)


class Event(models.Model):
    """
    An event is a competition that takes place in an edition of the Olympic Warriors.
    """

    name = models.CharField(max_length=100)
    edition = models.ForeignKey(Edition, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)


class Rugby(Event):
    """
    Rugby is a type of event that takes place in an edition of the Olympic Warriors.
    """

    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    score = models.IntegerField(validators=[MinValueValidator(0)])
