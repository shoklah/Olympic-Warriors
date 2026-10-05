/** Lower case, no accents, single spaces. */
export const normalise = (text) =>
	String(text ?? '')
		.normalize('NFD')
		.replace(/\p{M}/gu, '')
		.toLowerCase()
		.replace(/\s+/g, ' ')
		.trim();

const SEPARATORS = /[,;\n/&]+|\s+et\s+|\s+ou\s+|\s+and\s+/i;
const NOISE = new Set([
	'peu importe', 'personne', 'aucun', 'aucune', 'rien', 'n/a', 'na', 'none', 'nobody',
	'no one', 'anyone', 'whatever', 'pas de preference', 'idem', '-', '?'
]);
// Short everyday words that sit one edit away from a first name, never suggested as a typo.
const STOPWORDS = new Set([
	'avec', 'pour', 'dans', 'sans', 'pas', 'des', 'les', 'une', 'mais', 'plus', 'tout', 'tous',
	'etre', 'bien', 'peut', 'veux', 'avoir', 'sinon', 'elle', 'nous', 'vous', 'ils', 'est',
	'non', 'oui', 'moi', 'toi', 'ton', 'mon', 'son', 'ses', 'mes', 'tes', 'sur', 'par', 'que', 'qui',
	'with', 'and', 'the', 'for', 'not', 'any', 'one', 'yes', 'you', 'him', 'her'
]);

/** The parts of a free-text answer that name someone, one per entry, as written. */
export const splitNames = (text) =>
	String(text ?? '')
		.replace(/\bet\s*\/\s*ou\b/giu, ',')
		.split(SEPARATORS)
		.map((part) => part.trim())
		.filter(Boolean);

/** The words of a text: normalised, split on anything that is not a letter or a digit. */
const words = (text) => normalise(text).split(/[^a-z0-9]+/).filter(Boolean);

/** Whether `sequence` appears in `list` as consecutive words. */
function contains(list, sequence) {
	if (sequence.length === 0) return false;
	for (let i = 0; i + sequence.length <= list.length; i++) {
		if (sequence.every((word, j) => list[i + j] === word)) return true;
	}
	return false;
}

/** Edit distance, small strings only. */
function distance(a, b) {
	const row = Array.from({ length: b.length + 1 }, (_, j) => j);
	for (let i = 1; i <= a.length; i++) {
		let diagonal = row[0];
		row[0] = i;
		for (let j = 1; j <= b.length; j++) {
			const above = row[j];
			row[j] = Math.min(row[j] + 1, row[j - 1] + 1, diagonal + (a[i - 1] === b[j - 1] ? 0 : 1));
			diagonal = above;
		}
	}
	return row[b.length];
}

/**
 * A tie narrowed by a nickname: when several players match, those whose first name starts with
 * another word of the part (« Alex Boucton » among two Bouctons) are kept, if there are any.
 */
function narrow(found, list) {
	if (found.length < 2) return found;
	// Only a word that is no part of any candidate's own name can be a nickname: « Martin » is
	// the last name of Paul and of Martine Martin, not a nickname of Martine.
	const inAName = (word) => found.some((entry) => entry.first.includes(word) || entry.last.includes(word));
	const extras = list.filter((word) => word.length >= 3 && !inAName(word));
	const nicknames = found.filter((entry) =>
		extras.some((word) => entry.first.length === 1 && entry.first[0].startsWith(word))
	);
	return nicknames.length > 0 ? nicknames : found;
}

const result = (text, tier, found) => {
	const confidence = found.length > 1 ? 'ambiguous' : tier;
	return {
		text,
		// Only a single, certain match is proposed as the answer; the organiser still confirms it.
		best: found.length === 1 && tier !== 'near' ? found[0].id : null,
		confidence,
		candidates: found.map((e) => ({ id: e.id, confidence }))
	};
};

/**
 * For each part of `text`, the registered players it may mean: `{ text, best, confidence,
 * candidates: [{ id, confidence }] }`. The part is scanned for the players' names as whole
 * words, wherever they sit in the sentence (« Ne pas être avec Marie », « Antoine dupont si il
 * est là »), so no wording around the name has to be understood: the first and last name
 * together (`exact`, in either order), else a last name alone (`last`), else a first name
 * alone (`first`); several players at the best level make it `ambiguous` and nothing is
 * proposed. Only when nothing is found, a short part one typo away from a first or last name is
 * suggested (`near`, never proposed). The player themself is never offered, and noise like
 * « peu importe » matches nothing.
 */
export function matchNames(text, players, selfId) {
	const entries = players
		.filter((p) => p.id !== selfId)
		.map((p) => ({ id: p.id, first: words(p.first_name), last: words(p.last_name) }));

	return splitNames(text).map((raw) => {
		const list = words(raw);
		const none = { text: raw, best: null, confidence: 'none', candidates: [] };
		if (list.length === 0 || NOISE.has(normalise(raw))) return none;

		const tiers = { exact: [], last: [], first: [] };
		for (const entry of entries) {
			const hasFirst = contains(list, entry.first);
			const hasLast = contains(list, entry.last);
			if (hasFirst && hasLast) tiers.exact.push(entry);
			else if (hasLast) tiers.last.push(entry);
			else if (hasFirst) tiers.first.push(entry);
		}
		if (tiers.exact.length > 0) return result(raw, 'exact', tiers.exact);
		if (tiers.last.length > 0) {
			const found = narrow(tiers.last, list);
			// The text also names someone else by first name (« Léa Martin » with a Paul Martin and
			// a Léa Dupont): do not pick the last-name match, let the organiser choose.
			const others = tiers.first.filter((entry) => !found.includes(entry));
			if (others.length > 0) return result(raw, 'ambiguous', [...found, ...others]);
			return result(raw, 'last', found);
		}
		if (tiers.first.length > 0) return result(raw, 'first', tiers.first);

		// A typo is only worth suggesting in a short answer, where the word is the name.
		if (list.length <= 3) {
			const minimum = list.length === 1 ? 3 : 4;
			const near = entries.filter((entry) =>
				list.some(
					(word) =>
						word.length >= minimum &&
						!STOPWORDS.has(word) &&
						([entry.first, entry.last].some((name) => name.length === 1 && distance(name[0], word) === 1) ||
							(entry.first.length === 1 && entry.first[0].startsWith(word) && word.length >= 3))
				)
			);
			if (near.length > 0) return result(raw, 'near', near);
		}
		return none;
	});
}
