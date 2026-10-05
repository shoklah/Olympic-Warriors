# Builder Requests Clarity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make step 1 of the team builder (the wishes review) show that matches are suggestions to confirm: a state per request line (confirmed, clear, choose, check, none) with `?` / `✓` / `–` icons, the reason for each match, a counter, a one-click « confirm the clear matches » button and a warning before moving on with lines still to review.

**Architecture:** A pure module `$lib/builder/requests.js` derives the rows, the state of each line, its reason key, the counts and the links the bulk button adds, all from `matchNames`' own output and the confirmed links. `BuilderRequests.svelte` renders them (new `RequestIcon.svelte` for the icons) and dispatches `confirmClear`; the page confirms them in one `commit` and shows the warning.

**Tech Stack:** SvelteKit 2 / Svelte 4 (plain JS), Vitest + `@testing-library/svelte`. Front only. Spec: `docs/superpowers/specs/2026-10-06-builder-requests-clarity-design.md`.

**Conventions:** commands run from `front/`. Tests render with `renderWith(Component, props, locale = 'en')` from `$lib/test-utils`. Fixture `$lib/fixtures/builder.js` (`builderPayload.players`): Léa Martin (id 1: with « Paul Durand », avoid « Zoé »), Paul Durand (2: with « Léa »), Paul Petit (3), Inès Moreau (4: avoid « Bob »), Bob Roux (5), Zoé Blanc (6). With that roster every written part is a `clear` match, four lines in all. The counter and warning use `aria-live="polite"`, never `role="status"`: the page's save indicator is the one `role="status"` and an existing test queries it with `getByRole('status')`. Commit messages end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. Stage only the files each task names.

## File structure

- Create `front/src/lib/builder/requests.js` + `requests.test.js`: pure helpers.
- Create `front/src/lib/components/builder/RequestIcon.svelte` + `RequestIcon.test.js`: the three icons.
- Modify `front/src/lib/components/builder/BuilderRequests.svelte` + `BuilderRequests.test.js`.
- Modify `front/src/routes/[year=year]/builder/+page.svelte` + `page.test.js`.
- Modify `front/src/lib/i18n/fr.js` and `en.js`.
- Modify `CLAUDE.md` and the spec (`aria-live` instead of `role="status"`).

---

### Task 1: Pure request helpers

**Files:**
- Create: `front/src/lib/builder/requests.js`
- Test: `front/src/lib/builder/requests.test.js`

- [ ] **Step 1: Write the failing test**

