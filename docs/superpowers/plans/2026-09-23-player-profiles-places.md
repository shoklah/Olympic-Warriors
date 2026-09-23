# Player Profiles: Leaderboard by Places (addendum plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rank the `/players` leaderboard like a medal table on each person's places, and show those places in its rows. The averages stay on the profile only.

**Architecture:** `PlayerRecord` gains `places` (counted participations, best rank first). `_place` sorts on a medal-table key: the ranks best first plus a sentinel. That compares exactly like "number of 1st places, then 2nd, …", where an extra lower place counts in a person's favour. `/profiles/` rows swap the averages for `places`. The front row shows coloured places with a visually hidden sentence.

**Tech Stack:** Django 4.2 + DRF (tests in the compose `server` container), SvelteKit 2 / Svelte 4, Vitest.

**Spec:** `docs/superpowers/specs/2026-09-23-player-profiles-design.md`, revised 2026-09-23 ("Definitions > Places / Leaderboard", "Endpoints", "Leaderboard page"). The first plan (`2026-09-23-player-profiles.md`) is the record of the original build.

---

## Rules for whoever executes this

- Branch `claude/player-profiles`, main checkout `/Users/shoklah/Work/Playground/Olympic-Warriors`. Never switch branches, never `git stash`, never push, never `git add -A`.
- **The local dev database holds real data restored from prod.** Never run `manage.py shell`, `runscript`, `loaddata`, `import_edition`, raw SQL or anything else that can write to it, and don't log in to the dev admin. Put experiments in a throwaway `TestCase` run with `manage.py test` (it uses a separate test database), and delete it afterwards.
- Server tests: `docker compose exec -T server python manage.py test <dotted.path>`. Front: `cd front && npx vitest run <path>`, `npm test`, `npm run build`.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

---

### Task A: Medal-table order and `places` on the server

**Files:**
- Modify: `server/olympic_warriors/profiles.py` (module docstring rules, `PlayerRecord`, `_record`, `_place`, and a new `_medal_key`)
- Modify: `server/olympic_warriors/serializer.py` (`LeaderboardRowSerializer`, and a new `PlaceSerializer`)
- Modify: `server/olympic_warriors/views.py` (the `getProfiles` description)
- Modify: `server/olympic_warriors/tests/test_profiles.py`

- [ ] **Step 1: Write the failing tests**

In `server/olympic_warriors/tests/test_profiles.py`:

1. In `TestLeaderboard`, replace `test_ranked_by_share_then_mean_rank_then_editions_with_shared_positions` with:

```python
    def test_ranked_like_a_medal_table(self):
        order = [(record.first_name, record.position) for record in leaderboard(TODAY)]

        # Ana has two 1st places, Chloé one, Bob none but two 2nd places, Dan one 3rd.
        # Then the not-ranked-yet group by last name: Adam (Eve), Brun (Fay).
        self.assertEqual(
            order,
            [("Ana", 1), ("Chloé", 2), ("Bob", 3), ("Dan", 4), ("Eve", None), ("Fay", None)],
        )

    def test_places_are_the_counted_ranks_best_first(self):
        rows = self.rows()

        self.assertEqual([(p.year, p.rank) for p in rows["Ana"].places], [(2025, 1), (2024, 1)])
        self.assertEqual([(p.year, p.rank) for p in rows["Bob"].places], [(2025, 2), (2024, 2)])
        self.assertEqual(rows["Eve"].places, ())  # 2026 is still running
        self.assertEqual(rows["Fay"].places, ())  # no team in 2024
```

2. In `TestRecordAndPlace`, delete `test_positions_compare_the_rounded_share_not_the_raw_mean` and add:

```python
    @staticmethod
    def parts(*ranks_by_year):
        """Counted participations from (year, rank) pairs, each in a 10-team edition."""
        return tuple(Participation(year, None, None, rank, 10, True) for year, rank in ranks_by_year)

    def placed(self, *records):
        return [(record.first_name, record.position) for record in _place(list(records))]

    def test_one_first_place_beats_any_number_of_second_places(self):
        a = _record(self.user(1, "A", "Aa"), self.parts((2024, 1)))
        b = _record(self.user(2, "B", "Bb"), self.parts((2024, 2), (2023, 2), (2022, 2)))

        self.assertEqual(self.placed(b, a), [("A", 1), ("B", 2)])

    def test_an_extra_lower_place_counts_in_a_persons_favour(self):
        a = _record(self.user(1, "A", "Aa"), self.parts((2024, 1)))
        b = _record(self.user(2, "B", "Bb"), self.parts((2024, 1), (2023, 5)))

        self.assertEqual(self.placed(a, b), [("B", 1), ("A", 2)])

    def test_more_of_a_lower_place_breaks_a_tie_on_the_better_ones(self):
        a = _record(self.user(1, "A", "Aa"), self.parts((2024, 1), (2023, 3)))
        b = _record(self.user(2, "B", "Bb"), self.parts((2024, 1), (2023, 2)))

        self.assertEqual(self.placed(a, b), [("B", 1), ("A", 2)])

    def test_identical_places_share_a_position_listed_by_name(self):
        zoe = _record(self.user(1, "Zoé", "Zola"), self.parts((2024, 1), (2022, 3)))
        ada = _record(self.user(2, "Ada", "Adam"), self.parts((2023, 3), (2021, 1)))
        max_ = _record(self.user(3, "Max", "Mars"), self.parts((2024, 2)))

        self.assertEqual(self.placed(zoe, max_, ada), [("Ada", 1), ("Zoé", 1), ("Max", 3)])

    def test_places_are_best_first_then_newest_first_and_skip_uncounted(self):
        parts = (
            Participation(2025, None, None, None, 6, False),  # running
            Participation(2024, None, None, 2, 6, True),
            Participation(2023, None, None, 1, 6, True),
            Participation(2022, None, None, 2, 6, True),
        )

        record = _record(self.user(4, "R", "Roy"), parts)

        self.assertEqual([(p.year, p.rank) for p in record.places], [(2023, 1), (2024, 2), (2022, 2)])
```

3. In `TestProfileEndpoints.test_leaderboard_is_public_and_ordered`, replace the expected first-names list and the two assertions after it with:

```python
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
                "places": [{"year": 2025, "rank": 1}, {"year": 2024, "rank": 1}],
                "position": 1,
            },
        )
        self.assertEqual(response.data[1]["position"], 2)  # Chloé: one 1st place
        self.assertEqual((response.data[4]["places"], response.data[4]["position"]), ([], None))
```

(The first-names order is the same as before by coincidence; the positions change from `1, 1, 3, 4` to `1, 2, 3, 4`.)

- [ ] **Step 2: Run the tests and check they fail**

Run: `docker compose exec -T server python manage.py test olympic_warriors.tests.test_profiles`
Expected: FAIL.
- `test_ranked_like_a_medal_table` fails because Chloé is at position 1.
- The `places` tests raise `AttributeError: 'PlayerRecord' object has no attribute 'places'`.
- The endpoint test fails because the row still carries `average_rank` and `average_beaten`.

- [ ] **Step 3: Implement the server side**

In `server/olympic_warriors/profiles.py`:

- Add `import math` to the imports.
- In the module docstring, replace the leaderboard rule, the one starting "the leaderboard sorts ranked people by share", with:

```
- the leaderboard ranks people like a medal table on their places (the ranks of their
  counted participations): more 1st places first, then more 2nd places, and so on; an
  extra lower place counts in a person's favour; identical places share a position and
  are listed by name; people with nothing counted follow by name, without a position.
  The averages are profile figures and play no part in the order.
```

- In `PlayerRecord`, add a field between `participations` and `counted`:

```python
    places: tuple[Participation, ...]  # the counted participations, best rank first
```

and change the class docstring to: `"""A person's editions, places and averages, with their place on the leaderboard."""`.

- In `_record`, pass the places (and keep the averages):

```python
        places=tuple(sorted(counted_parts, key=lambda part: (part.rank, -part.year))),
```

- Replace `_place` with the medal-table version, and add `_medal_key` above it:

```python
def _medal_key(record):
    """
    Medal-table key: the record's ranks best first, then a sentinel above every rank.
    Comparing two keys compares the number of 1st places, then of 2nd places, and so on:
    at the first difference the lower rank wins, and a record that runs out of places
    loses to one that still has a place, so an extra lower place counts in its favour.
    """
    return (*(place.rank for place in record.places), math.inf)


def _place(records):
    """
    The ranked records in medal-table order with shared positions (identical places
    share one, listed by name), then the records with nothing counted, by name and
    without a position.
    """
    ranked = sorted(
        (record for record in records if record.counted),
        key=lambda r: (_medal_key(r), *_by_name(r)),
    )
    placed = []
    position, previous = None, None
    for index, record in enumerate(ranked, start=1):
        key = _medal_key(record)
        if key != previous:
            position, previous = index, key
        placed.append(replace(record, position=position))
    waiting = sorted((record for record in records if not record.counted), key=_by_name)
    return placed + waiting
```

