"""Tests for the pure registration-form parsing functions (no database)."""
import pandas as pd
from django.test import SimpleTestCase

from olympic_warriors.registration import (
    EMAIL,
    GLOBAL_LEVEL,
    NAME,
    RATINGS,
    parse_name,
    resolve_columns,
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
        columns = resolve_columns(make_df())

        self.assertEqual(columns[NAME], "Prénom et Nom")
        self.assertEqual(columns[EMAIL], "Adresse e-mail")
        self.assertEqual(columns[GLOBAL_LEVEL], GLOBAL_2026)
        for name, spec in RATINGS.items():
            self.assertEqual(columns[name], SKILL_SENTENCE.format(spec["criterion"]))
        self.assertEqual(len(columns), len(RATINGS) + 3)  # name, email, global level

    def test_resolves_2025_columns_without_email(self):
        columns = resolve_columns(make_df(global_header=GLOBAL_2025, with_email=False))

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
        self.assertEqual(parse_name("Pauline Fauré "), ("Pauline", "Fauré", "paulinefauré"))

    def test_first_name_only(self):
        self.assertEqual(parse_name("Adrien "), ("Adrien", "", "adrien"))

    def test_three_tokens_join_last_name(self):
        self.assertEqual(
            parse_name("Cédric LE GUEDART "), ("Cédric", "LE GUEDART", "cédricleguedart")
        )

    def test_empty_or_nan_raises(self):
        with self.assertRaises(ValueError):
            parse_name("   ")
        with self.assertRaises(ValueError):
            parse_name(float("nan"))
