# Edition-aware Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show one edition at a time in the SvelteKit front, selected by a year in the URL, fed by a single public summary endpoint, with real error handling and test tooling.

**Architecture:** The Django API gains `GET /edition/year/<year>/summary/` (public, score fields nulled for unrevealed disciplines) plus `photos_url` and a unique `year` on `Edition`. The front moves every edition page under a `[year=year]` route whose layout fetches the summary once; pages derive their rows through pure helpers in `$lib/edition.js`; `/` renders the latest edition's hub with the same component as `/<year>`. Vitest and Testing Library cover the helpers and the page components.

**Tech Stack:** Django 4.2 + DRF 3.15 (backend), SvelteKit 2 / Svelte 4 plain JS (front), Vitest 2 + jsdom + @testing-library/svelte 5 (front tests), Docker Compose for the Postgres-backed Django tests.

**Spec:** `docs/superpowers/specs/2026-09-22-edition-aware-frontend-design.md`

---

## Working environment

All work happens in the worktree `/Users/shoklah/Work/Playground/Olympic-Warriors/.claude/worktrees/edition-aware-front` on branch `claude/edition-aware-front`. Never `git checkout` in the main checkout; other sessions use it.

Set these once per shell:

```bash
WT=/Users/shoklah/Work/Playground/Olympic-Warriors/.claude/worktrees/edition-aware-front
MAIN=/Users/shoklah/Work/Playground/Olympic-Warriors
```

**Backend tests** run inside the main compose stack's server image with the worktree's `server/` mounted over `/server` (tests use their own `test_` database, the running stack is untouched). One-time prep:

```bash
cp $MAIN/server/dev.env $WT/server/dev.env && mkdir -p $WT/server/logs
```

Then, for any Django command:

```bash
docker compose --project-directory $MAIN run --rm --no-deps -T -v "$WT/server:/server" server python manage.py test olympic_warriors.tests.test_summary -v 2
```

**Front commands** run natively in `$WT/front` with Node 22 (`node --version` shows v22). `$env/static/private` needs `API_URL` at build time, so create the gitignored env file once:

```bash
printf 'API_URL=http://localhost:3003\n' > $WT/front/.env
```

Commit messages follow the repo style: `[FEAT]`, `[FIX]`, `[TEST]`, `[DOCS]`, `[CHORE]` prefix, and end with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

---

## File structure

**Backend (`server/olympic_warriors/`)**

| File | Change | Responsibility |
|---|---|---|
| `models/Edition.py` | modify | `year` unique, new `photos_url` |
| `migrations/0027_edition_photos_url_unique_year.py` | create | schema change |
| `serializer.py` | modify | five `Summary*` serializers and `EditionSummarySerializer` |
| `views.py` | modify | `getEditionSummary`, fix `getTeamResultsByEdition` |
| `urls.py` | modify | route the summary |
| `tests/test_summary.py` | create | endpoint, model and regression tests |

**Front (`front/`)**

| File | Change | Responsibility |
|---|---|---|
| `package.json`, `vite.config.js`, `src/setupTests.js` | modify/create | Vitest + Testing Library |
| `src/lib/api.js` | create | `apiGet`/`apiPost`, throw SvelteKit errors |
| `src/lib/server/urls.js` | create | `api(path)` prefixes `API_URL` |
| `src/lib/edition.js` | create | pure derivations from a summary |
| `src/lib/icons.js` | create | discipline name to icon URL, with fallback |
| `src/lib/img/icons/darts.svg`, `default.svg` | create | missing icons |
| `src/lib/fixtures/summary.js` | create | test fixture |
| `src/lib/components/EditionHub.svelte` | create | shared hub |
| `src/params/year.js` | create | four-digit matcher |
| `src/routes/+layout.server.js` | rewrite | editions list, latest year |
| `src/routes/+layout.svelte` | modify | theme keyed on hub routes |
| `src/routes/+error.svelte` | create | themed error page |
| `src/routes/+page.server.js`, `+page.svelte` | create/rewrite | home hub |
| `src/routes/Header.svelte`, `menu.svelte` | rewrite | year switcher, edition nav |
| `src/routes/[year=year]/+layout.server.js` | create | summary fetch |
| `src/routes/[year=year]/+page.svelte` | create | year hub |
| `src/routes/[year=year]/ranking/+page.svelte` | create | global ranking |
| `src/routes/[year=year]/disciplines/+page.svelte` | create | discipline cards |
| `src/routes/[year=year]/disciplines/[id]/+page.js`, `+page.svelte` | create | discipline ranking |
| `src/routes/[year=year]/teams/+page.svelte` | create | teams grid |
| `src/routes/[year=year]/teams/[id]/+page.js`, `+page.svelte` | create | team page |
| `src/routes/ranking/+page.server.js`, `teams/+page.server.js`, `disciplines/+page.server.js` | rewrite | 301 redirects |
| `src/routes/login/+page.server.js`, `+page.svelte` | modify | `apiPost`, no register toggle |
| `src/lib/utils.js`, `src/hooks.server.js`, `src/routes/Footer.svelte`, `src/routes/profile/`, `src/routes/action/`, `src/routes/photos/`, `src/routes/disciplines/[slug]/`, `src/routes/teams/[slug]/`, `src/routes/ranking/+page.svelte`, `src/routes/teams/+page.svelte`, `src/routes/disciplines/+page.svelte`, `src/routes/login/register.svelte` | delete | dead or replaced |

**Repo**

| File | Change |
|---|---|
| `.github/workflows/test.yml` | add `front` job |
| `CLAUDE.md` | update commands, API and front sections |

---

## Task 1: Edition model — unique year and `photos_url`

**Files:**
- Modify: `server/olympic_warriors/models/Edition.py:24-29`
- Create: `server/olympic_warriors/migrations/0027_edition_photos_url_unique_year.py`
- Create: `server/olympic_warriors/tests/test_summary.py`

- [ ] **Step 1: Write the failing tests**

Create `server/olympic_warriors/tests/test_summary.py`:

```python
"""
Tests for the Edition model changes and the public edition summary endpoint.
"""

from django.db import IntegrityError, transaction
from django.test import TestCase

from olympic_warriors.models import Edition


class TestEditionModel(TestCase):
    """year is unique and photos_url is optional."""

    def test_year_is_unique(self):
        Edition.objects.create(year=2026, host="Paris", start_date="2026-09-19", end_date="2026-09-20")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Edition.objects.create(
                    year=2026, host="Lyon", start_date="2026-10-01", end_date="2026-10-02"
                )

    def test_photos_url_defaults_to_none(self):
        edition = Edition.objects.create(
            year=2026, host="Paris", start_date="2026-09-19", end_date="2026-09-20"
        )
        self.assertIsNone(edition.photos_url)

    def test_photos_url_is_stored(self):
        edition = Edition.objects.create(
            year=2026,
            host="Paris",
            start_date="2026-09-19",
            end_date="2026-09-20",
            photos_url="https://drive.example.com/ow-2026",
        )
        edition.refresh_from_db()
        self.assertEqual(edition.photos_url, "https://drive.example.com/ow-2026")
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
docker compose --project-directory $MAIN run --rm --no-deps -T -v "$WT/server:/server" server python manage.py test olympic_warriors.tests.test_summary -v 2
```

Expected: `test_photos_url_defaults_to_none` and `test_photos_url_is_stored` fail with `TypeError: Edition() got unexpected keyword arguments: 'photos_url'` / `AttributeError`, `test_year_is_unique` fails with `AssertionError: IntegrityError not raised`.

- [ ] **Step 3: Change the model**

In `server/olympic_warriors/models/Edition.py`, replace the `year` line and add `photos_url` after `registration_form`:

```python
    year = models.IntegerField(
        unique=True, validators=[MinValueValidator(2020), MaxValueValidator(2030)]
    )
    host = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    registration_form = models.FileField(upload_to="registration_forms/", null=True, blank=True)
    photos_url = models.URLField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
```

- [ ] **Step 4: Generate the migration**

```bash
docker compose --project-directory $MAIN run --rm --no-deps -T -v "$WT/server:/server" server python manage.py makemigrations olympic_warriors -n edition_photos_url_unique_year
```

Expected: `Migrations for 'olympic_warriors': olympic_warriors/migrations/0027_edition_photos_url_unique_year.py` with two operations: `AddField photos_url` and `AlterField year`. Open the file and confirm it depends on `0026_darts` and reads:

```python
from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('olympic_warriors', '0026_darts'),
    ]

    operations = [
        migrations.AddField(
            model_name='edition',
            name='photos_url',
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='edition',
            name='year',
            field=models.IntegerField(unique=True, validators=[django.core.validators.MinValueValidator(2020), django.core.validators.MaxValueValidator(2030)]),
        ),
    ]
```

If the container created the file as root, fix ownership: `sudo chown $(id -u) $WT/server/olympic_warriors/migrations/0027_*.py` (only if `ls -l` shows root).

- [ ] **Step 5: Run the tests to verify they pass**

```bash
docker compose --project-directory $MAIN run --rm --no-deps -T -v "$WT/server:/server" server python manage.py test olympic_warriors.tests.test_summary -v 2
```

Expected: `Ran 3 tests ... OK`.

- [ ] **Step 6: Run the whole backend suite**

```bash
docker compose --project-directory $MAIN run --rm --no-deps -T -v "$WT/server:/server" server python manage.py test
```

Expected: `OK`. Every existing test creates one edition per year, so the unique constraint does not break them.

- [ ] **Step 7: Commit**

```bash
cd $WT && git add server/olympic_warriors/models/Edition.py server/olympic_warriors/migrations/0027_edition_photos_url_unique_year.py server/olympic_warriors/tests/test_summary.py
git commit -m "[FEAT] edition: unique year and optional photos_url

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Task 2: Fix `getTeamResultsByEdition`

**Files:**
- Modify: `server/olympic_warriors/views.py:775-778`
- Modify: `server/olympic_warriors/tests/test_summary.py`

- [ ] **Step 1: Write the failing test**

Append to `server/olympic_warriors/tests/test_summary.py`:

```python
from django.contrib.auth.models import User
from rest_framework.test import APIClient, APITestCase

from olympic_warriors.models import Relay, Team


