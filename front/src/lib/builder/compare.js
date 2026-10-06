/**
 * What the builder's compare table and swap preview draw (spec 2026-10-06-builder-player-compare).
 * Pure. Both read the same `playerProfile` as the single sheet, and the preview runs the page's
 * own scorer, so nothing here disagrees with the balance.
 */
import { playerProfile } from './profile.js';
import { swapPlayers } from './plan.js';

/** The two profiles and one row per skill: both values, which are estimated, who leads and by how much. */
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

/**
 * How many requests a draft leaves unmet, counting a player in the tray as apart from everyone
 * (the scorer skips them, which would make sending a player to the tray look like a fix). A pair
 * that asked for each other counts once, as in the scorer.
 */
function unmetCount(draft) {
	const teamOf = new Map();
	draft.teams.forEach((t, i) => t.players.forEach((id) => teamOf.set(id, i)));
	const together = (l) => teamOf.has(l.player) && teamOf.get(l.player) === teamOf.get(l.target);
	const pair = (l) => [l.player, l.target].sort().join('-');
	const withs = new Set(draft.links.filter((l) => l.kind === 'with' && !together(l)).map(pair));
	const avoids = new Set(draft.links.filter((l) => l.kind === 'avoid' && together(l)).map(pair));
	return withs.size + avoids.size;
}

/**
 * What swapping a and b would change, from the real `scorer` run on both drafts: the average
 * rating of each team the swap touches and the draft's number of unmet requests (the scorer's count
 * before, moved by the change `unmetCount` sees, so the figure matches the panel). null when blocked.
 */
export function swapPreview(draft, a, b, scorer) {
	const swapped = swapPlayers(draft, a, b);
	if (!swapped) return null;
	const before = scorer(draft.teams.map((t) => t.players));
	const after = scorer(swapped.teams.map((t) => t.players));
	const teams = draft.teams
		.map((t, index) => ({ index, touched: t.players.includes(a) !== t.players.includes(b) }))
		.filter((t) => t.touched)
		.map(({ index }) => ({ index, before: before.teams[index].rating, after: after.teams[index].rating }));
	return { teams, unmet: { before: before.unmet.length, after: before.unmet.length + unmetCount(swapped) - unmetCount(draft) } };
}
