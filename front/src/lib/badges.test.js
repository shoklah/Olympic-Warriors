import { describe, expect, it } from 'vitest';
import fr from './i18n/fr.js';
import en from './i18n/en.js';
import { translator } from './i18n';
import {
	BADGES,
	FAMILIES,
	TIER_THRESHOLDS,
	badgeCollection,
	badgeDetail,
	badgeGlyph,
	badgeMetal,
	hasGlyph,
	isKnownBadge,
	isTiered,
	nextThreshold
} from './badges.js';

/** Badge.Codes in server/olympic_warriors/models/Badge.py, in order. Keep in sync by hand. */
const BADGE_CODES = [
	'champion', 'runner-up', 'bronze', 'chocolate', 'wooden-spoon',
	'back-to-back', 'threepeat', 'dynasty', 'phoenix', 'legend', 'podium-regular', 'full-set',
	'eternal-second', 'janus', 'comeback', 'on-the-rise', 'icarus', 'lucky-charm',
	'rookie', 'veteran', 'argonaut', 'ever-present', 'homecoming', 'globetrotter',
	'comrades', 'networker',
	'goat', 'alone-at-the-top', 'hall-of-fame-podium', 'hall-of-famer', 'reign', 'kingslayer', 'rocket',
	'specialist', 'all-rounder', 'decathlete', 'brains-and-brawn', 'clean-sweep', 'metronome',
	'uncrowned', 'photo-finish',
	'athena', 'apollo', 'artemis', 'hermes', 'heracles', 'theseus', 'ares', 'hades', 'dionysus', 'olympus',
	'unbeaten', 'perfect-run', 'shutout', 'steamroller', 'golden-whistle', 'perfect-pitch',
	'mvp', 'fair-play', 'hype', 'costume', 'wounded', 'torchbearer'
];

const tEn = translator('en');
const tFr = translator('fr');

describe('badge catalogue', () => {
	it('mirrors Badge.Codes, in order', () => {
		expect(Object.keys(BADGES)).toEqual(BADGE_CODES);
	});

	it('gives every badge a metal', () => {
		for (const code of BADGE_CODES) {
			expect(['gold', 'silver', 'bronze', 'plain', 'tiers'], code).toContain(BADGES[code]);
		}
	});

	it('draws every badge but specialist, which borrows the discipline icon', () => {
		for (const code of BADGE_CODES.filter((c) => c !== 'specialist')) {
			expect(hasGlyph(code), code).toBe(true);
		}
	});

	it('names and explains every badge in both languages', () => {
		for (const code of BADGE_CODES) {
			for (const dict of [fr, en]) {
				expect(dict[`badge.${code}.name`], code).toEqual(expect.any(String));
				expect(dict[`badge.${code}.rule`], code).toEqual(expect.any(String));
			}
		}
	});
});

describe('badgeMetal', () => {
	it('is fixed, or picked by the tier', () => {
		expect(badgeMetal({ code: 'champion', tier: 0 })).toBe('gold');
		expect(badgeMetal({ code: 'wooden-spoon', tier: 0 })).toBe('plain');
		expect(['bronze', 'silver', 'gold'].map((m, i) => badgeMetal({ code: 'veteran', tier: i + 1 }))).toEqual([
			'bronze',
			'silver',
			'gold'
		]);
	});

	it('clamps a tier out of range into bronze to gold, and a missing one to bronze', () => {
		expect(badgeMetal({ code: 'veteran', tier: 0 })).toBe('bronze');
		expect(badgeMetal({ code: 'veteran', tier: 4 })).toBe('gold');
		expect(badgeMetal({ code: 'veteran' })).toBe('bronze');
		expect(badgeMetal({ code: 'veteran', tier: null })).toBe('bronze');
	});

	it('is plain for a code it does not know', () => {
		expect(badgeMetal({ code: 'future-badge', tier: 2 })).toBe('plain');
	});
});

describe('badgeGlyph', () => {
	it('is the badge glyph, or the discipline icon for specialist', () => {
		expect(badgeGlyph({ code: 'champion' })).toMatch(/badges\/champion\.svg$/);
		expect(badgeGlyph({ code: 'specialist', discipline: 'Rugby' })).toMatch(/icons\/rugby\.svg$/);
	});
});

describe('isKnownBadge and isTiered', () => {
	it('knows the catalogue only', () => {
		expect(isKnownBadge({ code: 'goat' })).toBe(true);
		expect(isKnownBadge({ code: 'future-badge' })).toBe(false);
		expect(isTiered('veteran')).toBe(true);
		expect(isTiered('champion')).toBe(false);
	});
});

