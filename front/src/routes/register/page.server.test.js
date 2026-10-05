// @vitest-environment node
// The actions read a real Request's form body, so these tests use Node's own FormData and Request.
import { describe, expect, it, vi } from 'vitest';
import { actions, load } from './+page.server.js';
import { registrationPayload } from '$lib/fixtures/registration.js';

vi.mock('$lib/server/urls', () => ({ api: (path) => `http://api${path}` }));

const json = (status, body) =>
	new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });

const cookiesWith = (token = 't') => ({
	get: (name) => (name === 'token' ? token : undefined),
	set: vi.fn(),
	delete: vi.fn()
});

/** A POST of `entries` (name/value pairs, repeats allowed) to the register page's `action`. */
const post = (action, entries) => {
	const form = new FormData();
	for (const [name, value] of entries) form.append(name, value);
	return new Request(`http://x/register?/${action}`, { method: 'POST', body: form });
};

const goodEntries = [
	['skill', 'CARD'], ['skill', 'STR'], ['rating.CARD', '6'], ['rating.STR', '7'],
	['global_level', '8'], ['sport_frequency', 'two_hours'],
	['sport.0.sport', 'Judo'], ['sport.0.level', 'amateur'], ['sport.0.practice', 'no_longer'],
	['sport.0.years', '2'], ['sport.0.months', '6'], ['sport.0.notes', ''],
	['team_with', ''], ['team_avoid', ''], ['dietary_restrictions', ''], ['attendance_confirmed', 'on']
];

describe('register load', () => {
	it('sends a visitor to /login with a 303 and asks nothing', async () => {
		const fetch = vi.fn();
		await expect(load({ fetch, cookies: cookiesWith(null), setHeaders: vi.fn() })).rejects.toMatchObject({
			status: 303,
			location: '/login?next=/register'
		});
		expect(fetch).not.toHaveBeenCalled();
	});

	it('returns the registration form, never cached, asked with the token', async () => {
		const fetch = vi.fn(async () => json(200, registrationPayload));
		const setHeaders = vi.fn();

		const data = await load({ fetch, cookies: cookiesWith(), setHeaders });

		expect(fetch.mock.calls[0][0]).toBe('http://api/registration/');
		expect(fetch.mock.calls[0][1].headers).toEqual({ authorization: 'Token t' });
		expect(data).toEqual({ registration: registrationPayload });
		expect(setHeaders).toHaveBeenCalledWith({ 'cache-control': 'private, no-store' });
	});

	it('sends a dead token to /login too', async () => {
		const fetch = vi.fn(async () => json(401, { detail: 'Invalid token.' }));
		await expect(load({ fetch, cookies: cookiesWith(), setHeaders: vi.fn() })).rejects.toMatchObject({
			status: 303,
			location: '/login?next=/register'
		});
	});

	it('sends someone who cannot register home', async () => {
		const fetch = vi.fn(async () => json(404, { error: 'not_a_person' }));
		await expect(load({ fetch, cookies: cookiesWith(), setHeaders: vi.fn() })).rejects.toMatchObject({
			status: 303,
			location: '/'
		});
	});

	it('lets any other failure reach the error page', async () => {
		const fetch = vi.fn(async () => json(404, { error: 'no_edition' }));
		await expect(load({ fetch, cookies: cookiesWith(), setHeaders: vi.fn() })).rejects.toMatchObject({ status: 404 });
	});
});

