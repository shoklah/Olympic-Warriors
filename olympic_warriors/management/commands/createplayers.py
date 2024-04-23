from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
import pandas as pd

from olympic_warriors.settings import settings


class Command(BaseCommand):
    help = "Create players from registration form results."
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

    def process_weighted_rating(self, df, ratings):
        df["Rating_Weighted"] = df.apply(
            lambda x: sum([x[rating] * ratings[rating]["coef"] for rating in ratings])
            / sum([ratings[rating]["coef"] for rating in ratings]),
            axis=1,
        )
        df["Rating_Weighted"] = df["Rating_Weighted"].apply(lambda x: 1 if x < 1 else x)
        df["Rating_Weighted"] = df["Rating_Weighted"].apply(lambda x: 10 if x > 10 else x)
        return df

    def handle(self, *args, **options):
        df = pd.read_csv(
            "/Users/shoklah/Work/Playground/Olympic-Warriors/Inscription-aux-Olympic-Warriors-2024.csv"
        )
        df.rename(columns=self.header_mapping, inplace=True)

        # process weighted average rating for each player
        df["Rating_Weighted"] = df.apply(
            lambda x: sum([x[rating] * self.ratings[rating]["coef"] for rating in self.ratings])
            / sum([self.ratings[rating]["coef"] for rating in self.ratings]),
            axis=1,
        )
        df["Rating_Weighted"] = df["Rating_Weighted"].apply(lambda x: 1 if x < 1 else x)
        df["Rating_Weighted"] = df["Rating_Weighted"].apply(lambda x: 10 if x > 10 else x)

        # multiply rating by 2.5 if rating is below 4 and global level estimation is above 5
        df["Rating_Weighted"] = df.apply(
            lambda x: (
                x["Rating_Weighted"] * 2.5
                if x["Rating_Weighted"] < 4
                and x["Global Level Estimation for Olympic Warriors 2024"] > 4
                else x["Rating_Weighted"]
            ),
            axis=1,
        )

        weighted_ratings = df.groupby("Name")["Rating_Weighted"].mean()
        # print(weighted_ratings)

        # calculate ajusted rating, including global level estimation
        df["Adjusted Weighted Rating"] = df.apply(
            lambda x: (
                (x["Rating_Weighted"] + x["Global Level Estimation for Olympic Warriors 2024"] * 4)
                / 5
            ),
            axis=1,
        )
        df["Adjusted Weighted Rating"] = df["Adjusted Weighted Rating"].apply(
            lambda x: 1 if x < 1 else x
        )
        df["Adjusted Weighted Rating"] = df["Adjusted Weighted Rating"].apply(
            lambda x: 10 if x > 10 else x
        )
        # df["Adjusted Rating"] = df["Adjusted Rating"].astype(int)
        adjusted_average_rating = df.groupby("Name")["Adjusted Weighted Rating"].mean()
        print(adjusted_average_rating)

        # df["Rating"] = df[self.ratings].mean(axis=1)
        # df["Rating"] = df["Rating"].apply(lambda x: 1 if x < 1 else x)
        # df["Rating"] = df["Rating"].apply(lambda x: 10 if x > 10 else x)

        # # multiply rating by 2.5 if rating is below 4 and global level estimation is above 5
        # df["Rating"] = df.apply(
        #     lambda x: (
        #         x["Rating"] * 2.5
        #         if x["Rating"] < 4 and x["Global Level Estimation for Olympic Warriors 2024"] > 5
        #         else x["Rating"]
        #     ),
        #     axis=1,
        # )

        # average_rating = df.groupby("Name")["Rating"].mean()
        # # print(average_rating)

        # # calculate ajusted rating, including global level estimation
        # df["Adjusted Rating"] = df.apply(
        #     lambda x: (
        #         (x["Rating"] + x["Global Level Estimation for Olympic Warriors 2024"] * 4) / 5
        #     ),
        #     axis=1,
        # )
        # df["Adjusted Rating"] = df["Adjusted Rating"].apply(lambda x: 1 if x < 1 else x)
        # df["Adjusted Rating"] = df["Adjusted Rating"].apply(lambda x: 10 if x > 10 else x)
        # # df["Adjusted Rating"] = df["Adjusted Rating"].astype(int)
        # adjusted_average_rating = df.groupby("Name")["Adjusted Rating"].mean()
        # print(adjusted_average_rating)

        # print all ratings
        ratings = df.groupby("Name")[
            list(self.ratings.keys()) + ["Global Level Estimation for Olympic Warriors 2024"]
        ].mean()
        print(ratings)
