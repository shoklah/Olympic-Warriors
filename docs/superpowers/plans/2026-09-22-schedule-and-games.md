# Schedule and Games Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show each team-sport discipline's schedule (rounds, pairings, referee, score once played) on the discipline page and each team's games and refereeing duties on the team page, driven by two new arrays in the public summary and a new `Game.is_played` flag.

**Architecture:** `Game.is_played` (migration 0028 backfilling every existing game) is edited in place in the admin changelist. `EditionSummarySerializer` adds `rounds` and `games`; game scores are nulled while the discipline is unrevealed. Two pure helpers in `edition.js` turn those arrays into per-discipline and per-team views; the two pages render them.

**Tech Stack:** Django 4.2 + DRF, SvelteKit 2 / Svelte 4, Vitest + Testing Library.

**Spec:** `docs/superpowers/specs/2026-09-22-schedule-and-games-design.md`

---

## Working environment

Worktree `/Users/shoklah/Work/Playground/Olympic-Warriors/.claude/worktrees/schedule-games`, branch `claude/schedule-games` off `dev`. Never `git checkout` in the main checkout.

```bash
WT=/Users/shoklah/Work/Playground/Olympic-Warriors/.claude/worktrees/schedule-games
MAIN=/Users/shoklah/Work/Playground/Olympic-Warriors
cp $MAIN/server/dev.env $WT/server/dev.env && mkdir -p $WT/server/logs   # once
printf 'API_URL=http://localhost:3003\n' > $WT/front/.env                 # once
cd $WT/front && npm ci                                                    # once
```

Django commands run in the main stack's image with the worktree mounted:

```bash
docker compose --project-directory $MAIN run --rm --no-deps -T -v "$WT/server:/server" server python manage.py test olympic_warriors.tests.test_summary -v 2
```

Front commands run natively in `$WT/front` (Node 22). Commit messages use the repo's `[FEAT]`/`[FIX]`/`[TEST]`/`[DOCS]` prefixes and end with a blank line then `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

---

## File structure

| File | Change | Responsibility |
|---|---|---|
| `server/olympic_warriors/models/Discipline.py` | modify | `Game.is_played` |
| `server/olympic_warriors/migrations/0028_game_is_played.py` | create | field + backfill |
| `server/olympic_warriors/admin.py` | modify | `GameAdmin` list columns and in-place editing |
| `server/olympic_warriors/serializer.py` | modify | `SummaryRoundSerializer`, `SummaryGameSerializer`, two arrays in the summary |
| `server/olympic_warriors/tests/test_summary.py` | modify | fixture and cases for rounds and games |
| `front/src/lib/fixtures/summary.js` | modify | rounds and games |
| `front/src/lib/edition.js` | modify | `disciplineSchedule`, `teamGames` |
| `front/src/lib/edition.test.js` | modify | helper tests |
| `front/src/routes/[year=year]/disciplines/[id]/+page.js`, `+page.svelte`, `page.test.js` | modify | schedule section |
| `front/src/routes/[year=year]/teams/[id]/+page.js`, `+page.svelte`, `page.test.js` | modify | games section |
| `CLAUDE.md` | modify | docs |

---

## Task 1: `Game.is_played`, migration with backfill, admin

**Files:**
- Modify: `server/olympic_warriors/models/Discipline.py` (class `Game`)
- Create: `server/olympic_warriors/migrations/0028_game_is_played.py`
- Modify: `server/olympic_warriors/admin.py` (`GameAdmin`)
- Modify: `server/olympic_warriors/tests/test_summary.py`

- [ ] **Step 1: Write the failing tests.** Append to `test_summary.py` (add `Game, TeamSportRound, Darts` to the models import and `from django.contrib import admin as django_admin` to the top imports):

