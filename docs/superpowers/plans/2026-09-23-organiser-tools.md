# Organiser Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Implementers run ONE AT A TIME on this checkout (shared git index).

**Goal:** A logged-in staff user scores games, enters results, reveals a discipline and closes a Swiss round from the public discipline page of the latest edition, on a phone.

**Architecture:** Four `PATCH` endpoints guarded by an `IsOrganiser` permission and a latest-edition check, going through the models' `save()`; the public summary keeps game scores and stored results for staff while the ranking stays hidden. On the front, the token cookie is resolved once in the root layout into an `organiser` flag carried in Svelte context, the year layout derives `editable`, and the discipline page renders a staff bar, a score sheet, result lines and a close-round button through SvelteKit form actions with `use:enhance`.

**Tech Stack:** Django 4.2 + DRF (Postgres in compose), SvelteKit 2 / Svelte 4 plain JS, Vitest + @testing-library/svelte.

**Spec:** `docs/superpowers/specs/2026-09-23-organiser-tools-design.md`. Where this plan and the spec disagree, the spec wins.

---

## Working environment

Main checkout `/Users/shoklah/Work/Playground/Olympic-Warriors`, branch `claude/organiser-tools` (spec committed). The user asked for this work to run directly in the main checkout on this branch; do not switch branches. Everything runs in the compose stack:

```bash
docker compose exec -T server python manage.py test olympic_warriors.tests.test_organiser   # one Django module
docker compose exec -T server python manage.py test                                          # all Django tests (~1 min)
docker compose exec -T front npx vitest run <path>                                           # one front file/folder
docker compose exec -T front npm test                                                        # whole front suite
docker compose exec -T front npm run build
```

The compose front serves this checkout live on `http://localhost:5173` and the API on `http://localhost:3003`. A local staff user exists for manual checks: `docker compose exec -T server python manage.py createsu` creates it from `SU_USERNAME`/`SU_PASSWORD` in `server/dev.env` (read them with `grep SU_ server/dev.env`).

Commit prefixes `[FEAT]`/`[FIX]`/`[TEST]`/`[DOCS]`, trailer `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Never `git reset`, `git stash`, `git checkout` or `git add -A`; stage explicit paths.

Conventions to keep: views are flat `@api_view` functions with `@extend_schema`; policy decorators go **below** `@api_view`; every visible front string goes through `t()`; component and page tests render through `renderWith`; French default, one French test per translated surface; markup sentence case (CSS uppercases).

---

## File structure

| File | Task | Change |
|---|---|---|
| `server/olympic_warriors/permissions.py` | 1 | `IsOrganiser` |
| `server/olympic_warriors/models/Edition.py`, `models/__init__.py` | 1 | `latest_edition()` |
| `server/olympic_warriors/serializer.py` | 1, 2 | `is_staff`, `pairing_system`, staff-aware result and game rows, the three input serializers |
| `server/olympic_warriors/views.py`, `urls.py` | 1, 2 | staff flag into the summary; four write views |
| `server/olympic_warriors/tests/test_summary.py`, `tests/test_organiser.py` | 1, 2 | tests |
| `front/src/lib/session.js` (+ test), `front/src/lib/api.js` (+ test) | 3 | context key, cookie name, token header, `apiPatch` |
| `front/src/routes/login/+page.server.js`, `front/src/routes/logout/+page.server.js` (+ test) | 3 | cookie in, cookie out |
| `front/src/routes/+layout.server.js` (+ test), `+layout.svelte`, `[year=year]/+layout.server.js` (+ test) | 3 | `organiser`, context, `editable` |
| `front/src/lib/components/Header.svelte` (+ test), `front/src/lib/test-utils.js` | 3 | `ORGA` pill, `renderWith` organiser arg |
| `front/src/lib/i18n/fr.js`, `en.js` | 4 | `orga.*` keys |
| `front/src/lib/edition.js` (+ test), `front/src/lib/fixtures/summary.js` | 4 | `formatTime`, `disciplineEntries`, `pairing_system`, `summaryStaff` |
| `front/src/lib/components/GameRow.svelte` (+ test), `ScoreSheet.svelte` (+ test), `StaffBar.svelte` (+ test) | 4 | `onEdit`; the two new components |
| `front/src/routes/[year=year]/disciplines/[id]/+page.svelte` (+ test), `+page.server.js` (+ test), `teams/[id]/+page.svelte` | 5 | controls and actions; `formatTime` on the team tiles |
| `CLAUDE.md` | 6 | docs |

---

## Task 1: Permission, latest edition, staff-aware summary

**Files:**
- Create: `server/olympic_warriors/permissions.py`
- Modify: `server/olympic_warriors/models/Edition.py`, `server/olympic_warriors/models/__init__.py`
- Modify: `server/olympic_warriors/serializer.py` (`UserSerializer`, `SummaryDisciplineSerializer`, `SummaryResultSerializer`, `SummaryGameSerializer`, `EditionSummarySerializer`)
- Modify: `server/olympic_warriors/views.py` (`getEditionSummary`)
- Modify: `server/olympic_warriors/tests/test_summary.py`

- [ ] **Step 1: Write the failing tests**

Append to `server/olympic_warriors/tests/test_summary.py`:

```python
class TestStaffSummary(APITestCase):
    """
    Staff get the scores of every game and the stored value of every result whatever
    reveal_score says; the ranking of a hidden discipline stays null for everyone.
    """

    def setUp(self):
        self.edition = Edition.objects.create(
            year=2026, host="Paris", start_date="2026-09-19", end_date="2026-09-20"
        )
        self.a = Team.objects.create(name="A", edition=self.edition)
        self.b = Team.objects.create(name="B", edition=self.edition)
        self.darts = Darts.objects.create(edition=self.edition)  # hidden, PTS, no round yet
        self.round = TeamSportRound.objects.create(discipline=self.darts, order=0)
        self.game = Game.objects.create(
            discipline=self.darts, round=self.round, team1=self.a, team2=self.b,
            referees=self.a, edition=self.edition, score1=7, score2=3, is_played=True,
        )
        self.staff = User.objects.create_user(username="staff", password="x", is_staff=True)
        self.player = User.objects.create_user(username="player", password="x")

    def summary(self, user=None):
        client = APIClient()
        if user is not None:
            client.force_authenticate(user=user)
        response = client.get("/edition/year/2026/summary/")
        self.assertEqual(response.status_code, 200)
        return response.data

    def test_public_and_player_get_no_score_on_a_hidden_discipline(self):
        for user in (None, self.player):
            data = self.summary(user)
            game = data["games"][0]
            self.assertEqual((game["score1"], game["score2"]), (None, None))
            result = next(r for r in data["results"] if r["team"] == self.a.id)
            self.assertIsNone(result["points"])
            self.assertIsNone(result["ranking"])

    def test_staff_get_scores_and_stored_points_but_no_ranking(self):
        data = self.summary(self.staff)
        game = data["games"][0]
        self.assertEqual((game["score1"], game["score2"]), (7, 3))
        result = next(r for r in data["results"] if r["team"] == self.a.id)
        self.assertEqual(result["points"], 3)  # league points of the played win
        self.assertIsNone(result["ranking"])
        self.assertIsNone(result["global_points"])

    def test_staff_get_a_stored_time(self):
        crossfit = Crossfit.objects.create(edition=self.edition)  # hidden, TIM, no round
        TeamResult.objects.filter(discipline=crossfit, team=self.a).update(time="00:13:15")
        data = self.summary(self.staff)
        result = next(
            r for r in data["results"] if r["team"] == self.a.id and r["discipline"] == crossfit.id
        )
        self.assertEqual(result["time"], "00:13:15")
        self.assertIsNone(result["ranking"])

    def test_revealed_discipline_is_the_same_for_everyone(self):
        Discipline.objects.filter(id=self.darts.id).update(reveal_score=True)
        public = self.summary()
        staff = self.summary(self.staff)
        self.assertEqual(public["games"], staff["games"])
        self.assertEqual(public["results"], staff["results"])

    def test_disciplines_carry_their_pairing_system(self):
        data = self.summary()
        self.assertEqual(data["disciplines"][0]["pairing_system"], "NO")


class TestCurrentUser(APITestCase):

    def test_current_user_says_whether_staff(self):
        staff = User.objects.create_user(username="staff", password="x", is_staff=True)
        self.client.force_authenticate(user=staff)
        response = self.client.get("/user/current/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_staff"])
        self.assertNotIn("password", response.data)


class TestLatestEdition(TestCase):

    def test_latest_is_the_highest_active_year(self):
        Edition.objects.create(year=2026, host="P", start_date="2026-09-19", end_date="2026-09-20")
        Edition.objects.create(
            year=2027, host="L", start_date="2027-09-19", end_date="2027-09-20", is_active=False
        )
        self.assertEqual(latest_edition().year, 2026)

    def test_none_without_any_edition(self):
        self.assertIsNone(latest_edition())
```

Add to the imports at the top of the file: `Crossfit` in the `olympic_warriors.models` import list, `from olympic_warriors.models.Edition import latest_edition`, and `from rest_framework.test import APIClient, APITestCase` (replace the existing `APITestCase` import line).

- [ ] **Step 2: Run them to verify they fail**

Run: `docker compose exec -T server python manage.py test olympic_warriors.tests.test_summary`
Expected: ImportError on `latest_edition`.

- [ ] **Step 3: Permission, latest edition, and "no result yet" as null**

`Discipline.register_teams` (`server/olympic_warriors/models/Discipline.py`, the `get_or_create` defaults) creates every result with `points=0` or `time="00:00:00"`, so a team without a result looks like one with a zero and the organiser page could never say what is missing. Change the defaults to:

```python
                defaults={
                    # A discipline with games computes its points from them (0 before any is
                    # played); one without keeps None until an organiser enters a value, and a
                    # time is None until entered, so "no result yet" is a null, never a zero.
                    "points": (
                        0
                        if self.result_type == ResultTypes.POINTS
                        and self.pairing_system != self.PairingSystem.NONE
                        else None
                    ),
                    "time": None,
                }
```

Then in `server/olympic_warriors/tests/test_transfer.py` the two assertions on the crossfit time (line 149, `self.assertIn("00:00:00", …)`, and line 241, `self.assertEqual(str(crossfit.time), "00:00:00")`) become `self.assertIn(None, {r["time"] for r in doc["tables"]["TeamResult"]})` and `self.assertIsNone(crossfit.time)`. Add to `TestStaffSummary`:

```python
    def test_a_fresh_result_has_no_value(self):
        quiz = Discipline.objects.create(name="Quiz", edition=self.edition, result_type="PTS")
        crossfit = Crossfit.objects.create(edition=self.edition)
        self.assertIsNone(TeamResult.objects.get(discipline=quiz, team=self.a).points)
        self.assertIsNone(TeamResult.objects.get(discipline=crossfit, team=self.a).time)
        self.assertEqual(TeamResult.objects.get(discipline=self.darts, team=self.a).points, 3)
```

`server/olympic_warriors/permissions.py`:

```python
"""
DRF permissions for the organiser endpoints.
"""

from rest_framework.permissions import BasePermission


class IsOrganiser(BasePermission):
    """
    Staff users only: anyone who can log into the Django admin can score from the site.
    Anonymous requests get 401 (token auth advertises a challenge), other users 403.
    """

    message = "Organisers only"

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_staff)
```

Append to `server/olympic_warriors/models/Edition.py` (module level, after the class):

```python
def latest_edition():
    """
    The active edition with the highest year: the only one the site may edit. None when
    there is no edition at all.
    """
    return Edition.objects.filter(is_active=True).order_by("-year").first()
```

In `server/olympic_warriors/models/__init__.py`, change `from .Edition import Edition` to `from .Edition import Edition, latest_edition`.

- [ ] **Step 4: Serializers and the view**

In `server/olympic_warriors/serializer.py`:

`UserSerializer.Meta.fields` becomes `("id", "username", "first_name", "last_name", "email", "is_staff")`.

`SummaryDisciplineSerializer.Meta.fields` becomes `("id", "name", "result_type", "reveal_score", "pairing_system")`.

`SummaryResultSerializer`: replace its docstring and `to_representation` with:

```python
    """
    A team's result in a discipline. The ranking fields are null while the discipline's
    reveal_score is off, or while the result itself has no score yet for its type: the
    summary is public and must not leak a standing early, nor 500 on a NULL score. With
    context["staff"] the stored points and time stay visible so an organiser can check and
    edit them; the ranking stays hidden for staff too until the discipline is revealed.
    """
```

```python
    def to_representation(self, instance):
        missing_score = (
            (instance.result_type == ResultTypes.POINTS and instance.points is None)
            or (instance.result_type == ResultTypes.TIME and instance.time is None)
            or instance.result_type == ResultTypes.NONE
            or not instance.result_type
        )
        if instance.discipline.reveal_score and not missing_score:
            return super().to_representation(instance)
        hidden = {
            "id": instance.id,
            "team": instance.team_id,
            "discipline": instance.discipline_id,
            "result_type": instance.result_type,
        }
        hidden.update({field: None for field in self.HIDDEN_FIELDS})
        if self.context.get("staff"):
            hidden["points"] = instance.points
            hidden["time"] = (
                self.fields["time"].to_representation(instance.time)
                if instance.time is not None
                else None
            )
        return hidden
```

`SummaryGameSerializer.to_representation` becomes:

```python
    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not instance.discipline.reveal_score and not self.context.get("staff"):
            data["score1"] = None
            data["score2"] = None
        return data
