"""Tests for the pure registration-form parsing functions (no database)."""
import pandas as pd
from django.test import SimpleTestCase

from olympic_warriors.registration import (
    CONFIRMED,
    EMAIL,
    FREQUENCY,
    FORM_PROFILES,
    GLOBAL_LEVEL,
    NAME,
    RATINGS,
    SPORTS,
    WISHES,
    clean_text,
    compute_ratings,
    parse_confirmation,
    parse_frequency,
    parse_name,
    rate,
    resolve_columns,
    resolve_extras,
)

SKILL_SENTENCE = (
    "Sur une échelle de 1 (le plus faible) à 10 (le plus élevé), comment estimes-tu "
    "le niveau que tu auras en août selon les critères suivants ? [{}]"
)
GLOBAL_2026 = (
    "Sur une échelle de 1 à 10, comment estimes-tu ton niveau global pour les Olympic "
    "Warriors de 2026 : Flag Rugby, Cache-cache, CrossFit, Relais, Maître des Fleurs, Fléchettes."
)
GLOBAL_2025 = (
    "Sur une échelle de 1 à 10, comment estimes-tu ton niveau global pour les Olympic "
    "Warriors de 2025 : Pétanque, Basket, Sprint/Relais, Parcours du Combattant, "
    "Kermesse (chamboule-tout, etc) et Géographie ?"
)
CRITERIA = [spec["criterion"] for spec in RATINGS.values()]


def make_df(global_header=GLOBAL_2026, with_email=True, rows=None, drop_criterion=None):
    """Build a DataFrame shaped like a Google Forms export for the given year."""
    headers = ["Horodateur"]
    if with_email:
        headers.append("Adresse e-mail")
    headers += ["Prénom et Nom", "A quelle fréquence pratiques-tu du sport ? "]
    headers += [SKILL_SENTENCE.format(c) for c in CRITERIA if c != drop_criterion]
    headers += [global_header, "Je confirme que je serai là ! 💪"]
    return pd.DataFrame(rows or [], columns=headers)


class ResolveColumnsTests(SimpleTestCase):
    def test_resolves_all_2026_columns(self):
        columns, ratings = resolve_columns(make_df())

        self.assertIs(ratings, FORM_PROFILES["2025"])
        self.assertEqual(columns[NAME], "Prénom et Nom")
        self.assertEqual(columns[EMAIL], "Adresse e-mail")
        self.assertEqual(columns[GLOBAL_LEVEL], GLOBAL_2026)
        for name, spec in RATINGS.items():
            self.assertEqual(columns[name], SKILL_SENTENCE.format(spec["criterion"]))
        self.assertEqual(len(columns), len(RATINGS) + 3)  # name, email, global level

    def test_resolves_2025_columns_without_email(self):
        columns, ratings = resolve_columns(make_df(global_header=GLOBAL_2025, with_email=False))

        self.assertIs(ratings, FORM_PROFILES["2025"])
        self.assertNotIn(EMAIL, columns)
        self.assertEqual(columns[GLOBAL_LEVEL], GLOBAL_2025)
        self.assertEqual(len(columns), len(RATINGS) + 2)  # name, global level

    def test_missing_skill_column_raises_with_criterion(self):
        df = make_df(drop_criterion="Cardio")

        with self.assertRaises(ValueError) as ctx:
            resolve_columns(df)
        self.assertIn("Cardio", str(ctx.exception))

    def test_missing_global_level_raises(self):
        df = make_df(global_header="Une question sans rapport")

        with self.assertRaises(ValueError) as ctx:
            resolve_columns(df)
        self.assertIn("niveau global", str(ctx.exception))

    def test_duplicate_skill_column_raises(self):
        df = make_df()
        df["Encore une question ? [Cardio]"] = None

        with self.assertRaises(ValueError) as ctx:
            resolve_columns(df)
        self.assertIn("Ambiguous", str(ctx.exception))

    def test_literal_2026_headers_are_not_reported_missing(self):
        # Copied verbatim from the Google Forms export; deliberately not built from RATINGS.
        literal = pd.DataFrame(
            columns=[
                "Prénom et Nom",
                "Sur une échelle de 1 (le plus faible) à 10 (le plus élevé), comment "
                "estimes-tu le niveau que tu auras en août selon les critères suivants ? "
                "[Cohésion et esprit d'équipe]",
                "Sur une échelle de 1 (le plus faible) à 10 (le plus élevé), comment "
                "estimes-tu le niveau que tu auras en août selon les critères suivants ? "
                "[Force (soulever, pousser, etc)]",
                "Sur une échelle de 1 (le plus faible) à 10 (le plus élevé), comment "
                "estimes-tu le niveau que tu auras en août selon les critères suivants ? "
                "[Explosivité (effort puissant en un temps court)]",
                " Sur une échelle de 1 à 10, comment estimes-tu ton niveau global pour les "
                "Olympic Warriors de 2026 : Flag Rugby, Cache-cache, CrossFit, Relais, "
                "Maître des Fleurs, Fléchettes.",
            ]
        )

        with self.assertRaises(ValueError) as ctx:
            resolve_columns(literal)

        # Only the seven skills absent from this frame may be reported missing.
        message = str(ctx.exception)
        for present in ("Cohésion", "Force (soulever", "Explosivité", "niveau global"):
            self.assertNotIn(present, message)
        self.assertIn("[Cardio]", message)


