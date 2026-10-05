"""The seed_demo_edition command: demo data for trying the team builder locally."""
import os
import tempfile
from datetime import date
from io import StringIO

import pandas as pd
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from olympic_warriors import builder, registration
from olympic_warriors.demo_seed import AVOIDANCE, _plain, load_seed, save_seed, split_wishes
from olympic_warriors.demo_seed import read_form
from olympic_warriors.models import (
    Edition, Player, PlayerRating, PlayerSport, RegistrationSkill, Team,
)
from olympic_warriors.models.Player import SportFrequency

NAMES = [
    ("Paul", "Durand"), ("Paul", "Lefevre"), ("Lea", "Martin"), ("Ines", "Moreau"),
    ("Camille", "Petit"), ("Hugo", "Roux"), ("Mathis", "Girard"), ("Sarah", "Blanc"),
    ("Theo", "Garnier"), ("Chloe", "Mercier"), ("Nathan", "Dupont"), ("Manon", "Fabre"),
    ("Louis", "Andre"), ("Jade", "Rousseau"),
]


def run(*args):
    out = StringIO()
    call_command("seed_demo_edition", *args, stdout=out)
    return out.getvalue()


def make_source(year=2026, inactive_user=False):
    edition = Edition.objects.create(
        year=year, host="Real", start_date=date(year, 9, 1), end_date=date(year, 9, 2)
    )
    RegistrationSkill.objects.create(
        edition=edition, identifier="CARD", name_fr="Cardio", name_en="Cardio", weight=1, order=0
    )
    users = []
    for i, (first, last) in enumerate(NAMES):
        user = User.objects.create_user(username=f"real{i}", first_name=first, last_name=last)
        users.append(user)
        player = Player.objects.create(
            user=user, edition=edition, rating=4 + i % 5, global_level=3 + i % 6
        )
        if i != 5:  # one player without any PlayerRating
            PlayerRating.objects.create(player=player, name="Cardio", identifier="CARD", rating=5)
    return edition, users