```

and its docstring's last sentence becomes "the scores are null while the discipline's reveal_score is off, unless context["staff"] is set."

In `EditionSummarySerializer.to_representation`, the last four lines of the returned dict become:

```python
            "results": SummaryResultSerializer(results, many=True, context=staff_context).data,
            "rounds": SummaryRoundSerializer(rounds, many=True).data,
            "games": SummaryGameSerializer(games, many=True, context=staff_context).data,
        }
```

with, right before `return {`, the line `staff_context = {"staff": bool(self.context.get("staff"))}`.

In `server/olympic_warriors/views.py`, `getEditionSummary` becomes:

```python
def getEditionSummary(request, year):
    try:
        edition = Edition.objects.get(year=year, is_active=True)
    except Edition.DoesNotExist:
        return Response({"error": "Edition not found"}, status=404)
    # Staff see game scores and stored results before the reveal; the ranking stays hidden.
    serializer = EditionSummarySerializer(edition, context={"staff": request.user.is_staff})
    return Response(serializer.data)
```

(`request.user` is `AnonymousUser` without a token, whose `is_staff` is False.) Update the view's `@extend_schema` description to mention that a staff token also returns hidden scores.

- [ ] **Step 5: Run the module, then the whole Django suite**

Run: `docker compose exec -T server python manage.py test olympic_warriors.tests.test_summary` → PASS.
Run: `docker compose exec -T server python manage.py test` → all pass. `test_summary.py`'s `test_disciplines_of_this_edition_in_id_order` asserts the exact discipline rows: add the `"pairing_system"` value each of its disciplines carries (read its setUp; `"NO"` when none is set) to the expected rows; do not weaken the assertion. `test_transfer.py` as changed in Step 3.

- [ ] **Step 6: Commit**

```bash
git add server/olympic_warriors/permissions.py server/olympic_warriors/models/Edition.py server/olympic_warriors/models/Discipline.py server/olympic_warriors/models/__init__.py server/olympic_warriors/serializer.py server/olympic_warriors/views.py server/olympic_warriors/tests/test_summary.py server/olympic_warriors/tests/test_transfer.py
git commit -m "[FEAT] api: staff-aware summary, pairing system in discipline rows, IsOrganiser and latest_edition

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Task 2: The four write endpoints

**Files:**
- Modify: `server/olympic_warriors/serializer.py` (three input serializers), `views.py`, `urls.py`
- Create: `server/olympic_warriors/tests/test_organiser.py`

- [ ] **Step 1: Write the failing tests**

`server/olympic_warriors/tests/test_organiser.py`:

```python
"""
Organiser endpoints: score a game, enter a result, reveal a discipline, close a round.
Staff only, latest edition only, every write through the models' save().
"""

from datetime import time

from django.contrib.auth.models import User
from rest_framework.test import APIClient, APITestCase

from olympic_warriors.models import (
    Crossfit,
    Darts,
    Discipline,
    Edition,
    Game,
    Team,
    TeamResult,
    TeamSportRound,
)


class OrganiserSetup(APITestCase):
    """2026 (latest) with Darts (RR, one round, one game) and Crossfit (TIM, no round); 2025 with Darts."""

    def setUp(self):
        self.edition = Edition.objects.create(
            year=2026, host="Paris", start_date="2026-09-19", end_date="2026-09-20"
        )
        self.old = Edition.objects.create(
            year=2025, host="Lyon", start_date="2025-09-20", end_date="2025-09-21"
        )
        self.a = Team.objects.create(name="A", edition=self.edition)
        self.b = Team.objects.create(name="B", edition=self.edition)
        self.c = Team.objects.create(name="C", edition=self.edition)
        self.darts = Darts.objects.create(edition=self.edition)
        self.round = TeamSportRound.objects.create(discipline=self.darts, order=0)
        self.game = Game.objects.create(
            discipline=self.darts, round=self.round, team1=self.a, team2=self.b,
            referees=self.c, edition=self.edition,
        )
        self.crossfit = Crossfit.objects.create(edition=self.edition)
        self.time_result = TeamResult.objects.get(discipline=self.crossfit, team=self.a)

        self.old_team = Team.objects.create(name="Z", edition=self.old)
        self.old_darts = Darts.objects.create(edition=self.old)
        self.old_result = TeamResult.objects.get(discipline=self.old_darts, team=self.old_team)

        self.staff = User.objects.create_user(username="staff", password="x", is_staff=True)
        self.player = User.objects.create_user(username="player", password="x")
        # JSON bodies: with the multipart default a missing boolean reads as False, not missing.
        self.client = APIClient()
        self.client.default_format = "json"
        self.client.force_authenticate(user=self.staff)

    def as_anonymous(self):
        client = APIClient()
        client.default_format = "json"
        return client

    def as_player(self):
        client = APIClient()
        client.default_format = "json"
        client.force_authenticate(user=self.player)
        return client


class TestPermissions(OrganiserSetup):

    def test_every_write_needs_a_token(self):
        client = self.as_anonymous()
        self.assertEqual(client.patch(f"/game/{self.game.id}/score/", {}).status_code, 401)
        self.assertEqual(client.patch(f"/result/{self.time_result.id}/value/", {}).status_code, 401)
        self.assertEqual(client.patch(f"/discipline/{self.darts.id}/reveal/", {}).status_code, 401)
        self.assertEqual(client.patch(f"/round/{self.round.id}/close/").status_code, 401)

    def test_every_write_refuses_a_player(self):
        client = self.as_player()
        self.assertEqual(client.patch(f"/game/{self.game.id}/score/", {}).status_code, 403)
        self.assertEqual(client.patch(f"/result/{self.time_result.id}/value/", {}).status_code, 403)
        self.assertEqual(client.patch(f"/discipline/{self.darts.id}/reveal/", {}).status_code, 403)
        self.assertEqual(client.patch(f"/round/{self.round.id}/close/").status_code, 403)


class TestGameScore(OrganiserSetup):

    def test_sets_the_score_and_recomputes_points(self):
        response = self.client.patch(
            f"/game/{self.game.id}/score/", {"score1": 7, "score2": 3, "is_played": True}
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual((response.data["score1"], response.data["score2"]), (7, 3))
        self.assertTrue(response.data["is_played"])
        self.assertEqual(TeamResult.objects.get(team=self.a, discipline=self.darts).points, 3)

    def test_unplaying_a_game_takes_its_points_back(self):
        self.client.patch(f"/game/{self.game.id}/score/", {"score1": 7, "score2": 3, "is_played": True})
        self.client.patch(f"/game/{self.game.id}/score/", {"score1": 7, "score2": 3, "is_played": False})
        self.assertEqual(TeamResult.objects.get(team=self.a, discipline=self.darts).points, 0)

    def test_refuses_a_missing_field_or_a_negative_score(self):
        response = self.client.patch(f"/game/{self.game.id}/score/", {"score1": 7, "score2": 3})
        self.assertEqual(response.status_code, 400)
        response = self.client.patch(
            f"/game/{self.game.id}/score/", {"score1": -1, "score2": 3, "is_played": True}
        )
        self.assertEqual(response.status_code, 400)

    def test_404_on_an_inactive_or_unknown_game(self):
        Game.objects.filter(id=self.game.id).update(is_active=False)
        response = self.client.patch(
            f"/game/{self.game.id}/score/", {"score1": 1, "score2": 0, "is_played": True}
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.client.patch("/game/999/score/", {}).status_code, 404)

    def test_409_outside_the_latest_edition(self):
        old_round = TeamSportRound.objects.create(discipline=self.old_darts, order=0)
        other = Team.objects.create(name="Y", edition=self.old)
        old_game = Game.objects.create(
            discipline=self.old_darts, round=old_round, team1=self.old_team, team2=other,
            referees=self.old_team, edition=self.old,
        )
        response = self.client.patch(
            f"/game/{old_game.id}/score/", {"score1": 1, "score2": 0, "is_played": True}
        )
        self.assertEqual(response.status_code, 409)


class TestTeamResult(OrganiserSetup):

    def test_sets_a_time_from_minutes_and_seconds(self):
        response = self.client.patch(f"/result/{self.time_result.id}/value/", {"time": "13:15"})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["time"], "00:13:15")
        self.time_result.refresh_from_db()
        self.assertEqual(self.time_result.time, time(0, 13, 15))

    def test_minutes_above_59_roll_into_hours(self):
        self.client.patch(f"/result/{self.time_result.id}/value/", {"time": "75:02"})
        self.time_result.refresh_from_db()
        self.assertEqual(self.time_result.time, time(1, 15, 2))

    def test_empty_clears_the_value(self):
        self.client.patch(f"/result/{self.time_result.id}/value/", {"time": "13:15"})
        response = self.client.patch(f"/result/{self.time_result.id}/value/", {"time": None})
        self.assertEqual(response.status_code, 200)
        self.time_result.refresh_from_db()
        self.assertIsNone(self.time_result.time)

    def test_sets_points_on_a_points_discipline_without_games(self):
        quiz = Discipline.objects.create(name="Quiz", edition=self.edition, result_type="PTS")
        result = TeamResult.objects.get(discipline=quiz, team=self.a)
        response = self.client.patch(f"/result/{result.id}/value/", {"points": 12})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["points"], 12)
        response = self.client.patch(f"/result/{result.id}/value/", {"points": -1})
        self.assertEqual(response.status_code, 400)
        response = self.client.patch(f"/result/{result.id}/value/", {"time": "01:00"})
        self.assertEqual(response.status_code, 400)

    def test_refuses_a_bad_time_and_the_wrong_field(self):
        self.assertEqual(
            self.client.patch(f"/result/{self.time_result.id}/value/", {"time": "13:75"}).status_code, 400
        )
        self.assertEqual(
            self.client.patch(f"/result/{self.time_result.id}/value/", {"time": "0:13:15"}).status_code, 400
        )
        self.assertEqual(
            self.client.patch(f"/result/{self.time_result.id}/value/", {"points": 3}).status_code, 400
        )

    def test_refuses_a_discipline_with_rounds(self):
        result = TeamResult.objects.get(discipline=self.darts, team=self.a)
        response = self.client.patch(f"/result/{result.id}/value/", {"points": 3})
        self.assertEqual(response.status_code, 400)

    def test_409_outside_the_latest_edition(self):
        response = self.client.patch(f"/result/{self.old_result.id}/value/", {"points": 3})
        self.assertEqual(response.status_code, 409)


class TestReveal(OrganiserSetup):

    def test_reveals_and_hides(self):
        response = self.client.patch(f"/discipline/{self.darts.id}/reveal/", {"reveal_score": True})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["reveal_score"])
        self.assertTrue(Discipline.objects.get(id=self.darts.id).reveal_score)
        self.client.patch(f"/discipline/{self.darts.id}/reveal/", {"reveal_score": False})
        self.assertFalse(Discipline.objects.get(id=self.darts.id).reveal_score)

    def test_refuses_a_missing_flag_and_an_old_edition(self):
        self.assertEqual(self.client.patch(f"/discipline/{self.darts.id}/reveal/", {}).status_code, 400)
        response = self.client.patch(f"/discipline/{self.old_darts.id}/reveal/", {"reveal_score": True})
        self.assertEqual(response.status_code, 409)


class TestCloseRound(OrganiserSetup):

    def test_refuses_while_a_game_is_unplayed(self):
        response = self.client.patch(f"/round/{self.round.id}/close/")
        self.assertEqual(response.status_code, 409)
        self.assertFalse(TeamSportRound.objects.get(id=self.round.id).is_over)

    def test_closes_a_complete_round(self):
        Game.objects.filter(id=self.game.id).update(is_played=True)
        response = self.client.patch(f"/round/{self.round.id}/close/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["is_over"])
        self.assertEqual(self.client.patch(f"/round/{self.round.id}/close/").status_code, 409)

    def test_closing_a_swiss_round_schedules_the_next_one(self):
        swiss = Discipline.objects.create(
            name="Petanque", edition=self.edition, result_type="PTS",
            pairing_system=Discipline.PairingSystem.SWISS, max_rounds=3,
        )
        first = TeamSportRound.objects.get(discipline=swiss, order=0)
        Game.objects.filter(round=first).update(is_played=True)
        response = self.client.patch(f"/round/{first.id}/close/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(TeamSportRound.objects.filter(discipline=swiss, order=1).exists())

    def test_409_outside_the_latest_edition(self):
        old_round = TeamSportRound.objects.create(discipline=self.old_darts, order=0)
        self.assertEqual(self.client.patch(f"/round/{old_round.id}/close/").status_code, 409)
```

- [ ] **Step 2: Run them to verify they fail**

Run: `docker compose exec -T server python manage.py test olympic_warriors.tests.test_organiser`
Expected: every request answers 404 or 405 (no route yet): FAIL.

- [ ] **Step 3: Input serializers**

Append to `server/olympic_warriors/serializer.py`:

```python
class GameScoreSerializer(serializers.Serializer):
    """The organiser sheet: both scores and the played flag, all required."""

    score1 = serializers.IntegerField(min_value=0)
    score2 = serializers.IntegerField(min_value=0)
    is_played = serializers.BooleanField()


class ResultValueSerializer(serializers.Serializer):
    """
    One of `points` (integer, 0 or more) or `time` ("mm:ss", minutes may exceed 59); null
    clears the value. The view decides which field the discipline accepts.
    """

    points = serializers.IntegerField(min_value=0, allow_null=True, required=False)
    time = serializers.RegexField(r"^\d{1,3}:[0-5]\d$", allow_null=True, required=False)


class RevealSerializer(serializers.Serializer):
    reveal_score = serializers.BooleanField()
```

- [ ] **Step 4: Views and URLs**

In `server/olympic_warriors/views.py`, add to the imports: `from datetime import time as time_of_day`, `parser_classes` in the existing `rest_framework.decorators` import, `from rest_framework.parsers import JSONParser`, `from .permissions import IsOrganiser`, `from .models import latest_edition` (extend the existing `.models` import list), and `GameScoreSerializer, ResultValueSerializer, RevealSerializer, SummaryGameSerializer, SummaryResultSerializer, SummaryDisciplineSerializer, SummaryRoundSerializer` in the `.serializer` import list. Then append, in a new `# Organiser` section at the end of the file:

```python
# Organiser


LATEST_ONLY = {"error": "Only the latest edition can be edited"}


def _editable(edition):
    """Only the active edition with the highest year can be edited from the site."""
    latest = latest_edition()
    return latest is not None and edition.id == latest.id


def _minutes_seconds(text):
    """"mm:ss" (minutes may exceed 59) to a time of day; None stays None."""
    if text is None:
        return None
    minutes, seconds = (int(part) for part in text.split(":"))
    return time_of_day(minutes // 60, minutes % 60, seconds)


@extend_schema(
    summary="Set a game's score and played flag (organisers, latest edition)",
    request=GameScoreSerializer,
    responses={
        "200": SummaryGameSerializer,
        "400": OpenApiResponse(description="Missing field or negative score"),
        "401": OpenApiResponse(description="Unauthorized"),
        "403": OpenApiResponse(description="Not an organiser"),
        "404": OpenApiResponse(description="Game not found"),
        "409": OpenApiResponse(description="Not the latest edition"),
    },
)
@api_view(["PATCH"])
@permission_classes([IsOrganiser])
@parser_classes([JSONParser])  # a form-encoded body would read a missing boolean as False
def setGameScore(request, game_id):
    try:
        game = Game.objects.select_related("discipline__edition").get(id=game_id, is_active=True)
    except Game.DoesNotExist:
        return Response({"error": "Game not found"}, status=404)
    if not _editable(game.discipline.edition):
        return Response(LATEST_ONLY, status=409)

    serializer = GameScoreSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"error": "Bad request", "details": serializer.errors}, status=400)

    for field, value in serializer.validated_data.items():
        setattr(game, field, value)
    game.save()  # recomputes the league points of both teams
    return Response(SummaryGameSerializer(game, context={"staff": True}).data)


@extend_schema(
    summary="Set a team's points or time in a discipline without games (organisers, latest edition)",
    request=ResultValueSerializer,
    responses={
        "200": SummaryResultSerializer,
        "400": OpenApiResponse(description="Wrong field for the result type, bad value, or a discipline with games"),
        "401": OpenApiResponse(description="Unauthorized"),
        "403": OpenApiResponse(description="Not an organiser"),
        "404": OpenApiResponse(description="Result not found"),
        "409": OpenApiResponse(description="Not the latest edition"),
    },
)
@api_view(["PATCH"])
@permission_classes([IsOrganiser])
@parser_classes([JSONParser])  # a form-encoded body would read a missing boolean as False
def setTeamResult(request, result_id):
    try:
        result = TeamResult.objects.select_related("discipline__edition").get(
            id=result_id, is_active=True
        )
    except TeamResult.DoesNotExist:
        return Response({"error": "Result not found"}, status=404)
    if not _editable(result.discipline.edition):
        return Response(LATEST_ONLY, status=409)
    if TeamSportRound.objects.filter(discipline=result.discipline, is_active=True).exists():
        return Response({"error": "Points of a discipline with games are computed"}, status=400)

    result_type = result.discipline.result_type
    field = {"PTS": "points", "TIM": "time"}.get(result_type)
    if field is None or field not in request.data or len(request.data) != 1:
        return Response({"error": f"Expected exactly the field '{field}'"}, status=400)

    serializer = ResultValueSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"error": "Bad request", "details": serializer.errors}, status=400)

    value = serializer.validated_data[field]
    setattr(result, field, _minutes_seconds(value) if field == "time" else value)
    result.save()
    return Response(SummaryResultSerializer(result, context={"staff": True}).data)


@extend_schema(
    summary="Reveal or hide a discipline's results (organisers, latest edition)",
    request=RevealSerializer,
    responses={
        "200": SummaryDisciplineSerializer,
        "400": OpenApiResponse(description="Missing flag"),
        "401": OpenApiResponse(description="Unauthorized"),
        "403": OpenApiResponse(description="Not an organiser"),
        "404": OpenApiResponse(description="Discipline not found"),
        "409": OpenApiResponse(description="Not the latest edition"),
    },
)
@api_view(["PATCH"])
@permission_classes([IsOrganiser])
@parser_classes([JSONParser])  # a form-encoded body would read a missing boolean as False
def setDisciplineReveal(request, discipline_id):
    try:
        discipline = Discipline.objects.select_related("edition").get(
            id=discipline_id, is_active=True
        )
    except Discipline.DoesNotExist:
        return Response({"error": "Discipline not found"}, status=404)
    if not _editable(discipline.edition):
        return Response(LATEST_ONLY, status=409)

    serializer = RevealSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"error": "Bad request", "details": serializer.errors}, status=400)

    discipline.reveal_score = serializer.validated_data["reveal_score"]
    discipline.save()
    return Response(SummaryDisciplineSerializer(discipline).data)


@extend_schema(
    summary="Close a round once every game is played (organisers, latest edition)",
    request=None,
    responses={
        "200": SummaryRoundSerializer,
        "401": OpenApiResponse(description="Unauthorized"),
        "403": OpenApiResponse(description="Not an organiser"),
        "404": OpenApiResponse(description="Round not found"),
        "409": OpenApiResponse(description="Not the latest edition, already over, or games unplayed"),
    },
)
@api_view(["PATCH"])
@permission_classes([IsOrganiser])
@parser_classes([JSONParser])  # a form-encoded body would read a missing boolean as False
def closeRound(request, round_id):
    try:
        round_ = TeamSportRound.objects.select_related("discipline__edition").get(
            id=round_id, is_active=True
        )
    except TeamSportRound.DoesNotExist:
        return Response({"error": "Round not found"}, status=404)
    if not _editable(round_.discipline.edition):
        return Response(LATEST_ONLY, status=409)
    if round_.is_over:
        return Response({"error": "Round already over"}, status=409)
    if Game.objects.filter(round=round_, is_active=True, is_played=False).exists():
        return Response({"error": "Some games are not played yet"}, status=409)

    round_.is_over = True
    round_.save()  # schedules the next Swiss round when the discipline is Swiss
    return Response(SummaryRoundSerializer(round_).data)
```

In `server/olympic_warriors/urls.py` add four paths, each right after its read sibling (`getGame`, `getTeamResult`, `getDiscipline`, `getRound`). The result write gets its own sub-path because `PATCH /result/<id>/` would share the `GET` view's path (the spec table is updated in Task 6):

```python
    path("game/<int:game_id>/score/", views.setGameScore),
    path("result/<int:result_id>/value/", views.setTeamResult),
    path("discipline/<int:discipline_id>/reveal/", views.setDisciplineReveal),
    path("round/<int:round_id>/close/", views.closeRound),
```

- [ ] **Step 5: Run the tests**

Run: `docker compose exec -T server python manage.py test olympic_warriors.tests.test_organiser` → PASS.
Run: `docker compose exec -T server python manage.py test` → all pass.
Run: `curl -s -o /dev/null -w "%{http_code}\n" -X PATCH http://localhost:3003/round/1/close/` → `401`.

- [ ] **Step 6: Commit**

```bash
git add server/olympic_warriors/serializer.py server/olympic_warriors/views.py server/olympic_warriors/urls.py server/olympic_warriors/tests/test_organiser.py
git commit -m "[FEAT] api: organiser endpoints to score a game, set a result, reveal a discipline, close a round

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Task 3: Front session: token cookie, organiser flag, editable, logout, ORGA pill

**Files:**
- Create: `front/src/lib/session.js`, `front/src/lib/session.test.js`
- Modify: `front/src/lib/api.js`, `front/src/lib/api.test.js`, `front/src/lib/test-utils.js`
- Modify: `front/src/routes/login/+page.server.js`
- Create: `front/src/routes/logout/+page.server.js`, `front/src/routes/logout/page.server.test.js`
- Modify: `front/src/routes/+layout.server.js`, create `front/src/routes/layout.server.test.js`
- Modify: `front/src/routes/+layout.svelte`
- Modify: `front/src/routes/[year=year]/+layout.server.js`, create `front/src/routes/[year=year]/layout.server.test.js`
- Modify: `front/src/lib/components/Header.svelte`, `Header.test.js`
- Modify: `front/src/lib/i18n/fr.js`, `en.js` (two keys only: `orga.pill`, `orga.logout`; the rest come in Task 4)

- [ ] **Step 1: Write the failing tests**

`front/src/lib/session.test.js`:

```js
import { describe, expect, it } from 'vitest';
import { ORGANISER, TOKEN_COOKIE, tokenCookieOptions } from './session.js';

describe('session constants', () => {
	it('names the context key and the cookie', () => {
		expect(ORGANISER).toBe('organiser');
		expect(TOKEN_COOKIE).toBe('token');
	});

	it('scopes the cookie to the site for a week, lax, unreadable by scripts', () => {
		expect(tokenCookieOptions()).toEqual({
			httpOnly: true,
			sameSite: 'lax',
			maxAge: 60 * 60 * 24 * 7,
			path: '/'
		});
	});
});
```

Append to `front/src/lib/api.test.js`:

```js
import { apiPatch } from './api.js';

describe('token header', () => {
	it('apiGet sends the DRF token header when given a token', async () => {
		const fetch = vi.fn().mockResolvedValue(jsonResponse(200, { is_staff: true }));
		await apiGet(fetch, 'http://api/user/current/', 'abc');
		expect(fetch).toHaveBeenCalledWith('http://api/user/current/', {
			method: 'GET',
			headers: { authorization: 'Token abc' }
		});
	});

	it('apiPatch sends the JSON body and the token', async () => {
		const fetch = vi.fn().mockResolvedValue(jsonResponse(200, { id: 1 }));
		await apiPatch(fetch, 'http://api/game/1/score/', { score1: 1 }, 'abc');
		expect(fetch).toHaveBeenCalledWith('http://api/game/1/score/', {
			method: 'PATCH',
			headers: { 'content-type': 'application/json', authorization: 'Token abc' },
			body: JSON.stringify({ score1: 1 })
		});
	});
});
```

(merge the `apiPatch` import into the existing `import { apiGet, apiPost } from './api.js';` line.)

`front/src/routes/logout/page.server.test.js`:

```js
import { describe, expect, it, vi } from 'vitest';
import { actions, load } from './+page.server.js';

const post = (fields) => {
	const body = new FormData();
	for (const [name, value] of Object.entries(fields)) body.append(name, value);
	return new Request('http://localhost/logout', { method: 'POST', body });
};

describe('logout action', () => {
	it('deletes the token cookie and goes back where the form was', async () => {
		const cookies = { delete: vi.fn() };
		await expect(
			actions.default({ cookies, request: post({ redirectTo: '/2026/disciplines/10' }) })
		).rejects.toMatchObject({ status: 303, location: '/2026/disciplines/10' });
		expect(cookies.delete).toHaveBeenCalledWith('token', { path: '/' });
	});

	it('refuses a non-local redirect', async () => {
		const cookies = { delete: vi.fn() };
		await expect(
			actions.default({ cookies, request: post({ redirectTo: '//evil.example' }) })
		).rejects.toMatchObject({ location: '/' });
	});
});

describe('logout load', () => {
	it('sends a GET to the hub', () => {
		let thrown = null;
		try {
			load();
		} catch (e) {
			thrown = e;
		}
		expect(thrown).toMatchObject({ status: 303, location: '/' });
	});
});
```

`front/src/routes/layout.server.test.js`:

```js
import { describe, expect, it, vi } from 'vitest';
import { load } from './+layout.server.js';

vi.mock('$lib/server/urls', () => ({ api: (path) => `http://api${path}` }));

const json = (status, body) =>
	new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });

const editions = [{ id: 1, year: 2026, host: 'Paris', photos_url: null }];

const run = async ({ token, user }) => {
	const cookies = { get: (name) => (name === 'token' ? token : undefined), delete: vi.fn() };
	const fetch = vi.fn(async (url) => {
		if (url.endsWith('/editions/')) return json(200, editions);
		if (url.endsWith('/user/current/')) return user;
		throw new Error(`unexpected ${url}`);
	});
	const data = await load({ fetch, cookies });
	return { data, cookies, fetch };
};

describe('root layout load', () => {
	it('is anonymous without a cookie and never asks who the user is', async () => {
		const { data, fetch } = await run({ token: undefined });
		expect(data.organiser).toBe(false);
		expect(data.latestYear).toBe(2026);
		expect(fetch.mock.calls.some(([url]) => url.endsWith('/user/current/'))).toBe(false);
	});

	it('is an organiser for a staff token', async () => {
		const { data, fetch } = await run({ token: 'abc', user: json(200, { is_staff: true }) });
		expect(data.organiser).toBe(true);
		const call = fetch.mock.calls.find(([url]) => url.endsWith('/user/current/'));
		expect(call[1].headers).toEqual({ authorization: 'Token abc' });
	});

	it('is not an organiser for a player token', async () => {
		const { data, cookies } = await run({ token: 'abc', user: json(200, { is_staff: false }) });
		expect(data.organiser).toBe(false);
		expect(cookies.delete).not.toHaveBeenCalled();
	});

	it('drops a dead token', async () => {
		const { data, cookies } = await run({ token: 'abc', user: json(401, { detail: 'Invalid token.' }) });
		expect(data.organiser).toBe(false);
		expect(cookies.delete).toHaveBeenCalledWith('token', { path: '/' });
	});

	it('keeps the token when the API is down', async () => {
		const { data, cookies } = await run({ token: 'abc', user: json(502, { error: 'x' }) });
		expect(data.organiser).toBe(false);
		expect(cookies.delete).not.toHaveBeenCalled();
	});
});
```

`front/src/routes/[year=year]/layout.server.test.js`:

```js
import { describe, expect, it, vi } from 'vitest';
import { load } from './+layout.server.js';