describe('register save', () => {
	it('puts the answers as JSON and reports success', async () => {
		const fetch = vi.fn(async () => json(200, registrationPayload));

		const result = await actions.save({ request: post('save', goodEntries), cookies: cookiesWith(), fetch });

		const [url, options] = fetch.mock.calls[0];
		expect(url).toBe('http://api/registration/');
		expect(options.method).toBe('PUT');
		expect(options.headers).toMatchObject({ authorization: 'Token t', 'content-type': 'application/json' });
		expect(JSON.parse(options.body)).toEqual({
			ratings: { CARD: 6, STR: 7 },
			global_level: 8,
			sport_frequency: 'two_hours',
			sports: [{ sport: 'Judo', level: 'amateur', practice: 'no_longer', duration_months: 30, notes: '' }],
			team_with: '',
			team_avoid: '',
			dietary_restrictions: '',
			attendance_confirmed: true
		});
		expect(result).toEqual({ ok: true, action: 'save' });
	});

	it('sends the two team fields as typed', async () => {
		const fetch = vi.fn(async () => json(200, registrationPayload));
		const entries = goodEntries.map(([name, value]) =>
			name === 'team_with' ? [name, 'Léa'] : name === 'team_avoid' ? [name, 'Carl'] : [name, value]
		);

		await actions.save({ request: post('save', entries), cookies: cookiesWith(), fetch });

		const body = JSON.parse(fetch.mock.calls[0][1].body);
		expect(body.team_with).toBe('Léa');
		expect(body.team_avoid).toBe('Carl');
	});

	it('sends the email only when the form had an email field', async () => {
		const fetch = vi.fn(async () => json(200, registrationPayload));

		await actions.save({ request: post('save', [...goodEntries, ['email', ' New@Example.com ']]), cookies: cookiesWith(), fetch });

		expect(JSON.parse(fetch.mock.calls[0][1].body).email).toBe('New@Example.com');
	});

	it("hands the API's codes back as dictionary keys with what was typed", async () => {
		const fetch = vi.fn(async () => json(400, { errors: ['missing_rating', 'attendance_required'] }));
		const entries = goodEntries.filter(([name]) => name !== 'attendance_confirmed' && name !== 'rating.STR');

		const result = await actions.save({ request: post('save', entries), cookies: cookiesWith(), fetch });

		expect(result.status).toBe(400);
		expect(result.data).toMatchObject({
			action: 'save',
			errors: ['register.error.missing_rating', 'register.error.attendance_required']
		});
		expect(result.data.values.ratings).toEqual({ CARD: '6', STR: '' });
		expect(result.data.values.team_with).toBe('');
	});

	it.each([
		[409, { error: 'closed' }, 'register.error.closed'],
		[409, { error: 'not_yet_open' }, 'register.error.not_yet_open'],
		[409, { error: 'removed_by_organiser' }, 'register.error.removed_by_organiser'],
		[429, { detail: 'Throttled' }, 'register.error.throttled'],
		[500, { detail: 'boom' }, 'register.error.failed']
	])('words a %i %j refusal', async (status, body, key) => {
		const fetch = vi.fn(async () => json(status, body));

		const result = await actions.save({ request: post('save', goodEntries), cookies: cookiesWith(), fetch });

		expect(result.status).toBe(status);
		expect(result.data).toMatchObject({ action: 'save', error: key });
		expect(result.data.values).toBeDefined();
	});

	it('hands the typed sports back when the API refuses sixteen of them', async () => {
		const fetch = vi.fn(async () => json(400, { errors: ['too_many_sports'] }));
		const rows = Array.from({ length: 16 }, (_, i) => [`sport.${i}.sport`, `Sport ${i}`]);

		const result = await actions.save({ request: post('save', [...goodEntries.filter(([n]) => !n.startsWith('sport.')), ...rows]), cookies: cookiesWith(), fetch });

		expect(result.status).toBe(400);
		expect(result.data.errors).toEqual(['register.error.too_many_sports']);
		expect(result.data.values.sports).toHaveLength(16);
		expect(JSON.parse(fetch.mock.calls[0][1].body).sports).toHaveLength(16);
	});

	it('refuses without a token', async () => {
		const fetch = vi.fn();

		const result = await actions.save({ request: post('save', goodEntries), cookies: cookiesWith(null), fetch });

		expect(result.status).toBe(403);
		expect(fetch).not.toHaveBeenCalled();
	});
});

describe('register withdraw', () => {
	it('deletes the registration', async () => {
		const fetch = vi.fn(async () => new Response(null, { status: 204 }));

		const result = await actions.withdraw({ request: post('withdraw', []), cookies: cookiesWith(), fetch });

		expect(fetch.mock.calls[0][0]).toBe('http://api/registration/');
		expect(fetch.mock.calls[0][1].method).toBe('DELETE');
		expect(result).toEqual({ ok: true, action: 'withdraw' });
	});

	it('words a placed player refusal', async () => {
		const fetch = vi.fn(async () => json(409, { error: 'has_team' }));

		const result = await actions.withdraw({ request: post('withdraw', []), cookies: cookiesWith(), fetch });

		expect(result.status).toBe(409);
		expect(result.data).toMatchObject({ action: 'withdraw', error: 'register.error.has_team' });
	});
});
