# Player Badges Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** People earn badges from their editions, streaks, teammates, the all-time table, their disciplines and their games. The badges are stored, refreshed nightly by cron, shown on the profile, and a few can be given by hand.

**Architecture:** A `Badge` table (plus a one-row `BadgeRefresh` lock) is filled by `olympic_warriors/badges.py`. There, `earned(today)` computes every computed badge from `profiles._load` (the same editions, players and standings the leaderboard reads) plus three queries: results, games and blindtest guesses. `refresh()` stores the difference. A `refresh_badges` command (run by a host crontab), an Edition admin action and `import_edition` call `refresh()`, and no page view writes. `GET /profile/<id>/` gains a grouped `badges` list. The front adds a catalogue (`src/lib/badges.js`), 42 more glyphs, a `Badge.svelte` medallion, and a Badges section on `/players/<id>`.

**Tech Stack:** Django 4.2 + DRF (PostgreSQL), SvelteKit 2 / Svelte 4 (plain JS), Vitest + @testing-library/svelte.

**Spec:** `docs/superpowers/specs/2026-09-23-player-badges-design.md` is the source of truth for the rules. This plan follows it, including the decisions folded in while planning (the sequence skips editions without a roster, the tier is written in the tile).

---

## Conventions for whoever executes this

- **Branch.** Work on `claude/happy-maxwell-49f5os` in `/home/user/Olympic-Warriors`. Do not switch branches.
- **Database.** The controller runs a local PostgreSQL 16 on `localhost:5433`. `server/dev.env` points at it and is gitignored. If `pg_isready -h localhost -p 5433` fails, start it with `su postgres -c "/usr/lib/postgresql/16/bin/pg_ctl -D /var/lib/postgresql/ow-data -o '-p 5433 -k /tmp' -l /var/lib/postgresql/ow-data/server.log start"`.
- **Server tests.** Run `cd /home/user/Olympic-Warriors/server && python3 manage.py test olympic_warriors.tests.<module>`. The whole suite is `python3 manage.py test` (343 tests pass at the start, in about 2.5 minutes). **Never run two Django test runs at once**: they share the test database name.
- **Front tests.** Run `cd /home/user/Olympic-Warriors/front && npx vitest run <path>`. The whole suite is `npm test` (329 tests pass at the start). `front/.env` exists, so `npm run build` works.
- **Commits.** Stage explicit paths only (`git add <paths>`), never `git add -A` or `git add .`: other agents may have uncommitted drafts in the tree. Messages follow the repo style (`[ADD] ...`, `[FEAT] front: ...`, `[TEST] ...`, `[DOCS] ...`) and end with these two lines:
  ```
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01BCyaie3oGmp9hTfHaEKWZw
  ```
- **Business logic.** It lives in model `save()` overrides elsewhere in this app. `Badge` has none, so `bulk_create` and queryset `delete()` skip nothing.
- **Svelte markup.** It stays sentence case, and uppercase comes from CSS (`.label`). Use the tokens in `front/src/routes/styles.css` and never hard-code a colour. Every visible string goes through `t`, with keys in both `fr.js` and `en.js`.
- **Glyphs.** Glyph files are white strokes on a 2000×2000 viewBox with no frame; see "Glyph tasks" before Task 12.

## File map

Server:
- **Create** `server/olympic_warriors/models/Badge.py`: `Badge` (with `Badge.Codes`), `MANUAL_CODES`, `BadgeRefresh`.
- **Modify** `server/olympic_warriors/models/__init__.py`: export them.
- **Create** `server/olympic_warriors/migrations/0033_badges.py`: the tables, the constraint and the `BadgeRefresh` row.
- **Modify** `server/olympic_warriors/profiles.py`: `Loaded`, `_load`, `_participations`, with `participations()` built on them.
- **Create** `server/olympic_warriors/badges.py`, containing:
  - `Earned`, `History`, `history`;
  - the rules, `earned`, `RefreshReport`, `refresh`;
  - `profile_badges`, `FAMILIES`, `KINDS`.
- **Create** `server/olympic_warriors/management/commands/refresh_badges.py`.
- **Modify** `server/olympic_warriors/management/commands/import_edition.py`: refresh after a real import.
- **Modify** `server/olympic_warriors/admin.py`: `BadgeAdminForm`, `BadgeAdmin`, and the Edition action.
- **Modify** `server/olympic_warriors/serializer.py`: `ProfileBadgePartnerSerializer`, `ProfileBadgeSerializer`, and `ProfileSerializer.badges`.
- **Modify** `server/olympic_warriors/views.py`: `getProfile` passes the badges.
- **Create** these tests:
  - `server/olympic_warriors/tests/test_badge_model.py`;
  - `test_badges.py` (the rules);
  - `test_badge_refresh.py` (refresh, the command, the admin, the import hook).
- **Modify** `server/olympic_warriors/tests/test_profiles.py`: the `badges` payload and the query count.

Front:
- **Create** 42 glyphs in `front/src/lib/img/badges/`.
- **Create** `front/src/lib/badges.js` and `front/src/lib/badges.test.js`.
- **Modify** `front/src/lib/i18n/fr.js` and `en.js`: the badge keys.
- **Create** `front/src/lib/components/Badge.svelte` and `Badge.test.js`.
- **Modify** `front/src/routes/players/[id]/+page.svelte` and its `page.test.js`.
- **Modify** `front/src/lib/fixtures/players.js`: `profile.badges` and `profileUnranked.badges`.

Docs:
- **Modify** `CLAUDE.md`, `docker-compose.prod.example.yml` (a comment) and the spec (a status line).

---

### Task 1: `Badge` and `BadgeRefresh`

**Files:**
- Create: `server/olympic_warriors/models/Badge.py`
- Modify: `server/olympic_warriors/models/__init__.py`
- Create: `server/olympic_warriors/migrations/0033_badges.py` (generated, then edited)
- Create: `server/olympic_warriors/tests/test_badge_model.py`

- [ ] **Step 1: Write the failing tests**

Create `server/olympic_warriors/tests/test_badge_model.py`:

```python
"""
Tests for the Badge model: the catalogue, the constraint on computed rows, and the one
BadgeRefresh row the migration creates.
"""

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase

from olympic_warriors.models import MANUAL_CODES, Badge, BadgeRefresh, Edition


class TestCatalogue(TestCase):
    def test_codes_are_the_spec_catalogue_in_order(self):
        codes = Badge.Codes.values
        self.assertEqual(len(codes), 63)
        self.assertEqual(len(set(codes)), 63)
        self.assertEqual(codes[:5], ["champion", "runner-up", "bronze", "chocolate", "wooden-spoon"])
        self.assertEqual(codes[-6:], ["mvp", "fair-play", "hype", "costume", "wounded", "torchbearer"])

    def test_six_codes_are_given_by_hand(self):
        self.assertEqual(
            sorted(MANUAL_CODES),
            sorted(["mvp", "fair-play", "hype", "costume", "wounded", "torchbearer"]),
        )


class TestBadgeRows(TestCase):
    def setUp(self):
        self.edition = Edition.objects.create(
            year=2024, host="Nantes", start_date="2024-09-21", end_date="2024-09-22"
        )
        self.user = User.objects.create(username="ana", first_name="Ana", last_name="Lopez")

    def badge(self, **kwargs):
        return Badge.objects.create(user=self.user, edition=self.edition, **kwargs)

    def test_defaults(self):
        badge = self.badge(code=Badge.Codes.CHAMPION)
        self.assertEqual(
            (badge.tier, badge.discipline, badge.partner, badge.is_manual, badge.note, badge.is_active),
            (0, "", None, False, "", True),
        )
        self.assertIsNotNone(badge.created_at)

    def test_a_computed_row_is_unique_on_its_key(self):
        other = User.objects.create(username="bob", first_name="Bob", last_name="Martin")
        self.badge(code=Badge.Codes.COMRADES, partner=other)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.badge(code=Badge.Codes.COMRADES, partner=other)

    def test_the_same_key_twice_is_fine_by_hand(self):
        self.badge(code=Badge.Codes.MVP, is_manual=True)
        self.badge(code=Badge.Codes.MVP, is_manual=True)
        self.assertEqual(Badge.objects.filter(code="mvp").count(), 2)

    def test_str_names_the_badge_person_and_year(self):
        badge = self.badge(code=Badge.Codes.RUNNER_UP)
        self.assertEqual(str(badge), "Dauphin - ana (2024)")


class TestBadgeRefresh(TestCase):
    def test_the_migration_created_the_one_row(self):
        self.assertTrue(BadgeRefresh.objects.filter(pk=1).exists())
        self.assertIsNone(BadgeRefresh.objects.get(pk=1).refreshed_at)
```

- [ ] **Step 2: Run them to see them fail**

Run: `cd /home/user/Olympic-Warriors/server && python3 manage.py test olympic_warriors.tests.test_badge_model`
Expected: an ImportError on `MANUAL_CODES` / `Badge`.

- [ ] **Step 3: Write the model**

Create `server/olympic_warriors/models/Badge.py`:

```python
from django.contrib.auth.models import User
from django.db import models
from django.db.models import Q


class Badge(models.Model):
    """
    A badge a person earned: computed by olympic_warriors.badges (is_manual False, rebuilt
    by badges.refresh()) or given by hand in the admin (is_manual True, never touched by the
    refresh). See the player badges design spec under docs/superpowers/specs/.
    """

    class Codes(models.TextChoices):
        """The catalogue, in catalogue order: the profile lists badges in this order. The
        front mirrors it in front/src/lib/badges.js (BADGE_CODES in badges.test.js)."""

        # Edition places
        CHAMPION = "champion", "Champion"
        RUNNER_UP = "runner-up", "Dauphin"
        BRONZE = "bronze", "Bronze"
        CHOCOLATE = "chocolate", "Médaille en chocolat"
        WOODEN_SPOON = "wooden-spoon", "Cuillère de bois"
        # Streaks and career
        BACK_TO_BACK = "back-to-back", "Doublé"
        THREEPEAT = "threepeat", "Triplé"
        DYNASTY = "dynasty", "Dynastie"
        PHOENIX = "phoenix", "Phénix"
        LEGEND = "legend", "Légende"
        PODIUM_REGULAR = "podium-regular", "Abonné au podium"
        FULL_SET = "full-set", "Collection complète"
        ETERNAL_SECOND = "eternal-second", "Poulidor"
        JANUS = "janus", "Janus"
        COMEBACK = "comeback", "Remontada"
        ON_THE_RISE = "on-the-rise", "Ascension"
        ICARUS = "icarus", "Icare"
        LUCKY_CHARM = "lucky-charm", "Porte-bonheur"
        # Loyalty
        ROOKIE = "rookie", "Bizut"
        VETERAN = "veteran", "Vétéran"
        ARGONAUT = "argonaut", "Argonaute"
        EVER_PRESENT = "ever-present", "Pénélope"
        HOMECOMING = "homecoming", "Ulysse"
        GLOBETROTTER = "globetrotter", "Globe-trotteur"
        # Teammates
        COMRADES = "comrades", "Compagnons d'armes"
        NETWORKER = "networker", "Rassembleur"
        # Hall of fame (the all-time table)
        GOAT = "goat", "G.O.A.T"
        ALONE_AT_THE_TOP = "alone-at-the-top", "Seul au sommet"
        HALL_OF_FAME_PODIUM = "hall-of-fame-podium", "Podium du panthéon"
        HALL_OF_FAMER = "hall-of-famer", "Entrée au panthéon"
        REIGN = "reign", "Règne"
        KINGSLAYER = "kingslayer", "Régicide"
        ROCKET = "rocket", "Fusée"
        # Disciplines
        SPECIALIST = "specialist", "Spécialiste"
        ALL_ROUNDER = "all-rounder", "Touche-à-tout"
        DECATHLETE = "decathlete", "Décathlonien"
        BRAINS_AND_BRAWN = "brains-and-brawn", "Tête et jambes"
        CLEAN_SWEEP = "clean-sweep", "Razzia"
        METRONOME = "metronome", "Métronome"
        UNCROWNED = "uncrowned", "Sans couronne"
        PHOTO_FINISH = "photo-finish", "Photo-finish"
        # The gods (a discipline family each) and Mount Olympus
        ATHENA = "athena", "Athéna"
        APOLLO = "apollo", "Apollon"
        ARTEMIS = "artemis", "Artémis"
        HERMES = "hermes", "Hermès"
        HERACLES = "heracles", "Héraclès"
        THESEUS = "theseus", "Thésée"
        ARES = "ares", "Arès"
        HADES = "hades", "Hadès"
        DIONYSUS = "dionysus", "Dionysos"
        OLYMPUS = "olympus", "Olympe"
        # Games
        UNBEATEN = "unbeaten", "Invaincu"
        PERFECT_RUN = "perfect-run", "Sans faute"
        SHUTOUT = "shutout", "Cadenas"
        STEAMROLLER = "steamroller", "Rouleau compresseur"
        GOLDEN_WHISTLE = "golden-whistle", "Sifflet d'or"
        PERFECT_PITCH = "perfect-pitch", "Oreille absolue"
        # Given by hand
        MVP = "mvp", "MVP"
        FAIR_PLAY = "fair-play", "Fair-play"
        HYPE = "hype", "Ambianceur"
        COSTUME = "costume", "Plus beau déguisement"
        WOUNDED = "wounded", "Blessé de guerre"
        TORCHBEARER = "torchbearer", "Porteur de flamme"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="badges")
    code = models.CharField(max_length=32, choices=Codes.choices)
    # The edition the badge was earned at: the one that completed it.
    edition = models.ForeignKey("Edition", on_delete=models.CASCADE)
    # 0 for an untiered badge, 1 to 3 (bronze, silver, gold) for a tiered one.
    tier = models.PositiveSmallIntegerField(default=0)
    # The discipline name, for specialist, unbeaten and perfect-run.
    discipline = models.CharField(max_length=100, blank=True, default="")
    # The other person, for comrades.
    partner = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.CASCADE, related_name="+"
    )
    is_manual = models.BooleanField(default=False)
    # An organiser's memo on a badge given by hand; never public.
    note = models.CharField(max_length=200, blank=True)
    # Clearing it revokes a badge; the refresh keeps a revoked computed row inactive.
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # Django 4.2 has no nulls_distinct: rows without a partner stay unique through
            # the refresh's diff, not through this constraint.
            models.UniqueConstraint(
                fields=["user", "code", "edition", "tier", "discipline", "partner"],
                condition=Q(is_manual=False),
                name="badge_unique_computed",
            )
        ]

    def __str__(self):
        return f"{self.get_code_display()} - {self.user} ({self.edition.year})"


# The badges organisers give by hand; the refresh never computes them.
MANUAL_CODES = frozenset(
    {
        Badge.Codes.MVP,
        Badge.Codes.FAIR_PLAY,
        Badge.Codes.HYPE,
        Badge.Codes.COSTUME,
        Badge.Codes.WOUNDED,
        Badge.Codes.TORCHBEARER,
    }
)


class BadgeRefresh(models.Model):
    """
    The one row (pk 1, created by migration 0033) that badges.refresh() locks, so that a
    cron run and an admin action run one after the other, and stamps when a run finishes.
    Not in the admin.
    """

    refreshed_at = models.DateTimeField(null=True, blank=True)
```

In `server/olympic_warriors/models/__init__.py`, add after the `Edition` import line:

```python
from .Badge import Badge, BadgeRefresh, MANUAL_CODES
```

- [ ] **Step 4: Generate the migration, then add the row**

Run: `cd /home/user/Olympic-Warriors/server && python3 manage.py makemigrations olympic_warriors -n badges`
Expected: `migrations/0033_badges.py` with `CreateModel` for both models and the `AddConstraint`.

Append to that migration's module, above `class Migration`:

```python
def create_refresh_row(apps, schema_editor):
    """The one BadgeRefresh row badges.refresh() locks."""
    apps.get_model("olympic_warriors", "BadgeRefresh").objects.get_or_create(pk=1)
```

