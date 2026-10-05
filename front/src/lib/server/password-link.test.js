import { describe, expect, it, vi } from 'vitest';
import { linkAction, linkPath, passwordErrors } from './password-link.js';

vi.mock('$lib/server/urls', () => ({ api: (path) => `http://api${path}` }));

describe('linkPath', () => {
	it('splices a Django-shaped link under its prefix', () => {
		expect(linkPath('/claim')({ uid: 'MzQ', token: 'claim-token-demo' })).toBe('/claim/MzQ/claim-token-demo/');
		expect(linkPath('/password-reset')({ uid: 'MzQ', token: 'a_b-c' })).toBe('/password-reset/MzQ/a_b-c/');
	});

	it('refuses any other part', () => {
		const path = linkPath('/claim');
		for (const params of [
			{ uid: '..', token: 'me' },
			{ uid: 'MzQ', token: 'a/b' },
			{ uid: '', token: 'abc' },
			{ uid: 'MzQ', token: 'x'.repeat(129) }
		]) {
			expect(path(params)).toBeNull();
		}
	});
});

describe('passwordErrors', () => {
	it('words known codes in order, unknown ones once as the generic refusal', () => {
		expect(passwordErrors(['password_too_short', 'weird', 'other', 'password_missing'])).toEqual([
			'claim.error.password_too_short',
			'claim.error.invalid',
			'claim.error.password_missing'
		]);
	});

	it('words no code at all as the generic refusal', () => {
		expect(passwordErrors(undefined)).toEqual(['claim.error.invalid']);
		expect(passwordErrors([])).toEqual(['claim.error.invalid']);
	});
});

describe('linkAction', () => {
	it('awaits an async landing and gives it the answer, the fetch and the new token', async () => {
		const landing = vi.fn(async (body, context) => `/after/${body.user_id}/${context.token}`);
		const action = linkAction(() => '/claim/u/t/', landing);
		const form = new FormData();
		form.append('password', 'x');
		form.append('confirmation', 'x');
		const fetch = vi.fn(
			async () =>
				new Response(JSON.stringify({ token: 'fresh', user_id: 9 }), {
					status: 200,
					headers: { 'content-type': 'application/json' }
				})
		);
		const event = {
			params: {},
			request: new Request('http://localhost/x', { method: 'POST', body: form }),
			fetch,
			cookies: { set: vi.fn() },
			getClientAddress: () => '203.0.113.7'
		};

		await expect(action(event)).rejects.toMatchObject({ status: 303, location: '/after/9/fresh' });
		expect(landing.mock.calls[0][1].fetch).toBe(event.fetch);
		expect(landing.mock.calls[0][1].token).toBe('fresh');
	});
});
