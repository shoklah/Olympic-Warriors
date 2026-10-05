/**
 * What the builder's player sheet draws of a player (spec 2026-10-06-builder-player-preview).
 * Pure. The fallbacks are the scorer's own (`features`), so the sheet never disagrees with the
 * balance about which values are estimated.
 */
import { features } from './score.js';

/** The profile of `player` for the edition's `skills`, names in `locale` (anything but `en` is French). */
export function playerProfile(player, skills, locale) {
	const { skills: values, incomplete } = features(player, skills);
	return {
		rating: player.rating,
		globalLevel: player.global_level ?? null,
		frequency: player.sport_frequency || null,
		bars: skills.map((s) => ({
			identifier: s.identifier,
			name: locale === 'en' ? s.name_en : s.name_fr,
			value: values[s.identifier],
			estimated: player.ratings?.[s.identifier] == null
		})),
		sports: player.sports ?? [],
		incomplete
	};
}
