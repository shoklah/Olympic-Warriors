# Team Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** An organiser-only page that proposes balanced teams from the registered players, honours confirmed « avec » / « à éviter » requests where possible, lets the organisers adjust by hand, and creates the teams on Apply.

**Architecture:** A `TeamDraft` row per edition (server-side draft, optimistic `updated_at`), three staff-only API endpoints (payload, draft save, apply), and a front page `/<year>/builder` whose generator and scoring are pure JS (`$lib/builder/`). The browser reconciles the saved draft with the roster on load; the server validates the shape and applies in one transaction (teams, `TeamResult` backfill, `Player.team`).

**Tech Stack:** Django 4.2 / DRF / PostgreSQL; SvelteKit 2 / Svelte 4 (plain JS, tabs), Vitest + @testing-library/svelte.

Spec: `docs/superpowers/specs/2026-10-05-team-builder-design.md`.

**Two PRs** (decided in the grilling): **PR A, server**: Tasks 1–6 on `feat/team-builder-server`, from `dev` once #122 is merged. **PR B, front**: Tasks 7–17 on `feat/team-builder`, from `dev` once PR A is merged; its tests need no server, and the browser walk (Task 17) runs when both are on `dev`.

**Prerequisite:** PR #122 (registration wizard) must be merged into `dev` first: the builder reads `Player.team_with` / `team_avoid` and the sports level ladder (`fun` … `regional`). Branch `feat/team-builder` from the updated `dev`.