describe('badgeDetail', () => {
	it('counts and lists the years of a repeated badge', () => {
		const champion = { code: 'champion', tier: 0, years: [2024, 2026], discipline: null, partner: null };
		expect(badgeDetail(champion, tEn, 'en')).toEqual(['×2', '2024', '2026']);
		expect(badgeDetail({ ...champion, years: [2025] }, tEn, 'en')).toEqual(['2025']);
	});

	it('gives the tier and the year it was reached', () => {
		const veteran = { code: 'veteran', tier: 2, years: [2024, 2026], discipline: null, partner: null };
		expect(badgeDetail(veteran, tEn, 'en')).toEqual(['Tier 2', '2026']);
		expect(badgeDetail(veteran, tFr, 'fr')).toEqual(['Niveau 2', '2026']);
	});

	it('gives the tier its metal shows, clamped into 1 to 3', () => {
		const veteran = { code: 'veteran', years: [2026], discipline: null, partner: null };
		expect(badgeDetail({ ...veteran, tier: 0 }, tEn, 'en')).toEqual(['Tier 1', '2026']);
		expect(badgeDetail({ ...veteran, tier: 4 }, tEn, 'en')).toEqual(['Tier 3', '2026']);
		expect(badgeDetail(veteran, tEn, 'en')).toEqual(['Tier 1', '2026']);
	});

	it('names the discipline of a specialist, in French under fr', () => {
		const specialist = { code: 'specialist', tier: 1, years: [2026], discipline: 'Relay', partner: null };
		expect(badgeDetail(specialist, tEn, 'en')).toEqual(['Relay', 'Tier 1', '2026']);
		expect(badgeDetail(specialist, tFr, 'fr')).toEqual(['Relais', 'Niveau 1', '2026']);
	});

	it('names the discipline of any badge that has one', () => {
		const unbeaten = { code: 'unbeaten', tier: 0, years: [2025, 2026], discipline: 'Dodgeball', partner: null };
		expect(badgeDetail(unbeaten, tEn, 'en')).toEqual(['Dodgeball', '×2', '2025', '2026']);
		expect(badgeDetail(unbeaten, tFr, 'fr')).toEqual(['Balle au prisonnier', '×2', '2025', '2026']);
	});

	it('leaves the partner of comrades to the page, keeping the year', () => {
		const comrades = { code: 'comrades', tier: 0, years: [2026], discipline: null, partner: { id: 12 } };
		expect(badgeDetail(comrades, tEn, 'en')).toEqual(['2026']);
	});

	it('is empty when the badge has no year', () => {
		const comrades = { code: 'comrades', tier: 0, years: [], discipline: null, partner: { id: 12 } };
		expect(badgeDetail(comrades, tEn, 'en')).toEqual([]);
		expect(badgeDetail({ ...comrades, code: 'champion', partner: null }, tEn, 'en')).toEqual([]);
	});
});

describe('FAMILIES', () => {
	it('covers every code exactly once, in catalogue order inside each family', () => {
		const codes = FAMILIES.flatMap((f) => f.codes);
		expect([...codes].sort()).toEqual(Object.keys(BADGES).sort());
		expect(new Set(codes).size).toBe(codes.length);
		const order = Object.keys(BADGES);
		for (const f of FAMILIES) {
			const idx = f.codes.map((c) => order.indexOf(c));
			expect(idx).toEqual([...idx].sort((a, b) => a - b));
		}
		expect(FAMILIES.map((f) => f.key)).toEqual([
			'podiums', 'streaks', 'loyalty', 'teammates', 'hall-of-fame', 'disciplines', 'olympus', 'games', 'awards'
		]);
		expect(FAMILIES.map((f) => f.codes.length)).toEqual([5, 13, 6, 2, 7, 8, 10, 6, 6]);
	});
});

describe('TIER_THRESHOLDS and nextThreshold', () => {
	it('lists the six tiered codes with the server thresholds', () => {
		expect(TIER_THRESHOLDS).toEqual({
			veteran: [3, 5, 10], 'ever-present': [4, 6, 8], networker: [20, 40, 60],
			specialist: [2, 3, 4], 'all-rounder': [3, 5, 8], 'golden-whistle': [5, 10, 20]
		});
		expect(Object.keys(TIER_THRESHOLDS).sort()).toEqual(Object.keys(BADGES).filter(isTiered).sort());
	});

	it('gives the next threshold, the first for a locked slot, and none at the top or untiered', () => {
		expect(nextThreshold('veteran', 0)).toBe(3);
		expect(nextThreshold('veteran', 1)).toBe(5);
		expect(nextThreshold('veteran', 2)).toBe(10);
		expect(nextThreshold('veteran', 3)).toBeNull();
		expect(nextThreshold('champion', 0)).toBeNull();
	});
});

describe('badgeCollection', () => {
	const entry = (code, extra = {}) => ({ code, tier: 0, years: [2026], discipline: null, partner: null, ...extra });

	it('counts earned slots overall and per family, ignoring unknown codes', () => {
		const c = badgeCollection([entry('champion', { years: [2021, 2024] }), entry('rookie'), entry('future-badge')]);
		expect(c.total).toBe(63);
		expect(c.earned).toBe(2);
		const podiums = c.families.find((f) => f.key === 'podiums');
		expect([podiums.earned, podiums.total]).toEqual([1, 5]);
		expect(c.families.reduce((n, f) => n + f.slots.length, 0)).toBe(63);
	});

	it('counts repeats, disciplines and partners, but a tier once', () => {
		const c = badgeCollection([
			entry('champion', { years: [2021, 2024] }),
			entry('specialist', { tier: 1, discipline: 'Rugby' }),
			entry('specialist', { tier: 2, discipline: 'Crossfit', years: [2025] }),
			entry('comrades', { partner: { id: 1, first_name: 'A', last_name: 'B' } }),
			entry('comrades', { partner: { id: 2, first_name: 'C', last_name: 'D' } }),
			entry('comrades', { partner: { id: 3, first_name: 'E', last_name: 'F' } }),
			entry('veteran', { tier: 2, years: [2024, 2026] })
		]);
		const slot = (code) => c.families.flatMap((f) => f.slots).find((s) => s.code === code);
		expect(slot('champion').count).toBe(2);
		expect(slot('specialist').count).toBe(2);
		expect(slot('specialist').medal.discipline).toBe('Crossfit'); // highest tier drawn
		expect(slot('comrades').count).toBe(3);
		expect(slot('veteran').count).toBe(1);
		expect(slot('veteran').earned).toBe(true);
	});

	it('gives a locked slot a stub medal and no entries', () => {
		const slot = badgeCollection([]).families[0].slots[0];
		expect(slot).toEqual({
			code: 'champion', entries: [], count: 0, earned: false,
			medal: { code: 'champion', tier: 0, years: [], discipline: null, partner: null }
		});
	});
});
