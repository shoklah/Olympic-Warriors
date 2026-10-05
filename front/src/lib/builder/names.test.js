import { describe, expect, it } from 'vitest';
import { matchNames, normalise, splitNames } from './names.js';

const players = [
	{ id: 1, first_name: 'Léa', last_name: 'Martin' },
	{ id: 2, first_name: 'Paul', last_name: 'Durand' },
	{ id: 3, first_name: 'Paul', last_name: 'Petit' },
	{ id: 4, first_name: 'Inès', last_name: 'Moreau' },
	{ id: 5, first_name: 'Bob', last_name: 'Roux' }
];

describe('normalise', () => {
	it('drops accents and case and squeezes spaces', () => {
		expect(normalise('  LÉA   Martin ')).toBe('lea martin');
	});
});

describe('splitNames', () => {
	it('splits on commas, semicolons, lines, slashes, ampersands and "et"/"and"', () => {
		expect(splitNames('Léa, Paul; Inès\nBob / Léa & Paul et Bob and Léa')).toEqual([
			'Léa', 'Paul', 'Inès', 'Bob', 'Léa', 'Paul', 'Bob', 'Léa'
		]);
	});

	it('drops the filler real answers put before a name, and trailing punctuation or emoji', () => {
		expect(splitNames('Ne pas être avec Marie')).toEqual(['Marie']);
		expect(splitNames('Être en équipe avec Thomas ')).toEqual(['Thomas']);
		expect(splitNames('Je souhaite être avec Adrien !')).toEqual(['Adrien']);
		expect(splitNames('Idéalement, je souhaiterai être avec Victor')).toEqual(['Victor']);
		expect(splitNames('Je voudrais être avec Margot si possible svp 😁')).toEqual(['Margot']);
		expect(splitNames('Avec Emma et/ou Thomas')).toEqual(['Emma', 'Thomas']);
		expect(splitNames('Alexandre ou Paul')).toEqual(['Alexandre', 'Paul']);
	});

	it('drops a leading "avec" and blanks', () => {
		expect(splitNames('Avec Léa,  , with Paul')).toEqual(['Léa', 'Paul']);
	});
});

describe('matchNames', () => {
	const best = (text, self = 99) => matchNames(text, players, self)[0];

	it('matches a whole name exactly, in either order, ignoring accents', () => {
		expect(best('lea martin')).toMatchObject({ best: 1, confidence: 'exact' });
		expect(best('Martin Léa')).toMatchObject({ best: 1, confidence: 'exact' });
	});

	it('matches a first name that is unique', () => {
		expect(best('Inès')).toMatchObject({ best: 4, confidence: 'first' });
	});

	it('does not pick between two players with the same first name', () => {
		const result = best('Paul');
		expect(result.best).toBeNull();
		expect(result.confidence).toBe('ambiguous');
		expect(result.candidates.map((c) => c.id).sort()).toEqual([2, 3]);
	});

	it('resolves a shared first name with a surname or initial', () => {
		expect(best('Paul Durand')).toMatchObject({ best: 2, confidence: 'exact' });
	});

	it('suggests, without preselecting, a first name one typo away', () => {
		const result = best('Ines');
		expect(result).toMatchObject({ best: 4 });
		const typo = best('Lia');
		expect(typo.best).toBeNull();
		expect(typo.confidence).toBe('near');
		expect(typo.candidates.map((c) => c.id)).toEqual([1]);
	});

	it('never offers the player themself', () => {
		expect(matchNames('Léa', players, 1)[0].candidates).toEqual([]);
	});

	it('leaves noise and unknown names without candidates', () => {
		for (const text of ['peu importe', 'personne', 'Zoé', 'n/a']) {
			expect(best(text)).toMatchObject({ best: null, candidates: [] });
		}
	});

	it('returns one entry per name, keeping the text', () => {
		expect(matchNames('Léa, Zoé', players, 99).map((m) => m.text)).toEqual(['Léa', 'Zoé']);
	});
});