**Rules for every implementer** (from CLAUDE.md and past slices):
- NEVER write to the dev database from a script or `manage.py shell` (tests only: `docker compose exec server python manage.py test ...` uses a throwaway DB). `makemigrations` is fine; do not run `migrate`.
- Front tests: `cd front && npx vitest run <file>`. Server tests run in Docker.
- Run each new test red before the code that makes it green; one commit per task.
- Svelte 4: a `bind:value` inside an `{#each}` over props can mark the prop dirty; keep reloading from props behind an identity check, never in a bare `$:` (see `RegistrationForm.svelte`'s `loadedFrom`).
- Colours only through tokens; every visible string through `t`; fr.js/en.js stay in parity.

## Deviations from the spec (decided while planning)

- The page saves the draft and applies it through **JSON endpoints** of the page (`builder/draft/+server.js`, `builder/apply/+server.js`) rather than form actions: the draft is saved debounced as the organiser works, and a 409 must hand the stored draft back to the page, which `apiSend` would drop. The proxies forward the API's status and body unchanged.
- The « existing teams » message and the post-Apply list name the admin pages but do **not** link to them: the front does not know the Django admin's public address (the dev Vite server does not proxy `/admin`).

---

# Server

## File structure

- `server/olympic_warriors/models/TeamDraft.py` — the draft row; migration generated.
- `server/olympic_warriors/builder.py` — draft validation, payload, save with the stale check, apply. No views, no models of its own.
- `server/olympic_warriors/views.py`, `urls.py` — three views.
- `server/olympic_warriors/admin.py` — a link on the Edition page.
- `server/olympic_warriors/transfer.py` — `TeamDraft` in `NOT_EXPORTED`.
- Tests: `server/olympic_warriors/tests/test_builder.py` (new), `test_transfer.py` already enforces the export list.

### Task 1: `TeamDraft` model

**Files:**
- Create: `server/olympic_warriors/models/TeamDraft.py`, migration `0046_teamdraft.py` (generated; use the next free number)
- Modify: `server/olympic_warriors/models/__init__.py`, `server/olympic_warriors/transfer.py:60-62`
- Test: `server/olympic_warriors/tests/test_builder.py` (create), `test_transfer.py` (existing check)

- [ ] **Step 1: Write the failing test**

```python
"""The team builder: draft rules, the payload, the stale check and Apply."""
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase

from olympic_warriors.models import Edition, Player, TeamDraft


def make_edition(year=2027):
    return Edition.objects.create(
        year=year, host="Paris", start_date=date(year, 9, 18), end_date=date(year, 9, 19)
    )


def make_player(edition, username, rating=5, **kw):
    user = User.objects.create(username=username, first_name=username.title(), last_name="Test")
    return Player.objects.create(user=user, edition=edition, rating=rating, **kw)


class TestTeamDraftModel(TestCase):
    def test_one_draft_per_edition_with_an_empty_document_by_default(self):
        edition = make_edition()

        draft = TeamDraft.objects.create(edition=edition)

        self.assertEqual(draft.document, {})
        self.assertEqual(edition.team_draft, draft)
        self.assertIsNotNone(draft.updated_at)
        with self.assertRaises(Exception):
            TeamDraft.objects.create(edition=edition)
```

- [ ] **Step 2: Run it red** — `docker compose exec server python manage.py test olympic_warriors.tests.test_builder` → ImportError (`TeamDraft`).

- [ ] **Step 3: Implement.** `models/TeamDraft.py`:

```python
from django.contrib.auth.models import User
from django.db import models

from .Edition import Edition


class TeamDraft(models.Model):
    """
    The organisers' working state of the team builder for an edition: confirmed name links,
    the proposed teams and the locked players, as the browser keeps them. The server only
    checks its shape (olympic_warriors.builder); nothing here touches Team or Player.team
    until the draft is applied. Private, never exported.
    """

    edition = models.OneToOneField(Edition, on_delete=models.CASCADE, related_name="team_draft")
    document = models.JSONField(default=dict)
    updated_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Team draft {self.edition.year}"
```

`models/__init__.py`: after `from .Team import Team, TeamResult` add `from .TeamDraft import TeamDraft`. `transfer.py`: add `"TeamDraft"` to `NOT_EXPORTED`. Then `docker compose exec server python manage.py makemigrations olympic_warriors -n teamdraft`.

- [ ] **Step 4: Run green**: the new test and `olympic_warriors.tests.test_transfer` (it fails when a model is neither exported nor listed) → PASS; `makemigrations --check --dry-run` clean.
- [ ] **Step 5: Commit** `[FEAT] TeamDraft: the team builder's server-side draft`.

### Task 2: Draft validation

**Files:** Create `server/olympic_warriors/builder.py`; Test `tests/test_builder.py`.

- [ ] **Step 1: Failing tests** (append):

```python
from olympic_warriors.builder import DraftError, validate_draft

IDS = [1, 2, 3, 4, 5, 6]


def doc(**changes):
    document = {
        "players_per_team": 3,
        "seed": 7,
        "links": [{"player": 1, "kind": "with", "target": 2}],
        "teams": [{"players": [1, 2, 3]}, {"players": [4, 5]}],
        "locked": [1],
    }
    document.update(changes)
    return document


class TestValidateDraft(TestCase):
    def codes(self, document):
        with self.assertRaises(DraftError) as caught:
            validate_draft(document, IDS)
        return caught.exception.codes

    def test_a_good_draft_is_returned_with_exactly_its_keys(self):
        cleaned = validate_draft(doc(extra="ignored"), IDS)

        self.assertEqual(set(cleaned), {"players_per_team", "seed", "links", "teams", "locked"})
        self.assertEqual(cleaned["teams"], [{"players": [1, 2, 3]}, {"players": [4, 5]}])

    def test_a_draft_before_any_proposal_is_valid(self):
        cleaned = validate_draft(doc(teams=[], locked=[], links=[]), IDS)

        self.assertEqual(cleaned["teams"], [])

    def test_shape_errors(self):
        self.assertEqual(self.codes([]), ["invalid_draft"])
        self.assertEqual(self.codes(doc(seed=-1)), ["invalid_draft"])
        self.assertEqual(self.codes(doc(seed=True)), ["invalid_draft"])
        self.assertEqual(self.codes(doc(teams="x")), ["invalid_draft"])
        self.assertEqual(self.codes(doc(teams=[{"players": "x"}])), ["invalid_draft"])
        self.assertEqual(self.codes(doc(links=[{"player": 1, "kind": "love", "target": 2}])), ["invalid_draft"])
        self.assertEqual(self.codes(doc(links=[{"player": 1, "kind": "with", "target": 1}])), ["invalid_draft"])

    def test_players_per_team_is_two_to_twenty(self):
        for bad in (1, 21, "3", None, True):
            with self.subTest(bad=bad):
                self.assertEqual(self.codes(doc(players_per_team=bad)), ["bad_size"])

    def test_unknown_players_are_refused_everywhere(self):
        self.assertEqual(self.codes(doc(teams=[{"players": [1, 99]}], locked=[])), ["unknown_player"])
        self.assertEqual(self.codes(doc(links=[{"player": 1, "kind": "with", "target": 99}])), ["unknown_player"])

    def test_a_player_in_two_teams_is_refused(self):
        self.assertEqual(self.codes(doc(teams=[{"players": [1, 2]}, {"players": [2, 3]}], locked=[])), ["invalid_draft"])

    def test_a_locked_player_must_be_placed(self):
        self.assertEqual(self.codes(doc(locked=[6])), ["invalid_draft"])

    def test_too_many_links(self):
        links = [{"player": 1, "kind": "with", "target": 2}] * 201
        self.assertEqual(self.codes(doc(links=links)), ["too_many_links"])
```

- [ ] **Step 2: Run red** → ImportError.
- [ ] **Step 3: Implement** `builder.py` (start of the module; later tasks append):

```python
"""The team builder's server side (spec 2026-10-05-team-builder-design.md): the draft's
shape rules, the roster payload, the stale-checked save and Apply. The generator and the
scoring live in the browser; nothing here balances teams."""
from django.db import transaction

MIN_PER_TEAM = 2
MAX_PER_TEAM = 20
MAX_LINKS = 200
KINDS = {"with", "avoid"}
SEED_LIMIT = 2**31


class DraftError(Exception):
    """A draft refused: `codes` are the API's (`invalid_draft`, `unknown_player`, `bad_size`, `too_many_links`)."""

    def __init__(self, codes):
        super().__init__(codes)
        self.codes = codes


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def validate_draft(document, player_ids):
    """The cleaned draft (only the five known keys) or a DraftError listing every problem."""
    ids = set(player_ids)
    errors = []

    def fail(code):
        if code not in errors:
            errors.append(code)

    if not isinstance(document, dict):
        raise DraftError(["invalid_draft"])

    per_team = document.get("players_per_team")
    if not _is_int(per_team) or not MIN_PER_TEAM <= per_team <= MAX_PER_TEAM:
        fail("bad_size")
    seed = document.get("seed")
    if not _is_int(seed) or not 0 <= seed < SEED_LIMIT:
        fail("invalid_draft")

    links = document.get("links", [])
    cleaned_links = []
    if not isinstance(links, list):
        fail("invalid_draft")
    elif len(links) > MAX_LINKS:
        fail("too_many_links")
    else:
        for link in links:
            if not isinstance(link, dict) or link.get("kind") not in KINDS:
                fail("invalid_draft")
                continue
            player, target = link.get("player"), link.get("target")
            if not _is_int(player) or not _is_int(target) or player == target:
                fail("invalid_draft")
            elif player not in ids or target not in ids:
                fail("unknown_player")
            else:
                cleaned_links.append({"player": player, "kind": link["kind"], "target": target})

    teams = document.get("teams", [])
    cleaned_teams = []
    placed = set()
    if not isinstance(teams, list):
        fail("invalid_draft")
    else:
        for team in teams:
            members = team.get("players") if isinstance(team, dict) else None
            if not isinstance(members, list) or not all(_is_int(m) for m in members):
                fail("invalid_draft")
                continue
            if any(m not in ids for m in members):
                fail("unknown_player")
                continue
            if len(set(members)) != len(members) or placed & set(members):
                fail("invalid_draft")
                continue
            placed |= set(members)
            cleaned_teams.append({"players": list(members)})

    locked = document.get("locked", [])
    if not isinstance(locked, list) or not all(_is_int(p) for p in locked) or not set(locked) <= placed:
        fail("invalid_draft")

    if errors:
        raise DraftError(errors)
    return {
        "players_per_team": per_team,
        "seed": seed,
        "links": cleaned_links,
        "teams": cleaned_teams,
        "locked": list(locked),
    }
```

- [ ] **Step 4: Run green.** Also run `docker compose exec server python manage.py test olympic_warriors.tests.test_builder`.
- [ ] **Step 5: Commit** `[FEAT] team builder: draft validation`.

### Task 3: Payload, save with the stale check

**Files:** Modify `builder.py`; Test `tests/test_builder.py`.

- [ ] **Step 1: Failing tests** (append):

```python
from django.db import connection
from django.test.utils import CaptureQueriesContext

from olympic_warriors import builder
from olympic_warriors.models import PlayerRating, PlayerSport, RegistrationSkill, Team


def make_skill(edition, identifier="CARD", order=0):
    return RegistrationSkill.objects.create(
        edition=edition, name_fr=f"{identifier} fr", name_en=f"{identifier} en",
        identifier=identifier, weight=4, order=order,
    )


class TestPayload(TestCase):
    def setUp(self):
        self.edition = make_edition()
        make_skill(self.edition)
        self.ana = make_player(
            self.edition, "ana", rating=7, global_level=8, sport_frequency="two_hours",
            team_with="Bob", team_avoid="Carl",
        )
        PlayerRating.objects.create(player=self.ana, name="Cardio", identifier="CARD", rating=6)
        PlayerSport.objects.create(player=self.ana, sport="Judo", level="league")

    def test_the_roster_carries_the_private_answers_and_nothing_of_the_user(self):
        body = builder.payload(self.edition)

        self.assertEqual(body["edition"], {"year": 2027})
        self.assertEqual(body["skills"], [{"identifier": "CARD", "name_fr": "CARD fr", "name_en": "CARD en"}])
        self.assertFalse(body["teams_exist"])
        self.assertFalse(body["registration_open"])
        self.assertIsNone(body["draft"])
        player = body["players"][0]
        self.assertEqual(
            player,
            {
                "id": self.ana.pk, "first_name": "Ana", "last_name": "Test", "rating": 7,
                "global_level": 8, "ratings": {"CARD": 6}, "sport_frequency": "two_hours",
                "sports": [{"sport": "Judo", "level": "league"}], "team_with": "Bob",
                "team_avoid": "Carl", "team": None,
            },
        )

    def test_only_active_players_of_active_users_are_listed(self):
        gone = make_player(self.edition, "gone")
        Player.objects.filter(pk=gone.pk).update(is_active=False)
        left = make_player(self.edition, "left")
        User.objects.filter(pk=left.user_id).update(is_active=False)

        ids = [p["id"] for p in builder.payload(self.edition)["players"]]

        self.assertEqual(ids, [self.ana.pk])

    def test_teams_exist_and_a_valid_team_are_reported(self):
        team = Team.objects.create(name="Red", edition=self.edition)
        Player.objects.filter(pk=self.ana.pk).update(team=team)

        body = builder.payload(self.edition)

        self.assertTrue(body["teams_exist"])
        self.assertEqual(body["players"][0]["team"], team.pk)

    def test_the_query_count_does_not_grow_with_the_roster(self):
        def count():
            with CaptureQueriesContext(connection) as queries:
                builder.payload(self.edition)
            return len(queries)

        before = count()
        for i in range(5):
            player = make_player(self.edition, f"p{i}")
            PlayerRating.objects.create(player=player, name="Cardio", identifier="CARD", rating=5)
            PlayerSport.objects.create(player=player, sport="Tennis")

        self.assertEqual(count(), before)
        self.assertEqual(before, builder.BUILDER_QUERIES)


class TestSaveDraft(TestCase):
    def setUp(self):
        self.edition = make_edition()
        self.boss = User.objects.create_user("boss", is_staff=True)
        self.ana = make_player(self.edition, "ana")
        self.bob = make_player(self.edition, "bob")
        self.document = {"players_per_team": 3, "seed": 1, "links": [], "teams": [], "locked": []}

    def test_a_first_save_creates_the_row_and_stamps_the_author(self):
        saved = builder.save_draft(self.edition, self.boss, self.document, None)

        self.assertEqual(saved.updated_by, self.boss)
        self.assertEqual(saved.document["players_per_team"], 3)

    def test_a_save_based_on_the_current_version_updates_it(self):
        first = builder.save_draft(self.edition, self.boss, self.document, None)

        second = builder.save_draft(
            self.edition, self.boss, {**self.document, "seed": 2}, first.updated_at.isoformat()
        )

        self.assertEqual(second.document["seed"], 2)
        self.assertEqual(TeamDraft.objects.count(), 1)

    def test_a_stale_save_is_refused_and_hands_back_the_stored_draft(self):
        first = builder.save_draft(self.edition, self.boss, self.document, None)
        builder.save_draft(self.edition, self.boss, {**self.document, "seed": 2}, first.updated_at.isoformat())

        with self.assertRaises(builder.StaleDraft) as stale:
            builder.save_draft(self.edition, self.boss, {**self.document, "seed": 3}, first.updated_at.isoformat())

        self.assertEqual(stale.exception.current.document["seed"], 2)

    def test_a_save_without_a_base_over_an_existing_draft_is_stale(self):
        builder.save_draft(self.edition, self.boss, self.document, None)

        with self.assertRaises(builder.StaleDraft):
            builder.save_draft(self.edition, self.boss, self.document, None)

    def test_a_save_based_on_a_cleared_draft_is_stale_with_no_current(self):
        with self.assertRaises(builder.StaleDraft) as stale:
            builder.save_draft(self.edition, self.boss, self.document, "2027-01-01T00:00:00+00:00")

        self.assertIsNone(stale.exception.current)

    def test_an_invalid_document_is_refused(self):
        with self.assertRaises(DraftError):
            builder.save_draft(self.edition, self.boss, {**self.document, "teams": [{"players": [999]}]}, None)
```

- [ ] **Step 2: Run red.**
- [ ] **Step 3: Implement** (append to `builder.py`; add imports at the top: `from .models import Edition, Player, PlayerRating, PlayerSport, RegistrationSkill, Team, TeamDraft` and `from .registration_state import registration_state`):

```python
# The payload's queries: players (with user and team), ratings, sports, skills, the draft,
# the teams-exist check and the registration state's skills check.
BUILDER_QUERIES = 7


class StaleDraft(Exception):
    """The draft changed (or was cleared) since the page loaded it; `current` is the stored one or None."""

    def __init__(self, current):
        super().__init__("stale_draft")
        self.current = current


def roster(edition):
    """The active players of active users: the ones the builder places."""
    return Player.objects.filter(edition=edition, is_active=True, user__is_active=True)


def _valid_team_id(player, edition):
    team = player.team
    if team is None or not team.is_active or team.edition_id != edition.pk:
        return None
    return team.pk


def draft_payload(draft):
    return {"document": draft.document, "updated_at": draft.updated_at.isoformat()}


def payload(edition):
    """What `GET /builder/<year>/` serves: the roster with its private registration answers,
    the questionnaire's skills, whether registration is open and the saved draft."""
    players = list(roster(edition).select_related("user", "team").order_by("user__last_name", "user__first_name", "id"))
    ids = [p.pk for p in players]
    ratings, sports = {}, {}
    for row in PlayerRating.objects.filter(player_id__in=ids, is_active=True).values("player_id", "identifier", "rating"):
        ratings.setdefault(row["player_id"], {})[row["identifier"]] = int(row["rating"])
    for row in PlayerSport.objects.filter(player_id__in=ids).order_by("order", "id").values("player_id", "sport", "level"):
        sports.setdefault(row["player_id"], []).append({"sport": row["sport"], "level": row["level"]})
    skills = [
        {"identifier": s.identifier, "name_fr": s.name_fr, "name_en": s.name_en}
        for s in RegistrationSkill.objects.filter(edition=edition, is_active=True).order_by("order", "id")
    ]
    draft = TeamDraft.objects.filter(edition=edition).first()
    return {
        "edition": {"year": edition.year},
        "skills": skills,
        "registration_open": registration_state(edition).is_open,
        "teams_exist": Team.objects.filter(edition=edition, is_active=True).exists(),
        "players": [
            {
                "id": p.pk,
                "first_name": p.user.first_name,
                "last_name": p.user.last_name,
                "rating": p.rating,
                "global_level": p.global_level,
                "ratings": ratings.get(p.pk, {}),
                "sport_frequency": p.sport_frequency,
                "sports": sports.get(p.pk, []),
                "team_with": p.team_with,
                "team_avoid": p.team_avoid,
                "team": _valid_team_id(p, edition),
            }
            for p in players
        ],
        "draft": draft_payload(draft) if draft else None,
    }


def save_draft(edition, user, document, based_on):
    """Store the draft, refusing a save based on a version that is no longer the stored one.
    Returns the row. Raises DraftError (shape) or StaleDraft."""
    cleaned = validate_draft(document, roster(edition).values_list("pk", flat=True))
    with transaction.atomic():
        current = TeamDraft.objects.select_for_update().filter(edition=edition).first()
        if current is None:
            if based_on is not None:
                raise StaleDraft(None)
            return TeamDraft.objects.create(edition=edition, document=cleaned, updated_by=user)
        if based_on != current.updated_at.isoformat():
            raise StaleDraft(current)
        current.document = cleaned
        current.updated_by = user
        current.save()
        return current


def clear_draft(edition):
    TeamDraft.objects.filter(edition=edition).delete()
```

Run once and set `BUILDER_QUERIES` to the measured value if it differs from 7 (the test asserts the constant equals what `payload` costs); the comment above it must then list what each query is. (`registration_state` with `user=None` runs one query; `payload`'s `Team` check, `TeamDraft`, ratings, sports, skills and players make the rest.)

- [ ] **Step 4: Run green.**
- [ ] **Step 5: Commit** `[FEAT] team builder: the roster payload and the stale-checked draft save`.

### Task 4: Apply

**Files:** Modify `builder.py`; Test `tests/test_builder.py`.

- [ ] **Step 1: Failing tests** (append):

```python
from olympic_warriors.models import Darts, Discipline, Relay, TeamResult


class TestApply(TestCase):
    def setUp(self):
        self.edition = make_edition()
        self.boss = User.objects.create_user("boss", is_staff=True)
        self.players = [make_player(self.edition, f"p{i}") for i in range(5)]
        self.ids = [p.pk for p in self.players]

    def store(self, teams, **extra):
        document = {"players_per_team": 3, "seed": 1, "links": [], "teams": teams, "locked": [], **extra}
        return builder.save_draft(self.edition, self.boss, document, None)

    def apply(self):
        """Apply the stored draft as a page that has just saved it would."""
        return builder.apply(self.edition, TeamDraft.objects.get().updated_at.isoformat())

    def test_creates_the_teams_sets_the_players_and_deletes_the_draft(self):
        self.store([{"players": self.ids[:3]}, {"players": self.ids[3:]}])

        result = self.apply()

        self.assertEqual([t["name"] for t in result["teams"]], ["Équipe 1", "Équipe 2"])
        teams = list(Team.objects.filter(edition=self.edition).order_by("id"))
        self.assertEqual([t.name for t in teams], ["Équipe 1", "Équipe 2"])
        for player in self.players[:3]:
            player.refresh_from_db()
            self.assertEqual(player.team, teams[0])
        self.players[4].refresh_from_db()
        self.assertEqual(self.players[4].team, teams[1])
        self.assertFalse(TeamDraft.objects.exists())

    def test_backfills_a_result_per_team_in_every_existing_discipline(self):
        relay = Relay.objects.create(edition=self.edition)
        darts = Darts.objects.create(edition=self.edition)
        self.store([{"players": self.ids[:3]}, {"players": self.ids[3:]}])

        self.apply()

        for discipline in (relay, darts):
            self.assertEqual(TeamResult.objects.filter(discipline=discipline).count(), 2)

    def test_reports_the_disciplines_with_a_pairing_system_and_no_round(self):
        scheduled = Darts.objects.create(edition=self.edition)
        Discipline.objects.filter(pk=scheduled.pk).update(pairing_system=Discipline.PairingSystem.ROUND_ROBIN)
        Relay.objects.create(edition=self.edition)
        self.store([{"players": self.ids[:3]}, {"players": self.ids[3:]}])

        result = self.apply()

        self.assertEqual([d["id"] for d in result["unscheduled"]], [scheduled.pk])

    def test_refusals(self):
        with self.assertRaises(builder.ApplyRefused) as refused:
            builder.apply(self.edition, None)
        self.assertEqual((refused.exception.code, refused.exception.status), ("no_draft", 409))

        self.store([{"players": self.ids[:3]}])  # one team, two players unplaced
        with self.assertRaises(builder.ApplyRefused) as refused:
            self.apply()
        self.assertEqual((refused.exception.code, refused.exception.status), ("bad_size", 400))

        builder.save_draft(
            self.edition, self.boss,
            {"players_per_team": 3, "seed": 1, "links": [], "teams": [{"players": self.ids[:2]}, {"players": self.ids[2:4]}], "locked": []},
            TeamDraft.objects.get().updated_at.isoformat(),
        )  # one player missing
        with self.assertRaises(builder.ApplyRefused) as refused:
            self.apply()
        self.assertEqual((refused.exception.code, refused.exception.status), ("incomplete", 400))

    def test_unbalanced_sizes_are_refused(self):
        self.store([{"players": self.ids[:4]}, {"players": self.ids[4:]}])

        with self.assertRaises(builder.ApplyRefused) as refused:
            self.apply()

        self.assertEqual(refused.exception.code, "bad_size")
        self.assertFalse(Team.objects.exists())

    def test_existing_teams_refuse_the_apply(self):
        self.store([{"players": self.ids[:3]}, {"players": self.ids[3:]}])
        Team.objects.create(name="Red", edition=self.edition)

        with self.assertRaises(builder.ApplyRefused) as refused:
            self.apply()

        self.assertEqual((refused.exception.code, refused.exception.status), ("teams_exist", 409))

    def test_a_player_who_left_since_the_draft_makes_it_incomplete(self):
        self.store([{"players": self.ids[:3]}, {"players": self.ids[3:]}])
        Player.objects.filter(pk=self.ids[0]).update(is_active=False)

        with self.assertRaises(builder.ApplyRefused) as refused:
            self.apply()

        self.assertEqual(refused.exception.code, "incomplete")

    def test_a_draft_saved_by_someone_else_since_is_refused_and_nothing_is_created(self):
        first = self.store([{"players": self.ids[:3]}, {"players": self.ids[3:]}])
        seen = first.updated_at.isoformat()
        builder.save_draft(
            self.edition, self.boss,
            {"players_per_team": 3, "seed": 2, "links": [], "teams": [{"players": self.ids[:2]}, {"players": self.ids[2:]}], "locked": []},
            seen,
        )

        with self.assertRaises(builder.ApplyRefused) as refused:
            builder.apply(self.edition, seen)

        self.assertEqual((refused.exception.code, refused.exception.status), ("stale_draft", 409))
        self.assertFalse(Team.objects.exists())
        self.assertTrue(TeamDraft.objects.exists())
```

(`Discipline.PairingSystem.ROUND_ROBIN`: check the enum's real member names in `models/Discipline.py` and use them; `Darts` needs the edition's teams only at scheduling, none exist yet so setting the pairing system through `update()` skips scheduling on purpose.)

- [ ] **Step 2: Run red.**
- [ ] **Step 3: Implement** (append):

```python
class ApplyRefused(Exception):
    """Apply refused: `code` is the API's, `status` 409 for a state conflict, 400 for a draft that cannot be applied."""

    def __init__(self, code, status):
        super().__init__(code)
        self.code = code
        self.status = status


def sizes_are_even(teams):
    """At least two teams, sizes differing by at most one."""
    sizes = [len(t["players"]) for t in teams]
    return len(sizes) >= 2 and min(sizes) >= 1 and max(sizes) - min(sizes) <= 1


def apply(edition, based_on):
    """Create the teams of the stored draft (the version `based_on`, the `updated_at` the
    caller saw: any other is refused) and place every player, in one transaction under
    the edition's row lock. Existing disciplines get a result per new team (the base
    `Discipline.register_teams`); their games are not scheduled, the reply lists them."""
    from .models import Discipline

    with transaction.atomic():
        Edition.objects.select_for_update().get(pk=edition.pk)
        draft = TeamDraft.objects.filter(edition=edition).first()
        if draft is None:
            raise ApplyRefused("no_draft", 409)
        if based_on != draft.updated_at.isoformat():
            raise ApplyRefused("stale_draft", 409)
        if Team.objects.filter(edition=edition, is_active=True).exists():
            raise ApplyRefused("teams_exist", 409)
        placed = [pid for team in draft.document.get("teams", []) for pid in team["players"]]
        players = {p.pk: p for p in roster(edition)}
        if len(placed) != len(set(placed)) or set(placed) != set(players):
            raise ApplyRefused("incomplete", 400)
        if not sizes_are_even(draft.document["teams"]):
            raise ApplyRefused("bad_size", 400)

        teams = []
        for index, entry in enumerate(draft.document["teams"], start=1):
            team = Team.objects.create(name=f"Équipe {index}", edition=edition)
            for pid in entry["players"]:
                player = players[pid]
                player.team = team
                player.save()
            teams.append({"id": team.pk, "name": team.name, "players": entry["players"]})

        unscheduled = []
        for discipline in Discipline.objects.filter(edition=edition, is_active=True):
            discipline.register_teams()
            if (
                discipline.pairing_system != Discipline.PairingSystem.NONE
                and not discipline.rounds.filter(is_active=True).exists()
            ):
                unscheduled.append({"id": discipline.pk, "name": discipline.name})
        draft.delete()
        return {"teams": teams, "unscheduled": unscheduled}
```

If `Player.save()` runs `clean()`-like checks that fail for any reason, fix the test data, not the check.

- [ ] **Step 4: Run green** (`olympic_warriors.tests.test_builder`).
- [ ] **Step 5: Commit** `[FEAT] team builder: apply creates the teams and backfills the results`.

### Task 5: Views, routes, permissions

**Files:** Modify `views.py`, `urls.py`; Test `tests/test_builder.py`.

- [ ] **Step 1: Failing tests** (append):

```python
from rest_framework.test import APIClient


class TestBuilderAPI(TestCase):
    def setUp(self):
        self.edition = make_edition(2027)
        self.boss = User.objects.create_user("boss", is_staff=True)
        self.player_user = User.objects.create_user("lea")
        self.ids = [make_player(self.edition, f"p{i}").pk for i in range(4)]
        self.client = APIClient()
        self.client.force_authenticate(self.boss)
        self.url = "/builder/2027/"
        self.document = {
            "players_per_team": 3, "seed": 5, "links": [],
            "teams": [{"players": self.ids[:2]}, {"players": self.ids[2:]}], "locked": [],
        }

    def test_the_routes_are_staff_only(self):
        for client_user in (None, self.player_user):
            client = APIClient()
            if client_user:
                client.force_authenticate(client_user)
            for method, url in (("get", self.url), ("put", self.url + "draft/"), ("post", self.url + "apply/")):
                with self.subTest(user=client_user, url=url):
                    response = getattr(client, method)(url, {}, format="json") if method != "get" else client.get(url)
                    self.assertEqual(response.status_code, 403 if client_user else 401)

    def test_get_serves_the_payload_uncached(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["players"]), 4)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertNotIn("username", str(response.json()))

    def test_only_the_latest_edition_and_a_known_year(self):
        make_edition(2028)

        self.assertEqual(self.client.get("/builder/2027/").status_code, 409)
        self.assertEqual(self.client.get("/builder/2027/").json(), {"error": "not_latest"})
        self.assertEqual(self.client.get("/builder/2999/").status_code, 404)

    def test_put_saves_and_returns_the_new_version(self):
        response = self.client.put(self.url + "draft/", {"document": self.document, "based_on": None}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["document"]["seed"], 5)
        self.assertIn("updated_at", response.json())

    def test_put_refuses_an_invalid_document_with_its_codes(self):
        bad = {**self.document, "teams": [{"players": [999]}]}

        response = self.client.put(self.url + "draft/", {"document": bad, "based_on": None}, format="json")

        self.assertEqual((response.status_code, response.json()), (400, {"errors": ["unknown_player"]}))

    def test_a_stale_put_is_409_with_the_stored_draft(self):
        first = self.client.put(self.url + "draft/", {"document": self.document, "based_on": None}, format="json").json()
        self.client.put(self.url + "draft/", {"document": {**self.document, "seed": 6}, "based_on": first["updated_at"]}, format="json")

        response = self.client.put(self.url + "draft/", {"document": self.document, "based_on": first["updated_at"]}, format="json")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"], "stale_draft")
        self.assertEqual(response.json()["draft"]["document"]["seed"], 6)

    def test_delete_clears_the_draft(self):
        self.client.put(self.url + "draft/", {"document": self.document, "based_on": None}, format="json")

        self.assertEqual(self.client.delete(self.url + "draft/").status_code, 204)
        self.assertFalse(TeamDraft.objects.exists())

    def test_apply_creates_the_teams(self):
        saved = self.client.put(self.url + "draft/", {"document": self.document, "based_on": None}, format="json").json()

        response = self.client.post(self.url + "apply/", {"based_on": saved["updated_at"]}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["teams"]), 2)
        self.assertEqual(response.json()["unscheduled"], [])

    def test_apply_refusals_carry_their_status(self):
        no_draft = self.client.post(self.url + "apply/", {"based_on": None}, format="json")
        self.assertEqual((no_draft.status_code, no_draft.json()), (409, {"error": "no_draft"}))
        saved = self.client.put(self.url + "draft/", {"document": {**self.document, "teams": [{"players": self.ids[:1]}]}, "based_on": None}, format="json").json()

        response = self.client.post(self.url + "apply/", {"based_on": saved["updated_at"]}, format="json")
        self.assertEqual((response.status_code, response.json()), (400, {"error": "bad_size"}))

        stale = self.client.post(self.url + "apply/", {"based_on": "2000-01-01T00:00:00+00:00"}, format="json")
        self.assertEqual((stale.status_code, stale.json()), (409, {"error": "stale_draft"}))
```

- [ ] **Step 2: Run red** (404 on the routes).
- [ ] **Step 3: Implement.** `views.py`: add `from . import builder` next to `from . import accounts, enrolment`, then (place after `myRegistration`):

```python
def _builder_edition(year):
    """The edition the builder may work on, or the refusing Response."""
    edition = Edition.objects.filter(year=year, is_active=True).first()
    if edition is None:
        return None, Response({"error": "no_edition"}, status=404)
    if edition != latest_edition():
        return None, Response({"error": "not_latest"}, status=409)
    return edition, None


def _no_store(response):
    response["Cache-Control"] = "private, no-store"
    return response


@extend_schema(summary="The team builder's roster, answers and draft (organisers)")
@api_view(["GET"])
def getBuilder(request, year):
    edition, refusal = _builder_edition(year)
    if refusal:
        return refusal
    return _no_store(Response(builder.payload(edition)))


@extend_schema(summary="Save or clear the team builder's draft (organisers)")
@api_view(["PUT", "DELETE"])
@parser_classes([JSONParser])
def teamDraft(request, year):
    edition, refusal = _builder_edition(year)
    if refusal:
        return refusal
    if request.method == "DELETE":
        builder.clear_draft(edition)
        return Response(status=204)
    body = request.data if isinstance(request.data, dict) else {}
    try:
        draft = builder.save_draft(edition, request.user, body.get("document"), body.get("based_on"))
    except builder.DraftError as error:
        return Response({"errors": error.codes}, status=400)
    except builder.StaleDraft as stale:
        current = builder.draft_payload(stale.current) if stale.current else None
        return _no_store(Response({"error": "stale_draft", "draft": current}, status=409))
    return _no_store(Response(builder.draft_payload(draft)))


@extend_schema(summary="Create the teams of the stored draft (organisers)")
@api_view(["POST"])
@parser_classes([JSONParser])
def applyTeams(request, year):
    edition, refusal = _builder_edition(year)
    if refusal:
        return refusal
    body = request.data if isinstance(request.data, dict) else {}
    try:
        return _no_store(Response(builder.apply(edition, body.get("based_on"))))
    except builder.ApplyRefused as refused:
        return Response({"error": refused.code}, status=refused.status)
```

(`Edition` and `latest_edition` are already imported in `views.py`; check and add if not.) `urls.py`, after the registration route: `path("builder/<int:year>/", views.getBuilder), path("builder/<int:year>/draft/", views.teamDraft), path("builder/<int:year>/apply/", views.applyTeams),`.

- [ ] **Step 4: Run green**, then the whole suite (`test_permissions.py`, `test_routes.py` must pass with no list change: the routes are staff-only by default) and `makemigrations --check --dry-run`.
- [ ] **Step 5: Commit** `[FEAT] team builder: staff-only endpoints`.

### Task 6: Admin link and server docs

**Files:** Modify `admin.py` (EditionAdmin near `registration_status`, line ~523), `CLAUDE.md`; Test `tests/test_registration_admin.py` or `test_builder.py`.

- [ ] **Step 1: Failing test** (append to `test_builder.py`):

```python
from django.test import override_settings


@override_settings(STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage")
class TestEditionAdminLink(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_superuser("admin", "a@b.c", "pw"))

    def test_the_latest_edition_page_links_to_the_builder_when_the_front_is_known(self):
        edition = make_edition(2027)

        with override_settings(PUBLIC_URL="https://ow.example"):
            response = self.client.get(f"/admin/olympic_warriors/edition/{edition.pk}/change/")

        self.assertContains(response, 'href="https://ow.example/2027/builder"')

    def test_no_link_without_a_public_url_or_for_an_older_edition(self):
        old = make_edition(2026)
        make_edition(2027)

        with override_settings(PUBLIC_URL="https://ow.example"):
            older = self.client.get(f"/admin/olympic_warriors/edition/{old.pk}/change/")
        with override_settings(PUBLIC_URL=""):
            latest = self.client.get(f"/admin/olympic_warriors/edition/{Edition.objects.get(year=2027).pk}/change/")

        self.assertNotContains(older, "/builder")
        self.assertNotContains(latest, "/builder")
```

- [ ] **Step 2: Run red.**
- [ ] **Step 3: Implement.** In `EditionAdmin`: add `"team_builder"` to `readonly_fields` and to the field group that holds `registration_status` (read the surrounding `fields`/`fieldsets`), and:

```python
    @display(description="Constituer les équipes")
    def team_builder(self, obj):
        """A link to the front's builder for the latest edition, when the front's address is known."""
        if obj.pk is None or obj != latest_edition():
            return "—"
        try:
            base = public_url()
        except ImproperlyConfigured:
            return "—"
        return format_html('<a href="{}/{}/builder">Ouvrir le constructeur d\'équipes</a>', base, obj.year)
```

Check `public_url` is imported from `.claims` (or import it) and `ImproperlyConfigured` from `django.core.exceptions`; `public_url()` returns the base without a trailing slash (verify and strip if not).

`CLAUDE.md`: add after the **In-app registration** paragraph a **Team builder** paragraph (spec `2026-10-05-team-builder-design.md`): `TeamDraft` (`models/TeamDraft.py`, one per edition, not exported, `document` shape, `updated_at` as the optimistic version), `builder.py` (`validate_draft` codes, `payload` and `BUILDER_QUERIES`, `save_draft`/`StaleDraft`, `apply` with its refusals and statuses, the `TeamResult` backfill through `Discipline.register_teams` and `unscheduled`), the three staff-only routes (`/builder/<year>/`, `/draft/`, `/apply/`, latest edition only: 404 `no_edition`, 409 `not_latest`), the Edition admin link, and the deploy note (`migrate`, server before front). Mention the front half once Task 17 lands.

- [ ] **Step 4: Run green**, full Django suite.
- [ ] **Step 5: Commit** `[FEAT] team builder: Edition admin link and docs`.

---

# Front

## File structure

- `front/src/lib/builder/random.js` — seeded PRNG. `names.js` — splitting and matching. `plan.js` — team sizes and draft reconciliation. `score.js` — features, scorer, weights. `generate.js` — the generator. `saver.js` — the debounced draft saver. Tests beside each.
- `front/src/lib/fixtures/builder.js` — a builder payload.
- `front/src/lib/server/builder-proxy.js` — forwards the page's JSON calls to the API.
- `front/src/routes/[year=year]/builder/`: `+page.server.js`, `+page.svelte`, `draft/+server.js`, `apply/+server.js`, tests.
- `front/src/lib/components/builder/`: `BuilderRequests.svelte`, `BuilderTeams.svelte`, `BuilderApply.svelte`, `PlayerCard.svelte`.
- Modify: `routes/+layout.svelte` (`NO_TAB_BAR`), `routes/[year=year]/ranking/+page.svelte` (the button), `i18n/fr.js`, `en.js`, `CLAUDE.md`.

### Task 7: Seeded PRNG and team sizes

**Files:** Create `front/src/lib/builder/random.js`, `plan.js`; Test `random.test.js`, `plan.test.js`.

- [ ] **Step 1: Failing tests**

`random.test.js`:
```js
import { describe, expect, it } from 'vitest';
import { newSeed, rng, shuffled } from './random.js';

describe('rng', () => {
	it('gives the same sequence for the same seed and stays in [0, 1)', () => {
		const a = rng(42);
		const b = rng(42);
		const first = [a(), a(), a()];
		expect(first).toEqual([b(), b(), b()]);
		expect(first.every((x) => x >= 0 && x < 1)).toBe(true);
		expect(rng(43)()).not.toBe(first[0]);
	});
});

describe('shuffled', () => {
	it('is a permutation, reproducible per seed, and leaves its input alone', () => {
		const input = [1, 2, 3, 4, 5, 6];
		const out = shuffled(input, rng(1));
		expect([...out].sort()).toEqual(input);
		expect(shuffled(input, rng(1))).toEqual(out);
		expect(input).toEqual([1, 2, 3, 4, 5, 6]);
	});
});

describe('newSeed', () => {
	it('is a non-negative integer below 2**31', () => {
		for (let i = 0; i < 20; i++) {
			const seed = newSeed();
			expect(Number.isInteger(seed) && seed >= 0 && seed < 2 ** 31).toBe(true);
		}
	});
});
```

`plan.test.js` (sizes first; reconcile is added in Task 8):
```js
import { describe, expect, it } from 'vitest';
import { teamSizes } from './plan.js';

describe('teamSizes', () => {
	it.each([
		[10, 3, [3, 3, 2, 2]],
		[9, 3, [3, 3, 3]],
		[11, 3, [3, 3, 3, 2]],
		[7, 4, [4, 3]],
		[20, 5, [5, 5, 5, 5]]
	])('%i players, %i per team', (n, per, expected) => {
		const sizes = teamSizes(n, per);
		expect(sizes).toEqual(expected);
		expect(sizes.reduce((a, b) => a + b, 0)).toBe(n);
	});

	it('refuses fewer than two teams', () => {
		expect(teamSizes(3, 3)).toBeNull();
		expect(teamSizes(1, 3)).toBeNull();
		expect(teamSizes(0, 3)).toBeNull();
	});
});
```

- [ ] **Step 2: Run red.**
- [ ] **Step 3: Implement**

`random.js`:
```js
/** A small seeded generator (mulberry32): the same seed gives the same teams. */
export function rng(seed) {
	let a = seed >>> 0;
	return () => {
		a = (a + 0x6d2b79f5) >>> 0;
		let t = a;
		t = Math.imul(t ^ (t >>> 15), t | 1);
		t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
		return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
	};
}

/** A copy of `items` in a random order drawn from `random` (Fisher-Yates). */
export function shuffled(items, random) {
	const out = [...items];
	for (let i = out.length - 1; i > 0; i--) {
		const j = Math.floor(random() * (i + 1));
		[out[i], out[j]] = [out[j], out[i]];
	}
	return out;
}

/** A fresh seed the API accepts (a non-negative integer below 2**31). */
export const newSeed = () => Math.floor(Math.random() * 2 ** 31);
```

`plan.js`:
```js
/**
 * The team sizes for `n` players at about `perTeam` each: `ceil(n / perTeam)` teams, as even
 * as possible (sizes differ by at most one, the larger first). null when that is under two teams.
 */
export function teamSizes(n, perTeam) {
	const count = Math.ceil(n / perTeam);
	if (!Number.isFinite(count) || count < 2 || n < count) return null;
	const base = Math.floor(n / count);
	const extra = n % count;
	return Array.from({ length: count }, (_, i) => (i < extra ? base + 1 : base));
}
```

- [ ] **Step 4: Run green.** **Step 5: Commit** `[FEAT] builder: seeded generator and team sizes`.

### Task 8: Draft reconciliation

**Files:** Modify `plan.js`; Test `plan.test.js`.

- [ ] **Step 1: Failing tests** (append):

```js
import { reconcile, emptyDraft } from './plan.js';

const draftOf = (over = {}) => ({ ...emptyDraft(), ...over });
const roster = (...ids) => ids.map((id) => ({ id }));

describe('reconcile', () => {
	it('keeps a draft whose players are all still there', () => {
		const draft = draftOf({
			teams: [{ players: [1, 2] }, { players: [3] }],
			links: [{ player: 1, kind: 'with', target: 2 }],
			locked: [1]
		});

		const out = reconcile(draft, roster(1, 2, 3));

		expect(out.draft).toEqual(draft);
		expect(out.left).toBe(0);
		expect(out.joined).toBe(0);
	});

	it('drops departed players from the teams, the links and the locks', () => {
		const draft = draftOf({
			teams: [{ players: [1, 2] }, { players: [3, 4] }],
			links: [{ player: 1, kind: 'with', target: 2 }, { player: 3, kind: 'avoid', target: 4 }],
			locked: [2, 4]
		});

		const out = reconcile(draft, roster(1, 3, 4));

		expect(out.draft.teams).toEqual([{ players: [1] }, { players: [3, 4] }]);
		expect(out.draft.links).toEqual([{ player: 3, kind: 'avoid', target: 4 }]);
		expect(out.draft.locked).toEqual([4]);
		expect(out.left).toBe(1);
	});

	it('counts new registrants once teams were proposed, and none before', () => {
		const proposed = draftOf({ teams: [{ players: [1] }, { players: [2] }] });

		expect(reconcile(proposed, roster(1, 2, 3, 4)).joined).toBe(2);
		expect(reconcile(draftOf(), roster(1, 2, 3, 4)).joined).toBe(0);
	});

	it('lists who is not placed, in roster order', () => {
		const proposed = draftOf({ teams: [{ players: [2] }, { players: [4] }] });

		expect(reconcile(proposed, roster(1, 2, 3, 4)).unplaced).toEqual([1, 3]);
	});
});
```

- [ ] **Step 2: Run red.**
- [ ] **Step 3: Implement** (append to `plan.js`):

```js
import { newSeed } from './random.js';

/** A draft before any proposal. `perTeam` is the one input the organiser sets first. */
export const emptyDraft = (perTeam = 3) => ({
	players_per_team: perTeam,
	seed: newSeed(),
	links: [],
	teams: [],
	locked: []
});

/**
 * The saved draft against the roster as it is now: departed players leave the teams, the
 * links and the locks (so the server's strict check never trips on them), and `joined`
 * counts the players placed nowhere once teams exist (late registrants), `unplaced` lists
 * them all. `left` counts the departed players found in the draft.
 */
export function reconcile(draft, players) {
	const ids = new Set(players.map((p) => p.id));
	const inDraft = new Set(draft.teams.flatMap((t) => t.players));
	const left = [...inDraft].filter((id) => !ids.has(id)).length;
	const teams = draft.teams.map((t) => ({ players: t.players.filter((id) => ids.has(id)) }));
	const placed = new Set(teams.flatMap((t) => t.players));
	const unplaced = players.map((p) => p.id).filter((id) => !placed.has(id));
	return {
		draft: {
			...draft,
			teams,
			links: draft.links.filter((l) => ids.has(l.player) && ids.has(l.target)),
			locked: draft.locked.filter((id) => ids.has(id))
		},
		left,
		joined: draft.teams.length > 0 ? unplaced.length : 0,
		unplaced
	};
}
```

- [ ] **Step 4: Run green.** **Step 5: Commit** `[FEAT] builder: reconcile a saved draft with the roster`.

### Task 9: Name matching

**Files:** Create `front/src/lib/builder/names.js`; Test `names.test.js`.

- [ ] **Step 1: Failing tests**

```js
import { describe, expect, it } from 'vitest';
import { matchNames, normalise, splitNames } from './names.js';

const players = [
	{ id: 1, first_name: 'Léa', last_name: 'Martin' },
	{ id: 2, first_name: 'Paul', last_name: 'Durand' },
	{ id: 3, first_name: 'Paul', last_name: 'Petit' },
	{ id: 4, first_name: 'Inès', last_name: 'Moreau' },
	{ id: 5, first_name: 'Bob', last_name: 'Roux' }
];

describe('normalise', () => {
	it('drops accents and case and squeezes spaces', () => {
		expect(normalise('  LÉA   Martin ')).toBe('lea martin');
	});
});

describe('splitNames', () => {
	it('splits on commas, semicolons, lines, slashes, ampersands and "et"/"and"', () => {
		expect(splitNames('Léa, Paul; Inès\nBob / Léa & Paul et Bob and Léa')).toEqual([
			'Léa', 'Paul', 'Inès', 'Bob', 'Léa', 'Paul', 'Bob', 'Léa'
		]);
	});

	it('drops a leading "avec" and blanks', () => {
		expect(splitNames('Avec Léa,  , with Paul')).toEqual(['Léa', 'Paul']);
	});
});

describe('matchNames', () => {
	const best = (text, self = 99) => matchNames(text, players, self)[0];

	it('matches a whole name exactly, in either order, ignoring accents', () => {
		expect(best('lea martin')).toMatchObject({ best: 1, confidence: 'exact' });
		expect(best('Martin Léa')).toMatchObject({ best: 1, confidence: 'exact' });
	});

	it('matches a first name that is unique', () => {
		expect(best('Inès')).toMatchObject({ best: 4, confidence: 'first' });
	});

	it('does not pick between two players with the same first name', () => {
		const result = best('Paul');
		expect(result.best).toBeNull();
		expect(result.confidence).toBe('ambiguous');
		expect(result.candidates.map((c) => c.id).sort()).toEqual([2, 3]);
	});

	it('resolves a shared first name with a surname or initial', () => {
		expect(best('Paul Durand')).toMatchObject({ best: 2, confidence: 'exact' });
	});

	it('suggests, without preselecting, a first name one typo away', () => {
		const result = best('Ines');
		expect(result).toMatchObject({ best: 4 });
		const typo = best('Lia');
		expect(typo.best).toBeNull();
		expect(typo.confidence).toBe('near');
		expect(typo.candidates.map((c) => c.id)).toEqual([1]);
	});

	it('never offers the player themself', () => {
		expect(matchNames('Léa', players, 1)[0].candidates).toEqual([]);
	});

	it('leaves noise and unknown names without candidates', () => {
		for (const text of ['peu importe', 'personne', 'Zoé', 'n/a']) {
			expect(best(text)).toMatchObject({ best: null, candidates: [] });
		}
	});

	it('returns one entry per name, keeping the text', () => {
		expect(matchNames('Léa, Zoé', players, 99).map((m) => m.text)).toEqual(['Léa', 'Zoé']);
	});
});
```

- [ ] **Step 2: Run red.**
- [ ] **Step 3: Implement**

```js
/** Lower case, no accents, single spaces. */
export const normalise = (text) =>
	String(text ?? '')
		.normalize('NFD')
		.replace(/\p{M}/gu, '')
		.toLowerCase()
		.replace(/\s+/g, ' ')
		.trim();

const SEPARATORS = /[,;\n/&]+|\s+et\s+|\s+and\s+/i;
const LEADING = /^(avec|with)\s+/i;
const NOISE = new Set([
	'peu importe', 'personne', 'aucun', 'aucune', 'rien', 'n/a', 'na', 'none', 'nobody',
	'no one', 'anyone', 'whatever', 'pas de preference', 'idem', '-', '?'
]);

/** The names of a free-text answer, one per entry. */
export const splitNames = (text) =>
	String(text ?? '')
		.split(SEPARATORS)
		.map((part) => part.trim().replace(LEADING, '').trim())
		.filter(Boolean);

/** Edit distance, small strings only. */
function distance(a, b) {
	const row = Array.from({ length: b.length + 1 }, (_, j) => j);
	for (let i = 1; i <= a.length; i++) {
		let diagonal = row[0];
		row[0] = i;
		for (let j = 1; j <= b.length; j++) {
			const above = row[j];
			row[j] = Math.min(row[j] + 1, row[j - 1] + 1, diagonal + (a[i - 1] === b[j - 1] ? 0 : 1));
			diagonal = above;
		}
	}
	return row[b.length];
}

/**
 * For each name of `text`, the registered players it may mean: `{ text, best, confidence,
 * candidates: [{ id, confidence }] }`. `best` is preselected only for a whole-name match or a
 * first name only one player has; a first name shared by several players is `ambiguous`, a
 * first name one typo away is `near` (suggested, never preselected). The player themself is
 * never offered, and noise like « peu importe » matches nothing.
 */
export function matchNames(text, players, selfId) {
	const others = players.filter((p) => p.id !== selfId);
	const entries = others.map((p) => ({
		id: p.id,
		first: normalise(p.first_name),
		full: [`${normalise(p.first_name)} ${normalise(p.last_name)}`, `${normalise(p.last_name)} ${normalise(p.first_name)}`]
	}));
	return splitNames(text).map((raw) => {
		const name = normalise(raw);
		const none = { text: raw, best: null, confidence: 'none', candidates: [] };
		if (NOISE.has(name)) return none;
		const whole = entries.filter((e) => e.full.includes(name));
		if (whole.length === 1) return { text: raw, best: whole[0].id, confidence: 'exact', candidates: [{ id: whole[0].id, confidence: 'exact' }] };
		const sameFirst = entries.filter((e) => e.first === name);
		if (sameFirst.length === 1) return { text: raw, best: sameFirst[0].id, confidence: 'first', candidates: [{ id: sameFirst[0].id, confidence: 'first' }] };
		if (sameFirst.length > 1) {
			return { text: raw, best: null, confidence: 'ambiguous', candidates: sameFirst.map((e) => ({ id: e.id, confidence: 'ambiguous' })) };
		}
		if (name.length >= 3 && !name.includes(' ')) {
			const near = entries.filter((e) => distance(e.first, name) === 1);
			if (near.length > 0) return { text: raw, best: null, confidence: 'near', candidates: near.map((e) => ({ id: e.id, confidence: 'near' })) };
		}
		return none;
	});
}
```

Note: the spec's example « Ines » vs « Inès »: after normalising both are `ines`, so « Ines » is a **unique first name** (`first`), not `near`; the test above encodes that (`best: 4`). « Lia » is one edit from « lea » (`near`).

- [ ] **Step 4: Run green.** **Step 5: Commit** `[FEAT] builder: match the names of free-text requests to players`.

### Task 10: Scoring

**Files:** Create `front/src/lib/builder/score.js`; Test `score.test.js`.

- [ ] **Step 1: Failing tests**

```js
import { describe, expect, it } from 'vitest';
import { WEIGHTS, features, makeScorer } from './score.js';

const skills = [{ identifier: 'CARD' }, { identifier: 'STR' }];
const player = (id, over = {}) => ({
	id, rating: 5, ratings: { CARD: 5, STR: 5 }, sport_frequency: 'hour', sports: [], ...over
});

describe('features', () => {
	it('uses the ratings and flags the experienced', () => {
		expect(features(player(1, { ratings: { CARD: 8, STR: 2 } }), skills)).toMatchObject({
			rating: 5, skills: { CARD: 8, STR: 2 }, experienced: false, incomplete: false
		});
		expect(features(player(1, { sport_frequency: 'two_hours' }), skills).experienced).toBe(true);
		expect(features(player(1, { sports: [{ sport: 'Judo', level: 'league' }] }), skills).experienced).toBe(true);
		expect(features(player(1, { sports: [{ sport: 'Judo', level: 'club' }] }), skills).experienced).toBe(false);
	});

	it('falls back to the overall rating and the middle frequency, and says so', () => {
		const f = features(player(1, { rating: 7, ratings: { CARD: 9 }, sport_frequency: '' }), skills);

		expect(f.skills).toEqual({ CARD: 9, STR: 7 });
		expect(f.incomplete).toBe(true);
		expect(f.experienced).toBe(false);
	});

	it('does not call a player without sports incomplete', () => {
		expect(features(player(1), skills).incomplete).toBe(false);
	});
});

describe('makeScorer', () => {
	const ps = [
		player(1, { rating: 9, ratings: { CARD: 9, STR: 9 } }),
		player(2, { rating: 9, ratings: { CARD: 9, STR: 9 } }),
		player(3, { rating: 1, ratings: { CARD: 1, STR: 1 } }),
		player(4, { rating: 1, ratings: { CARD: 1, STR: 1 } })
	];
	const scorer = (links = []) => makeScorer(ps, links, skills);

	it('scores a balanced split below an unbalanced one', () => {
		const score = scorer();

		expect(score([[1, 3], [2, 4]]).total).toBeLessThan(score([[1, 2], [3, 4]]).total);
		expect(score([[1, 3], [2, 4]]).parts.rating).toBe(0);
	});

	it('balances each skill, not only the overall rating', () => {
		const odd = [
			player(1, { rating: 5, ratings: { CARD: 9, STR: 1 } }),
			player(2, { rating: 5, ratings: { CARD: 9, STR: 1 } }),
			player(3, { rating: 5, ratings: { CARD: 1, STR: 9 } }),
			player(4, { rating: 5, ratings: { CARD: 1, STR: 9 } })
		];
		const score = makeScorer(odd, [], skills);

		expect(score([[1, 3], [2, 4]]).parts.rating).toBe(0);
		expect(score([[1, 3], [2, 4]]).parts.skills).toBe(0);
		expect(score([[1, 2], [3, 4]]).parts.skills).toBeGreaterThan(0);
	});

	it('reports an unmet "with" and a broken "avoid", once per pair', () => {
		const links = [
			{ player: 1, kind: 'with', target: 3 },
			{ player: 3, kind: 'with', target: 1 },
			{ player: 2, kind: 'avoid', target: 4 }
		];
		const result = scorer(links)([[1, 2, 4], [3]]);

		expect(result.unmet).toEqual([
			{ kind: 'with', player: 1, target: 3, mutual: true },
			{ kind: 'avoid', player: 2, target: 4, mutual: false }
		]);
	});

	it('counts a request met when it is, and ignores one with an unplaced player', () => {
		const links = [{ player: 1, kind: 'with', target: 2 }, { player: 3, kind: 'avoid', target: 4 }];

		expect(scorer(links)([[1, 2], [3]]).unmet).toEqual([]);
	});

	it('weighs a broken avoid above an unmet mutual with above a one-sided with', () => {
		expect(WEIGHTS.avoid).toBeGreaterThan(2 * WEIGHTS.with);
		expect(WEIGHTS.with).toBeGreaterThan(0);
		const teams = [[1, 3], [2, 4]];
		const withOne = scorer([{ player: 1, kind: 'with', target: 2 }])(teams).total;
		const withMutual = scorer([{ player: 1, kind: 'with', target: 2 }, { player: 2, kind: 'with', target: 1 }])(teams).total;
		const avoid = scorer([{ player: 1, kind: 'avoid', target: 3 }])(teams).total;
		const none = scorer()(teams).total;
		expect(withOne).toBeGreaterThan(none);
		expect(withMutual).toBeGreaterThan(withOne);
		expect(avoid).toBeGreaterThan(withMutual);
	});

	it('returns each team average rating and skill averages for the display', () => {
		const result = scorer()([[1, 3], [2, 4]]);

		expect(result.teams).toEqual([
			{ size: 2, rating: 5, skills: { CARD: 5, STR: 5 }, experienced: 0 },
			{ size: 2, rating: 5, skills: { CARD: 5, STR: 5 }, experienced: 0 }
		]);
	});
});
```

- [ ] **Step 2: Run red.**
- [ ] **Step 3: Implement**

```js
/**
 * Features and the balance score of a team assignment (spec 2026-10-05-team-builder).
 * Pure: the generator and the live display use the same scorer.
 */

/**
 * The cost of each term, in the same units as a standard deviation of team averages scaled
 * to ten. An unmet "with" costs less than a visible rating gap; a broken "avoid" more than
 * an unmet mutual "with" (the tests pin the order, not the numbers).
 */
export const WEIGHTS = { rating: 10, skills: 5, experience: 4, with: 2, avoid: 6 };

const FREQUENCY_RANK = { rare: 0, monthly: 1, hour: 2, two_hours: 3, four_hours: 4 };
const EXPERIENCED_FREQUENCY = 3;
const EXPERIENCED_LEVELS = new Set(['league', 'regional']);
const FALLBACK_FREQUENCY = 'hour';

/** What the scorer reads of a player; a missing skill counts as the overall rating. */
export function features(player, skills) {
	let incomplete = false;
	const values = {};
	for (const { identifier } of skills) {
		const value = player.ratings?.[identifier];
		if (value === undefined || value === null) incomplete = true;
		values[identifier] = value ?? player.rating;
	}
	if (!player.sport_frequency) incomplete = true;
	const rank = FREQUENCY_RANK[player.sport_frequency || FALLBACK_FREQUENCY] ?? FREQUENCY_RANK[FALLBACK_FREQUENCY];
	const experienced =
		rank >= EXPERIENCED_FREQUENCY || (player.sports ?? []).some((s) => EXPERIENCED_LEVELS.has(s.level));
	return { rating: player.rating, skills: values, experienced, incomplete };
}

const mean = (values) => (values.length ? values.reduce((a, b) => a + b, 0) / values.length : 0);
const deviation = (values) => {
	const m = mean(values);
	return Math.sqrt(mean(values.map((v) => (v - m) ** 2)));
};

/**
 * A scorer for a roster, its confirmed `links` and the edition's `skills`: call it with the
 * teams (arrays of player ids; a player in no team is simply not counted) to get
 * `{ total, parts, unmet, teams }`. `unmet` lists each broken request once (a pair that asked
 * for each other is one mutual "with"); `teams` carries the per-team averages for the display.
 */
export function makeScorer(players, links, skills, weights = WEIGHTS) {
	const byId = new Map(players.map((p) => [p.id, features(p, skills)]));
	const withs = links.filter((l) => l.kind === 'with');
	const avoids = links.filter((l) => l.kind === 'avoid');
	const wants = new Set(withs.map((l) => `${l.player}>${l.target}`));

	return (teams) => {
		const teamOf = new Map();
		teams.forEach((ids, index) => ids.forEach((id) => teamOf.set(id, index)));
		const rows = teams.map((ids) => {
			const fs = ids.map((id) => byId.get(id)).filter(Boolean);
			return {
				size: fs.length,
				rating: mean(fs.map((f) => f.rating)),
				skills: Object.fromEntries(skills.map((s) => [s.identifier, mean(fs.map((f) => f.skills[s.identifier]))])),
				experienced: fs.filter((f) => f.experienced).length
			};
		});

		const parts = {
			rating: deviation(rows.map((r) => r.rating)) * weights.rating,
			skills:
				(skills.length ? mean(skills.map((s) => deviation(rows.map((r) => r.skills[s.identifier])))) : 0) * weights.skills,
			experience: deviation(rows.map((r) => (r.size ? r.experienced / r.size : 0))) * weights.experience,
			with: 0,
			avoid: 0
		};

		const unmet = [];
		const seen = new Set();
		for (const link of withs) {
			const a = teamOf.get(link.player);
			const b = teamOf.get(link.target);
			if (a === undefined || b === undefined || a === b) continue;
			const mutual = wants.has(`${link.target}>${link.player}`);
			const key = [link.player, link.target].sort().join('-');
			if (mutual && seen.has(key)) continue;
			seen.add(key);
			unmet.push({ kind: 'with', player: link.player, target: link.target, mutual });
			parts.with += mutual ? 2 * weights.with : weights.with;
		}
		const avoidSeen = new Set();
		for (const link of avoids) {
			const a = teamOf.get(link.player);
			const b = teamOf.get(link.target);
			if (a === undefined || a !== b) continue;
			const key = [link.player, link.target].sort().join('-');
			if (avoidSeen.has(key)) continue;
			avoidSeen.add(key);
			unmet.push({ kind: 'avoid', player: link.player, target: link.target, mutual: false });
			parts.avoid += weights.avoid;
		}

		const total = parts.rating + parts.skills + parts.experience + parts.with + parts.avoid;
		return { total, parts, unmet, teams: rows };
	};
}
```

Check the tests' expectations against the code: in the « unmet » test the expected order is the with first then the avoid, and the mutual pair (1↔3) is reported once with `mutual: true` using the first link seen (`player: 1, target: 3`). Fix the code or the test if they disagree; do not weaken what they pin.

- [ ] **Step 4: Run green.** **Step 5: Commit** `[FEAT] builder: features and the balance scorer`.

### Task 11: Generator

**Files:** Create `front/src/lib/builder/generate.js`; Test `generate.test.js`.

- [ ] **Step 1: Failing tests**

```js
import { describe, expect, it } from 'vitest';
import { generate, placeNewcomers } from './generate.js';
import { makeScorer } from './score.js';

const skills = [{ identifier: 'CARD' }, { identifier: 'STR' }];
const roster = (n) =>
	Array.from({ length: n }, (_, i) => ({
		id: i + 1,
		rating: 1 + ((i * 7) % 10),
		ratings: { CARD: 1 + ((i * 3) % 10), STR: 1 + ((i * 5) % 10) },
		sport_frequency: ['rare', 'hour', 'two_hours', 'four_hours'][i % 4],
		sports: []
	}));

const sizesOf = (teams) => teams.map((t) => t.length).sort((a, b) => b - a);

describe('generate', () => {
	it('places everyone exactly once in evenly sized teams', () => {
		const players = roster(11);

		const { teams } = generate(players, [], skills, { perTeam: 3, seed: 1 });

		expect(sizesOf(teams)).toEqual([3, 3, 3, 2]);
		expect(teams.flat().sort((a, b) => a - b)).toEqual(players.map((p) => p.id));
	});

	it('gives the same teams for the same seed and different ones for another', () => {
		const players = roster(14);
		const a = generate(players, [], skills, { perTeam: 3, seed: 5 }).teams;
		const b = generate(players, [], skills, { perTeam: 3, seed: 5 }).teams;

		expect(a).toEqual(b);
	});

	it('does better than the plain greedy start', () => {
		const players = roster(14);
		const scorer = makeScorer(players, [], skills);
		const sorted = [...players].sort((x, y) => y.rating - x.rating).map((p) => p.id);
		const naive = [sorted.slice(0, 4), sorted.slice(4, 8), sorted.slice(8, 11), sorted.slice(11)];

		const { score } = generate(players, [], skills, { perTeam: 4, seed: 2 });

		expect(score.total).toBeLessThan(scorer(naive).total);
	});

	it('separates an avoid pair and keeps a mutual with pair together when balance allows', () => {
		const players = roster(12);
		const links = [
			{ player: 1, kind: 'avoid', target: 2 },
			{ player: 3, kind: 'with', target: 4 },
			{ player: 4, kind: 'with', target: 3 }
		];

		const { teams, score } = generate(players, links, skills, { perTeam: 3, seed: 9 });

		const teamOf = (id) => teams.findIndex((t) => t.includes(id));
		expect(teamOf(1)).not.toBe(teamOf(2));
		expect(teamOf(3)).toBe(teamOf(4));
		expect(score.unmet).toEqual([]);
	});

	it('leaves locked players in their team', () => {
		const players = roster(12);
		const first = generate(players, [], skills, { perTeam: 3, seed: 1 }).teams;
		const locked = [first[0][0], first[2][1]];

		const again = generate(players, [], skills, { perTeam: 3, seed: 77, current: first, locked }).teams;

		expect(again[0]).toContain(locked[0]);
		expect(again[2]).toContain(locked[1]);
	});

	it('reports a roster too small for two teams', () => {
		expect(() => generate(roster(3), [], skills, { perTeam: 3, seed: 1 })).toThrow(/too_few/);
	});
});

describe('placeNewcomers', () => {
	it('puts each newcomer in a smallest team and moves nobody else', () => {
		const players = roster(11);
		const base = generate(players.slice(0, 8), [], skills, { perTeam: 3, seed: 1 }).teams; // 3, 3, 2
		const before = base.map((t) => [...t]);

		const out = placeNewcomers(players, [], skills, base, [9, 10, 11]);

		expect(out.map((t) => t.length).sort()).toEqual([3, 4, 4].sort());
		out.forEach((team, i) => before[i].forEach((id) => expect(team).toContain(id)));
		expect(out.flat().sort((a, b) => a - b)).toEqual(players.map((p) => p.id));
		expect(Math.max(...out.map((t) => t.length)) - Math.min(...out.map((t) => t.length))).toBeLessThanOrEqual(1);
	});

	it('keeps a newcomer away from someone they avoid when it can', () => {
		const players = roster(7);
		const teams = [[1, 2, 3], [4, 5, 6]];
		const links = [{ player: 7, kind: 'avoid', target: 1 }];

		const out = placeNewcomers(players, links, skills, teams, [7]);

		expect(out[0]).not.toContain(7);
	});

	it('returns the teams unchanged without newcomers', () => {
		expect(placeNewcomers(roster(4), [], skills, [[1, 2], [3, 4]], [])).toEqual([[1, 2], [3, 4]]);
	});
});
```

- [ ] **Step 2: Run red.**
- [ ] **Step 3: Implement**

```js
import { rng, shuffled } from './random.js';
import { teamSizes } from './plan.js';
import { makeScorer } from './score.js';

const RESTARTS = 5;
const MAX_PASSES = 60;

/** A failure the page words: `too_few` (fewer than two teams of the asked size). */
export class BuilderError extends Error {
	constructor(code) {
		super(code);
		this.code = code;
	}
}

/**
 * Evenly sized, balanced teams for `players` (spec 2026-10-05-team-builder). Locked players
 * (`locked`, ids) stay in their team of `current` (arrays of ids); everyone else starts from a
 * greedy placement, strongest first into the team with the lowest rating total and room left,
 * then improves by swapping two unlocked players while the score drops, over a few seeded
 * restarts. Returns `{ teams, score }` (`score` the scorer's result). Same input and seed,
 * same teams.
 */
export function generate(players, links, skills, { perTeam, seed, current = null, locked = [] }) {
	const sizes = teamSizes(players.length, perTeam);
	if (!sizes) throw new BuilderError('too_few');
	const score = makeScorer(players, links, skills);
	const byId = new Map(players.map((p) => [p.id, p]));
	const random = rng(seed);

	// Locked players keep their place when that team exists and has room.
	const fixed = sizes.map(() => []);
	const lockedSet = new Set();
	(current ?? []).forEach((ids, index) => {
		if (index >= sizes.length) return;
		for (const id of ids) {
			if (locked.includes(id) && byId.has(id) && fixed[index].length < sizes[index]) {
				fixed[index].push(id);
				lockedSet.add(id);
			}
		}
	});
	const free = players.filter((p) => !lockedSet.has(p.id));

	const place = (order) => {
		const teams = fixed.map((ids) => [...ids]);
		const totals = teams.map((ids) => ids.reduce((sum, id) => sum + byId.get(id).rating, 0));
		for (const player of order) {
			let target = -1;
			teams.forEach((ids, i) => {
				if (ids.length >= sizes[i]) return;
				if (target === -1 || totals[i] < totals[target]) target = i;
			});
			teams[target].push(player.id);
			totals[target] += player.rating;
		}
		return teams;
	};

	const improve = (teams) => {
		let best = score(teams);
		for (let pass = 0; pass < MAX_PASSES; pass++) {
			let improved = false;
			for (let a = 0; a < teams.length; a++) {
				for (let b = a + 1; b < teams.length; b++) {
					for (let i = 0; i < teams[a].length; i++) {
						if (lockedSet.has(teams[a][i])) continue;
						for (let j = 0; j < teams[b].length; j++) {
							if (lockedSet.has(teams[b][j])) continue;
							[teams[a][i], teams[b][j]] = [teams[b][j], teams[a][i]];
							const next = score(teams);
							if (next.total < best.total - 1e-9) {
								best = next;
								improved = true;
							} else {
								[teams[a][i], teams[b][j]] = [teams[b][j], teams[a][i]];
							}
						}
					}
				}
			}
			if (!improved) break;
		}
		return { teams, score: best };
	};

	const byStrength = [...free].sort((x, y) => y.rating - x.rating || x.id - y.id);
	let best = improve(place(byStrength));
	for (let restart = 1; restart < RESTARTS; restart++) {
		const candidate = improve(place(shuffled(free, random)));
		if (candidate.score.total < best.score.total) best = candidate;
	}
	return best;
}

/**
 * Place `ids` (the players of the tray) into `teams` without moving anyone: strongest first,
 * each into the team that scores best among the smallest ones, so sizes keep differing by at
 * most one. Returns new arrays; `teams` is untouched.
 */
export function placeNewcomers(players, links, skills, teams, ids) {
	const score = makeScorer(players, links, skills);
	const byId = new Map(players.map((p) => [p.id, p]));
	const out = teams.map((t) => [...t]);
	const order = [...ids].sort((a, b) => byId.get(b).rating - byId.get(a).rating || a - b);
	for (const id of order) {
		const smallest = Math.min(...out.map((t) => t.length));
		let best = null;
		out.forEach((team, index) => {
			if (team.length !== smallest) return;
			team.push(id);
			const total = score(out).total;
			team.pop();
			if (best === null || total < best.total) best = { index, total };
		});
		out[best.index].push(id);
	}
	return out;
}
```


If a test's expectation (separating the avoid pair, keeping the mutual pair) is not met with these constants, adjust `RESTARTS`/search, not the test. Keep the whole module under a second for 50 players: add a test that runs `roster(50)` with `perTeam: 4` and asserts it returns within 1500 ms.

- [ ] **Step 4: Run green.** **Step 5: Commit** `[FEAT] builder: the team generator`.

### Task 12: Draft saver and the payload fixture

**Files:** Create `front/src/lib/builder/saver.js`, `front/src/lib/fixtures/builder.js`; Test `saver.test.js`.

- [ ] **Step 1: Failing tests** (`saver.test.js`, fake timers):

```js
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createSaver } from './saver.js';

const reply = (status, body) => Promise.resolve({ status, ok: status < 300, json: () => Promise.resolve(body) });

describe('createSaver', () => {
	beforeEach(() => vi.useFakeTimers());
	afterEach(() => vi.useRealTimers());

	it('saves once, debounced, with the version it was based on, and keeps the new one', async () => {
		const fetch = vi.fn(() => reply(200, { document: {}, updated_at: 'v2' }));
		const saved = vi.fn();
		const saver = createSaver({ url: '/x', fetch, based_on: 'v1', onSaved: saved });

		saver.save({ a: 1 });
		saver.save({ a: 2 });
		await vi.advanceTimersByTimeAsync(900);

		expect(fetch).toHaveBeenCalledTimes(1);
		expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ document: { a: 2 }, based_on: 'v1' });
		expect(saved).toHaveBeenCalledWith('v2');
		saver.save({ a: 3 });
		await vi.advanceTimersByTimeAsync(900);
		expect(JSON.parse(fetch.mock.calls[1][1].body).based_on).toBe('v2');
	});

	it('reports a stale draft with the stored one and stops saving', async () => {
		const fetch = vi.fn(() => reply(409, { error: 'stale_draft', draft: { document: { a: 9 }, updated_at: 'v9' } }));
		const stale = vi.fn();
		const saver = createSaver({ url: '/x', fetch, based_on: 'v1', onStale: stale });

		saver.save({ a: 1 });
		await vi.advanceTimersByTimeAsync(900);

		expect(stale).toHaveBeenCalledWith({ document: { a: 9 }, updated_at: 'v9' });
		saver.save({ a: 2 });
		await vi.advanceTimersByTimeAsync(900);
		expect(fetch).toHaveBeenCalledTimes(1);
	});

	it('reports other failures and lets the next change try again', async () => {
		const fetch = vi.fn(() => reply(500, {}));
		const failed = vi.fn();
		const saver = createSaver({ url: '/x', fetch, based_on: null, onError: failed });

		saver.save({ a: 1 });
		await vi.advanceTimersByTimeAsync(900);
		saver.save({ a: 2 });
		await vi.advanceTimersByTimeAsync(900);

		expect(failed).toHaveBeenCalledTimes(2);
		expect(fetch).toHaveBeenCalledTimes(2);
	});

	it('exposes the version it holds, for an apply to name', async () => {
		const fetch = vi.fn(() => reply(200, { document: {}, updated_at: 'v2' }));
		const saver = createSaver({ url: '/x', fetch, based_on: 'v1' });

		expect(saver.version()).toBe('v1');
		saver.save({ a: 1 });
		await vi.advanceTimersByTimeAsync(900);
		expect(saver.version()).toBe('v2');
	});

	it('flush saves a pending change at once', async () => {
		const fetch = vi.fn(() => reply(200, { document: {}, updated_at: 'v2' }));
		const saver = createSaver({ url: '/x', fetch, based_on: null });

		saver.save({ a: 1 });
		await saver.flush();

		expect(fetch).toHaveBeenCalledTimes(1);
	});
});
```

- [ ] **Step 2: Run red.**
- [ ] **Step 3: Implement** `saver.js`:

```js
const DELAY = 800;

/**
 * Saves the builder's draft to the page's own endpoint, debounced, each save based on the
 * version the last one returned. A 409 hands the stored draft to `onStale` and stops saving
 * until the page loads that draft (a new saver); any other failure goes to `onError` and the
 * next change tries again.
 */
export function createSaver({ url, fetch = globalThis.fetch, based_on = null, onSaved, onStale, onError }) {
	let version = based_on;
	let timer = null;
	let pending = null;
	let stopped = false;

	async function send() {
		if (pending === null || stopped) return;
		const document = pending;
		pending = null;
		try {
			const response = await fetch(url, {
				method: 'PUT',
				headers: { 'content-type': 'application/json' },
				body: JSON.stringify({ document, based_on: version })
			});
			const body = await response.json().catch(() => ({}));
			if (response.status === 409) {
				stopped = true;
				onStale?.(body.draft ?? null);
			} else if (response.ok) {
				version = body.updated_at;
				onSaved?.(version);
			} else {
				onError?.(response.status);
			}
		} catch {
			onError?.(0);
		}
	}

	return {
		version: () => version,
		save(document) {
			pending = document;
			clearTimeout(timer);
			timer = setTimeout(send, DELAY);
		},
		async flush() {
			clearTimeout(timer);
			await send();
		}
	};
}
```

`fixtures/builder.js` (used by the page tests):

```js
const player = (id, first, last, over = {}) => ({
	id, first_name: first, last_name: last, rating: 5, global_level: 5,
	ratings: { CARD: 5, STR: 5 }, sport_frequency: 'hour', sports: [],
	team_with: '', team_avoid: '', team: null, ...over
});

export const builderPayload = {
	edition: { year: 2029 },
	skills: [
		{ identifier: 'CARD', name_fr: 'Cardio', name_en: 'Cardio' },
		{ identifier: 'STR', name_fr: 'Force', name_en: 'Strength' }
	],
	registration_open: false,
	teams_exist: false,
	players: [
		player(1, 'Léa', 'Martin', { rating: 8, ratings: { CARD: 9, STR: 7 }, sport_frequency: 'four_hours', team_with: 'Paul Durand', team_avoid: 'Zoé' }),
		player(2, 'Paul', 'Durand', { rating: 6, ratings: { CARD: 5, STR: 7 }, team_with: 'Léa' }),
		player(3, 'Paul', 'Petit', { rating: 4, ratings: { CARD: 3, STR: 5 }, sports: [{ sport: 'Judo', level: 'league' }] }),
		player(4, 'Inès', 'Moreau', { rating: 7, ratings: { CARD: 6, STR: 8 }, team_avoid: 'Bob' }),
		player(5, 'Bob', 'Roux', { rating: 3, ratings: {}, sport_frequency: '' }),
		player(6, 'Zoé', 'Blanc', { rating: 5, ratings: { CARD: 5, STR: 5 } })
	],
	draft: null
};
```

- [ ] **Step 4: Run green.** **Step 5: Commit** `[FEAT] builder: the debounced draft saver and the payload fixture`.

### Task 13: Page load and JSON endpoints

**Files:** Create `front/src/lib/server/builder-proxy.js`, `routes/[year=year]/builder/+page.server.js`, `draft/+server.js`, `apply/+server.js`; Test `+page.server.test.js`, `endpoints.test.js` (same folder).

- [ ] **Step 1: Failing tests.** `+page.server.test.js` (look at `routes/account/page.server.test.js` for how an event is faked, and copy its style):

```js
import { describe, expect, it, vi } from 'vitest';
import { load } from './+page.server.js';
import { builderPayload } from '$lib/fixtures/builder.js';

vi.mock('$lib/server/urls', () => ({ api: (p) => `http://api${p}` }));

const event = (over = {}) => ({
	params: { year: '2029' },
	cookies: { get: () => 'tok' },
	setHeaders: vi.fn(),
	fetch: vi.fn(async () => new Response(JSON.stringify(builderPayload), { headers: { 'content-type': 'application/json' } })),
	parent: async () => ({ organiser: true, latestYear: 2029 }),
	url: new URL('http://site/2029/builder'),
	...over
});

describe('builder load', () => {
	it('sends a visitor to the login, a player home with a 403', async () => {
		await expect(load(event({ cookies: { get: () => undefined }, parent: async () => ({ organiser: false, latestYear: 2029 }) }))).rejects.toMatchObject({ status: 303, location: '/login?next=/2029/builder' });
		await expect(load(event({ parent: async () => ({ organiser: false, latestYear: 2029 }) }))).rejects.toMatchObject({ status: 403 });
	});

	it('is 404 for a year that is not the latest', async () => {
		await expect(load(event({ params: { year: '2028' } }))).rejects.toMatchObject({ status: 404 });
	});

	it('loads the payload with the token and never caches it', async () => {
		const e = event();

		const data = await load(e);

		expect(data.builder).toEqual(builderPayload);
		expect(e.fetch.mock.calls[0][0]).toBe('http://api/builder/2029/');
		expect(e.fetch.mock.calls[0][1].headers.authorization).toBe('Token tok');
		expect(e.setHeaders).toHaveBeenCalledWith({ 'cache-control': 'private, no-store' });
	});
});
```

(A visitor is told apart from a logged-in non-organiser by the missing token cookie: the root layout's `organiser` is false for both.) `endpoints.test.js`:

```js
import { describe, expect, it, vi } from 'vitest';
import { PUT, DELETE } from './draft/+server.js';
import { POST } from './apply/+server.js';

vi.mock('$lib/server/urls', () => ({ api: (p) => `http://api${p}` }));

const call = (handler, over = {}) =>
	handler({
		params: { year: '2029' },
		cookies: { get: () => 'tok' },
		request: new Request('http://site/x', { method: 'PUT', body: JSON.stringify({ document: { a: 1 }, based_on: null }), headers: { 'content-type': 'application/json' } }),
		fetch: vi.fn(async () => new Response(JSON.stringify({ updated_at: 'v1' }), { status: 200, headers: { 'content-type': 'application/json' } })),
		...over
	});

describe('builder endpoints', () => {
	it('forward the draft with the token and pass status and body through', async () => {
		const fetch = vi.fn(async () => new Response(JSON.stringify({ error: 'stale_draft', draft: null }), { status: 409, headers: { 'content-type': 'application/json' } }));

		const response = await call(PUT, { fetch });

		expect(fetch.mock.calls[0][0]).toBe('http://api/builder/2029/draft/');
		expect(fetch.mock.calls[0][1]).toMatchObject({ method: 'PUT' });
		expect(fetch.mock.calls[0][1].headers.authorization).toBe('Token tok');
		expect(response.status).toBe(409);
		expect(await response.json()).toEqual({ error: 'stale_draft', draft: null });
	});

	it('refuse without a token', async () => {
		expect((await call(PUT, { cookies: { get: () => undefined } })).status).toBe(401);
		expect((await call(POST, { cookies: { get: () => undefined } })).status).toBe(401);
	});

	it('delete and apply go to their API routes, apply with its body', async () => {
		const fetch = vi.fn(async () => new Response(null, { status: 204 }));

		await call(DELETE, { fetch });
		await call(POST, { fetch });

		expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({ document: { a: 1 }, based_on: null });
		expect(fetch.mock.calls.map((c) => [c[0], c[1].method])).toEqual([
			['http://api/builder/2029/draft/', 'DELETE'],
			['http://api/builder/2029/apply/', 'POST']
		]);
	});

	it('refuse a year that is not four digits', async () => {
		expect((await call(PUT, { params: { year: 'abc' } })).status).toBe(404);
	});
});
```

- [ ] **Step 2: Run red.**
- [ ] **Step 3: Implement.** `builder-proxy.js`:

```js
import { json } from '@sveltejs/kit';
import { api } from '$lib/server/urls';
import { TOKEN_COOKIE } from '$lib/session';

/**
 * Forward one of the builder page's JSON calls to the API with the organiser's token, and
 * hand the answer back as it is (status and body: a 409 carries the stored draft).
 * `year` is spliced into an API path, so only four digits reach it.
 */
export async function forward({ fetch, cookies, params, request }, method, path, withBody = false) {
	const token = cookies.get(TOKEN_COOKIE);
	if (!token) return json({ error: 'unauthorised' }, { status: 401 });
	if (!/^\d{4}$/.test(params.year)) return json({ error: 'not_found' }, { status: 404 });
	const headers = { authorization: `Token ${token}` };
	const options = { method, headers };
	if (withBody) {
		headers['content-type'] = 'application/json';
		options.body = await request.text();
	}
	let response;
	try {
		response = await fetch(api(`/builder/${params.year}${path}`), options);
	} catch {
		return json({ error: 'unreachable' }, { status: 502 });
	}
	const body = response.status === 204 ? null : await response.text();
	return new Response(body, {
		status: response.status,
		headers: { 'content-type': 'application/json', 'cache-control': 'private, no-store' }
	});
}
```

`draft/+server.js`:
```js
import { forward } from '$lib/server/builder-proxy';

export const PUT = (event) => forward(event, 'PUT', '/draft/', true);
export const DELETE = (event) => forward(event, 'DELETE', '/draft/');
```
`apply/+server.js`:
```js
import { forward } from '$lib/server/builder-proxy';

export const POST = (event) => forward(event, 'POST', '/apply/', true);
```

`+page.server.js`:
```js
import { error, redirect } from '@sveltejs/kit';
import { apiGet } from '$lib/api';
import { api } from '$lib/server/urls';
import { TOKEN_COOKIE } from '$lib/session';

/** The team builder: organisers only, the latest edition only, never cached (private answers). */
export const load = async ({ params, cookies, fetch, parent, setHeaders }) => {
	const { organiser, latestYear } = await parent();
	const token = cookies.get(TOKEN_COOKIE);
	if (!token) redirect(303, `/login?next=/${params.year}/builder`);
	if (!organiser) error(403, 'Organisers only');
	if (Number(params.year) !== latestYear) error(404, `No builder for ${params.year}`);
	setHeaders({ 'cache-control': 'private, no-store' });
	return { builder: await apiGet(fetch, api(`/builder/${params.year}/`), token) };
};
```

- [ ] **Step 4: Run green.** **Step 5: Commit** `[FEAT] builder page load and JSON endpoints`.

### Task 14: Dictionaries

**Files:** `front/src/lib/i18n/fr.js`, `en.js` (parity test).

- [ ] **Step 1:** Add to both (after the `register.*` block), French first:

```js
	'builder.title': "Constituer les équipes",
	'builder.steps.label': 'Étapes du constructeur',
	'builder.step.1': 'Demandes',
	'builder.step.2': 'Équipes',
	'builder.step.3': 'Appliquer',
	'builder.link': "Constituer les équipes",
	'builder.exists': "Cette édition a déjà des équipes : déplacez les joueurs depuis l'administration (liste des joueurs, colonne Équipe).",
	'builder.noPlayers': "Aucun joueur inscrit pour l'instant.",
	'builder.banner': { one: '{joined} nouvel inscrit à placer', other: '{joined} nouveaux inscrits à placer' },
	'builder.bannerLeft': { one: '{left} désistement retiré des équipes', other: '{left} désistements retirés des équipes' },
	'builder.requests.intro': 'Associez chaque nom des demandes à un joueur inscrit. Seules les demandes confirmées comptent.',
	'builder.requests.none': 'Aucune demande à examiner.',
	'builder.requests.with': 'veut être avec',
	'builder.requests.avoid': 'préfère éviter',
	'builder.requests.other': 'Autre joueur…',
	'builder.requests.noMatch': 'Aucun joueur correspondant',
	'builder.requests.confirm': 'Confirmer {name}',
	'builder.perTeam': 'Joueurs par équipe',
	'builder.perTeamLocked': 'Réinitialisez pour changer ce nombre.',
	'builder.counts': { one: '{n} équipe', other: '{n} équipes' },
	'builder.propose': 'Proposer des équipes',
	'builder.reroll': 'Relancer',
	'builder.placeNew': 'Placer les nouveaux',
	'builder.moveToTray': "Retirer de l'équipe",
	'builder.showRequests': 'Afficher les demandes sur les cartes',
	'builder.error.stale_draft': 'Le brouillon a changé depuis votre dernier enregistrement : rechargez la page.',
	'builder.apply.public': 'Les équipes seront visibles publiquement dès leur création.',
	'builder.reset': 'Tout réinitialiser',
	'builder.resetConfirm': { one: 'Effacer {n} placement ou verrou ? Les liens confirmés sont gardés.', other: 'Effacer {n} placements et verrous ? Les liens confirmés sont gardés.' },
	'builder.tooFew': "Il faut au moins deux équipes : baissez le nombre de joueurs par équipe.",
	'builder.tray': 'À placer',
	'builder.team': 'Équipe {n}',
	'builder.size': { one: '{n} joueur', other: '{n} joueurs' },
	'builder.average': 'moy. {rating}',
	'builder.move': 'Déplacer {name}',
	'builder.moveTo': 'Déplacer vers…',
	'builder.lock': 'Verrouiller {name}',
	'builder.unlock': 'Déverrouiller {name}',
	'builder.incomplete': 'Profil incomplet',
	'builder.skills': 'Compétences',
	'builder.unmet': 'Demandes non satisfaites',
	'builder.unmetNone': 'Toutes les demandes confirmées sont satisfaites.',
	'builder.unmet.with': '{player} voulait être avec {target}',
	'builder.unmet.avoid': '{player} préfère éviter {target}',
	'builder.unmet.mutual': ' (réciproque)',
	'builder.apply.summary': { one: '{teams} équipes, {n} joueur placé', other: '{teams} équipes, {n} joueurs placés' },
	'builder.apply.unplaced': { one: '{n} joueur reste à placer', other: '{n} joueurs restent à placer' },
	'builder.apply.open': "Les inscriptions sont encore ouvertes : les nouveaux inscrits n'auront pas d'équipe.",
	'builder.apply.confirmOpen': "Je crée quand même les équipes",
	'builder.apply.button': 'Créer les équipes',
	'builder.apply.done': 'Équipes créées.',
	'builder.apply.unscheduled': 'Épreuves à planifier dans l\'administration :',
	'builder.save.saved': 'Brouillon enregistré',
	'builder.save.error': "L'enregistrement du brouillon a échoué : réessayez.",
	'builder.stale': "Quelqu'un d'autre a modifié le brouillon.",
	'builder.stale.load': 'Charger leur version',
	'builder.error.no_draft': "Il n'y a pas de brouillon à appliquer.",
	'builder.error.teams_exist': "Cette édition a déjà des équipes.",
	'builder.error.incomplete': "Tous les joueurs ne sont pas placés exactement une fois : rechargez la page.",
	'builder.error.bad_size': 'Les équipes doivent avoir des tailles à un joueur près.',
	'builder.error.failed': "L'action a échoué : réessayez.",
```

English equivalents under the same keys (« Show the requests on the cards », « The draft changed since you last saved: reload the page », « Place the newcomers », « Take out of the team », « The teams will be public as soon as they are created », « Build the teams », « Requests », « Teams », « Apply », « Link each name … », « wants to be with », « would rather avoid », « Players per team », « Propose teams », « Re-roll », « Reset everything », « To place », « Team {n} », « Incomplete profile », « Create the teams », and so on, same plural shapes).

- [ ] **Step 2:** `npx vitest run src/lib/i18n` → parity PASS. **Step 3: Commit** `[FEAT] builder dictionaries (fr, en)`.

### Task 15: Builder page and components

**Files:** Create `front/src/lib/components/builder/PlayerCard.svelte`, `BuilderRequests.svelte`, `BuilderTeams.svelte`, `BuilderApply.svelte`, `routes/[year=year]/builder/+page.svelte`; Modify `routes/+layout.svelte` (`NO_TAB_BAR`); Test `routes/[year=year]/builder/page.test.js`.

State lives in `+page.svelte`; the three panels are controlled components. Names come from `fullName` in `$lib/players`.

- [ ] **Step 1: Failing page tests** (`page.test.js`; there is no `use:enhance`, so no `$app/forms` stub):

```js
import { fireEvent, screen, within } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import { renderWith } from '$lib/test-utils';
import { builderPayload } from '$lib/fixtures/builder.js';
import Page from './+page.svelte';

vi.mock('$app/navigation', () => ({ invalidateAll: vi.fn() }));

const data = (over = {}) => ({ builder: { ...builderPayload, ...over } });
const goTo = (name) => fireEvent.click(screen.getByRole('button', { name }));
const propose = async () => {
	await goTo('Teams');
	await fireEvent.click(screen.getByRole('button', { name: 'Propose teams' }));
};
const teamRegions = () => screen.getAllByRole('region', { name: /^Team \d/ });

describe('team builder page', () => {
	it('opens on the requests with the matches proposed from the free text', () => {
		renderWith(Page, { data: data() });

		expect(screen.getByRole('heading', { name: 'Requests' })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Confirm Paul Durand' })).toHaveAttribute('aria-pressed', 'false');
	});

	it('confirms a link by its button and shows it as pressed', async () => {
		renderWith(Page, { data: data() });

		const button = screen.getByRole('button', { name: 'Confirm Paul Durand' });
		await fireEvent.click(button);

		expect(button).toHaveAttribute('aria-pressed', 'true');
	});

	it('proposes teams, placing every player and flagging an incomplete profile', async () => {
		renderWith(Page, { data: data() });

		await propose();

		expect(teamRegions()).toHaveLength(2);
		expect(screen.queryByText('To place')).toBeNull();
		expect(teamRegions().flatMap((r) => within(r).getAllByRole('listitem'))).toHaveLength(6);
		expect(screen.getByText('Incomplete profile')).toBeInTheDocument(); // Bob has no ratings
	});

	it('fixes the players-per-team number once teams are proposed, until everything is reset', async () => {
		renderWith(Page, { data: data() });
		await propose();

		expect(screen.getByLabelText('Players per team')).toBeDisabled();

		vi.spyOn(window, 'confirm').mockReturnValue(true);
		await fireEvent.click(screen.getByRole('button', { name: 'Reset everything' }));

		expect(screen.getByLabelText('Players per team')).toBeEnabled();
		expect(screen.getByText('To place')).toBeInTheDocument();
	});

	it('moves a player to another team from the menu', async () => {
		renderWith(Page, { data: data() });
		await propose();
		const [first, second] = teamRegions();
		const card = within(first).getAllByRole('listitem')[0];
		const name = card.querySelector('.name').textContent;

		await fireEvent.change(within(card).getByRole('combobox'), { target: { value: '1' } });

		expect(within(teamRegions()[1]).getByText(name)).toBeInTheDocument();
		expect(within(teamRegions()[0]).queryByText(name)).toBeNull();
	});

	it('locks a player', async () => {
		renderWith(Page, { data: data() });
		await propose();

		const lock = screen.getAllByRole('button', { name: /^Lock / })[0];
		await fireEvent.click(lock);

		expect(screen.getAllByRole('button', { name: /^Unlock / })).toHaveLength(1);
	});

	it('shows only a message and no builder when teams already exist', () => {
		renderWith(Page, { data: data({ teams_exist: true }) });

		expect(screen.getByText(/already has teams/)).toBeInTheDocument();
		expect(screen.queryByRole('button', { name: 'Propose teams' })).toBeNull();
	});

	it('keeps Apply disabled while a player is unplaced, and says the teams become public', async () => {
		renderWith(Page, { data: data() });
		await goTo('Apply');

		expect(screen.getByRole('button', { name: 'Create the teams' })).toBeDisabled();
		expect(screen.getByText(/public as soon as they are created/)).toBeInTheDocument();
	});

	it('asks for a confirmation while registration is open', async () => {
		renderWith(Page, { data: data({ registration_open: true }) });
		await propose();
		await goTo('Apply');

		expect(screen.getByText(/still open/)).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Create the teams' })).toBeDisabled();

		await fireEvent.click(screen.getByLabelText('I create the teams anyway'));

		expect(screen.getByRole('button', { name: 'Create the teams' })).toBeEnabled();
	});

	it('applies through the page endpoint and lists the disciplines still to schedule', async () => {
		const fetch = vi.fn(async () =>
			new Response(JSON.stringify({ teams: [], unscheduled: [{ id: 3, name: 'Darts' }] }), { status: 200, headers: { 'content-type': 'application/json' } })
		);
		vi.stubGlobal('fetch', fetch);
		renderWith(Page, { data: data() });
		await propose();
		await goTo('Apply');

		await fireEvent.click(screen.getByRole('button', { name: 'Create the teams' }));
		await vi.waitFor(() => expect(screen.getByText('Teams created.')).toBeInTheDocument());

		expect(fetch.mock.calls.at(-1)[0]).toBe('/2029/builder/apply');
		expect(screen.getByText('Darts')).toBeInTheDocument();
		vi.unstubAllGlobals();
	});

	it('sends the version it saved with the apply, and refreshes the layout data', async () => {
		const { invalidateAll } = await import('$app/navigation');
		const fetch = vi.fn(async (url) =>
			new Response(JSON.stringify(url.endsWith('/apply') ? { teams: [], unscheduled: [] } : { updated_at: 'v7' }), { status: 200, headers: { 'content-type': 'application/json' } })
		);
		vi.stubGlobal('fetch', fetch);
		renderWith(Page, { data: data() });
		await propose();
		await goTo('Apply');

		await fireEvent.click(screen.getByRole('button', { name: 'Create the teams' }));
		await vi.waitFor(() => expect(screen.getByText('Teams created.')).toBeInTheDocument());

		const call = fetch.mock.calls.find(([url]) => url.endsWith('/apply'));
		expect(JSON.parse(call[1].body)).toEqual({ based_on: 'v7' });
		expect(invalidateAll).toHaveBeenCalled();
		vi.unstubAllGlobals();
	});

	it('disables Apply while the draft is stale', async () => {
		vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ error: 'stale_draft', draft: null }), { status: 409, headers: { 'content-type': 'application/json' } })));
		renderWith(Page, { data: data() });
		await propose();
		await vi.waitFor(() => expect(screen.getByText("Someone else changed the draft.")).toBeInTheDocument(), { timeout: 3000 });
		await goTo('Apply');

		expect(screen.getByRole('button', { name: 'Create the teams' })).toBeDisabled();
		vi.unstubAllGlobals();
	});

	it('shows the request notes by default and hides them from the switch, remembering it', async () => {
		localStorage.clear();
		renderWith(Page, { data: data() });
		await propose();

		expect(screen.getAllByText('+ Paul Durand').length).toBeGreaterThan(0);

		await fireEvent.click(screen.getByLabelText('Show the requests on the cards'));

		expect(screen.queryByText('+ Paul Durand')).toBeNull();
		expect(localStorage.getItem('builder.showRequests')).toBe('off');
	});

	it('starts with the notes hidden when the browser remembers that', async () => {
		localStorage.setItem('builder.showRequests', 'off');
		renderWith(Page, { data: data() });
		await propose();

		expect(screen.queryByText('+ Paul Durand')).toBeNull();
		expect(screen.getByLabelText('Show the requests on the cards')).not.toBeChecked();
		localStorage.clear();
	});

	it('words an apply refusal', async () => {
		vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ error: 'teams_exist' }), { status: 409, headers: { 'content-type': 'application/json' } })));
		renderWith(Page, { data: data() });
		await propose();
		await goTo('Apply');

		await fireEvent.click(screen.getByRole('button', { name: 'Create the teams' }));

		await vi.waitFor(() => expect(screen.getByText('This edition already has teams.')).toBeInTheDocument());
		vi.unstubAllGlobals();
	});

	it('reconciles a saved draft: a departed player leaves and late registrants wait in the tray', async () => {
		const draft = {
			document: { players_per_team: 3, seed: 1, links: [], locked: [], teams: [{ players: [1, 2, 3] }, { players: [4, 99] }] },
			updated_at: 'v1'
		};
		renderWith(Page, { data: data({ draft }) });
		await goTo('Teams');

		expect(screen.getByText('2 new registrants to place')).toBeInTheDocument();
		expect(screen.getByText('1 withdrawal removed from the teams')).toBeInTheDocument();
		expect(screen.getByText('To place')).toBeInTheDocument();
	});

	it('places the newcomers without moving anyone', async () => {
		const draft = {
			document: { players_per_team: 3, seed: 1, links: [], locked: [], teams: [{ players: [1, 2, 3] }, { players: [4] }] },
			updated_at: 'v1'
		};
		renderWith(Page, { data: data({ draft }) });
		await goTo('Teams');
		const before = teamRegions().map((r) => within(r).getAllByRole('listitem').map((li) => li.querySelector('.name').textContent));

		await fireEvent.click(screen.getByRole('button', { name: 'Place the newcomers' }));

		expect(screen.queryByText('To place')).toBeNull();
		const after = teamRegions().map((r) => within(r).getAllByRole('listitem').map((li) => li.querySelector('.name').textContent));
		before.forEach((names, i) => names.forEach((n) => expect(after[i]).toContain(n)));
		expect(after.flat()).toHaveLength(6);
	});

	it('speaks French', () => {
		renderWith(Page, { data: data() }, 'fr');

		expect(screen.getByRole('heading', { name: 'Demandes' })).toBeInTheDocument();
	});
});
```

(The English strings these tests read — « Requests », « Teams », « Apply », « Propose teams », « Reset everything », « Place the newcomers », « Players per team », « Confirm {name} », « Lock {name} », « Unlock {name} », « Incomplete profile », « To place », « Teams created. », « This edition already has teams. », « {joined} new registrants to place », « {left} withdrawal removed from the teams », « I create the teams anyway », « The teams will be public as soon as they are created », « Registration is still open… » — are the `builder.*` values of Task 14's English dictionary: write them exactly so.)

- [ ] **Step 2: Run red.**
- [ ] **Step 3: Implement.**

`$lib/components/builder/PlayerCard.svelte`:

```svelte
<script>
	import { createEventDispatcher } from 'svelte';
	import { useT } from '$lib/i18n';
	import { fullName } from '$lib/players';

	export let player;
	export let teamCount;
	export let index = -1;
	export let locked = false;
	export let incomplete = false;
	export let notes = [];

	const t = useT();
	const dispatch = createEventDispatcher();
	$: name = fullName(player);
	$: targets = Array.from({ length: teamCount }, (_, i) => i).filter((i) => i !== index);

	function dragStart(event) {
		event.dataTransfer?.setData('text/plain', String(player.id));
		if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move';
	}
	function change(event) {
		const value = event.currentTarget.value;
		event.currentTarget.value = '';
		if (value === '') return;
		dispatch('move', { id: player.id, to: value === 'tray' ? null : Number(value) });
	}
