# Builder Player Preview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** An eye button on every team-builder card opens a modal with the player's full rating profile (rating, global level, frequency, one bar per skill, sports).

**Architecture:** A pure helper `$lib/builder/profile.js` derives what the sheet draws from `features()` in `score.js` (so estimated values match the scorer). A new `PlayerSheet.svelte` renders it in the shared `modal` dialog pattern (bottom sheet under 1000px, centred above). `PlayerCard` dispatches `preview`, `BuilderTeams` forwards it, and the builder page owns the open state.

**Tech Stack:** SvelteKit 2 / Svelte 4 (plain JS), Vitest + `@testing-library/svelte`. Front only; spec: `docs/superpowers/specs/2026-10-06-builder-player-preview-design.md`.

**Conventions:** all commands run from `front/`. Tests render with `renderWith(Component, props, locale)` (English by default) from `$lib/test-utils`; fixture `$lib/fixtures/builder.js` (`builderPayload`: skills `CARD` Cardio and `STR` Strength; player 1 Léa Martin rating 8, ratings 9/7, `four_hours`; player 3 Paul Petit with a Judo `league` sport; player 5 Bob Roux with empty `ratings` and no frequency). Commit messages end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.

## File structure

- Create `front/src/lib/builder/profile.js` + `profile.test.js`: pure `playerProfile`.
- Create `front/src/lib/components/builder/PlayerSheet.svelte` + `PlayerSheet.test.js`: the dialog.
- Modify `front/src/lib/components/builder/PlayerCard.svelte` + `PlayerCard.test.js`: eye button, `preview` event.
- Modify `front/src/lib/components/builder/BuilderTeams.svelte`: forward `preview` from both card lists.
- Modify `front/src/routes/[year=year]/builder/+page.svelte` + `page.test.js`: open state, sheet, focus return.
- Modify `front/src/lib/i18n/fr.js` and `en.js`: new `builder.preview*` keys.
- Modify `CLAUDE.md`: one sentence in the team builder paragraph.

---

### Task 1: The pure profile helper

**Files:**
- Create: `front/src/lib/builder/profile.js`
- Test: `front/src/lib/builder/profile.test.js`

- [ ] **Step 1: Write the failing test**

```js
import { describe, expect, it } from 'vitest';
import { builderPayload } from '$lib/fixtures/builder.js';
import { playerProfile } from './profile.js';

const { players, skills } = builderPayload;
const byId = (id) => players.find((p) => p.id === id);

describe('playerProfile', () => {
	it('gives one bar per skill in order, from the player own ratings', () => {
		const profile = playerProfile(byId(1), skills, 'en');

		expect(profile.rating).toBe(8);
		expect(profile.frequency).toBe('four_hours');
		expect(profile.bars).toEqual([
			{ identifier: 'CARD', name: 'Cardio', value: 9, estimated: false },
			{ identifier: 'STR', name: 'Strength', value: 7, estimated: false }
		]);
		expect(profile.incomplete).toBe(false);
	});

	it('takes the overall rating for a missing skill and marks it estimated', () => {
		const profile = playerProfile({ ...byId(1), ratings: { CARD: 9 } }, skills, 'en');

		expect(profile.bars[1]).toMatchObject({ identifier: 'STR', value: 8, estimated: true });
		expect(profile.bars[0].estimated).toBe(false);
		expect(profile.incomplete).toBe(true);
	});

	it('marks every skill estimated and the profile incomplete when there are no ratings or frequency', () => {
		const profile = playerProfile(byId(5), skills, 'en');

		expect(profile.bars.map((b) => [b.value, b.estimated])).toEqual([[3, true], [3, true]]);
		expect(profile.frequency).toBeNull();
		expect(profile.incomplete).toBe(true);
	});

	it('names the skills by locale', () => {
		expect(playerProfile(byId(1), skills, 'fr').bars[1].name).toBe('Force');
		expect(playerProfile(byId(1), skills, 'en').bars[1].name).toBe('Strength');
	});

	it('carries the global level (null when unknown) and the sports', () => {
		expect(playerProfile({ ...byId(1), global_level: 6 }, skills, 'en').globalLevel).toBe(6);
		expect(playerProfile(byId(1), skills, 'en').globalLevel).toBeNull();
		expect(playerProfile(byId(3), skills, 'en').sports).toEqual([{ sport: 'Judo', level: 'league' }]);
	});
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `npx vitest run src/lib/builder/profile.test.js`
Expected: FAIL, cannot resolve `./profile.js`.

- [ ] **Step 3: Write the implementation**

```js
/**
 * What the builder's player sheet draws of a player (spec 2026-10-06-builder-player-preview).
 * Pure. The fallbacks are the scorer's own (`features`), so the sheet never disagrees with the
 * balance about which values are estimated.
 */
