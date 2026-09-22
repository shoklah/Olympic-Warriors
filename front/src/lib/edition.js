/**
 * Pure derivations over an edition summary as returned by
 * GET /edition/year/<year>/summary/. No fetching, no Svelte, fully unit-tested.
 */

const byRankThenName = (a, b) => a.ranking - b.ranking || a.name.localeCompare(b.name);

/** Teams of the edition sorted by global ranking, ties by name. */
export function rankedTeams(summary) {
	return [...summary.teams].sort(byRankThenName);
}

/** Team row by id, or null. */
export function findTeam(summary, teamId) {
	return summary.teams.find((t) => t.id === teamId) ?? null;
}

/** Discipline row by id, or null. */
export function findDiscipline(summary, disciplineId) {
	return summary.disciplines.find((d) => d.id === disciplineId) ?? null;
}

/**
 * Results of one discipline in rank order with `teamName` joined in.
 * Null when the discipline is unknown or its score is not revealed.
 */
export function disciplineResults(summary, disciplineId) {
	const discipline = findDiscipline(summary, disciplineId);
	if (!discipline || !discipline.reveal_score) return null;

	const names = new Map(summary.teams.map((t) => [t.id, t.name]));
	const rank = (r) => r.ranking ?? Number.POSITIVE_INFINITY; // no score yet: sort last
	return summary.results
		.filter((r) => r.discipline === disciplineId)
		.map((r) => ({ ...r, teamName: names.get(r.team) ?? 'Unknown' }))
		.sort((a, b) => rank(a) - rank(b) || a.teamName.localeCompare(b.teamName));
}

/**
 * One row per discipline (id order) for a team: name, whether the score is
 * revealed, and the rank, points and time when it is.
 */
export function teamResults(summary, teamId) {
	return summary.disciplines.map((discipline) => {
		const result = summary.results.find(
			(r) => r.team === teamId && r.discipline === discipline.id
		);
		const revealed = Boolean(discipline.reveal_score && result && result.ranking !== null);
		return {
			disciplineId: discipline.id,
			disciplineName: discipline.name,
			result_type: discipline.result_type,
			revealed,
			ranking: revealed ? result.ranking : null,
			points: revealed ? result.points : null,
			time: revealed ? result.time : null
		};
	});
}

const EVENT_TZ = 'Europe/Paris';

/** UTC offset of EVENT_TZ on that day at 09:00 UTC, as "+02:00" (DST-aware, no library). */
function eventOffset(isoDate) {
	const parts = new Intl.DateTimeFormat('en-US', { timeZone: EVENT_TZ, timeZoneName: 'longOffset' })
		.formatToParts(new Date(`${isoDate}T09:00:00Z`));
	const name = parts.find((p) => p.type === 'timeZoneName').value; // "GMT+02:00" or "GMT"
	return name === 'GMT' ? '+00:00' : name.slice(3);
}

/** The event starts at 09:00 Europe/Paris on start_date, whatever timezone renders it. */
export function startInstant(edition) {
	return new Date(`${edition.start_date}T09:00:00${eventOffset(edition.start_date)}`);
}

/** "upcoming" before the start instant, "started" from then on. */
export function editionPhase(edition, now = new Date()) {
	return now < startInstant(edition) ? 'upcoming' : 'started';
}

/** Days, hours, minutes, seconds until the start instant; zeros once started. */
export function countdownParts(edition, now = new Date()) {
	const distance = Math.max(0, startInstant(edition) - now);
	const seconds = Math.floor(distance / 1000);
	return {
		days: Math.floor(seconds / 86400),
		hours: Math.floor((seconds % 86400) / 3600),
		minutes: Math.floor((seconds % 3600) / 60),
		seconds: seconds % 60
	};
}

/** +3, 0, -2 */
export function formatDifference(n) {
	return n > 0 ? `+${n}` : `${n}`;
}

/**
 * Where the year switcher sends the visitor: same section under the other year
 * (a detail page falls back to its list), the hub for anything else.
 */
export function switchYearPath(pathname, year) {
	const match = pathname.match(/^\/\d{4}(?:\/([a-z]+))?/);
	if (!match) return `/${year}`;
	return match[1] ? `/${year}/${match[1]}` : `/${year}`;
}