and add as the last operation:

```python
        migrations.RunPython(create_refresh_row, migrations.RunPython.noop),
```

- [ ] **Step 5: Run the tests and the migration check**

Run: `python3 manage.py test olympic_warriors.tests.test_badge_model && python3 manage.py makemigrations --check --dry-run`
Expected: the tests pass, and "No changes detected".

- [ ] **Step 6: Commit**

```bash
cd /home/user/Olympic-Warriors
git add server/olympic_warriors/models/Badge.py server/olympic_warriors/models/__init__.py \
  server/olympic_warriors/migrations/0033_badges.py server/olympic_warriors/tests/test_badge_model.py
git commit -m "[ADD] badges: Badge and BadgeRefresh models, the catalogue of codes" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01BCyaie3oGmp9hTfHaEKWZw"
```

---

### Task 2: Split `profiles.participations()` into `_load` and `_participations`

This is a pure refactor with no behaviour change: `earned()` and `participations()` must read the same data.

**Files:**
- Modify: `server/olympic_warriors/profiles.py`
- Modify: `server/olympic_warriors/tests/test_profiles.py` (one test)

- [ ] **Step 1: Write the failing test**

Add to `test_profiles.py` (import `_load` next to the other names from `olympic_warriors.profiles`):

```python
class TestLoad(ProfilesSetup, TestCase):
    def test_exposes_the_data_participations_reads(self):
        loaded = _load(TODAY)

        self.assertEqual(set(loaded.editions), {self.y2024.id, self.y2025.id, self.y2026.id})
        self.assertEqual(loaded.editions[self.y2024.id].team_count, 4)
        self.assertEqual(loaded.finished, {self.y2024.id, self.y2025.id})
        # Standings only for finished editions with a player, and both of those rank.
        self.assertEqual(set(loaded.standings), {self.y2024.id, self.y2025.id})
        self.assertEqual(loaded.ranked, {self.y2024.id, self.y2025.id})
        self.assertEqual(loaded.chosen[(self.ana.id, self.y2025.id)].team_id, self.loups.id)
```

Run: `python3 manage.py test olympic_warriors.tests.test_profiles.TestLoad`
Expected: an ImportError on `_load`.

- [ ] **Step 2: Refactor**

In `profiles.py`, replace the body of `participations()` with a `Loaded` dataclass, `_load`, `_participations` and a thin `participations()`:

```python
@dataclass(frozen=True)
class Loaded:
    """
    What participations() and badges.earned() both read, from 2 + 3 per finished edition with
    a player queries: the active editions by id (annotated with `team_count`, their active
    teams), the chosen Player row per (user id, edition id), the finished edition ids, the
    standings of the finished editions that have a player, and which of those rank.
    """

    editions: dict
    chosen: dict
    finished: frozenset
    standings: dict
    ranked: frozenset


def _load(today):
    """The data behind the participations on `today` (a Paris date)."""
    editions = {
        edition.id: edition
        for edition in Edition.objects.filter(is_active=True).annotate(
            team_count=Count("team", filter=Q(team__is_active=True))
        )
    }
    players = (
        Player.objects.filter(is_active=True, edition_id__in=editions)
        .select_related("user", "team")
        .order_by("id")
    )
    chosen = _one_row_per_edition(players)

    finished = frozenset(pk for pk, edition in editions.items() if edition.end_date < today)
    with_players = {edition_id for _, edition_id in chosen}
    standings = {pk: compute_standings(editions[pk]) for pk in sorted(with_players & finished)}
    ranked = frozenset(pk for pk, standing in standings.items() if _is_ranked(standing))
    return Loaded(editions, chosen, finished, standings, ranked)


def _participations(loaded):
    """Every person's participations from loaded data, see participations()."""
    by_user = {}
    for (user_id, edition_id), player in loaded.chosen.items():
        edition = loaded.editions[edition_id]
        team = _valid_team(player)
        rank = None
        if team is not None and edition_id in loaded.ranked:
            # A hand-entered final_rank of 0 means no rank too.
            rank = loaded.standings[edition_id].team(team.id).ranking or None
        _, parts = by_user.setdefault(user_id, (player.user, []))
        parts.append(
            Participation(
                year=edition.year,
                team_id=team.id if team else None,
                team_name=team.name if team else None,
                rank=rank,
                teams=edition.team_count,
                finished=edition_id in loaded.finished,
            )
        )

    return {
        user_id: (user, tuple(sorted(parts, key=lambda p: p.year, reverse=True)))
        for user_id, (user, parts) in by_user.items()
    }


def participations(today=None):
    """
    Every person's participations, newest edition first, keyed by user id:
    {user_id: (user, (Participation, ...))}.
    Queries: the editions, the players, then three per finished edition with a player.
    """
    return _participations(_load(today or paris_today()))
```

Keep every other function as it is.

- [ ] **Step 3: Run the profiles tests**

Run: `python3 manage.py test olympic_warriors.tests.test_profiles`
Expected: all pass, including the query-count pins, which must not change.

- [ ] **Step 4: Commit**

```bash
git add server/olympic_warriors/profiles.py server/olympic_warriors/tests/test_profiles.py
git commit -m "[REFACTOR] profiles: _load and _participations, shared with the badges" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01BCyaie3oGmp9hTfHaEKWZw"
```

---

### Task 3: `badges.py`, the history, and the edition place badges

**Files:**
- Create: `server/olympic_warriors/badges.py`
- Create: `server/olympic_warriors/tests/test_badges.py`

- [ ] **Step 1: Write the test scaffolding and the first failing tests**

Create `server/olympic_warriors/tests/test_badges.py`:

```python
"""
Tests for olympic_warriors.badges: every computed badge rule, read through earned() on
small histories. Hand-ranked editions (Team.final_rank) make the place, streak, loyalty,
teammate and hall of fame histories quick to build; discipline and game rules use
revealed disciplines with results and games.
"""

from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase

from olympic_warriors.badges import earned, history
from olympic_warriors.models import Badge, Edition, Player, Team

C = Badge.Codes
TODAY = date(2031, 1, 1)


class World:
    """Builds histories: finished editions whose teams are hand-ranked, and people on them."""

    def edition(self, year, size=4, host="Paris", ranks=None, finished=True, ranked=True):
        """
        An edition held on Sept 21-22 of `year` (or ending after TODAY when not `finished`)
        with `size` teams T<year>-1.. ranked 1..size, or `ranks` (None for a team without a
        final_rank). With ranked=False the teams get no final_rank at all.
        Returns (edition, [teams]).
        """
        end = date(year, 9, 22) if finished else date(TODAY.year + 1, 1, 1)
        edition = Edition.objects.create(
            year=year, host=host, start_date=date(year, 9, 21), end_date=end
        )
        ranks = ranks if ranks is not None else list(range(1, size + 1))
        teams = [
            Team.objects.create(
                name=f"T{year}-{n}", edition=edition, final_rank=rank if ranked else None
            )
            for n, rank in enumerate(ranks, start=1)
        ]
        return edition, teams

    @staticmethod
    def person(name):
        return User.objects.create(username=f"u-{name}", first_name=name, last_name="Test")

    @staticmethod
    def seat(user, edition, team=None):
        return Player.objects.create(user=user, edition=edition, team=team, rating=5)


def badges_of(user, today=TODAY):
    """Sorted (code, year, tier, discipline, partner id) of the user's computed badges."""
    years = dict(Edition.objects.values_list("id", "year"))
    return sorted(
        (e.code, years[e.edition_id], e.tier, e.discipline, e.partner_id)
        for e in earned(today)
        if e.user_id == user.id
    )


def years_of(user, code, today=TODAY):
    """The years at which the user earned `code`, sorted."""
    return sorted(year for c, year, *_ in badges_of(user, today) if c == code)


class TestHistory(World, TestCase):
    def test_the_sequence_is_finished_editions_with_players_by_year(self):
        e2023, _ = self.edition(2023)  # finished, no roster: left out
        e2024, t2024 = self.edition(2024)
        e2025, t2025 = self.edition(2025)
        e2026, t2026 = self.edition(2026, finished=False)  # running: left out
        ana = self.person("Ana")
        self.seat(ana, e2025, t2025[0])
        self.seat(ana, e2024, t2024[1])
        self.seat(ana, e2026, t2026[0])

        h = history(TODAY)

        self.assertEqual([e.year for e in h.sequence], [2024, 2025])
        self.assertEqual({i: seat.rank for i, seat in h.seats[ana.id].items()}, {0: 2, 1: 1})
        self.assertEqual(h.first_edition_id, e2023.id)


class TestPlaces(World, TestCase):
    def setUp(self):
        self.e2024, self.teams = self.edition(2024, size=5)
        self.people = [self.person(n) for n in ("Ana", "Bob", "Chloé", "Dan", "Eve")]
        for user, team in zip(self.people, self.teams):
            self.seat(user, self.e2024, team)

    def test_first_second_third_fourth_and_last(self):
        ana, bob, chloe, dan, eve = self.people
        self.assertEqual(years_of(ana, C.CHAMPION), [2024])
        self.assertEqual(years_of(bob, C.RUNNER_UP), [2024])
        self.assertEqual(years_of(chloe, C.BRONZE), [2024])
        self.assertEqual(years_of(dan, C.CHOCOLATE), [2024])
        self.assertEqual(years_of(eve, C.WOODEN_SPOON), [2024])
        self.assertEqual(years_of(dan, C.WOODEN_SPOON), [])
```

Add more tests to `TestPlaces`, each on its own minimal history:
- **One per edition.** A person who wins two editions has `champion` in both years.
- **Chocolate needs 5 teams.** In a 4-team edition, 4th is `wooden-spoon` and not `chocolate`.
- **Chocolate is never the last place.** In a 5-team edition with ranks `[1, 2, 3, 4, 4]`, the two 4th teams share the last place: `wooden-spoon`, and no `chocolate`.
- **The spoon needs 4 teams.** In a 3-team edition, 3rd is `bronze` and not `wooden-spoon`.
- **The spoon needs a complete ranking.** In a hand-ranked edition where one team has no `final_rank` (`ranks=[1, 2, 3, None]`), the worst ranked team gets no `wooden-spoon`.
- **No team, no place.** A person without a team gets no place badge.
- **Unfinished editions give nothing.** A person 1st in a running edition gets no `champion`.

- [ ] **Step 2: Run them to see them fail**

Run: `python3 manage.py test olympic_warriors.tests.test_badges`
Expected: an ImportError on `olympic_warriors.badges`.

- [ ] **Step 3: Create `badges.py` with the history and the place rules**

```python
"""
Badges people earn from their editions (see the player badges design spec under
docs/superpowers/specs/). earned() computes every computed badge from the current data;
refresh() stores the difference in the Badge table. The nightly cron job, the Edition admin
action and import_edition call refresh(); a page view only reads the table.

The rules read the sequence: the finished active editions with at least one active player,
by year, so a year without an edition and an edition without a roster never break a
streak. Each rule is evaluated over the history up to each edition in turn, and a badge is
earned at the edition that completes it: playing more never takes a badge away.
"""

from dataclasses import dataclass

from .models import Badge
from .profiles import _load, _participations, paris_today

C = Badge.Codes


@dataclass(frozen=True)
class Earned:
    """One computed badge, keyed like a stored computed Badge row."""

    user_id: int
    code: str
    edition_id: int
    tier: int = 0
    discipline: str = ""
    partner_id: int | None = None


@dataclass(frozen=True)
class History:
    """
    What the rules read:
    - sequence: the editions of the sequence by year (annotated with `team_count`);
    - seats: {user id: {sequence index: Participation}}, sequence editions only;
    - users: {user id: User};
    - last_ranks: per sequence index, the rank of the last place, or None (_last_rank);
    - standings: per sequence index, the edition's Standings;
    - first_edition_id: the first finished active edition, roster or not (argonaut).
    """

    sequence: tuple
    seats: dict
    users: dict
    last_ranks: tuple
    standings: tuple
    first_edition_id: int | None


def _rank(seat):
    """The rank of a seat whose participation counts, else None."""
    return seat.rank if seat is not None and seat.counts else None


def _last_rank(edition, standing, ranked):
    """
    The rank of the edition's last place: every active team has a rank, in an edition of at
    least 4 teams (so a last place is never a podium place). None otherwise.
    """
    if edition.id not in ranked or edition.team_count < 4:
        return None
    ranks = [team.ranking for team in standing.teams.values()]
    if not ranks or not all(ranks):
        return None
    return max(ranks)


def history(today=None):
    """The History of the current data on `today` (a Paris date)."""
    loaded = _load(today or paris_today())
    people = _participations(loaded)
    sequence = tuple(
        sorted((loaded.editions[pk] for pk in loaded.standings), key=lambda e: e.year)
    )
    index = {edition.year: i for i, edition in enumerate(sequence)}
    seats = {}
    for user_id, (_, parts) in people.items():
        mine = {index[part.year]: part for part in parts if part.year in index}
        if mine:
            seats[user_id] = mine
    finished = [loaded.editions[pk] for pk in loaded.finished]
    return History(
        sequence=sequence,
        seats=seats,
        users={user_id: user for user_id, (user, _) in people.items()},
        last_ranks=tuple(
            _last_rank(edition, loaded.standings[edition.id], loaded.ranked)
            for edition in sequence
        ),
        standings=tuple(loaded.standings[edition.id] for edition in sequence),
        first_edition_id=min(finished, key=lambda e: e.year).id if finished else None,
    )


PLACES = {1: C.CHAMPION, 2: C.RUNNER_UP, 3: C.BRONZE}


def _places(h):
    """champion, runner-up, bronze, chocolate and wooden-spoon, at every edition earned."""
    for user_id, seats in h.seats.items():
        for i, seat in seats.items():
            rank = _rank(seat)
            if rank is None:
                continue
            edition_id = h.sequence[i].id
            last = rank == h.last_ranks[i]
            if rank in PLACES:
                yield Earned(user_id, PLACES[rank], edition_id)
            if rank == 4 and seat.teams >= 5 and not last:
                yield Earned(user_id, C.CHOCOLATE, edition_id)
            if last:
                yield Earned(user_id, C.WOODEN_SPOON, edition_id)


RULES = (_places,)


def earned(today=None):
    """Every computed badge on `today` (a Paris date, default today), as a set of Earned."""
    h = history(today)
    found = set()
    for rule in RULES:
        found.update(rule(h))
    return found
```

- [ ] **Step 4: Run the tests**

Run: `python3 manage.py test olympic_warriors.tests.test_badges`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add server/olympic_warriors/badges.py server/olympic_warriors/tests/test_badges.py
git commit -m "[ADD] badges: the history and the edition place badges" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01BCyaie3oGmp9hTfHaEKWZw"
```

---

### Task 4: Streaks and career

**Files:**
- Modify: `server/olympic_warriors/badges.py`
- Modify: `server/olympic_warriors/tests/test_badges.py`

- [ ] **Step 1: Write the failing tests**

Add a `TestStreaks` and a `TestCareer` class (both `World, TestCase`). Build the histories with `self.edition(year)` and seat people on `teams[rank - 1]`. For example:

```python
class TestStreaks(World, TestCase):
    def play(self, user, places):
        """Seat `user` in consecutive editions from 2021, at the given ranks (None: missed)."""
        for year, rank in zip(range(2021, 2021 + len(places)), places):
            edition = Edition.objects.filter(year=year).first()
            if edition is None:
                edition, _ = self.edition(year, size=6)
            if rank is not None:
                team = Team.objects.get(edition=edition, final_rank=rank)
                self.seat(user, edition, team)

    def test_a_title_streak_of_four_earns_each_streak_badge_once(self):
        ana = self.person("Ana")
        self.play(ana, [1, 1, 1, 1, 1])

        self.assertEqual(years_of(ana, C.BACK_TO_BACK), [2022])
        self.assertEqual(years_of(ana, C.THREEPEAT), [2023])
        self.assertEqual(years_of(ana, C.DYNASTY), [2024])