vi.mock('$lib/server/urls', () => ({ api: (path) => `http://api${path}` }));

const json = (status, body) =>
	new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });

const run = async ({ year, organiser, latestYear, token }) => {
	const fetch = vi.fn(async () => json(200, { edition: { year: Number(year) } }));
	const cookies = { get: (name) => (name === 'token' ? token : undefined) };
	const parent = async () => ({ organiser, latestYear });
	const data = await load({ fetch, cookies, params: { year }, parent });
	return { data, fetch };
};

describe('year layout load', () => {
	it('is editable for an organiser on the latest year only', async () => {
		expect((await run({ year: '2026', organiser: true, latestYear: 2026, token: 'abc' })).data.editable).toBe(true);
		expect((await run({ year: '2024', organiser: true, latestYear: 2026, token: 'abc' })).data.editable).toBe(false);
		expect((await run({ year: '2026', organiser: false, latestYear: 2026 })).data.editable).toBe(false);
	});

	it('fetches the summary with the token for an organiser and without it otherwise', async () => {
		const staff = await run({ year: '2026', organiser: true, latestYear: 2026, token: 'abc' });
		expect(staff.fetch.mock.calls[0][1].headers).toEqual({ authorization: 'Token abc' });
		const anon = await run({ year: '2026', organiser: false, latestYear: 2026, token: 'abc' });
		expect(anon.fetch.mock.calls[0][1].headers).toEqual({});
	});
});
```

In `front/src/lib/components/Header.test.js` add:

```js
	it('shows the ORGA pill with a logout form to an organiser', () => {
		renderWith(Header, {}, 'fr', true);

		const form = screen.getByRole('form', { name: 'Se déconnecter' });
		expect(form).toHaveAttribute('action', '/logout');
		expect(form.querySelector('input[name="redirectTo"]')).toHaveValue('/2026/ranking?tab=all');
		expect(screen.getByRole('button', { name: 'Se déconnecter' })).toHaveTextContent('Orga');
	});

	it('shows nothing of it to a visitor', () => {
		renderWith(Header, {}, 'en');
		expect(screen.queryByRole('form', { name: 'Log out' })).toBeNull();
	});
```

- [ ] **Step 2: Run them to verify they fail**

Run: `docker compose exec -T front npx vitest run src/lib/session src/lib/api src/routes/logout src/routes/layout.server src/routes/\[year=year\]/layout.server src/lib/components/Header`
Expected: FAIL (missing modules, `apiPatch` undefined, `organiser` undefined, no form).

- [ ] **Step 3: `session.js`, `api.js`, `test-utils.js`**

`front/src/lib/session.js`:

```js
import { getContext } from 'svelte';

/** Svelte context key under which the root layout stores whether the visitor is an organiser. */
export const ORGANISER = 'organiser';

/** Cookie holding the bare DRF token after /login; deleted by /logout. */
export const TOKEN_COOKIE = 'token';

/**
 * httpOnly, site-wide, one week; lax so an organiser arriving from an outside link is still
 * logged in (SvelteKit's origin check covers CSRF). `secure` is left to SvelteKit (true off localhost).
 */
export const tokenCookieOptions = () => ({
	httpOnly: true,
	sameSite: 'lax',
	maxAge: 60 * 60 * 24 * 7,
	path: '/'
});

/** Whether the visitor is a staff user; false outside any layout (tests). Init only. */
export const useOrganiser = () => getContext(ORGANISER) ?? false;
```

In `front/src/lib/api.js`: `request(fetch, url, options)` gains a `token` argument and merges the header:

```js
/** The DRF token header when a token is given, nothing otherwise. */
const authHeaders = (token) => (token ? { authorization: `Token ${token}` } : {});