```python
class TestGameIsPlayed(TestCase):
    """A game starts unplayed; the admin edits the flag in the changelist."""

    def setUp(self):
        self.edition = Edition.objects.create(
            year=2026, host="Paris", start_date="2026-09-19", end_date="2026-09-20"
        )
        self.a = Team.objects.create(name="A", edition=self.edition)
        self.b = Team.objects.create(name="B", edition=self.edition)
        self.c = Team.objects.create(name="C", edition=self.edition)
        self.darts = Darts.objects.create(edition=self.edition, reveal_score=True)
        self.round = TeamSportRound.objects.create(discipline=self.darts, order=0)

    def test_defaults_to_not_played(self):
        game = Game.objects.create(
            discipline=self.darts, round=self.round, team1=self.a, team2=self.b,
            referees=self.c, edition=self.edition,
        )
        self.assertFalse(game.is_played)

    def test_admin_edits_is_played_in_the_changelist(self):
        game_admin = django_admin.site._registry[Game]
        self.assertIn("is_played", game_admin.list_display)
        self.assertEqual(list(game_admin.list_editable), ["score1", "score2", "is_played"])

    def test_backfill_marks_existing_games_played(self):
        migration = importlib.import_module("olympic_warriors.migrations.0028_game_is_played")

        game = Game.objects.create(
            discipline=self.darts, round=self.round, team1=self.a, team2=self.b,
            referees=self.c, edition=self.edition,
        )
        migration.mark_existing_games_played(apps, None)
        game.refresh_from_db()
        self.assertTrue(game.is_played)
```

Add `import importlib` and `from django.apps import apps` to the top imports. The data function lives in the migration file itself: a helper module inside `migrations/` would be loaded as a migration by Django and crash the loader.

- [ ] **Step 2: Run** `... test olympic_warriors.tests.test_summary.TestGameIsPlayed -v 2`. Expected: `TypeError: Game() got unexpected keyword` is NOT what fails first; `test_defaults_to_not_played` fails with `AttributeError: 'Game' object has no attribute 'is_played'`, the admin test fails on `assertIn`, the backfill test fails on the import.

- [ ] **Step 3: Model, helper, migration, admin.**

In `models/Discipline.py`, class `Game`, after `edition`:

```python
    is_played = models.BooleanField(default=False)
```

Generate the schema migration, then add the data step to it:

```bash
docker compose --project-directory $MAIN run --rm --no-deps -T -v "$WT/server:/server" server python manage.py makemigrations olympic_warriors -n game_is_played
```

Edit `0028_game_is_played.py` so it reads:

```python
from django.db import migrations, models


def mark_existing_games_played(apps, schema_editor):
    """Every edition in the database is over: games that exist were played."""
    Game = apps.get_model("olympic_warriors", "Game")
    Game.objects.update(is_played=True)


class Migration(migrations.Migration):

    dependencies = [
        ('olympic_warriors', '0027_edition_photos_url_unique_year'),
    ]

    operations = [
        migrations.AddField(
            model_name='game',
            name='is_played',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(mark_existing_games_played, migrations.RunPython.noop),
    ]
```

In `admin.py`, `GameAdmin`:

```python
    list_display = [
        "discipline",
        "team1",
        "score1",
        "score2",
        "team2",
        "is_played",
        "referees",
        "round",
        "edition",
    ]
    list_editable = ["score1", "score2", "is_played"]
```

- [ ] **Step 4: Run the module tests, then the full suite.** Expected OK. Note: `makemigrations --check` must report nothing pending afterwards.

- [ ] **Step 5: Commit** `[FEAT] game: is_played flag, editable in the admin changelist` with the model, `0028_game_is_played.py`, `admin.py`, `test_summary.py`.

---

## Task 2: Rounds and games in the summary

**Files:**
- Modify: `server/olympic_warriors/serializer.py`
- Modify: `server/olympic_warriors/tests/test_summary.py`

- [ ] **Step 1: Add a `ScheduleSetup` mixin** in `test_summary.py` right after `SummarySetup` (add `Petanque` to the models import). It is separate because `Game.save()` adds league points to the Darts results and would change the global rankings the existing `SummarySetup` tests assert:

```python
class ScheduleSetup(SummarySetup):
    """SummarySetup plus a revealed Darts schedule and a hidden Petanque game."""

    def setUp(self):
        super().setUp()
        # Team sport with a schedule: Darts, revealed, two rounds, three games.
        self.darts = Darts.objects.create(edition=self.edition, reveal_score=True)
        self.darts_r1 = TeamSportRound.objects.create(discipline=self.darts, order=0)
        self.darts_r2 = TeamSportRound.objects.create(discipline=self.darts, order=1)
        self.g1 = Game.objects.create(
            discipline=self.darts, round=self.darts_r1, team1=self.team_b, score1=12,
            team2=self.team_a, score2=9, referees=self.team_c, edition=self.edition,
            is_played=True,
        )
        self.g2 = Game.objects.create(
            discipline=self.darts, round=self.darts_r1, team1=self.team_c, score1=0,
            team2=self.team_b, score2=0, referees=self.team_a, edition=self.edition,
        )
        self.g3 = Game.objects.create(
            discipline=self.darts, round=self.darts_r2, team1=self.team_a, score1=7,
            team2=self.team_c, score2=7, referees=self.team_b, edition=self.edition,
            is_played=True,
        )
        # Hidden team sport: one round, one played game whose score must not leak.
        self.petanque = Petanque.objects.create(edition=self.edition, reveal_score=False)
        self.petanque_r1 = TeamSportRound.objects.create(discipline=self.petanque, order=0)
        self.g4 = Game.objects.create(
            discipline=self.petanque, round=self.petanque_r1, team1=self.team_a, score1=13,
            team2=self.team_b, score2=4, referees=self.team_c, edition=self.edition,
            is_played=True,
        )
```

