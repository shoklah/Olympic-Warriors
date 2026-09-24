import { describe, expect, it } from 'vitest';
import { themeFrom } from './theme.js';

describe('themeFrom', () => {
	it('keeps a picked theme', () => {
		expect(themeFrom('light')).toBe('light');
		expect(themeFrom('dark')).toBe('dark');
	});

	it('leaves anything else to the device', () => {
		expect(themeFrom(undefined)).toBe('system');
		expect(themeFrom('')).toBe('system');
		expect(themeFrom('system')).toBe('system');
		expect(themeFrom('sepia')).toBe('system');
	});
});
