# Player Discipline Places Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Profiles show the player's places per discipline across editions and a best-discipline card.

**Architecture:**
- `compute_standings` exposes each team's discipline standings (no new query).
- `profiles.py` builds `DisciplinePlaces` per person from their counted participations, ordered and positioned by the medal-table key shared with the leaderboard.
- `/profile/<id>/` carries `disciplines`.
- The profile page renders a best-discipline card and a « Par épreuve » section.

**Tech Stack:** Django 4.2 + DRF (tests in the compose `server` container), SvelteKit 2 / Svelte 4, Vitest.

**Spec:** `docs/superpowers/specs/2026-09-24-player-discipline-places-design.md`.

---

## Rules for whoever executes this

- Branch `claude/player-discipline-places`, main checkout `/Users/shoklah/Work/Playground/Olympic-Warriors`. Never switch branches, never `git stash`, never push, never `git add -A`.
- **The local dev database holds real data.** Never run `manage.py shell`, `runscript`, `loaddata`, `import_edition`, raw SQL, or anything else that can write to it. Experiments go in a throwaway `TestCase`, deleted afterwards.
- Django tests: `docker compose exec -T server python manage.py test <path> --noinput`. Always pass `--noinput`: it drops only the separate test database.
- Front: `cd front && npx vitest run <path>`, `npm test`, `npm run build`.
- Test-first: write the tests, see them fail for the right reason, implement, see them pass, commit. Commit messages end with a `Co-Authored-By` line.

---

### Task 1: Server, discipline standings and discipline places

**Files:**
- Modify: `server/olympic_warriors/standings.py`, `server/olympic_warriors/profiles.py`, `server/olympic_warriors/serializer.py` (`ProfileSerializer`, new `DisciplinePlacesSerializer`)
- Modify: `server/olympic_warriors/tests/test_standings.py`, `server/olympic_warriors/tests/test_profiles.py`

- [ ] **Step 1: Write the failing tests**

**`test_standings.py`**, add to `TestTeamStandings`:

```python
    def test_disciplines_of_a_team_carry_names_and_standings(self):
        self.play(self.team_a, 5, self.team_b, 2)
        relay = Relay.objects.create(edition=self.edition, reveal_score=True)
        TeamResult.objects.filter(discipline=relay, team=self.team_b).update(points=1)
        standings = compute_standings(self.edition)

        b = {d.discipline_name: d for d in standings.disciplines_of(self.team_b.id)}

        self.assertEqual(set(b), {"Darts", "Relay"})
        self.assertEqual(b["Relay"].standing.ranking, 1)
        self.assertEqual(b["Relay"].discipline_id, relay.id)
        self.assertEqual(b["Darts"].standing.ranking, 2)
        self.assertEqual(standings.disciplines_of(self.ghost.id), ())  # inactive team
        self.assertEqual(standings.disciplines_of(999999), ())
```

This works because `StandingsSetup` creates a revealed `Darts` discipline, and the existing `test_runs_in_three_queries` keeps pinning 3 queries. Check the discipline's `name` values in the models (`Darts`, `Relay`).

**`test_profiles.py`:**
- Import `DisciplinePlace` and `DisciplinePlaces` from `olympic_warriors.profiles`.
- Add a class `TestDisciplinePlaces(ProfilesSetup, TestCase)`:

```python
class TestDisciplinePlaces(ProfilesSetup, TestCase):
    """
    On top of ProfilesSetup's revealed 2025 Relay (Loups 1, Ours 2, Pumas 3): a revealed
    2024 Relay (Bisons 1, Aigles 2, Cerfs 3, Daims 4), a revealed 2024 Darts (Aigles 1),
    a hidden 2025 Darts, and a revealed 2026 Darts in the running edition.
    """

    def setUp(self):
        super().setUp()
        relay = Relay.objects.create(edition=self.y2024, reveal_score=True)
        for team, points in [(self.bisons, 8), (self.aigles, 5), (self.cerfs, 1), (self.daims, 0)]:
            TeamResult.objects.filter(discipline=relay, team=team).update(points=points)
        darts = Darts.objects.create(edition=self.y2024, reveal_score=True)
        for team, points in [(self.aigles, 9), (self.bisons, 4), (self.cerfs, 2), (self.daims, 1)]:
            TeamResult.objects.filter(discipline=darts, team=team).update(points=points)
        hidden = Darts.objects.create(edition=self.y2025, reveal_score=False)
        TeamResult.objects.filter(discipline=hidden, team=self.loups).update(points=9)
        running = Darts.objects.create(edition=self.y2026, reveal_score=True)
        TeamResult.objects.filter(discipline=running, team=self.renards).update(points=9)

    def disciplines(self, first_name):
        record = next(r for r in leaderboard(TODAY) if r.first_name == first_name)
        return [
            (d.name, d.position, [(p.year, p.rank) for p in d.places]) for d in record.disciplines
        ]

    def test_places_aggregate_by_name_best_first_and_order_like_a_medal_table(self):
        # Ana: Relay 1st in 2025 and 2nd in 2024, Darts 1st in 2024 (the hidden 2025 Darts
        # and the running 2026 Darts give nothing). Relay has an extra lower place: first.
        self.assertEqual(
            self.disciplines("Ana"),
            [("Relay", 1, [(2025, 1), (2024, 2)]), ("Darts", 2, [(2024, 1)])],
        )

    def test_bob_places(self):
        # Bob: Relay 1st in 2024 and 2nd in 2025; Darts 2nd in 2024.
        self.assertEqual(
            self.disciplines("Bob"),
            [("Relay", 1, [(2024, 1), (2025, 2)]), ("Darts", 2, [(2024, 2)])],
        )

    def test_identical_places_share_a_position_listed_by_name(self):
        # Dan (Cerfs 2024): Relay 3rd and Darts 3rd: tied, listed by name.
        self.assertEqual(
            self.disciplines("Dan"), [("Darts", 1, [(2024, 3)]), ("Relay", 1, [(2024, 3)])]
        )

    def test_no_counted_participation_means_no_disciplines(self):
        self.assertEqual(self.disciplines("Eve"), [])  # 2026 is running
        self.assertEqual(self.disciplines("Fay"), [])  # no team in 2024

    def test_query_budget_is_unchanged(self):
        with self.assertNumQueries(PROFILES_QUERIES):
            leaderboard(TODAY)
```

(`Darts` must be imported from `olympic_warriors.models`.)

- In `TestProfileEndpoints.test_profile_lists_every_edition_newest_first`, Ana's payload now has `"disciplines": [{"name": "Relay", "position": 1, "places": [{"year": 2025, "rank": 1}]}]`. That is ProfilesSetup's 2025 Relay only; Ana's 2024 Aigles have no discipline in the base setup. Assert it, and keep the other keys.
- In `test_profile_without_a_team_or_a_counted_edition`, assert that Fay's `disciplines` is `[]`.
- Assert that the `/profiles/` rows don't carry `disciplines`.

Run: `docker compose exec -T server python manage.py test olympic_warriors.tests.test_standings olympic_warriors.tests.test_profiles --noinput` and check that they fail (missing attributes and imports).

- [ ] **Step 2: Implement `standings.py`**
- Import `field` from `dataclasses`.
- Add the `DisciplineStanding` dataclass, with a docstring.
- Give `Standings` the new field `by_team: dict[int, tuple[DisciplineStanding, ...]] = field(default_factory=dict)` and a method `disciplines_of(team_id)` that returns `self.by_team.get(team_id, ())`, with a docstring.
- In `compute_standings`, once `result_standings` is known, build `by_team` from `results`: for each result, sorted by `(discipline_id, id)`, append `DisciplineStanding(result.discipline_id, result.discipline.name, result_standings[result.id])` under `result.team_id`. Convert the lists to tuples, pass the result to `Standings(...)`, and update the module docstring in one line.

- [ ] **Step 3: Implement `profiles.py`**
- **New dataclasses** (frozen, with docstrings):
  - `DisciplinePlace(name: str, year: int, rank: int)`;
  - `DisciplinePlaces(name: str, places: tuple[DisciplinePlace, ...], position: int)`.
