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
		.map((r) => ({ ...r, teamName: names.get(r.team) ?? null }))
		.sort((a, b) => rank(a) - rank(b) || (a.teamName ?? '').localeCompare(b.teamName ?? ''));
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

/** Noon anchoring keeps the calendar day whatever the renderer's timezone. */
function parseDay(iso) {
	return new Date(`${iso}T12:00:00`);
}

/** BCP 47 tag behind each site locale, for Intl; French for anything else, like `t`. */
const DATE_TAGS = { fr: 'fr-FR', en: 'en-GB' };
const tagFor = (locale) => DATE_TAGS[locale] ?? DATE_TAGS.fr;

/** French writes the first of the month "1er"; Intl gives "1". */
function frenchFirst(text, date, locale) {
	return locale === 'fr' && date.getDate() === 1 ? text.replace(/^1\b/, '1er') : text;
}

function dayMonth(date, locale) {
	const text = date.toLocaleDateString(tagFor(locale), { day: 'numeric', month: 'long' });
	return frenchFirst(text, date, locale);
}

/**
 * The dates of an edition as one line in `locale`: "19 September 2026" for a single day,
 * "19 – 20 September 2026" within a month, "30 September – 1 October 2026" across two.
 */
export function formatDateRange(start, end, locale) {
	const to = parseDay(end);
	const year = to.getFullYear();
	if (start === end) return `${dayMonth(to, locale)} ${year}`;

	const from = parseDay(start);
	const sameMonth = from.getFullYear() === year && from.getMonth() === to.getMonth();
	const left = sameMonth
		? frenchFirst(from.toLocaleDateString(tagFor(locale), { day: 'numeric' }), from, locale)
		: dayMonth(from, locale);
	return `${left} – ${dayMonth(to, locale)} ${year}`;
}

/** +3, 0, -2 */
export function formatDifference(n) {
	return n > 0 ? `+${n}` : `${n}`;
}

/**
 * Ordinal of a rank: 1st, 2nd, 3rd, 4th, 11th, 21st in English; 1re then 2e, 3e in French
 * (the rank always describes a team, feminine). Anything but `en` is French, like `t`.
 */
export function ordinal(n, locale) {
	if (locale !== 'en') return n === 1 ? '1re' : `${n}e`;
	const mod100 = n % 100;
	if (mod100 >= 11 && mod100 <= 13) return `${n}th`;
	const mod10 = n % 10;
	if (mod10 === 1) return `${n}st`;
	if (mod10 === 2) return `${n}nd`;
	if (mod10 === 3) return `${n}rd`;
	return `${n}th`;
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

const teamNames = (summary) => new Map(summary.teams.map((t) => [t.id, t.name]));
/** A team's name, or null when the id matches no team: the page prints the "unknown" label. */
const nameOf = (names, id) => names.get(id) ?? null;

/**
 * Rounds of a discipline in order, each with its games and team names joined.
 * Null when the discipline has no round. Scores are null while unrevealed.
 */
export function disciplineSchedule(summary, disciplineId) {
	const rounds = summary.rounds.filter((r) => r.discipline === disciplineId);
	if (rounds.length === 0) return null;
	const names = teamNames(summary);
	return [...rounds]
		.sort((a, b) => a.order - b.order)
		.map((round) => ({
			order: round.order,
			isOver: round.is_over,
			games: summary.games
				.filter((g) => g.round === round.id)
				.map((g) => ({
					id: g.id,
					team1Id: g.team1,
					team1Name: nameOf(names, g.team1),
					team2Id: g.team2,
					team2Name: nameOf(names, g.team2),
					refereeName: nameOf(names, g.referees),
					isPlayed: g.is_played,
					score1: g.score1,
					score2: g.score2
				}))
		}));
}

/**
 * What goes under a discipline name: its round and game counts, or the kind of result
 * it produces when it has no round. `reveal_score` plays no part. The page words it.
 */
export function disciplineSubtitle(summary, discipline) {
	const rounds = summary.rounds.filter((r) => r.discipline === discipline.id).length;
	if (rounds === 0) return { resultType: discipline.result_type };

	const games = summary.games.filter((g) => g.discipline === discipline.id).length;
	return { rounds, games };
}

/** Beside a round heading: how many games it holds and how many are still to play. */
export function roundCount(round) {
	const left = round.games.filter((g) => !g.isPlayed).length;
	return { left, total: round.games.length };
}

/**
 * The games a team played (as team1 or team2), grouped by discipline in id order and
 * sorted by round, with team and referee names joined. Games the team only referees
 * are left out. Disciplines without such a game are omitted.
 */
export function teamGames(summary, teamId) {
	const names = teamNames(summary);
	const roundOrder = new Map(summary.rounds.map((r) => [r.id, r.order]));
	return summary.disciplines
		.map((discipline) => ({
			disciplineId: discipline.id,
			disciplineName: discipline.name,
			games: summary.games
				.filter(
					(g) => g.discipline === discipline.id && (g.team1 === teamId || g.team2 === teamId)
				)
				.map((g) => ({
					id: g.id,
					round: roundOrder.get(g.round) ?? 0,
					team1Id: g.team1,
					team2Id: g.team2,
					team1Name: nameOf(names, g.team1),
					team2Name: nameOf(names, g.team2),
					refereeName: g.referees == null ? null : nameOf(names, g.referees),
					isPlayed: g.is_played,
					score1: g.score1,
					score2: g.score2
				}))
				.sort((a, b) => a.round - b.round || a.id - b.id)
		}))
		.filter((d) => d.games.length > 0);
}