async function request(fetch, url, options, token = null) {
	const headers = { ...(options.headers ?? {}), ...authHeaders(token) };
	let response;
	try {
		response = await fetch(url, { ...options, headers });
	} catch {
		error(502, 'API unreachable');
	}
	// … unchanged from here
```

and the three exports become:

```js
/** GET a JSON resource; throws a SvelteKit error on any failure. */
export function apiGet(fetch, url, token = null) {
	return request(fetch, url, { method: 'GET', headers: {} }, token);
}

/** POST a JSON body; throws a SvelteKit error on any failure. */
export function apiPost(fetch, url, body, token = null) {
	return request(fetch, url, jsonOptions('POST', body), token);
}

/** PATCH a JSON body; throws a SvelteKit error on any failure. */
export function apiPatch(fetch, url, body, token = null) {
	return request(fetch, url, jsonOptions('PATCH', body), token);
}

const jsonOptions = (method, body) => ({
	method,
	headers: { 'content-type': 'application/json' },
	body: JSON.stringify(body)
});
```

(the existing `apiGet` test asserts `headers: {}` without a token: keep that behaviour, `authHeaders(null)` is `{}`).

`front/src/lib/test-utils.js` becomes:

```js
import { render } from '@testing-library/svelte';
import { I18N } from '$lib/i18n';
import { ORGANISER } from '$lib/session';

/**
 * Render a component with the locale and the organiser flag in context, as the root
 * layout does at runtime. Existing tests assert English text, so `en` is the default;
 * French and the organiser view are opt-in.
 */
export const renderWith = (Component, props = {}, locale = 'en', organiser = false) =>
	render(Component, {
		props,
		context: new Map([
			[I18N, locale],
			[ORGANISER, organiser]
		])
	});
```

- [ ] **Step 4: Login, logout, layouts, header**

`front/src/routes/login/+page.server.js`: replace `setAuthToken` and its call with

```js
import { TOKEN_COOKIE, tokenCookieOptions } from '$lib/session';
// …
		cookies.set(TOKEN_COOKIE, token, tokenCookieOptions());
		redirect(302, '/');
```

(delete the `setAuthToken` function; `secure` is no longer passed, SvelteKit defaults it).

`front/src/routes/logout/+page.server.js`:

```js
import { redirect } from '@sveltejs/kit';
import { TOKEN_COOKIE } from '$lib/session';

/** Same guard as /lang: one leading slash, no control characters. */
const localPath = (value) =>
	typeof value === 'string' && /^\/(?![/\\])[^\s\x00-\x1f\x7f]*$/.test(value) ? value : '/';

export const load = () => {
	redirect(303, '/');
};

export const actions = {
	/** The header's ORGA pill: forget the token, come back to the same page as a visitor. */
	default: async ({ cookies, request }) => {
		const form = await request.formData();
		cookies.delete(TOKEN_COOKIE, { path: '/' });
		redirect(303, localPath(form.get('redirectTo')));
	}
};
```

`front/src/routes/+layout.server.js` becomes:

```js
import { apiGet } from '$lib/api';
import { api } from '$lib/server/urls';
import { localeFrom } from '$lib/i18n/locale.js';
import { TOKEN_COOKIE } from '$lib/session';

/**
 * Whether the token cookie belongs to a staff user. A dead token (401/403) is dropped;
 * any other failure (API down) keeps it and counts as a visitor for this request.
 */
async function resolveOrganiser(fetch, cookies) {
	const token = cookies.get(TOKEN_COOKIE);
	if (!token) return false;
	try {
		const user = await apiGet(fetch, api('/user/current/'), token);
		return Boolean(user?.is_staff);
	} catch (err) {
		if (err?.status === 401 || err?.status === 403) cookies.delete(TOKEN_COOKIE, { path: '/' });
		return false;
	}
}

/**
 * Every active edition, newest first, plus the year the bare URLs default to, the
 * visitor's language from the `lang` cookie (French unless they switched) and whether
 * they are an organiser. Only the fields the nav and hub need ride along.
 */
export const load = async ({ fetch, cookies }) => {
	const editions = (await apiGet(fetch, api('/editions/')))
		.map(({ id, year, host, photos_url }) => ({ id, year, host, photos_url }))
		.sort((a, b) => b.year - a.year);
	return {
		editions,
		latestYear: editions[0]?.year ?? null,
		locale: localeFrom(cookies.get('lang')),
		organiser: await resolveOrganiser(fetch, cookies)
	};
};
```

`front/src/routes/+layout.svelte`: add `import { ORGANISER } from '$lib/session';` and, after `setContext(I18N, data.locale);`, `setContext(ORGANISER, data.organiser);`.

`front/src/routes/[year=year]/+layout.server.js` becomes:

```js
import { error } from '@sveltejs/kit';
import { apiGet } from '$lib/api';
import { api } from '$lib/server/urls';
import { TOKEN_COOKIE } from '$lib/session';

/**
 * The whole edition in one payload; every page under /<year> reads it via parent().
 * An organiser fetches it with their token (hidden scores included) and may edit the
 * latest edition only.
 */
export const load = async ({ fetch, cookies, params, parent }) => {
	const { organiser, latestYear } = await parent();
	const token = organiser ? (cookies.get(TOKEN_COOKIE) ?? null) : null;
	try {
		const summary = await apiGet(fetch, api(`/edition/year/${params.year}/summary/`), token);
		return { summary, editable: organiser && Number(params.year) === latestYear };
	} catch (err) {
		if (err?.status === 404) error(404, `No edition in ${params.year}`);
		throw err;
	}
};
```

`front/src/lib/components/Header.svelte`: add `import { useOrganiser } from '$lib/session';` and `const organiser = useOrganiser();` in the script; in the markup, right before the `<form method="POST" action="/lang" …>`:

```svelte
		{#if organiser}
			<!-- A plain POST like the language switch: the redirect reloads the page as a visitor. -->
			<form method="POST" action="/logout" class="orga" aria-label={t('orga.logout')}>
				<input type="hidden" name="redirectTo" value={$page.url.pathname + $page.url.search} />
				<!-- One tap logs out; the accessible name says so, the visible text stays the short pill. -->
				<button aria-label={t('orga.logout')}>{t('orga.pill')}</button>
			</form>
		{/if}
```

and in the style, after the `.lang button:focus-visible` rule:

```css
	.orga {
		margin: 0;
	}

	.orga button {
		min-height: 44px;
		padding: 0 0.9em;
		background: var(--accent);
		color: var(--bg);
		border: 1px solid var(--accent);
		border-radius: var(--radius-pill);
		font-family: var(--font-display);
		font-size: 1.1rem;
		letter-spacing: 0.08em;
		cursor: pointer;
	}

	.orga button:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}
```

Dictionary: `login.missing` is the last key of both files and has no trailing comma; add one, then append `'orga.pill': 'Orga',` and `'orga.logout': 'Se déconnecter'` to `fr.js`, `'orga.pill': 'Orga',` and `'orga.logout': 'Log out'` to `en.js`.

- [ ] **Step 5: Run the suite, build, live check**

Run: `docker compose exec -T front npm test` → green. `docker compose exec -T front npm run build` → `✓ built`.

Live: log in at `http://localhost:5173/login` with the local staff user (see Working environment), then `curl` cannot follow the httpOnly cookie easily, so check in a browser or with: `TOKEN=$(curl -s -X POST -H 'content-type: application/json' -d "{\"username\":\"$SU\",\"password\":\"$PW\"}" http://localhost:3003/auth/token/ | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')` then `curl -s -b "token=$TOKEN" http://localhost:5173/2026/ranking | grep -o 'action="/logout"'` prints the logout form, and `curl -s -b "token=deadbeef" http://localhost:5173/2026/ranking | grep -c 'action="/logout"'` prints 0.

- [ ] **Step 6: Commit**

```bash
git add front/src/lib/session.js front/src/lib/session.test.js front/src/lib/api.js front/src/lib/api.test.js front/src/lib/test-utils.js front/src/routes/login/+page.server.js front/src/routes/logout front/src/routes/+layout.server.js front/src/routes/layout.server.test.js front/src/routes/+layout.svelte "front/src/routes/[year=year]/+layout.server.js" "front/src/routes/[year=year]/layout.server.test.js" front/src/lib/components/Header.svelte front/src/lib/components/Header.test.js front/src/lib/i18n/fr.js front/src/lib/i18n/en.js
git commit -m "[FEAT] front: token cookie, organiser flag from the API, editable latest edition, logout and ORGA pill

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Task 4: Dictionary, helpers, fixtures, `GameRow.onEdit`, `ScoreSheet`, `StaffBar`

**Files:**
- Modify: `front/src/lib/i18n/fr.js`, `en.js`
- Modify: `front/src/lib/edition.js`, `edition.test.js`, `front/src/lib/fixtures/summary.js`
- Modify: `front/src/lib/components/GameRow.svelte`, `GameRow.test.js`
- Create: `front/src/lib/components/ScoreSheet.svelte`, `ScoreSheet.test.js`, `StaffBar.svelte`, `StaffBar.test.js`

- [ ] **Step 1: Dictionary keys**

Add to `fr.js` after `orga.logout` (add the comma it lacks):

```js
	'orga.hidden': 'Résultats masqués pour le public',
	'orga.public': 'Résultats publics',
	'orga.reveal': 'Dévoiler',
	'orga.hide': 'Masquer',
	'orga.missingResults': { one: '{n} équipe sans résultat', other: '{n} équipes sans résultat' },
	'orga.edit': 'Saisir le score',
	'orga.played': 'Joué',
	'orga.save': 'Enregistrer',
	'orga.cancel': 'Annuler',
	'orga.closeRound': 'Clore le tour',
	'orga.roundClosed': 'Terminé',
	'orga.timeHint': 'mm:ss',
	'orga.error.unauthorised': 'Session expirée, reconnectez-vous',
	'orga.error.forbidden': 'Réservé aux organisateurs',
	'orga.error.invalid': 'Valeur refusée',
	'orga.error.conflict': 'Impossible pour cette édition ou ce tour',
	'orga.error.failed': "Échec de l'enregistrement"
```

and to `en.js`:

```js
	'orga.hidden': 'Results hidden from the public',
	'orga.public': 'Results are public',
	'orga.reveal': 'Reveal',
	'orga.hide': 'Hide',
	'orga.missingResults': { one: '{n} team without a result', other: '{n} teams without a result' },
	'orga.edit': 'Enter the score',
	'orga.played': 'Played',
	'orga.save': 'Save',
	'orga.cancel': 'Cancel',
	'orga.closeRound': 'Close the round',
	'orga.roundClosed': 'Done',
	'orga.timeHint': 'mm:ss',
	'orga.error.unauthorised': 'Session expired, log in again',
	'orga.error.forbidden': 'Organisers only',
	'orga.error.invalid': 'Value refused',
	'orga.error.conflict': 'Not possible for this edition or round',
	'orga.error.failed': 'Could not save'
```

Run: `docker compose exec -T front npx vitest run src/lib/i18n` → PASS (parity).

- [ ] **Step 2: Fixtures**

In `front/src/lib/fixtures/summary.js`: the two disciplines gain `pairing_system`: Relay `'RR'`, Orienteering `'SW'` (in `summaryAllRevealed` too, it spreads them). Append:

```js
/**
 * What a staff user gets on the same edition: hidden game scores and stored results
 * visible, rankings still null, plus a hidden Darts without rounds (points to enter).
 */
export const summaryStaff = {
	...summary,
	disciplines: [
		...summary.disciplines,
		{ id: 12, name: 'Darts', result_type: 'PTS', reveal_score: false, pairing_system: 'NO' }
	],
	results: [
		...summary.results.slice(0, 3),
		{ id: 103, team: 1, discipline: 11, result_type: 'TIM', ranking: null, points: null, time: '00:12:30', points_difference: null, global_points: null },
		{ id: 104, team: 2, discipline: 11, result_type: 'TIM', ranking: null, points: null, time: null, points_difference: null, global_points: null },
		{ id: 105, team: 3, discipline: 11, result_type: 'TIM', ranking: null, points: null, time: '00:13:45', points_difference: null, global_points: null },
		{ id: 106, team: 1, discipline: 12, result_type: 'PTS', ranking: null, points: 20, time: null, points_difference: null, global_points: null },
		{ id: 107, team: 2, discipline: 12, result_type: 'PTS', ranking: null, points: null, time: null, points_difference: null, global_points: null },
		{ id: 108, team: 3, discipline: 12, result_type: 'PTS', ranking: null, points: 15, time: null, points_difference: null, global_points: null }
	],
	games: [...summary.games.slice(0, 3), { ...summary.games[3], score1: 3, score2: 1 }]
};
```

- [ ] **Step 3: Helper tests**

Append to `front/src/lib/edition.test.js` (import `disciplineEntries`, `formatTime` and `summaryStaff` at the top):

```js
describe('formatTime', () => {
	it('drops zero hours and keeps them otherwise', () => {
		expect(formatTime('00:13:15')).toBe('13:15');
		expect(formatTime('01:02:03')).toBe('1:02:03');
		expect(formatTime('00:00:07')).toBe('00:07');
		expect(formatTime(null)).toBeNull();
	});
});

describe('disciplineEntries', () => {
	it('lists one line per team with the stored value, by name while hidden', () => {
		expect(disciplineEntries(summaryStaff, 12)).toEqual([
			{ id: 106, team: 1, teamName: 'Aigles', points: 20, time: null, ranking: null },
			{ id: 107, team: 2, teamName: 'Bisons', points: null, time: null, ranking: null },
			{ id: 108, team: 3, teamName: 'Cerfs', points: 15, time: null, ranking: null }
		]);
	});

	it('orders by rank once revealed', () => {
		expect(disciplineEntries(summaryAllRevealed, 11).map((e) => e.teamName)).toEqual([
			'Aigles',
			'Cerfs',
			'Bisons'
		]);
	});

	it('is empty for an unknown discipline', () => {
		expect(disciplineEntries(summaryStaff, 99)).toEqual([]);
	});
});
```

Run: `docker compose exec -T front npx vitest run src/lib/edition.test.js` → FAIL (not exported).

- [ ] **Step 4: Helpers**

In `disciplineSchedule` (`front/src/lib/edition.js`), the round object gains its id: `{ id: round.id, order: round.order, isOver: round.is_over, games: … }` (the page's close-round form posts it). Add `id` to every expected round object in the `disciplineSchedule` tests of `edition.test.js` (`id: 20`, `id: 21`, and `id: 23` for the empty round of `includes a round with no games as an empty entry`).

Append to `front/src/lib/edition.js`:

```js
/** "00:13:15" → "13:15", "01:02:03" → "1:02:03"; hours only when they are not zero. */
export function formatTime(hhmmss) {
	if (!hhmmss) return null;
	const [h, m, s] = hhmmss.split(':');
	return Number(h) === 0 ? `${m}:${s}` : `${Number(h)}:${m}:${s}`;
}

/**
 * One entry line per team of a discipline, for the organiser's result form: the stored
 * points and time as the staff summary carries them. Rank order once revealed, else by
 * team name.
 */
export function disciplineEntries(summary, disciplineId) {
	const names = teamNames(summary);
	const rank = (r) => r.ranking ?? Number.POSITIVE_INFINITY;
	return summary.results
		.filter((r) => r.discipline === disciplineId)
		.map((r) => ({
			id: r.id,
			team: r.team,
			teamName: nameOf(names, r.team),
			points: r.points,
			time: r.time,
			ranking: r.ranking
		}))
		.sort((a, b) => rank(a) - rank(b) || (a.teamName ?? '').localeCompare(b.teamName ?? ''));
}
```

Run: `docker compose exec -T front npx vitest run src/lib/edition.test.js` → PASS.

- [ ] **Step 5: `GameRow.onEdit`**

Append to `GameRow.test.js`:

```js
	it('wraps the pairing in a button when onEdit is given and calls it on click', async () => {
		const onEdit = vi.fn();
		renderWith(GameRow, { ...played, onEdit });

		const button = screen.getByRole('button', { name: /Bisons\s*12 : 9\s*Aigles/ });
		await fireEvent.click(button);
		expect(onEdit).toHaveBeenCalledTimes(1);
		expect(screen.queryByRole('link')).toBeNull();
	});

	it('has no button without onEdit', () => {
		renderWith(GameRow, played);
		expect(screen.queryByRole('button')).toBeNull();
	});
```

(add `vi` to the vitest import and `fireEvent` to the testing-library import.)

In `GameRow.svelte`: add the prop after `highlightId`:

```js
	/** When set, the pairing is a button calling it (the organiser's score sheet). */
	export let onEdit = null;
```

and replace the markup from `<div class="game-row"` to the closing `</div>` with:

```svelte
<div class="game-row" data-testid="game-row">
	{#if onEdit}
		<!-- The organiser taps the pairing to open the score sheet: no links inside a button. -->
		<button type="button" class="teams edit" on:click={onEdit} title={t('orga.edit')}>
			{#if roundLabel}
				<span class="round label">{roundLabel}</span>
			{/if}
			<span class="team {team1Class}">{name1}</span>
			<!-- Same score block as the public branch: Svelte 4 has no local snippets. -->
			{#if hasScore}
				<span class="score num">{score1} : {score2}</span>
			{:else if !isPlayed}
				<span class="score num unplayed">— : —</span>
			{:else}
				<span class="score pending">{t('game.played')}</span>
			{/if}
			<span class="team right {team2Class}">{name2}</span>
		</button>
	{:else}
		<p class="teams">
			{#if roundLabel}
				<span class="round label">{roundLabel}</span>
			{/if}

			{#if team1Href && !own1}
				<a class="team {team1Class}" href={team1Href}>{name1}</a>
			{:else}
				<span class="team {team1Class}" class:own={own1}>{name1}</span>
			{/if}

			{#if hasScore}
				<span class="score num">{score1} : {score2}</span>
			{:else if !isPlayed}
				<span class="score num unplayed">— : —</span>
			{:else}
				<span class="score pending">{t('game.played')}</span>
			{/if}

			{#if team2Href && !own2}
				<a class="team right {team2Class}" href={team2Href}>{name2}</a>
			{:else}
				<span class="team right {team2Class}" class:own={own2}>{name2}</span>
			{/if}
		</p>
	{/if}
	{#if refereeName}
		<p class="referee">{t('game.referee', { name: refereeName })}</p>
	{/if}
</div>
```

Style additions:

```css
	.teams.edit {
		width: 100%;
		background: transparent;
		border: 0;
		padding: 0;
		font: inherit;
		color: inherit;
		text-align: inherit;
		cursor: pointer;
	}

	.teams.edit .team {
		text-align: left;
	}

	.teams.edit .team.right {
		text-align: right;
	}

	.teams.edit:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 4px;
		border-radius: 2px;
	}
```

Run: `docker compose exec -T front npx vitest run src/lib/components/GameRow` → PASS.

- [ ] **Step 6: `ScoreSheet` tests**

`front/src/lib/components/ScoreSheet.test.js`:

```js
import { fireEvent, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import { renderWith } from '$lib/test-utils';
import ScoreSheet from './ScoreSheet.svelte';

vi.mock('$app/forms', () => ({ enhance: () => ({ destroy() {} }) }));

const game = {
	id: 201,
	team1Id: 3,
	team1Name: 'Cerfs',
	team2Id: 2,
	team2Name: 'Bisons',
	refereeName: 'Aigles',
	isPlayed: false,
	score1: 0,
	score2: 0
};

describe('ScoreSheet', () => {
	it('renders both teams, the round and the referee, and posts the game id', () => {
		renderWith(ScoreSheet, { game, roundNumber: 1, open: true });

		const dialog = screen.getByRole('dialog', { name: 'Round 1 · ref: Aigles' });
		expect(dialog).toHaveTextContent(/Cerfs/);
		expect(dialog).toHaveTextContent(/Bisons/);
		const form = dialog.querySelector('form');
		expect(form).toHaveAttribute('action', '?/score');
		expect(form.querySelector('input[name="game"]')).toHaveValue('201');
	});

	it('steps the scores and never below zero', async () => {
		renderWith(ScoreSheet, { game, roundNumber: 1, open: true });

		const [minus1, plus1] = screen.getAllByRole('button', { name: /Cerfs/ });
		const score1 = screen.getByLabelText('Cerfs');
		await fireEvent.click(plus1);
		await fireEvent.click(plus1);
		expect(score1).toHaveValue(2);
		await fireEvent.click(minus1);
		await fireEvent.click(minus1);
		await fireEvent.click(minus1);
		expect(score1).toHaveValue(0);
	});

	it('starts the played switch on for an unplayed game', () => {
		renderWith(ScoreSheet, { game, roundNumber: 1, open: true });
		expect(screen.getByRole('checkbox', { name: 'Played' })).toBeChecked();
	});

	it('reflects the loaded score of a played game', () => {
		renderWith(ScoreSheet, { game: { ...game, isPlayed: true, score1: 12, score2: 9 }, roundNumber: 2, open: true });
		expect(screen.getByLabelText('Cerfs')).toHaveValue(12);
		expect(screen.getByLabelText('Bisons')).toHaveValue(9);
		expect(screen.getByRole('checkbox', { name: 'Played' })).toBeChecked();
	});

	it('closes on cancel, on Escape and on the backdrop', async () => {
		const { component } = renderWith(ScoreSheet, { game, roundNumber: 1, open: true });
		const closed = vi.fn();
		component.$on('close', closed);

		await fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
		await fireEvent.keyDown(window, { key: 'Escape' });
		await fireEvent.click(screen.getByTestId('backdrop'));
		expect(closed).toHaveBeenCalledTimes(3);
	});

	it('focuses the first score field when it opens', async () => {
		renderWith(ScoreSheet, { game, roundNumber: 1, open: true });
		await new Promise((resolve) => setTimeout(resolve, 0));
		expect(screen.getByLabelText('Cerfs')).toHaveFocus();
	});

	it('renders nothing when closed and shows the error line when given', () => {
		const { container } = renderWith(ScoreSheet, { game, roundNumber: 1, open: false });
		expect(container.querySelector('[role="dialog"]')).toBeNull();

		renderWith(ScoreSheet, { game, roundNumber: 1, open: true, error: 'orga.error.conflict' });
		expect(screen.getByRole('alert')).toHaveTextContent('Not possible for this edition or round');
	});

	it('speaks French under fr', () => {
		renderWith(ScoreSheet, { game, roundNumber: 1, open: true }, 'fr');
		expect(screen.getByRole('dialog', { name: 'Tour 1 · arbitre : Aigles' })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Enregistrer' })).toBeInTheDocument();
		expect(screen.getByRole('checkbox', { name: 'Joué' })).toBeInTheDocument();
	});
});
```

Run: `docker compose exec -T front npx vitest run src/lib/components/ScoreSheet` → FAIL (no module).

- [ ] **Step 7: `ScoreSheet.svelte`**

```svelte
<script>
	import { createEventDispatcher, tick } from 'svelte';
	import { enhance } from '$app/forms';
	import { useT } from '$lib/i18n';

	/** A game as `disciplineSchedule` shapes it (ids, names, scores, isPlayed, refereeName). */
	export let game;
	/** 1-based round number for the label. */
	export let roundNumber;
	export let open = false;
	/** A dictionary key for the line under the form, or null. */
	export let error = null;

	const t = useT();
	const dispatch = createEventDispatcher();

	/** The first score field, focused when the sheet opens; the page refocuses the row on close. */
	let firstField = null;
	$: if (open && firstField) tick().then(() => firstField?.focus());

	// Local copies: the steppers edit these, the loaded game stays as it is until the
	// action succeeds and the page reloads its data.
	let score1 = 0;
	let score2 = 0;
	let played = true;
	// The switch starts on whenever the sheet opens: saving a score means the game was played.
	$: if (open) {
		score1 = game.score1 ?? 0;
		score2 = game.score2 ?? 0;
		played = true;
	}

	const clamp = (n) => Math.max(0, Number.isFinite(n) ? n : 0);
	const close = () => dispatch('close');
	const onKey = (event) => {
		if (open && event.key === 'Escape') close();
	};
	// After a successful save the page's data reloads; the sheet closes on that success.
	const afterSubmit = () => async ({ result, update }) => {
		await update();
		if (result.type === 'success') close();
	};
	$: title = `${t('discipline.round', { n: roundNumber })} · ${t('game.referee', { name: game.refereeName ?? t('team.unknown') })}`;
</script>

<svelte:window on:keydown={onKey} />

{#if open}
	<div class="backdrop" data-testid="backdrop" on:click={close} aria-hidden="true"></div>
	<div class="sheet" role="dialog" aria-modal="true" aria-label={title}>
		<form method="POST" action="?/score" use:enhance={afterSubmit}>
			<input type="hidden" name="game" value={game.id} />
			<p class="label">{title}</p>

			<div class="line">
				<label class="name" for="score1-{game.id}">{game.team1Name ?? t('team.unknown')}</label>
				<span class="stepper">
					<button type="button" aria-label="− {game.team1Name}" on:click={() => (score1 = clamp(score1 - 1))}>−</button>
					<input id="score1-{game.id}" name="score1" type="number" inputmode="numeric" min="0" bind:value={score1} bind:this={firstField} />
					<button type="button" aria-label="+ {game.team1Name}" on:click={() => (score1 = clamp(score1 + 1))}>+</button>
				</span>
			</div>

			<div class="line">
				<label class="name" for="score2-{game.id}">{game.team2Name ?? t('team.unknown')}</label>
				<span class="stepper">
					<button type="button" aria-label="− {game.team2Name}" on:click={() => (score2 = clamp(score2 - 1))}>−</button>
					<input id="score2-{game.id}" name="score2" type="number" inputmode="numeric" min="0" bind:value={score2} />
					<button type="button" aria-label="+ {game.team2Name}" on:click={() => (score2 = clamp(score2 + 1))}>+</button>
				</span>
			</div>

			<label class="switch">
				<input type="checkbox" name="is_played" bind:checked={played} />
				<span class="track" aria-hidden="true"></span>
				{t('orga.played')}
			</label>

			{#if error}
				<p class="error" role="alert">{t(error)}</p>
			{/if}

			<div class="actions">
				<button type="button" class="ghost" on:click={close}>{t('orga.cancel')}</button>
				<button type="submit">{t('orga.save')}</button>
			</div>
		</form>
	</div>
{/if}

<style>
	.backdrop {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.6);
		z-index: 20;
	}

	.sheet {
		position: fixed;
		left: 0;
		right: 0;
		bottom: 0;
		z-index: 21;
		background: var(--bg-raised);
		border: 1px solid var(--line);
		border-radius: var(--radius-lg) var(--radius-lg) 0 0;
		padding: 1rem 1rem calc(1rem + env(safe-area-inset-bottom));
		max-height: 90vh;
		overflow-y: auto;
	}

	.line {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 1rem;
		margin: 0.8rem 0;
	}

	.name {
		font-weight: 600;
		min-width: 0;
		overflow-wrap: anywhere;
	}

	.stepper {
		display: flex;
		align-items: center;
		gap: 6px;
		flex: none;
	}

	.stepper button {
		width: 44px;
		height: 44px;
		border-radius: var(--radius);
		background: var(--bg-sunken);
		border: 1px solid var(--line-strong);
		color: var(--accent);
		font-size: 1.4rem;
		cursor: pointer;
	}

	.stepper input {
		width: 3.2rem;
		height: 44px;
		text-align: center;
		background: var(--bg-sunken);
		border: 1px solid var(--line-strong);
		border-radius: var(--radius);
		color: var(--ink);
		font-family: var(--font-display);
		font-size: 1.5rem;
		-moz-appearance: textfield;
	}

	.stepper input::-webkit-outer-spin-button,
	.stepper input::-webkit-inner-spin-button {
		appearance: none;
		margin: 0;
	}

	.switch {
		display: inline-flex;
		align-items: center;
		gap: 0.6rem;
		margin: 0.4rem 0 0.8rem;
		cursor: pointer;
		color: var(--text);
	}

	.switch input {
		position: absolute;
		opacity: 0;
		width: 1px;
		height: 1px;
	}

	.track {
		width: 36px;
		height: 20px;
		border-radius: var(--radius-pill);
		background: var(--line-strong);
		position: relative;
		transition: background 0.2s ease;
	}

	.track::after {
		content: '';
		position: absolute;
		top: 2px;
		left: 2px;
		width: 16px;
		height: 16px;
		border-radius: 50%;
		background: var(--ink);
		transition: transform 0.2s ease;
	}

	.switch input:checked + .track {
		background: var(--accent);
	}

	.switch input:checked + .track::after {
		transform: translateX(16px);
		background: var(--bg);
	}

	.switch input:focus-visible + .track {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}

	.error {
		margin: 0 0 0.6rem;
		color: var(--loss);
		font-size: 0.85rem;
	}

	.actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.6rem;
	}

	.actions button {
		min-height: 44px;
		padding: 0 1.2rem;
		border-radius: var(--radius);
		font-family: var(--font-display);
		font-size: 1.1rem;
		letter-spacing: 0.1em;
		background: var(--accent);
		color: var(--bg);
		border: 1px solid var(--accent);
		cursor: pointer;
	}

	.actions .ghost {
		background: transparent;
		color: var(--accent);
	}

	button:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}

	@media (min-width: 1000px) {
		.sheet {
			left: 50%;
			right: auto;
			bottom: auto;
			top: 50%;
			width: 420px;
			transform: translate(-50%, -50%);
			border-radius: var(--radius-lg);
		}
	}
</style>
```

Run: `docker compose exec -T front npx vitest run src/lib/components/ScoreSheet` → PASS. (`getAllByRole('button', { name: /Cerfs/ })` returns the minus and plus buttons in DOM order.)

- [ ] **Step 8: `StaffBar` tests and component**

`front/src/lib/components/StaffBar.test.js`:

```js
import { screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import { renderWith } from '$lib/test-utils';
import StaffBar from './StaffBar.svelte';

vi.mock('$app/forms', () => ({ enhance: () => ({ destroy() {} }) }));

describe('StaffBar', () => {
	it('offers to reveal a hidden discipline and says what is missing', () => {
		renderWith(StaffBar, { disciplineId: 12, revealed: false, missing: '2 teams without a result' });

		expect(screen.getByText('Results hidden from the public')).toBeInTheDocument();
		expect(screen.getByText('2 teams without a result')).toBeInTheDocument();
		const form = screen.getByRole('button', { name: 'Reveal' }).closest('form');
		expect(form).toHaveAttribute('action', '?/reveal');
		expect(form.querySelector('input[name="discipline"]')).toHaveValue('12');
		expect(form.querySelector('input[name="reveal_score"]')).toHaveValue('true');
	});

	it('offers to hide a revealed one', () => {
		renderWith(StaffBar, { disciplineId: 12, revealed: true, missing: null });

		expect(screen.getByText('Results are public')).toBeInTheDocument();
		const form = screen.getByRole('button', { name: 'Hide' }).closest('form');
		expect(form.querySelector('input[name="reveal_score"]')).toHaveValue('false');
	});

	it('shows the error line and speaks French', () => {
		renderWith(StaffBar, { disciplineId: 12, revealed: false, missing: null, error: 'orga.error.failed' }, 'fr');
		expect(screen.getByText('Résultats masqués pour le public')).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Dévoiler' })).toBeInTheDocument();
		expect(screen.getByRole('alert')).toHaveTextContent("Échec de l'enregistrement");
	});
});
```

`front/src/lib/components/StaffBar.svelte`:

```svelte
<script>
	import { enhance } from '$app/forms';
	import { useT } from '$lib/i18n';

	export let disciplineId;
	export let revealed = false;
	/** Worded count of what is still missing, or null when nothing is. */
	export let missing = null;
	/** A dictionary key for the line under the bar, or null. */
	export let error = null;

	const t = useT();
</script>

<div class="bar" class:revealed>
	<div class="text">
		<span class="status">{revealed ? t('orga.public') : t('orga.hidden')}</span>
		{#if missing}
			<span class="missing">{missing}</span>
		{/if}
	</div>
	<form method="POST" action="?/reveal" use:enhance>
		<input type="hidden" name="discipline" value={disciplineId} />
		<input type="hidden" name="reveal_score" value={revealed ? 'false' : 'true'} />
		<button>{revealed ? t('orga.hide') : t('orga.reveal')}</button>
	</form>
	{#if error}
		<p class="error" role="alert">{t(error)}</p>
	{/if}
</div>

<style>
	.bar {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: 0.6rem 1rem;
		margin: 0 0 14px;
		padding: 0.7rem 0.9rem;
		border: 1px dashed var(--todo);
		border-radius: var(--radius);
	}

	.bar.revealed {
		border-color: var(--win);
	}

	.text {
		display: flex;
		flex-direction: column;
		gap: 2px;
		min-width: 0;
	}

	.status {
		font-weight: 600;
	}

	.missing {
		font-size: 0.85rem;
		color: var(--muted);
	}

	form {
		margin: 0;
	}

	button {
		min-height: 44px;
		padding: 0 1.2rem;
		border-radius: var(--radius);
		background: var(--accent);
		color: var(--bg);
		border: 1px solid var(--accent);
		font-family: var(--font-display);
		font-size: 1.1rem;
		letter-spacing: 0.1em;
		cursor: pointer;
	}

	button:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}

	.error {
		flex-basis: 100%;
		margin: 0;
		color: var(--loss);
		font-size: 0.85rem;
	}
</style>
```

Run: `docker compose exec -T front npx vitest run src/lib/components/StaffBar` → PASS.

- [ ] **Step 9: Suite and commit**

Run: `docker compose exec -T front npm test` → green.

```bash
git add front/src/lib/i18n/fr.js front/src/lib/i18n/en.js front/src/lib/edition.js front/src/lib/edition.test.js front/src/lib/fixtures/summary.js front/src/lib/components/GameRow.svelte front/src/lib/components/GameRow.test.js front/src/lib/components/ScoreSheet.svelte front/src/lib/components/ScoreSheet.test.js front/src/lib/components/StaffBar.svelte front/src/lib/components/StaffBar.test.js
git commit -m "[FEAT] front: organiser dictionary, formatTime and disciplineEntries, GameRow onEdit, ScoreSheet and StaffBar

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Task 5: The discipline page controls and actions

**Files:**
- Create: `front/src/routes/[year=year]/disciplines/[id]/+page.server.js`, `page.server.test.js`
- Modify: `front/src/routes/[year=year]/disciplines/[id]/+page.svelte`, `page.test.js`
- Modify: `front/src/routes/[year=year]/teams/[id]/+page.svelte` (time through `formatTime`)

- [ ] **Step 1: Action tests**

`front/src/routes/[year=year]/disciplines/[id]/page.server.test.js`:

```js
import { describe, expect, it, vi } from 'vitest';
import { actions } from './+page.server.js';

vi.mock('$lib/server/urls', () => ({ api: (path) => `http://api${path}` }));

const json = (status, body) =>
	new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });

const post = (fields) => {
	const body = new FormData();
	for (const [name, value] of Object.entries(fields)) body.append(name, value);
	return new Request('http://localhost/2026/disciplines/10', { method: 'POST', body });
};

const call = (action, fields, { token = 'abc', response = json(200, {}) } = {}) => {
	const fetch = vi.fn().mockResolvedValue(response);
	const cookies = { get: (name) => (name === 'token' ? token : undefined) };
	return actions[action]({ cookies, request: post(fields), fetch }).then((result) => ({ result, fetch }));
};

describe('discipline actions', () => {
	it('score patches the game with both scores and the played flag', async () => {
		const { result, fetch } = await call('score', { game: '201', score1: '7', score2: '3', is_played: 'on' });
		expect(result).toEqual({ ok: true, action: 'score', id: 201 });
		expect(fetch).toHaveBeenCalledWith('http://api/game/201/score/', expect.objectContaining({
			method: 'PATCH',
			headers: { 'content-type': 'application/json', authorization: 'Token abc' },
			body: JSON.stringify({ score1: 7, score2: 3, is_played: true })
		}));
	});

	it('score sends is_played false when the switch is off', async () => {
		const { fetch } = await call('score', { game: '201', score1: '0', score2: '0' });
		expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ score1: 0, score2: 0, is_played: false });
	});

	it('result sends points, or a time, and null for an empty field', async () => {
		let { fetch } = await call('result', { result: '106', kind: 'PTS', value: '12' });
		expect(fetch.mock.calls[0][0]).toBe('http://api/result/106/value/');
		expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ points: 12 });
		({ fetch } = await call('result', { result: '103', kind: 'TIM', value: '13:15' }));
		expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ time: '13:15' });
		({ fetch } = await call('result', { result: '103', kind: 'TIM', value: '' }));
		expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ time: null });
	});

	it('reveal and close patch their rows', async () => {
		let { fetch } = await call('reveal', { discipline: '12', reveal_score: 'true' });
		expect(fetch.mock.calls[0][0]).toBe('http://api/discipline/12/reveal/');
		expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ reveal_score: true });
		({ fetch } = await call('close', { round: '22' }));
		expect(fetch.mock.calls[0][0]).toBe('http://api/round/22/close/');
	});

	it('refuses a non-numeric or negative value before calling the API', async () => {
		let { result, fetch } = await call('score', { game: '201', score1: 'x', score2: '3' });
		expect(result).toMatchObject({ status: 400, data: { action: 'score', id: 201, error: 'orga.error.invalid' } });
		expect(fetch).not.toHaveBeenCalled();
		({ result } = await call('result', { result: '106', kind: 'PTS', value: '-2' }));
		expect(result).toMatchObject({ status: 400, data: { error: 'orga.error.invalid' } });
	});

	it('fails with the unauthorised key without a cookie', async () => {
		const { result } = await call('close', { round: '22' }, { token: undefined });
		expect(result).toMatchObject({ status: 401, data: { action: 'close', id: 22, error: 'orga.error.unauthorised' } });
	});

	it('maps API errors to dictionary keys', async () => {
		const cases = [
			[400, 'orga.error.invalid'],
			[401, 'orga.error.unauthorised'],
			[403, 'orga.error.forbidden'],
			[409, 'orga.error.conflict'],
			[502, 'orga.error.failed']
		];
		for (const [status, key] of cases) {
			const { result } = await call('close', { round: '22' }, { response: json(status, { error: 'x' }) });
			expect(result).toMatchObject({ status, data: { error: key } });
		}
	});
});
```

Run: `docker compose exec -T front npx vitest run "src/routes/\[year=year\]/disciplines/\[id\]/page.server"` → FAIL (no module).

- [ ] **Step 2: The actions**

`front/src/routes/[year=year]/disciplines/[id]/+page.server.js`:

```js
import { fail } from '@sveltejs/kit';
import { apiPatch } from '$lib/api';
import { api } from '$lib/server/urls';
import { TOKEN_COOKIE } from '$lib/session';