```

Add these cases, one test each:
- **Streaks and gaps**
  - **Later streaks earn again.** Places `[1, 1, 2, 1, 1]` give `back-to-back` in 2022 and 2025.
  - **A year without an edition is skipped.** Editions in 2021, 2022 and 2024, with no 2023 edition, and titles in all three: `threepeat` in 2024.
  - **A missed edition breaks a streak.** Places `[1, None, 1]`: no `back-to-back`.
  - **An unranked edition breaks a place streak.** Title in 2021; in 2022 the person plays for a team without a `final_rank` (build 2022 with `ranks=[1, 2, None]` and seat them on the unranked team); title in 2023. No `back-to-back`.
  - **A roster-less edition does not break a streak.** An edition with no players at all between two titles leaves them consecutive: `back-to-back`.
- **podium-regular**
  - Places `[3, 2, 1]` give it in 2023.
  - Places `[3, 2, 1, 2]` still give it only in 2023.
  - Places `[3, 2, 4, 1, 1, 2]` give it in 2026.
- **phoenix**
  - Places `[1, 2, 1]` give it in 2023.
  - Places `[1, None, 1]` give it in 2023.
  - Places `[1, 1]` do not give it.
  - Places `[2, 1]` do not give it: no earlier title.
  - Places `[1, 3, 1, 4, 1]` give it in 2023 and 2025.
- **legend**
  - Places `[1, 3, 1, 1]` give it in 2024, once.
- **full-set**
  - Places `[3, 1, 2]` give it in 2023, once.
- **eternal-second**
  - Places `[2, 4, 2]` give it in 2023.
  - Places `[1, 2, 2]` do not give it.
  - Places `[2, 2, 1]` give it in 2022, and it stays after the 2023 title: playing more never removes a badge.
- **janus**
  - A title in a 6-team edition, then 6th in a 6-team edition: `janus` at the second, once.
- **comeback**
  - 6th, then 3rd in the next edition: `comeback` at the second.
  - 6th, a missed edition, then 1st: no `comeback`.
- **on-the-rise**
  - In 6-team editions, places `[6, 4, 2]` give it in 2023.
  - Places `[6, 4, 2, 1]` give it only in 2023.
  - Places `[6, 4, 4, 3, 2]` give it in 2025: the run restarts at the repeated 4.
  - It compares relative ranks: 3rd of 5 (0.5) then 3rd of 9 (0.25) then 1st is a rise. Build the three editions with those sizes.
- **icarus**
  - In 6-team editions, places `[1, 4]` give it at the second edition.
  - Places `[1, 3]` do not.
- **lucky-charm**
  - Places `[2, 3, 1]` give it in 2023.
  - Places `[2, 4, 1]` do not.
  - Places `[2, 3, 1, 6]` still give it in 2023.

- [ ] **Step 2: Run them to see them fail**

Run: `python3 manage.py test olympic_warriors.tests.test_badges`
Expected: the new tests fail, and the place tests still pass.

- [ ] **Step 3: Implement**

Add to `badges.py` (below `_places`):

```python
TITLE_STREAKS = {2: C.BACK_TO_BACK, 3: C.THREEPEAT, 4: C.DYNASTY}


def _on_podium(seat):
    rank = _rank(seat)
    return rank is not None and rank <= 3


def _runs(h, seats, holds):
    """
    (sequence index, run length) for every edition of the sequence: how many consecutive
    editions end there where holds(seat) is true for the person, 0 when it is not.
    """
    length = 0
    for i in range(len(h.sequence)):
        seat = seats.get(i)
        length = length + 1 if seat is not None and holds(seat) else 0
        yield i, length


def _streaks(h):
    """back-to-back, threepeat, dynasty and podium-regular: once per streak, at the
    edition completing it."""
    for user_id, seats in h.seats.items():
        for i, length in _runs(h, seats, lambda seat: _rank(seat) == 1):
            if length in TITLE_STREAKS:
                yield Earned(user_id, TITLE_STREAKS[length], h.sequence[i].id)
        for i, length in _runs(h, seats, _on_podium):
            if length == 3:
                yield Earned(user_id, C.PODIUM_REGULAR, h.sequence[i].id)


def _career(h):
    """phoenix, legend, full-set, eternal-second, janus, comeback, on-the-rise, icarus and
    lucky-charm."""
    for user_id, seats in h.seats.items():
        yield from _career_of(h, user_id, seats)


def _career_of(h, user_id, seats):
    out, once = [], set()

    def earn(code, edition_id, repeat=False):
        if repeat or code not in once:
            once.add(code)
            out.append(Earned(user_id, code, edition_id))

    titles = seconds = rise = 0
    places, counted = set(), []
    had_last = previous_last = False
    previous_rank = previous_share = None
    for i, edition in enumerate(h.sequence):
        seat = seats.get(i)
        rank = _rank(seat)
        last = rank is not None and rank == h.last_ranks[i]
        edition_id = edition.id

        if rank == 1:
            if titles and previous_rank != 1:
                earn(C.PHOENIX, edition_id, repeat=True)
            titles += 1
            if titles == 3:
                earn(C.LEGEND, edition_id)
        if rank == 2:
            seconds += 1
            if seconds == 2 and not titles:
                earn(C.ETERNAL_SECOND, edition_id)
        if rank is not None and rank <= 3:
            places.add(rank)
            if places == {1, 2, 3}:
                earn(C.FULL_SET, edition_id)
        had_last = had_last or last
        if titles and had_last:
            earn(C.JANUS, edition_id)
        if previous_last and rank is not None and rank <= 3:
            earn(C.COMEBACK, edition_id, repeat=True)
        if previous_rank == 1 and rank is not None and rank > seat.teams / 2:
            earn(C.ICARUS, edition_id, repeat=True)

        # Relative rank: 0 for first, 1 for last, so editions of different sizes compare.
        share = None if rank is None else (rank - 1) / (seat.teams - 1)
        if share is None:
            rise = 0
        elif previous_share is not None and share < previous_share:
            rise += 1
        else:
            rise = 1
        if rise == 3:
            earn(C.ON_THE_RISE, edition_id, repeat=True)

        if rank is not None:
            counted.append(rank)
            if len(counted) == 3 and all(r <= 3 for r in counted):
                earn(C.LUCKY_CHARM, edition_id)

        previous_rank, previous_share, previous_last = rank, share, last
    return out
```

Then set `RULES = (_places, _streaks, _career)`.

- [ ] **Step 4: Run the tests**

Run: `python3 manage.py test olympic_warriors.tests.test_badges`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add server/olympic_warriors/badges.py server/olympic_warriors/tests/test_badges.py
git commit -m "[ADD] badges: streaks and career" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01BCyaie3oGmp9hTfHaEKWZw"
```

---

### Task 5: Loyalty and teammates

**Files:**
- Modify: `server/olympic_warriors/badges.py`
- Modify: `server/olympic_warriors/tests/test_badges.py`

- [ ] **Step 1: Write the failing tests** (a `TestLoyalty` and a `TestTeammates` class)

**Loyalty.** A participation is enough, with or without a team or a rank.
- **rookie**
  - Earned at the first finished edition played, once.
  - A person whose only edition is running gets nothing.
- **veteran**
  - Tier 1 at the 3rd edition played, tier 2 at the 5th, and tier 3 at the 10th.
  - The editions need not be consecutive.
- **argonaut**
  - Playing the first finished edition gives it at that edition.
  - When the first finished edition has no roster (2020 with no players, then 2021 with players), nobody gets it.
  - A person who starts in the second edition does not get it.
- **ever-present**
  - Tier 1 at the 4th consecutive edition, tier 2 at the 6th, and tier 3 at the 8th.
  - After a break, a new run of 4 earns nothing new, since each tier is earned once.
- **homecoming**
  - Played 2021, missed 2022 and 2023, played 2024: earned in 2024.
  - Missing only one edition earns nothing.
  - Two comebacks earn it twice.
  - A first edition is not a comeback.
- **globetrotter**
  - Hosts "Paris", " paris " and "Nantes" give nothing, since matching ignores case and surrounding spaces.
  - Adding "Lyon" earns it at that edition, once.
  - A later fourth host earns nothing more.
  - « Orléans » and "Orleans" count as one host.

**Teammates.**
- **comrades**
  - Ana and Bob on the same team in three editions (not necessarily consecutive): both earn it at the third, Ana with `partner_id == bob.id` and Bob with `partner_id == ana.id`.
  - Two shared editions give nothing.
  - Being in the same edition on different teams gives nothing.
  - A fourth shared edition earns nothing more.
- **networker**
  - Seat Ana on 11-person teams: 10 new teammates in 2021 and 10 more in 2022 earn tier 1 in 2022.
  - Build the teammates in a loop.
  - Tiers 2 and 3 come at 40 and 60 distinct teammates.
  - Meeting the same people again adds nothing.

- [ ] **Step 2: Run them to see them fail**

Run: `python3 manage.py test olympic_warriors.tests.test_badges`

- [ ] **Step 3: Implement**

Add `from collections import Counter, defaultdict` and `from itertools import combinations` to the imports, and `_sort_key` to the import from `.profiles`. Then:

```python
VETERAN_TIERS = {3: 1, 5: 2, 10: 3}
EVER_PRESENT_TIERS = {4: 1, 6: 2, 8: 3}
NETWORKER_TIERS = ((20, 1), (40, 2), (60, 3))


def _loyalty(h):
    """rookie, veteran, argonaut, ever-present, homecoming and globetrotter: a
    participation is enough, team or rank not needed."""
    for user_id, seats in h.seats.items():
        played = run = 0
        seen = None
        hosts, present = set(), set()
        for i, edition in enumerate(h.sequence):
            if i not in seats:
                run = 0
                continue
            edition_id = edition.id
            played += 1
            run += 1
            if played == 1:
                yield Earned(user_id, C.ROOKIE, edition_id)
            if played in VETERAN_TIERS:
                yield Earned(user_id, C.VETERAN, edition_id, tier=VETERAN_TIERS[played])
            tier = EVER_PRESENT_TIERS.get(run)
            if tier and tier not in present:
                present.add(tier)
                yield Earned(user_id, C.EVER_PRESENT, edition_id, tier=tier)
            if seen is not None and i - seen > 2:  # missed at least 2 consecutive editions
                yield Earned(user_id, C.HOMECOMING, edition_id)
            seen = i
            host = _sort_key(edition.host.strip())
            if host not in hosts:
                hosts.add(host)
                if len(hosts) == 3:
                    yield Earned(user_id, C.GLOBETROTTER, edition_id)
        # The first finished edition is index 0 exactly when it has a roster.
        if 0 in seats and h.sequence[0].id == h.first_edition_id:
            yield Earned(user_id, C.ARGONAUT, h.first_edition_id)


def _teams(h, i):
    """{team id: sorted user ids} of the people seated on a valid team at sequence index i."""
    teams = defaultdict(list)
    for user_id, seats in h.seats.items():
        seat = seats.get(i)
        if seat is not None and seat.team_id is not None:
            teams[seat.team_id].append(user_id)
    return {team_id: sorted(users) for team_id, users in teams.items()}


def _teammates(h):
    """comrades (once per partner, both ways) and networker (tiers)."""
    together = Counter()
    mates = defaultdict(set)
    for i, edition in enumerate(h.sequence):
        edition_id = edition.id
        for users in _teams(h, i).values():
            for a, b in combinations(users, 2):
                together[(a, b)] += 1
                if together[(a, b)] == 3:
                    yield Earned(a, C.COMRADES, edition_id, partner_id=b)
                    yield Earned(b, C.COMRADES, edition_id, partner_id=a)
            for user_id in users:
                before = len(mates[user_id])
                mates[user_id].update(other for other in users if other != user_id)
                for threshold, tier in NETWORKER_TIERS:
                    if before < threshold <= len(mates[user_id]):
                        yield Earned(user_id, C.NETWORKER, edition_id, tier=tier)
```

Set `RULES = (_places, _streaks, _career, _loyalty, _teammates)`.

- [ ] **Step 4: Run the tests**, then **Step 5: Commit** (`[ADD] badges: loyalty and teammates`, staging the same two files).

---

### Task 6: The hall of fame (all-time tables)

**Files:**
- Modify: `server/olympic_warriors/badges.py`
- Modify: `server/olympic_warriors/tests/test_badges.py`

- [ ] **Step 1: Write the failing tests** (`TestHallOfFame`)

The table after edition i is the `/players` leaderboard built only from the editions up to i. Tables are read from the first index at which two editions have counted participations.
- **The first edition gives nothing.** A 2021 champion has no `goat` from the 2021 table alone. If a second edition exists where they are still 1st on places, `goat` comes in 2022.
- **goat**
  - Once, at the first table where the person is 1st, even when shared.
- **alone-at-the-top**
  - Needs the 1st position held by nobody else. Teammates tied 1st do not get it. Build a history where one person has more titles than every other.
- **hall-of-fame-podium and hall-of-famer**
  - Earned at the first table with a position of 3 or better, or 10 or better.
  - Someone at position 11 gets no `hall-of-famer`. With shared positions, seat enough people in separate teams.
- **reign**
  - 1st in 3 consecutive tables (2022, 2023, 2024) gives it in 2024.
  - Losing 1st, then 3 more tables at 1st, gives it again.
- **kingslayer**
  - Someone not 1st in the 2022 table and 1st in the 2023 table gets it in 2023.
  - A person 1st in every table never gets it.
  - The first table (2022) never gives it.
- **rocket**
  - The biggest climb between two consecutive tables, at the later one. Ties share it.
  - No climb at all gives no `rocket`.
  - Someone new in the later table has no previous position, so they do not count.

Assert positions with `profiles._place` rules in mind: identical places share a position.

- [ ] **Step 2: Implement**

Add `_place` and `_record` to the import from `.profiles`, then:

```python
def _tables(h):
    """
    (sequence index, {user id: position}) for every all-time table the hall of fame reads:
    the /players leaderboard built from the editions up to that index, from the first index
    at which two editions of the sequence have counted participations (the table after a
    single edition is only that edition's ranking, which the place badges cover).
    """
    with_counted = 0
    for i in range(len(h.sequence)):
        if any(i in seats and seats[i].counts for seats in h.seats.values()):
            with_counted += 1
        if with_counted < 2:
            continue
        records = []
        for user_id, seats in h.seats.items():
            parts = tuple(seats[j] for j in sorted(seats, reverse=True) if j <= i)
            if parts:
                records.append(_record(h.users[user_id], parts))
        yield i, {record.user_id: record.position for record in _place(records)}


FAME = ((C.HALL_OF_FAME_PODIUM, 3), (C.HALL_OF_FAMER, 10))


def _hall_of_fame(h):
    """goat, alone-at-the-top, hall-of-fame-podium and hall-of-famer (once each), reign
    (once per streak), kingslayer and rocket (at every table earned)."""
    reached = set()
    reign = Counter()
    previous = None
    for i, positions in _tables(h):
        edition_id = h.sequence[i].id
        leaders = [user_id for user_id, position in positions.items() if position == 1]
        for user_id, position in positions.items():
            if position is None:
                continue
            candidates = [(C.GOAT, position == 1), (C.ALONE_AT_THE_TOP, leaders == [user_id])]
            candidates += [(code, position <= top) for code, top in FAME]
            for code, holds in candidates:
                if holds and (user_id, code) not in reached:
                    reached.add((user_id, code))
                    yield Earned(user_id, code, edition_id)
        for user_id in h.seats:
            reign[user_id] = reign[user_id] + 1 if positions.get(user_id) == 1 else 0
            if reign[user_id] == 3:
                yield Earned(user_id, C.REIGN, edition_id)
        if previous is not None:
            for user_id in leaders:
                if previous.get(user_id) != 1:
                    yield Earned(user_id, C.KINGSLAYER, edition_id)
            climbs = {
                user_id: previous[user_id] - position
                for user_id, position in positions.items()
                if position is not None and previous.get(user_id) is not None
            }
            best = max(climbs.values(), default=0)
            if best >= 1:
                for user_id, climb in climbs.items():
                    if climb == best:
                        yield Earned(user_id, C.ROCKET, edition_id)
        previous = positions
```

