import { describe, expect, it } from 'vitest';
import fr from './i18n/fr.js';
import en from './i18n/en.js';
import { translator } from './i18n';
import {
	BADGES,
	FAMILIES,
	PROGRESS_CODES,
	PROGRESS_TARGETS,
	TIER_THRESHOLDS,
	badgeCollection,
	badgeDetail,
	badgeGlyph,
	badgeMetal,
	badgeRarity,
	hasGlyph,
	isKnownBadge,
	isTiered,
	nextThreshold,
	progressFor,
	progressView,
	slotLabel
} from './badges.js';

/** Badge.Codes in server/olympic_warriors/models/Badge.py, in order. Keep in sync by hand. */
const BADGE_CODES = [
	'champion', 'runner-up', 'bronze', 'chocolate', 'wooden-spoon',
	'back-to-back', 'threepeat', 'dynasty', 'phoenix', 'legend', 'podium-regular', 'full-set',
	'eternal-second', 'janus', 'comeback', 'on-the-rise', 'icarus', 'lucky-charm',
	'rookie', 'veteran', 'argonaut', 'ever-present', 'homecoming',
	'comrades', 'networker',
	'goat', 'alone-at-the-top', 'hall-of-fame-podium', 'hall-of-famer', 'reign', 'kingslayer', 'rocket',
	'specialist', 'master', 'all-rounder', 'decathlete', 'brains-and-brawn', 'clean-sweep', 'metronome',
	'uncrowned', 'photo-finish',
	'athena', 'apollo', 'artemis', 'hermes', 'heracles', 'theseus', 'ares', 'hades', 'dionysus', 'olympus',
	'unbeaten', 'perfect-run', 'shutout', 'steamroller', 'perfect-pitch',
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
	it('lists every year of a repeated badge; the sheet says the count separately', () => {
		const champion = { code: 'champion', tier: 0, years: [2024, 2026], discipline: null, partner: null };
		expect(badgeDetail(champion, tEn, 'en')).toEqual(['2024', '2026']);
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
		expect(badgeDetail(unbeaten, tEn, 'en')).toEqual(['Dodgeball', '2025', '2026']);
		expect(badgeDetail(unbeaten, tFr, 'fr')).toEqual(['Balle au prisonnier', '2025', '2026']);
	});

	it('says since when a master has held the discipline, in French under fr', () => {
		const master = { code: 'master', tier: 0, years: [2022], discipline: 'Relay', partner: null };
		expect(badgeDetail(master, tEn, 'en')).toEqual(['Relay', 'since 2022']);
		expect(badgeDetail(master, tFr, 'fr')).toEqual(['Relais', 'depuis 2022']);
		expect(badgeDetail({ ...master, years: [] }, tEn, 'en')).toEqual(['Relay']);
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
		expect(FAMILIES.map((f) => f.codes.length)).toEqual([5, 13, 5, 2, 7, 9, 10, 5, 6]);
	});
});

