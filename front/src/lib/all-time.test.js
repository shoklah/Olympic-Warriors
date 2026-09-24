import { describe, expect, it } from 'vitest';
import { allTimePath, byShownName, yearSpan } from './all-time.js';
import { held } from './fixtures/held.js';

describe('byShownName', () => {
	it('sorts by the English name in English', () => {
		expect(byShownName(held, 'en').map((d) => d.name)).toEqual([
			'Blindtest',
			'Dodgeball',
			'Hide and Seek',
			'Relay'
		]);
	});

	it('sorts by the French name in French', () => {
		// Balle au prisonnier, Blindtest, Cache-cache, Relais.
		expect(byShownName(held, 'fr').map((d) => d.name)).toEqual([
			'Dodgeball',
			'Blindtest',
			'Hide and Seek',
			'Relay'
		]);
	});

	it('leaves its input alone', () => {
		byShownName(held, 'fr');
		expect(held[0].name).toBe('Blindtest');
	});
});

describe('yearSpan', () => {
	it('spans the first and the last year held', () => {
		expect(yearSpan([2021, 2024, 2026])).toBe('2021–2026');
	});

	it('prints a single year alone', () => {
		expect(yearSpan([2026])).toBe('2026');
	});

	it('prints nothing without a year', () => {
		expect(yearSpan([])).toBe('');
	});
});

describe('allTimePath', () => {
	const relay = held[3];

	it("leads to the all-time tab of the browsed year's page when that edition held it", () => {
		expect(allTimePath(relay, 2024)).toBe('/2024/disciplines/7?tab=all-time');
		expect(allTimePath(relay, '2023')).toBe('/2023/disciplines/3?tab=all-time');
	});

	it('leads to its newest edition otherwise', () => {
		expect(allTimePath(relay, 2025)).toBe('/2026/disciplines/10?tab=all-time');
		expect(allTimePath(held[1], 2026)).toBe('/2025/disciplines/32?tab=all-time');
	});
});