Set `RULES = (_places, _streaks, _career, _loyalty, _teammates, _hall_of_fame)`.

- [ ] **Step 3: Run the tests**, then **Step 4: Commit** (`[ADD] badges: the hall of fame, from the all-time tables`).

---

### Task 7: Disciplines and the gods

**Files:**
- Modify: `server/olympic_warriors/badges.py`
- Modify: `server/olympic_warriors/tests/test_badges.py`

These rules read discipline ranks from `compute_standings`, so the tests need computed editions. Create teams **without** `final_rank` (`self.edition(year, size, ranked=False)`) and then disciplines, whose first save creates a `TeamResult` per active team. Set points with `TeamResult.objects.filter(discipline=d, team=t).update(points=p)` and `reveal_score=True`. A person seated on a team gets that team's discipline results.

- [ ] **Step 1: Write the failing tests** (`TestDisciplines`)

A helper in the class:

```python
    def results(self, discipline_model, edition, points, reveal=True):
        """A discipline of `edition` whose teams score `points` (a list, in team order)."""
        discipline = discipline_model.objects.create(edition=edition, reveal_score=reveal)
        for team, value in zip(Team.objects.filter(edition=edition).order_by("id"), points):
            TeamResult.objects.filter(discipline=discipline, team=team).update(points=value)
        return discipline
```

Cases (import `Relay`, `Darts`, `GeneralCultureQuizz`, `Rugby`, `Crossfit`, `Petanque`, and the others as needed):
- **The coverage test.** Every `Discipline` subclass is in `FAMILIES`, and in `KINDS` unless it is Fair. Create one of each: `for model in Discipline.__subclasses__(): model.objects.create(edition=e)`, then read `.name`. This makes adding a discipline without a god fail the suite.
- **specialist**
  - Winning Relay in 2021 and 2022 gives tier 1 in 2022 with `discipline == "Relay"`; tier 2 comes at the 3rd win and tier 3 at the 4th.
  - Winning Relay then Darts gives nothing.
- **all-rounder**
  - Tier 1 at the edition of the 3rd distinct discipline won.
  - Tiers 2 and 3 come at 5 and 8.
- **decathlete**
  - Podium in 10 distinct disciplines, spread over editions, gives it once.
- **brains-and-brawn**
  - Winning General Culture Quizz and Relay in one edition gives it.
  - Winning two physical disciplines does not.
  - Winning Fair and a quiz does not.
- **clean-sweep**
  - 3 wins in one edition give it; 2 do not.
- **metronome**
  - A podium in each of 4 ranked disciplines gives it.
  - It needs every ranked discipline: 4th in one of 5 means no.
  - It needs at least 4 ranked disciplines: podiums in all 3 of 3 means no.
  - A hidden discipline does not count as ranked.
- **uncrowned**
  - The most discipline wins (at least 2, none higher), but the team is not the edition's 1st: earned.
  - The edition's champion never gets it.
  - A tie on wins with another team still counts.
- **photo-finish**
  - A Rugby won on the points difference. With 3 teams A, B and C, one `TeamSportRound`, and played games A 20–0 C, B 5–0 C and A 0–0 B (each refereed by the third team), A and B both have 4 league points (`Game.save()` recomputes them) and A's difference is better. A gets `photo-finish` once for the edition. See `test_standings.py` for building games.
  - A computed edition won alone by exactly 1 total point is earned.
  - Winning by 2 points is not.
- **Hidden disciplines** (`reveal_score=False`) give no discipline badge and no god.
- **gods**
  - A Darts win gives `artemis` once, at the first win, and a second Darts win adds nothing.
  - Winning one discipline of each of the nine families gives `olympus` at the edition of the ninth.
  - Use the cheapest models: Relay (hermes), Darts (artemis), General Culture Quizz (athena), Blindtest (apollo), Crossfit (heracles), Orienteering (theseus), Rugby (ares, points set by hand without games), Hide and Seek (hades) and Fair (dionysus).
- **A hand-ranked edition with no results** gives no discipline badge.

- [ ] **Step 2: Implement**

Add `from .models import Badge, TeamResult` and `from .models.ResultTypes import ResultTypes`, then:

```python
MIND, PHYSICAL = "mind", "physical"

# The god of each discipline, by database name. Adding a discipline means picking its god
# here and its kind in KINDS: test_badges fails otherwise.
FAMILIES = {
    "General Culture Quizz": C.ATHENA,
    "Geography Quizz": C.ATHENA,
    "Geoguessr": C.ATHENA,
    "Burger Quizz": C.ATHENA,
    "Blindtest": C.APOLLO,
    "Dance": C.APOLLO,
    "Darts": C.ARTEMIS,
    "Petanque": C.ARTEMIS,
    "Disc Throw": C.ARTEMIS,
    "Frisbee": C.ARTEMIS,
    "Relay": C.HERMES,
    "Jumping Rope": C.HERMES,
    "Obstacle Course": C.HERMES,
    "Blindfolded Obstacle Course": C.HERMES,
    "Crossfit": C.HERACLES,
    "Orienteering": C.THESEUS,
    "Rugby": C.ARES,
    "Football": C.ARES,
    "Handball": C.ARES,
    "Basketball": C.ARES,
    "Volleyball": C.ARES,
    "Dodgeball": C.ARES,
    "Hide and Seek": C.HADES,
    "Fair": C.DIONYSUS,
}
GODS = tuple(dict.fromkeys(FAMILIES.values()))  # the nine, in catalogue order

# Mind or physical, for brains-and-brawn. Fair is neither.
KINDS = {
    name: MIND
    if name in {"General Culture Quizz", "Geography Quizz", "Geoguessr", "Burger Quizz", "Blindtest"}
    else PHYSICAL
    for name in FAMILIES
    if name != "Fair"
}

SPECIALIST_TIERS = {2: 1, 3: 2, 4: 3}
ALL_ROUNDER_TIERS = ((3, 1), (5, 2), (8, 3))


@dataclass(frozen=True)
class DisciplineResult:
    """A team's result in one discipline of a sequence edition, with its standing's rank
    (0 when hidden or unscored)."""

    team_id: int
    discipline_id: int
    name: str
    result_type: str
    points: int | None
    ranking: int


def _discipline_results(h):
    """{sequence index: [DisciplineResult]}: the active results of the sequence (1 query)."""
    index = {edition.id: i for i, edition in enumerate(h.sequence)}
    rows = TeamResult.objects.filter(
        discipline__edition_id__in=index,
        discipline__is_active=True,
        team__is_active=True,
        is_active=True,
    ).values_list(
        "id", "team_id", "discipline_id", "discipline__name", "discipline__edition_id",
        "discipline__result_type", "points",
    )
    results = defaultdict(list)
    for pk, team_id, discipline_id, name, edition_id, result_type, points in rows:
        i = index[edition_id]
        ranking = h.standings[i].result(pk).ranking
        results[i].append(
            DisciplineResult(team_id, discipline_id, name, result_type, points, ranking)
        )
    return results


def _disciplines(h):
    """specialist, all-rounder, decathlete, brains-and-brawn, clean-sweep, metronome,
    uncrowned, photo-finish, the gods and olympus."""
    if not h.sequence:
        return
    results = _discipline_results(h)
    for user_id, seats in h.seats.items():
        yield from _disciplines_of(h, results, user_id, seats)


def _disciplines_of(h, results, user_id, seats):
    won_times = Counter()
    won, podiums, gods = set(), set(), set()
    decathlete = False
    for i, edition in enumerate(h.sequence):
        seat = seats.get(i)
        if seat is None or seat.team_id is None:
            continue
        edition_id = edition.id
        rows = results.get(i, [])
        mine = [r for r in rows if r.team_id == seat.team_id]
        wins = [r for r in mine if r.ranking == 1]
        names = sorted({r.name for r in wins})

        for name in names:
            won_times[name] += 1
            tier = SPECIALIST_TIERS.get(won_times[name])
            if tier:
                yield Earned(user_id, C.SPECIALIST, edition_id, tier=tier, discipline=name)
        before = len(won)
        won.update(names)
        for threshold, tier in ALL_ROUNDER_TIERS:
            if before < threshold <= len(won):
                yield Earned(user_id, C.ALL_ROUNDER, edition_id, tier=tier)
        podiums.update(r.name for r in mine if 1 <= r.ranking <= 3)
        if not decathlete and len(podiums) >= 10:
            decathlete = True
            yield Earned(user_id, C.DECATHLETE, edition_id)

        kinds = {KINDS.get(name) for name in names}
        if MIND in kinds and PHYSICAL in kinds:
            yield Earned(user_id, C.BRAINS_AND_BRAWN, edition_id)
        if len(wins) >= 3:
            yield Earned(user_id, C.CLEAN_SWEEP, edition_id)
        ranked = {r.discipline_id for r in rows if r.ranking}
        on_podium = {r.discipline_id for r in mine if 1 <= r.ranking <= 3}
        if len(ranked) >= 4 and ranked <= on_podium:
            yield Earned(user_id, C.METRONOME, edition_id)
        if _uncrowned(rows, seat, wins):
            yield Earned(user_id, C.UNCROWNED, edition_id)
        if _photo_finish(h, i, rows, seat, wins):
            yield Earned(user_id, C.PHOTO_FINISH, edition_id)

        for name in names:
            god = FAMILIES.get(name)
            if god and god not in gods:
                gods.add(god)
                yield Earned(user_id, god, edition_id)
                if len(gods) == len(GODS):
                    yield Earned(user_id, C.OLYMPUS, edition_id)


def _uncrowned(rows, seat, wins):
    """The most discipline wins of the edition (at least 2, no team with more), without the
    title (the person's participation counts and is not 1st)."""
    per_team = Counter(r.team_id for r in rows if r.ranking == 1)
    rank = _rank(seat)
    return len(wins) >= 2 and len(wins) == max(per_team.values()) and rank not in (None, 1)


def _photo_finish(h, i, rows, seat, wins):
    """A points discipline won on the points-difference tie-breaker (a rank-2 result with the
    same points), or a computed edition won alone by 1 total point."""
    for win in wins:
        if win.result_type == ResultTypes.POINTS and any(
            r.discipline_id == win.discipline_id and r.ranking == 2 and r.points == win.points
            for r in rows
        ):
            return True
    if _rank(seat) != 1:
        return False
    teams = h.standings[i].teams
    mine = teams.get(seat.team_id)
    if mine is None or mine.total_points is None:  # hand-ranked: no totals
        return False
    leaders = [team_id for team_id, team in teams.items() if team.ranking == 1]
    others = [team.total_points for team_id, team in teams.items() if team_id != seat.team_id]
    return leaders == [seat.team_id] and bool(others) and mine.total_points - max(others) <= 1
```

Set `RULES = (_places, _streaks, _career, _loyalty, _teammates, _hall_of_fame, _disciplines)`.

- [ ] **Step 3: Run the tests**, then **Step 4: Commit** (`[ADD] badges: discipline badges and the gods`).

---

### Task 8: Games and the blindtest

**Files:**
- Modify: `server/olympic_warriors/badges.py`
- Modify: `server/olympic_warriors/tests/test_badges.py`

- [ ] **Step 1: Write the failing tests** (`TestGames`)

Build a computed edition with a Rugby discipline (`pairing_system` left at `NO`, so nothing is scheduled), one `TeamSportRound(discipline=rugby, order=1)`, and `Game` rows:
- `Game.objects.create(discipline=rugby, round=r, team1=a, team2=b, referees=c, edition=e, score1=12, score2=0, is_played=True)`;
- `reveal_score=True` on the Rugby, unless a case says otherwise.

Cases:
- **perfect-run and unbeaten**
  - 3 games, all won: `perfect-run` with `discipline == "Rugby"`, and no `unbeaten`.
  - 3 games, 2 won and 1 drawn: `unbeaten`.
  - 2 games, all won: nothing.
  - One loss: nothing.
- **A hidden discipline gives no game badge**, except `golden-whistle`.
- **Unplayed games, games of an inactive round and inactive games count for nothing.**
- **shutout**
  - Won 12 to 0: `shutout` once for the edition, even with two such games.
  - Won 12 to 3: nothing.
- **steamroller**
  - The winner of the biggest margin of the edition's revealed games gets it.
  - Two games tied on the biggest margin give it to both winners.
  - A draw never counts.
- **golden-whistle**
  - The person's teams refereed 5 played games over the editions: tier 1 at the edition reaching 5.
  - Tiers 2 and 3 come at 10 and 20.
  - Refereeing in a hidden discipline counts.
- **perfect-pitch**
  - Create a `Blindtest` for the edition (its save creates 10 rounds with a guess per team), with `reveal_score=True`.
  - Setting `is_artist_correct=True, is_song_correct=True` on every guess of one team earns it. Update through `BlindtestGuess.objects.filter(...).update(...)` to skip the points bookkeeping in `save()`.
  - One round with only the artist right: nothing.
  - A deactivated round is ignored.
  - A hidden blindtest gives nothing.

- [ ] **Step 2: Implement**

Add `BlindtestGuess` and `Game` to the `.models` import, then:

```python
GOLDEN_WHISTLE_TIERS = ((5, 1), (10, 2), (20, 3))


@dataclass(frozen=True)
class GameRow:
    discipline_name: str
    revealed: bool
    team1_id: int
    score1: int
    team2_id: int
    score2: int
    referees_id: int


@dataclass(frozen=True)
class GameFacts:
    """What one edition's games say about its teams."""

    records: dict  # team id -> {discipline name: (played, won, lost)}, revealed games only
    shutouts: frozenset
    steamrollers: frozenset
    refereed: dict  # team id -> games refereed, revealed or not


def _game_rows(h):
    """{sequence index: [GameRow]}: the active, played games of active rounds of active
    disciplines, the filter compute_standings uses (1 query)."""
    index = {edition.id: i for i, edition in enumerate(h.sequence)}
    rows = Game.objects.filter(
        discipline__edition_id__in=index,
        discipline__is_active=True,
        round__is_active=True,
        is_active=True,
        is_played=True,
    ).values_list(
        "discipline__edition_id", "discipline__name", "discipline__reveal_score",
        "team1_id", "score1", "team2_id", "score2", "referees_id",
    )
    games = defaultdict(list)
    for edition_id, *game in rows:
        games[index[edition_id]].append(GameRow(*game))
    return games


def _game_facts(games):
    records = defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))
    shutouts, margins, refereed = set(), [], Counter()
    for game in games:
        refereed[game.referees_id] += 1
        if not game.revealed:  # a badge never leaks a hidden score
            continue
        for team_id, mine, theirs in (
            (game.team1_id, game.score1, game.score2),
            (game.team2_id, game.score2, game.score1),
        ):
            record = records[team_id][game.discipline_name]
            record[0] += 1
            if mine > theirs:
                record[1] += 1
                margins.append((mine - theirs, team_id))
                if theirs == 0:
                    shutouts.add(team_id)
            elif mine < theirs:
                record[2] += 1
    best = max((margin for margin, _ in margins), default=0)
    return GameFacts(
        records={
            team_id: {name: tuple(r) for name, r in by_name.items()}
            for team_id, by_name in records.items()
        },
        shutouts=frozenset(shutouts),
        steamrollers=frozenset(team_id for margin, team_id in margins if margin == best),
        refereed=dict(refereed),
    )


def _perfect_pitch(h):
    """{sequence index: team ids} that found artist and song in every active round of a
    revealed, active blindtest (1 query)."""
    index = {edition.id: i for i, edition in enumerate(h.sequence)}
    rows = BlindtestGuess.objects.filter(
        blindtest_round__blindtest__edition_id__in=index,
        blindtest_round__blindtest__is_active=True,
        blindtest_round__blindtest__reveal_score=True,
        blindtest_round__is_active=True,
        is_active=True,
    ).values_list(
        "blindtest_round__blindtest__edition_id", "blindtest_round__blindtest_id",
        "blindtest_round_id", "team_id", "is_artist_correct", "is_song_correct",
    )
    rounds, found, edition_of = defaultdict(set), defaultdict(set), {}
    for edition_id, blindtest_id, round_id, team_id, artist, song in rows:
        rounds[blindtest_id].add(round_id)
        edition_of[blindtest_id] = index[edition_id]
        if artist and song:
            found[(blindtest_id, team_id)].add(round_id)
    teams = defaultdict(set)
    for (blindtest_id, team_id), rounds_found in found.items():
        if rounds_found == rounds[blindtest_id]:
            teams[edition_of[blindtest_id]].add(team_id)
    return teams


def _games(h):
    """unbeaten, perfect-run, shutout, steamroller, golden-whistle and perfect-pitch."""
    if not h.sequence:
        return
    games = _game_rows(h)
    pitch = _perfect_pitch(h)
    facts = [_game_facts(games.get(i, [])) for i in range(len(h.sequence))]
    for user_id, seats in h.seats.items():
        refereed = 0
        for i, edition in enumerate(h.sequence):
            seat = seats.get(i)
            if seat is None or seat.team_id is None:
                continue
            edition_id, team_id, fact = edition.id, seat.team_id, facts[i]
            for name, (played, won, lost) in sorted(fact.records.get(team_id, {}).items()):
                if played >= 3 and lost == 0:
                    code = C.PERFECT_RUN if won == played else C.UNBEATEN
                    yield Earned(user_id, code, edition_id, discipline=name)
            if team_id in fact.shutouts:
                yield Earned(user_id, C.SHUTOUT, edition_id)
            if team_id in fact.steamrollers:
                yield Earned(user_id, C.STEAMROLLER, edition_id)
            if team_id in pitch.get(i, ()):
                yield Earned(user_id, C.PERFECT_PITCH, edition_id)
            before = refereed
            refereed += fact.refereed.get(team_id, 0)
            for threshold, tier in GOLDEN_WHISTLE_TIERS:
                if before < threshold <= refereed:
                    yield Earned(user_id, C.GOLDEN_WHISTLE, edition_id, tier=tier)
```