class ParseNameTests(SimpleTestCase):
    def test_two_tokens(self):
        self.assertEqual(parse_name("Alice Martin"), ("Alice", "Martin", "alicemartin"))

    def test_trailing_space_and_accent_keep_legacy_username(self):
        self.assertEqual(parse_name("Camille Béziau "), ("Camille", "Béziau", "camillebéziau"))

    def test_first_name_only(self):
        self.assertEqual(parse_name("Adrien "), ("Adrien", "", "adrien"))

    def test_three_tokens_join_last_name(self):
        self.assertEqual(
            parse_name("Cédric DE LA MOTTE "), ("Cédric", "DE LA MOTTE", "cédricdelamotte")
        )

    def test_empty_or_nan_raises(self):
        with self.assertRaises(ValueError):
            parse_name("   ")
        with self.assertRaises(ValueError):
            parse_name(float("nan"))

    def test_username_matches_legacy_scheme(self):
        # Earlier editions created usernames with name.replace(" ", "").lower();
        # returning players must keep matching their account.
        for raw in ["Camille Béziau ", "Cédric DE LA MOTTE ", "Adrien ", "Léa DURAND"]:
            self.assertEqual(parse_name(raw)[2], raw.replace(" ", "").lower())

    def test_internal_double_space_is_collapsed(self):
        self.assertEqual(parse_name("Jean  Dupont"), ("Jean", "Dupont", "jeandupont"))


def make_row(name, skill, global_level, email="x@example.com"):
    """One form response where every skill has the same value."""
    return ["1/1/2026 10:00:00", email, name, "Souvent"] + [skill] * len(CRITERIA) + [
        global_level, "Oui"
    ]


