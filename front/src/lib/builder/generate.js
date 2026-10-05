import { rng, shuffled } from './random.js';
import { teamSizes } from './plan.js';
import { makeScorer } from './score.js';

const RESTARTS = 5;
const VARIETY_RESTARTS = 16;
const MAX_PASSES = 60;

/** A failure the page words: `too_few` (fewer than two teams of the asked size). */
export class BuilderError extends Error {
	constructor(code) {
		super(code);
		this.code = code;
	}
}

/**
 * Evenly sized, balanced teams for `players` (spec 2026-10-05-team-builder). Locked players
 * (`locked`, ids) stay in their team of `current` (arrays of ids); everyone else starts from a
 * greedy placement, strongest first into the team with the lowest rating total and room left,
 * then improves by swapping two unlocked players while the score drops, over a few seeded
 * restarts. With `variety`, more restarts run and one of the distinct arrangements scoring
 * close to the best (and not the `current` one) is drawn, so a re-roll gives a real alternative. Returns `{ teams, score }` (`score` the scorer's result). Same input and seed,
 * same teams.
 */
export function generate(players, links, skills, { perTeam, seed, current = null, locked = [], variety = false }) {
	const sizes = teamSizes(players.length, perTeam);
	if (!sizes) throw new BuilderError('too_few');
	const score = makeScorer(players, links, skills);
	const byId = new Map(players.map((p) => [p.id, p]));
	const random = rng(seed);

	// Locked players keep their place when that team exists and has room.
	const fixed = sizes.map(() => []);
	const lockedSet = new Set();
	(current ?? []).forEach((ids, index) => {
		if (index >= sizes.length) return;
		for (const id of ids) {
			if (locked.includes(id) && byId.has(id) && fixed[index].length < sizes[index]) {
				fixed[index].push(id);
				lockedSet.add(id);
			}
		}
	});
	const free = players.filter((p) => !lockedSet.has(p.id));

	const place = (order) => {
		const teams = fixed.map((ids) => [...ids]);
		const totals = teams.map((ids) => ids.reduce((sum, id) => sum + byId.get(id).rating, 0));
		for (const player of order) {
			let target = -1;
			teams.forEach((ids, i) => {
				if (ids.length >= sizes[i]) return;
				if (target === -1 || totals[i] < totals[target]) target = i;
			});
			teams[target].push(player.id);
			totals[target] += player.rating;
		}
		return teams;
	};

	const improve = (teams) => {
		let best = score(teams);
		for (let pass = 0; pass < MAX_PASSES; pass++) {
			let improved = false;
			for (let a = 0; a < teams.length; a++) {
				for (let b = a + 1; b < teams.length; b++) {
					for (let i = 0; i < teams[a].length; i++) {
						if (lockedSet.has(teams[a][i])) continue;
						for (let j = 0; j < teams[b].length; j++) {
							if (lockedSet.has(teams[b][j])) continue;
							[teams[a][i], teams[b][j]] = [teams[b][j], teams[a][i]];
							const next = score(teams);
							if (next.total < best.total - 1e-9) {
								best = next;
								improved = true;
							} else {
								[teams[a][i], teams[b][j]] = [teams[b][j], teams[a][i]];
							}
						}
					}
				}
			}
			if (!improved) break;
		}
		return { teams, score: best };
	};

	const byStrength = [...free].sort((x, y) => y.rating - x.rating || x.id - y.id);
	const restarts = variety ? VARIETY_RESTARTS : RESTARTS;
	const results = [improve(place(byStrength))];
	for (let restart = 1; restart < restarts; restart++) {
		results.push(improve(place(shuffled(free, random))));
	}
	let best = results[0];
	for (const r of results) if (r.score.total < best.score.total) best = r;
	if (!variety) return best;

	// Teams are positional when locks refer to team indexes; otherwise a permutation is the same partition.
	const signature = (teams) => {
		const lists = teams.map((ids) => [...ids].sort((a, b) => a - b).join(','));
		return (lockedSet.size ? lists : lists.sort()).join('|');
	};
	const limit = best.score.total + Math.max(0.5, 0.25 * best.score.total);
	const distinct = new Map();
	for (const r of results) {
		if (r.score.total <= limit && !distinct.has(signature(r.teams))) distinct.set(signature(r.teams), r);
	}
	let candidates = [...distinct.values()];
	if (current) {
		const own = signature(current);
		const others = candidates.filter((r) => signature(r.teams) !== own);
		if (others.length > 0) candidates = others;
	}
	return candidates[Math.floor(random() * candidates.length)];
}

/**
 * Place `ids` (the players of the tray) into `teams` without moving anyone: strongest first,
 * each into the team that scores best among the smallest ones, so sizes keep differing by at
 * most one. Returns new arrays; `teams` is untouched.
 */
export function placeNewcomers(players, links, skills, teams, ids) {
	const score = makeScorer(players, links, skills);
	const byId = new Map(players.map((p) => [p.id, p]));
	const out = teams.map((t) => [...t]);
	const order = [...ids].sort((a, b) => byId.get(b).rating - byId.get(a).rating || a - b);
	for (const id of order) {
		const smallest = Math.min(...out.map((t) => t.length));
		let best = null;
		out.forEach((team, index) => {
			if (team.length !== smallest) return;
			team.push(id);
			const total = score(out).total;
			team.pop();
			if (best === null || total < best.total) best = { index, total };
		});
		out[best.index].push(id);
	}
	return out;
}