import { features } from './score.js';

/** The profile of `player` for the edition's `skills`, names in `locale` (anything but `en` is French). */
export function playerProfile(player, skills, locale) {
	const { skills: values, incomplete } = features(player, skills);
	return {
		rating: player.rating,
		globalLevel: player.global_level ?? null,
		frequency: player.sport_frequency || null,
		bars: skills.map((s) => ({
			identifier: s.identifier,
			name: locale === 'en' ? s.name_en : s.name_fr,
			value: values[s.identifier],
			estimated: player.ratings?.[s.identifier] == null
		})),
		sports: player.sports ?? [],
		incomplete
	};
}
```

- [ ] **Step 4: Run it to verify it passes**

Run: `npx vitest run src/lib/builder/profile.test.js`
Expected: PASS, 5 tests.

- [ ] **Step 5: Commit**

```bash
git add src/lib/builder/profile.js src/lib/builder/profile.test.js
git commit -m "[FEAT] builder: playerProfile, what the player sheet draws

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Dictionary keys

**Files:**
- Modify: `front/src/lib/i18n/fr.js` (after `'builder.incomplete'`, line ~199)
- Modify: `front/src/lib/i18n/en.js` (after `'builder.incomplete'`, line ~193)

`parity.test.js` fails until both dictionaries hold the same keys, so add both in one step.

- [ ] **Step 1: Add the French keys** after `'builder.incomplete': 'Profil incomplet',`

```js
	'builder.preview': 'Voir le profil de {name}',
	'builder.preview.tray': 'À placer',
	'builder.preview.rating': 'Note',
	'builder.preview.frequency': 'Pratique sportive',
	'builder.preview.skills': 'Compétences',
	'builder.preview.estimated': 'estimé',
	'builder.preview.sports': 'Sports',
	'builder.preview.noSports': 'Aucun sport renseigné',
	'builder.preview.close': 'Fermer',
```

- [ ] **Step 2: Add the English keys** after `'builder.incomplete': 'Incomplete profile',`

```js
	'builder.preview': 'View {name} profile',
	'builder.preview.tray': 'To place',
	'builder.preview.rating': 'Rating',
	'builder.preview.frequency': 'Sport frequency',
	'builder.preview.skills': 'Skills',
	'builder.preview.estimated': 'estimated',
	'builder.preview.sports': 'Sports',
	'builder.preview.noSports': 'No sport given',
	'builder.preview.close': 'Close',
```

The sheet reuses `builder.team`, `builder.incomplete`, `register.globalLevel`, `register.frequency.*` and `register.level.*`.

- [ ] **Step 3: Run the parity test**

Run: `npx vitest run src/lib/i18n`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/lib/i18n/fr.js src/lib/i18n/en.js
git commit -m "[FEAT] builder: dictionary keys for the player preview

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 3: The sheet

**Files:**
- Create: `front/src/lib/components/builder/PlayerSheet.svelte`
- Test: `front/src/lib/components/builder/PlayerSheet.test.js`