/** The dictionary key the page shows for an API status; anything else is a plain failure. */
const ERROR_KEYS = {
	400: 'orga.error.invalid',
	401: 'orga.error.unauthorised',
	403: 'orga.error.forbidden',
	409: 'orga.error.conflict'
};

/**
 * One organiser write: the token cookie, one PATCH, and either {ok} or a fail() carrying
 * the action and row so the page can show the line under the right control.
 */
async function patch({ cookies, fetch }, action, id, path, body) {
	const token = cookies.get(TOKEN_COOKIE);
	if (!token) return fail(401, { action, id, error: ERROR_KEYS[401] });
	try {
		await apiPatch(fetch, api(path), body, token);
		return { ok: true, action, id };
	} catch (err) {
		const status = Number.isInteger(err?.status) && err.status >= 400 && err.status <= 599 ? err.status : 500;
		return fail(status, { action, id, error: ERROR_KEYS[status] ?? 'orga.error.failed' });
	}
}

const id = (form, name) => Number(form.get(name));

export const actions = {
	score: async (event) => {
		const form = await event.request.formData();
		const game = id(form, 'game');
		const score1 = Number(form.get('score1'));
		const score2 = Number(form.get('score2'));
		if (!Number.isInteger(score1) || !Number.isInteger(score2) || score1 < 0 || score2 < 0) {
			return fail(400, { action: 'score', id: game, error: ERROR_KEYS[400] });
		}
		return patch(event, 'score', game, `/game/${game}/score/`, {
			score1,
			score2,
			is_played: form.get('is_played') === 'on'
		});
	},

	result: async (event) => {
		const form = await event.request.formData();
		const result = id(form, 'result');
		const raw = String(form.get('value') ?? '').trim();
		let body;
		if (form.get('kind') === 'TIM') {
			body = { time: raw === '' ? null : raw };
		} else {
			const points = raw === '' ? null : Number(raw);
			if (points !== null && (!Number.isInteger(points) || points < 0)) {
				return fail(400, { action: 'result', id: result, error: ERROR_KEYS[400] });
			}
			body = { points };
		}
		return patch(event, 'result', result, `/result/${result}/value/`, body);
	},

	reveal: async (event) => {
		const form = await event.request.formData();
		const discipline = id(form, 'discipline');
		return patch(event, 'reveal', discipline, `/discipline/${discipline}/reveal/`, {
			reveal_score: form.get('reveal_score') === 'true'
		});
	},

	close: async (event) => {
		const form = await event.request.formData();
		const round = id(form, 'round');
		return patch(event, 'close', round, `/round/${round}/close/`, {});
	}
};
```

Run the action tests → PASS.

- [ ] **Step 3: Page tests**

In `front/src/routes/[year=year]/disciplines/[id]/page.test.js`: add `vi` to the vitest import, `fireEvent` to the testing-library import, `summaryStaff` to the fixtures import, `disciplineEntries` to the `$lib/edition` import, and at the top `vi.mock('$app/forms', () => ({ enhance: () => ({ destroy() {} }) }));`. Extend `dataFor` to take an `editable` flag:

```js
const dataFor = (s, id, editable = false) => ({
	summary: s,
	discipline: findDiscipline(s, id),
	results: disciplineResults(s, id),
	schedule: disciplineSchedule(s, id),
	entries: disciplineEntries(s, id),
	editable
});
```

Append a describe:

```js
describe('discipline page for an organiser', () => {
	it('shows nothing of it to a visitor even with a staff payload', () => {
		renderWith(Page, { data: dataFor(summaryStaff, 11) });
		expect(screen.queryByText('Results hidden from the public')).toBeNull();
		expect(screen.queryByRole('button')).toBeNull();
	});

	it('offers to hide a revealed discipline, with no missing count', () => {
		renderWith(Page, { data: dataFor(summaryStaff, 10, true) }, 'en', true);
		expect(screen.getByText('Results are public')).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Hide' })).toBeInTheDocument();
		expect(screen.queryByText(/to play/)).toBeNull();
	});

	it('says how many games are unplayed on a hidden discipline with games', () => {
		const hidden = { ...summaryStaff, disciplines: summaryStaff.disciplines.map((d) => (d.id === 10 ? { ...d, reveal_score: false } : d)) };
		renderWith(Page, { data: dataFor(hidden, 10, true) }, 'en', true);
		expect(screen.getByText('Results hidden from the public')).toBeInTheDocument();
		expect(screen.getAllByText('1 to play').length).toBeGreaterThan(0);
	});

	it('shows result lines with the stored values for a discipline without rounds', () => {
		renderWith(Page, { data: dataFor(summaryStaff, 12, true) }, 'en', true);

		expect(screen.getByText('Results hidden from the public')).toBeInTheDocument();
		expect(screen.getByText('1 team without a result')).toBeInTheDocument();
		const lines = screen.getAllByTestId('result-line');
		expect(lines).toHaveLength(3);
		expect(lines[0]).toHaveTextContent('Aigles');
		expect(lines[0].querySelector('input[name="value"]')).toHaveValue(20);
		expect(lines[1].querySelector('input[name="value"]')).toHaveValue(null);
		expect(lines[0].querySelector('form')).toHaveAttribute('action', '?/result');
		expect(lines[0].querySelector('input[name="result"]')).toHaveValue('106');
		expect(lines[0].querySelector('input[name="kind"]')).toHaveValue('PTS');
		expect(screen.queryByTestId('result-row')).toBeNull();
	});

	it('shows a time field as mm:ss for a timed discipline', () => {
		const timed = { ...summaryStaff, rounds: summaryStaff.rounds.filter((r) => r.discipline !== 11), games: summaryStaff.games.filter((g) => g.discipline !== 11) };
		renderWith(Page, { data: dataFor(timed, 11, true) }, 'en', true);

		const lines = screen.getAllByTestId('result-line');
		expect(lines[0].querySelector('input[name="value"]')).toHaveValue('12:30');
		expect(lines[0].querySelector('input[name="value"]')).toHaveAttribute('placeholder', 'mm:ss');
		expect(lines[0].querySelector('input[name="value"]')).toHaveAttribute('pattern', '[0-9]{1,3}:[0-5][0-9]');
		expect(lines[0].querySelector('input[name="value"]')).not.toHaveAttribute('inputmode');
		expect(lines[0].querySelector('input[name="kind"]')).toHaveValue('TIM');
	});

	it('turns game rows into buttons that open the sheet', async () => {
		renderWith(Page, { data: dataFor(summaryStaff, 10, true) }, 'en', true);

		const row = screen.getAllByRole('button', { name: /Cerfs\s*— : —\s*Bisons/ })[0];
		expect(screen.queryByRole('dialog')).toBeNull();
		await fireEvent.click(row);
		expect(screen.getByRole('dialog', { name: 'Round 1 · ref: Aigles' })).toBeInTheDocument();
	});

	it('offers to close a complete Swiss round only', () => {
		renderWith(Page, { data: dataFor(summaryStaff, 11, true) }, 'en', true);
		// Orienteering is Swiss with one played game in round 1
		const close = screen.getByRole('button', { name: 'Close the round' });
		expect(close.closest('form').querySelector('input[name="round"]')).toHaveValue('22');

		const { container } = renderWith(Page, { data: dataFor(summaryStaff, 10, true) }, 'en', true);
		// Relay is round robin: never a close button, even on its complete round 2
		expect(container.querySelectorAll('form[action="?/close"]')).toHaveLength(0);
	});

	it('labels a closed round as done and hides its button', () => {
		const closed = { ...summaryStaff, rounds: summaryStaff.rounds.map((r) => (r.id === 22 ? { ...r, is_over: true } : r)) };
		renderWith(Page, { data: dataFor(closed, 11, true) }, 'en', true);
		expect(screen.queryByRole('button', { name: 'Close the round' })).toBeNull();
		expect(screen.getByRole('heading', { name: 'Round 1' }).parentElement).toHaveTextContent('Done');
	});

	it('shows the error line under the control the action names, also when form changes later', async () => {
		const { component } = renderWith(Page, { data: dataFor(summaryStaff, 12, true) }, 'en', true);
		expect(screen.queryByRole('alert')).toBeNull();

		// A failed action updates `form` without reloading `data`: the line must still appear.
		await component.$set({ form: { action: 'result', id: 107, error: 'orga.error.invalid' } });
		const lines = screen.getAllByTestId('result-line');
		expect(lines[1]).toHaveTextContent('Value refused');
		expect(lines[0]).not.toHaveTextContent('Value refused');
	});

	it('speaks French under fr', () => {
		renderWith(Page, { data: dataFor(summaryStaff, 12, true) }, 'fr', true);
		expect(screen.getByText('Résultats masqués pour le public')).toBeInTheDocument();
		expect(screen.getByText('1 équipe sans résultat')).toBeInTheDocument();
		expect(screen.getAllByRole('button', { name: 'Enregistrer' })).toHaveLength(3);
	});
});
```

Also, since `+page.js` now returns `entries`, add `entries: disciplineEntries(s, id)` to the existing `dataFor` (done above) and update `+page.js`:

```js
import { error } from '@sveltejs/kit';
import { disciplineEntries, disciplineResults, disciplineSchedule, findDiscipline } from '$lib/edition';