No existing assertion changes: the classes below use `ScheduleSetup`, the existing ones keep `SummarySetup`.

- [ ] **Step 2: Write the failing tests.** Append a new class:

```python
class TestSummarySchedule(ScheduleSetup, TestCase):
    """Rounds and games in the summary; scores hidden until the discipline is revealed."""

    def test_rounds_in_discipline_and_order(self):
        rounds = self.summary()["rounds"]
        self.assertEqual(
            rounds,
            [
                {"id": self.darts_r1.id, "discipline": self.darts.id, "order": 0, "is_over": False},
                {"id": self.darts_r2.id, "discipline": self.darts.id, "order": 1, "is_over": False},
                {"id": self.petanque_r1.id, "discipline": self.petanque.id, "order": 0, "is_over": False},
            ],
        )

    def test_games_in_round_order_with_scores_when_revealed(self):
        games = [g for g in self.summary()["games"] if g["discipline"] == self.darts.id]
        self.assertEqual([g["id"] for g in games], [self.g1.id, self.g2.id, self.g3.id])
        self.assertEqual(
            games[0],
            {
                "id": self.g1.id,
                "discipline": self.darts.id,
                "round": self.darts_r1.id,
                "team1": self.team_b.id,
                "team2": self.team_a.id,
                "referees": self.team_c.id,
                "is_played": True,
                "score1": 12,
                "score2": 9,
            },
        )
        self.assertFalse(games[1]["is_played"])

    def test_hidden_discipline_game_keeps_pairing_but_not_scores(self):
        game = next(g for g in self.summary()["games"] if g["discipline"] == self.petanque.id)
        self.assertEqual((game["team1"], game["team2"], game["referees"]), (self.team_a.id, self.team_b.id, self.team_c.id))
        self.assertTrue(game["is_played"])
        self.assertIsNone(game["score1"])
        self.assertIsNone(game["score2"])

    def test_inactive_round_and_game_excluded(self):
        self.darts_r2.is_active = False
        self.darts_r2.save()
        Game.objects.filter(pk=self.g2.pk).update(is_active=False)
        data = self.summary()
        self.assertEqual([r["id"] for r in data["rounds"]], [self.darts_r1.id, self.petanque_r1.id])
        self.assertEqual([g["id"] for g in data["games"]], [self.g1.id, self.g4.id])
```

- [ ] **Step 3: Run** `... test olympic_warriors.tests.test_summary -v 2`. Expected: the four new tests fail with `KeyError: 'rounds'` / `'games'`; every existing test still passes.

- [ ] **Step 4: Serializers.** In `serializer.py`, add `TeamSportRound, Game` to the models import if missing (they are), then insert before `EditionSummarySerializer`:

```python
class SummaryRoundSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeamSportRound
        fields = ("id", "discipline", "order", "is_over")


class SummaryGameSerializer(serializers.ModelSerializer):
    """
    A scheduled game. Pairings, referee and the played flag are always visible;
    the scores are null while the discipline's reveal_score is off.
    """

    score1 = serializers.IntegerField(read_only=True, allow_null=True)
    score2 = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = Game
        fields = (
            "id",
            "discipline",
            "round",
            "team1",
            "team2",
            "referees",
            "is_played",
            "score1",
            "score2",
        )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not instance.discipline.reveal_score:
            data["score1"] = None
            data["score2"] = None
        return data
```

In `EditionSummarySerializer`: declare `rounds = SummaryRoundSerializer(many=True)` and `games = SummaryGameSerializer(many=True)`, update the docstring, and in `to_representation` add:

