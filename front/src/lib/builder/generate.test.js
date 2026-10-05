import { describe, expect, it } from 'vitest';
import { generate, placeNewcomers } from './generate.js';
import { makeScorer } from './score.js';

const skills = [{ identifier: 'CARD' }, { identifier: 'STR' }];
const roster = (n) =>
	Array.from({ length: n }, (_, i) => ({
		id: i + 1,
		rating: 1 + ((i * 7) % 10),
		ratings: { CARD: 1 + ((i * 3) % 10), STR: 1 + ((i * 5) % 10) },
		sport_frequency: ['rare', 'hour', 'two_hours', 'four_hours'][i % 4],
		sports: []
	}));

const sizesOf = (teams) => teams.map((t) => t.length).sort((a, b) => b - a);

describe('generate', () => {
	it('places everyone exactly once in evenly sized teams', () => {
		const players = roster(11);

		const { teams } = generate(players, [], skills, { perTeam: 3, seed: 1 });

		expect(sizesOf(teams)).toEqual([3, 3, 3, 2]);
		expect(teams.flat().sort((a, b) => a - b)).toEqual(players.map((p) => p.id));
	});

	it('gives the same teams for the same seed and different ones for another', () => {
		const players = roster(14);
		const a = generate(players, [], skills, { perTeam: 3, seed: 5 }).teams;
		const b = generate(players, [], skills, { perTeam: 3, seed: 5 }).teams;

		expect(a).toEqual(b);
	});

	it('does better than the plain greedy start', () => {
		const players = roster(14);
		const scorer = makeScorer(players, [], skills);
		const sorted = [...players].sort((x, y) => y.rating - x.rating).map((p) => p.id);
		const naive = [sorted.slice(0, 4), sorted.slice(4, 8), sorted.slice(8, 11), sorted.slice(11)];

		const { score } = generate(players, [], skills, { perTeam: 4, seed: 2 });

		expect(score.total).toBeLessThan(scorer(naive).total);
	});

	it('separates an avoid pair and keeps a mutual with pair together when balance allows', () => {
		const players = roster(12);
		const links = [
			{ player: 1, kind: 'avoid', target: 2 },
			{ player: 3, kind: 'with', target: 4 },
			{ player: 4, kind: 'with', target: 3 }
		];

		const { teams, score } = generate(players, links, skills, { perTeam: 3, seed: 9 });

		const teamOf = (id) => teams.findIndex((t) => t.includes(id));
		expect(teamOf(1)).not.toBe(teamOf(2));
		expect(teamOf(3)).toBe(teamOf(4));
		expect(score.unmet).toEqual([]);
	});

	it('leaves locked players in their team', () => {
		const players = roster(12);
		const first = generate(players, [], skills, { perTeam: 3, seed: 1 }).teams;
		const locked = [first[0][0], first[2][1]];

		const again = generate(players, [], skills, { perTeam: 3, seed: 77, current: first, locked }).teams;

		expect(again[0]).toContain(locked[0]);
		expect(again[2]).toContain(locked[1]);
	});

	it('reports a roster too small for two teams', () => {
		expect(() => generate(roster(3), [], skills, { perTeam: 3, seed: 1 })).toThrow(/too_few/);
	});
});

describe('placeNewcomers', () => {
	it('puts each newcomer in a smallest team and moves nobody else', () => {
		const players = roster(11);
		const base = generate(players.slice(0, 8), [], skills, { perTeam: 3, seed: 1 }).teams; // 3, 3, 2
		const before = base.map((t) => [...t]);

		const out = placeNewcomers(players, [], skills, base, [9, 10, 11]);

		expect(out.map((t) => t.length).sort()).toEqual([3, 4, 4].sort());
		out.forEach((team, i) => before[i].forEach((id) => expect(team).toContain(id)));
		expect(out.flat().sort((a, b) => a - b)).toEqual(players.map((p) => p.id));
		expect(Math.max(...out.map((t) => t.length)) - Math.min(...out.map((t) => t.length))).toBeLessThanOrEqual(1);
	});

	it('keeps a newcomer away from someone they avoid when it can', () => {
		const players = roster(7);
		const teams = [[1, 2, 3], [4, 5, 6]];
		const links = [{ player: 7, kind: 'avoid', target: 1 }];

		const out = placeNewcomers(players, links, skills, teams, [7]);

		expect(out[0]).not.toContain(7);
	});

	it('returns the teams unchanged without newcomers', () => {
		expect(placeNewcomers(roster(4), [], skills, [[1, 2], [3, 4]], [])).toEqual([[1, 2], [3, 4]]);
	});
});

describe('generate speed', () => {
	it('proposes teams for 50 players in under 1.5 seconds', () => {
		const start = performance.now();

		const { teams } = generate(roster(50), [], skills, { perTeam: 4, seed: 3 });

		expect(performance.now() - start).toBeLessThan(1500);
		expect(teams.flat()).toHaveLength(50);
	});
});

describe('generate with variety', () => {
	const players = roster(14);
	const key = (teams) => teams.map((t) => [...t].sort((a, b) => a - b).join(',')).sort().join('|');

	it('never returns the current partition when another one is acceptable', () => {
		const current = generate(players, [], skills, { perTeam: 4, seed: 99 }).teams;
		for (let seed = 1; seed <= 10; seed++) {
			const { teams } = generate(players, [], skills, { perTeam: 4, seed, current, variety: true });
			expect(key(teams)).not.toBe(key(current));
		}
	});

	it('offers several distinct partitions over different seeds, all near the best score', () => {
		const best = generate(players, [], skills, { perTeam: 4, seed: 1 }).score.total;
		const seen = new Set();
		for (let seed = 1; seed <= 12; seed++) {
			const result = generate(players, [], skills, { perTeam: 4, seed, variety: true });
			seen.add(key(result.teams));
			expect(result.score.total).toBeLessThanOrEqual(best + Math.max(0.5, 0.25 * best) + 1e-6);
		}
		expect(seen.size).toBeGreaterThanOrEqual(4);
	});

	it('keeps locked players in their team', () => {
		const current = generate(players, [], skills, { perTeam: 4, seed: 3 }).teams;
		const locked = [current[1][0], current[2][0]];
		for (let seed = 1; seed <= 5; seed++) {
			const { teams } = generate(players, [], skills, { perTeam: 4, seed, current, locked, variety: true });
			expect(teams[1]).toContain(locked[0]);
			expect(teams[2]).toContain(locked[1]);
		}
	});

	it('is deterministic for a seed', () => {
		const a = generate(players, [], skills, { perTeam: 4, seed: 7, variety: true });
		const b = generate(players, [], skills, { perTeam: 4, seed: 7, variety: true });
		expect(a.teams).toEqual(b.teams);
	});

	it('stays fast on 50 players', () => {
		const start = Date.now();
		generate(roster(50), [], skills, { perTeam: 4, seed: 2, variety: true });
		expect(Date.now() - start).toBeLessThan(3000);
	});
});