In `server/olympic_warriors/serializer.py`, add above `LeaderboardRowSerializer`:

```python
class PlaceSerializer(serializers.Serializer):
    """One counted edition of a person: the year and the team's rank that year."""

    year = serializers.IntegerField()
    rank = serializers.IntegerField()
```

and in `LeaderboardRowSerializer`, replace the two average fields with:

```python
    places = PlaceSerializer(many=True, help_text="Counted editions, best rank first")
```

Update its docstring's first line to "A person on the all-time leaderboard (a PlayerRecord, see olympic_warriors.profiles): places only, the averages are on the profile."

In `server/olympic_warriors/views.py`, change the `getProfiles` description to:

```python
    description=(
        "Ranked people first, like a medal table on their places (more 1st places, then "
        "more 2nd places, and so on; identical places share a position), then the ones "
        "with no counted edition yet (finished, ranked, at least two teams), by name and "
        "without a position."
    ),
```

- [ ] **Step 4: Run the tests and check they pass**

Run: `docker compose exec -T server python manage.py test olympic_warriors.tests.test_profiles`
Expected: `OK`. The count is the previous 32, minus the two replaced tests (the share-order test and the rounded-share test), plus 2 in `TestLeaderboard` and 5 in `TestRecordAndPlace`, so `Ran 37 tests`. `PROFILES_QUERIES` is unchanged.

Then run the whole suite: `docker compose exec -T server python manage.py test`. Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add server/olympic_warriors/profiles.py server/olympic_warriors/serializer.py server/olympic_warriors/views.py server/olympic_warriors/tests/test_profiles.py
git commit -m "[ADD] profiles: leaderboard ranked like a medal table on places, rows carry places not averages

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task B: Leaderboard rows show places

**Files:**
- Modify: `front/src/lib/players.js` and `front/src/lib/players.test.js` (`MAX_PLACES`, `shownPlaces`)
- Modify: `front/src/lib/i18n/fr.js`, `front/src/lib/i18n/en.js`
- Modify: `front/src/lib/fixtures/players.js` (`leaderboard` only)
- Modify: `front/src/routes/players/+page.svelte` and `front/src/routes/players/page.test.js`

- [ ] **Step 1: Write the failing tests**

Append to `front/src/lib/players.test.js`, and add `MAX_PLACES` and `shownPlaces` to its import from `./players.js`:

```js
describe('shownPlaces', () => {
	const places = (n) => Array.from({ length: n }, (_, i) => ({ year: 2030 - i, rank: i + 1 }));

	it('shows every place up to the cap', () => {
		expect(shownPlaces(places(3))).toEqual({ shown: places(3), more: 0 });
		expect(shownPlaces(places(MAX_PLACES)).more).toBe(0);
	});

	it('keeps the best places and counts the rest', () => {
		const { shown, more } = shownPlaces(places(MAX_PLACES + 2));
		expect(shown).toEqual(places(MAX_PLACES));
		expect(more).toBe(2);
	});
});
```

