import { describe, expect, it } from 'vitest';
import { teamSizes } from './plan.js';

describe('teamSizes', () => {
	it.each([
		[10, 3, [3, 3, 2, 2]],
		[9, 3, [3, 3, 3]],
		[11, 3, [3, 3, 3, 2]],
		[7, 4, [4, 3]],
		[20, 5, [5, 5, 5, 5]]
	])('%i players, %i per team', (n, per, expected) => {
		const sizes = teamSizes(n, per);
		expect(sizes).toEqual(expected);
		expect(sizes.reduce((a, b) => a + b, 0)).toBe(n);
	});

	it('refuses fewer than two teams', () => {
		expect(teamSizes(3, 3)).toBeNull();
		expect(teamSizes(1, 3)).toBeNull();
		expect(teamSizes(0, 3)).toBeNull();
	});
});
