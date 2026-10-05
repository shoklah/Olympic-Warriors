import { describe, expect, it } from 'vitest';
import { matchNames, normalise, splitNames } from './names.js';

const players = [
	{ id: 1, first_name: 'Léa', last_name: 'Martin' },
	{ id: 2, first_name: 'Paul', last_name: 'Durand' },
	{ id: 3, first_name: 'Paul', last_name: 'Petit' },
	{ id: 4, first_name: 'Inès', last_name: 'Moreau' },
	{ id: 5, first_name: 'Bob', last_name: 'Roux' },
	{ id: 6, first_name: 'Marie', last_name: 'Clanet' },
	{ id: 7, first_name: 'Antoine', last_name: 'Dupont' },
	{ id: 8, first_name: 'Sarah', last_name: 'Dupont' },
	{ id: 9, first_name: 'Jean-Pierre', last_name: 'de la Fontaine' },
	{ id: 10, first_name: 'Alexandra', last_name: 'Boucton' },
	{ id: 11, first_name: 'Emma', last_name: 'Boucton' }
];

describe('normalise', () => {
	it('drops accents and case and squeezes spaces', () => {
		expect(normalise('  LÉA   Martin ')).toBe('lea martin');
	});
});

describe('splitNames', () => {
	it('splits on commas, semicolons, lines, slashes, ampersands, "et", "ou", "et/ou" and "and"', () => {
		expect(splitNames('Léa, Paul; Inès\nBob / Léa & Paul et Bob and Léa')).toEqual([
			'Léa', 'Paul', 'Inès', 'Bob', 'Léa', 'Paul', 'Bob', 'Léa'
		]);
		expect(splitNames('Emma et/ou Thomas')).toEqual(['Emma', 'Thomas']);
		expect(splitNames('Alexandre ou Paul')).toEqual(['Alexandre', 'Paul']);
	});

	it('keeps each fragment as written and drops blanks', () => {
		expect(splitNames('Ne pas être avec Marie,  , Idéalement avec Paul !')).toEqual([
			'Ne pas être avec Marie',
			'Idéalement avec Paul !'
		]);
	});
});

describe('matchNames', () => {
	const first = (text, self = 99) => matchNames(text, players, self)[0];
	const ids = (match) => match.candidates.map((c) => c.id).sort((a, b) => a - b);

	it('finds a name wherever it sits in the sentence, whatever surrounds it', () => {
		for (const text of [
			'Ne pas être avec Marie',
			'Je souhaite être avec Marie !',
			'je voudrais être en équipe avec Marie si possible svp 😁',
			'marie',
			'MARIE (pour le ❤️)'
		]) {
			expect(first(text), text).toMatchObject({ best: 6, confidence: 'first' });
		}
		// A comma still splits the answer: the part that names someone is found among the parts.
		const parts = matchNames('Idéalement, je voudrais être avec Marie', players, 99);
		expect(parts.map((m) => m.best)).toEqual([null, 6]);
	});

	it('matches a whole name in either order, ignoring accents and case', () => {
		expect(first('lea martin')).toMatchObject({ best: 1, confidence: 'exact' });
		expect(first('Martin Léa')).toMatchObject({ best: 1, confidence: 'exact' });
		expect(first('avec Antoine dupont si il est là')).toMatchObject({ best: 7, confidence: 'exact' });
	});

	it('matches a last name alone', () => {
		expect(first('Clanet')).toMatchObject({ best: 6, confidence: 'last' });
		expect(first('plutôt avec Durand')).toMatchObject({ best: 2, confidence: 'last' });
	});

	it('prefers the whole name over a shared first name', () => {
		const result = first('Paul Durand');
		expect(result).toMatchObject({ best: 2, confidence: 'exact' });
		expect(ids(result)).toEqual([2]);
	});

	it('does not pick between players sharing a first name or a last name', () => {
		const paul = first('Paul');
		expect(paul).toMatchObject({ best: null, confidence: 'ambiguous' });
		expect(ids(paul)).toEqual([2, 3]);
		const dupont = first('Dupont');
		expect(dupont).toMatchObject({ best: null, confidence: 'ambiguous' });
		expect(ids(dupont)).toEqual([7, 8]);
	});

	it('resolves a shared last name with the first name', () => {
		expect(first('Sarah Dupont')).toMatchObject({ best: 8, confidence: 'exact' });
		expect(first('Sarah')).toMatchObject({ best: 8, confidence: 'first' });
	});

	it('narrows a shared last name by a nickname that starts the first name', () => {
		expect(first('Alex Boucton')).toMatchObject({ best: 10, confidence: 'last' });
		expect(ids(first('Boucton'))).toEqual([10, 11]);
	});

	it('suggests the first names a nickname starts, without proposing one', () => {
		const result = first('Alex');
		expect(result).toMatchObject({ best: null, confidence: 'near' });
		expect(ids(result)).toEqual([10]);
	});

	it('handles compound first names and multi-word last names', () => {
		expect(first('Jean-Pierre')).toMatchObject({ best: 9, confidence: 'first' });
		expect(first('de la Fontaine')).toMatchObject({ best: 9, confidence: 'last' });
		expect(first('Jean Pierre de la Fontaine')).toMatchObject({ best: 9, confidence: 'exact' });
	});

	it('matches whole words only', () => {
		expect(first('Bobby')).toMatchObject({ best: null, candidates: [] });
		expect(first('Paulette')).toMatchObject({ best: null, candidates: [] });
	});

	it('suggests, without preselecting, a name one typo away from a short answer', () => {
		const result = first('Lia');
		expect(result).toMatchObject({ best: null, confidence: 'near' });
		expect(ids(result)).toEqual([1]);
		expect(first('Maria')).toMatchObject({ best: null, confidence: 'near' });
	});

	it('does not suggest typos inside a long sentence', () => {
		expect(first('Une petite préférence avec les premiers participants des olympiades')).toMatchObject({
			candidates: []
		});
	});

	it('never offers the player themself', () => {
		expect(matchNames('Léa', players, 1)[0].candidates).toEqual([]);
		expect(ids(matchNames('Paul', players, 2)[0])).toEqual([3]);
	});

	it('leaves noise and unknown names without candidates', () => {
		for (const text of ['peu importe', 'personne', 'Zoé', 'n/a', 'pas de préférence']) {
			expect(first(text), text).toMatchObject({ best: null, candidates: [] });
		}
	});

	it('returns one entry per fragment, keeping its text', () => {
		const result = matchNames('Léa, Zoé et Paul Durand', players, 99);

		expect(result.map((m) => m.text)).toEqual(['Léa', 'Zoé', 'Paul Durand']);
		expect(result.map((m) => m.best)).toEqual([1, null, 2]);
	});
});