Set `RULES = (_places, _streaks, _career, _loyalty, _teammates, _hall_of_fame, _disciplines, _games)`.

- [ ] **Step 3: Pin the query count.** Add to `test_badges.py`:

```python
# profiles._load (2 + 3 per sequence edition), then results, games and blindtest guesses.
BADGES_QUERIES = lambda editions: 5 + 3 * editions  # noqa: E731


class TestQueries(World, TestCase):
    def test_earned_runs_a_fixed_number_of_queries(self):
        for year in (2021, 2022, 2023):
            edition, teams = self.edition(year)
            self.seat(self.person(f"P{year}"), edition, teams[0])
        with self.assertNumQueries(BADGES_QUERIES(3)):
            earned(TODAY)
```

- [ ] **Step 4: Run the tests**, then **Step 5: Commit** (`[ADD] badges: game badges and the blindtest's perfect pitch`).

---

### Task 9: `refresh()` and the `refresh_badges` command

**Files:**
- Modify: `server/olympic_warriors/badges.py`
- Create: `server/olympic_warriors/management/commands/refresh_badges.py`
- Create: `server/olympic_warriors/tests/test_badge_refresh.py`

- [ ] **Step 1: Write the failing tests**

`test_badge_refresh.py` reuses `World` and `TODAY` from `test_badges` (`from olympic_warriors.tests.test_badges import TODAY, World`). Cases:
- **The first run stores what was earned.** A 4-team edition with four people: `refresh(TODAY)` stores their `champion`, `runner-up`, `bronze`, `wooden-spoon` and `rookie` rows as `is_manual=False`. The report's `added` equals the row count and `removed == 0`. `BadgeRefresh.objects.get(pk=1).refreshed_at` is set.
- **A second run writes nothing.** `added == removed == 0`, with the same row ids and `created_at`.
- **A correction deletes what is no longer earned.** Swap two teams' `final_rank`: the old `champion` row is gone and a new one exists for the new champion.
- **A revoked row stays revoked.** Set a computed row's `is_active=False`; after a refresh it is still inactive and still there.
- **Manual rows are untouched.** A manual `mvp` row survives, unchanged, with the same id.
- **Duplicates collapse.** Two computed rows with the same key and `partner=None` (the constraint allows it, see Task 1) end as one after a refresh.
- **The row comes back.** `BadgeRefresh.objects.all().delete()`, then `refresh()` works and recreates it.
- **The command.** `call_command("refresh_badges", stdout=out)` prints `Badges: N added, 0 removed, 0 kept.` and the refresh time. Use `today` via `mock.patch("olympic_warriors.badges.paris_today", return_value=TODAY)`.

- [ ] **Step 2: Implement**

Add to `badges.py` (imports: `from datetime import datetime`, `from django.db import transaction`, `from django.utils import timezone`, and `BadgeRefresh` from `.models`):

```python
@dataclass(frozen=True)
class RefreshReport:
    """What a refresh changed."""

    added: int
    removed: int
    kept: int
    refreshed_at: datetime


KEY_FIELDS = ("user_id", "code", "edition_id", "tier", "discipline", "partner_id")


def refresh(today=None):
    """
    Store earned(today) in the Badge table, in one transaction under the BadgeRefresh row
    lock: delete the computed rows no longer earned (active or not), bulk-create the new
    ones, and leave the others alone, so created_at and a revoked row's is_active survive.
    Manual rows are never read or written.
    """
    with transaction.atomic():
        BadgeRefresh.objects.get_or_create(pk=1)  # a flushed test database loses the row
        state = BadgeRefresh.objects.select_for_update().get(pk=1)
        wanted = {tuple(getattr(e, f) for f in KEY_FIELDS): e for e in earned(today)}
        stored = defaultdict(list)
        for pk, *key in Badge.objects.filter(is_manual=False).values_list("id", *KEY_FIELDS):
            stored[tuple(key)].append(pk)
        gone = [
            pk
            for key, pks in stored.items()
            for pk in (pks if key not in wanted else sorted(pks)[1:])
        ]
        new = [
            Badge(
                user_id=e.user_id, code=e.code, edition_id=e.edition_id, tier=e.tier,
                discipline=e.discipline, partner_id=e.partner_id,
            )
            for key, e in wanted.items()
            if key not in stored
        ]
        if gone:
            Badge.objects.filter(id__in=gone).delete()
        if new:
            Badge.objects.bulk_create(new)
        state.refreshed_at = timezone.now()
        state.save(update_fields=["refreshed_at"])
    return RefreshReport(
        added=len(new), removed=len(gone), kept=len(wanted) - len(new),
        refreshed_at=state.refreshed_at,
    )
```

Create `management/commands/refresh_badges.py`:

```python
"""
Recompute every computed badge and store the difference. The nightly host crontab runs it
(see CLAUDE.md, "Player badges").
"""

from django.core.management.base import BaseCommand

from olympic_warriors.badges import refresh


class Command(BaseCommand):
    help = "Recompute every computed badge and store the difference (the nightly cron job)."

    def handle(self, *args, **options):
        report = refresh()
        self.stdout.write(
            f"Badges: {report.added} added, {report.removed} removed, {report.kept} kept. "
            f"Refreshed at {report.refreshed_at.isoformat()}."
        )
```

- [ ] **Step 3: Run the tests**, then **Step 4: Commit** (`[ADD] badges: refresh() and the refresh_badges command`).

---

### Task 10: Admin, the Edition action, and the import hook

**Files:**
- Modify: `server/olympic_warriors/admin.py`
- Modify: `server/olympic_warriors/management/commands/import_edition.py`
- Modify: `server/olympic_warriors/tests/test_badge_refresh.py`

- [ ] **Step 1: Write the failing tests** (in `test_badge_refresh.py`; log in with `self.client.force_login(User.objects.create_superuser("admin", "a@b.c", "pw"))`, as `test_admin.py` does)
- **The Edition changelist action.** `POST /admin/olympic_warriors/edition/` with `{"action": "refresh_badges", "_selected_action": [edition.id]}` calls `refresh` once. Patch `olympic_warriors.admin.refresh` to return a `RefreshReport`, and show a message containing « Badges recalculés ».
- **The Badge changelist** answers 200. Its add page offers only the six manual codes as `code` options, and has no `tier`, `discipline` or `partner` field.
- **Adding through the admin** stores `is_manual=True`.
- **A computed row's change page** shows its fields read-only and only `is_active` editable. Posting `is_active` off saves it.
- **The import hook.**
  - A real `import_edition` calls `refresh` once, and a `--dry-run` does not.
  - Patch `olympic_warriors.management.commands.import_edition.import_edition` to return a minimal report: `{"year": 2024, "edition_id": 1, "users_reused": 0, "users_created": 0, "created_users": [], "counts": {}, "missing_files": []}`. Patch `...import_edition.refresh` too.
  - Pass the path of a temporary JSON file holding `{}`.

- [ ] **Step 2: Implement**

In `admin.py`, add `Badge` and `MANUAL_CODES` to the `.models` import and `from .badges import refresh`. Then:

```python
def refresh_badges(modeladmin, request, queryset):
    """Rebuild every computed badge: streaks and tables span editions, so the selection
    does not matter."""
    report = refresh()
    modeladmin.message_user(
        request,
        f"Badges recalculés : {report.added} ajoutés, {report.removed} retirés, "
        f"{report.kept} inchangés.",
    )


refresh_badges.short_description = "Recalculer les badges (toutes les éditions)"
```

Add `actions = [refresh_badges]` to `EditionAdmin`.

```python
class BadgeAdminForm(ModelForm):
    """A badge given by hand: only the manual codes. A computed row only edits is_active."""

    class Meta:
        model = Badge
        fields = ["user", "code", "edition", "note", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "code" in self.fields:
            self.fields["code"].choices = [
                (value, label) for value, label in Badge.Codes.choices if value in MANUAL_CODES
            ]


class BadgeAdmin(ModelAdmin):
    """Badges: computed ones are read-only but is_active (revoke), manual ones editable."""

    form = BadgeAdminForm
    list_display = ("user", "code", "edition", "tier", "discipline", "partner", "is_manual", "is_active")
    list_filter = ("code", "edition", "is_manual")
    search_fields = ("user__first_name", "user__last_name")
    list_select_related = ("user", "edition", "partner")

    COMPUTED_FIELDS = ("user", "code", "edition", "tier", "discipline", "partner", "is_active")
    MANUAL_FIELDS = ("user", "code", "edition", "note", "is_active")

    def get_fields(self, request, obj=None):
        return self.COMPUTED_FIELDS if obj is not None and not obj.is_manual else self.MANUAL_FIELDS

    def get_readonly_fields(self, request, obj=None):
        if obj is not None and not obj.is_manual:
            return self.COMPUTED_FIELDS[:-1]
        return ()

    def save_model(self, request, obj, form, change):
        if not change:
            obj.is_manual = True
        super().save_model(request, obj, form, change)

    def changelist_view(self, request, extra_context=None):
        return super().changelist_view(request_only_active(request), extra_context)
```

Register it with `site.register(Badge, BadgeAdmin)`. Match how the other `changelist_view` overrides call `request_only_active`: copy one of them exactly.

In `import_edition.py`, add `from olympic_warriors.badges import refresh`, and in the `else:` branch after the success line:

```python
            badges = refresh()
            self.stdout.write(
                f"Badges: {badges.added} added, {badges.removed} removed, {badges.kept} kept."
            )
```

- [ ] **Step 3: Run the tests** (`test_badge_refresh`, `test_admin`, `test_transfer`), then **Step 4: Commit** (`[ADD] badges: admin, the Edition refresh action, the import hook`).

---

### Task 11: `badges` on `GET /profile/<id>/`

**Files:**
- Modify: `server/olympic_warriors/badges.py` (`profile_badges`)
- Modify: `server/olympic_warriors/serializer.py`
- Modify: `server/olympic_warriors/views.py`
- Modify: `server/olympic_warriors/tests/test_profiles.py`

- [ ] **Step 1: Write the failing tests** (in `TestProfileEndpoints`, creating `Badge` rows directly)
- **An empty list.** A profile with no badge has `"badges": []`.
- **Grouping.** Two `champion` rows (2024, 2025) give one entry `{"code": "champion", "tier": 0, "years": [2024, 2025], "discipline": None, "partner": None}`.
- **Tiered rows.** Two `veteran` rows (tier 1 in 2024, tier 2 in 2025) give `tier: 2, years: [2024, 2025]`.
- **specialist** rows for Relay and Darts are two entries, Darts first (by name), `discipline: "Darts"`.
- **comrades** carries `partner: {"id", "first_name", "last_name"}`, with no username or email. The existing no-login test covers the whole payload.
- **Catalogue order.** `wooden-spoon` comes before `goat`, which comes before `mvp`, in the order of `Badge.Codes`.
- **Hidden rows.** Inactive rows and rows of an inactive edition are left out.
- **The query count.** The profile endpoint runs `PROFILES_QUERIES + 1`, and `/profiles/` stays at `PROFILES_QUERIES`. Update `test_both_endpoints_run_in_a_fixed_number_of_queries`.

- [ ] **Step 2: Implement**

In `badges.py`:

```python
CATALOGUE_ORDER = {code: n for n, code in enumerate(Badge.Codes.values)}


def profile_badges(user_id):
    """
    The person's active badges of active editions for GET /profile/<id>/ (1 query), grouped
    by (code, discipline, partner) in catalogue order: [{code, tier, years, discipline,
    partner}], `tier` the highest, `years` sorted, names only for the partner.
    """
    groups = {}
    rows = Badge.objects.filter(
        user_id=user_id, is_active=True, edition__is_active=True
    ).select_related("edition", "partner")
    for row in rows:
        partner = row.partner
        group = groups.setdefault(
            (row.code, row.discipline, row.partner_id),
            {
                "code": row.code,
                "tier": 0,
                "years": set(),
                "discipline": row.discipline or None,
                "partner": None
                if partner is None
                else {"id": partner.id, "first_name": partner.first_name, "last_name": partner.last_name},
            },
        )
        group["tier"] = max(group["tier"], row.tier)
        group["years"].add(row.edition.year)

    def order(badge):
        partner = badge["partner"] or {"last_name": "", "first_name": "", "id": 0}
        return (
            CATALOGUE_ORDER.get(badge["code"], len(CATALOGUE_ORDER)),
            _sort_key(badge["discipline"] or ""),
            _sort_key(partner["last_name"]),
            _sort_key(partner["first_name"]),
            partner["id"],
        )

    return sorted(({**g, "years": sorted(g["years"])} for g in groups.values()), key=order)
```

In `serializer.py`, above `ProfileSerializer`:

```python
class ProfileBadgePartnerSerializer(serializers.Serializer):
    """The other person of a comrades badge: names only."""

    id = serializers.IntegerField(help_text="The user id")
    first_name = serializers.CharField()
    last_name = serializers.CharField()


class ProfileBadgeSerializer(serializers.Serializer):
    """One badge on a profile: the rows of one (code, discipline, partner), see
    badges.profile_badges."""

    code = serializers.CharField()
    tier = serializers.IntegerField(help_text="0 untiered, 1 to 3 (bronze, silver, gold)")
    years = serializers.ListField(child=serializers.IntegerField(), help_text="Oldest first")
    discipline = serializers.CharField(allow_null=True)
    partner = ProfileBadgePartnerSerializer(allow_null=True)
```

and in `ProfileSerializer`:

```python
    badges = serializers.SerializerMethodField()

    @extend_schema_field(ProfileBadgeSerializer(many=True))
    def get_badges(self, obj):
        return ProfileBadgeSerializer(self.context.get("badges", []), many=True).data
```