class ComputeRatingsTests(SimpleTestCase):
    def compute(self, rows):
        df = make_df(rows=rows)
        columns, ratings = resolve_columns(df)
        return compute_ratings(df, columns, ratings)

    def test_global_rating_blends_weighted_and_global_estimate(self):
        out = self.compute([make_row("Alice Martin", 6, 8)])

        self.assertEqual(out.loc[0, "Weighted_Rating"], 6)
        self.assertEqual(out.loc[0, "Global_Rating"], 7.6)

    def test_low_weighted_with_high_global_is_boosted(self):
        out = self.compute([make_row("Bob", 2, 6)])

        self.assertEqual(out.loc[0, "Weighted_Rating"], 5.0)
        self.assertEqual(out.loc[0, "Global_Rating"], 5.8)

    def test_low_weighted_with_low_global_is_not_boosted(self):
        out = self.compute([make_row("Bob", 2, 3)])

        self.assertEqual(out.loc[0, "Weighted_Rating"], 2)
        self.assertEqual(out.loc[0, "Global_Rating"], 2.8)

    def test_columns_are_renamed_to_internal_names(self):
        out = self.compute([make_row("Alice Martin", 6, 8)])

        self.assertEqual(out.loc[0, NAME], "Alice Martin")
        self.assertEqual(out.loc[0, EMAIL], "x@example.com")
        self.assertEqual(out.loc[0, GLOBAL_LEVEL], 8)
        self.assertEqual(out.loc[0, "Cardio"], 6)

    def test_non_numeric_rating_raises_with_name(self):
        row = make_row("Alice Martin", 6, 8)
        row[4] = "beaucoup"

        with self.assertRaises(ValueError) as ctx:
            self.compute([row])
        self.assertIn("Alice Martin", str(ctx.exception))

    def test_out_of_range_rating_raises_with_name(self):
        with self.assertRaises(ValueError) as ctx:
            self.compute([make_row("Alice Martin", 11, 8)])
        self.assertIn("Alice Martin", str(ctx.exception))

    def test_all_invalid_cells_are_reported_together(self):
        alice = make_row("Alice Martin", 6, 8)
        alice[4] = "beaucoup"
        bob = make_row("Bob", 6, 12)

        with self.assertRaises(ValueError) as ctx:
            self.compute([alice, bob])
        message = str(ctx.exception)
        self.assertIn("Alice Martin", message)
        self.assertIn("Bob", message)

    def test_invalid_cell_with_blank_name_is_reported_by_row(self):
        row = make_row(float("nan"), 6, 12)

        with self.assertRaises(ValueError) as ctx:
            self.compute([row])
        self.assertIn("row 2", str(ctx.exception))

    def test_weighted_exactly_four_is_not_boosted(self):
        out = self.compute([make_row("X", 4, 8)])

        self.assertEqual(out.loc[0, "Weighted_Rating"], 4.0)

    def test_global_exactly_four_does_not_boost(self):
        out = self.compute([make_row("X", 3, 4)])

        self.assertEqual(out.loc[0, "Weighted_Rating"], 3.0)


# The 2024 form: "septembre" wording, an "Observation et orientation" skill, a single
# "Endurance et cardio" skill, and short "Culture" / "Force" labels.
SKILL_SENTENCE_2024 = (
    "Sur une échelle de 1 (le plus faible) à 10 (le plus élevé), comment estimes-tu "
    "le niveau que tu auras en septembre selon les critères suivants ? [{}]"
)
GLOBAL_2024 = (
    "Sur une échelle de 1 à 10, comment estimes-tu ton niveau global pour les Olympic "
    "Warriors de 2024 (Cache-cache, Touch Rugby, Balle au camp, Course d'orientation, "
    "Blind Test, CrossFit) ?"
)
CRITERIA_2024 = [spec["criterion"] for spec in FORM_PROFILES["2024"].values()]


def make_df_2024(rows=None, drop_criterion=None):
    headers = ["Horodateur", "Adresse e-mail", "Prénom et Nom", "A quelle fréquence pratiques-tu du sport ? "]
    headers += [SKILL_SENTENCE_2024.format(c) for c in CRITERIA_2024 if c != drop_criterion]
    headers += [GLOBAL_2024, "J'ai payé mon inscription et je confirme que je serai là."]
    return pd.DataFrame(rows or [], columns=headers)


def make_row_2024(name, skills, global_level, email=""):
    """One 2024 response; skills is the list of ten values in form order."""
    return ["1/4/2024 10:00:00", email, name, "Souvent"] + list(skills) + [global_level, "Oui"]