```python
        rounds = TeamSportRound.objects.filter(
            discipline__edition=instance, discipline__is_active=True, is_active=True
        ).order_by("discipline_id", "order")
        games = (
            Game.objects.filter(
                discipline__edition=instance,
                discipline__is_active=True,
                round__is_active=True,
                team1__is_active=True,
                team2__is_active=True,
                is_active=True,
            )
            .select_related("discipline", "round")
            .order_by("round__order", "id")
        )
```

and two keys in the returned dict: `"rounds": SummaryRoundSerializer(rounds, many=True).data`, `"games": SummaryGameSerializer(games, many=True).data`.

- [ ] **Step 5: Run the module tests and the full suite.** Expected OK. Also `test_public_without_token` in `TestEditionSummaryEndpoint` asserts the key set: update it to `{"edition", "disciplines", "teams", "results", "rounds", "games"}`.

- [ ] **Step 6: Commit** `[FEAT] summary: rounds and games, scores hidden until revealed`.

---

## Task 3: Fixture and helpers

**Files:**
- Modify: `front/src/lib/fixtures/summary.js`
- Modify: `front/src/lib/edition.js`
- Modify: `front/src/lib/edition.test.js`

- [ ] **Step 1: Fixture.** In `summary`, after `results`, add:

```js
	rounds: [
		{ id: 20, discipline: 10, order: 0, is_over: true },
		{ id: 21, discipline: 10, order: 1, is_over: false },
		{ id: 22, discipline: 11, order: 0, is_over: false }
	],
	games: [
		{ id: 200, discipline: 10, round: 20, team1: 2, team2: 1, referees: 3, is_played: true, score1: 12, score2: 9 },
		{ id: 201, discipline: 10, round: 20, team1: 3, team2: 2, referees: 1, is_played: false, score1: 0, score2: 0 },
		{ id: 202, discipline: 10, round: 21, team1: 1, team2: 3, referees: 2, is_played: true, score1: 7, score2: 7 },
		{ id: 203, discipline: 11, round: 22, team1: 1, team2: 2, referees: 3, is_played: true, score1: null, score2: null }
	]
```

In `summaryAllRevealed`, add `games: [...summary.games.slice(0, 3), { ...summary.games[3], score1: 3, score2: 1 }]`.

- [ ] **Step 2: Failing tests.** Append to `edition.test.js` (import `disciplineSchedule, teamGames`):

```js
describe('disciplineSchedule', () => {
	it('groups games by round in order with names joined', () => {
		const rounds = disciplineSchedule(summary, 10);
		expect(rounds.map((r) => [r.order, r.isOver, r.games.length])).toEqual([
			[0, true, 2],
			[1, false, 1]
		]);
		expect(rounds[0].games[0]).toEqual({
			id: 200,
			team1Id: 2,
			team1Name: 'Bisons',
			team2Id: 1,
			team2Name: 'Aigles',
			refereeName: 'Cerfs',
			isPlayed: true,
			score1: 12,
			score2: 9
		});
	});

	it('keeps null scores for an unrevealed discipline', () => {
		const [round] = disciplineSchedule(summary, 11);
		expect(round.games[0]).toMatchObject({ team1Name: 'Aigles', team2Name: 'Bisons', isPlayed: true, score1: null, score2: null });
	});

	it('is null for a discipline without rounds', () => {
		expect(disciplineSchedule({ ...summary, rounds: [], games: [] }, 10)).toBeNull();
		expect(disciplineSchedule(summary, 999)).toBeNull();
	});

	it('names an unknown team Unknown', () => {
		const odd = { ...summary, games: [{ ...summary.games[0], referees: 42 }] };
		expect(disciplineSchedule(odd, 10)[0].games[0].refereeName).toBe('Unknown');
	});
});

describe('teamGames', () => {
	it('lists play and referee rows per discipline, own score first', () => {
		const [relay, orienteering] = teamGames(summary, 1);
		expect(relay.disciplineName).toBe('Relay');
		expect(relay.games).toEqual([
			{ id: 200, round: 0, role: 'play', opponentId: 2, opponentName: 'Bisons', team1Name: 'Bisons', team2Name: 'Aigles', isPlayed: true, ownScore: 9, theirScore: 12, result: 'loss' },
			{ id: 201, round: 0, role: 'referee', opponentId: null, opponentName: null, team1Name: 'Cerfs', team2Name: 'Bisons', isPlayed: false, ownScore: null, theirScore: null, result: null },
			{ id: 202, round: 1, role: 'play', opponentId: 3, opponentName: 'Cerfs', team1Name: 'Aigles', team2Name: 'Cerfs', isPlayed: true, ownScore: 7, theirScore: 7, result: 'draw' }
		]);
		expect(orienteering.games[0]).toMatchObject({ role: 'play', opponentName: 'Bisons', isPlayed: true, ownScore: null, result: null });
	});

	it('reports a win and an unplayed game', () => {
		const [relay] = teamGames(summary, 2);
		expect(relay.games.map((g) => [g.role, g.isPlayed, g.result])).toEqual([
			['play', true, 'win'],
			['play', false, null],
			['referee', true, null]
		]);
	});

	it('omits disciplines where the team has no game', () => {
		const none = { ...summary, games: summary.games.filter((g) => g.discipline !== 11) };
		expect(teamGames(none, 3).map((d) => d.disciplineName)).toEqual(['Relay']);
	});
});
```

