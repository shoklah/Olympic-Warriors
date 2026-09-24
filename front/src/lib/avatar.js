/**
 * The first letter of a name part, accents kept: NFC first, so an `e` followed by a
 * combining acute comes out as one `É`, then the first letter with any marks still on it.
 * Leading punctuation is skipped (`d'Artagnan` gives `D`).
 */
const firstLetter = (part) =>
	String(part ?? '')
		.normalize('NFC')
		.match(/\p{L}\p{M}*/u)?.[0] ?? '';

/**
 * What an avatar without a photo shows: the first letter of the first name and of the last
 * name, `LM` for Léa Martin. Uppercased here rather than in CSS: these are initials, not text
 * the markup keeps in sentence case. A missing part gives one letter, nothing at all `?`.
 */
export function initials(first, last) {
	return (firstLetter(first) + firstLetter(last)).toUpperCase() || '?';
}