Props: `open`, `player`, `skills`, `teamIndex` (`-1` for the tray), `opener` (the element to focus on close). Event: `close`.

- [ ] **Step 1: Write the failing test**

```js
import { fireEvent, screen, within } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import { renderWith } from '$lib/test-utils';
import { builderPayload } from '$lib/fixtures/builder.js';
import PlayerSheet from './PlayerSheet.svelte';

const { players, skills } = builderPayload;
const byId = (id) => players.find((p) => p.id === id);
const props = (id, over = {}) => ({ open: true, player: byId(id), skills, teamIndex: -1, ...over });
const dialog = () => screen.getByRole('dialog', { name: /./ });

describe('PlayerSheet', () => {
	it('renders nothing while closed', () => {
		renderWith(PlayerSheet, props(1, { open: false }));

		expect(screen.queryByRole('dialog')).toBeNull();
	});

	it('shows the name, the summary and one bar per skill', () => {
		renderWith(PlayerSheet, props(1, { player: { ...byId(1), global_level: 6 } }));

		const sheet = within(screen.getByRole('dialog', { name: 'Léa Martin' }));
		expect(sheet.getByText('To place')).toBeInTheDocument();
		expect(sheet.getByText('Rating').nextSibling).toHaveTextContent('8');
		expect(sheet.getByText('Overall level').nextSibling).toHaveTextContent('6');
		expect(sheet.getByText('At least four hours a week')).toBeInTheDocument();
		expect(sheet.getByText('Cardio').parentElement).toHaveTextContent('9');
		expect(sheet.getByText('Strength').parentElement).toHaveTextContent('7');
		expect(sheet.queryByText('estimated')).toBeNull();
		expect(sheet.queryByText('Incomplete profile')).toBeNull();
	});

	it('says which team the player is in', () => {
		renderWith(PlayerSheet, props(1, { teamIndex: 2 }));

		expect(within(dialog()).getByText('Team 3')).toBeInTheDocument();
	});

	it('marks estimated skills and the incomplete profile, and shows a dash for what is unknown', () => {
		renderWith(PlayerSheet, props(5));

		const sheet = within(dialog());
		expect(sheet.getAllByText('estimated')).toHaveLength(2);
		expect(sheet.getByText('Incomplete profile')).toBeInTheDocument();
		expect(sheet.getByText('Overall level').nextSibling).toHaveTextContent('—');
		expect(sheet.getByText('Sport frequency').nextSibling).toHaveTextContent('—');
	});

	it('lists the sports with their level, or says there is none', () => {
		const { unmount } = renderWith(PlayerSheet, props(3));
		expect(within(dialog()).getByText('Judo · In a club, with competitions')).toBeInTheDocument();
		unmount();

		renderWith(PlayerSheet, props(1));
		expect(within(dialog()).getByText('No sport given')).toBeInTheDocument();
	});

	it('closes on Escape and on its button', async () => {
		const { component } = renderWith(PlayerSheet, props(1));
		let closed = 0;
		component.$on('close', () => closed++);

		await fireEvent.keyDown(window, { key: 'Escape' });
		await fireEvent.click(screen.getByRole('button', { name: 'Close' }));

		expect(closed).toBe(2);
	});

	it('gives focus back to the opener on close', async () => {
		const opener = document.createElement('button');
		document.body.append(opener);
		renderWith(PlayerSheet, props(1, { opener }));

		await fireEvent.click(screen.getByRole('button', { name: 'Close' }));

		expect(document.activeElement).toBe(opener);
		opener.remove();
	});

	it('speaks French', () => {
		renderWith(PlayerSheet, props(3, { teamIndex: 0 }), 'fr');

		const sheet = within(screen.getByRole('dialog', { name: 'Paul Petit' }));
		expect(sheet.getByText('Équipe 1')).toBeInTheDocument();
		expect(sheet.getByText('Force')).toBeInTheDocument();
		expect(sheet.getByRole('button', { name: 'Fermer' })).toBeInTheDocument();
	});
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `npx vitest run src/lib/components/builder/PlayerSheet.test.js`
Expected: FAIL, cannot resolve `./PlayerSheet.svelte`.

- [ ] **Step 3: Write the component**

```svelte
<script>
	import { createEventDispatcher, tick } from 'svelte';
	import { useLocale, useT } from '$lib/i18n';
	import { fullName } from '$lib/players';
	import { modal } from '$lib/modal';
	import { playerProfile } from '$lib/builder/profile.js';

	export let open = false;
	export let player = null;
	export let skills;
	/** The team's index, -1 for a player still in the tray. */
	export let teamIndex = -1;
	/** What had focus before the sheet opened: it gets it back on close. */
	export let opener = null;

	const t = useT();
	const locale = useLocale();
	const dispatch = createEventDispatcher();

	let sheetEl = null;
	$: if (open && sheetEl) tick().then(() => sheetEl?.focus());

	function close() {
		dispatch('close');
		opener?.focus();
	}

	$: profile = player ? playerProfile(player, skills, locale) : null;
	$: name = player ? fullName(player) : '';
	const shown = (value) => Math.round(value * 10) / 10;
