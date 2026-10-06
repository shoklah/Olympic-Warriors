/**
 * What step 1 of the builder shows of the written requests (spec 2026-10-06-builder-requests-clarity):
 * one row per player and kind, one line per part of the text, the state of each line and the
 * counts. Pure; `matchNames` decides what is suggested, this only reads its answer.
 */
import { matchNames, splitNames } from './names.js';

const KINDS = [['team_with', 'with'], ['team_avoid', 'avoid']];

/** One row per written request, « avec » then « à éviter », players in roster order. */
export function requestRows(players) {
	return players.flatMap((player) =>
		KINDS.flatMap(([field, kind]) =>
			player[field]?.trim() ? [{ player, kind, matches: matchNames(player[field], players, player.id) }] : []
		)
	);
}

/** Whether the written part `text` of `player`'s `kind` request is set aside (`ignored`: `{ player, kind, text }`). */
export const isIgnored = (ignored, player, kind, text) =>
	ignored.some((i) => i.player === player.id && i.kind === kind && i.text === text);

/**
 * Where a line stands: `ignored` (set aside by the organisers, whatever else it is), `confirmed` (a
 * candidate of it is a confirmed link), else `none` (no candidate), `clear` (one certain
 * candidate, `best`), `check` (a single candidate a typo away) or `choose` (several candidates).
 */
export function lineState(match, links, player, kind, ignored = []) {
	if (isIgnored(ignored, player, kind, match.text)) return 'ignored';
	const confirmed = match.candidates.some((c) =>
		links.some((l) => l.player === player.id && l.kind === kind && l.target === c.id)
	);
	if (confirmed) return 'confirmed';
	if (match.candidates.length === 0) return 'none';
	if (match.best !== null) return 'clear';
	return match.confidence === 'near' ? 'check' : 'choose';
}

/** The dictionary key of the line's caption: how the match was made, or that there is none. */
export const reasonKey = (match) =>
	match.candidates.length === 0 ? 'builder.requests.noMatch' : `builder.requests.why.${match.confidence}`;

/**
 * `{ total, confirmed, review, none, clear, ignored }` over the lines; `review` is every line still to
 * decide on, `clear` those a click can confirm, and an ignored line is in none of the others.
 */
export function summarise(rows, links, ignored = []) {
	const counts = { total: 0, confirmed: 0, review: 0, none: 0, clear: 0, ignored: 0 };
	for (const row of rows) {
		for (const match of row.matches) {
			const state = lineState(match, links, row.player, row.kind, ignored);
			counts.total += 1;
			if (state === 'ignored') counts.ignored += 1;
			else if (state === 'confirmed') counts.confirmed += 1;
			else if (state === 'none') counts.none += 1;
			else {
				counts.review += 1;
				if (state === 'clear') counts.clear += 1;
			}
		}
	}
	return counts;
}

/**
 * What a card shows of a player's `kind` request: the text as written, or, once some of its parts are
 * ignored, the parts left joined by commas ('' when none is left).
 */
export function shownText(player, kind, ignored) {
	const field = kind === 'with' ? 'team_with' : 'team_avoid';
	const text = player[field]?.trim() ?? '';
	if (!ignored.some((i) => i.player === player.id && i.kind === kind)) return text;
	return splitNames(text)
		.filter((part) => !isIgnored(ignored, player, kind, part))
		.join(', ');
}

/** The `{ player, kind, target }` links of every clear line: what « confirm the clear matches » adds. */
export function clearLinks(rows, links, ignored = []) {
	return rows.flatMap((row) =>
		row.matches
			.filter((match) => lineState(match, links, row.player, row.kind, ignored) === 'clear')
			.map((match) => ({ player: row.player.id, kind: row.kind, target: match.best }))
	);
}
