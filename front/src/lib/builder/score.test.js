import { describe, expect, it } from 'vitest';
import { WEIGHTS, features, makeScorer } from './score.js';

const skills = [{ identifier: 'CARD' }, { identifier: 'STR' }];
const player = (id, over = {}) => ({
	id, rating: 5, ratings: { CARD: 5, STR: 5 }, sport_frequency: 'hour', sports: [], ...over
});

describe('features', () => {
	it('uses the ratings and flags the experienced', () => {
		expect(features(player(1, { ratings: { CARD: 8, STR: 2 } }), skills)).toMatchObject({
			rating: 5, skills: { CARD: 8, STR: 2 }, experienced: false, incomplete: false
		});
		expect(features(player(1, { sport_frequency: 'two_hours' }), skills).experienced).toBe(true);
		expect(features(player(1, { sports: [{ sport: 'Judo', level: 'league' }] }), skills).experienced).toBe(true);
		expect(features(player(1, { sports: [{ sport: 'Judo', level: 'club' }] }), skills).experienced).toBe(false);
	});

	it('falls back to the overall rating and the middle frequency, and says so', () => {
		const f = features(player(1, { rating: 7, ratings: { CARD: 9 }, sport_frequency: '' }), skills);

		expect(f.skills).toEqual({ CARD: 9, STR: 7 });
		expect(f.incomplete).toBe(true);
		expect(f.experienced).toBe(false);
	});

	it('does not call a player without sports incomplete', () => {
		expect(features(player(1), skills).incomplete).toBe(false);
	});
});

describe('makeScorer', () => {
	const ps = [
		player(1, { rating: 9, ratings: { CARD: 9, STR: 9 } }),
		player(2, { rating: 9, ratings: { CARD: 9, STR: 9 } }),
		player(3, { rating: 1, ratings: { CARD: 1, STR: 1 } }),
		player(4, { rating: 1, ratings: { CARD: 1, STR: 1 } })
	];
	const scorer = (links = []) => makeScorer(ps, links, skills);

	it('scores a balanced split below an unbalanced one', () => {
		const score = scorer();

		expect(score([[1, 3], [2, 4]]).total).toBeLessThan(score([[1, 2], [3, 4]]).total);
		expect(score([[1, 3], [2, 4]]).parts.rating).toBe(0);
	});

	it('balances each skill, not only the overall rating', () => {
		const odd = [
			player(1, { rating: 5, ratings: { CARD: 9, STR: 1 } }),
			player(2, { rating: 5, ratings: { CARD: 9, STR: 1 } }),
			player(3, { rating: 5, ratings: { CARD: 1, STR: 9 } }),
			player(4, { rating: 5, ratings: { CARD: 1, STR: 9 } })
		];
		const score = makeScorer(odd, [], skills);

		expect(score([[1, 3], [2, 4]]).parts.rating).toBe(0);
		expect(score([[1, 3], [2, 4]]).parts.skills).toBe(0);
		expect(score([[1, 2], [3, 4]]).parts.skills).toBeGreaterThan(0);
	});

	it('reports an unmet "with" and a broken "avoid", once per pair', () => {
		const links = [
			{ player: 1, kind: 'with', target: 3 },
			{ player: 3, kind: 'with', target: 1 },
			{ player: 2, kind: 'avoid', target: 4 }
		];
		const result = scorer(links)([[1, 2, 4], [3]]);

		expect(result.unmet).toEqual([
			{ kind: 'with', player: 1, target: 3, mutual: true },
			{ kind: 'avoid', player: 2, target: 4, mutual: false }
		]);
	});

	it('counts a request met when it is, and ignores one with an unplaced player', () => {
		const links = [{ player: 1, kind: 'with', target: 2 }, { player: 3, kind: 'avoid', target: 4 }];

		expect(scorer(links)([[1, 2], [3]]).unmet).toEqual([]);
	});

	it('weighs a broken avoid above an unmet mutual with above a one-sided with', () => {
		expect(WEIGHTS.avoid).toBeGreaterThan(2 * WEIGHTS.with);
		expect(WEIGHTS.with).toBeGreaterThan(0);
		const teams = [[1, 3], [2, 4]];
		const withOne = scorer([{ player: 1, kind: 'with', target: 2 }])(teams).total;
		const withMutual = scorer([{ player: 1, kind: 'with', target: 2 }, { player: 2, kind: 'with', target: 1 }])(teams).total;
		const avoid = scorer([{ player: 1, kind: 'avoid', target: 3 }])(teams).total;
		const none = scorer()(teams).total;
		expect(withOne).toBeGreaterThan(none);
		expect(withMutual).toBeGreaterThan(withOne);
		expect(avoid).toBeGreaterThan(withMutual);
	});

	it('returns each team average rating and skill averages for the display', () => {
		const result = scorer()([[1, 3], [2, 4]]);

		expect(result.teams).toEqual([
			{ size: 2, rating: 5, skills: { CARD: 5, STR: 5 }, experienced: 0 },
			{ size: 2, rating: 5, skills: { CARD: 5, STR: 5 }, experienced: 0 }
		]);
	});
});