@override_settings(DEBUG=True, DEMO_SEED_PATH="/nonexistent/demo-seed.json")
class TestSeedDemoEdition(TestCase):
    def test_refuses_without_debug(self):
        make_source()
        with override_settings(DEBUG=False, STAGE_DEMO=False):
            with self.assertRaises(CommandError):
                run()
            with self.assertRaises(CommandError):
                run("--remove")
        self.assertFalse(Edition.objects.filter(year=2040).exists())

    def test_stage_demo_runs_without_debug_with_a_random_admin_password(self):
        make_source()
        with override_settings(DEBUG=False, STAGE_DEMO=True, PUBLIC_URL="https://stage.example.org/"):
            out = run()
            admin = User.objects.get(username="demo-admin")
            self.assertTrue(admin.is_superuser)
            self.assertFalse(admin.check_password("demo-password"))
            self.assertRegex(out, r"Admin: demo-admin / \S{16,}")
            self.assertIn("https://stage.example.org/2040/builder", out)
            run("--remove")
        self.assertFalse(Edition.objects.filter(year=2040).exists())
        self.assertFalse(User.objects.filter(username="demo-admin").exists())

    def test_debug_keeps_the_fixed_local_password(self):
        make_source()
        run()
        self.assertTrue(User.objects.get(username="demo-admin").check_password("demo-password"))

    def test_copies_the_real_players_with_generated_extras(self):
        _, users = make_source()
        before = User.objects.count()

        output = run()

        edition = Edition.objects.get(year=2040)
        self.assertEqual(User.objects.count(), before + 1)  # demo-admin only
        self.assertTrue(User.objects.get(username="demo-admin").is_superuser)
        players = Player.objects.filter(edition=edition)
        self.assertEqual({p.user_id for p in players}, {u.pk for u in users})
        self.assertFalse(Team.objects.filter(edition=edition).exists())
        self.assertTrue(all(p.attendance_confirmed for p in players))
        self.assertEqual(
            list(edition.registrationskill_set.values_list("identifier", flat=True)), ["CARD"]
        )
        self.assertIn("/2040/builder", output)
        self.assertIn("Generated", output)

        data = builder.payload(edition)
        self.assertTrue(data["registration_open"])
        self.assertEqual(len(data["players"]), len(NAMES))
        texts = [p["team_with"] for p in data["players"] if p["team_with"]]
        self.assertTrue(any(t.startswith("Peu importe") for t in texts))
        self.assertTrue(any("Antoine Dupont" in t for t in texts))  # nobody of the roster
        self.assertTrue(any(p["team_avoid"] for p in data["players"]))
        self.assertTrue(any(p["sports"] for p in data["players"]))
        incomplete = [p for p in data["players"] if not p["ratings"] and not p["sport_frequency"]]
        self.assertEqual(len(incomplete), 2)

    def test_a_source_without_global_levels_gets_the_one_the_form_would_give(self):
        source, _ = make_source()
        RegistrationSkill.objects.create(
            edition=source, identifier="STR", name_fr="Force", name_en="Strength", weight=2, order=1
        )
        for player in Player.objects.filter(edition=source):
            PlayerRating.objects.create(player=player, name="Force", identifier="STR", rating=7)
        Player.objects.filter(edition=source).update(global_level=None)

        run()

        weights = {"CARD": 1, "STR": 2}
        rated = 0
        for player in Player.objects.filter(edition__year=2040):
            self.assertIsNotNone(player.global_level)
            self.assertTrue(1 <= player.global_level <= 10)
            skills = {r.identifier: r.rating for r in PlayerRating.objects.filter(player=player)}
            if set(skills) == {"CARD", "STR"}:
                # The stored rating is what the form's formula gives for that answer.
                _, blended = registration.rate(skills, weights, player.global_level)
                self.assertEqual(player.rating, round(blended))
                rated += 1
        self.assertGreater(rated, 0)

    def test_a_player_without_every_skill_gets_the_rating_as_global_level(self):
        source, users = make_source()
        Player.objects.filter(edition=source).update(global_level=None)

        run()

        lonely = Player.objects.get(edition__year=2040, user=users[5])  # no PlayerRating at all
        self.assertEqual(lonely.global_level, lonely.rating)

    def test_a_given_global_level_is_kept(self):
        source, users = make_source()

        run()

        for user in users:
            old = Player.objects.get(edition=source, user=user)
            new = Player.objects.get(edition__year=2040, user=user)
            self.assertEqual((new.global_level, new.rating), (old.global_level, old.rating))

    def test_generated_answers_are_coherent_like_the_form(self):
        make_source()

        run()

        frequencies = list(SportFrequency.values)
        for player in Player.objects.filter(edition__year=2040):
            sports = list(PlayerSport.objects.filter(player=player))
            if not player.sport_frequency:  # a legacy-style incomplete player: nothing generated
                self.assertEqual(sports, [])
                continue
            active = frequencies.index(player.sport_frequency) >= frequencies.index("two_hours")
            self.assertLessEqual(len(sports), 3)
            self.assertEqual(len({s.sport for s in sports}), len(sports))
            for sport in sports:
                self.assertIn(sport.level, PlayerSport.Level.values)
                self.assertIn(sport.practice, PlayerSport.Practice.values)
                self.assertTrue(0 < sport.duration_months <= 1200)
                self.assertLessEqual(len(sport.notes), 200)
                if sport.practice == "regularly":
                    self.assertTrue(active, "regular practice needs at least two hours a week")
            if not active:
                self.assertFalse(any(s.practice == "regularly" for s in sports))
            self.assertLessEqual(len(player.dietary_restrictions), 500)
        # The frequency follows the rating: the best-rated players do more than the worst.
        rank = lambda p: frequencies.index(p.sport_frequency)
        done = [p for p in Player.objects.filter(edition__year=2040) if p.sport_frequency]
        high = [rank(p) for p in done if p.rating >= 7]
        low = [rank(p) for p in done if p.rating <= 4]
        self.assertTrue(high and low)
        self.assertGreater(sum(high) / len(high), sum(low) / len(low))
        self.assertTrue(Player.objects.filter(edition__year=2040).exclude(dietary_restrictions="").exists())

    def test_generated_wishes_read_like_the_forms_and_sit_in_the_right_field(self):
        make_source()

        run()

        players = list(Player.objects.filter(edition__year=2040))
        for player in players:
            self.assertFalse(AVOIDANCE.search(_plain(player.team_with)), player.team_with)
            if player.team_avoid:
                self.assertTrue(AVOIDANCE.search(_plain(player.team_avoid)), player.team_avoid)
            self.assertLessEqual(len(player.team_with), 500)
        withs = [p.team_with for p in players if p.team_with]
        self.assertTrue(any("\n" in t for t in withs), "a list over several lines")
        self.assertTrue(any("😁" in t or "😅" in t or "❤️" in t for t in withs), "emoji")
        self.assertTrue(any(p.team_with and p.team_avoid for p in players), "both wishes at once")
        self.assertTrue(any(p.team_avoid for p in players))

    def test_is_deterministic(self):
        make_source()
        run()
        first = list(
            Player.objects.filter(edition__year=2040).order_by("user_id").values_list(
                "user_id", "team_with", "team_avoid", "sport_frequency"
            )
        )
        run("--remove")
        run()
        second = list(
            Player.objects.filter(edition__year=2040).order_by("user_id").values_list(
                "user_id", "team_with", "team_avoid", "sport_frequency"
            )
        )
        self.assertEqual(first, second)

    def test_from_year_and_missing_source(self):
        with self.assertRaises(CommandError):
            run()
        make_source(2025)
        with self.assertRaises(CommandError):
            run()
        run("--from-year", "2025")
        self.assertEqual(Player.objects.filter(edition__year=2040).count(), len(NAMES))

    def test_source_without_active_players(self):
        edition, _ = make_source()
        Player.objects.filter(edition=edition).update(is_active=False)
        with self.assertRaises(CommandError):
            run()

    def test_a_second_run_asks_to_remove_first(self):
        make_source()
        run()
        with self.assertRaises(CommandError):
            run()

    def test_remove_keeps_real_users_and_the_source(self):
        source, users = make_source()
        run()
        User.objects.create_user(username="demo-01")  # a leftover of the previous version

        run("--remove")

        self.assertFalse(Edition.objects.filter(year=2040).exists())
        self.assertFalse(User.objects.filter(username__startswith="demo-").exists())
        self.assertEqual(User.objects.filter(username__startswith="real").count(), len(users))
        self.assertEqual(Player.objects.filter(edition=source).count(), len(NAMES))
        self.assertEqual(PlayerRating.objects.count(), len(NAMES) - 1)
        run("--remove")


FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "registration_2026_sample.csv")


def write_form(test, rows):
    """
    A synthetic form CSV with the real headers: rows are (name, frequency, history, wishes) or
    (name, frequency, history, wishes, global level).
    """
    df = pd.read_csv(FIXTURE).iloc[:1]
    out = pd.concat([df] * len(rows), ignore_index=True)
    cols = list(out.columns)
    level_column = next(c for c in cols if str(c).startswith(registration.GLOBAL_LEVEL_PREFIX))
    for i, (name, frequency, history, wishes, *level) in enumerate(rows):
        out.loc[i, cols[2]] = name
        out.loc[i, cols[3]] = frequency
        out.loc[i, cols[4]] = history
        out.loc[i, cols[-2]] = wishes
        out.loc[i, level_column] = level[0] if level else float("nan")
    handle, path = tempfile.mkstemp(suffix=".csv")
    os.close(handle)
    test.addCleanup(os.remove, path)
    out.to_csv(path, index=False)
    return path


@override_settings(DEBUG=True, DEMO_SEED_PATH="/nonexistent/demo-seed.json")
class TestSeedDemoEditionForm(TestCase):
    def setUp(self):
        make_source()

    def players(self):
        return {
            p.user.username: p
            for p in Player.objects.filter(edition__year=2040).select_related("user")
        }

    def test_fills_matched_players_and_generates_nothing(self):
        path = write_form(self, [
            ("Paul Durand", "Environ une heure par semaine", "Foot - 6 ans", "Avec Lea Martin"),
            ("Lea Martin", "Au moins deux heures par semaine", "", "Je ne veux pas être avec Paul"),
        ])

        output = run("--form", path)

        players = self.players()
        paul = players["real0"]
        self.assertEqual(paul.sport_frequency, "hour")
        self.assertEqual(paul.team_with, "Avec Lea Martin")
        self.assertEqual(paul.team_avoid, "")
        self.assertEqual(
            list(PlayerSport.objects.filter(player=paul).values_list("sport", "notes")),
            [("Historique (import)", "Foot - 6 ans")],
        )
        lea = players["real2"]
        self.assertEqual(lea.sport_frequency, "two_hours")
        self.assertEqual((lea.team_with, lea.team_avoid), ("", "Je ne veux pas être avec Paul"))
        self.assertFalse(PlayerSport.objects.filter(player=lea).exists())
        self.assertIn("2 players matched", output)
        self.assertIn(f"{len(NAMES) - 2} not", output)
        others = [p for u, p in players.items() if u not in ("real0", "real2")]
        for p in others:
            self.assertEqual((p.sport_frequency, p.team_with, p.team_avoid), ("", "", ""))
        self.assertFalse(PlayerSport.objects.exclude(player__user__username__in=["real0"]).exists())
        # the player without any source rating stays as copied, nobody is made incomplete
        self.assertEqual(PlayerRating.objects.filter(player__edition__year=2040).count(), len(NAMES) - 1)

    def test_wishes_are_truncated(self):
        path = write_form(self, [("Paul Durand", "", "", "x" * 800)])
        run("--form", path)
        self.assertEqual(len(self.players()["real0"].team_with), 500)

    def test_bad_form_files(self):
        with self.assertRaises(CommandError):
            run("--form", "/nonexistent/form.csv")
        handle, path = tempfile.mkstemp(suffix=".csv")
        os.close(handle)
        self.addCleanup(os.remove, path)
        with open(path, "w") as f:
            f.write("a,b\n1,2\n")
        with self.assertRaises(CommandError):
            run("--form", path)
        self.assertFalse(Edition.objects.filter(year=2040).exists())


