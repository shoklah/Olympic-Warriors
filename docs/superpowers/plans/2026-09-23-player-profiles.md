# Player Profiles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every person who played a public profile with their rank in each edition and their averages, plus an all-time players leaderboard at `/players`.

**Architecture:** A new `olympic_warriors/profiles.py` computes every person's participations, averages and leaderboard position from `compute_standings` (nothing is stored). Two public DRF endpoints serve it (`/profiles/`, `/profile/<user_id>/`). The SvelteKit front adds `/players` and `/players/<id>` outside the year segment, a Players nav item, a hub link and roster links on the team page. The admin gets `team` in `list_editable` and a `Player.clean()` that refuses cross-edition teams and duplicate rows.

**Tech Stack:** Django 4.2 + DRF (PostgreSQL, tests run in the compose `server` container), SvelteKit 2 / Svelte 4 (plain JS), Vitest + @testing-library/svelte.

**Spec:** `docs/superpowers/specs/2026-09-23-player-profiles-design.md`, the source of truth for the rules.

> **Executed 2026-09-23.** The code blocks below are the plan as written. Review rounds changed several details during execution (no rank for a computed edition with nothing ranked, `Participation.counts`, `PlayerInlineForm` on new teams, the leaderboard's `players.over` line, `fullName`, the loader's canonical-id check, the hub's `.actions` block). The spec, CLAUDE.md and the code are the reference; this plan is the build record.

---

## Conventions for whoever executes this

- Work on branch `claude/player-profiles` in the main checkout (`/Users/shoklah/Work/Playground/Olympic-Warriors`). Do not switch branches.
- The compose stack is running and mounts `./server` and `./front`, so the server container sees your edits immediately.
- Server tests: `docker compose exec server python manage.py test <dotted.path>`. They need Postgres, so never run them outside the container.
- Front tests: `cd front && npx vitest run <path>`; the whole front suite is `cd front && npm test`.
- Commit messages follow the repo style: `[ADD] ...`, `[FEAT] front: ...`, `[TEST] ...`, `[DOCS] ...`, each ending with the line `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Svelte markup stays sentence case; uppercase comes only from CSS (`.label`). Pages use the tokens from `front/src/routes/styles.css` and never hard-code colours.
- Every visible string goes through `t` (`useT()` at component init), with keys in both `front/src/lib/i18n/fr.js` and `en.js`.

## File map

Server:
- Create `server/olympic_warriors/profiles.py`: `paris_today`, `beaten_share`, `Participation`, `participations`, `PlayerRecord`, `leaderboard`.
- Create `server/olympic_warriors/tests/test_profiles.py`: the module and endpoint tests.
- Modify `server/olympic_warriors/serializer.py`: add `user` to `SummaryPlayerSerializer`; add `ProfileTeamSerializer`, `ProfileEditionSerializer`, `LeaderboardRowSerializer`, `ProfileSerializer`.
- Modify `server/olympic_warriors/views.py`: `getProfiles`, `getProfile`.
- Modify `server/olympic_warriors/urls.py`: two paths.
- Modify `server/olympic_warriors/models/Player.py`: `Player.clean()`.
- Modify `server/olympic_warriors/admin.py`: `TeamWithYearChoiceField`, `PlayerAdmin.list_editable`, `formfield_for_foreignkey`.
- Create `server/olympic_warriors/tests/test_player_admin.py`.
- Modify `server/olympic_warriors/tests/test_summary.py`: one test for `user`.

Front:
- Create `front/src/lib/players.js` and `front/src/lib/players.test.js`: formatters.
- Create `front/src/lib/fixtures/players.js`: leaderboard and profile payloads.
- Modify `front/src/lib/i18n/fr.js` and `front/src/lib/i18n/en.js`: new keys.
- Create `front/src/routes/players/+page.server.js`, `+page.svelte`, `page.server.test.js`, `page.test.js`.
- Create `front/src/routes/players/[id]/+page.server.js`, `+page.svelte`, `page.server.test.js`, `page.test.js`.
- Modify `front/src/lib/components/Header.svelte`, `TabBar.svelte`, `EditionHub.svelte` and their tests.
- Modify `front/src/routes/[year=year]/teams/[id]/+page.svelte` and its `page.test.js`.
- Modify `front/src/lib/fixtures/summary.js`: roster players gain `user`.

Docs:
- Modify `CLAUDE.md`.

---

### Task 1: `beaten_share` and the Paris date

**Files:**
- Create: `server/olympic_warriors/profiles.py`
- Create: `server/olympic_warriors/tests/test_profiles.py`

- [ ] **Step 1: Write the failing tests**

Create `server/olympic_warriors/tests/test_profiles.py`:

```python
"""
Tests for olympic_warriors.profiles: a person's editions, averages and leaderboard place,
computed from the edition standings, and the two public endpoints serving them.
"""

from datetime import date, datetime, timezone
from unittest import mock

from django.test import SimpleTestCase

from olympic_warriors.profiles import beaten_share, paris_today


class TestBeatenShare(SimpleTestCase):
    def test_first_beats_every_other_team_and_last_none(self):
        self.assertEqual(beaten_share(1, 6), 1.0)
        self.assertEqual(beaten_share(6, 6), 0.0)
        self.assertAlmostEqual(beaten_share(2, 8), 6 / 7)

    def test_no_share_without_a_rank_or_with_a_single_team(self):
        self.assertIsNone(beaten_share(None, 6))
        self.assertIsNone(beaten_share(1, 1))
        self.assertIsNone(beaten_share(1, 0))

    def test_clamped_when_a_hand_entered_rank_is_out_of_range(self):
        self.assertEqual(beaten_share(9, 6), 0.0)
        self.assertEqual(beaten_share(0, 6), 1.0)


class TestParisToday(SimpleTestCase):
    def test_is_the_calendar_day_in_paris_not_utc(self):
        instant = datetime(2026, 9, 20, 22, 30, tzinfo=timezone.utc)  # 00:30 on the 21st in Paris
        with mock.patch("olympic_warriors.profiles.datetime") as fake:
            fake.now.side_effect = lambda tz: instant.astimezone(tz)
            self.assertEqual(paris_today(), date(2026, 9, 21))
```

- [ ] **Step 2: Run the tests to check they fail**

Run: `docker compose exec server python manage.py test olympic_warriors.tests.test_profiles`
Expected: ERROR, `ModuleNotFoundError: No module named 'olympic_warriors.profiles'`.

- [ ] **Step 3: Write the minimal implementation**

Create `server/olympic_warriors/profiles.py`:

```python
"""
Player records across editions, from the team standings of each edition: a person's rank
in an edition is their team's rank, and nothing is stored.

The rules (see the player profiles design spec under docs/superpowers/specs/):
- a person is a user with an active Player in an active edition; one participation per
  (user, edition): the lowest id among the rows with a valid team (active, of the
  player's edition), else the lowest id;
- an edition is finished once its end_date is before today in Europe/Paris; an
  unfinished edition gives no rank, so its standings are not computed;
- a participation counts when finished, ranked, and the edition has at least 2 teams;
- the share beaten is (teams - rank) / (teams - 1), clamped to [0, 1];
- averages are over counted participations: mean rank to one decimal, mean share as a
  whole percentage;
- the leaderboard sorts ranked people by share, then mean rank, then counted editions,
  then name; equal (share, mean rank) pairs share a position; people with nothing
  counted follow by name, without a position.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")


def paris_today():
    """Today's calendar date where the event takes place; the server clock runs in UTC."""
    return datetime.now(PARIS).date()


def beaten_share(rank, teams):
    """Share of the other teams finished behind: 1.0 for first, 0.0 for last."""
    if rank is None or teams < 2:
        return None
    return min(1.0, max(0.0, (teams - rank) / (teams - 1)))
```

- [ ] **Step 4: Run the tests to check they pass**

Run: `docker compose exec server python manage.py test olympic_warriors.tests.test_profiles`
Expected: `Ran 4 tests` … `OK`.

- [ ] **Step 5: Commit**

```bash
git add server/olympic_warriors/profiles.py server/olympic_warriors/tests/test_profiles.py
git commit -m "[ADD] profiles: share of teams beaten and the Paris calendar date

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: `participations()`, one row per person and edition

**Files:**
- Modify: `server/olympic_warriors/profiles.py`
- Modify: `server/olympic_warriors/tests/test_profiles.py`

- [ ] **Step 1: Write the failing tests**

In `server/olympic_warriors/tests/test_profiles.py`, replace the import block at the top with:

```python
from datetime import date, datetime, timezone
from unittest import mock

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase

from olympic_warriors.models import Edition, Player, Relay, Team, TeamResult
from olympic_warriors.profiles import beaten_share, paris_today, participations

TODAY = date(2026, 9, 23)
# The editions query, the players query, then three per finished edition with players
# (2024 and 2025 in ProfilesSetup; 2026 is still running).
PROFILES_QUERIES = 2 + 3 * 2
```

Then append:

```python
class ProfilesSetup:
    """
    Three editions seen on TODAY (2026-09-23):
    - 2024, finished and hand-ranked: Aigles 1, Bisons 2, Cerfs 3, Daims 4;
    - 2025, finished and computed from a revealed Relay: Loups 1, Ours 2, Pumas 3;
    - 2026, running until 2026-09-30: Renards and Sangliers.
    People: Ana (Aigles, Loups, Renards), Bob (Bisons, Ours), Chloé (Loups), Dan (Cerfs),
    Eve (Sangliers only) and Fay (2024 without a team).
    """

    def setUp(self):
        self.y2024 = Edition.objects.create(
            year=2024, host="Nantes", start_date="2024-09-21", end_date="2024-09-22"
        )
        self.y2025 = Edition.objects.create(
            year=2025, host="Lyon", start_date="2025-09-20", end_date="2025-09-21"
        )
        self.y2026 = Edition.objects.create(
            year=2026, host="Paris", start_date="2026-09-22", end_date="2026-09-30"
        )
        self.aigles, self.bisons, self.cerfs, self.daims = [
            Team.objects.create(name=name, edition=self.y2024, final_rank=rank)
            for name, rank in [("Aigles", 1), ("Bisons", 2), ("Cerfs", 3), ("Daims", 4)]
        ]
        self.loups, self.ours, self.pumas = [
            Team.objects.create(name=name, edition=self.y2025) for name in ("Loups", "Ours", "Pumas")
        ]
        relay = Relay.objects.create(edition=self.y2025, reveal_score=True)
        for team, points in [(self.loups, 10), (self.ours, 5), (self.pumas, 0)]:
            TeamResult.objects.filter(discipline=relay, team=team).update(points=points)
        self.renards, self.sangliers = [
            Team.objects.create(name=name, edition=self.y2026) for name in ("Renards", "Sangliers")
        ]

        self.ana = self.person("Ana", "Lopez")
        self.bob = self.person("Bob", "Martin")
        self.chloe = self.person("Chloé", "Nguyen")
        self.dan = self.person("Dan", "Petit")
        self.eve = self.person("Eve", "Adam")
        self.fay = self.person("Fay", "Brun")
        self.play(self.ana, self.y2024, self.aigles)
        self.play(self.ana, self.y2025, self.loups)
        self.play(self.ana, self.y2026, self.renards)
        self.play(self.bob, self.y2024, self.bisons)
        self.play(self.bob, self.y2025, self.ours)
        self.play(self.chloe, self.y2025, self.loups)
        self.play(self.dan, self.y2024, self.cerfs)
        self.play(self.eve, self.y2026, self.sangliers)
        self.play(self.fay, self.y2024)

    @staticmethod
    def person(first_name, last_name):
        """A user whose login and email must never reach a public payload."""
        return User.objects.create(
            username=f"login-{first_name.lower()}",
            email=f"{first_name.lower()}@mail.example",
            first_name=first_name,
            last_name=last_name,
        )

    @staticmethod
    def play(user, edition, team=None, **kwargs):
        return Player.objects.create(user=user, edition=edition, team=team, rating=5, **kwargs)


def summary_of(parts):
    """(year, team name, rank, teams, finished) per participation, for compact asserts."""
    return [(p.year, p.team_name, p.rank, p.teams, p.finished) for p in parts]


class TestParticipations(ProfilesSetup, TestCase):
    def test_one_participation_per_edition_newest_first(self):
        user, parts = participations(TODAY)[self.ana.id]

        self.assertEqual(user, self.ana)
        self.assertEqual(
            summary_of(parts),
            [
                (2026, "Renards", None, 2, False),
                (2025, "Loups", 1, 3, True),
                (2024, "Aigles", 1, 4, True),
            ],
        )
        self.assertEqual(parts[1].team_id, self.loups.id)

    def test_computed_and_hand_ranked_editions_give_the_team_rank(self):
        _, parts = participations(TODAY)[self.bob.id]

        self.assertEqual(summary_of(parts), [(2025, "Ours", 2, 3, True), (2024, "Bisons", 2, 4, True)])

    def test_hand_ranked_team_without_final_rank_has_no_rank(self):
        elans = Team.objects.create(name="Élans", edition=self.y2024)
        gus = self.person("Gus", "Roy")
        self.play(gus, self.y2024, elans)

        _, parts = participations(TODAY)[gus.id]

        self.assertEqual(summary_of(parts), [(2024, "Élans", None, 5, True)])

    def test_an_edition_is_finished_from_the_day_after_its_end_date(self):
        _, on_the_last_day = participations(date(2026, 9, 30))[self.eve.id]
        _, the_day_after = participations(date(2026, 10, 1))[self.eve.id]

        self.assertEqual(summary_of(on_the_last_day), [(2026, "Sangliers", None, 2, False)])
        # Nothing revealed in 2026: both teams tie on 0 points, so both are 1st.
        self.assertEqual(summary_of(the_day_after), [(2026, "Sangliers", 1, 2, True)])

    def test_a_player_without_a_team_has_no_team_and_no_rank(self):
        _, parts = participations(TODAY)[self.fay.id]

        self.assertEqual(summary_of(parts), [(2024, None, None, 4, True)])
        self.assertIsNone(parts[0].team_id)

    def test_inactive_players_and_editions_drop_out_and_an_inactive_team_is_no_team(self):
        Player.objects.filter(user=self.chloe).update(is_active=False)
        Edition.objects.filter(pk=self.y2025.pk).update(is_active=False)
        Team.objects.filter(pk=self.cerfs.pk).update(is_active=False)

        result = participations(TODAY)

        self.assertNotIn(self.chloe.id, result)
        self.assertEqual([p.year for p in result[self.ana.id][1]], [2026, 2024])
        self.assertEqual(summary_of(result[self.dan.id][1]), [(2024, None, None, 3, True)])

    def test_a_team_of_another_edition_counts_as_no_team(self):
        gus = self.person("Gus", "Roy")
        self.play(gus, self.y2024, self.loups)  # objects.create skips Player.clean()

        _, parts = participations(TODAY)[gus.id]

        self.assertEqual(summary_of(parts), [(2024, None, None, 4, True)])

    def test_duplicate_rows_collapse_to_the_lowest_id_with_a_team(self):
        gus = self.person("Gus", "Roy")
        self.play(gus, self.y2024)
        self.play(gus, self.y2024, self.daims)
        self.play(gus, self.y2024, self.cerfs)

        _, parts = participations(TODAY)[gus.id]

        self.assertEqual(summary_of(parts), [(2024, "Daims", 4, 4, True)])

    def test_someone_who_never_played_is_absent(self):
        root = User.objects.create_superuser("root", "root@mail.example", "pw")

        self.assertNotIn(root.id, participations(TODAY))

    def test_standings_are_computed_for_finished_editions_with_players_only(self):
        # A finished edition nobody played in costs no standings queries.
        empty = Edition.objects.create(
            year=2023, host="Tours", start_date="2023-09-16", end_date="2023-09-17"
        )
        Team.objects.create(name="Vide", edition=empty)

        with self.assertNumQueries(PROFILES_QUERIES):
            participations(TODAY)
```

- [ ] **Step 2: Run the tests to check they fail**

Run: `docker compose exec server python manage.py test olympic_warriors.tests.test_profiles`
Expected: ERROR, `ImportError: cannot import name 'participations' from 'olympic_warriors.profiles'`.

- [ ] **Step 3: Write the implementation**

In `server/olympic_warriors/profiles.py`, replace the imports under the docstring with:

```python
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from django.db.models import Count, Q

from .models import Edition, Player
from .standings import compute_standings
```

and append to the end of the file:

```python
@dataclass(frozen=True)
class Participation:
    """One person's edition: their team, its rank among `teams` active teams, and whether
    the edition is over. rank is None without a team, before the end, or in a
    hand-ranked edition where the team has no final_rank."""

    year: int
    team_id: int | None
    team_name: str | None
    rank: int | None
    teams: int
    finished: bool

    @property
    def counted(self):
        """Whether the edition feeds the averages: over, ranked, and more than one team."""
        return self.finished and self.rank is not None and self.teams >= 2


def _valid_team(player):
    """The player's team when it is active and belongs to the player's edition."""
    team = player.team
    if team is None or not team.is_active or team.edition_id != player.edition_id:
        return None
    return team


def participations(today=None):
    """
    Every person's participations, newest edition first, keyed by user id:
    {user_id: (user, (Participation, ...))}.
    Queries: the editions, the players, then three per finished edition with a player.
    """
    today = today or paris_today()
    editions = {
        edition.id: edition
        for edition in Edition.objects.filter(is_active=True).annotate(
            team_count=Count("team", filter=Q(team__is_active=True))
        )
    }
    players = (
        Player.objects.filter(is_active=True, edition__is_active=True)
        .select_related("user", "team")
        .order_by("id")
    )

    chosen = {}  # (user id, edition id) -> the Player row that stands for it
    for player in players:
        key = (player.user_id, player.edition_id)
        kept = chosen.get(key)
        if kept is None or (_valid_team(kept) is None and _valid_team(player) is not None):
            chosen[key] = player

    finished = {pk for pk, edition in editions.items() if edition.end_date < today}
    played = {edition_id for _, edition_id in chosen}
    standings = {pk: compute_standings(editions[pk]) for pk in sorted(played & finished)}

    users = {}
    by_user = defaultdict(list)
    for (user_id, edition_id), player in chosen.items():
        edition = editions[edition_id]
        team = _valid_team(player)
        rank = None
        if team is not None and edition_id in standings:
            rank = standings[edition_id].team(team.id).ranking
        users[user_id] = player.user
        by_user[user_id].append(
            Participation(
                year=edition.year,
                team_id=team.id if team else None,
                team_name=team.name if team else None,
                rank=rank,
                teams=edition.team_count,
                finished=edition_id in finished,
            )
        )

    return {
        user_id: (users[user_id], tuple(sorted(parts, key=lambda p: p.year, reverse=True)))
        for user_id, parts in by_user.items()
    }
```

- [ ] **Step 4: Run the tests to check they pass**

Run: `docker compose exec server python manage.py test olympic_warriors.tests.test_profiles`
Expected: `Ran 14 tests` … `OK`.

If `test_standings_are_computed_for_finished_editions_with_players_only` reports a different count, print the queries (`from django.db import connection; from django.test.utils import CaptureQueriesContext`) and fix the code, not the constant. The expected count is two queries plus three per finished edition.

- [ ] **Step 5: Commit**

```bash
git add server/olympic_warriors/profiles.py server/olympic_warriors/tests/test_profiles.py
git commit -m "[ADD] profiles: one participation per person and edition, ranked from the standings

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: `leaderboard()`, averages and shared positions

**Files:**
- Modify: `server/olympic_warriors/profiles.py`
- Modify: `server/olympic_warriors/tests/test_profiles.py`

- [ ] **Step 1: Write the failing tests**

In `server/olympic_warriors/tests/test_profiles.py`, change the profiles import to:

```python
from olympic_warriors.profiles import beaten_share, leaderboard, paris_today, participations
```

and append:

```python
class TestLeaderboard(ProfilesSetup, TestCase):
    def rows(self, today=TODAY):
        return {record.first_name: record for record in leaderboard(today)}

    def test_averages_over_counted_editions_only(self):
        rows = self.rows()

        # Ana: 1st of 4 and 1st of 3; the running 2026 is played but not counted.
        self.assertEqual((rows["Ana"].played, rows["Ana"].counted), (3, 2))
        self.assertEqual((rows["Ana"].average_rank, rows["Ana"].average_beaten), (1.0, 100))
        # Bob: 2nd of 4 (2/3 beaten) and 2nd of 3 (1/2 beaten): 58%.
        self.assertEqual((rows["Bob"].average_rank, rows["Bob"].average_beaten), (2.0, 58))
        # Dan: 3rd of 4 (1/3 beaten).
        self.assertEqual((rows["Dan"].average_rank, rows["Dan"].average_beaten), (3.0, 33))

    def test_ranked_by_share_then_mean_rank_then_editions_with_shared_positions(self):
        order = [(record.first_name, record.position) for record in leaderboard(TODAY)]

        # Ana and Chloé tie on (100%, 1.0): shared 1st, Ana first for her 2 editions.
        # Then the not-ranked-yet group by last name: Adam (Eve), Brun (Fay).
        self.assertEqual(
            order,
            [("Ana", 1), ("Chloé", 1), ("Bob", 3), ("Dan", 4), ("Eve", None), ("Fay", None)],
        )

    def test_nothing_counted_means_no_figures_and_no_position(self):
        rows = self.rows()

        for name in ("Eve", "Fay"):
            self.assertEqual(rows[name].counted, 0)
            self.assertIsNone(rows[name].average_rank)
            self.assertIsNone(rows[name].average_beaten)
            self.assertIsNone(rows[name].position)
        self.assertEqual(rows["Eve"].played, 1)

    def test_an_edition_with_a_single_team_is_not_counted(self):
        solo_year = Edition.objects.create(
            year=2023, host="Tours", start_date="2023-09-16", end_date="2023-09-17"
        )
        solo = Team.objects.create(name="Solo", edition=solo_year, final_rank=1)
        gus = self.person("Gus", "Roy")
        self.play(gus, solo_year, solo)

        gus_row = self.rows()["Gus"]

        self.assertEqual((gus_row.played, gus_row.counted, gus_row.position), (1, 0, None))

    def test_the_running_edition_counts_once_it_is_over(self):
        rows = self.rows(date(2026, 10, 1))

        # 2026 had nothing revealed: Renards and Sangliers are both 1st of 2.
        self.assertEqual((rows["Eve"].counted, rows["Eve"].average_beaten), (1, 100))
        self.assertEqual((rows["Ana"].counted, rows["Ana"].average_rank), (3, 1.0))
```

- [ ] **Step 2: Run the tests to check they fail**

Run: `docker compose exec server python manage.py test olympic_warriors.tests.test_profiles`
Expected: ERROR, `ImportError: cannot import name 'leaderboard' from 'olympic_warriors.profiles'`.

- [ ] **Step 3: Write the implementation**

In `server/olympic_warriors/profiles.py`, change `from dataclasses import dataclass` to `from dataclasses import dataclass, replace`, then append:

```python
@dataclass(frozen=True)
class PlayerRecord:
    """A person's editions and averages, with their place on the leaderboard."""

    user_id: int
    first_name: str
    last_name: str
    participations: tuple[Participation, ...]
    counted: int
    average_rank: float | None
    average_beaten: int | None
    position: int | None = None

    @property
    def played(self):
        """Editions taken part in, finished or not."""
        return len(self.participations)


def _record(user, parts):
    """A person's record without a position: counted editions and their averages."""
    counted = [part for part in parts if part.counted]
    average_rank = average_beaten = None
    if counted:
        average_rank = round(sum(part.rank for part in counted) / len(counted), 1)
        shares = [beaten_share(part.rank, part.teams) for part in counted]
        average_beaten = round(100 * sum(shares) / len(shares))
    return PlayerRecord(
        user_id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        participations=parts,
        counted=len(counted),
        average_rank=average_rank,
        average_beaten=average_beaten,
    )


def _by_name(record):
    return (record.last_name.casefold(), record.first_name.casefold(), record.user_id)


def leaderboard(today=None):
    """
    Every person: the ranked ones in leaderboard order with their shared positions, then
    the ones with nothing counted yet, by name and without a position. Positions compare
    the rounded (share, mean rank) pair that the API returns.
    """
    records = [_record(user, parts) for user, parts in participations(today).values()]
    ranked = sorted(
        (record for record in records if record.counted),
        key=lambda r: (-r.average_beaten, r.average_rank, -r.counted, *_by_name(r)),
    )
    placed = []
    position, previous = None, None
    for index, record in enumerate(ranked, start=1):
        pair = (record.average_beaten, record.average_rank)
        if pair != previous:
            position, previous = index, pair
        placed.append(replace(record, position=position))
    waiting = sorted((record for record in records if not record.counted), key=_by_name)
    return placed + waiting
```

- [ ] **Step 4: Run the tests to check they pass**

Run: `docker compose exec server python manage.py test olympic_warriors.tests.test_profiles`
Expected: `Ran 19 tests` … `OK`.

- [ ] **Step 5: Commit**

```bash
git add server/olympic_warriors/profiles.py server/olympic_warriors/tests/test_profiles.py
git commit -m "[ADD] profiles: leaderboard with averages over finished editions and shared positions

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Public endpoints `/profiles/` and `/profile/<user_id>/`

**Files:**
- Modify: `server/olympic_warriors/serializer.py` (append at the end of the file)
- Modify: `server/olympic_warriors/views.py` (new `# Profiles` section before `# Editions`, around line 187)
- Modify: `server/olympic_warriors/urls.py` (after the `# players` block)
- Modify: `server/olympic_warriors/tests/test_profiles.py`

- [ ] **Step 1: Write the failing tests**

In `server/olympic_warriors/tests/test_profiles.py`, add `from rest_framework.test import APIClient` to the imports and append:

```python
class TestProfileEndpoints(ProfilesSetup, TestCase):
    def setUp(self):
        super().setUp()
        patcher = mock.patch("olympic_warriors.profiles.paris_today", return_value=TODAY)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client = APIClient()  # no credentials: both endpoints are public

    def test_leaderboard_is_public_and_ordered(self):
        response = self.client.get("/profiles/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [row["first_name"] for row in response.data],
            ["Ana", "Chloé", "Bob", "Dan", "Eve", "Fay"],
        )
        self.assertEqual(
            response.data[0],
            {
                "id": self.ana.id,
                "first_name": "Ana",
                "last_name": "Lopez",
                "played": 3,
                "counted": 2,
                "average_rank": 1.0,
                "average_beaten": 100,
                "position": 1,
            },
        )
        self.assertEqual(response.data[4]["position"], None)
        self.assertEqual(response.data[4]["average_rank"], None)

    def test_profile_lists_every_edition_newest_first(self):
        response = self.client.get(f"/profile/{self.ana.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {k: v for k, v in response.data.items() if k != "editions"},
            {
                "id": self.ana.id,
                "first_name": "Ana",
                "last_name": "Lopez",
                "position": 1,
                "counted": 2,
                "average_rank": 1.0,
                "average_beaten": 100,
            },
        )
        self.assertEqual(
            response.data["editions"],
            [
                {
                    "year": 2026,
                    "team": {"id": self.renards.id, "name": "Renards"},
                    "rank": None,
                    "teams": 2,
                    "finished": False,
                },
                {
                    "year": 2025,
                    "team": {"id": self.loups.id, "name": "Loups"},
                    "rank": 1,
                    "teams": 3,
                    "finished": True,
                },
                {
                    "year": 2024,
                    "team": {"id": self.aigles.id, "name": "Aigles"},
                    "rank": 1,
                    "teams": 4,
                    "finished": True,
                },
            ],
        )

    def test_profile_without_a_team_or_a_counted_edition(self):
        response = self.client.get(f"/profile/{self.fay.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["position"])
        self.assertIsNone(response.data["average_rank"])
        self.assertEqual(
            response.data["editions"],
            [{"year": 2024, "team": None, "rank": None, "teams": 4, "finished": True}],
        )

    def test_404_for_someone_who_never_played_and_for_an_unknown_id(self):
        root = User.objects.create_superuser("root", "root@mail.example", "pw")

        self.assertEqual(self.client.get(f"/profile/{root.id}/").status_code, 404)
        self.assertEqual(self.client.get("/profile/999999/").status_code, 404)

    def test_payloads_carry_no_login_name_or_email(self):
        for url in ("/profiles/", f"/profile/{self.ana.id}/"):
            content = self.client.get(url).content
            self.assertNotIn(b"login-", content)
            self.assertNotIn(b"mail.example", content)
            self.assertNotIn(b"username", content)
            self.assertNotIn(b"email", content)

    def test_both_endpoints_run_in_a_fixed_number_of_queries(self):
        with self.assertNumQueries(PROFILES_QUERIES):
            self.client.get("/profiles/")
        with self.assertNumQueries(PROFILES_QUERIES):
            self.client.get(f"/profile/{self.ana.id}/")
```

- [ ] **Step 2: Run the tests to check they fail**

Run: `docker compose exec server python manage.py test olympic_warriors.tests.test_profiles.TestProfileEndpoints`
Expected: FAIL, with the status code assertions showing `404 != 200` (the URLs don't exist yet).

- [ ] **Step 3: Add the serializers**

Append to `server/olympic_warriors/serializer.py`:

```python
class ProfileTeamSerializer(serializers.Serializer):
    """A participation's team."""

    id = serializers.IntegerField()
    name = serializers.CharField()


class ProfileEditionSerializer(serializers.Serializer):
    """One edition of a profile (a Participation); rank stays null until it is over."""

    year = serializers.IntegerField()
    team = serializers.SerializerMethodField()
    rank = serializers.IntegerField(allow_null=True)
    teams = serializers.IntegerField()
    finished = serializers.BooleanField()

    @extend_schema_field(ProfileTeamSerializer(allow_null=True))
    def get_team(self, obj):
        if obj.team_id is None:
            return None
        return {"id": obj.team_id, "name": obj.team_name}


class LeaderboardRowSerializer(serializers.Serializer):
    """
    A person on the all-time leaderboard (a PlayerRecord, see olympic_warriors.profiles).
    Public: names only, never the username (the login name) nor the email.
    """

    id = serializers.IntegerField(source="user_id")
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    played = serializers.IntegerField()
    counted = serializers.IntegerField()
    average_rank = serializers.FloatField(allow_null=True)
    average_beaten = serializers.IntegerField(allow_null=True)
    position = serializers.IntegerField(allow_null=True)


class ProfileSerializer(serializers.Serializer):
    """A person's profile: the leaderboard figures plus every edition, newest first."""

    id = serializers.IntegerField(source="user_id")
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    position = serializers.IntegerField(allow_null=True)
    counted = serializers.IntegerField()
    average_rank = serializers.FloatField(allow_null=True)
    average_beaten = serializers.IntegerField(allow_null=True)
    editions = ProfileEditionSerializer(source="participations", many=True)
```

- [ ] **Step 4: Add the views**

In `server/olympic_warriors/views.py`, add `LeaderboardRowSerializer` and `ProfileSerializer` to the `from .serializer import (...)` list, add this import below that block:

```python
from .profiles import leaderboard
```

and insert this section immediately before the `# Editions` comment:

```python
# Profiles


@extend_schema(
    summary="Every person who played, in all-time leaderboard order",
    description=(
        "Ranked people first by share of teams beaten (shared positions on ties), then "
        "the ones with no finished, ranked edition yet, by name and without a position."
    ),
    responses={
        "200": LeaderboardRowSerializer(many=True),
        "500": OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
@permission_classes([AllowAny])
def getProfiles(request):
    return Response(LeaderboardRowSerializer(leaderboard(), many=True).data)


@extend_schema(
    summary="One person's editions, averages and all-time position, by user id",
    responses={
        "200": ProfileSerializer,
        "404": OpenApiResponse(description="Player not found"),
        "500": OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
@permission_classes([AllowAny])
def getProfile(request, user_id):
    # The same leaderboard as /profiles/, so a profile can never disagree on a position.
    record = next((r for r in leaderboard() if r.user_id == user_id), None)
    if record is None:
        return Response({"error": "Player not found"}, status=404)
    return Response(ProfileSerializer(record).data)
```

`@permission_classes` must stay **below** `@api_view`. Placed above it, DRF 3.16+ raises a `TypeError` at import and the server won't boot.

- [ ] **Step 5: Wire the URLs**

In `server/olympic_warriors/urls.py`, after the line `path("players/team/<int:team_id>/", views.getPlayersByTeam),` add:

```python
    # profiles (public, by user id)
    path("profiles/", views.getProfiles),
    path("profile/<int:user_id>/", views.getProfile),
```

- [ ] **Step 6: Run the tests to check they pass**

Run: `docker compose exec server python manage.py test olympic_warriors.tests.test_profiles`
Expected: `Ran 25 tests` … `OK`.

- [ ] **Step 7: Check the schema still generates**

Run: `docker compose exec server python manage.py spectacular --file /tmp/schema.yml --validate`
Expected: the same totals as on `dev`, which already reports `Errors: 1` (about `createGameEvent`) and 3 warnings. Nothing new may mention `getProfiles`, `getProfile`, `ProfileSerializer` or `LeaderboardRowSerializer`.

- [ ] **Step 8: Commit**

```bash
git add server/olympic_warriors/serializer.py server/olympic_warriors/views.py server/olympic_warriors/urls.py server/olympic_warriors/tests/test_profiles.py
git commit -m "[ADD] public /profiles/ leaderboard and /profile/<user_id>/ endpoints

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Roster players carry their user id in the summary

**Files:**
- Modify: `server/olympic_warriors/serializer.py` (`SummaryPlayerSerializer`, around line 196)
- Modify: `server/olympic_warriors/tests/test_summary.py` (`TestEditionSummarySerializer`)

- [ ] **Step 1: Write the failing test**

In `server/olympic_warriors/tests/test_summary.py`, add to `class TestEditionSummarySerializer(SummarySetup, TestCase)`, right after `test_teams_in_name_order_with_active_roster`:

```python
    def test_roster_players_carry_their_user_id(self):
        aigles = self.summary()["teams"][0]
        users = {u.username: u.id for u in User.objects.filter(username__in=["ana", "bob"])}

        self.assertEqual([p["user"] for p in aigles["players"]], [users["ana"], users["bob"]])
```

- [ ] **Step 2: Run the test to check it fails**

Run: `docker compose exec server python manage.py test olympic_warriors.tests.test_summary.TestEditionSummarySerializer.test_roster_players_carry_their_user_id`
Expected: ERROR, `KeyError: 'user'`.

- [ ] **Step 3: Add the field**

In `server/olympic_warriors/serializer.py`, change `SummaryPlayerSerializer.Meta.fields` from `("id", "first_name", "last_name")` to:

```python
        fields = ("id", "user", "first_name", "last_name")
```

- [ ] **Step 4: Run the summary tests, including the query pin**

Run: `docker compose exec server python manage.py test olympic_warriors.tests.test_summary`
Expected: `OK`. `TestSummaryQueryCount` must still pass with `SUMMARY_QUERIES = 9`: `user` is the `user_id` column of rows that are already loaded.

- [ ] **Step 5: Commit**

```bash
git add server/olympic_warriors/serializer.py server/olympic_warriors/tests/test_summary.py
git commit -m "[ADD] summary: roster players carry their user id, for profile links

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: `Player.clean()` and team assignment in the Player changelist

**Files:**
- Modify: `server/olympic_warriors/models/Player.py`
- Modify: `server/olympic_warriors/admin.py` (imports, `PlayerInline` around line 89, and `PlayerAdmin` around line 116)
- Create: `server/olympic_warriors/tests/test_player_admin.py`

- [ ] **Step 1: Write the failing tests**

Create `server/olympic_warriors/tests/test_player_admin.py`:

```python
"""
Assigning teams to players: Player.clean() refuses a team of another edition and a second
active row for the same person and edition, and the Player changelist edits the team with
teams labelled by year.
"""

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from django.forms import inlineformset_factory

from olympic_warriors.admin import PlayerInlineForm
from olympic_warriors.models import Edition, Player, Team

CHANGELIST = "/admin/olympic_warriors/player/"


class PlayerSetup:
    def setUp(self):
        self.y2024 = Edition.objects.create(
            year=2024, host="Nantes", start_date="2024-09-21", end_date="2024-09-22"
        )
        self.y2026 = Edition.objects.create(
            year=2026, host="Paris", start_date="2026-09-19", end_date="2026-09-20"
        )
        self.mxm_2024 = Team.objects.create(name="MxM", edition=self.y2024)
        self.mxm_2026 = Team.objects.create(name="MxM", edition=self.y2026)
        self.ana = User.objects.create(username="ana", first_name="Ana", last_name="Lopez")
        self.player = Player.objects.create(user=self.ana, edition=self.y2026, rating=5)


class TestPlayerClean(PlayerSetup, TestCase):
    def test_a_team_of_the_same_edition_is_accepted(self):
        self.player.team = self.mxm_2026
        self.player.full_clean()

    def test_a_team_of_another_edition_is_refused_on_team(self):
        self.player.team = self.mxm_2024

        with self.assertRaises(ValidationError) as caught:
            self.player.full_clean()
        self.assertIn("team", caught.exception.message_dict)

    def test_a_second_active_row_for_the_same_person_and_edition_is_refused_on_team(self):
        second = Player(user=self.ana, edition=self.y2026, rating=5)

        with self.assertRaises(ValidationError) as caught:
            second.full_clean()
        self.assertIn("team", caught.exception.message_dict)

    def test_an_inactive_duplicate_and_another_edition_are_accepted(self):
        Player(user=self.ana, edition=self.y2026, rating=5, is_active=False).full_clean()
        Player(user=self.ana, edition=self.y2024, rating=5).full_clean()
        self.player.full_clean()  # the only active row of 2026 for Ana


@override_settings(STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage")
class TestPlayerChangelist(PlayerSetup, TestCase):
    def setUp(self):
        super().setUp()
        root = User.objects.create_superuser("root", "root@example.com", "pw")
        self.client.force_login(root)

    def save_team(self, team):
        return self.client.post(
            CHANGELIST,
            {
                "form-TOTAL_FORMS": "1",
                "form-INITIAL_FORMS": "1",
                "form-MIN_NUM_FORMS": "0",
                "form-MAX_NUM_FORMS": "1000",
                "form-0-id": str(self.player.id),
                "form-0-team": str(team.id),
                "_save": "Save",
            },
        )

    def test_team_is_editable_from_the_changelist(self):
        response = self.save_team(self.mxm_2026)

        self.assertEqual(response.status_code, 302)
        self.player.refresh_from_db()
        self.assertEqual(self.player.team, self.mxm_2026)

    def test_a_team_of_another_edition_shows_an_error_on_the_row(self):
        response = self.save_team(self.mxm_2024)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "belongs to another edition")
        self.player.refresh_from_db()
        self.assertIsNone(self.player.team)

    def test_team_choices_carry_their_year_newest_first(self):
        content = self.client.get(CHANGELIST).content.decode()

        self.assertIn("MxM (2026)", content)
        self.assertIn("MxM (2024)", content)
        self.assertLess(content.index("MxM (2026)"), content.index("MxM (2024)"))


class TestPlayerInlineForm(PlayerSetup, TestCase):
    """On the team page, `team` is the inline's hidden foreign key: its errors must still show."""

    def test_team_errors_show_among_the_row_errors(self):
        formset_class = inlineformset_factory(
            Team, Player, form=PlayerInlineForm, fields=["user", "edition", "rating", "is_active"]
        )
        formset = formset_class(
            {
                "player_set-TOTAL_FORMS": "1",
                "player_set-INITIAL_FORMS": "0",
                "player_set-MIN_NUM_FORMS": "0",
                "player_set-MAX_NUM_FORMS": "1000",
                "player_set-0-user": str(self.ana.id),
                "player_set-0-edition": str(self.y2026.id),
                "player_set-0-rating": "5",
                "player_set-0-is_active": "on",
            },
            instance=self.mxm_2026,
        )

        self.assertFalse(formset.is_valid())  # Ana already has an active 2026 player
        self.assertIn("already has an active player", str(formset.forms[0].non_field_errors()))
```

- [ ] **Step 2: Run the tests to check they fail**

Run: `docker compose exec server python manage.py test olympic_warriors.tests.test_player_admin`
Expected: ERROR at import, `ImportError: cannot import name 'PlayerInlineForm' from 'olympic_warriors.admin'`. To see the other failures before implementing, temporarily comment out that import and the `TestPlayerInlineForm` class:
- `test_a_team_of_another_edition_is_refused_on_team` and `test_a_second_active_row_for_the_same_person_and_edition_is_refused_on_team` fail with `ValidationError not raised`;
- the changelist POST tests fail, because there's no editable column yet;
- the label test fails, because the labels are just `MxM`.

Put the import and the class back before Step 3.

- [ ] **Step 3: Add `Player.clean()`**

In `server/olympic_warriors/models/Player.py`, add `from django.core.exceptions import ValidationError` to the imports, and add this method to `Player` below `__str__`:

```python
    def clean(self):
        """
        Refuse a team of another edition, and a second active row for the same person in
        the same edition. Both errors sit on `team`: it is the one field every admin form
        of a player shows (the changelist, the team inline, the change form), and an
        error on a field the form lacks makes Django raise ValueError instead of showing
        it. Imports insert without clean(), so they are not affected.
        """
        super().clean()
        if self.team_id is not None and self.edition_id is not None:
            if self.team.edition_id != self.edition_id:
                raise ValidationError({"team": "This team belongs to another edition."})
        if self.is_active and self.user_id is not None and self.edition_id is not None:
            duplicates = Player.objects.filter(
                user_id=self.user_id, edition_id=self.edition_id, is_active=True
            ).exclude(pk=self.pk)
            if duplicates.exists():
                raise ValidationError(
                    {"team": "This person already has an active player in this edition."}
                )
```

- [ ] **Step 4: Make the team editable in the changelist, labelled by year**

In `server/olympic_warriors/admin.py`, add `from django.forms import ModelChoiceField, ModelForm` below `from django.contrib.admin import ...`.

Replace `class PlayerInline` with:

```python
class PlayerInlineForm(ModelForm):
    """
    On the team page `team` is the inline's hidden foreign key, and the tabular inline
    never renders a hidden field's errors: repeat them among the row's errors, since
    Player.clean() puts its errors on `team`.
    """

    def non_field_errors(self):
        return self.error_class(
            [*super().non_field_errors(), *self.errors.get("team", [])], error_class="nonfield"
        )


class PlayerInline(TabularInline):
    """
    Inline for the Player model to be accessed from the Team model.
    """

    model = Player
    form = PlayerInlineForm
    extra = 1
```

Then add this class right above `class PlayerAdmin`:

```python
class TeamWithYearChoiceField(ModelChoiceField):
    """Team choices labelled with their year: team names repeat across editions."""

    def label_from_instance(self, obj):
        return f"{obj.name} ({obj.edition.year})"
```

In `PlayerAdmin`, add `list_editable = ["team"]` below `list_display`, and this method below `inlines`:

```python
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Teams labelled `name (year)`, newest edition first."""
        if db_field.name == "team":
            kwargs["queryset"] = Team.objects.select_related("edition").order_by(
                "-edition__year", "name"
            )
            kwargs["form_class"] = TeamWithYearChoiceField
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
```

- [ ] **Step 5: Run the new tests and the admin search test**

Run: `docker compose exec server python manage.py test olympic_warriors.tests.test_player_admin olympic_warriors.tests.test_admin`
Expected: `Ran 9 tests` … `OK` (8 in the new file, plus the changelist search test).

- [ ] **Step 6: Check no migration is needed**

Run: `docker compose exec server python manage.py makemigrations --check --dry-run`
Expected: `No changes detected`.

- [ ] **Step 7: Commit**

```bash
git add server/olympic_warriors/models/Player.py server/olympic_warriors/admin.py server/olympic_warriors/tests/test_player_admin.py
git commit -m "[ADD] admin: assign teams from the Player changelist; Player.clean() refuses cross-edition teams and duplicates

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Front formatters, dictionary keys and fixtures

**Files:**
- Create: `front/src/lib/players.js`
- Create: `front/src/lib/players.test.js`
- Create: `front/src/lib/fixtures/players.js`
- Modify: `front/src/lib/i18n/fr.js`, `front/src/lib/i18n/en.js`

- [ ] **Step 1: Write the failing tests**

Create `front/src/lib/players.test.js`:

```js
import { describe, expect, it } from 'vitest';
import { editionStatus, formatAverage, formatShare } from './players.js';

describe('formatAverage', () => {
	it('prints one decimal with the locale separator', () => {
		expect(formatAverage(2.5, 'en')).toBe('2.5');
		expect(formatAverage(2.5, 'fr')).toBe('2,5');
		expect(formatAverage(1, 'en')).toBe('1.0');
	});

	it('treats anything but en as French', () => {
		expect(formatAverage(1.5, 'de')).toBe('1,5');
	});

	it('dashes a missing average', () => {
		expect(formatAverage(null, 'en')).toBe('—');
	});
});

describe('formatShare', () => {
	it('prints a whole percentage, with a no-break space in French', () => {
		expect(formatShare(71, 'en')).toBe('71%');
		// Node 22's ICU puts U+00A0 (not the narrow U+202F) before % in French.
		expect(formatShare(71, 'fr')).toBe('71\u00a0%');
		expect(formatShare(0, 'en')).toBe('0%');
		expect(formatShare(100, 'en')).toBe('100%');
	});

	it('dashes a missing share', () => {
		expect(formatShare(null, 'fr')).toBe('—');
	});
});

describe('editionStatus', () => {
	it('is ranked when finished with a rank', () => {
		expect(editionStatus({ finished: true, rank: 2 })).toBe('ranked');
	});

	it('is in progress until the edition is over, whatever the rank', () => {
		expect(editionStatus({ finished: false, rank: null })).toBe('inProgress');
	});

	it('is unranked when over without a rank', () => {
		expect(editionStatus({ finished: true, rank: null })).toBe('unranked');
	});
});
```

- [ ] **Step 2: Run the tests to check they fail**

Run: `cd front && npx vitest run src/lib/players.test.js`
Expected: FAIL, `Failed to resolve import "./players.js"`.

- [ ] **Step 3: Write the formatters**

Create `front/src/lib/players.js`:

```js
/**
 * Formatting for the players leaderboard and profiles. Pure and locale-aware: anything
 * but `en` is French, like `t` and `ordinal`. A missing figure prints as a dash.
 */
const tag = (locale) => (locale === 'en' ? 'en' : 'fr');
const missing = (value) => value === null || value === undefined;

/** A mean rank with one decimal: 2.5 in English, 2,5 in French. */
export function formatAverage(value, locale) {
	if (missing(value)) return '—';
	return new Intl.NumberFormat(tag(locale), {
		minimumFractionDigits: 1,
		maximumFractionDigits: 1
	}).format(value);
}

/** A whole percentage (0 to 100): 71% in English, 71 % in French. */
export function formatShare(value, locale) {
	if (missing(value)) return '—';
	return new Intl.NumberFormat(tag(locale), { style: 'percent', maximumFractionDigits: 0 }).format(
		value / 100
	);
}

/** How a profile's edition row reads: ranked, still running, or over without a rank. */
export function editionStatus(participation) {
	if (!participation.finished) return 'inProgress';
	return participation.rank === null ? 'unranked' : 'ranked';
}
```

- [ ] **Step 4: Run the tests to check they pass**

Run: `cd front && npx vitest run src/lib/players.test.js`
Expected: `8 passed`.

- [ ] **Step 5: Add the dictionary keys**

In `front/src/lib/i18n/fr.js`, add after `'nav.photos': 'Photos',`:

```js
	'nav.players': 'Joueurs',
```

after `'hub.editions': 'Éditions',`:

```js
	'hub.players': 'Joueurs',
	'players.title': 'Joueurs',
	'players.subtitle': "Toutes éditions, par part d'équipes battues",
	'players.notRanked': 'Pas encore classés',
	'players.average': 'moy. {value}',
	'players.editions': { one: '{n} édition', other: '{n} éditions' },
	'profile.allTime': 'général',
	'profile.averageRank': 'Rang moyen',
	'profile.beaten': 'Équipes battues',
	'profile.counted': { one: '{n} classée', other: '{n} classées' },
	'profile.noRankedEdition': "Aucune édition classée pour l'instant",
	'profile.editions': 'Éditions',
	'profile.noTeam': "Pas d'équipe",
	'profile.inProgress': 'En cours',
```

In `front/src/lib/i18n/en.js`, add after `'nav.photos': 'Photos',`:

```js
	'nav.players': 'Players',
```

after `'hub.editions': 'Editions',`:

```js
	'hub.players': 'Players',
	'players.title': 'Players',
	'players.subtitle': 'All editions, by share of teams beaten',
	'players.notRanked': 'Not ranked yet',
	'players.average': 'avg {value}',
	'players.editions': { one: '{n} edition', other: '{n} editions' },
	'profile.allTime': 'all-time',
	'profile.averageRank': 'Average rank',
	'profile.beaten': 'Teams beaten',
	'profile.counted': { one: '{n} counted', other: '{n} counted' },
	'profile.noRankedEdition': 'No ranked edition yet',
	'profile.editions': 'Editions',
	'profile.noTeam': 'No team recorded',
	'profile.inProgress': 'In progress',
```

- [ ] **Step 6: Add the payload fixtures**

Create `front/src/lib/fixtures/players.js`:

```js
/**
 * Payloads of the public profile endpoints. `leaderboard` is /profiles/: two players
 * tied 1st, one 3rd, then two not ranked yet. `profile` is /profile/34/: a running
 * edition, two ranked ones and one without a team. `profileUnranked` has nothing counted.
 */
export const leaderboard = [
	{ id: 12, first_name: 'Léa', last_name: 'Martin', played: 2, counted: 2, average_rank: 1, average_beaten: 100, position: 1 },
	{ id: 7, first_name: 'Hugo', last_name: 'Maurinier', played: 1, counted: 1, average_rank: 1, average_beaten: 100, position: 1 },
	{ id: 34, first_name: 'Xavier', last_name: 'Baby', played: 4, counted: 2, average_rank: 2.5, average_beaten: 76, position: 3 },
	{ id: 40, first_name: 'Ana', last_name: 'Petit', played: 1, counted: 0, average_rank: null, average_beaten: null, position: null },
	{ id: 41, first_name: 'Jules', last_name: 'Roux', played: 2, counted: 0, average_rank: null, average_beaten: null, position: null }
];

export const profile = {
	id: 34,
	first_name: 'Xavier',
	last_name: 'Baby',
	position: 3,
	counted: 2,
	average_rank: 2.5,
	average_beaten: 76,
	editions: [
		{ year: 2030, team: { id: 40, name: 'Les Aigles' }, rank: null, teams: 4, finished: false },
		{ year: 2026, team: { id: 21, name: 'MxM' }, rank: 2, teams: 6, finished: true },
		{ year: 2024, team: null, rank: null, teams: 8, finished: true },
		{ year: 2023, team: { id: 5, name: 'Bisons' }, rank: 3, teams: 8, finished: true }
	]
};

export const profileUnranked = {
	id: 40,
	first_name: 'Ana',
	last_name: 'Petit',
	position: null,
	counted: 0,
	average_rank: null,
	average_beaten: null,
	editions: [{ year: 2030, team: { id: 41, name: 'Renards' }, rank: null, teams: 4, finished: false }]
};
```

- [ ] **Step 7: Run the dictionary parity tests and the helpers**

Run: `cd front && npx vitest run src/lib/i18n src/lib/players.test.js`
Expected: every test passes, including `parity.test.js`.

- [ ] **Step 8: Commit**

```bash
git add front/src/lib/players.js front/src/lib/players.test.js front/src/lib/fixtures/players.js front/src/lib/i18n/fr.js front/src/lib/i18n/en.js
git commit -m "[FEAT] front: player figure formatters, dictionary keys and profile fixtures

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: `/players`, the all-time leaderboard page

**Files:**
- Create: `front/src/routes/players/+page.server.js`
- Create: `front/src/routes/players/page.server.test.js`
- Create: `front/src/routes/players/+page.svelte`
- Create: `front/src/routes/players/page.test.js`

- [ ] **Step 1: Write the failing loader test**

Create `front/src/routes/players/page.server.test.js`:

```js
import { describe, expect, it, vi } from 'vitest';
import { load } from './+page.server.js';
import { leaderboard } from '$lib/fixtures/players.js';

vi.mock('$lib/server/urls', () => ({ api: (path) => `http://api${path}` }));

const json = (status, body) =>
	new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });

describe('players leaderboard load', () => {
	it('loads the leaderboard as the API orders it', async () => {
		const fetch = vi.fn(async () => json(200, leaderboard));

		const data = await load({ fetch });

		expect(fetch.mock.calls[0][0]).toBe('http://api/profiles/');
		expect(data.players).toEqual(leaderboard);
	});
});
```

- [ ] **Step 2: Write the failing page test**

Create `front/src/routes/players/page.test.js`:

```js
import { screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import { renderWith } from '$lib/test-utils';
import Page from './+page.svelte';
import { leaderboard } from '$lib/fixtures/players.js';

const data = { players: leaderboard };

describe('players leaderboard page', () => {
	it('ranks players by share beaten, ties sharing a position', () => {
		renderWith(Page, { data });

		expect(screen.getByRole('heading', { level: 1, name: 'Players' })).toBeInTheDocument();
		expect(screen.getByText('All editions, by share of teams beaten')).toBeInTheDocument();
		const rows = screen.getAllByTestId('player-row');
		expect(rows).toHaveLength(3);
		expect(rows[0]).toHaveTextContent(/1\s*Léa Martin\s*100%\s*avg 1\.0 · 2 editions/);
		expect(rows[1]).toHaveTextContent(/1\s*Hugo Maurinier\s*100%\s*avg 1\.0 · 1 edition/);
		expect(rows[2]).toHaveTextContent(/3\s*Xavier Baby\s*76%\s*avg 2\.5 · 2 editions/);
		expect(rows[0]).toHaveAttribute('href', '/players/12');
	});

	it('lists the players not ranked yet by name, with their editions and no position', () => {
		renderWith(Page, { data });

		expect(screen.getByRole('heading', { name: 'Not ranked yet' })).toBeInTheDocument();
		const rows = screen.getAllByTestId('unranked-row');
		expect(rows).toHaveLength(2);
		expect(rows[0]).toHaveTextContent(/Ana Petit\s*1 edition/);
		expect(rows[1]).toHaveTextContent(/Jules Roux\s*2 editions/);
		expect(rows[1]).toHaveAttribute('href', '/players/41');
	});

	it('has no not-ranked section when everyone is ranked', () => {
		renderWith(Page, { data: { players: leaderboard.slice(0, 3) } });

		expect(screen.queryByRole('heading', { name: 'Not ranked yet' })).toBeNull();
	});

	it('speaks French under fr', () => {
		renderWith(Page, { data }, 'fr');

		expect(screen.getByRole('heading', { level: 1, name: 'Joueurs' })).toBeInTheDocument();
		const rows = screen.getAllByTestId('player-row');
		expect(rows[2]).toHaveTextContent(/3\s*Xavier Baby\s*76\s%\s*moy\. 2,5 · 2 éditions/);
		expect(screen.getByRole('heading', { name: 'Pas encore classés' })).toBeInTheDocument();
	});
});
```

- [ ] **Step 3: Run the tests to check they fail**

Run: `cd front && npx vitest run src/routes/players`
Expected: FAIL, `Failed to resolve import "./+page.server.js"` and `"./+page.svelte"`.

- [ ] **Step 4: Write the loader**

Create `front/src/routes/players/+page.server.js`:

```js
import { apiGet } from '$lib/api';
import { api } from '$lib/server/urls';

/** The all-time leaderboard, in the order the API ranks it (the page never re-sorts). */
export const load = async ({ fetch }) => ({ players: await apiGet(fetch, api('/profiles/')) });
```

- [ ] **Step 5: Write the page**

Create `front/src/routes/players/+page.svelte`:

```svelte
<script>
	import MedalRank from '$lib/components/MedalRank.svelte';
	import { formatAverage, formatShare } from '$lib/players';
	import { useLocale, useT } from '$lib/i18n';

	export let data;

	const locale = useLocale();
	const t = useT();

	$: ranked = data.players.filter((player) => player.position !== null);
	$: waiting = data.players.filter((player) => player.position === null);
</script>

<div class="page">
	<h1>{t('players.title')}</h1>
	<p class="subtitle label">{t('players.subtitle')}</p>

	<ol class="list">
		{#each ranked as player}
			<li>
				<a
					class="row"
					class:gold={player.position === 1}
					class:silver={player.position === 2}
					class:bronze={player.position === 3}
					href="/players/{player.id}"
					data-testid="player-row"
				>
					<MedalRank rank={player.position} />
					<span class="name">{player.first_name} {player.last_name}</span>
					<span class="figures">
						<span class="num share">{formatShare(player.average_beaten, locale)}</span>
						<span class="detail"
							>{t('players.average', { value: formatAverage(player.average_rank, locale) })} · {t(
								'players.editions',
								{ n: player.counted }
							)}</span
						>
					</span>
				</a>
			</li>
		{/each}
	</ol>

	{#if waiting.length > 0}
		<h2 class="label">{t('players.notRanked')}</h2>
		<ul class="list">
			{#each waiting as player}
				<li>
					<a class="row waiting" href="/players/{player.id}" data-testid="unranked-row">
						<span class="name">{player.first_name} {player.last_name}</span>
						<span class="detail">{t('players.editions', { n: player.played })}</span>
					</a>
				</li>
			{/each}
		</ul>
	{/if}
</div>

<style>
	h1 {
		margin: 1.4rem 0 0.2rem;
	}

	.subtitle {
		margin: 0 0 1rem;
	}

	h2 {
		margin: 1.6rem 0 0.6rem;
	}

	.list {
		display: flex;
		flex-direction: column;
		gap: 6px;
		margin: 0 0 1.6rem;
		padding: 0;
		list-style: none;
	}

	.row {
		display: grid;
		grid-template-columns: 44px minmax(0, 1fr) auto;
		align-items: center;
		gap: 12px;
		--medal-size: 1.9rem;
		padding: 10px 12px;
		background: var(--bg-raised);
		border: 1px solid var(--line);
		border-left: 4px solid var(--line-strong);
		border-radius: var(--radius);
		color: var(--text);
		text-decoration: none;
		transition:
			transform 0.2s ease,
			background 0.2s ease;
	}

	.row.waiting {
		grid-template-columns: minmax(0, 1fr) auto;
	}

	.row:hover {
		background: var(--line);
		transform: translateY(-2px);
		text-decoration: none;
	}

	.row:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: -2px;
	}

	.row.gold {
		border-left-color: var(--gold);
	}

	.row.silver {
		border-left-color: var(--silver);
	}

	.row.bronze {
		border-left-color: var(--bronze);
	}

	.name {
		min-width: 0;
		font-weight: 600;
		overflow-wrap: anywhere;
	}

	.figures {
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		gap: 2px;
	}

	.share {
		font-size: 1.6rem;
		line-height: 1;
		letter-spacing: 0.06em;
	}

	.detail {
		font-size: 0.75rem;
		color: var(--muted);
		white-space: nowrap;
	}
</style>
```

- [ ] **Step 6: Run the tests to check they pass**

Run: `cd front && npx vitest run src/routes/players`
Expected: `5 passed`.

- [ ] **Step 7: Commit**

```bash
git add front/src/routes/players
git commit -m "[FEAT] front: /players, the all-time leaderboard

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: `/players/<id>`, the profile page

**Files:**
- Create: `front/src/routes/players/[id]/+page.server.js`
- Create: `front/src/routes/players/[id]/page.server.test.js`
- Create: `front/src/routes/players/[id]/+page.svelte`
- Create: `front/src/routes/players/[id]/page.test.js`

- [ ] **Step 1: Write the failing loader test**

Create `front/src/routes/players/[id]/page.server.test.js`:

```js
import { describe, expect, it, vi } from 'vitest';
import { load } from './+page.server.js';
import { profile } from '$lib/fixtures/players.js';

vi.mock('$lib/server/urls', () => ({ api: (path) => `http://api${path}` }));

const json = (status, body) =>
	new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });

describe('player profile load', () => {
	it('loads the profile of a numeric id', async () => {
		const fetch = vi.fn(async () => json(200, profile));

		const data = await load({ fetch, params: { id: '34' } });

		expect(fetch.mock.calls[0][0]).toBe('http://api/profile/34/');
		expect(data.profile).toEqual(profile);
	});

	it('answers 404 to anything but digits without calling the API', async () => {
		const fetch = vi.fn();

		for (const id of ['abc', '../admin', '12a', '']) {
			await expect(load({ fetch, params: { id } })).rejects.toMatchObject({ status: 404 });
		}
		expect(fetch).not.toHaveBeenCalled();
	});

	it("passes the API's 404 through", async () => {
		const fetch = vi.fn(async () => json(404, { error: 'Player not found' }));

		await expect(load({ fetch, params: { id: '999' } })).rejects.toMatchObject({ status: 404 });
	});
});
```

- [ ] **Step 2: Write the failing page test**

Create `front/src/routes/players/[id]/page.test.js`:

```js
import { screen, within } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import { renderWith } from '$lib/test-utils';
import Page from './+page.svelte';
import { profile, profileUnranked } from '$lib/fixtures/players.js';

describe('player profile page', () => {
	it('shows the name, the all-time position and the two figures', () => {
		renderWith(Page, { data: { profile } });

		expect(screen.getByRole('heading', { level: 1, name: 'Xavier Baby' })).toBeInTheDocument();
		const breadcrumb = screen.getByRole('navigation', { name: 'Breadcrumb' });
		expect(within(breadcrumb).getByRole('link', { name: 'Players' })).toHaveAttribute('href', '/players');
		const position = screen.getByTestId('position');
		expect(position).toHaveTextContent(/3\s*all-time/);
		expect(position).toHaveAttribute('href', '/players');
		expect(screen.getByTestId('average-rank')).toHaveTextContent(/Average rank\s*2\.5/);
		expect(screen.getByTestId('beaten')).toHaveTextContent(/Teams beaten\s*76%/);
		expect(screen.getByText('4 editions · 2 counted')).toBeInTheDocument();
		expect(screen.queryByText('No ranked edition yet')).toBeNull();
	});

	it('lists every edition newest first: running, ranked, without a team', () => {
		renderWith(Page, { data: { profile } });

		const rows = screen.getAllByTestId('edition-row');
		expect(rows).toHaveLength(4);
		expect(rows[0]).toHaveTextContent(/2030\s*Les Aigles\s*In progress/);
		expect(rows[1]).toHaveTextContent(/2026\s*MxM\s*2\s*\/ 6/);
		expect(rows[2]).toHaveTextContent(/2024\s*No team recorded\s*—/);
		expect(rows[3]).toHaveTextContent(/2023\s*Bisons\s*3\s*\/ 8/);
		expect(within(rows[1]).getByRole('link', { name: 'MxM' })).toHaveAttribute('href', '/2026/teams/21');
		expect(within(rows[1]).getByRole('link', { name: '2026' })).toHaveAttribute('href', '/2026');
		expect(within(rows[2]).queryAllByRole('link').map((a) => a.textContent.trim())).toEqual(['2024']);
	});

	it('dashes the figures and says so when nothing is counted yet', () => {
		renderWith(Page, { data: { profile: profileUnranked } });

		expect(screen.queryByTestId('position')).toBeNull();
		expect(screen.getByTestId('average-rank')).toHaveTextContent(/Average rank\s*—/);
		expect(screen.getByTestId('beaten')).toHaveTextContent(/Teams beaten\s*—/);
		expect(screen.getByText('No ranked edition yet')).toBeInTheDocument();
		expect(screen.getByText('1 edition · 0 counted')).toBeInTheDocument();
	});

	it('speaks French under fr', () => {
		renderWith(Page, { data: { profile } }, 'fr');

		expect(screen.getByTestId('position')).toHaveTextContent(/3\s*général/);
		expect(screen.getByTestId('average-rank')).toHaveTextContent(/Rang moyen\s*2,5/);
		expect(screen.getByTestId('beaten')).toHaveTextContent(/Équipes battues\s*76\s%/);
		expect(screen.getByText('4 éditions · 2 classées')).toBeInTheDocument();
		const rows = screen.getAllByTestId('edition-row');
		expect(rows[0]).toHaveTextContent(/2030\s*Les Aigles\s*En cours/);
		expect(rows[2]).toHaveTextContent(/2024\s*Pas d'équipe/);
	});
});
```

- [ ] **Step 3: Run the tests to check they fail**

Run: `cd front && npx vitest run "src/routes/players/[id]"`
Expected: FAIL, `Failed to resolve import "./+page.server.js"` and `"./+page.svelte"`.

- [ ] **Step 4: Write the loader**

Create `front/src/routes/players/[id]/+page.server.js`:

```js
import { error } from '@sveltejs/kit';
import { apiGet } from '$lib/api';
import { api } from '$lib/server/urls';

/**
 * One person's profile by user id. Only digits reach the API: the id is spliced into an
 * API path, and a decoded `..` could otherwise walk to another endpoint. The API's 404
 * (unknown id, or a user who never played) becomes the error page through apiGet.
 */
export const load = async ({ fetch, params }) => {
	if (!/^\d+$/.test(params.id)) error(404, 'No such player');
	return { profile: await apiGet(fetch, api(`/profile/${params.id}/`)) };
};
```

- [ ] **Step 5: Write the page**

Create `front/src/routes/players/[id]/+page.svelte`:

```svelte
<script>
	import Breadcrumb from '$lib/components/Breadcrumb.svelte';
	import MedalRank from '$lib/components/MedalRank.svelte';
	import { editionStatus, formatAverage, formatShare } from '$lib/players';
	import { useLocale, useT } from '$lib/i18n';

	export let data;

	const locale = useLocale();
	const t = useT();

	$: profile = data.profile;
	$: name = `${profile.first_name} ${profile.last_name}`;
</script>

<div class="page">
	<Breadcrumb items={[{ label: t('players.title'), href: '/players' }, { label: name }]} />
	<h1>{name}</h1>

	{#if profile.position !== null}
		<!-- A plain number: a French ordinal would have to guess the player's gender. -->
		<a class="position" href="/players" data-testid="position">
			<MedalRank rank={profile.position} />
			<span class="label">{t('profile.allTime')}</span>
		</a>
	{/if}

	<!-- Two figures at the same size: neither is the headline. -->
	<div class="figures">
		<div class="figure" data-testid="average-rank">
			<span class="label">{t('profile.averageRank')}</span>
			<span class="num value">{formatAverage(profile.average_rank, locale)}</span>
		</div>
		<div class="figure" data-testid="beaten">
			<span class="label">{t('profile.beaten')}</span>
			<span class="num value">{formatShare(profile.average_beaten, locale)}</span>
		</div>
	</div>

	<p class="counts">
		{t('players.editions', { n: profile.editions.length })} · {t('profile.counted', {
			n: profile.counted
		})}
	</p>
	{#if profile.counted === 0}
		<p class="counts">{t('profile.noRankedEdition')}</p>
	{/if}

	<h2>{t('profile.editions')}</h2>
	<ul class="editions">
		{#each profile.editions as edition}
			{@const status = editionStatus(edition)}
			<li class="edition" data-testid="edition-row">
				<a class="year num" href="/{edition.year}">{edition.year}</a>
				{#if edition.team}
					<a class="team" href="/{edition.year}/teams/{edition.team.id}">{edition.team.name}</a>
				{:else}
					<span class="team muted">{t('profile.noTeam')}</span>
				{/if}
				{#if status === 'ranked'}
					<span class="rank">
						<MedalRank rank={edition.rank} />
						<span class="num of">/ {edition.teams}</span>
					</span>
				{:else if status === 'inProgress'}
					<span class="tag label">{t('profile.inProgress')}</span>
				{:else}
					<span class="rank muted">—</span>
				{/if}
			</li>
		{/each}
	</ul>
</div>

<style>
	h1 {
		margin: 0 0 0.6rem;
		overflow-wrap: anywhere;
	}

	h2 {
		margin: 1.6rem 0 0.6rem;
	}

	.position {
		display: inline-flex;
		align-items: baseline;
		gap: 8px;
		--medal-size: 1.6rem;
		margin-bottom: 0.9rem;
		color: var(--text);
		text-decoration: none;
	}

	.position:hover .label {
		color: var(--accent);
	}

	.position:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
		border-radius: 2px;
	}

	.figures {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 8px;
		margin-bottom: 0.6rem;
	}

	.figure {
		display: flex;
		flex-direction: column;
		gap: 4px;
		min-width: 0;
		padding: 10px 12px;
		background: var(--bg-raised);
		border: 1px solid var(--line);
		border-radius: var(--radius);
	}

	.value {
		font-size: 2.1rem;
		line-height: 1;
		letter-spacing: 0.04em;
		color: var(--ink);
	}

	.counts {
		margin: 0 0 0.4rem;
		font-size: 0.85rem;
		color: var(--muted);
	}

	.editions {
		margin: 0 0 2rem;
		padding: 0;
		list-style: none;
	}

	.edition {
		display: grid;
		grid-template-columns: 3.2rem minmax(0, 1fr) auto;
		align-items: center;
		gap: 12px;
		--medal-size: 1.5rem;
		padding: 10px 0;
		border-top: 1px solid var(--line);
	}

	.year {
		font-size: 1.3rem;
		letter-spacing: 0.06em;
		color: var(--accent);
		text-decoration: none;
	}

	.team {
		min-width: 0;
		overflow-wrap: anywhere;
		color: var(--text);
	}

	.muted {
		color: var(--muted);
	}

	.rank {
		display: inline-flex;
		align-items: baseline;
		gap: 4px;
	}

	.of {
		font-size: 1rem;
		color: var(--muted);
	}

	.tag {
		padding: 3px 10px;
		border: 1px solid var(--accent);
		border-radius: var(--radius-pill);
		color: var(--accent);
		white-space: nowrap;
	}
</style>
```

- [ ] **Step 6: Run the tests to check they pass**

Run: `cd front && npx vitest run "src/routes/players/[id]"`
Expected: `7 passed`.

If the `rows[2]` assertion on the links fails because the year link's accessible name differs, check the markup rather than loosening the test. The year link must be the only link in a row without a team.

- [ ] **Step 7: Commit**

```bash
git add "front/src/routes/players/[id]"
git commit -m "[FEAT] front: /players/<id>, a player's editions, averages and all-time position

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Players in the header, the tab bar and the hub

**Files:**
- Modify: `front/src/lib/components/Header.svelte` (the `tabs` array in the script)
- Modify: `front/src/lib/components/TabBar.svelte` (the `items` array in the script)
- Modify: `front/src/lib/components/EditionHub.svelte` (the countdown/ranking block and its styles)
- Modify: `front/src/lib/components/Header.test.js`, `TabBar.test.js`, `EditionHub.test.js`

- [ ] **Step 1: Write the failing tests**

In `front/src/lib/components/Header.test.js`, change the first import line to `import { screen, within } from '@testing-library/svelte';` and add inside `describe('Header', ...)`:

```js
	it('links the players leaderboard after the disciplines, outside any year', () => {
		renderWith(Header, {}, 'en');

		const nav = screen.getByRole('navigation', { name: 'Sections' });
		expect(within(nav).getAllByRole('link').map((a) => a.textContent.trim())).toEqual([
			'Ranking',
			'Disciplines',
			'Players',
			'Photos'
		]);
		const players = screen.getByRole('link', { name: 'Players' });
		expect(players).toHaveAttribute('href', '/players');
		expect(players).not.toHaveAttribute('aria-current');
	});

	it('words the players tab in French', () => {
		renderWith(Header, {}, 'fr');

		expect(screen.getByRole('link', { name: 'Joueurs' })).toHaveAttribute('href', '/players');
	});
```

In `front/src/lib/components/TabBar.test.js`, change the first import line to `import { render, screen, within } from '@testing-library/svelte';` and add inside `describe('TabBar', ...)`:

```js
	it('puts players between disciplines and photos', () => {
		renderWith(TabBar, { year: 2026, pathname: '/2026/ranking', photosUrl: 'https://photos.example/2026' });

		const nav = screen.getByRole('navigation', { name: 'Sections' });
		expect(within(nav).getAllByRole('link').map((a) => a.textContent.trim())).toEqual([
			'Ranking',
			'Disciplines',
			'Players',
			'Photos'
		]);
		expect(screen.getByRole('link', { name: 'Players' })).toHaveAttribute('href', '/players');
	});

	it('marks players on the leaderboard and on a profile only', () => {
		for (const pathname of ['/players', '/players/34']) {
			const { unmount } = renderWith(TabBar, { year: 2026, pathname });

			expect(screen.getByRole('link', { name: 'Players' })).toHaveAttribute('aria-current', 'page');
			expect(screen.getByRole('link', { name: 'Ranking' })).not.toHaveAttribute('aria-current');
			unmount();
		}
	});

	it('does not mark players on a year page', () => {
		renderWith(TabBar, { year: 2026, pathname: '/2026/ranking' });

		expect(screen.getByRole('link', { name: 'Players' })).not.toHaveAttribute('aria-current');
	});
```

In `front/src/lib/components/EditionHub.test.js`, add inside `describe('EditionHub', ...)`:

```js
	it('links the players leaderboard before the start, while the ranking waits', () => {
		vi.setSystemTime(new Date('2026-09-17T07:00:00Z'));
		renderWith(EditionHub, { summary, editions });

		expect(screen.getByRole('link', { name: 'Players' })).toHaveAttribute('href', '/players');
		expect(screen.queryByRole('link', { name: 'Ranking' })).toBeNull();
	});

	it('links the players leaderboard beside the ranking once started', () => {
		vi.setSystemTime(new Date('2026-09-19T08:00:00Z'));
		renderWith(EditionHub, { summary, editions });

		expect(screen.getByRole('link', { name: 'Ranking' })).toHaveAttribute('href', '/2026/ranking');
		expect(screen.getByRole('link', { name: 'Players' })).toHaveAttribute('href', '/players');
	});

	it('words the players link in French', () => {
		vi.setSystemTime(new Date('2026-09-19T08:00:00Z'));
		renderWith(EditionHub, { summary, editions }, 'fr');

		expect(screen.getByRole('link', { name: 'Joueurs' })).toHaveAttribute('href', '/players');
	});
```

- [ ] **Step 2: Run the tests to check they fail**

Run: `cd front && npx vitest run src/lib/components/Header.test.js src/lib/components/TabBar.test.js src/lib/components/EditionHub.test.js`
Expected: FAIL, the new tests find no `Players` / `Joueurs` link.

- [ ] **Step 3: Add the Players tab to the header**

In `front/src/lib/components/Header.svelte`, in the `tabs` array, after `{ name: t('nav.disciplines'), url: \`/${year}/disciplines\` },` add:

```js
				// Spans every edition, so it points outside the year segment.
				{ name: t('nav.players'), url: '/players' },
```

- [ ] **Step 4: Add the Players item to the tab bar**

In `front/src/lib/components/TabBar.svelte`, in the `items` array, after `{ name: t('nav.disciplines'), url: \`/${current}/disciplines\` },` add:

```js
				// Spans every edition, so it points outside the year segment.
				{ name: t('nav.players'), url: '/players' },
```

- [ ] **Step 5: Add the Players link to the hub**

In `front/src/lib/components/EditionHub.svelte`, replace:

```svelte
{#if phase === 'upcoming'}
	<div id="countdown">
		<div class="label"><span class="num">{parts.days}</span>{t('hub.days')}</div>
		<div class="label"><span class="num">{parts.hours}</span>{t('hub.hours')}</div>
		<div class="label"><span class="num">{parts.minutes}</span>{t('hub.minutes')}</div>
		<div class="label"><span class="num">{parts.seconds}</span>{t('hub.seconds')}</div>
	</div>
{:else}
	<div id="ranking">
		<a href="/{edition.year}/ranking">{t('hub.ranking')}</a>
	</div>
{/if}
```

with:

```svelte
{#if phase === 'upcoming'}
	<div id="countdown">
		<div class="label"><span class="num">{parts.days}</span>{t('hub.days')}</div>
		<div class="label"><span class="num">{parts.hours}</span>{t('hub.hours')}</div>
		<div class="label"><span class="num">{parts.minutes}</span>{t('hub.minutes')}</div>
		<div class="label"><span class="num">{parts.seconds}</span>{t('hub.seconds')}</div>
	</div>
{/if}

<!-- The leaderboard covers past editions, so its link shows before the start too; on a
     phone the hub has no tab bar, and this is the way in. -->
<div id="ranking">
	{#if phase !== 'upcoming'}
		<a href="/{edition.year}/ranking">{t('hub.ranking')}</a>
	{/if}
	<a class="secondary" href="/players">{t('hub.players')}</a>
</div>
```

In the same file's `<style>`, after the `#ranking a:focus-visible { ... }` rule, add:

```css
	#ranking {
		flex-wrap: wrap;
		gap: 1rem;
	}

	/* Same shape as the ranking button, outlined: the edition's ranking stays the main call. */
	#ranking a.secondary {
		background: transparent;
		color: var(--accent);
		box-shadow: inset 0 0 0 2px var(--accent);
	}
```

- [ ] **Step 6: Run the tests to check they pass**

Run: `cd front && npx vitest run src/lib/components`
Expected: every test passes, including the existing EditionHub tests (`queryByRole('link', { name: 'Ranking' })` is still null before the start).

- [ ] **Step 7: Commit**

```bash
git add front/src/lib/components/Header.svelte front/src/lib/components/TabBar.svelte front/src/lib/components/EditionHub.svelte front/src/lib/components/Header.test.js front/src/lib/components/TabBar.test.js front/src/lib/components/EditionHub.test.js
git commit -m "[FEAT] front: Players in the header, the tab bar and the hub

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Team page roster chips link to profiles

**Files:**
- Modify: `front/src/lib/fixtures/summary.js` (the three roster players, lines 24–34)
- Modify: `front/src/routes/[year=year]/teams/[id]/+page.svelte` (the roster and `.chip` style)
- Modify: `front/src/routes/[year=year]/teams/[id]/page.test.js`

- [ ] **Step 1: Give the fixture players a user id**

In `front/src/lib/fixtures/summary.js`, change the three players to:

```js
				{ id: 1, user: 11, first_name: 'Ana', last_name: 'Lopez' },
				{ id: 2, user: 12, first_name: 'Bob', last_name: 'Martin' }
```

and

```js
			players: [{ id: 3, user: 13, first_name: 'Chloé', last_name: 'Nguyen' }]
```

- [ ] **Step 2: Write the failing test**

In `front/src/routes/[year=year]/teams/[id]/page.test.js`, add inside `describe('team page', ...)`:

```js
	it('links each roster name to the player profile', () => {
		renderWith(Page, { data: dataFor(1) });

		expect(screen.getByRole('link', { name: 'Ana Lopez' })).toHaveAttribute('href', '/players/11');
		expect(screen.getByRole('link', { name: 'Bob Martin' })).toHaveAttribute('href', '/players/12');
	});
```

- [ ] **Step 3: Run the test to check it fails**

Run: `cd front && npx vitest run "src/routes/[year=year]/teams/[id]/page.test.js"`
Expected: FAIL, `Unable to find an accessible element with the role "link" and name "Ana Lopez"`.

- [ ] **Step 4: Turn the chips into links**

In `front/src/routes/[year=year]/teams/[id]/+page.svelte`, replace:

```svelte
			<span class="chip">{player.first_name} {player.last_name}</span>
```

with:

```svelte
			<a class="chip" href="/players/{player.user}">{player.first_name} {player.last_name}</a>
```

and in its `<style>`, replace the `.chip { ... }` rule with:

```css
	.chip {
		padding: 6px 12px;
		border-radius: var(--radius-pill);
		background: var(--bg-raised);
		border: 1px solid var(--line-strong);
		font-size: 0.8rem;
		min-width: 0;
		overflow-wrap: anywhere;
		color: var(--text);
		text-decoration: none;
		transition: border-color 0.2s ease;
	}

	.chip:hover {
		border-color: var(--accent);
		text-decoration: none;
	}

	.chip:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}
```

Leave the names on `/<year>/ranking` alone. Each team card there is already a single `<a>`, and a link inside a link is invalid HTML.

- [ ] **Step 5: Run the whole front suite**

Run: `cd front && npm test`
Expected: every test file passes. `summary.js` is shared by many tests, and the added `user` fields must not break any of them.

- [ ] **Step 6: Commit**

```bash
git add front/src/lib/fixtures/summary.js "front/src/routes/[year=year]/teams/[id]/+page.svelte" "front/src/routes/[year=year]/teams/[id]/page.test.js"
git commit -m "[FEAT] front: team page roster names link to the player profiles

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: `CLAUDE.md`, full verification and a look in the browser

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Document the backend**

In `CLAUDE.md`, insert this paragraph immediately before the line starting `**Soft deletes:**`:

```markdown
**Player profiles:** `olympic_warriors/profiles.py` builds every person's record from the edition standings and stores nothing (spec under `docs/superpowers/specs/`). A person is a `User` with an active `Player` in an active edition, one participation per (user, edition): the lowest id among the rows with a valid team (active, of the player's edition), else the lowest id. An edition is finished once its `end_date` is before today in Europe/Paris (`paris_today()`: the server clock runs in UTC), and only a finished edition gives a rank, the team's standing (`final_rank` in a hand-ranked edition), so unfinished editions skip `compute_standings`; a computed edition in which no result has a rank gives no rank at all, since every team would otherwise tie 1st on nothing. A participation counts when finished, ranked and in an edition of at least two teams; `average_rank` (one decimal) and `average_beaten` (the mean of `(teams - rank) / (teams - 1)`, as a whole percentage) average the counted ones. `leaderboard()` sorts by share beaten, mean rank, counted editions and name, equal (share, mean rank) pairs share a position, and people with nothing counted follow by name with a null position; it runs `2 + 3 × finished editions with players` queries (`PROFILES_QUERIES` in `test_profiles.py`). `Player.clean()` refuses a team of another edition and a second active row for the same (user, edition), both keyed on `team`, the one field every admin form of a player has (an error on a field the form lacks makes Django raise `ValueError`); `PlayerAdmin` edits `team` from the changelist, with teams labelled `name (year)`. Django validates every row of a posted changelist page, so one duplicate pair blocks saving that whole page until one of its rows is deactivated. On the team page, `PlayerInlineForm` repeats `team` errors among the row errors, because the inline's hidden foreign key never shows its own; on a new team the check reads the unsaved team object, which already carries its edition. Two new inline rows for the same person saved together both pass (the duplicate check only sees saved rows).
```

- [ ] **Step 2: Document the API changes**

In `CLAUDE.md`, replace:

```
Six edition/discipline read views carry `@permission_classes([AllowAny])` below `@api_view` and are public; everything else returns 401 without a token.
```

with:

```
Six edition/discipline read views and the two profile views (`GET /profiles/`, the leaderboard; `GET /profile/<user_id>/`, 404 for someone who never played) carry `@permission_classes([AllowAny])` below `@api_view` and are public; everything else returns 401 without a token. The profile payloads carry names, teams and ranks only, never the username (the login name) or the email.
```

Replace:

```
`teams` (each with its roster, `ranking` and `total_points`)
```

with:

```
`teams` (each with its roster, whose players carry `id`, `user`, `first_name` and `last_name`, plus `ranking` and `total_points`)
```

Replace:

```
Together with `/editions/` it is everything the front reads.
```

with:

```
Together with `/editions/` and the two profile endpoints it is everything the front reads.
```

- [ ] **Step 3: Document the front**

In `CLAUDE.md`, replace:

```
Detail routes take a numeric id, not a slug. All read pages are public — no route checks a cookie.
```

with:

```
Detail routes take a numeric id, not a slug. Two routes sit outside the year segment because they span editions: `/players`, the all-time leaderboard from `/profiles/`, and `/players/<user id>`, a profile from `/profile/<id>/`, whose `+page.server.js` answers 404 to anything but digits before calling the API; `src/lib/players.js` formats their figures (`formatAverage`, `formatShare`, `editionStatus`) and `src/lib/fixtures/players.js` holds their payloads. All read pages are public — no route checks a cookie.
```

Replace:

```
the Ranking and Disciplines tabs with `aria-current` plus a Photos tab when the edition has a `photos_url`; tabs hidden at 999px and below)
```

with:

```
the Ranking, Disciplines and Players tabs with `aria-current`, Players pointing to `/players` whatever the year, plus a Photos tab when the edition has a `photos_url`; tabs hidden at 999px and below)
```

Replace:

```
and `EditionHub` (the hub).
```

with:

```
and `EditionHub` (the hub: an `.actions` block with the ranking button once started and a Players link in both phases, outlined beside the ranking button and filled on its own before the start, since on a phone the hub has no tab bar). Roster names link to `/players/<user>` on the team page only: each team card of the ranking page is already one link, and links cannot nest.
```

Replace:

```
Page tests assert on text shapes, not on classes: `1 Bisons 5 pts` for a ranking row, `R1 Bisons 12 : 9 Aigles` for a team game row.
```

with:

```
Page tests assert on text shapes, not on classes: `1 Bisons 5 pts` for a ranking row, `R1 Bisons 12 : 9 Aigles` for a team game row, `1 Léa Martin avg 1.0 over 2 editions 100%` for a leaderboard row, `2026 MxM 2 / 6` for a profile edition row.
```

- [ ] **Step 4: Run the whole Django suite**

Run: `docker compose exec server python manage.py test`
Expected: `OK`, and every test that passed on `dev` still passes. If an older test breaks because of `Player.clean()` or the `user` field, read the failure before changing anything.

- [ ] **Step 5: Run the whole front suite and the production build (the CI gate)**

Run: `cd front && npm test && npm run build`
Expected: every test file passes and the build ends with `✓ built` / `Wrote site to "build"`, with no errors.

- [ ] **Step 6: Look at it in the browser**

The dev stack serves the front on http://localhost:5173 with the branch's code. Using the built-in browser:
1. Open http://localhost:5173/players. Ranked players should appear with medals and shares, then the "Pas encore classés" group. Locally, 2026 is the only finished edition with teams, so every ranked row rests on one edition.
2. Open a ranked player's profile. Check the two figures, the position linking back to `/players`, and the edition rows.
3. Open a team page such as http://localhost:5173/2026/teams/<id> and follow a roster chip to its profile.
4. Resize to the mobile preset. The bottom tab bar should show Ranking, Disciplines and Players (plus Photos only for an edition with a `photos_url`; none has one locally) with Players lit on `/players`, the hub (http://localhost:5173/) should show the outlined Players link, and nothing should scroll sideways. Reset to the desktop preset afterwards.
5. Open http://localhost:5173/players/abc. It should render the 404 error page.

If any page shows an error, check `docker compose logs server --tail 50` first. The server container reads the branch's code, but it only reloads when `runserver` notices the change.

- [ ] **Step 7: Commit**

```bash
git add CLAUDE.md
git commit -m "[DOCS] CLAUDE.md: player profiles, their endpoints, admin checks and routes

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Self-review notes (for the executor)

- **Spec coverage:**
  - Definitions: Tasks 1–3.
  - Endpoints and privacy: Task 4.
  - Summary `user`: Task 5.
  - Admin and `Player.clean()`: Task 6.
  - Leaderboard and profile pages: Tasks 8–9.
  - Navigation and hub: Task 10.
  - Roster links: Task 11.
  - Docs and verification: Task 12.
- **Plan review (2026-09-23):** an independent read-only review applied every block to scratch copies. It found the French percent space to be U+00A0 (fixed in Task 7), added `PlayerInlineForm` (Task 6), and confirmed the rest: the hand-computed values, the query counts, the test counts, the full Django suite (253 OK) and `vite build`.
- **Header tests:** the `aria-current` check on `/players` and `/players/34` is tested through `TabBar`, which takes `pathname` as a prop. `Header` uses the same `startsWith` rule, and its store mock is fixed on `/2026/ranking`, so its tests cover the tab order and link only.
- **Out of scope:** no migration, no changes to the ranking page's names, no skill ratings anywhere in the new payloads.
