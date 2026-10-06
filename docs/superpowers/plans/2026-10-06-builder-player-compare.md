# Builder player compare Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** From a player's sheet, compare them with a second player on a butterfly table, preview the effect of swapping them, and swap in one draft update.

**Architecture:** Pure logic in `$lib/builder/plan.js` (`swapBlock`, `swapPlayers`) and a new `$lib/builder/compare.js` (`compareProfiles`, `swapPreview`). `PlayerSheet` stays presentational: the page owns `compareId`, derives the other player, the block reason and the preview, and applies a `swap` event through one `commit`. Spec: `docs/superpowers/specs/2026-10-06-builder-player-compare-design.md`.

**Tech Stack:** SvelteKit 2 / Svelte 4, plain JS, Vitest + @testing-library/svelte. Run tests from `front/` with `npx vitest run <path>`.

---

### Task 1: Swap rules in `plan.js`

**Files:**
- Modify: `front/src/lib/builder/plan.js`
- Test: `front/src/lib/builder/plan.test.js`

- [ ] **Step 1: Failing tests** for `swapBlock(draft, a, b)` (returns `null` or `'locked' | 'sameTeam' | 'bothTray'`, checked in that order) and `swapPlayers(draft, a, b)` (new draft, or `null` when blocked): team vs team exchanges teams and keeps slots, team vs tray both ways, same team / both tray / locked give `null`, and swapping twice restores the draft.
- [ ] **Step 2:** `npx vitest run src/lib/builder/plan.test.js` fails (not exported).
- [ ] **Step 3: Implement**

```js
const teamIndexOf = (draft, id) => draft.teams.findIndex((t) => t.players.includes(id));

/** Why a and b cannot be swapped, or null: locked first, then same team, then both in the tray. */
export function swapBlock(draft, a, b) {
	if (draft.locked.includes(a) || draft.locked.includes(b)) return 'locked';
	const ta = teamIndexOf(draft, a);
	const tb = teamIndexOf(draft, b);
	if (ta === tb) return ta === -1 ? 'bothTray' : 'sameTeam';
	return null;
}

/** The draft with a and b exchanged, each taking the other's slot; null when the swap is blocked. */
export function swapPlayers(draft, a, b) {
	if (swapBlock(draft, a, b)) return null;
	const swap = (id) => (id === a ? b : id === b ? a : id);
	return { ...draft, teams: draft.teams.map((t) => ({ players: t.players.map(swap) })) };
}
```

- [ ] **Step 4:** tests pass. **Step 5:** commit `[FEAT] builder: swap rules`.

### Task 2: `compare.js`

**Files:**
- Create: `front/src/lib/builder/compare.js`, `front/src/lib/builder/compare.test.js`

- [ ] **Step 1: Failing tests** on `$lib/fixtures/builder.js`: `compareProfiles(pa, pb, skills, locale)` gives `{ a, b, rows }` (the two `playerProfile`s and one row per skill `{ identifier, name, a, b, aEstimated, bEstimated, lead, delta }`, `lead` `'a'|'b'|null`, `delta` the absolute difference rounded to one decimal; a tie leads `null`; an estimated value is flagged). `swapPreview(draft, a, b, scorer)` gives `null` when blocked, else `{ teams: [{ index, before, after }], unmet: { before, after } }` (one team for a team/tray swap, two otherwise, ascending index; averages from `scorer(teamIds).teams[i].rating`, `unmet` the length of `.unmet`), and never mutates `draft`.
- [ ] **Step 2:** fails. **Step 3: Implement**

```js
import { playerProfile } from './profile.js';
import { swapBlock, swapPlayers } from './plan.js';

export function compareProfiles(pa, pb, skills, locale) {
	const a = playerProfile(pa, skills, locale);
	const b = playerProfile(pb, skills, locale);
	const rows = a.bars.map((bar, i) => {
		const other = b.bars[i];
		const delta = Math.round(Math.abs(bar.value - other.value) * 10) / 10;
		return {
			identifier: bar.identifier,
			name: bar.name,
			a: bar.value,
			b: other.value,
			aEstimated: bar.estimated,
			bEstimated: other.estimated,
			lead: delta === 0 ? null : bar.value > other.value ? 'a' : 'b',
			delta
		};
	});
	return { a, b, rows };
}

export function swapPreview(draft, a, b, scorer) {
	const swapped = swapPlayers(draft, a, b);
	if (!swapped) return null;
	const before = scorer(draft.teams.map((t) => t.players));
	const after = scorer(swapped.teams.map((t) => t.players));
	const teams = draft.teams
		.map((t, index) => ({ index, changed: t.players.includes(a) !== t.players.includes(b) }))
		.filter((t) => t.changed)
		.map(({ index }) => ({ index, before: before.teams[index].rating, after: after.teams[index].rating }));
	return { teams, unmet: { before: before.unmet.length, after: after.unmet.length } };
}
```

- [ ] **Step 4:** pass. **Step 5:** commit `[FEAT] builder: compare table rows and swap preview`.