- **`Participation`** gains a last field `disciplines: tuple[DisciplinePlace, ...] = ()`. Existing positional constructions keep working.
- **`participations()`:**
  - When a participation gets a rank (`team is not None and edition_id in ranked`), also collect `tuple(DisciplinePlace(d.discipline_name, edition.year, d.standing.ranking) for d in standings[edition_id].disciplines_of(team.id) if d.standing.ranking > 0)`.
  - Only a participation that `counts` should carry them. Build the `Participation` first, then `replace(part, disciplines=...)` when `part.counts`, or compute `teams >= 2` before building.
- **Medal key:** generalise it to `_medal_key(ranks)`, taking an iterable of ints: `(*ranks, math.inf)`. The leaderboard calls it with `(p.rank for p in record.places)`.
- **`_discipline_places(counted_parts)`:**
  - Group the places by name.
  - Sort each group best first: key `(rank, -year)`.
  - Order the groups by `(_medal_key(ranks), _sort_key(name))`.
  - Assign shared positions: the same key means the same position, reusing the pattern `_place` uses.
  - Return a tuple of `DisciplinePlaces`.
- **`PlayerRecord`** gains `disciplines: tuple[DisciplinePlaces, ...] = ()`, filled in `_record`.
- Update the module docstring with the discipline rule in one or two lines.

- [ ] **Step 4: Serializer**

In `serializer.py`:
- Add `DisciplinePlacesSerializer` (`name` CharField, `position` IntegerField, `places = PlaceSerializer(many=True)`), with a docstring.
- `PlaceSerializer` already has `year` and `rank`, which `DisciplinePlace` provides.
- `ProfileSerializer` gains `disciplines = DisciplinePlacesSerializer(many=True)`.
- `LeaderboardRowSerializer` is unchanged.

- [ ] **Step 5: Run and commit**

Run `docker compose exec -T server python manage.py test --noinput`; the whole suite must pass. Commit with `[ADD] profiles: places per discipline across editions, ordered like a medal table` and a Co-Authored-By line.

---

### Task 2: Front, best-discipline card and « Par épreuve » section

**Files:**
- Modify: `front/src/lib/players.js` and `players.test.js` (`bestDisciplines`)
- Modify: `front/src/lib/i18n/fr.js` and `en.js`
- Modify: `front/src/lib/fixtures/players.js` (`profile`, `profileUnranked`)
- Modify: `front/src/routes/players/[id]/+page.svelte` and `page.test.js`

- [ ] **Step 1: Write the failing tests**

**`players.test.js`:**

```js
describe('bestDisciplines', () => {
	const d = (name, position) => ({ name, position, places: [{ year: 2025, rank: position }] });

	it('keeps the disciplines at position 1', () => {
		expect(bestDisciplines([d('Relay', 1), d('Darts', 2)])).toEqual({ shown: [d('Relay', 1)], more: 0, count: 1 });
	});

	it('keeps every tied best discipline up to the cap', () => {
		const tied = ['A', 'B', 'C', 'D', 'E'].map((n) => d(n, 1));
		expect(bestDisciplines(tied)).toEqual({ shown: tied.slice(0, 3), more: 2, count: 5 });
	});

	it('is empty without disciplines', () => {
		expect(bestDisciplines([])).toEqual({ shown: [], more: 0, count: 0 });
	});
});
```

**Fixtures:**

`profile` (Xavier) gains:

```js
	disciplines: [
		{ name: 'Relay', position: 1, places: [{ year: 2026, rank: 1 }, { year: 2023, rank: 2 }] },
		{ name: 'Crossfit', position: 2, places: [{ year: 2026, rank: 1 }, { year: 2023, rank: 4 }] },
		{ name: 'Darts', position: 3, places: [{ year: 2026, rank: 3 }] }
	]
```

`profileUnranked` gains `disciplines: []`.

**`[id]/page.test.js`**, add:
- **Best card:** `screen.getByTestId('best-discipline')` has the text `/Signature event\s*Relay/`. It contains an `img` whose `src` matches `relay.svg`. Its text contains neither "Crossfit" nor "Darts".
- **Tie:** a profile whose disciplines are Relay and Darts, both at position 1, shows the label `Signature events`, lists both names, and has no "+".
- **No disciplines** (`profileUnranked`): the card reads `/Signature event\s*—/` and there is no `By discipline` heading.
- **Section:** `screen.getByRole('heading', { name: 'By discipline' })`. `getAllByTestId('discipline-row')` has length 3.
  - Row 0 reads `/Relay\s*1\s*2026\s*2\s*2023/` and includes the hidden sentence `1st place in 2026, 2nd place in 2023`.
  - Row 1's `4` has none of the classes gold, silver or bronze.
  - The row's `.places` element has `aria-hidden="true"`.
