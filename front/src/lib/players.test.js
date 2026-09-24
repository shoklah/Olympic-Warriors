import { describe, expect, it } from 'vitest';
import {
	MAX_PLACES,
	bestDisciplines,
	byDisplayedName,
	editionStatus,
	formatAverage,
	fullName,
	listYears,
	showcaseLabel,
	shownPlaces,
	spokenPlaces
} from './players.js';

describe('formatAverage', () => {
	it('prints one decimal with the locale separator', () => {
		expect(formatAverage(2.5, 'en')).toBe('2.5');
		expect(formatAverage(2.5, 'fr')).toBe('2,5');
		expect(formatAverage(1, 'en')).toBe('1.0');
	});

	it('treats anything but en as French', () => {
		expect(formatAverage(1.5, 'de')).toBe('1,5');
	});

	it('dashes a missing average', () => {
		expect(formatAverage(null, 'en')).toBe('—');
	});
});

describe('editionStatus', () => {
	it('is ranked when finished with a rank', () => {
		expect(editionStatus({ finished: true, rank: 2 })).toBe('ranked');
	});

	it('is in progress until the edition is over, whatever the rank', () => {
		expect(editionStatus({ finished: false, rank: null })).toBe('inProgress');
	});

	it('is unranked when over without a rank', () => {
		expect(editionStatus({ finished: true, rank: null })).toBe('unranked');
	});
});

describe('fullName', () => {
	it('joins first and last name', () => {
		expect(fullName({ first_name: 'Xavier', last_name: 'Baby' })).toBe('Xavier Baby');
	});

	it('keeps just the first name when the last name is blank', () => {
		expect(fullName({ first_name: 'Xavier', last_name: '' })).toBe('Xavier');
	});

	it('keeps just the last name when the first name is blank', () => {
		expect(fullName({ first_name: '', last_name: 'Baby' })).toBe('Baby');
	});

	it('dashes when both are blank', () => {
		expect(fullName({ first_name: '', last_name: '' })).toBe('—');
	});
});

describe('shownPlaces', () => {
	const places = (n) => Array.from({ length: n }, (_, i) => ({ year: 2030 - i, rank: i + 1 }));

	it('shows every place up to the cap', () => {
		expect(shownPlaces(places(3))).toEqual({ shown: places(3), more: 0 });
		expect(shownPlaces(places(MAX_PLACES)).more).toBe(0);
	});

	it('keeps the best places and counts the rest', () => {
		const { shown, more } = shownPlaces(places(MAX_PLACES + 2));
		expect(shown).toEqual(places(MAX_PLACES));
		expect(more).toBe(2);
	});
});

describe('bestDisciplines', () => {
	const d = (name, position) => ({ name, position, places: [{ year: 2025, rank: position }] });

	it('keeps the disciplines at position 1', () => {
		expect(bestDisciplines([d('Relay', 1), d('Darts', 2)])).toEqual({ shown: [d('Relay', 1)], more: 0, count: 1 });
	});

	it('keeps every tied best discipline up to the cap', () => {
		const tied = ['A', 'B', 'C', 'D', 'E'].map((n) => d(n, 1));
		expect(bestDisciplines(tied)).toEqual({ shown: tied.slice(0, 3), more: 2, count: 5 });
	});

	it('is empty without disciplines', () => {
		expect(bestDisciplines([])).toEqual({ shown: [], more: 0, count: 0 });
	});
});

describe('byDisplayedName', () => {
	const tie = ['Dodgeball', 'Blindtest', 'Hide and Seek'].map((name) => ({ name, position: 1, places: [] }));

	it('sorts a tie by the French displayed name', () => {
		expect(byDisplayedName(tie, 'fr').map((d) => d.name)).toEqual(['Dodgeball', 'Blindtest', 'Hide and Seek']);
	});

	it('sorts a tie by the English displayed name', () => {
		expect(byDisplayedName(tie, 'en').map((d) => d.name)).toEqual(['Blindtest', 'Dodgeball', 'Hide and Seek']);
	});

	it('keeps different positions in the server order, only re-sorting ties', () => {
		const mixed = [
			{ name: 'Relay', position: 1, places: [] },
			{ name: 'Darts', position: 2, places: [] },
			{ name: 'Basketball', position: 2, places: [] }
		];
		expect(byDisplayedName(mixed, 'en').map((d) => d.name)).toEqual(['Relay', 'Basketball', 'Darts']);
	});
});

describe('spokenPlaces', () => {
	const places = [
		{ year: 2026, rank: 1 },
		{ year: 2023, rank: 2 }
	];

	it('reads places best first, in English', () => {
		expect(spokenPlaces(places, 'en')).toBe('1st place in 2026, 2nd place in 2023');
	});

	it('reads places best first, in French', () => {
		expect(spokenPlaces(places, 'fr')).toBe('1re place en 2026, 2e place en 2023');
	});
});

describe('showcaseLabel', () => {
	const showcase = [
		{ code: 'champion', tier: 0, discipline: null },
		{ code: 'veteran', tier: 2, discipline: null },
		{ code: 'networker', tier: 1, discipline: null }
	];

	it('names the badges in display order, in English', () => {
		expect(showcaseLabel(showcase, 'en')).toBe('showcase: Champion, Veteran, Networker');
	});

	it('names the badges in display order, in French', () => {
		expect(showcaseLabel(showcase, 'fr')).toBe('vitrine : Champion, Vétéran, Rassembleur');
	});

	it('names a specialist by the badge, not its discipline', () => {
		expect(showcaseLabel([{ code: 'specialist', tier: 1, discipline: 'Relay' }], 'fr')).toBe('vitrine : Spécialiste');
	});

	it('skips a code the front does not know, from a newer server', () => {
		const withUnknown = [showcase[0], { code: 'future-badge', tier: 0, discipline: null }, showcase[2]];
		expect(showcaseLabel(withUnknown, 'en')).toBe('showcase: Champion, Networker');
	});

	it('adds nothing for an empty showcase, one of unknown codes only, or none at all', () => {
		expect(showcaseLabel([], 'en')).toBe('');
		expect(showcaseLabel([{ code: 'future-badge', tier: 0, discipline: null }], 'fr')).toBe('');
		expect(showcaseLabel(undefined, 'en')).toBe('');
	});
});

describe('listYears', () => {
	it('joins years as a sentence list in English', () => {
		expect(listYears([2024], 'en')).toBe('2024');
		expect(listYears([2024, 2026], 'en')).toBe('2024 and 2026');
		expect(listYears([2024, 2025, 2026], 'en')).toBe('2024, 2025, and 2026');
	});

	it('joins years as a sentence list in French', () => {
		expect(listYears([2024, 2026], 'fr')).toBe('2024 et 2026');
		expect(listYears([2024, 2025, 2026], 'fr')).toBe('2024, 2025 et 2026');
	});
});
