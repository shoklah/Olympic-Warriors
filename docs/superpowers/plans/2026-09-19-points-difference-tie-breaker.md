# Points Difference Tie-Breaker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rank teams with equal league points in a discipline by their points difference, expose that difference on the API, and show it on the discipline ranking page.

**Architecture:** The difference is never stored. A helper in `server/olympic_warriors/models/Team.py` annotates `TeamResult` querysets with `points_difference` summed from the discipline's active `Game` rows via two subqueries. `TeamResult.ranking` uses the annotation as a secondary sort key; the serializer and the front read the new property. Spec: `docs/superpowers/specs/2026-09-19-points-difference-tie-breaker-design.md`.

**Tech Stack:** Django 4.2 ORM (`Subquery`, `OuterRef`, `Coalesce`), Django REST Framework serializers, SvelteKit 2 / Svelte 4 (plain JS).

---

## How to run things

Everything runs inside the root compose stack, which is already up and mounts `./server` into the `server` container, so edits are picked up without a rebuild.

```bash
docker compose exec server python manage.py test olympic_warriors.tests.test_ranking
docker compose exec server python manage.py test          # whole suite, needs Postgres
```

Tests are plain `django.test.TestCase`, run with the Django runner (not pytest). `Game.objects.create(...)` calls `Game.save()`, which rolls league points into `TeamResult.points` (3 win / 1 draw / 0 loss); a `Game` needs a `TeamSportRound` and a `referees` team, neither of which is validated, so any team will do as referee in tests.

`TeamResult` is defined in `server/olympic_warriors/models/Team.py` (not a `TeamResult.py`), and `Game` lives in `server/olympic_warriors/models/Discipline.py`, which imports `Team.py`. That is why the helper below fetches `Game` with `apps.get_model` instead of importing it.

## File structure

- Modify `server/olympic_warriors/models/Team.py`: add `annotate_points_difference()` helper, `TeamResult.points_difference` property, tie-break in `TeamResult.ranking`.
- Modify `server/olympic_warriors/serializer.py`: expose `points_difference` on `TeamResultSerializer`.
- Create `server/olympic_warriors/tests/test_ranking.py`: all backend tests for this feature.
- Modify `front/src/routes/disciplines/[slug]/ranking/+page.server.js`: sort results by rank.
- Modify `front/src/routes/disciplines/[slug]/ranking/+page.svelte`: show the signed difference.
- Modify `CLAUDE.md`: one sentence on the tie-breaker in the domain paragraph.

---

### Task 1: `points_difference` on `TeamResult`

**Files:**
- Modify: `server/olympic_warriors/models/Team.py` (imports at top, `TeamResult` class)
- Create: `server/olympic_warriors/tests/test_ranking.py`

- [ ] **Step 1: Write the failing tests for the difference**

Create `server/olympic_warriors/tests/test_ranking.py`:

```python
"""
Tests for discipline rankings and the points difference tie-breaker.
"""

from django.test import TestCase

from olympic_warriors.models import (
    Edition,
    Team,
    TeamResult,
    TeamSportRound,
    Game,
    Darts,
    GeneralCultureQuizz,
)
from olympic_warriors.serializer import TeamResultSerializer


class RankingTestSetup(TestCase):
    """
    One edition with four teams and a Darts discipline without a pairing system, so no
    game is scheduled automatically and each test creates exactly the games it needs.
    """

    def setUp(self):
        self.edition = Edition.objects.create(
            year=2026,
            host="Paris",
            start_date="2026-09-19",
            end_date="2026-09-20",
        )
        self.team_a = Team.objects.create(name="A", edition=self.edition)
        self.team_b = Team.objects.create(name="B", edition=self.edition)
        self.team_c = Team.objects.create(name="C", edition=self.edition)
        self.team_d = Team.objects.create(name="D", edition=self.edition)
        self.darts = Darts.objects.create(edition=self.edition, reveal_score=True)
        self.round = TeamSportRound.objects.create(discipline=self.darts, order=0)

    def play(self, team1, score1, team2, score2):
        """
        Create a finished game; Game.save() rolls the league points into TeamResult.
        """
        return Game.objects.create(
            discipline=self.darts,
            round=self.round,
            team1=team1,
            score1=score1,
            team2=team2,
            score2=score2,
            referees=self.team_d,
            edition=self.edition,
        )

    def result(self, team):
        return TeamResult.objects.get(team=team, discipline=self.darts)


class TestPointsDifference(RankingTestSetup):
    """points_difference is summed from the discipline's active games."""

    def test_sums_games_as_team1_and_as_team2(self):
        self.play(self.team_a, 5, self.team_b, 2)  # A +3, B -3
        self.play(self.team_d, 2, self.team_a, 3)  # A +1, D -1

        self.assertEqual(self.result(self.team_a).points_difference, 4)
        self.assertEqual(self.result(self.team_b).points_difference, -3)
        self.assertEqual(self.result(self.team_d).points_difference, -1)

    def test_is_zero_without_games(self):
        self.assertEqual(self.result(self.team_c).points_difference, 0)

    def test_ignores_inactive_games(self):
        game = self.play(self.team_a, 5, self.team_b, 2)
        game.is_active = False
        game.save()

        self.assertEqual(self.result(self.team_a).points_difference, 0)
        self.assertEqual(self.result(self.team_b).points_difference, 0)

    def test_ignores_games_of_other_disciplines(self):
        other = Darts.objects.create(edition=self.edition, reveal_score=True)
        other_round = TeamSportRound.objects.create(discipline=other, order=0)
        Game.objects.create(
            discipline=other,
            round=other_round,
            team1=self.team_a,
            score1=9,
            team2=self.team_b,
            score2=0,
            referees=self.team_d,
            edition=self.edition,
        )

        self.assertEqual(self.result(self.team_a).points_difference, 0)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
docker compose exec server python manage.py test olympic_warriors.tests.test_ranking
```
Expected: 4 errors with `AttributeError: 'TeamResult' object has no attribute 'points_difference'`.

