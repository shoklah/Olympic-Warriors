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