```js
import { describe, expect, it } from 'vitest';
import { builderPayload } from '$lib/fixtures/builder.js';
import { clearLinks, lineState, reasonKey, requestRows, summarise } from './requests.js';

// A clear match, an ambiguous one, a typo and noise.
const roster = [
	{ id: 1, first_name: 'Léa', last_name: 'Martin', team_with: 'Paul', team_avoid: 'Inez' },
	{ id: 2, first_name: 'Paul', last_name: 'Durand', team_with: 'peu importe', team_avoid: '' },
	{ id: 3, first_name: 'Paul', last_name: 'Petit', team_with: '', team_avoid: '' },
	{ id: 4, first_name: 'Inès', last_name: 'Moreau', team_with: '', team_avoid: '' }
];
const state = (rows, index, links = []) => lineState(rows[index].matches[0], links, rows[index].player, rows[index].kind);

describe('requestRows', () => {
	it('has one row per written request, « avec » before « à éviter », in roster order', () => {
		const rows = requestRows(roster);

		expect(rows.map((r) => [r.player.id, r.kind])).toEqual([[1, 'with'], [1, 'avoid'], [2, 'with']]);
		expect(rows[0].matches[0].text).toBe('Paul');
	});
});

describe('lineState', () => {
	it('is clear for a single certain candidate, even by first name', () => {
		const rows = requestRows(builderPayload.players);

		expect(rows).toHaveLength(4);
		expect(rows.map((_, i) => state(rows, i))).toEqual(['clear', 'clear', 'clear', 'clear']);
	});

	it('is choose for several candidates, check for a typo and none for noise', () => {
		const rows = requestRows(roster);

		expect(state(rows, 0)).toBe('choose');
		expect(state(rows, 1)).toBe('check');
		expect(state(rows, 2)).toBe('none');
	});

	it('is confirmed as soon as one candidate of the line is a confirmed link, whatever else it was', () => {
		const rows = requestRows(roster);

		expect(state(rows, 0, [{ player: 1, kind: 'with', target: 2 }])).toBe('confirmed');
		expect(state(rows, 1, [{ player: 1, kind: 'avoid', target: 4 }])).toBe('confirmed');
	});

	it('ignores a link of another player or another kind', () => {
		const rows = requestRows(roster);

		expect(state(rows, 0, [{ player: 2, kind: 'with', target: 2 }, { player: 1, kind: 'avoid', target: 2 }])).toBe('choose');
	});
});

describe('reasonKey', () => {
	it('follows how the match was made, and says when there is none', () => {
		const make = (confidence, n = 1) => ({ confidence, candidates: Array.from({ length: n }, (_, id) => ({ id })) });

		expect(reasonKey(make('exact'))).toBe('builder.requests.why.exact');
		expect(reasonKey(make('last'))).toBe('builder.requests.why.last');
		expect(reasonKey(make('first'))).toBe('builder.requests.why.first');
		expect(reasonKey(make('near'))).toBe('builder.requests.why.near');
		expect(reasonKey(make('ambiguous', 2))).toBe('builder.requests.why.ambiguous');
		expect(reasonKey(make('none', 0))).toBe('builder.requests.noMatch');
	});
});

describe('summarise', () => {
	it('counts the lines by what remains to be done', () => {
		const rows = requestRows(roster);

		expect(summarise(rows, [])).toEqual({ total: 3, confirmed: 0, review: 2, none: 1, clear: 0 });
		expect(summarise(rows, [{ player: 1, kind: 'avoid', target: 4 }])).toEqual({ total: 3, confirmed: 1, review: 1, none: 1, clear: 0 });
	});

	it('counts the clear lines of the fixture and lets confirming one take it out', () => {
		const rows = requestRows(builderPayload.players);

		expect(summarise(rows, [])).toEqual({ total: 4, confirmed: 0, review: 4, none: 0, clear: 4 });
		expect(summarise(rows, [{ player: 1, kind: 'with', target: 2 }])).toEqual({ total: 4, confirmed: 1, review: 3, none: 0, clear: 3 });
	});

	it('is all zeros without any request', () => {
		expect(summarise([], [])).toEqual({ total: 0, confirmed: 0, review: 0, none: 0, clear: 0 });
	});
});

describe('clearLinks', () => {
	it('lists the link of every clear line, and nothing else', () => {
		expect(clearLinks(requestRows(builderPayload.players), [])).toEqual([
			{ player: 1, kind: 'with', target: 2 },
			{ player: 1, kind: 'avoid', target: 6 },
			{ player: 2, kind: 'with', target: 1 },
			{ player: 4, kind: 'avoid', target: 5 }
		]);
		expect(clearLinks(requestRows(roster), [])).toEqual([]); // choose, check and none are left to the organiser
	});

	it('leaves out a line that is already confirmed', () => {
		const links = [{ player: 1, kind: 'with', target: 2 }];

		expect(clearLinks(requestRows(builderPayload.players), links)).toHaveLength(3);
	});
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `npx vitest run src/lib/builder/requests.test.js`
Expected: FAIL, cannot resolve `./requests.js`.

- [ ] **Step 3: Write the implementation**

```js
/**
 * What step 1 of the builder shows of the written requests (spec 2026-10-06-builder-requests-clarity):
 * one row per player and kind, one line per part of the text, the state of each line and the
 * counts. Pure; `matchNames` decides what is suggested, this only reads its answer.
 */
import { matchNames } from './names.js';

const KINDS = [['team_with', 'with'], ['team_avoid', 'avoid']];

/** One row per written request, « avec » then « à éviter », players in roster order. */
export function requestRows(players) {
	return players.flatMap((player) =>
		KINDS.flatMap(([field, kind]) =>
			player[field]?.trim() ? [{ player, kind, matches: matchNames(player[field], players, player.id) }] : []
		)
	);
}

/**
 * Where a line stands: `confirmed` (a candidate of it is a confirmed link), else `none` (no
 * candidate), `clear` (one certain candidate, `best`), `check` (a single candidate a typo away)
 * or `choose` (several candidates).
 */
export function lineState(match, links, player, kind) {
	const confirmed = match.candidates.some((c) =>
		links.some((l) => l.player === player.id && l.kind === kind && l.target === c.id)
	);
	if (confirmed) return 'confirmed';
	if (match.candidates.length === 0) return 'none';
	if (match.best !== null) return 'clear';
	return match.confidence === 'near' ? 'check' : 'choose';
}

/** The dictionary key of the line's caption: how the match was made, or that there is none. */
export const reasonKey = (match) =>
	match.candidates.length === 0 ? 'builder.requests.noMatch' : `builder.requests.why.${match.confidence}`;