In `views.py`, `getProfile` returns
`Response(ProfileSerializer(record, context={"badges": profile_badges(user_id)}).data)`,
with `from .badges import profile_badges`. Update the docstring of `ProfileSerializer` and the view's `extend_schema` summary to mention badges.

- [ ] **Step 3: Run** `test_profiles`, `test_routes` and `test_public_endpoints`, then the **whole server suite** once. Then **Step 4: Commit** (`[FEAT] profile: badges on GET /profile/<id>/`).

---

### Glyph tasks (12, 13, 14): shared brief

The 21 glyphs already in `front/src/lib/img/badges/` set the style; read five of them first. Also look at `/tmp/claude-0/-home-user-Olympic-Warriors/8b9660c0-f805-57d8-83b2-d95343823c44/scratchpad/badges/gen.py`, the generator that drew them.

The house style (`front/src/lib/img/icons/*.svg` follows it too):

```html
<svg width="2000" height="2000" viewBox="0 0 2000 2000" fill="none" xmlns="http://www.w3.org/2000/svg">
<!-- One line saying what the glyph shows. -->
<path d="..." stroke="white" stroke-width="120" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
```

- **Strokes.** White strokes 80 to 150 units wide (main outlines 110 to 150, details 70 to 100), with round caps and joins. Small solid parts are filled white.
- **Background.** None, no frame and no text: the badge component draws the ring.
- **Numerals.** Only where a row below says so, drawn as strokes.
- **Canvas.** Keep the drawing inside roughly 150 to 1850 on both axes, centred, and filling it like the existing glyphs: the frame shows the glyph at 60% of the badge.
- **Elements.** Only `path`, `circle`, `ellipse` and `g` (with `transform`), so the Design board can inline them.
- **Distinctness.** Each glyph must read on its own at 26px, and differ from its neighbours in the catalogue.
- **The five Olympic rings** are a protected symbol: never use them.

**Render check (required).** Write each glyph, then build a contact sheet and look at it:
- Write an HTML page that shows every new glyph in a 200px gold ring (`border: 5px solid #e6b800; border-radius: 50%`, glyph at 120px) and a 44px silver ring (glyph at 26px), on `#141414` tiles over `#000`. The existing sheet generator `.../scratchpad/badges/sheet.py` does exactly this for a folder.
- Screenshot it with `/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell --no-sandbox --allow-file-access-from-files --screenshot=<png> --window-size=1330,<height> file://<html>`, and open the PNG with the Read tool.
- Fix every glyph that does not read at a glance: wrong subject, clutter at 26px, or too small in the ring. Iterate until each one reads.
- Use your own file names in the scratchpad (`sheet-<task>.html` / `.png`), because other glyph tasks run at the same time.

**Do not commit.** Leave the SVG files in `front/src/lib/img/badges/` and report the contact sheet's PNG path. The controller reviews it and commits.

### Task 12: Glyphs, places to loyalty (14)

| File stem | Subject |
|---|---|
| `bronze` | A medal on a V ribbon with a 3, like `chocolate.svg` without the bite |
| `legend` | Zeus' thunderbolt: a bold zigzag bolt |
| `podium-regular` | A three-step podium with a circular loop arrow above it |
| `full-set` | Three round medals fanned out on their ribbons |
| `eternal-second` | A bicycle wheel (rim, hub, a few spokes) hanging from a medal's V ribbon |
| `janus` | Two faces in profile, back to back, sharing one head |
| `comeback` | A floor line with an arrow curving up out of it to the upper right |
| `on-the-rise` | Three stairs rising left to right, with an arrow going up them |
| `lucky-charm` | A four-leaf clover with a stem |
| `rookie` | An olive sprout: a short stem with two leaves, from a ground line |
| `argonaut` | The Argo from the side: a galley hull with a curled prow and a row of oars, **no sail** (so it differs from `homecoming`) |
| `ever-present` | A loom: a frame, vertical warp threads, and a shuttle across them |
| `globetrotter` | A globe (circle with meridian and parallels) with a map pin on it |
| `networker` | Five or six dots linked by lines, like a constellation |

### Task 13: Glyphs, hall of fame to the gods (14)

| File stem | Subject |
|---|---|
| `alone-at-the-top` | A mountain peak with a small flag on its summit |
| `hall-of-famer` | A single classical column (capital, fluted shaft, base) |
| `reign` | A throne seen from the front: tall back, seat, legs |
| `kingslayer` | A crown lying toppled on its side, with two short motion lines |
| `all-rounder` | A multi-tool or Swiss army knife with two or three blades fanned out |
| `decathlete` | A ten-pointed star |
| `brains-and-brawn` | A brain (left) and a flexed arm (right), side by side |
| `metronome` | A metronome: a tall trapezoid body with a pendulum arm tilted |
| `uncrowned` | A crown (like `dynasty.svg`) with a zigzag crack down its middle |
| `apollo` | Apollo's lyre: a U frame with curled arms, a crossbar and strings |
| `hermes` | A winged sandal: a sandal from the side with a wing at the heel |
| `heracles` | Heracles' club: a knotty club, thick end up, tilted |
| `theseus` | A square labyrinth seen from above (three or four nested walls with gaps) |
| `olympus` | A mountain with a small temple (pediment and columns) on its top |

### Task 14: Glyphs, the gods to the hand-given ones (14)

| File stem | Subject |
|---|---|
| `ares` | A Corinthian helmet from the side with a crest on top |
| `hades` | The same helmet drawn with **dashed** strokes (`stroke-dasharray`), the helm of invisibility |
| `dionysus` | A wine cup (kantharos: bowl, two handles, foot) |
| `unbeaten` | A heater shield (flat top, pointed bottom) |
| `perfect-run` | The same shield with a five-pointed star inside |
| `shutout` | A padlock, closed |
| `steamroller` | A road roller from the side: big front drum, cab, rear wheel |
| `perfect-pitch` | A tuning fork, with two small sound arcs |
| `mvp` | A five-pointed star under a small crown |
| `fair-play` | Two hands shaking |
| `hype` | A megaphone with three sound arcs |
| `costume` | A theatre mask (one face, eye holes, a smile) |
| `wounded` | An adhesive bandage (rounded strip, dotted pad), tilted |
| `torchbearer` | A torch: a handle, a cup, and a flame |

---

### Task 15: Front catalogue and dictionaries

**Files:**
- Create: `front/src/lib/badges.js`
- Create: `front/src/lib/badges.test.js`
- Modify: `front/src/lib/i18n/fr.js`
- Modify: `front/src/lib/i18n/en.js`

Depends on Tasks 12 to 14, since the test checks every glyph exists.

- [ ] **Step 1: Write the failing test** `front/src/lib/badges.test.js`:

```js
import { describe, expect, it } from 'vitest';
import fr from './i18n/fr.js';
import en from './i18n/en.js';
import { translator } from './i18n';
import { BADGES, badgeDetail, badgeGlyph, badgeMetal, hasGlyph, isKnownBadge, isTiered } from './badges.js';

/** Badge.Codes in server/olympic_warriors/models/Badge.py, in order. Keep in sync by hand. */
const BADGE_CODES = [
	'champion', 'runner-up', 'bronze', 'chocolate', 'wooden-spoon',
	'back-to-back', 'threepeat', 'dynasty', 'phoenix', 'legend', 'podium-regular', 'full-set',
	'eternal-second', 'janus', 'comeback', 'on-the-rise', 'icarus', 'lucky-charm',
	'rookie', 'veteran', 'argonaut', 'ever-present', 'homecoming', 'globetrotter',
	'comrades', 'networker',
	'goat', 'alone-at-the-top', 'hall-of-fame-podium', 'hall-of-famer', 'reign', 'kingslayer', 'rocket',
	'specialist', 'all-rounder', 'decathlete', 'brains-and-brawn', 'clean-sweep', 'metronome',
	'uncrowned', 'photo-finish',
	'athena', 'apollo', 'artemis', 'hermes', 'heracles', 'theseus', 'ares', 'hades', 'dionysus', 'olympus',
	'unbeaten', 'perfect-run', 'shutout', 'steamroller', 'golden-whistle', 'perfect-pitch',
	'mvp', 'fair-play', 'hype', 'costume', 'wounded', 'torchbearer'
];

const tEn = translator('en');
const tFr = translator('fr');

describe('badge catalogue', () => {
	it('mirrors Badge.Codes, in order', () => {
		expect(Object.keys(BADGES)).toEqual(BADGE_CODES);
	});

	it('gives every badge a metal', () => {
		for (const code of BADGE_CODES) {
			expect(['gold', 'silver', 'bronze', 'plain', 'tiers'], code).toContain(BADGES[code]);
		}
	});

	it('draws every badge but specialist, which borrows the discipline icon', () => {
		for (const code of BADGE_CODES.filter((c) => c !== 'specialist')) {
			expect(hasGlyph(code), code).toBe(true);
		}
	});

	it('names and explains every badge in both languages', () => {
		for (const code of BADGE_CODES) {
			for (const dict of [fr, en]) {
				expect(dict[`badge.${code}.name`], code).toEqual(expect.any(String));
				expect(dict[`badge.${code}.rule`], code).toEqual(expect.any(String));
			}
		}
	});
});

describe('badgeMetal', () => {
	it('is fixed, or picked by the tier', () => {
		expect(badgeMetal({ code: 'champion', tier: 0 })).toBe('gold');
		expect(badgeMetal({ code: 'wooden-spoon', tier: 0 })).toBe('plain');
		expect(['bronze', 'silver', 'gold'].map((m, i) => badgeMetal({ code: 'veteran', tier: i + 1 }))).toEqual([
			'bronze',
			'silver',
			'gold'
		]);
	});
});

describe('badgeGlyph', () => {
	it('is the badge glyph, or the discipline icon for specialist', () => {
		expect(badgeGlyph({ code: 'champion' })).toMatch(/badges\/champion\.svg$/);
		expect(badgeGlyph({ code: 'specialist', discipline: 'Rugby' })).toMatch(/icons\/rugby\.svg$/);
	});
});

describe('isKnownBadge and isTiered', () => {
	it('knows the catalogue only', () => {
		expect(isKnownBadge({ code: 'goat' })).toBe(true);
		expect(isKnownBadge({ code: 'future-badge' })).toBe(false);
		expect(isTiered('veteran')).toBe(true);
		expect(isTiered('champion')).toBe(false);
	});
});

describe('badgeDetail', () => {
	it('counts and lists the years of a repeated badge', () => {
		const champion = { code: 'champion', tier: 0, years: [2024, 2026], discipline: null, partner: null };
		expect(badgeDetail(champion, tEn, 'en')).toEqual(['×2', '2024', '2026']);
		expect(badgeDetail({ ...champion, years: [2025] }, tEn, 'en')).toEqual(['2025']);
	});

	it('gives the tier and the year it was reached', () => {
		const veteran = { code: 'veteran', tier: 2, years: [2024, 2026], discipline: null, partner: null };
		expect(badgeDetail(veteran, tEn, 'en')).toEqual(['Tier 2', '2026']);
		expect(badgeDetail(veteran, tFr, 'fr')).toEqual(['Niveau 2', '2026']);
	});

	it('names the discipline of a specialist, in French under fr', () => {
		const specialist = { code: 'specialist', tier: 1, years: [2026], discipline: 'Relay', partner: null };
		expect(badgeDetail(specialist, tEn, 'en')).toEqual(['Relay', 'Tier 1', '2026']);
		expect(badgeDetail(specialist, tFr, 'fr')).toEqual(['Relais', 'Niveau 1', '2026']);
	});

	it('leaves the partner of comrades to the page, keeping the year', () => {
		const comrades = { code: 'comrades', tier: 0, years: [2026], discipline: null, partner: { id: 12 } };
		expect(badgeDetail(comrades, tEn, 'en')).toEqual(['2026']);
	});
});
```

Run: `cd front && npx vitest run src/lib/badges.test.js`
Expected: fails on the missing module.

- [ ] **Step 2: Write `front/src/lib/badges.js`**

```js
import { iconFor } from './icons.js';
import { disciplineName } from './i18n';
import fallback from './img/icons/default.svg?url';

/**
 * The badge catalogue, in catalogue order (Badge.Codes on the server; badges.test.js
 * mirrors it): each code's metal, or 'tiers' when the tier picks it (1 bronze, 2 silver,
 * 3 gold). See the player badges design spec under docs/superpowers/specs/.
 */
export const BADGES = {
	champion: 'gold',
	'runner-up': 'silver',
	bronze: 'bronze',
	chocolate: 'plain',
	'wooden-spoon': 'plain',
	'back-to-back': 'gold',
	threepeat: 'gold',
	dynasty: 'gold',
	phoenix: 'gold',
	legend: 'gold',
	'podium-regular': 'silver',
	'full-set': 'gold',
	'eternal-second': 'silver',
	janus: 'plain',
	comeback: 'silver',
	'on-the-rise': 'bronze',
	icarus: 'plain',
	'lucky-charm': 'silver',
	rookie: 'plain',
	veteran: 'tiers',
	argonaut: 'gold',
	'ever-present': 'tiers',
	homecoming: 'plain',
	globetrotter: 'bronze',
	comrades: 'silver',
	networker: 'tiers',
	goat: 'gold',
	'alone-at-the-top': 'gold',
	'hall-of-fame-podium': 'silver',
	'hall-of-famer': 'bronze',
	reign: 'gold',
	kingslayer: 'gold',
	rocket: 'bronze',
	specialist: 'tiers',
	'all-rounder': 'tiers',
	decathlete: 'gold',
	'brains-and-brawn': 'silver',
	'clean-sweep': 'gold',
	metronome: 'gold',
	uncrowned: 'plain',
	'photo-finish': 'silver',
	athena: 'bronze',
	apollo: 'bronze',
	artemis: 'bronze',
	hermes: 'bronze',
	heracles: 'bronze',
	theseus: 'bronze',
	ares: 'bronze',
	hades: 'bronze',
	dionysus: 'bronze',
	olympus: 'gold',
	unbeaten: 'silver',
	'perfect-run': 'gold',
	shutout: 'bronze',
	steamroller: 'silver',
	'golden-whistle': 'tiers',
	'perfect-pitch': 'gold',
	mvp: 'gold',
	'fair-play': 'silver',
	hype: 'plain',
	costume: 'plain',
	wounded: 'plain',
	torchbearer: 'gold'
};

const TIER_METALS = ['bronze', 'silver', 'gold'];

/** Every SVG in ./img/badges, bundled; the file stem is the badge code. */
const files = import.meta.glob('./img/badges/*.svg', { eager: true, query: '?url', import: 'default' });
const glyphs = Object.fromEntries(
	Object.entries(files).map(([path, url]) => [path.slice('./img/badges/'.length, -'.svg'.length), url])
);

const hasOwn = (obj, key) => Object.prototype.hasOwnProperty.call(obj, key);

/** Whether the front knows this badge's code (a newer server may send one it does not). */
export const isKnownBadge = (badge) => hasOwn(BADGES, badge.code);

export const isTiered = (code) => BADGES[code] === 'tiers';

export const hasGlyph = (code) => hasOwn(glyphs, code);

/** 'gold' | 'silver' | 'bronze' | 'plain': the ring colour. */
export function badgeMetal(badge) {
	const metal = BADGES[badge.code];
	if (metal === 'tiers') return TIER_METALS[Math.min(Math.max(badge.tier, 1), 3) - 1];
	return metal ?? 'plain';
}

/** The glyph URL: the discipline's own icon for specialist. */
export function badgeGlyph(badge) {
	if (badge.code === 'specialist') return iconFor(badge.discipline ?? '');
	return glyphs[badge.code] ?? fallback;
}

/**
 * The text parts of a profile tile's detail line, which the page joins with ' · ':
 * a tiered badge gives [discipline (specialist only), 'Tier 2', year reached]; comrades
 * gives [year], the page writing the partner link before it; any other badge gives
 * ['×2', ...years] when earned more than once, else [year].
 */
export function badgeDetail(badge, t, locale) {
	const years = badge.years.map(String);
	if (isTiered(badge.code)) {
		const parts = [];
		if (badge.code === 'specialist' && badge.discipline) parts.push(disciplineName(locale, badge.discipline));
		parts.push(t('badge.level', { tier: badge.tier }));
		if (years.length) parts.push(years[years.length - 1]);
		return parts;
	}
	if (badge.code === 'comrades') return years.slice(-1);
	return years.length > 1 ? [t('badge.times', { n: years.length }), ...years] : years;
}
```

