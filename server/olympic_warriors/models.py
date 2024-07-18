from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.crypto import get_random_string

import pandas as pd


class Player(models.Model):
    """
    A player is a user that has a rating and is part of a team.
    """

    def __str__(self):
        return self.user.username

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)])
    team = models.ForeignKey("Team", on_delete=models.CASCADE, null=True, blank=True)
    edition = models.ForeignKey("Edition", on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)


class PlayerRating(models.Model):
    """
    A player rating on a specific area, with its name and identifier.
    """

    def __str__(self):
        return f"{self.player.user.username} - {self.name}"

    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    identifier = models.CharField(max_length=5)
    rating = models.FloatField(validators=[MinValueValidator(1), MaxValueValidator(10)])
    is_active = models.BooleanField(default=True)


class Edition(models.Model):
    """
    An edition is a year in which the Olympic Warriors take place.
    """

    def __str__(self):
        return str(self.year)

    year = models.IntegerField(validators=[MinValueValidator(2020), MaxValueValidator(2030)])
    host = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    registration_form = models.FileField(upload_to="registration_forms/", null=True, blank=True)
    is_active = models.BooleanField(default=True)

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

    ratings = {
        "Cohesion and Team Spirit": {"id": "TEAM", "coef": 2},
        "Observation and Orientation": {"id": "OBS", "coef": 1},
        "Mobility": {"id": "MOB", "coef": 3},
        "Accuracy and Aiming": {"id": "ACC", "coef": 2},
        "Running and Speed": {"id": "SPD", "coef": 4},
        "Endurance and Cardio": {"id": "STMN", "coef": 4},
        "Cultural Knowledge": {"id": "CULT", "coef": 1},
        "Strength": {"id": "STR", "coef": 3},
        "Explosiveness": {"id": "EXPL", "coef": 4},
        "Strategy and Game Vision": {"id": "STRAT", "coef": 2},
    }

    def process_weighted_rating(self, df):
        """
        Process weighted average rating for each player.

        :param df: The DataFrame with the player data.
        :return: The DataFrame with the weighted rating.
        """
        df["Weighted_Rating"] = df.apply(
            lambda x: sum([x[rating] * self.ratings[rating]["coef"] for rating in self.ratings])
            / sum([self.ratings[rating]["coef"] for rating in self.ratings]),
            axis=1,
        )

        df["Weighted_Rating"] = df["Weighted_Rating"].apply(lambda x: 1 if x < 1 else x)
        df["Weighted_Rating"] = df["Weighted_Rating"].apply(lambda x: 10 if x > 10 else x)

        # multiply rating by 2.5 if rating is below 4 and global level estimation is above 5
        df["Weighted_Rating"] = df.apply(
            lambda x: (
                x["Weighted_Rating"] * 2.5
                if x["Weighted_Rating"] < 4
                and x["Global Level Estimation for Olympic Warriors 2024"] > 4
                else x["Weighted_Rating"]
            ),
            axis=1,
        )

        return df

    def process_global_rating(self, df):
        """
        Process global level estimation for each player from weighted rating and global level estimation.

        :param df: The DataFrame with the player data.
        :return: The DataFrame with the global rating.
        """
        df["Global_Rating"] = df.apply(
            lambda x: (
                (x["Weighted_Rating"] + x["Global Level Estimation for Olympic Warriors 2024"] * 4)
                / 5
            ),
            axis=1,
        )
        df["Global_Rating"] = df["Global_Rating"].apply(lambda x: 1 if x < 1 else x)
        df["Global_Rating"] = df["Global_Rating"].apply(lambda x: 10 if x > 10 else x)
        df["Global_Rating"] = df["Global_Rating"].round(2)

        return df

    def create_players_from_registration_form(self, registration_form):
        """
        Create players from the registration form of the edition.

        :param registration_form: The registration form of the edition.
        """

        df = pd.read_csv(registration_form)
        df.rename(columns=self.header_mapping, inplace=True)

        df = self.process_weighted_rating(df)
        df = self.process_global_rating(df)

        ## Create players from the registration form
        for _, row in df.iterrows():
            try:
                user = User.objects.get(username=row["Name"].replace(" ", "").lower())
            except User.DoesNotExist:
                user = User.objects.create_user(
                    username=row["Name"].replace(" ", "").lower(),
                    password=get_random_string(length=8),
                    email=f"{row['Name'].replace(' ', '').lower()}@olympicwarriors.com",
                )

            try:
                player = Player.objects.get(user=user, edition=self)
            except Player.DoesNotExist:
                player = Player.objects.create(
                    user=user,
                    rating=row["Global_Rating"],
                    edition=self,
                )

            for rating in self.ratings:
                PlayerRating.objects.create(
                    player=player,
                    name=rating,
                    identifier=self.ratings[rating]["id"],
                    rating=row[rating],
                )

    def save(self, *args, **kwargs):
        """
        Override the save method to create players from the registration form of the edition.
        """
        # Check if the object is already in the database
        if self.pk is not None:
            # Get the original object from the database
            original_obj = Edition.objects.get(pk=self.pk)
            # Compare registration from to see if it has been updated
            new_registration_form = getattr(self, "registration_form")
            if new_registration_form != getattr(original_obj, "registration_form"):
                super().save(*args, **kwargs)
                self.create_players_from_registration_form(new_registration_form)
        elif self.registration_form:
            super().save(*args, **kwargs)
            self.create_players_from_registration_form(self.registration_form)

        # Call the original save method to save the object
        super().save(*args, **kwargs)


class Team(models.Model):
    """
    A team is a group of players that participate in an edition of the Olympic Warriors.
    """

    def __str__(self):
        return self.name

    name = models.CharField(max_length=100)
    edition = models.ForeignKey(Edition, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)


class Registration(models.Model):
    """
    A registration is a link between a Player and an Edition. It is used to keep track of
    the teams that participate in an edition.
    """

    def __str__(self):
        return f"{self.player.user.username} - {self.edition.year}"

    player = models.ForeignKey(Player, on_delete=models.CASCADE)
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