/** `{ total, confirmed, review, none, clear }` over the lines; `review` is every line still to decide on, `clear` those a click can confirm. */
export function summarise(rows, links) {
	const counts = { total: 0, confirmed: 0, review: 0, none: 0, clear: 0 };
	for (const row of rows) {
		for (const match of row.matches) {
			const state = lineState(match, links, row.player, row.kind);
			counts.total += 1;
			if (state === 'confirmed') counts.confirmed += 1;
			else if (state === 'none') counts.none += 1;
			else {
				counts.review += 1;
				if (state === 'clear') counts.clear += 1;
			}
		}
	}
	return counts;
}

/** The `{ player, kind, target }` links of every clear line: what « confirm the clear matches » adds. */
export function clearLinks(rows, links) {
	return rows.flatMap((row) =>
		row.matches
			.filter((match) => lineState(match, links, row.player, row.kind) === 'clear')
			.map((match) => ({ player: row.player.id, kind: row.kind, target: match.best }))
	);
}
```

- [ ] **Step 4: Run it to verify it passes**

Run: `npx vitest run src/lib/builder/requests.test.js`
Expected: PASS, 10 tests.

- [ ] **Step 5: Commit**

```bash
git add src/lib/builder/requests.js src/lib/builder/requests.test.js
git commit -m "[FEAT] builder: pure helpers for the state of each written request

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Dictionary keys

**Files:**
- Modify: `front/src/lib/i18n/fr.js` (after `'builder.requests.confirm': 'Confirmer {name}',`)
- Modify: `front/src/lib/i18n/en.js` (after `'builder.requests.confirm': 'Confirm {name}',`)

The parity test fails until both hold the same keys: add both in one step.

- [ ] **Step 1: Add the French keys** after `'builder.requests.confirm': 'Confirmer {name}',`

```js
	'builder.requests.count.total': { one: '{n} demande', other: '{n} demandes' },
	'builder.requests.count.confirmed': { one: '{n} confirmée', other: '{n} confirmées' },
	'builder.requests.count.review': '{n} à examiner',
	'builder.requests.count.none': '{n} sans correspondance',
	'builder.requests.confirmClear': { one: 'Confirmer {n} correspondance sûre', other: 'Confirmer {n} correspondances sûres' },
	'builder.requests.state.confirmed': 'Confirmé',
	'builder.requests.state.clear': 'Correspondance sûre',
	'builder.requests.state.choose': 'À choisir',
	'builder.requests.state.check': 'À vérifier',
	'builder.requests.state.none': 'Aucune correspondance',
	'builder.requests.why.exact': 'Nom complet · un seul joueur',
	'builder.requests.why.last': 'Nom de famille · un seul joueur',
	'builder.requests.why.first': 'Prénom · un seul joueur',
	'builder.requests.why.ambiguous': '{n} joueurs possibles, à choisir',
	'builder.requests.why.near': "Orthographe proche, vérifiez que c'est la bonne personne",
	'builder.requests.warning': { one: "{n} demande n'est pas confirmée et sera ignorée.", other: '{n} demandes ne sont pas confirmées et seront ignorées.' },
```

- [ ] **Step 2: Add the English keys** after `'builder.requests.confirm': 'Confirm {name}',`

```js
	'builder.requests.count.total': { one: '{n} request', other: '{n} requests' },
	'builder.requests.count.confirmed': { one: '{n} confirmed', other: '{n} confirmed' },
	'builder.requests.count.review': '{n} to review',
	'builder.requests.count.none': '{n} with no match',
	'builder.requests.confirmClear': { one: 'Confirm {n} clear match', other: 'Confirm {n} clear matches' },
	'builder.requests.state.confirmed': 'Confirmed',
	'builder.requests.state.clear': 'Clear match',
	'builder.requests.state.choose': 'Choose',
	'builder.requests.state.check': 'Check',
	'builder.requests.state.none': 'No match',
	'builder.requests.why.exact': 'Full name · only one player',
	'builder.requests.why.last': 'Last name · only one player',
	'builder.requests.why.first': 'First name · only one player',
	'builder.requests.why.ambiguous': '{n} players possible, pick one',
	'builder.requests.why.near': 'Close spelling, check it is the right person',
	'builder.requests.warning': { one: "{n} request isn't confirmed and will be ignored.", other: "{n} requests aren't confirmed and will be ignored." },
```

- [ ] **Step 3: Run the dictionary tests**

Run: `npx vitest run src/lib/i18n`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/lib/i18n/fr.js src/lib/i18n/en.js
git commit -m "[FEAT] builder: dictionary keys for the clearer wishes review

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 3: The icon