class TestTeamResultsByEdition(APITestCase):
    """The by-edition results view filters through the discipline's edition."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create(username="orga", password="x")
        self.client.force_authenticate(user=self.user)
        self.edition = Edition.objects.create(
            year=2026, host="Paris", start_date="2026-09-19", end_date="2026-09-20"
        )
        self.other = Edition.objects.create(
            year=2025, host="Lyon", start_date="2025-09-20", end_date="2025-09-21"
        )
        Team.objects.create(name="A", edition=self.edition)
        Team.objects.create(name="Z", edition=self.other)
        Relay.objects.create(edition=self.edition)  # one result for A
        Relay.objects.create(edition=self.other)  # one result for Z

    def test_returns_only_that_editions_results(self):
        response = self.client.get(f"/results/edition/{self.edition.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([r["team_name"] for r in response.data], ["A"])
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
docker compose --project-directory $MAIN run --rm --no-deps -T -v "$WT/server:/server" server python manage.py test olympic_warriors.tests.test_summary.TestTeamResultsByEdition -v 2
```

Expected: FAIL with `FieldError: Cannot resolve keyword 'edition' into field`.

- [ ] **Step 3: Fix the filter**

In `server/olympic_warriors/views.py`, in `getTeamResultsByEdition`:

```python
def getTeamResultsByEdition(request, edition_id):
    team_results = TeamResult.objects.filter(discipline__edition=edition_id, is_active=True)
    serializer = TeamResultSerializer(team_results, many=True)
    return Response(serializer.data)
```

- [ ] **Step 4: Run the test to verify it passes**

Same command as step 2. Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
cd $WT && git add server/olympic_warriors/views.py server/olympic_warriors/tests/test_summary.py
git commit -m "[FIX] results by edition: filter through the discipline's edition

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Task 3: Summary serializers

**Files:**
- Modify: `server/olympic_warriors/serializer.py` (append)
- Modify: `server/olympic_warriors/tests/test_summary.py`

- [ ] **Step 1: Write the failing tests**

Append to `server/olympic_warriors/tests/test_summary.py`:

```python
from olympic_warriors.models import Orienteering, Player, TeamResult
from olympic_warriors.serializer import EditionSummarySerializer


class SummarySetup(TestCase):
    """
    One 2026 edition with three teams, a revealed Relay (points 10/5/0) and a hidden
    Orienteering, plus a 2025 edition that must never leak into the 2026 summary.
    """

    def setUp(self):
        self.edition = Edition.objects.create(
            year=2026,
            host="Paris",
            start_date="2026-09-19",
            end_date="2026-09-20",
            photos_url="https://drive.example.com/ow-2026",
        )
        self.other = Edition.objects.create(
            year=2025, host="Lyon", start_date="2025-09-20", end_date="2025-09-21"
        )
        self.team_a = Team.objects.create(name="Aigles", edition=self.edition)
        self.team_b = Team.objects.create(name="Bisons", edition=self.edition)
        self.team_c = Team.objects.create(name="Cerfs", edition=self.edition)
        self.team_z = Team.objects.create(name="Zèbres", edition=self.other)

        ana = User.objects.create(username="ana", first_name="Ana", last_name="Lopez")
        bob = User.objects.create(username="bob", first_name="Bob", last_name="Martin")
        old = User.objects.create(username="old", first_name="Old", last_name="Timer")
        Player.objects.create(user=ana, edition=self.edition, rating=5, team=self.team_a)
        Player.objects.create(user=bob, edition=self.edition, rating=5, team=self.team_a)
        Player.objects.create(
            user=old, edition=self.edition, rating=5, team=self.team_a, is_active=False
        )

        self.relay = Relay.objects.create(edition=self.edition, reveal_score=True)
        TeamResult.objects.filter(discipline=self.relay, team=self.team_a).update(points=5)
        TeamResult.objects.filter(discipline=self.relay, team=self.team_b).update(points=10)
        TeamResult.objects.filter(discipline=self.relay, team=self.team_c).update(points=0)
        self.orienteering = Orienteering.objects.create(edition=self.edition, reveal_score=False)
        Relay.objects.create(edition=self.other, reveal_score=True)

    def summary(self):
        return EditionSummarySerializer(self.edition).data


class TestEditionSummarySerializer(SummarySetup):

    def test_edition_fields(self):
        edition = self.summary()["edition"]
        self.assertEqual(
            edition,
            {
                "id": self.edition.id,
                "year": 2026,
                "host": "Paris",
                "start_date": "2026-09-19",
                "end_date": "2026-09-20",
                "photos_url": "https://drive.example.com/ow-2026",
            },
        )

    def test_disciplines_of_this_edition_in_id_order(self):
        disciplines = self.summary()["disciplines"]
        self.assertEqual(
            disciplines,
            [
                {"id": self.relay.id, "name": "Relay", "result_type": "PTS", "reveal_score": True},
                {
                    "id": self.orienteering.id,
                    "name": "Orienteering",
                    "result_type": "TIM",
                    "reveal_score": False,
                },
            ],
        )

    def test_inactive_discipline_excluded(self):
        self.orienteering.is_active = False
        self.orienteering.save()
        self.assertEqual([d["name"] for d in self.summary()["disciplines"]], ["Relay"])

    def test_teams_in_name_order_with_active_roster(self):
        teams = self.summary()["teams"]
        self.assertEqual([t["name"] for t in teams], ["Aigles", "Bisons", "Cerfs"])
        aigles = teams[0]
        self.assertEqual(aigles["ranking"], 2)
        self.assertEqual(aigles["total_points"], 3)
        self.assertEqual(
            [(p["first_name"], p["last_name"]) for p in aigles["players"]],
            [("Ana", "Lopez"), ("Bob", "Martin")],
        )
        self.assertEqual(teams[1]["ranking"], 1)
        self.assertEqual(teams[1]["total_points"], 5)

    def test_inactive_team_excluded(self):
        self.team_c.is_active = False
        self.team_c.save()
        self.assertEqual([t["name"] for t in self.summary()["teams"]], ["Aigles", "Bisons"])

    def test_revealed_results_carry_scores(self):
        results = [r for r in self.summary()["results"] if r["discipline"] == self.relay.id]
        by_team = {r["team"]: r for r in results}
        self.assertEqual(
            by_team[self.team_b.id],
            {
                "id": by_team[self.team_b.id]["id"],
                "team": self.team_b.id,
                "discipline": self.relay.id,
                "result_type": "PTS",
                "ranking": 1,
                "points": 10,
                "time": None,
                "points_difference": 0,
                "global_points": 5,
            },
        )
        self.assertEqual(by_team[self.team_a.id]["ranking"], 2)
        self.assertEqual(by_team[self.team_a.id]["global_points"], 3)
        self.assertEqual(by_team[self.team_c.id]["ranking"], 3)
        self.assertEqual(by_team[self.team_c.id]["global_points"], 1)

    def test_hidden_results_are_null(self):
        results = [
            r for r in self.summary()["results"] if r["discipline"] == self.orienteering.id
        ]
        self.assertEqual(len(results), 3)
        for result in results:
            self.assertEqual(result["result_type"], "TIM")
            for field in ("ranking", "points", "time", "points_difference", "global_points"):
                self.assertIsNone(result[field], field)

    def test_inactive_result_excluded(self):
        TeamResult.objects.filter(discipline=self.relay, team=self.team_c).update(is_active=False)
        results = [r for r in self.summary()["results"] if r["discipline"] == self.relay.id]
        self.assertEqual(sorted(r["team"] for r in results), sorted([self.team_a.id, self.team_b.id]))

    def test_other_edition_never_leaks(self):
        data = self.summary()
        self.assertNotIn("Zèbres", [t["name"] for t in data["teams"]])
        self.assertEqual(len(data["results"]), 6)
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
docker compose --project-directory $MAIN run --rm --no-deps -T -v "$WT/server:/server" server python manage.py test olympic_warriors.tests.test_summary -v 2
```

Expected: `ImportError: cannot import name 'EditionSummarySerializer'`.

- [ ] **Step 3: Write the serializers**

Append to `server/olympic_warriors/serializer.py`:

```python
# Edition summary: everything the public front needs for one edition in one payload.


class SummaryEditionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Edition
        fields = ("id", "year", "host", "start_date", "end_date", "photos_url")


class SummaryDisciplineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Discipline
        fields = ("id", "name", "result_type", "reveal_score")


class SummaryPlayerSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(source="user.first_name")
    last_name = serializers.CharField(source="user.last_name")

    class Meta:
        model = Player
        fields = ("id", "first_name", "last_name")


class SummaryTeamSerializer(serializers.ModelSerializer):
    ranking = serializers.ReadOnlyField()
    total_points = serializers.ReadOnlyField()
    players = serializers.SerializerMethodField()

    class Meta:
        model = Team
        fields = ("id", "name", "ranking", "total_points", "players")

    @extend_schema_field(SummaryPlayerSerializer(many=True))
    def get_players(self, obj):
        players = (
            Player.objects.filter(team=obj, is_active=True)
            .select_related("user")
            .order_by("user__last_name", "user__first_name")
        )
        return SummaryPlayerSerializer(players, many=True).data


class SummaryResultSerializer(serializers.ModelSerializer):
    """
    A team's result in a discipline. Score fields are null while the discipline's
    reveal_score is off: the summary is public and must not leak a score early.
    """

    HIDDEN_FIELDS = ("ranking", "points", "time", "points_difference", "global_points")

    result_type = serializers.ReadOnlyField()
    ranking = serializers.ReadOnlyField()
    points_difference = serializers.ReadOnlyField()
    global_points = serializers.ReadOnlyField()

    class Meta:
        model = TeamResult
        fields = (
            "id",
            "team",
            "discipline",
            "result_type",
            "ranking",
            "points",
            "time",
            "points_difference",
            "global_points",
        )

    def to_representation(self, instance):
        if instance.discipline.reveal_score:
            return super().to_representation(instance)
        hidden = {
            "id": instance.id,
            "team": instance.team_id,
            "discipline": instance.discipline_id,
            "result_type": instance.result_type,
        }
        hidden.update({field: None for field in self.HIDDEN_FIELDS})
        return hidden


class EditionSummarySerializer(serializers.Serializer):
    """
    Serialize an Edition into {edition, disciplines, teams, results}, active rows only.
    """

    edition = SummaryEditionSerializer()
    disciplines = SummaryDisciplineSerializer(many=True)
    teams = SummaryTeamSerializer(many=True)
    results = SummaryResultSerializer(many=True)

    def to_representation(self, instance):
        disciplines = Discipline.objects.filter(edition=instance, is_active=True).order_by("id")
        teams = Team.objects.filter(edition=instance, is_active=True).order_by("name")
        results = (
            TeamResult.objects.filter(
                discipline__edition=instance,
                discipline__is_active=True,
                team__is_active=True,
                is_active=True,
            )
            .select_related("discipline", "team")
            .order_by("id")
        )
        return {
            "edition": SummaryEditionSerializer(instance).data,
            "disciplines": SummaryDisciplineSerializer(disciplines, many=True).data,
            "teams": SummaryTeamSerializer(teams, many=True).data,
            "results": SummaryResultSerializer(results, many=True).data,
        }
```

- [ ] **Step 4: Run the tests to verify they pass**

Same command as step 2. Expected: `Ran 13 tests ... OK`.

- [ ] **Step 5: Commit**

```bash
cd $WT && git add server/olympic_warriors/serializer.py server/olympic_warriors/tests/test_summary.py
git commit -m "[FEAT] edition summary serializer

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Task 4: Summary view and URL

**Files:**
- Modify: `server/olympic_warriors/views.py` (imports and after `getEditions`)
- Modify: `server/olympic_warriors/urls.py:49-51`
- Modify: `server/olympic_warriors/tests/test_summary.py`

- [ ] **Step 1: Write the failing tests**

Append to `server/olympic_warriors/tests/test_summary.py`:

```python
class TestEditionSummaryEndpoint(APITestCase):
    """GET /edition/year/<year>/summary/ is public and 404s on unknown or inactive years."""

    def setUp(self):
        self.client = APIClient()  # no credentials on purpose
        self.edition = Edition.objects.create(
            year=2026, host="Paris", start_date="2026-09-19", end_date="2026-09-20"
        )
        Team.objects.create(name="Aigles", edition=self.edition)
        Relay.objects.create(edition=self.edition, reveal_score=True)

    def test_public_without_token(self):
        response = self.client.get("/edition/year/2026/summary/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.data.keys()), {"edition", "disciplines", "teams", "results"})
        self.assertEqual(response.data["edition"]["year"], 2026)
        self.assertEqual(response.data["teams"][0]["name"], "Aigles")
        self.assertEqual(response.data["results"][0]["ranking"], 1)

    def test_unknown_year_is_404(self):
        response = self.client.get("/edition/year/1999/summary/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {"error": "Edition not found"})

    def test_inactive_edition_is_404(self):
        self.edition.is_active = False
        self.edition.save()
        response = self.client.get("/edition/year/2026/summary/")
        self.assertEqual(response.status_code, 404)
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
docker compose --project-directory $MAIN run --rm --no-deps -T -v "$WT/server:/server" server python manage.py test olympic_warriors.tests.test_summary.TestEditionSummaryEndpoint -v 2
```

Expected: three failures, `test_public_without_token` with `404 != 200` (no route yet, Django 404 HTML), the others may pass by accident on the Django 404 but `test_unknown_year_is_404` fails on `response.data`.

- [ ] **Step 3: Add the view**

In `server/olympic_warriors/views.py`, add `EditionSummarySerializer` to the `from .serializer import (...)` list, then insert after `getEditions` (before the `# Teams` comment):

```python
@extend_schema(
    summary="Everything the public front needs for one edition, by year",
    responses={
        "200": EditionSummarySerializer,
        "404": OpenApiResponse(description="Edition not found"),
        "500": OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
@permission_classes([AllowAny])
def getEditionSummary(request, year):
    try:
        edition = Edition.objects.get(year=year, is_active=True)
    except Edition.DoesNotExist:
        return Response({"error": "Edition not found"}, status=404)
    serializer = EditionSummarySerializer(edition)
    return Response(serializer.data)
```

`@permission_classes` must stay below `@api_view` (DRF 3.16+ raises otherwise).

- [ ] **Step 4: Route it**

In `server/olympic_warriors/urls.py`, under `# editions`:

```python
    # editions
    path("edition/<int:edition_id>/", views.getEdition),
    path("edition/year/<int:year>/summary/", views.getEditionSummary),
    path("editions/", views.getEditions),
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
docker compose --project-directory $MAIN run --rm --no-deps -T -v "$WT/server:/server" server python manage.py test olympic_warriors.tests.test_summary -v 2
```

Expected: `Ran 16 tests ... OK`.

- [ ] **Step 6: Run the whole backend suite and the schema check**

```bash
docker compose --project-directory $MAIN run --rm --no-deps -T -v "$WT/server:/server" server python manage.py test
docker compose --project-directory $MAIN run --rm --no-deps -T -v "$WT/server:/server" server python manage.py spectacular --file /dev/null
```

Expected: `OK`, and the schema generation prints no error about `getEditionSummary`.

- [ ] **Step 7: Commit**

```bash
cd $WT && git add server/olympic_warriors/views.py server/olympic_warriors/urls.py server/olympic_warriors/tests/test_summary.py
git commit -m "[FEAT] public edition summary endpoint by year

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Task 5: Front test tooling and CI job

**Files:**
- Modify: `front/package.json`
- Modify: `front/vite.config.js`
- Create: `front/src/setupTests.js`
- Create: `front/src/lib/smoke.test.js` (deleted again in Task 6)
- Modify: `.github/workflows/test.yml`

- [ ] **Step 1: Install the dev dependencies**

```bash
cd $WT/front && npm install -D vitest@^2 jsdom@^25 @testing-library/svelte@^5 @testing-library/jest-dom@^6
```

Expected: `package.json` gains the four entries under `devDependencies`, `package-lock.json` updates, no peer warnings about Svelte 4 (Testing Library 5 supports Svelte 3 to 5).

- [ ] **Step 2: Add the test script**

In `front/package.json`, `scripts` becomes:

```json
	"scripts": {
		"dev": "vite dev --port 5173",
		"build": "vite build",
		"preview": "vite preview",
		"test": "vitest run"
	},
```

- [ ] **Step 3: Configure Vitest**

Replace `front/vite.config.js`:

```js
import { sveltekit } from '@sveltejs/kit/vite';
import { svelteTesting } from '@testing-library/svelte/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit(), svelteTesting()],
	server: {
		host: '0.0.0.0',
		port: 5173
	},
	test: {
		environment: 'jsdom',
		include: ['src/**/*.test.js'],
		setupFiles: ['src/setupTests.js']
	}
});
```

Create `front/src/setupTests.js`:

```js
import '@testing-library/jest-dom/vitest';
```

- [ ] **Step 4: Write a smoke test and run it**

Create `front/src/lib/smoke.test.js`:

```js
import { describe, expect, it } from 'vitest';

describe('vitest', () => {
	it('runs', () => {
		expect(1 + 1).toBe(2);
	});
});
```

```bash
cd $WT/front && npm test
```

Expected: `✓ src/lib/smoke.test.js (1)` and `Test Files 1 passed`.

- [ ] **Step 5: Add the CI job**

In `.github/workflows/test.yml`, add a second job after `test:` at the same indentation:

```yaml
  front:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: front

    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Set up Node
        uses: actions/setup-node@v4
        with:
          node-version: '22'
          cache: npm
          cache-dependency-path: front/package-lock.json

      - name: Install dependencies
        run: npm ci

      - name: Provide the build-time API URL
        run: echo "API_URL=http://localhost:3003" > .env

      - name: Run front tests
        run: npm test

      - name: Build
        run: npm run build
```

- [ ] **Step 6: Commit**

```bash
cd $WT && git add front/package.json front/package-lock.json front/vite.config.js front/src/setupTests.js front/src/lib/smoke.test.js .github/workflows/test.yml
git commit -m "[CHORE] front: vitest and testing-library, front CI job

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Task 6: `$lib/api.js` and `$lib/server/urls.js`

**Files:**
- Create: `front/src/lib/api.js`
- Create: `front/src/lib/api.test.js`
- Create: `front/src/lib/server/urls.js`
- Delete: `front/src/lib/smoke.test.js`

- [ ] **Step 1: Write the failing tests**

Create `front/src/lib/api.test.js`:

```js
import { describe, expect, it, vi } from 'vitest';
import { apiGet, apiPost } from './api.js';

const jsonResponse = (status, body) =>
	new Response(JSON.stringify(body), {
		status,
		headers: { 'content-type': 'application/json' }
	});

describe('apiGet', () => {
	it('returns the parsed body on 2xx', async () => {
		const fetch = vi.fn().mockResolvedValue(jsonResponse(200, [{ year: 2026 }]));
		await expect(apiGet(fetch, 'http://api/editions/')).resolves.toEqual([{ year: 2026 }]);
		expect(fetch).toHaveBeenCalledWith('http://api/editions/', { method: 'GET', headers: {} });
	});

	it('throws a SvelteKit error carrying the status and the body message', async () => {
		const fetch = vi.fn().mockResolvedValue(jsonResponse(404, { error: 'Edition not found' }));
		await expect(apiGet(fetch, 'http://api/x')).rejects.toMatchObject({
			status: 404,
			body: { message: 'Edition not found' }
		});
	});

	it('uses the DRF detail field when there is no error field', async () => {
		const fetch = vi.fn().mockResolvedValue(jsonResponse(401, { detail: 'Not authenticated' }));
		await expect(apiGet(fetch, 'http://api/x')).rejects.toMatchObject({
			status: 401,
			body: { message: 'Not authenticated' }
		});
	});

	it('falls back to the status text for a non-JSON error body', async () => {
		const fetch = vi.fn().mockResolvedValue(
			new Response('<h1>Bad Gateway</h1>', { status: 502, statusText: 'Bad Gateway' })
		);
		await expect(apiGet(fetch, 'http://api/x')).rejects.toMatchObject({
			status: 502,
			body: { message: 'Bad Gateway' }
		});
	});

	it('maps a network failure to 502', async () => {
		const fetch = vi.fn().mockRejectedValue(new TypeError('fetch failed'));
		await expect(apiGet(fetch, 'http://api/x')).rejects.toMatchObject({
			status: 502,
			body: { message: 'API unreachable' }
		});
	});
});

describe('apiPost', () => {
	it('sends JSON and returns the parsed body', async () => {
		const fetch = vi.fn().mockResolvedValue(jsonResponse(200, { token: 'abc' }));
		await expect(apiPost(fetch, 'http://api/auth/token/', { username: 'u' })).resolves.toEqual({
			token: 'abc'
		});
		expect(fetch).toHaveBeenCalledWith('http://api/auth/token/', {
			method: 'POST',
			headers: { 'content-type': 'application/json' },
			body: '{"username":"u"}'
		});
	});

	it('throws on a 400 with the first field error as message', async () => {
		const fetch = vi.fn().mockResolvedValue(
			jsonResponse(400, { non_field_errors: ['Unable to log in with provided credentials.'] })
		);
		await expect(apiPost(fetch, 'http://api/auth/token/', {})).rejects.toMatchObject({
			status: 400,
			body: { message: 'Unable to log in with provided credentials.' }
		});
	});
});
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd $WT/front && npm test
```

Expected: `Failed to resolve import "./api.js"`.

- [ ] **Step 3: Write `api.js`**

Create `front/src/lib/api.js`:

```js
import { error } from '@sveltejs/kit';

/**
 * Pick a human message out of a DRF error body.
 * {error}, {detail}, or the first string of the first field error list.
 */
function messageFrom(body, fallback) {
	if (body && typeof body === 'object') {
		if (typeof body.error === 'string') return body.error;
		if (typeof body.detail === 'string') return body.detail;
		for (const value of Object.values(body)) {
			if (Array.isArray(value) && typeof value[0] === 'string') return value[0];
			if (typeof value === 'string') return value;
		}
	}
	return fallback;
}

async function request(fetch, url, options) {
	let response;
	try {
		response = await fetch(url, options);
	} catch {
		error(502, 'API unreachable');
	}

	const isJson = (response.headers.get('content-type') ?? '').includes('application/json');
	const body = isJson ? await response.json() : await response.text();

	if (!response.ok) {
		error(response.status, messageFrom(isJson ? body : null, response.statusText || 'API error'));
	}
	return body;
}

/** GET a JSON resource; throws a SvelteKit error on any failure. */
export function apiGet(fetch, url) {
	return request(fetch, url, { method: 'GET', headers: {} });
}

/** POST a JSON body; throws a SvelteKit error on any failure. */
export function apiPost(fetch, url, body) {
	return request(fetch, url, {
		method: 'POST',
		headers: { 'content-type': 'application/json' },
		body: JSON.stringify(body)
	});
}
```

Create `front/src/lib/server/urls.js`:

```js
import { API_URL } from '$env/static/private';

/** Absolute API URL for a path such as "/editions/". */
export const api = (path) => `${API_URL}${path}`;
```

- [ ] **Step 4: Run the tests to verify they pass, then drop the smoke test**

```bash
cd $WT/front && npm test && git rm -q src/lib/smoke.test.js && npm test
```

Expected: `Test Files 1 passed (1)`, `Tests 7 passed (7)` both times (the second run has one file fewer).

- [ ] **Step 5: Commit**

```bash
cd $WT && git add front/src/lib/api.js front/src/lib/api.test.js front/src/lib/server/urls.js
git commit -m "[FEAT] front: throwing API helper

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Task 7: `$lib/edition.js` helpers and the fixture

**Files:**
- Create: `front/src/lib/fixtures/summary.js`
- Create: `front/src/lib/edition.js`
- Create: `front/src/lib/edition.test.js`

- [ ] **Step 1: Write the fixture**

Create `front/src/lib/fixtures/summary.js`:

```js
/**
 * One edition as the summary endpoint returns it: a revealed points discipline (Relay),
 * a hidden timed one (Orienteering), three teams. Bisons lead, Aigles second, Cerfs last.
 */
export const summary = {
	edition: {
		id: 1,
		year: 2026,
		host: 'Paris',
		start_date: '2026-09-19',
		end_date: '2026-09-20',
		photos_url: null
	},
	disciplines: [
		{ id: 10, name: 'Relay', result_type: 'PTS', reveal_score: true },
		{ id: 11, name: 'Orienteering', result_type: 'TIM', reveal_score: false }
	],
	teams: [
		{
			id: 1,
			name: 'Aigles',
			ranking: 2,
			total_points: 3,
			players: [
				{ id: 1, first_name: 'Ana', last_name: 'Lopez' },
				{ id: 2, first_name: 'Bob', last_name: 'Martin' }
			]
		},
		{
			id: 2,
			name: 'Bisons',
			ranking: 1,
			total_points: 5,
			players: [{ id: 3, first_name: 'Chloé', last_name: 'Nguyen' }]
		},
		{ id: 3, name: 'Cerfs', ranking: 3, total_points: 2, players: [] }
	],
	results: [
		{ id: 100, team: 1, discipline: 10, result_type: 'PTS', ranking: 2, points: 5, time: null, points_difference: -2, global_points: 3 },
		{ id: 101, team: 2, discipline: 10, result_type: 'PTS', ranking: 1, points: 10, time: null, points_difference: 4, global_points: 5 },
		{ id: 102, team: 3, discipline: 10, result_type: 'PTS', ranking: 3, points: 0, time: null, points_difference: -2, global_points: 2 },
		{ id: 103, team: 1, discipline: 11, result_type: 'TIM', ranking: null, points: null, time: null, points_difference: null, global_points: null },
		{ id: 104, team: 2, discipline: 11, result_type: 'TIM', ranking: null, points: null, time: null, points_difference: null, global_points: null },
		{ id: 105, team: 3, discipline: 11, result_type: 'TIM', ranking: null, points: null, time: null, points_difference: null, global_points: null }
	]
};

/** Same edition with Orienteering revealed and timed results filled in. */
export const summaryAllRevealed = {
	...summary,
	disciplines: [
		summary.disciplines[0],
		{ ...summary.disciplines[1], reveal_score: true }
	],
	results: [
		...summary.results.slice(0, 3),
		{ id: 103, team: 1, discipline: 11, result_type: 'TIM', ranking: 1, points: null, time: '00:12:30', points_difference: 0, global_points: 5 },
		{ id: 104, team: 2, discipline: 11, result_type: 'TIM', ranking: 3, points: null, time: '00:15:02', points_difference: 0, global_points: 2 },
		{ id: 105, team: 3, discipline: 11, result_type: 'TIM', ranking: 2, points: null, time: '00:13:45', points_difference: 0, global_points: 3 }
	]
};
```

- [ ] **Step 2: Write the failing tests**

Create `front/src/lib/edition.test.js`:

```js
import { describe, expect, it } from 'vitest';
import {
	countdownParts,
	disciplineResults,
	editionPhase,
	findDiscipline,
	findTeam,
	formatDifference,
	rankedTeams,
	switchYearPath,
	teamResults
} from './edition.js';
import { summary, summaryAllRevealed } from './fixtures/summary.js';

describe('rankedTeams', () => {
	it('sorts by ranking then name', () => {
		expect(rankedTeams(summary).map((t) => t.name)).toEqual(['Bisons', 'Aigles', 'Cerfs']);
	});

	it('keeps tied teams in name order', () => {
		const tied = {
			...summary,
			teams: [
				{ ...summary.teams[2], ranking: 1 },
				{ ...summary.teams[0], ranking: 1 },
				{ ...summary.teams[1], ranking: 3 }
			]
		};
		expect(rankedTeams(tied).map((t) => t.name)).toEqual(['Aigles', 'Cerfs', 'Bisons']);
	});

	it('does not mutate the summary', () => {
		rankedTeams(summary);
		expect(summary.teams[0].name).toBe('Aigles');
	});
});

describe('disciplineResults', () => {
	it('returns rows in rank order with the team name joined', () => {
		const rows = disciplineResults(summary, 10);
		expect(rows.map((r) => [r.ranking, r.teamName, r.points, r.points_difference])).toEqual([
			[1, 'Bisons', 10, 4],
			[2, 'Aigles', 5, -2],
			[3, 'Cerfs', 0, -2]
		]);
	});

	it('returns null for an unrevealed discipline', () => {
		expect(disciplineResults(summary, 11)).toBeNull();
	});

	it('returns timed rows for a revealed timed discipline', () => {
		const rows = disciplineResults(summaryAllRevealed, 11);
		expect(rows.map((r) => [r.ranking, r.teamName, r.time])).toEqual([
			[1, 'Aigles', '00:12:30'],
			[2, 'Cerfs', '00:13:45'],
			[3, 'Bisons', '00:15:02']
		]);
	});

	it('returns null for an unknown discipline', () => {
		expect(disciplineResults(summary, 999)).toBeNull();
	});

	it('sorts a row without a score last', () => {
		const partial = {
			...summary,
			results: summary.results.map((r) =>
				r.id === 101 ? { ...r, ranking: null, points: null, points_difference: null, global_points: null } : r
			)
		};
		expect(disciplineResults(partial, 10).map((r) => r.teamName)).toEqual(['Aigles', 'Cerfs', 'Bisons']);
	});
});

describe('teamResults', () => {
	it('gives one row per discipline in id order', () => {
		expect(teamResults(summary, 1)).toEqual([
			{
				disciplineId: 10,
				disciplineName: 'Relay',
				result_type: 'PTS',
				revealed: true,
				ranking: 2,
				points: 5,
				time: null
			},
			{
				disciplineId: 11,
				disciplineName: 'Orienteering',
				result_type: 'TIM',
				revealed: false,
				ranking: null,
				points: null,
				time: null
			}
		]);
	});

	it('marks a discipline the team has no result in as unrevealed', () => {
		const missing = { ...summary, results: summary.results.filter((r) => r.team !== 1) };
		expect(teamResults(missing, 1).map((r) => r.revealed)).toEqual([false, false]);
	});
});

describe('findTeam / findDiscipline', () => {
	it('find by numeric id', () => {
		expect(findTeam(summary, 2).name).toBe('Bisons');
		expect(findDiscipline(summary, 11).name).toBe('Orienteering');
	});

	it('return null when missing', () => {
		expect(findTeam(summary, 42)).toBeNull();
		expect(findDiscipline(summary, 42)).toBeNull();
	});
});

describe('editionPhase', () => {
	it('is upcoming before 09:00 on start_date', () => {
		expect(editionPhase(summary.edition, new Date(2026, 8, 19, 8, 59))).toBe('upcoming');
	});

	it('is started from 09:00 on start_date', () => {
		expect(editionPhase(summary.edition, new Date(2026, 8, 19, 9, 0))).toBe('started');
	});

	it('is started long after', () => {
		expect(editionPhase(summary.edition, new Date(2027, 0, 1))).toBe('started');
	});
});

describe('countdownParts', () => {
	it('splits the remaining time', () => {
		expect(countdownParts(summary.edition, new Date(2026, 8, 17, 7, 58, 30))).toEqual({
			days: 2,
			hours: 1,
			minutes: 1,
			seconds: 30
		});
	});

	it('is all zeros once started', () => {
		expect(countdownParts(summary.edition, new Date(2026, 8, 19, 9, 0, 1))).toEqual({
			days: 0,
			hours: 0,
			minutes: 0,
			seconds: 0
		});
	});
});

describe('formatDifference', () => {
	it('signs positives, keeps zero and negatives', () => {
		expect(formatDifference(3)).toBe('+3');
		expect(formatDifference(0)).toBe('0');
		expect(formatDifference(-2)).toBe('-2');
	});
});

describe('switchYearPath', () => {
	it('replaces the year segment and keeps the section', () => {
		expect(switchYearPath('/2026/teams', 2025)).toBe('/2025/teams');
		expect(switchYearPath('/2026/disciplines/12', 2025)).toBe('/2025/disciplines');
		expect(switchYearPath('/2026/teams/3', 2025)).toBe('/2025/teams');
		expect(switchYearPath('/2026', 2025)).toBe('/2025');
	});

	it('goes to the hub from a non-edition page', () => {
		expect(switchYearPath('/', 2025)).toBe('/2025');
		expect(switchYearPath('/login', 2025)).toBe('/2025');
	});
});
```

- [ ] **Step 3: Run the tests to verify they fail**

```bash
cd $WT/front && npm test
```

Expected: `Failed to resolve import "./edition.js"`.

- [ ] **Step 4: Write `edition.js`**

Create `front/src/lib/edition.js`:

```js
/**
 * Pure derivations over an edition summary as returned by
 * GET /edition/year/<year>/summary/. No fetching, no Svelte, fully unit-tested.
 */

const byRankThenName = (a, b) => a.ranking - b.ranking || a.name.localeCompare(b.name);

/** Teams of the edition sorted by global ranking, ties by name. */
export function rankedTeams(summary) {
	return [...summary.teams].sort(byRankThenName);
}

/** Team row by id, or null. */
export function findTeam(summary, teamId) {
	return summary.teams.find((t) => t.id === teamId) ?? null;
}

/** Discipline row by id, or null. */
export function findDiscipline(summary, disciplineId) {
	return summary.disciplines.find((d) => d.id === disciplineId) ?? null;
}

/**
 * Results of one discipline in rank order with `teamName` joined in.
 * Null when the discipline is unknown or its score is not revealed.
 */
export function disciplineResults(summary, disciplineId) {
	const discipline = findDiscipline(summary, disciplineId);
	if (!discipline || !discipline.reveal_score) return null;

	const names = new Map(summary.teams.map((t) => [t.id, t.name]));
	const rank = (r) => r.ranking ?? Number.POSITIVE_INFINITY; // no score yet: sort last
	return summary.results
		.filter((r) => r.discipline === disciplineId)
		.map((r) => ({ ...r, teamName: names.get(r.team) ?? 'Unknown' }))
		.sort((a, b) => rank(a) - rank(b) || a.teamName.localeCompare(b.teamName));
}

/**
 * One row per discipline (id order) for a team: name, whether the score is
 * revealed, and the rank, points and time when it is.
 */
export function teamResults(summary, teamId) {
	return summary.disciplines.map((discipline) => {
		const result = summary.results.find(
			(r) => r.team === teamId && r.discipline === discipline.id
		);
		const revealed = Boolean(discipline.reveal_score && result && result.ranking !== null);
		return {
			disciplineId: discipline.id,
			disciplineName: discipline.name,
			result_type: discipline.result_type,
			revealed,
			ranking: revealed ? result.ranking : null,
			points: revealed ? result.points : null,
			time: revealed ? result.time : null
		};
	});
}

/** The event starts at 09:00 local time on start_date. */
export function startInstant(edition) {
	const [year, month, day] = edition.start_date.split('-').map(Number);
	return new Date(year, month - 1, day, 9, 0, 0);
}

/** "upcoming" before the start instant, "started" from then on. */
export function editionPhase(edition, now = new Date()) {
	return now < startInstant(edition) ? 'upcoming' : 'started';
}

/** Days, hours, minutes, seconds until the start instant; zeros once started. */
export function countdownParts(edition, now = new Date()) {
	const distance = Math.max(0, startInstant(edition) - now);
	const seconds = Math.floor(distance / 1000);
	return {
		days: Math.floor(seconds / 86400),
		hours: Math.floor((seconds % 86400) / 3600),
		minutes: Math.floor((seconds % 3600) / 60),
		seconds: seconds % 60
	};
}

/** +3, 0, -2 */
export function formatDifference(n) {
	return n > 0 ? `+${n}` : `${n}`;
}

/**
 * Where the year switcher sends the visitor: same section under the other year
 * (a detail page falls back to its list), the hub for anything else.
 */
export function switchYearPath(pathname, year) {
	const match = pathname.match(/^\/\d{4}(?:\/([a-z]+))?/);
	if (!match) return `/${year}`;
	return match[1] ? `/${year}/${match[1]}` : `/${year}`;
}
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
cd $WT/front && npm test
```

Expected: `Test Files 2 passed (2)`, all `edition.test.js` cases green.

- [ ] **Step 6: Commit**

```bash
cd $WT && git add front/src/lib/edition.js front/src/lib/edition.test.js front/src/lib/fixtures/summary.js
git commit -m "[FEAT] front: pure edition summary helpers

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Task 8: Icons module, Darts and fallback SVGs

**Files:**
- Create: `front/src/lib/icons.js`
- Create: `front/src/lib/icons.test.js`
- Create: `front/src/lib/img/icons/darts.svg`
- Create: `front/src/lib/img/icons/default.svg`

- [ ] **Step 1: Write the failing tests**

Create `front/src/lib/icons.test.js`:

```js
import { describe, expect, it } from 'vitest';
import { iconFor, iconSlug } from './icons.js';

describe('iconSlug', () => {
	it('lowercases and strips spaces and apostrophes', () => {
		expect(iconSlug('Hide and Seek')).toBe('hideandseek');
		expect(iconSlug("Course d'orientation")).toBe('coursedorientation');
		expect(iconSlug('Rugby')).toBe('rugby');
	});
});

describe('iconFor', () => {
	it('returns the matching svg url', () => {
		expect(iconFor('Rugby')).toMatch(/rugby\.svg$/);
		expect(iconFor('Hide and Seek')).toMatch(/hideandseek\.svg$/);
		expect(iconFor('Darts')).toMatch(/darts\.svg$/);
	});

	it('falls back to default.svg for an unknown discipline', () => {
		expect(iconFor('General Culture Quizz')).toMatch(/default\.svg$/);
	});
});
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd $WT/front && npm test
```

Expected: `Failed to resolve import "./icons.js"`.

- [ ] **Step 3: Write the SVGs and the module**

Create `front/src/lib/img/icons/darts.svg` (same white-on-transparent style as the others):

```svg
<svg width="2000" height="2000" viewBox="0 0 2000 2000" fill="none" xmlns="http://www.w3.org/2000/svg">
<circle cx="1000" cy="1000" r="900" stroke="white" stroke-width="120"/>
<circle cx="1000" cy="1000" r="560" stroke="white" stroke-width="120"/>
<circle cx="1000" cy="1000" r="220" fill="white"/>
<path d="M1000 1000L1720 280" stroke="white" stroke-width="110" stroke-linecap="round"/>
<path d="M1720 280L1560 300L1720 440L1740 280Z" fill="white"/>
</svg>
```

Create `front/src/lib/img/icons/default.svg`:

```svg
<svg width="2000" height="2000" viewBox="0 0 2000 2000" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M1000 120L1235 700L1860 745L1380 1150L1530 1770L1000 1440L470 1770L620 1150L140 745L765 700Z" fill="white"/>
</svg>
```

Create `front/src/lib/icons.js`:

```js
/**
 * Discipline name to icon URL. Every SVG in ./img/icons is bundled; the file stem is
 * the slug of the discipline name ("Hide and Seek" -> hideandseek.svg).
 */
const files = import.meta.glob('./img/icons/*.svg', { eager: true, query: '?url', import: 'default' });

const icons = Object.fromEntries(
	Object.entries(files).map(([path, url]) => [path.slice('./img/icons/'.length, -'.svg'.length), url])
);

export function iconSlug(name) {
	return name.toLowerCase().replace(/[\s']/g, '');
}

export function iconFor(name) {
	return icons[iconSlug(name)] ?? icons.default;
}
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd $WT/front && npm test
```

Expected: `Test Files 3 passed (3)`.

- [ ] **Step 5: Commit**

```bash
cd $WT && git add front/src/lib/icons.js front/src/lib/icons.test.js front/src/lib/img/icons/darts.svg front/src/lib/img/icons/default.svg
git commit -m "[FEAT] front: discipline icons by name with fallback, darts icon

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Task 9: Root layout data, year matcher, year layout, error page

**Files:**
- Create: `front/src/params/year.js`
- Rewrite: `front/src/routes/+layout.server.js`
- Create: `front/src/routes/[year=year]/+layout.server.js`
- Create: `front/src/routes/+error.svelte`
- Delete: `front/src/hooks.server.js`

No unit test here: these files are SvelteKit glue over already-tested helpers. They are exercised by `npm run build` in this task and by the browser smoke in Task 16.

- [ ] **Step 1: Param matcher**

Create `front/src/params/year.js`:

```js
/** Four digits, so "/login" and "/ranking" never match the [year] route. */
export function match(param) {
	return /^\d{4}$/.test(param);
}
```

- [ ] **Step 2: Root layout load**

Replace `front/src/routes/+layout.server.js`:

```js
import { apiGet } from '$lib/api';
import { api } from '$lib/server/urls';

/** Every active edition, newest first, plus the year the bare URLs default to. */
export const load = async ({ fetch }) => {
	const editions = (await apiGet(fetch, api('/editions/'))).sort((a, b) => b.year - a.year);
	return { editions, latestYear: editions[0]?.year ?? null };
};
```

- [ ] **Step 3: Year layout load**

Create `front/src/routes/[year=year]/+layout.server.js`:

```js
import { error } from '@sveltejs/kit';
import { apiGet } from '$lib/api';
import { api } from '$lib/server/urls';

/** The whole edition in one payload; every page under /<year> reads it via parent(). */
export const load = async ({ fetch, params }) => {
	try {
		const summary = await apiGet(fetch, api(`/edition/year/${params.year}/summary/`));
		return { summary };
	} catch (err) {
		if (err?.status === 404) error(404, `No edition in ${params.year}`);
		throw err;
	}
};
```

- [ ] **Step 4: Error page**

Create `front/src/routes/+error.svelte`:

```svelte
<script>
	import { page } from '$app/stores';
</script>

<section>
	<h1>{$page.status}</h1>
	<p>{$page.error?.message ?? 'Something went wrong'}</p>
	<a href="/">Back to the Olympic Warriors</a>
</section>

<style>
	section {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 1rem;
		margin: 6rem 1rem;
		color: var(--color-theme-1);
		text-align: center;
	}

	h1 {
		font-size: 4rem;
		margin: 0;
	}

	a {
		color: var(--color-bg-0);
		background-color: var(--color-theme-1);
		padding: 0.6rem 2rem;
		border-radius: 2em;
		font-weight: 700;
	}
</style>
```

- [ ] **Step 5: Delete the hooks stub**

```bash
cd $WT && git rm -q front/src/hooks.server.js
```

- [ ] **Step 6: Build**

```bash
cd $WT/front && npm run build 2>&1 | tail -5
```

Expected: `✓ built in …` with no error. (Old pages still reference `$lib/utils.js`; that file is deleted in Task 15, so the build passes for now.)

- [ ] **Step 7: Commit**

```bash
cd $WT && git add front/src/params/year.js front/src/routes/+layout.server.js "front/src/routes/[year=year]/+layout.server.js" front/src/routes/+error.svelte
git commit -m "[FEAT] front: year route layout, editions list, error page

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Task 10: Header, mobile menu, layout theme

**Files:**
- Rewrite: `front/src/routes/Header.svelte`
- Rewrite: `front/src/routes/menu.svelte`
- Modify: `front/src/routes/+layout.svelte:18-28`
- Delete: `front/src/routes/Footer.svelte`

- [ ] **Step 1: Header**

Replace `front/src/routes/Header.svelte`:

```svelte
<script>
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import logo from '$lib/img/logo.svg';
	import { switchYearPath } from '$lib/edition';
	import Menu from './menu.svelte';

	$: editions = $page.data.editions ?? [];
	$: year = Number($page.params.year ?? $page.data.latestYear);
	$: edition = editions.find((e) => e.year === year);
	$: tabs = [
		{ name: 'Ranking', url: `/${year}/ranking` },
		{ name: 'Teams', url: `/${year}/teams` },
		{ name: 'Disciplines', url: `/${year}/disciplines` },
		...(edition?.photos_url ? [{ name: 'Photos', url: edition.photos_url, external: true }] : [])
	];

	const switchYear = (event) => goto(switchYearPath($page.url.pathname, event.target.value));
</script>

<header>
	<div class="logo">
		<a href="/">
			<img src={logo} alt="OW" />
		</a>
		{#if editions.length > 0}
			<select aria-label="Edition" value={year} on:change={switchYear}>
				{#each editions as e}
					<option value={e.year}>{e.year}</option>
				{/each}
			</select>
		{/if}
	</div>

	<nav>
		<ul>
			{#each tabs as tab}
				<li aria-current={$page.url.pathname === tab.url ? 'page' : undefined}>
					{#if tab.external}
						<a href={tab.url} target="_blank" rel="noopener">{tab.name}</a>
					{:else}
						<a href={tab.url}>{tab.name}</a>
					{/if}
				</li>
			{/each}
		</ul>
	</nav>
	<Menu {tabs} {editions} {year} />
</header>

<style>
	header {
		display: flex;
		z-index: 10;
		padding: 2em clamp(0em, 2vw, 5em);
		justify-content: space-between;
	}

	.logo {
		display: flex;
		align-items: center;
		gap: 1rem;
	}

	.logo a {
		display: flex;
		align-items: center;
		justify-content: center;
		height: 100%;
	}

	.logo img {
		margin-left: 2vw;
		height: 3em;
		object-fit: contain;
	}

	select {
		background: transparent;
		color: var(--color-theme-1);
		border: 2px solid var(--color-theme-1);
		border-radius: 2em;
		padding: 0.3em 0.8em;
		font-weight: 700;
		font-size: 1rem;
		letter-spacing: 0.1em;
		cursor: pointer;
	}

	select option {
		color: black;
	}

	nav {
		display: flex;
		justify-content: center;
		view-transition-name: navbar;
	}

	nav a {
		display: flex;
		height: 90%;
		align-items: center;
		padding: 0 2em;
		color: var(--color-theme-1);
		font-weight: 700;
		font-size: 1rem;
		text-transform: uppercase;
		letter-spacing: 0.2em;
		text-decoration: none;
	}

	ul {
		display: flex;
		justify-content: center;
		align-items: center;
		padding: 0;
		margin: 0;
		height: 3em;
	}

	li {
		position: relative;
		height: 100%;
	}

	li[aria-current='page']::before {
		content: '';
		width: 30px;
		height: 3px;
		position: absolute;
		top: 0;
		left: calc(50% - 15px);
		background-color: var(--color-theme-1);
		view-transition-name: indicator;
	}

	a:hover {
		color: var(--color-theme-1);
	}

	@media (max-width: 1000px) {
		ul {
			display: none;
		}
	}
</style>
```

- [ ] **Step 2: Mobile menu**

Replace `front/src/routes/menu.svelte`:

```svelte
<script>
	import { slide } from 'svelte/transition';
	import { quintOut } from 'svelte/easing';

	export let tabs;
	export let editions = [];
	export let year = null;

	let menuOpen = false;
</script>

<label class="hamburger">
	<input type="checkbox" id="menu-toggle" bind:checked={menuOpen} />
	<svg viewBox="0 0 32 32">
		<path
			class="line line-top-bottom"
			d="M27 10 13 10C10.8 10 9 8.2 9 6 9 3.5 10.8 2 13 2 15.2 2 17 3.8 17 6L17 26C17 28.2 18.8 30 21 30 23.2 30 25 28.2 25 26 25 23.8 23.2 22 21 22L7 22"
		/>
		<path class="line" d="M7 16 27 16" />
	</svg>
</label>

{#if menuOpen}
	<div class="menu" transition:slide={{ duration: 300, easing: quintOut, axis: 'y' }}>
		{#each tabs as tab}
			{#if tab.external}
				<a href={tab.url} target="_blank" rel="noopener" on:click={() => (menuOpen = false)}>{tab.name}</a>
			{:else}
				<a href={tab.url} on:click={() => (menuOpen = false)}>{tab.name}</a>
			{/if}
		{/each}
		<div class="years">
			{#each editions as e}
				<a href="/{e.year}" class:current={e.year === year} on:click={() => (menuOpen = false)}>{e.year}</a>
			{/each}
		</div>
	</div>
{/if}

<style>
	@media (min-width: 1000px) {
		.hamburger {
			display: none;
		}
	}

	@media (max-width: 1000px) {
		.hamburger {
			display: block;
		}
	}

	.menu a {
		color: var(--color-theme-1);
		font-weight: 700;
		font-size: 1.5rem;
		text-transform: uppercase;
		letter-spacing: 0.2em;
		text-decoration: none;
		padding: 0.8em 1em;
		transition: 0.2s ease-in-out;
	}

	.menu {
		position: fixed;
		top: 0;
		left: 0;
		width: 100vw;
		height: 100vh;
		display: flex;
		padding-top: 6rem;
		flex-direction: column;
		-webkit-backdrop-filter: blur(8px);
		backdrop-filter: blur(8px);
	}

	.years {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		padding: 1.5rem 1em;
	}

	.years a {
		font-size: 1rem;
		padding: 0.4em 1em;
		border: 2px solid var(--color-theme-1);
		border-radius: 2em;
	}

	.years a.current {
		color: var(--color-bg-0);
		background-color: var(--color-theme-1);
	}

	.menu::after {
		content: '';
		position: fixed;
		top: 0;
		left: 0;
		width: 100vw;
		height: 100vh;
		background-color: var(--color-bg-0);
		opacity: 0.4;
		z-index: -11;
	}

	.hamburger {
		z-index: 11;
		cursor: pointer;
		margin-left: 1.2rem;
	}

	.hamburger input {
		display: none;
	}

	.hamburger svg {
		height: 3.2em;
		transition: transform 600ms cubic-bezier(0.4, 0, 0.2, 1);
	}

	.line {
		fill: none;
		stroke: var(--color-theme-1);
		stroke-linecap: round;
		stroke-linejoin: round;
		stroke-width: 3;
		transition:
			stroke-dasharray 600ms cubic-bezier(0.4, 0, 0.2, 1),
			stroke-dashoffset 600ms cubic-bezier(0.4, 0, 0.2, 1);
	}

	.line-top-bottom {
		stroke-dasharray: 12 63;
	}

	.hamburger input:checked + svg {
		transform: rotate(-45deg);
	}

	.hamburger input:checked + svg .line-top-bottom {
		stroke-dasharray: 20 300;
		stroke-dashoffset: -32.42;
	}
</style>
```

- [ ] **Step 3: Layout theme keyed on hub routes**

In `front/src/routes/+layout.svelte`, replace the `$: { ... }` block and the commented footer:

```svelte
<script>
	import Header from './Header.svelte';
	import './styles.css';
	import { onNavigate } from '$app/navigation';
	import { page } from '$app/stores';

	onNavigate((navigation) => {
		if (!document.startViewTransition) return;

		return new Promise((resolve) => {
			document.startViewTransition(async () => {
				resolve();
				await navigation.complete;
			});
		});
	});

	const HUB_ROUTES = new Set(['/', '/[year=year]']);
	$: isHub = HUB_ROUTES.has($page.route.id);

	$: if (typeof document !== 'undefined') {
		document.documentElement.style.setProperty('--color-bg-0', isHub ? 'black' : 'white');
		document.documentElement.style.setProperty('--color-theme-1', isHub ? '#F9F3C1' : 'black');
	}
</script>

<div class="app">
	<Header />

	<main>
		<slot />
	</main>
</div>
```

Keep the existing `<style>` block unchanged.

- [ ] **Step 4: Delete the unused footer, build**

```bash
cd $WT && git rm -q front/src/routes/Footer.svelte && cd front && npm run build 2>&1 | tail -3
```

Expected: `✓ built`.

- [ ] **Step 5: Commit**

```bash
cd $WT && git add front/src/routes/Header.svelte front/src/routes/menu.svelte front/src/routes/+layout.svelte
git commit -m "[FEAT] front: edition-scoped header with year switcher

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Task 11: Hub component, home and year hub pages

**Files:**
- Create: `front/src/lib/components/EditionHub.svelte`
- Create: `front/src/lib/components/EditionHub.test.js`
- Create: `front/src/routes/+page.server.js`
- Rewrite: `front/src/routes/+page.svelte`
- Create: `front/src/routes/[year=year]/+page.svelte`

- [ ] **Step 1: Write the failing component test**

Create `front/src/lib/components/EditionHub.test.js`:

```js
import { render, screen } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import EditionHub from './EditionHub.svelte';
import { summary } from '../fixtures/summary.js';

const editions = [
	{ id: 1, year: 2026, host: 'Paris', photos_url: null },
	{ id: 2, year: 2025, host: 'Lyon', photos_url: null },
	{ id: 3, year: 2024, host: 'Nantes', photos_url: null }
];

describe('EditionHub', () => {
	beforeEach(() => vi.useFakeTimers());
	afterEach(() => vi.useRealTimers());

	it('shows a countdown before the start', () => {
		vi.setSystemTime(new Date(2026, 8, 17, 9, 0, 0));
		render(EditionHub, { summary, editions });

		expect(screen.getByText('Days').querySelector('span')).toHaveTextContent('2');
		expect(screen.queryByRole('link', { name: 'Ranking' })).toBeNull();
	});

	it('shows the ranking button once started', () => {
		vi.setSystemTime(new Date(2026, 8, 19, 10, 0, 0));
		render(EditionHub, { summary, editions });

		expect(screen.getByRole('link', { name: 'Ranking' })).toHaveAttribute('href', '/2026/ranking');
		expect(screen.queryByText('Days')).toBeNull();
	});

	it('shows host, dates, discipline icons and the other editions', () => {
		vi.setSystemTime(new Date(2026, 8, 19, 10, 0, 0));
		render(EditionHub, { summary, editions });

		expect(screen.getByText(/Paris/)).toBeInTheDocument();
		expect(screen.getByAltText('Relay')).toHaveAttribute('src', expect.stringMatching(/relay\.svg|default\.svg/));
		expect(screen.getByAltText('Orienteering')).toHaveAttribute('src', expect.stringMatching(/orienteering\.svg$/));
		expect(screen.getByRole('link', { name: '2025' })).toHaveAttribute('href', '/2025');
		expect(screen.getByRole('link', { name: '2024' })).toHaveAttribute('href', '/2024');
		expect(screen.queryByRole('link', { name: '2026' })).toBeNull();
	});
});
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd $WT/front && npm test
```

Expected: `Failed to resolve import "./EditionHub.svelte"`.

- [ ] **Step 3: Write the hub component**

Create `front/src/lib/components/EditionHub.svelte`:

```svelte
<script>
	import { onMount } from 'svelte';
	import eclipse from '$lib/img/eclipse.png';
	import title from '$lib/img/title.svg';
	import { iconFor } from '$lib/icons';
	import { countdownParts, editionPhase } from '$lib/edition';

	export let summary;
	export let editions;

	$: edition = summary.edition;
	$: half = Math.ceil(summary.disciplines.length / 2);
	$: columns = [summary.disciplines.slice(0, half), summary.disciplines.slice(half)];
	$: others = editions.filter((e) => e.year !== edition.year);

	let now = new Date();
	$: phase = editionPhase(edition, now);
	$: parts = countdownParts(edition, now);

	onMount(() => {
		const interval = setInterval(() => (now = new Date()), 1000);
		return () => clearInterval(interval);
	});

	const formatDate = (iso) => new Date(`${iso}T12:00:00`).toLocaleDateString('fr-FR', {
		day: 'numeric',
		month: 'long'
	});
</script>

<div class="fullscreen">
	<img id="eclipse" src={eclipse} alt="eclipse" />
	<img id="title" src={title} alt="OLYMPIC WARRIORS" />

	{#each columns as column}
		<div class="sportcolumn">
			{#each column as discipline}
				<img src={iconFor(discipline.name)} alt={discipline.name} />
			{/each}
		</div>
	{/each}
</div>

<p class="where">{edition.host} · {formatDate(edition.start_date)} – {formatDate(edition.end_date)} {edition.year}</p>

{#if phase === 'upcoming'}
	<div id="countdown">
		<div><span>{parts.days}</span>Days</div>
		<div><span>{parts.hours}</span>Hours</div>
		<div><span>{parts.minutes}</span>Minutes</div>
		<div><span>{parts.seconds}</span>Seconds</div>
	</div>
{:else}
	<div id="ranking">
		<a href="/{edition.year}/ranking">Ranking</a>
	</div>
{/if}

{#if others.length > 0}
	<nav class="editions" aria-label="Other editions">
		{#each others as other}
			<a href="/{other.year}">{other.year}</a>
		{/each}
	</nav>
{/if}

<style>
	.sportcolumn {
		position: absolute;
		display: flex;
		flex-direction: column;
		opacity: 0.3;
		gap: 180px;
	}

	.sportcolumn:first-of-type {
		left: 20vw;
	}

	.sportcolumn:first-of-type :nth-child(2) {
		transform: translate(-80px, 0);
	}

	.sportcolumn:last-of-type {
		right: 20vw;
	}

	.sportcolumn:last-of-type :nth-child(2) {
		transform: translate(80px, 0);
	}

	.sportcolumn img {
		width: min(100px, 10vw);
	}

	.where {
		text-align: center;
		color: var(--color-theme-1);
		font-weight: 600;
		letter-spacing: 0.1em;
		margin: 0 1rem 1rem;
	}

	#countdown,
	#ranking {
		display: flex;
		justify-content: center;
		gap: 2rem;
		font-size: 1rem;
		margin: 1rem 0;
		color: var(--color-theme-1);
	}

	#ranking a {
		color: var(--color-bg-0);
		background-color: var(--color-theme-1);
		padding: 0.6rem 4rem;
		border-radius: 2em;
		font-weight: 700;
		font-size: 2rem;
		transition: 0.3s;
		text-decoration: none;
	}

	#ranking a:hover {
		opacity: 0.8;
	}

	#countdown div {
		display: flex;
		flex-direction: column;
		align-items: center;
		width: 75px;
	}

	#countdown span {
		font-size: 2.5rem;
		font-weight: 600;
		margin-bottom: 1rem;
	}

	.editions {
		display: flex;
		justify-content: center;
		gap: 1rem;
		margin: 2rem 1rem;
	}

	.editions a {
		color: var(--color-theme-1);
		border: 2px solid var(--color-theme-1);
		border-radius: 2em;
		padding: 0.4rem 1.2rem;
		font-weight: 700;
		letter-spacing: 0.1em;
		text-decoration: none;
		transition: 0.2s;
	}

	.editions a:hover {
		color: var(--color-bg-0);
		background-color: var(--color-theme-1);
	}

	#eclipse {
		width: min(98%, 1200px);
		margin: 0 auto;
		transform: translate(1%, 0);
		z-index: -10;
	}

	#title {
		width: min(25%, 300px);
		position: absolute;
	}

	.fullscreen {
		position: relative;
		height: 65vh;
		display: flex;
		flex-direction: column;
		justify-content: center;
		align-items: center;
	}

	@media (max-width: 1000px) {
		.sportcolumn {
			gap: 100px;
		}

		.sportcolumn img {
			width: min(100px, 20vw);
		}

		#eclipse {
			width: min(98%, 800px);
		}

		#title {
			width: min(25%, 200px);
		}

		.fullscreen {
			height: 60vh;
		}

		#ranking a {
			padding: 0.6rem 2rem;
			font-size: 1.2rem;
		}
	}
</style>
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd $WT/front && npm test
```

Expected: `EditionHub.test.js (3)` green, `Test Files 4 passed (4)`.

- [ ] **Step 5: Home and year hub pages**

Create `front/src/routes/+page.server.js`:

```js
import { error } from '@sveltejs/kit';
import { apiGet } from '$lib/api';
import { api } from '$lib/server/urls';

/** The bare URL shows the latest edition's hub without changing the address. */
export const load = async ({ fetch, parent }) => {
	const { latestYear } = await parent();
	if (latestYear === null) error(404, 'No edition yet');
	const summary = await apiGet(fetch, api(`/edition/year/${latestYear}/summary/`));
	return { summary };
};
```

Replace `front/src/routes/+page.svelte`:

```svelte
<script>
	import EditionHub from '$lib/components/EditionHub.svelte';

	export let data;
</script>

<EditionHub summary={data.summary} editions={data.editions} />
```

Create `front/src/routes/[year=year]/+page.svelte` with the identical content:

```svelte
<script>
	import EditionHub from '$lib/components/EditionHub.svelte';

	export let data;
</script>

<EditionHub summary={data.summary} editions={data.editions} />
```

- [ ] **Step 6: Build and commit**

```bash
cd $WT/front && npm run build 2>&1 | tail -3
cd $WT && git add front/src/lib/components/EditionHub.svelte front/src/lib/components/EditionHub.test.js front/src/routes/+page.server.js front/src/routes/+page.svelte "front/src/routes/[year=year]/+page.svelte"
git commit -m "[FEAT] front: edition hub for / and /<year>

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Task 12: Global ranking page

**Files:**
- Create: `front/src/routes/[year=year]/ranking/+page.svelte`
- Create: `front/src/routes/[year=year]/ranking/page.test.js`
- Delete: `front/src/routes/ranking/+page.svelte`

- [ ] **Step 1: Write the failing test**

Create `front/src/routes/[year=year]/ranking/page.test.js`:

```js
import { render, screen, within } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import Page from './+page.svelte';
import { summary } from '$lib/fixtures/summary.js';

describe('ranking page', () => {
	it('lists teams in rank order with total points', () => {
		render(Page, { data: { summary } });

		const rows = screen.getAllByTestId('team-row');
		expect(rows).toHaveLength(3);
		expect(rows[0]).toHaveTextContent(/1\. Bisons\s*5 pts/);
		expect(rows[1]).toHaveTextContent(/2\. Aigles\s*3 pts/);
		expect(rows[2]).toHaveTextContent(/3\. Cerfs\s*2 pts/);
		expect(within(rows[0]).getByRole('link')).toHaveAttribute('href', '/2026/teams/2');
	});

	it('links revealed disciplines and disables hidden ones', () => {
		render(Page, { data: { summary } });

		const relay = screen.getByRole('link', { name: 'Relay' });
		expect(relay).toHaveAttribute('href', '/2026/disciplines/10');
		expect(relay).not.toHaveAttribute('aria-disabled');

		const orienteering = screen.getByRole('link', { name: 'Orienteering' });
		expect(orienteering).toHaveAttribute('aria-disabled', 'true');
	});
});
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd $WT/front && npm test
```

Expected: `Failed to resolve import "./+page.svelte"`.

- [ ] **Step 3: Write the page**

Create `front/src/routes/[year=year]/ranking/+page.svelte`:

```svelte
<script>
	import { iconFor } from '$lib/icons';
	import { rankedTeams } from '$lib/edition';

	export let data;

	$: year = data.summary.edition.year;
	$: teams = rankedTeams(data.summary);
	$: disciplines = data.summary.disciplines;
</script>

<div class="flex-box">
	<div id="disciplines">
		{#each disciplines as discipline}
			<a
				class="discipline-card"
				class:hidden={!discipline.reveal_score}
				href="/{year}/disciplines/{discipline.id}"
				aria-disabled={discipline.reveal_score ? undefined : 'true'}
				aria-label={discipline.name}
			>
				<img src={iconFor(discipline.name)} alt="" />
			</a>
		{/each}
	</div>

	<div id="teams">
		{#each teams as team}
			<div class="team-card" data-testid="team-row">
				<a href="/{year}/teams/{team.id}">{team.ranking}. {team.name}</a>
				<p>{team.total_points} pts</p>
			</div>
		{/each}
	</div>
</div>

<style>
	.flex-box {
		display: flex;
		flex-direction: column;
		gap: 20px;
	}

	#disciplines {
		display: flex;
		gap: clamp(5px, 3vw, 40px);
		margin: 0 clamp(10px, 4vw, 40px);
		overflow-x: auto;
		overflow-y: hidden;
		flex-wrap: nowrap;
		-ms-overflow-style: none;
		scrollbar-width: none;
	}

	#disciplines::-webkit-scrollbar {
		display: none;
	}

	.discipline-card {
		height: clamp(70px, 12vw, 100px);
		width: clamp(70px, 12vw, 100px);
		flex: none;
		border-radius: 50%;
		background-color: var(--color-theme-1);
		display: flex;
		justify-content: center;
		align-items: center;
		transition: 0.3s;
	}

	.discipline-card.hidden {
		opacity: 0.2;
		pointer-events: none;
	}

	.discipline-card img {
		height: 80%;
		width: 80%;
	}

	.discipline-card:hover {
		transform: translate(0, -4px);
	}

	#teams {
		display: flex;
		flex-direction: column;
		gap: 10px;
		margin: 0 1vw;
	}

	.team-card {
		background-color: var(--color-bg-0);
		border: 1px solid #ccc;
		border-radius: 10px;
		padding: 0 10px;
		box-shadow: 0 2px 4px #00000030;
		transition: 0.3s;
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.team-card a,
	.team-card p {
		font-size: 1rem;
		font-weight: 600;
		color: var(--color-theme-1);
		margin: 1em 0;
	}

	#teams .team-card:nth-of-type(1) {
		background: linear-gradient(45deg, #e6b800, #f2d06b, #e6b800, #e6ac00);
	}

	#teams .team-card:nth-of-type(2) {
		background: linear-gradient(45deg, #e0e0e0, #cfcfcf, #b0b0b0, #d1d1d1, #f7f7f7);
	}

	#teams .team-card:nth-of-type(3) {
		background: linear-gradient(45deg, #cd7f32, #b87333, #8c5311);
	}

	.team-card:hover {
		transform: translate(0, -4px);
	}

	@media (min-width: 1000px) {
		.flex-box {
			flex-direction: row;
			justify-content: center;
			gap: 20px;
			margin: 80px 0;
		}

		#teams {
			order: 1;
			width: min(65%, 800px);
		}

		#disciplines {
			order: 2;
			flex-direction: column;
			gap: 15px;
			overflow: visible;
		}

		.discipline-card {
			border-radius: 10px;
			height: 100px;
			width: 100px;
		}
	}
</style>
```

- [ ] **Step 4: Run the test to verify it passes, delete the old page**

```bash
cd $WT/front && npm test && cd $WT && git rm -q front/src/routes/ranking/+page.svelte
```

Expected: `Test Files 5 passed (5)`.

- [ ] **Step 5: Commit**

```bash
cd $WT && git add "front/src/routes/[year=year]/ranking"
git commit -m "[FEAT] front: year-scoped global ranking page

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Task 13: Disciplines list and discipline ranking page

**Files:**
- Create: `front/src/routes/[year=year]/disciplines/+page.svelte`
- Create: `front/src/routes/[year=year]/disciplines/[id]/+page.js`
- Create: `front/src/routes/[year=year]/disciplines/[id]/+page.svelte`
- Create: `front/src/routes/[year=year]/disciplines/[id]/page.test.js`
- Delete: `front/src/routes/disciplines/+page.svelte`, `front/src/routes/disciplines/[slug]/` (four files)

- [ ] **Step 1: Write the failing test**

Create `front/src/routes/[year=year]/disciplines/[id]/page.test.js`:

```js
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import Page from './+page.svelte';
import { disciplineResults, findDiscipline } from '$lib/edition';
import { summary, summaryAllRevealed } from '$lib/fixtures/summary.js';

const dataFor = (s, id) => ({
	summary: s,
	discipline: findDiscipline(s, id),
	results: disciplineResults(s, id)
});

describe('discipline page', () => {
	it('shows points rows with the difference for a revealed points discipline', () => {
		render(Page, { data: dataFor(summary, 10) });

		expect(screen.getByRole('heading', { name: 'Relay' })).toBeInTheDocument();
		const rows = screen.getAllByTestId('result-row');
		expect(rows).toHaveLength(3);
		expect(rows[0]).toHaveTextContent(/1\.\s*Bisons\s*10 pts \(\+4\)/);
		expect(rows[1]).toHaveTextContent(/2\.\s*Aigles\s*5 pts \(-2\)/);
		expect(rows[2]).toHaveTextContent(/3\.\s*Cerfs\s*0 pts \(-2\)/);
		expect(screen.getByRole('link', { name: 'Bisons' })).toHaveAttribute('href', '/2026/teams/2');
	});

	it('shows times for a revealed timed discipline', () => {
		render(Page, { data: dataFor(summaryAllRevealed, 11) });

		const rows = screen.getAllByTestId('result-row');
		expect(rows[0]).toHaveTextContent('1. Aigles');
		expect(rows[0]).toHaveTextContent('00:12:30');
	});

	it('shows the not-revealed message instead of rows', () => {
		render(Page, { data: dataFor(summary, 11) });

		expect(screen.getByText('Results not revealed yet')).toBeInTheDocument();
		expect(screen.queryAllByTestId('result-row')).toHaveLength(0);
	});
});
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd $WT/front && npm test
```

Expected: `Failed to resolve import "./+page.svelte"`.

- [ ] **Step 3: Write the discipline page and its load**

Create `front/src/routes/[year=year]/disciplines/[id]/+page.js`:

```js
import { error } from '@sveltejs/kit';
import { disciplineResults, findDiscipline } from '$lib/edition';

export const load = async ({ params, parent }) => {
	const { summary } = await parent();
	const discipline = findDiscipline(summary, Number(params.id));
	if (!discipline) error(404, 'Discipline not found');
	return { discipline, results: disciplineResults(summary, discipline.id) };
};
```

Create `front/src/routes/[year=year]/disciplines/[id]/+page.svelte`:

```svelte
<script>
	import { formatDifference } from '$lib/edition';

	export let data;

	$: year = data.summary.edition.year;
</script>

<h1>{data.discipline.name}</h1>

{#if data.results === null}
	<p class="hidden">Results not revealed yet</p>
{:else}
	<div id="results">
		{#each data.results as result}
			<div class="team-card" data-testid="result-row">
				<p>{result.ranking === null ? '—' : `${result.ranking}.`} <a href="/{year}/teams/{result.team}">{result.teamName}</a></p>
				{#if result.ranking === null}
					<p>—</p>
				{:else if result.result_type === 'TIM'}
					<p>{result.time}</p>
				{:else}
					<p>{result.points} pts ({formatDifference(result.points_difference)})</p>
				{/if}
			</div>
		{/each}
	</div>
{/if}

<style>
	.hidden {
		text-align: center;
		font-weight: 600;
		margin: 3rem 1rem;
	}

	#results {
		display: flex;
		flex-direction: column;
		gap: 10px;
		margin: 0 auto;
		width: min(98%, 800px);
	}

	.team-card {
		background-color: var(--color-bg-0);
		border: 1px solid #ccc;
		border-radius: 10px;
		padding: 0 10px;
		box-shadow: 0 2px 4px #00000030;
		transition: 0.3s;
		display: flex;
		justify-content: space-between;
	}

	.team-card a {
		color: inherit;
	}

	#results .team-card:nth-of-type(1) {
		background: linear-gradient(45deg, #e6b800, #f2d06b, #e6b800, #e6ac00);
	}

	#results .team-card:nth-of-type(2) {
		background: linear-gradient(45deg, #e0e0e0, #cfcfcf, #b0b0b0, #d1d1d1, #f7f7f7);
	}

	#results .team-card:nth-of-type(3) {
		background: linear-gradient(45deg, #cd7f32, #b87333, #8c5311);
	}

	.team-card:hover {
		transform: translate(0, -4px);
	}

	.team-card p {
		font-size: 1rem;
		font-weight: 600;
	}
</style>
```

- [ ] **Step 4: Write the disciplines list page**

Create `front/src/routes/[year=year]/disciplines/+page.svelte`:

```svelte
<script>
	import { iconFor } from '$lib/icons';

	export let data;

	$: year = data.summary.edition.year;
</script>

<h1>Disciplines</h1>
<div class="grid-container">
	{#each data.summary.disciplines as discipline}
		<a href="/{year}/disciplines/{discipline.id}">
			<div class="card">
				<img src={iconFor(discipline.name)} alt={discipline.name} />
				<h2>{discipline.name}</h2>
			</div>
		</a>
	{/each}
</div>

<style>
	h1 {
		visibility: hidden;
	}

	img {
		position: absolute;
		height: 90%;
		width: 50%;
		right: 0;
	}

	.grid-container {
		display: grid;
		width: min(90%, 1400px);
		grid-template-columns: repeat(auto-fill, minmax(500px, 1fr));
		gap: 16px;
		padding: 16px;
		margin: 0 auto;
	}

	.card {
		position: relative;
		height: 160px;
		background-color: var(--color-theme-1);
		border-radius: 8px;
		border: 2px solid #999999;
		padding: 16px;
		transition: 0.2s;
	}

	.card:hover {
		transform: translate(0, -4px);
	}

	h2 {
		color: var(--color-theme-2);
		font-size: 1.5rem;
		font-weight: 600;
	}

	a:hover {
		text-decoration: none;
	}

	@media (max-width: 1000px) {
		h1 {
			display: none;
		}
	}

	@media (max-width: 580px) {
		.grid-container {
			grid-template-columns: 1fr;
		}

		.card {
			height: 100px;
		}
	}
</style>
```

- [ ] **Step 5: Run the tests, delete the old pages, build**

```bash
cd $WT/front && npm test
cd $WT && git rm -q -r front/src/routes/disciplines/+page.svelte "front/src/routes/disciplines/[slug]"
cd $WT/front && npm run build 2>&1 | tail -3
```

Expected: `Test Files 6 passed (6)`, build `✓ built`.

- [ ] **Step 6: Commit**

```bash
cd $WT && git add "front/src/routes/[year=year]/disciplines"
git commit -m "[FEAT] front: year-scoped discipline pages, ranking gated by reveal_score

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Task 14: Teams list and team page

**Files:**
- Create: `front/src/routes/[year=year]/teams/+page.svelte`
- Create: `front/src/routes/[year=year]/teams/[id]/+page.js`
- Create: `front/src/routes/[year=year]/teams/[id]/+page.svelte`
- Create: `front/src/routes/[year=year]/teams/[id]/page.test.js`
- Delete: `front/src/routes/teams/+page.svelte`, `front/src/routes/teams/[slug]/` (two files)

- [ ] **Step 1: Write the failing test**

Create `front/src/routes/[year=year]/teams/[id]/page.test.js`:

```js
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import Page from './+page.svelte';
import { findTeam, teamResults } from '$lib/edition';
import { summary } from '$lib/fixtures/summary.js';

const dataFor = (id) => ({ summary, team: findTeam(summary, id), results: teamResults(summary, id) });

describe('team page', () => {
	it('shows the name, global rank, total points and the full roster', () => {
		render(Page, { data: dataFor(1) });

		expect(screen.getByRole('heading', { name: 'Aigles' })).toBeInTheDocument();
		expect(screen.getByText('2nd · 3 pts')).toBeInTheDocument();
		expect(screen.getByText('Ana Lopez')).toBeInTheDocument();
		expect(screen.getByText('Bob Martin')).toBeInTheDocument();
	});

	it('shows one row per discipline with a dash when not revealed', () => {
		render(Page, { data: dataFor(1) });

		const rows = screen.getAllByTestId('discipline-row');
		expect(rows).toHaveLength(2);
		expect(rows[0]).toHaveTextContent(/Relay\s*2\s*5 pts/);
		expect(rows[1]).toHaveTextContent(/Orienteering\s*—\s*—/);
	});
});
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd $WT/front && npm test
```

Expected: `Failed to resolve import "./+page.svelte"`.

- [ ] **Step 3: Write the team page and its load**

Create `front/src/routes/[year=year]/teams/[id]/+page.js`:

```js
import { error } from '@sveltejs/kit';
import { findTeam, teamResults } from '$lib/edition';

export const load = async ({ params, parent }) => {
	const { summary } = await parent();
	const team = findTeam(summary, Number(params.id));
	if (!team) error(404, 'Team not found');
	return { team, results: teamResults(summary, team.id) };
};
```

Create `front/src/routes/[year=year]/teams/[id]/+page.svelte`:

```svelte
<script>
	export let data;

	const ordinal = (n) => (n === 1 ? '1st' : n === 2 ? '2nd' : n === 3 ? '3rd' : `${n}th`);
</script>

<h1>{data.team.name}</h1>
<p class="standing">{ordinal(data.team.ranking)} · {data.team.total_points} pts</p>

<div class="players">
	{#each data.team.players as player}
		<div class="player-card">
			<p>{player.first_name} {player.last_name}</p>
		</div>
	{/each}
</div>

<table>
	<thead>
		<tr><th>Discipline</th><th>Rank</th><th>Result</th></tr>
	</thead>
	<tbody>
		{#each data.results as row}
			<tr data-testid="discipline-row">
				<td>{row.disciplineName}</td>
				{#if row.revealed}
					<td>{row.ranking}</td>
					<td>{row.result_type === 'TIM' ? row.time : `${row.points} pts`}</td>
				{:else}
					<td>—</td>
					<td>—</td>
				{/if}
			</tr>
		{/each}
	</tbody>
</table>

<style>
	.standing {
		text-align: center;
		font-weight: 600;
		margin: 0;
	}

	.players {
		display: flex;
		flex-wrap: wrap;
		justify-content: center;
		gap: 20px;
		margin: 20px 1rem;
	}

	.player-card {
		background: var(--color-theme-2);
		color: black;
		padding: 20px 40px;
		border-radius: 10px;
		width: 200px;
		text-align: center;
		box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
		transition: transform 0.3s;
	}

	.player-card p {
		font-size: 1.2rem;
		font-weight: 600;
		margin: 0;
	}

	.player-card:hover {
		transform: scale(1.05);
	}

	table {
		width: min(98%, 600px);
		margin: 2rem auto;
		border-collapse: collapse;
	}

	th,
	td {
		padding: 0.6rem 1rem;
		text-align: left;
		border-bottom: 1px solid #ccc;
	}

	th {
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.1em;
		font-size: 0.8rem;
	}
</style>
```

- [ ] **Step 4: Write the teams list page**

Create `front/src/routes/[year=year]/teams/+page.svelte`:

```svelte
<script>
	export let data;

	$: year = data.summary.edition.year;
	$: teams = [...data.summary.teams].sort((a, b) => a.name.localeCompare(b.name));
</script>

<h1>Teams</h1>
<div class="grid-container">
	{#each teams as team}
		<a href="/{year}/teams/{team.id}">
			<div class="card">
				<h2>{team.name}</h2>
				<div class="players">
					{#each team.players as player}
						<p>{player.first_name} {player.last_name}</p>
					{/each}
				</div>
			</div>
		</a>
	{/each}
</div>

<style>
	h1 {
		visibility: hidden;
	}

	a:hover {
		text-decoration: none;
	}

	.players {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-around;
	}

	.grid-container {
		display: grid;
		width: min(calc(100vw - 32px), 1000px);
		grid-template-columns: repeat(auto-fill, minmax(500px, 1fr));
		gap: 16px;
		padding: 16px;
		margin: 0 auto;
	}

	.card {
		background-color: var(--color-bg-0);
		border: 1px solid #ccc;
		border-radius: 8px;
		padding: 16px;
		box-shadow: 0 2px 4px #00000030;
		transition: 0.2s;
	}

	.card:hover {
		transform: translate(0, -4px);
	}

	h2 {
		font-size: 1.2rem;
		font-weight: 600;
	}

	p {
		margin: 5px;
	}

	@media (max-width: 700px) {
		.grid-container {
			grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
		}

		.players {
			flex-direction: column;
			align-items: center;
			margin: 0;
		}
	}

	@media (max-width: 1000px) {
		h1 {
			display: none;
		}
	}
</style>
```

- [ ] **Step 5: Run the tests, delete the old pages, build**

```bash
cd $WT/front && npm test
cd $WT && git rm -q -r front/src/routes/teams/+page.svelte "front/src/routes/teams/[slug]"
cd $WT/front && npm run build 2>&1 | tail -3
```

Expected: `Test Files 7 passed (7)`, build `✓ built`.

- [ ] **Step 6: Commit**

```bash
cd $WT && git add "front/src/routes/[year=year]/teams"
git commit -m "[FEAT] front: year-scoped teams pages with full rosters and results

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Task 15: Legacy redirects, login cleanup, dead code removal

**Files:**
- Rewrite: `front/src/routes/ranking/+page.server.js`, `front/src/routes/teams/+page.server.js`, `front/src/routes/disciplines/+page.server.js`
- Modify: `front/src/routes/login/+page.server.js`, `front/src/routes/login/+page.svelte`
- Delete: `front/src/routes/login/register.svelte`, `front/src/lib/utils.js`, `front/src/routes/profile/`, `front/src/routes/action/`, `front/src/routes/photos/`

- [ ] **Step 1: Legacy redirects**

Replace `front/src/routes/ranking/+page.server.js`:

```js
import { error, redirect } from '@sveltejs/kit';

export const load = async ({ parent }) => {
	const { latestYear } = await parent();
	if (latestYear === null) error(404, 'No edition yet');
	redirect(301, `/${latestYear}/ranking`);
};
```

Replace `front/src/routes/teams/+page.server.js`:

```js
import { error, redirect } from '@sveltejs/kit';

export const load = async ({ parent }) => {
	const { latestYear } = await parent();
	if (latestYear === null) error(404, 'No edition yet');
	redirect(301, `/${latestYear}/teams`);
};
```

Replace `front/src/routes/disciplines/+page.server.js`:

```js
import { error, redirect } from '@sveltejs/kit';

export const load = async ({ parent }) => {
	const { latestYear } = await parent();
	if (latestYear === null) error(404, 'No edition yet');
	redirect(301, `/${latestYear}/disciplines`);
};
```

- [ ] **Step 2: Login on the new helper**

Replace `front/src/routes/login/+page.server.js`:

```js
import { fail, redirect } from '@sveltejs/kit';
import { apiPost } from '$lib/api';
import { api } from '$lib/server/urls';

const setAuthToken = ({ cookies, token }) => {
	cookies.set('Authorization', `Bearer ${token}`, {
		httpOnly: true,
		secure: true,
		sameSite: 'strict',
		maxAge: 60 * 60 * 24 * 7, // 1 week
		path: '/'
	});
};

export const actions = {
	login: async ({ cookies, request, fetch }) => {
		const { username, password } = Object.fromEntries(await request.formData());

		const missing = {};
		if (!username) missing.username = true;
		if (!password) missing.password = true;
		if (Object.keys(missing).length > 0) {
			return fail(400, { missing, username });
		}

		let token;
		try {
			({ token } = await apiPost(fetch, api('/auth/token/'), { username, password }));
		} catch (err) {
			return fail(err?.status ?? 500, { username, error: err?.body?.message ?? 'Login failed' });
		}

		if (!token) {
			return fail(500, { username, error: 'Authentication failed: token not received' });
		}

		setAuthToken({ cookies, token });
		redirect(302, '/');
	}
};
```

Replace `front/src/routes/login/+page.svelte`:

```svelte
<script>
	import Login from './login.svelte';

	export let form;
</script>

<div class="login">
	<Login {form} />
</div>

<style>
	.login {
		position: relative;
	}

	@media (max-width: 1100px) {
		.login {
			margin-top: 2rem;
		}
	}
</style>
```

In `front/src/routes/login/login.svelte`, the username input reads `value={form?.email ?? ''}` and the missing check looks at `form.missing.email`; change both to `username` so the new action's fields line up:

```svelte
    {#if form?.missing && form?.missing.username}<p class="error" transition:slide={{ duration: 800, easing: quintOut }}>
        The username field is required
    </p>{/if}
    <input name="username" placeholder="Username" value={form?.username ?? ''}
           style="border-bottom: {(form?.missing && form?.missing.username) ? '#ff0000' : 'var(--color-theme-1)'} 2px solid;" autofocus>
```

- [ ] **Step 3: Delete dead files**

```bash
cd $WT && git rm -q -r front/src/routes/login/register.svelte front/src/lib/utils.js front/src/routes/profile front/src/routes/action front/src/routes/photos
```

- [ ] **Step 4: Confirm nothing references removed modules, then test and build**

```bash
cd $WT/front && grep -rn "utils\|requestAPI\|cleanString\|sections" src || echo "no stale references"
npm test && npm run build 2>&1 | tail -3
```

Expected: `no stale references`, `Test Files 7 passed (7)`, `✓ built`.

- [ ] **Step 5: Commit**

```bash
cd $WT && git add front/src/routes/ranking/+page.server.js front/src/routes/teams/+page.server.js front/src/routes/disciplines/+page.server.js front/src/routes/login
git commit -m "[CHORE] front: legacy redirects, login on the new helper, remove placeholders

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Task 16: Browser smoke check against the compose stack

**Files:** none (verification only). Fix anything found, commit as `[FIX]`.

The main compose stack mounts `$MAIN/server`, not the worktree, so the summary endpoint is not live there yet. Run a second server on port 3004 with the worktree code, and the front dev server natively.

- [ ] **Step 1: Migrate the dev database with the worktree code and start a server on 3004**

```bash
docker compose --project-directory $MAIN run --rm --no-deps -T -v "$WT/server:/server" server python manage.py migrate
docker compose --project-directory $MAIN run --rm --no-deps -d -p 3004:3003 -v "$WT/server:/server" -v "$MAIN/server/mediafiles:/server/mediafiles" --name ow-wt-server server python manage.py runserver 0.0.0.0:3003
curl -s http://localhost:3004/edition/year/2026/summary/ | head -c 300
```

Expected: the migration applies `0027`, and curl prints a JSON document starting with `{"edition":{"id":`. If curl prints `Edition not found`, use a year that exists: `curl -s http://localhost:3004/editions/`.

- [ ] **Step 2: Start the front against it**

```bash
printf 'API_URL=http://localhost:3004\n' > $WT/front/.env
```

Add to `$WT/.claude/launch.json` (create if missing):

```json
{
  "version": "0.0.1",
  "configurations": [
    {
      "name": "front-wt",
      "runtimeExecutable": "npm",
      "runtimeArgs": ["run", "dev", "--prefix", "front", "--", "--port", "5174"],
      "port": 5174
    }
  ]
}
```

Start it with the browser's `preview_start` on `front-wt`.

- [ ] **Step 3: Walk the pages in the built-in browser**

Check each and note anything off:

1. `/` shows the latest edition's hero, host and dates, the Ranking button (the 2026 event has passed), and year chips for the other editions.
2. Pick another year in the header select on `/<latest>/teams`: the URL becomes `/<other>/teams` and the team list changes.
3. `/<year>/ranking`: teams in rank order, hidden disciplines dimmed.
4. Click a dimmed discipline: nothing happens. Open a hidden discipline URL directly: "Results not revealed yet".
5. A revealed discipline: rows with points and difference or times; team names link to team pages.
6. A team page: full roster, table with dashes for hidden disciplines.
7. `/1999`: themed 404 with "No edition in 1999". `/<year>/teams/999999`: themed 404 "Team not found".
8. `/ranking`, `/teams`, `/disciplines` redirect to the latest year.
9. Mobile preset: hamburger opens, items include the year links' sections, header select still usable.
10. `/login` renders the form only; a wrong password shows "Unable to log in with provided credentials." from DRF.

- [ ] **Step 4: Stop the temporary server and restore the front env**

```bash
docker rm -f ow-wt-server
printf 'API_URL=http://localhost:3003\n' > $WT/front/.env
```

- [ ] **Step 5: Commit any fixes**

```bash
cd $WT && git add -A front/src && git commit -m "[FIX] front: smoke-check fixes

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

Skip the commit when there is nothing to fix.

---

## Task 17: Documentation

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update the commands section**

In `CLAUDE.md`, replace the line `Front (inside \`front/\`): \`npm run dev\`, \`npm run build\`, \`npm run preview\`. There is no \`check\` or \`lint\` script.` with:

```markdown
Front (inside `front/`): `npm run dev`, `npm run build`, `npm run preview`, `npm test` (Vitest + Testing Library, jsdom; tests live next to the code as `*.test.js`, fixtures in `src/lib/fixtures/`). There is no `check` or `lint` script.
```

Replace the sentence about CI (`CI (\`.github/workflows/test.yml\`) only runs pylint ...`) with:

```markdown
CI (`.github/workflows/test.yml`) has two jobs: `test` only runs pylint with `continue-on-error` and boots the compose stack (the Django migrate/test steps are commented out, so it is not a real gate), and `front` runs `npm test` and `npm run build`, which do gate.
```

- [ ] **Step 2: Update the "What this is" and API paragraphs**

In the opening description, change `SvelteKit 2 / Svelte 4 (plain JS, no TypeScript, no test/lint tooling)` to `SvelteKit 2 / Svelte 4 (plain JS, no TypeScript; Vitest tests, no lint)`.

In the **API** paragraph, after `Five edition/discipline read views carry \`@permission_classes([AllowAny])\` below \`@api_view\` and are public;` insert:

```markdown
so does `GET /edition/year/<year>/summary/`, the one endpoint the front reads: `{edition, disciplines, teams (with rosters, ranking, total_points), results}` for an active edition looked up by its unique `year`, with every score field of a discipline whose `reveal_score` is off returned as `null` (`EditionSummarySerializer` in `serializer.py`).
```

Add to the domain paragraph after `\`Edition\` owns \`Team\`s, ...`: `\`Edition.year\` is unique and is the key the front and the transfer commands use; \`Edition.photos_url\` is an optional external album link shown in the front header.`

- [ ] **Step 3: Rewrite the Frontend architecture section**

Replace the whole `## Frontend architecture` section with:

```markdown
## Frontend architecture

Every edition page lives under a four-digit year segment (`src/params/year.js`): `/2026`, `/2026/ranking`, `/2026/disciplines/<id>`, `/2026/teams/<id>`. `/` renders the latest edition's hub with the same `EditionHub` component as `/<year>`; the bare `/ranking`, `/teams` and `/disciplines` redirect to the latest year. All read pages are public.

Data loading is server-side and minimal: the root layout fetches `/editions/` (newest first, `latestYear`), and the `[year=year]` layout fetches `/edition/year/<year>/summary/` once; every page underneath reads `summary` via `parent()` and derives its rows with the pure helpers in `src/lib/edition.js` (`rankedTeams`, `disciplineResults`, `teamResults`, `editionPhase`, `countdownParts`, `switchYearPath`). Detail pages use a `+page.js` that resolves the id from the summary and throws a 404 when missing.

`src/lib/api.js` (`apiGet`/`apiPost`) throws SvelteKit `error(status, message)` on any non-2xx or network failure, so loads never check a return value; `src/routes/+error.svelte` renders those. `src/lib/server/urls.js` prefixes `API_URL` (`$env/static/private`, baked in at build time). Discipline icons are resolved by `src/lib/icons.js` from every SVG in `src/lib/img/icons/` (file stem = lowercased name without spaces or apostrophes, `default.svg` fallback), so a new discipline needs an icon there or shows the fallback.

Auth: the login form action posts to `/auth/token/` and stores `Authorization: Bearer <token>` in an httpOnly cookie. Nothing reads it yet; `/login` is out of the nav and kept for the future organiser tools.
```

- [ ] **Step 4: Commit**

```bash
cd $WT && git add CLAUDE.md
git commit -m "[DOCS] CLAUDE.md: edition-aware front, summary endpoint, front tests

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Task 18: Final verification and PR

- [ ] **Step 1: Full backend suite and front suite from a clean state**

```bash
docker compose --project-directory $MAIN run --rm --no-deps -T -v "$WT/server:/server" server python manage.py test
cd $WT/front && rm -rf .svelte-kit build && npm test && npm run build 2>&1 | tail -3
```

Expected: Django `OK`, Vitest `Test Files 7 passed (7)`, `✓ built`.

- [ ] **Step 2: Review the branch**

```bash
cd $WT && git log --oneline origin/dev..HEAD && git diff --stat origin/dev..HEAD | tail -1
```

Expected: about 15 commits, spec and plan included, no stray files (`git status` clean, no `front/.env`, no `server/dev.env`, no `server/logs` in the diff; all three are gitignored).

- [ ] **Step 3: Push and open the PR into `dev`**

```bash
cd $WT && git push -u origin claude/edition-aware-front
gh pr create --base dev --title "[FEAT] edition-aware frontend on a public summary endpoint" --body "$(cat <<'EOF'
## Summary
- `Edition.year` unique, optional `Edition.photos_url` (migration 0027)
- public `GET /edition/year/<year>/summary/`: edition, disciplines, teams with rosters, results, score fields nulled while `reveal_score` is off
- fix `getTeamResultsByEdition` (filtered on a non-existent field)
- front restructured under `/<year>/…` with a header year switcher, `/` as the latest edition's hub, all read pages public, throwing API helper and themed error page
- Vitest + Testing Library, `front` CI job

Spec: `docs/superpowers/specs/2026-09-22-edition-aware-frontend-design.md`

## After deploy
- `migrate` runs 0027
- set `photos_url` per edition in the admin

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Do not open a `dev` to `main` PR; promotion is Hugo's call.