- [ ] **Step 3: Add the dictionary keys**

In `fr.js`, after the `profile.*` keys:

```js
	'profile.badges': 'Badges',
	'badge.level': 'Niveau {tier}',
	'badge.times': '×{n}',
	'badge.with': 'avec',
	'badge.champion.name': 'Champion',
	'badge.champion.rule': 'Gagner une édition',
	'badge.runner-up.name': 'Dauphin',
	'badge.runner-up.rule': "Finir 2e d'une édition",
	'badge.bronze.name': 'Bronze',
	'badge.bronze.rule': "Finir 3e d'une édition",
	'badge.chocolate.name': 'Médaille en chocolat',
	'badge.chocolate.rule': "Finir 4e d'une édition d'au moins 5 équipes",
	'badge.wooden-spoon.name': 'Cuillère de bois',
	'badge.wooden-spoon.rule': "Finir à la dernière place d'une édition d'au moins 4 équipes",
	'badge.back-to-back.name': 'Doublé',
	'badge.back-to-back.rule': 'Gagner deux éditions consécutives',
	'badge.threepeat.name': 'Triplé',
	'badge.threepeat.rule': 'Gagner trois éditions consécutives',
	'badge.dynasty.name': 'Dynastie',
	'badge.dynasty.rule': 'Gagner quatre éditions consécutives',
	'badge.phoenix.name': 'Phénix',
	'badge.phoenix.rule': "Regagner le titre après l'avoir perdu",
	'badge.legend.name': 'Légende',
	'badge.legend.rule': 'Gagner trois éditions',
	'badge.podium-regular.name': 'Abonné au podium',
	'badge.podium-regular.rule': 'Monter sur le podium trois éditions de suite',
	'badge.full-set.name': 'Collection complète',
	'badge.full-set.rule': "Décrocher l'or, l'argent et le bronze au fil des éditions",
	'badge.eternal-second.name': 'Poulidor',
	'badge.eternal-second.rule': 'Finir 2e deux fois sans avoir encore gagné',
	'badge.janus.name': 'Janus',
	'badge.janus.rule': 'Connaître la victoire et la dernière place',
	'badge.comeback.name': 'Remontada',
	'badge.comeback.rule': 'Monter sur le podium juste après une dernière place',
	'badge.on-the-rise.name': 'Ascension',
	'badge.on-the-rise.rule': 'Progresser au classement trois éditions de suite',
	'badge.icarus.name': 'Icare',
	'badge.icarus.rule': 'Tomber dans la seconde moitié juste après un titre',
	'badge.lucky-charm.name': 'Porte-bonheur',
	'badge.lucky-charm.rule': 'Monter sur le podium à ses trois premières éditions',
	'badge.rookie.name': 'Bizut',
	'badge.rookie.rule': 'Jouer sa première édition',
	'badge.veteran.name': 'Vétéran',
	'badge.veteran.rule': 'Jouer 3, 5 puis 10 éditions',
	'badge.argonaut.name': 'Argonaute',
	'badge.argonaut.rule': 'Avoir joué la toute première édition',
	'badge.ever-present.name': 'Pénélope',
	'badge.ever-present.rule': "Jouer 4, 6 puis 8 éditions d'affilée",
	'badge.homecoming.name': 'Ulysse',
	'badge.homecoming.rule': "Revenir après au moins deux éditions d'absence",
	'badge.globetrotter.name': 'Globe-trotteur',
	'badge.globetrotter.rule': 'Jouer dans trois villes différentes',
	'badge.comrades.name': "Compagnons d'armes",
	'badge.comrades.rule': "Partager l'équipe de la même personne trois fois",
	'badge.networker.name': 'Rassembleur',
	'badge.networker.rule': 'Jouer avec 20, 40 puis 60 coéquipiers différents',
	'badge.goat.name': 'G.O.A.T',
	'badge.goat.rule': 'Atteindre la 1re place du classement général',
	'badge.alone-at-the-top.name': 'Seul au sommet',
	'badge.alone-at-the-top.rule': 'Occuper seul la 1re place du classement général',
	'badge.hall-of-fame-podium.name': 'Podium du panthéon',
	'badge.hall-of-fame-podium.rule': 'Entrer dans le top 3 du classement général',
	'badge.hall-of-famer.name': 'Entrée au panthéon',
	'badge.hall-of-famer.rule': 'Entrer dans le top 10 du classement général',
	'badge.reign.name': 'Règne',
	'badge.reign.rule': 'Garder la 1re place du classement général trois éditions de suite',
	'badge.kingslayer.name': 'Régicide',
	'badge.kingslayer.rule': 'Prendre la 1re place du classement général',
	'badge.rocket.name': 'Fusée',
	'badge.rocket.rule': 'Faire la plus forte remontée du classement général après une édition',
	'badge.specialist.name': 'Spécialiste',
	'badge.specialist.rule': 'Gagner la même discipline 2, 3 puis 4 fois',
	'badge.all-rounder.name': 'Touche-à-tout',
	'badge.all-rounder.rule': 'Gagner 3, 5 puis 8 disciplines différentes',
	'badge.decathlete.name': 'Décathlonien',
	'badge.decathlete.rule': 'Monter sur le podium de 10 disciplines différentes',
	'badge.brains-and-brawn.name': 'Tête et jambes',
	'badge.brains-and-brawn.rule': "Gagner une épreuve de tête et une épreuve physique lors d'une même édition",
	'badge.clean-sweep.name': 'Razzia',
	'badge.clean-sweep.rule': "Gagner au moins trois disciplines lors d'une même édition",
	'badge.metronome.name': 'Métronome',
	'badge.metronome.rule': "Monter sur le podium de chaque discipline d'une édition",
	'badge.uncrowned.name': 'Sans couronne',
	'badge.uncrowned.rule': "Gagner le plus de disciplines sans gagner l'édition",
	'badge.photo-finish.name': 'Photo-finish',
	'badge.photo-finish.rule': "Gagner au départage, ou l'édition avec un point d'avance",
	'badge.athena.name': 'Athéna',
	'badge.athena.rule': 'Gagner un quiz, le Geoguessr ou le Burger Quiz',
	'badge.apollo.name': 'Apollon',
	'badge.apollo.rule': 'Gagner le blindtest ou la danse',
	'badge.artemis.name': 'Artémis',
	'badge.artemis.rule': "Gagner une épreuve d'adresse : fléchettes, pétanque, lancer de disque ou frisbee",
	'badge.hermes.name': 'Hermès',
	'badge.hermes.rule': "Gagner une course : relais, corde à sauter ou parcours d'obstacles",
	'badge.heracles.name': 'Héraclès',
	'badge.heracles.rule': 'Gagner le crossfit',
	'badge.theseus.name': 'Thésée',
	'badge.theseus.rule': "Gagner la course d'orientation",
	'badge.ares.name': 'Arès',
	'badge.ares.rule': 'Gagner un sport collectif',
	'badge.hades.name': 'Hadès',
	'badge.hades.rule': 'Gagner le cache-cache',
	'badge.dionysus.name': 'Dionysos',
	'badge.dionysus.rule': 'Gagner la fête foraine',
	'badge.olympus.name': 'Olympe',
	'badge.olympus.rule': 'Gagner une épreuve de chacun des neuf dieux',
	'badge.unbeaten.name': 'Invaincu',
	'badge.unbeaten.rule': "Ne perdre aucun match d'une discipline, sur trois au moins",
	'badge.perfect-run.name': 'Sans faute',
	'badge.perfect-run.rule': "Gagner tous les matchs d'une discipline, sur trois au moins",
	'badge.shutout.name': 'Cadenas',
	'badge.shutout.rule': 'Gagner un match sans encaisser de point',
	'badge.steamroller.name': 'Rouleau compresseur',
	'badge.steamroller.rule': "Gagner avec le plus large écart de l'édition",
	'badge.golden-whistle.name': "Sifflet d'or",
	'badge.golden-whistle.rule': 'Arbitrer 5, 10 puis 20 matchs',
	'badge.perfect-pitch.name': 'Oreille absolue',
	'badge.perfect-pitch.rule': 'Trouver artiste et titre à chaque manche du blindtest',
	'badge.mvp.name': 'MVP',
	'badge.mvp.rule': "Désigné MVP de l'édition",
	'badge.fair-play.name': 'Fair-play',
	'badge.fair-play.rule': "Prix du fair-play de l'édition",
	'badge.hype.name': 'Ambianceur',
	'badge.hype.rule': "Prix de l'ambiance de l'édition",
	'badge.costume.name': 'Plus beau déguisement',
	'badge.costume.rule': "Prix du plus beau déguisement de l'édition",
	'badge.wounded.name': 'Blessé de guerre',
	'badge.wounded.rule': "A tout donné, jusqu'à la blessure",
	'badge.torchbearer.name': 'Porteur de flamme',
	'badge.torchbearer.rule': "A organisé l'édition",
```

In `en.js`, the same keys:

```js
	'profile.badges': 'Badges',
	'badge.level': 'Tier {tier}',
	'badge.times': '×{n}',
	'badge.with': 'with',
	'badge.champion.name': 'Champion',
	'badge.champion.rule': 'Win an edition',
	'badge.runner-up.name': 'Runner-up',
	'badge.runner-up.rule': 'Finish 2nd in an edition',
	'badge.bronze.name': 'Bronze',
	'badge.bronze.rule': 'Finish 3rd in an edition',
	'badge.chocolate.name': 'Chocolate medal',
	'badge.chocolate.rule': 'Finish 4th in an edition of 5 teams or more',
	'badge.wooden-spoon.name': 'Wooden spoon',
	'badge.wooden-spoon.rule': 'Finish last in an edition of 4 teams or more',
	'badge.back-to-back.name': 'Back-to-back',
	'badge.back-to-back.rule': 'Win two consecutive editions',
	'badge.threepeat.name': 'Threepeat',
	'badge.threepeat.rule': 'Win three consecutive editions',
	'badge.dynasty.name': 'Dynasty',
	'badge.dynasty.rule': 'Win four consecutive editions',
	'badge.phoenix.name': 'Phoenix',
	'badge.phoenix.rule': 'Win the title again after losing it',
	'badge.legend.name': 'Legend',
	'badge.legend.rule': 'Win three editions',
	'badge.podium-regular.name': 'Podium regular',
	'badge.podium-regular.rule': 'Reach the podium in three consecutive editions',
	'badge.full-set.name': 'Full set',
	'badge.full-set.rule': 'Take gold, silver and bronze across editions',
	'badge.eternal-second.name': 'Eternal second',
	'badge.eternal-second.rule': 'Finish 2nd twice without a title yet',
	'badge.janus.name': 'Janus',
	'badge.janus.rule': 'Know both the title and the last place',
	'badge.comeback.name': 'Comeback',
	'badge.comeback.rule': 'Reach the podium right after a last place',
	'badge.on-the-rise.name': 'On the rise',
	'badge.on-the-rise.rule': 'Climb the ranking three editions in a row',
	'badge.icarus.name': 'Icarus',
	'badge.icarus.rule': 'Drop to the bottom half right after a title',
	'badge.lucky-charm.name': 'Lucky charm',
	'badge.lucky-charm.rule': 'Reach the podium in each of the first three editions',
	'badge.rookie.name': 'Rookie',
	'badge.rookie.rule': 'Play a first edition',
	'badge.veteran.name': 'Veteran',
	'badge.veteran.rule': 'Play 3, 5, then 10 editions',
	'badge.argonaut.name': 'Argonaut',
	'badge.argonaut.rule': 'Played the very first edition',
	'badge.ever-present.name': 'Ever-present',
	'badge.ever-present.rule': 'Play 4, 6, then 8 editions in a row',
	'badge.homecoming.name': 'Homecoming',
	'badge.homecoming.rule': 'Come back after missing two editions or more',
	'badge.globetrotter.name': 'Globetrotter',
	'badge.globetrotter.rule': 'Play in three different host cities',
	'badge.comrades.name': 'Comrades in arms',
	'badge.comrades.rule': 'Share a team with the same person three times',
	'badge.networker.name': 'Networker',
	'badge.networker.rule': 'Play alongside 20, 40, then 60 different teammates',
	'badge.goat.name': 'G.O.A.T',
	'badge.goat.rule': 'Reach 1st place in the all-time ranking',
	'badge.alone-at-the-top.name': 'Alone at the top',
	'badge.alone-at-the-top.rule': 'Hold 1st place in the all-time ranking alone',
	'badge.hall-of-fame-podium.name': 'Hall of fame podium',
	'badge.hall-of-fame-podium.rule': 'Reach the all-time top 3',
	'badge.hall-of-famer.name': 'Hall of famer',
	'badge.hall-of-famer.rule': 'Reach the all-time top 10',
	'badge.reign.name': 'Reign',
	'badge.reign.rule': 'Keep 1st place in the all-time ranking three editions in a row',
	'badge.kingslayer.name': 'Kingslayer',
	'badge.kingslayer.rule': 'Take 1st place in the all-time ranking',
	'badge.rocket.name': 'Rocket',
	'badge.rocket.rule': 'Make the biggest all-time climb after an edition',
	'badge.specialist.name': 'Specialist',
	'badge.specialist.rule': 'Win the same discipline 2, 3, then 4 times',
	'badge.all-rounder.name': 'All-rounder',
	'badge.all-rounder.rule': 'Win 3, 5, then 8 different disciplines',
	'badge.decathlete.name': 'Decathlete',
	'badge.decathlete.rule': 'Reach the podium in 10 different disciplines',
	'badge.brains-and-brawn.name': 'Brains and brawn',
	'badge.brains-and-brawn.rule': 'Win a mind discipline and a physical one in the same edition',
	'badge.clean-sweep.name': 'Clean sweep',
	'badge.clean-sweep.rule': 'Win three disciplines or more in one edition',
	'badge.metronome.name': 'Metronome',
	'badge.metronome.rule': 'Reach the podium in every discipline of an edition',
	'badge.uncrowned.name': 'Uncrowned',
	'badge.uncrowned.rule': 'Win the most disciplines but not the edition',
	'badge.photo-finish.name': 'Photo finish',
	'badge.photo-finish.rule': 'Win on the tie-breaker, or the edition by one point',
	'badge.athena.name': 'Athena',
	'badge.athena.rule': 'Win a quiz, the Geoguessr or the Burger Quiz',
	'badge.apollo.name': 'Apollo',
	'badge.apollo.rule': 'Win the blindtest or the dance',
	'badge.artemis.name': 'Artemis',
	'badge.artemis.rule': 'Win a precision discipline: darts, pétanque, disc throw or frisbee',
	'badge.hermes.name': 'Hermes',
	'badge.hermes.rule': 'Win a race: relay, jumping rope or an obstacle course',
	'badge.heracles.name': 'Heracles',
	'badge.heracles.rule': 'Win the crossfit',
	'badge.theseus.name': 'Theseus',
	'badge.theseus.rule': 'Win the orienteering',
	'badge.ares.name': 'Ares',
	'badge.ares.rule': 'Win a team sport',
	'badge.hades.name': 'Hades',
	'badge.hades.rule': 'Win hide and seek',
	'badge.dionysus.name': 'Dionysus',
	'badge.dionysus.rule': 'Win the fair',
	'badge.olympus.name': 'Mount Olympus',
	'badge.olympus.rule': 'Win a discipline of each of the nine gods',
	'badge.unbeaten.name': 'Unbeaten',
	'badge.unbeaten.rule': 'Lose no game of a discipline, three or more played',
	'badge.perfect-run.name': 'Perfect run',
	'badge.perfect-run.rule': 'Win every game of a discipline, three or more played',
	'badge.shutout.name': 'Shutout',
	'badge.shutout.rule': 'Win a game without conceding a point',
	'badge.steamroller.name': 'Steamroller',
	'badge.steamroller.rule': 'Win by the biggest margin of the edition',
	'badge.golden-whistle.name': 'Golden whistle',
	'badge.golden-whistle.rule': 'Referee 5, 10, then 20 games',
	'badge.perfect-pitch.name': 'Perfect pitch',
	'badge.perfect-pitch.rule': 'Name the artist and the song in every round of the blindtest',
	'badge.mvp.name': 'MVP',
	'badge.mvp.rule': "Named the edition's MVP",
	'badge.fair-play.name': 'Fair play',
	'badge.fair-play.rule': "The edition's fair play award",
	'badge.hype.name': 'Hype squad',
	'badge.hype.rule': "The edition's hype award",
	'badge.costume.name': 'Best costume',
	'badge.costume.rule': "The edition's best costume award",
	'badge.wounded.name': 'Walking wounded',
	'badge.wounded.rule': 'Gave everything, injury included',
	'badge.torchbearer.name': 'Torchbearer',
	'badge.torchbearer.rule': 'Organised the edition',
```