**Files:**
- Create: `front/src/lib/components/builder/RequestIcon.svelte`
- Test: `front/src/lib/components/builder/RequestIcon.test.js`

- [ ] **Step 1: Write the failing test**

```js
import { render } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import RequestIcon from './RequestIcon.svelte';

const paths = (name) => [...render(RequestIcon, { name }).container.querySelectorAll('svg path')].map((p) => p.getAttribute('d'));

describe('RequestIcon', () => {
	it('is hidden from assistive technology: the state is always said in words beside it', () => {
		const { container } = render(RequestIcon, { name: 'check' });

		expect(container.querySelector('svg')).toHaveAttribute('aria-hidden', 'true');
	});

	it('draws a circle with a different mark for each state', () => {
		const marks = ['question', 'check', 'minus'].map((name) => paths(name).join('|'));

		expect(new Set(marks).size).toBe(3);
		expect(paths('check')).toEqual(['M8 12.5l3 3 5-6']);
		expect(paths('minus')).toEqual(['M8 12h8']);
	});
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `npx vitest run src/lib/components/builder/RequestIcon.test.js`
Expected: FAIL, cannot resolve `./RequestIcon.svelte`.

- [ ] **Step 3: Write the component**

```svelte
<script>
	/** The state a request line or chip is in: 'question' (to confirm), 'check' (confirmed) or 'minus' (nothing to confirm). */
	export let name;
</script>