class TestSplitWishes(TestCase):
    """The form's single wishes question, as its real answers are worded, split into the two fields."""

    def test_a_plain_wish_is_all_with(self):
        for text in [
            "Avec Emma ! Ou un membre du Comité",
            "Juliette \nThomas \nEmma (pour le ❤️)",
            "Antoine dupont si il est la, sinon je me contenterais de Sarah",
            "Pas de préférence",
            "s'en carre l'oignon",
        ]:
            self.assertEqual(split_wishes(text), (text, ""), text)

    def test_wishing_to_avoid_someone_is_all_avoid(self):
        for text in ["Ne pas être avec Marie", "Je ne veux pas être avec Paul", "Eviter Paul svp", "Surtout pas avec Léa"]:
            self.assertEqual(split_wishes(text), ("", text), text)

    def test_not_wanting_to_be_a_burden_is_no_avoidance(self):
        text = 'Pas de personne en particulier, mais je veux bien être avec des gens "chill" (je ne veux pas être le boulet de ceux qui ont la gagne à tout prix 😅)'
        self.assertEqual(split_wishes(text), (text, ""))

    def test_a_mix_is_split_clause_by_clause(self):
        self.assertEqual(
            split_wishes("Ne pas être avec Florentin ou Victor. Le reste pas de préférence"),
            ("Le reste pas de préférence", "Ne pas être avec Florentin ou Victor."),
        )
        self.assertEqual(
            split_wishes("Idéalement avec Léa ! Pas avec Paul"),
            ("Idéalement avec Léa !", "Pas avec Paul"),
        )

    def test_nothing_stays_nothing_and_long_texts_are_cut(self):
        self.assertEqual(split_wishes(""), ("", ""))
        self.assertEqual(len(split_wishes("x" * 800)[0]), 500)
        self.assertEqual(len(split_wishes("Pas avec " + "x" * 800)[1]), 500)


