import { describe, expect, it } from 'vitest';
import { forwardedFor } from './forwarded-for.js';

describe('forwardedFor', () => {
	it("hands the API the visitor's address", () => {
		expect(forwardedFor(() => '203.0.113.7')).toEqual({ 'x-forwarded-for': '203.0.113.7' });
	});

	it('sends nothing when the adapter cannot tell the address', () => {
		const throwing = () => {
			throw new Error('Address header was specified with ADDRESS_HEADER=x-forwarded-for but is absent from request');
		};
		expect(forwardedFor(throwing)).toEqual({});
		expect(forwardedFor(() => '')).toEqual({});
	});
});