- [ ] **Step 3: Run `npm test`.** Expected: the new describes fail on missing exports.

- [ ] **Step 4: Helpers.** Append to `edition.js`:

```js
const teamNames = (summary) => new Map(summary.teams.map((t) => [t.id, t.name]));
const nameOf = (names, id) => names.get(id) ?? 'Unknown';

/**
 * Rounds of a discipline in order, each with its games and team names joined.
 * Null when the discipline has no round. Scores are null while unrevealed.
 */
export function disciplineSchedule(summary, disciplineId) {
	const rounds = summary.rounds.filter((r) => r.discipline === disciplineId);
	if (rounds.length === 0) return null;
	const names = teamNames(summary);
	return [...rounds]
		.sort((a, b) => a.order - b.order)
		.map((round) => ({
			order: round.order,
			isOver: round.is_over,
			games: summary.games
				.filter((g) => g.round === round.id)
				.map((g) => ({
					id: g.id,
					team1Id: g.team1,
					team1Name: nameOf(names, g.team1),
					team2Id: g.team2,
					team2Name: nameOf(names, g.team2),
					refereeName: nameOf(names, g.referees),
					isPlayed: g.is_played,
					score1: g.score1,
					score2: g.score2
				}))
		}));
}

function gameResult(own, theirs) {
	if (own === null || theirs === null) return null;
	if (own > theirs) return 'win';
	if (own < theirs) return 'loss';
	return 'draw';
}

/**
 * Every game a team plays or referees, grouped by discipline in id order,
 * with the team's own score first. Disciplines without a game are omitted.
 */
export function teamGames(summary, teamId) {
	const names = teamNames(summary);
	const roundOrder = new Map(summary.rounds.map((r) => [r.id, r.order]));
	return summary.disciplines
		.map((discipline) => ({
			disciplineId: discipline.id,
			disciplineName: discipline.name,
			games: summary.games
				.filter(
					(g) =>
						g.discipline === discipline.id &&
						(g.team1 === teamId || g.team2 === teamId || g.referees === teamId)
				)
				.map((g) => {
					const plays = g.team1 === teamId || g.team2 === teamId;
					const isTeam1 = g.team1 === teamId;
					const opponentId = plays ? (isTeam1 ? g.team2 : g.team1) : null;
					const ownScore = plays ? (isTeam1 ? g.score1 : g.score2) : null;
					const theirScore = plays ? (isTeam1 ? g.score2 : g.score1) : null;
					return {
						id: g.id,
						round: roundOrder.get(g.round) ?? 0,
						role: plays ? 'play' : 'referee',
						opponentId,
						opponentName: opponentId === null ? null : nameOf(names, opponentId),
						team1Name: nameOf(names, g.team1),
						team2Name: nameOf(names, g.team2),
						isPlayed: g.is_played,
						ownScore,
						theirScore,
						result: plays && g.is_played ? gameResult(ownScore, theirScore) : null
					};
				})
				.sort((a, b) => a.round - b.round || a.id - b.id)
		}))
		.filter((d) => d.games.length > 0);
}
```

- [ ] **Step 5: Run `npm test`.** Expected all green (existing tests untouched by the fixture growth: they read `results`, `teams`, `disciplines` only).

- [ ] **Step 6: Commit** `[FEAT] front: schedule and team games helpers`.

---

## Task 4: Discipline page schedule