Replace the `leaderboard` export in `front/src/lib/fixtures/players.js` (and its line in the file's top comment) with:

```js
/**
 * `leaderboard` is /profiles/: Léa 1st (a 1st and a 2nd place), Hugo and Inès tied 2nd
 * (one 1st place each), Xavier 4th (a 2nd and a 3rd place), then two not ranked yet.
 */
export const leaderboard = [
	{ id: 12, first_name: 'Léa', last_name: 'Martin', played: 3, counted: 2, places: [{ year: 2024, rank: 1 }, { year: 2026, rank: 2 }], position: 1 },
	{ id: 7, first_name: 'Hugo', last_name: 'Maurinier', played: 1, counted: 1, places: [{ year: 2025, rank: 1 }], position: 2 },
	{ id: 9, first_name: 'Inès', last_name: 'Moreau', played: 1, counted: 1, places: [{ year: 2025, rank: 1 }], position: 2 },
	{ id: 34, first_name: 'Xavier', last_name: 'Baby', played: 4, counted: 2, places: [{ year: 2026, rank: 2 }, { year: 2023, rank: 3 }], position: 4 },
	{ id: 40, first_name: 'Ana', last_name: 'Petit', played: 1, counted: 0, places: [], position: null },
	{ id: 41, first_name: 'Jules', last_name: 'Roux', played: 2, counted: 0, places: [], position: null }
];
```

Rewrite `front/src/routes/players/page.test.js` as:

```js
import { screen, within } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import { renderWith } from '$lib/test-utils';
import Page from './+page.svelte';
import { leaderboard } from '$lib/fixtures/players.js';

const data = { players: leaderboard };
const ranked = leaderboard.filter((p) => p.position !== null);
const waiting = leaderboard.filter((p) => p.position === null);

describe('players leaderboard page', () => {
	it('ranks players by their places, best first, with a spoken sentence', () => {
		renderWith(Page, { data });

		expect(screen.getByRole('heading', { level: 1, name: 'Players' })).toBeInTheDocument();
		expect(screen.getByText('Ranked by 1st places, then 2nd, then 3rd…')).toBeInTheDocument();
		const rows = screen.getAllByTestId('player-row');
		expect(rows).toHaveLength(4);
		expect(rows[0]).toHaveTextContent(/1\s*Léa Martin\s*1\s*2\s*1st place in 2024, 2nd place in 2026/);
		expect(rows[1]).toHaveTextContent(/2\s*Hugo Maurinier\s*1\s*1st place in 2025/);
		expect(rows[2]).toHaveTextContent(/2\s*Inès Moreau\s*1\s*1st place in 2025/);
		expect(rows[3]).toHaveTextContent(/4\s*Xavier Baby\s*2\s*3\s*2nd place in 2026, 3rd place in 2023/);
		expect(rows[0]).toHaveAttribute('href', '/players/12');
		expect(within(rows[0]).getByTestId('places')).toHaveAttribute('aria-hidden', 'true');
		expect(rows[0]).not.toHaveTextContent(/%|avg/);
	});

	it('colours each place like a medal', () => {
		renderWith(Page, { data });

		const places = within(screen.getAllByTestId('player-row')[3]).getByTestId('places');
		const [second, third] = places.querySelectorAll('.place');
		expect(second).toHaveClass('silver');
		expect(third).toHaveClass('bronze');
	});

	it('medals tied players alike, not by row position', () => {
		renderWith(Page, { data });

		const rows = screen.getAllByTestId('player-row');
		expect(rows[0]).toHaveClass('gold');
		expect(rows[1]).toHaveClass('silver');
		expect(rows[2]).toHaveClass('silver');
		expect(rows[3]).not.toHaveClass('bronze');
	});

	it('shows the best places only past the cap, with the rest counted', () => {
		const places = Array.from({ length: 10 }, (_, i) => ({ year: 2030 - i, rank: 1 + (i % 3) }));
		const busy = { ...ranked[0], places };
		renderWith(Page, { data: { players: [busy] } });

		const row = screen.getByTestId('player-row');
		expect(within(row).getByTestId('places').querySelectorAll('.place')).toHaveLength(8);
		expect(within(row).getByTestId('places')).toHaveTextContent('+2');
		// The spoken sentence still lists all ten.
		expect(row.textContent.match(/place in/g)).toHaveLength(10);
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
		renderWith(Page, { data: { players: ranked } });

		expect(screen.queryByRole('heading', { name: 'Not ranked yet' })).toBeNull();
	});

	it('has no ranked list when nobody is ranked yet', () => {
		const { container } = renderWith(Page, { data: { players: waiting } });

		expect(container.querySelector('ol')).toBeNull();
		expect(screen.queryAllByTestId('player-row')).toHaveLength(0);
		expect(screen.getAllByTestId('unranked-row')).toHaveLength(2);
	});

	it('speaks French under fr', () => {
		renderWith(Page, { data }, 'fr');

		expect(screen.getByRole('heading', { level: 1, name: 'Joueurs' })).toBeInTheDocument();
		expect(screen.getByText('Classés par nombre de 1res places, puis de 2es, puis de 3es…')).toBeInTheDocument();
		const rows = screen.getAllByTestId('player-row');
		expect(rows[0]).toHaveTextContent(/1\s*Léa Martin\s*1\s*2\s*1re place en 2024, 2e place en 2026/);
		expect(screen.getByRole('heading', { name: 'Pas encore classés' })).toBeInTheDocument();
	});
});
```

- [ ] **Step 2: Run the tests and check they fail**

Run: `cd front && npx vitest run src/lib/players.test.js src/routes/players/page.test.js`
Expected: FAIL.
- `shownPlaces` and `MAX_PLACES` are not exported yet.
- The page still renders averages and share.
- The subtitle is the old one.

- [ ] **Step 3: Implement**

In `front/src/lib/players.js`, append:

```js
/** How many places a leaderboard row shows before it counts the rest as +N. */
export const MAX_PLACES = 8;

/** The best `max` places (already sorted best first by the API) and how many are left out. */
export function shownPlaces(places, max = MAX_PLACES) {
	return { shown: places.slice(0, max), more: Math.max(0, places.length - max) };
}
```

In `front/src/lib/i18n/fr.js`:
- Change `players.subtitle` to `'Classés par nombre de 1res places, puis de 2es, puis de 3es…'`.
- Remove `players.over`.
- Add `'players.placeIn': '{place} place en {year}'` and `'players.more': '+{n}'`.

In `front/src/lib/i18n/en.js`:
- Change `players.subtitle` to `'Ranked by 1st places, then 2nd, then 3rd…'`.
- Remove `players.over`.
- Add `'players.placeIn': '{place} place in {year}'` and `'players.more': '+{n}'`.

In `front/src/routes/players/+page.svelte`:
- Change the imports to `import { fullName, shownPlaces } from '$lib/players';` and add `import { ordinal } from '$lib/edition';`. `formatAverage` and `formatShare` are no longer used here.
- Add to the script: `const spoken = (places) => places.map((p) => t('players.placeIn', { place: ordinal(p.rank, locale), year: p.year })).join(', ');`
- Replace the ranked row's `.text` block and the `.share` span with:

```svelte
						<span class="text">
							<span class="name">{fullName(player)}</span>
							<span class="places" aria-hidden="true" data-testid="places">
								{#each shownPlaces(player.places).shown as place}
									<span
										class="num place"
										class:gold={place.rank === 1}
										class:silver={place.rank === 2}
										class:bronze={place.rank === 3}>{place.rank}</span
									>
								{/each}
								{#if shownPlaces(player.places).more > 0}
									<span class="num more"
										>{t('players.more', { n: shownPlaces(player.places).more })}</span
									>
								{/if}
							</span>
							<span class="visually-hidden">{spoken(player.places)}</span>
						</span>
```

- In the `<style>` block, make the ranked `.row` grid `grid-template-columns: 44px minmax(0, 1fr);`. Keep the `.row.waiting` two-column grid as it is. Remove the `.share` rule. Add:

```css
	.places {
		display: flex;
		flex-wrap: wrap;
		gap: 2px 8px;
		margin-top: 2px;
	}

	.place {
		font-size: 1.15rem;
		line-height: 1.1;
		letter-spacing: 0.04em;
		color: var(--faint);
	}

	.place.gold {
		color: var(--gold);
	}

	.place.silver {
		color: var(--silver);
	}

	.place.bronze {
		color: var(--bronze);
	}

	.more {
		font-size: 0.95rem;
		line-height: 1.3;
		color: var(--muted);
	}
```

Keep the `.detail` rule, because the not-ranked rows still use it.

- [ ] **Step 4: Run the tests and check they pass**

Run: `cd front && npx vitest run src/lib/players.test.js src/routes/players src/lib/i18n`
Expected: every test passes, including `parity.test.js`.

Then run: `cd front && npm test && npm run build`
Expected: every test passes and the build succeeds.

- [ ] **Step 5: Commit**

```bash
git add front/src/lib/players.js front/src/lib/players.test.js front/src/lib/i18n/fr.js front/src/lib/i18n/en.js front/src/lib/fixtures/players.js front/src/routes/players/+page.svelte front/src/routes/players/page.test.js
git commit -m "[FEAT] front: leaderboard rows show places best first, ranked like a medal table

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task C: Docs and verification

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update CLAUDE.md**

**In the `**Player profiles:**` paragraph:**
- Replace the sentence about `leaderboard()` sorting by share beaten, mean rank, counted editions and name, with its shared positions on equal (share, mean rank) pairs. The new text says: `leaderboard()` (helper `_place`, key `_medal_key`) ranks people like a medal table on their places, meaning the ranks of their counted editions best first. More 1st places come first, then more 2nd places, and so on. An extra lower place counts in a person's favour. Identical places share a position and are listed by name.
- State that `average_rank` and `average_beaten` are profile figures only.

**In the API paragraph:** say that `/profiles/` rows carry `places` (`[{year, rank}]`, best first) and no averages.

**In the page-tests paragraph:** replace the leaderboard text shape with `1 Léa Martin 1 2` plus its spoken sentence `1st place in 2024, 2nd place in 2026`.

Read the paragraphs first, and keep the dense style.

- [ ] **Step 2: Full verification**

Run:
- `docker compose exec -T server python manage.py test`: `OK`
- `docker compose exec -T server python manage.py makemigrations --check --dry-run`: `No changes detected`
- `cd front && npm test && npm run build`: all green

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "[DOCS] CLAUDE.md: leaderboard by places, averages on the profile

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

The coordinator then checks `/players` and a profile in the browser at desktop and phone width.
