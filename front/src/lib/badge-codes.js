/**
 * The badge codes and their metals, with no glyph. `badges.js` bundles every glyph
 * (`import.meta.glob`, inlined as data URIs), so a module that pages without any badge
 * load, such as `players.js` (the ranking and team pages), checks codes here instead and
 * never pulls the glyphs into their chunks. `badges.js` re-exports all of it.
 */

/**
 * The badge catalogue, in catalogue order (Badge.Codes on the server; badges.test.js
 * mirrors it): each code's metal, or 'tiers' when the tier picks it (1 bronze, 2 silver,
 * 3 gold). See the player badges design spec under docs/superpowers/specs/.
 */
export const BADGES = {
	champion: 'gold',
	'runner-up': 'silver',
	bronze: 'bronze',
	chocolate: 'plain',
	'wooden-spoon': 'plain',
	'back-to-back': 'gold',
	threepeat: 'gold',
	dynasty: 'gold',
	phoenix: 'gold',
	legend: 'gold',
	'podium-regular': 'silver',
	'full-set': 'gold',
	'eternal-second': 'silver',
	janus: 'plain',
	comeback: 'silver',
	'on-the-rise': 'bronze',
	icarus: 'plain',
	'lucky-charm': 'silver',
	rookie: 'plain',
	veteran: 'tiers',
	argonaut: 'gold',
	'ever-present': 'tiers',
	homecoming: 'plain',
	comrades: 'silver',
	networker: 'tiers',
	goat: 'gold',
	'alone-at-the-top': 'gold',
	'hall-of-fame-podium': 'silver',
	'hall-of-famer': 'bronze',
	reign: 'gold',
	kingslayer: 'gold',
	rocket: 'bronze',
	specialist: 'tiers',
	'all-rounder': 'tiers',
	decathlete: 'gold',
	'brains-and-brawn': 'silver',
	'clean-sweep': 'gold',
	metronome: 'gold',
	uncrowned: 'plain',
	'photo-finish': 'silver',
	athena: 'bronze',
	apollo: 'bronze',
	artemis: 'bronze',
	hermes: 'bronze',
	heracles: 'bronze',
	theseus: 'bronze',
	ares: 'bronze',
	hades: 'bronze',
	dionysus: 'bronze',
	olympus: 'gold',
	unbeaten: 'silver',
	'perfect-run': 'gold',
	shutout: 'bronze',
	steamroller: 'silver',
	'perfect-pitch': 'gold',
	mvp: 'gold',
	'fair-play': 'silver',
	hype: 'plain',
	costume: 'plain',
	wounded: 'plain',
	torchbearer: 'gold'
};

const hasOwn = (obj, key) => Object.prototype.hasOwnProperty.call(obj, key);

/** Whether the front knows this badge's code (a newer server may send one it does not). */
export const isKnownBadge = (badge) => hasOwn(BADGES, badge.code);

export const isTiered = (code) => BADGES[code] === 'tiers';