</script>

{#if open && player}
	<div class="backdrop" data-testid="backdrop" on:click={close} aria-hidden="true"></div>
	<div
		class="sheet"
		role="dialog"
		aria-modal="true"
		aria-labelledby="player-sheet-title"
		tabindex="-1"
		bind:this={sheetEl}
		use:modal={{ onClose: close }}
	>
		<h2 id="player-sheet-title">{name}</h2>
		<p class="where">{teamIndex >= 0 ? t('builder.team', { n: teamIndex + 1 }) : t('builder.preview.tray')}</p>

		<dl class="summary">
			<div>
				<dt>{t('builder.preview.rating')}</dt>
				<dd class="num">{profile.rating}</dd>
			</div>
			<div>
				<dt>{t('register.globalLevel')}</dt>
				<dd class="num">{profile.globalLevel ?? '—'}</dd>
			</div>
			<div>
				<dt>{t('builder.preview.frequency')}</dt>
				<dd>{profile.frequency ? t(`register.frequency.${profile.frequency}`) : '—'}</dd>
			</div>
		</dl>

		<h3>{t('builder.preview.skills')}</h3>
		<ul class="bars">
			{#each profile.bars as bar (bar.identifier)}
				<li class:estimated={bar.estimated}>
					<span class="skill">{bar.name}</span>
					<span class="track" aria-hidden="true"><span class="fill" style="width: {bar.value * 10}%"></span></span>
					<span class="value num">{shown(bar.value)}</span>
					{#if bar.estimated}<span class="note">{t('builder.preview.estimated')}</span>{/if}
				</li>
			{/each}
		</ul>
		{#if profile.incomplete}<p class="incomplete">{t('builder.incomplete')}</p>{/if}

		<h3>{t('builder.preview.sports')}</h3>
		{#if profile.sports.length === 0}
			<p class="none">{t('builder.preview.noSports')}</p>
		{:else}
			<ul class="sports">
				{#each profile.sports as s}
					<li>{s.sport} · {t(`register.level.${s.level}`)}</li>
				{/each}
			</ul>
		{/if}

		<div class="actions">
			<button type="button" on:click={close}>{t('builder.preview.close')}</button>
		</div>
	</div>
{/if}

<style>
	.backdrop {
		position: fixed;
		inset: 0;
		background: var(--scrim);
		z-index: 30;
	}
	.sheet {
		position: fixed;
		left: 0;
		right: 0;
		bottom: 0;
		z-index: 31;
		background: var(--bg-raised);
		border: 1px solid var(--line);
		border-radius: var(--radius-lg) var(--radius-lg) 0 0;
		padding: 1rem 1rem calc(1rem + env(safe-area-inset-bottom));
		max-height: 90vh;
		max-height: 90dvh;
		overflow-y: auto;
		overscroll-behavior: contain;
	}
	h2 {
		margin: 0;
		text-align: center;
	}
	h3 {
		margin: 1rem 0 0.5rem;
		font-size: 1rem;
		font-family: var(--font-body);
		text-transform: none;
		letter-spacing: 0;
	}
	.where {
		margin: 0.2rem 0 1rem;
		text-align: center;
		color: var(--muted);
	}
	.summary {
		display: grid;
		gap: 0.5rem;
		margin: 0;
	}
	.summary div {
		display: flex;
		justify-content: space-between;
		gap: 1rem;
	}
	dt {
		color: var(--muted);
	}
	dd {
		margin: 0;
		text-align: right;
		color: var(--ink);
	}
	.bars,
	.sports {
		display: grid;
		gap: 0.375rem;
		margin: 0;
		padding: 0;
		list-style: none;
	}
	.bars li {
		display: grid;
		grid-template-columns: 6rem 1fr 2rem;
		gap: 0.5rem;
		align-items: center;
	}
	.skill {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.track {
		display: block;
		height: 0.5rem;
		background: var(--bg);
		border: 1px solid var(--line);
		border-radius: 999px;
		overflow: hidden;
	}
	.fill {
		display: block;
		height: 100%;
		background: var(--accent);
	}
	.estimated .fill {
		opacity: 0.35;
	}
	.value {
		text-align: right;
	}
	.note {
		grid-column: 2 / 4;
		font-size: 0.8125rem;
		color: var(--muted);
	}
	.incomplete {
		margin: 0.5rem 0 0;
		font-size: 0.8125rem;
		color: var(--loss);
	}
	.none {
		margin: 0;
		color: var(--muted);
	}
	.actions {
		display: flex;
		justify-content: center;
		margin-top: 1rem;
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
	.actions button:focus-visible {
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

- [ ] **Step 4: Run it to verify it passes**

Run: `npx vitest run src/lib/components/builder/PlayerSheet.test.js`
Expected: PASS, 8 tests. If a `nextSibling` assertion fails because of whitespace nodes, switch it to `getByText('Rating').parentElement` with `toHaveTextContent('Rating8')`-style matching, keeping the intent (the value sits beside its label).

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/builder/PlayerSheet.svelte src/lib/components/builder/PlayerSheet.test.js
git commit -m "[FEAT] builder: PlayerSheet, a player's full rating profile in the shared modal

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 4: The eye button on the card

**Files:**
- Modify: `front/src/lib/components/builder/PlayerCard.svelte`
- Test: `front/src/lib/components/builder/PlayerCard.test.js`

- [ ] **Step 1: Add the failing tests** at the end of the `describe` block in `PlayerCard.test.js`

```js
	it('has an eye button, in the tray as in a team, that asks to preview the player', async () => {
		for (const index of [-1, 0]) {
			const { component, unmount } = renderWith(PlayerCard, { player, teamCount: 2, index });
			const seen = [];
			component.$on('preview', (e) => seen.push(e.detail));

			const button = screen.getByRole('button', { name: 'View Léa Martin profile' });
			await fireEvent.click(button);

			expect(seen).toEqual([{ id: 1, opener: button }]);
			unmount();
		}
	});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `npx vitest run src/lib/components/builder/PlayerCard.test.js`
Expected: FAIL, no button named « View Léa Martin profile ».

- [ ] **Step 3: Implement.** In `PlayerCard.svelte`:

Add the handler after `change()`:

```js
	function preview(event) {
		dispatch('preview', { id: player.id, opener: event.currentTarget });
	}
```

Mark placed cards for the layout: change the `<li class="card" …>` line to

```svelte
<li class="card" class:locked class:placed={index !== -1} class:dragging draggable="true" on:dragstart={dragStart} on:dragend={() => (dragging = false)}>
```

Add the button first inside `.actions`, after the closing `{/if}` of the select and before the lock's `{#if index !== -1}`:

```svelte
			<button type="button" class="icon-button" aria-label={t('builder.preview', { name })} on:click={preview}>
				<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" /><circle cx="12" cy="12" r="3" /></svg>
			</button>
```

In the desktop media query, make room for one button in the tray and two on a placed card. Replace

```css
		.top {
			padding-right: 2.5rem;
		}
```

with

```css
		.top {
			padding-right: 2.5rem;
		}
		.card.placed .top {
			padding-right: 5rem;
		}
```

- [ ] **Step 4: Run the card tests**

Run: `npx vitest run src/lib/components/builder/PlayerCard.test.js`
Expected: PASS (the existing tests are unaffected: they query the combobox and the card).

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/builder/PlayerCard.svelte src/lib/components/builder/PlayerCard.test.js
git commit -m "[FEAT] builder: an eye button on each card asks to preview the player

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Forward the event, wire the page

**Files:**
- Modify: `front/src/lib/components/builder/BuilderTeams.svelte`
- Modify: `front/src/routes/[year=year]/builder/+page.svelte`
- Test: `front/src/routes/[year=year]/builder/page.test.js`

- [ ] **Step 1: Add the failing page tests** inside the `describe('team builder page', …)` block of `page.test.js`

```js
	it('opens a player sheet from the eye button and gives focus back on close', async () => {
		renderWith(Page, { data: data() });
		await goTo('Teams');

		const eye = screen.getByRole('button', { name: 'View Léa Martin profile' });
		await fireEvent.click(eye);

		const sheet = within(screen.getByRole('dialog', { name: 'Léa Martin' }));
		expect(sheet.getByText('To place')).toBeInTheDocument();
		expect(sheet.getByText('Cardio')).toBeInTheDocument();

		await fireEvent.click(sheet.getByRole('button', { name: 'Close' }));

		expect(screen.queryByRole('dialog')).toBeNull();
		expect(document.activeElement).toBe(eye);
	});

	it('names the team of a placed player in the sheet', async () => {
		renderWith(Page, { data: data() });
		await propose();

		const region = teamRegions()[0];
		await fireEvent.click(within(region).getAllByRole('button', { name: /^View .* profile$/ })[0]);

		expect(within(screen.getByRole('dialog')).getByText('Team 1')).toBeInTheDocument();
	});
```

- [ ] **Step 2: Run them to verify they fail**

Run: `npx vitest run "src/routes/[year=year]/builder/page.test.js"`
Expected: the two new tests FAIL (no dialog opens); the rest PASS.

- [ ] **Step 3: Forward `preview` in `BuilderTeams.svelte`.** Add `on:preview` to both card usages. The tray card becomes:

```svelte
					<PlayerCard player={byId.get(id)} teamCount={teams.length} incomplete={incomplete.has(id)} notes={showRequests ? notesFor(byId.get(id)) : []} on:move on:preview />
```

and the team card's handler list becomes:

```svelte
						on:move
						on:lock
						on:preview
```

- [ ] **Step 4: Wire the page** (`+page.svelte`).

Import the sheet next to the other builder components:

```js
	import PlayerSheet from '$lib/components/builder/PlayerSheet.svelte';
```

After `function toggleLock(...) { ... }` add:

```js
	let preview = null; // { id, opener } while a player's sheet is open
	function openPreview({ detail }) {
		preview = detail;
	}
	$: previewed = preview ? byId.get(preview.id) ?? null : null;
	// A player who left the roster (a reloaded draft) closes the sheet.
	$: if (preview && !previewed) preview = null;
	$: previewTeam = previewed ? draft.teams.findIndex((tm) => tm.players.includes(previewed.id)) : -1;
```

Add `on:preview={openPreview}` to the `<BuilderTeams …>` element (next to `on:move={move}`).

Render the sheet once, right after the `<BuilderTeams …/>` element's closing (still inside the same step block, before the block's closing tag):

```svelte
			<PlayerSheet
				open={previewed !== null}
				player={previewed}
				skills={builder.skills}
				teamIndex={previewTeam}
				opener={preview?.opener ?? null}
				on:close={() => (preview = null)}
			/>
```

Check how `<BuilderTeams` closes in the file (`sed -n 244,275p "src/routes/[year=year]/builder/+page.svelte"`) and put the sheet after it, inside the same `{#if step === 2}`-style block, so it exists only on the teams step.

- [ ] **Step 5: Run the page tests**

Run: `npx vitest run "src/routes/[year=year]/builder"`
Expected: PASS. If the focus assertion fails because `close()` focuses the opener before Svelte clears `preview`, that is fine (the opener node is still in the DOM, a tray card does not re-render on close). If the opener was detached by a re-render, no test covers it and the behaviour is a harmless no-op.

- [ ] **Step 6: Commit**

```bash
git add src/lib/components/builder/BuilderTeams.svelte "src/routes/[year=year]/builder/+page.svelte" "src/routes/[year=year]/builder/page.test.js"
git commit -m "[FEAT] builder: open a player's sheet from the eye button

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Docs and the whole suite

**Files:**
- Modify: `CLAUDE.md` (repo root), team builder paragraph
- Modify: `docs/superpowers/specs/2026-10-06-builder-player-preview-design.md`

- [ ] **Step 1: Document it.** In `CLAUDE.md`, in the team builder paragraph, right after the sentence ending « …(`builder.link`) for an organiser of the latest edition while the edition has no team. », add:

```
 Each card has an eye button (`builder.preview`) that opens `PlayerSheet` (`$lib/components/builder/`, the shared `modal` dialog), a player's rating profile for the organisers: overall rating, global level, frequency, one bar per skill and the sports; `$lib/builder/profile.js` (`playerProfile`) derives it from `features()` so a skill the player never rated shows the overall rating, dimmed and marked « estimé », exactly as the scorer reads it. The page keeps one `preview` (`{id, opener}`), closes the sheet when the player leaves the roster and gives focus back to the eye button; the wishes stay on the card. Spec `2026-10-06-builder-player-preview-design.md`.
```

- [ ] **Step 2: Sync the spec with what was built.** In the spec's i18n paragraph, replace the key list with: `builder.preview` (« Voir le profil de {name} »), `builder.preview.tray`, `.rating`, `.frequency`, `.skills`, `.estimated`, `.sports`, `.noSports`, `.close`; reused: `builder.team`, `builder.incomplete`, `register.globalLevel`, `register.frequency.*`, `register.level.*`.

- [ ] **Step 3: Run the full front suite and the build**

Run: `npm test && npm run build`
Expected: all tests PASS, build succeeds.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md docs/superpowers/specs/2026-10-06-builder-player-preview-design.md
git commit -m "[DOCS] builder player preview: CLAUDE.md and spec sync

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

## Self-review

- **Spec coverage:** trigger on every card, tray and teams (Task 4); sheet content, estimated fallback, dash for unknowns, sports, team subtitle, no wishes (Task 3); modal pattern with focus return via `opener` (Tasks 3, 5); pure helper reusing `features` (Task 1); i18n parity (Task 2); a player leaving the roster closes the sheet (Task 5 reactive guard); tests per spec (all tasks); sort/filter deliberately not built.
- **Types:** `playerProfile` returns `{rating, globalLevel, frequency, bars[{identifier,name,value,estimated}], sports, incomplete}`, used identically in the sheet; `preview` detail is `{id, opener}` in the card test, the page's `openPreview` and the sheet's `opener` prop; `teamIndex` is -1 for the tray everywhere.
- **No placeholders:** the only conditional wording is the Step 5 fallbacks, which name the exact change.