<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
	<circle cx="12" cy="12" r="9" />
	{#if name === 'check'}
		<path d="M8 12.5l3 3 5-6" />
	{:else if name === 'minus'}
		<path d="M8 12h8" />
	{:else}
		<path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.4-1 .9-1 1.7" />
		<path d="M12 17h.01" />
	{/if}
</svg>

<style>
	svg {
		flex: none;
		width: 1em;
		height: 1em;
		fill: none;
		stroke: currentColor;
		stroke-width: 2;
		stroke-linecap: round;
		stroke-linejoin: round;
	}
</style>
```

- [ ] **Step 4: Run it to verify it passes**

Run: `npx vitest run src/lib/components/builder/RequestIcon.test.js`
Expected: PASS, 2 tests.

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/builder/RequestIcon.svelte src/lib/components/builder/RequestIcon.test.js
git commit -m "[FEAT] builder: RequestIcon, the question, check and minus circles

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 4: The review panel

**Files:**
- Modify (replace whole file): `front/src/lib/components/builder/BuilderRequests.svelte`
- Test: `front/src/lib/components/builder/BuilderRequests.test.js` (append)

- [ ] **Step 1: Add the failing tests.** Append inside `describe('BuilderRequests', …)` of `BuilderRequests.test.js` (its `players`, `withText` and imports exist; add `within` is already imported):

```js
	it('says what each line is: clear matches, then confirmed ones', () => {
		const { component } = renderWith(BuilderRequests, { players, links: [] });

		expect(screen.getAllByText('Clear match')).toHaveLength(4);
		expect(screen.queryByText('Confirmed')).toBeNull();

		component.$set({ links: [{ player: 1, kind: 'with', target: 2 }] });
		return vi.waitFor(() => {
			expect(screen.getAllByText('Clear match')).toHaveLength(3);
			expect(screen.getAllByText('Confirmed')).toHaveLength(1);
		});
	});

	it('says why a name matched', () => {
		renderWith(BuilderRequests, { players, links: [] });

		expect(screen.getByText('Full name · only one player')).toBeInTheDocument(); // « Paul Durand »
		expect(screen.getAllByText('First name · only one player')).toHaveLength(3); // « Zoé », « Léa », « Bob »
	});

	it('marks lines that need a decision and a name without a player', () => {
		const roster = [
			{ id: 1, first_name: 'Léa', last_name: 'Martin', team_with: 'Paul', team_avoid: 'Inez' },
			{ id: 2, first_name: 'Paul', last_name: 'Durand', team_with: 'peu importe', team_avoid: '' },
			{ id: 3, first_name: 'Paul', last_name: 'Petit', team_with: '', team_avoid: '' },
			{ id: 4, first_name: 'Inès', last_name: 'Moreau', team_with: '', team_avoid: '' }
		];
		renderWith(BuilderRequests, { players: roster, links: [] });

		expect(screen.getByText('Choose')).toBeInTheDocument();
		expect(screen.getByText('2 players possible, pick one')).toBeInTheDocument();
		expect(screen.getByText('Check')).toBeInTheDocument();
		expect(screen.getByText('Close spelling, check it is the right person')).toBeInTheDocument();
		expect(screen.getByText('No match')).toBeInTheDocument();
		expect(screen.getByText('No matching player')).toBeInTheDocument();
	});

	it('counts the requests and tells the review apart from what is confirmed', () => {
		renderWith(BuilderRequests, { players, links: [{ player: 1, kind: 'with', target: 2 }] });

		expect(screen.getByText('4 requests · 1 confirmed · 3 to review')).toBeInTheDocument();
	});

	it('mentions the requests with no match in the count only when there are some', () => {
		renderWith(BuilderRequests, { players: withText(2, { team_with: 'peu importe' }), links: [] });

		expect(screen.getByText(/with no match/)).toBeInTheDocument();
	});

	it('offers to confirm the clear matches in one click, and reports them all at once', async () => {
		const { component } = renderWith(BuilderRequests, { players, links: [] });
		const events = [];
		component.$on('confirmClear', (e) => events.push(e.detail));

		await fireEvent.click(screen.getByRole('button', { name: 'Confirm 4 clear matches' }));

		expect(events).toEqual([[
			{ player: 1, kind: 'with', target: 2 },
			{ player: 1, kind: 'avoid', target: 6 },
			{ player: 2, kind: 'with', target: 1 },
			{ player: 4, kind: 'avoid', target: 5 }
		]]);
	});

	it('has no bulk button when no line is clear', () => {
		renderWith(BuilderRequests, { players: players.map((p) => ({ ...p, team_with: 'Paul', team_avoid: '' })), links: [] });

		expect(screen.queryByRole('button', { name: /clear match/ })).toBeNull();
	});

	it('shows a confirmed chip as pressed with a status of its own', () => {
		renderWith(BuilderRequests, { players, links: [{ player: 4, kind: 'avoid', target: 5 }] });

		const section = screen.getByRole('region', { name: 'Inès Moreau: would rather avoid' });
		expect(within(section).getByRole('button', { name: 'Confirm Bob Roux' })).toHaveAttribute('aria-pressed', 'true');
		expect(within(section).getByText('Confirmed')).toBeInTheDocument();
	});

	it('speaks French', () => {
		renderWith(BuilderRequests, { players, links: [{ player: 1, kind: 'with', target: 2 }] }, 'fr');

		expect(screen.getByText('4 demandes · 1 confirmée · 3 à examiner')).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Confirmer 3 correspondances sûres' })).toBeInTheDocument();
		expect(screen.getAllByText('Correspondance sûre')).toHaveLength(3);
		expect(screen.getByText('Confirmé')).toBeInTheDocument();
		expect(screen.getByText('Prénom · un seul joueur', { exact: false })).toBeInTheDocument();
	});
```

Also change the first import line of the test file to `import { fireEvent, screen, within } from '@testing-library/svelte';` (it already is) and add `vi` to the vitest import: `import { describe, expect, it, vi } from 'vitest';`.

- [ ] **Step 2: Run them to verify they fail**

Run: `npx vitest run src/lib/components/builder/BuilderRequests.test.js`
Expected: the new tests FAIL (no status text, no counter, no button); the older ones PASS.

- [ ] **Step 3: Replace `BuilderRequests.svelte` with:**

```svelte
<script>
	import { createEventDispatcher } from 'svelte';
	import { useT } from '$lib/i18n';
	import { fullName } from '$lib/players';
	import { clearLinks, lineState, reasonKey, requestRows, summarise } from '$lib/builder/requests.js';
	import RequestIcon from './RequestIcon.svelte';

	export let players;
	export let links;

	const t = useT();
	const dispatch = createEventDispatcher();
	const STATE_ICON = { confirmed: 'check', clear: 'question', choose: 'question', check: 'question', none: 'minus' };

	$: byId = new Map(players.map((p) => [p.id, p]));
	// The matches depend on the roster only, so confirming a link never recomputes them.
	$: rows = requestRows(players);
	// One card per player, holding the « avec » and the « à éviter » requests they wrote.
	$: cards = players
		.map((player) => ({ player, rows: rows.filter((row) => row.player.id === player.id) }))
		.filter((card) => card.rows.length > 0);
	$: confirmed = new Set(links.map((l) => `${l.player}:${l.kind}:${l.target}`));
	$: isOn = (player, kind, target) => confirmed.has(`${player.id}:${kind}:${target}`);
	$: stateOf = (row, match) => lineState(match, links, row.player, row.kind);
	$: summary = summarise(rows, links);
	$: counter = [
		t('builder.requests.count.total', { n: summary.total }),
		t('builder.requests.count.confirmed', { n: summary.confirmed }),
		t('builder.requests.count.review', { n: summary.review }),
		...(summary.none > 0 ? [t('builder.requests.count.none', { n: summary.none })] : [])
	].join(' · ');
	const toggle = (player, kind, target) => dispatch('toggle', { player: player.id, kind, target });
	const confirmClear = () => dispatch('confirmClear', clearLinks(rows, links));
	const why = (match) => t(reasonKey(match), { n: match.candidates.length });

	/** Confirmed links of this player and kind that no name of their text suggested (added through « Autre joueur »). */
	$: extras = (row) => {
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
{#if cards.length === 0}
	<p>{t('builder.requests.none')}</p>
{:else}
	<div class="bar">
		<p class="counter" aria-live="polite">{counter}</p>
		{#if summary.clear > 0}
			<button type="button" class="pill" on:click={confirmClear}>{t('builder.requests.confirmClear', { n: summary.clear })}</button>
		{/if}
	</div>
	<ul class="grid">
		{#each cards as card (card.player.id)}
			<li class="card">
				<h3 class="who">{fullName(card.player)}</h3>
				{#each card.rows as row (row.kind)}
					<section class="kind" aria-label="{fullName(card.player)}: {t(`builder.requests.${row.kind}`)}">
						<p class="label">{t(`builder.requests.${row.kind}`)}</p>
						<ul class="matches">
							{#each row.matches as match}
								{@const state = stateOf(row, match)}
								<li class="match">
									<span class="line">
										<span class="text">« {match.text} »</span>
										<span class="status {state}"><RequestIcon name={STATE_ICON[state]} />{t(`builder.requests.state.${state}`)}</span>
									</span>
									{#if match.candidates.length > 0}
										<span class="chips">
											{#each match.candidates as candidate}
												<button
													type="button"
													class="chip"
													class:clear={state === 'clear'}
													aria-pressed={isOn(row.player, row.kind, candidate.id)}
													aria-label={t('builder.requests.confirm', { name: fullName(byId.get(candidate.id)) })}
													on:click={() => toggle(row.player, row.kind, candidate.id)}
												>
													<RequestIcon name={isOn(row.player, row.kind, candidate.id) ? 'check' : 'question'} />
													{fullName(byId.get(candidate.id))}
												</button>
											{/each}
										</span>
									{/if}
									<span class="why">{why(match)}</span>
								</li>
							{/each}
							{#if extras(row).length > 0}
								<li class="match added">
									<span class="text">{t('builder.requests.added')}</span>
									<span class="chips">
										{#each extras(row) as link}
											<button type="button" class="chip" aria-pressed="true" aria-label={t('builder.requests.confirm', { name: fullName(byId.get(link.target)) })} on:click={() => toggle(row.player, row.kind, link.target)}>
												<RequestIcon name="check" />
												{fullName(byId.get(link.target))}
											</button>
										{/each}
									</span>
								</li>
							{/if}
						</ul>
						<select aria-label="{t('builder.requests.other')} ({fullName(row.player)}) · {t(`builder.requests.${row.kind}`)}" on:change={(e) => other(e, row.player, row.kind)}>
							<option value="">{t('builder.requests.other')}</option>
							{#each players.filter((p) => p.id !== row.player.id) as p}<option value={p.id}>{fullName(p)}</option>{/each}
						</select>
					</section>
				{/each}
			</li>
		{/each}
	</ul>
{/if}

<style>
	.hint {
		color: var(--muted);
		font-size: 0.875rem;
		margin: 0 0 1rem;
	}
	.bar {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem 1rem;
		margin-bottom: 1rem;
	}
	.counter {
		margin: 0;
		color: var(--muted);
		font-size: 0.875rem;
	}
	.pill {
		padding: 0.5rem 1.125rem;
		border-radius: 999px;
		border: 1px solid var(--accent);
		background: transparent;
		color: var(--accent);
		font: inherit;
		font-weight: 600;
		cursor: pointer;
	}
	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(min(26rem, 100%), 1fr));
		gap: 1rem;
		align-items: stretch;
		margin: 0;
		padding: 0;
		list-style: none;
	}
	.card {
		display: grid;
		align-content: start;
		gap: 0.75rem;
		padding: 0.75rem 1rem;
		background: var(--bg-raised);
		border: 1px solid var(--line);
		border-radius: var(--radius);
	}
	.who {
		margin: 0;
		font-size: 1.125rem;
	}
	.kind {
		display: grid;
		gap: 0.5rem;
	}
	.label {
		margin: 0;
		font-size: 0.75rem;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--muted);
	}
	.kind ul {
		display: grid;
		gap: 0.375rem;
		margin: 0;
		padding: 0;
		list-style: none;
	}
	.match {
		display: grid;
		gap: 0.375rem;
		padding-bottom: 0.5rem;
		border-bottom: 1px solid var(--line);
	}
	.match:last-child {
		border-bottom: 0;
		padding-bottom: 0;
	}
	.match.added .text {
		font-size: 0.75rem;
		letter-spacing: 0.06em;
		text-transform: uppercase;
	}
	.line {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		justify-content: space-between;
		gap: 0.25rem 0.75rem;
	}
	.text {
		color: var(--muted);
	}
	/* The state in words and an icon as well as a colour: none of the three is the only signal. */
	.status {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		font-size: 0.75rem;
		font-weight: 600;
		white-space: nowrap;
	}
	.status.confirmed {
		color: var(--win);
	}
	.status.clear {
		color: var(--accent);
	}
	.status.choose,
	.status.check {
		color: var(--todo);
	}
	.status.none {
		color: var(--muted);
	}
	.why {
		font-size: 0.8125rem;
		color: var(--muted);
	}
	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		align-items: center;
	}
	/* A suggestion is dashed: a question. A clear one is solid in the accent, and a confirmed one
	   solid and tinted in the win colour. */
	.chip {
		display: inline-flex;
		align-items: center;
		gap: 0.375rem;
		padding: 0.375rem 0.875rem;
		border-radius: 999px;
		border: 1.5px dashed var(--line-strong);
		background: transparent;
		color: var(--ink);
		font: inherit;
		font-weight: 600;
		cursor: pointer;
	}
	.chip.clear {
		border-style: solid;
		border-color: var(--accent);
		color: var(--accent);
	}
	.chip[aria-pressed='true'] {
		border-style: solid;
		border-color: var(--win);
		background: color-mix(in srgb, var(--win) 16%, transparent);
		color: var(--win);
	}
	select {
		width: 100%;
		max-width: 20rem;
		padding: 0.5rem 0.625rem;
		background: var(--bg-sunken);
		color: var(--ink);
		border: 1px solid var(--line-strong);
		border-radius: var(--radius);
		font: inherit;
	}
	/* Side by side, every card the same size (the tallest row sets the height); one column on a
	   phone keeps each card as tall as its content. */
	@media (min-width: 600px) {
		.grid {
			grid-auto-rows: 1fr;
		}
	}
</style>
```

- [ ] **Step 4: Run the panel's tests**

Run: `npx vitest run src/lib/components/builder/BuilderRequests.test.js`
Expected: PASS (new and old). If the French counter assertion fails on plural forms (`1 confirmée`), check `fr.js` `count.confirmed` is `{ one, other }` and that French puts 1 in the singular. If `getByText('Prénom · un seul joueur', { exact: false })` finds several elements, switch that line to `getAllByText(...)` with `.length` greater than 0.

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/builder/BuilderRequests.svelte src/lib/components/builder/BuilderRequests.test.js
git commit -m "[FEAT] builder: the wishes review shows each line's state, reason and a bulk confirm

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 5: The page confirms in bulk and warns before moving on

**Files:**
- Modify: `front/src/routes/[year=year]/builder/+page.svelte`
- Test: `front/src/routes/[year=year]/builder/page.test.js`

- [ ] **Step 1: Add the failing tests** inside `describe('team builder page', …)` of `page.test.js`:

```js
	it('confirms every clear match with one click and keeps the count and the warning in step', async () => {
		renderWith(Page, { data: data() });

		expect(screen.getByText('4 requests · 0 confirmed · 4 to review')).toBeInTheDocument();
		expect(screen.getByText("4 requests aren't confirmed and will be ignored.")).toBeInTheDocument();

		await fireEvent.click(screen.getByRole('button', { name: 'Confirm 4 clear matches' }));

		for (const name of ['Confirm Paul Durand', 'Confirm Zoé Blanc', 'Confirm Léa Martin', 'Confirm Bob Roux']) {
			expect(screen.getByRole('button', { name })).toHaveAttribute('aria-pressed', 'true');
		}
		expect(screen.getByText('4 requests · 4 confirmed · 0 to review')).toBeInTheDocument();
		expect(screen.queryByRole('button', { name: /clear match/ })).toBeNull();
		expect(screen.queryByText(/will be ignored/)).toBeNull();
	});

	it('warns that unconfirmed requests are ignored only while some are left, and only on the requests step', async () => {
		renderWith(Page, { data: data() });
		await fireEvent.click(screen.getByRole('button', { name: 'Confirm Paul Durand' }));

		expect(screen.getByText("3 requests aren't confirmed and will be ignored.")).toBeInTheDocument();

		await goTo('Teams');
		expect(screen.queryByText(/will be ignored/)).toBeNull();
	});
```

- [ ] **Step 2: Run them to verify they fail**

Run: `npx vitest run "src/routes/[year=year]/builder/page.test.js"`
Expected: the two new tests FAIL; the rest PASS.

- [ ] **Step 3: Wire the page** (`+page.svelte`).

Add the import next to the other builder ones:

```js
	import { requestRows, summarise } from '$lib/builder/requests.js';
```

After `function toggleLink(...) { ... }` add:

```js
	const linkKey = (l) => `${l.player}:${l.kind}:${l.target}`;
	// The clear matches the organiser confirmed in one click: one change of the draft, so one save.
	function confirmClear({ detail }) {
		const have = new Set(draft.links.map(linkKey));
		const added = detail.filter((l) => !have.has(linkKey(l)) && have.add(linkKey(l)));
		if (added.length > 0) commit({ ...draft, links: [...draft.links, ...added] });
	}
	$: requestSummary = summarise(requestRows(players), draft.links);
```

Change the requests panel line to

```svelte
			<BuilderRequests {players} links={draft.links} on:toggle={toggleLink} on:confirmClear={confirmClear} />
```

Above `<div class="nav-buttons">` add (the wrapper stays in the page so a later announcement is read; the note appears inside it):

```svelte
		<div aria-live="polite">
			{#if step === 1 && requestSummary.review > 0}
				<p class="notice">{t('builder.requests.warning', { n: requestSummary.review })}</p>
			{/if}
		</div>
```

- [ ] **Step 4: Run the builder tests**

Run: `npx vitest run "src/routes/[year=year]/builder" src/lib/components/builder src/lib/builder`
Expected: PASS. If `.notice` styling looks off beside the other notices, leave it: it is the page's existing class.

- [ ] **Step 5: Commit**

```bash
git add "src/routes/[year=year]/builder/+page.svelte" "src/routes/[year=year]/builder/page.test.js"
git commit -m "[FEAT] builder: confirm the clear matches in one save, warn before moving on

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Docs and the whole suite

**Files:**
- Modify: `CLAUDE.md`
- Modify: `docs/superpowers/specs/2026-10-06-builder-requests-clarity-design.md`

- [ ] **Step 1: Document it.** In `CLAUDE.md`, in the team builder front half, right after « `BuilderRequests` (names to confirmed links), » insert: « each written part is a line whose state (`$lib/builder/requests.js`: `confirmed`, `clear` for one certain candidate, `choose` for several, `check` for a typo, `none`) shows as a `?` / `✓` / `–` icon (`RequestIcon`), a status and the reason of the match, a counter and « Confirmer N correspondances sûres » (the `confirmClear` event, confirmed in one save by the page, with a note before moving on while lines are left to review; `aria-live`, never `role="status"`, which the save indicator holds alone), ». Use `grep -n "BuilderRequests" CLAUDE.md` to find the exact spot and keep the sentence grammatical.

- [ ] **Step 2: Sync the spec.** In the spec, replace « A `role="status"` line (polite, so a bulk confirmation is announced) » by « A line with `aria-live="polite"` (not `role="status"`: the page's save indicator is the only one, and a test queries it, so a bulk confirmation is announced without it) », and « (`role="status"`). It does not block the step change. » by « (in a polite live region). It does not block the step change. ».

- [ ] **Step 3: Run the whole front suite and the build**

Run: `npm test && npm run build`
Expected: all tests PASS, build succeeds.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md docs/superpowers/specs/2026-10-06-builder-requests-clarity-design.md
git commit -m "[DOCS] builder requests: CLAUDE.md and spec sync

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

## Self-review

- **Spec coverage:** the five states and their chip, icon and status (Tasks 1, 3, 4); the reason caption per confidence (Tasks 1, 2, 4); the counter and the bulk button, hidden at 0 clear, one save (Tasks 1, 4, 5); the warning before moving on, outside step 1 silent (Task 5); `requests.js` as the one place for the logic (Task 1); i18n parity (Task 2); tests as listed (all tasks); no matcher or server change.
- **Types:** `requestRows` rows are `{player, kind, matches}`; `lineState(match, links, player, kind)`; `summarise` → `{total, confirmed, review, none, clear}`; `clearLinks` → `{player: id, kind, target}`; the `confirmClear` event detail is that array; the page's `confirmClear({ detail })` reads it the same way. Icon names `question`, `check`, `minus` match `STATE_ICON` and the icon's branches.
- **No placeholders:** each step has its code or exact commands; the two conditional notes in Tasks 4 and 5 name the exact change to make.