export const load = async ({ params, parent }) => {
	const { summary } = await parent();
	const discipline = findDiscipline(summary, Number(params.id));
	if (!discipline) error(404, 'Discipline not found');
	return {
		discipline,
		results: disciplineResults(summary, discipline.id),
		schedule: disciplineSchedule(summary, discipline.id),
		entries: disciplineEntries(summary, discipline.id)
	};
};
```

(`editable` comes from the year layout through `parent()` data merging; `data.editable` is available on the page without returning it here.)

Run: `docker compose exec -T front npx vitest run "src/routes/\[year=year\]/disciplines/\[id\]/page.test"` → the new describe FAILS.

- [ ] **Step 4: The page**

`front/src/routes/[year=year]/disciplines/[id]/+page.svelte` script becomes:

```svelte
<script>
	import { enhance } from '$app/forms';
	import { formatDifference, formatTime, roundCount } from '$lib/edition';
	import { iconFor } from '$lib/icons';
	import { disciplineName, useLocale, useT } from '$lib/i18n';
	import Breadcrumb from '$lib/components/Breadcrumb.svelte';
	import DisciplineRail from '$lib/components/DisciplineRail.svelte';
	import MedalRank from '$lib/components/MedalRank.svelte';
	import GameRow from '$lib/components/GameRow.svelte';
	import ScoreSheet from '$lib/components/ScoreSheet.svelte';
	import StaffBar from '$lib/components/StaffBar.svelte';

	export let data;
	/** The last action's result: {ok, action, id} or {action, id, error} (a fail). */
	export let form = null;

	const locale = useLocale();
	const t = useT();

	$: year = data.summary.edition.year;
	$: name = disciplineName(locale, data.discipline.name);
	$: rounds = (data.schedule ?? []).filter((round) => round.games.length > 0);
	// The difference is summed from game scores, so a discipline without rounds
	// has nothing but zeroes to show.
	$: showDifference = data.schedule !== null;

	// Organiser view: only on the latest edition, for a staff user (data.editable).
	$: editable = Boolean(data.editable);
	$: hasRounds = data.schedule !== null;
	$: isSwiss = data.discipline.pairing_system === 'SW';
	$: unplayed = (data.schedule ?? []).reduce((n, round) => n + roundCount(round).left, 0);
	$: withoutResult = data.entries.filter((e) => e.points === null && e.time === null).length;
	// Worded only while hidden: once public, what is missing shows as dashes in the list.
	$: missing = data.discipline.reveal_score
		? null
		: hasRounds
			? unplayed > 0
				? t('discipline.toPlay', { n: unplayed })
				: null
			: withoutResult > 0
				? t('orga.missingResults', { n: withoutResult })
				: null;
	// Reactive on purpose: a failed action updates `form` without reloading `data`.
	$: errorFor = (action, id) =>
		form && form.action === action && form.id === id && form.error ? form.error : null;

	/** The game whose sheet is open, or null; the row's button gets focus back on close. */
	let editing = null;
	let editingRound = 0;
	let opener = null;
	const openSheet = (game, roundOrder, event) => {
		opener = event?.currentTarget ?? null;
		editing = game;
		editingRound = roundOrder + 1;
	};
	const closeSheet = () => {
		editing = null;
		opener?.focus();
	};