@override_settings(DEBUG=True)
class TestDemoSeed(TestCase):
    """The real form's answers, kept as a local seed that seed_demo_edition uses by default."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.seed = os.path.join(self.dir.name, "demo-seed.json")
        self.settings = override_settings(DEMO_SEED_PATH=self.seed)
        self.settings.enable()
        self.addCleanup(self.settings.disable)
        self.source, _ = make_source()

    def build(self, rows):
        out = StringIO()
        call_command("build_demo_seed", write_form(self, rows), stdout=out)
        return out.getvalue()

    def players(self):
        return {
            p.user.username: p
            for p in Player.objects.filter(edition__year=2040).select_related("user")
        }

    def test_builds_the_seed_from_a_form_and_round_trips_it(self):
        output = self.build([
            ("Paul Durand", "Environ une heure par semaine", "Foot - 6 ans", "Ne pas être avec Lea", 7),
            ("Lea Martin", "Au moins deux heures par semaine", "", "Avec Paul"),
        ])

        self.assertIn("2 players, 2 with wishes", output)
        self.assertIn("private answers", output)
        rows = load_seed(self.seed)
        self.assertEqual(set(rows), {"pauldurand", "leamartin"})
        self.assertEqual(rows["pauldurand"].team_avoid, "Ne pas être avec Lea")
        self.assertEqual(rows["pauldurand"].global_level, 7)
        self.assertIsNone(rows["leamartin"].global_level)
        save_seed(rows, self.seed)
        self.assertEqual(load_seed(self.seed), rows)

    def test_seeds_the_demo_from_it_without_the_form(self):
        self.build([
            ("Paul Durand", "Environ une heure par semaine", "Foot - 6 ans", "Avec Lea Martin"),
            ("Lea Martin", "Au moins deux heures par semaine", "", "Ne pas être avec Paul"),
        ])

        output = run()

        players = self.players()
        paul, lea = players["real0"], players["real2"]
        self.assertEqual((paul.sport_frequency, paul.team_with), ("hour", "Avec Lea Martin"))
        self.assertEqual((lea.team_with, lea.team_avoid), ("", "Ne pas être avec Paul"))
        self.assertEqual(
            list(PlayerSport.objects.filter(player=paul).values_list("sport", "notes")),
            [("Historique (import)", "Foot - 6 ans")],
        )
        self.assertIn("Nothing generated", output)
        others = [p for u, p in players.items() if u not in ("real0", "real2")]
        self.assertEqual([p for p in others if (p.sport_frequency, p.team_with, p.team_avoid) != ("", "", "")], [])

    def test_the_seeds_global_level_fills_a_missing_one_and_keeps_the_rating(self):
        old = Player.objects.get(edition=self.source, user__username="real0")
        Player.objects.filter(edition=self.source).update(global_level=None)
        self.build([("Paul Durand", "", "", "", 9)])

        run()

        paul = self.players()["real0"]
        self.assertEqual((paul.global_level, paul.rating), (9, old.rating))
        self.assertIsNotNone(self.players()["real2"].global_level)  # no row: derived

    def test_a_given_global_level_wins_over_the_seeds(self):
        self.build([("Paul Durand", "", "", "", 9)])

        run()

        old = Player.objects.get(edition=self.source, user__username="real0")
        self.assertEqual(self.players()["real0"].global_level, old.global_level)

    def test_generate_ignores_the_seed(self):
        self.build([("Paul Durand", "Environ une heure par semaine", "Foot - 6 ans", "Avec Lea Martin")])

        output = run("--generate")

        self.assertIn("Generated", output)
        self.assertNotEqual(self.players()["real0"].team_with, "Avec Lea Martin")
        self.assertTrue(Player.objects.filter(edition__year=2040).exclude(team_with="").count() > 1)

    def test_an_explicit_form_wins_over_the_seed(self):
        self.build([("Paul Durand", "", "", "From the seed")])

        run("--form", write_form(self, [("Paul Durand", "", "", "From the form")]))

        self.assertEqual(self.players()["real0"].team_with, "From the form")

    def test_without_a_seed_the_answers_are_generated(self):
        run()

        self.assertTrue(Player.objects.filter(edition__year=2040).exclude(sport_frequency="").exists())

    def test_an_unreadable_seed_stops_before_anything_is_created(self):
        with open(self.seed, "w") as f:
            f.write("not json")

        with self.assertRaises(CommandError):
            run()
        self.assertFalse(Edition.objects.filter(year=2040).exists())

    def test_the_seed_command_refuses_a_bad_form(self):
        handle, path = tempfile.mkstemp(suffix=".csv")
        os.close(handle)
        self.addCleanup(os.remove, path)
        with open(path, "w") as f:
            f.write("a,b\n1,2\n")
        with self.assertRaises(CommandError):
            call_command("build_demo_seed", path, stdout=StringIO())
        self.assertFalse(os.path.exists(self.seed))
