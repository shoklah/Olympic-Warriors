import { describe, expect, it } from 'vitest';
import { builderPayload } from '$lib/fixtures/builder.js';
import { playerProfile } from './profile.js';

const { players, skills } = builderPayload;
const byId = (id) => players.find((p) => p.id === id);

describe('playerProfile', () => {
	it('gives one bar per skill in order, from the player own ratings', () => {
		const profile = playerProfile(byId(1), skills, 'en');

		expect(profile.rating).toBe(8);
		expect(profile.frequency).toBe('four_hours');
		expect(profile.bars).toEqual([
			{ identifier: 'CARD', name: 'Cardio', value: 9, estimated: false },
			{ identifier: 'STR', name: 'Strength', value: 7, estimated: false }
		]);
		expect(profile.incomplete).toBe(false);
	});

	it('takes the overall rating for a missing skill and marks it estimated', () => {
		const profile = playerProfile({ ...byId(1), ratings: { CARD: 9 } }, skills, 'en');

		expect(profile.bars[1]).toMatchObject({ identifier: 'STR', value: 8, estimated: true });
		expect(profile.bars[0].estimated).toBe(false);
		expect(profile.incomplete).toBe(true);
	});

	it('marks every skill estimated and the profile incomplete when there are no ratings or frequency', () => {
		const profile = playerProfile(byId(5), skills, 'en');

		expect(profile.bars.map((b) => [b.value, b.estimated])).toEqual([[3, true], [3, true]]);
		expect(profile.frequency).toBeNull();
		expect(profile.incomplete).toBe(true);
	});

	it('names the skills by locale', () => {
		expect(playerProfile(byId(1), skills, 'fr').bars[1].name).toBe('Force');
		expect(playerProfile(byId(1), skills, 'en').bars[1].name).toBe('Strength');
	});

	it('carries the global level (null when unknown) and the sports', () => {
		expect(playerProfile({ ...byId(1), global_level: 6 }, skills, 'en').globalLevel).toBe(6);
		expect(playerProfile({ ...byId(1), global_level: null }, skills, 'en').globalLevel).toBeNull();
		expect(playerProfile(byId(3), skills, 'en').sports).toEqual([{ sport: 'Judo', level: 'league' }]);
	});
});