</script>
```

Markup changes, in order:

1. Between the `h1` and the `.rail` div (the spec puts the bar under the title, above the rail), when editable:

```svelte
	{#if editable}
		<StaffBar
			disciplineId={data.discipline.id}
			revealed={data.discipline.reveal_score}
			{missing}
			error={errorFor('reveal', data.discipline.id)}
		/>
	{/if}
```

2. The results block becomes:

```svelte
	{#if editable && !hasRounds}
		<!-- The organiser's entry form replaces the list: one line per team, one form each. -->
		<div id="entries">
			{#each data.entries as entry}
				<form method="POST" action="?/result" class="result-line" data-testid="result-line" use:enhance>
					<input type="hidden" name="result" value={entry.id} />
					<input type="hidden" name="kind" value={data.discipline.result_type} />
					<MedalRank rank={entry.ranking} />
					<label class="name" for="entry-{entry.id}">{entry.teamName ?? t('team.unknown')}</label>
					{#if data.discipline.result_type === 'TIM'}
						<!-- A text keyboard: the numeric keypad has no colon. The pattern is a JS string
						     because Svelte would read `{1,3}` in a plain attribute as an expression. -->
						<input
							id="entry-{entry.id}"
							name="value"
							type="text"
							placeholder={t('orga.timeHint')}
							pattern={'[0-9]{1,3}:[0-5][0-9]'}
							value={formatTime(entry.time) ?? ''}
						/>
					{:else}
						<input
							id="entry-{entry.id}"
							name="value"
							type="number"
							inputmode="numeric"
							min="0"
							value={entry.points ?? ''}
						/>
					{/if}
					<button>{t('orga.save')}</button>
					{#if errorFor('result', entry.id)}
						<p class="error" role="alert">{t(errorFor('result', entry.id))}</p>
					{/if}
				</form>
			{/each}
		</div>
	{:else if data.results === null}
		<p class="not-revealed">{t('discipline.notRevealed')}</p>
	{:else}
		… (the existing `#results` list, with `{result.time}` replaced by `{formatTime(result.time)}`)
	{/if}
```

3. In the schedule, the round header and the rows become:

```svelte
			{#each rounds as round}
				{@const count = roundCount(round)}
				{@const closable = editable && isSwiss && !round.isOver && count.left === 0}
				<div class="round-header">
					<h3>{t('discipline.round', { n: round.order + 1 })}</h3>
					{#if editable && round.isOver}
						<span class="label done">{t('orga.roundClosed')}</span>
					{:else if closable}
						<form method="POST" action="?/close" use:enhance>
							<input type="hidden" name="round" value={round.id} />
							<button class="close">{t('orga.closeRound')}</button>
						</form>
					{:else}
						<span class="label" class:todo={count.left > 0}>
							{count.left > 0
								? t('discipline.toPlay', { n: count.left })
								: t('discipline.games', { n: count.total })}
						</span>
					{/if}
				</div>
				{#if errorFor('close', round.id)}
					<p class="error" role="alert">{t(errorFor('close', round.id))}</p>
				{/if}
				{#each round.games as game}
					<GameRow
						team1Name={game.team1Name}
						team2Name={game.team2Name}
						team1Href="/{year}/teams/{game.team1Id}"
						team2Href="/{year}/teams/{game.team2Id}"
						score1={game.score1}
						score2={game.score2}
						isPlayed={game.isPlayed}
						refereeName={game.refereeName}
						onEdit={editable ? (event) => openSheet(game, round.order, event) : null}
					/>
				{/each}
			{/each}
```

4. After the closing `</div>` of `.page`, when editable and a game is being edited:

```svelte
{#if editable && editing}
	<ScoreSheet
		game={editing}
		roundNumber={editingRound}
		open={true}
		error={errorFor('score', editing.id)}
		on:close={closeSheet}
	/>
{/if}
```

Styles to add:

```css
	#entries {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.result-line {
		display: grid;
		grid-template-columns: 44px minmax(0, 1fr) 6rem auto;
		align-items: center;
		gap: 12px;
		--medal-size: 1.9rem;
		margin: 0;
		padding: 10px 12px;
		background: var(--bg-raised);
		border-radius: var(--radius);
		border-left: 4px solid var(--line-strong);
	}

	.result-line input {
		min-height: 44px;
		width: 100%;
		background: var(--bg-sunken);
		border: 1px solid var(--line-strong);
		border-radius: var(--radius);
		color: var(--ink);
		font-family: var(--font-display);
		font-size: 1.3rem;
		text-align: right;
		padding: 0 0.6rem;
	}

	.result-line button,
	.close {
		min-height: 44px;
		padding: 0 1rem;
		border-radius: var(--radius);
		background: var(--accent);
		color: var(--bg);
		border: 1px solid var(--accent);
		font-family: var(--font-display);
		font-size: 1rem;
		letter-spacing: 0.1em;
		cursor: pointer;
	}

	.result-line .error {
		grid-column: 1 / -1;
	}

	.error {
		margin: 0.2rem 0 0;
		color: var(--loss);
		font-size: 0.85rem;
	}

	.round-header form {
		margin: 0;
	}

	.round-header .done {
		color: var(--win);
	}

	button:focus-visible,
	.result-line input:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}
```

In `front/src/routes/[year=year]/teams/[id]/+page.svelte`: import `formatTime` from `$lib/edition` and replace `{row.time}` with `{formatTime(row.time)}`; in its test, the French test's `11:48:00`-style value does not exist in the fixture, so only assert `summaryAllRevealed`-based renders if any use a time (`grep -n "00:" front/src/routes/\[year=year\]/teams/\[id\]/page.test.js`; update to `12:30`-style if present). Same in the discipline page's existing test `shows times for a revealed timed discipline` (`00:12:30` → `12:30`).

Run: `docker compose exec -T front npx vitest run "src/routes/\[year=year\]"` → PASS. `docker compose exec -T front npm test` → green. `docker compose exec -T front npm run build` → `✓ built`.

- [ ] **Step 5: Live check**

With the local staff user logged in (browser at `http://localhost:5173/login`), open the latest edition's disciplines: a hidden one shows the bar and the count; tap a game row, the sheet opens, step a score, save, the row updates and the sheet closes; on a discipline without rounds, enter a points value and save, the field keeps it after the reload; press Reveal, the bar flips and the ranking appears; log out via the pill, the page shows none of it. Report what was seen.

- [ ] **Step 6: Commit**

```bash
git add "front/src/routes/[year=year]/disciplines/[id]" "front/src/routes/[year=year]/teams/[id]/+page.svelte" "front/src/routes/[year=year]/teams/[id]/page.test.js" front/src/lib/edition.js front/src/lib/edition.test.js
git commit -m "[FEAT] discipline page: organiser bar, score sheet, result lines, close round through form actions

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Task 6: Docs, smoke, PR

**Files:**
- Modify: `CLAUDE.md`, `docs/superpowers/specs/2026-09-23-organiser-tools-design.md` (status, `/value/` path)

- [ ] **Step 1: CLAUDE.md**

In "## Backend architecture":
- The **API** paragraph: after "everything else returns 401 without a token.", add: "Four organiser writes (`PATCH /game/<id>/score/`, `/result/<id>/value/`, `/discipline/<id>/reveal/`, `/round/<id>/close/`) carry `@permission_classes([IsOrganiser])` from `permissions.py` (staff flag: 401 without a token, 403 for a player) and refuse with 409 any row outside `latest_edition()` (the active edition with the highest year, `models/Edition.py`). They go through the models' `save()`, so scoring recomputes league points and closing a round schedules the next Swiss one; a round closes only once every game is played. A result value is settable only on a discipline without rounds (game points are computed); a time is sent as `mm:ss` and stored as `00:mm:ss` (minutes above 59 roll into hours). The sheet overwrites a game's score: a game is scored either from the site or through game events (unused today, additive), never both."
- The **Summary endpoint** paragraph: after the `SummaryGameSerializer` sentence add: "With a staff token (`context["staff"]` from `request.user.is_staff`) the game scores and the stored `points`/`time` of every result stay visible before the reveal, so an organiser can check and edit them; `ranking`, `points_difference` and `global_points` stay null for staff too until the discipline is revealed. Discipline rows carry `pairing_system` (`NO`, `RR`, `SW`)."

In "## Frontend architecture":
- The **Auth** paragraph becomes: "Auth: the login form action posts to `/auth/token/` and stores the bare DRF token in the `token` cookie (httpOnly, SameSite strict, one week; `$lib/session.js` holds the name and options); `/logout` deletes it. The root `+layout.server.js` resolves `organiser` once per request by calling `/user/current/` with the token (`is_staff`; a 401/403 drops the cookie, an API failure keeps it and counts as a visitor), `+layout.svelte` puts it in context under `ORGANISER` (`useOrganiser()`, init only), and the `[year=year]` layout fetches the summary with the token for an organiser and returns `editable` (organiser on the latest year). `/login` stays out of the nav; the header shows an `ORGA` pill (a logout form) to an organiser."
- A new paragraph after it: "**Organiser tools** render only when `data.editable`, on the discipline page, through named form actions in `disciplines/[id]/+page.server.js` (`score`, `result`, `reveal`, `close`) that read the token cookie, call `apiPatch` and return `fail(status, {action, id, error})` with a dictionary key, or `{ok, action, id}`; `use:enhance` re-runs the loads on success so the page shows the new state. `StaffBar` (hidden/public, the missing count, reveal or hide), `ScoreSheet` (a bottom sheet under 1000px, a centred dialog above: steppers, the `played` switch on by default, cancel/save, closes on success), result lines for a discipline without rounds (`disciplineEntries`, points or `mm:ss` time, empty clears), `GameRow`'s `onEdit` turning the pairing into a button, and `Clore le tour` on a complete Swiss round. An anonymous visitor gets the page byte for byte as before. `formatTime` prints `mm:ss` with hours only when non-zero."
- The **Page tests** paragraph: `renderWith(Component, props, locale, organiser)`; the fourth argument opts into the organiser view; `summaryStaff` in the fixtures is the staff payload.

- [ ] **Step 2: Spec touch-ups**

In the spec: the result endpoint path is `PATCH /result/<id>/value/` (update the table and the front action description); status line to `implemented on branch claude/organiser-tools`.

- [ ] **Step 3: Everything green, then push and PR**

Run: `docker compose exec -T server python manage.py test` and `docker compose exec -T front npm test` and `npm run build` → all green. Repeat the Task 5 live check once in both languages at 375px and desktop.

```bash
git add CLAUDE.md docs/superpowers/specs/2026-09-23-organiser-tools-design.md
git commit -m "[DOCS] organiser tools: CLAUDE.md on the endpoints, the session and the page controls

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git push -u origin claude/organiser-tools
```

The controller opens the PR after the final review (body: summary, the runbook's time fix, "no migration").

---

## Self-review notes

- Spec coverage: permission and latest edition (T1), staff summary and `pairing_system` (T1), endpoints (T2), session and `editable` (T3), pill and logout (T3), dictionary (T3/T4), helpers and fixtures (T4), `GameRow.onEdit`, `ScoreSheet`, `StaffBar` (T4), page and actions (T5), `formatTime` on the team page (T5), docs and runbook (T6, runbook lives in the spec).
- Deviation from the spec: the result endpoint is `PATCH /result/<id>/value/` because `PATCH /result/<id>/` would share a path with the `GET` view; noted in T2 and T6.
- Names used across tasks: `IsOrganiser`, `latest_edition`, `setGameScore`, `setTeamResult`, `setDisciplineReveal`, `closeRound`, `GameScoreSerializer`, `ResultValueSerializer`, `RevealSerializer`; `ORGANISER`, `TOKEN_COOKIE`, `tokenCookieOptions`, `useOrganiser`, `apiPatch`, `renderWith(..., organiser)`, `formatTime`, `disciplineEntries`, `summaryStaff`, `GameRow.onEdit`, `ScoreSheet` (`game`, `roundNumber`, `open`, `error`, `close` event), `StaffBar` (`disciplineId`, `revealed`, `missing`, `error`), actions `score`/`result`/`reveal`/`close`, form fields `game`, `score1`, `score2`, `is_played`, `result`, `kind`, `value`, `discipline`, `reveal_score`, `round`.
