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

import { swapBlock, swapPlayers } from './plan.js';

describe('swapPlayers', () => {
	const draft = draftOf({ teams: [{ players: [1, 2] }, { players: [3, 4] }], locked: [] });

	it('exchanges two teams, each player taking the other slot', () => {
		expect(swapPlayers(draft, 1, 4).teams).toEqual([{ players: [4, 2] }, { players: [3, 1] }]);
	});

	it('puts a tray player in the team and sends the other to the tray, either way round', () => {
		expect(swapPlayers(draft, 2, 9).teams).toEqual([{ players: [1, 9] }, { players: [3, 4] }]);
		expect(swapPlayers(draft, 9, 2).teams).toEqual([{ players: [1, 9] }, { players: [3, 4] }]);
	});

	it('is its own undo and leaves the draft it was given alone', () => {
		const once = swapPlayers(draft, 1, 4);
		expect(swapPlayers(once, 1, 4)).toEqual(draft);
		expect(draft.teams[0].players).toEqual([1, 2]);
	});

	it('refuses the same team, the tray with the tray, and a locked player', () => {
		expect(swapPlayers(draft, 1, 2)).toBeNull();
		expect(swapPlayers(draft, 8, 9)).toBeNull();
		expect(swapPlayers({ ...draft, locked: [1] }, 1, 4)).toBeNull();
		expect(swapPlayers({ ...draft, locked: [4] }, 1, 4)).toBeNull();
	});

	it('names the reason, locked before the placement', () => {
		expect(swapBlock({ ...draft, locked: [1] }, 1, 2)).toBe('locked');
		expect(swapBlock(draft, 1, 2)).toBe('sameTeam');
		expect(swapBlock(draft, 8, 9)).toBe('bothTray');
		expect(swapBlock(draft, 1, 4)).toBeNull();
		expect(swapBlock(emptyDraft(), 1, 2)).toBe('bothTray');
	});
});
