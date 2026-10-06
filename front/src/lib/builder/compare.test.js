import { describe, expect, it } from 'vitest';
import { builderPayload } from '$lib/fixtures/builder.js';
import { emptyDraft } from './plan.js';
import { makeScorer } from './score.js';
import { compareProfiles, swapPreview } from './compare.js';

const { players, skills } = builderPayload;
const byId = (id) => players.find((p) => p.id === id);

describe('compareProfiles', () => {
	it('gives one row per skill with who leads and by how much', () => {
		const { rows } = compareProfiles(byId(1), byId(2), skills, 'en');

		expect(rows.map((r) => r.name)).toEqual(['Cardio', 'Strength']);
		expect(rows[0]).toMatchObject({ a: 9, b: 5, lead: 'a', delta: 4 });
		expect(rows[1]).toMatchObject({ a: 7, b: 7, lead: null, delta: 0 });
	});

	it('flags the estimated side and names skills in the locale', () => {
		const { rows } = compareProfiles(byId(1), byId(5), skills, 'fr');

		expect(rows[1]).toMatchObject({ name: 'Force', aEstimated: false, bEstimated: true, b: 3, lead: 'a' });
	});
});

describe('swapPreview', () => {
	const draft = { ...emptyDraft(), teams: [{ players: [1, 5] }, { players: [2, 3] }, { players: [4, 6] }] };
	const scorer = makeScorer(players, [{ player: 1, kind: 'with', target: 2 }], skills);

	it('shows the two teams a swap touches and the unmet requests before and after', () => {
		const preview = swapPreview(draft, 5, 2, scorer);

		expect(preview.teams.map((t) => t.index)).toEqual([0, 1]);
		expect(preview.teams[0].before).toBeCloseTo(5.5);
		expect(preview.teams[0].after).toBeCloseTo(7);
		expect(preview.unmet).toEqual({ before: 1, after: 0 });
	});

	it('shows one team for a swap with the tray and leaves the draft alone', () => {
		const copy = JSON.parse(JSON.stringify(draft));
		const preview = swapPreview(draft, 5, 99, scorer);

		expect(preview.teams.map((t) => t.index)).toEqual([0]);
		expect(draft).toEqual(copy);
	});

	it('is null when the swap is blocked', () => {
		expect(swapPreview(draft, 1, 5, scorer)).toBeNull();
		expect(swapPreview({ ...draft, locked: [1] }, 1, 2, scorer)).toBeNull();
	});
});
