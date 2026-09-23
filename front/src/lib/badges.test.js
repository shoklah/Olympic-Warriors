import { describe, expect, it } from 'vitest';
import fr from './i18n/fr.js';
import en from './i18n/en.js';
import { translator } from './i18n';
import { BADGES, badgeDetail, badgeGlyph, badgeMetal, hasGlyph, isKnownBadge, isTiered } from './badges.js';

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
});