- [ ] **Step 4: Run** `npx vitest run src/lib/badges.test.js src/lib/i18n/parity.test.js`
Expected: all pass.

- [ ] **Step 5: Commit** `front/src/lib/badges.js`, `badges.test.js`, `fr.js` and `en.js` (`[FEAT] front: badge catalogue and dictionary keys`).

---

### Task 16: `Badge.svelte` and the profile's Badges section

**Files:**
- Create: `front/src/lib/components/Badge.svelte`
- Create: `front/src/lib/components/Badge.test.js`
- Modify: `front/src/routes/players/[id]/+page.svelte`
- Modify: `front/src/routes/players/[id]/page.test.js`
- Modify: `front/src/lib/fixtures/players.js`

- [ ] **Step 1: Fixtures.** In `players.js`, add to `profile`:

```js
	badges: [
		{ code: 'champion', tier: 0, years: [2024, 2026], discipline: null, partner: null },
		{ code: 'veteran', tier: 2, years: [2023, 2026], discipline: null, partner: null },
		{ code: 'comrades', tier: 0, years: [2026], discipline: null, partner: { id: 12, first_name: 'Léa', last_name: 'Martin' } },
		{ code: 'specialist', tier: 1, years: [2026], discipline: 'Relay', partner: null },
		{ code: 'future-badge', tier: 0, years: [2026], discipline: null, partner: null }
	]
```

Add `badges: []` to `profileUnranked`, and update the fixture's doc comment.

- [ ] **Step 2: Write the failing tests**

`front/src/lib/components/Badge.test.js`:

```js
import { describe, expect, it } from 'vitest';
import { renderWith } from '$lib/test-utils';
import Badge from './Badge.svelte';

describe('Badge', () => {
	it('draws the glyph in a ring of the metal, hidden from assistive tech', () => {
		const { container } = renderWith(Badge, { badge: { code: 'champion', tier: 0, years: [2024] } });
		const root = container.querySelector('[data-metal]');
		expect(root).toHaveAttribute('data-metal', 'gold');
		expect(root).toHaveAttribute('aria-hidden', 'true');
		expect(root.querySelector('img').getAttribute('src')).toMatch(/champion\.svg$/);
		expect(root.querySelector('img')).toHaveAttribute('alt', '');
		expect(root.querySelectorAll('.pip')).toHaveLength(0);
	});

	it('shows three pips for a tiered badge, the first `tier` lit, in the tier metal', () => {
		const { container } = renderWith(Badge, { badge: { code: 'veteran', tier: 2, years: [2026] } });
		expect(container.querySelector('[data-metal]')).toHaveAttribute('data-metal', 'silver');
		expect(container.querySelectorAll('.pip')).toHaveLength(3);
		expect(container.querySelectorAll('.pip.on')).toHaveLength(2);
	});

	it('borrows the discipline icon for a specialist', () => {
		const { container } = renderWith(Badge, {
			badge: { code: 'specialist', tier: 1, years: [2026], discipline: 'Rugby' }
		});
		expect(container.querySelector('img').getAttribute('src')).toMatch(/rugby\.svg$/);
	});
});
```

Add to `page.test.js`:

```js
	it('lists the badges with their detail and rule, skipping unknown codes', () => {
		renderWith(Page, { data: { profile } });

		expect(screen.getByRole('heading', { level: 2, name: 'Badges' })).toBeInTheDocument();
		const tiles = screen.getAllByTestId('badge');
		expect(tiles).toHaveLength(4);
		expect(tiles[0]).toHaveTextContent(/Champion\s*×2 · 2024 · 2026\s*Win an edition/);
		expect(tiles[1]).toHaveTextContent(/Veteran\s*Tier 2 · 2026\s*Play 3, 5, then 10 editions/);
		expect(tiles[2]).toHaveTextContent(/Comrades in arms\s*with\s*Léa Martin\s*·\s*2026/);
		expect(within(tiles[2]).getByRole('link', { name: 'Léa Martin' })).toHaveAttribute('href', '/players/12');
		expect(tiles[3]).toHaveTextContent(/Specialist\s*Relay · Tier 1 · 2026/);
		expect(screen.queryByText(/future-badge/)).toBeNull();
	});

	it('has no badges section without badges', () => {
		renderWith(Page, { data: { profile: profileUnranked } });
		expect(screen.queryByRole('heading', { level: 2, name: 'Badges' })).toBeNull();
		expect(screen.queryAllByTestId('badge')).toHaveLength(0);
	});
```

and extend the existing French test (`'speaks French under fr'`):

```js
		const tiles = screen.getAllByTestId('badge');
		expect(tiles[0]).toHaveTextContent(/Champion\s*×2 · 2024 · 2026\s*Gagner une édition/);
		expect(tiles[1]).toHaveTextContent(/Vétéran\s*Niveau 2 · 2026/);
		expect(tiles[2]).toHaveTextContent(/Compagnons d'armes\s*avec\s*Léa Martin/);
		expect(tiles[3]).toHaveTextContent(/Spécialiste\s*Relais · Niveau 1 · 2026/);
```

The existing tests check the headings and rows of the page. A new `h2` "Badges" appears before "Editions", so check that no existing assertion counts `h2`s. Adjust only if one does.

- [ ] **Step 3: Write `Badge.svelte`**

```svelte
<script>
	import { badgeGlyph, badgeMetal, isTiered } from '$lib/badges';

	/** A badge of the profile payload: { code, tier, years, discipline, partner }. */
	export let badge;

	$: metal = badgeMetal(badge);
	$: tiered = isTiered(badge.code);
</script>

<!-- Purely visual: the tile around it writes the name and, for a tiered badge, the tier. -->
<span class="badge {metal}" data-metal={metal} aria-hidden="true">
	<span class="medal"><img src={badgeGlyph(badge)} alt="" /></span>
	{#if tiered}
		<span class="pips">
			{#each [1, 2, 3] as n}
				<span class="pip" class:on={n <= badge.tier}></span>
			{/each}
		</span>
	{/if}
</span>

<style>
	/* `--badge-size` lets a page scale the medallion, as `--medal-size` does for MedalRank. */
	.badge {
		--size: var(--badge-size, 56px);
		display: inline-flex;
		flex-direction: column;
		align-items: center;
		gap: calc(var(--size) * 0.08);
	}

	.gold {
		--metal: var(--gold);
	}

	.silver {
		--metal: var(--silver);
	}

	.bronze {
		--metal: var(--bronze);
	}

	.plain {
		--metal: var(--accent);
	}

	.medal {
		position: relative;
		display: grid;
		place-items: center;
		width: var(--size);
		height: var(--size);
		border: max(2px, calc(var(--size) * 0.04)) solid var(--metal);
		border-radius: 50%;
	}

	/* The hairline inner ring, like a medal's rim. */
	.medal::after {
		content: '';
		position: absolute;
		inset: calc(var(--size) * 0.055);
		border: 1px solid var(--metal);
		border-radius: 50%;
		opacity: 0.35;
	}

	img {
		width: 60%;
		height: 60%;
	}

	.pips {
		display: flex;
		gap: calc(var(--size) * 0.06);
	}

	.pip {
		width: max(5px, calc(var(--size) * 0.07));
		aspect-ratio: 1;
		border-radius: 50%;
		background: var(--line);
	}

	.pip.on {
		background: var(--metal);
	}
</style>
```

- [ ] **Step 4: Add the section to the profile page**

In `front/src/routes/players/[id]/+page.svelte`, import `Badge` and `{ badgeDetail, isKnownBadge }` from `$lib/badges`, and add `$: badges = (profile.badges ?? []).filter(isKnownBadge);`. Insert between the counts paragraphs and the Editions `h2`:

```svelte
	{#if badges.length}
		<h2>{t('profile.badges')}</h2>
		<ul class="badges" role="list">
			{#each badges as badge}
				<li class="tile" data-testid="badge">
					<Badge {badge} />
					<span class="label name">{t(`badge.${badge.code}.name`)}</span>
					<span class="detail">
						{#if badge.partner}
							{t('badge.with')}
							<a href="/players/{badge.partner.id}">{fullName(badge.partner)}</a> ·
						{/if}
						{badgeDetail(badge, t, locale).join(' · ')}
					</span>
					<span class="rule">{t(`badge.${badge.code}.rule`)}</span>
				</li>
			{/each}
		</ul>
	{/if}
```

and styles:

```css
	.badges {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(9rem, 1fr));
		gap: 22px 16px;
		--badge-size: 56px;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.tile {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 6px;
		min-width: 0;
	}

	.name {
		color: var(--ink);
	}

	.detail {
		font-size: 0.85rem;
		color: var(--muted);
		overflow-wrap: anywhere;
	}

	.detail a {
		color: var(--accent);
	}

	.detail a:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
		border-radius: 2px;
	}

	.rule {
		font-size: 0.78rem;
		line-height: 1.35;
		color: var(--muted);
	}
```

- [ ] **Step 5: Run** `npx vitest run src/lib/components/Badge.test.js "src/routes/players/[id]/page.test.js"`, then `npm test` and `npm run build`.
Expected: all pass, and the build succeeds.

- [ ] **Step 6: Commit** the five files (`[FEAT] front: badges on the profile`).

---

### Task 17: Docs, full verification, and a look in the browser

**Files:**
- Modify: `CLAUDE.md`
- Modify: `docker-compose.prod.example.yml`
- Modify: `docs/superpowers/specs/2026-09-23-player-badges-design.md` (status line under the title: `> **Built 2026-09-23**, plan: docs/superpowers/plans/2026-09-23-player-badges.md.`)

- [ ] **Step 1: `CLAUDE.md`**

Add a **Player badges** paragraph after **Player profiles** in the backend section. It covers:
- `badges.py`: `earned(today)` from `profiles._load`, plus results, games and guesses, and `BADGES_QUERIES` = 5 + 3 per sequence edition.
- The sequence rule: finished active editions with at least one player, by year. The earned-at rule: playing more never removes a badge.
- `Badge` (migration `0033`): `Badge.Codes` is the catalogue in display order (63 codes). `MANUAL_CODES` are the six given by hand; `BadgeAdmin` offers only those and sets `is_manual`. A computed row is read-only except `is_active`, which revokes it, and the refresh keeps a revoked row.
- What `refresh()` does: the `BadgeRefresh` row lock, delete, `bulk_create`, keep, manual rows untouched, `refreshed_at`.
- Who calls it:
  - the nightly crontab line from the spec (02:00 UTC is after midnight in Paris);
  - the Edition changelist action « Recalculer les badges »;
  - a real `import_edition`.

  No page view writes.
- `FAMILIES` and `KINDS` match on discipline names.
- `GET /profile/<id>/` carries `badges` from `profile_badges`, one query more than `/profiles/`.
- The spec under `docs/superpowers/specs/`.

Add a 6th step to **Adding a discipline**: "Pick its god in `FAMILIES` and its kind in `KINDS` in `badges.py` (`test_badges.py` fails otherwise)."

In the front **Presentation** paragraph, replace the sentence about `front/src/lib/img/badges/` ("... not imported anywhere yet") with one covering:
- `src/lib/badges.js`: `BADGES`, code to metal or `tiers`, in `Badge.Codes` order and mirrored by `BADGE_CODES` in `badges.test.js`; `badgeGlyph`, with `specialist` borrowing the discipline icon; `badgeMetal`; `badgeDetail`; `isKnownBadge`;
- the glyphs in `src/lib/img/badges/<code>.svg`, in the house style with no frame;
- `Badge.svelte`, the `aria-hidden` medallion, sized by `--badge-size`, with tier pips;
- the profile tiles, with text shape `Champion ×2 · 2024 · 2026 Win an edition`. Add it to the text-shape list in the tests paragraph too.

- [ ] **Step 2: `docker-compose.prod.example.yml`.** Above the `server:` service's `command:` line, add:

```yaml
    # Badges are rebuilt nightly by a crontab entry on the host (see CLAUDE.md, "Player badges"):
    # 0 2 * * * cd <repo> && docker compose -f <this file> exec -T server python manage.py refresh_badges
```

- [ ] **Step 3: Full verification**
  - `cd server && python3 manage.py test`: every test passes.
  - `python3 manage.py makemigrations --check --dry-run`: no changes.
  - `cd front && npm test && npm run build`: both pass.
  - A look in the browser:
    - Run `python3 manage.py migrate` against the dev database and create a few editions, teams and players in a shell. `server/olympic_warriors/tests/test_badges.py`'s `World` shows how.
    - Run `python3 manage.py refresh_badges`, then serve the API with `python3 manage.py runserver 3003` and the front with `cd front && npm run dev`.
    - Screenshot `/players/<id>` at 390px and 1280px with the headless shell (see the glyph brief).
    - Check that the section reads well: tiles aligned, rings in the right metals, and the pips under tiered badges.

- [ ] **Step 4: Commit** the docs (`[DOCS] badges: CLAUDE.md, the cron line, the spec status`).

---

## Self-review notes (for the executor)

- **Spec coverage.** Every catalogue row maps to a rule in Tasks 3 to 8, or to the admin (Task 10). The storage, refresh, cron, admin action, import hook, payload, glyphs, component and profile section map to Tasks 1, 9, 10, 11, 12 to 16 and 17.
- **Decided while planning** (the spec already says so):
  - The sequence skips editions without a roster.
  - `argonaut` reads the first finished edition, roster or not.
  - `chocolate` is also refused when the 4th place is shared with the last one.
  - The tier is written in the tile's detail line (`Tier 2`), and `Badge.svelte` stays `aria-hidden`.
  - The keys are `badge.level`, `badge.times` and `badge.with`.
- **Order.**
  - Server Tasks 1 to 11 run one after the other. Tasks 3 to 8 build `badges.py` and `test_badges.py` up; each adds its rule to `RULES`.
  - The glyph Tasks 12 to 14 are independent of the server and of each other. They can run in parallel from the start, and do not commit.
  - Task 15 needs the glyphs; Task 16 needs Task 15; Task 17 comes last.
- **Names used across tasks:**
  - `Earned`, `History`, `history`, `earned`, `RULES`, `refresh`, `RefreshReport` and `profile_badges`;
  - `FAMILIES`, `KINDS`, `GODS` and `CATALOGUE_ORDER`;
  - `Badge.Codes`, `MANUAL_CODES` and `BadgeRefresh`;
  - `BADGES`, `badgeMetal`, `badgeGlyph`, `badgeDetail`, `isKnownBadge`, `isTiered` and `hasGlyph`.