- **French** (extend the existing French test or add one): `Épreuve fétiche`, `Relais` in the card and in the first row, the heading `Par épreuve`, and the row sentence `1re place en 2026, 2e place en 2023`.

Run: `cd front && npx vitest run src/lib/players.test.js "src/routes/players/[id]"` and check that the tests fail.

- [ ] **Step 2: Implement**
- **`players.js`:**

```js
/**
 * The player's best disciplines (position 1, ties included), the first `max` of them and
 * how many more there are.
 */
export function bestDisciplines(disciplines, max = 3) {
	const best = disciplines.filter((d) => d.position === 1);
	return { shown: best.slice(0, max), more: Math.max(0, best.length - max), count: best.length };
}
```

- **Dictionaries:** `profile.bestDiscipline`: fr `{ one: 'Épreuve fétiche', other: 'Épreuves fétiches' }`, en `{ one: 'Signature event', other: 'Signature events' }`. `profile.byDiscipline`: fr `'Par épreuve'`, en `'By discipline'`.
- **`[id]/+page.svelte`:**
  - Import `iconFor` from `$lib/icons`, `disciplineName` from `$lib/i18n`, `ordinal` from `$lib/edition` and `bestDisciplines` from `$lib/players`.
  - Add a `spoken(places)` helper like the leaderboard's: `players.placeIn` with `ordinal(rank, locale)`, joined with `', '`.
  - **Figures:** `.figures` becomes `grid-template-columns: repeat(2, minmax(0, 14rem))`. Add a second card, `data-testid="best-discipline"`:
    - its label is `t('profile.bestDiscipline', { n: Math.max(best.count, 1) })`;
    - with `best.count > 0`, each shown discipline is `<span class="best"><img src={iconFor(d.name)} alt="" /> {disciplineName(locale, d.name)}</span>`, plus `t('players.more', { n: best.more })` when `best.more > 0`;
    - otherwise the card shows `<span class="num value">—</span>`;
    - keep the cards the same height (the grid stretches them).
  - **Section:** after the Éditions list, add `{#if profile.disciplines.length > 0}`:
    - `<h2>{t('profile.byDiscipline')}</h2>`;
    - a `<ul class="disciplines" role="list">` of `<li class="discipline" data-testid="discipline-row">`. Each row holds `<img src={iconFor(d.name)} alt="" />`, `<span class="name">{disciplineName(locale, d.name)}</span>`, then `<span class="places" aria-hidden="true">` with, per place, `<span class="place"><span class="num rank" class:gold class:silver class:bronze>{rank}</span> <span class="year">{year}</span></span>` separated by `{' '}`, and finally `<span class="visually-hidden">{spoken(d.places)}</span>`.
  - **Style**, tokens only:
    - `.discipline`: a grid with icon 20px, name, and places; `border-top: 1px solid var(--line)`, the same rhythm as `.edition`;
    - `.rank`: `var(--muted)` by default, `var(--gold/--silver/--bronze)` for 1–3, font-size about 1.3rem;
    - `.year`: 0.75rem, `var(--muted)`;
    - `.best img` and `.discipline img`: 18–20px;
    - the best card's name text: 0.95rem, `overflow-wrap: anywhere`;
    - at 375px nothing may overflow.
  - Use `{@const}` inside `#each` where it avoids repeated calls.

- [ ] **Step 3: Run and commit**

`cd front && npm test && npm run build` must pass. Commit with `[FEAT] front: profile places per discipline and best-discipline card` and a Co-Authored-By line.

---

### Task 3: Docs and verification (coordinator)

- **CLAUDE.md:**
  - `Standings.by_team` / `disciplines_of`;
  - `DisciplinePlaces` and the discipline rule in the Player profiles paragraph;
  - `/profile/<id>/` `disciplines` in the API paragraph;
  - the profile's best card and section in the front paragraphs.
- **Full suites:** Django, front, build, and `makemigrations --check`.
- **Browser:** a profile with several disciplines at desktop and 375px.