- [ ] **Step 3: Add the helper and the property**

In `server/olympic_warriors/models/Team.py`, replace the imports at the top of the file:

```python
from django.apps import apps
from django.db import models
from django.db.models import F, OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce

from .Edition import Edition
from .ResultTypes import ResultTypes
```

Then add this function between the imports and `class TeamResult`:

```python
def annotate_points_difference(queryset):
    """
    Annotate a TeamResult queryset with `points_difference`: over the active games of the
    result's discipline, the sum of the team's score minus its opponent's score. Teams
    without any game get 0.

    Game is fetched from the app registry because Discipline.py imports this module.
    """
    Game = apps.get_model("olympic_warriors", "Game")

    def score_gap(team_field, own_score, other_score):
        games = Game.objects.filter(
            discipline_id=OuterRef("discipline_id"),
            is_active=True,
            **{team_field: OuterRef("team_id")},
        )
        total = (
            games.order_by()
            .values(team_field)
            .annotate(gap=Sum(F(own_score) - F(other_score)))
            .values("gap")[:1]
        )
        return Coalesce(Subquery(total, output_field=models.IntegerField()), 0)

    return queryset.annotate(
        points_difference=score_gap("team1", "score1", "score2")
        + score_gap("team2", "score2", "score1")
    )
```

And add this property to `TeamResult`, right after the `result_type` property:

```python
    @property
    def points_difference(self) -> int:
        """
        Sum of the team's score minus its opponent's score over the active games of the
        discipline. 0 when the team has no game.
        """
        difference = (
            annotate_points_difference(TeamResult.objects.filter(pk=self.pk))
            .values_list("points_difference", flat=True)
            .first()
        )
        return difference or 0
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:
```bash
docker compose exec server python manage.py test olympic_warriors.tests.test_ranking
```
Expected: `Ran 4 tests ... OK`.

If Django complains about mixed types in the `+` expression, wrap the sum: `ExpressionWrapper(score_gap(...) + score_gap(...), output_field=models.IntegerField())` (import `ExpressionWrapper` from `django.db.models`).

- [ ] **Step 5: Commit**

```bash
git add server/olympic_warriors/models/Team.py server/olympic_warriors/tests/test_ranking.py
git commit -m "[FEAT] derive TeamResult.points_difference from active games

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: tie-break `TeamResult.ranking` on points difference

**Files:**
- Modify: `server/olympic_warriors/models/Team.py` (`TeamResult.ranking`)
- Modify: `server/olympic_warriors/tests/test_ranking.py`

- [ ] **Step 1: Write the failing ranking tests**

Append to `server/olympic_warriors/tests/test_ranking.py`:

```python
class TestRankingTieBreaker(RankingTestSetup):
    """Equal league points are split by points difference; equal difference shares a rank."""

    def test_equal_points_are_ranked_by_difference(self):
        self.play(self.team_a, 5, self.team_b, 2)  # A 3 pts (+3), B 0 pts (-3)
        self.play(self.team_c, 1, self.team_d, 0)  # C 3 pts (+1), D 0 pts (-1)

        self.assertEqual(self.result(self.team_a).ranking, 1)
        self.assertEqual(self.result(self.team_c).ranking, 2)
        self.assertEqual(self.result(self.team_d).ranking, 3)
        self.assertEqual(self.result(self.team_b).ranking, 4)

    def test_more_points_beat_better_difference(self):
        self.play(self.team_a, 1, self.team_b, 0)  # A 3 pts (+1)
        self.play(self.team_c, 9, self.team_d, 9)  # C 1 pt (0), D 1 pt (0)

        self.assertEqual(self.result(self.team_a).ranking, 1)
        self.assertEqual(self.result(self.team_c).ranking, 2)
        self.assertEqual(self.result(self.team_d).ranking, 2)
        self.assertEqual(self.result(self.team_b).ranking, 4)

    def test_equal_points_and_difference_share_rank(self):
        self.play(self.team_a, 3, self.team_b, 1)  # A 3 pts (+2), B 0 pts (-2)
        self.play(self.team_c, 3, self.team_d, 1)  # C 3 pts (+2), D 0 pts (-2)

        self.assertEqual(self.result(self.team_a).ranking, 1)
        self.assertEqual(self.result(self.team_c).ranking, 1)
        self.assertEqual(self.result(self.team_b).ranking, 3)
        self.assertEqual(self.result(self.team_d).ranking, 3)

    def test_hidden_scores_rank_zero(self):
        self.darts.reveal_score = False
        self.darts.save()
        self.play(self.team_a, 5, self.team_b, 2)

        self.assertEqual(self.result(self.team_a).ranking, 0)

    def test_discipline_without_games_ranks_on_points_only(self):
        quizz = GeneralCultureQuizz.objects.create(edition=self.edition, reveal_score=True)
        points = {self.team_a: 10, self.team_b: 5, self.team_c: 5, self.team_d: 0}
        for team, value in points.items():
            TeamResult.objects.filter(team=team, discipline=quizz).update(points=value)

        def rank(team):
            return TeamResult.objects.get(team=team, discipline=quizz).ranking

        self.assertEqual(rank(self.team_a), 1)
        self.assertEqual(rank(self.team_b), 2)
        self.assertEqual(rank(self.team_c), 2)
        self.assertEqual(rank(self.team_d), 4)
        self.assertEqual(
            TeamResult.objects.get(team=self.team_b, discipline=quizz).points_difference, 0
        )
```

- [ ] **Step 2: Run the tests to verify the tie-break ones fail**

Run:
```bash
docker compose exec server python manage.py test olympic_warriors.tests.test_ranking
```
Expected: `test_equal_points_are_ranked_by_difference` fails (`2 != 1` for team C, since A and C currently share rank 1) and `test_more_points_beat_better_difference` fails on team B (`3 != 4`). The other three pass already.

- [ ] **Step 3: Use the difference as a secondary key in `ranking`**

In `server/olympic_warriors/models/Team.py`, replace the `POINTS` branch of `TeamResult.ranking`:

```python
        elif self.discipline.result_type == ResultTypes.POINTS:
            results = annotate_points_difference(
                TeamResult.objects.filter(discipline=self.discipline, is_active=True)
            )
            ahead = results.filter(
                Q(points__gt=self.points)
                | Q(points=self.points, points_difference__gt=self.points_difference)
            )
            return ahead.count() + 1
```

Also update the property docstring so it reads:

```python
        """
        Get the ranking of the team in the discipline. Points disciplines break ties on
        points difference; teams still tied share a rank.

        @return: ranking of the team in the discipline
        """
```

- [ ] **Step 4: Run the whole ranking module and the discipline tests**

Run:
```bash
docker compose exec server python manage.py test olympic_warriors.tests.test_ranking olympic_warriors.tests.test_disciplines
```
Expected: `Ran 17 tests ... OK`.

- [ ] **Step 5: Commit**

