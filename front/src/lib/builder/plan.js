import { newSeed } from './random.js';

/**
 * The team sizes for `n` players at about `perTeam` each: `ceil(n / perTeam)` teams, as even
 * as possible (sizes differ by at most one, the larger first). null when that is under two teams.
 */
export function teamSizes(n, perTeam) {
	const count = Math.ceil(n / perTeam);
	if (!Number.isFinite(count) || count < 2 || n < count) return null;
	const base = Math.floor(n / count);
	const extra = n % count;
	return Array.from({ length: count }, (_, i) => (i < extra ? base + 1 : base));
}

/** A draft before any proposal. `perTeam` is the one input the organiser sets first. */
export const emptyDraft = (perTeam = 3) => ({
	players_per_team: perTeam,
	seed: newSeed(),
	links: [],
	teams: [],
	locked: []
});

/**
 * The saved draft against the roster as it is now: departed players leave the teams, the
 * links and the locks (so the server's strict check never trips on them), and `joined`
 * counts the players placed nowhere once teams exist (late registrants), `unplaced` lists
 * them all. `left` counts the departed players found in the draft.
 */
export function reconcile(draft, players) {
	const ids = new Set(players.map((p) => p.id));
	const inDraft = new Set(draft.teams.flatMap((t) => t.players));
	const left = [...inDraft].filter((id) => !ids.has(id)).length;
	const teams = draft.teams.map((t) => ({ players: t.players.filter((id) => ids.has(id)) }));
	const placed = new Set(teams.flatMap((t) => t.players));
	const unplaced = players.map((p) => p.id).filter((id) => !placed.has(id));
	return {
		draft: {
			...draft,
			teams,
			links: draft.links.filter((l) => ids.has(l.player) && ids.has(l.target)),
			locked: draft.locked.filter((id) => ids.has(id))
		},
		left,
		joined: draft.teams.length > 0 ? unplaced.length : 0,
		unplaced
	};
}

const teamIndexOf = (draft, id) => draft.teams.findIndex((t) => t.players.includes(id));

/** Why a and b cannot be swapped, or null: locked first, then the same team, then both in the tray. */
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