### Task 3: i18n

**Files:** `front/src/lib/i18n/fr.js`, `en.js` (parity test `parity.test.js`).

- [ ] Add after `builder.preview.close`: `builder.compare.open`, `.pick`, `.search`, `.change`, `.close`, `.swap`, `.locked`, `.sameTeam`, `.bothTray`, `.blocked` (draft not editable), `.average` (`{team} : {before} → {after}`), `.up`, `.down`, `.unmet` (`{before} → {after}`), `.better`, `.worse`, `.same`, `.noResults`, `.rating`, `.lead` (`+{n}`), `.tray` is reused from `builder.preview.tray`. Run `npx vitest run src/lib/i18n` to confirm parity.
- [ ] Commit `[FEAT] builder: compare strings`.

### Task 4: `PlayerSheet` compare mode

**Files:** `front/src/lib/components/builder/PlayerSheet.svelte`, `PlayerSheet.test.js`

New props: `candidates` (`[{ id, name, teamIndex, rating }]`, every other player, sorted by the page), `other` (the compared player or null), `otherTeamIndex`, `swapReason` (`null` when the swap is allowed, else `'locked' | 'sameTeam' | 'bothTray' | 'blocked'`), `preview` (a `swapPreview` result or null), `nameOf`-free: names come from `fullName`. New events: `compare` (`{ id }`), `uncompare`, `swap`.

- [ ] **Step 1: Failing tests:** the picker opens from « Compare with… », lists everyone but A and filters accent-insensitively (`normalize('NFD')` stripped), « No result » text; choosing a row dispatches `compare`; with `other` set the sheet renders a `<table>` whose header names both players, one row per skill with both values, a `+n` marker on the leading side, `estimated`; Change returns to the picker, Close comparison dispatches `uncompare`; the swap button is disabled and `aria-describedby` its reason for each `swapReason`; enabled it dispatches `swap`; the preview lines show `before → after` with the words; Escape inside the picker closes only the picker; a French render.
- [ ] **Step 2:** fail. **Step 3: Implement.** Local state `picking` and `query`; `picking` resets when `open` or `player` changes. Use `compareProfiles(player, other, skills, locale)` for the table; bars are `aria-hidden` spans (A's right-aligned growing left, B's left-aligned growing right) with the numbers as text cells; a wider `.sheet` (560px from 1000px) while comparing; the preview block `aria-live="polite"` (never `role="status"`). Words: average up/down/same by `after` vs `before` rounded to one decimal; unmet better when fewer.
- [ ] **Step 4:** pass. **Step 5:** commit `[FEAT] builder: compare two players in the sheet`.

### Task 5: Page wiring

**Files:** `front/src/routes/[year=year]/builder/+page.svelte`, `page.test.js`

- [ ] **Step 1: Failing page tests:** open the sheet on a placed player, pick another in another team, swap: both placements change in one `PUT` (one saver call), the sheet stays open on the pair, a second swap restores them; the swap is disabled for a locked player; `compareId` clears when the sheet closes and when the other leaves the roster.
- [ ] **Step 2:** fail. **Step 3: Implement** in the page:

```js
let compareId = null;
$: if (!preview || compareId === preview.id || (compareId !== null && !byId.has(compareId))) compareId = null;
$: other = compareId !== null ? byId.get(compareId) ?? null : null;
$: otherTeam = other ? draft.teams.findIndex((tm) => tm.players.includes(other.id)) : -1;
$: swapReason = previewed && other ? (saveBlocked ? 'blocked' : swapBlock(draft, previewed.id, other.id)) : null;
$: swapView = previewed && other && !swapReason ? swapPreview(draft, previewed.id, other.id, scorer) : null;
$: candidates = previewed
	? players.filter((p) => p.id !== previewed.id)
		.map((p) => ({ id: p.id, name: fullName(p), teamIndex: draft.teams.findIndex((tm) => tm.players.includes(p.id)), rating: p.rating }))
		.sort((x, y) => x.name.localeCompare(y.name))
	: [];
function swap({ detail: { a, b } }) {
	const next = swapPlayers(draft, a, b);
	if (next && !saveBlocked) commit(next);
}
```

  Wire `candidates`, `other`, `otherTeamIndex={otherTeam}`, `swapReason`, `preview={swapView}`, `on:compare={({ detail }) => (compareId = detail.id)}`, `on:uncompare={() => (compareId = null)}`, `on:swap={swap}`. (`preview` is already the page's variable name for the open sheet: the prop is passed as `preview={swapView}` and the sheet names it `swapPreview` internally to avoid confusion.)
- [ ] **Step 4:** pass. **Step 5:** commit `[FEAT] builder: swap two players from the compare sheet`.

### Task 6: Docs and verification

- [ ] Add a « Player compare » paragraph to the Team builder section of `CLAUDE.md` (spec link, the swap rules, the one-update swap, files).
- [ ] `cd front && npm test && npm run build`; both pass.
- [ ] Commit `[DOCS] builder: player compare`.
