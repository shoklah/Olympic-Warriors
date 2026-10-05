/** Lower case, no accents, single spaces. */
export const normalise = (text) =>
	String(text ?? '')
		.normalize('NFD')
		.replace(/\p{M}/gu, '')
		.toLowerCase()
		.replace(/\s+/g, ' ')
		.trim();

const SEPARATORS = /[,;\n/&]+|\s+et\s+|\s+and\s+/i;
const LEADING = /^(avec|with)\s+/i;
const NOISE = new Set([
	'peu importe', 'personne', 'aucun', 'aucune', 'rien', 'n/a', 'na', 'none', 'nobody',
	'no one', 'anyone', 'whatever', 'pas de preference', 'idem', '-', '?'
]);

/** The names of a free-text answer, one per entry. */
export const splitNames = (text) =>
	String(text ?? '')
		.split(SEPARATORS)
		.map((part) => part.trim().replace(LEADING, '').trim())
		.filter(Boolean);

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
 * For each name of `text`, the registered players it may mean: `{ text, best, confidence,
 * candidates: [{ id, confidence }] }`. `best` is preselected only for a whole-name match or a
 * first name only one player has; a first name shared by several players is `ambiguous`, a
 * first name one typo away is `near` (suggested, never preselected). The player themself is
 * never offered, and noise like « peu importe » matches nothing.
 */
export function matchNames(text, players, selfId) {
	const others = players.filter((p) => p.id !== selfId);
	const entries = others.map((p) => ({
		id: p.id,
		first: normalise(p.first_name),
		full: [`${normalise(p.first_name)} ${normalise(p.last_name)}`, `${normalise(p.last_name)} ${normalise(p.first_name)}`]
	}));
	return splitNames(text).map((raw) => {
		const name = normalise(raw);
		const none = { text: raw, best: null, confidence: 'none', candidates: [] };
		if (NOISE.has(name)) return none;
		const whole = entries.filter((e) => e.full.includes(name));
		if (whole.length === 1) return { text: raw, best: whole[0].id, confidence: 'exact', candidates: [{ id: whole[0].id, confidence: 'exact' }] };
		const sameFirst = entries.filter((e) => e.first === name);
		if (sameFirst.length === 1) return { text: raw, best: sameFirst[0].id, confidence: 'first', candidates: [{ id: sameFirst[0].id, confidence: 'first' }] };
		if (sameFirst.length > 1) {
			return { text: raw, best: null, confidence: 'ambiguous', candidates: sameFirst.map((e) => ({ id: e.id, confidence: 'ambiguous' })) };
		}
		if (name.length >= 3 && !name.includes(' ')) {
			const near = entries.filter((e) => distance(e.first, name) === 1);
			if (near.length > 0) return { text: raw, best: null, confidence: 'near', candidates: near.map((e) => ({ id: e.id, confidence: 'near' })) };
		}
		return none;
	});
}
