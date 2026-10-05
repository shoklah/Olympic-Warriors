/**
 * Features and the balance score of a team assignment (spec 2026-10-05-team-builder).
 * Pure: the generator and the live display use the same scorer.
 */

/**
 * The cost of each term, in the same units as a standard deviation of team averages scaled
 * to ten. An unmet "with" costs less than a visible rating gap; a broken "avoid" more than
 * an unmet mutual "with" (the tests pin the order, not the numbers).
 */
export const WEIGHTS = { rating: 10, skills: 5, experience: 4, with: 2, avoid: 6 };

const FREQUENCY_RANK = { rare: 0, monthly: 1, hour: 2, two_hours: 3, four_hours: 4 };
const EXPERIENCED_FREQUENCY = 3;
const EXPERIENCED_LEVELS = new Set(['league', 'regional']);
const FALLBACK_FREQUENCY = 'hour';

/** What the scorer reads of a player; a missing skill counts as the overall rating. */
export function features(player, skills) {
	let incomplete = false;
	const values = {};
	for (const { identifier } of skills) {
		const value = player.ratings?.[identifier];
		if (value === undefined || value === null) incomplete = true;
		values[identifier] = value ?? player.rating;
	}
	if (!player.sport_frequency) incomplete = true;
	const rank = FREQUENCY_RANK[player.sport_frequency || FALLBACK_FREQUENCY] ?? FREQUENCY_RANK[FALLBACK_FREQUENCY];
	const experienced =
		rank >= EXPERIENCED_FREQUENCY || (player.sports ?? []).some((s) => EXPERIENCED_LEVELS.has(s.level));
	return { rating: player.rating, skills: values, experienced, incomplete };
}

const mean = (values) => (values.length ? values.reduce((a, b) => a + b, 0) / values.length : 0);
const deviation = (values) => {
	const m = mean(values);
	return Math.sqrt(mean(values.map((v) => (v - m) ** 2)));
};

/**
 * A scorer for a roster, its confirmed `links` and the edition's `skills`: call it with the
 * teams (arrays of player ids; a player in no team is simply not counted) to get
 * `{ total, parts, unmet, teams }`. `unmet` lists each broken request once (a pair that asked
 * for each other is one mutual "with"); `teams` carries the per-team averages for the display.
 */
export function makeScorer(players, links, skills, weights = WEIGHTS) {
	const byId = new Map(players.map((p) => [p.id, features(p, skills)]));
	const withs = links.filter((l) => l.kind === 'with');
	const avoids = links.filter((l) => l.kind === 'avoid');
	const wants = new Set(withs.map((l) => `${l.player}>${l.target}`));

	return (teams) => {
		const teamOf = new Map();
		teams.forEach((ids, index) => ids.forEach((id) => teamOf.set(id, index)));
		const rows = teams.map((ids) => {
			const fs = ids.map((id) => byId.get(id)).filter(Boolean);
			return {
				size: fs.length,
				rating: mean(fs.map((f) => f.rating)),
				skills: Object.fromEntries(skills.map((s) => [s.identifier, mean(fs.map((f) => f.skills[s.identifier]))])),
				experienced: fs.filter((f) => f.experienced).length
			};
		});

		const parts = {
			rating: deviation(rows.map((r) => r.rating)) * weights.rating,
			skills:
				(skills.length ? mean(skills.map((s) => deviation(rows.map((r) => r.skills[s.identifier])))) : 0) * weights.skills,
			experience: deviation(rows.map((r) => (r.size ? r.experienced / r.size : 0))) * weights.experience,
			with: 0,
			avoid: 0
		};

		const unmet = [];
		const seen = new Set();
		for (const link of withs) {
			const a = teamOf.get(link.player);
			const b = teamOf.get(link.target);
			if (a === undefined || b === undefined || a === b) continue;
			const mutual = wants.has(`${link.target}>${link.player}`);
			const key = [link.player, link.target].sort().join('-');
			if (mutual && seen.has(key)) continue;
			seen.add(key);
			unmet.push({ kind: 'with', player: link.player, target: link.target, mutual });
			parts.with += mutual ? 2 * weights.with : weights.with;
		}
		const avoidSeen = new Set();
		for (const link of avoids) {
			const a = teamOf.get(link.player);
			const b = teamOf.get(link.target);
			if (a === undefined || a !== b) continue;
			const key = [link.player, link.target].sort().join('-');
			if (avoidSeen.has(key)) continue;
			avoidSeen.add(key);
			unmet.push({ kind: 'avoid', player: link.player, target: link.target, mutual: false });
			parts.avoid += weights.avoid;
		}

		const total = parts.rating + parts.skills + parts.experience + parts.with + parts.avoid;
		return { total, parts, unmet, teams: rows };
	};
}