```bash
git add server/olympic_warriors/models/Team.py server/olympic_warriors/tests/test_ranking.py
git commit -m "[FEAT] break equal-points ties on points difference in discipline ranking

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: expose `points_difference` on the API

**Files:**
- Modify: `server/olympic_warriors/serializer.py` (`TeamResultSerializer`, around line 165)
- Modify: `server/olympic_warriors/tests/test_ranking.py`

- [ ] **Step 1: Write the failing serializer test**

Append to `server/olympic_warriors/tests/test_ranking.py`:

```python
class TestTeamResultSerializer(RankingTestSetup):
    """The API exposes the difference next to ranking and global_points."""

    def test_serializes_points_difference(self):
        self.play(self.team_a, 5, self.team_b, 2)

        data = TeamResultSerializer(self.result(self.team_a)).data

        self.assertEqual(data["points_difference"], 3)
        self.assertEqual(data["ranking"], 1)
```

- [ ] **Step 2: Run it to verify it fails**

Run:
```bash
docker compose exec server python manage.py test olympic_warriors.tests.test_ranking.TestTeamResultSerializer
```
Expected: FAIL with `KeyError: 'points_difference'`.

- [ ] **Step 3: Add the read-only field**

In `server/olympic_warriors/serializer.py`, change `TeamResultSerializer` to:

```python
class TeamResultSerializer(serializers.ModelSerializer):
    ranking = serializers.ReadOnlyField()
    global_points = serializers.ReadOnlyField()
    points_difference = serializers.ReadOnlyField()
    team_name = serializers.CharField(source="team.name")

    class Meta:
        model = TeamResult
        fields = "__all__"
```

- [ ] **Step 4: Run the full suite**

Run:
```bash
docker compose exec server python manage.py test
```
Expected: all tests pass (`OK`). If an unrelated pre-existing failure shows up, note it in the commit message body rather than fixing it here.

- [ ] **Step 5: Commit**

```bash
git add server/olympic_warriors/serializer.py server/olympic_warriors/tests/test_ranking.py
git commit -m "[FEAT] expose points_difference on team results

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: show the difference on the discipline ranking page

The front has no test tooling, so this task is verified in the browser. Route: `http://localhost:5173/disciplines/<id>/ranking` after logging in at `/login`; the discipline id is the numeric primary key visible in the Django admin at `http://localhost:3003/admin/`.

**Files:**
- Modify: `front/src/routes/disciplines/[slug]/ranking/+page.server.js`
- Modify: `front/src/routes/disciplines/[slug]/ranking/+page.svelte`

- [ ] **Step 1: Sort the results by rank in the loader**

In `+page.server.js`, right after the `enrichedResults` array is built and before the `return`, add:

```javascript
        // Show the list in rank order; tied teams keep the API order.
        enrichedResults.sort((a, b) => a.ranking - b.ranking);
```

- [ ] **Step 2: Show the signed difference on the page**

In `+page.svelte`, replace the `<script>` block with:

```svelte
<script>
    export let data;
    let results = data.results;
    let discipline = data.discipline;

    const formatDifference = (difference) =>
        difference > 0 ? `+${difference}` : `${difference}`;
</script>
```

and replace the points line inside the `{:else}` branch:

```svelte
                {:else}
                    <p>{result.points} pts ({formatDifference(result.points_difference)})</p>
                {/if}
```

- [ ] **Step 3: Verify in the browser**

Pick a points discipline with games in the running stack (or set two scores in the Django admin on a Darts/Rugby game). Open its ranking page and check:
- cards are listed 1, 2, 3, ... top to bottom;
- each points card reads like `3 pts (+3)`, `0 pts (-3)`, or `0 pts (0)` for a team without games;
- a time discipline (Relay) still shows only the time.

If the front container does not pick up the change, check its logs with `docker compose logs front --tail 20`.

- [ ] **Step 4: Commit**

```bash
git add "front/src/routes/disciplines/[slug]/ranking/+page.server.js" "front/src/routes/disciplines/[slug]/ranking/+page.svelte"
git commit -m "[FEAT] show points difference and sort discipline ranking by rank

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: document the tie-breaker

**Files:**
- Modify: `CLAUDE.md` (the "Domain:" paragraph under "Backend architecture")

- [ ] **Step 1: Update the domain paragraph**

In `CLAUDE.md`, find the sentence:

```
Rankings are computed properties on `TeamResult` and `Team`, gated by `Discipline.reveal_score`; `Discipline.get_ranking()` is a dead stub.
```

and replace it with:

```
Rankings are computed properties on `TeamResult` and `Team`, gated by `Discipline.reveal_score`; points disciplines break ties on `TeamResult.points_difference`, which is summed on the fly from active `Game` scores by `annotate_points_difference()` in `models/Team.py` (never stored, so it cannot desync). `Discipline.get_ranking()` is a dead stub.
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "[DOC] describe the points difference tie-breaker

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