class ResolveColumns2024Tests(SimpleTestCase):
    def test_resolves_2024_columns_with_the_2024_profile(self):
        columns, ratings = resolve_columns(make_df_2024())

        self.assertIs(ratings, FORM_PROFILES["2024"])
        self.assertEqual(columns[GLOBAL_LEVEL], GLOBAL_2024)
        self.assertIn("Observation and Orientation", columns)
        self.assertIn("Endurance and Cardio", columns)
        self.assertNotIn("Cardio", columns)
        for name, spec in ratings.items():
            self.assertEqual(columns[name], SKILL_SENTENCE_2024.format(spec["criterion"]))
        self.assertEqual(len(columns), len(ratings) + 3)  # name, email, global level

    def test_2024_profile_has_the_historical_identifiers(self):
        ids = sorted(spec["id"] for spec in FORM_PROFILES["2024"].values())

        self.assertEqual(
            ids, ["ACC", "CULT", "EXPL", "MOB", "OBS", "SPD", "STMN", "STR", "STRT", "TEAM"]
        )
        self.assertEqual(sum(spec["coef"] for spec in FORM_PROFILES["2024"].values()), 26)

    def test_missing_column_is_reported_against_the_closest_profile(self):
        df = make_df_2024(drop_criterion="Culture")

        with self.assertRaises(ValueError) as ctx:
            resolve_columns(df)
        message = str(ctx.exception)
        self.assertIn("2024", message)
        self.assertIn("[Culture]", message)
        self.assertNotIn("[Cardio]", message)

    def test_literal_2024_headers_resolve(self):
        # Copied verbatim from the 2024 Google Forms export.
        literal = pd.DataFrame(
            columns=["Horodateur", "Adresse e-mail", "Prénom et Nom"]
            + [SKILL_SENTENCE_2024.format(c) for c in (
                "Cohésion et esprit d'équipe", "Observation et orientation",
                "Souplesse et coordination", "Précision et lancer", "Course et vitesse",
                "Endurance et cardio", "Culture", "Force",
                "Explosivité (effort puissant en un temps court)", "Stratégie et vision de jeu",
            )]
            + [GLOBAL_2024]
        )

        columns, ratings = resolve_columns(literal)

        self.assertIs(ratings, FORM_PROFILES["2024"])


class ComputeRatings2024Tests(SimpleTestCase):
    def compute(self, rows):
        df = make_df_2024(rows=rows)
        columns, ratings = resolve_columns(df)
        return compute_ratings(df, columns, ratings)

    def test_uses_the_2024_coefficients(self):
        # Observation (coef 1) at 10, the other nine skills at 5: (5 * 25 + 10) / 26.
        out = self.compute([make_row_2024("Alice Martin", [5, 10, 5, 5, 5, 5, 5, 5, 5, 5], 7)])

        self.assertAlmostEqual(out.loc[0, "Weighted_Rating"], 135 / 26)
        self.assertEqual(out.loc[0, "Global_Rating"], 6.64)
        self.assertEqual(out.loc[0, "Observation and Orientation"], 10)

    def test_same_formula_as_later_forms(self):
        out = self.compute([make_row_2024("Alice Martin", [6] * 10, 8)])

        self.assertEqual(out.loc[0, "Weighted_Rating"], 6)
        self.assertEqual(out.loc[0, "Global_Rating"], 7.6)


class RateTests(SimpleTestCase):
    WEIGHTS = {"a": 1, "b": 3}

    def test_weights_the_skills_then_blends_the_global_level(self):
        weighted, global_rating = rate({"a": 10, "b": 2}, self.WEIGHTS, 5)

        self.assertEqual(weighted, 4.0)  # (10 + 2 * 3) / 4
        self.assertEqual(global_rating, 4.8)  # (4 + 5 * 4) / 5

    def test_a_weak_weighted_rating_with_a_confident_global_level_is_boosted(self):
        weighted, global_rating = rate({"a": 2, "b": 2}, self.WEIGHTS, 6)

        self.assertEqual(weighted, 5.0)  # 2 * 2.5
        self.assertEqual(global_rating, 5.8)

    def test_no_boost_when_the_global_level_is_low(self):
        weighted, global_rating = rate({"a": 2, "b": 2}, self.WEIGHTS, 3)

        self.assertEqual(weighted, 2)
        self.assertEqual(global_rating, 2.8)

    def test_the_boundaries_do_not_boost(self):
        self.assertEqual(rate({"a": 4, "b": 4}, self.WEIGHTS, 8)[0], 4)  # weighted exactly 4
        self.assertEqual(rate({"a": 3, "b": 3}, self.WEIGHTS, 4)[0], 3)  # global exactly 4

    def test_the_rating_stays_on_the_scale(self):
        self.assertEqual(rate({"a": 1, "b": 1}, self.WEIGHTS, 1), (1, 1.0))
        self.assertEqual(rate({"a": 10, "b": 10}, self.WEIGHTS, 10), (10, 10.0))

    def test_skills_outside_the_weights_are_ignored(self):
        self.assertEqual(rate({"a": 6, "b": 6, "zzz": 1}, self.WEIGHTS, 8), (6, 7.6))