</script>

<li class="card" class:locked draggable="true" on:dragstart={dragStart}>
	<span class="top">
		<span class="name">{name}</span>
		<span class="rating num">{player.rating}</span>
	</span>
	{#if incomplete}<span class="badge">{t('builder.incomplete')}</span>{/if}
	{#each notes as note}<span class="note">{note}</span>{/each}
	<span class="actions">
		<select aria-label={t('builder.move', { name })} on:change={change}>
			<option value="">{t('builder.moveTo')}</option>
			{#each targets as i}<option value={i}>{t('builder.team', { n: i + 1 })}</option>{/each}
			{#if index !== -1}<option value="tray">{t('builder.moveToTray')}</option>{/if}
		</select>
		{#if index !== -1}
			<button
				type="button"
				class="icon-button"
				aria-pressed={locked}
				aria-label={t(locked ? 'builder.unlock' : 'builder.lock', { name })}
				on:click={() => dispatch('lock', { id: player.id })}
			>
				<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M7 11V8a5 5 0 0 1 10 0v3M6 11h12v9H6z" /></svg>
			</button>
		{/if}
	</span>
</li>

<style>
	.card {
		display: grid;
		gap: 0.375rem;
		padding: 0.625rem 0.75rem;
		list-style: none;
		background: var(--bg-raised);
		border: 1px solid var(--line);
		border-radius: var(--radius);
		cursor: grab;
	}
	.card.locked {
		border-color: var(--accent);
	}
	.top {
		display: flex;
		justify-content: space-between;
		gap: 0.5rem;
	}
	.name {
		font-weight: 600;
		color: var(--ink);
	}
	.rating {
		color: var(--muted);
	}
	.badge,
	.note {
		font-size: 0.8125rem;
		color: var(--muted);
	}
	.badge {
		color: var(--loss);
	}
	.actions {
		display: flex;
		gap: 0.5rem;
		align-items: center;
	}
	select {
		flex: 1;
		min-width: 0;
		padding: 0.375rem 0.5rem;
		background: var(--bg-sunken);
		color: var(--ink);
		border: 1px solid var(--line-strong);
		border-radius: var(--radius);
		font: inherit;
	}
	.icon-button {
		display: inline-grid;
		place-items: center;
		width: 2.25rem;
		height: 2.25rem;
		padding: 0;
		border-radius: 999px;
		border: 1px solid var(--line-strong);
		background: transparent;
		color: var(--muted);
		cursor: pointer;
	}
	.icon-button[aria-pressed='true'] {
		color: var(--accent);
		border-color: var(--accent);
	}
	.icon-button svg {
		width: 1.125rem;
		height: 1.125rem;
		fill: none;
		stroke: currentColor;
		stroke-width: 2;
		stroke-linecap: round;
		stroke-linejoin: round;
	}
</style>
```

`BuilderTeams.svelte`:

```svelte
<script>
	import { createEventDispatcher } from 'svelte';
	import { useT } from '$lib/i18n';
	import { fullName } from '$lib/players';
	import PlayerCard from './PlayerCard.svelte';

	export let players;
	export let teams;
	export let unplaced;
	export let result;
	export let skills;
	export let perTeam;
	export let locked;
	export let incomplete;
	export let notesFor;
	export let tooFew = false;
	export let showRequests = true;

	const t = useT();
	const dispatch = createEventDispatcher();
	$: byId = new Map(players.map((p) => [p.id, p]));
	$: proposed = teams.length > 0;
	$: count = proposed ? teams.length : Math.ceil(players.length / perTeam);
	$: unmet = result?.unmet ?? [];
	$: skillName = (s) => s.name_fr;

	function drop(event, to) {
		event.preventDefault();
		const id = Number(event.dataTransfer?.getData('text/plain'));
		if (byId.has(id)) dispatch('move', { id, to });
	}
	const nameOf = (id) => (byId.has(id) ? fullName(byId.get(id)) : '');
</script>

<div class="controls">
	<div class="field">
		<label for="per-team">{t('builder.perTeam')}</label>
		<input
			id="per-team"
			type="number"
			min="2"
			max="20"
			step="1"
			value={perTeam}
			disabled={proposed}
			aria-describedby={proposed ? 'per-team-hint' : undefined}
			on:change={(event) => dispatch('perTeam', Number(event.currentTarget.value))}
		/>
		{#if proposed}<p class="hint" id="per-team-hint">{t('builder.perTeamLocked')}</p>{/if}
	</div>
	<p class="count num">{t('builder.counts', { n: count })}</p>
	<label class="check">
		<input type="checkbox" checked={showRequests} on:change={(e) => dispatch('showRequests', e.currentTarget.checked)} />
		{t('builder.showRequests')}
	</label>
	<div class="buttons">
		{#if !proposed}
			<button type="button" class="submit" disabled={players.length === 0} on:click={() => dispatch('propose')}>{t('builder.propose')}</button>
		{:else}
			<button type="button" class="submit" on:click={() => dispatch('reroll')}>{t('builder.reroll')}</button>
			{#if unplaced.length > 0}
				<button type="button" class="pill" on:click={() => dispatch('placeNew')}>{t('builder.placeNew')}</button>
			{/if}
			<button type="button" class="pill" on:click={() => dispatch('reset')}>{t('builder.reset')}</button>
		{/if}
	</div>
</div>
{#if tooFew}<p class="error" role="alert">{t('builder.tooFew')}</p>{/if}

{#if proposed}
	<section class="unmet" aria-labelledby="unmet-title">
		<h3 id="unmet-title">{t('builder.unmet')}</h3>
		{#if unmet.length === 0}
			<p class="hint">{t('builder.unmetNone')}</p>
		{:else}
			<ul>
				{#each unmet as u}
					<li>
						{t(`builder.unmet.${u.kind}`, { player: nameOf(u.player), target: nameOf(u.target) })}{u.mutual ? t('builder.unmet.mutual') : ''}
					</li>
				{/each}
			</ul>
		{/if}
	</section>
{/if}

<div class="board">
	{#if unplaced.length > 0}
		<section class="column tray" aria-label={t('builder.tray')} on:dragover|preventDefault on:drop={(e) => drop(e, null)}>
			<h3>{t('builder.tray')}</h3>
			<ul>
				{#each unplaced as id (id)}
					<PlayerCard player={byId.get(id)} teamCount={teams.length || count} incomplete={incomplete.has(id)} notes={showRequests ? notesFor(byId.get(id)) : []} on:move />
				{/each}
			</ul>
		</section>
	{/if}
	{#each teams as team, i}
		<section class="column" aria-label={t('builder.team', { n: i + 1 })} on:dragover|preventDefault on:drop={(e) => drop(e, i)}>
			<h3>{t('builder.team', { n: i + 1 })}</h3>
			<p class="stats">
				<span>{t('builder.size', { n: team.players.length })}</span>
				{#if result?.teams[i]}<span class="num">{t('builder.average', { rating: result.teams[i].rating.toFixed(1) })}</span>{/if}
			</p>
			{#if result?.teams[i]}
				<ul class="bars" aria-hidden="true">
					{#each skills as s}
						<li title="{skillName(s)} {result.teams[i].skills[s.identifier].toFixed(1)}">
							<span class="fill" style="width: {result.teams[i].skills[s.identifier] * 10}%"></span>
						</li>
					{/each}
				</ul>
			{/if}
			<ul>
				{#each team.players as id (id)}
					<PlayerCard
						player={byId.get(id)}
						teamCount={teams.length}
						index={i}
						locked={locked.includes(id)}
						incomplete={incomplete.has(id)}
						notes={showRequests ? notesFor(byId.get(id)) : []}
						on:move
						on:lock
					/>
				{/each}
			</ul>
		</section>
	{/each}
</div>
```
with scoped styles (tokens only): `.board` a responsive grid (`repeat(auto-fill, minmax(15rem, 1fr))`), `.column` a card with `--bg-sunken` background and `--line` border, `.bars li` a thin track (`--bg`, `--line`) with a `.fill` of `--accent`, `.hint` muted, `.error` like the registration form's, `.submit`/`.pill` buttons copied from `RegistrationForm.svelte`.

`BuilderRequests.svelte`:

```svelte
<script>
	import { createEventDispatcher } from 'svelte';
	import { useT } from '$lib/i18n';
	import { fullName } from '$lib/players';
	import { matchNames } from '$lib/builder/names.js';

	export let players;
	export let links;

	const t = useT();
	const dispatch = createEventDispatcher();
	const KINDS = [['team_with', 'with'], ['team_avoid', 'avoid']];

	$: byId = new Map(players.map((p) => [p.id, p]));
	// The matches depend on the roster only, so confirming a link never recomputes them.
	$: rows = players.flatMap((player) =>
		KINDS.flatMap(([field, kind]) =>
			player[field]?.trim() ? [{ player, kind, matches: matchNames(player[field], players, player.id) }] : []
		)
	);
	$: confirmed = new Set(links.map((l) => `${l.player}:${l.kind}:${l.target}`));
	const isOn = (player, kind, target) => confirmed.has(`${player.id}:${kind}:${target}`);
	const toggle = (player, kind, target) => dispatch('toggle', { player: player.id, kind, target });

	/** Confirmed links of this player and kind that no name of their text suggested (added through « Autre joueur »). */
	const extras = (row) => {
		const suggested = new Set(row.matches.flatMap((m) => m.candidates.map((c) => c.id)));
		return links.filter((l) => l.player === row.player.id && l.kind === row.kind && !suggested.has(l.target));
	};
	function other(event, player, kind) {
		const target = Number(event.currentTarget.value);
		event.currentTarget.value = '';
		if (target && !isOn(player, kind, target)) toggle(player, kind, target);
	}
</script>

<p class="hint">{t('builder.requests.intro')}</p>
{#if rows.length === 0}
	<p>{t('builder.requests.none')}</p>
{:else}
	<ul class="rows">
		{#each rows as row (`${row.player.id}-${row.kind}`)}
			<li class="row">
				<p class="who"><strong>{fullName(row.player)}</strong> {t(`builder.requests.${row.kind}`)}</p>
				<ul>
					{#each row.matches as match}
						<li class="match">
							<span class="text">« {match.text} »</span>
							{#each match.candidates as candidate}
								<button
									type="button"
									class="chip"
									aria-pressed={isOn(row.player, row.kind, candidate.id)}
									aria-label={t('builder.requests.confirm', { name: fullName(byId.get(candidate.id)) })}
									on:click={() => toggle(row.player, row.kind, candidate.id)}
								>
									{fullName(byId.get(candidate.id))}
								</button>
							{/each}
							{#if match.candidates.length === 0}<span class="hint">{t('builder.requests.noMatch')}</span>{/if}
						</li>
					{/each}
					{#each extras(row) as link}
						<li class="match">
							<button type="button" class="chip" aria-pressed="true" aria-label={t('builder.requests.confirm', { name: fullName(byId.get(link.target)) })} on:click={() => toggle(row.player, row.kind, link.target)}>
								{fullName(byId.get(link.target))}
							</button>
						</li>
					{/each}
				</ul>
				<select aria-label="{t('builder.requests.other')} ({fullName(row.player)})" on:change={(e) => other(e, row.player, row.kind)}>
					<option value="">{t('builder.requests.other')}</option>
					{#each players.filter((p) => p.id !== row.player.id) as p}<option value={p.id}>{fullName(p)}</option>{/each}
				</select>
			</li>
		{/each}
	</ul>
{/if}
```
Styles in tokens: `.chip` pill with `aria-pressed='true'` filled with `--accent` and `--bg` text, as the registration's `.submit`.

`BuilderApply.svelte`:

```svelte
<script>
	import { createEventDispatcher } from 'svelte';
	import { useT } from '$lib/i18n';

	export let teamCount;
	export let placedCount;
	export let unplacedCount;
	export let registrationOpen;
	export let unmet = [];
	export let nameOf;
	export let busy = false;
	export let error = '';
	export let done = null;
	export let saveBlocked = false;

	const t = useT();
	const dispatch = createEventDispatcher();
	let confirmedOpen = false;
	$: blocked = busy || saveBlocked || done !== null || teamCount === 0 || unplacedCount > 0 || (registrationOpen && !confirmedOpen);
</script>

{#if done}
	<p class="saved" role="status">{t('builder.apply.done')}</p>
	{#if done.unscheduled.length > 0}
		<p>{t('builder.apply.unscheduled')}</p>
		<ul>{#each done.unscheduled as discipline}<li>{discipline.name}</li>{/each}</ul>
	{/if}
{:else}
	<p class="num">{t('builder.apply.summary', { teams: teamCount, n: placedCount })}</p>
	{#if unplacedCount > 0}<p class="error">{t('builder.apply.unplaced', { n: unplacedCount })}</p>{/if}
	{#if unmet.length > 0}
		<ul>
			{#each unmet as u}
				<li>{t(`builder.unmet.${u.kind}`, { player: nameOf(u.player), target: nameOf(u.target) })}{u.mutual ? t('builder.unmet.mutual') : ''}</li>
			{/each}
		</ul>
	{/if}
	<p class="notice">{t('builder.apply.public')}</p>
	{#if registrationOpen}
		<p class="notice">{t('builder.apply.open')}</p>
		<label class="check"><input type="checkbox" bind:checked={confirmedOpen} /> {t('builder.apply.confirmOpen')}</label>
	{/if}
	{#if error}<p class="error" role="alert">{t(error)}</p>{/if}
	<button type="button" class="submit" disabled={blocked} on:click={() => dispatch('apply')}>{t('builder.apply.button')}</button>
{/if}
```

`+page.svelte` (complete):

```svelte
<script>
	import { onDestroy, onMount } from 'svelte';
	import { invalidateAll } from '$app/navigation';
	import { useT } from '$lib/i18n';
	import { fullName } from '$lib/players';
	import { emptyDraft, reconcile } from '$lib/builder/plan.js';
	import { BuilderError, generate, placeNewcomers } from '$lib/builder/generate.js';
	import { newSeed } from '$lib/builder/random.js';
	import { features, makeScorer } from '$lib/builder/score.js';
	import { createSaver } from '$lib/builder/saver.js';
	import { splitNames } from '$lib/builder/names.js';
	import Breadcrumb from '$lib/components/Breadcrumb.svelte';
	import BuilderRequests from '$lib/components/builder/BuilderRequests.svelte';
	import BuilderTeams from '$lib/components/builder/BuilderTeams.svelte';
	import BuilderApply from '$lib/components/builder/BuilderApply.svelte';

	export let data;
	const t = useT();

	$: builder = data.builder;
	$: players = builder.players;
	$: year = builder.edition.year;
	$: byId = new Map(players.map((p) => [p.id, p]));

	let step = 1;
	let draft = emptyDraft();
	let unplaced = [];
	let banner = { joined: 0, left: 0 };
	let saveState = 'idle';
	let stale = undefined; // undefined: not stale; null: stale and the draft was cleared; object: theirs
	let tooFew = false;
	let busy = false;
	let applyError = '';
	let done = null;
	let saver;
	let showRequests = true;

	const NOTES_KEY = 'builder.showRequests';
	onMount(() => {
		try {
			showRequests = localStorage.getItem(NOTES_KEY) !== 'off';
		} catch {
			// private mode or blocked storage: the default stands
		}
	});
	function setShowRequests({ detail }) {
		showRequests = detail;
		try {
			localStorage.setItem(NOTES_KEY, detail ? 'on' : 'off');
		} catch {
			// not remembered, still applied
		}
	}

	function load(saved) {
		const out = reconcile(saved ? saved.document : emptyDraft(), players);
		draft = out.draft;
		unplaced = out.unplaced;
		banner = { joined: out.joined, left: out.left };
		stale = undefined;
		saveState = 'idle';
		saver = createSaver({
			url: `/${year}/builder/draft`,
			based_on: saved ? saved.updated_at : null,
			onSaved: () => (saveState = 'saved'),
			onStale: (theirs) => {
				stale = theirs;
				saveState = 'stale';
			},
			onError: () => (saveState = 'error')
		});
	}

	// Loaded again only for a different payload (a new load), never because a bound child
	// input marked `data` dirty.
	let loadedFrom = null;
	$: if (builder !== loadedFrom) {
		loadedFrom = builder;
		load(builder.draft);
	}

	$: teamIds = draft.teams.map((tm) => tm.players);
	$: scorer = makeScorer(players, draft.links, builder.skills);
	$: result = teamIds.length > 0 ? scorer(teamIds) : null;
	$: incomplete = new Set(players.filter((p) => features(p, builder.skills).incomplete).map((p) => p.id));
	$: placedCount = players.length - unplaced.length;

	/** What the cards show of a player's requests: the texts no confirmed link explains stay as notes. */
	$: notesFor = (player) =>
		[player.team_with && `+ ${player.team_with}`, player.team_avoid && `− ${player.team_avoid}`].filter(Boolean);

	function commit(next) {
		draft = next;
		const placed = new Set(draft.teams.flatMap((tm) => tm.players));
		unplaced = players.map((p) => p.id).filter((id) => !placed.has(id));
		saveState = 'saving';
		saver.save(draft);
	}

	function toggleLink({ detail: { player, kind, target } }) {
		const same = (l) => l.player === player && l.kind === kind && l.target === target;
		const links = draft.links.some(same) ? draft.links.filter((l) => !same(l)) : [...draft.links, { player, kind, target }];
		commit({ ...draft, links });
	}
	function setPerTeam({ detail }) {
		if (draft.teams.length === 0 && Number.isInteger(detail) && detail >= 2 && detail <= 20) {
			tooFew = false;
			commit({ ...draft, players_per_team: detail });
		}
	}
	function run(seed) {
		try {
			const { teams } = generate(players, draft.links, builder.skills, {
				perTeam: draft.players_per_team,
				seed,
				current: teamIds,
				locked: draft.locked
			});
			tooFew = false;
			commit({ ...draft, seed, teams: teams.map((ids) => ({ players: ids })) });
		} catch (err) {
			if (err instanceof BuilderError) tooFew = true;
			else throw err;
		}
	}
	const propose = () => run(draft.seed);
	const reroll = () => run(newSeed());
	function placeNew() {
		const teams = placeNewcomers(players, draft.links, builder.skills, teamIds, unplaced);
		commit({ ...draft, teams: teams.map((ids) => ({ players: ids })) });
	}
	function reset() {
		const n = draft.teams.length + draft.locked.length;
		if (!window.confirm(t('builder.resetConfirm', { n }))) return;
		commit({ ...draft, teams: [], locked: [] });
	}
	function move({ detail: { id, to } }) {
		const teams = draft.teams.map((tm) => ({ players: tm.players.filter((p) => p !== id) }));
		if (to !== null && teams[to]) teams[to].players.push(id);
		commit({ ...draft, teams, locked: draft.locked.filter((p) => p !== id) });
	}
	function toggleLock({ detail: { id } }) {
		const locked = draft.locked.includes(id) ? draft.locked.filter((p) => p !== id) : [...draft.locked, id];
		commit({ ...draft, locked });
	}
	$: saveBlocked = saveState === 'stale' || saveState === 'error';
	async function apply() {
		if (saveBlocked) return;
		busy = true;
		applyError = '';
		try {
			await saver.flush();
			if (saveBlocked) return;
			const response = await fetch(`/${year}/builder/apply`, {
				method: 'POST',
				headers: { 'content-type': 'application/json' },
				body: JSON.stringify({ based_on: saver.version() })
			});
			const body = await response.json().catch(() => ({}));
			if (response.ok) {
				done = body;
				await invalidateAll(); // the layout's summary now has the teams
			} else {
				applyError = `builder.error.${['no_draft', 'teams_exist', 'incomplete', 'bad_size', 'stale_draft'].includes(body.error) ? body.error : 'failed'}`;
			}
		} catch {
			applyError = 'builder.error.failed';
		} finally {
			busy = false;
		}
	}
	const loadTheirs = () => load(stale ?? null);

	onDestroy(() => saver?.flush());
	const nameOf = (id) => (byId.has(id) ? fullName(byId.get(id)) : '');
	const STEPS = [1, 2, 3];
</script>

<div class="page">
	<Breadcrumb items={[{ label: String(year), href: `/${year}` }, { label: t('builder.title') }]} />
	<h1>{t('builder.title')}</h1>

	{#if done}
		<h2>{t('builder.step.3')}</h2>
		<BuilderApply {done} teamCount={done.teams.length} placedCount={0} unplacedCount={0} registrationOpen={false} nameOf={() => ''} />
	{:else if builder.teams_exist}
		<p class="notice">{t('builder.exists')}</p>
	{:else if players.length === 0}
		<p class="notice">{t('builder.noPlayers')}</p>
	{:else}
		{#if banner.joined > 0}<p class="notice">{t('builder.banner', { joined: banner.joined })}</p>{/if}
		{#if banner.left > 0}<p class="notice">{t('builder.bannerLeft', { left: banner.left })}</p>{/if}
		{#if saveState === 'stale'}
			<p class="error" role="alert">
				{t('builder.stale')}
				<button type="button" class="pill" on:click={loadTheirs}>{t('builder.stale.load')}</button>
			</p>
		{:else if saveState === 'error'}
			<p class="error" role="alert">{t('builder.save.error')}</p>
		{:else if saveState === 'saved'}
			<p class="hint" role="status">{t('builder.save.saved')}</p>
		{/if}

		<nav class="progress" aria-label={t('builder.steps.label')}>
			<ol>
				{#each STEPS as n}
					<li>
						<button type="button" class="step-name" aria-current={n === step ? 'step' : undefined} on:click={() => (step = n)}>
							<span class="num" aria-hidden="true">{n}</span>
							{t(`builder.step.${n}`)}
						</button>
					</li>
				{/each}
			</ol>
		</nav>

		{#if step === 1}
			<h2>{t('builder.step.1')}</h2>
			<BuilderRequests {players} links={draft.links} on:toggle={toggleLink} />
		{:else if step === 2}
			<h2>{t('builder.step.2')}</h2>
			<BuilderTeams
				{players}
				teams={draft.teams}
				{unplaced}
				{result}
				skills={builder.skills}
				perTeam={draft.players_per_team}
				locked={draft.locked}
				{incomplete}
				{notesFor}
				{tooFew}
				on:perTeam={setPerTeam}
				on:propose={propose}
				on:reroll={reroll}
				on:placeNew={placeNew}
				on:reset={reset}
				on:move={move}
				{showRequests}
				on:showRequests={setShowRequests}
				on:lock={toggleLock}
			/>
		{:else}
			<h2>{t('builder.step.3')}</h2>
			<BuilderApply
				teamCount={draft.teams.length}
				{placedCount}
				unplacedCount={unplaced.length}
				registrationOpen={builder.registration_open}
				unmet={result?.unmet ?? []}
				{nameOf}
				{busy}
				error={applyError}
				{done}
				{saveBlocked}
				on:apply={apply}
			/>
		{/if}
	{/if}
</div>
```
Styles: the `.page` wrapper, `.notice`, `.error`, `.hint`, `.progress` and `.step-name` blocks copy the registration form's (tokens only), including the 600px media rule for the step buttons.

Remove the unused `splitNames` import from the page. The saver's `onError` also sets `saveState = 'error'`, which disables Apply until a later save succeeds. The `h2` headings are « Requests », « Teams », « Apply » (the tests read both the step buttons and the headings by role, so the buttons are `button` role and the headings `heading`).

`routes/+layout.svelte`: add `'/[year=year]/builder'` to `NO_TAB_BAR`.

- [ ] **Step 4: Run green** (`npx vitest run src/routes/[year=year]/builder src/lib/components/builder`), fix until every test passes **without weakening the assertions**; where a test relies on a name or label the components define, keep both in step with the dictionary. Add component-level tests for `BuilderRequests` (toggle event, the no-match note, an ambiguous name offering both candidates, a link added through « Autre joueur » shown as pressed) and `BuilderApply` (the disabled combinations, the open-registration confirmation, `done` listing `unscheduled`) in the same style.
- [ ] **Step 5: Run the whole front suite and `npm run build`; commit** `[FEAT] team builder page`.

### Task 16: Entry point on the ranking page

**Files:** Modify `routes/[year=year]/ranking/+page.svelte`, its `page.test.js`.

- [ ] **Step 1: Failing tests** (append to `page.test.js`; use its existing helper for building `data`; the organiser flag comes through `data.editable`):

```js
it('offers the team builder to an organiser of the latest edition while there is no team', () => {
	renderWith(Page, { data: { ...data, editable: true, summary: { ...data.summary, teams: [] } } }, 'en', true);

	expect(screen.getByRole('link', { name: 'Build the teams' })).toHaveAttribute('href', '/2026/builder');
});

it('hides it from visitors and once teams exist', () => {
	renderWith(Page, { data: { ...data, editable: false, summary: { ...data.summary, teams: [] } } });
	expect(screen.queryByRole('link', { name: 'Build the teams' })).toBeNull();

	renderWith(Page, { data: { ...data, editable: true } }, 'en', true);
	expect(screen.queryByRole('link', { name: 'Build the teams' })).toBeNull();
});
```
(Adapt `data` and the year to the fixture the file already uses.)

- [ ] **Step 2: Run red.** **Step 3: Implement** in the ranking page, after the `<h1>`: `{#if data.editable && teams.length === 0}<a class="builder-link quiet-link" href="/{year}/builder">{t('builder.link')}</a>{/if}` with a token-only style (a pill like `.pill` in the organiser tools, accent border). The `builder.link` string is « Constituer les équipes » / « Build the teams ».
- [ ] **Step 4: Run green**, full front suite and build. **Step 5: Commit** `[FEAT] ranking page: team builder link for organisers`.

### Task 17: Docs and the browser walk

**Files:** `CLAUDE.md`.

- [ ] **Step 1:** Extend the **Team builder** paragraph added in Task 6 with the front half: route and its guards, `$lib/builder/` (modules and what each is for: `names.js`, `plan.js` with `reconcile`, `score.js` with `WEIGHTS` and the fallbacks, `generate.js`, `random.js`, `saver.js`), the JSON endpoints and why they are not form actions, the panels, the existing-teams message, the ranking-page link, `NO_TAB_BAR`, the tests. Then `git grep -n "team builder\|Team builder" CLAUDE.md` once to check there is a single paragraph.
- [ ] **Step 2: Commit** `[DOCS] CLAUDE.md: the team builder`.
- [ ] **Step 3 (controller only, after both PRs are on `dev`, with Hugo's yes; subagents never touch the dev DB):** on the dev stack (`migrate` first for the new migration), seed or reuse the smoke edition 2029 (about ten registered players; give a few of them `team_with`/`team_avoid` texts and a skills set), log in as `smoke-admin` and walk `/2029/builder`: the requests panel matches, the generator output, a drag and the menu move, a lock then a re-roll, a reload mid-draft (the draft comes back), a second browser tab making a stale save (the notice), a roster change (register someone) giving the tray and the banner, Apply with registration open (the confirmation), the result (teams, results backfilled, `unscheduled`), then the page for an edition that now has teams, at 375px and in French. Clean up afterwards only when Hugo says so.

---

## Self-review against the spec

- Draft model, shape rules and codes → Tasks 1–2. Payload (fields, `registration_open`, `teams_exist`, active players of active users only, no username/email), `BUILDER_QUERIES` → Task 3. Save with the stale check and the `based_on` rules (first save, cleared draft, concurrent save) → Tasks 3 and 5. Apply (no body, lock, every refusal and status, creation, `TeamResult` backfill via `register_teams`, `unscheduled`, draft deleted) → Task 4. Staff-only routes and the latest-edition rule → Task 5. Admin link → Task 6.
- Front: name splitting and matching with the confidence levels and noise → Task 9; team sizes → Task 7; reconcile on load (departed, new, banner) → Task 8 and 15; fallbacks and « Profil incomplet » → Task 10 and 15; score parts, penalties, ordering of weights → Task 10; generator with locks, seed, restarts, `too_few` → Task 11; debounced draft saving and the stale notice → Tasks 12 and 15; page guards (visitor, non-organiser, not latest, no-store) → Task 13; three panels, per-team number fixed after the proposal and « Tout réinitialiser » keeping links, move menu and drag, unmet list, apply gating, open-registration confirmation, existing-teams message → Task 15; entry points (ranking button, admin link) → Tasks 6 and 16; dictionaries → Task 14; `CLAUDE.md` and the walk → Task 17.
- Deviations from the spec, stated at the top: JSON endpoints instead of form actions, and no admin links in the messages.
- Known limit to mention in the PR: the weights in `score.js` are tuned by reading, not by data; the tests pin their order, so retuning is a one-line change.