describe('TIER_THRESHOLDS and nextThreshold', () => {
	it('lists the five tiered codes with the server thresholds', () => {
		expect(TIER_THRESHOLDS).toEqual({
			veteran: [3, 5, 10], 'ever-present': [4, 6, 8], networker: [5, 10, 20],
			specialist: [2, 3, 4], 'all-rounder': [3, 5, 8]
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
		expect(c.total).toBe(62);
		expect(c.earned).toBe(2);
		const podiums = c.families.find((f) => f.key === 'podiums');
		expect([podiums.earned, podiums.total]).toEqual([1, 5]);
		expect(c.families.reduce((n, f) => n + f.slots.length, 0)).toBe(62);
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

describe('badgeRarity', () => {
	it('gives the rounded percent of players holding the badge', () => {
		const stats = { players: 47, holders: { champion: 12 } };
		expect(badgeRarity(stats, 'champion')).toEqual({ holders: 12, players: 47, percent: 26 });
	});

	it('rounds to 0 when holders are few but nonzero, and gives 0 holders for a code with none', () => {
		const rare = badgeRarity({ players: 1000, holders: { mvp: 1 } }, 'mvp');
		expect(rare).toEqual({ holders: 1, players: 1000, percent: 0 });

		const none = badgeRarity({ players: 47, holders: {} }, 'mvp');
		expect(none).toEqual({ holders: 0, players: 47, percent: 0 });
	});

	it('reads the at-least-tier count from tiers when a tier is given', () => {
		const stats = { players: 47, holders: { veteran: 20 }, tiers: { veteran: [20, 12, 1] } };
		expect(badgeRarity(stats, 'veteran', 2)).toEqual({ holders: 12, players: 47, percent: 26 });
	});

	it('gives 0 holders for a tiered code missing from tiers', () => {
		const stats = { players: 47, holders: { veteran: 20 }, tiers: {} };
		expect(badgeRarity(stats, 'veteran', 1)).toEqual({ holders: 0, players: 47, percent: 0 });
	});

	it('gives null when stats are missing (an older API) or players is 0', () => {
		expect(badgeRarity(null, 'champion')).toBeNull();
		expect(badgeRarity(undefined, 'champion')).toBeNull();
		expect(badgeRarity({ players: 0, holders: { champion: 0 } }, 'champion')).toBeNull();
	});
});

describe('slotLabel', () => {
	const slotOf = (code, badges) =>
		badgeCollection(badges)
			.families.flatMap((f) => f.slots)
			.find((s) => s.code === code);
	const clean = (years) => [{ code: 'clean-sweep', tier: 0, years, discipline: null, partner: null }];

	it('names an earned slot, a repeated one with a spoken count, and a locked one', () => {
		const t = translator('en');
		expect(slotLabel(slotOf('clean-sweep', clean([2026])), t)).toBe('Clean sweep, badge earned');
		expect(slotLabel(slotOf('clean-sweep', clean([2023, 2026])), t)).toBe('Clean sweep, badge earned 2 times');
		expect(slotLabel(slotOf('clean-sweep', []), t)).toBe('Clean sweep, badge locked');
	});

	it('speaks French', () => {
		const t = translator('fr');
		expect(slotLabel(slotOf('clean-sweep', clean([2023, 2026])), t)).toBe('Razzia, badge obtenu 2 fois');
		expect(slotLabel(slotOf('clean-sweep', []), t)).toBe('Razzia, badge à débloquer');
	});
});

describe('PROGRESS_TARGETS and PROGRESS_CODES', () => {
	/** The codes whose badge can become impossible, each with its « Plus atteignable » line. */
	const CLOSING = ['eternal-second', 'lucky-charm', 'argonaut'];

	it('mirrors the targets of the countable badges without tiers in badges.py', () => {
		expect(PROGRESS_TARGETS).toEqual({
			legend: 3, 'full-set': 3, decathlete: 10, olympus: 9, 'back-to-back': 2, threepeat: 3, dynasty: 4,
			'podium-regular': 3, 'on-the-rise': 2, reign: 3, comrades: 3, 'clean-sweep': 3, 'eternal-second': 2,
			'lucky-charm': 3
		});
	});

	it('lists the 20 codes with progress, in catalogue order: the tiered ones, the targets and argonaut', () => {
		expect(PROGRESS_CODES).toEqual([
			'back-to-back', 'threepeat', 'dynasty', 'legend', 'podium-regular', 'full-set', 'eternal-second',
			'on-the-rise', 'lucky-charm', 'veteran', 'argonaut', 'ever-present', 'comrades', 'networker', 'reign',
			'specialist', 'all-rounder', 'decathlete', 'clean-sweep', 'olympus'
		]);
		expect([...PROGRESS_CODES].sort()).toEqual(
			[...Object.keys(TIER_THRESHOLDS), ...Object.keys(PROGRESS_TARGETS), 'argonaut'].sort()
		);
		const order = Object.keys(BADGES);
		const idx = PROGRESS_CODES.map((code) => order.indexOf(code));
		expect(idx).toEqual([...idx].sort((a, b) => a - b));
	});

	it('words every progress code in both languages: a count line for a bar, a line once out of reach', () => {
		for (const code of PROGRESS_CODES) {
			for (const dict of [fr, en]) {
				if (code === 'argonaut') {
					expect(dict[`badge.count.${code}`], code).toBeUndefined();
				} else {
					expect(dict[`badge.count.${code}`], code).toEqual(expect.stringContaining('{fraction}'));
				}
				if (CLOSING.includes(code)) {
					expect(dict[`badge.outOfReach.${code}`], code).toEqual(expect.any(String));
				} else {
					expect(dict[`badge.outOfReach.${code}`], code).toBeUndefined();
				}
			}
		}
	});
});

describe('progressFor', () => {
	const veteran = { code: 'veteran', value: 7, best: null, reachable: true, discipline: null, partner: null, year: null };
	const legend = { ...veteran, code: 'legend', value: 1 };

	it("finds the profile's progress entry of a code", () => {
		expect(progressFor([legend, veteran], 'veteran')).toBe(veteran);
		expect(progressFor([legend, veteran], 'legend')).toBe(legend);
	});

	it('is null without an entry, for a code without progress, or without a list (an older API)', () => {
		expect(progressFor([legend], 'veteran')).toBeNull();
		expect(progressFor([{ ...veteran, code: 'champion' }], 'champion')).toBeNull();
		expect(progressFor(undefined, 'veteran')).toBeNull();
		expect(progressFor(null, 'veteran')).toBeNull();
		expect(progressFor({ veteran }, 'veteran')).toBeNull();
	});
});

describe('progressView', () => {
	const entry = (code, extra = {}) => ({
		code, value: 0, best: null, reachable: true, discipline: null, partner: null, year: null, ...extra
	});
	const ticks = (view) => view.ticks.map(({ threshold, lit, metal }) => [threshold, lit, metal]);

	it('draws a tiered badge on one track to its top threshold, a tick per tier lit once the count reaches it', () => {
		const view = progressView(entry('veteran', { value: 7 }));
		expect(view).toMatchObject({ code: 'veteran', outOfReach: false, count: 7, target: 10, share: 0.7, topTier: false });
		expect(ticks(view)).toEqual([[3, true, 'bronze'], [5, true, 'silver'], [10, false, 'gold']]);
		expect(view.ticks.map((tick) => tick.share)).toEqual([0.3, 0.5, 1]);
		// The fill takes the metal of the highest tick lit.
		expect(view.fill).toBe('silver');
	});

	it('aims at the first threshold above the count: a tier just reached aims at the next one', () => {
		const view = progressView(entry('veteran', { value: 3 }));
		expect(view).toMatchObject({ count: 3, target: 5, fill: 'bronze' });
		expect(ticks(view)).toEqual([[3, true, 'bronze'], [5, false, 'silver'], [10, false, 'gold']]);
	});

	it('fills in muted before the first tick, with nothing lit', () => {
		const view = progressView(entry('networker', { value: 4 }));
		expect(view).toMatchObject({ count: 4, target: 5, share: 0.2, fill: 'muted' });
		expect(view.ticks.every((tick) => !tick.lit)).toBe(true);
		expect(progressView(entry('veteran'))).toMatchObject({ count: 0, target: 3, share: 0, fill: 'muted' });
	});

	it("lights a specialist's ticks by its own discipline's count, and names the discipline", () => {
		const view = progressView(entry('specialist', { value: 2, discipline: 'Darts' }));
		expect(view).toMatchObject({ count: 2, target: 3, fill: 'bronze', discipline: 'Darts' });
		expect(ticks(view)).toEqual([[2, true, 'bronze'], [3, false, 'silver'], [4, false, 'gold']]);
	});

	it('shows a full gold track, every tick lit, and the count alone at the top tier', () => {
		const view = progressView(entry('veteran', { value: 12 }));
		expect(view).toMatchObject({ count: 12, target: null, share: 1, topTier: true, fill: 'gold', best: null });
		expect(view.ticks.every((tick) => tick.lit)).toBe(true);
		expect(progressView(entry('veteran', { value: 10 }))).toMatchObject({ count: 10, topTier: true });
	});

	it("aims ever-present above its best run and keeps that best for the note", () => {
		// Tier 2 held from a run of 6, a current run of 5: « 5 / 8 », the 4 lit by the run.
		const view = progressView(entry('ever-present', { value: 5, best: 6 }));
		expect(view).toMatchObject({ count: 5, target: 8, share: 5 / 8, topTier: false, fill: 'bronze', best: 6 });
		expect(ticks(view)).toEqual([[4, true, 'bronze'], [6, false, 'silver'], [8, false, 'gold']]);
	});

	it("lights no tick for ever-present's short run below its best tier", () => {
		const view = progressView(entry('ever-present', { value: 1, best: 6 }));
		expect(view).toMatchObject({ count: 1, target: 8, fill: 'muted', best: 6 });
		expect(view.ticks.every((tick) => !tick.lit)).toBe(true);
	});

	it('puts ever-present at the top tier by its best run, whatever the current one, with no note', () => {
		const view = progressView(entry('ever-present', { value: 2, best: 9 }));
		expect(view).toMatchObject({ count: 9, target: null, share: 1, topTier: true, fill: 'gold', best: null });
		expect(view.ticks.every((tick) => tick.lit)).toBe(true);
	});

	it('draws a badge without tiers to its fixed target, in its own metal, with no tick', () => {
		const view = progressView(entry('legend', { value: 1 }));
		expect(view).toMatchObject({ count: 1, target: 3, share: 1 / 3, topTier: false, ticks: [], fill: 'gold' });
		expect(progressView(entry('podium-regular', { value: 1, best: 1 })).fill).toBe('silver');
		expect(progressView(entry('on-the-rise', { value: 1, best: 1 })).fill).toBe('bronze');
	});

	it("fills every badge without tiers in its catalogue metal, the accent for a plain one", () => {
		for (const code of Object.keys(PROGRESS_TARGETS)) {
			const metal = BADGES[code] === 'plain' ? 'accent' : BADGES[code];
			expect(progressView(entry(code, { value: 1 })).fill, code).toBe(metal);
		}
	});

	it('caps the fill at the target', () => {
		expect(progressView(entry('legend', { value: 5 })).share).toBe(1);
	});

	it("keeps a streak's best run for the note only when it is above the current run", () => {
		expect(progressView(entry('back-to-back', { value: 0, best: 1 })).best).toBe(1);
		expect(progressView(entry('podium-regular', { value: 2, best: 2 })).best).toBeNull();
		expect(progressView(entry('legend', { value: 2 })).best).toBeNull();
	});

	it('carries the partner of comrades and the year of clean-sweep', () => {
		const hugo = { id: 7, first_name: 'Hugo', last_name: 'Maurinier', photo: null };
		expect(progressView(entry('comrades', { value: 2, partner: hugo }))).toMatchObject({
			count: 2, target: 3, partner: hugo, discipline: null, year: null
		});
		expect(progressView(entry('clean-sweep', { value: 2, year: 2025 }))).toMatchObject({
			count: 2, target: 3, year: 2025, partner: null, discipline: null
		});
	});

	it('is out of reach, with no bar, for a badge that can no longer be earned', () => {
		for (const code of ['eternal-second', 'lucky-charm', 'argonaut']) {
			expect(progressView(entry(code, { value: null, reachable: false })), code).toEqual({ code, outOfReach: true });
		}
	});

	it('draws nothing for argonaut while reachable, a code without progress, or no entry', () => {
		expect(progressView(entry('argonaut'))).toBeNull();
		expect(progressView(entry('champion', { value: 1 }))).toBeNull();
		expect(progressView(null)).toBeNull();
	});

	it('reads a missing count as 0', () => {
		expect(progressView(entry('legend', { value: null }))).toMatchObject({ count: 0, share: 0 });
	});
});