class ExtrasTests(SimpleTestCase):
    def test_finds_the_optional_columns_that_are_present(self):
        extras = resolve_extras(make_df())  # frequency and confirmation, no sports or wishes

        self.assertEqual(
            extras,
            {
                FREQUENCY: "A quelle fréquence pratiques-tu du sport ? ",
                CONFIRMED: "Je confirme que je serai là ! 💪",
            },
        )

    def test_finds_all_four_in_the_2026_wording(self):
        df = pd.DataFrame(
            columns=[
                "A quelle fréquence pratiques-tu du sport ? ",
                "Quels sont les sports que tu as pratiqué (dans toute ta vie et à tout niveau) ?",
                "Idéalement, avec qui souhaiterais-tu être ou ne pas être en équipe ? \n(Ces demandes)",
                "Je confirme que je serai là ! 💪",
            ]
        )

        self.assertEqual(set(resolve_extras(df)), {FREQUENCY, SPORTS, WISHES, CONFIRMED})

    def test_the_2024_wording(self):
        df = pd.DataFrame(
            columns=[
                "Avec qui souhaiterais-tu être ou ne pas être en équipe ? (confidentiel)",
                "J'ai payé mon inscription et je confirme que je serai là.",
            ]
        )

        self.assertEqual(set(resolve_extras(df)), {WISHES, CONFIRMED})

    def test_nothing_is_required(self):
        self.assertEqual(resolve_extras(pd.DataFrame(columns=["Prénom et Nom"])), {})

    def test_parse_frequency_maps_the_five_answers(self):
        answers = {
            "Moins d'une fois par mois": "rare",
            "Moins d'une fois par semaine mais plusieurs fois par mois": "monthly",
            "Environ une heure par semaine": "hour",
            "Au moins deux heures par semaine": "two_hours",
            "Au moins quatre heures par semaine": "four_hours",
        }
        for text, code in answers.items():
            self.assertEqual(parse_frequency(text), code)

    def test_parse_frequency_tolerates_spacing_case_and_curly_apostrophes(self):
        self.assertEqual(parse_frequency("  moins d’une fois par MOIS "), "rare")

    def test_parse_frequency_leaves_the_unknown_blank(self):
        self.assertEqual(parse_frequency("Souvent"), "")
        self.assertEqual(parse_frequency(float("nan")), "")

    def test_the_frequency_codes_are_the_models(self):
        from olympic_warriors.models.Player import SportFrequency  # imports Django models

        codes = {parse_frequency(t) for t in (
            "Moins d'une fois par mois", "Environ une heure par semaine",
            "Au moins deux heures par semaine", "Au moins quatre heures par semaine",
            "Moins d'une fois par semaine mais plusieurs fois par mois",
        )}
        self.assertEqual(codes, set(SportFrequency.values))

    def test_parse_confirmation(self):
        self.assertTrue(parse_confirmation("Oui"))
        self.assertTrue(parse_confirmation(" oui "))
        self.assertFalse(parse_confirmation("Non"))
        self.assertFalse(parse_confirmation(float("nan")))

    def test_clean_text(self):
        self.assertEqual(clean_text("  Avec Bob \n"), "Avec Bob")
        self.assertEqual(clean_text(float("nan")), "")