**Files:**
- Modify: `front/src/routes/[year=year]/disciplines/[id]/+page.js`, `+page.svelte`, `page.test.js`

- [ ] **Step 1: Failing test.** In `page.test.js`, extend `dataFor` with `schedule: disciplineSchedule(s, id)` (import it) and add:

```js
	it('shows the schedule by round with scores, dashes and referees', () => {
		render(Page, { data: dataFor(summary, 10) });

		expect(screen.getByRole('heading', { name: 'Schedule' })).toBeInTheDocument();
		expect(screen.getByRole('heading', { name: 'Round 1' })).toBeInTheDocument();
		const games = screen.getAllByTestId('game-row');
		expect(games).toHaveLength(3);
		expect(games[0]).toHaveTextContent(/Bisons\s*12 – 9\s*Aigles/);
		expect(games[0]).toHaveTextContent('ref: Cerfs');
		expect(games[1]).toHaveTextContent(/Cerfs\s*—\s*Bisons/);
		expect(games[2]).toHaveTextContent(/Aigles\s*7 – 7\s*Cerfs/);
	});

	it('shows pairings without scores for an unrevealed discipline', () => {
		render(Page, { data: dataFor(summary, 11) });

		expect(screen.getByText('Results not revealed yet')).toBeInTheDocument();
		expect(screen.getAllByTestId('game-row')[0]).toHaveTextContent(/Aigles\s*—\s*Bisons/);
	});

	it('has no schedule section for a discipline without rounds', () => {
		render(Page, { data: dataFor({ ...summary, rounds: [], games: [] }, 10) });
		expect(screen.queryByRole('heading', { name: 'Schedule' })).toBeNull();
	});
```

Rounds are numbered from 1 in the UI (`order + 1`).

- [ ] **Step 2: Run `npm test`.** Expected: the three new cases fail.

- [ ] **Step 3: Load and page.** `+page.js`:

```js
import { error } from '@sveltejs/kit';
import { disciplineResults, disciplineSchedule, findDiscipline } from '$lib/edition';

export const load = async ({ params, parent }) => {
	const { summary } = await parent();
	const discipline = findDiscipline(summary, Number(params.id));
	if (!discipline) error(404, 'Discipline not found');
	return {
		discipline,
		results: disciplineResults(summary, discipline.id),
		schedule: disciplineSchedule(summary, discipline.id)
	};
};
```

In `+page.svelte`, after the `{/if}` that closes the results block, add:

```svelte
{#if data.schedule !== null}
	<section class="schedule">
		<h2>Schedule</h2>
		{#each data.schedule as round}
			<h3>Round {round.order + 1}</h3>
			{#each round.games as game}
				<div class="game" data-testid="game-row">
					<p class="teams">
						<a href="/{year}/teams/{game.team1Id}">{game.team1Name}</a>
						<span class="score">{game.isPlayed && game.score1 !== null ? `${game.score1} – ${game.score2}` : '—'}</span>
						<a href="/{year}/teams/{game.team2Id}">{game.team2Name}</a>
					</p>
					<p class="referee">ref: {game.refereeName}</p>
				</div>
			{/each}
		{/each}
	</section>
{/if}
```

and styles:

```css
	.schedule {
		width: min(98%, 800px);
		margin: 2rem auto;
	}

	.schedule h2 {
		font-size: 1.3rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.1em;
	}

	.schedule h3 {
		font-size: 1rem;
		font-weight: 700;
		margin: 1.5rem 0 0.5rem;
	}

	.game {
		border: 1px solid #ccc;
		border-radius: 10px;
		padding: 0.6rem 10px;
		margin-bottom: 8px;
	}

	.game .teams {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 1rem;
		margin: 0;
		font-weight: 600;
	}

	.game .teams a {
		color: inherit;
		flex: 1;
	}

	.game .teams a:last-child {
		text-align: right;
	}

	.game .score {
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}

	.game .referee {
		margin: 0.2rem 0 0;
		font-size: 0.85rem;
		opacity: 0.7;
	}
```

- [ ] **Step 4: Run `npm test`, then `npm run build`.** Expected green.
- [ ] **Step 5: Commit** `[FEAT] front: schedule by round on the discipline page`.

---

## Task 5: Team page games

**Files:**
- Modify: `front/src/routes/[year=year]/teams/[id]/+page.js`, `+page.svelte`, `page.test.js`

- [ ] **Step 1: Failing test.** In `page.test.js`, extend `dataFor` with `games: teamGames(summary, id)` and add:

```js
	it('lists games per discipline with result, to play and referee rows', () => {
		render(Page, { data: dataFor(1) });

		expect(screen.getByRole('heading', { name: 'Games' })).toBeInTheDocument();
		const rows = screen.getAllByTestId('game-row');
		expect(rows).toHaveLength(4);
		expect(rows[0]).toHaveTextContent(/Round 1 · vs Bisons · 9 – 12 · lost/);
		expect(rows[1]).toHaveTextContent(/Round 1 · referee · Cerfs vs Bisons/);
		expect(rows[2]).toHaveTextContent(/Round 2 · vs Cerfs · 7 – 7 · draw/);
		expect(rows[3]).toHaveTextContent(/Round 1 · vs Bisons · played/);
	});

	it('says to play for an unplayed game', () => {
		render(Page, { data: dataFor(2) });
		expect(screen.getAllByTestId('game-row')[1]).toHaveTextContent(/Round 1 · vs Cerfs · to play/);
	});
```

The last Aigles row is the hidden Orienteering game: played, scores null, so it reads `played` without a score.

- [ ] **Step 2: Run `npm test`.** Expected: the two cases fail.

- [ ] **Step 3: Load and page.** `+page.js`:

```js
import { error } from '@sveltejs/kit';
import { findTeam, teamGames, teamResults } from '$lib/edition';

export const load = async ({ params, parent }) => {
	const { summary } = await parent();
	const team = findTeam(summary, Number(params.id));
	if (!team) error(404, 'Team not found');
	return { team, results: teamResults(summary, team.id), games: teamGames(summary, team.id) };
};
```

In `+page.svelte`, after the `</table>`, add:

```svelte
{#if data.games.length > 0}
	<section class="games">
		<h2>Games</h2>
		{#each data.games as discipline}
			<h3>{discipline.disciplineName}</h3>
			<ul>
				{#each discipline.games as game}
					<li data-testid="game-row">
						{#if game.role === 'referee'}
							Round {game.round + 1} · referee · {game.team1Name} vs {game.team2Name}
						{:else if !game.isPlayed}
							Round {game.round + 1} · vs {game.opponentName} · to play
						{:else if game.result === null}
							Round {game.round + 1} · vs {game.opponentName} · played
						{:else}
							Round {game.round + 1} · vs {game.opponentName} · {game.ownScore} – {game.theirScore} · {game.result === 'win' ? 'won' : game.result === 'loss' ? 'lost' : 'draw'}
						{/if}
					</li>
				{/each}
			</ul>
		{/each}
	</section>
{/if}
```

Styles:

```css
	.games {
		width: min(98%, 600px);
		margin: 2rem auto;
	}

	.games h2 {
		font-size: 1.3rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.1em;
	}

	.games h3 {
		font-size: 1rem;
		font-weight: 700;
		margin: 1.5rem 0 0.5rem;
	}

	.games ul {
		margin: 0;
	}

	.games li {
		padding: 0.5rem 0;
		border-bottom: 1px solid #ccc;
		font-variant-numeric: tabular-nums;
	}
```

- [ ] **Step 4: Run `npm test`, `npm run build`.** Expected green.
- [ ] **Step 5: Commit** `[FEAT] front: games and refereeing duties on the team page`.

---

## Task 6: Smoke check, docs, PR

- [ ] **Step 1: Smoke** as in the previous plan: temporary server on 3004 with the worktree mounted (migrate first, which backfills `is_played` on the dev database), `front/.env` pointing at it, dev server on 5174 via a `launch.json` in the main checkout (delete afterwards). Check `/2026/disciplines/<rugby id>` shows five rounds of games with scores, `/2026/teams/<id>` shows won/lost rows and referee rows, an unrevealed discipline shows dashes, and the admin game changelist has the editable `is_played` column.
- [ ] **Step 2: CLAUDE.md.** Domain paragraph: `Game.is_played` is set by hand in the admin changelist (`list_editable`), the schedulers create games unplayed, migration 0028 marked every existing game played. Summary paragraph: `rounds` and `games` arrays, scores null until revealed. Front helpers list: `disciplineSchedule`, `teamGames`.
- [ ] **Step 3: Full suites** (Django, `npm test` under `TZ=UTC`, `npm run build`), push, `gh pr create --base dev` with a summary, the deploy note (`migrate` applies 0028) and the Co-Authored-By footer.
